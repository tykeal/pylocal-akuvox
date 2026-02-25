<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: Device Configuration Management

**Feature**: 002-device-config
**Date**: 2026-02-24

> **Note**: The examples below use the *planned* public API for
> feature 002-device-config.
>
> - `get_relay_config` is introduced in Phase 1.
> - `set_relay_config` is introduced in Phase 2.
> - `RelayConfig.keys()` is introduced in Phase 3.
>
> These APIs may not be available in the current released version
> of `pylocal_akuvox`.

## Reading Relay Configuration

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        config = await device.get_relay_config()
        print(f"Hold delay: {config.hold_delay_a}")
        print(f"Relay name: {config.relay_name_a}")

asyncio.run(main())
```

## Updating Relay Configuration

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.set_relay_config(
            hold_delay_a="8",
            relay_name_a="Front Door",
        )

asyncio.run(main())
```

## Discovering Available Keys

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        config = await device.get_relay_config()
        for key in config.keys():
            print(key)

asyncio.run(main())
```

## With Authentication

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

async def main():
    auth = AuthConfig(
        method=AuthMethod.BASIC,
        username="admin",
        password="secret",
    )
    async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
        config = await device.get_relay_config()
        print(config)

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
        config = await device.get_relay_config()
        print(config)

asyncio.run(main())
```

## Read-Then-Write Pattern

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        # Read current config
        config = await device.get_relay_config()
        print(f"Current hold delay: {config.hold_delay_a}")

        # Update a single setting
        await device.set_relay_config(hold_delay_a="10")

        # Verify the change
        updated = await device.get_relay_config()
        print(f"Updated hold delay: {updated.hold_delay_a}")

asyncio.run(main())
```
