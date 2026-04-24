<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Group Management (CRUD)

**Feature Branch**: `003-group-management`
**Created**: 2026-07-21
**Status**: Draft
**Input**: User description: "Add group management (CRUD) to the pylocal-akuvox
library. Groups organize users on Akuvox security devices. The HA integration
(local-akuvox) needs to expose group management to Home Assistant users."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - List Groups from a Device (Priority: P1)

A developer retrieves the list of groups configured on an Akuvox device.
This is the most fundamental operation because it allows the calling
application (e.g., a Home Assistant integration) to discover what groups
exist before performing any other group operations. The response includes
each group's identity, name, and associated attributes. Results may span
multiple pages on devices with many groups.

**Why this priority**: Reading is the prerequisite for every other group
operation. Without being able to list groups, a developer cannot display
them, verify additions, or identify groups to modify or delete.

**Independent Test**: Can be fully tested by connecting to a device and
calling the list operation. Delivers immediate value by surfacing existing
group data to the calling application.

**Acceptance Scenarios**:

1. **Given** a device with one or more groups configured, **When** the
   developer calls list groups, **Then** the library returns a collection
   of group objects with at least an ID and a name for each group.
2. **Given** a device with no groups configured, **When** the developer
   calls list groups, **Then** the library returns an empty collection
   (not an error).
3. **Given** a device with more groups than fit in a single response page,
   **When** the developer calls list groups with a page parameter, **Then**
   the library returns only the groups for that page.
4. **Given** the device returns a malformed or unexpected response, **When**
   the developer calls list groups, **Then** the library raises a parse
   error with an actionable message.

---

### User Story 2 - Add a New Group (Priority: P2)

A developer creates a new group on the Akuvox device by providing a
group name and any required group attributes. After creation, the group
appears in subsequent list results and can be assigned to users.

**Why this priority**: Creating groups is the next most important
operation after listing. A Home Assistant user managing access control
needs to define organizational groups before assigning users to them.

**Independent Test**: Can be fully tested by calling the add operation
and then verifying the new group appears in a subsequent list call.

**Acceptance Scenarios**:

1. **Given** a valid group name, **When** the developer calls add group,
   **Then** the group is created on the device and no error is raised.
2. **Given** a missing or empty group name, **When** the developer calls
   add group, **Then** the library raises a validation error before
   sending any request to the device.
3. **Given** the device rejects the add request (e.g., duplicate name or
   device capacity reached), **When** the developer calls add group,
   **Then** the library raises a device error with the device's error
   message.

---

### User Story 3 - Modify an Existing Group (Priority: P3)

A developer updates the attributes of an existing group (e.g., renaming
it or changing its associated properties). The modify operation requires
the group's internal ID and accepts the fields to be changed, merging
them with the current group record before sending to the device.

**Why this priority**: Modification is needed to maintain groups over
time (renaming, updating associations) but is less common than creation
or listing.

**Independent Test**: Can be fully tested by modifying a known group and
verifying the updated attributes appear in a subsequent list call.

**Acceptance Scenarios**:

1. **Given** a valid group ID and a new name, **When** the developer
   calls modify group, **Then** the group name is updated on the device.
2. **Given** a group ID that does not exist on the device, **When** the
   developer calls modify group, **Then** the library raises a device
   error indicating the group was not found.
3. **Given** only a group ID is provided with no name change, **When**
   the developer calls modify group, **Then** the library raises a
   validation error since there is nothing to change.

---

### User Story 4 - Delete a Group (Priority: P4)

A developer removes a group from the Akuvox device by providing the
group's internal ID. After deletion, the group no longer appears in
list results.

**Why this priority**: Deletion is a necessary lifecycle operation but
used less frequently than listing, creating, or modifying groups.

**Independent Test**: Can be fully tested by deleting a known group and
verifying it no longer appears in a subsequent list call.

**Acceptance Scenarios**:

1. **Given** a valid group ID, **When** the developer calls delete group,
   **Then** the group is removed from the device and no error is raised.
2. **Given** a group ID that does not exist on the device, **When** the
   developer calls delete group, **Then** no error is raised because the
   device treats delete as idempotent.

---

### User Story 5 - Access Groups via the Device Facade (Priority: P5)

A developer uses the high-level device facade (the main entry point for
all device interactions) to perform group operations without importing
the group module directly. The facade exposes add, list, modify, and
delete group methods that delegate to the underlying group module.

**Why this priority**: The facade is the ergonomic public API that Home
Assistant integration developers use. Without facade methods, callers
would need to manage the HTTP client directly, breaking the established
library pattern.

**Independent Test**: Can be fully tested by using only the facade
object to perform all four group CRUD operations.

**Acceptance Scenarios**:

1. **Given** an active device connection via the facade, **When** the
   developer calls any group operation through the facade, **Then** the
   operation behaves identically to calling the group module directly.
