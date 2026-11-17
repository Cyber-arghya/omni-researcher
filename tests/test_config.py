"""Unit tests for configuration validation and path handling."""

from pathlib import Path

from src.config import Settings


def test_default_settings(tmp_path: Path) -> None:
    """Verify default settings instantiation and path creation."""
    s = Settings(
        storage_dir=tmp_path / "storage",
        reports_dir=tmp_path / "reports",
        chroma_persist_dir=tmp_path / "storage" / "vector_db",
    )
    s.ensure_directories()

    assert s.storage_dir.exists()
    assert s.reports_dir.exists()
    assert s.chroma_persist_dir.exists()
    assert s.is_local_mode is True
    assert s.max_cost_limit_usd >= 0.1
    assert s.max_total_tokens >= 1000


def test_cost_calculation(tmp_path: Path) -> None:
    """Verify ResearchState cost calculation logic."""
    from src.state.schemas import ResearchState

    state = ResearchState(session_id="test_cost", topic="Test Topic")
    assert state.estimated_cost_usd == 0.0

    # Local model cost is 0.0
    state.record_cost(1000, 500, "llama3.2:latest")
    assert state.total_tokens_used == 1500
    assert state.estimated_cost_usd == 0.0

    # Cloud model cost accumulation
    state.record_cost(1000, 1000, "gpt-4o")
    assert state.total_tokens_used == 3500
    assert state.estimated_cost_usd > 0.0


def test_nvidia_settings_and_router(tmp_path: Path) -> None:
    """Verify NVIDIA NIM configuration and ModelRouter initialization."""
    from src.llm.router import ModelRouter

    s = Settings(
        llm_provider="nvidia",
        nvidia_api_key="nvapi-test-key",
        nvidia_model="nvidia/nemotron-3-ultra-550b-a55b",
        storage_dir=tmp_path / "storage",
        reports_dir=tmp_path / "reports",
    )
    assert s.llm_provider == "nvidia"
    assert s.nvidia_api_key == "nvapi-test-key"
    assert s.nvidia_base_url == "https://integrate.api.nvidia.com/v1"

    router = ModelRouter()
    assert router.client is not None
