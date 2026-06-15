<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# pylocal-akuvox

[![CI](https://github.com/tykeal/pylocal-akuvox/actions/workflows/build-test.yaml/badge.svg)](https://github.com/tykeal/pylocal-akuvox/actions/workflows/build-test.yaml)
[![Documentation](https://readthedocs.org/projects/pylocal-akuvox/badge/?version=latest)](https://pylocal-akuvox.readthedocs.io/en/latest/?badge=latest)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.13.2%2B-blue.svg)](https://www.python.org/downloads/)

Async Python library for the Akuvox local HTTP API.

**pylocal-akuvox** provides a single `AkuvoxDevice` object for
communicating with Akuvox intercoms and access controllers on the LAN.
It supports user/PIN management, relay control, schedule management,
and log retrieval over the device's local HTTP API.

## Features

- **Async-only** — designed for `asyncio` event loops and Home Assistant
- **Single runtime dependency** — only `aiohttp`
- **Full device management** — users, PINs, relays, schedules, and logs
- **Multiple auth modes** — None, Allowlist, Basic, and Digest
- **SSL support** — including self-signed certificate handling
- **Legacy TLS compatibility** — OpenSSL SECLEVEL relaxation for old devices
- **Comprehensive error handling** — typed exception hierarchy
- **Capability-aware API** — built-in device support matrix, safe probing,
  and fail-fast unsupported-operation checks

## Installation

```bash
pip install pylocal-akuvox
```

## Quick Start

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        info = await device.get_info()
        print(f"{info.model} — FW {info.firmware_version}")

asyncio.run(main())
```

## Capability-aware API

Known device classes are matched against a built-in capability matrix when
the connection opens. For unfamiliar devices, or after a firmware update, run
the safe read-only probe and then act only on confirmed capabilities:

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice, Capability, CapabilityStatus

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        capabilities = await device.probe_capabilities()

        user_add_status = capabilities.status_of(Capability.USER_ADD)
        if user_add_status is CapabilityStatus.SUPPORTED:
            await device.add_user(
                name="Alice",
                user_id="2001",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
                private_pin="1234",
            )
        else:
            print("User creation is not confirmed for this device")

asyncio.run(main())
```

The probe uses a deterministic, non-destructive read sequence. Operations
whose status is `UNSUPPORTED` always fail fast. Operations whose status is
`UNKNOWN` fail fast by default; set `device.attempt_unknown_capability = True`
only when you intentionally want to try an unproven device-side operation.
The effective profile is available as `device.capabilities` for the current
connection.

The examples below call service methods directly for brevity. They assume the
relevant capability is `SUPPORTED`; for portable code, guard each operation
with the probed or matrix profile as shown above.

### Manage Users and PINs

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.add_user(
            name="Alice",
            user_id="2001",
            web_relay="0",
            schedule_relay="1001-1",
            lift_floor_num="0",
            private_pin="1234",
        )

        users = await device.list_users()
        for user in users:
            print(f"{user.name} (ID: {user.user_id})")

asyncio.run(main())
```

### Trigger a Door Relay

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice

async def main():
    async with AkuvoxDevice("192.168.1.100") as device:
        await device.trigger_relay(num=1, delay=5)

asyncio.run(main())
```

### Authentication

```python
import asyncio
from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

async def main():
    # Basic Auth
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="secret")
    async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
        info = await device.get_info()

asyncio.run(main())
```

## Documentation

Full documentation is available at
[pylocal-akuvox.readthedocs.io](https://pylocal-akuvox.readthedocs.io/).

## Contributing

This project uses [uv](https://docs.astral.sh/uv/) for dependency
management.

```bash
# Clone and install
git clone https://github.com/tykeal/pylocal-akuvox.git
cd pylocal-akuvox
uv sync --group dev

# Run tests
uv run pytest tests/ -x -q

# Run linting
uv run ruff check src/ tests/

# Build docs locally
uv run --extra docs sphinx-build -b html docs docs/_build/html
```

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
