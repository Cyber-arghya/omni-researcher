"""arXiv academic pre-print search client."""

import logging
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivClient:
    """Async client for querying the official arXiv Open API."""

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Search arXiv for scholarly pre-prints."""
        encoded_query = urllib.parse.quote(query)
        params: dict[str, str | int] = {
            "search_query": f"all:{encoded_query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(ARXIV_API_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("arXiv API returned status %d", resp.status_code)
                    return []

                return self._parse_atom_response(resp.text)
        except Exception as e:
            logger.warning("arXiv search error for '%s': %s", query, str(e))
            return []

    def _parse_atom_response(self, xml_text: str) -> list[SearchResult]:
        """Parse XML Atom response from arXiv API into SearchResult items."""
        results: list[SearchResult] = []
        try:
            root = ET.fromstring(xml_text)
            for entry in root.findall("atom:entry", ATOM_NS):
                title_elem = entry.find("atom:title", ATOM_NS)
                summary_elem = entry.find("atom:summary", ATOM_NS)
                id_elem = entry.find("atom:id", ATOM_NS)

                title = (
                    title_elem.text.strip().replace("\n", " ")
                    if title_elem is not None and title_elem.text
                    else "Untitled"
                )
                summary = (
                    summary_elem.text.strip().replace("\n", " ")
                    if summary_elem is not None and summary_elem.text
                    else ""
                )
                url = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

                if url:
                    results.append(
                        SearchResult(
                            title=f"[arXiv] {title}",
                            url=url,
                            snippet=summary[:300] + ("..." if len(summary) > 300 else ""),
                            source_engine="arxiv",
                        )
                    )
        except Exception as e:
            logger.debug("Failed to parse arXiv XML: %s", str(e))

        return results
