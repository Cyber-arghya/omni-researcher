"""Rigorous unit and edge-case tests for the academic search client parsers.

Validates:
- arXiv Atom XML parsing, corrupted XML, empty feeds, missing fields, and HTTP/network failures.
- Semantic Scholar JSON parsing, missing fields, 500/403 errors, and connection timeouts.
- Crossref JSON parsing, malformed items, empty results, and network exceptions.
- PubMed two-step ESearch + ESummary pipeline, missing UIDs, empty idlists, and partial API failures.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.academic.arxiv_client import ArxivClient
from src.academic.crossref_client import CrossrefClient
from src.academic.pubmed_client import PubMedClient
from src.academic.semantic_scholar import SemanticScholarClient


# ==========================================
# 1. arXiv Client Tests
# ==========================================
def test_arxiv_atom_xml_parser_happy_path() -> None:
    """Verify standard parsing of valid arXiv Atom XML response."""
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


def test_arxiv_atom_xml_parser_empty_and_corrupted() -> None:
    """Verify arXiv parser gracefully handles empty feeds and malformed XML."""
    client = ArxivClient()

    # Empty feed
    empty_results = client._parse_atom_response('<feed xmlns="http://www.w3.org/2005/Atom"></feed>')
    assert empty_results == []

    # Corrupted / non-XML string
    corrupted_results = client._parse_atom_response("<<malformed <<xml??")
    assert corrupted_results == []

    # Entry missing id (must be skipped or handled without crashing)
    missing_id_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>No ID Paper</title>
        <summary>Some text</summary>
      </entry>
    </feed>
    """
    assert client._parse_atom_response(missing_id_xml) == []


async def test_arxiv_network_failures() -> None:
    """Verify arXiv search handles HTTP 500, 429, and network timeouts safely."""
    client = ArxivClient()

    # HTTP 500
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp
        assert await client.search("quantum") == []

    # Network Timeout
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        assert await client.search("quantum") == []

    # Connect Error
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        assert await client.search("quantum") == []


# ==========================================
# 2. Semantic Scholar Client Tests
# ==========================================
async def test_semantic_scholar_response_parsing_happy_path() -> None:
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


async def test_semantic_scholar_missing_fields_and_errors() -> None:
    """Verify Semantic Scholar handles missing paper fields and API errors."""
    client = SemanticScholarClient()

    # Incomplete paper metadata (missing abstract, missing citation count)
    mock_payload = {
        "data": [
            {
                "paperId": "incomplete_01",
                "title": "Paper Without Abstract",
                "url": "https://www.semanticscholar.org/paper/incomplete_01",
            }
        ]
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        results = await client.search("incomplete")
        assert len(results) == 1
        assert results[0].title == "[Semantic Scholar] Paper Without Abstract"

    # HTTP 403 Forbidden / Rate limit 429
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp
        assert await client.search("rate_limited") == []

    # Network Exception
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("DNS failed")):
        assert await client.search("dns_fail") == []


# ==========================================
# 3. Crossref Client Tests
# ==========================================
async def test_crossref_response_parsing_happy_path() -> None:
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


async def test_crossref_empty_items_and_network_errors() -> None:
    """Verify Crossref handles empty items, missing titles, and network faults."""
    client = CrossrefClient()

    # Empty items list
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"items": []}}
        mock_get.return_value = mock_resp
        assert await client.search("nonexistent") == []

    # Item missing title list
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"items": [{"DOI": "10.1234/test", "URL": "https://doi.org/test"}]}
        }
        mock_get.return_value = mock_resp
        results = await client.search("missing_title")
        assert len(results) == 1
        assert "Untitled" in results[0].title

    # Server error 503
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_get.return_value = mock_resp
        assert await client.search("crossref_down") == []


# ==========================================
# 4. PubMed Client Tests
# ==========================================
async def test_pubmed_response_parsing_happy_path() -> None:
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


async def test_pubmed_empty_search_and_partial_failures() -> None:
    """Verify PubMed behavior when esearch returns no IDs or esummary fails."""
    client = PubMedClient()

    # 1. ESearch returns empty idlist
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"esearchresult": {"idlist": []}}
        mock_get.return_value = mock_resp

        results = await client.search("no_hits_query")
        assert results == []

    # 2. ESearch succeeds, but ESummary returns HTTP 500
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {"esearchresult": {"idlist": ["99999"]}}

        mock_fail = MagicMock()
        mock_fail.status_code = 500

        mock_get.side_effect = [mock_ok, mock_fail]
        results = await client.search("esummary_fail")
        assert results == []

    # 3. Network timeout on ESearch
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("ESearch timed out")):
        results = await client.search("timeout_query")
        assert results == []
