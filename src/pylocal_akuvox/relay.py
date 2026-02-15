# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Relay operations for Akuvox devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox.exceptions import AkuvoxValidationError

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient

_MAX_DELAY = 65535


async def trigger_relay(
    http: AkuvoxHttpClient,
    *,
    num: int,
    mode: int = 0,
    level: int = 0,
    delay: int = 0,
) -> None:
    """Trigger a relay to unlock a door or gate.

    Args:
        http: The HTTP client for device communication.
        num: Relay number (positive integer).
        mode: 0=Auto Close (default), 1=Manual.
        level: 0=NO-COM (default), 1=NC-COM.
        delay: Close delay in seconds (0-65535).

    """
    if num < 1:
        msg = "Relay number must be a positive integer"
        raise AkuvoxValidationError(msg)
    if mode not in (0, 1):
        msg = "Mode must be 0 (Auto Close) or 1 (Manual)"
        raise AkuvoxValidationError(msg)
    if level not in (0, 1):
        msg = "Level must be 0 (NO-COM) or 1 (NC-COM)"
        raise AkuvoxValidationError(msg)
    if delay < 0 or delay > _MAX_DELAY:
        msg = f"Delay must be 0-{_MAX_DELAY} seconds"
        raise AkuvoxValidationError(msg)

    payload: dict[str, Any] = {
        "num": num,
        "mode": mode,
        "level": level,
        "delay": delay,
    }
    await http.post("/api/relay/trig", data=payload)


async def get_relay_status(
    http: AkuvoxHttpClient,
) -> dict[str, Any]:
    """Retrieve current relay states from the device."""
    return await http.get("/api/relay/status")
