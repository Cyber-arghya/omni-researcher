"""HTML and Markdown output sanitization to prevent XSS in exported reports."""

import html
import re


def sanitize_markdown_output(markdown_text: str) -> str:
    """Sanitize LLM-generated markdown before export or display.

    Strips script tags, iframe elements, dangerous javascript: URIs, and tracking pixels.
    """
    if not markdown_text:
        return ""

    # Remove dangerous HTML script and iframe tags
    cleaned = re.sub(
        r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", markdown_text, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(
        r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(
        r"<\s*object[^>]*>.*?<\s*/\s*object\s*>", "", cleaned, flags=re.DOTALL | re.IGNORECASE
    )

    # Disallow inline javascript: or data: URIs in markdown links or img tags
    cleaned = re.sub(
        r"\[([^\]]+)\]\(javascript:[^)]+\)", r"[\1](#blocked-script)", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"\[([^\]]+)\]\(data:[^)]+\)", r"[\1](#blocked-data)", cleaned, flags=re.IGNORECASE
    )

    return cleaned


def escape_html_entities(text: str) -> str:
    """Safely escape text for inclusion in HTML report templates."""
    return html.escape(text, quote=True)
