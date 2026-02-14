<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Akuvox Local HTTP API Library

**Feature Branch**: `001-akuvox-http-library`
**Created**: 2026-02-13
**Status**: Draft
**Input**: User description: "Build a Python library to use the local HTTP
API of Akuvox security devices. A minimal number of libraries shall be used
and the library shall be created as a well defined Pythonic object."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect to an Akuvox Device (Priority: P1)

A developer creates a connection to an Akuvox intercom or access control
device on the local network by providing the device's IP address. The
library validates connectivity and retrieves basic device information
(model, firmware version, MAC address) to confirm the connection is
working. For MVP, the device is expected to be configured with AllowList
authentication, so no credentials are required from the caller.

**Why this priority**: Without a working connection and device identification,
no other functionality is possible. This is the foundation for all
subsequent stories.

**Independent Test**: Can be fully tested by instantiating the library
object with a device address and verifying that device information is
returned with expected fields populated.

**Acceptance Scenarios**:

1. **Given** a valid device IP on an AllowList-configured device, **When**
   the developer creates a device instance and requests device info,
   **Then** the library returns device model, firmware version, and MAC
   address.
2. **Given** an unreachable device IP, **When** the developer attempts to
   connect, **Then** the library raises a clear connection error within a
   reasonable timeout.
3. **Given** a reachable device that rejects the connection (e.g., caller
   IP not on the AllowList), **When** the developer attempts to connect,
   **Then** the library raises an authentication error distinguishable
   from a connection error.

---

### User Story 2 - Retrieve Device Status (Priority: P2)

A developer queries the current status of an Akuvox device to determine
system time, uptime, and operational health. This enables monitoring and
diagnostic use cases.

**Why this priority**: Status monitoring is essential for integration with
home automation dashboards and alerting systems. It is a read-only
operation that validates the connection layer before attempting
write operations.

**Independent Test**: Can be tested by requesting device status and
verifying the response contains expected status fields with valid values.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer requests device
   status, **Then** the library returns current system time and device
   uptime.
2. **Given** a connected device, **When** the developer requests status
   and the device returns partial data, **Then** the library returns
   available fields and indicates which fields are unavailable rather
   than raising an error.

---

### User Story 3 - Manage Local Users and PINs (Priority: P3) 🎯 MVP

A developer creates, modifies, and deletes user accounts on the Akuvox
device. This includes programming PIN codes for each user to enable
keypad-based door access. The library provides full CRUD operations for
local user records stored on the device.

**Why this priority**: Adding and removing users with PINs is the primary
MVP use case. This is the core operational goal that justifies building
the library.

**Independent Test**: Can be tested by creating a user with a PIN,
verifying the user exists, modifying the user's PIN, and then deleting
the user — confirming each operation returns the expected result.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer creates a new user
   with a name and PIN, **Then** the library confirms the user was created
   and the user appears in the device's user list.
2. **Given** an existing user on the device, **When** the developer
   modifies the user's PIN, **Then** the library confirms the update
   and the new PIN is reflected when querying the user.
3. **Given** an existing user on the device, **When** the developer
   deletes the user, **Then** the library confirms the deletion and the
   user no longer appears in the device's user list.
4. **Given** a connected device, **When** the developer attempts to
   create a user with a PIN that violates the device's PIN format
   constraints, **Then** the library raises a validation error before
   sending the request.

---

### User Story 4 - Control Door Relays (Priority: P4)

A developer triggers a relay on the Akuvox device to unlock a door or gate.
The library provides a method to activate a specific relay by number and
returns confirmation of the relay state change.

**Why this priority**: Door unlock is a common integration use case for
Akuvox devices in home automation and access control systems. It delivers
practical value but is lower priority than user/PIN management for the
MVP target.

**Independent Test**: Can be tested by activating a relay and verifying
the library returns a success confirmation without error.

**Acceptance Scenarios**:

1. **Given** a connected device instance, **When** the developer calls the
   relay activation method with a valid relay number, **Then** the library
   activates the relay and returns a success result.
2. **Given** a connected device, **When** the developer requests activation
   of a relay number that does not exist on the device, **Then** the
   library raises a descriptive error indicating the relay is invalid.
3. **Given** a device that has become unreachable after initial connection,
   **When** the developer calls the relay activation method, **Then** the
   library raises a connection error rather than silently failing.

---

### User Story 5 - Manage Access Schedules (Priority: P5)

A developer creates, modifies, and deletes access schedules on the Akuvox
device. Schedules define time-based rules that govern when users are
permitted access. The library provides full CRUD operations for
schedule records.

**Why this priority**: Schedule management enables time-based access
policies, which is a common requirement for commercial and residential
deployments. It builds on top of user management.

