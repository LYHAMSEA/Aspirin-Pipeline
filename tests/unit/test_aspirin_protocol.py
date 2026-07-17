"""Unit tests for the aspirin synthesis protocol steps."""

from __future__ import annotations

import unittest.mock

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
async def test_prepare_reagents_returns_expected_keys() -> None:
    result = await prepare_reagents()
    assert "salicylic_acid_g" in result
    assert "acetic_anhydride_ml" in result
    assert result["salicylic_acid_g"] > 0
    assert result["acetic_anhydride_ml"] > 0


@pytest.mark.asyncio
async def test_charge_reactor() -> None:
    result = await charge_reactor()
    assert result["status"] == "charged"
    assert "temperature" in result
    assert "ph" in result


@pytest.mark.asyncio
async def test_hold_at_temperature_returns_readings() -> None:
    result = await hold_at_temperature()
    assert "readings" in result
    assert len(result["readings"]) == 15  # REACTION_HOLD_MIN
    assert result["hold_duration_min"] == 15


@pytest.mark.asyncio
async def test_quench_reaction() -> None:
    result = await quench_reaction()
    assert result["precipitation_observed"] is True
    assert result["water_added_ml"] == 100.0


@pytest.mark.asyncio
async def test_vacuum_filter_mass_reasonable() -> None:
    result = await vacuum_filter()
    crude = result["crude_mass_g"]
    # Crude mass should be 88-98% of theoretical yield (plain hyphen)
    assert EXPECTED_YIELD_G * 0.85 <= crude <= EXPECTED_YIELD_G


@pytest.mark.asyncio
async def test_recrystallise_returns_purity() -> None:
    result = await recrystallise()
    assert 95.0 <= result["purity_pct"] <= 100.0
    assert result["pure_mass_g"] > 0


@pytest.mark.asyncio
async def test_dry_and_weigh_yield_pct() -> None:
    result = await dry_and_weigh()
    assert 0 < result["yield_pct"] <= 100.0
    assert result["final_mass_g"] > 0


@pytest.mark.asyncio
async def test_quality_control_passes_when_conditions_met() -> None:
    """QC passes when melting point is in range and FeCl3 test is negative."""
    with unittest.mock.patch("chemops.protocols.aspirin_synthesis.random") as mock_rng:
        mock_rng.gauss.return_value = 0.0  # MP = 135.0 + 0.0 = 135.0 (in range)
        mock_rng.random.return_value = 0.5  # 0.5 > 0.03 → FeCl3 negative
        result = await quality_control()
    assert result["qc_status"] == "PASSED"
    assert result["melting_point_c"] == 135.0
    assert result["fecl3_test"] == "negative"


@pytest.mark.asyncio
async def test_quality_control_fails_on_bad_melting_point() -> None:
    """QC raises ValueError when melting point is outside 134.5-136.5 range."""
    with unittest.mock.patch("chemops.protocols.aspirin_synthesis.random") as mock_rng:
        mock_rng.gauss.return_value = 5.0  # MP = 135.0 + 5.0 = 140.0 (out of range)
        mock_rng.random.return_value = 0.5  # FeCl3 negative — only MP fails
        with pytest.raises(ValueError, match="MP out of range"):
            await quality_control()


@pytest.mark.asyncio
async def test_quality_control_fails_on_fecl3_positive() -> None:
    """QC raises ValueError when FeCl3 test is positive (salicylic acid impurity)."""
    with unittest.mock.patch("chemops.protocols.aspirin_synthesis.random") as mock_rng:
        mock_rng.gauss.return_value = 0.0  # MP in range — only FeCl3 fails
        mock_rng.random.return_value = 0.0  # 0.0 < 0.03 → FeCl3 positive
        with pytest.raises(ValueError, match="FeCl3 test positive"):
            await quality_control()


def test_protocol_step_count() -> None:
    steps = get_aspirin_protocol()
    assert len(steps) == 9


def test_protocol_step_names() -> None:
    steps = get_aspirin_protocol()
    names = [name for name, _ in steps]
    assert names[0] == "prepare_reagents"
    assert names[-1] == "quality_control"
