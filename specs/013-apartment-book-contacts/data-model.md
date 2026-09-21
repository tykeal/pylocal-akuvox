<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Data Model: Apartment-Book Contact Schema Support (X915S)

**Feature**: `013-apartment-book-contacts` | **Date**: 2026-06-18
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

This feature **extends** the existing `Contact` entity additively. Only the
delta from the current model is described here; the unchanged door-phone
behaviour is the baseline from feature 004.

## Entity: `Contact` (extended)

`@dataclass(frozen=True, kw_only=True)` in
`src/pylocal_akuvox/models/contacts.py`. One model serves **both** schema
shapes; the shape selects which fields are populated on read.

### Fields

| Field | Type | Required | API key | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `name` | `str` | Yes | `Name` | — | Display name. Required on **both** shapes; missing `Name` raises `AkuvoxParseError`. **Unchanged.** |
| `id` | `str \| None` | No | `ID` | `None` | Device-assigned on door-phone; **always `None`** on apartment-book (device assigns none — FR-003). **Unchanged type/semantics.** |
| `phone` | `str \| None` | No | `Phone` | `None` | Empty coerced to `None` (`data.get("Phone") or None`). **Unchanged.** |
| `group` | `str \| None` | No | `Group` | `None` | From the `Group` API key; `None` on apartment-book (no group field). **Unchanged.** |
| `apt_name` | `str \| None` | No | `APTName` | `None` | **NEW.** Apartment name. `None` on door-phone. |
| `apt_num` | `str \| None` | No | `APTNum` | `None` | **NEW.** Apartment number. `None` on door-phone. |
| `building` | `str \| None` | No | `Building` | `None` | **NEW.** Building. Empty string preserved as `""` (information). `None` on door-phone. |
| `landline` | `str \| None` | No | `Landline` | `None` | **NEW.** Landline. Empty string preserved as `""`. `None` on door-phone. |

The four new fields are appended **after** the existing ones with `None`
defaults. Because the dataclass is `kw_only`, this is backward-compatible:
existing construction, equality, and hashing are preserved, and door-phone
instances carry the new fields as `None` (FR-002/FR-004).

### Empty-as-information rule

The new apartment-book fields are populated with **uncoerced** `dict.get`:

| Source value | Parsed `building` / `landline` |
| --- | --- |
| key present, `"x"` | `"x"` |
| key present, `""` | `""` (preserved — the device returned the key) |
| key absent | `None` |

This deliberately differs from the `phone`/`group` `… or None` coercion,
which is retained unchanged. The spec's Edge Cases require an empty
apartment-book value to be preserved as information, not collapsed to `None`.

## Method: `Contact.from_api_response`

```python
@classmethod
def from_api_response(
    cls,
    data: dict[str, Any],
    *,
    capabilities: DeviceCapabilities | None = None,
) -> Contact: ...
```

Shape is selected by
`capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)` (or
`DOOR_PHONE` when `capabilities is None`). `Name` is required on both shapes.

**Door-phone branch (UNCHANGED — byte-identical):**

```python
# {"ID": "1", "Name": "Alice", "Phone": "555-0100", "Group": "Residents"}
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

**Apartment-book branch (CHANGED — now populates the four fields):**

```python
# {"APTName": "1", "APTNum": "1", "Building": "", "Landline": "",
#  "Name": "01_monitor", "Phone": "192.168.0.10"}
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

```python
# apartment-book payload omitting ID — succeeds, id is None (FR-003)
# {"APTName": "2", "Name": "02_monitor", "Phone": "192.168.0.11"}
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

## Method: `Contact.to_api_payload` (UNCHANGED)

```python
def to_api_payload(self) -> dict[str, str]: ...
```

Emits **only** `Name` (always) and `ID` / `Phone` / `Group` (when not
`None`). It is **not** extended to emit `APTName` / `APTNum` / `Building` /
`Landline`, guaranteeing no apartment-book key ever appears in a write payload
(FR-004). A `Contact` carrying apartment-book fields still yields a
door-phone-only payload.

```python
# Contact(name="01_monitor", phone="192.168.0.10", apt_name="1", apt_num="1")
# Returns (no apartment-book keys):
{"Name": "01_monitor", "Phone": "192.168.0.10"}
```

## Record identity (apartment-book) — FR-010

Apartment-book records carry **no device-assigned `ID`** and no group field
(`Group`), so
`id` is `None`. The library provides **no synthetic identity** and makes **no
uniqueness guarantee**. Documentation recommends callers correlate records by
the `(apt_num, phone)` composite when both are populated, falling back to
`name`:

| Strategy | Stability | Limitation |
| --- | --- | --- |
| `(apt_num, phone)` (recommended) | Good while both populated | Ambiguous if `phone` empty or two records share the pair |
| `name` (fallback) | Always present | Editable; not guaranteed unique |

Two records with the same `name` but different `apt_num` / `phone` are
distinguishable under the recommended composite (US4). See
[research.md](./research.md) Decision 1 for the full trade-off and rejected
options (a synthetic composite `id`; `Name` as identifier).

## Relationships

```text
AkuvoxDevice.list_contacts()  ──require(CONTACT_LIST)──▶ SUPPORTED
        │  threads capabilities=
        ▼
contacts.list_contacts(http, capabilities=…)
        ▼
Contact.from_api_response(item, capabilities=…)
        │  schema_shapes["contact"]
        ├── DOOR_PHONE      → door-phone branch (apt fields None)
        └── APARTMENT_BOOK  → apartment-book branch (apt fields populated)

AkuvoxDevice.{add,modify,delete}_contact()
        │  require(CONTACT_{ADD,MODIFY,DELETE})
        ▼
    X915S: UNSUPPORTED → AkuvoxUnsupportedError(reason="capability_missing")
                         (raised before any network I/O)
```

## State transitions

The model is immutable (frozen); there are no in-memory state transitions.
Device-side record lifecycle for apartment-book devices is **read-only over
HTTP** (no add / modify / delete), so the door-phone lifecycle diagram from
feature 004 does not apply to the apartment-book shape.
