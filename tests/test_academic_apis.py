"""Unit tests for the academic search client parsers."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.academic.arxiv_client import ArxivClient
from src.academic.crossref_client import CrossrefClient
from src.academic.pubmed_client import PubMedClient
from src.academic.semantic_scholar import SemanticScholarClient


def test_arxiv_atom_xml_parser() -> None:
    """Verify parsing of arXiv Atom XML responses."""
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.12345v1</id>
        <title>All-Solid-State Lithium Batteries: Recent Breakthroughs</title>
        <summary>This paper reviews recent advances in sulfide-based solid electrolytes...</summary>
      </entry>
    </feed>
    """
    client = ArxivClient()
    results = client._parse_atom_response(sample_xml)

    assert len(results) == 1
    assert "[arXiv]" in results[0].title
    assert results[0].url == "http://arxiv.org/abs/2401.12345v1"
    assert "sulfide-based solid electrolytes" in results[0].snippet
    assert results[0].source_engine == "arxiv"


async def test_semantic_scholar_response_parsing() -> None:
    """Verify Semantic Scholar JSON response handling."""
    mock_payload = {
        "data": [
            {
                "paperId": "abc1234",
                "title": "Machine Learning in Quantum Computing",
                "abstract": "A survey of neural network quantum states.",
                "url": "https://www.semanticscholar.org/paper/abc1234",
                "citationCount": 42,
                "year": 2024,
            }
        ]
    }
    client = SemanticScholarClient(api_key="mock_key")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        results = await client.search("quantum ML")
        assert len(results) == 1
        assert "[Semantic Scholar]" in results[0].title
        assert "Citations: 42" in results[0].snippet
        assert results[0].source_engine == "semantic_scholar"


async def test_crossref_response_parsing() -> None:
    """Verify Crossref JSON response handling."""
    mock_payload = {
        "message": {
            "items": [
                {
                    "title": ["Solid Electrolyte Interphase Mechanisms"],
                    "DOI": "10.1038/s41586-024-001",
                    "URL": "https://doi.org/10.1038/s41586-024-001",
                    "publisher": "Nature Publishing Group",
                    "container-title": ["Nature Energy"],
                }
            ]
        }
    }
    client = CrossrefClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        results = await client.search("solid electrolyte")
        assert len(results) == 1
        assert results[0].title == "[Crossref] Solid Electrolyte Interphase Mechanisms"
        assert "Nature Publishing Group" in results[0].snippet
        assert results[0].source_engine == "crossref"


async def test_pubmed_response_parsing() -> None:
    """Verify PubMed two-step ESearch + ESummary JSON handling."""
    search_payload = {"esearchresult": {"idlist": ["12345678"]}}
    summary_payload = {
        "result": {
            "uids": ["12345678"],
            "12345678": {
                "title": "Clinical Efficacy of Novel Immunotherapy",
                "source": "The Lancet",
                "pubdate": "2025 Jan",
            },
        }
    }
    client = PubMedClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp_search = MagicMock()
        mock_resp_search.status_code = 200
        mock_resp_search.json.return_value = search_payload

        mock_resp_summary = MagicMock()
        mock_resp_summary.status_code = 200
        mock_resp_summary.json.return_value = summary_payload

        mock_get.side_effect = [mock_resp_search, mock_resp_summary]

        results = await client.search("immunotherapy")
        assert len(results) == 1
        assert results[0].title == "[PubMed] Clinical Efficacy of Novel Immunotherapy"
        assert results[0].url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert results[0].source_engine == "pubmed"
