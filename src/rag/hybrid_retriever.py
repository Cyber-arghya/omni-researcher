"""Hybrid Retriever combining Dense Vector similarity with Sparse BM25 using Reciprocal Rank Fusion (RRF)."""

import math
import re
from collections import defaultdict
from typing import Any

from src.rag.vector_store import LocalVectorStore


class SimpleBM25:
    """In-memory BM25 ranker for exact lexical and acronym matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus: list[dict[str, Any]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_len = 0.0
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.total_docs = 0

    def fit(self, documents: list[dict[str, Any]]) -> None:
        """Index a list of chunks {child_id, text, metadata}."""
        self.corpus = documents
        self.total_docs = len(documents)
        if self.total_docs == 0:
            return

        self.doc_lengths = []
        self.doc_freqs = defaultdict(int)

        total_words = 0
        for doc in documents:
            tokens = set(self._tokenize(doc["text"]))
            words_count = len(self._tokenize(doc["text"]))
            self.doc_lengths.append(words_count)
            total_words += words_count
            for t in tokens:
                self.doc_freqs[t] += 1

        self.avg_doc_len = total_words / self.total_docs if self.total_docs > 0 else 1.0

    def score(self, query: str, top_k: int = 10) -> list[tuple[dict[str, Any], float]]:
        """Score all corpus documents against query terms."""
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.corpus:
            return []

        scores: list[tuple[int, float]] = []

        for idx, doc in enumerate(self.corpus):
            doc_tokens = self._tokenize(doc["text"])
            doc_len = self.doc_lengths[idx]
            doc_score = 0.0

            token_counts: dict[str, int] = defaultdict(int)
            for t in doc_tokens:
                token_counts[t] += 1

            for qt in query_tokens:
                if qt not in self.doc_freqs:
                    continue
                df = self.doc_freqs[qt]
                idf = math.log(1.0 + (self.total_docs - df + 0.5) / (df + 0.5))
                tf = token_counts[qt]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                term_score = idf * (tf * (self.k1 + 1.0)) / (denom if denom > 0 else 1.0)
                doc_score += term_score

            if doc_score > 0.0:
                scores.append((idx, doc_score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [(self.corpus[idx], score) for idx, score in scores[:top_k]]

    def _tokenize(self, text: str) -> list[str]:
        """Normalize and tokenize text to lowercase alphanumeric words."""
        return re.findall(r"\w+", text.lower())


class HybridRetriever:
    """Fuses Dense Vector and BM25 Sparse retrieval via Reciprocal Rank Fusion."""

    def __init__(self, vector_store: LocalVectorStore | None = None) -> None:
        self.vector_store = vector_store or LocalVectorStore()
        self.bm25 = SimpleBM25()
        self._all_chunks: list[dict[str, Any]] = []

    def update_corpus(self, chunks: list[dict[str, Any]]) -> None:
        """Update the in-memory BM25 index with newly collected chunks."""
        self._all_chunks = chunks
        self.bm25.fit(chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """Execute hybrid search using Reciprocal Rank Fusion (RRF)."""
        # 1. Dense retrieval
        dense_results = self.vector_store.query(query, top_k=top_k * 2)

        # 2. Sparse BM25 retrieval
        sparse_scored = self.bm25.score(query, top_k=top_k * 2)
        sparse_results = [item[0] for item in sparse_scored]

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: dict[str, float] = defaultdict(float)
        chunk_map: dict[str, dict[str, Any]] = {}

        # Accumulate dense ranks
        for rank, item in enumerate(dense_results):
            cid = item["child_id"]
            rrf_scores[cid] += 1.0 / (rrf_k + (rank + 1))
            chunk_map[cid] = item

        # Accumulate sparse ranks
        for rank, item in enumerate(sparse_results):
            cid = item["child_id"]
            rrf_scores[cid] += 1.0 / (rrf_k + (rank + 1))
            chunk_map[cid] = item

        # Sort by RRF score descending
        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        final_chunks: list[dict[str, Any]] = []
        for cid in sorted_cids[:top_k]:
            chunk = chunk_map[cid]
            chunk["rrf_score"] = rrf_scores[cid]
            final_chunks.append(chunk)

        return final_chunks
