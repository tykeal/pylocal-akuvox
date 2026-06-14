# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Extended truth-table tests for :class:`DeviceClassPattern`.

Per ``specs/008-capability-matrix/contracts/matrix-lookup.md``
§"`DeviceClassPattern` matching semantics", these tests exercise every
production pattern shape used in ``CAPABILITY_MATRIX``:

* X916 ``glob`` band ``"916.30.10.*"``
* X915S ``floor`` band ``"2915.30.10.114+"``
* E18C ``glob`` band ``"18.30.11.*"``
* IT83 ``exact`` band ``"83.30.10.4"``

Phase 1 (``test_capabilities.py``) covered the same parser shape with
synthetic patterns; this file pins the four production-shape patterns
explicitly so a regression in any single pattern's parse path is
caught at this entry point even if other tests mask it.
"""

from __future__ import annotations

import pytest

from pylocal_akuvox.capabilities import DeviceClassPattern
from pylocal_akuvox.models import DeviceInfo


def _info(model: str, firmware: str) -> DeviceInfo:
    """Build a :class:`DeviceInfo` with only the fields the matcher uses."""
    return DeviceInfo(
        model=model,
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version=firmware,
        hardware_version="1.0",
        uptime=None,
        web_language=None,
    )


# --- X916 glob ``"916.30.10.*"`` -------------------------------------------


@pytest.mark.parametrize(
    "firmware",
    ["916.30.10.0", "916.30.10.114", "916.30.10.999"],
)
def test_x916_glob_matches_within_band(firmware: str) -> None:
    """Every fourth-segment value matches the X916 glob band."""
    pattern = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert pattern.matches(_info("X916", firmware))


@pytest.mark.parametrize(
    "firmware",
    ["916.30.11.0", "916.31.10.114", "917.30.10.0"],
)
def test_x916_glob_rejects_outside_band(firmware: str) -> None:
    """Differing in any non-``*`` segment fails the X916 glob match."""
    pattern = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert not pattern.matches(_info("X916", firmware))


def test_x916_glob_matches_model_with_suffix() -> None:
    """Model-prefix match is ``startswith`` so ``X916S`` matches ``X916``."""
    pattern = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert pattern.matches(_info("X916S", "916.30.10.114"))


# --- X915S floor ``"2915.30.10.114+"`` -------------------------------------


def test_x915s_floor_matches_at_floor() -> None:
    """Floor-form matches the floor itself (>= floor)."""
    pattern = DeviceClassPattern(model_prefix="X915S", firmware_band="2915.30.10.114+")
    assert pattern.matches(_info("X915S", "2915.30.10.114"))


def test_x915s_floor_matches_above_floor() -> None:
    """Floor-form matches strictly higher firmware."""
    pattern = DeviceClassPattern(model_prefix="X915S", firmware_band="2915.30.10.114+")
    assert pattern.matches(_info("X915S", "2915.30.10.115"))
    assert pattern.matches(_info("X915S", "2915.30.11.0"))
    assert pattern.matches(_info("X915S", "2916.0.0.0"))


def test_x915s_floor_rejects_below_floor() -> None:
    """Below-floor firmware (e.g. historical 113) does NOT match."""
    pattern = DeviceClassPattern(model_prefix="X915S", firmware_band="2915.30.10.114+")
    assert not pattern.matches(_info("X915S", "2915.30.10.113"))
    assert not pattern.matches(_info("X915S", "2915.30.9.999"))


# --- E18C glob ``"18.30.11.*"`` --------------------------------------------


def test_e18c_glob_matches_within_band() -> None:
    """E18C glob matches any fourth-segment value."""
    pattern = DeviceClassPattern(model_prefix="E18C", firmware_band="18.30.11.*")
    assert pattern.matches(_info("E18C", "18.30.11.21"))
    assert pattern.matches(_info("E18C", "18.30.11.0"))


def test_e18c_glob_rejects_outside_band() -> None:
    """E18C glob does NOT match a different third segment."""
    pattern = DeviceClassPattern(model_prefix="E18C", firmware_band="18.30.11.*")
    assert not pattern.matches(_info("E18C", "18.30.10.21"))
    assert not pattern.matches(_info("E18C", "19.30.11.21"))


# --- IT83 exact ``"83.30.10.4"`` ------------------------------------------


def test_it83_exact_matches_only_exact_firmware() -> None:
    """IT83 exact form matches only the literal firmware tuple."""
    pattern = DeviceClassPattern(model_prefix="IT83", firmware_band="83.30.10.4")
    assert pattern.matches(_info("IT83", "83.30.10.4"))


def test_it83_exact_rejects_neighbouring_firmwares() -> None:
    """One-off firmwares fail the IT83 exact match."""
    pattern = DeviceClassPattern(model_prefix="IT83", firmware_band="83.30.10.4")
    assert not pattern.matches(_info("IT83", "83.30.10.3"))
    assert not pattern.matches(_info("IT83", "83.30.10.5"))
    assert not pattern.matches(_info("IT83", "83.30.11.4"))


# --- Cross-pattern non-overlap checks -------------------------------------


def test_x916_glob_does_not_match_x915s_or_it83() -> None:
    """Production patterns are non-overlapping by construction."""
    x916 = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert not x916.matches(_info("X915S", "2915.30.10.114"))
    assert not x916.matches(_info("IT83", "83.30.10.4"))


def test_it83_exact_does_not_match_x916_or_x915s() -> None:
    """IT83's exact band cannot match the door-phone classes."""
    it83 = DeviceClassPattern(model_prefix="IT83", firmware_band="83.30.10.4")
    assert not it83.matches(_info("X916", "916.30.10.114"))
    assert not it83.matches(_info("X915S", "2915.30.10.114"))


def test_non_numeric_trailing_label_is_stripped() -> None:
    """``"916.30.10.114-beta"`` parses as ``(916, 30, 10, 114)``."""
    pattern = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert pattern.matches(_info("X916", "916.30.10.114-beta"))


def test_wholly_non_numeric_firmware_is_non_match_not_error() -> None:
    """A non-numeric firmware string returns ``False`` without raising."""
    pattern = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert pattern.matches(_info("X916", "not-a-version")) is False
