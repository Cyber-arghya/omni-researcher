"""Visual diagram and chart extractor for PDFs and web pages."""

import hashlib
import logging
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.crawler.stealth import get_stealth_headers
from src.state.schemas import ExtractedImage

logger = logging.getLogger(__name__)


class VisualImageExtractor:
    """Discovers and extracts charts, diagrams, and figures from HTML or PDFs."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or (settings.storage_dir / "images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def extract_from_html(self, html_content: str, base_url: str) -> list[ExtractedImage]:
        """Extract relevant figure and chart images from rendered HTML."""
        soup = BeautifulSoup(html_content, "html.parser")
        images: list[ExtractedImage] = []

        # Find img tags inside <figure> or with keywords like 'chart', 'plot', 'diagram'
        for img in soup.find_all("img"):
            raw_src = img.get("src")
            if not isinstance(raw_src, str) or not raw_src.strip():
                continue

            absolute_url = urljoin(base_url, raw_src)
            raw_alt = img.get("alt", "")
            raw_title = img.get("title", "")
            alt_text = (
                raw_alt
                if isinstance(raw_alt, str)
                else (" ".join(str(x) for x in raw_alt) if raw_alt else "")
            )
            title_text = (
                raw_title
                if isinstance(raw_title, str)
                else (" ".join(str(x) for x in raw_title) if raw_title else "")
            )
            caption = alt_text or title_text

            # Look for parent figure caption
            parent_figure = img.find_parent("figure")
            if parent_figure:
                figcaption = parent_figure.find("figcaption")
                if figcaption:
                    caption = figcaption.get_text(strip=True)

            # Filter heuristics: prioritize images with descriptive chart/data captions
            caption_lower = caption.lower()
            is_candidate = any(
                keyword in caption_lower or keyword in raw_src.lower()
                for keyword in ["figure", "fig", "chart", "diagram", "plot", "table", "benchmark"]
            )

            if is_candidate and absolute_url.startswith("http"):
                saved_path = await self._download_image(absolute_url)
                if saved_path:
                    images.append(
                        ExtractedImage(
                            id=f"img_{hashlib.md5(absolute_url.encode()).hexdigest()[:12]}",
                            file_path=str(saved_path),
                            source_url=absolute_url,
                            caption=caption or "Extracted web diagram",
                        )
                    )

        return images

    async def _download_image(self, url: str) -> Path | None:
        """Download an image to local storage with anti-bot headers."""
        try:
            headers = get_stealth_headers(referer=url)
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 2048:  # ignore tiny icons < 2KB
                    file_hash = hashlib.md5(url.encode()).hexdigest()
                    file_path = self.output_dir / f"{file_hash}.png"
                    file_path.write_bytes(resp.content)
                    return file_path
        except Exception as e:
            logger.debug("Failed to download image %s: %s", url, str(e))
        return None
