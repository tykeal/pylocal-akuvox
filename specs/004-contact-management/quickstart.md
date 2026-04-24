<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: Contact Management (CRUD with Group Membership)

**Feature**: 004-contact-management
**Date**: 2026-07-22

> **Note**: The examples below use the *planned* public API for
> feature 004-contact-management.
>
> - `list_contacts` and the `Contact` model are introduced in Phase 1.
> - `add_contact`, `modify_contact`, `delete_contact` are introduced in
>   Phase 2.
> - Documentation and MVP test script updates in Phase 3.
>
> These APIs may not be available in the current released version
> of `pylocal_akuvox`.

## Listing Contacts

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        contacts = await device.list_contacts()
        for contact in contacts:
            print(f"ID={contact.id}  Name={contact.name}  "
                  f"Phone={contact.phone}  Group={contact.group}")

asyncio.run(main())
```

## Adding a Contact

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Name only — device assigns Default group and empty phone
        await device.add_contact(name="Alice")

        # With phone and group
        await device.add_contact(
            name="Bob",
            phone="555-0100",
            group="Residents",
        )

asyncio.run(main())
```

## Modifying a Contact

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Change name only (fetch-merge-write preserves other fields)
        await device.modify_contact(id="1", name="Alice Smith")

        # Change group (move contact between groups)
        await device.modify_contact(id="1", group="Staff")

        # Change multiple fields at once
        await device.modify_contact(
            id="1",
            phone="555-0200",
            group="Contractors",
        )

asyncio.run(main())
```

## Deleting a Contact

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Single delete
        await device.delete_contact(id="1")

        # Batch delete (multiple contacts in one request)
        await device.delete_contact(id=["2", "3", "4"])

asyncio.run(main())
```

## Managing Group Membership

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Create a contact in a specific group
        await device.add_contact(
            name="Charlie",
            phone="555-0300",
            group="Residents",
        )

        # List contacts and find Charlie
        contacts = await device.list_contacts()
        charlie = next(c for c in contacts if c.name == "Charlie")
        print(f"Charlie is in group: {charlie.group}")

        # Move Charlie to a different group
        await device.modify_contact(id=charlie.id, group="Staff")

        # Verify the move
        contacts = await device.list_contacts()
        charlie = next(c for c in contacts if c.name == "Charlie")
        print(f"Charlie is now in group: {charlie.group}")

asyncio.run(main())
```

## Full CRUD Workflow

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # List existing contacts
        contacts = await device.list_contacts()
        print(f"Found {len(contacts)} contact(s)")

        # Create a new contact
        await device.add_contact(
            name="Diana",
            phone="555-0400",
            group="Visitors",
        )

        # Find the new contact's ID
        contacts = await device.list_contacts()
        diana = next(c for c in contacts if c.name == "Diana")
        print(f"Created contact: ID={diana.id}")

        # Update the contact's phone and group
        await device.modify_contact(
            id=diana.id,
            phone="555-0401",
            group="Staff",
        )

        # Verify changes
        contacts = await device.list_contacts()
        diana = next(c for c in contacts if c.name == "Diana")
        print(f"Updated: Phone={diana.phone}, Group={diana.group}")

        # Delete the contact
        await device.delete_contact(id=diana.id)

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
        contacts = await device.list_contacts()
        print(f"Found {len(contacts)} contact(s)")

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
        contacts = await device.list_contacts()
        print(f"Found {len(contacts)} contact(s)")

asyncio.run(main())
```

## Paginated Listing

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Get page 1 of contacts
        page1 = await device.list_contacts(page=1)
        print(f"Page 1: {len(page1)} contact(s)")

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
            await device.add_contact(name="")
    except AkuvoxValidationError as e:
        print(f"Validation error: {e}")
    except AkuvoxDeviceError as e:
        print(f"Device error: {e}")
    except AkuvoxConnectionError as e:
        print(f"Connection error: {e}")

asyncio.run(main())
```
