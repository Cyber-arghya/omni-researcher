"""Quality, grounding, and hallucination evaluation benchmarks."""

from evals.citation_accuracy import evaluate_citation_coverage
from evals.hallucination_eval import evaluate_hallucination_index
from evals.run_benchmarks import benchmark_report

__all__ = [
    "benchmark_report",
    "evaluate_citation_coverage",
    "evaluate_hallucination_index",
]
