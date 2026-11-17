"""Critic / Devil's Advocate agent evaluating information sufficiency and contradictions."""

import logging

from src.llm.prompts import CRITIC_SYSTEM_PROMPT
from src.llm.router import ModelRouter
from src.state.schemas import CriticFeedback, ResearchState

logger = logging.getLogger(__name__)


class CriticAgent:
    """Rigorous peer reviewer that challenges findings, surfaces gaps, and calculates saturation."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()

    async def evaluate_progress(self, state: ResearchState) -> CriticFeedback:
        """Evaluate evidence sufficiency and identify missing angles or contradictions."""
        # Calculate Information Saturation Index
        num_docs = len(state.collected_documents)
        num_queries = len(state.search_queries)

        # Basic saturation formula: approaches 1.0 as documents accumulate
        saturation = min(
            1.0, (num_docs / 12.0) * 0.7 + (state.current_depth / state.target_depth) * 0.3
        )
        state.information_saturation = saturation

        prompt = (
            f"Topic: {state.topic}\n"
            f"Current Depth: {state.current_depth} / {state.target_depth}\n"
            f"Calculated Information Saturation: {saturation:.2f}\n"
            f"Total Documents Collected: {num_docs}\n"
            f"Queries Executed: {num_queries}\n\n"
            f"Recent Document Titles:\n"
            + "\n".join([f"- {d.title} ({d.url})" for d in state.collected_documents[-6:]])
        )

        messages = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            parsed = await self.router.run_deep(messages, state, temperature=0.1, json_mode=True)

            # If max depth is reached, force readiness for synthesis
            ready = parsed.get("ready_for_synthesis", False)
            if state.current_depth >= state.target_depth or saturation >= 0.85:
                ready = True

            feedback = CriticFeedback(
                missing_perspectives=parsed.get("missing_perspectives", []),
                unaddressed_contradictions=parsed.get("unaddressed_contradictions", []),
                suggested_counter_queries=parsed.get("suggested_counter_queries", []),
                information_sufficiency_score=float(
                    parsed.get("information_sufficiency_score", saturation)
                ),
                ready_for_synthesis=ready,
            )

            state.critic_notes.append(feedback)
            logger.info(
                "Critic evaluation: Sufficiency=%.2f, ReadyForSynthesis=%s",
                feedback.information_sufficiency_score,
                feedback.ready_for_synthesis,
            )
            return feedback

        except Exception as e:
            logger.warning("Critic agent evaluation fallback: %s", str(e))
            fallback_feedback = CriticFeedback(
                information_sufficiency_score=saturation,
                ready_for_synthesis=state.current_depth >= state.target_depth,
            )
            state.critic_notes.append(fallback_feedback)
            return fallback_feedback
