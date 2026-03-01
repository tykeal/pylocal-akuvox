<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: pylocal-akuvox

## Installation

```bash
pip install pylocal-akuvox
```

## Connect and Get Device Info (SC-001: ≤5 lines)

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        info = await device.get_info()
        print(f"{info.model} — FW {info.firmware_version}")

asyncio.run(main())
```

## Manage Users and PINs (SC-007: ≤10 lines)

```python
async with AkuvoxDevice("192.168.1.100") as device:
    # Create a user with a PIN
    await device.add_user(
        name="Alice",
        user_id="2001",
        private_pin="1234",
        web_relay="0",
        schedule_relay="1001-1",
        lift_floor_num="0",
    )

    # List all users
    users = await device.list_users()
    for user in users:
        print(f"{user.name} (PIN: {user.private_pin})")

    # Update a user's PIN
    await device.modify_user(id="1", private_pin="5678")

    # Delete a user
    await device.delete_user(id="1")
```

## Trigger a Door Relay (SC-009: ≤1s confirmation)

```python
async with AkuvoxDevice("192.168.1.100") as device:
    await device.trigger_relay(num=1, delay=5)
```

## Retrieve Device Status

```python
async with AkuvoxDevice("192.168.1.100") as device:
    status = await device.get_status()
    print(f"Uptime: {status.uptime}")
```

## Manage Schedules (SC-010: ≤10 lines)

```python
async with AkuvoxDevice("192.168.1.100") as device:
    # Create a weekly schedule (Mon-Fri, 08:00-18:00)
    await device.add_schedule(
        name="Weekday Access",
        schedule_type="1",
        mon="1",
        tue="1",
        wed="1",
        thur="1",
        fri="1",
        time_start="08:00",
        time_end="18:00",
    )

    # List schedules
    schedules = await device.list_schedules()

    # Delete a schedule
    await device.delete_schedule(id="1001")
```

## Retrieve Logs

```python
async with AkuvoxDevice("192.168.1.100") as device:
    # Door access logs
    door_logs = await device.get_door_logs()
    for entry in door_logs:
        print(f"{entry.date} {entry.time}: {entry.name} — {entry.status}")

    # Call logs
    call_logs = await device.get_call_logs()
    for entry in call_logs:
        print(f"{entry.date} {entry.time}: {entry.call_type} — {entry.name}")
```

## Authentication Modes (SC-006)

```python
from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

# AllowList (default — no credentials needed)
async with AkuvoxDevice("192.168.1.100") as device:
    info = await device.get_info()

# Basic Auth
auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="secret")
async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
    info = await device.get_info()

# Digest Auth
auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="secret")
async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
    info = await device.get_info()
```

## Error Handling (SC-002)

```python
from pylocal_akuvox.exceptions import (
    AkuvoxConnectionError,
    AkuvoxAuthenticationError,
    AkuvoxValidationError,
)

try:
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.add_user(name="Bob", user_id="2002",
                              private_pin="12ab",
                              web_relay="0",
                              schedule_relay="1001-1",
                              lift_floor_num="0")
except AkuvoxConnectionError as e:
    print(f"Cannot reach device: {e}")
except AkuvoxAuthenticationError as e:
    print(f"Auth failed: {e}")
except AkuvoxValidationError as e:
    print(f"Invalid input: {e}")
```
