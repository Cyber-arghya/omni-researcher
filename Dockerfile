# ==============================================================================
# OpenDeepResearcher - Production Multi-Stage Dockerfile
# Stage 1: Builder (install build tools, compile wheels, install dependencies)
# Stage 2: Runtime (lean Debian slim image, non-root 'researcher' user, zero secrets)
# ==============================================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build essentials if needed for compiling C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for rapid, deterministic package resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Leverage optimal layer caching: copy dependency manifests first
COPY pyproject.toml README.md ./

# Install production dependencies into a standalone virtual environment
RUN uv venv /opt/venv && \
    uv pip install --no-cache --python /opt/venv/bin/python .

# --- Stage 2: Minimal Runtime ---
FROM python:3.12-slim AS runtime

LABEL maintainer="OpenDeepResearcher Contributors"
LABEL description="Production runtime container for OpenDeepResearcher"

WORKDIR /app

# Install minimal runtime system libraries (libxml2 for trafilatura, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment containing only runtime dependencies from builder
COPY --from=builder /opt/venv /opt/venv

# Enforce non-root execution: create dedicated unprivileged user
RUN groupadd -r researcher && useradd -r -g researcher -d /app -s /sbin/nologin researcher

# Copy source code and application assets
COPY src/ /app/src/
COPY pyproject.toml README.md /app/

# Set up storage and reports directories with proper non-root permissions
RUN mkdir -p /app/storage /app/reports && \
    chown -R researcher:researcher /app

# Switch to unprivileged non-root user
USER researcher

# Set environment PATH to use virtual environment binaries
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port for FastAPI server
EXPOSE 8000

# Default command launches FastAPI server
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