**Independent Test**: Can be tested by creating a schedule with time
ranges, verifying it exists, modifying the time ranges, and deleting
the schedule.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer creates a new
   schedule with time ranges, **Then** the library confirms the schedule
   was created and it appears in the device's schedule list.
2. **Given** an existing schedule, **When** the developer modifies the
   schedule's time ranges, **Then** the library confirms the update and
   changes are reflected when querying the schedule.
3. **Given** an existing schedule, **When** the developer deletes the
   schedule, **Then** the library confirms the deletion and the schedule
   no longer appears in the device's schedule list.

---

### User Story 6 - Retrieve Call and Door Logs (Priority: P6)

A developer retrieves historical call logs and door access logs from the
Akuvox device. Call logs include records of intercom calls (answered,
missed, rejected). Door logs include records of door open events
(relay activations, PIN entries, remote unlocks). The library returns
structured log entries with timestamps and event details.

**Why this priority**: Log retrieval enables auditing, reporting, and
integration with monitoring dashboards. It is a read-only operation that
depends on stable connectivity but does not require user management.

**Independent Test**: Can be tested by requesting call logs and door logs
and verifying the response contains structured entries with timestamps.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer requests call
   logs, **Then** the library returns a list of call log entries each
   containing at minimum a timestamp, call direction, and call result.
2. **Given** a connected device, **When** the developer requests door
   logs, **Then** the library returns a list of door log entries each
   containing at minimum a timestamp, access method, and result.
3. **Given** a device with no log entries, **When** the developer requests
   logs, **Then** the library returns an empty list rather than raising
   an error.

---

### User Story 7 - Support Multiple Authentication Methods (Priority: P7)

A developer configures the library to use any of the authentication
methods supported by Akuvox devices. The library selects the correct
authentication handler based on configuration. Akuvox devices support
four authentication modes:

- **None**: No validation; accepts all requests (development only)
- **AllowList**: Accepts requests from predefined IP addresses (no
  credentials sent by the caller; the device validates the source IP)
- **Basic Auth**: HTTP Basic authentication with username and password
- **Digest Auth**: HTTP Digest authentication with MD5

Token-based authentication is listed as "reserved" in the Akuvox API
documentation and is not implemented. The library MUST NOT support Token
authentication.

**Why this priority**: The initial deployment uses AllowList mode, which
requires no authentication handling by the library. Explicit Basic and
Digest auth support is needed for broader compatibility but is not
required for MVP.

**Independent Test**: Can be tested by connecting to the same device using
each authentication mode and verifying that device info is returned
successfully in each case.

**Acceptance Scenarios**:

1. **Given** a device configured for Basic authentication, **When** the
   developer creates a device instance with Basic auth credentials,
   **Then** the library authenticates successfully and returns device info.
2. **Given** a device configured for Digest authentication, **When** the
   developer creates a device instance with Digest auth credentials,
   **Then** the library authenticates successfully and returns device info.
3. **Given** a device with no authentication or AllowList mode, **When**
   the developer creates a device instance without credentials, **Then**
   the library connects successfully without sending auth headers.

---

### Edge Cases

- What happens when the device firmware version does not support a
  requested API endpoint? The library MUST raise a clear
  "unsupported operation" error rather than returning raw HTTP errors.
- How does the library handle concurrent relay activation requests?
  The library MUST serialize requests to the same device to prevent
  conflicting state on the hardware.
- What happens when the device responds with malformed or unexpected
  data? The library MUST raise a parse error with the raw response
  included for debugging rather than crashing.
- How does the library behave when the device IP resolves but the
  device is not an Akuvox unit? The library MUST detect non-Akuvox
  responses and raise a device identification error.
- What happens when creating a user with a duplicate name or PIN
  already assigned to another user? The library MUST raise a conflict
  error identifying the duplicate field.
- What happens when retrieving logs from a device that has reached
  its log storage capacity? The library MUST return available entries
  and indicate if the log has been truncated.
- What happens when creating a schedule with overlapping time ranges
  or invalid time values? The library MUST raise a validation error
  before sending the request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST provide a single primary object that
  represents a connection to one Akuvox device, accepting host address
  and optional authentication configuration at construction time.
- **FR-002**: The library MUST support the following Akuvox
  authentication modes: None (no validation), AllowList (IP-based;
  no credentials sent by the caller), HTTP Basic Auth, and HTTP
  Digest Auth. Token authentication is documented as "reserved" by
  Akuvox and MUST NOT be implemented. For MVP, AllowList mode
  (no credentials required) is the operational target.
- **FR-003**: The library MUST retrieve device information including at
  minimum: device model, firmware version, and MAC address.
