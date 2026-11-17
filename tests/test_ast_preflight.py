"""Rigorous security and edge-case unit tests for AST pre-flight verification, path sandboxing, SSRF guards, and sanitization."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.security.preflight import (
    ToolCallSchema,
    verify_ast_safety,
    verify_path_sandbox,
    verify_url_safety,
)
from src.security.sanitizer import sanitize_markdown_output


# ==========================================
# 1. AST Pre-flight Safety Checks
# ==========================================
def test_ast_safety_checker_safe_code() -> None:
    """Verify that legitimate Python calculations and data manipulations pass."""
    safe_samples = [
        "x = [1, 2, 3]\ny = sum(x)\nprint(y)",
        "result = {i: i**2 for i in range(10) if i % 2 == 0}",
        "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)",
    ]
    for code in safe_samples:
        assert verify_ast_safety(code) is True


def test_ast_safety_checker_blocked_constructs() -> None:
    """Verify detection and rejection of imports, system calls, and eval/exec."""
    dangerous_samples = [
        "import os\nos.system('calc.exe')",
        "from subprocess import Popen\nPopen(['whoami'])",
        'eval(\'__import__("os").system("whoami")\')',
        "exec('print(\"untrusted code execution\")')",
        "compile('x = 1', 'test', 'exec')",
        "import shutil\nshutil.rmtree('/tmp')",
        "os.popen('cat /etc/passwd')",
    ]
    for code in dangerous_samples:
        assert verify_ast_safety(code) is False


def test_ast_safety_checker_syntax_error_handling() -> None:
    """Verify that malformed or syntax-error Python strings return False cleanly without crashing."""
    assert verify_ast_safety("def broken_syntax(::: unclosed") is False
    assert verify_ast_safety("for while if else") is False


# ==========================================
# 2. Path Sandboxing & Confinement
# ==========================================
def test_path_sandbox_confinement(tmp_path: Path) -> None:
    """Verify path traversal blocks outside sandbox roots."""
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()

    safe_file = sandbox_root / "report.md"
    safe_file.touch()
    assert verify_path_sandbox(safe_file, allowed_roots=[sandbox_root]) == safe_file.resolve()

    # Traversal via parent directory
    outside_file = tmp_path / "outside.txt"
    outside_file.touch()
    with pytest.raises(PermissionError, match="escapes designated sandbox"):
        verify_path_sandbox(outside_file, allowed_roots=[sandbox_root])

    # Traversal via '..' string path
    traversal_path = sandbox_root / ".." / "outside.txt"
    with pytest.raises(PermissionError, match="escapes designated sandbox"):
        verify_path_sandbox(traversal_path, allowed_roots=[sandbox_root])


def test_path_sandbox_windows_reserved_names(tmp_path: Path) -> None:
    """Verify Windows reserved device names (CON, PRN, AUX, NUL, COM1) are strictly rejected."""
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()

    for reserved in ["CON.txt", "NUL.json", "aux.md", "com1.log", "PRN"]:
        reserved_path = sandbox_root / reserved
        with pytest.raises(PermissionError, match="Reserved Windows filename is prohibited"):
            verify_path_sandbox(reserved_path, allowed_roots=[sandbox_root])


# ==========================================
# 3. URL & SSRF Safety
# ==========================================
def test_url_ssrf_safety() -> None:
    """Verify public URLs are permitted and intranet/loopback/cloud-metadata are blocked."""
    # Allowed public addresses
    assert verify_url_safety("https://arxiv.org/abs/2401.0001") is True
    assert verify_url_safety("https://api.semanticscholar.org/graph/v1") is True
    assert verify_url_safety("http://example.com/data") is True

    # Blocked loopbacks & local services
    assert verify_url_safety("http://localhost:8000") is False
    assert verify_url_safety("http://127.0.0.1:11434") is False
    assert verify_url_safety("http://0.0.0.0:80") is False
    assert verify_url_safety("http://[::1]:8080") is False

    # Blocked AWS/GCP cloud metadata endpoint
    assert verify_url_safety("http://169.254.169.254/latest/meta-data/") is False

    # Blocked private LAN subnets
    assert verify_url_safety("http://192.168.1.1/admin") is False
    assert verify_url_safety("http://10.0.0.5/api") is False
    assert verify_url_safety("http://172.16.0.10:9000") is False

    # Blocked non-HTTP schemes
    assert verify_url_safety("ftp://malicious.com/payload") is False
    assert verify_url_safety("file:///etc/passwd") is False
    assert verify_url_safety("javascript:alert(1)") is False


# ==========================================
# 4. Tool Call Schema Validation
# ==========================================
def test_tool_call_schema_validation() -> None:
    """Verify Pydantic validation rejects shell injection metacharacters."""
    # Valid call
    valid_call = ToolCallSchema(
        query="solid state battery advances",
        url="https://nature.com/articles/123",
        file_path="storage/report.md",
    )
    assert valid_call.query == "solid state battery advances"

    # Injections containing ;, |, &, $, ` must raise ValidationError
    injection_queries = [
        "quantum battery; rm -rf /",
        "deep learning | curl attacker.com",
        "ai research `id`",
        "search && echo hacked",
        "search $SECRET_KEY",
    ]
    for bad_query in injection_queries:
        with pytest.raises(ValidationError):
            ToolCallSchema(query=bad_query)


# ==========================================
# 5. Markdown Sanitizer
# ==========================================
def test_markdown_sanitization() -> None:
    """Verify dangerous XSS constructs are stripped while legitimate markdown remains intact."""
    dirty_md = (
        "# Clean Heading\n"
        "<script>alert(1)</script>\n"
        "<iframe src='http://evil.com'></iframe>\n"
        "[Dangerous](javascript:alert('pwned'))\n"
        "Here is a [Legit Link](https://arxiv.org/abs/2401.0001) and **bold text**."
    )
    clean_md = sanitize_markdown_output(dirty_md)

    assert "<script>" not in clean_md
    assert "<iframe" not in clean_md
    assert "javascript:" not in clean_md
    assert "# Clean Heading" in clean_md
    assert "**bold text**" in clean_md
    assert "https://arxiv.org/abs/2401.0001" in clean_md
