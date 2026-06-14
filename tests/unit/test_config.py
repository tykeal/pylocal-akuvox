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
    AkuvoxValidationError,
)
from pylocal_akuvox.models import DeviceConfig
from tests.unit._helpers import register_default_info

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
        register_default_info(m)
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
        register_default_info(m)
        m.get(f"{BASE_URL}/api/config/get", payload=error_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="Failed"):
                await device.get_device_config()


async def test_get_device_config_connection_error() -> None:
    """Verify connection failure raises AkuvoxConnectionError."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.get_device_config()


# -- T010: set_device_config() function tests --

_SET_SUCCESS_RESPONSE = {
    "retcode": 0,
    "action": "config",
    "message": "set successfully!",
    "data": {},
}


async def test_set_device_config_single_key() -> None:
    """Verify set_device_config sends correct envelope for one key."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.set_device_config({"Config.DoorSetting.RELAY.HoldDelayA": "8"})

    sent = m.requests[("POST", _config_set_url())][0]
    body = sent.kwargs["json"]
    assert body["target"] == "config"
    assert body["action"] == "set"
    assert body["data"] == {"Config.DoorSetting.RELAY.HoldDelayA": "8"}


async def test_set_device_config_multiple_keys() -> None:
    """Verify set_device_config sends multiple keys in one call."""
    settings = {
        "Config.DoorSetting.RELAY.HoldDelayA": "8",
        "Config.DoorSetting.RELAY.NameA": "Front Door",
    }
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.set_device_config(settings)

    sent = m.requests[("POST", _config_set_url())][0]
    body = sent.kwargs["json"]
    assert body["data"] == settings


async def test_set_device_config_empty_dict_raises() -> None:
    """Verify empty settings dict raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="at least one"):
                await device.set_device_config({})

    assert ("POST", _config_set_url()) not in m.requests


async def test_set_device_config_device_error() -> None:
    """Verify negative retcode raises AkuvoxDeviceError."""
    error_response = {
        "retcode": -1,
        "action": "config",
        "message": "set failed",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/config/set", payload=error_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="set failed"):
                await device.set_device_config(
                    {"Config.DoorSetting.RELAY.HoldDelayA": "8"}
                )


async def test_set_device_config_connection_error() -> None:
    """Verify connection failure raises AkuvoxConnectionError."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/config/set",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.set_device_config(
                    {"Config.DoorSetting.RELAY.HoldDelayA": "8"}
                )


def _config_set_url() -> aiohttp.client.URL:
    """Build URL for aioresponses request lookup."""
    return aiohttp.client.URL(f"{BASE_URL}/api/config/set")


# -- T016: key discovery tests --

_MULTI_CATEGORY_DATA = {
    "Config.DoorSetting.RELAY.HoldDelayA": "5",
    "Config.DoorSetting.RELAY.TriggerDelayA": "0",
    "Config.DoorSetting.RELAY.NameA": "Relay1",
    "Config.Network.LAN.IPAddress": "192.168.1.100",
    "Config.Network.LAN.SubnetMask": "255.255.255.0",
    "Config.SIP.Account.DisplayName": "E21V",
    "Config.Features.DoorSetting.DoorUnlockMode": "1",
}


def test_keys_returns_all_config_keys() -> None:
    """Verify keys() returns all autop-format key names."""
    cfg = DeviceConfig.from_api_response(_MULTI_CATEGORY_DATA)
    keys = cfg.keys()
    assert len(keys) == 7
    assert "Config.DoorSetting.RELAY.HoldDelayA" in keys
    assert "Config.Network.LAN.IPAddress" in keys
    assert "Config.SIP.Account.DisplayName" in keys


def test_keys_groupable_by_category_prefix() -> None:
    """Verify keys can be grouped by dotted category prefix."""
    cfg = DeviceConfig.from_api_response(_MULTI_CATEGORY_DATA)
    categories: dict[str, int] = {}
    for key in cfg.keys():
        parts = key.split(".")
        cat = ".".join(parts[:2])
        categories[cat] = categories.get(cat, 0) + 1

    assert categories["Config.DoorSetting"] == 3
    assert categories["Config.Network"] == 2
    assert categories["Config.SIP"] == 1
    assert categories["Config.Features"] == 1


def test_specific_relay_and_network_keys_discoverable() -> None:
    """Verify specific relay and network keys are accessible."""
    cfg = DeviceConfig.from_api_response(_MULTI_CATEGORY_DATA)
    assert "Config.DoorSetting.RELAY.HoldDelayA" in cfg
    assert "Config.Network.LAN.SubnetMask" in cfg
    assert cfg["Config.SIP.Account.DisplayName"] == "E21V"
    assert cfg.get("Config.NonExistent.Key") is None
