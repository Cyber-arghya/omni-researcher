"""Academic and open science research clients (arXiv, Semantic Scholar, Crossref, PubMed)."""

from src.academic.arxiv_client import ArxivClient
from src.academic.crossref_client import CrossrefClient
from src.academic.pubmed_client import PubMedClient
from src.academic.semantic_scholar import SemanticScholarClient

__all__ = [
    "ArxivClient",
    "CrossrefClient",
    "PubMedClient",
    "SemanticScholarClient",
]
