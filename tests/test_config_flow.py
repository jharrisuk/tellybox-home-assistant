"""Config, reauthentication and reconfiguration flow tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tellybox.api import (
	TellyboxApiError,
	TellyboxAuthError,
	TellyboxConnectionError,
)
from custom_components.tellybox.config_flow import STEP_USER_SCHEMA
from custom_components.tellybox.const import CONF_TOKEN, CONF_URL, DOMAIN

URL = "http://192.168.1.50:8082"
TOKEN = "a" * 64
INSTALLATION_ID = "00000000-0000-0000-0000-000000000001"
OTHER_INSTALLATION_ID = "00000000-0000-0000-0000-000000000002"


def stats(installation_id: str = INSTALLATION_ID) -> dict[str, Any]:
	"""Return a minimal parsed statistics payload."""
	return {
		"installation_id": installation_id,
		"generated_at": 1760000000000,
		"server": {
			"version": "0.26.5",
			"host_status": "ok",
			"cpu_percent": 12.5,
			"memory_percent": 42.1,
			"uptime_seconds": 3600,
			"host_uptime_seconds": 86400,
			"memory_total_bytes": 17179869184,
			"memory_available_bytes": 9946625843,
			"disks": [],
		},
		"streams": {
			"active": 1,
			"connected": 2,
			"paused": 1,
			"local": 1,
			"remote": 1,
		},
		"downloads": {"active": 0},
		"upload": {
			"configured_mbps": 50,
			"unlimited": False,
			"measured_mbps": 3.25,
			"measurement_seconds": 10,
		},
	}


def entry_for(data: dict[str, Any] | None = None, unique_id: str = f"tellybox_{INSTALLATION_ID}") -> MockConfigEntry:
	"""Return a configured mock entry."""
	return MockConfigEntry(
		domain=DOMAIN,
		title="Tellybox (old address)",
		data=data or {CONF_URL: URL, CONF_TOKEN: TOKEN},
		unique_id=unique_id,
	)


async def start_user_flow(hass):
	"""Start the user flow and return the form result."""
	return await hass.config_entries.flow.async_init(
		DOMAIN,
		context={"source": config_entries.SOURCE_USER},
	)


async def test_schema_uses_the_current_home_assistant_schema_library() -> None:
	"""The integration must use probatio on Home Assistant 2026.10 and newer."""
	assert isinstance(STEP_USER_SCHEMA, probatio.Schema)


async def test_user_flow_creates_one_entry(hass) -> None:
	"""A valid address and token create a config entry with a stable unique ID."""
	result = await start_user_flow(hass)
	assert result["type"] is FlowResultType.FORM
	assert result["step_id"] == "user"

	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats()),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: URL + "/", CONF_TOKEN: " " + TOKEN + " "},
		)

	assert result["type"] is FlowResultType.CREATE_ENTRY
	assert result["title"] == "Tellybox (192.168.1.50:8082)"
	assert result["data"] == {CONF_URL: URL, CONF_TOKEN: TOKEN}
	assert result["result"].unique_id == f"tellybox_{INSTALLATION_ID}"


@pytest.mark.parametrize(
	("user_input", "error"),
	[
		({CONF_URL: "not-a-url", CONF_TOKEN: TOKEN}, "invalid_url"),
		({CONF_URL: URL, CONF_TOKEN: "short"}, "invalid_token"),
	],
)
async def test_user_flow_rejects_bad_input_without_a_request(hass, user_input, error) -> None:
	"""URL and token shape errors are reported on the form."""
	result = await start_user_flow(hass)
	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats()),
	) as request:
		result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)

	assert result["type"] is FlowResultType.FORM
	assert result["errors"] == {"base": error}
	request.assert_not_awaited()


@pytest.mark.parametrize(
	("exception", "error"),
	[
		(TellyboxAuthError("rejected"), "invalid_auth"),
		(TellyboxConnectionError("offline"), "cannot_connect"),
		(TellyboxApiError("bad payload"), "invalid_response"),
	],
)
async def test_user_flow_maps_request_failures(hass, exception, error) -> None:
	"""Authentication, connection and schema failures are distinct form errors."""
	result = await start_user_flow(hass)
	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(side_effect=exception),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: URL, CONF_TOKEN: TOKEN},
		)

	assert result["type"] is FlowResultType.FORM
	assert result["errors"] == {"base": error}


async def test_duplicate_installation_aborts(hass) -> None:
	"""The stable installation ID prevents a second entry for the same server."""
	existing = entry_for()
	existing.add_to_hass(hass)

	result = await start_user_flow(hass)
	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats()),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: URL, CONF_TOKEN: TOKEN},
		)

	assert result["type"] is FlowResultType.ABORT
	assert result["reason"] == "already_configured"


async def test_reauth_updates_token_and_title(hass) -> None:
	"""Reauthentication keeps the identity and updates the stored URL and title."""
	entry = entry_for({CONF_URL: URL, CONF_TOKEN: "b" * 64})
	entry.add_to_hass(hass)
	new_url = "http://192.168.1.60:8082"

	result = await hass.config_entries.flow.async_init(
		DOMAIN,
		context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
		data=entry.data,
	)
	assert result["type"] is FlowResultType.FORM
	assert result["step_id"] == "reauth_confirm"

	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats()),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: new_url, CONF_TOKEN: TOKEN},
		)

	assert result["type"] is FlowResultType.ABORT
	assert result["reason"] == "reauth_successful"
	assert entry.data == {CONF_URL: new_url, CONF_TOKEN: TOKEN}
	assert entry.title == "Tellybox (192.168.1.60:8082)"
	assert entry.unique_id == f"tellybox_{INSTALLATION_ID}"


async def test_reauth_rejects_a_different_installation(hass) -> None:
	"""A token for another server cannot overwrite the existing entry."""
	entry = entry_for()
	entry.add_to_hass(hass)

	result = await hass.config_entries.flow.async_init(
		DOMAIN,
		context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
		data=entry.data,
	)
	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats(OTHER_INSTALLATION_ID)),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: URL, CONF_TOKEN: TOKEN},
		)

	assert result["type"] is FlowResultType.ABORT
	assert result["reason"] == "wrong_installation"
	assert entry.data == {CONF_URL: URL, CONF_TOKEN: TOKEN}


async def test_reconfigure_updates_address_and_token(hass) -> None:
	"""Reconfiguration changes the endpoint without duplicating the installation."""
	entry = entry_for()
	entry.add_to_hass(hass)
	new_url = "http://tellybox.lan:8082"
	new_token = "c" * 64

	result = await hass.config_entries.flow.async_init(
		DOMAIN,
		context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
	)
	assert result["type"] is FlowResultType.FORM
	assert result["step_id"] == "reconfigure"

	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats()),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: new_url, CONF_TOKEN: new_token},
		)

	assert result["type"] is FlowResultType.ABORT
	assert result["reason"] == "reconfigure_successful"
	assert entry.data == {CONF_URL: new_url, CONF_TOKEN: new_token}
	assert entry.title == "Tellybox (tellybox.lan:8082)"
	assert entry.unique_id == f"tellybox_{INSTALLATION_ID}"


async def test_reconfigure_rejects_a_different_installation(hass) -> None:
	"""Reconfiguration cannot point an existing entry at another Tellybox server."""
	entry = entry_for()
	entry.add_to_hass(hass)

	result = await hass.config_entries.flow.async_init(
		DOMAIN,
		context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
	)
	with patch(
		"custom_components.tellybox.config_flow.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats(OTHER_INSTALLATION_ID)),
	):
		result = await hass.config_entries.flow.async_configure(
			result["flow_id"],
			{CONF_URL: URL, CONF_TOKEN: TOKEN},
		)

	assert result["type"] is FlowResultType.ABORT
	assert result["reason"] == "wrong_installation"
	assert entry.data == {CONF_URL: URL, CONF_TOKEN: TOKEN}


async def test_entry_setup_and_failed_poll_reports_offline(hass) -> None:
	"""The connectivity sensor stays available and turns off after a failed poll."""
	entry = entry_for()
	entry.add_to_hass(hass)

	with patch(
		"custom_components.tellybox.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=stats()),
	):
		assert await hass.config_entries.async_setup(entry.entry_id)
		await hass.async_block_till_done()

	assert entry.state is ConfigEntryState.LOADED
	registry = er.async_get(hass)
	entity_id = registry.async_get_entity_id(
		"binary_sensor",
		DOMAIN,
		f"{entry.entry_id}_online",
	)
	assert entity_id is not None
	assert hass.states.get(entity_id).state == "on"

	with patch(
		"custom_components.tellybox.TellyboxApi.async_get_stats",
		new=AsyncMock(side_effect=TellyboxConnectionError("offline")),
	):
		await entry.runtime_data.async_refresh()
		await hass.async_block_till_done()

	assert entry.runtime_data.last_update_success is False
	assert hass.states.get(entity_id).state == "off"

	assert await hass.config_entries.async_unload(entry.entry_id)
	await hass.async_block_till_done()
	assert entry.state is ConfigEntryState.NOT_LOADED


async def test_disk_sensor_displays_gb_while_native_bytes_and_identity_stay_stable(hass) -> None:
	"""Home Assistant converts the native byte value to GB for display."""
	payload = stats()
	payload["server"]["disks"] = [{
		"id": "media",
		"name": "Media",
		"available_bytes": 500_000_000_000,
		"total_bytes": 1_000_000_000_000,
		"used_bytes": 500_000_000_000,
	}]
	entry = entry_for()
	entry.add_to_hass(hass)

	with patch(
		"custom_components.tellybox.TellyboxApi.async_get_stats",
		new=AsyncMock(return_value=payload),
	):
		assert await hass.config_entries.async_setup(entry.entry_id)
		await hass.async_block_till_done()

	registry = er.async_get(hass)
	entity_id = registry.async_get_entity_id(
		"sensor",
		DOMAIN,
		f"{entry.entry_id}_disk_media_available_bytes",
	)
	assert entity_id is not None
	state = hass.states.get(entity_id)
	assert state is not None
	assert float(state.state) == 500.0
	assert state.attributes["unit_of_measurement"] == "GB"
	assert entry.runtime_data.data["server"]["disks"][0]["available_bytes"] == 500_000_000_000

	assert await hass.config_entries.async_unload(entry.entry_id)
	await hass.async_block_till_done()
	assert entry.state is ConfigEntryState.NOT_LOADED
