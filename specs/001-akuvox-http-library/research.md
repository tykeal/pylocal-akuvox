<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Akuvox Local HTTP API Library

## R1: Akuvox HTTP API Structure

**Decision**: The Akuvox local HTTP API uses a REST-like pattern at
`http://<device-ip>/api/<resource>/<action>` with JSON request and
response bodies. POST endpoints accept `application/json` request
bodies. GET endpoints pass parameters via query string and do not
require a request body. Mutation POST requests require a wrapped
body: `{"action":"X","data":{"item":[{...}]}}`. All **responses**
follow a uniform envelope:
`{ "retcode": int, "action": str, "message": str, "data": {...} }`.
GET endpoints return `retcode: 0` on success; mutation endpoints
return `retcode >= 0` on success (`retcode: 1` is typical) and
`retcode < 0` on failure.

**Rationale**: Confirmed from two Apifox-generated OpenAPI specs
(`linux_AC_api` for access controllers, `linux_api` for full device
range). The AC-specific spec has 47 endpoints; the general spec has
74 endpoints including call management, contacts, SIP, and groups.

**Alternatives considered**:

- Cloud API: Out of scope per spec; library targets LAN only.
- SDMC/ACMS server protocols: Proprietary server-side protocols,
  not relevant for direct device communication.

## R2: Async HTTP Client Library

**Decision**: Use `aiohttp` as the single HTTP dependency.

**Rationale**: aiohttp provides async HTTP client with built-in support
for HTTP Basic and Digest authentication via `aiohttp.BasicAuth` and
`aiohttp.DigestAuthMiddleware` (added in aiohttp 3.13). It is the
standard async HTTP library in the Home Assistant ecosystem.
It has zero additional transitive runtime
dependencies beyond the stdlib and a few small packages (multidict,
yarl, aiosignal, frozenlist, aiohappyeyeballs). This satisfies SC-003
(≤2 runtime deps) since aiohttp is the only direct dependency needed.

**Alternatives considered**:

- `httpx`: Supports async and sync, but heavier; includes HTTP/2
  support we don't need. Does not have built-in Digest auth without
  additional packages.
- `urllib3` + `asyncio`: Not natively async; would require wrapping
  in executors, violating Constitution IV (no event loop blocking).
- `requests`: Synchronous only; incompatible with FR-012.

## R3: Authentication Handling

**Decision**: Implement four auth modes: None (no headers),
AllowList (no headers, device validates source IP), Basic Auth
(via `aiohttp.BasicAuth`), Digest Auth (via
`aiohttp.DigestAuthMiddleware`, available in aiohttp 3.13+).
Token auth is explicitly excluded (reserved/unimplemented by Akuvox).

**Rationale**: The OpenAPI specs have empty `securitySchemes` — auth
is configured at the device level, not per-endpoint. The device either
accepts all requests (None), validates source IP (AllowList), or
requires HTTP-level auth (Basic/Digest). From the library's perspective,
None and AllowList are identical (no credentials sent). Basic and Digest
are handled natively by aiohttp.

**Alternatives considered**:

- Custom auth header injection: Unnecessary; aiohttp handles
  Basic/Digest natively.
- Token support as placeholder: Prohibited by spec — "MUST NOT
  support Token authentication."

## R4: Device API Endpoint Mapping

**Decision**: Map library operations to Akuvox API endpoints as follows:

| Library Operation | HTTP Method | Endpoint |
| ----------------- | ----------- | -------- |
| Get device info | GET | `/api/system/info` |
| Get device status | GET | `/api/system/status` |
| Get relay config | GET | `/api/relay/get` |
| Get relay status | GET | `/api/relay/status` |
| Trigger relay | POST | `/api/relay/trig` |
| Set relay config | POST | `/api/relay/set` |
| List users | GET | `/api/user/get` |
| Add user | POST | `/api/user/add` |
| Modify user | POST | `/api/user/set` |
| Delete user | POST | `/api/user/del` |
| List schedules | POST | `/api/schedule/get` |
| Add schedule | POST | `/api/schedule/add` |
| Modify schedule | POST | `/api/schedule/set` |
| Delete schedule | POST | `/api/schedule/del` |
| Get door logs | POST | `/api/doorlog/get` |
| Get call logs | POST | `/api/calllog/get` |

**Rationale**: Direct mapping from Apifox specs, corrected based on
real E18 device testing. GET endpoints (info, status, user/get) take
no body; query params used for pagination (`?page=N`). POST mutation
endpoints require `application/json` content type with body wrapped
in `{"action":"X","data":{"item":[{...}]}}`. The `user/set` endpoint
requires a complete user record (read-modify-write pattern). Page
size is fixed at 10 items by the device.

**Alternatives considered**: None — these are the documented endpoints.

## R5: Request Serialization Strategy

**Decision**: Use an `asyncio.Lock` per `AkuvoxDevice` instance to
serialize all HTTP requests to the same device.

**Rationale**: FR-010 requires serializing concurrent requests to
prevent conflicting hardware state. A per-instance lock is simple,
correct, and sufficient for LAN-only single-device communication.
The lock granularity is per-device (not global) so multiple device
instances can operate concurrently.

