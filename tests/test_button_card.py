"""YAML and documentation checks for the portable Tellybox button-card panel."""

from __future__ import annotations

import pathlib
import re
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CARD = ROOT / "dashboard-button-card.yaml"
README = ROOT / "README.md"
COMPACT = ROOT / "dashboard-compact-card.yaml"


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


class ButtonCardYamlTests(unittest.TestCase):
	def setUp(self) -> None:
		self.raw = CARD.read_text(encoding="utf-8")
		self.config = yaml.safe_load(self.raw)
		self.panel = self.config["custom_fields"]["panel"]

	def test_card_is_one_button_card_with_one_frontend_dependency(self) -> None:
		self.assertEqual(self.config["type"], "custom:button-card")
		self.assertEqual({value for value in values_for_key(self.config, "type")}, {"custom:button-card"})
		self.assertTrue(self.config["triggers_update"] == "all")
		self.assertNotIn("card_mod", self.raw)
		self.assertNotIn("card-mod:", self.raw)
		self.assertNotIn("\t", self.raw)

	def test_entity_prefix_and_logo_are_set_once(self) -> None:
		variables = self.config["variables"]
		self.assertEqual(variables["entity_prefix"], "tellybox_tellybox_local")
		self.assertEqual(variables["logo"], "/local/tellybox/dark_logo.png")
		self.assertIn("String(config.entity_prefix || '')", self.panel)
		self.assertIn("(configuredPrefix || defaultPrefix)", self.panel)
		self.assertIn("entity('binary_sensor', 'online')", self.panel)
		self.assertIn("entity('sensor', 'service_uptime')", self.panel)
		self.assertEqual(self.panel.count("const prefix ="), 1)

	def test_panel_is_a_button_card_js_template(self) -> None:
		self.assertTrue(self.panel.startswith("[[[\n"))
		self.assertTrue(self.panel.rstrip().endswith("]]]"))
		self.assertIn("return `", self.panel)

	def test_card_keeps_the_supplied_visual_sections(self) -> None:
		for text in (
			"radial-gradient(700px 220px",
			"TELLYBOX SERVER",
			"Watching",
			"Connected",
			"Local",
			"Remote",
			"Downloads",
			"meterLabel",
		):
			self.assertIn(text, self.raw)

	def test_numeric_parsing_is_strict_and_division_is_guarded(self) -> None:
		self.assertNotIn("parseFloat", self.panel)
		self.assertNotIn(".innerHTML", self.panel)
		self.assertNotIn("eval(", self.panel)
		self.assertIn("Number.isFinite", self.panel)
		self.assertIn("/^[+-]?(?:\\d+\\.?\\d*|\\.\\d+)$/", self.panel)
		self.assertIn("cap > 0", self.panel)
		self.assertIn("Number(pct.toFixed(1))", self.panel)

	def test_unknown_and_unlimited_states_are_explicit(self) -> None:
		self.assertIn("return '—'", self.panel)
		self.assertIn("cap === 0 ? '∞'", self.panel)
		self.assertIn("Unlimited upload cap", self.panel)
		self.assertIn("Telemetry unavailable", self.panel)

	def test_all_injected_values_are_html_escaped(self) -> None:
		self.assertIn("const escapeHtml", self.panel)
		for expression in (
			"escapeHtml(logo)",
			"escapeHtml(uptime)",
			"escapeHtml(uploadUnit)",
			"escapeHtml(capUnit)",
		):
			self.assertIn(expression, self.panel)

	def test_uptime_supports_common_units_and_never_echoes_raw_state(self) -> None:
		for unit in ("ms", "s", "min", "h", "d", "w"):
			self.assertIn(f"'{unit}'", self.panel)
		self.assertIn("secondsFrom", self.panel)
		self.assertIn("if (seconds === null) return '—'", self.panel)
		self.assertIn("86400", self.panel)

	def test_comments_document_logo_placement_and_frontend_install(self) -> None:
		self.assertIn("custom_components/tellybox/brand/dark_logo.png", self.raw)
		self.assertIn("<config>/www/tellybox/dark_logo.png", self.raw)
		self.assertIn("HACS > Frontend > button-card", self.raw)
		self.assertIn("Change `entity_prefix` once", self.raw)
		self.assertIn("http://tellybox.local", self.raw)


class ButtonCardReadmeTests(unittest.TestCase):
	def setUp(self) -> None:
		self.readme = README.read_text(encoding="utf-8")

	def test_readme_documents_frontend_dependency_and_reload(self) -> None:
		self.assertIn("dashboard-button-card.yaml", self.readme)
		self.assertIn("custom:button-card", self.readme)
		self.assertIn("HACS > Frontend", self.readme)
		self.assertIn("button-card", self.readme)
		self.assertIn("reload", self.readme.lower())
		self.assertIn("hard-refresh", self.readme)

	def test_readme_documents_portable_logo_placement(self) -> None:
		self.assertIn("custom_components/tellybox/brand/dark_logo.png", self.readme)
		self.assertIn("`www/tellybox/`", self.readme)
		self.assertIn("`/local/tellybox/dark_logo.png`", self.readme)
		self.assertIn("new brand asset", self.readme)

	def test_readme_documents_prefix_replacement_and_default_address(self) -> None:
		self.assertIn("entity_prefix", self.readme)
		self.assertIn("`tellybox_tellybox_local`", self.readme)
		self.assertIn("Settings > Devices & services > Tellybox > Entities", self.readme)
		self.assertIn("http://tellybox.local", self.readme)

	def test_readme_keeps_the_native_compact_alternative(self) -> None:
		self.assertIn("dashboard-compact-card.yaml", self.readme)
		self.assertIn("native Lovelace vertical-stack", self.readme)
		self.assertIn("does not use custom cards", self.readme)
		self.assertTrue(COMPACT.is_file())

	def test_readme_links_the_server_repository_both_ways(self) -> None:
		self.assertIn("https://github.com/jharrisuk/tellybox-homelab", self.readme)
		self.assertIn("links back", self.readme)

	def test_new_content_has_no_personal_addresses_or_secrets(self) -> None:
		self.assertNotIn("C:\\Users", self.readme)
		self.assertNotIn("/home/jh", self.readme)
		self.assertIsNone(re.search(r"192\.168\.\d+\.\d+", self.readme))
		self.assertIsNone(re.search(r"\b[A-Fa-f0-9]{64}\b", self.readme))
		self.assertNotIn("PRIVATE KEY", self.readme)


if __name__ == "__main__":
	unittest.main()
