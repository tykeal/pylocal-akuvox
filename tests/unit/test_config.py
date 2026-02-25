# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for device configuration module."""

from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxConnectionError,
    AkuvoxDeviceError,
)
from pylocal_akuvox.models import DeviceConfig

# -- T004: get_device_config() function tests --

BASE_URL = "http://192.168.1.100"

_CONFIG_RESPONSE = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "Config.DoorSetting.RELAY.HoldDelayA": "5",
        "Config.DoorSetting.RELAY.TriggerDelayA": "0",
        "Config.DoorSetting.RELAY.NameA": "Relay1",
        "Config.Network.LAN.IPAddress": "192.168.1.100",
    },
}


async def test_get_device_config_returns_device_config() -> None:
    """Verify get_device_config returns a DeviceConfig with all keys."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/config/get", payload=_CONFIG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            cfg = await device.get_device_config()

    assert isinstance(cfg, DeviceConfig)
    assert len(cfg) == 4
    assert cfg["Config.DoorSetting.RELAY.HoldDelayA"] == "5"
    assert cfg["Config.Network.LAN.IPAddress"] == "192.168.1.100"


async def test_get_device_config_device_error() -> None:
    """Verify negative retcode raises AkuvoxDeviceError."""
    error_response = {
        "retcode": -1,
        "action": "get",
        "message": "Failed",
        "data": {},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/config/get", payload=error_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="Failed"):
                await device.get_device_config()


async def test_get_device_config_connection_error() -> None:
    """Verify connection failure raises AkuvoxConnectionError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/config/get",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.get_device_config()
