"""Dual-Tier LLM Router with token and financial cost budget guardrails."""

import logging
from typing import Any

from src.config import settings
from src.llm.client import LLMClient
from src.state.schemas import ResearchState

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when the session exceeds configured cost or token limits."""


class ModelRouter:
    """Manages model tier delegation and enforces budget invariants."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.client = llm_client or LLMClient()
        if settings.llm_provider == "nvidia":
            self.fast_model = (
                settings.nvidia_model
                if settings.llm_fast_model in ["llama3.2:latest", "llama3.2:3b"]
                else settings.llm_fast_model
            )
            self.deep_model = (
                settings.nvidia_model
                if settings.llm_deep_model in ["deepseek-r1:latest", "qwen2.5:7b"]
                else settings.llm_deep_model
            )
        elif settings.llm_provider == "ollama":
            from src.hardware import HardwareProfiler

            tier_cfg = HardwareProfiler.get_tier_config(
                settings.hardware_profile, settings.llm_provider
            )
            self.fast_model = (
                tier_cfg["fast_model"]
                if settings.llm_fast_model == "llama3.2:latest"
                else settings.llm_fast_model
            )
            self.deep_model = (
                tier_cfg["deep_model"]
                if settings.llm_deep_model == "deepseek-r1:latest"
                else settings.llm_deep_model
            )
        else:
            self.fast_model = settings.llm_fast_model
            self.deep_model = settings.llm_deep_model

    def _check_budget(self, state: ResearchState) -> None:
        """Enforce cost and token caps before making an LLM call."""
        if state.estimated_cost_usd >= settings.max_cost_limit_usd:
            raise BudgetExceededError(
                f"Session cost limit reached (${state.estimated_cost_usd:.2f} >= ${settings.max_cost_limit_usd:.2f})"
            )
        if state.total_tokens_used >= settings.max_total_tokens:
            raise BudgetExceededError(
                f"Session token limit reached ({state.total_tokens_used} >= {settings.max_total_tokens})"
            )

    async def run_fast(
        self,
        messages: list[dict[str, str]],
        state: ResearchState,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Any:
        """Execute task using Tier 1 fast model (queries, filtering, chunk summaries)."""
        self._check_budget(state)
        result: Any
        if json_mode:
            result, p_tokens, c_tokens = await self.client.chat_json(
                messages=messages,
                model=self.fast_model,
                temperature=temperature,
            )
        else:
            result, p_tokens, c_tokens = await self.client.chat_completion(
                messages=messages,
                model=self.fast_model,
                temperature=temperature,
            )

        state.record_cost(p_tokens, c_tokens, self.fast_model)
        return result

    async def run_deep(
        self,
        messages: list[dict[str, str]],
        state: ResearchState,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        json_mode: bool = False,
    ) -> Any:
        """Execute task using Tier 2 deep reasoning model (critique, synthesis, contradictions)."""
        self._check_budget(state)
        result: Any
        if json_mode:
            result, p_tokens, c_tokens = await self.client.chat_json(
                messages=messages,
                model=self.deep_model,
                temperature=temperature,
            )
        else:
            result, p_tokens, c_tokens = await self.client.chat_completion(
                messages=messages,
                model=self.deep_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        state.record_cost(p_tokens, c_tokens, self.deep_model)
        return result
