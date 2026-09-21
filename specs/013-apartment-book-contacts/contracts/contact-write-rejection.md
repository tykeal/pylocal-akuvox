<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Contact Write Rejection (read-only device classes)

**Feature**: `013-apartment-book-contacts` | **Date**: 2026-06-18
**Plan**: [../plan.md](../plan.md) | **Spec**: [../spec.md](../spec.md)

Observable contract for **rejecting** contact mutations on a device class
whose contact writes are unsupported (the X915S apartment-book case), plus the
HTTP-envelope translation that backs the opt-in / unrecognised-device path.

## Public surface (unchanged signatures)

```python
# pylocal_akuvox/device.py — AkuvoxDevice
async def add_contact(
    self, *, name: str, phone: str | None = None, group: str | None = None
) -> None: ...
async def modify_contact(
    self,
    *,
    id: str,
    name: str | None = None,
    phone: str | None = None,
    group: str | None = None,
) -> None: ...
async def delete_contact(self, *, id: str | list[str]) -> None: ...
```

## Primary path — capability gate (FR-005/FR-006)

Each wrapper calls `ctx.capabilities.require(Capability.CONTACT_*, …)`. On the
X915S all three contact-mutation capabilities are `UNSUPPORTED`, so the gate
raises **before any network I/O**:

| Operation | Capability | Raised |
|---|---|---|
| `add_contact` | `CONTACT_ADD` | `AkuvoxUnsupportedError` |
| `modify_contact` | `CONTACT_MODIFY` | `AkuvoxUnsupportedError` |
| `delete_contact` | `CONTACT_DELETE` | `AkuvoxUnsupportedError` |

All three raises are **uniform**:

```python
AkuvoxUnsupportedError(
    "Device class X915S does not support contact.<op>",
    capability=Capability.CONTACT_<OP>,
    device_class="X915S",
    reason="capability_missing",
)
```

- Same exception **type** and same `reason` (`capability_missing`) across all
  three (FR-006).
- **No** `AkuvoxDeviceError`, **no** bare `NotImplementedError`, **no** raw
  `"unsupport action"` string (FR-005).
- **Zero** network requests are issued (the gate fires first).
- The message names the device class and the operation; user-facing docs
  state that apartment-book contact management is out-of-band (web UI /
  provisioning), satisfying the "actionable error" requirement (FR-008).

### Matrix change (the only one permitted — FR-013)

`_X915S_CURRENT` adds:

```python
Capability.CONTACT_MODIFY: CapabilityStatus.UNSUPPORTED,
Capability.CONTACT_DELETE: CapabilityStatus.UNSUPPORTED,
```

joining the existing `CONTACT_ADD: UNSUPPORTED`. `CONTACT_LIST` stays
`SUPPORTED`; `schema_shapes["contact"]` stays `APARTMENT_BOOK`.

### Service-layer cleanup

The `APARTMENT_BOOK` → `NotImplementedError` deferral
(`_APARTMENT_BOOK_WRITE_DEFERRAL_MSG`) is **removed** from
`contacts.add_contact` / `modify_contact`, along with the now-dead
`schema_shape=` kwarg. `delete_contact` is already shape-agnostic.

## Secondary path — envelope translation (FR-007)

For a caller who opts in (`attempt_unknown_capability=True`) or an
unrecognised device class that bypasses the static `UNSUPPORTED` gate and
reaches the device, the firmware returns:

```json
{"retcode": -1, "action": "unknow", "message": "unsupport action"}
```

`_http._handle_response` translates this (and the `"unsupported action"`
variant, **case-insensitively**) to:

```python
AkuvoxUnsupportedError("unsupport action", reason="envelope_unsupported")
```

— **not** `AkuvoxDeviceError`. The existing `"Api unsupported"` envelope is
still translated (now also carrying `reason="envelope_unsupported"`).

| Envelope `message` (case-insensitive) | Result |
|---|---|
| contains `api unsupported` | `AkuvoxUnsupportedError(reason="envelope_unsupported")` |
| contains `unsupport action` | `AkuvoxUnsupportedError(reason="envelope_unsupported")` |
| contains `unsupported action` | `AkuvoxUnsupportedError(reason="envelope_unsupported")` |
| other `retcode < 0` | `AkuvoxDeviceError(message)` (unchanged) |

## Pre-flight discoverability (FR-009 — raise-only)

No new API. A caller checks support before writing via the existing surface:

```python
from pylocal_akuvox import Capability, CapabilityStatus

if device.capabilities.status_of(Capability.CONTACT_ADD) is CapabilityStatus.SUPPORTED:
    await device.add_contact(name="Alice")
# X915S -> status_of(...) is UNSUPPORTED; skip without a failed write
```

## Guarantees

- **SC-003**: each of the three mutating ops produces `AkuvoxUnsupportedError`
  in 100% of tested paths, all sharing one `reason` classification — never
  `AkuvoxDeviceError` / `NotImplementedError` / a raw `"unsupport action"`
  string.
- **SC-004**: write support is determinable before any write via
  `capabilities.status_of(...)` / `supported_set`.
- **FR-012**: no contact write against an apartment-book device silently
  attempts or cryptically fails; every entry point resolves to
  `AkuvoxUnsupportedError`.
