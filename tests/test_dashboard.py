"""YAML, template and native-card checks for the Tellybox dashboard."""

from __future__ import annotations

import pathlib
import unittest

import jinja2
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard-example.yaml"
THEME = ROOT / "themes" / "tellybox.yaml"
BRAND_ROUTE = "/api/brands/integration/tellybox/dark_logo.png"

EXPECTED_ENTITIES = {
	"binary_sensor.tellybox_online",
	"sensor.tellybox_active_streams",
	"sensor.tellybox_connected_streams",
	"sensor.tellybox_local_streams",
	"sensor.tellybox_remote_streams",
	"sensor.tellybox_active_downloads",
	"sensor.tellybox_measured_remote_upload",
	"sensor.tellybox_configured_upload_limit",
	"sensor.tellybox_uptime",
	"sensor.tellybox_cpu_usage",
	"sensor.tellybox_memory_usage",
}

SUMMARY_VALUES = {
	"binary_sensor.tellybox_online": "on",
	"sensor.tellybox_active_streams": "3",
	"sensor.tellybox_connected_streams": "4",
	"sensor.tellybox_local_streams": "2",
	"sensor.tellybox_remote_streams": "2",
	"sensor.tellybox_active_downloads": "1",
	"sensor.tellybox_measured_remote_upload": "3.25",
	"sensor.tellybox_configured_upload_limit": "50",
	"sensor.tellybox_cpu_usage": "12.5",
	"sensor.tellybox_memory_usage": "42.1",
	"sensor.tellybox_uptime": "93784",
}


def load_dashboard() -> dict:
	"""Load the dashboard YAML."""
	return yaml.safe_load(DASHBOARD.read_text(encoding="utf-8"))


def values_for_key(value, key: str):
	"""Yield every value stored under a key at any depth."""
	if isinstance(value, dict):
		for item_key, item_value in value.items():
			if item_key == key:
				yield item_value
			yield from values_for_key(item_value, key)
	elif isinstance(value, list):
		for item in value:
			yield from values_for_key(item, key)


def markdown_contents(config: dict) -> list[str]:
	"""Return every Markdown card body in dashboard order."""
	return [value for value in values_for_key(config, "content") if isinstance(value, str)]


class FakeHomeAssistant:
	"""Small template context that behaves like the Home Assistant helpers."""

	def __init__(
		self,
		entities,
		states,
		attributes,
		device_map: dict[str, str] | None = None,
		device_entities_map: dict[str, list[str]] | None = None,
	) -> None:
		self.entities = list(entities)
		self.state_values = states
		self.attributes = attributes
		if device_map is None:
			device_map = {entity: "device-single" for entity in self.entities}
		self.device_map = device_map
		if device_entities_map is None:
			grouped: dict[str, list[str]] = {}
			for entity in self.entities:
				device = device_map.get(entity)
				if device:
					grouped.setdefault(device, []).append(entity)
			device_entities_map = grouped
		self.device_entities_map = device_entities_map

	def integration_entities(self, domain: str) -> list[str]:
		return list(self.entities) if domain == "tellybox" else []

	def device_id(self, entity: str) -> str | None:
		return self.device_map.get(entity)

	def device_entities(self, device: str) -> list[str]:
		return list(self.device_entities_map.get(device, []))

	def states(self, entity: str) -> str:
		return self.state_values.get(entity, "unknown")

	def state_attr(self, entity: str, attribute: str):
		return self.attributes.get(entity, {}).get(attribute)

	def is_state(self, entity: str, state: str) -> bool:
		return self.state_values.get(entity) == state

	def is_number(self, value) -> bool:
		if isinstance(value, bool):
			return False
		try:
			float(value)
		except (TypeError, ValueError):
			return False
		return True


