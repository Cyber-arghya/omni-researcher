"""Rigorous unit and live hardware tests for the autonomous hardware profiler.

Validates physical resource detection, nvidia-smi fallback parsing,
failure handling (timeouts, missing binary, corrupted output), and tier resolution
with ZERO fake passes.
"""

import subprocess
from unittest.mock import MagicMock, patch

from src.hardware import PROFILE_PRESETS, HardwareProfiler


def test_profile_presets_integrity() -> None:
    """Verify that all hardware tier presets contain necessary keys."""
    expected_tiers = ["entry_8gb", "enthusiast_16gb", "workstation_24gb_plus", "cloud_hybrid"]
    for tier in expected_tiers:
        assert tier in PROFILE_PRESETS
        cfg = PROFILE_PRESETS[tier]
        assert "fast_model" in cfg
        assert "deep_model" in cfg
        assert "embedding_device" in cfg
        assert "max_context_tokens" in cfg
        assert "crawler_concurrency" in cfg
        assert cfg["max_context_tokens"] >= 4096


def test_probe_system_resources_live() -> None:
    """GENUINE HARDWARE TEST: Probes actual physical host resources without mocking.

    Guarantees that probe_system_resources() executes cleanly on real hardware,
    extracting positive RAM, valid CPU core counts, and non-negative VRAM.
    """
    vram_gb, ram_gb, cpu_cores = HardwareProfiler.probe_system_resources()

    assert isinstance(vram_gb, float)
    assert vram_gb >= 0.0, "VRAM cannot be negative"

    assert isinstance(ram_gb, float)
    assert ram_gb > 1.0, f"Host RAM ({ram_gb} GB) must be greater than 1.0 GB"

    assert isinstance(cpu_cores, int)
    assert cpu_cores >= 1, f"Logical CPU count ({cpu_cores}) must be at least 1"


def test_get_gpu_name_live() -> None:
    """GENUINE HARDWARE TEST: Retrieves the active GPU name on the live host."""
    gpu_name = HardwareProfiler.get_gpu_name()

    assert isinstance(gpu_name, str)
    assert len(gpu_name) > 0, "GPU name must not be empty"
    # Should either be a detected dedicated GPU (e.g. NVIDIA) or fallback string
    assert (
        "Integrated" in gpu_name or "CPU" in gpu_name or "NVIDIA" in gpu_name or "AMD" in gpu_name
    )


def test_probe_system_resources_nvidia_smi_parsing() -> None:
    """Verify exact unit conversion and string parsing from nvidia-smi.

    Simulates PyTorch CUDA unavailable (e.g. CPU wheel) and verifies that
    nvidia-smi reporting '8188' MiB correctly converts to ~7.996 GB VRAM.
    """
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "8188\n"

    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch("subprocess.run", return_value=mock_res) as mock_sub,
    ):
        vram_gb, ram_gb, cpu_cores = HardwareProfiler.probe_system_resources()
        assert mock_sub.called
        assert round(vram_gb, 3) == 7.996
        assert ram_gb > 0.0
        assert cpu_cores >= 1


