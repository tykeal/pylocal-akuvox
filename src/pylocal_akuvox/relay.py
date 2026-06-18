# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Relay operations for Akuvox devices."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, quote_plus

from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxDeviceError,
    AkuvoxRequestError,
    AkuvoxValidationError,
)

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient

_MAX_DELAY = 65535
_LOGGER = logging.getLogger(__name__)
_OPEN_DOOR_PASSWORD_PLACEHOLDER = "<redacted>"
_OPEN_DOOR_QUERY_CREDENTIAL_RE = re.compile(
    r"(?i)(\b(?:UserName|Password)=)([^&\s\"'<>]*)",
)
_OPEN_DOOR_RESULT_RE = re.compile(
    r"""
    <input\b
    (?=[^>]*\bid\s*=\s*
        (?:"\s*hcSingleResult\s*"|'\s*hcSingleResult\s*'|hcSingleResult\b)
    )
    (?=[^>]*\bvalue\s*=\s*
        (?P<quote>["'])\s*(?P<value>[^"']*?)\s*(?P=quote)
    )
    [^>]*>
    """,
    re.IGNORECASE | re.VERBOSE,
)


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


def _validate_door_num(door_num: int) -> None:
    """Validate an OpenDoor HTTP door number before any request."""
    if isinstance(door_num, bool) or not isinstance(door_num, int) or door_num < 1:
        msg = "Door number must be a positive integer"
        raise AkuvoxValidationError(msg)


def _redacted_open_door_query(*, user: str, door_num: int) -> dict[str, Any]:
    """Return log-safe OpenDoor query parameters with the password redacted."""
    return {
        "action": "OpenDoor",
        "UserName": user,
        "Password": _OPEN_DOOR_PASSWORD_PLACEHOLDER,
        "DoorNum": door_num,
    }


def _redacted_body_excerpt(body: str, *, user: str, password: str) -> str:
    """Return a bounded body excerpt with credential spellings redacted."""
    redacted = _OPEN_DOOR_QUERY_CREDENTIAL_RE.sub(
        lambda match: f"{match.group(1)}{_OPEN_DOOR_PASSWORD_PLACEHOLDER}",
        body,
    )
    candidates = set()
    for value in (user, password):
        quoted = quote(value, safe="")
        quoted_plus = quote_plus(value, safe="")
        candidates.update(
            {
                value,
                quoted,
                quoted_plus,
                re.sub(
                    r"%[0-9A-F]{2}",
                    lambda match: match.group(0).lower(),
                    quoted,
                ),
                re.sub(
                    r"%[0-9A-F]{2}",
                    lambda match: match.group(0).lower(),
                    quoted_plus,
                ),
            },
        )
    candidates -= {""}
    for candidate in candidates:
        redacted = redacted.replace(candidate, _OPEN_DOOR_PASSWORD_PLACEHOLDER)
    single_line = (
        redacted.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
    )
    return single_line[:200]


def _open_door_http_body_result(body: str) -> str | None:
    """Return the OpenDoor body result marker when present."""
    match = _OPEN_DOOR_RESULT_RE.search(body)
    if match is None:
        return None
    return match.group("value").strip()


def _raise_for_open_door_http_status(
    status: int,
    body: str,
    *,
    user: str,
    password: str,
) -> None:
    """Raise the public OpenDoor error mapped from HTTP status and body."""
    if 200 <= status < 300:
        result = _open_door_http_body_result(body)
        if result is None:
            _LOGGER.debug(
                "OpenDoor HTTP unlock response body lacked a recognizable "
                "hcSingleResult marker; treating HTTP %s as success",
                status,
            )
            return
        if result == "0":
            return
        body_excerpt = _redacted_body_excerpt(body, user=user, password=password)
        if result == "-1":
            msg = (
                f"OpenDoor HTTP unlock authentication failed "
                f"(HTTP {status}, hcSingleResult={result}); verify the "
                f"Open Relay Via HTTP username/password configured on the "
                f"device; body={body_excerpt}"
            )
            raise AkuvoxAuthenticationError(msg)
        msg = (
            f"OpenDoor HTTP unlock failed "
            f"(HTTP {status}, hcSingleResult={result}); body={body_excerpt}"
        )
        raise AkuvoxDeviceError(msg)
    body_excerpt = _redacted_body_excerpt(body, user=user, password=password)
    if status == 401:
        msg = (
            f"Authentication required for OpenDoor HTTP unlock "
            f"(HTTP {status}); body={body_excerpt}"
        )
        raise AkuvoxAuthenticationError(msg)
    if 400 <= status < 500:
        msg = f"OpenDoor HTTP unlock rejected: HTTP {status}; body={body_excerpt}"
        raise AkuvoxRequestError(msg)
    msg = f"OpenDoor HTTP unlock failed: HTTP {status}; body={body_excerpt}"
    raise AkuvoxDeviceError(msg)


async def open_door_http(
    http: AkuvoxHttpClient,
    *,
    user: str,
    password: str,
    door_num: int = 1,
) -> None:
    """Unlock a door via the credentialed OpenDoor HTTP relay endpoint.

    Args:
        http: The HTTP client for device communication.
        user: Open Relay Via HTTP username configured on the device.
        password: Open Relay Via HTTP password. Akuvox sends this clear text
            in the URL by vendor design, so it can appear in proxy or device
            access logs outside this library.
        door_num: Door number to open; must be a positive integer.

    Returns:
        ``None`` when the device returns HTTP 2xx and either reports
        ``hcSingleResult=0`` in the HTML body or omits that firmware-specific
        marker.

    Raises:
        AkuvoxValidationError: If ``door_num`` is not a positive integer.
        AkuvoxConnectionError: If the request fails at the transport layer.
        AkuvoxAuthenticationError: If the device returns HTTP 401, or HTTP 2xx
            with ``hcSingleResult=-1`` in the body.
        AkuvoxRequestError: If the device returns another HTTP 4xx status.
        AkuvoxDeviceError: If the device returns any other non-2xx status, or
            HTTP 2xx with another non-zero ``hcSingleResult`` in the body.

    Notes:
        The device must have Phone → Relay → Open Relay Via HTTP enabled with
        matching relay-specific credentials. These credentials are supplied per
        call and are not read from or stored in
        :class:`pylocal_akuvox.AuthConfig`.

    """
    _validate_door_num(door_num)
    params: dict[str, Any] = {
        "action": "OpenDoor",
        "UserName": user,
        "Password": password,
        "DoorNum": door_num,
    }
    _LOGGER.debug(
        "OpenDoor HTTP unlock request params=%s",
        _redacted_open_door_query(user=user, door_num=door_num),
    )
    status, body = await http._request_raw(  # noqa: SLF001
        "GET",
        "/fcgi/do",
        params=params,
        allow_redirects=False,
    )
    _raise_for_open_door_http_status(status, body, user=user, password=password)


async def get_relay_status(
    http: AkuvoxHttpClient,
) -> dict[str, Any]:
    """Retrieve current relay states from the device."""
    return await http.get("/api/relay/status")
