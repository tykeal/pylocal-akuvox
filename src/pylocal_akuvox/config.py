# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Relay configuration operations for Akuvox devices."""

from __future__ import annotations

KEY_MAP: dict[str, str] = {
    "hold_delay_a": "Config.DoorSetting.RELAY.HoldDelayA",
    "trig_delay_a": "Config.DoorSetting.RELAY.TrigDelayA",
    "relay_name_a": "Config.DoorSetting.RELAY.RelayNameA",
    "hold_delay_b": "Config.DoorSetting.RELAY.HoldDelayB",
    "trig_delay_b": "Config.DoorSetting.RELAY.TrigDelayB",
    "relay_name_b": "Config.DoorSetting.RELAY.RelayNameB",
}

_REVERSE_MAP: dict[str, str] | None = None


def reverse_key_map() -> dict[str, str]:
    """Return a mapping from autop-format keys to snake_case attribute names."""
    global _REVERSE_MAP  # noqa: PLW0603
    if _REVERSE_MAP is None:
        _REVERSE_MAP = {v: k for k, v in KEY_MAP.items()}
    return _REVERSE_MAP
