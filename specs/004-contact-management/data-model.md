<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Contact Management (CRUD with Group Membership)

**Feature**: 004-contact-management
**Date**: 2026-07-22

## Entities

### Contact

Represents an address book / directory entry on an Akuvox device.
Contacts are separate from Users (who have access control credentials).
Contacts have a writable Group field, enabling group membership
management. The model has four fields, as confirmed by live device
testing (2026-07-22).

**Frozen dataclass** (`@dataclass(frozen=True, kw_only=True)`).

**Fields**:

| Field | Type | Required | API Key | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `name` | `str` | Yes | `Name` | — | Human-readable display name |
| `id` | `str \| None` | No | `ID` | `None` | Device-assigned; created |
| | | | | | as `None` |
| `phone` | `str` | No | `Phone` | `""` | Phone number; empty if unset |
| `group` | `str` | No | `Group` | `"Default"` | Group membership; writable |

**Design rationale**: `name` is listed first because it is the only
required field for creation. `id` follows as the identity field
(device-assigned). `phone` and `group` are optional with device-
consistent defaults. The `group` field defaults to `"Default"` in
`from_api_response()` to match device behavior when the field is
omitted from the response.

**Key differentiator from User**: The `group` field is writable on
contacts. On users, Group is read-only via the API. This makes
contacts the mechanism for managing group membership.

### Methods

**`from_api_response(data: dict[str, Any]) -> Contact`**

Class method. Creates a `Contact` from a single item dict in the
device API response. Raises `AkuvoxParseError` if the required
`Name` field is missing. Uses `.get()` with defaults for optional
fields.

```python
# Example input from device:
{"ID": "1", "Name": "Alice", "Phone": "555-0100", "Group": "Residents"}
# Returns:
Contact(name="Alice", id="1", phone="555-0100", group="Residents")

# Minimal input (name only):
{"Name": "Bob"}
# Returns:
Contact(name="Bob", id=None, phone="", group="Default")
```

**`to_api_payload(self) -> dict[str, str]`**

Instance method. Converts to PascalCase dict for add/set API
calls. Always includes Name. Includes ID, Phone, and Group only
when non-default (non-None for ID; always included for Phone and
Group to preserve device state during fetch-merge-write).

```python
# Contact(name="Alice", id="1", phone="555-0100", group="Residents")
# Returns:
{"ID": "1", "Name": "Alice", "Phone": "555-0100", "Group": "Residents"}

# Contact(name="Bob", id=None, phone="", group="Default")
# Returns:
{"Name": "Bob", "Phone": "", "Group": "Default"}
```

## Relationships

```text
AkuvoxDevice ──delegates──▶ contacts.list_contacts()
                            contacts.add_contact()
                            contacts.modify_contact()
                            contacts.delete_contact()
                                │
                                ▼
                          AkuvoxHttpClient
                                │
                                ▼
                     GET  /api/contact/get
                     POST /api/contact/set  (action: add|set|del)
                                │
                                ▼
                             Contact
                                │
                          references
                                │
                                ▼
                          Group (by name)
```

**Group relationship**: Contacts reference groups by name via the
`Group` field. Groups (feature 003) manage group identity (name).
The "Default" group is always present but does not appear in
`/api/group/get` results. Specifying a non-existent group name
causes the device to fall back to "Default".

## Validation Rules

### add_contact()

- `name` MUST be non-empty (FR-004). Empty or missing name raises
  `AkuvoxValidationError` before any network request.
- `phone` is optional. Omitted → not sent in payload; device defaults
  to empty string.
- `group` is optional. Omitted → not sent in payload; device defaults
  to "Default". Non-existent group → device falls back to "Default".
- Mutation envelope: `target: "contact"`, `action: "add"`.
- Endpoint: `POST /api/contact/set`.

### modify_contact()

