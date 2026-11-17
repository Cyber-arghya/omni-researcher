"""FastAPI web server exposing REST endpoints, SSE telemetry, and Cockpit UI."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agents.director import ResearchDirector
from src.config import settings
from src.crawler.crawler_engine import CrawlerEngine
from src.exporters.audio_script import AudioScriptExporter
from src.exporters.latex_export import LatexExporter
from src.hardware import HardwareProfiler
from src.state.schemas import ResearchState

logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenDeepResearcher API & Cockpit",
    version="0.2.0",
    description="Autonomous Deep Research Agent with GraphRAG, Firecrawl scraping, and Real-Time Cockpit UI.",
)

# Active session store in memory
SESSIONS: dict[str, ResearchState] = {}
SESSION_REPORTS: dict[str, dict[str, Any]] = {}
crawler_engine = CrawlerEngine()

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class EventBroadcaster:
    """Publish-subscribe event broadcaster for SSE streams."""

    def __init__(self) -> None:
        self.subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        if session_id not in self.subscribers:
            self.subscribers[session_id] = []
        self.subscribers[session_id].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if session_id in self.subscribers and queue in self.subscribers[session_id]:
            self.subscribers[session_id].remove(queue)
            if not self.subscribers[session_id]:
                del self.subscribers[session_id]

    async def broadcast(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        if session_id in self.subscribers:
            for queue in list(self.subscribers[session_id]):
                await queue.put({"event": event_type, "data": data})


broadcaster = EventBroadcaster()


# --- Pydantic Request Models ---


class StartResearchRequest(BaseModel):
    topic: str = Field(description="Target research query")
    depth: int = Field(default=2, ge=1, le=4)
    user_constraints: str = Field(default="")


class SteerRequest(BaseModel):
    action: str = Field(default="APPROVE", description="HITL action: APPROVE, PIVOT, ABORT")
    feedback: str = Field(default="", description="Steering prompt or constraints")


class ScrapeRequest(BaseModel):
    url: str = Field(description="Target URL to scrape")


class CrawlRequest(BaseModel):
    url: str = Field(description="Domain root URL to recursively crawl")
    max_depth: int = Field(default=2, ge=1, le=3)
    max_pages: int = Field(default=15, ge=1, le=50)


class ConfigUpdateRequest(BaseModel):
    llm_provider: str | None = None
    llm_fast_model: str | None = None
    llm_deep_model: str | None = None
    llm_base_url: str | None = None
    max_cost_limit_usd: float | None = None


class HardwareProfileRequest(BaseModel):
    profile: str = Field(description="Hardware tier profile name")


# --- Background Worker ---


async def _run_research_background(state: ResearchState) -> None:
    session_id = state.session_id
    director = ResearchDirector()
    try:
        # 1. Announce planning stage
        await broadcaster.broadcast(
            session_id,
            "agent_status",
            {
                "stage": "PLANNING",
                "detail": "Formulating research queries & sub-topics",
                "tokens": state.total_tokens_used,
                "cost_usd": state.estimated_cost_usd,
            },
        )

        # 2. Hardware telemetry broadcast
        vram, ram, _ = HardwareProfiler.probe_system_resources()
        await broadcaster.broadcast(
            session_id,
            "hardware_metrics",
            {"vram_used_gb": vram, "vram_total_gb": vram or 8.0, "ram_gb": ram},
        )

        # 3. Run research loop
        report = await director.run_research(state, unattended=True)

        # 4. Generate formats
        md_text = report.chapters[0]["content_markdown"] if report.chapters else ""
        latex_text = (
            LatexExporter().export(report)[0].read_text(encoding="utf-8") if report.chapters else ""
        )
        audio_script = (
            AudioScriptExporter().export(report).read_text(encoding="utf-8")
            if report.chapters
            else ""
        )

        report_payload = {
            "session_id": session_id,
            "title": report.title,
            "executive_summary": report.executive_summary,
            "markdown_content": md_text,
            "latex_content": latex_text,
            "audio_script": audio_script,
            "citations": report.citations,
            "bibtex": report.bibtex_entries,
        }
        SESSION_REPORTS[session_id] = report_payload

        # 5. Broadcast complete
        await broadcaster.broadcast(session_id, "report_completed", report_payload)

    except Exception as e:
        logger.exception("Research execution failed for session %s", session_id)
        state.status = "FAILED"
        state.error_message = str(e)
        await broadcaster.broadcast(
            session_id,
            "agent_status",
            {"stage": "FAILED", "detail": str(e), "tokens": state.total_tokens_used},
        )


# --- Cockpit UI Route ---


@app.get("/", response_class=HTMLResponse)
async def serve_cockpit_ui() -> HTMLResponse:
    """Serve the single-page application Cockpit UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            "<html><body><h2>OpenDeepResearcher Cockpit index.html not found</h2></body></html>",
            status_code=404,
        )
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


