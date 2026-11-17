"""Universal LLM Client supporting local Ollama, LM Studio, and cloud providers."""

import asyncio
import json
import logging
from typing import Any

import json_repair
from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Provider-agnostic asynchronous LLM client."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the underlying AsyncOpenAI client with appropriate base URL and API keys."""
        if self.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=settings.llm_base_url,
                api_key="ollama",  # Ollama doesn't require an API key
            )
        elif self.provider == "lmstudio":
            self.client = AsyncOpenAI(
                base_url=settings.llm_base_url,
                api_key="lm-studio",
            )
        elif self.provider == "openai":
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key or "missing-key",
            )
        elif self.provider == "groq":
            self.client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key or "missing-key",
            )
        elif self.provider == "deepseek":
            self.client = AsyncOpenAI(
                base_url="https://api.deepseek.com/v1",
                api_key=settings.deepseek_api_key or "missing-key",
            )
        elif self.provider == "gemini":
            # Gemini OpenAI-compatible endpoint
            self.client = AsyncOpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=settings.gemini_api_key or "missing-key",
            )
        else:
            # Custom / OpenAI fallback
            self.client = AsyncOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.openai_api_key or "default-key",
            )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
        retries: int = 2,
    ) -> tuple[str, int, int]:
        """Execute chat completion with automatic retries and token metrics.

        Returns:
            Tuple of (response_text, prompt_tokens, completion_tokens)
        """
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = await self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0

                return content, prompt_tokens, completion_tokens

            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM chat completion attempt %d/%d failed with error: %s",
                    attempt + 1,
                    retries + 1,
                    str(e),
                )
                if attempt < retries:
                    await asyncio.sleep(2**attempt)

        raise RuntimeError(f"LLM completion failed after {retries + 1} attempts: {last_error}")

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.1,
    ) -> tuple[dict[str, Any], int, int]:
        """Execute chat completion and parse output as guaranteed JSON using json_repair.

        Returns:
            Tuple of (parsed_dict, prompt_tokens, completion_tokens)
        """
        raw_text, prompt_tokens, completion_tokens = await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                return parsed, prompt_tokens, completion_tokens
        except json.JSONDecodeError:
            pass

        # Use json_repair for malformed JSON from smaller/local models
        repaired = json_repair.loads(raw_text)
        if isinstance(repaired, dict):
            return repaired, prompt_tokens, completion_tokens

        logger.error("Failed to parse JSON response: %s", raw_text)
        return {"raw_output": raw_text}, prompt_tokens, completion_tokens
