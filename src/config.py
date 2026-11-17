"""Application configuration and environment settings using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for OpenDeepResearcher."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM Provider Selection ---
    llm_provider: Literal[
        "ollama", "openai", "gemini", "anthropic", "groq", "deepseek", "lmstudio", "custom"
    ] = Field(default="ollama", description="Primary LLM provider backend")
    llm_fast_model: str = Field(
        default="llama3.2:latest",
        description="Tier 1 model for query decomposition, filtering, and classification",
    )
    llm_deep_model: str = Field(
        default="deepseek-r1:latest",
        description="Tier 2 reasoning model for synthesis, critique, and contradiction resolution",
    )
    llm_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for local Ollama, LM Studio, or OpenAI-compatible endpoint",
    )

    # API Keys
    openai_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    groq_api_key: str | None = Field(default=None)
    deepseek_api_key: str | None = Field(default=None)

    # --- Vision & Multi-Modal ---
    vision_enabled: bool = Field(default=True, description="Enable chart and diagram extraction")
    vision_model: str = Field(
        default="llama3.2-vision:11b",
        description="Model used for chart-to-table analysis (or cloud gpt-4o / gemini-2.0-flash)",
    )

    # --- Web Search Providers ---
    search_provider: Literal["ddg", "searxng", "tavily"] = Field(
        default="ddg", description="Primary web search provider"
    )
    tavily_api_key: str | None = Field(default=None)
    searxng_base_url: str = Field(default="http://localhost:8080")

    # --- Academic APIs ---
    semantic_scholar_api_key: str | None = Field(default=None)
    ncbi_pubmed_email: str | None = Field(default=None)
    ncbi_pubmed_api_key: str | None = Field(default=None)

    # --- Cost & Token Safety Caps ---
    max_cost_limit_usd: float = Field(
        default=2.00, ge=0.1, description="Hard cap in USD for cloud API expenses per session"
    )
    max_total_tokens: int = Field(
        default=150_000, ge=1_000, description="Hard limit on cumulative session tokens"
    )

    # --- Research Parameters ---
    default_research_depth: int = Field(default=2, ge=1, le=5)
    max_search_queries_per_step: int = Field(default=5, ge=1, le=10)
    max_search_results_per_query: int = Field(default=6, ge=1, le=20)
    information_saturation_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    similarity_drift_threshold: float = Field(
        default=0.45, ge=0.2, le=0.9, description="Cosine similarity anchor to prevent rabbit holes"
    )

    # --- Storage & Paths ---
    storage_dir: Path = Field(default=Path("./storage"))
    reports_dir: Path = Field(default=Path("./reports"))
    sqlite_db_path: Path = Field(default=Path("./storage/cache.db"))
    knowledge_graph_path: Path = Field(default=Path("./storage/knowledge_graph.json"))
    chroma_persist_dir: Path = Field(default=Path("./storage/vector_db"))

    # --- Scraper & Browser ---
    headless_browser_enabled: bool = Field(default=True)
    scraper_timeout_seconds: int = Field(default=15, ge=5, le=60)

    def ensure_directories(self) -> None:
        """Create necessary project directories if they do not exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_local_mode(self) -> bool:
        """Returns True if configured to use local Ollama or LM Studio models."""
        return self.llm_provider in ("ollama", "lmstudio")


# Singleton instance
settings = Settings()
settings.ensure_directories()
