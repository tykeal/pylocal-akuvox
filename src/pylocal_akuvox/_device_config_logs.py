# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Configuration and log helpers for :mod:`pylocal_akuvox.device`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox import config, logs
from pylocal_akuvox._capability_types import Capability

if TYPE_CHECKING:
    from pylocal_akuvox._device_runtime import _DeviceContext
    from pylocal_akuvox.models import CallLogEntry, DeviceConfig, DoorLogEntry


async def get_device_config(ctx: _DeviceContext) -> DeviceConfig:
    """Retrieve full device configuration."""
    ctx.capabilities.require(
        Capability.DEVICE_CONFIG_GET,
        allow_unknown=ctx.allow_unknown,
    )
    return await config.get_device_config(ctx.client)


async def set_device_config(ctx: _DeviceContext, settings: dict[str, str]) -> None:
    """Update device configuration settings."""
    ctx.capabilities.require(
        Capability.DEVICE_CONFIG_SET,
        allow_unknown=ctx.allow_unknown,
    )
    await config.set_device_config(ctx.client, settings)


async def get_door_logs(
    ctx: _DeviceContext,
    *,
    page: int | None = None,
) -> list[DoorLogEntry]:
    """Retrieve door access logs from the device."""
    ctx.capabilities.require(Capability.LOG_DOOR, allow_unknown=ctx.allow_unknown)
    return await logs.get_door_logs(ctx.client, page=page)


async def get_call_logs(
    ctx: _DeviceContext,
    *,
    page: int | None = None,
) -> list[CallLogEntry]:
    """Retrieve call logs from the device."""
    ctx.capabilities.require(Capability.LOG_CALL, allow_unknown=ctx.allow_unknown)
    return await logs.get_call_logs(ctx.client, page=page)
