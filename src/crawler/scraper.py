"""Tiered web scraper combining high-speed async HTTP with stealth browser fallback."""

import hashlib
import logging

import httpx

from src.config import settings
from src.crawler.image_extractor import VisualImageExtractor
from src.crawler.normalizer import HTMLNormalizer
from src.crawler.stealth import get_stealth_headers
from src.state.schemas import ScrapedDocument

logger = logging.getLogger(__name__)


class WebScraper:
    """High-resilience web scraper with anti-bot evasion and content normalization."""

    def __init__(self) -> None:
        self.normalizer = HTMLNormalizer()
        self.image_extractor = VisualImageExtractor()
        self.timeout = settings.scraper_timeout_seconds

    async def scrape_url(self, url: str) -> ScrapedDocument | None:
        """Scrape and normalize a single URL into a structured ScrapedDocument."""
        doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]

        # Tier 1: High-Speed Async HTTP Request
        html_content, status_code = await self._fetch_http(url)

        # Check if Tier 1 was blocked or returned insufficient JavaScript-rendered content
        if status_code in (403, 429) or (html_content and len(html_content.split()) < 50):
            logger.info(
                "Tier 1 HTTP blocked or sparse (%d) for %s. Attempting Playwright fallback...",
                status_code,
                url,
            )
            html_content = await self._fetch_playwright(url)

        if not html_content:
            logger.warning("Scraper received empty content for %s", url)
            return None

        # Check for paywall or anti-bot challenge stubs
        if self.normalizer.is_likely_paywall_or_junk(html_content):
            logger.info("Discarding %s: identified as paywall or low-quality stub.", url)
            return None

        clean_markdown, plain_text = self.normalizer.normalize_html_to_markdown(
            html_content, url=url
        )
        images = await self.image_extractor.extract_from_html(html_content, base_url=url)

        # Simple title extraction heuristic
        title = url
        if "#" in clean_markdown[:200]:
            first_line = clean_markdown.strip().split("\n")[0]
            title = first_line.replace("#", "").strip()

        return ScrapedDocument(
            id=doc_id,
            url=url,
            title=title,
            raw_markdown=clean_markdown,
            clean_text=plain_text,
            images=images,
            metadata={"status_code": status_code},
        )

    async def _fetch_http(self, url: str) -> tuple[str | None, int]:
        """Fetch raw HTML using async httpx with stealth headers."""
        headers = get_stealth_headers()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                return resp.text, resp.status_code
        except Exception as e:
            logger.debug("HTTP fetch error on %s: %s", url, str(e))
            return None, 500

    async def _fetch_playwright(self, url: str) -> str | None:
        """Headless browser fallback for dynamic React/Vue SPAs or anti-bot bypass."""
        if not settings.headless_browser_enabled:
            return None

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=get_stealth_headers()["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                # Block heavy media downloads to ensure blazing fast page loads
                await page.route(
                    "**/*.{mp4,mp3,avi,mkv,flv,woff,woff2,ttf}",
                    lambda route: route.abort(),
                )

                await page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
                content = await page.content()
                await browser.close()
                return str(content) if content else None
        except ImportError:
            logger.debug("Playwright not installed, skipping headless fallback.")
            return None
        except Exception as e:
            logger.debug("Playwright fetch failed on %s: %s", url, str(e))
            return None
