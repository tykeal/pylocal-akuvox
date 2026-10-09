<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Apartment-Book Contact Read

**Feature**: `013-apartment-book-contacts` | **Date**: 2026-06-18
**Plan**: [../plan.md](../plan.md) | **Spec**: [../spec.md](../spec.md)

Observable contract for reading contacts on an **apartment-book** device
(X915S apartment intercom), and the byte-identical door-phone baseline.

## Public surface (unchanged signatures)

```python
# pylocal_akuvox/models/contacts.py — Contact (frozen, kw_only)
name: str
id: str | None = None
phone: str | None = None
group: str | None = None
apt_name: str | None = None  # NEW — source key APTName
apt_num: str | None = None  # NEW — source key APTNum
building: str | None = None  # NEW — source key Building
landline: str | None = None  # NEW — source key Landline


@classmethod
def from_api_response(
    cls,
    data: dict[str, Any],
    *,
    capabilities: DeviceCapabilities | None = None,
) -> Contact: ...


# pylocal_akuvox/device.py — AkuvoxDevice
async def list_contacts(self, *, page: int | None = None) -> list[Contact]: ...
```

`list_contacts` is capability-gated on `CONTACT_LIST` (`SUPPORTED` on X915S)
and threads `capabilities=` into each `from_api_response`.

## Request (unchanged)

```text
GET /api/contact/get[?page=<n>]
```

## Schema-shape selection

| `schema_shapes["contact"]` | Branch | Apartment-book fields |
|---|---|---|
| `DOOR_PHONE` (default / `capabilities is None`) | door-phone | all `None` |
| `APARTMENT_BOOK` (X915S) | apartment-book | populated from source |

## Parse rules

| Input condition | Behaviour |
|---|---|
| `Name` present | required; populates `name` (both shapes) |
| `Name` absent | `AkuvoxParseError` (both shapes) |
| `ID` absent (apartment-book) | **no error**; `id = None` (FR-003) |
| `Phone` / `Group` empty | coerced to `None` (`… or None`) — **unchanged** |
| `APTName`/`APTNum`/`Building`/`Landline` present, non-empty | preserved verbatim |
| `APTName`/`APTNum`/`Building`/`Landline` present, empty `""` | **preserved as `""`** (information) |
| `APTName`/`APTNum`/`Building`/`Landline` absent | `None` |
| door-phone shape | the four apartment-book fields are **never** set (default `None`) |

## Examples

**Apartment-book record (representative X915S):**

```json
{"APTName": "1", "APTNum": "1", "Building": "", "Landline": "",
 "Name": "01_monitor", "Phone": "192.168.0.10"}
```

→

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

**Apartment-book record omitting `ID`:**

```json
{"APTName": "2", "Name": "02_monitor", "Phone": "192.168.0.11"}
```

→

```python
Contact(
    name="02_monitor",
    id=None,
    phone="192.168.0.11",
    group=None,
    apt_name="2",
    apt_num=None,
    building=None,
    landline=None,
)
```

**Door-phone record (byte-identical to today, FR-004):**

```json
{"ID": "1", "Name": "Alice", "Phone": "555-0100", "Group": "Residents"}
```

→

```python
Contact(
    name="Alice",
    id="1",
    phone="555-0100",
    group="Residents",
    apt_name=None,
    apt_num=None,
    building=None,
    landline=None,
)
```

## Guarantees

- **SC-001**: 100% of the four apartment-book fields present in the source are
  preserved (zero dropped).
- **SC-002**: `list_contacts()` on an X915S returns the device's record count;
  a missing `ID` never raises.
- **SC-005**: door-phone parse output is unchanged (new fields `None`).
- **FR-010**: apartment-book records have no device `ID`; the recommended
  caller-side key is the `(apt_num, phone)` composite (fallback `name`), with
  no library-level uniqueness guarantee.
