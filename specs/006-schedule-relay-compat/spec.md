<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: Schedule-Relay Field Compatibility for E18 Firmware

**Feature Branch**: `006-schedule-relay-compat`
**Created**: 2025-11-14
**Status**: Draft
**Input**: Dual-write `ScheduleRelay` and `Schedule-Relay` in user add/set payloads to support Akuvox E18 firmware 18.30.11.21, which renamed the primary access-schedule request field. Backward-compatible across all tested firmwares. Secondary-relay scheduling is outside the current public API and remains out of scope. See issue #99.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add user succeeds on E18 firmware 18.30.11.21 (Priority: P1)

An integrator using the library to provision door-access users on an Akuvox E18-class intercom running firmware 18.30.11.21 calls the library's add-user operation with an access schedule assigned to the primary relay. The device accepts the request and the user is created with the correct schedule binding, just as it would on older firmwares.

**Why this priority**: This is the regression being fixed. Without it, every add-user call against affected E18 devices fails outright (`retcode: -1, "Failed"`), blocking the integrator's entire provisioning workflow on that hardware. This is the only behavior change required to restore functionality.

**Independent Test**: Against an E18-class device on firmware 18.30.11.21, invoke the library's add-user operation with a schedule assigned to the primary relay; confirm the device returns success and that a subsequent get-user call shows the schedule correctly stored on the primary relay.

**Acceptance Scenarios**:

1. **Given** an E18 device on firmware 18.30.11.21 and a valid new-user payload that includes a primary-relay schedule, **When** the integrator calls add-user, **Then** the device returns a success result and the user is created with the expected schedule binding.
2. **Given** the same device and a request that modifies an existing user's primary-relay schedule, **When** the integrator calls modify-user, **Then** the device returns a success result and the stored schedule reflects the new value.

---

### User Story 2 - Existing firmwares continue to work unchanged (Priority: P1)

An integrator already using the library against older firmwares (e.g., X916 on 916.30.10.114, or any E-series firmware prior to 18.30.11.21) continues to add and modify users without any change in behavior, return values, or stored data.

**Why this priority**: A fix that restored one firmware while breaking another would be a net regression. Backward compatibility across the existing tested-firmware matrix is a release blocker, not a nice-to-have, and must be verified alongside the primary fix.

**Independent Test**: Against an X916 device on firmware 916.30.10.114 (and any other previously-supported firmware available), run the existing add-user and modify-user flows with a primary-relay schedule and confirm identical success results and stored schedule values compared to the prior library release.

**Acceptance Scenarios**:

1. **Given** an X916 device on firmware 916.30.10.114, **When** the integrator calls add-user with a primary-relay schedule, **Then** the device returns success and the schedule is stored on the primary relay exactly as it was with the prior library version.
2. **Given** any previously-supported firmware, **When** the integrator inspects a user after add or modify, **Then** the primary-relay schedule is reported under the same un-hyphenated field name as before, and downstream code that reads it requires no changes.

---

### User Story 3 - Secondary relay remains out of scope (Priority: P2)

An integrator using the current public API does not receive any new secondary-relay scheduling behavior as part of this compatibility fix. The change is limited to the existing primary-relay schedule field.

**Why this priority**: Testing on the affected E18 firmware showed that a hyphenated secondary-relay field is silently accepted but discards the value. Because the current library does not expose secondary-relay scheduling, this feature must avoid introducing either `ScheduleSRelay` or a hyphenated secondary companion while fixing the primary relay.

**Independent Test**: Inspect outgoing add-user and modify-user payloads produced by the current API and confirm the feature adds only `Schedule-Relay` alongside `ScheduleRelay`; no secondary-relay request key is introduced.

**Acceptance Scenarios**:

1. **Given** an E18 device on firmware 18.30.11.21, **When** the integrator calls add-user with the current primary-relay schedule parameter, **Then** the payload contains the two primary-relay field names and no new secondary-relay field.
2. **Given** any tested firmware, **When** the integrator modifies a user's primary-relay schedule, **Then** the payload shape changes only for the primary-relay field names.

---

### Edge Cases

