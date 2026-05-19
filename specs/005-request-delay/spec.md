<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Feature Branch**: `005-request-delay`
**Created**: 2025-07-14
**Status**: Draft
**Input**: User description: "Add configurable inter-request delay to HTTP client"
**Related Issue**: #96

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default Delay Protects Device (Priority: P1)

As a library consumer using pylocal-akuvox, I want the HTTP client to automatically pause between consecutive requests so that the Akuvox intercom device is not overwhelmed during batch operations (e.g., syncing multiple contacts or groups in sequence).

**Why this priority**: This is the core value proposition — preventing device lockups that occur when requests are fired back-to-back against the resource-constrained embedded system. Without this, batch operations can cause API failures.

**Independent Test**: Can be fully tested by issuing multiple sequential requests through the HTTP client and verifying that a pause occurs between each successful response and the next request being sent.

**Acceptance Scenarios**:

1. **Given** an HTTP client initialized with default settings, **When** two requests are issued in sequence and both succeed, **Then** a 0.25-second pause occurs between the first response completing and the second request being sent.
2. **Given** an HTTP client initialized with default settings, **When** a single request is issued, **Then** no delay occurs before the request is sent (delay is only after response).
3. **Given** an HTTP client initialized with default settings, **When** five requests are issued in rapid succession, **Then** each request after the first is preceded by a 0.25-second pause following the previous successful response.

---

### User Story 2 - Consumer Configures Custom Delay (Priority: P2)

As a library consumer, I want to configure the inter-request delay value so that I can tune the pacing for my specific use case — faster for single interactive operations or slower for large batch imports.

**Why this priority**: Different consumers have different usage patterns. A Home Assistant integration doing occasional single commands needs less delay than a bulk provisioning script. Configurability ensures the library serves all use cases.

**Independent Test**: Can be fully tested by creating HTTP client instances with different delay values and verifying that the actual pause between requests matches the configured value.

**Acceptance Scenarios**:

1. **Given** an HTTP client initialized with a custom delay of 0.5 seconds, **When** two requests are issued in sequence and both succeed, **Then** a 0.5-second pause occurs between the first response completing and the second request being sent.
2. **Given** an HTTP client initialized with a delay of 0.0 seconds, **When** two requests are issued in sequence, **Then** no pause occurs between requests (backwards-compatible behavior).
3. **Given** a device wrapper initialized with a custom delay value, **When** the device issues HTTP requests, **Then** the configured delay is applied between requests.

---

### User Story 3 - Delay Skipped on Errors (Priority: P3)

As a library consumer, I want the inter-request delay to be skipped when a request fails so that error handling is not unnecessarily slowed down and the error is reported to callers as quickly as possible.

**Why this priority**: When a request fails, there is no benefit to waiting — the device is not processing a successful response, and the caller needs to handle the error promptly. Skipping the delay on errors also simplifies retry logic for consumers.

**Independent Test**: Can be fully tested by issuing a request that results in an error and verifying that no inter-request delay occurs before the error is raised.

**Acceptance Scenarios**:

1. **Given** an HTTP client with a configured delay, **When** a request fails (connection error, timeout, or HTTP error status), **Then** no delay is applied and the error is raised immediately.
2. **Given** an HTTP client with a configured delay, **When** a request fails followed by a subsequent successful request, **Then** the delay is only applied after the successful response.

---

### Edge Cases

- What happens when the delay value is negative? The system should treat negative values as invalid and reject them at initialization time.
- What happens when the delay value is extremely large (e.g., 60 seconds)? The system should accept it — consumers may have legitimate reasons for long delays, and it is their responsibility to choose appropriate values.
- What happens if the client is used concurrently by multiple callers? The existing lock serialization ensures only one request is in-flight at a time; the delay occurs within the lock, so concurrent callers simply wait their turn.
- What happens if the sleep is interrupted (e.g., task cancellation)? The cancellation should propagate normally — the delay should not suppress task cancellation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The HTTP client MUST accept a `request_delay` configuration parameter at initialization time that specifies the pause duration (in seconds) between a successful response and releasing the request lock.
- **FR-002**: The HTTP client MUST default the `request_delay` parameter to 0.25 seconds when not explicitly provided by the consumer.
- **FR-003**: The HTTP client MUST pause for the configured `request_delay` duration after each successful response before allowing the next request to proceed.
- **FR-004**: The HTTP client MUST NOT apply any delay when a request results in an error (connection failure, timeout, or HTTP error response).
- **FR-005**: The HTTP client MUST NOT apply any delay before the first request — the delay occurs only after a response is received.
- **FR-006**: The HTTP client MUST skip the delay entirely when `request_delay` is set to 0.0, preserving backwards-compatible behavior with no sleep overhead.
- **FR-007**: The HTTP client MUST apply the delay uniformly to all request types (both GET and POST operations).
- **FR-008**: The device wrapper MUST accept a `request_delay` parameter and pass it through to the underlying HTTP client.
- **FR-009**: The HTTP client MUST reject negative values for `request_delay` at initialization time with a clear error indicating the value must be zero or positive.
- **FR-010**: The HTTP client MUST NOT introduce any breaking changes to the existing public interface — all existing constructor signatures and method signatures remain compatible.

### Key Entities

- **Request Delay**: A numeric duration (in seconds) representing the pause between a successful HTTP response and releasing the serialization lock. Accepted range: 0.0 or any positive number. Default: 0.25 seconds.
- **HTTP Client**: The component responsible for issuing serialized HTTP requests to the Akuvox device. Owns the lock and the delay behavior.
- **Device Wrapper**: The higher-level component that consumers interact with directly. Passes configuration (including request delay) through to the HTTP client.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Batch operations of 10+ sequential requests complete without device lockup when using the default delay setting.
- **SC-002**: The time between consecutive successful requests is within 10% of the configured delay value (e.g., 0.225–0.275s for default 0.25s setting).
- **SC-003**: Setting `request_delay=0.0` results in no measurable overhead compared to current behavior (less than 1ms added latency between requests).
- **SC-004**: All existing library consumers continue to function without code changes after the feature is added (no breaking API changes).
- **SC-005**: A single isolated request is sent with no pre-request latency; any configured delay is applied only after a successful response.

## Assumptions

- The existing request serialization mechanism is the correct place to integrate the delay (after response, before lock release).
- 0.25 seconds is a safe default that balances responsiveness with device protection, based on experience with Akuvox embedded hardware.
- Consumers who need zero delay (e.g., for testing or for devices with more resources) can explicitly set `request_delay=0.0`.
- The delay applies within the library uniformly — there is no need for per-endpoint or per-method delay differentiation.
- Task cancellation during the delay sleep should propagate normally (standard async cancellation semantics).
