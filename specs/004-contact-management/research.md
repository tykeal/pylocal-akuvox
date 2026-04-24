<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Contact Management (CRUD with Group Membership)

**Feature**: 004-contact-management
**Date**: 2026-07-22

## R1: Contact API Endpoint Structure

**Decision**: Use a single mutation endpoint `/api/contact/set` with
action routing for all mutations (add, set, del). Use
`GET /api/contact/get` for listing.

**Rationale**: Live device testing (2026-07-22) confirmed that contact
mutations use the same single-endpoint pattern as users — all mutations
go through `POST /api/contact/set` with the `action` field in the
request body determining the operation. This differs from the group
management API (003), which uses separate endpoints per action. The
mutation envelope format is consistent:
`{"target": "contact", "action": "X", "data": {"item": [{...}]}}`.

**Alternatives considered**:

- Separate endpoints per action (`/api/contact/add`, `/api/contact/del`)
  matching the group pattern — rejected; live device testing confirmed
  single-endpoint routing.
- POST for list operations — rejected; GET is the established pattern
  for read endpoints.

**Impact on implementation**: The `contacts.py` module will follow the
`users.py` pattern — a single `_mutation_body()` helper generates the
envelope and all mutations POST to `/api/contact/set`. This is distinct
from `groups.py` which posts to separate URLs.

## R2: Contact Data Model

**Decision**: Create a `Contact` frozen dataclass with four fields:
`id` (str, optional), `name` (str, required), `phone` (str, optional),
and `group` (str, optional).

**Rationale**: Live device testing confirmed the contact API returns
exactly four fields per item: `ID` (string), `Name` (string), `Phone`
(string), and `Group` (string). No additional fields were observed.
The model follows the existing `User` and `Group` patterns with
`from_api_response()` and `to_api_payload()` methods.

**Field semantics**:

| API Field | Python Attr | Type | Notes |
| --- | --- | --- | --- |
| `ID` | `id` | `str \| None` | Device-assigned; `None` on creation |
| `Name` | `name` | `str` | Required; human-readable display name |
| `Phone` | `phone` | `str \| None` | Optional; `None` when unset |
| `Group` | `group` | `str \| None` | Optional; `None` when unset |

**Alternatives considered**:

- Dict-based model — rejected; FR-014 requires immutable data
  structure; consistency with existing models.
- Preserving raw device values for optional fields in the
  dataclass (for example `""` for phone or `"Default"` for
  group) — rejected; the Python model should normalize empty or
  omitted optional values to `None` in `from_api_response()`
  for a cleaner API.
- Making `group` default to `"Default"` in the dataclass —
  rejected; device-side defaults should not be hard-coded into
  the model. `from_api_response()` should normalize
  missing/empty group values to `None` rather than inventing a
  `"Default"` value defensively.

## R3: Fetch-Merge-Write for Modify

**Decision**: Implement the fetch-merge-write pattern for
`modify_contact()`, matching `modify_user()` in `users.py`.

**Rationale**: The device requires the `Name` field on every modify
(set) request. If Name is omitted, the device may reject the request
or clear the name. Since the caller may only want to change the phone
number or group, the library must:

1. Fetch the current contact record by ID
   (via `_get_contact_by_id()`)
2. Merge the caller's changes into the fetched record
3. POST the complete updated record to `/api/contact/set`

This is identical to the `modify_user()` pattern. The
`_get_contact_by_id()` helper iterates through pages of contacts to
find the one matching the given ID, raising `AkuvoxDeviceError` if
not found.

**Alternatives considered**:

- Require the caller to provide all fields on every modify — rejected;
  violates SC-001 (≤3 lines per operation) and UX consistency. Users
  would need to list-then-modify manually.
- Send only changed fields — rejected; device requires Name on every
  set request. Missing Name causes device-side errors.
- Cache contact state locally — rejected; adds complexity, staleness
  risk, and contradicts the stateless library design.

## R4: Group Field Writability

**Decision**: The `group` parameter is a first-class writable field on
both `add_contact()` and `modify_contact()`.

**Rationale**: Unlike users (where Group is read-only via the API),
contacts support writing the Group field. This is the primary mechanism
for managing group membership. Setting a contact's Group field moves
it to that group. If the specified group doesn't exist on the device,
the device silently falls back to "Default".

The library passes the group value through to the device without
validating group existence — the device handles fallback behavior.
This avoids an extra network round-trip to validate groups and matches
the documented device behavior.

**Alternatives considered**:

- Validate group existence before sending — rejected; adds unnecessary
  network round-trip; device handles fallback gracefully.
- Separate `move_contact_to_group()` method — rejected; spec requires
  group change via the standard modify call (SC-007). A separate method
  would duplicate functionality.

## R5: Delete Behavior (Non-Idempotent)

**Decision**: `delete_contact()` raises `AkuvoxDeviceError` when given
a non-existent contact ID.

