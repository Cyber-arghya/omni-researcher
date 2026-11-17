"""Comprehensive unit tests for the multi-engine search dispatcher, deduplication, and fallback chains."""

from unittest.mock import AsyncMock

from src.search.engine import SearchEngineDispatcher
from src.state.schemas import SearchQuery, SearchResult


async def test_search_batch_deduplication_and_trailing_slashes() -> None:
    """Verify that identical URLs with differing trailing slashes are properly deduplicated."""
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


async def test_search_batch_exclude_urls() -> None:
    """Verify that search_batch respects exclude_urls and ignores pre-visited pages."""
    dispatcher = SearchEngineDispatcher()
    mock_results = [
        SearchResult(
            title="Known Page",
            url="https://example.com/known",
            snippet="Old",
            source_engine="ddg",
        ),
        SearchResult(
            title="New Page",
            url="https://example.com/new",
            snippet="Fresh",
            source_engine="ddg",
        ),
    ]
    dispatcher.search_single = AsyncMock(return_value=mock_results)  # type: ignore[method-assign]

    queries = [SearchQuery(query="test query", perspective="General")]
    exclude = {"https://example.com/known"}

    batch = await dispatcher.search_batch(queries, exclude_urls=exclude)
    assert len(batch) == 1
    assert batch[0].url == "https://example.com/new"


async def test_search_batch_empty_and_exception_handling() -> None:
    """Verify that search_batch handles empty queries and sub-task exceptions cleanly."""
    dispatcher = SearchEngineDispatcher()

    # Empty query list returns empty list
    assert await dispatcher.search_batch([]) == []

    # One query succeeds, one query throws an exception
    async def flaky_search(query: str, max_results: int = 6) -> list[SearchResult]:
        if "fail" in query:
            raise ConnectionError("DNS failure")
        return [
            SearchResult(
                title="Good",
                url="https://example.com/good",
                snippet="OK",
                source_engine="ddg",
            )
        ]

    dispatcher.search_single = flaky_search  # type: ignore[method-assign]
    queries = [
        SearchQuery(query="fail query", perspective="Test"),
        SearchQuery(query="good query", perspective="Test"),
    ]

    batch = await dispatcher.search_batch(queries)
    assert len(batch) == 1
    assert batch[0].url == "https://example.com/good"


async def test_search_single_fallbacks() -> None:
    """Verify multi-tier fallbacks across DDG, SearXNG, and Tavily."""
    dispatcher = SearchEngineDispatcher()

    # 1. DDG -> SearXNG fallback
    dispatcher.primary_provider = "ddg"
    dispatcher.ddg.search = AsyncMock(return_value=[])  # type: ignore[method-assign]
    dispatcher.searxng.search = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            SearchResult(
                title="SearXNG",
                url="https://searxng.org/1",
                snippet="Found",
                source_engine="searxng",
            )
        ]
    )

    results = await dispatcher.search_single("test query")
    assert len(results) == 1
    assert results[0].source_engine == "searxng"

    # 2. Tavily -> DDG fallback
    dispatcher.primary_provider = "tavily"
    dispatcher.tavily.search = AsyncMock(return_value=[])  # type: ignore[method-assign]
    dispatcher.ddg.search = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            SearchResult(
                title="DDG Fallback",
                url="https://ddg.gg/1",
                snippet="Found",
                source_engine="ddg",
            )
        ]
    )
    results_tavily = await dispatcher.search_single("tavily query")
    assert len(results_tavily) == 1
    assert results_tavily[0].source_engine == "ddg"
