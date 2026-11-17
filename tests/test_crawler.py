"""Comprehensive unit tests for crawler normalizer, spreadsheet parser, and stealth evasion."""

from pathlib import Path

import openpyxl
import pytest

from src.crawler.normalizer import HTMLNormalizer
from src.crawler.spreadsheet_parser import SpreadsheetParser
from src.crawler.stealth import get_random_user_agent, get_stealth_headers


# ==========================================
# 1. Stealth Evasion Headers
# ==========================================
def test_stealth_headers_and_randomized_ua() -> None:
    """Verify authentic headers and randomized desktop user agents."""
    uas = {get_random_user_agent() for _ in range(10)}
    assert len(uas) > 1, "User agents must vary across invocations"
    for ua in uas:
        assert "Mozilla" in ua
        assert "AppleWebKit" in ua or "Gecko" in ua

    headers = get_stealth_headers(referer="https://google.com")
    assert headers["Referer"] == "https://google.com"
    assert "User-Agent" in headers
    assert "Accept-Language" in headers
    assert "Sec-Fetch-Dest" in headers


# ==========================================
# 2. HTML Normalization & Paywall Filtering
# ==========================================
def test_html_normalization_happy_path() -> None:
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
    clean_md, plain_text = normalizer.normalize_html_to_markdown(raw_html)
    assert "Solid-State Battery Progress" in clean_md
    assert "alert('malicious')" not in clean_md
    assert "body {color: red;}" not in clean_md
    assert len(plain_text) > 0


def test_html_normalization_empty_and_corrupted() -> None:
    """Verify normalizer handles empty and malformed HTML without crashing."""
    normalizer = HTMLNormalizer()
    # Empty string
    md_empty, txt_empty = normalizer.normalize_html_to_markdown("")
    assert md_empty == ""
    assert txt_empty == ""

    # Malformed HTML
    malformed = "<div unclosed tag><p>Text without closing"
    md_malformed, _ = normalizer.normalize_html_to_markdown(malformed)
    assert "Text without closing" in md_malformed


def test_paywall_and_junk_detection() -> None:
    """Verify detection of paywalls and low-word-count boilerplate stubs."""
    normalizer = HTMLNormalizer()

    # Short stub (< 100 words)
    assert normalizer.is_likely_paywall_or_junk("Short page with few words.") is True

    # Paywall trigger phrase
    paywall_text = (
        "This is an in-depth article about renewable energy technologies. " * 15
        + "You have reached your free article limit. Subscribe to continue reading."
    )
    assert normalizer.is_likely_paywall_or_junk(paywall_text) is True

    # Clean legitimate long article
    clean_article = (
        "Solid state batteries utilize solid electrolytes rather than liquid or polymer gel electrolytes. "
        "Materials proposed for use as solid electrolytes in solid-state batteries include ceramics such as "
        "sulfides, phosphates, and oxides, as well as solid polymer electrolytes. Solid-state batteries find "
        "potential use in pacemakers, RFID devices, wearable devices, and electric vehicles. They are potentially "
        "safer, with higher energy densities, but at a much higher cost. Challenges to widespread adoption include "
        "energy and power density, durability, material costs, sensitivity and stability. "
    ) * 4
    assert normalizer.is_likely_paywall_or_junk(clean_article) is False


# ==========================================
# 3. Spreadsheet Parser (CSV & XLSX)
# ==========================================
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


def test_spreadsheet_xlsx_parsing(tmp_path: Path) -> None:
    """Verify Excel XLSX multi-cell parsing and formatting."""
    xlsx_file = tmp_path / "test_data.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "BatteryMetrics"
    ws.append(["Metric", "Target", "Achieved"])
    ws.append(["Energy Density", "500 Wh/kg", "450 Wh/kg"])
    ws.append(["Cycle Life", "1000", "800"])
    wb.save(xlsx_file)

    parser = SpreadsheetParser()
    tables = parser.parse_file(xlsx_file)
    assert len(tables) == 1
    assert "BatteryMetrics" in tables[0].title
    assert "Energy Density" in tables[0].markdown_representation


def test_spreadsheet_security_and_failure_guards(tmp_path: Path) -> None:
    """Verify security rejection of .xlsm macros, missing files, and unsupported formats."""
    parser = SpreadsheetParser()

    # 1. Non-existent file
    with pytest.raises(FileNotFoundError):
        parser.parse_file(tmp_path / "missing.csv")

    # 2. Block macro-enabled Excel (.xlsm)
    xlsm_file = tmp_path / "macro_exploit.xlsm"
    xlsm_file.write_text("fake binary", encoding="utf-8")
    with pytest.raises(ValueError, match=r"Macro-enabled Excel workbooks"):
        parser.parse_file(xlsm_file)

    # 3. Unsupported format (.docx or .exe)
    bad_file = tmp_path / "document.docx"
    bad_file.write_text("word data", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported spreadsheet format"):
        parser.parse_file(bad_file)
