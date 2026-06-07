"""
ChemOps Orchestrator — central engine for autonomous lab pipeline control.

Manages protocol execution, equipment coordination, and telemetry streaming.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from prometheus_client import Counter, Gauge, Histogram, Summary

# FIX: TC003 — Callable is only needed for type annotations, move into
# TYPE_CHECKING block so it is not imported at runtime.
if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

STEP_DURATION = Histogram(
    "chemops_step_duration_seconds",
    "Duration of each protocol step",
    ["protocol", "step"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800],
)

STEP_TOTAL = Counter(
    "chemops_steps_total",
    "Total protocol steps executed",
    ["protocol", "step", "status"],
)

ACTIVE_RUNS = Gauge(
    "chemops_active_runs",
    "Number of currently active protocol runs",
)

TEMPERATURE_GAUGE = Gauge(
    "chemops_reactor_temperature_celsius",
    "Current reactor temperature",
    ["reactor_id"],
)

PH_GAUGE = Gauge(
    "chemops_reactor_ph",
    "Current reactor pH",
    ["reactor_id"],
)

YIELD_SUMMARY = Summary(
    "chemops_product_yield_percent",
    "Product yield percentage per run",
    ["protocol"],
)

PROTOCOL_RUNS = Counter(
    "chemops_protocol_runs_total",
    "Total protocol runs",
    ["protocol", "outcome"],
)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class StepStatus(StrEnum):  # FIX: UP042 — StrEnum replaces (str, Enum)
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(StrEnum):  # FIX: UP042
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class StepResult:
    step_id: str
    name: str
    status: StepStatus
    duration_s: float
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ProtocolRun:
    run_id: str
    protocol_name: str
    status: RunStatus
    started_at: float
    completed_at: float | None = None
    steps: list[StepResult] = field(default_factory=list)
    final_yield: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float | None:
        if self.completed_at:
            return self.completed_at - self.started_at
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """
    Asynchronous protocol orchestrator.

    Executes ordered lists of callable steps, records telemetry, and
    streams metrics to Prometheus throughout the run.
    """

    def __init__(self, reactor_id: str = "reactor-01") -> None:
        self.reactor_id = reactor_id
        self._runs: dict[str, ProtocolRun] = {}
        self._hooks: list[Callable[[ProtocolRun], None]] = []
        logger.info("Orchestrator initialised for reactor %s", reactor_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_hook(self, hook: Callable[[ProtocolRun], None]) -> None:
        """Register a callback invoked after every run completes."""
        self._hooks.append(hook)

    async def execute_protocol(
        self,
        protocol_name: str,
        steps: list[tuple[str, Callable[..., Any]]],
        metadata: dict[str, Any] | None = None,
    ) -> ProtocolRun:
        """
        Execute a named protocol composed of (step_name, coroutine_factory) pairs.

        Parameters
        ----------
        protocol_name:
            Human-readable protocol identifier (e.g. "aspirin_synthesis_v2").
        steps:
            Ordered list of ``(name, async_callable)`` pairs.
        metadata:
            Arbitrary key/value data stored on the run record.

        Returns
        -------
        ProtocolRun
            Completed (or failed) run record.
        """
        run_id = str(uuid.uuid4())
        run = ProtocolRun(
            run_id=run_id,
            protocol_name=protocol_name,
            status=RunStatus.RUNNING,
            started_at=time.time(),
            metadata=metadata or {},
        )
        self._runs[run_id] = run
        ACTIVE_RUNS.inc()
        logger.info("Starting run %s for protocol '%s'", run_id, protocol_name)

        try:
            for step_name, step_fn in steps:
                result = await self._execute_step(protocol_name, step_name, step_fn)
                run.steps.append(result)

                if result.status == StepStatus.FAILED:
                    run.status = RunStatus.FAILED
                    PROTOCOL_RUNS.labels(protocol=protocol_name, outcome="failed").inc()
                    logger.error(
                        "Run %s failed at step '%s': %s",
                        run_id,
                        step_name,
                        result.error,
                    )
                    return run

            run.status = RunStatus.COMPLETE
            run.completed_at = time.time()
            PROTOCOL_RUNS.labels(protocol=protocol_name, outcome="success").inc()
            logger.info("Run %s complete in %.1fs", run_id, run.duration)
            return run

        except asyncio.CancelledError:
            run.status = RunStatus.ABORTED
            run.completed_at = time.time()
            PROTOCOL_RUNS.labels(protocol=protocol_name, outcome="aborted").inc()
            logger.warning("Run %s was cancelled", run_id)
            return run

        finally:
            ACTIVE_RUNS.dec()
            for hook in self._hooks:
                try:
                    hook(run)
                except Exception:
                    logger.exception("Hook raised an unexpected exception")

    def get_run(self, run_id: str) -> ProtocolRun | None:
        return self._runs.get(run_id)

    def all_runs(self) -> list[ProtocolRun]:
        return list(self._runs.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        protocol: str,
        step_name: str,
        step_fn: Callable[..., Any],
    ) -> StepResult:
        logger.debug("Executing step '%s'", step_name)
        start = time.perf_counter()

        try:
            data = await step_fn()
            duration = time.perf_counter() - start

            STEP_DURATION.labels(protocol=protocol, step=step_name).observe(duration)
            STEP_TOTAL.labels(protocol=protocol, step=step_name, status="success").inc()

            if isinstance(data, dict):
                if "temperature" in data:
                    TEMPERATURE_GAUGE.labels(reactor_id=self.reactor_id).set(data["temperature"])
                if "ph" in data:
                    PH_GAUGE.labels(reactor_id=self.reactor_id).set(data["ph"])
                if "yield_pct" in data:
                    YIELD_SUMMARY.labels(protocol=protocol).observe(data["yield_pct"])

            return StepResult(
                step_id=str(uuid.uuid4()),
                name=step_name,
                status=StepStatus.COMPLETE,
                duration_s=duration,
                data=data or {},
            )

        except Exception as exc:
            duration = time.perf_counter() - start
            STEP_DURATION.labels(protocol=protocol, step=step_name).observe(duration)
            STEP_TOTAL.labels(protocol=protocol, step=step_name, status="failure").inc()
            logger.exception("Step '%s' raised: %s", step_name, exc)
            return StepResult(
                step_id=str(uuid.uuid4()),
                name=step_name,
                status=StepStatus.FAILED,
                duration_s=duration,
                error=str(exc),
            )
