"""Firecrawl-grade HTML-to-Clean-Markdown normalizer with table recovery."""

import re
from typing import ClassVar

import trafilatura
from bs4 import BeautifulSoup, Comment


class HTMLNormalizer:
    """Cleans messy DOM trees and produces structured, semantic Markdown."""

    JUNK_TAGS: ClassVar[list[str]] = [
        "script",
        "style",
        "noscript",
        "svg",
        "header",
        "footer",
        "nav",
        "aside",
        "iframe",
        "form",
        "button",
    ]

    PAYWALL_PATTERNS: ClassVar[list[str]] = [
        r"subscribe to continue reading",
        r"create a free account to read",
        r"you have reached your free article limit",
        r"sign in to read the full story",
        r"this content is exclusive to subscribers",
    ]

    def is_likely_paywall_or_junk(self, text: str) -> bool:
        """Detect if page content is just a paywall screen or cookie consent stub."""
        lower_text = text.lower()
        word_count = len(text.split())

        if word_count < 100:
            return True

        return any(re.search(pattern, lower_text) for pattern in self.PAYWALL_PATTERNS)

    def normalize_html_to_markdown(self, html_content: str, url: str = "") -> tuple[str, str]:
        """Convert raw HTML into clean Markdown and plain text.

        Returns:
            Tuple of (clean_markdown, plain_text)
        """
        if not html_content:
            return "", ""

        # Tier 1: Try trafilatura extraction first for maximum boilerplate removal
        extracted = trafilatura.extract(
            html_content,
            url=url,
            output_format="markdown",
            include_tables=True,
            include_images=True,
            include_links=True,
            favor_precision=True,
        )

        if extracted and len(extracted.split()) > 150:
            plain_text = (
                trafilatura.extract(html_content, url=url, output_format="txt") or extracted
            )
            return extracted, plain_text

        # Tier 2: BeautifulSoup cleanup fallback for custom DOM structures
        soup = BeautifulSoup(html_content, "html.parser")

        # Strip comments
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        # Remove junk elements
        for tag_name in self.JUNK_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # Target article or main tag if present
        target_root = soup.find("article") or soup.find("main") or soup.find("body") or soup
        text = target_root.get_text(separator="\n", strip=True)

        # Normalize redundant newlines
        cleaned_text = re.sub(r"\n{3,}", "\n\n", text)
        return cleaned_text, cleaned_text
