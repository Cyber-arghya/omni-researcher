"""Comprehensive unit tests for SessionStore, BundleExporter, ContextDistiller, and mission controls."""

import tempfile
import zipfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from src.exporters.bundle_exporter import BundleExporter
from src.rag.distiller import ContextDistiller
from src.server import SESSIONS, app
from src.state.schemas import ResearchState, ScrapedDocument
from src.state.session_store import SessionStore


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_session_store_lifecycle() -> None:
    """Test non-volatile SQLite persistence operations, updates, and deletion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_sessions.db"
        store = SessionStore(db_path=db_path)

        state = ResearchState(
            session_id="test_sess_001",
            topic="Solid State Electrolytes",
            target_depth=2,
            current_depth=1,
            status="SEARCHING",
        )

        # 1. Upsert
        store.upsert_session(state, report_payload={"markdown_content": "# Intro"})
        retrieved = store.get_session("test_sess_001")
        assert retrieved is not None
        assert retrieved["topic"] == "Solid State Electrolytes"
        assert retrieved["report_payload"]["markdown_content"] == "# Intro"

        # 2. Update existing session
        state.status = "COMPLETED"
        store.upsert_session(state, report_payload={"markdown_content": "# Final"})
        retrieved_updated = store.get_session("test_sess_001")
        assert retrieved_updated is not None
        assert retrieved_updated["status"] == "COMPLETED"
        assert retrieved_updated["report_payload"]["markdown_content"] == "# Final"

        # 3. List
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test_sess_001"

        # 4. Non-existent session returns None
        assert store.get_session("non_existent_id") is None

        # 5. Delete non-existent session returns False
        assert store.delete_session("non_existent_id") is False

        # 6. Delete existing session returns True
        assert store.delete_session("test_sess_001") is True
        assert store.get_session("test_sess_001") is None

        # 7. Clear all
        store.upsert_session(state)
        assert store.clear_all() == 1
        assert len(store.list_sessions()) == 0


def test_bundle_exporter_zip_structure() -> None:
    """Verify that BundleExporter generates valid, non-empty ZIP archive with all assets."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = BundleExporter(sessions_dir=Path(tmp_dir))
        state = ResearchState(
            session_id="bundle_test_01",
            topic="Quantum Dot LEDs",
            target_depth=2,
            status="COMPLETED",
        )
        state.collected_documents.append(
            ScrapedDocument(
                id="doc_qled_01",
                url="https://example.com/qled",
                title="QLED Advances",
                clean_text="Quantum dots provide high color purity and energy efficiency.",
            )
        )

        report_payload = {
            "markdown_content": "# Quantum Dot LEDs\nBreakthroughs in stability.",
            "latex_content": "\\section{Intro}\nQuantum dots.",
            "audio_script": "Host: Welcome to the QLED briefing.",
            "bibtex": ["@article{qled2026, title={Advances}}"],
        }

        zip_path = exporter.export_bundle(state, report_payload)
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            assert "01_Executive_Summary.md" in names
            assert "02_Academic_Paper.tex" in names
            assert "03_References.bib" in names
            assert "04_Podcast_Dialogue.txt" in names
            assert "metadata.json" in names
            assert any(n.startswith("sources/") for n in names)


def test_context_distiller_deduplication_and_ranking() -> None:
    """Test MinHash-style deduplication and zero-VRAM lexical scoring."""
    sample_text = (
        "We use cookies to improve your user experience on this website.\n\n"
        "Perovskite solar cells exhibit high power conversion efficiency over 26%.\n\n"
        "Perovskite solar cells exhibit high power conversion efficiency over 26%.\n\n"
        "Subscribe to our weekly renewable energy newsletter.\n\n"
        "Degradation occurs primarily due to moisture and thermal decomposition under 85C."
    )

    condensed = ContextDistiller.deduplicate_paragraphs(sample_text)
    assert "cookies" not in condensed.lower()
    assert "subscribe" not in condensed.lower()
    assert condensed.count("power conversion efficiency") == 1
    assert "moisture and thermal decomposition" in condensed

    # Test lexical zero-vram ranking
    chunks = [
        {"text": "Quantum computing enables Shor's algorithm for prime factorization."},
        {"text": "The weather today in New York is cloudy with light rain."},
        {"text": "Superconducting qubits require dilution refrigerators at 15 millikelvin."},
    ]
    ranked = ContextDistiller.rank_chunks_zero_vram(chunks, query="quantum qubit dilution", top_k=2)
    assert len(ranked) == 2
    assert "millikelvin" in ranked[0]["text"] or "Shor's algorithm" in ranked[0]["text"]

    # Edge cases: empty chunks or empty query
    assert ContextDistiller.rank_chunks_zero_vram([], query="test") == []
    empty_q_ranked = ContextDistiller.rank_chunks_zero_vram(chunks, query="")
    assert len(empty_q_ranked) > 0


def test_server_cancel_and_delete_endpoints(client: TestClient) -> None:
    """Test emergency cancellation, single deletion, 404s, and bulk purge APIs."""
    state = ResearchState(
        session_id="cancel_session_123",
        topic="Neuromorphic Computing",
        target_depth=2,
    )
    SESSIONS["cancel_session_123"] = state

    # 1. Test Cancel
    cancel_resp = client.post("/api/sessions/cancel_session_123/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "ABORTED"
    assert SESSIONS["cancel_session_123"].status == "ABORTED"

    # Cancel non-existent session returns 404
    bad_cancel = client.post("/api/sessions/unknown_123/cancel")
    assert bad_cancel.status_code == 404

    # 2. Test Bundle Download
    bundle_resp = client.get("/api/sessions/cancel_session_123/bundle")
    assert bundle_resp.status_code == 200
    assert bundle_resp.headers["content-type"] == "application/zip"

    # Bundle for non-existent session returns 404
    bad_bundle = client.get("/api/sessions/unknown_bundle_id/bundle")
    assert bad_bundle.status_code == 404

    # 3. Test Delete Individual Session
    del_resp = client.delete("/api/sessions/cancel_session_123")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
    assert "cancel_session_123" not in SESSIONS

    # Delete non-existent session returns 404
    bad_del = client.delete("/api/sessions/unknown_to_delete")
    assert bad_del.status_code == 404

    # 4. Test Bulk Purge
    SESSIONS["temp_1"] = ResearchState(session_id="temp_1", topic="Topic 1")
    SESSIONS["temp_2"] = ResearchState(session_id="temp_2", topic="Topic 2")
    clear_resp = client.delete("/api/history")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "CLEARED"
    assert len(SESSIONS) == 0
