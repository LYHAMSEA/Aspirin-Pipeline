"""Unit tests for the Orchestrator engine."""

from __future__ import annotations

import asyncio

import pytest

from chemops.core.orchestrator import Orchestrator, RunStatus, StepStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def ok_step() -> dict:
    return {"temperature": 25.0, "ph": 7.0}


async def failing_step() -> dict:
    raise ValueError("Simulated instrument failure")


async def slow_step() -> dict:
    await asyncio.sleep(0.05)
    return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_single_step():
    orch = Orchestrator(reactor_id="test-reactor")
    run = await orch.execute_protocol("test_proto", [("ok_step", ok_step)])
    assert run.status == RunStatus.COMPLETE
    assert len(run.steps) == 1
    assert run.steps[0].status == StepStatus.COMPLETE


@pytest.mark.asyncio
async def test_run_stops_on_failure():
    orch = Orchestrator(reactor_id="test-reactor")
    steps = [
        ("first", ok_step),
        ("failing", failing_step),
        ("should_not_run", ok_step),
    ]
    run = await orch.execute_protocol("test_proto", steps)
    assert run.status == RunStatus.FAILED
    # Only two steps recorded — third never executed
    assert len(run.steps) == 2
    assert run.steps[1].status == StepStatus.FAILED
    assert "Simulated instrument failure" in run.steps[1].error


@pytest.mark.asyncio
async def test_multi_step_all_pass():
    orch = Orchestrator(reactor_id="test-reactor")
    steps = [("s1", ok_step), ("s2", ok_step), ("s3", slow_step)]
    run = await orch.execute_protocol("multi", steps)
    assert run.status == RunStatus.COMPLETE
    assert len(run.steps) == 3
    assert all(s.status == StepStatus.COMPLETE for s in run.steps)


@pytest.mark.asyncio
async def test_run_stored_in_orchestrator():
    orch = Orchestrator(reactor_id="test-reactor")
    run = await orch.execute_protocol("stored", [("ok", ok_step)])
    fetched = orch.get_run(run.run_id)
    assert fetched is not None
    assert fetched.run_id == run.run_id


@pytest.mark.asyncio
async def test_hook_called_on_completion():
    orch = Orchestrator(reactor_id="test-reactor")
    received = []
    orch.register_hook(lambda r: received.append(r.run_id))
    run = await orch.execute_protocol("hooked", [("ok", ok_step)])
    assert run.run_id in received


@pytest.mark.asyncio
async def test_hook_called_on_failure():
    orch = Orchestrator(reactor_id="test-reactor")
    received = []
    orch.register_hook(lambda r: received.append(r.status))
    await orch.execute_protocol("hooked_fail", [("fail", failing_step)])
    assert RunStatus.FAILED in received


@pytest.mark.asyncio
async def test_empty_protocol():
    orch = Orchestrator(reactor_id="test-reactor")
    run = await orch.execute_protocol("empty", [])
    assert run.status == RunStatus.COMPLETE
    assert run.steps == []


@pytest.mark.asyncio
async def test_run_duration_recorded():
    orch = Orchestrator(reactor_id="test-reactor")
    run = await orch.execute_protocol("timed", [("slow", slow_step)])
    assert run.duration is not None
    assert run.duration >= 0.05
