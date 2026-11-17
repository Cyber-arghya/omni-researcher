"""ChromaDB local vector store wrapper for chunk indexing and retrieval."""

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.rag.embeddings import EmbeddingEngine
from src.rag.text_splitter import DocumentChunk

logger = logging.getLogger(__name__)


class LocalVectorStore:
    """Manages local embedded ChromaDB collection for dense vector retrieval."""

    def __init__(
        self,
        collection_name: str = "research_chunks",
        embedding_engine: EmbeddingEngine | None = None,
    ) -> None:
        self.persist_dir = str(settings.chroma_persist_dir)
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Embed and insert document chunks into ChromaDB."""
        if not chunks:
            return

        ids = [c.child_id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [
            {
                **c.metadata,
                "parent_id": c.parent_id,
                "parent_text": c.parent_text[:2000],  # keep parent excerpt in metadata
            }
            for c in chunks
        ]

        embeddings = self.embedding_engine.embed_texts(texts)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=texts,
            metadatas=metadatas,  # type: ignore[arg-type]
        )
        logger.info("Successfully indexed %d chunks into ChromaDB", len(chunks))

    def query(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Query top-k most semantically similar chunks."""
        query_embedding = self.embedding_engine.embed_query(query_text)
        if not query_embedding:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=top_k,
        )

        matched_items: list[dict[str, Any]] = []
        res_ids = results.get("ids")
        if results and res_ids and res_ids[0]:
            ids = res_ids[0]
            res_docs = results.get("documents")
            docs = res_docs[0] if res_docs else []
            res_metas = results.get("metadatas")
            metas = res_metas[0] if res_metas else []
            res_dists = results.get("distances")
            distances = res_dists[0] if res_dists else []

            for i in range(len(ids)):
                matched_items.append(
                    {
                        "child_id": ids[i],
                        "text": docs[i] if i < len(docs) else "",
                        "metadata": metas[i] if i < len(metas) else {},
                        "score": 1.0 - float(distances[i]) if i < len(distances) else 1.0,
                    }
                )

        return matched_items
