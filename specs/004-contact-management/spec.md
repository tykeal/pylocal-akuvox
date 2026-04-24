<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Contact Management (CRUD with Group Membership)

**Feature Branch**: `004-contact-management`
**Created**: 2026-07-22
**Status**: Draft
**Input**: User description: "Add Contact CRUD operations with group membership
support to the async Python library for Akuvox security devices."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — List Contacts from a Device (Priority: P1)

A developer retrieves the list of contacts (address book entries) from an
Akuvox device. This is the foundational operation because it lets the
calling application (e.g., a Home Assistant integration) discover which
contacts exist before performing any other contact operations. The
response includes each contact's identity, name, phone number, and group
assignment. Results may span multiple pages on devices with large address
books.

**Why this priority**: Reading is the prerequisite for every other
contact operation. Without listing contacts, a developer cannot display
them, verify additions, or identify contacts to modify or delete.

**Independent Test**: Can be fully tested by connecting to a device and
calling the list operation. Delivers immediate value by surfacing
existing contact data to the calling application.

**Acceptance Scenarios**:

1. **Given** a device with one or more contacts configured, **When** the
   developer calls list contacts, **Then** the library returns a
   collection of contact objects with at least an ID, name, phone, and
   group for each contact.
2. **Given** a device with no contacts configured, **When** the developer
   calls list contacts, **Then** the library returns an empty collection
   (not an error).
3. **Given** a device with more contacts than fit in a single response
   page, **When** the developer calls list contacts with a page
   parameter, **Then** the library returns only the contacts for that
   page.
4. **Given** the device returns a malformed or unexpected response,
   **When** the developer calls list contacts, **Then** the library
   raises a parse error with an actionable message.

---

### User Story 2 — Add a New Contact (Priority: P2)

A developer creates a new contact on the Akuvox device by providing a
name and optional phone number and group assignment. The device assigns
an internal ID automatically. If no group is specified, the contact is
assigned to the built-in "Default" group. After creation, the contact
appears in subsequent list results.

**Why this priority**: Creating contacts is the next most important
operation after listing. A Home Assistant user managing a building
intercom needs to populate the address book before organizing contacts
into groups.

**Independent Test**: Can be fully tested by calling the add operation
and then verifying the new contact appears in a subsequent list call.

**Acceptance Scenarios**:

1. **Given** a valid contact name, **When** the developer calls add
   contact with only a name, **Then** the contact is created on the
   device with the "Default" group and no error is raised.
2. **Given** a valid contact name, phone number, and group name, **When**
   the developer calls add contact, **Then** the contact is created with
   the specified phone and group.
3. **Given** a missing or empty contact name, **When** the developer
   calls add contact, **Then** the library raises a validation error
   before sending any request to the device.
4. **Given** a group name that does not exist on the device, **When** the
   developer calls add contact with that group, **Then** the device
   assigns the contact to the "Default" group (device-side fallback
   behavior).
5. **Given** the device rejects the add request, **When** the developer
   calls add contact, **Then** the library raises a device error with the
   device's error message.

---

### User Story 3 — Modify an Existing Contact (Priority: P3)

A developer updates the attributes of an existing contact — including
the ability to change its group assignment. This is the key operation
for managing group membership: moving a contact between groups is done by
modifying the contact's Group field. The modify operation requires the
contact's internal ID and accepts the fields to change. Since the device
requires the Name field on every modify request, the library fetches the
current contact state and merges the caller's changes before sending the
update (fetch-merge-write pattern, matching user modification).

**Why this priority**: Modification enables ongoing management of the
address book — renaming contacts, updating phone numbers, and critically,
changing group assignments. Group membership management is a core feature
of this specification.

**Independent Test**: Can be fully tested by modifying a known contact
and verifying the updated attributes appear in a subsequent list call.

**Acceptance Scenarios**:

1. **Given** a valid contact ID and a new name, **When** the developer
   calls modify contact, **Then** the contact name is updated on the
   device.
2. **Given** a valid contact ID and a new group name, **When** the
   developer calls modify contact, **Then** the contact is moved to the
   specified group.
3. **Given** a valid contact ID, a new phone number, and a new group,
   **When** the developer calls modify contact, **Then** all specified
   fields are updated in a single operation.
