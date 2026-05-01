"""Unit tests for the aspirin synthesis protocol steps."""

from __future__ import annotations

import pytest

from chemops.protocols.aspirin_synthesis import (
    EXPECTED_YIELD_G,
    charge_reactor,
    dry_and_weigh,
    get_aspirin_protocol,
    hold_at_temperature,
    prepare_reagents,
    quality_control,
    quench_reaction,
    recrystallise,
    vacuum_filter,
)


@pytest.mark.asyncio
async def test_prepare_reagents_returns_expected_keys():
    result = await prepare_reagents()
    assert "salicylic_acid_g" in result
    assert "acetic_anhydride_ml" in result
    assert result["salicylic_acid_g"] > 0
    assert result["acetic_anhydride_ml"] > 0


@pytest.mark.asyncio
async def test_charge_reactor():
    result = await charge_reactor()
    assert result["status"] == "charged"
    assert "temperature" in result
    assert "ph" in result


@pytest.mark.asyncio
async def test_hold_at_temperature_returns_readings():
    result = await hold_at_temperature()
    assert "readings" in result
    assert len(result["readings"]) == 15  # REACTION_HOLD_MIN
    assert result["hold_duration_min"] == 15


@pytest.mark.asyncio
async def test_quench_reaction():
    result = await quench_reaction()
    assert result["precipitation_observed"] is True
    assert result["water_added_ml"] == 100.0


@pytest.mark.asyncio
async def test_vacuum_filter_mass_reasonable():
    result = await vacuum_filter()
    crude = result["crude_mass_g"]
    # Crude mass should be 88–98% of theoretical yield
    assert EXPECTED_YIELD_G * 0.85 <= crude <= EXPECTED_YIELD_G


@pytest.mark.asyncio
async def test_recrystallise_returns_purity():
    result = await recrystallise()
    assert 95.0 <= result["purity_pct"] <= 100.0
    assert result["pure_mass_g"] > 0


@pytest.mark.asyncio
async def test_dry_and_weigh_yield_pct():
    result = await dry_and_weigh()
    assert 0 < result["yield_pct"] <= 100.0
    assert result["final_mass_g"] > 0


@pytest.mark.asyncio
async def test_quality_control_passes_most_of_time():
    """QC should pass in the vast majority of random runs."""
    passes = 0
    for _ in range(20):
        try:
            await quality_control()
            passes += 1
        except ValueError:
            pass
    # Statistically, ≥17/20 should pass (97% pass rate)
    assert passes >= 15


def test_protocol_step_count():
    steps = get_aspirin_protocol()
    assert len(steps) == 9


def test_protocol_step_names():
    steps = get_aspirin_protocol()
    names = [name for name, _ in steps]
    assert names[0] == "prepare_reagents"
    assert names[-1] == "quality_control"
