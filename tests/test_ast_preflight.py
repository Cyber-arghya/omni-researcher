"""Unit tests for AST pre-flight verification, path sandboxing, and output sanitization."""

from pathlib import Path

import pytest

from src.security.preflight import (
    verify_ast_safety,
    verify_path_sandbox,
    verify_url_safety,
)
from src.security.sanitizer import sanitize_markdown_output


def test_ast_safety_checker() -> None:
    """Verify detection of malicious AST calls."""
    safe_code = "x = [1, 2, 3]\ny = sum(x)\nprint(y)"
    assert verify_ast_safety(safe_code) is True

    unsafe_import = "import os\nos.system('calc.exe')"
    assert verify_ast_safety(unsafe_import) is False

    unsafe_eval = 'eval(\'__import__("os").system("whoami")\')'
    assert verify_ast_safety(unsafe_eval) is False


def test_path_sandbox_confinement(tmp_path: Path) -> None:
    """Verify path traversal blocks outside sandbox."""
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()

    safe_file = sandbox_root / "report.md"
    safe_file.touch()
    assert verify_path_sandbox(safe_file, allowed_roots=[sandbox_root]) == safe_file.resolve()

    # Outside traversal
    outside_file = tmp_path / "outside.txt"
    outside_file.touch()
    with pytest.raises(PermissionError, match="escapes designated sandbox"):
        verify_path_sandbox(outside_file, allowed_roots=[sandbox_root])


def test_url_ssrf_safety() -> None:
    """Verify SSRF blocked addresses."""
    assert verify_url_safety("https://arxiv.org/abs/2401.0001") is True
    assert verify_url_safety("http://localhost:8000") is False
    assert verify_url_safety("http://127.0.0.1:11434") is False
    assert verify_url_safety("http://169.254.169.254/latest/meta-data/") is False


def test_markdown_sanitization() -> None:
    """Verify dangerous XSS constructs are stripped."""
    dirty_md = "# Report\n<script>alert(1)</script>\n[Click](javascript:alert(1))\nSafe content."
    clean_md = sanitize_markdown_output(dirty_md)
    assert "<script>" not in clean_md
    assert "javascript:" not in clean_md
    assert "Safe content." in clean_md
