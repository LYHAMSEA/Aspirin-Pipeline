"""
Sensor abstraction layer.

Provides unified interfaces to lab instruments (temperature probes,
pH meters, balances, pressure transducers). In production, swap the
SimulatedSensor backend for a hardware driver (GPIB, Modbus, OPC-UA).
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus sensor metrics
# ---------------------------------------------------------------------------

SENSOR_READING = Gauge(
    "chemops_sensor_reading",
    "Latest sensor reading",
    ["sensor_id", "unit"],
)

SENSOR_LAST_SEEN = Gauge(
    "chemops_sensor_last_seen_timestamp",
    "Unix timestamp of last successful sensor read",
    ["sensor_id"],
)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class SensorReading:
    sensor_id: str
    value: float
    unit: str
    timestamp: float

    def as_dict(self) -> dict:
        return {
            "sensor_id": self.sensor_id,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class Sensor(ABC):
    def __init__(self, sensor_id: str, unit: str) -> None:
        self.sensor_id = sensor_id
        self.unit = unit

    @abstractmethod
    async def read(self) -> SensorReading:
        """Return a current sensor reading."""

    async def read_and_record(self) -> SensorReading:
        reading = await self.read()
        SENSOR_READING.labels(
            sensor_id=self.sensor_id, unit=self.unit
        ).set(reading.value)
        SENSOR_LAST_SEEN.labels(sensor_id=self.sensor_id).set(reading.timestamp)
        logger.debug(
            "Sensor %s → %.4f %s", self.sensor_id, reading.value, self.unit
        )
        return reading


# ---------------------------------------------------------------------------
# Simulated sensors (for CI / testing)
# ---------------------------------------------------------------------------


class SimulatedTemperatureSensor(Sensor):
    """Simulates a thermocouple or RTD probe."""

    def __init__(self, sensor_id: str, base_temp: float = 25.0, noise: float = 0.3) -> None:
        super().__init__(sensor_id, "celsius")
        self._base = base_temp
        self._noise = noise

    async def read(self) -> SensorReading:
        await asyncio.sleep(0.05)
        value = self._base + random.gauss(0, self._noise)
        return SensorReading(
            sensor_id=self.sensor_id,
            value=round(value, 3),
            unit=self.unit,
            timestamp=time.time(),
        )

    def set_base(self, temp: float) -> None:
        """Update the simulated setpoint (e.g. when heater is adjusted)."""
        self._base = temp


class SimulatedPHSensor(Sensor):
    """Simulates a combination pH electrode."""

    def __init__(self, sensor_id: str, base_ph: float = 7.0, noise: float = 0.05) -> None:
        super().__init__(sensor_id, "pH")
        self._base = base_ph
        self._noise = noise

    async def read(self) -> SensorReading:
        await asyncio.sleep(0.05)
        value = max(0.0, min(14.0, self._base + random.gauss(0, self._noise)))
        return SensorReading(
            sensor_id=self.sensor_id,
            value=round(value, 3),
            unit=self.unit,
            timestamp=time.time(),
        )

    def set_base(self, ph: float) -> None:
        self._base = ph


class SimulatedPressureSensor(Sensor):
    """Simulates a vacuum pressure transducer (mbar)."""

    def __init__(self, sensor_id: str, base_pressure: float = 1013.0, noise: float = 2.0) -> None:
        super().__init__(sensor_id, "mbar")
        self._base = base_pressure
        self._noise = noise

    async def read(self) -> SensorReading:
        await asyncio.sleep(0.05)
        value = max(0.0, self._base + random.gauss(0, self._noise))
        return SensorReading(
            sensor_id=self.sensor_id,
            value=round(value, 2),
            unit=self.unit,
            timestamp=time.time(),
        )


class SimulatedBalance(Sensor):
    """Simulates an analytical balance (grams)."""

    def __init__(self, sensor_id: str, expected_mass: float = 0.0, noise: float = 0.001) -> None:
        super().__init__(sensor_id, "grams")
        self._expected = expected_mass
        self._noise = noise

    async def read(self) -> SensorReading:
        await asyncio.sleep(0.1)  # balance settling time
        value = max(0.0, self._expected + random.gauss(0, self._noise))
        return SensorReading(
            sensor_id=self.sensor_id,
            value=round(value, 4),
            unit=self.unit,
            timestamp=time.time(),
        )

    def tare(self) -> None:
        self._expected = 0.0


# ---------------------------------------------------------------------------
# Sensor registry
# ---------------------------------------------------------------------------


class SensorRegistry:
    """Central store for all connected sensors."""

    def __init__(self) -> None:
        self._sensors: dict[str, Sensor] = {}

    def register(self, sensor: Sensor) -> None:
        self._sensors[sensor.sensor_id] = sensor
        logger.info("Registered sensor '%s' (%s)", sensor.sensor_id, sensor.unit)

    def get(self, sensor_id: str) -> Sensor | None:
        return self._sensors.get(sensor_id)

    def all_ids(self) -> list[str]:
        return list(self._sensors.keys())

    async def poll_all(self) -> list[SensorReading]:
        """Read all sensors concurrently."""
        tasks = [s.read_and_record() for s in self._sensors.values()]
        return list(await asyncio.gather(*tasks))


def build_default_registry() -> SensorRegistry:
    """Convenience factory — builds a registry with typical aspirin-lab sensors."""
    reg = SensorRegistry()
    reg.register(SimulatedTemperatureSensor("temp-reactor-01", base_temp=25.0))
    reg.register(SimulatedTemperatureSensor("temp-bath-01", base_temp=25.0))
    reg.register(SimulatedPHSensor("ph-reactor-01", base_ph=7.0))
    reg.register(SimulatedPressureSensor("pressure-vacuum-01", base_pressure=1013.0))
    reg.register(SimulatedBalance("balance-main-01", expected_mass=0.0))
    return reg
