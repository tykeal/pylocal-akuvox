# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for AkuvoxDevice connect/disconnect lifecycle and error cases."""

import asyncio
import contextlib
import inspect
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox import (
    _device_access,
    _device_config_logs,
    _device_contacts,
    _device_relays,
    _device_users,
)
from pylocal_akuvox.auth import AuthConfig, AuthMethod
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxParseError,
    AkuvoxUnsupportedError,
)
from pylocal_akuvox.models import DeviceInfo, DeviceStatus
from tests.unit._helpers import assert_only_connect_time_info, register_default_info

BASE_URL = "http://192.168.1.100"

# -- T018: Connect / disconnect lifecycle --


async def test_context_manager_creates_and_closes_session() -> None:
    """Verify async context manager opens and closes the HTTP session."""
    device = AkuvoxDevice("192.168.1.100")
    with aioresponses() as m:
        register_default_info(m)
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
    with aioresponses() as m:
        register_default_info(m)
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
        with pytest.raises(AkuvoxConnectionError, match="Connection"):
            async with AkuvoxDevice("192.168.1.100", timeout=2):
                pass


async def test_timeout_raises_connection_error() -> None:
    """Verify connection timeout raises AkuvoxConnectionError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=TimeoutError("Timed out"),
        )
        with pytest.raises(AkuvoxConnectionError):
            async with AkuvoxDevice("192.168.1.100", timeout=1):
                pass


async def test_http_401_raises_authentication_error() -> None:
    """Verify HTTP 401 raises AkuvoxAuthenticationError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            status=401,
        )
        with pytest.raises(AkuvoxAuthenticationError):
            async with AkuvoxDevice("192.168.1.100"):
                pass


async def test_non_json_response_raises_parse_error() -> None:
    """Verify non-JSON response raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            body="<html>Not Found</html>",
            content_type="text/html",
        )
        with pytest.raises(AkuvoxParseError):
            async with AkuvoxDevice("192.168.1.100"):
                pass


async def test_missing_envelope_raises_parse_error() -> None:
    """Verify response without envelope fields raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"unexpected": "data"},
        )
        with pytest.raises(AkuvoxParseError, match="envelope"):
            async with AkuvoxDevice("192.168.1.100"):
                pass


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
        with pytest.raises(AkuvoxParseError, match="Missing required field"):
            async with AkuvoxDevice("192.168.1.100"):
                pass


# -- T022: get_status tests --


async def test_get_status_returns_device_status() -> None:
    """Verify get_status calls GET /api/system/status and returns DeviceStatus."""
    with aioresponses() as m:
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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

# Stub DeviceInfo used by the auth-mode tests below to short-circuit
# the connect-time ``get_info()`` round-trip in ``__aenter__``. Those
# tests patch out ``aiohttp.ClientSession`` entirely so no real HTTP
# response is available; replacing ``get_info`` on the class with an
# ``AsyncMock`` lets the matrix-lookup step run against a known stub.
_STUB_INFO = DeviceInfo(
    model="StubModel",
    mac_address="AA:BB:CC:DD:EE:FF",
    firmware_version="0.0.0.0",
    hardware_version="0.0",
    uptime=None,
    web_language=None,
)


def _patch_get_info_stub() -> contextlib.AbstractContextManager[AsyncMock]:
    """Return a context manager that stubs ``AkuvoxDevice.get_info``."""
    return patch(
        "pylocal_akuvox.device.AkuvoxDevice.get_info",
        new=AsyncMock(return_value=_STUB_INFO),
    )


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
    with (
        patch(_PATCH_CONNECTOR),
        patch(_PATCH_SESSION) as mock_cls,
        _patch_get_info_stub(),
    ):
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100"):
            _assert_session_kwargs(mock_cls)


