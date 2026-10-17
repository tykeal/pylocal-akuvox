# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report device config set probe."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._diagnostic_redaction import _first_line
from pylocal_akuvox._report_steps import (
    TestStepFailed,
    TestStepSkipped,
    _default_emit,
    print_header,
)
from pylocal_akuvox.exceptions import (
    AkuvoxDeviceError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pylocal_akuvox.device import AkuvoxDevice
    from pylocal_akuvox.models import DeviceConfig

_CONFIG_SET_TOGGLE_KEY = "Config.DoorSetting.RELAY.HoldDelayA"
_CONFIG_SET_NOOP_KEYS = (
    # Lead with benign UI / localization / label settings, avoiding network,
    # account, server, and management-protocol config. The first four were
    # live-validated as writable by same-value no-op on an E18 (fw
    # 18.30.10.118) and are present in the R20A schema. No single key is
    # universal, so keep the try-until-accepted loop and retain R20A
    # DeviceName plus proven relay-A label/settings fallbacks.
    "Config.Settings.GENERAL.WebTitle",
    "Config.Settings.LANGUAGE.WebLang",
    "Config.Settings.LANGUAGE.Type",
    "Config.Settings.BACKLIGHT.Level",
    "Config.DoorSetting.GENERAL.DeviceName",
    "Config.DoorSetting.RELAY.NameA",
    "Config.DoorSetting.RELAY.RelayNameA",
    "Config.DoorSetting.RELAY.TriggerDelayA",
    "Config.DoorSetting.RELAY.TrigDelayA",
)
_CONFIG_SET_NOOP_REJECTION_ERRORS = (
    AkuvoxUnsupportedError,
    AkuvoxRequestError,
    AkuvoxDeviceError,
)


async def test_set_device_config(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Set and verify a device configuration value."""
    print_header("SET DEVICE CONFIG (/api/config/set)")
    cfg = await device.get_device_config()
    original = cfg.get(_CONFIG_SET_TOGGLE_KEY)
    if original is None:
        await _probe_config_set_noop(device, cfg)
        return
    await _probe_config_set_toggle_with_restore(device, original)


async def _probe_config_set_noop(device: AkuvoxDevice, cfg: DeviceConfig) -> None:
    """Exercise config.set with the first accepted same-value fallback."""
    rejections: list[tuple[str, BaseException]] = []
    saw_candidate = False

    for key, current in _iter_config_set_noop_candidates(cfg):
        saw_candidate = True
        _default_emit(
            f"  {_CONFIG_SET_TOGGLE_KEY} not present; probing {key} "
            "with unchanged value"
        )
        try:
            await device.set_device_config({key: current})
        except _CONFIG_SET_NOOP_REJECTION_ERRORS as exc:
            rejections.append((key, exc))
            _default_emit(f"  ⚠ {key} rejected: {_first_line(str(exc))}")
            continue

        _default_emit(f"  Set {key} to its current value")
        _default_emit("  ✓ No restore needed; value was unchanged")
        _default_emit("  ✓ set_device_config() OK")
        return

    if not saw_candidate:
        msg = (
            f"Config key {_CONFIG_SET_TOGGLE_KEY!r} not present and no safe "
            "fallback key available"
        )
        _default_emit(f"  ⚠ {msg}; skipping")
        raise TestStepSkipped(msg)

    msg = _format_config_set_noop_rejections(rejections)
    raise TestStepFailed(msg) from rejections[-1][1]


def _iter_config_set_noop_candidates(cfg: DeviceConfig) -> Iterator[tuple[str, str]]:
    """Yield present same-value config.set fallback candidates in probe order."""
    for key in _CONFIG_SET_NOOP_KEYS:
        current = cfg.get(key)
        if current is not None:
            yield key, current


def _format_config_set_noop_rejections(
    rejections: list[tuple[str, BaseException]],
) -> str:
    """Summarize rejected same-value config.set fallback attempts."""
    details = "; ".join(f"{key}: {_first_line(str(exc))}" for key, exc in rejections)
    return f"All safe config.set fallback candidates were rejected ({details})"


async def _probe_config_set_toggle_with_restore(
    device: AkuvoxDevice,
    original: str,
) -> None:
    """Toggle the legacy probe key and restore it afterward."""
    key = _CONFIG_SET_TOGGLE_KEY
    primary_error = False
    try:
        new_val = "7" if original != "7" else "6"
        await device.set_device_config({key: new_val})
        _default_emit(f"  Set {key} = {new_val}")
        cfg2 = await device.get_device_config()
        readback = cfg2.get(key)
        if readback == new_val:
            _default_emit(f"  ✓ Read-back confirmed: {readback}")
            _default_emit("  ✓ set_device_config() OK")
        else:
            msg = f"Read-back mismatch: {readback!r}"
            raise TestStepFailed(msg)
    except Exception:
        primary_error = True
        raise
    finally:
        try:
            await device.set_device_config({key: original})
            _default_emit(f"  Restored {key} = {original}")
        except Exception as exc:
            if not primary_error:
                raise
            _default_emit(f"  ⚠ Restore failed after earlier failure: {exc}")
