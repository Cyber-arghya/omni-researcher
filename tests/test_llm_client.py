"""Comprehensive unit tests for the Universal LLM Client, reasoning traces, retries, and JSON repair."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.client import LLMClient


async def test_llm_client_reasoning_content_parsing() -> None:
    """Verify that reasoning_content from thinking models (Nemotron, DeepSeek-R1) is captured."""
    client = LLMClient()

    # Mock response where content is empty and reasoning_content holds the thought
    mock_msg = MagicMock()
    mock_msg.content = ""
    mock_msg.reasoning_content = "This is the step-by-step thinking trace."
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 120

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response

        content, p_tok, c_tok = await client.chat_completion(
            messages=[{"role": "user", "content": "Explain quantum batteries"}],
            model="nvidia/nemotron-3-ultra-550b-a55b",
        )

        assert content == "This is the step-by-step thinking trace."
        assert p_tok == 50
        assert c_tok == 120
        # Verify that enable_thinking was requested for nemotron
        call_kwargs = mock_create.call_args[1]
        assert "extra_body" in call_kwargs
        assert call_kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": True}}


async def test_llm_client_automatic_retry_success() -> None:
    """Verify that transient API failure on attempt 1 triggers retry and succeeds on attempt 2."""
    client = LLMClient()

    mock_msg = MagicMock()
    mock_msg.content = "Recovered response after transient failure."
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 20
    mock_response.usage.completion_tokens = 40

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        # First call fails with an API connection exception, second call succeeds
        mock_create.side_effect = [ConnectionError("API drop"), mock_response]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            content, p_tok, c_tok = await client.chat_completion(
                messages=[{"role": "user", "content": "Retry test"}],
                model="llama3.2:latest",
                retries=2,
            )
            assert content == "Recovered response after transient failure."
            assert p_tok == 20
            assert c_tok == 40
            assert mock_create.call_count == 2
            assert mock_sleep.called


async def test_llm_client_retry_exhaustion_raises_runtime_error() -> None:
    """Verify that when all retries fail, RuntimeError is raised."""
    client = LLMClient()

    with patch.object(
        client.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = ConnectionError("Persistent network outage")

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="LLM completion failed after 3 attempts"),
        ):
            await client.chat_completion(
                messages=[{"role": "user", "content": "Exhaustion test"}],
                model="llama3.2:latest",
                retries=2,
            )


async def test_llm_client_chat_json_repair() -> None:
    """Verify chat_json correctly parses clean JSON and repairs malformed/trailing-comma JSON."""
    client = LLMClient()

    # Case 1: Malformed JSON with trailing commas repaired by json_repair
    malformed_json_str = '{"topic": "Solid State", "subtopics": ["anode", "cathode",],}'

    with patch.object(
        client,
        "chat_completion",
        new_callable=AsyncMock,
        return_value=(malformed_json_str, 30, 25),
    ):
        data, p_tok, c_tok = await client.chat_json(
            messages=[{"role": "user", "content": "Generate subtopics"}],
            model="llama3.2:latest",
        )
        assert isinstance(data, dict)
        assert data["topic"] == "Solid State"
        assert len(data["subtopics"]) == 2
        assert p_tok == 30
        assert c_tok == 25

    # Case 2: Completely unparseable plain string returns raw_output dict
    with patch.object(
        client,
        "chat_completion",
        new_callable=AsyncMock,
        return_value=("Just plain text without any json brackets", 10, 10),
    ):
        fallback_data, _, _ = await client.chat_json(
            messages=[{"role": "user", "content": "Unparseable"}],
            model="llama3.2:latest",
        )
        assert "raw_output" in fallback_data
