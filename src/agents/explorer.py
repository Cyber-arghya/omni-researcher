"""Explorer agent for harvesting web content, indexing RAG chunks, and building the knowledge graph."""

import asyncio
import logging

from src.academic.arxiv_client import ArxivClient
from src.academic.pubmed_client import PubMedClient
from src.crawler.scraper import WebScraper
from src.graph.extractor import GraphExtractor
from src.graph.graph_store import KnowledgeGraphStore
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.text_splitter import ParentDocumentChunker
from src.rag.vector_store import LocalVectorStore
from src.search.engine import SearchEngineDispatcher
from src.state.schemas import ResearchState, ScrapedDocument, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class ExplorerAgent:
    """Dispatches search queries, scrapes pages, and indexes findings into Vector RAG & Knowledge Graph."""

    def __init__(
        self,
        search_engine: SearchEngineDispatcher | None = None,
        scraper: WebScraper | None = None,
        vector_store: LocalVectorStore | None = None,
        retriever: HybridRetriever | None = None,
        graph_store: KnowledgeGraphStore | None = None,
    ) -> None:
        self.search_engine = search_engine or SearchEngineDispatcher()
        self.scraper = scraper or WebScraper()
        self.chunker = ParentDocumentChunker()
        self.vector_store = vector_store or LocalVectorStore()
        self.retriever = retriever or HybridRetriever(self.vector_store)
        self.graph_store = graph_store or KnowledgeGraphStore()
        self.graph_extractor = GraphExtractor()
        self.arxiv = ArxivClient()
        self.pubmed = PubMedClient()

    async def execute_exploration(
        self,
        queries: list[SearchQuery],
        state: ResearchState,
    ) -> list[ScrapedDocument]:
        """Harvest web pages and academic papers from generated queries."""
        if not queries:
            return []

        # 1. Dispatch queries across Web Search
        web_results = await self.search_engine.search_batch(
            queries=queries,
            max_results_per_query=4,
            exclude_urls=state.visited_urls,
        )

        # 2. Dispatch query to arXiv academic search for scholarly perspectives
        academic_results: list[SearchResult] = []
        try:
            academic_results = await self.arxiv.search(state.topic, max_results=3)
        except Exception as e:
            logger.debug("Academic search fallback: %s", str(e))

        all_candidate_results = web_results + academic_results
        candidate_urls = [r.url for r in all_candidate_results if r.url not in state.visited_urls]

        logger.info("Explorer found %d candidate URLs to scrape", len(candidate_urls))

        # 3. Parallel web scraping with concurrency limit of 5
        semaphore = asyncio.Semaphore(5)

        async def _scrape_safe(url: str) -> ScrapedDocument | None:
            async with semaphore:
                try:
                    return await self.scraper.scrape_url(url)
                except Exception as err:
                    logger.debug("Scrape failed for %s: %s", url, str(err))
                    return None

        scrape_tasks = [_scrape_safe(url) for url in candidate_urls[:10]]
        scraped_docs = await asyncio.gather(*scrape_tasks)
        valid_docs = [doc for doc in scraped_docs if doc is not None]

        # 4. Ingest valid documents into Vector RAG & Knowledge Graph
        for doc in valid_docs:
            state.visited_urls.add(doc.url)
            state.collected_documents.append(doc)

            # A. Parent-Document Chunking & Vector Store Indexing
            chunks = self.chunker.chunk_document(
                doc_id=doc.id,
                text=doc.clean_text,
                metadata={"url": doc.url, "title": doc.title},
            )
            self.vector_store.add_chunks(chunks)

            # Update in-memory BM25 index
            chunk_dicts = [
                {"child_id": c.child_id, "text": c.text, "metadata": c.metadata} for c in chunks
            ]
            self.retriever.update_corpus(chunk_dicts)

            # B. Entity-Relation Triple Extraction for GraphRAG
            nodes, edges = await self.graph_extractor.extract_triples(
                text_chunk=doc.clean_text[:3000],
                doc_id=doc.id,
            )
            self.graph_store.add_nodes(nodes)
            self.graph_store.add_edges(edges)

        # Persist graph updates to disk
        self.graph_store.save_to_disk()

        logger.info("Explorer indexed %d documents into RAG and Knowledge Graph", len(valid_docs))
        return valid_docs
