"""Multi-Modal Vision Client with hardware-aware graceful degradation."""

import base64
import logging
from pathlib import Path

from src.config import settings
from src.llm.client import LLMClient
from src.llm.prompts import VISION_ANALYST_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class VisionClient:
    """Client for analyzing charts, plots, and diagrams extracted from PDFs or web pages."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.enabled = settings.vision_enabled
        self.model = settings.vision_model

    def _encode_image(self, image_path: Path) -> str:
        """Encode local image file to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def analyze_image(
        self,
        image_path: str | Path,
        caption: str = "",
    ) -> tuple[str, int, int]:
        """Analyze an image using a vision model.

        Gracefully degrades if vision is disabled or the model fails.

        Returns:
            Tuple of (analysis_markdown, prompt_tokens, completion_tokens)
        """
        if not self.enabled:
            return f"*(Vision analysis disabled. Image caption: {caption})*", 0, 0

        path = Path(image_path)
        if not path.exists():
            logger.warning("Image file not found: %s", path)
            return f"*(Image not found: {caption})*", 0, 0

        try:
            base64_image = self._encode_image(path)
            messages = [
                {"role": "system", "content": VISION_ANALYST_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze this extracted chart/diagram. Caption: {caption}",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                },
            ]

            analysis, prompt_tokens, completion_tokens = await self.llm_client.chat_completion(
                messages=messages,  # type: ignore[arg-type]
                model=self.model,
                temperature=0.1,
                max_tokens=1500,
            )
            return analysis, prompt_tokens, completion_tokens

        except Exception as e:
            # Graceful degradation: log warning and do not crash the pipeline
            logger.warning(
                "Vision model analysis failed for %s. Gracefully falling back. Error: %s",
                path.name,
                str(e),
            )
            fallback_text = (
                f"### [Visual Asset: {path.name}]\n"
                f"**Caption**: {caption or 'No caption provided'}\n\n"
                f"*Note: Vision model processing unavailable. Retained as primary reference.*"
            )
            return fallback_text, 0, 0
