<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Group Management (CRUD)

**Feature**: 003-group-management
**Date**: 2026-07-21

## R1: Group API Endpoint Structure

**Decision**: Use separate endpoints per mutation action:
`POST /api/group/add`, `POST /api/group/set`, `POST /api/group/del`.
Use `GET /api/group/get` for listing.

**Rationale**: Live device testing (2026-04-24) confirmed that group
mutations use separate POST endpoints per action, unlike users and
schedules which route all mutations through a single `/api/{entity}/set`
endpoint. The mutation envelope format remains consistent:
`{"target": "group", "action": "X", "data": {"item": [{...}]}}`.

**Alternatives considered**:

- Single endpoint `/api/group/set` for all mutations (matching the
  user/schedule pattern) — rejected; live device testing confirmed
  separate endpoints.
- POST for list operations — rejected; GET is the established pattern
  for read endpoints in this library.

**Impact on implementation**: The `_mutation_body()` helper still
generates the standard envelope, but each CRUD function posts to its
own endpoint URL. This is a minor divergence from `users.py` and
`schedules.py` but does not affect the public API or facade pattern.

## R2: Group Data Model

**Decision**: Create a minimal `Group` frozen dataclass with only
`id` (str, optional) and `name` (str, required) fields.

**Rationale**: Live device testing confirmed the group API returns
only two fields per item: `ID` (string) and `Name` (string). No
additional fields (members, relays, permissions, etc.) were observed.
The model follows the existing `User` and `AccessSchedule` patterns
with `from_api_response()` and `to_api_payload()` methods.

**Field semantics**:

| API Field | Python Attr | Type | Notes |
| --- | --- | --- | --- |
| `ID` | `id` | `str \| None` | Device-assigned; `None` on creation |
| `Name` | `name` | `str` | Required; human-readable label |

**Alternatives considered**:

- Dict-based model — rejected; FR-009 requires immutable data
  structure; consistency with existing models.
- Dataclass with additional optional fields — rejected; no evidence
  from device responses to support extra fields. Can be extended
  later without breaking changes if future firmware exposes them.

## R3: Modify Without Fetch-Merge-Write

**Decision**: Send modify payloads directly without fetching the
current record first.

**Rationale**: The group model has only two fields: ID (identity,
never changes) and Name (the only mutable field). Unlike users
(11+ fields) and schedules (17+ fields) where the device requires
a complete record for set operations, group modify only needs ID +
Name. There is no risk of overwriting unspecified fields because
there are no other fields. This eliminates the
`_get_entity_by_id()` → merge → POST cycle used in `users.py`
and `schedules.py`.

**Validation**: `modify_group()` MUST require a non-empty `name`
parameter. If only an ID is provided with no name, a validation
error is raised (spec acceptance scenario US3-3: "nothing to
change"). This is simpler than the user/schedule pattern where
all fields are optional on modify.

**Alternatives considered**:

- Fetch-merge-write (matching user/schedule pattern) — rejected;
  unnecessary complexity for a 2-field model. Would add a network
  round-trip with no benefit.
- Allow name-less modify as a no-op — rejected; spec explicitly
  requires a validation error.

## R4: Delete Idempotency

**Decision**: `delete_group()` does not check whether the group
exists before deletion. No error is raised for non-existent IDs.

**Rationale**: Live device testing confirmed that deleting a
non-existent group ID returns `retcode: 0` (success). The HTTP
client interprets `retcode >= 0` as success, so no special
handling is needed. This matches the spec requirement (US4-2)
that delete is idempotent.

**Alternatives considered**:

- Pre-check existence before delete — rejected; adds unnecessary
  network round-trip; device already handles this correctly.
- Raise error on non-existent ID — rejected; contradicts live
  device behavior and spec requirement.

## R5: Error Handling for Group Operations

**Decision**: Rely on the existing `_http.py` error handling.
No new exception types needed.

**Rationale**: The HTTP client already handles:

- HTTP 401 → `AkuvoxAuthenticationError`
- HTTP 400 → `AkuvoxRequestError`
- Negative retcode → `AkuvoxDeviceError`
- "Api unsupported" → `AkuvoxUnsupportedError`
- Connection failures → `AkuvoxConnectionError`
- JSON parse errors → `AkuvoxParseError`

Device-specific error codes observed during testing:

| Scenario | retcode | Ret | Handling |
| --- | --- | --- | --- |
| Add with empty name | -1 | 14 | `AkuvoxDeviceError` via HTTP client |
| Modify non-existent ID | -1 | -4 | `AkuvoxDeviceError` via HTTP client |
| Delete non-existent ID | 0 | — | Success (idempotent) |

New client-side validations map to `AkuvoxValidationError`:

- Empty name on `add_group()` → `AkuvoxValidationError`
- Missing name on `modify_group()` → `AkuvoxValidationError`

## R6: Module Structure

**Decision**: Create `groups.py` following the `users.py` pattern.

**Rationale**: Every domain operation in the library has its own
module (`relay.py`, `users.py`, `logs.py`, `schedules.py`,
`config.py`). Each module contains pure async functions that accept
`AkuvoxHttpClient` as the first parameter. The device facade
(`device.py`) delegates to these modules via lazy imports. This
pattern provides separation of concerns and testability.

Module functions:

- `list_groups(http, *, page=None) -> list[Group]`
- `add_group(http, *, name) -> None`
- `modify_group(http, *, id, name) -> None`
- `delete_group(http, *, id) -> None`
- `_mutation_body(action, item) -> dict` (private helper)

**Alternatives considered**:

- Adding group functions to `users.py` — rejected; groups are a
  separate API domain; violates separation of concerns.
- Adding to `device.py` directly — rejected; violates the
  established delegation pattern.

## R7: Pagination Convention

**Decision**: Follow the existing `?page=N` query parameter
convention for `list_groups()`.

**Rationale**: Live device testing confirmed pagination follows
the same `?page=N` convention as users and schedules. The
`list_groups()` function accepts an optional `page` parameter
matching `list_users()` and `list_schedules()`.

**Response parsing**: Items are extracted from `data.item` array.
The `data.num` field indicates total count. If `item` is not a
list, an empty list is returned (matching the established
defensive parsing pattern).

## R8: Test Script Integration

**Decision**: Extend `examples/mvp_test.py` with group tests.

**Rationale**: The existing test script has a clear read-tests /
write-tests separation with `--write` flag control. Group read
tests (list_groups) go in `_run_read_tests()`. Group write tests
(add + delete under `--write`) go in `_run_write_tests()` with
the same pattern: add → verify in list → delete → verify removal.

**Phase 3 additions**:

- `test_list_groups()` in read section
- `test_add_group()` + `test_delete_group()` in write section
- Group validation checks in `test_validation()`
