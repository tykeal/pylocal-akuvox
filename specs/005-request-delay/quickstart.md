<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Feature**: 005-request-delay

## Default Usage (No Code Changes Required)

After this feature is implemented, all existing code automatically benefits from the 0.25-second inter-request delay:

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice(host="192.168.1.100") as device:
        # These requests will have 0.25s delay between them automatically
        users = await device.list_users()
        groups = await device.list_groups()
        contacts = await device.list_contacts()


asyncio.run(main())
```

## Custom Delay

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

contacts = [
    ("Alice", "555-0100"),
    ("Bob", "555-0101"),
]


async def main():
    async with AkuvoxDevice(
        host="192.168.1.100",
        request_delay=0.5,
    ) as device:
        for name, phone in contacts:
            await device.add_contact(name=name, phone=phone)


asyncio.run(main())
```

## Disable Delay (Backward-Compatible Behavior)

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice(
        host="192.168.1.100",
        request_delay=0.0,
    ) as device:
        info = await device.get_info()
        print(info)


asyncio.run(main())
```

## Longer Delay for Sequential Reads

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice


async def main():
    async with AkuvoxDevice(
        host="192.168.1.100",
        request_delay=1.0,  # 1 second between requests
    ) as device:
        await device.get_info()
        # 1.0s delay happens here before the next request starts
        await device.get_status()


asyncio.run(main())
```

## Error Handling

```python
import asyncio
from pylocal_akuvox import AkuvoxConnectionError, AkuvoxDevice


async def main():
    try:
        async with AkuvoxDevice(host="192.168.1.100") as device:
            await device.get_info()  # If this fails, no delay
    except AkuvoxConnectionError:
        pass  # Error raised immediately, no 0.25s wait


asyncio.run(main())

# Invalid delay raises immediately at construction
try:
    AkuvoxDevice(host="192.168.1.100", request_delay=-1.0)
except ValueError as err:
    print(err)  # "request_delay must be zero or a positive number"
```
