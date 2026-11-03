"""Local checks for the HACS and Home Assistant packaging contract."""

from __future__ import annotations

import json
import pathlib
import re
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tellybox"
MANIFEST = COMPONENT / "manifest.json"
HACS = ROOT / "hacs.json"
README = ROOT / "README.md"
DASHBOARD = ROOT / "dashboard-example.yaml"
THEME = ROOT / "themes" / "tellybox.yaml"


def load(path: pathlib.Path):
	"""Load one JSON file."""
	return json.loads(path.read_text(encoding="utf-8"))


def png_size(path: pathlib.Path) -> tuple[int, int]:
	"""Return the width and height from a PNG IHDR chunk."""
	data = path.read_bytes()
	if data[:8] != b"\x89PNG\r\n\x1a\n":
		raise AssertionError(f"{path.name} is not a PNG")
	return struct.unpack(">II", data[16:24])


class LayoutTests(unittest.TestCase):
	def test_hacs_integration_layout(self) -> None:
		self.assertTrue((COMPONENT / "__init__.py").is_file())
		self.assertTrue((COMPONENT / "manifest.json").is_file())
		self.assertTrue((COMPONENT / "strings.json").is_file())
		self.assertTrue((COMPONENT / "translations" / "en.json").is_file())
		self.assertTrue((COMPONENT / "brand" / "icon.png").is_file())
		self.assertTrue((ROOT / "hacs.json").is_file())
		self.assertTrue((ROOT / "README.md").is_file())
		self.assertTrue(DASHBOARD.is_file())
		self.assertTrue(THEME.is_file())

	def test_only_one_integration_is_packaged(self) -> None:
		integrations = [path.name for path in (ROOT / "custom_components").iterdir() if path.is_dir()]
		self.assertEqual(integrations, ["tellybox"])

	def test_brand_assets_follow_home_assistant_sizes(self) -> None:
		brand = COMPONENT / "brand"
		self.assertEqual(png_size(brand / "icon.png"), (256, 256))
		self.assertEqual(png_size(brand / "icon@2x.png"), (512, 512))
		self.assertEqual(png_size(brand / "dark_logo.png"), (768, 256))
		self.assertEqual(png_size(brand / "dark_logo@2x.png"), (1536, 512))

	def test_no_application_or_server_source_is_copied(self) -> None:
		for forbidden in ("app", "server", "relay", "adbbridge", "gradle", "package.json"):
			self.assertFalse((ROOT / forbidden).exists(), forbidden)

	def test_generated_and_secret_files_are_ignored(self) -> None:
		names = {path.name for path in ROOT.rglob("*") if path.is_file()}
		self.assertNotIn(".env", names)
		ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
		self.assertIn("__pycache__/", ignore)
		self.assertIn("*.py[cod]", ignore)
		self.assertIn(".pytest_cache/", ignore)
		self.assertIn("DASHBOARD-RESULT.txt", ignore)


class ManifestTests(unittest.TestCase):
	def setUp(self) -> None:
		self.manifest = load(MANIFEST)

	def test_required_hacs_keys_and_new_repository_links(self) -> None:
		self.assertEqual(self.manifest["domain"], "tellybox")
		self.assertEqual(self.manifest["name"], "Tellybox")
		self.assertEqual(self.manifest["codeowners"], ["@jharrisuk"])
		self.assertEqual(
			self.manifest["documentation"],
			"https://github.com/jharrisuk/tellybox-home-assistant",
		)
		self.assertEqual(
			self.manifest["issue_tracker"],
			"https://github.com/jharrisuk/tellybox-home-assistant/issues",
		)
		self.assertTrue(self.manifest["config_flow"])
		self.assertEqual(self.manifest["version"], "0.1.1")
		self.assertEqual(self.manifest["integration_type"], "hub")
		self.assertEqual(self.manifest["iot_class"], "local_polling")
		self.assertEqual(self.manifest["requirements"], [])

	def test_manifest_has_no_core_only_homeassistant_key(self) -> None:
		self.assertNotIn("homeassistant", self.manifest)

	def test_hacs_manifest_declares_the_accurate_minimum(self) -> None:
		hacs = load(HACS)
		self.assertEqual(hacs["name"], "Tellybox")
		self.assertEqual(hacs["homeassistant"], "2026.10.0")
		self.assertTrue(hacs["render_readme"])
		self.assertEqual(set(hacs), {"name", "homeassistant", "render_readme"})