def test_probe_system_resources_nvidia_smi_corrupted_output() -> None:
    """Verify robust fallback when nvidia-smi returns non-numeric output or errors."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "ERR! GPU Unreachable\n"

    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch("subprocess.run", return_value=mock_res),
    ):
        # Must not raise ValueError; must safely default vram_gb to 0.0
        vram_gb, ram_gb, cpu_cores = HardwareProfiler.probe_system_resources()
        assert vram_gb == 0.0
        assert ram_gb > 0.0
        assert cpu_cores >= 1


def test_probe_system_resources_nvidia_smi_missing_binary() -> None:
    """Verify graceful fallback when nvidia-smi executable is missing."""
    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi not found")),
    ):
        vram_gb, ram_gb, cpu_cores = HardwareProfiler.probe_system_resources()
        assert vram_gb == 0.0
        assert ram_gb > 0.0
        assert cpu_cores >= 1


def test_probe_system_resources_nvidia_smi_timeout() -> None:
    """Verify graceful handling when nvidia-smi command hangs or times out."""
    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2.0),
        ),
    ):
        vram_gb, ram_gb, cpu_cores = HardwareProfiler.probe_system_resources()
        assert vram_gb == 0.0
        assert ram_gb > 0.0
        assert cpu_cores >= 1


def test_get_gpu_name_fallback_cases() -> None:
    """Verify get_gpu_name parsing, non-zero returncode, and exception fallback."""
    # 1. Successful parse from nvidia-smi
    mock_ok = MagicMock()
    mock_ok.returncode = 0
    mock_ok.stdout = "NVIDIA GeForce RTX 4060\n"

    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch("subprocess.run", return_value=mock_ok),
    ):
        name = HardwareProfiler.get_gpu_name()
        assert name == "NVIDIA GeForce RTX 4060"

    # 2. Non-zero exit code
    mock_err = MagicMock()
    mock_err.returncode = 1
    mock_err.stdout = ""

    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch("subprocess.run", return_value=mock_err),
    ):
        name = HardwareProfiler.get_gpu_name()
        assert name == "Integrated / CPU"

    # 3. Subprocess exception (e.g. FileNotFoundError)
    with (
        patch("src.hardware._TORCH_AVAILABLE", False),
        patch("subprocess.run", side_effect=FileNotFoundError()),
    ):
        name = HardwareProfiler.get_gpu_name()
        assert name == "Integrated / CPU"


def test_hardware_profiler_cloud_provider() -> None:
    """Verify that cloud providers map directly to cloud_hybrid tier."""
    assert HardwareProfiler.resolve_tier("auto", provider="nvidia") == "cloud_hybrid"
    assert HardwareProfiler.resolve_tier("auto", provider="openai") == "cloud_hybrid"
    assert HardwareProfiler.resolve_tier("auto", provider="groq") == "cloud_hybrid"


def test_hardware_profiler_explicit_override() -> None:
    """Verify that user explicit profile override takes precedence."""
    assert (
        HardwareProfiler.resolve_tier(requested_profile="workstation_24gb_plus", provider="ollama")
        == "workstation_24gb_plus"
    )
    assert (
        HardwareProfiler.resolve_tier(requested_profile="entry_8gb", provider="ollama")
        == "entry_8gb"
    )
    assert (
        HardwareProfiler.resolve_tier(requested_profile="enthusiast_16gb", provider="ollama")
        == "enthusiast_16gb"
    )


def test_hardware_tier_boundary_resolution() -> None:
    """Verify deterministic mapping across exact VRAM and RAM boundary thresholds."""
    # 0GB VRAM, 8GB RAM -> entry_8gb
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(0.0, 8.0, 4)):
        assert HardwareProfiler.resolve_tier("auto", "ollama") == "entry_8gb"

    # 8GB VRAM, 16GB RAM -> entry_8gb
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(8.0, 16.0, 8)):
        assert HardwareProfiler.resolve_tier("auto", "ollama") == "entry_8gb"

    # 16GB VRAM, 32GB RAM -> enthusiast_16gb
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(16.0, 32.0, 16)):
        assert HardwareProfiler.resolve_tier("auto", "ollama") == "enthusiast_16gb"

    # 24GB VRAM, 64GB RAM -> workstation_24gb_plus
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(24.0, 64.0, 32)):
        assert HardwareProfiler.resolve_tier("auto", "ollama") == "workstation_24gb_plus"


def test_get_tier_config() -> None:
    """Verify get_tier_config returns complete parameter mapping."""
    cfg = HardwareProfiler.get_tier_config(requested_profile="entry_8gb", provider="ollama")
    assert cfg["resolved_tier"] == "entry_8gb"
    assert cfg["fast_model"] == "llama3.2:3b"
    assert cfg["deep_model"] == "qwen2.5:7b"
    assert cfg["embedding_device"] == "cpu"
    assert cfg["crawler_concurrency"] == 3
