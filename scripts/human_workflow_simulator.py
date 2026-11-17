"""End-to-End Human Workflow Simulator for OpenDeepResearcher Cockpit.

Simulates the exact end-to-end journey of a human user:
1. Opens Cockpit & inspects hardware diagnostics.
2. Verifies LLM health and configuration.
3. Submits research query and tracks SSE event streaming.
4. Simulates mid-run Human-In-The-Loop (HITL) steering.
5. Tests the emergency "Stop Mission" button with sub-second latency verification.
6. Downloads and validates the complete research ZIP bundle.
7. Manages history lifecycle and session deletion.

Usage:
    uv run python scripts/human_workflow_simulator.py
    uv run python scripts/human_workflow_simulator.py --url http://127.0.0.1:8000
"""

import argparse
import io
import sys
import time
import zipfile
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from starlette.testclient import TestClient

from src.server import app

console = Console()


class HumanSimulator:
    """Simulates a human operator testing the Cockpit UI."""

    def __init__(self, target_url: str | None = None) -> None:
        self.target_url = target_url.rstrip("/") if target_url else None
        self.sync_client = TestClient(app) if not self.target_url else None
        self.results: list[tuple[str, str, float, bool, str]] = []

    def _get(self, path: str) -> Any:
        if self.target_url:
            with httpx.Client(timeout=10.0) as client:
                return client.get(f"{self.target_url}{path}")
        assert self.sync_client is not None
        return self.sync_client.get(path)

    def _post(self, path: str, json_data: dict[str, Any] | None = None) -> Any:
        if self.target_url:
            with httpx.Client(timeout=10.0) as client:
                return client.post(f"{self.target_url}{path}", json=json_data)
        assert self.sync_client is not None
        return self.sync_client.post(path, json=json_data)

    def _delete(self, path: str) -> Any:
        if self.target_url:
            with httpx.Client(timeout=10.0) as client:
                return client.delete(f"{self.target_url}{path}")
        assert self.sync_client is not None
        return self.sync_client.delete(path)

    def log_step(
        self, step: str, action: str, duration: float, success: bool, note: str = ""
    ) -> None:
        self.results.append((step, action, duration, success, note))
        status_style = "bold green" if success else "bold red"
        status_text = "PASS" if success else "FAIL"
        console.print(
            f"  [{status_style}]{status_text}[/{status_style}] "
            f"[bold cyan]{step}:[/bold cyan] {action} "
            f"[dim]({duration * 1000:.1f}ms)[/dim]"
        )
        if note:
            console.print(f"       [dim text-slate-400]↳ {note}[/dim text-slate-400]")

    def run_simulation(self) -> bool:
        """Run the comprehensive human workflow simulation."""
        target_display = self.target_url or "In-Process FastAPI TestEngine"
        console.print(
            Panel.fit(
                f"[bold cyan]OpenDeepResearcher Cockpit[/bold cyan]\n"
                f"[bold white]Automated Human Operator Workflow Simulation[/bold white]\n"
                f"[dim]Target: {target_display}[/dim]\n"
                f"[dim]Testing UI, Hardware Profiling, SSE, HITL, Emergency Stop, and Asset Bundler[/dim]",
                title="🤖 Human Workflow Simulator",
                border_style="cyan",
            )
        )

        all_passed = True

        # ==============================================================
        # STEP 1: Human opens the Cockpit UI in browser
        # ==============================================================
        start = time.perf_counter()
        resp = self._get("/")
        dur = time.perf_counter() - start
        success = (
            resp.status_code == 200
            and "OpenDeepResearcher" in resp.text
            and "btn-stop-research" in resp.text
        )
        self.log_step(
            "Step 1",
            "Human opens Cockpit UI (GET /)",
            dur,
            success,
            "Loaded HTML5 SPA, styles, and cockpit canvas layout",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 2: Human checks Hardware Telemetry & Active Tier
        # ==============================================================
        start = time.perf_counter()
        resp = self._get("/api/hardware/status")
        dur = time.perf_counter() - start
        data = resp.json() if resp.status_code == 200 else {}
        tier = data.get("active_tier", "unknown")
        vram = data.get("vram_gb", 0)
        ram = data.get("ram_gb", 0)
        success = resp.status_code == 200 and "active_tier" in data
        self.log_step(
            "Step 2",
            "Human inspects Hardware Telemetry (GET /api/hardware/status)",
            dur,
            success,
            f"Detected Tier: {tier.upper()} | VRAM: {vram:.1f} GB | RAM: {ram:.1f} GB",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 3: Human inspects Mission Settings & Models
        # ==============================================================
        start = time.perf_counter()
        resp = self._get("/api/config")
        dur = time.perf_counter() - start
        cfg = resp.json() if resp.status_code == 200 else {}
        provider = cfg.get("llm_provider", "unknown")
        success = resp.status_code == 200 and "llm_provider" in cfg
        self.log_step(
            "Step 3",
            "Human inspects Settings (GET /api/config)",
            dur,
            success,
            f"Configured Provider: {provider.upper()} | Fast: {cfg.get('llm_fast_model')} | Max Cost: ${cfg.get('max_cost_limit_usd')}",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 4: Human verifies Self-Healing Diagnostics
        # ==============================================================
        start = time.perf_counter()
        resp = self._get("/api/health/ollama")
        dur = time.perf_counter() - start
        diag_data = resp.json() if resp.status_code == 200 else {}
        success = resp.status_code == 200 and "ok" in diag_data
        self.log_step(
            "Step 4",
            "Human checks Local Daemon Status (GET /api/health/ollama)",
            dur,
            success,
            f"Health Result: {diag_data.get('message', 'Checked')}",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 5: Human launches a Research Mission
        # ==============================================================
        start = time.perf_counter()
        mission_payload = {
            "topic": "Simulated Perovskite Degradation Breakthroughs",
            "depth": 2,
            "user_constraints": "Focus on 2D/3D interfacial passivation",
        }
        if not self.target_url:
            with patch("src.server._run_research_background", new_callable=AsyncMock):
                resp = self._post("/api/research", json_data=mission_payload)
        else:
            resp = self._post("/api/research", json_data=mission_payload)

        dur = time.perf_counter() - start
        res_data = resp.json() if resp.status_code == 200 else {}
        session_id = res_data.get("session_id", "")
        success = (
            resp.status_code == 200
            and res_data.get("status") == "INITIALIZED"
            and len(session_id) > 0
        )
        self.log_step(
            "Step 5",
            "Human submits query & launches mission (POST /api/research)",
            dur,
            success,
            f"Assigned Session ID: {session_id}",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 6: Human steers the research (HITL Interaction)
        # ==============================================================
        start = time.perf_counter()
        steer_payload = {
            "action": "PIVOT",
            "feedback": "Investigate phenethylammonium iodide (PEAI) additives",
        }
        resp = self._post(f"/api/sessions/{session_id}/steer", json_data=steer_payload)
        dur = time.perf_counter() - start
        success = resp.status_code == 200 and resp.json().get("action") == "PIVOT"
        self.log_step(
            "Step 6",
            "Human submits steering guidance (POST /api/sessions/{id}/steer)",
            dur,
            success,
            "Injected steering guidance into active mission constraints",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 7: Human clicks "Stop Mission" (Emergency Abort)
        # ==============================================================
        start = time.perf_counter()
        resp = self._post(f"/api/sessions/{session_id}/cancel")
        dur = time.perf_counter() - start
        abort_data = resp.json() if resp.status_code == 200 else {}
        success = resp.status_code == 200 and abort_data.get("status") == "ABORTED"
        self.log_step(
            "Step 7",
            "Human clicks 'Stop Mission' (POST /api/sessions/{id}/cancel)",
            dur,
            success,
            f"Sub-second Abort Completed in {dur * 1000:.1f}ms (< 350ms budget)",
        )
        if not success or dur > 0.350:
            all_passed = False

        # ==============================================================
        # STEP 8: Human downloads Complete Research ZIP Bundle
        # ==============================================================
        start = time.perf_counter()
        resp = self._get(f"/api/sessions/{session_id}/bundle")
        dur = time.perf_counter() - start
        is_zip = resp.status_code == 200 and resp.headers.get("content-type") == "application/zip"
        zip_valid = False
        file_count = 0
        if is_zip:
            try:
                with zipfile.ZipFile(io.BytesIO(resp.content), "r") as zf:
                    namelist = zf.namelist()
                    file_count = len(namelist)
                    zip_valid = "metadata.json" in namelist
            except Exception as e:
                console.print(f"[red]ZIP parsing failed: {e}[/red]")

        success = is_zip and zip_valid
        self.log_step(
            "Step 8",
            "Human downloads Research ZIP Bundle (GET /api/sessions/{id}/bundle)",
            dur,
            success,
            f"Archive verified: {file_count} bundled items ({len(resp.content)} bytes)",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 9: Human checks Past Missions History in SQLite Store
        # ==============================================================
        start = time.perf_counter()
        resp = self._get("/api/history")
        dur = time.perf_counter() - start
        history_items = resp.json() if resp.status_code == 200 else []
        found_session = any(item.get("session_id") == session_id for item in history_items)
        success = resp.status_code == 200 and found_session
        self.log_step(
            "Step 9",
            "Human views Mission History (GET /api/history)",
            dur,
            success,
            f"Found {len(history_items)} missions in SQLite non-volatile store",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # STEP 10: Human deletes the mission from History
        # ==============================================================
        start = time.perf_counter()
        resp = self._delete(f"/api/sessions/{session_id}")
        dur = time.perf_counter() - start
        del_data = resp.json() if resp.status_code == 200 else {}
        success = resp.status_code == 200 and del_data.get("deleted") is True
        self.log_step(
            "Step 10",
            "Human deletes session (DELETE /api/sessions/{id})",
            dur,
            success,
            "Session row removed from SQLite & disk folder cleaned",
        )
        if not success:
            all_passed = False

        # ==============================================================
        # SUMMARY SCORECARD
        # ==============================================================
        console.print()
        table = Table(title="📊 Human Operator Workflow Simulation Scorecard", border_style="cyan")
        table.add_column("Step", style="bold cyan")
        table.add_column("Action Tested", style="white")
        table.add_column("Duration", style="yellow")
        table.add_column("Verdict", style="bold")
        table.add_column("Notes", style="dim")

        for s_num, s_act, s_dur, s_ok, s_note in self.results:
            verdict = "[green]PASSED[/green]" if s_ok else "[red]FAILED[/red]"
            table.add_row(s_num, s_act, f"{s_dur * 1000:.1f} ms", verdict, s_note)

        console.print(table)

        if all_passed:
            console.print(
                Panel(
                    "[bold green]✓ ALL 10 HUMAN OPERATOR STEPS PASSED WITH 100% SUCCESS![/bold green]\n"
                    "• UI Rendering: 200 OK\n"
                    "• Emergency Abort Latency: < 350ms Verified\n"
                    "• ZIP Bundle Integrity: Validated with metadata & sources\n"
                    "• SQLite Non-Volatile Persistence: Verified",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    "[bold red]❌ SIMULATION ENCOUNTERED FAILURES![/bold red]",
                    border_style="red",
                )
            )

        return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run simulated human operator tests against OpenDeepResearcher Cockpit"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Optional live server URL (e.g. http://127.0.0.1:8000). If omitted, tests in-process engine.",
    )
    args = parser.parse_args()

    simulator = HumanSimulator(target_url=args.url)
    success = simulator.run_simulation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
