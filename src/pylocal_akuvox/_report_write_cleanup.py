# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report best-effort write-test cleanup helpers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pylocal_akuvox._report_steps import TestResults
    from pylocal_akuvox.device import AkuvoxDevice


async def _best_effort_delete(delete_coro: Callable[[], Awaitable[None]]) -> None:
    """Run a silent teardown operation and suppress cleanup failures."""
    try:
        await delete_coro()
    except asyncio.CancelledError:
        raise
    except Exception:
        return


def _step_failed(results: TestResults, label: str) -> bool:
    """Return whether a diagnostic step recorded a failure."""
    return any(failed_label == label for failed_label, _ in results.failed)


async def _cleanup_user_by_user_id(device: AkuvoxDevice, user_id: str) -> None:
    """Delete any silent-cleanup user matching a known user ID."""
    users = await device.list_users()
    for user in users:
        if user.user_id == user_id and user.id is not None:
            await device.delete_user(id=user.id)


async def _cleanup_schedule_by_name(device: AkuvoxDevice, name: str) -> None:
    """Delete any silent-cleanup schedule matching a known name."""
    schedules = await device.list_schedules()
    for sched in schedules:
        if sched.name == name and sched.id is not None:
            await device.delete_schedule(id=sched.id)


async def _cleanup_group_by_name(device: AkuvoxDevice, name: str) -> None:
    """Delete any silent-cleanup group matching a known name."""
    groups = await device.list_groups()
    for group in groups:
        if group.name == name and group.id is not None:
            await device.delete_group(id=group.id)


async def _cleanup_contact_by_name(device: AkuvoxDevice, name: str) -> None:
    """Delete any silent-cleanup contact matching a known name."""
    contacts = await device.list_contacts()
    for contact in contacts:
        if contact.name == name and contact.id is not None:
            await device.delete_contact(id=contact.id)
