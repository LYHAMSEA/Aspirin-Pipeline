"""Unit tests for the sensor abstraction layer."""

from __future__ import annotations

import pytest

from chemops.sensors.instruments import (
    SensorRegistry,
    SimulatedBalance,
    SimulatedPHSensor,
    SimulatedPressureSensor,
    SimulatedTemperatureSensor,
    build_default_registry,
)


@pytest.mark.asyncio
async def test_temperature_sensor_reads_near_base():
    sensor = SimulatedTemperatureSensor("t1", base_temp=85.0, noise=0.01)
    reading = await sensor.read()
    assert 84.0 <= reading.value <= 86.0
    assert reading.unit == "celsius"
    assert reading.sensor_id == "t1"


@pytest.mark.asyncio
async def test_ph_sensor_clamped_to_valid_range():
    # Set base near boundary — noise should not exceed 0–14
    sensor = SimulatedPHSensor("ph1", base_ph=0.1, noise=0.01)
    for _ in range(20):
        r = await sensor.read()
        assert 0.0 <= r.value <= 14.0


@pytest.mark.asyncio
async def test_pressure_sensor_non_negative():
    sensor = SimulatedPressureSensor("p1", base_pressure=0.5, noise=0.1)
    for _ in range(10):
        r = await sensor.read()
        assert r.value >= 0.0


@pytest.mark.asyncio
async def test_balance_tare():
    balance = SimulatedBalance("bal1", expected_mass=14.0)
    reading_before = await balance.read()
    assert reading_before.value > 0
    balance.tare()
    reading_after = await balance.read()
    assert reading_after.value < 0.05  # near zero after tare


@pytest.mark.asyncio
async def test_sensor_registry_poll_all():
    reg = SensorRegistry()
    reg.register(SimulatedTemperatureSensor("t-a", base_temp=25.0))
    reg.register(SimulatedPHSensor("ph-a", base_ph=7.0))
    readings = await reg.poll_all()
    assert len(readings) == 2
    ids = {r.sensor_id for r in readings}
    assert ids == {"t-a", "ph-a"}


@pytest.mark.asyncio
async def test_default_registry_has_five_sensors():
    reg = build_default_registry()
    assert len(reg.all_ids()) == 5


@pytest.mark.asyncio
async def test_read_and_record_returns_reading():
    sensor = SimulatedTemperatureSensor("t2", base_temp=60.0)
    reading = await sensor.read_and_record()
    assert reading.sensor_id == "t2"
    assert reading.timestamp > 0