async def test_auth_none_creates_session_without_auth() -> None:
    """Verify AuthMethod.NONE creates session without credentials."""
    auth = AuthConfig(method=AuthMethod.NONE)
    with (
        patch(_PATCH_CONNECTOR),
        patch(_PATCH_SESSION) as mock_cls,
        _patch_get_info_stub(),
    ):
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100", auth=auth):
            _assert_session_kwargs(mock_cls)


async def test_auth_allowlist_creates_session_without_auth() -> None:
    """Verify AuthMethod.ALLOWLIST creates session without credentials."""
    auth = AuthConfig(method=AuthMethod.ALLOWLIST)
    with (
        patch(_PATCH_CONNECTOR),
        patch(_PATCH_SESSION) as mock_cls,
        _patch_get_info_stub(),
    ):
        mock_session = mock_cls.return_value
        mock_session.closed = False
        mock_session.close = _async_noop
        async with AkuvoxDevice("192.168.1.100", auth=auth):
            _assert_session_kwargs(mock_cls)


async def test_auth_basic_creates_session_with_basic_auth() -> None:
    """Verify AuthMethod.BASIC creates session with BasicAuth."""
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    with (
        patch(_PATCH_CONNECTOR),
        patch(_PATCH_SESSION) as mock_cls,
        _patch_get_info_stub(),
    ):
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
        _patch_get_info_stub(),
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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

    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._capability_types import (
        Capability,
        CapabilityStatus,
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

    from pylocal_akuvox._capability_profile import DeviceCapabilities

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


# ---------------------------------------------------------------------------
# T036: Connect-time matrix population (FR-008)
# ---------------------------------------------------------------------------


_CONNECT_DEVICE_PAYLOADS: dict[str, dict[str, object]] = {
    "X916": {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "X916",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "916.30.10.114",
                "HardwareVersion": "1.0",
            }
        },
    },
    "X915S": {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "X915S",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "2915.30.10.114",
                "HardwareVersion": "1.0",
            }
        },
    },
    "E18C": {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "E18C",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "18.30.11.21",
                "HardwareVersion": "1.0",
            }
        },
    },
    "IT83": {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "IT83",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "83.30.10.4",
                "HardwareVersion": "1.0",
            }
        },
    },
}


@pytest.mark.parametrize("device_class", ["X916", "X915S", "E18C", "IT83"])
async def test_connect_populates_capabilities(device_class: str) -> None:
    """``__aenter__`` populates ``device.capabilities`` from the matrix.

    Per ``contracts/matrix-lookup.md`` §"Connect-time integration"
    (FR-008): the connect-time ``GET /api/system/info`` call is the
    only HTTP request that fires before the matrix is consulted, and
    no list-endpoint requests are issued during ``__aenter__``.
    """
    from pylocal_akuvox._capability_matching import lookup_capabilities

    payload = _CONNECT_DEVICE_PAYLOADS[device_class]
    data = payload["data"]
    assert isinstance(data, dict)
    expected = lookup_capabilities(DeviceInfo.from_api_response(data))
    assert expected is not None

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=payload)
        async with AkuvoxDevice("192.168.1.100") as device:
            assert device.capabilities is expected
            assert device.capabilities.provenance is not None

    # Exactly one GET to /api/system/info; ZERO list-endpoint requests.
    assert_only_connect_time_info(m)
    info_url_key = ("GET", aiohttp.client.URL(f"{BASE_URL}/api/system/info"))
    assert info_url_key in m.requests


# ---------------------------------------------------------------------------
# T037: Unrecognised-device fallback (FR-013)
# ---------------------------------------------------------------------------


_UNRECOGNISED_INFO: dict[str, object] = {
    "retcode": 0,
    "action": "info",
    "message": "",
    "data": {
        "Status": {
            "Model": "UnknownDevice",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "1.0.0.0",
            "HardwareVersion": "1.0",
        }
    },
}