- **FR-004**: The library MUST activate door relays by relay number.
- **FR-005**: The library MUST retrieve current device status including
  system time and uptime.
- **FR-006**: The library MUST raise distinct, well-named exception types
  for connection failures, authentication failures, invalid operations,
  and unexpected device responses.
- **FR-007**: The library MUST allow configurable request timeouts with
  a sensible default (assumed: 10 seconds).
- **FR-008**: The library MUST use a minimal set of third-party
  dependencies. Only libraries strictly necessary for HTTP communication
  and authentication are permitted.
- **FR-009**: The library MUST follow Pythonic conventions: context
  managers for resource lifecycle, properties for read-only attributes,
  type annotations on all public interfaces, and comprehensive
  docstrings.
- **FR-010**: The library MUST serialize concurrent requests to the same
  device to prevent conflicting hardware state.
- **FR-011**: The library MUST validate device responses and raise
  descriptive errors when the device returns unexpected data formats.
- **FR-012**: The library MUST provide an asynchronous-only interface
  using async/await patterns. Synchronous wrappers are not in scope.
  This aligns with the primary use case of Home Assistant integration
  and event-loop-based automation platforms.
- **FR-013**: The library MUST support creating, reading, modifying, and
  deleting local user accounts on the device, including programming
  and updating PIN codes for each user.
- **FR-014**: The library MUST validate PIN format constraints locally
  before sending user creation or modification requests to the device.
- **FR-015**: The library MUST support creating, reading, modifying, and
  deleting access schedules on the device, including defining time-based
  access rules.
- **FR-016**: The library MUST retrieve call logs from the device,
  returning structured entries with timestamps, call direction, and
  call result.
- **FR-017**: The library MUST retrieve door access logs from the device,
  returning structured entries with timestamps, access method, and
  result.

### Key Entities

- **Device**: Represents a single Akuvox intercom or access control unit.
  Attributes include host address, authentication configuration,
  device model, firmware version, and MAC address.
- **Relay**: Represents a controllable relay on the device. Attributes
  include relay number and current state (open/closed).
- **DeviceStatus**: Represents a point-in-time snapshot of the device's
  operational state including system time and uptime. Relay states are
  queried separately.
- **AuthConfig**: Represents the authentication configuration for a
  device connection. Attributes include authentication method (none,
  allowlist, basic, digest) and optional credentials. Token mode is
  reserved by Akuvox and not supported.
- **User**: Represents a local user account on the device. Attributes
  include user identifier, display name, and PIN code.
- **AccessSchedule**: Represents a time-based access rule on the device.
  Attributes include schedule identifier, name, time ranges, and
  associated users.
- **CallLogEntry**: Represents a single call log record. Attributes
  include timestamp, call direction (inbound/outbound), remote party
  identifier, and call result (answered/missed/rejected).
- **DoorLogEntry**: Represents a single door access log record.
  Attributes include timestamp, access method (PIN/relay/remote),
  user identifier (if available), and result (granted/denied).

### Assumptions

- The Akuvox HTTP API endpoints follow the documented patterns from
  official Akuvox HTTP API manuals (e.g., `/api/relay/trig`,
  `/api/system/info`).
- The library targets LAN-only communication; no cloud API or remote
  access is in scope.
- Default request timeout is 10 seconds, suitable for local network
  latency.
- The library does not manage low-level device configuration (e.g.,
  changing device passwords, updating firmware, network settings).
  User and schedule management via the HTTP API is in scope.
  Group management is deferred to a future feature.
- Device discovery (scanning the network for Akuvox devices) is out
  of scope for this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can connect to an Akuvox device and retrieve
  device information in under 5 lines of code (excluding imports).
- **SC-002**: All error conditions produce distinct, named exceptions
  with actionable messages — no raw HTTP status codes are exposed to
  the caller.
- **SC-003**: The library introduces no more than 2 third-party runtime
  dependencies (excluding the standard library).
- **SC-004**: 100% of public methods and classes include type annotations
  and docstrings.
- **SC-005**: The library can complete a connect-query-disconnect cycle
  in under 2 seconds on a local network.
- **SC-006**: All supported authentication methods (none, allowlist,
  basic, digest) work without requiring the developer to change their
  code beyond the initial configuration.
- **SC-007**: A developer can perform a full user CRUD cycle (create,
  read, update, delete) in under 10 lines of code (excluding imports).
- **SC-008**: Log retrieval returns structured, consistently formatted
  entries regardless of log volume — from zero entries to the device's
  maximum capacity.
- **SC-009**: A developer can unlock a door and receive confirmation
  of the action within 1 second on a local network.
- **SC-010**: A developer can perform a full schedule CRUD cycle
  (create, read, update, delete) in under 10 lines of code
  (excluding imports).
