"""Unit tests for the multi-engine search dispatcher and deduplication."""

from src.search.engine import SearchEngineDispatcher
from src.state.schemas import SearchQuery, SearchResult


async def test_search_batch_deduplication() -> None:
    """Verify that identical URLs from different queries are properly deduplicated."""
    dispatcher = SearchEngineDispatcher()

    mock_results_1 = [
        SearchResult(
            title="Article 1",
            url="https://example.com/battery",
            snippet="Overview",
            source_engine="ddg",
        ),
        SearchResult(
            title="Article 2",
            url="https://example.com/solid-state",
            snippet="Details",
            source_engine="ddg",
        ),
    ]
    mock_results_2 = [
        SearchResult(
            title="Article 2 Duplicate",
            url="https://example.com/solid-state/",
            snippet="Duplicate details",
            source_engine="ddg",
        ),
        SearchResult(
            title="Article 3",
            url="https://example.com/anode",
            snippet="Anode findings",
            source_engine="ddg",
        ),
    ]

    async def mock_search_single(query: str, max_results: int = 6) -> list[SearchResult]:
        if "density" in query:
            return mock_results_1
        return mock_results_2

    dispatcher.search_single = mock_search_single  # type: ignore[method-assign]

    queries = [
        SearchQuery(query="battery energy density", perspective="Technical"),
        SearchQuery(query="solid state innovations", perspective="Foundational"),
    ]

    batch = await dispatcher.search_batch(queries, max_results_per_query=5)

    assert len(batch) == 3
    urls = {r.url.rstrip("/") for r in batch}
    assert urls == {
        "https://example.com/battery",
        "https://example.com/solid-state",
        "https://example.com/anode",
    }


async def test_search_single_fallback() -> None:
    """Verify fallback to secondary engine when primary returns empty."""
    dispatcher = SearchEngineDispatcher()
    dispatcher.primary_provider = "ddg"

    async def mock_ddg_search(query: str, max_results: int = 6) -> list[SearchResult]:
        return []

    async def mock_searxng_search(query: str, max_results: int = 6) -> list[SearchResult]:
        return [
            SearchResult(
                title="SearXNG Result",
                url="https://searxng.org/result",
                snippet="Found",
                source_engine="searxng",
            )
        ]

    dispatcher.ddg.search = mock_ddg_search  # type: ignore[method-assign]
    dispatcher.searxng.search = mock_searxng_search  # type: ignore[method-assign]

    results = await dispatcher.search_single("fallback test")
    assert len(results) == 1
    assert results[0].source_engine == "searxng"
    assert results[0].url == "https://searxng.org/result"
