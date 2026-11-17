"""Unit tests for the autonomous hardware profiler and dynamic resource allocation."""

from unittest.mock import patch

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


def test_hardware_profiler_cloud_provider() -> None:
    """Verify that cloud providers map directly to cloud_hybrid tier."""
    tier = HardwareProfiler.resolve_tier(requested_profile="auto", provider="nvidia")
    assert tier == "cloud_hybrid"

    tier_openai = HardwareProfiler.resolve_tier(requested_profile="auto", provider="openai")
    assert tier_openai == "cloud_hybrid"


def test_hardware_profiler_explicit_override() -> None:
    """Verify that user explicit profile override takes precedence."""
    tier = HardwareProfiler.resolve_tier(
        requested_profile="workstation_24gb_plus", provider="ollama"
    )
    assert tier == "workstation_24gb_plus"

    tier_entry = HardwareProfiler.resolve_tier(requested_profile="entry_8gb", provider="ollama")
    assert tier_entry == "entry_8gb"


def test_hardware_profiler_dynamic_tier_detection() -> None:
    """Verify dynamic tier detection under simulated hardware specs."""
    # Simulation 1: Laptop with 8GB VRAM and 16GB RAM -> entry_8gb
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(8.0, 16.0, 8)):
        tier = HardwareProfiler.resolve_tier(requested_profile="auto", provider="ollama")
        assert tier == "entry_8gb"

    # Simulation 2: Enthusiast with 16GB VRAM and 32GB RAM -> enthusiast_16gb
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(16.0, 32.0, 16)):
        tier = HardwareProfiler.resolve_tier(requested_profile="auto", provider="ollama")
        assert tier == "enthusiast_16gb"

    # Simulation 3: Workstation with 24GB VRAM and 64GB RAM -> workstation_24gb_plus
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(24.0, 64.0, 32)):
        tier = HardwareProfiler.resolve_tier(requested_profile="auto", provider="ollama")
        assert tier == "workstation_24gb_plus"


def test_get_tier_config() -> None:
    """Verify get_tier_config returns complete parameter mapping."""
    with patch.object(HardwareProfiler, "probe_system_resources", return_value=(8.0, 16.0, 8)):
        cfg = HardwareProfiler.get_tier_config(requested_profile="entry_8gb", provider="ollama")
        assert cfg["resolved_tier"] == "entry_8gb"
        assert cfg["fast_model"] == "llama3.2:3b"
        assert cfg["deep_model"] == "qwen2.5:7b"
        assert cfg["embedding_device"] == "cpu"
        assert cfg["crawler_concurrency"] == 3
