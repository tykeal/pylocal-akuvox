# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for AkuvoxDevice connect/disconnect lifecycle and error cases."""

from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.auth import AuthConfig, AuthMethod
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxParseError,
)
from pylocal_akuvox.models import DeviceInfo, DeviceStatus

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


async def test_device_passes_request_delay_to_http_client() -> None:
    """Verify AkuvoxDevice passes request_delay to AkuvoxHttpClient."""
    device = AkuvoxDevice("192.168.1.100", request_delay=0.5)
    assert device._http._request_delay == 0.5


async def test_device_default_request_delay() -> None:
    """Verify AkuvoxDevice uses default 0.25s delay."""
    device = AkuvoxDevice("192.168.1.100")
    assert device._http._request_delay == 0.25


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


# -- T022: get_status tests --


async def test_get_status_returns_device_status() -> None:
    """Verify get_status calls GET /api/system/status and returns DeviceStatus."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "action": "status",
                "message": "",
                "data": {"SystemTime": 1700000000, "UpTime": 86400},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            status = await device.get_status()

    assert isinstance(status, DeviceStatus)
    assert status.unix_time == 1700000000
    assert status.uptime == 86400


async def test_get_status_missing_field_raises_parse_error() -> None:
    """Verify missing SystemTime raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "action": "status",
                "message": "",
                "data": {"UpTime": 100},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="Missing required field"):
                await device.get_status()


async def test_get_status_invalid_type_raises_parse_error() -> None:
    """Verify non-integer SystemTime raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "action": "status",
                "message": "",
                "data": {"SystemTime": "bad", "UpTime": 100},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="Invalid type"):
                await device.get_status()


async def test_get_status_string_ints_coerced() -> None:
    """Verify string-encoded integers are coerced to int."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "action": "status",
                "message": "",
                "data": {"SystemTime": "1700000000", "UpTime": "3600"},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            status = await device.get_status()

    assert status.unix_time == 1700000000
    assert status.uptime == 3600


# -- T048: Auth mode integration tests --

_PATCH_CONNECTOR = "pylocal_akuvox._http.aiohttp.TCPConnector"
_PATCH_SESSION = "pylocal_akuvox._http.aiohttp.ClientSession"


async def _async_noop() -> None:
    """No-op async function for mock session close."""


def _assert_session_kwargs(
    mock_cls: MagicMock,
    *,
    expect_basic: bool = False,
    expect_digest: bool = False,
) -> None:
    """Check ClientSession was created with expected auth configuration."""
    _, kwargs = mock_cls.call_args
    if expect_basic:
        assert isinstance(kwargs["auth"], aiohttp.BasicAuth)
    else:
        assert kwargs["auth"] is None
    if expect_digest:
        assert len(kwargs["middlewares"]) == 1
    else:
        assert kwargs["middlewares"] == ()


async def test_auth_default_creates_session_without_auth() -> None:
    """Verify default auth=None creates session without credentials."""
    with patch(_PATCH_CONNECTOR), patch(_PATCH_SESSION) as mock_cls:
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100"):
            _assert_session_kwargs(mock_cls)


async def test_auth_none_creates_session_without_auth() -> None:
    """Verify AuthMethod.NONE creates session without credentials."""
    auth = AuthConfig(method=AuthMethod.NONE)
    with patch(_PATCH_CONNECTOR), patch(_PATCH_SESSION) as mock_cls:
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100", auth=auth):
            _assert_session_kwargs(mock_cls)


async def test_auth_allowlist_creates_session_without_auth() -> None:
    """Verify AuthMethod.ALLOWLIST creates session without credentials."""
    auth = AuthConfig(method=AuthMethod.ALLOWLIST)
    with patch(_PATCH_CONNECTOR), patch(_PATCH_SESSION) as mock_cls:
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100", auth=auth):
            _assert_session_kwargs(mock_cls)


async def test_auth_basic_creates_session_with_basic_auth() -> None:
    """Verify AuthMethod.BASIC creates session with BasicAuth."""
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    with patch(_PATCH_CONNECTOR), patch(_PATCH_SESSION) as mock_cls:
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100", auth=auth):
            _assert_session_kwargs(mock_cls, expect_basic=True)
            assert mock_cls.call_args[1]["auth"].login == "admin"
            assert mock_cls.call_args[1]["auth"].password == "pass"


async def test_auth_digest_creates_session_with_middleware() -> None:
    """Verify AuthMethod.DIGEST creates session with DigestAuthMiddleware."""
    auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="pass")
    with (
        patch(_PATCH_CONNECTOR),
        patch("pylocal_akuvox._http.aiohttp.DigestAuthMiddleware") as mock_digest_mw,
        patch(_PATCH_SESSION) as mock_cls,
    ):
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100", auth=auth):
            mock_digest_mw.assert_called_once_with("admin", "pass")
            mw_instance = mock_digest_mw.return_value
            assert mock_cls.call_args[1]["auth"] is None
            assert mock_cls.call_args[1]["middlewares"] == (mw_instance,)


