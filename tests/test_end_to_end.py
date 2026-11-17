"""End-to-end integration test verifying the full deep research loop, multi-format exporters, and hallucination audits."""

from pathlib import Path

from evals.citation_accuracy import evaluate_citation_coverage
from evals.hallucination_eval import evaluate_hallucination_index

from src.agents.fact_checker import FactCheckerAgent
from src.exporters.audio_script import AudioScriptExporter
from src.exporters.html_export import HTMLExporter
from src.exporters.latex_export import LatexExporter
from src.exporters.markdown_export import MarkdownExporter
from src.state.schemas import (
    ResearchReport,
    ResearchState,
    ScrapedDocument,
    SearchQuery,
)


def test_end_to_end_research_pipeline_happy_path(tmp_path: Path) -> None:
    """Verify that a grounded research session generates valid multi-format export files."""
    state = ResearchState(
        session_id="integration_test_001",
        topic="Next-Gen Solid-State Battery Solid Electrolyte Benchmarks",
        target_depth=1,
    )

    # 1. Setup mock document and citations
    doc = ScrapedDocument(
        id="doc_123",
        url="https://nature.com/articles/solid-state-breakthrough",
        title="Nature: Solid-State Battery Breakthrough",
        clean_text="Sulfide electrolytes achieve ionic conductivity exceeding 25 mS/cm at room temperature.",
    )
    state.collected_documents.append(doc)
    state.search_queries.append(
        SearchQuery(query="solid state ionic conductivity", perspective="Technical")
    )

    # 2. Test FactChecker grounding
    fact_checker = FactCheckerAgent()
    mock_report = ResearchReport(
        topic=state.topic,
        title=f"Autonomous Deep Research: {state.topic}",
        executive_summary="Sulfide solid electrolytes have achieved 25 mS/cm conductivity.",
        chapters=[
            {
                "chapter_title": "Analysis",
                "content_markdown": "Recent experiments confirm [REF_ID:1] that sulfide electrolytes reach 25 mS/cm.",
            }
        ],
        citations=[
            {
                "id": "[REF_ID:1]",
                "url": doc.url,
                "title": doc.title,
                "snippet": doc.clean_text,
            }
        ],
        bibtex_entries=[
            "@article{doc_123,\n  title={Nature: Solid-State Battery Breakthrough},\n  url={https://nature.com/articles/solid-state-breakthrough}\n}"
        ],
        model_used="test-model",
        total_sources_consulted=1,
    )

    grounded_text = fact_checker.verify_and_ground_citations(mock_report)
    assert "[^1]" in grounded_text
    assert "[REF_ID:1]" not in grounded_text
    assert doc.url in grounded_text

    # 3. Test Exporters
    md_exporter = MarkdownExporter()
    md_file = md_exporter.export(mock_report, output_dir=tmp_path)
    assert md_file.exists()
    assert md_file.stat().st_size > 100

    html_exporter = HTMLExporter()
    html_file = html_exporter.export(mock_report, output_dir=tmp_path)
    assert html_file.exists()
    assert "mermaid" in html_file.read_text(encoding="utf-8")

    latex_exporter = LatexExporter()
    tex_file, bib_file = latex_exporter.export(mock_report, output_dir=tmp_path)
    assert tex_file.exists()
    assert bib_file.exists()
    assert "\\begin{document}" in tex_file.read_text(encoding="utf-8")

    audio_exporter = AudioScriptExporter()
    audio_file = audio_exporter.export(mock_report, output_dir=tmp_path)
    assert audio_file.exists()
    assert "ALEX" in audio_file.read_text(encoding="utf-8")

    # 4. Test Evaluation Benchmarks
    coverage_metrics = evaluate_citation_coverage(mock_report)
    assert coverage_metrics["total_sources"] == 1
    assert coverage_metrics["cited_sentences"] >= 1

    hallucination_metrics = evaluate_hallucination_index(mock_report)
    assert hallucination_metrics["grounding_confidence_score"] == 1.0
    assert hallucination_metrics["phantom_unmatched_citations"] == 0


def test_hallucination_index_catches_phantom_citations() -> None:
    """Verify that evaluate_hallucination_index catches fabricated/phantom citations."""
    hallucinated_report = ResearchReport(
        topic="Cold Fusion",
        title="Cold Fusion Advances",
        executive_summary="Unverified room temperature fusion claims.",
        chapters=[
            {
                "chapter_title": "Claims",
                "content_markdown": "We observed anomalous heat [^1] and massive neutron flux [^99] without shielding [^42].",
            }
        ],
        # Only source 1 is present in the bibliography; [^99] and [^42] are fabricated!
        citations=[
            {
                "id": "[^1]",
                "url": "https://example.com/source1",
                "title": "Legit Source",
                "snippet": "Anomalous heat.",
            }
        ],
        model_used="hallucinating-llm",
        total_sources_consulted=1,
    )

    metrics = evaluate_hallucination_index(hallucinated_report)
    assert metrics["phantom_unmatched_citations"] == 2
    assert metrics["grounding_confidence_score"] < 1.0


def test_citation_coverage_on_empty_report() -> None:
    """Verify that citation coverage audit handles empty reports gracefully without division by zero."""
    empty_report = ResearchReport(
        topic="Empty Topic",
        title="Empty",
        executive_summary="",
        chapters=[],
        citations=[],
        model_used="test",
        total_sources_consulted=0,
    )
    metrics = evaluate_citation_coverage(empty_report)
    assert metrics["total_sources"] == 0
    assert metrics["cited_sentences"] == 0
