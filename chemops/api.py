"""
ChemOps API server.

Exposes:
  GET  /healthz               — liveness probe
  GET  /readyz                — readiness probe
  POST /runs                  — trigger a new protocol run
  GET  /runs                  — list all runs
  GET  /runs/{run_id}         — fetch a specific run
  GET  /metrics               — Prometheus metrics (scraped by prometheus)
  GET  /sensors               — latest sensor readings
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from chemops.core.orchestrator import Orchestrator, ProtocolRun, RunStatus
from chemops.protocols.aspirin_synthesis import get_aspirin_protocol
from chemops.sensors.instruments import SensorRegistry, build_default_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state (shared across requests)
# ---------------------------------------------------------------------------

orchestrator: Orchestrator
sensor_registry: SensorRegistry

# Store background tasks so they are not garbage-collected mid-run
# FIX: RUF006 — keep a reference to every created task
_background_tasks: set[asyncio.Task[ProtocolRun]] = set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # FIX: ANN201
    global orchestrator, sensor_registry
    orchestrator = Orchestrator(reactor_id="reactor-01")
    sensor_registry = build_default_registry()
    logger.info("ChemOps API ready")
    yield
    logger.info("ChemOps API shutting down")


app = FastAPI(
    title="ChemOps",
    description="Git-Driven CI/CD Pipeline for Autonomous Laboratory Orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

SUPPORTED_PROTOCOLS = {"aspirin_synthesis"}


class RunRequest(BaseModel):
    protocol: str = "aspirin_synthesis"
    metadata: dict[str, Any] = {}


class RunResponse(BaseModel):
    run_id: str
    protocol: str
    status: str
    started_at: float
    completed_at: float | None = None
    final_yield: float | None = None
    steps: list[dict[str, Any]] = []

    @classmethod
    def from_run(cls, run: ProtocolRun) -> "RunResponse":
        return cls(
            run_id=run.run_id,
            protocol=run.protocol_name,
            status=run.status.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            final_yield=run.final_yield,
            steps=[
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration_s": round(s.duration_s, 3),
                    "data": s.data,
                    "error": s.error,
                }
                for s in run.steps
            ],
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict[str, str]:  # FIX: ANN201
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz() -> dict[str, str]:  # FIX: ANN201
    return {"status": "ready", "reactor": orchestrator.reactor_id}


@app.post("/runs", response_model=RunResponse, tags=["runs"])
async def create_run(req: RunRequest) -> RunResponse:  # FIX: ANN201
    """Start a new protocol run (non-blocking — returns immediately)."""
    if req.protocol not in SUPPORTED_PROTOCOLS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown protocol '{req.protocol}'. "
                   f"Supported: {sorted(SUPPORTED_PROTOCOLS)}",
        )

    if req.protocol == "aspirin_synthesis":
        steps = get_aspirin_protocol()
    else:
        raise HTTPException(status_code=422, detail="Protocol not implemented")

    # FIX: F841 + RUF006 — store the task reference in the module-level set
    # so it is not garbage-collected while still running.
    task: asyncio.Task[ProtocolRun] = asyncio.create_task(
        orchestrator.execute_protocol(req.protocol, steps, req.metadata)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Wait briefly so we can return an initial run object with the run_id
    await asyncio.sleep(0.1)

    runs = orchestrator.all_runs()
    if runs:
        latest = max(runs, key=lambda r: r.started_at)
        return RunResponse.from_run(latest)

    raise HTTPException(status_code=500, detail="Run creation failed")


@app.get("/runs", response_model=list[RunResponse], tags=["runs"])
async def list_runs() -> list[RunResponse]:  # FIX: ANN201
    return [RunResponse.from_run(r) for r in orchestrator.all_runs()]


@app.get("/runs/{run_id}", response_model=RunResponse, tags=["runs"])
async def get_run(run_id: str) -> RunResponse:  # FIX: ANN201
    run = orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RunResponse.from_run(run)


@app.get("/sensors", tags=["sensors"])
async def get_sensor_readings() -> dict[str, Any]:  # FIX: ANN201
    readings = await sensor_registry.poll_all()
    return {r.sensor_id: r.as_dict() for r in readings}


@app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
async def metrics() -> PlainTextResponse:  # FIX: ANN201
    """Prometheus scrape endpoint."""
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
