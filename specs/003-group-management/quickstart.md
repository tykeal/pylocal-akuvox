<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: Group Management (CRUD)

**Feature**: 003-group-management
**Date**: 2026-07-21

> **Note**: The examples below use the *planned* public API for
> feature 003-group-management.
>
> - `list_groups` and the `Group` model are introduced in Phase 1.
> - `add_group`, `modify_group`, `delete_group` are introduced in
>   Phase 2.
> - Documentation and MVP test script updates in Phase 3.
>
> These APIs may not be available in the current released version
> of `pylocal_akuvox`.

## Listing Groups

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        groups = await device.list_groups()
        for group in groups:
            print(f"ID={group.id}  Name={group.name}")


asyncio.run(main())
```

## Adding a Group

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.add_group(name="Residents")


asyncio.run(main())
```

## Modifying a Group

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.modify_group(id="1", name="Updated Residents")


asyncio.run(main())
```

## Deleting a Group

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.delete_group(id="1")


asyncio.run(main())
```

## Full CRUD Workflow

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # List existing groups
        groups = await device.list_groups()
        print(f"Found {len(groups)} group(s)")

        # Create a new group
        await device.add_group(name="Contractors")

        # Find the new group's ID
        groups = await device.list_groups()
        new_group = next(g for g in groups if g.name == "Contractors")
        print(f"Created group: ID={new_group.id}")

        # Rename the group
        await device.modify_group(id=new_group.id, name="External Staff")

        # Delete the group
        await device.delete_group(id=new_group.id)


asyncio.run(main())
```

## With Authentication

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod


async def main():
    auth = AuthConfig(
        method=AuthMethod.BASIC,
        username="admin",
        password="secret",
    )
    async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
        groups = await device.list_groups()
        print(f"Found {len(groups)} group(s)")


asyncio.run(main())
```

## With SSL (Self-Signed Certificate)

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    # verify_ssl=False only for local/dev with self-signed certs;
    # use verify_ssl=True (default) for production/trusted certs.
    async with AkuvoxDevice(
        "192.168.1.100",
        use_ssl=True,
        verify_ssl=False,
    ) as device:
        groups = await device.list_groups()
        print(f"Found {len(groups)} group(s)")


asyncio.run(main())
```

## Paginated Listing

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Get page 1 of groups
        page1 = await device.list_groups(page=1)
        print(f"Page 1: {len(page1)} group(s)")


asyncio.run(main())
```

## Error Handling

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxValidationError,
)


async def main():
    try:
        async with AkuvoxDevice("192.168.1.100") as device:
            # This raises AkuvoxValidationError (empty name)
            await device.add_group(name="")
    except AkuvoxValidationError as e:
        print(f"Validation error: {e}")
    except AkuvoxDeviceError as e:
        print(f"Device error: {e}")
    except AkuvoxConnectionError as e:
        print(f"Connection error: {e}")


asyncio.run(main())
```