# --- SSE Telemetry Route ---


@app.get("/api/events/{session_id}")
async def sse_events(session_id: str) -> StreamingResponse:
    """Server-Sent Events endpoint streaming real-time agent progression."""

    async def event_generator() -> Any:
        queue = broadcaster.subscribe(session_id)
        # Send initial status
        state = SESSIONS.get(session_id)
        init_stage = state.status if state else "INITIALIZING"
        init_payload = {
            "stage": init_stage,
            "detail": f"Connected to session {session_id}",
            "tokens": state.total_tokens_used if state else 0,
            "cost_usd": state.estimated_cost_usd if state else 0.0,
        }
        yield f"event: agent_status\ndata: {json.dumps(init_payload)}\n\n"

        # If already completed, emit report immediately
        if session_id in SESSION_REPORTS:
            yield f"event: report_completed\ndata: {json.dumps(SESSION_REPORTS[session_id])}\n\n"

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                    if event["event"] in ("report_completed", "error"):
                        break
                except TimeoutError:
                    # SSE Keep-alive heartbeat ping
                    yield ": ping\n\n"
        finally:
            broadcaster.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Research API Endpoints ---


@app.post("/api/research")
@app.post("/research")
async def start_research(
    request: StartResearchRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Initiate an autonomous deep research mission."""
    session_id = f"session_{abs(hash(request.topic))}"
    state = ResearchState(
        session_id=session_id,
        topic=request.topic,
        target_depth=request.depth,
        user_constraints=request.user_constraints,
    )
    SESSIONS[session_id] = state

    background_tasks.add_task(_run_research_background, state)

    return {
        "session_id": session_id,
        "status": "INITIALIZED",
        "topic": request.topic,
        "depth": request.depth,
    }


@app.get("/api/sessions/{session_id}")
@app.get("/research/{session_id}")
async def get_research_status(session_id: str) -> dict[str, Any]:
    """Retrieve real-time status, saturation index, and token metrics."""
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Research session not found")

    report_payload = SESSION_REPORTS.get(session_id)
    return {
        "session_id": state.session_id,
        "topic": state.topic,
        "status": state.status,
        "current_depth": state.current_depth,
        "target_depth": state.target_depth,
        "information_saturation": state.information_saturation,
        "documents_collected": len(state.collected_documents),
        "total_tokens_used": state.total_tokens_used,
        "estimated_cost_usd": state.estimated_cost_usd,
        "error_message": state.error_message,
        "final_report": report_payload,
        "graph_nodes": [],
        "graph_edges": [],
    }


@app.get("/api/history")
async def get_history() -> list[dict[str, Any]]:
    """Retrieve recent research session history."""
    return [
        {
            "session_id": s.session_id,
            "topic": s.topic,
            "status": s.status,
            "depth": s.target_depth,
            "documents": len(s.collected_documents),
            "tokens": s.total_tokens_used,
        }
        for s in reversed(list(SESSIONS.values()))
    ]


@app.post("/api/sessions/{session_id}/steer")
async def steer_session(session_id: str, request: SteerRequest) -> dict[str, Any]:
    """Submit human-in-the-loop steering feedback."""
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Research session not found")

    if request.action == "PIVOT" and request.feedback:
        state.user_constraints += f" [User Steering]: {request.feedback}"
    elif request.action == "ABORT":
        state.status = "ABORTED"

    return {"session_id": session_id, "action": request.action, "status": state.status}


@app.get("/research/{session_id}/report")
async def get_research_report(session_id: str) -> dict[str, Any]:
    """Retrieve finalized research report, chapters, and citations."""
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Research session not found")

    if state.status != "COMPLETED":
        return {"status": state.status, "message": "Research still in progress or incomplete"}

    report = state.final_report
    return {
        "session_id": state.session_id,
        "title": report.title if report else "",
        "executive_summary": report.executive_summary if report else "",
        "markdown_content": report.chapters[0]["content_markdown"]
        if (report and report.chapters)
        else "",
        "citations": report.citations if report else [],
        "bibtex": report.bibtex_entries if report else [],
    }


# --- Hardware Profiling Endpoints ---


@app.get("/api/hardware/status")
async def get_hardware_status() -> dict[str, Any]:
    """Return host hardware metrics, detected profile, and dynamic limits."""
    vram_gb, ram_gb, cpu_cores = HardwareProfiler.probe_system_resources()
    preset = HardwareProfiler.get_tier_config(
        requested_profile=settings.hardware_profile, provider=settings.llm_provider
    )
    active_tier = preset.get("resolved_tier", "entry_8gb")
    return {
        "active_tier": active_tier,
        "vram_gb": vram_gb,
        "ram_gb": ram_gb,
        "cpu_cores": cpu_cores,
        "preset": {
            "name": active_tier,
            "description": preset.get("description", ""),
            "max_concurrent_crawlers": preset.get("crawler_concurrency", 3),
            "chunk_size": preset.get("max_context_tokens", 8192),
            "embedding_batch_size": preset.get("crawler_batch_size", 3),
            "embedding_device": preset.get("embedding_device", "cpu"),
            "fast_model": preset.get("fast_model", ""),
            "deep_model": preset.get("deep_model", ""),
        },
    }


@app.post("/api/hardware/profile")
async def set_hardware_profile(request: HardwareProfileRequest) -> dict[str, Any]:
    """Manually override the active hardware profile."""
    valid_profiles = [
        "auto",
        "entry_8gb",
        "enthusiast_16gb",
        "workstation_24gb_plus",
        "cloud_hybrid",
    ]
    if request.profile not in valid_profiles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile '{request.profile}'. Must be one of {valid_profiles}",
        )
    settings.hardware_profile = request.profile  # type: ignore[assignment]
    return {"status": "OK", "hardware_profile": settings.hardware_profile}


# --- Config & Health Endpoints ---


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Retrieve runtime LLM and cost configuration."""
    return {
        "llm_provider": settings.llm_provider,
        "llm_fast_model": settings.llm_fast_model,
        "llm_deep_model": settings.llm_deep_model,
        "llm_base_url": settings.llm_base_url,
        "max_cost_limit_usd": settings.max_cost_limit_usd,
    }


@app.post("/api/config")
async def update_config(request: ConfigUpdateRequest) -> dict[str, Any]:
    """Dynamically update runtime configuration parameters."""
    if request.llm_provider is not None:
        settings.llm_provider = request.llm_provider  # type: ignore[assignment]
    if request.llm_fast_model is not None:
        settings.llm_fast_model = request.llm_fast_model
    if request.llm_deep_model is not None:
        settings.llm_deep_model = request.llm_deep_model
    if request.llm_base_url is not None:
        settings.llm_base_url = request.llm_base_url
    if request.max_cost_limit_usd is not None:
        settings.max_cost_limit_usd = request.max_cost_limit_usd

    return {"status": "UPDATED", "config": await get_config()}


@app.get("/api/health/ollama")
async def ping_ollama() -> dict[str, Any]:
    """Test connectivity to the local Ollama instance."""
    url = f"{settings.llm_base_url.rstrip('/v1').rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return {
                    "ok": True,
                    "message": f"Connected to Ollama! Found {len(models)} local models.",
                    "models": [m.get("name") for m in models],
                }
            return {
                "ok": False,
                "message": f"Ollama returned HTTP status {resp.status_code}",
            }
    except Exception as e:
        return {"ok": False, "message": f"Cannot reach Ollama at {url}: {e}"}


# --- Web Scraping & Crawling Endpoints ---


@app.post("/scrape")
async def scrape_page(request: ScrapeRequest) -> dict[str, Any]:
    """Firecrawl-grade single page extraction endpoint."""
    doc = await crawler_engine.scrape(request.url)
    if not doc:
        raise HTTPException(status_code=422, detail="Failed to scrape content or page was blocked.")

    return {
        "url": doc.url,
        "title": doc.title,
        "markdown": doc.raw_markdown,
        "clean_text": doc.clean_text,
        "images_extracted": len(doc.images),
    }


@app.post("/crawl")
async def crawl_domain(request: CrawlRequest) -> dict[str, Any]:
    """Firecrawl-grade recursive domain crawler endpoint."""
    docs = await crawler_engine.crawl(
        request.url, max_depth=request.max_depth, max_pages=request.max_pages
    )
    return {
        "root_url": request.url,
        "pages_crawled": len(docs),
        "documents": [{"url": d.url, "title": d.title} for d in docs],
    }
