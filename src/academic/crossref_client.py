"""Crossref DOI metadata resolution and publication verification client."""

import logging

import httpx

from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"


class CrossrefClient:
    """Async client for querying the Crossref Open DOI registry."""

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Search Crossref for peer-reviewed journal papers and metadata."""
        params: dict[str, str | int] = {
            "query": query,
            "rows": max_results,
            "sort": "relevance",
        }
        headers = {
            "User-Agent": "OpenDeepResearcher/0.1 (mailto:researcher@opendeepresearcher.org)",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(CROSSREF_API_URL, params=params, headers=headers)
                if resp.status_code != 200:
                    logger.debug("Crossref API returned status %d", resp.status_code)
                    return []

                data = resp.json()
                items = data.get("message", {}).get("items", [])

                results: list[SearchResult] = []
                for item in items:
                    title_list = item.get("title", [])
                    title = title_list[0] if title_list else "Untitled"
                    doi = item.get("DOI", "")
                    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
                    publisher = item.get("publisher", "")
                    container = (
                        item.get("container-title", [""])[0] if item.get("container-title") else ""
                    )

                    snippet = f"Published by {publisher} in {container}. DOI: {doi}"
                    if url:
                        results.append(
                            SearchResult(
                                title=f"[Crossref] {title}",
                                url=url,
                                snippet=snippet,
                                source_engine="crossref",
                            )
                        )

                return results
        except Exception as e:
            logger.debug("Crossref search error for '%s': %s", query, str(e))
            return []