4. **Given** a contact ID that does not exist on the device, **When** the
   developer calls modify contact, **Then** the library raises a device
   error indicating the contact was not found.
5. **Given** only a contact ID is provided with no fields to change,
   **When** the developer calls modify contact, **Then** the library
   raises a validation error since there is nothing to change.

---

### User Story 4 — Delete a Contact (Priority: P4)

A developer removes one or more contacts from the Akuvox device by
providing the contact's internal ID. After deletion, the contact no
longer appears in list results. The device supports batch deletion
(multiple contacts in a single request).

**Why this priority**: Deletion is a necessary lifecycle operation but
used less frequently than listing, creating, or modifying contacts.

**Independent Test**: Can be fully tested by deleting a known contact and
verifying it no longer appears in a subsequent list call.

**Acceptance Scenarios**:

1. **Given** a valid contact ID, **When** the developer calls delete
   contact, **Then** the contact is removed from the device and no error
   is raised.
2. **Given** multiple valid contact IDs, **When** the developer calls
   batch delete, **Then** all specified contacts are removed in a single
   operation.
3. **Given** a contact ID that does not exist on the device, **When** the
   developer calls delete contact, **Then** the library raises a device
   error indicating the contact was not found (unlike group delete, which
   is idempotent).

---

### User Story 5 — Access Contacts via the Device Facade (Priority: P5)

A developer uses the high-level device facade (the main entry point for
all device interactions) to perform contact operations without importing
the contact module directly. The facade exposes add, list, modify, and
delete contact methods that delegate to the underlying contact module.

**Why this priority**: The facade is the ergonomic public API that Home
Assistant integration developers use. Without facade methods, callers
would need to manage the HTTP client directly, breaking the established
library pattern.

**Independent Test**: Can be fully tested by using only the facade object
to perform all four contact CRUD operations.

**Acceptance Scenarios**:

1. **Given** an active device connection via the facade, **When** the
   developer calls any contact operation through the facade, **Then** the
   operation behaves identically to calling the contact module directly.
2. **Given** the facade is used as an async context manager, **When** the
   developer calls contact operations, **Then** all operations are
   async-only and share the managed HTTP session.

---

### Edge Cases

- What happens when the device returns a contact item missing required
  fields (e.g., no ID or no Name)? The library raises a parse error for
  the malformed item.
- What happens when the page number exceeds available pages? The device
  returns an empty item list and the library returns an empty collection.
- What happens when the device returns a non-list value for the items
  field? The library returns an empty collection rather than crashing.
- What happens when modify is called with a group that does not exist?
  The device silently falls back to "Default" group assignment. The
  library passes the group value through and documents this device
  behavior.
- What happens when a contact's phone number is empty or omitted? The
  library allows empty phone numbers (the field is optional on the
  device).
- What happens when a network error occurs mid-operation? The library
  raises a connection error (existing behavior from the HTTP client).
- What happens when batch delete includes a mix of valid and invalid IDs?
  The device processes each item independently and returns per-item
  result codes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST provide an async function to list all
  contacts from the device, returning a collection of contact model
  objects.
- **FR-002**: The list contacts function MUST accept an optional page
  parameter for paginated retrieval.
- **FR-003**: The library MUST provide an async function to add a new
  contact to the device, accepting contact attributes as named
  parameters.
- **FR-004**: The add contact function MUST validate that a contact name
  is provided before sending the request to the device.
- **FR-005**: The add contact function MUST accept an optional group name
  parameter. When omitted, the device assigns the contact to the built-in
  "Default" group.
- **FR-006**: The add contact function MUST accept an optional phone
  number parameter.
- **FR-007**: The library MUST provide an async function to modify an
  existing contact on the device, identified by internal ID.
- **FR-008**: The modify contact function MUST accept the contact's
  internal ID and optional new values for name, phone, and group. At
  least one field to change MUST be provided.
- **FR-009**: The modify contact function MUST use a fetch-merge-write
  pattern: fetch the current contact state, merge caller-provided fields,
  and send the complete updated record to the device (the device requires
  the Name field on every modify request).
- **FR-010**: The library MUST provide an async function to delete one or
  more contacts from the device, identified by internal ID.
- **FR-011**: The delete contact function MUST support batch deletion
  (multiple contact IDs in a single request).