**Rationale**: Unlike group deletion (which is idempotent — deleting
a non-existent group returns success), contact deletion returns a
negative retcode (`Ret: -7`) for non-existent IDs. The HTTP client
interprets negative retcodes as errors, so no special handling is
needed — the existing error path raises `AkuvoxDeviceError`.

**Batch deletion**: The spec requires supporting multiple contact IDs
per delete request. The mutation envelope supports this via the `item`
array. The library will accept a single ID (string) for simple delete
and a list of IDs for batch delete.

**Alternatives considered**:

- Make delete idempotent by catching the error — rejected; spec
  explicitly states delete raises an error for non-existent IDs
  (US4-3). Changing device semantics would be surprising.
- Separate `batch_delete_contacts()` method — rejected; a single
  `delete_contact()` accepting `id: str | list[str]` is more
  ergonomic and matches batch delete being a natural extension.

## R6: Error Handling for Contact Operations

**Decision**: Rely on the existing `_http.py` error handling.
No new exception types needed.

**Rationale**: The HTTP client already handles all error categories.
Device-specific error codes observed during testing:

| Scenario | retcode | Ret | Handling |
| --- | --- | --- | --- |
| Add with empty name | -1 | — | `AkuvoxDeviceError` via HTTP client |
| Modify non-existent ID | -1 | -7 | `AkuvoxDeviceError` via HTTP client |
| Delete non-existent ID | -1 | -7 | `AkuvoxDeviceError` via HTTP client |
| Add with non-existent group | 0 | 0 | Success; device defaults to "Default" |

New client-side validations map to `AkuvoxValidationError`:

- Empty name on `add_contact()` → `AkuvoxValidationError`
- No fields to change on `modify_contact()` → `AkuvoxValidationError`

## R7: Module Structure

**Decision**: Create `contacts.py` following the `users.py`
single-endpoint pattern.

**Rationale**: Every domain operation in the library has its own
module. The contact module follows `users.py` because it uses the
same single-endpoint action-routing pattern. Key differences from
groups.py:

- Single endpoint `/api/contact/set` for all mutations (like users)
  vs separate endpoints per action (like groups)
- `_get_contact_by_id()` private helper for fetch-merge-write
  (like `_get_user_by_id()` in users)
- Batch delete support via list[str] ID parameter

Module functions:

- `list_contacts(http, *, page=None) -> list[Contact]`
- `add_contact(http, *, name, phone=None, group=None) -> None`
- `modify_contact(http, *, id, name=None, phone=None, group=None) -> None`
- `delete_contact(http, *, id) -> None`  (id: str | list[str])
- `_get_contact_by_id(http, internal_id) -> dict` (private helper)
- `_mutation_body(action, item) -> dict` (private helper)

**Alternatives considered**:

- Adding contact functions to `users.py` — rejected; contacts are a
  separate API domain; violates separation of concerns.
- Shared base module for user/contact fetch-merge-write — rejected;
  premature abstraction. The pattern is simple (< 15 lines) and
  duplicating it is clearer than adding an abstraction layer.

## R8: Pagination Convention

**Decision**: Follow the existing `?page=N` query parameter
convention for `list_contacts()`.

**Rationale**: Live device testing confirmed pagination follows
the same `?page=N` convention as users, schedules, and groups.
The `list_contacts()` function accepts an optional `page` parameter
matching all other list functions.

**Response parsing**: Items are extracted from `data.item` array.
The `data.num` field indicates total count. If `item` is not a
list, an empty list is returned (matching the established
defensive parsing pattern).

## R9: "Default" Group Semantics

**Decision**: Document the "Default" group behavior but do not
enforce it in the library.

**Rationale**: The "Default" group is a built-in group that:

- Is always present on the device
- Does NOT appear in `/api/group/get` results
- Is the fallback group for contacts with no group or a
  non-existent group specified

The library does not need special handling for "Default":

- `add_contact()` with no group → device assigns "Default"
- `modify_contact()` with group="Default" → device accepts it
- Listing contacts in "Default" → they appear with
  `Group: "Default"` in the response

This is pure device behavior. The library passes values through.

**Alternatives considered**:

- Auto-default group to "Default" in add_contact — rejected; the
  device handles this. Setting it client-side would duplicate logic
  and might interfere if the device changes default behavior.
- Filter "Default" from results — rejected; hiding data from the
  caller is surprising and breaks transparency.

## R10: Test Script Integration

**Decision**: Extend `examples/mvp_test.py` with contact tests.

**Rationale**: The existing test script has a clear read-tests /
write-tests separation with `--write` flag control. Contact read
tests (list_contacts) go in `_run_read_tests()`. Contact write tests
(add + modify group assignment + delete under `--write`) go in
`_run_write_tests()` with the same pattern: add → verify in list →
modify → verify group change → delete → verify removal.

**Phase 3 additions**:

- `test_list_contacts()` in read section
- `test_add_contact()` + `test_modify_contact()` +
  `test_delete_contact()` in write section
- Contact validation checks in `test_validation()`
