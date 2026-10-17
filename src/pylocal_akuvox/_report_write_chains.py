# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report per-resource write-test CRUD chains."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._capability_types import Capability
from pylocal_akuvox._report_steps import skip_step, step
from pylocal_akuvox._report_write_cleanup import (
    _best_effort_delete,
    _cleanup_contact_by_name,
    _cleanup_group_by_name,
    _cleanup_schedule_by_name,
    _cleanup_user_by_user_id,
    _step_failed,
)
from pylocal_akuvox._report_write_steps import (
    _TEST_CONTACT_NAME,
    _TEST_GROUP_NAME,
    _TEST_SCHEDULE_NAME,
    _TEST_USER_ID,
    test_add_contact,
    test_add_group,
    test_add_schedule,
    test_add_user,
    test_delete_contact,
    test_delete_group,
    test_delete_schedule,
    test_delete_user,
    test_modify_contact,
    test_modify_schedule,
    test_modify_user,
    test_verify_contact_deletion,
    test_verify_group_deletion,
    test_verify_schedule_deletion,
    test_verify_user_deletion,
)

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._report_steps import TestResults
    from pylocal_akuvox.device import AkuvoxDevice


async def _run_user_write_tests(
    device: AkuvoxDevice,
    results: TestResults,
    capabilities: DeviceCapabilities,
    *,
    redact_stdout: bool,
) -> None:
    """Run the user add / modify / delete / verify chain with cleanup."""
    internal_id: str | None = None
    user_deleted = False
    try:
        internal_id = await step(
            results=results,
            name="add_user",
            capability=Capability.USER_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_user(device, redact_stdout=redact_stdout),
        )
        if internal_id is None:
            reason = "requires internal ID from add_user"
            skip_step(results, "modify_user", reason)
            skip_step(results, "delete_user", reason)
            skip_step(results, "verify_user_deletion", reason)
        else:
            await step(
                results=results,
                name="modify_user",
                capability=Capability.USER_MODIFY,
                capabilities=capabilities,
                coro_factory=lambda: test_modify_user(
                    device, internal_id, redact_stdout=redact_stdout
                ),
            )
            await step(
                results=results,
                name="delete_user",
                capability=Capability.USER_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_user(device, internal_id),
            )
            if results.was_passed("delete_user"):
                await step(
                    results=results,
                    name="verify_user_deletion",
                    capability=Capability.USER_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_user_deletion(device, internal_id),
                )
                user_deleted = results.was_passed("verify_user_deletion")
            else:
                skip_step(
                    results,
                    "verify_user_deletion",
                    "requires delete_user to pass",
                )
    finally:
        if internal_id is not None and not user_deleted:
            await _best_effort_delete(lambda: device.delete_user(id=internal_id))
        elif internal_id is None and _step_failed(results, "add_user"):
            await _best_effort_delete(
                lambda: _cleanup_user_by_user_id(device, _TEST_USER_ID)
            )


async def _run_schedule_write_tests(
    device: AkuvoxDevice,
    results: TestResults,
    capabilities: DeviceCapabilities,
) -> None:
    """Run the schedule add / modify / delete / verify chain with cleanup."""
    sched_id: str | None = None
    schedule_deleted = False
    try:
        sched_id = await step(
            results=results,
            name="add_schedule",
            capability=Capability.SCHEDULE_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_schedule(device),
        )
        if sched_id is None:
            reason = "requires internal ID from add_schedule"
            skip_step(results, "modify_schedule", reason)
            skip_step(results, "delete_schedule", reason)
            skip_step(results, "verify_schedule_deletion", reason)
        else:
            await step(
                results=results,
                name="modify_schedule",
                capability=Capability.SCHEDULE_MODIFY,
                capabilities=capabilities,
                coro_factory=lambda: test_modify_schedule(device, sched_id),
            )
            await step(
                results=results,
                name="delete_schedule",
                capability=Capability.SCHEDULE_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_schedule(device, sched_id),
            )
            if results.was_passed("delete_schedule"):
                await step(
                    results=results,
                    name="verify_schedule_deletion",
                    capability=Capability.SCHEDULE_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_schedule_deletion(
                        device, sched_id
                    ),
                )
                schedule_deleted = results.was_passed("verify_schedule_deletion")
            else:
                skip_step(
                    results,
                    "verify_schedule_deletion",
                    "requires delete_schedule to pass",
                )
    finally:
        if sched_id is not None and not schedule_deleted:
            await _best_effort_delete(lambda: device.delete_schedule(id=sched_id))
        elif sched_id is None and _step_failed(results, "add_schedule"):
            await _best_effort_delete(
                lambda: _cleanup_schedule_by_name(device, _TEST_SCHEDULE_NAME)
            )