- `id` MUST be provided (identifies the contact to modify).
- At least one of `name`, `phone`, or `group` MUST be provided
  (FR-008). If none are provided, raises `AkuvoxValidationError`
  ("at least one field to change must be provided").
- Uses **fetch-merge-write** pattern (FR-009):
  1. Call `_get_contact_by_id(http, id)` to fetch current record
  2. Merge caller-provided fields into the fetched dict
  3. POST the complete record to `/api/contact/set`
- Device requires `Name` on every set request — fetch-merge-write
  ensures it is always present.
- Non-existent ID → `AkuvoxDeviceError` (device returns `Ret: -7`).
- Mutation envelope: `target: "contact"`, `action: "set"`.
- Endpoint: `POST /api/contact/set`.

### delete_contact()

- `id` MUST be provided. Accepts `str` (single) or `list[str]`
  (batch) for batch deletion (FR-011).
- Single ID: `{"item": [{"ID": "1"}]}`
- Batch IDs: `{"item": [{"ID": "1"}, {"ID": "2"}]}`
- Non-existent ID → `AkuvoxDeviceError` (device returns negative
  retcode). Delete is NOT idempotent (unlike groups).
- Mutation envelope: `target: "contact"`, `action: "del"`.
- Endpoint: `POST /api/contact/set`.

### list_contacts()

- `page` is optional. If provided, passed as `?page=N` query
  parameter.
- Response items missing the required `Name` field raise
  `AkuvoxParseError`.
- Non-list `item` values return an empty list (defensive parsing).
- Endpoint: `GET /api/contact/get`.

## State Transitions

Contacts have a simple lifecycle:

```text
[Not Exists] ──add_contact()──▶ [Exists] ──modify_contact()──▶ [Exists (updated)]
                                    │                               │
                                    │   ◀──modify_contact()─────────┘
                                    │   (name, phone, group changes)
                                    ▼
                          delete_contact() ──▶ [Not Exists]
```

Group membership transitions (via modify_contact):

```text
Contact(group="Default") ──modify(group="Residents")──▶ Contact(group="Residents")
                                                            │
Contact(group="Staff") ◀──modify(group="Staff")─────────────┘
```

## Mutation Envelope Format

All mutation requests use the standard Akuvox envelope via
`POST /api/contact/set`:

**Add**:

```json
{
  "target": "contact",
  "action": "add",
  "data": {
    "item": [
      {"Name": "Alice", "Phone": "555-0100", "Group": "Residents"}
    ]
  }
}
```

**Set (modify)**:

```json
{
  "target": "contact",
  "action": "set",
  "data": {
    "item": [
      {"ID": "1", "Name": "Alice", "Phone": "555-0100", "Group": "Staff"}
    ]
  }
}
```

**Del (delete)**:

```json
{
  "target": "contact",
  "action": "del",
  "data": {
    "item": [
      {"ID": "1"}
    ]
  }
}
```

**Batch delete**:

```json
{
  "target": "contact",
  "action": "del",
  "data": {
    "item": [
      {"ID": "1"},
      {"ID": "2"},
      {"ID": "3"}
    ]
  }
}
```

**List response** (`GET /api/contact/get`):

```json
{
  "retcode": 0,
  "action": "get",
  "message": "OK",
  "data": {
    "num": 2,
    "item": [
      {"ID": "1", "Name": "Alice", "Phone": "555-0100",
       "Group": "Residents"},
      {"ID": "2", "Name": "Bob", "Phone": "", "Group": "Default"}
    ]
  }
}
```

**Mutation response**:

```json
{
  "retcode": 0,
  "action": "add",
  "message": "OK",
  "data": {
    "num": 1,
    "item": [
      {
        "ID": "3",
        "Name": "Charlie",
        "Phone": "555-0300",
        "Group": "Default",
        "Ret": 0
      }
    ]
  }
}
```

Per-item `Ret` codes: `0` = success. Non-zero indicates an
item-level error (reported via `retcode: -1` at envelope level).
