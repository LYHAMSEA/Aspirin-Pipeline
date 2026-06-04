"""
Aspirin Synthesis Protocol -- acetylsalicylic acid production pipeline.
 
Reaction:
    Salicylic acid + Acetic anhydride -> Acetylsalicylic acid + Acetic acid
    C7H6O3  +  (CH3CO)2O  ->  C9H8O4  +  CH3COOH
 
This module defines the ordered list of laboratory steps as async coroutines
suitable for execution by the ChemOps Orchestrator.
"""
# FIX: RUF002 -- replaced EN DASH characters (U+2013) with plain hyphens
# in the module docstring above.
 
from __future__ import annotations
 
import asyncio
import logging
import random
from typing import Any
 
logger = logging.getLogger(__name__)
 
# ---------------------------------------------------------------------------
# Reaction parameters
# ---------------------------------------------------------------------------
 
SALICYLIC_ACID_MASS_G = 14.0        # grams
ACETIC_ANHYDRIDE_ML = 20.0          # mL (slight excess)
PHOSPHORIC_ACID_DROPS = 5           # catalyst
TARGET_REACTION_TEMP_C = 85.0       # degrees C
REACTION_HOLD_MIN = 15              # minutes at temperature
RECRYSTALLISATION_SOLVENT = "ethanol"
EXPECTED_YIELD_G = 16.5             # theoretical max (g)
 
 
# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------
 
 
async def prepare_reagents() -> dict[str, Any]:
    """
    Weigh and transfer salicylic acid; measure acetic anhydride volume.
    """
    logger.info("Preparing reagents")
    await asyncio.sleep(2)
 
    actual_mass = SALICYLIC_ACID_MASS_G + random.gauss(0, 0.05)
    actual_volume = ACETIC_ANHYDRIDE_ML + random.gauss(0, 0.1)
 
    logger.info(
        "Reagents prepared: salicylic acid=%.3f g, acetic anhydride=%.2f mL",
        actual_mass,
        actual_volume,
    )
    return {
        "salicylic_acid_g": round(actual_mass, 3),
        "acetic_anhydride_ml": round(actual_volume, 2),
        "catalyst": f"{PHOSPHORIC_ACID_DROPS} drops H3PO4",
        "temperature": 22.0,
        "ph": 7.0,
    }
 
 
async def charge_reactor() -> dict[str, Any]:
    """
    Transfer reagents into the reactor vessel and add catalyst.
    """
    logger.info("Charging reactor with reagents and catalyst")
    await asyncio.sleep(3)
 
    return {
        "status": "charged",
        "vessel": "250 mL round-bottom flask",
        "temperature": 23.5,
        "ph": 3.2,
    }
 
 
async def heat_to_reaction_temperature() -> dict[str, Any]:
    """
    Ramp reactor temperature to TARGET_REACTION_TEMP_C at 5 degrees C/min.
    """
    logger.info("Heating to %.0f degrees C", TARGET_REACTION_TEMP_C)
    ramp_steps = 13
    current_temp = 23.0
 
    for _ in range(ramp_steps):  # FIX: B007 -- renamed unused `i` to `_`
        await asyncio.sleep(0.5)
        current_temp = min(current_temp + 5, TARGET_REACTION_TEMP_C)
        logger.debug("Reactor temp: %.1f degrees C", current_temp)
 
    actual_temp = TARGET_REACTION_TEMP_C + random.gauss(0, 0.5)
    logger.info("Target temperature reached: %.2f degrees C", actual_temp)
 
    return {
        "temperature": round(actual_temp, 2),
        "ph": 2.8,
        "ramp_rate_c_per_min": 5.0,
    }
 
 
async def hold_at_temperature() -> dict[str, Any]:
    """
    Maintain reaction temperature for REACTION_HOLD_MIN minutes.
    Monitors temperature and pH at 1-minute intervals.
    """
    logger.info(
        "Holding at %.0f degrees C for %d min",
        TARGET_REACTION_TEMP_C,
        REACTION_HOLD_MIN,
    )
    readings: list[dict[str, float]] = []
 
    for minute in range(REACTION_HOLD_MIN):
        await asyncio.sleep(0.3)
        temp = TARGET_REACTION_TEMP_C + random.gauss(0, 0.8)
        ph = 2.6 + random.gauss(0, 0.1)
        readings.append({"minute": minute + 1, "temp": round(temp, 2), "ph": round(ph, 2)})
        logger.debug("t+%d min -> T=%.2f degrees C, pH=%.2f", minute + 1, temp, ph)
 
    avg_temp = sum(r["temp"] for r in readings) / len(readings)
    avg_ph = sum(r["ph"] for r in readings) / len(readings)
 
    return {
        "hold_duration_min": REACTION_HOLD_MIN,
        "avg_temperature": round(avg_temp, 2),
        "avg_ph": round(avg_ph, 2),
        "temperature": round(avg_temp, 2),
        "ph": round(avg_ph, 2),
        "readings": readings,
    }
 
 
