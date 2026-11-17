"""FastAPI web server exposing REST endpoints for research, /scrape, and /crawl."""

from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agents.director import ResearchDirector
from src.crawler.crawler_engine import CrawlerEngine
from src.state.schemas import ResearchState

app = FastAPI(
    title="OpenDeepResearcher API",
    version="0.1.0",
    description="Autonomous Deep Research Agent API with Firecrawl-equivalent scraping and GraphRAG.",
)

# Active session store in memory
SESSIONS: dict[str, ResearchState] = {}
crawler_engine = CrawlerEngine()


class StartResearchRequest(BaseModel):
    topic: str = Field(description="Target research query")
    depth: int = Field(default=2, ge=1, le=4)
    user_constraints: str = Field(default="")


class ScrapeRequest(BaseModel):
    url: str = Field(description="Target URL to scrape")


class CrawlRequest(BaseModel):
    url: str = Field(description="Domain root URL to recursively crawl")
    max_depth: int = Field(default=2, ge=1, le=3)
    max_pages: int = Field(default=15, ge=1, le=50)


async def _run_research_background(state: ResearchState) -> None:
    director = ResearchDirector()
    try:
        await director.run_research(state, unattended=True)
    except Exception as e:
        state.status = "FAILED"
        state.error_message = str(e)


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


@app.get("/research/{session_id}")
async def get_research_status(session_id: str) -> dict[str, Any]:
    """Retrieve real-time status, saturation index, and token metrics."""
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Research session not found")

    return {
        "session_id": state.session_id,
        "status": state.status,
        "current_depth": state.current_depth,
        "target_depth": state.target_depth,
        "information_saturation": state.information_saturation,
        "documents_collected": len(state.collected_documents),
        "total_tokens_used": state.total_tokens_used,
        "estimated_cost_usd": state.estimated_cost_usd,
        "error_message": state.error_message,
    }


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