class TranslationTests(unittest.TestCase):
	def test_strings_and_english_translation_match(self) -> None:
		strings = load(COMPONENT / "strings.json")
		english = load(COMPONENT / "translations" / "en.json")
		self.assertEqual(strings, english)

	def test_config_flow_has_user_reauth_and_reconfigure_text(self) -> None:
		strings = load(COMPONENT / "strings.json")
		steps = strings["config"]["step"]
		self.assertEqual(set(steps), {"user", "reauth_confirm", "reconfigure"})
		for step in steps.values():
			self.assertIn("title", step)
			self.assertIn("description", step)
			self.assertEqual(set(step["data"]), {"url", "token"})
			self.assertEqual(set(step["data_description"]), {"url", "token"})

	def test_abort_and_error_reasons_are_translated(self) -> None:
		strings = load(COMPONENT / "strings.json")["config"]
		self.assertEqual(
			set(strings["error"]),
			{"invalid_url", "invalid_token", "invalid_auth", "cannot_connect", "invalid_response"},
		)
		self.assertIn("already_configured", strings["abort"])
		self.assertIn("wrong_installation", strings["abort"])

	def test_translations_describe_address_without_literal_urls(self) -> None:
		strings = load(COMPONENT / "strings.json")
		for step in strings["config"]["step"].values():
			url = step["data_description"]["url"]
			self.assertIn("local viewing address", url)
			self.assertNotIn("http://", url)
			self.assertIn("port 8082", url)


class DocumentationTests(unittest.TestCase):
	def setUp(self) -> None:
		self.readme = README.read_text(encoding="utf-8")

	def test_readme_documents_the_custom_repository_and_not_the_catalogue(self) -> None:
		self.assertIn("https://github.com/jharrisuk/tellybox-home-assistant", self.readme)
		self.assertIn("not in the default HACS catalogue", self.readme)
		self.assertIn("Add from link", self.readme)
		self.assertIn("Custom repositories", self.readme)

	def test_readme_documents_ports_and_the_conditional_hostname(self) -> None:
		self.assertIn("8990", self.readme)
		self.assertIn("8082", self.readme)
		self.assertIn("/api/integrations/home-assistant/stats", self.readme)
		self.assertIn("http://tellybox.local", self.readme)
		self.assertNotIn("http://tellybox.local:8082", self.readme)
		self.assertIn("do not add `:8082`", self.readme)
		self.assertIn("local reverse proxy", self.readme)
		self.assertIn("http://SERVER_IP:8082", self.readme)

	def test_readme_documents_the_dashboard_and_entity_replacement(self) -> None:
		self.assertIn("dashboard-example.yaml", self.readme)
		self.assertIn("themes/tellybox.yaml", self.readme)
		self.assertIn("device_id('binary_sensor.tellybox_online')", self.readme)
		self.assertIn("device_entities()", self.readme)
		self.assertNotIn("integration_entities('tellybox')", self.readme)
		self.assertIn("Settings > Devices & services > Tellybox > Entities", self.readme)
		self.assertIn("GB or TB", self.readme)
		self.assertIn("never turned into `0`", self.readme)

	def test_readme_documents_branding_and_the_dark_logo_limitation(self) -> None:
		self.assertIn("custom_components/tellybox/brand/", self.readme)
		self.assertIn("Home Assistant 2026.3", self.readme)
		self.assertIn("falls back to the square icon", self.readme)
		self.assertIn("Tellybox brand assets", self.readme)
		self.assertIn("/api/brands/integration/tellybox/dark_logo.png", self.readme)
		self.assertIn("#5402", self.readme)
		self.assertIn("#5171", self.readme)
		self.assertIn("catalogue thumbnail", self.readme)
		self.assertIn("cannot correct every HACS UI version", self.readme)

	def test_readme_documents_restart_and_release_updates(self) -> None:
		self.assertIn("restart Home Assistant", self.readme)
		self.assertIn("published GitHub release", self.readme)

	def test_readme_documents_the_actual_minimum_home_assistant_version(self) -> None:
		self.assertIn("2026.10.0", self.readme)
		self.assertIn("Home Assistant 2026.9 and earlier", self.readme)

	def test_readme_documents_the_licence_and_check_exception(self) -> None:
		self.assertIn("PolyForm Noncommercial License 1.0.0", self.readme)
		self.assertIn("`license`", self.readme)
		self.assertIn("not an OSI-approved open-source licence", self.readme)


