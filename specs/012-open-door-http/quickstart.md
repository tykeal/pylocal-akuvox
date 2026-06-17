<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: OpenDoor HTTP Relay Unlock

**Feature**: `012-open-door-http` | **Date**: 2026-06-17
**Plan**: [plan.md](./plan.md) | **Contract**: [contracts/open-door-http.md](./contracts/open-door-http.md)

This quickstart shows how to trigger an unlock through Akuvox's
vendor-documented `/fcgi/do?action=OpenDoor` endpoint and how to choose
between it and the existing `/api/relay/trig` path. The code below reflects
the **planned** surface (implemented in the follow-up PR).

## Device prerequisite

Enable **Phone → Relay → Open Relay Via HTTP** in the device web UI and set
a dedicated username/password. These credentials are **separate** from the
library's general `AuthConfig` and are supplied per call.

## Unlock with OpenDoor

```python
from pylocal_akuvox import AkuvoxDevice

async with AkuvoxDevice("192.168.1.100") as device:
    # Not capability-gated: no probe required first.
    await device.open_door_http(
        user="relayuser",
        password="relaypass",
        door_num=1,          # defaults to 1
    )
    # Returns None on success; raises on failure.
```

Issued request:

```text
GET /fcgi/do?action=OpenDoor&UserName=relayuser&Password=relaypass&DoorNum=1
```

## Special characters are encoded safely

```python
await device.open_door_http(user="a b", password="p@ss &word=1")
```

Each credential is URL-encoded exactly once, so a `&`, `=`, `@`, space, or
non-ASCII character cannot split or inject extra query parameters. Debug
logs show the password as `<redacted>` while `action`, `UserName`, and
`DoorNum` stay visible.

## Handling failures

```python
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxRequestError,
    AkuvoxValidationError,
)

try:
    await device.open_door_http(user="relayuser", password="relaypass")
except AkuvoxValidationError:
    ...   # invalid door_num — no request was issued
except AkuvoxAuthenticationError:
    ...   # HTTP 401 — wrong relay credentials or feature disabled
except AkuvoxRequestError:
    ...   # HTTP 403 / other 4xx
except AkuvoxDeviceError:
    ...   # HTTP 5xx / other non-2xx
except AkuvoxConnectionError:
    ...   # transport failure (refused / DNS / timeout)
```

## Choosing the mechanism

| Use… | When |
|------|------|
| `device.trigger_relay(num=...)` (`/api/relay/trig`) | Door phones (X-series, R-series) where the JSON relay API works. Authenticated via the library's `AuthConfig`. |
| `device.open_door_http(user=..., password=...)` (`/fcgi/do?action=OpenDoor`) | Device classes where every `/api/relay/*` call returns the device's unsupported-handler envelope (e.g. the IT83 indoor monitor). Requires Open-Relay-Via-HTTP enabled with its own credentials. |

> **Security trade-off**: with OpenDoor the password travels in clear text
> in the URL (vendor design) and will appear in proxy / device access logs.
> The library redacts it from its **own** logs but cannot prevent on-the-wire
> or device-side logging. Prefer `/api/relay/trig` where it works.

> **IT83 note**: `trigger_relay()` on an IT83 raises an actionable error
> directing you to `open_door_http()` — the capability-dispatch path does
> **not** send a credential-less OpenDoor request.

## Real-hardware smoke test (optional)

`examples/mvp_test.py --write` can exercise OpenDoor once, gated behind an
explicit opt-in flag and the relay credentials:

```bash
uv run examples/mvp_test.py 192.168.1.100 --write \
    --open-door --open-door-user relayuser --open-door-pass relaypass
```

Without `--open-door` (or without credentials) the OpenDoor call is
**skipped and reported**, never treated as a failure.
