"""HTTP client failure tests using a fake aiohttp session, without Home Assistant."""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import types
import unittest

# api.py only needs these two aiohttp symbols at import time. A fake session
# below exercises every response branch without installing aiohttp or HA.
aiohttp = types.ModuleType("aiohttp")


class ClientError(Exception):
	"""Fake aiohttp.ClientError."""


class ClientTimeout:
	"""Fake aiohttp.ClientTimeout."""

	def __init__(self, total: float | None = None) -> None:
		self.total = total


aiohttp.ClientError = ClientError
aiohttp.ClientTimeout = ClientTimeout
sys.modules["aiohttp"] = aiohttp

COMPONENT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tellybox"
PACKAGE = types.ModuleType("tellybox_http")
PACKAGE.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE.__name__] = PACKAGE

from tellybox_http.api import (  # noqa: E402
	TellyboxApi,
	TellyboxApiError,
	TellyboxAuthError,
	TellyboxConnectionError,
)

TOKEN = "a" * 64
VALID = {
	"schema": "tellybox.home-assistant.stats",
	"schemaVersion": 1,
	"installationId": "00000000-0000-0000-0000-000000000000",
	"server": {"version": "0.26.5", "hostStatus": "ok", "disks": []},
	"streams": {"active": 0, "connected": 0, "paused": 0, "local": 0, "remote": 0},
	"downloads": {"active": 0},
	"upload": {"configuredMbps": 50, "unlimited": False, "measuredMbps": 0, "measurementSeconds": 10},
}


class Content:
	"""Chunked body reader that does not need aiohttp's StreamReader."""

	def __init__(self, body: bytes, error: Exception | None = None) -> None:
		self._body = body
		self._error = error
		self._position = 0

	async def read(self, size: int = -1) -> bytes:
		if self._error:
			raise self._error
		remaining = len(self._body) - self._position
		if remaining <= 0:
			return b""
		if size is None or size < 0:
			size = remaining
		chunk = self._body[self._position:self._position + size]
		self._position += len(chunk)
		return chunk


class Response:
	def __init__(
		self,
		status: int = 200,
		payload=None,
		headers=None,
		error: Exception | None = None,
		enter_error: Exception | None = None,
		body: bytes | None = None,
	) -> None:
		self.status = status
		self._payload = payload
		self.headers = headers if headers is not None else {"Content-Type": "application/json"}
		self._error = error
		self._enter_error = enter_error
		if body is None:
			body = b"" if payload is None else json.dumps(payload).encode("utf-8")
		self.content = Content(body, error)

	async def __aenter__(self):
		if self._enter_error:
			raise self._enter_error
		return self

	async def __aexit__(self, *args):
		return False


class Session:
	def __init__(self, response: Response) -> None:
		self.response = response
		self.calls: list[tuple[str, dict]] = []

	def get(self, url: str, **kwargs):
		self.calls.append((url, kwargs))
		return self.response


def api_for(response: Response) -> tuple[TellyboxApi, Session]:
	session = Session(response)
	return TellyboxApi(session, "http://192.168.1.50:8082/", TOKEN, timeout=7), session


class ApiTests(unittest.TestCase):
	def run_api(self, response: Response):
		api, session = api_for(response)
		return asyncio.run(api.async_get_stats()), session

	def test_successful_request_uses_bearer_header_no_redirect_and_timeout(self) -> None:
		data, session = self.run_api(Response(payload=VALID))
		self.assertEqual(data["installation_id"], VALID["installationId"])
		url, options = session.calls[0]
		self.assertEqual(url, "http://192.168.1.50:8082/api/integrations/home-assistant/stats")
		self.assertEqual(options["headers"]["Authorization"], "Bearer " + TOKEN)
		self.assertFalse(options["allow_redirects"])
		self.assertEqual(options["timeout"].total, 7)

	def test_auth_failures_are_distinct_and_do_not_echo_the_token(self) -> None:
		for status in (401, 403):
			with self.subTest(status=status):
				with self.assertRaises(TellyboxAuthError) as raised:
					self.run_api(Response(status=status))
				self.assertNotIn(TOKEN, str(raised.exception))

	def test_connection_and_response_failures_map_to_the_documented_errors(self) -> None:
		cases = [
			(Response(enter_error=TimeoutError()), TellyboxConnectionError),
			(Response(enter_error=ClientError()), TellyboxConnectionError),
			(Response(status=302), TellyboxApiError),
			(Response(status=500), TellyboxApiError),
			(Response(payload=VALID, headers={"Content-Type": "text/html"}), TellyboxApiError),
			(Response(error=ValueError("bad json")), TellyboxApiError),
			(Response(payload={**VALID, "schemaVersion": 2}), TellyboxApiError),
			(Response(payload=VALID, headers={"Content-Type": "application/json", "Content-Length": str(600 * 1024)}), TellyboxApiError),
		]
		for response, expected in cases:
			with self.subTest(expected=expected.__name__):
				with self.assertRaises(expected):
					self.run_api(response)

	def test_chunked_body_over_the_cap_is_rejected_without_content_length(self) -> None:
		body = b"{" + b" " * (530 * 1024) + b"}"
		responses = [
			Response(body=body, headers={"Content-Type": "application/json"}),
			Response(body=body, headers={"Content-Type": "application/json", "Content-Length": "10"}),
		]
		for response in responses:
			with self.subTest(headers=response.headers):
				with self.assertRaises(TellyboxApiError):
					self.run_api(response)


if __name__ == "__main__":
	unittest.main()
