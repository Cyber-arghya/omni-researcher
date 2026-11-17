"""Multi-representation embedding engine supporting local BGE-M3 and cloud APIs."""

import logging
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Manages dense semantic vector embeddings for local and cloud models."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model: Any = None

    def _get_local_model(self) -> Any:
        """Lazy load the local SentenceTransformer embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading local embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute dense vector embeddings for a list of text strings."""
        if not texts:
            return []

        # If running in local mode or default, use SentenceTransformers
        if settings.is_local_mode or not settings.openai_api_key:
            model = self._get_local_model()
            embeddings = model.encode(texts, normalize_embeddings=True)
            return [emb.tolist() for emb in embeddings]

        # Cloud OpenAI fallback
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.embeddings.create(input=texts, model="text-embedding-3-small")
            return [data.embedding for data in resp.data]
        except Exception as e:
            logger.warning("Cloud embedding failed, falling back to local model: %s", str(e))
            model = self._get_local_model()
            embeddings = model.encode(texts, normalize_embeddings=True)
            return [emb.tolist() for emb in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Compute dense vector embedding for a single search query."""
        results = self.embed_texts([query])
        return results[0] if results else []
