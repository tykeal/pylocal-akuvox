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

### User Story 1 - Read Device Configuration (Priority: P1)

A developer retrieves the full device configuration from an Akuvox
device. The endpoint (`/api/config/get`) returns all autop-format
configuration keys — relay settings, network, SIP, display, door
settings, and more. This is the foundation for any configuration
workflow — you must read before you can decide what to change.

**Why this priority**: Reading configuration is the safest starting
point and a prerequisite for any write operation. It delivers
immediate value for monitoring and diagnostics without risk of
altering device state.

**Independent Test**: Connect to a device, call the get device
configuration method, and verify that configuration keys are
returned with the expected structure and values.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer requests
   device configuration, **Then** the library returns a structured
   object containing all configuration keys as autop-format
   key-value pairs (e.g., relay settings, network, SIP, display).
2. **Given** a connected device, **When** the developer requests
   device configuration, **Then** all keys returned by the device
   are accessible, including model-specific or undocumented keys.
3. **Given** a device that is unreachable, **When** the developer
   requests device configuration, **Then** a connection error is
   raised within the configured timeout.

---

### User Story 2 - Update Device Configuration (Priority: P2)

A developer modifies configuration settings on an Akuvox device —
for example, changing the hold delay for a door relay or updating
a display setting. The developer provides one or more autop-format
configuration keys and their new values; the library applies them
to the device via `POST /api/config/set`.

**Why this priority**: Writing configuration enables automation
and programmatic device management, which is the core use case
for Home Assistant integration. Depends on US1 for verifying
changes.

**Independent Test**: Connect to a device, set a configuration
value (e.g., relay hold delay), then read back the configuration
and verify the new value was applied.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer sets a
   single configuration value using an autop-format key, **Then**
   the device accepts the change and the method returns without
   raising an exception (absence of an exception indicates
   success).
2. **Given** a connected device, **When** the developer sets
   multiple configuration values in one call, **Then** all
   values are applied and confirmed.
3. **Given** a connected device, **When** the developer sets a
   configuration key to an invalid value, **Then** the device
   returns an error and the library raises an appropriate
   exception.
4. **Given** a connected device, **When** the developer provides
   no key-value pairs, **Then** the library raises a validation
   error before sending to the device.

---

### User Story 3 - Discover Available Configuration Keys (Priority: P3)

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

**Independent Test**: Connect to a device, retrieve device
configuration, and verify that the returned structure exposes
all available configuration key names.

**Acceptance Scenarios**:

1. **Given** a connected device, **When** the developer retrieves
   device configuration, **Then** the response includes all
   autop-format key names that can be used in subsequent set
   operations.
2. **Given** a connected device with model-specific settings,
   **When** the developer retrieves configuration, **Then** all
   available settings are included regardless of whether they
   have non-default values.

---

### Edge Cases

- What happens when a configuration key exists on one device
  model but not another? The library MUST propagate the device
  error as an appropriate exception.
- What happens when the device reboots or is busy during a
  configuration write? The library MUST raise a connection
  error if the request times out.
- What happens when the developer provides an empty configuration
  update (no keys)? The library MUST raise a validation error
  before sending to the device.
- What happens when authentication is required but not provided?
  The library MUST raise an authentication error, consistent
  with existing behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Library MUST provide a method to retrieve the
  full device configuration from a connected device via
  `GET /api/config/get`.
- **FR-002**: Library MUST return device configuration as a
  structured `DeviceConfig` object that provides access to all
  autop-format key-value pairs returned by the device.
- **FR-003**: Library MUST provide a method to update one or more
  device configuration settings via `POST /api/config/set`.
- **FR-004**: Library MUST validate that at least one
  configuration key-value pair is provided before sending an
  update request.
- **FR-005**: Library MUST map device error responses (negative
  retcode values) to typed exceptions, consistent with the
  existing error handling pattern.
- **FR-006**: Library MUST support all authentication modes
  (None, AllowList, Basic Auth, Digest Auth) for configuration
  operations, consistent with existing device operations.
- **FR-007**: Library MUST support SSL connections (including
  self-signed certificate handling) for configuration operations,
  consistent with existing device operations.
- **FR-008**: Library MUST serialize configuration requests
  through the existing per-device lock to prevent concurrent
  access issues.
- **FR-009**: Library MUST preserve autop-format keys as-is
  (e.g., `Config.DoorSetting.RELAY.HoldDelayA`) for both read
  and write operations. No snake_case mapping is performed.
- **FR-010**: Each implementation phase MUST be independently
  verifiable against a live device, enabling incremental
  validation of configuration read and write operations.
- **FR-011**: Library MUST provide a method to enumerate all
  autop-format configuration key names available on a
  `DeviceConfig` instance, enabling key discovery (US3).

### Key Entities

- **DeviceConfig**: Represents the full device configuration.
  Wraps all autop-format key-value pairs returned by
  `GET /api/config/get`. Provides dict-like access to any
  configuration key (relay settings, network, SIP, display,
  etc.).

### Assumptions

- The Akuvox local HTTP API uses the same envelope response
  format (`retcode`, `message`, `data`) for configuration
  endpoints as for all other endpoints.
- The device configuration GET endpoint returns all settings
  in a single response (no pagination needed). Real devices
  return 900+ keys across many categories.
- Configuration keys use autop-format naming (e.g.,
  `Config.DoorSetting.RELAY.HoldDelayA`,
  `Config.Network.LAN.IPAddress`).
- The configuration set endpoint accepts one or more
  autop-format key-value pairs in a single request.
- Configuration changes take effect immediately on the device
  (no reboot or apply step required).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developer can retrieve device configuration from a
  device in 5 lines of code or fewer (excluding imports and
  boilerplate).
- **SC-002**: Developer can update a device configuration setting
  in 5 lines of code or fewer (excluding imports and boilerplate).
- **SC-003**: All configuration operations raise typed exceptions
  on failure — never return silent errors or raw error codes.
- **SC-004**: Configuration operations work with all four
  authentication modes without additional developer effort.
- **SC-005**: 100% unit test coverage for all new configuration
  code.
- **SC-006**: All new public methods and classes include
  comprehensive docstrings.
- **SC-007**: Configuration read and write operations can be
  validated against a live device, with clear pass/fail results
  available for each defined user scenario.
