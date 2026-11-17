"""Comprehensive unit tests for configuration settings, provider routing, and ResearchState cost metrics."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.llm.router import ModelRouter
from src.state.schemas import ResearchState


def test_default_settings(tmp_path: Path) -> None:
    """Verify default settings instantiation and directory creation."""
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
    assert s.llm_provider == "ollama"


def test_provider_settings_configurations(tmp_path: Path) -> None:
    """Verify settings validation across diverse cloud and local providers."""
    providers = ["openai", "gemini", "groq", "deepseek", "nvidia", "lmstudio"]
    for prov in providers:
        s = Settings(
            llm_provider=prov,  # type: ignore[arg-type]
            storage_dir=tmp_path / prov,
            reports_dir=tmp_path / f"{prov}_reports",
        )
        assert s.llm_provider == prov

    # Invalid provider must raise ValidationError
    with pytest.raises(ValidationError):
        Settings(llm_provider="non_existent_provider")  # type: ignore[arg-type]


def test_cost_calculation_across_models() -> None:
    """Verify token usage tracking and price calculations across different model families."""
    state = ResearchState(session_id="cost_test_01", topic="Superconductors")
    assert state.estimated_cost_usd == 0.0
    assert state.total_tokens_used == 0

    # 1. Local model is always $0.00
    state.record_cost(prompt_tokens=2000, completion_tokens=1000, model_name="llama3.2:latest")
    assert state.total_tokens_used == 3000
    assert state.estimated_cost_usd == 0.0

    # 2. GPT-4o / Claude 3.5 pricing ($2.50 / $10.00 per 1M)
    state.record_cost(prompt_tokens=1000, completion_tokens=500, model_name="gpt-4o")
    expected_gpt4_cost = (1000 * 2.50 + 500 * 10.0) / 1_000_000
    assert abs(state.estimated_cost_usd - expected_gpt4_cost) < 1e-6
    assert state.total_tokens_used == 4500

    # 3. Gemini / Flash pricing ($0.15 / $0.60 per 1M)
    prev_cost = state.estimated_cost_usd
    state.record_cost(prompt_tokens=10_000, completion_tokens=2_000, model_name="gemini-1.5-flash")
    expected_gemini_cost = (10_000 * 0.15 + 2_000 * 0.60) / 1_000_000
    assert abs(state.estimated_cost_usd - (prev_cost + expected_gemini_cost)) < 1e-6

    # 4. DeepSeek pricing ($0.27 / $1.10 per 1M)
    prev_cost = state.estimated_cost_usd
    state.record_cost(prompt_tokens=5_000, completion_tokens=1_000, model_name="deepseek-v3")
    expected_ds_cost = (5_000 * 0.27 + 1_000 * 1.10) / 1_000_000
    assert abs(state.estimated_cost_usd - (prev_cost + expected_ds_cost)) < 1e-6


def test_research_state_depth_and_status_constraints() -> None:
    """Verify validation constraints on target_depth and valid statuses."""
    # Valid state initialization
    state = ResearchState(
        session_id="valid_state",
        topic="Solid state electrolytes",
        target_depth=3,
        status="INITIALIZED",
    )
    assert state.target_depth == 3
    assert state.status == "INITIALIZED"

    # target_depth < 1 must be rejected by Pydantic ge=1
    with pytest.raises(ValidationError):
        ResearchState(session_id="bad_depth", topic="Test", target_depth=0)

    # target_depth > 5 must be rejected by Pydantic le=5
    with pytest.raises(ValidationError):
        ResearchState(session_id="bad_depth", topic="Test", target_depth=6)

    # Invalid status must be rejected
    with pytest.raises(ValidationError):
        ResearchState(session_id="bad_status", topic="Test", status="INVALID_STATUS")  # type: ignore[arg-type]


def test_model_router_initialization() -> None:
    """Verify ModelRouter initializes with active provider client."""
    router = ModelRouter()
    assert router.client is not None
    assert router.fast_model is not None
    assert router.deep_model is not None
