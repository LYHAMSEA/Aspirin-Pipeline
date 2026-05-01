# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install dependencies into a virtual env
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

WORKDIR /build

# System deps needed for compiled wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (layer-cache friendly)
COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install ".[dev,lint]"

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — lean image with only what's needed to run
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="ChemOps API"
LABEL org.opencontainers.image.description="Git-Driven CI/CD Pipeline for Autonomous Laboratory Orchestration"
LABEL org.opencontainers.image.source="https://github.com/your-org/chemops"
LABEL org.opencontainers.image.licenses="MIT"

# Security: run as non-root
RUN groupadd --gid 1001 chemops && \
    useradd --uid 1001 --gid chemops --shell /bin/bash --create-home chemops

WORKDIR /app

# Copy the venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source
COPY --chown=chemops:chemops chemops/ ./chemops/
COPY --chown=chemops:chemops pyproject.toml ./

# Install package in editable mode (no extra deps — already in venv)
RUN pip install --no-deps -e .

USER chemops

# Expose API port and Prometheus metrics port
EXPOSE 8000

# Healthcheck — liveness probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Default command — production uvicorn server
CMD ["uvicorn", "chemops.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
