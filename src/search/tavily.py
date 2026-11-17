"""Tavily search API client for premium research retrieval."""

import logging

import httpx

from src.config import settings
from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)


class TavilySearcher:
    """Async client for querying the Tavily Search API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.tavily_api_key

    async def search(self, query: str, max_results: int = 6) -> list[SearchResult]:
        """Execute search using Tavily API."""
        if not self.api_key:
            logger.info("Tavily API key not configured, skipping Tavily.")
            return []

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    logger.warning("Tavily API returned status %d", response.status_code)
                    return []

                data = response.json()
                raw_results = data.get("results", [])

                results: list[SearchResult] = []
                for item in raw_results[:max_results]:
                    res_url = item.get("url", "")
                    title = item.get("title", "")
                    content = item.get("content", "")
                    score = item.get("score", 1.0)

                    if res_url and res_url.startswith("http"):
                        results.append(
                            SearchResult(
                                title=title,
                                url=res_url,
                                snippet=content,
                                source_engine="tavily",
                                score=float(score),
                            )
                        )

                return results

        except Exception as e:
            logger.warning("Tavily search error for '%s': %s", query, str(e))
            return []