def render(content: str, fake: FakeHomeAssistant) -> str:
	"""Render one Home Assistant-style Markdown template with the fake context."""
	return jinja2.Environment().from_string(content).render(
		integration_entities=fake.integration_entities,
		device_id=fake.device_id,
		device_entities=fake.device_entities,
		states=fake.states,
		state_attr=fake.state_attr,
		is_state=fake.is_state,
		is_number=fake.is_number,
	)


class DashboardTests(unittest.TestCase):
	def setUp(self) -> None:
		self.config = load_dashboard()
		self.contents = markdown_contents(self.config)

	def test_dashboard_is_a_native_sections_view(self) -> None:
		self.assertEqual(set(self.config), {"title", "views"})
		self.assertEqual(len(self.config["views"]), 1)
		view = self.config["views"][0]
		self.assertEqual(view["type"], "sections")
		self.assertEqual(view["theme"], "Tellybox")
		self.assertEqual(view["max_columns"], 3)
		self.assertGreaterEqual(len(view["sections"]), 5)
		for section in view["sections"]:
			self.assertEqual(section["type"], "grid")
			self.assertEqual(section["cards"][0]["type"], "heading")

	def test_dashboard_uses_only_native_cards(self) -> None:
		raw = DASHBOARD.read_text(encoding="utf-8")
		self.assertNotIn("custom:", raw)
		self.assertNotIn("card-mod", raw)
		types = {value for value in values_for_key(self.config, "type") if isinstance(value, str)}
		self.assertLessEqual(
			types,
			{
				"sections",
				"grid",
				"heading",
				"markdown",
				"tile",
				"gauge",
				"history-graph",
				"picture",
				"entity",
			},
		)
		self.assertIn("tile", types)
		self.assertIn("gauge", types)
		self.assertIn("history-graph", types)
		self.assertIn("heading", types)
		self.assertIn("picture", types)

	def test_every_current_aggregate_entity_has_an_explicit_card(self) -> None:
		entities = {value for value in values_for_key(self.config, "entity") if isinstance(value, str)}
		self.assertEqual(entities, EXPECTED_ENTITIES)

	def test_summary_and_storage_use_device_scoped_placeholder_lookup(self) -> None:
		scoped = [
			content
			for content in self.contents
			if "device_id('binary_sensor.tellybox_online')" in content
		]
		self.assertEqual(len(scoped), 2)
		for content in scoped:
			self.assertIn("device_entities(", content)
			self.assertNotIn("integration_entities", content)

		summary = next(content for content in self.contents if "active streams" in content)
		self.assertNotIn("friendly_name", summary)
		self.assertIn("'sensor.tellybox_active_streams'", summary)

	def test_full_width_cards_use_supported_grid_options(self) -> None:
		raw = DASHBOARD.read_text(encoding="utf-8")
		self.assertNotIn("column_span", raw)
		options = list(values_for_key(self.config, "grid_options"))
		self.assertGreaterEqual(len(options), 3)
		for option in options:
			self.assertEqual(option, {"columns": "full"})

	def test_header_uses_the_verified_brand_wordmark_route(self) -> None:
		view = self.config["views"][0]
		card = view["header"]["card"]
		self.assertEqual(card["type"], "picture")
		self.assertEqual(card["image"], BRAND_ROUTE)
		self.assertEqual(card["alt_text"], "Tellybox")
		raw = DASHBOARD.read_text(encoding="utf-8")
		self.assertNotIn("aggregated", raw)
		self.assertNotIn("Streams, transfers and server health", raw)

	def test_markdown_templates_parse(self) -> None:
		for content in self.contents:
			jinja2.Environment().parse(content)

	def test_rendered_summary_keeps_a_real_zero_and_hides_unknown(self) -> None:
		entities = list(EXPECTED_ENTITIES) + ["sensor.tellybox_media_available_space"]
		states = dict(SUMMARY_VALUES)
		states.update(
			{
				"sensor.tellybox_active_streams": "0",
				"sensor.tellybox_remote_streams": "unknown",
				"sensor.tellybox_media_available_space": "500.0",
			}
		)
		attributes = {entity: {} for entity in entities}
		attributes["binary_sensor.tellybox_online"]["device_class"] = "connectivity"
		fake = FakeHomeAssistant(entities, states, attributes)
		summary = next(content for content in self.contents if "active streams" in content)
		rendered = render(summary, fake)
		self.assertIn("**0** active streams", rendered)
		self.assertIn("uptime 1d 2h", rendered)
		self.assertIn("— remote", rendered)
		self.assertNotIn("0 remote", rendered)

	def test_rendered_summary_respects_the_uptime_state_unit(self) -> None:
		summary = next(content for content in self.contents if "active streams" in content)
		entities = list(EXPECTED_ENTITIES)
		for unit, state in (("s", "93784"), ("h", "26.05"), ("d", "1.085"), ("min", "1562.4")):
			states = dict(SUMMARY_VALUES)
			states["sensor.tellybox_uptime"] = state
			attributes = {entity: {} for entity in entities}
			attributes["binary_sensor.tellybox_online"]["device_class"] = "connectivity"
			attributes["sensor.tellybox_uptime"]["unit_of_measurement"] = unit
			rendered = render(summary, FakeHomeAssistant(entities, states, attributes))
			self.assertIn("uptime 1d 2h", rendered, unit)

		attributes = {entity: {} for entity in entities}
		attributes["binary_sensor.tellybox_online"]["device_class"] = "connectivity"
		attributes["sensor.tellybox_uptime"]["unit_of_measurement"] = "fortnight"
		rendered = render(summary, FakeHomeAssistant(entities, dict(SUMMARY_VALUES), attributes))
		self.assertIn("uptime —", rendered)

	def test_rendered_summary_ignores_an_id_from_another_device(self) -> None:
		entities = [entity for entity in EXPECTED_ENTITIES if entity != "sensor.tellybox_active_streams"]
		entities.append("sensor.tellybox_active_streams")
		device_map = {entity: "device-selected" for entity in EXPECTED_ENTITIES}
		device_map["sensor.tellybox_active_streams"] = "device-other"
		states = dict(SUMMARY_VALUES)
		states["sensor.tellybox_active_streams"] = "99"
		attributes = {entity: {} for entity in entities}
		attributes["binary_sensor.tellybox_online"]["device_class"] = "connectivity"
		summary = next(content for content in self.contents if "active streams" in content)
		rendered = render(
			summary,
			FakeHomeAssistant(
				entities,
				states,
				attributes,
				device_map=device_map,
				device_entities_map={
					"device-selected": [
						entity for entity in EXPECTED_ENTITIES if entity != "sensor.tellybox_active_streams"
					],
					"device-other": ["sensor.tellybox_active_streams"],
				},
			),
		)
		self.assertIn("**—** active streams", rendered)
		self.assertNotIn("**99** active streams", rendered)

	def test_rendered_storage_displays_gb_and_tb(self) -> None:
		entities = [
			"binary_sensor.tellybox_online",
			"sensor.media_available_space",
			"sensor.archive_available_space",
			"sensor.backup_available_space",
			"sensor.stale_available_space",
		]
		states = {
			"binary_sensor.tellybox_online": "on",
			"sensor.media_available_space": "500.0",
			"sensor.archive_available_space": "1500",
			"sensor.backup_available_space": "2500000000000",
			"sensor.stale_available_space": "unknown",
		}
		attributes = {
			"sensor.media_available_space": {
				"friendly_name": "Tellybox Media available space",
				"device_class": "data_size",
				"unit_of_measurement": "GB",
			},
			"sensor.archive_available_space": {
				"friendly_name": "Tellybox Archive available space",
				"device_class": "data_size",
				"unit_of_measurement": "GB",
			},
			"sensor.backup_available_space": {
				"friendly_name": "Tellybox Backup available space",
				"device_class": "data_size",
				"unit_of_measurement": "B",
			},
			"sensor.stale_available_space": {
				"friendly_name": "Tellybox Stale available space",
				"device_class": "data_size",
				"unit_of_measurement": "GB",
			},
		}
		storage = next(content for content in self.contents if "Disk | Available" in content)
		rendered = render(storage, FakeHomeAssistant(entities, states, attributes))
		self.assertIn("| Tellybox Media | 500.0 GB |", rendered)
		self.assertIn("| Tellybox Archive | 1.5 TB |", rendered)
		self.assertIn("| Tellybox Backup | 2.5 TB |", rendered)
		self.assertIn("| Tellybox Stale | — |", rendered)
		self.assertNotIn("2500000000000", rendered)
		self.assertNotIn("500.0 KB", rendered)

	def test_rendered_storage_only_lists_the_selected_device(self) -> None:
		selected = [
			"binary_sensor.tellybox_online",
			"sensor.tellybox_active_streams",
			"sensor.tellybox_media_available_space",
		]
		other = [
			"binary_sensor.tellybox_2_online",
			"sensor.tellybox_2_active_streams",
			"sensor.tellybox_2_media_available_space",
		]
		entities = selected + other
		states = {
			"binary_sensor.tellybox_online": "on",
			"binary_sensor.tellybox_2_online": "on",
			"sensor.tellybox_active_streams": "2",
			"sensor.tellybox_2_active_streams": "99",
			"sensor.tellybox_media_available_space": "500",
			"sensor.tellybox_2_media_available_space": "900",
		}
		attributes = {
			"sensor.tellybox_media_available_space": {
				"friendly_name": "Tellybox Media available space",
				"device_class": "data_size",
				"unit_of_measurement": "GB",
			},
			"sensor.tellybox_2_media_available_space": {
				"friendly_name": "Tellybox 2 Media available space",
				"device_class": "data_size",
				"unit_of_measurement": "GB",
			},
		}
		device_map = {entity: "device-selected" for entity in selected}
		device_map.update({entity: "device-other" for entity in other})
		fake = FakeHomeAssistant(
			entities,
			states,
			attributes,
			device_map=device_map,
			device_entities_map={
				"device-selected": selected,
				"device-other": other,
			},
		)
		summary = next(content for content in self.contents if "active streams" in content)
		rendered_summary = render(summary, fake)
		self.assertIn("**2** active streams", rendered_summary)
		self.assertNotIn("**99** active streams", rendered_summary)
		storage = next(content for content in self.contents if "Disk | Available" in content)
		rendered_storage = render(storage, fake)
		self.assertIn("| Tellybox Media | 500.0 GB |", rendered_storage)
		self.assertNotIn("Tellybox 2 Media", rendered_storage)

	def test_rendered_storage_explains_missing_disks(self) -> None:
		storage = next(content for content in self.contents if "Disk | Available" in content)
		rendered = render(
			storage,
			FakeHomeAssistant(
				["binary_sensor.tellybox_online"],
				{"binary_sensor.tellybox_online": "on"},
				{},
			),
		)
		self.assertIn("No disk readings are available", rendered)


class ThemeTests(unittest.TestCase):
	def test_theme_common_variables_apply_in_both_frontend_modes(self) -> None:
		raw = THEME.read_text(encoding="utf-8")
		self.assertNotIn("\t", raw)
		theme = yaml.safe_load(raw)["Tellybox"]
		self.assertEqual(theme["primary-color"], "#C7ED89")
		self.assertEqual(theme["accent-color"], "#C7ED89")
		self.assertEqual(theme["primary-background-color"], "#0B0E0B")
		self.assertIn("lovelace-background", theme)
		self.assertNotIn("modes", theme)

	def test_dashboard_has_no_tabs(self) -> None:
		self.assertNotIn("\t", DASHBOARD.read_text(encoding="utf-8"))


if __name__ == "__main__":
	unittest.main()
