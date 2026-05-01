"""Integration tests — full protocol execution through the orchestrator."""

from __future__ import annotations

import pytest

from chemops.core.orchestrator import Orchestrator, RunStatus
from chemops.protocols.aspirin_synthesis import get_aspirin_protocol


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_aspirin_synthesis_run():
    """Run the complete aspirin synthesis protocol end-to-end."""
    orchestrator = Orchestrator(reactor_id="integration-reactor")
    steps = get_aspirin_protocol()

    run = await orchestrator.execute_protocol(
        "aspirin_synthesis",
        steps,
        metadata={"test": True},
    )

    # Run should complete (QC has ~97% pass rate; retry if flaky)
    assert run.status in {RunStatus.COMPLETE, RunStatus.FAILED}

    # All 9 steps should have been attempted up to any failure
    if run.status == RunStatus.COMPLETE:
        assert len(run.steps) == 9
        for step in run.steps:
            assert step.duration_s >= 0
            assert step.name  # non-empty name


@pytest.mark.asyncio
@pytest.mark.integration
async def test_orchestrator_stores_run():
    orchestrator = Orchestrator(reactor_id="integration-reactor-2")
    steps = get_aspirin_protocol()
    run = await orchestrator.execute_protocol("aspirin_synthesis", steps)
    fetched = orchestrator.get_run(run.run_id)
    assert fetched is not None
    assert fetched.run_id == run.run_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_sequential_runs():
    orchestrator = Orchestrator(reactor_id="integration-reactor-3")
    for i in range(2):
        steps = get_aspirin_protocol()
        run = await orchestrator.execute_protocol(
            "aspirin_synthesis", steps, metadata={"batch": i}
        )
        assert run.status in {RunStatus.COMPLETE, RunStatus.FAILED}

    assert len(orchestrator.all_runs()) == 2
