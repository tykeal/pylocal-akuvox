# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for relay configuration module."""

from __future__ import annotations

import re

from pylocal_akuvox.config import KEY_MAP

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