async def _run_group_write_tests(
    device: AkuvoxDevice,
    results: TestResults,
    capabilities: DeviceCapabilities,
) -> None:
    """Run the group add / delete / verify chain with cleanup."""
    group_id: str | None = None
    group_deleted = False
    try:
        group_id = await step(
            results=results,
            name="add_group",
            capability=Capability.GROUP_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_group(device),
        )
        if group_id is None:
            reason = "requires internal ID from add_group"
            skip_step(results, "delete_group", reason)
            skip_step(results, "verify_group_deletion", reason)
        else:
            await step(
                results=results,
                name="delete_group",
                capability=Capability.GROUP_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_group(device, group_id),
            )
            if results.was_passed("delete_group"):
                await step(
                    results=results,
                    name="verify_group_deletion",
                    capability=Capability.GROUP_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_group_deletion(device, group_id),
                )
                group_deleted = results.was_passed("verify_group_deletion")
            else:
                skip_step(
                    results,
                    "verify_group_deletion",
                    "requires delete_group to pass",
                )
    finally:
        if group_id is not None and not group_deleted:
            await _best_effort_delete(lambda: device.delete_group(id=group_id))
        elif group_id is None and _step_failed(results, "add_group"):
            await _best_effort_delete(
                lambda: _cleanup_group_by_name(device, _TEST_GROUP_NAME)
            )


async def _run_contact_write_tests(
    device: AkuvoxDevice,
    results: TestResults,
    capabilities: DeviceCapabilities,
) -> None:
    """Run the contact add / modify / delete / verify chain with cleanup."""
    contact_id: str | None = None
    contact_deleted = False
    try:
        contact_id = await step(
            results=results,
            name="add_contact",
            capability=Capability.CONTACT_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_contact(device),
        )
        if contact_id is None:
            reason = "requires internal ID from add_contact"
            skip_step(results, "modify_contact", reason)
            skip_step(results, "delete_contact", reason)
            skip_step(results, "verify_contact_deletion", reason)
        else:
            await step(
                results=results,
                name="modify_contact",
                capability=Capability.CONTACT_MODIFY,
                capabilities=capabilities,
                coro_factory=lambda: test_modify_contact(device, contact_id),
            )
            await step(
                results=results,
                name="delete_contact",
                capability=Capability.CONTACT_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_contact(device, contact_id),
            )
            if results.was_passed("delete_contact"):
                await step(
                    results=results,
                    name="verify_contact_deletion",
                    capability=Capability.CONTACT_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_contact_deletion(
                        device, contact_id
                    ),
                )
                contact_deleted = results.was_passed("verify_contact_deletion")
            else:
                skip_step(
                    results,
                    "verify_contact_deletion",
                    "requires delete_contact to pass",
                )
    finally:
        if contact_id is not None and not contact_deleted:
            await _best_effort_delete(lambda: device.delete_contact(id=contact_id))
        elif contact_id is None and _step_failed(results, "add_contact"):
            await _best_effort_delete(
                lambda: _cleanup_contact_by_name(device, _TEST_CONTACT_NAME)
            )
