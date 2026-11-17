"""Pytest fixtures and test environment setup."""

from pathlib import Path

import pytest

from src.config import Settings
from src.state.schemas import ResearchState


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Fixture providing isolated temporary settings paths."""
    return Settings(
        llm_provider="ollama",
        storage_dir=tmp_path / "storage",
        reports_dir=tmp_path / "reports",
        chroma_persist_dir=tmp_path / "storage" / "vector_db",
        sqlite_db_path=tmp_path / "storage" / "cache.db",
        knowledge_graph_path=tmp_path / "storage" / "knowledge_graph.json",
        max_cost_limit_usd=2.0,
        max_total_tokens=50000,
    )


@pytest.fixture
def mock_research_state() -> ResearchState:
    """Fixture providing an initial ResearchState instance."""
    return ResearchState(
        session_id="test_session_123",
        topic="Solid-State Battery Energy Density Benchmarks 2026",
        user_constraints="Focus on commercial vehicle applications",
        target_depth=2,
    )
