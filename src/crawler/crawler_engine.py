"""Firecrawl-grade recursive crawler engine implementing /scrape, /crawl, and /map."""

import asyncio
import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.crawler.scraper import WebScraper
from src.crawler.stealth import get_stealth_headers
from src.state.schemas import ScrapedDocument

logger = logging.getLogger(__name__)


class CrawlerEngine:
    """Orchestrates recursive domain crawling, URL mapping, and content extraction."""

    def __init__(self, scraper: WebScraper | None = None) -> None:
        self.scraper = scraper or WebScraper()

    async def scrape(self, url: str) -> ScrapedDocument | None:
        """Endpoint equivalent to /scrape: extracts content from a single URL."""
        return await self.scraper.scrape_url(url)

    async def map_domain(self, base_url: str, max_urls: int = 50) -> list[str]:
        """Endpoint equivalent to /map: discovers valid internal links across a domain without full content scrape."""
        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc

        discovered_urls: set[str] = {base_url}
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(base_url, headers=get_stealth_headers())
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a_tag in soup.find_all("a", href=True):
                        raw_href = a_tag.get("href")
                        if not isinstance(raw_href, str):
                            continue
                        full_url = urljoin(base_url, raw_href)
                        parsed = urlparse(full_url)

                        if parsed.netloc == domain and full_url.startswith("http"):
                            # Filter out anchor links and asset files
                            clean_url = full_url.split("#")[0].rstrip("/")
                            if not any(
                                clean_url.endswith(ext)
                                for ext in [".png", ".jpg", ".pdf", ".zip", ".css"]
                            ):
                                discovered_urls.add(clean_url)
                                if len(discovered_urls) >= max_urls:
                                    break
        except Exception as e:
            logger.warning("Error mapping domain %s: %s", domain, str(e))

        return list(discovered_urls)

    async def crawl(
        self,
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 20,
    ) -> list[ScrapedDocument]:
        """Endpoint equivalent to /crawl: recursively crawls domain up to max_depth."""
        queue: list[tuple[str, int]] = [(start_url, 0)]
        visited: set[str] = set()
        crawled_docs: list[ScrapedDocument] = []

        domain = urlparse(start_url).netloc

        while queue and len(crawled_docs) < max_pages:
            current_url, depth = queue.pop(0)
            normalized = current_url.rstrip("/")

            if normalized in visited or depth > max_depth:
                continue

            visited.add(normalized)
            doc = await self.scrape(current_url)

            if doc:
                crawled_docs.append(doc)

                # If within depth limit, find next level internal links
                if depth < max_depth:
                    internal_links = await self.map_domain(current_url, max_urls=10)
                    for link in internal_links:
                        if link not in visited and urlparse(link).netloc == domain:
                            queue.append((link, depth + 1))

            await asyncio.sleep(0.5)

        return crawled_docs
