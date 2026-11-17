"""Pydantic validation models for tool execution arguments."""

import re

from pydantic import BaseModel, Field, field_validator


class WebSearchValidation(BaseModel):
    """Validation schema for web search inputs."""

    query: str = Field(min_length=2, max_length=300)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        # Strip potential shell injection characters
        cleaned = re.sub(r"[;<>&|`$]", " ", v).strip()
        if not cleaned:
            raise ValueError("Query contains only disallowed characters")
        return cleaned


class ScrapeUrlValidation(BaseModel):
    """Validation schema for target scrape URLs."""

    url: str = Field(pattern=r"^https?://[^\s]+$")


class DocumentUploadValidation(BaseModel):
    """Validation schema for local file path uploads."""

    file_path: str = Field(min_length=1, max_length=260)
