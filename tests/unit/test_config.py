# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for relay configuration module."""

from __future__ import annotations

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox.config import KEY_MAP
from pylocal_akuvox.exceptions import (
    AkuvoxConnectionError,
    AkuvoxDeviceError,
)
from pylocal_akuvox.models import RelayConfig

_AUTOP_PATTERN = re.compile(r"^Config\.DoorSetting\.RELAY\.\w+$")

_EXPECTED_KEYS = {
    "hold_delay_a",
    "trig_delay_a",
    "relay_name_a",
    "hold_delay_b",
    "trig_delay_b",
    "relay_name_b",
}


def test_key_map_contains_all_expected_keys() -> None:
    """Verify KEY_MAP contains all expected snake_case keys."""
    assert _EXPECTED_KEYS.issubset(KEY_MAP.keys())


def test_key_map_values_match_autop_pattern() -> None:
    """Verify every KEY_MAP value matches Config.DoorSetting.RELAY.* pattern."""
    for attr_name, autop_key in KEY_MAP.items():
        assert _AUTOP_PATTERN.match(autop_key), (
            f"KEY_MAP[{attr_name!r}] = {autop_key!r} "
            f"does not match {_AUTOP_PATTERN.pattern}"
        )


def test_key_map_reverse_lookup() -> None:
    """Verify reverse lookup from autop-format to snake_case works."""
    from pylocal_akuvox.config import reverse_key_map

    reverse = reverse_key_map()
    for attr_name, autop_key in KEY_MAP.items():
        assert reverse[autop_key] == attr_name


def test_key_map_reverse_lookup_length() -> None:
    """Verify reverse map has same length as KEY_MAP (no collisions)."""
    from pylocal_akuvox.config import reverse_key_map

    assert len(reverse_key_map()) == len(KEY_MAP)


# -- T007: get_relay_config() function tests --

BASE_URL = "http://192.168.1.100"

_RELAY_CONFIG_RESPONSE = {
    "retcode": 0,
    "action": "relay",
    "message": "get successfully!",
    "data": {
        "Config.DoorSetting.RELAY.HoldDelayA": "5",
        "Config.DoorSetting.RELAY.TrigDelayA": "0",
        "Config.DoorSetting.RELAY.RelayNameA": "Door",
    },
}


async def test_get_relay_config_returns_relay_config() -> None:
    """Verify get_relay_config returns a RelayConfig object."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/relay/get", payload=_RELAY_CONFIG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            cfg = await device.get_relay_config()

    assert isinstance(cfg, RelayConfig)
    assert cfg.hold_delay_a == "5"
    assert cfg.trig_delay_a == "0"
    assert cfg.relay_name_a == "Door"


async def test_get_relay_config_with_extra_keys() -> None:
    """Verify get_relay_config stores unknown keys in extra."""
    response = {
        "retcode": 0,
        "action": "relay",
        "message": "get successfully!",
        "data": {
            "Config.DoorSetting.RELAY.HoldDelayA": "5",
            "Config.DoorSetting.RELAY.TrigDelayA": "0",
            "Config.DoorSetting.RELAY.RelayNameA": "Door",
            "Config.DoorSetting.RELAY.HttpRelayA": "1",
        },
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/relay/get", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            cfg = await device.get_relay_config()

    assert cfg.extra is not None
    assert cfg.extra["Config.DoorSetting.RELAY.HttpRelayA"] == "1"


async def test_get_relay_config_device_error() -> None:
    """Verify negative retcode raises AkuvoxDeviceError."""
    error_response = {
        "retcode": -1,
        "action": "relay",
        "message": "Failed",
        "data": {},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/relay/get", payload=error_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="Failed"):
                await device.get_relay_config()


async def test_get_relay_config_connection_error() -> None:
    """Verify connection failure raises AkuvoxConnectionError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/relay/get",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.get_relay_config()