- **FR-012**: All contact mutation requests (add, modify, delete) MUST
  use the standard Akuvox envelope format with `target` set to
  `"contact"` and the appropriate `action` value (`"add"`, `"set"`, or
  `"del"`).
- **FR-013**: All mutations MUST go through the single `/api/contact/set`
  endpoint with action routing, matching the user management pattern.
- **FR-014**: The contact model MUST be an immutable data structure with
  a factory method to create instances from device API responses and a
  method to convert instances to device API payloads.
- **FR-015**: The device facade MUST expose add, list, modify, and delete
  contact methods that delegate to the contact operations module.
- **FR-016**: All contact operations MUST be async-only, consistent with
  the existing library patterns.
- **FR-017**: The contact model MUST be exported from the library's
  public API surface (the package's top-level namespace).
- **FR-018**: Contact API responses MUST be parsed from the standard
  Akuvox response envelope, extracting items from the `data.item` array.
- **FR-019**: Malformed or missing required fields in contact API
  responses MUST raise a parse error with an actionable message
  identifying the missing field.

### Key Entities

- **Contact**: Represents an address book / directory entry on the Akuvox
  device. Contacts are separate from Users (who have access control
  credentials). Key attributes (verified via live device testing):
  - **ID** (string, device-assigned): Internal identifier assigned by the
    device on creation. Required for modify and delete operations.
  - **Name** (string, required): Human-readable display name for the
    contact.
  - **Phone** (string, optional): Phone number associated with the
    contact.
  - **Group** (string, optional): Name of the group the contact belongs
    to. Defaults to "Default" if omitted or if the specified group does
    not exist on the device. Writable on contacts (unlike users, where
    Group is read-only via the API).

- **Relationship to Groups**: Groups (feature 003) manage group identity
  (name). Contacts reference groups by name via the Group field. This
  enables organizing the address book by group and managing group
  membership by setting or changing a contact's Group field.

## Assumptions (Verified via Live Device Testing)

The following assumptions have been verified against a live Akuvox device
(firmware tested 2026-07-22):

- The contact API uses a single mutation endpoint: `GET /api/contact/get`
  for retrieval and `POST /api/contact/set` with action routing for all
  mutations (add, set, del). This matches the user management pattern,
  not the group management pattern.
- The list endpoint returns
  `{"retcode":0,"action":"get","message":"OK","data":{"num":N,"item":[...]}}`.
- Mutation requests use the standard envelope:
  `{"target":"contact","action":"X","data":{"item":[{...}]}}`.
- Mutation responses include per-item `Ret` codes (0 = success).
- **Contact model is simple**: ID (str), Name (str), Phone (str),
  Group (str). No additional fields were observed in device responses.
- Name is the only required field for creation. The device assigns the
  ID automatically.
- Phone defaults to empty string if omitted.
- Group defaults to "Default" if omitted or if the specified group does
  not exist on the device.
- "Default" is a built-in group that is always present but does not
  appear in `/api/group/get` results.
- Modify requires the Name field; the library uses fetch-merge-write to
  ensure it is always present.
- Modify with a non-existent ID returns `Ret: -7`.
- Delete supports batch operations (multiple items in the array).
- Pagination follows the same `?page=N` convention as users and
  schedules.
- Group assignment is writable on contacts (unlike users where Group is
  read-only via the API). This is the mechanism for managing group
  membership.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can list, add, modify, and delete contacts on
  an Akuvox device using no more than 3 lines of code per operation
  (excluding imports and connection setup), matching the ergonomic bar
  set by user management.
- **SC-002**: All four contact CRUD operations follow the identical code
  patterns as the existing user CRUD operations — a developer familiar
  with user management can use contact management without consulting
  additional documentation.
- **SC-003**: 100% of contact model fields are type-annotated and the
  model is immutable, consistent with all other models in the library.
- **SC-004**: All error conditions (validation failures, device errors,
  parse errors) produce named exceptions with messages that identify the
  specific problem, with zero raw error codes exposed to the caller.
- **SC-005**: The contact model is discoverable through the library's
  public API surface (importable from the top-level package namespace).
- **SC-006**: Contact operations complete within the same latency
  envelope as equivalent user operations (governed by device response
  time and the configured timeout).
- **SC-007**: A developer can change a contact's group assignment
  (managing group membership) through a single modify call, without
  needing to delete and re-create the contact.
