"""Unit tests for the Universal LLM Client and reasoning content parsing."""

from unittest.mock import AsyncMock, MagicMock, patch

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
