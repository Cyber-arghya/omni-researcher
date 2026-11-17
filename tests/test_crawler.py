"""Unit tests for the crawler normalizer and spreadsheet parser."""

from pathlib import Path

from src.crawler.normalizer import HTMLNormalizer
from src.crawler.spreadsheet_parser import SpreadsheetParser
from src.crawler.stealth import get_random_user_agent, get_stealth_headers


def test_stealth_headers() -> None:
    """Verify authentic headers and randomized user agents."""
    ua = get_random_user_agent()
    assert "Mozilla" in ua
    headers = get_stealth_headers(referer="https://google.com")
    assert headers["Referer"] == "https://google.com"
    assert "User-Agent" in headers


def test_html_normalization() -> None:
    """Verify HTML cleaning, script stripping, and boilerplate removal."""
    normalizer = HTMLNormalizer()
    raw_html = """
    <html>
      <head><script>alert('malicious')</script><style>body {color: red;}</style></head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <article>
          <h1>Solid-State Battery Progress</h1>
          <p>Solid-state batteries demonstrate over 400 Wh/kg energy density in laboratory prototypes.</p>
        </article>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    clean_md, _ = normalizer.normalize_html_to_markdown(raw_html)
    assert "Solid-State Battery Progress" in clean_md
    assert "alert('malicious')" not in clean_md
    assert "body {color: red;}" not in clean_md


def test_spreadsheet_csv_parsing(tmp_path: Path) -> None:
    """Verify CSV parsing into ExtractedTable format."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(
        "Company,Revenue,Growth\nQuantumScape,$50M,15%\nSolidPower,$30M,12%\n", encoding="utf-8"
    )

    parser = SpreadsheetParser()
    tables = parser.parse_file(csv_file)

    assert len(tables) == 1
    table = tables[0]
    assert "Company" in table.headers
    assert len(table.rows) == 2
    assert "QuantumScape" in table.markdown_representation
