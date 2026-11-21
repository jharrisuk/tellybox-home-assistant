"""YAML and documentation checks for the portable Tellybox full panel card."""

from __future__ import annotations

import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CARD = ROOT / "dashboard-panel-card.yaml"
README = ROOT / "README.md"


class PanelCardYamlTests(unittest.TestCase):
	def setUp(self) -> None:
		self.raw = CARD.read_text(encoding="utf-8")
		self.config = yaml.safe_load(self.raw)
		self.panel = self.config["custom_fields"]["panel"]

	def test_card_is_one_button_card_with_shared_variables(self) -> None:
		self.assertEqual(self.config["type"], "custom:button-card")
		self.assertTrue(self.config["triggers_update"] == "all")
		self.assertEqual(self.config["variables"]["entity_prefix"], "tellybox_tellybox_local")
		self.assertEqual(self.config["variables"]["logo"], "/local/tellybox/dark_logo.png")
		self.assertNotIn("card_mod", self.raw)
		self.assertNotIn("card-mod:", self.raw)

	def test_panel_is_a_button_card_js_template(self) -> None:
		self.assertTrue(self.panel.startswith("[[[\n"))
		self.assertTrue(self.panel.rstrip().endswith("]]]"))
		self.assertIn("return `", self.panel)
		self.assertNotIn(".innerHTML", self.panel)
		self.assertNotIn("eval(", self.panel)

	def test_play_disk_and_memory_lookups_are_tolerant(self) -> None:
		for text in (
			"play_requests_24_hours",
			"const plays = count(id('sensor', 'play_requests_24_hours'), id('sensor', 'plays'))",
			"key.endsWith('_available_space')",
			"key.toLowerCase().includes('media')",
			"plays · 24h",
			"const memUsage = num(id('sensor', 'memory_usage'))",
			"Number.isFinite",
		):
			self.assertIn(text, self.panel)

	def test_offline_wins_over_maintenance(self) -> None:
		self.assertIn("const maint = online && maintState === 'on'", self.panel)
		self.assertIn("const status = offline ? 'OFFLINE' : maint ? 'MAINTENANCE'", self.panel)
		self.assertIn("!online ? 'Telemetry paused'", self.panel)


class PanelCardReadmeTests(unittest.TestCase):
	def setUp(self) -> None:
		self.readme = README.read_text(encoding="utf-8")

	def test_readme_uses_the_real_entity_suffixes(self) -> None:
		for suffix in (
			"service_uptime",
			"play_requests_24_hours",
			"failed_or_limited_sign_ins_24_hours",
			"maintenance_mode",
			"memory_total",
			"memory_available",
			"host_uptime",
			"viewers",
			"paused_streams",
		):
			self.assertIn(suffix, self.readme)

	def test_readme_documents_the_tolerant_panel_lookups(self) -> None:
		self.assertIn("falls back to the older", self.readme)
		self.assertIn("`_media_disk_available_space`", self.readme)
		self.assertIn("`_media_available_space`", self.readme)
		self.assertIn("preferring one whose ID contains `media`", self.readme)
		self.assertIn("Memory prefers `sensor.<prefix>_memory_usage`", self.readme)
		self.assertIn("plays · 24h", self.readme)

	def test_readme_version_matches_the_manifest(self) -> None:
		self.assertIn("`0.2.1`", self.readme)


if __name__ == "__main__":
	unittest.main()