2. **Given** the facade is used as an async context manager, **When** the
   developer calls group operations, **Then** all operations are
   async-only and share the managed HTTP session.

---

### Edge Cases

- What happens when the device returns a group item missing required
  fields (e.g., no ID or no Name)? The library raises a parse error
  for the malformed item.
- What happens when page number exceeds available pages? The device
  returns an empty item list and the library returns an empty collection.
- What happens when the device returns a non-list value for the items
  field? The library returns an empty collection rather than crashing.
- What happens when modify is called with no fields to change (only the
  ID)? The library performs a read-then-write with the unchanged record
  (no-op semantically but still sends the request).
- What happens when a network error occurs mid-operation? The library
  raises a connection error (existing behavior from the HTTP client).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST provide an async function to list all
  groups from the device, returning a collection of group model objects.
- **FR-002**: The list groups function MUST accept an optional page
  parameter for paginated retrieval.
- **FR-003**: The library MUST provide an async function to add a new
  group to the device, accepting group attributes as named parameters.
- **FR-004**: The add group function MUST validate that a group name is
  provided before sending the request to the device.
- **FR-005**: The library MUST provide an async function to modify an
  existing group on the device, identified by internal ID.
- **FR-006**: The modify group function MUST accept the group's internal
  ID and a new name. Since the group model has only ID and Name, no
  fetch-merge-write cycle is needed (unlike user modification).
- **FR-007**: The library MUST provide an async function to delete a
  group from the device, identified by internal ID.
- **FR-008**: All group mutation requests (add, modify, delete) MUST use
  the standard Akuvox envelope format with `target` set to `"group"` and
  the appropriate `action` value.
- **FR-009**: The group model MUST be an immutable data structure with a
  factory method to create instances from device API responses and a
  method to convert instances to device API payloads.
- **FR-010**: The device facade MUST expose add, list, modify, and
  delete group methods that delegate to the group operations module.
- **FR-011**: All group operations MUST be async-only, consistent with
  the existing library patterns.
- **FR-012**: The group model MUST be exported from the library's public
  API surface (the package's top-level namespace).
- **FR-013**: Group API responses MUST be parsed from the standard
  Akuvox response envelope, extracting items from the `data.item` array.
- **FR-014**: Malformed or missing required fields in group API responses
  MUST raise a parse error with an actionable message identifying the
  missing field.

### Key Entities

- **Group**: Represents an organizational group on the Akuvox device.
  Key attributes (verified via live device testing):
  - **ID** (string, optional on creation): Device-assigned internal
    identifier. Required for modify and delete operations.
  - **Name** (string, required): Human-readable display name for the
    group.
  - No additional fields were observed in device responses. The model
    should remain minimal (ID + Name) and can be extended with optional
    attributes if future firmware versions expose additional fields.

## Assumptions (Verified via Live Device Testing)

The following assumptions have been verified against a live Akuvox
device (firmware tested 2026-04-24):

- The group API uses separate endpoints: `GET /api/group/get` for
  retrieval, and `POST /api/group/{add,set,del}` for mutations.
- The list endpoint returns `{"data": {"num": N, "item": [...]}}`.
- Mutation requests use the standard envelope:
  `{"target": "group", "action": "X", "data": {"item": [{...}]}}`.
- Mutation responses include per-item `Ret` codes (0 = success).
- **Group model is minimal**: only `ID` (str) and `Name` (str).
  No additional fields (members, relays, permissions) were observed
  in device responses. Additional fields will be supported as
  optional attributes if discovered in other firmware versions.
- Group Name is the only required field for creation. The device
  assigns the ID automatically.
- Empty name on add returns `retcode: -1` with `Ret: 14`.
- Modify non-existent ID returns `retcode: -1` with `Ret: -4`.
- **Delete is idempotent**: deleting a non-existent ID returns
  `retcode: 0` (success), not an error.
- Pagination follows the same `?page=N` convention as users and
  schedules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can list, add, modify, and delete groups on an
  Akuvox device using no more than 3 lines of code per operation
  (excluding imports and connection setup), matching the ergonomic bar
  set by user management.
- **SC-002**: All four group CRUD operations follow the identical code
  patterns as the existing user CRUD operations — a developer familiar
  with user management can use group management without consulting
  additional documentation.
- **SC-003**: 100% of group model fields are type-annotated and the
  model is immutable, consistent with all other models in the library.
- **SC-004**: All error conditions (validation failures, device errors,
  parse errors) produce named exceptions with messages that identify the
  specific problem, with zero raw error codes exposed to the caller.
- **SC-005**: The group model is discoverable through the library's
  public API surface (importable from the top-level package namespace).
- **SC-006**: Group operations complete within the same latency envelope
  as equivalent user operations (governed by device response time and the
  configured timeout).
