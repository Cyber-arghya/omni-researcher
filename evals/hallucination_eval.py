"""Hallucination detection and factual consistency scoring."""

import re

from src.state.schemas import ResearchReport


def evaluate_hallucination_index(report: ResearchReport) -> dict[str, float | int]:
    """Audit citations in the report to ensure all cited references exist in the source index."""
    body = report.chapters[0]["content_markdown"] if report.chapters else ""

    # Find all footnote citations [^1], [^2], etc.
    cited_numbers = set(re.findall(r"\[\^(\d+)\]", body))
    available_sources = len(report.citations)

    unmatched_citations: list[str] = []
    for num_str in cited_numbers:
        ref_idx = int(num_str)
        # Footnotes are 1-indexed
        if ref_idx < 1 or ref_idx > available_sources:
            unmatched_citations.append(f"[^{num_str}]")

    phantom_ratio = len(unmatched_citations) / max(1, len(cited_numbers))
    grounding_score = max(0.0, 1.0 - phantom_ratio)

    return {
        "unique_citations_in_text": len(cited_numbers),
        "available_grounded_sources": available_sources,
        "phantom_unmatched_citations": len(unmatched_citations),
        "grounding_confidence_score": round(grounding_score, 3),
    }