- **Unset primary schedule on modify**: When the integrator calls modify-user without supplying a new primary-relay schedule (parameter omitted or `None`), this feature adds neither `ScheduleRelay` nor `Schedule-Relay` to the outgoing update, so the device cannot end up with two conflicting values for the same logical field. (Add-user rejects an empty/missing primary-relay schedule with a validation error before any request is built, so the "two keys disagreeing" risk does not arise there.)
- **Secondary relay remains out of scope**: The current public API does not accept a secondary-relay schedule. This feature must not add one while fixing the primary-relay compatibility issue.
- **Future firmware that recognizes both names**: If a future firmware recognizes both the hyphenated and un-hyphenated primary-relay field names, sending identical values for both keys means the stored result is unambiguous regardless of which one the device prefers.
- **Response parsing**: All tested firmwares return the primary-relay schedule under the un-hyphenated name on read; the library's read path is unaffected and continues to consume that single field name.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When creating a user, the library MUST include the primary-relay access schedule under both the un-hyphenated field-name variant (`ScheduleRelay`) and the hyphenated field-name variant (`Schedule-Relay`) in the outgoing request, with both keys carrying the same value.
- **FR-002**: When modifying a user, the library MUST include the primary-relay access schedule under both the un-hyphenated field-name variant (`ScheduleRelay`) and the hyphenated field-name variant (`Schedule-Relay`) in the outgoing request, with both keys carrying the same value, whenever that schedule is part of the update.
- **FR-003**: The library MUST NOT introduce secondary-relay scheduling fields as part of this feature; neither `ScheduleSRelay` nor any hyphenated secondary companion may be added by the primary-relay compatibility change.
- **FR-004**: The library MUST continue to read the primary-relay access schedule from the un-hyphenated field name in device responses; response-parsing behavior MUST be unchanged.
- **FR-005**: The library's public interface for assigning a primary-relay schedule (parameter names, types, and semantics exposed to callers) MUST be unchanged; the dual-field behavior is an internal request-shaping detail.
- **FR-006**: The library MUST NOT perform any firmware version detection or version-conditional branching to decide which field name(s) to send; the dual-write behavior applies uniformly to all devices.
- **FR-007**: For modify-user requests, when the caller does not supply a new primary-relay schedule value (parameter omitted or `None`), the two field-name variants MUST remain consistent in the outgoing payload — specifically, neither `ScheduleRelay` nor `Schedule-Relay` is added to the update by this feature, so the device cannot receive conflicting values for the same logical field. Add-user requires a non-empty primary-relay schedule by precondition (caller-supplied empty values are rejected with a validation error), so the "both omitted" case does not apply to add-user.
- **FR-008**: Automated unit tests at the outgoing-payload boundary MUST verify that add-user and modify-user request payloads contain both field-name variants (`ScheduleRelay` and `Schedule-Relay`) for the primary-relay schedule with identical values, and that no secondary-relay request field is introduced by this feature.

### Key Entities

- **Primary-relay access schedule**: The schedule binding that controls when a given user is authorized to trigger the device's primary relay (e.g., main door). Carried in outgoing user add/modify requests; on affected firmware it is recognized only under a hyphenated field name, on other tested firmware only under the un-hyphenated name, and on read it is always reported under the un-hyphenated name.
- **Secondary-relay access schedule**: A device capability outside the current library API. The affected firmware's hyphenated secondary form is unsafe, so this primary-relay fix intentionally leaves secondary-relay scheduling out of scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Add-user and modify-user operations that include a primary-relay schedule succeed on Akuvox E18-class devices running firmware 18.30.11.21, where they previously failed 100% of the time with a generic failure result.
- **SC-002**: Add-user and modify-user operations on every previously-supported firmware (including X916 on 916.30.10.114) produce identical observable outcomes — success/failure result, stored schedule value on subsequent read, and any returned data — compared to the prior library release.
- **SC-003**: After an add or modify that sets a primary-relay schedule, a follow-up read of the same user on any tested firmware returns the exact schedule value that was sent, with no data loss or substitution.
- **SC-004**: No add-user or modify-user request generated by this feature includes a new secondary-relay scheduling field.
- **SC-005**: Integrators using the library require zero code changes on their side to pick up the fix — upgrading the library version is sufficient to restore add-user and modify-user functionality on the affected firmware.
