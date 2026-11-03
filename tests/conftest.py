"""Shared Home Assistant test fixtures."""

from __future__ import annotations

import socket
import sys

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

if sys.platform == "win32":
	# pytest-homeassistant-custom-component blocks socket.socket, but the
	# Windows Proactor event loop creates its self-pipe with socketpair().
	# Allow only that internal socketpair call; tests still cannot open sockets.
	_true_socket = socket.socket
	_true_socketpair = socket.socketpair

	def _windows_socketpair(*args, **kwargs):
		current = socket.socket
		socket.socket = _true_socket
		try:
			return _true_socketpair(*args, **kwargs)
		finally:
			socket.socket = current

	socket.socketpair = _windows_socketpair


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
	"""Load custom_components.tellybox during tests."""
	return enable_custom_integrations
