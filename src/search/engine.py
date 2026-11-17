"""Unified Search Engine Dispatcher with automated provider fallback and deduplication."""

import asyncio
import logging

from src.config import settings
from src.search.ddg import DuckDuckGoSearcher
from src.search.searxng import SearXNGSearcher
from src.search.tavily import TavilySearcher
from src.state.schemas import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class SearchEngineDispatcher:
    """Unified search orchestrator dispatching queries to configured search backends."""

    def __init__(self) -> None:
        self.ddg = DuckDuckGoSearcher()
        self.searxng = SearXNGSearcher()
        self.tavily = TavilySearcher()
        self.primary_provider = settings.search_provider

    async def search_single(self, query: str, max_results: int = 6) -> list[SearchResult]:
        """Execute a single query with automated fallback chain.

        Fallback sequence: Primary -> DDG (if not primary) -> SearXNG -> Tavily.
        """
        results: list[SearchResult] = []

        if self.primary_provider == "ddg":
            results = await self.ddg.search(query, max_results)
            if not results:
                logger.info("DDG returned no results, trying SearXNG fallback...")
                results = await self.searxng.search(query, max_results)

        elif self.primary_provider == "tavily":
            results = await self.tavily.search(query, max_results)
            if not results:
                logger.info("Tavily returned no results, falling back to DDG...")
                results = await self.ddg.search(query, max_results)

        elif self.primary_provider == "searxng":
            results = await self.searxng.search(query, max_results)
            if not results:
                logger.info("SearXNG returned no results, falling back to DDG...")
                results = await self.ddg.search(query, max_results)

        return results

    async def search_batch(
        self,
        queries: list[SearchQuery],
        max_results_per_query: int = 6,
        exclude_urls: set[str] | None = None,
    ) -> list[SearchResult]:
        """Concurrently execute multiple search queries and deduplicate URLs."""
        if not queries:
            return []

        visited = exclude_urls or set()
        tasks = [self.search_single(q.query, max_results_per_query) for q in queries]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        deduplicated: list[SearchResult] = []
        seen_urls: set[str] = set(visited)

        for res in batch_results:
            if not isinstance(res, list):
                logger.error("Search query task raised an exception: %s", str(res))
                continue

            for item in res:
                normalized_url = item.url.rstrip("/")
                if normalized_url not in seen_urls:
                    seen_urls.add(normalized_url)
                    deduplicated.append(item)

        return deduplicated
