# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Shared test helpers for Phase-2 capability-aware ``AkuvoxDevice``.

Phase 2 changed :meth:`pylocal_akuvox.device.AkuvoxDevice.__aenter__`
to issue ``GET /api/system/info`` and look the device up in the
curated capability matrix. Pre-Phase-2 tests typically used
``async with AkuvoxDevice(...)`` without mocking
``/api/system/info``; this module exposes
:func:`register_default_info` so those tests can mock the connect-time
call with a one-line addition inside their ``aioresponses`` block.

The default fixture maps to the X916 baseline matrix entry
(``model_prefix="X916"``, ``firmware_band="916.30.10.*"``) so every
public ``AkuvoxDevice`` capability resolves to ``SUPPORTED`` and the
existing per-method behaviour assertions continue to hold without
touching the gate logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aioresponses import aioresponses

BASE_URL = "http://192.168.1.100"

# X916 baseline payload — model "X916S" with firmware "916.30.10.114"
# both startswith("X916") and match the "916.30.10.*" glob band, so
# ``lookup_capabilities`` resolves to ``_X916_BASELINE`` (every
# operation SUPPORTED). This keeps existing gated-method tests green
# without per-test capability fiddling.
DEFAULT_INFO_PAYLOAD: dict[str, object] = {
    "retcode": 0,
    "action": "info",
    "message": "",
    "data": {
        "Status": {
            "Model": "X916S",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "916.30.10.114",
            "HardwareVersion": "1.0",
            "Uptime": "1d",
            "WebLang": 0,
        }
    },
}


def register_default_info(
    m: aioresponses,
    *,
    url: str = f"{BASE_URL}/api/system/info",
    payload: dict[str, object] | None = None,
    repeat: bool = False,
) -> None:
    """Register a default ``/api/system/info`` response on ``m``.

    Use inside an ``aioresponses`` block to satisfy
    :meth:`AkuvoxDevice.__aenter__`'s connect-time matrix lookup so
    test bodies can focus on the operation under test:

    .. code-block:: python

        with aioresponses() as m:
            register_default_info(m)
            m.get(f"{BASE_URL}/api/something", payload=...)
            async with AkuvoxDevice("192.168.1.100") as device:
                await device.something()

    Args:
        m: The active :class:`aioresponses` mock.
        url: Override the URL the mock matches (defaults to the
            standard ``http://192.168.1.100/api/system/info``).
        payload: Override the payload (defaults to
            :data:`DEFAULT_INFO_PAYLOAD`, an X916 fixture).
        repeat: If ``True``, register with ``repeat=True`` so the
            mock matches multiple ``__aenter__`` invocations in
            tests that rebuild the device.

    """
    m.get(
        url,
        payload=payload if payload is not None else DEFAULT_INFO_PAYLOAD,
        repeat=repeat,
    )


__all__ = [
    "BASE_URL",
    "DEFAULT_INFO_PAYLOAD",
    "register_default_info",
]
