# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for AkuvoxDevice connect/disconnect lifecycle and error cases."""

import pytest
from aioresponses import aioresponses

from pylocal_akuvox.auth import AuthConfig, AuthMethod
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxParseError,
)
from pylocal_akuvox.models import DeviceInfo

BASE_URL = "http://192.168.1.100"

# -- T018: Connect / disconnect lifecycle --


async def test_context_manager_creates_and_closes_session() -> None:
    """Verify async context manager opens and closes the HTTP session."""
    device = AkuvoxDevice("192.168.1.100")
    async with device:
        assert device._http._session is not None
        assert not device._http._session.closed
    assert device._http._session is None


async def test_get_info_returns_device_info() -> None:
    """Verify get_info calls GET /api/system/info and returns DeviceInfo."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={
                "retcode": 0,
                "action": "info",
                "message": "",
                "data": {
                    "Status": {
                        "Model": "E21V",
                        "MAC": "AA:BB:CC:DD:EE:FF",
                        "FirmwareVersion": "2.0.0.1",
                        "HardwareVersion": "1.0",
                        "Uptime": "3 days",
                        "WebLang": 0,
                    }
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            info = await device.get_info()

    assert isinstance(info, DeviceInfo)
    assert info.model == "E21V"
    assert info.mac_address == "AA:BB:CC:DD:EE:FF"
    assert info.firmware_version == "2.0.0.1"
    assert info.hardware_version == "1.0"
    assert info.uptime == "3 days"
    assert info.web_language == 0


async def test_get_info_minimal_response() -> None:
    """Verify get_info handles minimal response with required fields only."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={
                "retcode": 0,
                "action": "info",
                "message": "",
                "data": {
                    "Status": {
                        "Model": "R29G",
                        "MAC": "11:22:33:44:55:66",
                        "FirmwareVersion": "1.0.0.0",
                        "HardwareVersion": "2.0",
                    }
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            info = await device.get_info()

    assert info.model == "R29G"
    assert info.uptime is None
    assert info.web_language is None


async def test_device_with_custom_timeout() -> None:
    """Verify AkuvoxDevice passes timeout to HTTP client."""
    device = AkuvoxDevice("192.168.1.100", timeout=30)
    assert device._http._timeout.total == 30


async def test_device_with_auth() -> None:
    """Verify AkuvoxDevice passes auth config to HTTP client."""
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    device = AkuvoxDevice("192.168.1.100", auth=auth)
    assert device._http._auth is auth


async def test_nested_context_manager_raises() -> None:
    """Verify re-entering context manager raises AkuvoxConnectionError."""
    device = AkuvoxDevice("192.168.1.100")
    async with device:
        with pytest.raises(AkuvoxConnectionError, match="already open"):
            async with device:
                pass


# -- T019: Connection error cases --


async def test_unreachable_host_raises_connection_error() -> None:
    """Verify unreachable IP raises AkuvoxConnectionError within timeout."""
    import aiohttp

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=aiohttp.ClientError("Connection refused"),
        )
        async with AkuvoxDevice("192.168.1.100", timeout=2) as device:
            with pytest.raises(AkuvoxConnectionError, match="Connection"):
                await device.get_info()


async def test_timeout_raises_connection_error() -> None:
    """Verify connection timeout raises AkuvoxConnectionError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=TimeoutError("Timed out"),
        )
        async with AkuvoxDevice("192.168.1.100", timeout=1) as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.get_info()


async def test_http_401_raises_authentication_error() -> None:
    """Verify HTTP 401 raises AkuvoxAuthenticationError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            status=401,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxAuthenticationError):
                await device.get_info()


async def test_non_json_response_raises_parse_error() -> None:
    """Verify non-JSON response raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            body="<html>Not Found</html>",
            content_type="text/html",
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError):
                await device.get_info()


async def test_missing_envelope_raises_parse_error() -> None:
    """Verify response without envelope fields raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"unexpected": "data"},
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="envelope"):
                await device.get_info()


async def test_missing_required_field_raises_parse_error() -> None:
    """Verify missing Model field in Status raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={
                "retcode": 0,
                "action": "info",
                "message": "",
                "data": {
                    "Status": {
                        "MAC": "AA:BB:CC:DD:EE:FF",
                        "FirmwareVersion": "1.0.0.0",
                        "HardwareVersion": "1.0",
                    }
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="Missing required field"):
                await device.get_info()
