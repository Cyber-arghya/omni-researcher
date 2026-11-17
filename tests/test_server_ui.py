"""Unit and integration tests for FastAPI Server, Cockpit UI routes, SSE, and hardware APIs."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from src.config import settings
from src.server import SESSIONS, app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_serve_cockpit_ui(client: TestClient) -> None:
    """Test root endpoint serves the HTML5 Cockpit interface."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "OpenDeepResearcher" in resp.text
    assert "GraphRAG" in resp.text
    assert "header-hardware-badge" in resp.text


def test_get_hardware_status(client: TestClient) -> None:
    """Test /api/hardware/status returns hardware telemetry and active preset."""
    resp = client.get("/api/hardware/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_tier" in data
    assert "vram_gb" in data
    assert "ram_gb" in data
    assert "cpu_cores" in data
    assert "preset" in data
    assert "max_concurrent_crawlers" in data["preset"]


def test_set_hardware_profile(client: TestClient) -> None:
    """Test manual hardware profile override via /api/hardware/profile."""
    resp = client.post("/api/hardware/profile", json={"profile": "enthusiast_16gb"})
    assert resp.status_code == 200
    assert resp.json()["hardware_profile"] == "enthusiast_16gb"
    assert settings.hardware_profile == "enthusiast_16gb"

    # Test invalid profile rejection
    bad_resp = client.post("/api/hardware/profile", json={"profile": "invalid_supercomputer"})
    assert bad_resp.status_code == 400


def test_get_and_update_config(client: TestClient) -> None:
    """Test GET and POST on /api/config."""
    get_resp = client.get("/api/config")
    assert get_resp.status_code == 200
    cfg = get_resp.json()
    assert "llm_provider" in cfg
    assert "max_cost_limit_usd" in cfg

    post_resp = client.post(
        "/api/config",
        json={
            "llm_provider": "nvidia",
            "max_cost_limit_usd": 5.0,
        },
    )
    assert post_resp.status_code == 200
    updated = post_resp.json()["config"]
    assert updated["llm_provider"] == "nvidia"
    assert updated["max_cost_limit_usd"] == 5.0


def test_ping_ollama(client: TestClient) -> None:
    """Test /api/health/ollama ping endpoint."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_get.return_value = mock_resp

        resp = client.get("/api/health/ollama")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "llama3.2:latest" in data["models"]


def test_start_research_and_sessions(client: TestClient) -> None:
    """Test session lifecycle from start to steering and retrieval."""
    with patch("src.server._run_research_background", new_callable=AsyncMock):
        resp = client.post("/api/research", json={"topic": "Quantum Computing", "depth": 2})
        assert resp.status_code == 200
        data = resp.json()
        session_id = data["session_id"]
        assert data["status"] == "INITIALIZED"
        assert data["topic"] == "Quantum Computing"

        # Check session status
        status_resp = client.get(f"/api/sessions/{session_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["session_id"] == session_id

        # Steer session
        steer_resp = client.post(
            f"/api/sessions/{session_id}/steer",
            json={"action": "PIVOT", "feedback": "Focus on topological qubits"},
        )
        assert steer_resp.status_code == 200
        state = SESSIONS[session_id]
        assert "Focus on topological qubits" in state.user_constraints

        # Check history endpoint
        hist_resp = client.get("/api/history")
        assert hist_resp.status_code == 200
        history_items = hist_resp.json()
        assert any(item["session_id"] == session_id for item in history_items)


def test_session_not_found(client: TestClient) -> None:
    """Test 404 behavior for unknown sessions."""
    resp = client.get("/api/sessions/non_existent_session")
    assert resp.status_code == 404