class SourceTests(unittest.TestCase):
	def test_config_flow_uses_probatio_and_supports_reconfigure(self) -> None:
		source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
		self.assertIn("import probatio", source)
		self.assertIn("STEP_USER_SCHEMA = probatio.Schema", source)
		self.assertIn("async def async_step_reconfigure", source)
		self.assertIn("async_update_reload_and_abort", source)
		self.assertNotIn("voluptuous", source)

	def test_api_remains_a_single_read_only_request(self) -> None:
		source = (COMPONENT / "api.py").read_text(encoding="utf-8")
		self.assertIn("self._session.get(", source)
		self.assertIn("allow_redirects=False", source)
		self.assertIn("Authorization", source)
		self.assertIn("Bearer", source)
		for method in (".post(", ".put(", ".patch(", ".delete("):
			self.assertNotIn(method, source)

	def test_no_viewer_admin_or_application_route_is_used(self) -> None:
		for path in COMPONENT.glob("*.py"):
			source = path.read_text(encoding="utf-8")
			for forbidden in ("/api/activity", "/api/apps", "/api/auth", "/stream/", "/admin"):
				self.assertNotIn(forbidden, source, path.name)

	def test_no_credentials_or_private_endpoints_are_committed(self) -> None:
		source = "\n".join(path.read_text(encoding="utf-8") for path in COMPONENT.glob("*.py"))
		self.assertIsNone(re.search(r"[A-Fa-f0-9]{64}", source))
		self.assertNotIn("password=", source.lower())
		self.assertNotIn("secret=", source.lower())
		self.assertNotIn("192.168.", source)
		self.assertNotIn("10.0.0.", source)

	def test_python_sources_use_tabs_for_indentation(self) -> None:
		for path in COMPONENT.glob("*.py"):
			for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
				if line.startswith(" "):
					self.fail(f"{path.name}:{number} starts with spaces")

	def test_disk_sensor_keeps_native_bytes_and_suggests_gb(self) -> None:
		source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
		self.assertIn("_attr_native_unit_of_measurement = UnitOfInformation.BYTES", source)
		self.assertIn("_attr_suggested_unit_of_measurement = UnitOfInformation.GIGABYTES", source)

	def test_ci_skips_only_the_documented_hacs_license_check(self) -> None:
		workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
		self.assertIn("hacs/action@main", workflow)
		self.assertIn('ignore: "license"', workflow)
		self.assertNotIn('ignore: "brands license"', workflow)
		self.assertNotIn("ignore: \"*\"", workflow)


class LicenceTests(unittest.TestCase):
	def test_noncommercial_licence_and_notice_are_preserved(self) -> None:
		licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
		notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
		self.assertIn("PolyForm Noncommercial License 1.0.0", licence)
		self.assertIn("Required Notice: Copyright 2026 James Harris", notice)

	def test_scope_does_not_claim_osi_approval(self) -> None:
		scope = (ROOT / "LICENSE-SCOPE.md").read_text(encoding="utf-8")
		self.assertIn("not OSI-approved open-source software", scope)
		self.assertIn("brand images in `custom_components/tellybox/brand/`", scope)
		self.assertIn("not licensed as general-purpose artwork", scope)


if __name__ == "__main__":
	unittest.main()
