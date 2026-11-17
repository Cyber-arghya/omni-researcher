"""Autonomous hardware detection and dynamic resource allocation profiler."""

import logging
import subprocess
from typing import Any, Literal

import psutil

try:
    import torch

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

HardwareTier = Literal["entry_8gb", "enthusiast_16gb", "workstation_24gb_plus", "cloud_hybrid"]

PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "entry_8gb": {
        "fast_model": "llama3.2:3b",
        "deep_model": "qwen2.5:7b",
        "embedding_device": "cpu",
        "max_context_tokens": 8192,
        "crawler_concurrency": 3,
        "crawler_batch_size": 3,
        "vision_strategy": "sequential",
        "description": "Optimized for <= 8GB VRAM & <= 16GB RAM. CPU embeddings, quantized KV cache.",
    },
    "enthusiast_16gb": {
        "fast_model": "llama3.1:8b",
        "deep_model": "qwen2.5:14b",
        "embedding_device": "cuda",
        "max_context_tokens": 16384,
        "crawler_concurrency": 6,
        "crawler_batch_size": 6,
        "vision_strategy": "concurrent",
        "description": "Optimized for 12GB-16GB VRAM & 32GB RAM. GPU embeddings, dual browser workers.",
    },
    "workstation_24gb_plus": {
        "fast_model": "qwen2.5:14b",
        "deep_model": "qwen2.5:32b",
        "embedding_device": "cuda",
        "max_context_tokens": 32768,
        "crawler_concurrency": 12,
        "crawler_batch_size": 10,
        "vision_strategy": "concurrent",
        "description": "High-end 24GB+ VRAM & 64GB+ RAM. 32B+ reasoning models, 12 concurrent crawlers.",
    },
    "cloud_hybrid": {
        "fast_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "deep_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "embedding_device": "cpu",
        "max_context_tokens": 64000,
        "crawler_concurrency": 6,
        "crawler_batch_size": 6,
        "vision_strategy": "cloud",
        "description": "Zero local VRAM footprint. Heavy inference offloaded to NVIDIA NIM or cloud APIs.",
    },
}


class HardwareProfiler:
    """Probes physical host resources and dynamically determines optimal execution parameters."""

    @classmethod
    def get_gpu_name(cls) -> str:
        """Retrieve the GPU model name via PyTorch or nvidia-smi."""
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            try:
                return str(torch.cuda.get_device_name(0))
            except Exception:
                pass

        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                check=False,
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip().splitlines()[0].strip()
        except Exception:
            pass

        return "Integrated / CPU"

    @classmethod
    def probe_system_resources(cls) -> tuple[float, float, int]:
        """Inspect host physical resources.

        Returns:
            Tuple of (vram_gb, ram_gb, logical_cpu_cores)
        """
        ram_gb = psutil.virtual_memory().total / (1024**3)
        cpu_cores = psutil.cpu_count(logical=True) or 4

        vram_gb = 0.0
        # 1. Try PyTorch CUDA if available
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            try:
                vram_bytes = torch.cuda.get_device_properties(0).total_memory
                vram_gb = vram_bytes / (1024**3)
            except Exception as e:
                logger.debug("CUDA memory query failed: %s", str(e))

        # 2. Hardware fallback: Query nvidia-smi directly (e.g. for CPU-only torch wheels)
        if vram_gb == 0.0:
            try:
                res = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=2.0,
                )
                if res.returncode == 0 and res.stdout.strip():
                    first_line = res.stdout.strip().splitlines()[0]
                    vram_mib = float(first_line.strip())
                    vram_gb = vram_mib / 1024.0
            except Exception as e:
                logger.debug("nvidia-smi probe failed: %s", str(e))

        return vram_gb, ram_gb, cpu_cores

    @classmethod
    def resolve_tier(
        cls,
        requested_profile: str = "auto",
        provider: str = "ollama",
    ) -> HardwareTier:
        """Deterministically map available system resources to a HardwareTier."""
        if requested_profile in PROFILE_PRESETS:
            return requested_profile  # type: ignore[return-value]

        # Cloud-backed execution needs zero local GPU VRAM
        if provider in ["nvidia", "openai", "gemini", "anthropic", "deepseek", "groq"]:
            return "cloud_hybrid"

        vram_gb, ram_gb, _ = cls.probe_system_resources()

        if vram_gb >= 22.0 and ram_gb >= 48.0:
            return "workstation_24gb_plus"
        elif (vram_gb >= 10.0 and ram_gb >= 24.0) or (vram_gb == 0.0 and ram_gb >= 32.0):
            return "enthusiast_16gb"
        else:
            return "entry_8gb"

    @classmethod
    def get_tier_config(
        cls,
        requested_profile: str = "auto",
        provider: str = "ollama",
    ) -> dict[str, Any]:
        """Return the complete runtime parameter dictionary for the resolved hardware tier."""
        tier = cls.resolve_tier(requested_profile, provider)
        preset = dict(PROFILE_PRESETS[tier])
        preset["resolved_tier"] = tier

        # Safety override: if CUDA is not physically available, force embedding_device to CPU
        if not (_TORCH_AVAILABLE and torch.cuda.is_available()):
            preset["embedding_device"] = "cpu"

        logger.info(
            "HardwareProfiler resolved tier '%s': %s (RAM: %.1f GB, VRAM: %.1f GB)",
            tier,
            preset["description"],
            *cls.probe_system_resources()[:2],
        )
        return preset
