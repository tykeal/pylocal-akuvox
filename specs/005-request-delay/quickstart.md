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
async with AkuvoxDevice(host="192.168.1.100", auth=auth) as device:
    # These requests will have 0.25s delay between them automatically
    users = await device.list_users()
    groups = await device.list_groups()
    contacts = await device.list_contacts()
```

## Custom Delay

```python
# Slower delay for large batch imports
async with AkuvoxDevice(
    host="192.168.1.100",
    auth=auth,
    request_delay=0.5,
) as device:
    for contact in bulk_contacts:
        await device.add_contact(name=contact.name, phone=contact.phone)
```

## Disable Delay (Backward-Compatible Behavior)

```python
# Zero delay for testing or high-performance single operations
async with AkuvoxDevice(
    host="192.168.1.100",
    auth=auth,
    request_delay=0.0,
) as device:
    info = await device.get_info()
```

## Direct HTTP Client Usage

```python
from pylocal_akuvox._http import AkuvoxHttpClient

async with AkuvoxHttpClient(
    host="192.168.1.100",
    request_delay=1.0,  # 1 second between requests
) as client:
    await client.get("/api/system/info")
    # 1.0s delay happens here (inside the lock)
    await client.get("/api/system/status")
```

## Error Handling

```python
# Delay is NOT applied when requests fail
async with AkuvoxDevice(host="192.168.1.100", auth=auth) as device:
    try:
        await device.get_info()  # If this fails, no delay
    except AkuvoxConnectionError:
        pass  # Error raised immediately, no 0.25s wait

# Invalid delay raises immediately at construction
try:
    device = AkuvoxDevice(host="192.168.1.100", request_delay=-1.0)
except ValueError as e:
    print(e)  # "request_delay must be zero or a positive number"
```
