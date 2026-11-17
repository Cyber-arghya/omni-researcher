"""AST pre-flight verification, path sandbox confinement, and URL security checks."""

import ast
import ipaddress
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.config import settings

# Disallowed AST nodes and function calls in agent-generated dynamic code
BLOCKED_AST_NODES = {ast.Import, ast.ImportFrom, ast.Exec if hasattr(ast, "Exec") else type(None)}
BLOCKED_CALL_NAMES = {
    "exec",
    "eval",
    "compile",
    "os.system",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "shutil.rmtree",
}

# Windows reserved device names
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}


class ToolCallSchema(BaseModel):
    """Strict schema for every tool invocation argument."""

    query: Annotated[str, Field(max_length=500, pattern=r"^[^;<>&|`$]+$")]
    url: Annotated[str, Field(pattern=r"^https?://[^\s]+$")] | None = None
    file_path: Annotated[str, Field(max_length=260)] | None = None


def verify_ast_safety(code_str: str) -> bool:
    """Parse and walk Python AST to reject dangerous function calls or imports.

    Returns:
        True if safe, False if malicious/dangerous AST node is detected.
    """
    try:
        tree = ast.parse(code_str, mode="exec")
        for node in ast.walk(tree):
            if type(node) in BLOCKED_AST_NODES:
                return False

            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALL_NAMES)
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("system", "popen", "rmtree")
                )
            ):
                return False

        return True
    except SyntaxError:
        return False


def verify_path_sandbox(file_path: str | Path, allowed_roots: list[Path] | None = None) -> Path:
    """Resolve and confine target path within allowed project storage boundaries.

    Prevents directory traversal attacks (../) and Windows reserved device names.
    """
    resolved = Path(file_path).resolve()
    roots = allowed_roots or [settings.storage_dir.resolve(), settings.reports_dir.resolve()]

    # Confine to designated project sandbox directories
    if not any(resolved.is_relative_to(root) for root in roots):
        raise PermissionError(f"Security Alert: Path escapes designated sandbox: {resolved}")

    # Check for Windows device names (CON, NUL, AUX, PRN)
    if resolved.stem.upper() in WINDOWS_RESERVED_NAMES:
        raise PermissionError(
            f"Security Alert: Reserved Windows filename is prohibited: {resolved.name}"
        )

    return resolved


def verify_url_safety(url: str) -> bool:
    """Validate that URL does not point to internal metadata endpoints or private IPs (SSRF protection)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False

        # Disallow loopback, link-local, and cloud metadata hostnames
        blocked_named_hosts = {
            "localhost",
            "metadata.google.internal",
            "instance-data",
        }
        if hostname in blocked_named_hosts:
            return False

        # Normalize IPv6 brackets if present
        clean_host = hostname.strip("[]")

        # Check IP-based private, loopback, link-local, reserved ranges
        try:
            ip = ipaddress.ip_address(clean_host)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        except ValueError:
            # Hostname is a domain name (not an IP literal)
            pass

        return True
    except Exception:
        return False
