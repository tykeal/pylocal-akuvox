# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for relay operations: trigger and status retrieval."""

from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxValidationError,
)
from tests.unit._helpers import register_default_info

BASE_URL = "http://192.168.1.100"

_TRIG_OK_RESPONSE = {
    "retcode": 1,
    "action": "trigRelay",
    "message": "OK",
    "data": {},
}

_STATUS_RESPONSE = {
    "retcode": 0,
    "action": "get",
    "message": "",
    "data": {
        "RelayA": "open",
        "RelayB": "closed",
    },
}


async def test_trigger_relay_posts_to_correct_endpoint() -> None:
    """Verify trigger_relay POSTs to /api/relay/trig."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "relay"
        assert body["action"] == "trig"
        assert body["data"]["num"] == 1


async def test_trigger_relay_with_all_params() -> None:
    """Verify trigger_relay sends num, mode, level, delay."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=2, mode=1, level=1, delay=5)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "relay"
        assert body["action"] == "trig"
        assert body["data"] == {"num": 2, "mode": 1, "level": 1, "delay": 5}


async def test_trigger_relay_defaults() -> None:
    """Verify trigger_relay defaults: mode=0, level=0, delay=0."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["data"] == {"num": 1, "mode": 0, "level": 0, "delay": 0}


async def test_trigger_relay_invalid_num_zero() -> None:
    """Verify relay num 0 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Relay number must be"):
                await device.trigger_relay(num=0)


async def test_trigger_relay_invalid_num_negative() -> None:
    """Verify negative relay num raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Relay number must be"):
                await device.trigger_relay(num=-1)


async def test_trigger_relay_invalid_delay_negative() -> None:
    """Verify negative delay raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Delay must be"):
                await device.trigger_relay(num=1, delay=-1)


async def test_trigger_relay_invalid_delay_too_large() -> None:
    """Verify delay > 65535 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Delay must be"):
                await device.trigger_relay(num=1, delay=65536)


async def test_trigger_relay_invalid_mode() -> None:
    """Verify mode not 0 or 1 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Mode must be"):
                await device.trigger_relay(num=1, mode=2)


async def test_trigger_relay_invalid_mode_negative() -> None:
    """Verify negative mode raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Mode must be"):
                await device.trigger_relay(num=1, mode=-1)


async def test_trigger_relay_invalid_level() -> None:
    """Verify level not 0 or 1 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Level must be"):
                await device.trigger_relay(num=1, level=2)


async def test_trigger_relay_invalid_level_negative() -> None:
    """Verify negative level raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Level must be"):
                await device.trigger_relay(num=1, level=-1)


async def test_trigger_relay_max_delay_valid() -> None:
    """Verify delay=65535 (max) is accepted."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1, delay=65535)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["data"]["delay"] == 65535


async def test_trigger_relay_device_error() -> None:
    """Verify device error (retcode < 0) raises AkuvoxDeviceError."""
    error_response = {
        "retcode": -1,
        "action": "trigRelay",
        "message": "Failed",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=error_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="Failed"):
                await device.trigger_relay(num=1)


async def test_trigger_relay_connection_error() -> None:
    """Verify connection failure raises AkuvoxConnectionError."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/relay/trig",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.trigger_relay(num=1)


async def test_get_relay_status_gets_correct_endpoint() -> None:
    """Verify get_relay_status GETs /api/relay/status."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/relay/status", payload=_STATUS_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            result = await device.get_relay_status()

    assert result == {"RelayA": "open", "RelayB": "closed"}


async def test_get_relay_status_empty_data() -> None:
    """Verify get_relay_status returns empty dict when no data."""
    response = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/relay/status", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            result = await device.get_relay_status()

    assert result == {}


# --- Free-function coverage (relay.trigger_relay) ----------------------------
#
# Service-module free functions remain capability-unaware (Phase 2 contract).
# AkuvoxDevice.trigger_relay routes through the adapter registry, but the
# legacy free function is kept as a public entry point for advanced users
# who want a capability-unaware call. The tests below exercise it directly.


async def test_free_function_trigger_relay_posts_correctly() -> None:
    """Direct call to relay.trigger_relay free function."""
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.relay import trigger_relay

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await trigger_relay(http, num=3, mode=1, level=1, delay=10)

        # Verify the request was made to /api/relay/trig
        post_calls = [(k, v) for k, v in m.requests.items() if k[0] == "POST"]
        assert len(post_calls) == 1
        key, calls = post_calls[0]
        assert str(key[1]).endswith("/api/relay/trig")
        body = calls[0].kwargs["json"]
        assert body["target"] == "relay"
        assert body["action"] == "trig"
        assert body["data"] == {"num": 3, "mode": 1, "level": 1, "delay": 10}


async def test_free_function_trigger_relay_validates_args() -> None:
    """Free-function trigger_relay shares validation with adapter path."""
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.relay import trigger_relay

    async with AkuvoxHttpClient(host="192.168.1.100") as http:
        with pytest.raises(AkuvoxValidationError):
            await trigger_relay(http, num=0)
        with pytest.raises(AkuvoxValidationError):
            await trigger_relay(http, num=True)  # bool subclass rejected
