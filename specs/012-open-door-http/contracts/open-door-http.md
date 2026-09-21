<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: OpenDoor HTTP Relay Unlock

**Feature**: `012-open-door-http` | **Date**: 2026-06-17
**Plan**: [../plan.md](../plan.md) | **Spec**: [../spec.md](../spec.md)

This is the observable contract for the credentialed
`/fcgi/do?action=OpenDoor` unlock path. The request shape is **fixed** by
FR-001; symbol names are confirmed in planning but the observable request
contract below does not change.

## Public surface

```python
# pylocal_akuvox/relay.py
async def open_door_http(
    http: AkuvoxHttpClient,
    *,
    user: str,
    password: str,
    door_num: int = 1,
) -> None: ...


# pylocal_akuvox/device.py — AkuvoxDevice
async def open_door_http(
    self,
    *,
    user: str,
    password: str,
    door_num: int = 1,
) -> None: ...
```

- Keyword-only credential/`door_num` arguments.
- Returns `None` on success; raises a named `Akuvox*` exception on failure.
- The `AkuvoxDevice` passthrough is **not capability-gated** (FR-006): it
  delegates directly to the free function and does **not** require a prior
  `probe_capabilities()` call.
- The relay credentials are **per-call** and independent of the device's
  `AuthConfig` (FR-007). They are never stored or cached.

## Request

```text
GET /fcgi/do?action=OpenDoor&UserName=<enc>&Password=<enc>&DoorNum=<n>
```

| Parameter | Value | Notes |
|-----------|-------|-------|
| `action` | `OpenDoor` (fixed) | The only `/fcgi/do` action in scope (FR-013) |
| `UserName` | URL-encoded `user` | Dedicated Open-Relay-Via-HTTP credential |
| `Password` | URL-encoded `password` | Clear-text in URL by vendor design; **redacted** in logs |
| `DoorNum` | `door_num` (default `1`) | Vendor-documented name — **not** `relay=` (FR-014) |

- Method: `GET`. Issued via `AkuvoxHttpClient._request_raw` (raw,
  non-JSON path) — **not** the JSON-envelope `get` (FR-004).
- All values are URL-encoded exactly once; credentials are never
  string-interpolated into the path (FR-002). A `&`, `=`, `@`, space, or
  non-ASCII character in a credential cannot alter the query structure.

## Response classification

The body is **not** assumed to be JSON and is **not** routed through the
envelope parser. Success/failure is classified on HTTP status (see
[../research.md](../research.md) Decision 1):

| HTTP status | Result |
|-------------|--------|
| `2xx` | success — returns `None` |
| `401` | `AkuvoxAuthenticationError` |
| `403` and any other `4xx` | `AkuvoxRequestError` |
| `5xx` and any other non-`2xx` | `AkuvoxDeviceError` |
| transport failure (refused / DNS / timeout) | `AkuvoxConnectionError` |

A non-JSON failure body (HTML/plain text) MUST NOT surface as
`AkuvoxParseError` (FR-004). Failure exception messages carry the status
and a truncated **body** excerpt — never the request URL or credentials.

> **Forward note**: if a real IT83 is found to return `HTTP 200` with an
> error marker in the body, the classification is tightened to inspect that
> marker. The rule is isolated in one helper so this does not affect
> request construction or redaction.

## Validation (pre-request)

`door_num` is validated **before** any network request (FR-005). The
following raise `AkuvoxValidationError` and issue **zero** requests:

- `door_num < 1` (non-positive)
- `door_num` not an `int`
- `door_num` is a `bool` (`True`/`False` rejected — `bool` is an `int`
  subclass, matching `trigger_relay`'s relay-number validation)

## Logging & redaction (FR-003)

- Any log record the library emits for an OpenDoor call replaces the
  `Password` value with the `<redacted>` placeholder.
- `action`, `UserName`, and `DoorNum` remain visible for diagnosability.
- The literal password appears **zero** times in log output across all
  success and failure paths (SC-003). Redaction is unconditional (not
  gated on log level).

## Error reference

| Exception | When |
|-----------|------|
| `AkuvoxValidationError` | invalid `door_num` (pre-request) |
| `AkuvoxAuthenticationError` | HTTP `401` (wrong relay credentials / feature disabled) |
| `AkuvoxRequestError` | HTTP `403` or other `4xx` |
| `AkuvoxDeviceError` | HTTP `5xx` or other non-`2xx` |
| `AkuvoxConnectionError` | transport failure (refused / DNS / timeout) |

## Relationship to the capability-dispatch path

The capability-dispatched FCGI variant (`_fcgi_relay_trigger`, reached via
`AkuvoxDevice.trigger_relay` for `RELAY_TRIGGER_FCGI` devices) no longer
issues a credential-less OpenDoor request (FR-015). It is converted to an
actionable guard that raises and directs callers to `open_door_http`. The
`RELAY_TRIGGER_FCGI` capability and the IT83 matrix entry are retained as
informational. See [../plan.md](../plan.md) "Resolved Clarification 2".
