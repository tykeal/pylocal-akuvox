# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report individual write and verification steps."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pylocal_akuvox._diagnostic_redaction import _display_value
from pylocal_akuvox._report_steps import (
    TestStepFailed,
    _default_emit,
    print_header,
)

if TYPE_CHECKING:
    from pylocal_akuvox.device import AkuvoxDevice

_MUTATION_SETTLE_SECS = 2
_TEST_USER_NAME = "pylocal-test"
_TEST_USER_ID = "9999"
_TEST_USER_PIN = "1234"
_TEST_SCHEDULE_NAME = "pylocal-test-sched"
_TEST_GROUP_NAME = "__test_group__"
_TEST_CONTACT_NAME = "__test_contact__"


async def test_add_user(
    device: AkuvoxDevice, *, redact_stdout: bool = False
) -> str:  # pragma: no cover  # noqa: E501
    """Test: Add a test user and return its internal ID."""
    print_header("ADD USER (/api/user/set action:add)")
    test_name = _TEST_USER_NAME
    test_user_id = _TEST_USER_ID
    test_pin = _TEST_USER_PIN

    await device.add_user(
        name=test_name,
        user_id=test_user_id,
        private_pin=test_pin,
        web_relay="0",
        schedule_relay="1001-1",
        lift_floor_num="0",
    )
    name = _display_value("Name", test_name, redact_stdout=redact_stdout)
    user_id = _display_value("UserID", test_user_id, redact_stdout=redact_stdout)
    pin = _display_value("PrivatePIN", test_pin, redact_stdout=redact_stdout)
    _default_emit(f"  Added user: {name} (UserID={user_id}, PIN={pin})")
    _default_emit("  ✓ add_user() OK")

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    # Search for the newly added user (page 1 has all items)
    users = await device.list_users()
    for user in users:
        if user.user_id == test_user_id and user.id is not None:
            _default_emit(f"  → Assigned internal ID: {user.id}")
            return user.id

    msg = "User added but internal ID not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_modify_user(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: Modify the test user's PIN."""
    print_header("MODIFY USER (/api/user/set)")
    new_pin = "5678"
    await device.modify_user(id=internal_id, private_pin=new_pin)
    pin = _display_value("PrivatePIN", new_pin, redact_stdout=redact_stdout)
    _default_emit(f"  Modified user ID={internal_id}: PIN changed to {pin}")
    _default_emit("  ✓ modify_user() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_delete_user(
    device: AkuvoxDevice, internal_id: str
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Delete the test user."""
    print_header("DELETE USER (/api/user/set action:del)")
    await device.delete_user(id=internal_id)
    _default_emit(f"  Deleted user ID={internal_id}")
    _default_emit("  ✓ delete_user() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_trigger_relay(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Trigger relay 1.

    Uses ``delay=0``. Door-phone classes route through
    ``/api/relay/trig``. IT83-class FCGI dispatch now raises an
    actionable guard because real OpenDoor unlocks require
    relay-specific credentials; use ``--open-door`` to exercise that
    credentialed path.
    """
    print_header("TRIGGER RELAY (/api/relay/trig | /fcgi/do?action=OpenDoor)")
    await device.trigger_relay(num=1)
    _default_emit("  Triggered relay 1")
    _default_emit("  ✓ trigger_relay() OK")


async def test_open_door(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    user: str,
    password: str,
    redact_stdout: bool = False,
) -> None:
    """Test: Trigger OpenDoor HTTP relay 1 with relay-specific credentials."""
    print_header("OPEN DOOR HTTP (/fcgi/do?action=OpenDoor)")
    display_user = _display_value("UserName", user, redact_stdout=redact_stdout)
    display_password = _display_value(
        "Password",
        password,
        redact_stdout=True,
    )
    _default_emit(f"  UserName: {display_user}")
    _default_emit(f"  Password: {display_password}")
    await device.open_door_http(user=user, password=password)
    _default_emit("  Triggered OpenDoor HTTP door 1")
    _default_emit("  ✓ open_door_http() OK")


async def test_add_schedule(device: AkuvoxDevice) -> str:  # pragma: no cover
    """Test: Add a test schedule and return its internal ID."""
    print_header("ADD SCHEDULE (/api/schedule/set action:add)")
    test_name = _TEST_SCHEDULE_NAME

    await device.add_schedule(
        schedule_type="1",
        name=test_name,
        week="12345",
        time_start="08:00",
        time_end="18:00",
    )
    _default_emit(f"  Added schedule: {test_name} (Weekly, Mon-Fri 08-18)")
    _default_emit("  ✓ add_schedule() OK")

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    schedules = await device.list_schedules()
    for sched in schedules:
        if sched.name == test_name and sched.id is not None:
            _default_emit(f"  → Assigned internal ID: {sched.id}")
            return sched.id

    msg = "Schedule added but internal ID not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_modify_schedule(
    device: AkuvoxDevice, internal_id: str
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Modify the test schedule."""
    print_header("MODIFY SCHEDULE (/api/schedule/set)")
    await device.modify_schedule(
        id=internal_id,
        name="pylocal-test-modified",
        time_start="09:00",
        time_end="17:00",
    )
    _default_emit(f"  Modified schedule ID={internal_id}: name + times changed")
    _default_emit("  ✓ modify_schedule() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_delete_schedule(
    device: AkuvoxDevice, internal_id: str
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Delete the test schedule."""
    print_header("DELETE SCHEDULE (/api/schedule/set action:del)")
    await device.delete_schedule(id=internal_id)
    _default_emit(f"  Deleted schedule ID={internal_id}")
    _default_emit("  ✓ delete_schedule() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_add_group(device: AkuvoxDevice) -> str:  # pragma: no cover
    """Test: Add a group and return its internal ID."""
    print_header("ADD GROUP (/api/group/add)")
    await device.add_group(name=_TEST_GROUP_NAME)
    _default_emit("  Sent add_group(name='__test_group__')")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    groups = await device.list_groups()
    for grp in groups:
        if grp.name == _TEST_GROUP_NAME and grp.id is not None:
            _default_emit(f"  ✓ add_group() OK — ID={grp.id}")
            return grp.id
    msg = "Group created but not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_delete_group(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Delete the test group."""
    print_header("DELETE GROUP (/api/group/del)")
    await device.delete_group(id=internal_id)
    _default_emit(f"  Deleted group ID={internal_id}")
    _default_emit("  ✓ delete_group() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_add_contact(device: AkuvoxDevice) -> str:  # pragma: no cover
    """Test: Add a contact and return its internal ID."""
    print_header("ADD CONTACT (/api/contact/set action:add)")
    await device.add_contact(
        name=_TEST_CONTACT_NAME,
        phone="5550000",
        group="Default",
    )
    _default_emit("  Sent add_contact(name='__test_contact__')")
    _default_emit("  ✓ add_contact() OK")

    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    contacts = await device.list_contacts()
    for c in contacts:
        if c.name == _TEST_CONTACT_NAME and c.id is not None:
            _default_emit(f"  → Assigned internal ID: {c.id}")
            return c.id
    msg = "Contact created but not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_delete_contact(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Delete the test contact."""
    print_header("DELETE CONTACT (/api/contact/set action:del)")
    await device.delete_contact(id=internal_id)
    _default_emit(f"  Deleted contact ID={internal_id}")
    _default_emit("  ✓ delete_contact() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_modify_contact(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Modify a contact's group membership."""
    print_header("MODIFY CONTACT (/api/contact/set action:set)")
    await device.modify_contact(id=internal_id, group="Default")
    _default_emit(f"  Modified contact ID={internal_id} group→Default")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    contacts = await device.list_contacts()
    for c in contacts:
        if c.id == internal_id:
            _default_emit(f"  → Group is now: {c.group}")
            break
    _default_emit("  ✓ modify_contact() OK")


async def test_verify_user_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test user was deleted."""
    print_header("VERIFY USER DELETION")
    users = await device.list_users()
    found = any(u.id == internal_id for u in users)
    if found:
        raise TestStepFailed("User still present after delete")
    _default_emit("  ✓ User successfully removed")


async def test_verify_schedule_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test schedule was deleted."""
    print_header("VERIFY SCHEDULE DELETION")
    scheds = await device.list_schedules()
    found = any(s.id == internal_id for s in scheds)
    if found:
        raise TestStepFailed("Schedule still present after delete")
    _default_emit("  ✓ Schedule successfully removed")


async def test_verify_group_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test group was deleted."""
    print_header("VERIFY GROUP DELETION")
    grps = await device.list_groups()
    found = any(g.id == internal_id for g in grps)
    if found:
        raise TestStepFailed("Group still present after delete")
    _default_emit("  ✓ Group successfully removed")


async def test_verify_contact_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test contact was deleted."""
    print_header("VERIFY CONTACT DELETION")
    contacts = await device.list_contacts()
    found = any(c.id == internal_id for c in contacts)
    if found:
        raise TestStepFailed("Contact still present after delete")
    _default_emit("  ✓ Contact successfully removed")
