"""DuckDuckGo Search integration with rate-limiting and defensive error recovery."""

import asyncio
import logging

from duckduckgo_search import DDGS

from src.state.schemas import SearchResult

logger = logging.getLogger(__name__)


class DuckDuckGoSearcher:
    """Async wrapper around DuckDuckGo search with rate-limiting guards."""

    def __init__(self, request_delay_seconds: float = 1.5) -> None:
        self.request_delay = request_delay_seconds
        self._last_request_time = 0.0
        self._lock: asyncio.Lock | None = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazily initialize lock in the current active event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def search(self, query: str, max_results: int = 6) -> list[SearchResult]:
        """Execute web search using DuckDuckGo.

        Enforces a minimal delay between consecutive requests to avoid HTTP 429 rate limits.
        """
        async with self.lock:
            # Respect rate-limiting delay
            await asyncio.sleep(self.request_delay)

            try:
                # Run synchronous DDGS in thread executor to prevent blocking asyncio loop
                loop = asyncio.get_running_loop()
                raw_results = await loop.run_in_executor(
                    None,
                    self._execute_sync_search,
                    query,
                    max_results,
                )

                results: list[SearchResult] = []
                for item in raw_results:
                    url = item.get("href") or item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("body") or item.get("snippet", "")

                    if url and url.startswith("http"):
                        results.append(
                            SearchResult(
                                title=title,
                                url=url,
                                snippet=snippet,
                                source_engine="ddg",
                            )
                        )

                return results

            except Exception as e:
                logger.warning("DuckDuckGo search failed for '%s': %s", query, str(e))
                return []

    def _execute_sync_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Synchronous DuckDuckGo search invocation."""
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
