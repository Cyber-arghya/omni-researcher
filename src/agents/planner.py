"""Planner agent implementing STORM multi-perspective query decomposition."""

import logging

from src.llm.prompts import PLANNER_SYSTEM_PROMPT
from src.llm.router import ModelRouter
from src.state.schemas import ResearchState, SearchQuery

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Formulates orthogonal multi-perspective research search queries."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()

    async def plan_queries(self, state: ResearchState) -> list[SearchQuery]:
        """Decompose topic into 3-5 high-yield search queries based on depth and prior findings."""
        prior_queries = [q.query for q in state.search_queries]
        perspectives_covered = list({q.perspective for q in state.search_queries})

        user_prompt = (
            f"Research Topic: {state.topic}\n"
            f"User Focus / Constraints: {state.user_constraints or 'None'}\n"
            f"Current Research Depth: {state.current_depth} / {state.target_depth}\n"
            f"Prior Queries Already Executed: {prior_queries}\n"
            f"Perspectives Covered So Far: {perspectives_covered}\n\n"
        )

        if state.critic_notes:
            latest_critic = state.critic_notes[-1]
            user_prompt += (
                f"Critic Recommendations for missing angles:\n"
                f"- Missing Perspectives: {latest_critic.missing_perspectives}\n"
                f"- Unaddressed Contradictions: {latest_critic.unaddressed_contradictions}\n"
                f"- Suggested Counter-Queries: {latest_critic.suggested_counter_queries}\n"
            )

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            parsed = await self.router.run_fast(messages, state, temperature=0.3, json_mode=True)
            new_queries: list[SearchQuery] = []

            for item in parsed.get("queries", []):
                q_text = item.get("query", "").strip()
                if q_text and q_text not in prior_queries:
                    new_queries.append(
                        SearchQuery(
                            query=q_text,
                            perspective=item.get("perspective", "General"),
                            purpose=item.get("purpose", ""),
                        )
                    )

            logger.info(
                "Planner formulated %d new search queries for depth %d",
                len(new_queries),
                state.current_depth,
            )
            return new_queries

        except Exception as e:
            logger.error("Planner agent failed: %s", str(e))
            # Fallback heuristic query if LLM planning fails
            fallback = SearchQuery(
                query=f"{state.topic} overview benchmark analysis",
                perspective="Overview",
                purpose="Emergency fallback query",
            )
            return [fallback]