async def quench_reaction() -> dict[str, Any]:
    """
    Add ice-cold distilled water to precipitate crude aspirin.
    """
    logger.info("Quenching reaction with ice-cold water")
    await asyncio.sleep(2)
 
    temp_after_quench = 22.0 + random.gauss(0, 1.0)
    return {
        "water_added_ml": 100.0,
        "temperature": round(temp_after_quench, 2),
        "ph": 3.5,
        "precipitation_observed": True,
    }
 
 
async def vacuum_filter() -> dict[str, Any]:
    """
    Collect crude product by vacuum filtration through Buchner funnel.
    """
    logger.info("Vacuum filtering crude product")
    await asyncio.sleep(2)
 
    crude_mass = EXPECTED_YIELD_G * random.uniform(0.88, 0.98)
    return {
        "crude_mass_g": round(crude_mass, 3),
        "temperature": 22.0,
        "filter_paper": "Whatman No. 1",
        "vacuum_pressure_mbar": 50,
    }
 
 
async def recrystallise() -> dict[str, Any]:
    """
    Dissolve crude product in hot ethanol, cool slowly for pure crystals.
    """
    logger.info("Recrystallising from %s", RECRYSTALLISATION_SOLVENT)
    await asyncio.sleep(3)
 
    purity = random.uniform(97.5, 99.8)
    pure_mass = EXPECTED_YIELD_G * random.uniform(0.80, 0.92)
 
    return {
        "solvent": RECRYSTALLISATION_SOLVENT,
        "dissolution_temp_c": 78.0,
        "cooling_temp_c": 4.0,
        "pure_mass_g": round(pure_mass, 3),
        "purity_pct": round(purity, 2),
        "temperature": 4.0,
        "ph": 3.4,
    }
 
 
async def dry_and_weigh() -> dict[str, Any]:
    """
    Oven-dry product at 60 degrees C for 30 min; record final mass.
    """
    logger.info("Drying product at 60 degrees C")
    await asyncio.sleep(2)
 
    final_mass = EXPECTED_YIELD_G * random.uniform(0.78, 0.90)
    yield_pct = (final_mass / EXPECTED_YIELD_G) * 100
 
    logger.info("Final product: %.3f g (%.1f%% yield)", final_mass, yield_pct)
 
    return {
        "final_mass_g": round(final_mass, 3),
        "yield_pct": round(yield_pct, 1),
        "drying_temp_c": 60.0,
        "drying_duration_min": 30,
        "temperature": 60.0,
    }
 
 
async def quality_control() -> dict[str, Any]:
    """
    Melting point determination and IR spot check.
    Aspirin MP: 135-136 degrees C; ferric chloride test must be negative.
    """
    # FIX: RUF002 -- replaced EN DASH in "135-136" with plain hyphen above
    logger.info("Running QC checks")
    await asyncio.sleep(2)
 
    melting_point = 135.0 + random.gauss(0, 0.5)
    fecl3_positive = random.random() < 0.03
 
    qc_passed = (134.5 <= melting_point <= 136.5) and not fecl3_positive
 
    if not qc_passed:
        reason = []
        if not (134.5 <= melting_point <= 136.5):
            reason.append(f"MP out of range ({melting_point:.1f} degrees C)")
        if fecl3_positive:
            reason.append("FeCl3 test positive (salicylic acid impurity)")
        raise ValueError(f"QC FAILED: {'; '.join(reason)}")
 
    logger.info("QC PASSED -- MP=%.1f degrees C, FeCl3 test negative", melting_point)
    return {
        "melting_point_c": round(melting_point, 1),
        "fecl3_test": "negative",
        "qc_status": "PASSED",
        "temperature": 22.0,
    }
 
 
# ---------------------------------------------------------------------------
# Protocol builder
# ---------------------------------------------------------------------------
 
 
def get_aspirin_protocol() -> list[tuple[str, Any]]:
    """
    Return ordered (step_name, coroutine_factory) list for the orchestrator.
    """
    return [
        ("prepare_reagents", prepare_reagents),
        ("charge_reactor", charge_reactor),
        ("heat_to_reaction_temperature", heat_to_reaction_temperature),
        ("hold_at_temperature", hold_at_temperature),
        ("quench_reaction", quench_reaction),
        ("vacuum_filter", vacuum_filter),
        ("recrystallise", recrystallise),
        ("dry_and_weigh", dry_and_weigh),
        ("quality_control", quality_control),
    ]
 