**Alternatives considered**:

- asyncio.Semaphore: Allows N concurrent requests, but the device
  hardware may not handle concurrent mutations safely.
- No serialization: Violates FR-010; concurrent relay triggers
  could corrupt device state.
- Request queue with worker: Over-engineered for a LAN client
  with sub-second response times.

## R6: Response Envelope and Error Handling

**Decision**: All Akuvox responses use the envelope
`{ "retcode": int, "action": str, "message": str, "data": {...} }`.
Map `retcode` values to exception types:

- `retcode == 0`: Success
- `retcode != 0` with known codes: Map to specific exception types
- HTTP 401: `AkuvoxAuthenticationError`
- HTTP 400: `AkuvoxRequestError`
- HTTP 500: `AkuvoxDeviceError`
- Non-JSON response: `AkuvoxParseError`
- Connection refused/timeout: `AkuvoxConnectionError`

**Rationale**: The OpenAPI specs define response codes 200, 400, 401,
500, and pseudo-codes "x-200" for "Api unsupported" and "Error param".
The `retcode` field in the 200 response body distinguishes success from
application-level errors. This maps cleanly to a Python exception
hierarchy rooted at `AkuvoxError`.

**Alternatives considered**:

- Return raw response dicts: Violates SC-002 (no raw HTTP codes
  exposed to caller) and FR-006 (distinct exception types).
- Single exception type: Violates FR-006 (must distinguish
  connection, auth, invalid op, and parse errors).

## R7: User Data Model Fields

**Decision**: The User entity maps to the Akuvox user object with these
fields from the API:

- `ID` (str): Internal database ID (used for set/del operations)
- `Name` (str): Display name (mandatory on add)
- `UserID` (str): PerID / external user identifier (mandatory on add)
- `PrivatePIN` (str): PIN code for keypad access (optional)
- `CardCode` (str): RFID card code (optional)
- `WebRelay` (str): Assigned relay (mandatory on add)
- `ScheduleRelay` (str): Schedule-relay mapping (mandatory on add)
- `Type` (str): User type (ordinary/admin)
- `Source` (str): Source of the user record
- `SourceType` (str): Source type (Local/Cloud/SDMC)
- `LiftFloorNum` (str): Floor number for elevator control

**Rationale**: Fields extracted from the `/api/user/get` response
schema. Mandatory fields for add: Name, UserID, LiftFloorNum,
WebRelay, ScheduleRelay. Optional: PrivatePIN, CardCode, AuthMode,
PhoneNum, Group, DialAccount, PriorityCall, and device-specific
BLE/Analog fields.

**Alternatives considered**: Exposing only Name + PIN was considered
for MVP simplicity, but the API requires WebRelay, LiftFloorNum,
and ScheduleRelay as mandatory fields on user creation.

## R8: Schedule Data Model Fields

**Decision**: The Schedule entity maps to:

- `ID` (str): Internal database ID
- `Name` (str): Schedule display name
- `Type` (str): 0=Normal, 1=Weekly, 2=Daily
- `Mode` (str): 0=Normal, 1=Weekly, 2=Daily
- `DateStart` / `DateEnd` (str): Date range (YYYYMMDD-YYYYMMDD)
- `TimeStart` / `TimeEnd` (str): Time range (HH:MM-HH:MM)
- `Sun`..`Sat` (str): Day-of-week flags
- `Daily` (str): Daily time range
- `Week` (str): Day codes (0=sun..6=sat)
- `Date` (str): Date range string
- `DisplayID` (str): Display identifier
- `SourceType` (str): 1=Local, 2=Cloud, 3=ACMS, 4=SDMC

**Rationale**: Fields extracted from `/api/schedule/get` response.
Schedule add requires Type (mandatory); Name, Week, Date, Daily are
optional.

## R9: Log Entry Data Models

**Decision**:

Door log entry fields:

- `ID`, `Date`, `Time`, `Name`, `Code`, `Type` (open door type),
  `Relay`, `Status` (Succ/Failed), `AccessMode` (optional)

Call log entry fields:

- `ID`, `Date`, `Time`, `Name`, `Type` (Dialed/Received/Missed/
  Forwarded/Unknow), `LocalIdentity`, `Num`, `PicUrl` (optional)

Both support pagination via `page` param and filtering via
`Status`, `TimeStart`, `TimeEnd`, `NameOrCode`/`NameOrNumber`.

**Rationale**: Fields extracted from `/api/doorlog/get` and
`/api/calllog/get` response schemas respectively.

## R10: Python Packaging with uv

**Decision**: Use `uv` for package management with `pyproject.toml`
as the single project configuration file. The `src/` layout with
`src/pylocal_akuvox/` package directory. Python 3.14 as the minimum
version. Pre-commit hooks via prek (already configured in repo).

**Rationale**: User specified uv as the package manager and Python 3.14
as the base. The src-layout prevents import confusion during testing.
prek is already set up on the repository.

**Alternatives considered**:

- Poetry: Heavier, less HA ecosystem alignment.
- setuptools: Lower-level; uv provides better dependency resolution.
- Flat layout (no src/): Can cause test import issues.
