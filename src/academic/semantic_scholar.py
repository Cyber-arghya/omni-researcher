"""Semantic Scholar API client for citation graph and academic paper retrieval."""

import logging

import httpx

from src.config import settings
from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarClient:
    """Async client for querying Semantic Scholar's academic graph API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.semantic_scholar_api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Search academic papers on Semantic Scholar with citation counts."""
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        params: dict[str, str | int] = {
            "query": query,
            "limit": max_results,
            "fields": "title,abstract,url,citationCount,year,authors",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(SEMANTIC_SCHOLAR_URL, params=params, headers=headers)
                if resp.status_code != 200:
                    logger.debug("Semantic Scholar returned status %d", resp.status_code)
                    return []

                data = resp.json()
                papers = data.get("data", [])

                results: list[SearchResult] = []
                for p in papers:
                    title = p.get("title", "Untitled")
                    url = (
                        p.get("url") or f"https://www.semanticscholar.org/paper/{p.get('paperId')}"
                    )
                    abstract = p.get("abstract") or ""
                    citations = p.get("citationCount", 0)
                    year = p.get("year", "N/A")

                    snippet = f"({year}, Citations: {citations}) {abstract}"
                    results.append(
                        SearchResult(
                            title=f"[Semantic Scholar] {title}",
                            url=url,
                            snippet=snippet[:300] + ("..." if len(snippet) > 300 else ""),
                            source_engine="semantic_scholar",
                            score=float(min(1.0, 0.5 + citations / 1000)),
                        )
                    )

                return results
        except Exception as e:
            logger.debug("Semantic Scholar search error for '%s': %s", query, str(e))
            return []
