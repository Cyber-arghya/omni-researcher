"""Citation accuracy and grounding evaluation metric."""

import re

from src.state.schemas import ResearchReport


def evaluate_citation_coverage(report: ResearchReport) -> dict[str, float | int]:
    """Calculate the citation density and citation grounding ratio.

    Returns:
        Dict with metrics:
        - total_sentences: count of statements
        - cited_sentences: count of sentences with a [^n] or [REF_ID:n] citation
        - citation_density: ratio of cited sentences
        - total_sources: number of unique sources referenced
    """
    body = report.chapters[0]["content_markdown"] if report.chapters else report.executive_summary

    # Split into rough sentences
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", body) if len(s.strip()) > 20]
    total_sentences = len(sentences)

    if total_sentences == 0:
        return {
            "total_sentences": 0,
            "cited_sentences": 0,
            "citation_density": 0.0,
            "total_sources": 0,
        }

    cited_sentences = sum(1 for s in sentences if re.search(r"(\[\^\d+\]|\[REF_ID:\d+\])", s))
    density = cited_sentences / total_sentences

    return {
        "total_sentences": total_sentences,
        "cited_sentences": cited_sentences,
        "citation_density": round(density, 3),
        "total_sources": len(report.citations),
    }
