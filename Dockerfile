# =============================================================================
# Stage 1: Builder — install dependencies into a virtual env
# =============================================================================
FROM python:3.12-slim AS builder

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
# Copy ONLY pyproject.toml first — this layer is only invalidated
# when dependencies change, not when source code changes
COPY pyproject.toml ./

RUN pip install --upgrade pip setuptools wheel && \
    pip install ".[dev,lint]"

# =============================================================================
# Stage 2: Runtime — lean image with only what is needed to run
# =============================================================================
FROM python:3.12-slim AS runtime

# Build args injected by CI — stored as image labels for traceability
ARG BUILD_DATE
ARG GIT_SHA
ARG VERSION=latest

LABEL org.opencontainers.image.title="ChemOps API"
LABEL org.opencontainers.image.description="Git-Driven CI/CD Pipeline for Autonomous Laboratory Orchestration"
LABEL org.opencontainers.image.source="https://github.com/LYHAMSEA/Aspirin-Pipeline"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_SHA}"
LABEL org.opencontainers.image.version="${VERSION}"

# Security: run as non-root user
RUN groupadd --gid 1001 chemops && \
    useradd --uid 1001 --gid chemops --shell /bin/bash --create-home chemops

WORKDIR /app

# Copy the venv from builder stage — no pip, no build tools in runtime
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install curl for the healthcheck (not in slim by default)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy source — chowned to non-root user
COPY --chown=chemops:chemops chemops/ ./chemops/
COPY --chown=chemops:chemops pyproject.toml ./

# Install the package itself (no deps — already in venv from builder)
RUN pip install --no-deps -e .

# Drop to non-root before anything runs
USER chemops

# Expose API port
EXPOSE 8000

# Healthcheck — Docker and compose use this to determine container health
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Production uvicorn server
# workers=2 is safe for a 1-2 vCPU server; scale to 2*CPU+1 for larger hosts
CMD ["uvicorn", "chemops.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
