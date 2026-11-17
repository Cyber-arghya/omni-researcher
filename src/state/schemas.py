"""Core Pydantic data schemas representing the research state, documents, claims, and knowledge graph."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(UTC)


class SearchResult(BaseModel):
    """Individual search engine result item."""

    title: str = Field(description="Title of the search result")
    url: str = Field(description="Web URL of the page")
    snippet: str = Field(default="", description="Snippet or meta description from search engine")
    source_engine: str = Field(
        default="ddg", description="Search engine used (ddg, searxng, tavily, arxiv)"
    )
    score: float = Field(default=1.0, description="Relevance ranking score")


class SearchQuery(BaseModel):
    """Generated research search query with rationale."""

    query: str = Field(description="The exact search string submitted to search engine")
    perspective: str = Field(
        default="General",
        description="Perspective (e.g., Foundational, Technical Architecture, Empirical Benchmarks, Counter-arguments, Future Outlook)",
    )
    purpose: str = Field(default="", description="Why this query was formulated")
    timestamp: datetime = Field(default_factory=_utc_now)


class ExtractedTable(BaseModel):
    """Structured tabular data extracted from HTML or XLSX/CSV."""

    id: str = Field(description="Unique identifier for the table")
    title: str = Field(default="", description="Table caption or title")
    headers: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    markdown_representation: str = Field(default="", description="Rendered markdown table")


class ExtractedImage(BaseModel):
    """Visual chart or diagram extracted from page or PDF."""

    id: str = Field(description="Unique identifier for image")
    file_path: str = Field(description="Local file path where image is stored")
    source_url: str = Field(description="Original URL or document filename")
    caption: str = Field(default="", description="Caption or alt text accompanying the image")
    analysis_summary: str = Field(
        default="", description="Vision LLM analysis of the chart/diagram"
    )
    data_points: list[dict[str, Any]] = Field(
        default_factory=list, description="Extracted structured data points"
    )


class ScrapedDocument(BaseModel):
    """Normalized, cleaned document retrieved from web or local file."""

    id: str = Field(description="Deterministic hash ID (e.g. SHA-256 of URL/content)")
    url: str = Field(description="Source URL or local file path")
    title: str = Field(default="", description="Cleaned document title")
    raw_markdown: str = Field(default="", description="HTML converted to clean markdown")
    clean_text: str = Field(default="", description="Plain text content for vector indexing")
    tables: list[ExtractedTable] = Field(default_factory=list)
    images: list[ExtractedImage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    publish_date: str | None = Field(default=None)
    crawled_at: datetime = Field(default_factory=_utc_now)


class FactClaim(BaseModel):
    """Extracted factual claim tied to source chunk for grounding."""

    id: str = Field(description="Unique claim identifier")
    claim_text: str = Field(description="The concrete factual assertion")
    source_url: str = Field(description="Source page where claim originated")
    source_chunk_id: str = Field(description="Specific chunk ID containing the grounding evidence")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    grounded: bool = Field(
        default=False, description="Verified by the Fact-Checker against source text"
    )


class GraphNode(BaseModel):
    """Entity node in the GraphRAG Knowledge Graph."""

    id: str = Field(description="Unique entity identifier (e.g., entity name sanitized)")
    label: str = Field(description="Entity name")
    entity_type: str = Field(
        default="Concept",
        description="Entity category: Technology, Organization, Person, Metric, etc.",
    )
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Relationship edge in the GraphRAG Knowledge Graph."""

    source_id: str = Field(description="Origin entity node ID")
    target_id: str = Field(description="Target entity node ID")
    relation_type: str = Field(
        description="Predicate relationship (e.g., DEVELOPS, ACCELERATES, CONFLICTS_WITH)"
    )
    weight: float = Field(default=1.0, description="Edge weight or frequency")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_doc_id: str | None = Field(default=None)


class CriticFeedback(BaseModel):
    """Adversarial evaluation from the Devil's Advocate / Critic agent."""

    missing_perspectives: list[str] = Field(default_factory=list)
    unaddressed_contradictions: list[str] = Field(default_factory=list)
    suggested_counter_queries: list[str] = Field(default_factory=list)
    information_sufficiency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    ready_for_synthesis: bool = Field(default=False)


class ResearchReport(BaseModel):
    """Publication-ready multi-format research dossier."""

    topic: str
    title: str
    executive_summary: str
    chapters: list[dict[str, str]] = Field(
        default_factory=list, description="List of {chapter_title, content_markdown}"
    )
    tables: list[ExtractedTable] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(
        default_factory=list, description="Footnote citation list [{id, url, snippet}]"
    )
    bibtex_entries: list[str] = Field(default_factory=list, description="BibTeX reference entries")
    generated_at: datetime = Field(default_factory=_utc_now)
    model_used: str = Field(default="")
    total_sources_consulted: int = Field(default=0)


class ResearchState(BaseModel):
    """Central state machine object persisted across all research transitions."""

    session_id: str = Field(description="Unique research session identifier")
    topic: str = Field(description="Target research query")
    user_constraints: str = Field(
        default="", description="Specific guidelines or focus areas from user"
    )
    target_depth: int = Field(default=2, ge=1, le=5)
    current_depth: int = Field(default=0)
    status: Literal[
        "INITIALIZED",
        "PLANNING",
        "SEARCHING",
        "CRAWLING",
        "INDEXING",
        "EVALUATING",
        "CRITIQUING",
        "PAUSED_HITL",
        "SYNTHESIZING",
        "GROUNDING",
        "EXPORTING",
        "COMPLETED",
        "FAILED",
    ] = Field(default="INITIALIZED")

    # Data collections
    search_queries: list[SearchQuery] = Field(default_factory=list)
    visited_urls: set[str] = Field(default_factory=set)
    collected_documents: list[ScrapedDocument] = Field(default_factory=list)
    extracted_claims: list[FactClaim] = Field(default_factory=list)
    graph_nodes: list[GraphNode] = Field(default_factory=list)
    graph_edges: list[GraphEdge] = Field(default_factory=list)
    critic_notes: list[CriticFeedback] = Field(default_factory=list)

    # Metrics & Budgeting
    information_saturation: float = Field(default=0.0)
    total_tokens_used: int = Field(default=0)
    estimated_cost_usd: float = Field(default=0.0)

    # Deliverables
    draft_report: str | None = Field(default=None)
    final_report: ResearchReport | None = Field(default=None)
    report_paths: dict[str, str] = Field(
        default_factory=dict, description="Generated file paths (.md, .tex, .html, .pdf)"
    )
    error_message: str | None = Field(default=None)

    def record_cost(self, prompt_tokens: int, completion_tokens: int, model_name: str) -> None:
        """Accumulate token counts and estimate USD cost for cloud providers."""
        tokens = prompt_tokens + completion_tokens
        self.total_tokens_used += tokens

        # Conservative pricing estimation per 1M tokens ($2.50 prompt, $10.00 completion typical for GPT-4o)
        if "gpt-4" in model_name or "claude-3-5" in model_name:
            cost = (prompt_tokens * 2.50 + completion_tokens * 10.0) / 1_000_000
        elif "gemini" in model_name or "flash" in model_name:
            cost = (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000
        elif "deepseek" in model_name:
            cost = (prompt_tokens * 0.27 + completion_tokens * 1.10) / 1_000_000
        else:
            # Local Ollama / LM Studio is free
            cost = 0.0

        self.estimated_cost_usd += cost
