<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Group Management (CRUD)

**Feature**: 003-group-management
**Date**: 2026-07-21

## Entities

### Group

Represents an organizational group on an Akuvox device. Groups
organize users for access control purposes. The model is minimal:
only ID and Name, as confirmed by live device testing (2026-04-24).

**Frozen dataclass** (`@dataclass(frozen=True, kw_only=True)`).

**Fields**:

| Field | Type | Required | API Key | Notes |
| --- | --- | --- | --- | --- |
| `name` | `str` | Yes | `Name` | Human-readable display name |
| `id` | `str \| None` | No | `ID` | Device-assigned; `None` on creation |

**Design rationale**: Listed `name` first because it is the only
required field for creation. `id` is optional (assigned by device
on add). This matches the `User` model pattern where required
fields precede optional ones.

### Methods

**`from_api_response(data: dict[str, Any]) -> Group`**

Class method. Creates a `Group` from a single item dict in the
device API response. Raises `AkuvoxParseError` if the required
`Name` field is missing.

```python
# Example input from device:
{"ID": "1", "Name": "Residents"}
# Returns:
Group(name="Residents", id="1")
```

**`to_api_payload(self) -> dict[str, str]`**

Instance method. Converts to PascalCase dict for add/set API
calls. Only includes non-None fields.

```python
# Group(name="Visitors", id=None)
# Returns:
{"Name": "Visitors"}

# Group(name="Visitors", id="2")
# Returns:
{"ID": "2", "Name": "Visitors"}
```

## Relationships

```text
AkuvoxDevice ──delegates──▶ groups.list_groups()
                            groups.add_group()
                            groups.modify_group()
                            groups.delete_group()
                                │
                                ▼
                          AkuvoxHttpClient
                                │
                                ▼
                     GET  /api/group/get
                     POST /api/group/add
                     POST /api/group/set
                     POST /api/group/del
                                │
                                ▼
                             Group
```

## Validation Rules

### add_group()

- `name` MUST be non-empty (FR-004). Empty or missing name raises
  `AkuvoxValidationError` before any network request.
- Device-side: empty name returns `retcode: -1`, `Ret: 14`
  (caught by HTTP client as `AkuvoxDeviceError`).

### modify_group()

- `id` MUST be provided (identifies the group to modify).
- `name` MUST be non-empty (US3-3). If no name is provided,
  raises `AkuvoxValidationError` ("nothing to change").
- No fetch-merge-write needed: only 2 fields (ID + Name), so
  the full payload is sent directly.
- Device-side: non-existent ID returns `retcode: -1`, `Ret: -4`
  (caught by HTTP client as `AkuvoxDeviceError`).

### delete_group()

- `id` MUST be provided (identifies the group to delete).
- No existence check: delete is idempotent (device returns
  `retcode: 0` for non-existent IDs).

### list_groups()

- `page` is optional. If provided, passed as `?page=N` query
  parameter.
- Response items missing the required `Name` field raise
  `AkuvoxParseError`.
- Non-list `item` values return an empty list (defensive
  parsing).

## State Transitions

Groups have no state machine. They are simple identity records:

```text
[Not Exists] ──add_group()──▶ [Exists] ──modify_group()──▶ [Exists (updated)]
                                  │
                                  ▼
                        delete_group() ──▶ [Not Exists]
```

## Mutation Envelope Format

All mutation requests use the standard Akuvox envelope:

```json
{
  "target": "group",
  "action": "<add|set|del>",
  "data": {
    "item": [
      {"Name": "Residents"}
    ]
  }
}
```

Response envelope:

```json
{
  "retcode": 0,
  "action": "<add|set|del>",
  "message": "OK",
  "data": {
    "num": 1,
    "item": [
      {"ID": "1", "Name": "Residents", "Ret": 0}
    ]
  }
}
```

Per-item `Ret` codes: `0` = success. Non-zero indicates an
item-level error (reported via `retcode: -1` at envelope level).
