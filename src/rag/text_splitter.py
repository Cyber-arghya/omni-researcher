"""Token-aware Parent-Document chunking for RAG."""

import re
from typing import NamedTuple


class DocumentChunk(NamedTuple):
    """Chunk tuple preserving parent-child context hierarchy."""

    child_id: str
    parent_id: str
    text: str
    parent_text: str
    metadata: dict[str, str]


class ParentDocumentChunker:
    """Splits documents into granular child chunks for dense vector search,

    while preserving parent section context for LLM synthesis.
    """

    def __init__(
        self,
        child_chunk_size: int = 300,
        child_overlap: int = 50,
        parent_chunk_size: int = 1000,
    ) -> None:
        self.child_chunk_size = child_chunk_size
        self.child_overlap = child_overlap
        self.parent_chunk_size = parent_chunk_size

    def chunk_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, str] | None = None,
    ) -> list[DocumentChunk]:
        """Split text into parent sections and child retrieval chunks."""
        meta = metadata or {}
        chunks: list[DocumentChunk] = []

        # Split into parent paragraphs/sections by double newline or markdown headers
        parent_sections = self._split_text_by_size(text, self.parent_chunk_size, overlap=100)

        for p_idx, parent_text in enumerate(parent_sections):
            parent_id = f"{doc_id}_p{p_idx}"
            child_sections = self._split_text_by_size(
                parent_text, self.child_chunk_size, overlap=self.child_overlap
            )

            for c_idx, child_text in enumerate(child_sections):
                child_id = f"{parent_id}_c{c_idx}"
                chunks.append(
                    DocumentChunk(
                        child_id=child_id,
                        parent_id=parent_id,
                        text=child_text,
                        parent_text=parent_text,
                        metadata={
                            **meta,
                            "doc_id": doc_id,
                            "child_id": child_id,
                            "parent_id": parent_id,
                        },
                    )
                )

        return chunks

    def _split_text_by_size(self, text: str, max_words: int, overlap: int) -> list[str]:
        """Word-boundary aware splitting."""
        words = re.findall(r"\S+", text)
        if not words:
            return []

        chunks: list[str] = []
        i = 0
        while i < len(words):
            chunk_words = words[i : i + max_words]
            chunks.append(" ".join(chunk_words))
            if i + max_words >= len(words):
                break
            i += max(1, max_words - overlap)

        return chunks
