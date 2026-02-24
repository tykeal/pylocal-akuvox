<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Device Configuration Management

**Feature Branch**: `002-device-config`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "We need to add in capabilities to get
and set configuration on the Akuvox devices"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Read Relay Configuration (Priority: P1)

A developer retrieves the current relay configuration from an Akuvox
device to understand its door settings (hold delay, trigger delay,
relay name, HTTP relay access). This is the foundation for any
configuration workflow — you must read before you can decide what
to change.

**Why this priority**: Reading configuration is the safest starting
point and a prerequisite for any write operation. It delivers
immediate value for monitoring and diagnostics without risk of
altering device state.

**Independent Test**: Connect to a device, call the get relay
configuration method, and verify that known relay settings are
returned with the expected structure and values.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer requests
   relay configuration, **Then** the library returns a structured
   object containing all relay settings (hold delay, trigger delay,
   relay name, HTTP relay configuration).
2. **Given** a connected device with multiple relays, **When** the
   developer requests relay configuration, **Then** settings for
   all configured relays are returned.
3. **Given** a device that is unreachable, **When** the developer
   requests relay configuration, **Then** a connection error is
   raised within the configured timeout.

---

### User Story 2 — Update Relay Configuration (Priority: P2)

A developer modifies relay settings on an Akuvox device — for
example, changing the hold delay for a door relay or updating
the relay name. The developer provides one or more configuration
keys and their new values; the library applies them to the device.

**Why this priority**: Writing configuration enables automation
and programmatic device management, which is the core use case
for Home Assistant integration. Depends on US1 for verifying
changes.

**Independent Test**: Connect to a device, set a relay
configuration value (e.g., hold delay), then read back the
configuration and verify the new value was applied.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer sets a
   single relay configuration value, **Then** the device accepts
   the change and the library returns a success confirmation.
2. **Given** a connected device, **When** the developer sets
   multiple relay configuration values in one call, **Then** all
   values are applied and confirmed.
3. **Given** a connected device, **When** the developer sets a
   configuration key to an invalid value, **Then** the device
   returns an error and the library raises an appropriate
   exception.
4. **Given** a connected device, **When** the developer sets a
   configuration key that does not exist, **Then** the library
   raises a validation or device error.

---

### User Story 3 — Discover Available Configuration Keys (Priority: P3)

A developer wants to understand what configuration keys are
available on a particular device. Since different Akuvox models
may support different settings, the developer retrieves the
current configuration and inspects the available keys rather than
guessing or hard-coding key names.

**Why this priority**: Discoverability improves developer
experience and reduces errors when working with unfamiliar
devices. This is effectively provided by US1's read capability
but framed as an explicit use case for documentation and API
design.

**Independent Test**: Connect to a device, retrieve relay
configuration, and verify that the returned structure exposes
all available configuration key names.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer retrieves
   relay configuration, **Then** the response includes identifiable
   key names that can be used in subsequent set operations.
2. **Given** a connected device with a relay configuration that
   includes optional/model-specific settings, **When** the
   developer retrieves configuration, **Then** all available
   settings are included regardless of whether they have
   non-default values.

---

### Edge Cases

- What happens when a configuration key exists on one device
  model but not another? The library should propagate the device
  error as an appropriate exception.
- What happens when the device reboots or is busy during a
  configuration write? The library should raise a connection
  error if the request times out.
- What happens when the developer provides an empty configuration
  update (no keys)? The library should raise a validation error
  before sending to the device.
- What happens when authentication is required but not provided?
  The library should raise an authentication error, consistent
  with existing behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Library MUST provide a method to retrieve the
  current relay configuration from a connected device.
- **FR-002**: Library MUST return relay configuration as a
  structured object with named attributes (not raw key-value
  strings).
- **FR-003**: Library MUST provide a method to update one or more
  relay configuration settings on a connected device.
- **FR-004**: Library MUST validate that at least one
  configuration key-value pair is provided before sending an
  update request.
- **FR-005**: Library MUST map device error responses (non-zero
  retcode) to typed exceptions, consistent with the existing
  error handling pattern.
- **FR-006**: Library MUST support all authentication modes
  (None, Allowlist, Basic, Digest) for configuration operations,
  consistent with existing device operations.
- **FR-007**: Library MUST support SSL connections (including
  self-signed certificate handling) for configuration operations,
  consistent with existing device operations.
- **FR-008**: Library MUST serialize configuration requests
  through the existing per-device lock to prevent concurrent
  access issues.
- **FR-009**: Library MUST use the autop-format key convention
  (e.g., `Config.DoorSetting.RELAY.*`) for configuration keys
  sent to the device.
- **FR-010**: The existing example test script
  (`examples/mvp_test.py`) MUST be updated at each implementation
  phase to exercise the new configuration capabilities, enabling
  live-device validation of read and write operations.

### Key Entities

- **RelayConfig**: Represents the relay configuration for a
  device. Contains settings such as hold delay, trigger delay,
  relay name, and HTTP relay access configuration. Attributes
  map from autop-format keys to developer-friendly snake_case
  names.

## Assumptions

- The Akuvox local HTTP API uses the same envelope response
  format (`retcode`, `message`, `data`) for relay configuration
  endpoints as for all other endpoints.
- The relay configuration GET endpoint returns all relay settings
  in a single response (no pagination needed).
- Configuration keys follow the `Config.DoorSetting.RELAY.*`
  naming pattern documented in the existing API research.
- The relay set endpoint accepts one or more key-value pairs in
  a single request.
- Configuration changes take effect immediately on the device
  (no reboot or apply step required).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developer can retrieve relay configuration from a
  device in 5 lines of code or fewer (excluding imports and
  boilerplate).
- **SC-002**: Developer can update a relay configuration setting
  in 5 lines of code or fewer (excluding imports and boilerplate).
- **SC-003**: All configuration operations raise typed exceptions
  on failure — never return silent errors or raw error codes.
- **SC-004**: Configuration operations work with all four
  authentication modes without additional developer effort.
- **SC-005**: 100% unit test coverage for all new configuration
  code.
- **SC-006**: All new public methods and classes include
  comprehensive docstrings.
- **SC-007**: The example test script validates configuration
  read and write operations against a live device, with results
  reported per test scenario (pass/fail with details).
