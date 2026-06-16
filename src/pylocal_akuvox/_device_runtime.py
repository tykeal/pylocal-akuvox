# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Runtime helpers for :class:`pylocal_akuvox.device.AkuvoxDevice`."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pylocal_akuvox._capability_matching import lookup_capabilities
from pylocal_akuvox._device_profiles import _conservative_empty_profile
from pylocal_akuvox.exceptions import AkuvoxConnectionError
from pylocal_akuvox.models import DeviceInfo, DeviceStatus

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._http import AkuvoxHttpClient


@dataclass(frozen=True, slots=True)
class _DeviceContext:
    """Runtime dependencies for device helper functions."""

    client: AkuvoxHttpClient
    capabilities: DeviceCapabilities
    allow_unknown: bool


class _DeviceRuntime(Protocol):
    """Mutable facade state required by lifecycle helpers."""

    _http: AkuvoxHttpClient
    _info: DeviceInfo | None
    _capabilities: DeviceCapabilities | None

    async def get_info(self) -> DeviceInfo:
        """Retrieve device identification data."""


def require_capabilities(
    capabilities: DeviceCapabilities | None,
) -> DeviceCapabilities:
    """Return established capabilities or raise the legacy lifecycle error."""
    if capabilities is None:
        msg = (
            "Device capabilities have not been initialised; "
            "use ``async with AkuvoxDevice(...) as device`` to "
            "enter the context manager before calling service "
            "methods"
        )
        raise AkuvoxConnectionError(msg)
    return capabilities


def make_context(
    client: AkuvoxHttpClient,
    capabilities: DeviceCapabilities | None,
    *,
    allow_unknown: bool,
) -> _DeviceContext:
    """Build the shared context used by domain helper functions."""
    return _DeviceContext(
        client=client,
        capabilities=require_capabilities(capabilities),
        allow_unknown=allow_unknown,
    )


async def enter_device(device: _DeviceRuntime) -> None:
    """Open the HTTP session and populate cached info/capabilities."""
    await device._http.__aenter__()
    try:
        info = await device.get_info()
        device._info = info
        profile = lookup_capabilities(info)
        if profile is None:
            profile = _conservative_empty_profile(info)
        device._capabilities = profile
    except BaseException:
        with contextlib.suppress(BaseException):
            await asyncio.shield(device._http.__aexit__(None, None, None))
        device._info = None
        device._capabilities = None
        raise


async def exit_device(
    device: _DeviceRuntime,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: object,
) -> None:
    """Close the HTTP session and clear cached runtime state."""
    try:
        await device._http.__aexit__(exc_type, exc_val, exc_tb)
    finally:
        device._info = None
        device._capabilities = None


async def get_info(
    client: AkuvoxHttpClient,
    cached_info: DeviceInfo | None,
) -> DeviceInfo:
    """Return cached device info or fetch it from the device."""
    if cached_info is not None:
        return cached_info
    data = await client.get("/api/system/info")
    return DeviceInfo.from_api_response(data)


async def get_status(client: AkuvoxHttpClient) -> DeviceStatus:
    """Retrieve current device status from the device."""
    data = await client.get("/api/system/status")
    return DeviceStatus.from_api_response(data)