_E2E_INFO_PAYLOAD: dict[str, object] = {
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
}


async def test_auth_basic_get_info_end_to_end() -> None:
    """Verify BASIC auth device retrieves info via real request path."""
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_E2E_INFO_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
            assert device._http._session is not None
            assert isinstance(device._http._session.auth, aiohttp.BasicAuth)
            info = await device.get_info()
    assert info.model == "E21V"


# -- T006: get_device_config facade tests --

_DEVICE_CONFIG_PAYLOAD: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "Config.DoorSetting.RELAY.HoldDelayA": "5",
        "Config.DoorSetting.RELAY.TriggerDelayA": "0",
        "Config.Network.LAN.IPAddress": "192.168.1.100",
    },
}


async def test_get_device_config_returns_device_config() -> None:
    """Verify get_device_config delegates to config module."""
    from pylocal_akuvox.models import DeviceConfig

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/config/get", payload=_DEVICE_CONFIG_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100") as device:
            cfg = await device.get_device_config()

    assert isinstance(cfg, DeviceConfig)
    assert len(cfg) == 3


async def test_get_device_config_with_auth() -> None:
    """Verify get_device_config works with BASIC auth."""
    from pylocal_akuvox.models import DeviceConfig

    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/config/get", payload=_DEVICE_CONFIG_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
            cfg = await device.get_device_config()

    assert isinstance(cfg, DeviceConfig)


async def test_auth_digest_get_info_end_to_end() -> None:
    """Verify DIGEST auth device retrieves info via real request path."""
    auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="pass")
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_E2E_INFO_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
            assert device._http._session is not None
            info = await device.get_info()
    assert info.model == "E21V"


# -- T011: set_device_config facade tests --

_SET_CONFIG_SUCCESS: dict[str, object] = {
    "retcode": 0,
    "action": "config",
    "message": "set successfully!",
    "data": {},
}


async def test_set_device_config_delegates() -> None:
    """Verify set_device_config delegates to config module."""
    settings = {"Config.DoorSetting.RELAY.HoldDelayA": "8"}
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_CONFIG_SUCCESS)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.set_device_config(settings)

    url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/config/set"))
    call = m.requests[url_key][0]
    body = call.kwargs["json"]
    assert body["target"] == "config"
    assert body["action"] == "set"
    assert body["data"] == settings


async def test_set_device_config_with_auth() -> None:
    """Verify set_device_config works with BASIC auth."""
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    settings = {"Config.DoorSetting.RELAY.HoldDelayA": "8"}
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_CONFIG_SUCCESS)
        async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
            assert device._http._session is not None
            assert isinstance(device._http._session.auth, aiohttp.BasicAuth)
            await device.set_device_config(settings)

    url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/config/set"))
    assert url_key in m.requests


# ---------------------------------------------------------------------------
# T022: AkuvoxDevice.probe_capabilities() wrapper
# ---------------------------------------------------------------------------


async def test_probe_capabilities_default_resolves_to_5_seconds() -> None:
    """device.probe_capabilities() with no kwarg passes timeout=5.0 to helper."""
    from unittest.mock import AsyncMock, patch

    from pylocal_akuvox.capabilities import (
        Capability,
        CapabilityStatus,
        DeviceCapabilities,
    )

    sentinel = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={Capability.USER_LIST: CapabilityStatus.SUPPORTED},
        field_aliases={},
        schema_shapes={},
        notes={},
    )

    device = AkuvoxDevice(host="192.168.1.100", timeout=5, request_delay=0.0)
    with patch(
        "pylocal_akuvox.device._probe_capabilities",
        new=AsyncMock(return_value=sentinel),
    ) as mock_probe:
        result = await device.probe_capabilities()

    assert result is sentinel
    # Wrapper resolves None → 5.0 default per probe-api.md §"Public surface".
    assert mock_probe.call_args.kwargs["timeout"] == 5.0
    # Result becomes the device's effective profile.
    assert device.capabilities is sentinel


async def test_probe_capabilities_with_custom_timeout() -> None:
    """device.probe_capabilities(timeout=2.5) threads through to the helper."""
    from unittest.mock import AsyncMock, patch

    from pylocal_akuvox.capabilities import DeviceCapabilities

    sentinel = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={},
        field_aliases={},
        schema_shapes={},
        notes={},
    )

    device = AkuvoxDevice(host="192.168.1.100", timeout=5, request_delay=0.0)
    with patch(
        "pylocal_akuvox.device._probe_capabilities",
        new=AsyncMock(return_value=sentinel),
    ) as mock_probe:
        await device.probe_capabilities(timeout=2.5)

    assert mock_probe.call_args.kwargs["timeout"] == 2.5


async def test_capabilities_property_is_none_until_probed() -> None:
    """device.capabilities is None before any probe runs."""
    device = AkuvoxDevice(host="192.168.1.100", timeout=5, request_delay=0.0)
    assert device.capabilities is None
