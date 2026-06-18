# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for relay-trigger adapter dispatch (FR-012, SC-006).

Per ``specs/008-capability-matrix/contracts/adapter-dispatch.md``
§"Per-device-class behaviour":

* Door-phone classes (X916, X915S current FW, E18C current FW) dispatch
  to ``POST /api/relay/trig`` with the documented body shape.
* IT83 raises an actionable guard directing callers to
  ``open_door_http`` because credential-less OpenDoor dispatch is retired.
* IT83 with explicit ``adapter=Capability.RELAY_TRIGGER_API`` raises
  ``capability_missing`` with no relay-trigger request issued
  (the connect-time ``GET /api/system/info`` still happens; the
  capability gate prevents any *additional* request).
* X916 with explicit ``adapter=Capability.RELAY_TRIGGER_FCGI``
  (FCGI=UNKNOWN) raises ``capability_unknown`` by default; with the
  integrator opt-in flag set, it reaches the same OpenDoor guard.
* FCGI adapter issues no request for any relay-trigger shape; callers
  must use the credentialed ``open_door_http`` helper instead.
* Unrecognised-device profile + ``trigger_relay`` →
  ``capability_unknown`` with no relay request issued (only the
  connect-time info call).
* Empty registry simulates the ``adapter_missing`` reason.
"""

from __future__ import annotations

from typing import Any

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox._capability_types import Capability
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError
from tests.unit._helpers import (
    BASE_URL,
    assert_only_connect_time_info,
    register_default_info,
)

_TRIG_OK = {"retcode": 1, "action": "trigRelay", "message": "OK", "data": {}}


# Per-device-class info payloads --------------------------------------------

_X916_INFO = {
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
}
_X915S_INFO = {
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
}
_E18C_INFO = {
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
}
_IT83_INFO = {
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


# --- Door-phone classes route to /api/relay/trig --------------------------


@pytest.mark.parametrize(
    "info_payload",
    [_X916_INFO, _X915S_INFO, _E18C_INFO],
    ids=["X916", "X915S_current", "E18C_current"],
)
async def test_door_phone_classes_route_to_api_relay_trig(
    info_payload: dict[str, object],
) -> None:
    """X916 / X915S current / E18C current dispatch to ``POST /api/relay/trig``."""
    with aioresponses() as m:
        register_default_info(m, payload=info_payload)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1)
        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"))
        assert url_key in m.requests
        body = m.requests[url_key][0].kwargs["json"]
        assert body == {
            "target": "relay",
            "action": "trig",
            "data": {"num": 1, "mode": 0, "level": 0, "delay": 0},
        }


# --- IT83 FCGI dispatch raises actionable guard --------------------------


async def test_it83_routes_to_fcgi_guard() -> None:
    """IT83 trigger_relay raises the OpenDoor guard without a relay request."""
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(
                AkuvoxUnsupportedError, match="open_door_http"
            ) as exc_info:
                await device.trigger_relay(num=1)
        assert exc_info.value.reason == "capability_missing"
        assert exc_info.value.capability is Capability.RELAY_TRIGGER_FCGI
        assert_only_connect_time_info(m)


# --- IT83 + adapter=API → capability_missing ------------------------------


async def test_it83_with_api_adapter_override_raises_capability_missing() -> None:
    """IT83 + ``adapter=API`` raises ``capability_missing``.

    No relay-trigger request is issued; the only HTTP call in the
    log is the unavoidable connect-time ``GET /api/system/info``
    (asserted via :func:`assert_only_connect_time_info` below,
    which checks both the request-key set and the per-key call
    count).
    """
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1, adapter=Capability.RELAY_TRIGGER_API)
        assert exc_info.value.reason == "capability_missing"
        assert exc_info.value.capability is Capability.RELAY_TRIGGER_API
        assert exc_info.value.device_class == "IT83"
        # Only the connect-time /api/system/info call should be in the log.
        assert_only_connect_time_info(m)


# --- X916 + adapter=FCGI → capability_unknown by default; opt-in proceeds -


async def test_x916_with_fcgi_adapter_default_raises_capability_unknown() -> None:
    """X916 (FCGI=UNKNOWN) + ``adapter=FCGI`` raises by default."""
    with aioresponses() as m:
        register_default_info(m, payload=_X916_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1, adapter=Capability.RELAY_TRIGGER_FCGI)
        assert exc_info.value.reason == "capability_unknown"
        assert exc_info.value.capability is Capability.RELAY_TRIGGER_FCGI
        assert_only_connect_time_info(m)


async def test_x916_with_fcgi_adapter_and_attempt_unknown_reaches_guard() -> None:
    """X916 + adapter=FCGI + opt-in reaches the OpenDoor guard."""
    with aioresponses() as m:
        register_default_info(m, payload=_X916_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            device.attempt_unknown_capability = True
            with pytest.raises(
                AkuvoxUnsupportedError, match="open_door_http"
            ) as exc_info:
                await device.trigger_relay(num=1, adapter=Capability.RELAY_TRIGGER_FCGI)
        assert exc_info.value.reason == "capability_missing"
        assert exc_info.value.capability is Capability.RELAY_TRIGGER_FCGI
        assert_only_connect_time_info(m)


# --- FCGI adapter guards every relay-trigger shape -----------------------


@pytest.mark.parametrize(
    ("kwarg", "value"),
    [("mode", 1), ("level", 1), ("delay", 5)],
)
async def test_fcgi_adapter_rejects_nonzero_extras(kwarg: str, value: int) -> None:
    """FCGI adapter raises the OpenDoor guard before any relay request."""
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError, match="open_door_http"):
                kwargs: dict[str, Any] = {"num": 1, kwarg: value}
                await device.trigger_relay(**kwargs)
        # No FCGI request was issued.
        assert_only_connect_time_info(m)


# --- Unrecognised-device profile → capability_unknown ---------------------


async def test_unrecognised_device_trigger_relay_raises_capability_unknown() -> None:
    """Unrecognised model + ``trigger_relay`` raises (zero relay requests)."""
    info = {
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
    with aioresponses() as m:
        register_default_info(m, payload=info)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1)
        # Either ``capability_unknown`` or ``device_unrecognized`` is
        # acceptable per matrix-lookup.md §"Connect-time integration"
        # note. Both indicate the same observable failure mode.
        assert exc_info.value.reason in {"capability_unknown", "device_unrecognized"}
        assert_only_connect_time_info(m)


# --- adapter_missing simulation -----------------------------------------


async def test_adapter_missing_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry entry deletion surfaces ``reason="adapter_missing"``.

    The defensive ``if fn is None`` arm in ``trigger_relay`` is the
    only raise site for this reason. We exercise it by deleting the
    API entry from the registry copy used by the dispatcher.
    """
    from pylocal_akuvox import _device_relays, capability_adapters

    patched = dict(capability_adapters.RELAY_TRIGGER_ADAPTERS)
    del patched[(Capability.RELAY_TRIGGER_API, "api")]
    monkeypatch.setattr(_device_relays, "RELAY_TRIGGER_ADAPTERS", patched)

    with aioresponses() as m:
        register_default_info(m, payload=_X916_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError) as exc_info:
                await device.trigger_relay(num=1)
        assert exc_info.value.reason == "adapter_missing"
        assert_only_connect_time_info(m)


# --- FCGI adapter never sends credential-less OpenDoor requests -----------


async def test_fcgi_adapter_valid_shape_still_raises_guard() -> None:
    """FCGI adapter guard raises even for formerly valid default arguments."""
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError, match="open_door_http"):
                await device.trigger_relay(num=1)
        assert_only_connect_time_info(m)


async def test_fcgi_adapter_no_longer_classifies_http_500() -> None:
    """FCGI adapter guard does not issue requests for HTTP classification."""
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError, match="open_door_http"):
                await device.trigger_relay(num=1)
        assert_only_connect_time_info(m)


async def test_fcgi_adapter_no_longer_classifies_http_401() -> None:
    """FCGI adapter guard replaces the old auth-status mapping."""
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError, match="open_door_http"):
                await device.trigger_relay(num=1)
        assert_only_connect_time_info(m)


async def test_fcgi_adapter_no_longer_classifies_http_403() -> None:
    """FCGI adapter guard replaces the old request-status mapping."""
    with aioresponses() as m:
        register_default_info(m, payload=_IT83_INFO)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxUnsupportedError, match="open_door_http"):
                await device.trigger_relay(num=1)
        assert_only_connect_time_info(m)
