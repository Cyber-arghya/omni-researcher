"""SearXNG private self-hosted meta-search engine client."""

import logging

import httpx

from src.config import settings
from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)


class SearXNGSearcher:
    """Async client for querying local or self-hosted SearXNG instances."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.searxng_base_url).rstrip("/")

    async def search(self, query: str, max_results: int = 6) -> list[SearchResult]:
        """Execute search against SearXNG JSON API."""
        url = f"{self.base_url}/search"
        params = {
            "q": query,
            "format": "json",
            "language": "en",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.warning(
                        "SearXNG returned status %d for '%s'", response.status_code, query
                    )
                    return []

                data = response.json()
                raw_results = data.get("results", [])

                results: list[SearchResult] = []
                for item in raw_results[:max_results]:
                    res_url = item.get("url", "")
                    title = item.get("title", "")
                    content = item.get("content", "")

                    if res_url and res_url.startswith("http"):
                        results.append(
                            SearchResult(
                                title=title,
                                url=res_url,
                                snippet=content,
                                source_engine="searxng",
                            )
                        )

                return results

        except Exception as e:
            logger.warning("SearXNG search error for '%s': %s", query, str(e))
            return []
