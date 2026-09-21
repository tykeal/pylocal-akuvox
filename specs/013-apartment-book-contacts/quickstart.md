<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: Apartment-Book Contacts (X915S)

**Feature**: `013-apartment-book-contacts` | **Date**: 2026-06-18
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

How to read apartment-book contacts, check whether contact writes are
supported, and handle the unsupported-write signal. Door-phone callers (X916 /
E18C) need **no** changes — the new fields default to `None` and behaviour is
byte-identical.

## Read apartment-book contacts (X915S)

```python
from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="secret")

async with AkuvoxDevice("192.168.0.2", auth=auth) as device:
    await device.probe_capabilities()  # selects APARTMENT_BOOK shape
    contacts = await device.list_contacts()

    for c in contacts:
        # Door-phone fields still work; apartment-book metadata is preserved:
        print(c.name, c.phone, c.apt_name, c.apt_num, c.building, c.landline)
        assert c.id is None  # X915S assigns no device ID
```

For an X915S record
`{"APTName": "1", "APTNum": "1", "Building": "", "Landline": "",
"Name": "01_monitor", "Phone": "192.168.0.10"}` you get:

```python
Contact(
    name="01_monitor",
    id=None,
    phone="192.168.0.10",
    group=None,
    apt_name="1",
    apt_num="1",
    building="",
    landline="",
)
```

Empty `building` / `landline` are preserved as `""` (the device returned the
key) — they are **not** collapsed to `None`.

## Identify an apartment-book record (no device `ID`)

Apartment-book records have no device-assigned `ID`. The library preserves the
fields but makes **no** uniqueness guarantee. Correlate records with the
`(apt_num, phone)` composite when both are populated, falling back to `name`:

```python
def record_key(c):
    if c.apt_num and c.phone:
        return ("apt", c.apt_num, c.phone)  # recommended composite
    return ("name", c.name)  # fallback


by_key = {record_key(c): c for c in contacts}
```

Two records with the same `name` but different `apt_num` / `phone` remain
distinguishable under this rule.

## Check write support before writing (raise-only, FR-009)

There is no bespoke `contacts_writable` helper — use the capability surface:

```python
from pylocal_akuvox import Capability, CapabilityStatus

writable = (
    device.capabilities.status_of(Capability.CONTACT_ADD) is CapabilityStatus.SUPPORTED
)
if writable:
    await device.add_contact(name="Alice", phone="555-0100")
else:
    # X915S: contacts are read-only over HTTP — manage via the device
    # web UI / provisioning instead.
    ...
```

## Handle the unsupported-write signal (X915S)

All three mutating operations behave **uniformly** on a read-only device
class — one exception type, one reason:

```python
from pylocal_akuvox import AkuvoxUnsupportedError

for call in (
    device.add_contact(name="Bob"),
    device.modify_contact(id="1", name="Bob"),
    device.delete_contact(id="1"),
):
    try:
        await call
    except AkuvoxUnsupportedError as exc:
        assert exc.capability is not None  # CONTACT_ADD/MODIFY/DELETE
        assert exc.device_class == "X915S"
        assert exc.reason == "capability_missing"  # uniform across all three
        # exc message names the device class + operation and points to the
        # out-of-band management channel.
```

No network request is issued — the capability gate rejects the call
in-memory before any I/O. You never see `AkuvoxDeviceError`,
`NotImplementedError`, or a raw `"unsupport action"` string.

### Opt-in / unrecognised devices

If you opt into attempting unknown capabilities and the request reaches a
device that rejects it with `{"retcode": -1, "action": "unknow",
"message": "unsupport action"}`, the library still surfaces
`AkuvoxUnsupportedError` (with `reason="envelope_unsupported"`) rather than
`AkuvoxDeviceError`.

## Device-class contact models

| Device class | Schema shape | Reads | Writes (HTTP) | Distinguishing fields |
|---|---|---|---|---|
| X916 / E18C (door phone) | door-phone | Supported | Supported | `ID`, `Name`, `Phone`, `Group` |
| X915S (apartment intercom) | apartment-book | Supported (read-only) | **Unsupported** | `Name`, `Phone`, `APTName`, `APTNum`, `Building`, `Landline` (no `ID`, no `Group`) |

Behaviour is selected by each device's capability profile
(`schema_shapes["contact"]`), so any future apartment-book device inherits the
same read preservation and write-rejection behaviour.
