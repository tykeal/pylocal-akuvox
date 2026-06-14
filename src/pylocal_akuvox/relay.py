# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Relay operations for Akuvox devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox.exceptions import AkuvoxValidationError

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient

_MAX_DELAY = 65535


def _validate_relay_trigger_args(
    *,
    num: int,
    mode: int,
    level: int,
    delay: int,
) -> None:
    """Shared input validation for relay-trigger arguments.

    Used by both the legacy free-function :func:`trigger_relay` (kept
    for backward compatibility with callers using
    ``AkuvoxHttpClient`` directly) and the capability-aware
    :meth:`AkuvoxDevice.trigger_relay` adapter dispatch path. Raises
    :class:`AkuvoxValidationError` on any out-of-range argument; never
    issues a network request.
    """
    # ``isinstance(x, bool)`` rejection: ``bool`` is a subclass of
    # ``int`` in Python, and silently accepting ``True``/``False``
    # would let confusing bug-prone calls like
    # ``trigger_relay(num=True)`` issue a real request with ``num=1``.
    # Reject explicitly so the caller sees the type error here.
    if isinstance(num, bool) or num < 1:
        msg = "Relay number must be a positive integer"
        raise AkuvoxValidationError(msg)
    if isinstance(mode, bool) or mode not in (0, 1):
        msg = "Mode must be 0 (Auto Close) or 1 (Manual)"
        raise AkuvoxValidationError(msg)
    if isinstance(level, bool) or level not in (0, 1):
        msg = "Level must be 0 (NO-COM) or 1 (NC-COM)"
        raise AkuvoxValidationError(msg)
    if isinstance(delay, bool) or delay < 0 or delay > _MAX_DELAY:
        msg = f"Delay must be 0-{_MAX_DELAY} seconds"
        raise AkuvoxValidationError(msg)


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
    _validate_relay_trigger_args(num=num, mode=mode, level=level, delay=delay)

    payload: dict[str, Any] = {
        "num": num,
        "mode": mode,
        "level": level,
        "delay": delay,
    }
    body: dict[str, Any] = {
        "target": "relay",
        "action": "trig",
        "data": payload,
    }
    await http.post("/api/relay/trig", data=body)


async def get_relay_status(
    http: AkuvoxHttpClient,
) -> dict[str, Any]:
    """Retrieve current relay states from the device."""
    return await http.get("/api/relay/status")
