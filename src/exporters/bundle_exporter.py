"""Safe disk-backed ZIP research bundle exporter."""

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

from src.state.schemas import ResearchState

logger = logging.getLogger(__name__)

DEFAULT_SESSIONS_DIR = Path("./storage/sessions")


class BundleExporter:
    """Consolidates research dossiers, extracted tables, and source texts into a single ZIP archive."""

    def __init__(self, sessions_dir: Path = DEFAULT_SESSIONS_DIR) -> None:
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def export_bundle(
        self, state: ResearchState, report_payload: dict[str, Any] | None = None
    ) -> Path:
        """Create a compressed research archive (.zip) on disk."""
        session_id = state.session_id
        session_folder = self.sessions_dir / session_id
        session_folder.mkdir(parents=True, exist_ok=True)

        zip_path = session_folder / f"research_bundle_{session_id}.zip"

        report = report_payload or {}
        md_text = report.get("markdown_content") or (
            state.final_report.chapters[0]["content_markdown"]
            if state.final_report and state.final_report.chapters
            else ""
        )
        latex_text = report.get("latex_content", "")
        audio_script = report.get("audio_script", "")
        bibtex_entries = report.get("bibtex", [])

        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Executive Summary & Full Markdown Dossier
            if md_text:
                zip_file.writestr("01_Executive_Summary.md", md_text)

            # 2. Academic LaTeX Document
            if latex_text:
                zip_file.writestr("02_Academic_Paper.tex", latex_text)

            # 3. BibTeX Citation Ledger
            if bibtex_entries:
                zip_file.writestr("03_References.bib", "\n\n".join(bibtex_entries))

            # 4. Audio Briefing Script
            if audio_script:
                zip_file.writestr("04_Podcast_Dialogue.txt", audio_script)

            # 5. Metadata & Telemetry Audit
            metadata = {
                "session_id": session_id,
                "topic": state.topic,
                "target_depth": state.target_depth,
                "status": state.status,
                "total_tokens_used": state.total_tokens_used,
                "estimated_cost_usd": state.estimated_cost_usd,
                "documents_collected": len(state.collected_documents),
            }
            zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))

            # 6. Discovered Sources & Scraped Documents
            for idx, doc in enumerate(state.collected_documents, 1):
                clean_snippet = doc.clean_text or doc.raw_markdown or ""
                doc_meta = f"Title: {doc.title}\nURL: {doc.url}\nWord Count: {len(clean_snippet.split())}\n\n"
                zip_file.writestr(
                    f"sources/source_{idx:02d}_{abs(hash(doc.url)) % 10000}.txt",
                    doc_meta + clean_snippet,
                )

            # 7. Knowledge Graph (if exists on disk)
            kg_path = Path("./storage/knowledge_graph.json")
            if kg_path.exists():
                zip_file.write(kg_path, arcname="05_Knowledge_Graph.json")

        logger.info(
            "Successfully exported research bundle for session %s at %s", session_id, zip_path
        )
        return zip_path
