<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Device Configuration Management

**Feature**: 002-device-config
**Date**: 2026-02-24

## R1: Relay Configuration GET Endpoint

**Decision**: Use `GET /api/relay/get` to retrieve relay settings.

**Rationale**: The API contract (`akuvox-api.yaml` lines 67-81)
documents this endpoint as returning relay settings including trigger
delay, hold delay, relay name, and HTTP relay access configuration.
The endpoint accepts both GET and POST but GET is the standard read
method used by the existing library for status endpoints.

**Alternatives considered**:

- POST to `/api/relay/get` — accepted by the device but
  inconsistent with the library's pattern of using GET for reads
  (e.g., `get_relay_status`, `get_info`, `get_status`)

**Response structure** (from live device testing in Phase 1 of
spec 001):

The GET endpoint returns the standard envelope with autop-format
keys in the data object. Exact keys will be confirmed during
Phase 1 implementation via live device testing. Expected keys
based on API documentation:

- `Config.DoorSetting.RELAY.HoldDelayA` — door hold time (seconds)
- `Config.DoorSetting.RELAY.TrigDelayA` — trigger delay (seconds)
- `Config.DoorSetting.RELAY.RelayNameA` — relay display name
- Additional per-relay keys (B suffix for relay 2, etc.)

## R2: Relay Configuration SET Endpoint

**Decision**: Use `POST /api/relay/set` with autop-format keys
in the standard `{target, action, data}` envelope.

**Rationale**: The API contract (`akuvox-api.yaml` lines 83-105)
documents this as POST-only, using the same envelope format as
relay trigger. The `data` field contains autop-format key-value
pairs.

**Request format** (from API contract):

```json
{
  "target": "relay",
  "action": "set",
  "data": {
    "Config.DoorSetting.RELAY.HoldDelayA": "8"
  }
}
```

**Alternatives considered**:

- Individual key endpoints — not available in the API
- Batch endpoint with non-autop keys — not supported

## R3: Data Model Design

**Decision**: Create a single `RelayConfig` frozen dataclass
with `from_api_response()` and `to_api_payload()` methods,
following the `User` and `AccessSchedule` patterns.

**Rationale**: The existing codebase uses frozen dataclasses for
all API response models. `User` and `AccessSchedule` both have
`from_api_response()` for parsing and `to_api_payload()` for
serialization. The same pattern maps cleanly to relay
configuration.

**Key mapping**: Autop-format keys map to snake_case attributes:

| Autop Key | Attribute |
| --- | --- |
| `Config.DoorSetting.RELAY.HoldDelayA` | `hold_delay_a` |
| `Config.DoorSetting.RELAY.TrigDelayA` | `trig_delay_a` |
| `Config.DoorSetting.RELAY.RelayNameA` | `relay_name_a` |

Additional keys will be discovered during live device testing
and added to the model.

**Alternatives considered**:

- Raw dict — rejected; FR-002 requires structured objects
- Mutable dataclass — rejected; consistency with existing models

## R4: Module Structure

**Decision**: Create `config.py` following the `relay.py` pattern.

**Rationale**: Every domain operation in the library has its own
module (`relay.py`, `users.py`, `logs.py`, `schedules.py`). Each
module contains pure async functions that accept `AkuvoxHttpClient`
as the first parameter. The device facade (`device.py`) delegates
to these modules. This pattern provides separation of concerns
and testability.

**Alternatives considered**:

- Adding config methods directly to `relay.py` — rejected;
  relay trigger/status is operationally different from
  configuration management
- Adding to `device.py` directly — rejected; violates the
  established delegation pattern

## R5: Error Handling Alignment

**Decision**: Rely on the existing `_http.py` error handling.
No new exception types needed.

**Rationale**: The HTTP client already handles:

- HTTP 401 → `AkuvoxAuthenticationError`
- HTTP 400 → `AkuvoxRequestError`
- Negative retcode → `AkuvoxDeviceError`
- "Api unsupported" → `AkuvoxUnsupportedError`
- Connection failures → `AkuvoxConnectionError`

The only new validation is FR-004 (empty config update), which
maps to `AkuvoxValidationError` — already used in `relay.py`.

## R6: Test Script Integration

**Decision**: Extend `examples/mvp_test.py` at each phase.

**Rationale**: FR-010 requires each phase to be independently
verifiable against a live device. The existing test script has
a clear read-tests / write-tests separation with `--write` flag
control. Config read tests go in the read section; config write
tests go in the write section gated by `--write`.

**Phase 1 additions**: Read relay config test
**Phase 2 additions**: Write relay config test (under `--write`)
**Phase 3 additions**: Key discovery / inspection test