async def test_unrecognised_device_installs_conservative_empty_profile() -> None:
    """Unknown model gets the conservative-empty fallback profile."""
    from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_UNRECOGNISED_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            caps = device.capabilities
            assert caps is not None
            assert dict(caps.capabilities) == {}
            assert "device_not_in_matrix" in caps.notes
            note_text = caps.notes["device_not_in_matrix"]
            assert "probe_capabilities" in note_text
            assert "attempt_unknown_capability" in note_text

            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )
            # Closed-set: either reason is acceptable per
            # matrix-lookup.md §"Connect-time integration" note.
            assert exc_info.value.reason in {
                "capability_unknown",
                "device_unrecognized",
            }

    # Only the connect-time info call fired.
    assert_only_connect_time_info(m)


def test_private_require_capabilities_stays_callable() -> None:
    """The compatibility capability helper delegates to runtime logic."""
    from pylocal_akuvox._capability_profile import DeviceCapabilities

    sentinel = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={},
        field_aliases={},
        schema_shapes={},
        notes={},
    )

    device = AkuvoxDevice(host="192.168.1.100", timeout=5, request_delay=0.0)
    device._capabilities = sentinel  # noqa: SLF001

    assert device._require_capabilities() is sentinel  # noqa: SLF001


def test_private_relay_resolvers_stay_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The private relay resolver methods remain thin compatibility delegates."""
    from pylocal_akuvox import _device_relays
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._capability_types import Capability

    sentinel = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={},
        field_aliases={},
        schema_shapes={},
        notes={},
    )
    calls: list[tuple[str, bool]] = []

    def fake_override(
        caps: DeviceCapabilities,
        adapter: Capability,
        *,
        allow_unknown: bool,
    ) -> Capability:
        """Record override resolver arguments."""
        assert caps is sentinel
        assert adapter is Capability.RELAY_TRIGGER_API
        calls.append(("override", allow_unknown))
        return Capability.RELAY_TRIGGER_API

    def fake_default(caps: DeviceCapabilities) -> Capability:
        """Record default resolver arguments."""
        assert caps is sentinel
        calls.append(("default", False))
        return Capability.RELAY_TRIGGER_FCGI

    monkeypatch.setattr(_device_relays, "resolve_override_adapter", fake_override)
    monkeypatch.setattr(_device_relays, "resolve_default_adapter", fake_default)

    device = AkuvoxDevice(host="192.168.1.100", timeout=5, request_delay=0.0)
    device.attempt_unknown_capability = True

    assert (
        device._resolve_override_adapter(sentinel, Capability.RELAY_TRIGGER_API)  # noqa: SLF001
        is Capability.RELAY_TRIGGER_API
    )
    assert (
        device._resolve_default_adapter(sentinel)  # noqa: SLF001
        is Capability.RELAY_TRIGGER_FCGI
    )
    assert calls == [("override", True), ("default", False)]


# ---------------------------------------------------------------------------
# T038: Per-method capability gate + introspection audit (FR-011, SC-005)
# ---------------------------------------------------------------------------

# Documented infrastructure and explicit opt-in surfaces that are NOT
# capability-gated. ``open_door_http`` uses per-call Open Relay Via HTTP
# credentials and must remain available without a capability probe.
_INFRA_OUT_OF_SCOPE = {
    "get_info",
    "get_status",
    "open_door_http",
    "probe_capabilities",
}

# Methods whose gate lives in the ``RELAY_TRIGGER_ADAPTERS`` registry
# scan, NOT in a literal ``self._capabilities.require(...)`` call.
# Per ``contracts/adapter-dispatch.md`` §"Dispatch order".
_ADAPTER_GATED = {"trigger_relay"}

_DEVICE_HELPERS: dict[str, tuple[str, Callable[..., Any]]] = {
    "add_contact": ("_device_contacts", _device_contacts.add_contact),
    "add_group": ("_device_access", _device_access.add_group),
    "add_schedule": ("_device_access", _device_access.add_schedule),
    "add_user": ("_device_users", _device_users.add_user),
    "delete_contact": ("_device_contacts", _device_contacts.delete_contact),
    "delete_group": ("_device_access", _device_access.delete_group),
    "delete_schedule": ("_device_access", _device_access.delete_schedule),
    "delete_user": ("_device_users", _device_users.delete_user),
    "get_call_logs": ("_device_config_logs", _device_config_logs.get_call_logs),
    "get_device_config": (
        "_device_config_logs",
        _device_config_logs.get_device_config,
    ),
    "get_door_logs": ("_device_config_logs", _device_config_logs.get_door_logs),
    "get_relay_status": ("_device_relays", _device_relays.get_relay_status),
    "list_contacts": ("_device_contacts", _device_contacts.list_contacts),
    "list_groups": ("_device_access", _device_access.list_groups),
    "list_schedules": ("_device_access", _device_access.list_schedules),
    "list_users": ("_device_users", _device_users.list_users),
    "modify_contact": ("_device_contacts", _device_contacts.modify_contact),
    "modify_group": ("_device_access", _device_access.modify_group),
    "modify_schedule": ("_device_access", _device_access.modify_schedule),
    "modify_user": ("_device_users", _device_users.modify_user),
    "set_device_config": ("_device_config_logs", _device_config_logs.set_device_config),
    "trigger_relay": ("_device_relays", _device_relays.trigger_relay),
}


def _public_coroutine_methods() -> list[tuple[str, Callable[..., Any]]]:
    """Return every public (non-underscore) coroutine method on AkuvoxDevice."""
    return [
        (name, fn)
        for name, fn in inspect.getmembers(
            AkuvoxDevice, predicate=inspect.iscoroutinefunction
        )
        if not name.startswith("_")
    ]


def test_every_public_device_method_has_capability_gate() -> None:
    """FR-011 introspection lock: every non-exempt public coroutine is gated.

    Iterates :func:`inspect.getmembers` over :class:`AkuvoxDevice`,
    filters to public coroutine functions, partitions by the explicit
    out-of-scope sets, and asserts every remaining method delegates to
    a helper whose source contains the literal
    ``ctx.capabilities.require(`` substring.

    The exempt sets ``_INFRA_OUT_OF_SCOPE`` and ``_ADAPTER_GATED`` are
    defined at the module level above (with explanatory comments) so
    that the rationale is visible at the test-failure site. Adding a
    new method without a gate forces a deliberate update to one of
    these sets — locking FR-011 in CI.
    """
    methods = _public_coroutine_methods()
    assert methods, "expected at least one public coroutine on AkuvoxDevice"

    for name, fn in methods:
        if name in _INFRA_OUT_OF_SCOPE:
            continue
        helper = _DEVICE_HELPERS.get(name)
        assert helper is not None, (
            f"public coroutine {name!r} on AkuvoxDevice is missing "
            "an entry in _DEVICE_HELPERS"
        )
        helper_module, helper_fn = helper
        if name in _ADAPTER_GATED:
            # Adapter-gated methods reference RELAY_TRIGGER_ADAPTERS
            # instead of a literal require(...) call.
            source = inspect.getsource(helper_fn)
            assert "RELAY_TRIGGER_ADAPTERS" in source, (
                f"adapter-gated method {name!r} must reference "
                f"RELAY_TRIGGER_ADAPTERS in its source"
            )
            continue
        helper_call = f"{helper_module}.{helper_fn.__name__}"
        assert helper_call in inspect.getsource(fn), (
            f"public coroutine {name!r} on AkuvoxDevice must delegate "
            "to its owning helper"
        )
        source = inspect.getsource(helper_fn)
        assert "ctx.capabilities.require(" in source, (
            f"public coroutine {name!r} on AkuvoxDevice is missing a "
            "capability gate in its owning helper (expected literal "
            "'ctx.capabilities.require(' in helper source)"
        )


async def test_unsupported_raises_before_request_x915s_add_contact() -> None:
    """X915S add_contact raises ``capability_missing`` with no service request.

    The connect-time ``GET /api/system/info`` is unavoidable; the
    capability gate prevents any *additional* request beyond that
    discovery call (asserted via
    :func:`assert_only_connect_time_info` below, which checks
    both the request-key set and the per-key call count).
    """
    from pylocal_akuvox._capability_types import Capability
    from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_CONNECT_DEVICE_PAYLOADS["X915S"],
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.add_contact(name="Bob")
        assert exc_info.value.reason == "capability_missing"
        assert exc_info.value.capability is Capability.CONTACT_ADD
        assert exc_info.value.device_class == "X915S"
    assert_only_connect_time_info(m)


async def test_unsupported_raises_before_request_it83_relay_api() -> None:
    """IT83 trigger_relay(adapter=API) raises ``capability_missing``."""
    from pylocal_akuvox._capability_types import Capability
    from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_CONNECT_DEVICE_PAYLOADS["IT83"],
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1, adapter=Capability.RELAY_TRIGGER_API)
        assert exc_info.value.reason == "capability_missing"
        assert exc_info.value.capability is Capability.RELAY_TRIGGER_API
        assert exc_info.value.device_class == "IT83"
    assert_only_connect_time_info(m)


async def test_unsupported_raises_before_request_it83_add_user() -> None:
    """IT83 add_user raises ``capability_unknown`` (UNKNOWN status by default)."""
    from pylocal_akuvox._capability_types import Capability
    from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_CONNECT_DEVICE_PAYLOADS["IT83"],
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )
        assert exc_info.value.reason == "capability_unknown"
        assert exc_info.value.capability is Capability.USER_ADD
        assert exc_info.value.device_class == "IT83"
    assert_only_connect_time_info(m)


# ---------------------------------------------------------------------------
# T039: ``attempt_unknown_capability`` integrator opt-in (FR-021, SC-011)
# ---------------------------------------------------------------------------


def test_attempt_unknown_capability_defaults_false() -> None:
    """``attempt_unknown_capability`` defaults to False."""
    device = AkuvoxDevice("192.168.1.100")
    assert device.attempt_unknown_capability is False


async def test_attempt_unknown_default_raises_for_unknown_capability() -> None:
    """Default opt-out: UNKNOWN-status call raises with no service request.

    The connect-time ``GET /api/system/info`` is unavoidable; no
    *additional* request is issued beyond that discovery call
    (asserted below).
    """
    from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_CONNECT_DEVICE_PAYLOADS["IT83"],
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            assert device.attempt_unknown_capability is False
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )
            assert exc_info.value.reason == "capability_unknown"
    assert_only_connect_time_info(m)


async def test_attempt_unknown_true_lets_unknown_capability_through() -> None:
    """Opt-in: UNKNOWN-status call dispatches; library surfaces device error."""
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_CONNECT_DEVICE_PAYLOADS["IT83"],
        )
        # Device-side failure envelope: retcode<0 surfaces as
        # AkuvoxDeviceError per `_handle_response`.
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": -1,
                "action": "set",
                "message": "Device-side failure",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            device.attempt_unknown_capability = True
            with pytest.raises(AkuvoxDeviceError):
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )
        # The connect-time info call AND the dispatched POST fired.
        post_url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        assert post_url_key in m.requests


async def test_attempt_unknown_does_not_bypass_unsupported() -> None:
    """Opt-in does NOT bypass confirmed UNSUPPORTED (X915S add_contact)."""
    from pylocal_akuvox._capability_types import Capability
    from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_CONNECT_DEVICE_PAYLOADS["X915S"],
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            device.attempt_unknown_capability = True
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.add_contact(name="Bob")
        assert exc_info.value.reason == "capability_missing"
        assert exc_info.value.capability is Capability.CONTACT_ADD
    # Only the connect-time info call.
    assert_only_connect_time_info(m)


# --- Coverage: defensive paths ----------------------------------------------


async def test_trigger_relay_without_context_manager_raises() -> None:
    """Calling a service method before __aenter__ surfaces a clear error.

    Covers the defensive ``self._capabilities is None`` arm of
    ``_require_capabilities``. Per Copilot review round 4, this is
    a lifecycle / session-not-open error rather than a capability
    outcome, so the helper raises :class:`AkuvoxConnectionError`
    (mirroring the rest of the public surface when the HTTP
    session is closed) instead of an
    :class:`AkuvoxUnsupportedError` with the misleading
    ``device_unrecognized`` reason.
    """
    device = AkuvoxDevice("192.168.1.100")
    with pytest.raises(AkuvoxConnectionError) as exc_info:
        await device.trigger_relay(num=1)
    assert "context manager" in str(exc_info.value)


async def test_default_dispatch_all_unsupported_raises_capability_missing() -> None:
    """All relay-trigger variants UNSUPPORTED => ``capability_missing``.

    The IT83 matrix entry has API=UNSUPPORTED + FCGI=SUPPORTED, so a
    real device cannot trip this branch. Construct a synthetic
    capabilities profile that flips FCGI to UNSUPPORTED to exercise
    the all-unsupported branch in
    :meth:`AkuvoxDevice._resolve_default_adapter`.
    """
    from pylocal_akuvox import (
        Capability,
        CapabilityStatus,
        DeviceCapabilities,
    )

    info_payload = {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "IT83",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "83.30.10.4",
                "HardwareVersion": "1.0",
            }
        },
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=info_payload)
        async with AkuvoxDevice("192.168.1.100") as device:
            # Override capabilities profile: every relay-trigger variant
            # UNSUPPORTED.
            device._capabilities = DeviceCapabilities(  # noqa: SLF001
                device_class="SyntheticBricked",
                firmware_version="0.0.0",
                capabilities={
                    Capability.RELAY_TRIGGER_API: CapabilityStatus.UNSUPPORTED,
                    Capability.RELAY_TRIGGER_FCGI: CapabilityStatus.UNSUPPORTED,
                },
                field_aliases={},
                schema_shapes={},
            )
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1)
        assert exc_info.value.reason == "capability_missing"


async def test_aexit_clears_cached_info_and_capabilities() -> None:
    """``__aexit__`` resets cached state so re-entry sees fresh data.

    Per Copilot review round 2: ``get_info()`` advertises caching
    "for the duration of a connection". Without clearing on exit,
    a second ``async with`` block would reuse the stale snapshot
    and capability-gated wrappers would silently dispatch against
    pre-reconnect data.
    """
    device = AkuvoxDevice("192.168.1.100")
    with aioresponses() as m:
        register_default_info(m, repeat=True)
        async with device:
            assert device._info is not None
            assert device._capabilities is not None
        assert device._info is None
        assert device._capabilities is None
        # Re-entry must succeed and re-populate.
        async with device:
            assert device._info is not None
            assert device._capabilities is not None
        assert device._info is None
        assert device._capabilities is None


async def test_trigger_relay_rejects_non_relay_adapter_override() -> None:
    """``trigger_relay(adapter=Capability.USER_ADD)`` raises validation error.

    The ``adapter=`` parameter is typed as ``Capability`` but only
    relay-trigger variants make sense. A non-relay capability
    would have previously leaked ``KeyError`` from the internal
    ``CAPABILITY_TO_VARIANT`` mapping; the adapter must reject
    such overrides at the public boundary with
    :class:`AkuvoxValidationError`.
    """
    from pylocal_akuvox._capability_types import Capability
    from pylocal_akuvox.exceptions import AkuvoxValidationError

    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError) as exc_info:
                await device.trigger_relay(num=1, adapter=Capability.USER_ADD)
        assert "relay-trigger variant" in str(exc_info.value)
        assert "user.add" in str(exc_info.value)


async def test_aenter_closes_session_when_discovery_fails() -> None:
    """If discovery raises inside ``__aenter__``, the HTTP session is closed.

    Per Copilot review round 4: ``_http.__aenter__()`` ran
    successfully, then ``get_info()`` raises (e.g. parse error on
    a malformed payload). ``__aexit__`` will not be invoked for an
    aborting ``__aenter__``, so without an internal try/except the
    aiohttp session and connector would leak. Assert that the
    underlying session is closed and that cached state is reset
    after the failed connect.
    """
    device = AkuvoxDevice("192.168.1.100")
    with aioresponses() as m:
        # Malformed envelope -> AkuvoxParseError inside get_info().
        m.get(f"{BASE_URL}/api/system/info", payload={"unexpected": "shape"})
        with pytest.raises(AkuvoxParseError):
            await device.__aenter__()
    # Session must be torn down; cached state must be cleared.
    assert device._http._session is None
    assert device._info is None
    assert device._capabilities is None


async def test_default_dispatch_reports_unknown_variant_in_error() -> None:
    """All-UNKNOWN dispatch: error.capability points at the UNKNOWN variant.

    Per Copilot review round 5: if the default dispatch fails
    because API=UNSUPPORTED + FCGI=UNKNOWN (no SUPPORTED variant,
    at least one UNKNOWN), the raised
    AkuvoxUnsupportedError(reason="capability_unknown") must
    carry a ``capability`` field that matches the variant that
    actually triggered the UNKNOWN path. Reporting the API
    variant in that case would be internally inconsistent — API
    is UNSUPPORTED, not UNKNOWN.
    """
    from pylocal_akuvox import (
        Capability,
        CapabilityStatus,
        DeviceCapabilities,
    )

    info_payload = {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "Synthetic",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "0.0.0",
                "HardwareVersion": "1.0",
            }
        },
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=info_payload)
        async with AkuvoxDevice("192.168.1.100") as device:
            device._capabilities = DeviceCapabilities(  # noqa: SLF001
                device_class="SyntheticAPIBlockedFCGIUnknown",
                firmware_version="0.0.0",
                capabilities={
                    Capability.RELAY_TRIGGER_API: CapabilityStatus.UNSUPPORTED,
                    # RELAY_TRIGGER_FCGI absent => UNKNOWN per status_of.
                },
                field_aliases={},
                schema_shapes={},
            )
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1)
        assert exc_info.value.reason == "capability_unknown"
        assert exc_info.value.capability is Capability.RELAY_TRIGGER_FCGI


async def test_aenter_clears_state_when_cleanup_close_raises_cancelled() -> None:
    """CancelledError during cleanup-close still resets cached state.

    Per Copilot review round 8: on Python 3.13
    ``asyncio.CancelledError`` inherits ``BaseException`` and would
    bypass a ``contextlib.suppress(Exception)``. ``__aenter__``
    wraps the cleanup close in ``contextlib.suppress(BaseException)``
    around an ``asyncio.shield``, so a cancellation in the close
    cannot skip the cached-state reset.
    """
    device = AkuvoxDevice("192.168.1.100")

    async def raise_cancelled(*_args: object, **_kwargs: object) -> None:
        """Stub ``__aexit__`` that immediately raises ``CancelledError``."""
        raise asyncio.CancelledError

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload={"unexpected": "shape"})
        with (
            patch.object(device._http, "__aexit__", side_effect=raise_cancelled),
            pytest.raises(AkuvoxParseError),
        ):
            await device.__aenter__()
    assert device._info is None
    assert device._capabilities is None
    # The mocked __aexit__ raised before the real close ran, so the
    # underlying aiohttp session is still open. Tidy it up here to
    # avoid a noisy "Unclosed client session" warning from aiohttp.
    if device._http._session is not None:
        await device._http._session.close()
        device._http._session = None
