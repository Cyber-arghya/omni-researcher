"""Benchmark runner for evaluating deep research report quality and grounding."""

import json

from evals.citation_accuracy import evaluate_citation_coverage
from evals.hallucination_eval import evaluate_hallucination_index
from src.state.schemas import ResearchReport


def benchmark_report(report: ResearchReport) -> dict[str, float | int]:
    """Run full evaluation suite on a generated research report."""
    coverage = evaluate_citation_coverage(report)
    hallucination = evaluate_hallucination_index(report)

    results = {
        "topic": report.topic,
        "total_sources_consulted": report.total_sources_consulted,
        **coverage,
        **hallucination,
    }

    print("=== RESEARCH REPORT QUALITY BENCHMARK ===")
    print(json.dumps(results, indent=2))
    return results
