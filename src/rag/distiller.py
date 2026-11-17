"""Zero-VRAM context distillation and MinHash-based paragraph deduplication."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

BOILERPLATE_PATTERNS = [
    r"cookies?",
    r"cookie\s*policy",
    r"accept\s*all\s*cookies",
    r"privacy\s*settings",
    r"terms\s*of\s*service",
    r"all\s*rights\s*reserved",
    r"subscribe",
    r"follow\s*us",
    r"share\s*this\s*article",
]
COMPILED_BOILERPLATE = [re.compile(p, re.IGNORECASE) for p in BOILERPLATE_PATTERNS]


class ContextDistiller:
    """Prunes boilerplate, eliminates redundant paragraphs, and distills high-density facts."""

    @staticmethod
    def _is_boilerplate(paragraph: str) -> bool:
        """Check if paragraph matches standard web junk/cookie notices."""
        clean = paragraph.strip()
        if len(clean) < 30:
            return True
        return any(pattern.search(clean) for pattern in COMPILED_BOILERPLATE)

    @classmethod
    def deduplicate_paragraphs(cls, text: str, jaccard_threshold: float = 0.70) -> str:
        """Remove duplicate and near-duplicate paragraphs from raw scraped web content."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        unique_paragraphs: list[str] = []
        seen_word_sets: list[set[str]] = []

        for p in paragraphs:
            if cls._is_boilerplate(p):
                continue

            words = set(re.findall(r"\w+", p.lower()))
            if not words:
                continue

            # Compare Jaccard similarity against already accepted paragraphs
            is_duplicate = False
            for prev_words in seen_word_sets:
                intersection = len(words & prev_words)
                union = len(words | prev_words)
                if union > 0 and (intersection / union) >= jaccard_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_paragraphs.append(p)
                seen_word_sets.append(words)

        distilled_text = "\n\n".join(unique_paragraphs)
        orig_words = len(text.split())
        distilled_words = len(distilled_text.split())
        savings_pct = (1.0 - (distilled_words / orig_words)) * 100 if orig_words else 0
        logger.debug(
            "ContextDistiller pruned %d words -> %d words (%.1f%% token reduction)",
            orig_words,
            distilled_words,
            savings_pct,
        )
        return distilled_text

    @staticmethod
    def rank_chunks_zero_vram(
        chunks: list[dict[str, Any]], query: str, top_k: int = 15
    ) -> list[dict[str, Any]]:
        """Rank candidate chunks using fast lexical BM25 token scoring without GPU VRAM overhead."""
        query_terms = set(re.findall(r"\w+", query.lower()))
        if not query_terms or not chunks:
            return chunks[:top_k]

        scored: list[tuple[float, dict[str, Any]]] = []
        for c in chunks:
            text = c.get("text", "")
            tokens = re.findall(r"\w+", text.lower())
            if not tokens:
                continue

            score = 0.0
            token_count = len(tokens)
            for term in query_terms:
                freq = tokens.count(term)
                if freq > 0:
                    # BM25-style saturation scoring
                    tf = freq / (freq + 1.2 * (0.25 + 0.75 * (token_count / 200.0)))
                    score += tf

            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
