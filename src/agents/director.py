"""Director agent orchestrating the multi-agent deep research loop and HITL gates."""

import asyncio
import logging
from collections.abc import Callable

from src.agents.critic import CriticAgent
from src.agents.explorer import ExplorerAgent
from src.agents.fact_checker import FactCheckerAgent
from src.agents.planner import PlannerAgent
from src.agents.synthesizer import SynthesizerAgent
from src.state.schemas import ResearchReport, ResearchState

logger = logging.getLogger(__name__)


class ResearchDirector:
    """Supervises the end-to-end autonomous research workflow and active HITL interventions."""

    def __init__(
        self,
        planner: PlannerAgent | None = None,
        explorer: ExplorerAgent | None = None,
        critic: CriticAgent | None = None,
        synthesizer: SynthesizerAgent | None = None,
        fact_checker: FactCheckerAgent | None = None,
    ) -> None:
        self.planner = planner or PlannerAgent()
        self.explorer = explorer or ExplorerAgent()
        self.critic = critic or CriticAgent()
        self.synthesizer = synthesizer or SynthesizerAgent()
        self.fact_checker = fact_checker or FactCheckerAgent()

    async def run_research(
        self,
        state: ResearchState,
        hitl_callback: Callable[[str, str], bool] | None = None,
        unattended: bool = False,
        cancel_token: asyncio.Event | None = None,
    ) -> ResearchReport:
        """Execute the full deep research loop from planning to synthesis and verification."""
        logger.info("Starting autonomous research session: %s", state.session_id)
        state.status = "PLANNING"

        while state.current_depth < state.target_depth:
            if cancel_token and cancel_token.is_set():
                state.status = "ABORTED"
                raise asyncio.CancelledError(f"Session {state.session_id} was aborted by user.")

            state.current_depth += 1
            logger.info(
                "=== Entering Research Depth: %d / %d ===", state.current_depth, state.target_depth
            )

            # 1. Planning Stage: Formulate search queries
            state.status = "PLANNING"
            new_queries = await self.planner.plan_queries(state)
            state.search_queries.extend(new_queries)

            if cancel_token and cancel_token.is_set():
                state.status = "ABORTED"
                raise asyncio.CancelledError(f"Session {state.session_id} was aborted by user.")

            # 2. Exploration Stage: Search, crawl, chunk, and index
            state.status = "SEARCHING"
            await self.explorer.execute_exploration(new_queries, state, cancel_token=cancel_token)

            if cancel_token and cancel_token.is_set():
                state.status = "ABORTED"
                raise asyncio.CancelledError(f"Session {state.session_id} was aborted by user.")

            # 3. Critic & Gap Evaluation Stage
            state.status = "CRITIQUING"
            feedback = await self.critic.evaluate_progress(state)

            # Mid-Execution Active Human-in-the-Loop Gate
            if not unattended and feedback.unaddressed_contradictions and hitl_callback:
                state.status = "PAUSED_HITL"
                contradiction_prompt = (
                    "Notice: Contradiction detected in research data:\n"
                    + "\n".join([f"- {c}" for c in feedback.unaddressed_contradictions])
                    + "\nWould you like to steer research to investigate this controversy deeper?"
                )
                should_steer = hitl_callback("Contradiction Detected", contradiction_prompt)
                if should_steer:
                    state.user_constraints += f" Pay special attention to resolving: {feedback.unaddressed_contradictions[0]}"

            # Check if research is complete
            if feedback.ready_for_synthesis or state.current_depth >= state.target_depth:
                logger.info(
                    "Information sufficiency threshold reached. Concluding exploration loop."
                )
                break

        # 4. Synthesis Stage: Long-form analytical dossier drafting
        if cancel_token and cancel_token.is_set():
            state.status = "ABORTED"
            raise asyncio.CancelledError(f"Session {state.session_id} was aborted by user.")

        state.status = "SYNTHESIZING"
        report = (
            await self.synthesizer.synthesizer_report(state)
            if hasattr(self.synthesizer, "synthesizer_report")
            else await self.synthesizer.synthesize_report(state)
        )

        # 5. Grounding & Anti-Hallucination Fact-Checking
        state.status = "GROUNDING"
        self.fact_checker.verify_and_ground_citations(report)

        state.status = "COMPLETED"
        logger.info("Research session %s successfully completed!", state.session_id)
        return report
