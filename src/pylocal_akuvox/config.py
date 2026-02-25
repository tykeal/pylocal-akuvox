# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Relay configuration operations for Akuvox devices."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.models import RelayConfig

KEY_MAP: dict[str, str] = {
    "hold_delay_a": "Config.DoorSetting.RELAY.HoldDelayA",
    "trig_delay_a": "Config.DoorSetting.RELAY.TrigDelayA",
    "relay_name_a": "Config.DoorSetting.RELAY.RelayNameA",
    "hold_delay_b": "Config.DoorSetting.RELAY.HoldDelayB",
    "trig_delay_b": "Config.DoorSetting.RELAY.TrigDelayB",
    "relay_name_b": "Config.DoorSetting.RELAY.RelayNameB",
}

_REVERSE_MAP: Mapping[str, str] | None = None


def reverse_key_map() -> Mapping[str, str]:
    """Return an immutable mapping from autop keys to attribute names."""
    global _REVERSE_MAP  # noqa: PLW0603
    if _REVERSE_MAP is None:
        _REVERSE_MAP = MappingProxyType({v: k for k, v in KEY_MAP.items()})
    return _REVERSE_MAP


async def get_relay_config(http: AkuvoxHttpClient) -> RelayConfig:
    """Retrieve relay configuration from the device.

    Args:
        http: The HTTP client for device communication.

    Returns:
        A RelayConfig object with the current relay settings.

    """
    from pylocal_akuvox.models import RelayConfig as _RelayConfig

    data = await http.get("/api/relay/get")
    return _RelayConfig.from_api_response(data)
