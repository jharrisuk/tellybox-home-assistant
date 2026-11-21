"""Behaviour checks for the ported statistics entities. No running Home Assistant needed."""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from homeassistant.components.sensor import SensorDeviceClass  # noqa: E402
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime  # noqa: E402

from custom_components.tellybox.binary_sensor import TellyboxMaintenanceSensor  # noqa: E402
from custom_components.tellybox.sensor import SENSORS  # noqa: E402

PAYLOAD = {
	"streams": {"paused": 2, "viewers": 5},
	"activity": {"plays": 7, "failed": 1},
	"server": {"host_uptime_seconds": 9, "memory_total_bytes": 10, "memory_available_bytes": 4},
}

NEW_SENSORS = {
	"paused_streams": 2,
	"viewers": 5,
	"plays": 7,
	"failed_plays": 1,
	"host_uptime": 9,
	"memory_total": 10,
	"memory_available": 4,
}


def description(key: str):
	"""Return the sensor description for one translation key."""
	return next(sensor for sensor in SENSORS if sensor.key == key)


class PortedSensorTests(unittest.TestCase):
	def test_new_sensors_read_their_allowlisted_fields(self) -> None:
		for key, expected in NEW_SENSORS.items():
			with self.subTest(key=key):
				self.assertEqual(description(key).value_fn(PAYLOAD), expected)

	def test_new_sensors_are_none_when_the_server_omits_the_field(self) -> None:
		for key in NEW_SENSORS:
			with self.subTest(key=key):
				self.assertIsNone(description(key).value_fn({}))

	def test_new_sensor_metadata_matches_the_reference_contract(self) -> None:
		for key in ("plays", "failed_plays", "host_uptime", "memory_total", "memory_available"):
			with self.subTest(key=key):
				self.assertEqual(description(key).entity_category, EntityCategory.DIAGNOSTIC)
		self.assertEqual(description("host_uptime").device_class, SensorDeviceClass.DURATION)
		self.assertEqual(description("host_uptime").native_unit_of_measurement, UnitOfTime.SECONDS)
		for key in ("memory_total", "memory_available"):
			with self.subTest(key=key):
				self.assertEqual(description(key).device_class, SensorDeviceClass.DATA_SIZE)
				self.assertEqual(description(key).native_unit_of_measurement, UnitOfInformation.BYTES)
		for key in ("paused_streams", "viewers"):
			with self.subTest(key=key):
				self.assertIsNone(description(key).entity_category)


class MaintenanceBinarySensorTests(unittest.TestCase):
	def sensor(self, data):
		entry = SimpleNamespace(entry_id="entry", unique_id="unique", title="Tellybox", data={"url": "http://example.test"})
		coordinator = SimpleNamespace(data=data, last_update_success=True)
		return TellyboxMaintenanceSensor(coordinator, entry)

	def test_reads_the_maintenance_flag(self) -> None:
		self.assertTrue(self.sensor({"maintenance": {"enabled": True}}).is_on)
		self.assertFalse(self.sensor({"maintenance": {"enabled": False}}).is_on)

	def test_is_unavailable_when_the_server_omits_the_flag(self) -> None:
		for data in ({}, {"maintenance": None}, {"maintenance": "enabled"}):
			with self.subTest(data=data):
				sensor = self.sensor(data)
				self.assertFalse(sensor.available)
				self.assertFalse(sensor.is_on)

	def test_stays_available_when_the_mapping_is_present(self) -> None:
		sensor = self.sensor({"maintenance": {"enabled": True}})
		self.assertTrue(sensor.available)


if __name__ == "__main__":
	unittest.main()
