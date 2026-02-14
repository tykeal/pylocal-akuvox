<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Akuvox Local HTTP API Library

**Input**: Design documents from
`/specs/001-akuvox-http-library/`
**Prerequisites**: plan.md, spec.md, research.md,
data-model.md, contracts/akuvox-api.yaml, quickstart.md

**Tests**: Unit-level tests are MANDATORY per constitution
(Principle II: TDD). Red-Green-Refactor enforced at all times.
Higher-level tests MAY be deferred per Principle VI.

**Organization**: Tasks grouped by user story for independent
implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no deps)
- **[Story]**: User story this task belongs to (US1–US7)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure, packaging, and
tooling per plan.md and research.md R10.

- [x] T001 Initialize uv project with pyproject.toml at
  repo root: Python >=3.14, src-layout, project name
  `pylocal-akuvox`, add aiohttp as runtime dependency,
  pytest + pytest-asyncio + aioresponses as dev dependencies
- [x] T002 Create src/pylocal_akuvox/`__init__`.py with package
  version and public API re-exports (empty stubs for now)
- [x] T003 [P] Create empty test structure: tests/`__init__`.py,
  tests/conftest.py (shared fixtures), tests/unit/`__init__`.py
- [x] T004 [P] Configure ruff in ruff.toml: enable C901
  with max-complexity=10, enable type-checking rules, set
  target Python 3.14
- [x] T005 [P] Configure mypy in pyproject.toml: strict mode,
  src-layout package discovery
- [x] T006 [P] Configure pytest in pyproject.toml: asyncio_mode
  = auto, testpaths = ["tests"]
- [x] T007 Verify project builds and empty test suite passes:
  `uv run pytest tests/ -x -q`

**Checkpoint**: Project skeleton builds, lints, and tests pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend
on. MUST be complete before any user story begins.

### Tests for Foundational

- [x] T008 [P] Write unit tests for exception hierarchy in
  tests/unit/test_exceptions.py: verify AkuvoxError base,
  all 7 subtypes inherit correctly, each has message attr,
  repr is actionable (FR-006, SC-002)
- [x] T009 [P] Write unit tests for AuthConfig and AuthMethod
  in tests/unit/test_auth.py: NONE/ALLOWLIST reject creds,
  BASIC/DIGEST require both username and password, Token
  value rejected (FR-002, data-model.md validation rules)
- [x] T010 [P] Write unit tests for response envelope parsing
  in tests/unit/test_http.py: retcode 0 returns data,
  retcode != 0 raises AkuvoxDeviceError, non-JSON raises
  AkuvoxParseError, HTTP 401 raises AkuvoxAuthenticationError,
  HTTP 400 raises AkuvoxRequestError, connection timeout
  raises AkuvoxConnectionError, "x-200 Api unsupported"
  retcode raises AkuvoxUnsupportedError (FR-011), two
  concurrent requests serialize via Lock (FR-010) (R6)
- [x] T011 [P] Write unit tests for all data models in
  tests/unit/test_models.py: DeviceInfo, DeviceStatus, Relay
  field mapping from PascalCase API to snake_case Python,
  required fields, optional fields default to None

### Implementation for Foundational

- [x] T012 [P] Implement exception hierarchy in
  src/pylocal_akuvox/exceptions.py: AkuvoxError base with
  7 subtypes per data-model.md Exception Hierarchy section
- [x] T013 [P] Implement AuthConfig dataclass and AuthMethod
  enum in src/pylocal_akuvox/auth.py: validation in
  `__post_init__`, NONE/ALLOWLIST/BASIC/DIGEST values, Token
  excluded (FR-002, R3)
- [x] T014 [P] Implement core data models as frozen dataclasses
  in src/pylocal_akuvox/models.py: DeviceInfo, DeviceStatus,
  Relay with from_api_response class methods for PascalCase
  to snake_case mapping (data-model.md)
- [x] T015 Implement internal HTTP client wrapper in
  src/pylocal_akuvox/_http.py: aiohttp.ClientSession lifecycle,
  asyncio.Lock for request serialization (FR-010, R5),
  text/plain content-type for POST (R1), response envelope
  parsing with exception mapping (R6), configurable timeout
  default 10s (FR-007)
- [x] T016 Update src/pylocal_akuvox/`__init__`.py with public
  re-exports: AkuvoxDevice, AuthConfig, AuthMethod, all
  exception types, all model types
- [x] T017 Verify all foundational tests pass:
  `uv run pytest tests/unit/ -x -q`

**Checkpoint**: Foundation ready — exception hierarchy, auth
config, models, and HTTP client all tested and working.
User story implementation can now begin.

---

## Phase 3: User Story 1 — Connect to Device (P1)

**Goal**: Developer connects to an Akuvox device by IP and
retrieves device info (model, firmware, MAC). AllowList auth
assumed for MVP. (FR-001, FR-003, FR-009, SC-001, SC-005)

**Independent Test**: Instantiate AkuvoxDevice with a mock
device address, call get_info(), verify DeviceInfo fields.

### Tests for User Story 1

- [x] T018 [P] [US1] Write unit tests for AkuvoxDevice
  connect/disconnect lifecycle in tests/unit/test_device.py:
  async context manager creates and closes session, get_info
  calls GET /api/system/info, returns DeviceInfo with model,
  firmware_version, mac_address (mock with aioresponses)
- [x] T019 [P] [US1] Write unit tests for connection error
  cases in tests/unit/test_device.py: unreachable IP raises
  AkuvoxConnectionError within timeout, HTTP 401 raises
  AkuvoxAuthenticationError, non-Akuvox response (HTML or
  missing envelope fields) raises AkuvoxParseError with raw
  response included for debugging (edge case: non-Akuvox
  device at target IP)

### Implementation for User Story 1

- [x] T020 [US1] Implement AkuvoxDevice class in
  src/pylocal_akuvox/device.py: `__init__`(host, auth=None,
  timeout=10), async context manager (`__aenter__`/`__aexit__`),
  `_http` client integration, get_info() method calling
  GET /api/system/info and returning DeviceInfo (FR-001,
  FR-003, FR-009, FR-012)
- [x] T021 [US1] Verify US1 tests pass and quickstart connect
  example works against mocked device:
  `uv run pytest tests/unit/test_device.py -x -q`

**Checkpoint**: US1 complete — AkuvoxDevice connects, retrieves
device info, handles errors. SC-001 (≤5 lines) validated.

---

## Phase 4: User Story 2 — Retrieve Device Status (P2)

**Goal**: Developer queries device status (system time and
uptime). Read-only operation validating the connection layer.
(FR-005, SC-005)

**Independent Test**: Call get_status() on a connected device,
verify DeviceStatus fields populated.

### Tests for User Story 2

- [x] T022 [P] [US2] Write unit tests for get_status in
  tests/unit/test_device.py: calls GET /api/system/status,
  returns DeviceStatus with unix_time and uptime, partial
  data returns available fields with None for missing

### Implementation for User Story 2

- [x] T023 [US2] Implement get_status() method on AkuvoxDevice
  in src/pylocal_akuvox/device.py: calls GET /api/system/status,
  returns DeviceStatus, handles partial data gracefully
- [x] T024 [US2] Verify US2 tests pass:
  `uv run pytest tests/unit/test_device.py -x -q`

**Checkpoint**: US2 complete — device status retrieval works
independently.

---

## Phase 5: User Story 3 — Manage Users and PINs (P3) 🎯 MVP

**Goal**: Full CRUD for local user accounts including PIN
programming. This is the core MVP deliverable. (FR-013, FR-014,
SC-007)

**Independent Test**: Create user with PIN, list users to verify
presence, modify PIN, delete user, verify removal.

### Tests for User Story 3

- [ ] T025 [P] [US3] Write unit tests for User model in
  tests/unit/test_models.py: User from_api_response maps all
  fields (ID, Name, UserID, PrivatePIN, CardCode, WebRelay,
  ScheduleRelay, LiftFloorNum, Type, Source, SourceType),
  snake_case attrs, optional fields default None
- [ ] T026 [P] [US3] Write unit tests for PIN validation in
  tests/unit/test_users.py: 4-8 digit PINs accepted (incl
  "0000"), <4 or >8 digits rejected, non-digit chars rejected,
  empty/None PIN allowed (optional field), schedule_relay
  format validated as `NNN-NNN;` pattern (data-model.md)
- [ ] T027 [P] [US3] Write unit tests for user CRUD operations
  in tests/unit/test_users.py: add_user POSTs to
  /api/user/add with required fields (Name, UserID, WebRelay,
  ScheduleRelay, LiftFloorNum), list_users POSTs to
  /api/user/get and paginates, modify_user POSTs to
  /api/user/set with ID, delete_user POSTs to /api/user/del
  with ID, add_user with duplicate Name or PIN returns
  non-zero retcode mapped to AkuvoxRequestError (edge case:
  duplicate user conflict) (mock with aioresponses)

### Implementation for User Story 3

- [ ] T028 [US3] Add User model to src/pylocal_akuvox/models.py:
  all fields from data-model.md User entity, from_api_response
  class method, to_api_payload for add/set operations
- [ ] T029 [US3] Implement user operations module in
  src/pylocal_akuvox/users.py: validate_pin (4-8 digits),
  validate_schedule_relay (`NNN-NNN;` pattern), add_user,
  list_users (with pagination helper), modify_user, delete_user
  — all using `_http` client (FR-013, FR-014, R4, R7)
- [ ] T030 [US3] Wire user methods onto AkuvoxDevice in
  src/pylocal_akuvox/device.py: add_user, list_users,
  modify_user, delete_user delegating to users module
- [ ] T031 [US3] Verify US3 tests pass and quickstart user
  management example works:
  `uv run pytest tests/unit/test_users.py -x -q`

**Checkpoint**: US3 (MVP) complete — full user CRUD with PIN
validation. SC-007 (≤10 lines) validated.

---

## Phase 6: User Story 4 — Control Door Relays (P4)

**Goal**: Trigger a relay by number to unlock a door/gate.
Return success confirmation. (FR-004, SC-009)

**Independent Test**: Call trigger_relay with a valid relay
number, verify success confirmation returned.

### Tests for User Story 4

- [ ] T032 [P] [US4] Write unit tests for relay operations in
  tests/unit/test_relay.py: trigger_relay POSTs to
  /api/relay/trig with num, mode, level, delay params,
  get_relay_status GETs /api/relay/status, invalid relay
  number raises AkuvoxRequestError, connection loss during
  trigger raises AkuvoxConnectionError

### Implementation for User Story 4

- [ ] T033 [US4] Implement relay operations module in
  src/pylocal_akuvox/relay.py: trigger_relay(num, mode=0,
  level=0, delay=0), get_relay_status() — all using `_http`
  client (FR-004, R4, data-model.md Relay/Trigger params)
- [ ] T034 [US4] Wire relay methods onto AkuvoxDevice in
  src/pylocal_akuvox/device.py: trigger_relay, get_relay_status
  delegating to relay module
- [ ] T035 [US4] Verify US4 tests pass:
  `uv run pytest tests/unit/test_relay.py -x -q`

**Checkpoint**: US4 complete — relay triggering works
independently. SC-009 (<1s confirmation) validated via mock.

---

## Phase 7: User Story 5 — Manage Access Schedules (P5)

**Goal**: Full CRUD for access schedules with time-based rules.
(FR-015, SC-010)

**Independent Test**: Create schedule with time ranges, list
to verify, modify time ranges, delete, verify removal.

### Tests for User Story 5

- [ ] T036 [P] [US5] Write unit tests for AccessSchedule model
  in tests/unit/test_models.py: from_api_response maps all
  fields (ID, Name, Type, DateStart, DateEnd, TimeStart,
  TimeEnd, Week, Daily, DisplayID, SourceType, Mode),
  individual day fields (Sun-Sat) mapped if present in API
  response alongside Week string
- [ ] T037 [P] [US5] Write unit tests for schedule validation
  and CRUD in tests/unit/test_schedules.py: type must be 0/1/2,
  time format HH:MM validated, date format YYYYMMDD validated,
  week codes 0-6 validated, add/list/modify/delete operations
  hit correct endpoints (R4, R8)

### Implementation for User Story 5

- [ ] T038 [US5] Add AccessSchedule model to
  src/pylocal_akuvox/models.py: all fields from data-model.md,
  from_api_response, to_api_payload
- [ ] T039 [US5] Implement schedule operations module in
  src/pylocal_akuvox/schedules.py: validation functions,
  add_schedule, list_schedules (paginated), modify_schedule,
  delete_schedule — using `_http` client (FR-015, R4, R8)
- [ ] T040 [US5] Wire schedule methods onto AkuvoxDevice in
  src/pylocal_akuvox/device.py: add_schedule, list_schedules,
  modify_schedule, delete_schedule
- [ ] T041 [US5] Verify US5 tests pass:
  `uv run pytest tests/unit/test_schedules.py -x -q`

**Checkpoint**: US5 complete — schedule CRUD works
independently. SC-010 (≤10 lines) validated.

---

## Phase 8: User Story 6 — Retrieve Call and Door Logs (P6)

**Goal**: Retrieve structured call logs and door access logs
with timestamps. (FR-016, FR-017, SC-008)

**Independent Test**: Request call and door logs, verify
structured entries with expected fields. Empty log returns
empty list.

### Tests for User Story 6

- [ ] T042 [P] [US6] Write unit tests for log entry models in
  tests/unit/test_models.py: DoorLogEntry and CallLogEntry
  from_api_response, field mapping (Type→door_type/call_type,
  Num→count, Status values Succ/Failed, call_type values
  Dialed/Received/Missed/Forwarded/Unknow)
- [ ] T043 [P] [US6] Write unit tests for log retrieval in
  tests/unit/test_logs.py: get_door_logs POSTs to
  /api/doorlog/get with pagination, get_call_logs POSTs to
  /api/calllog/get with pagination, empty device returns
  empty list not error, truncated log (total count exceeds
  returned entries) indicated in response metadata (edge
  case: log storage capacity) (R4, R9)

### Implementation for User Story 6

- [ ] T044 [US6] Add DoorLogEntry and CallLogEntry models to
  src/pylocal_akuvox/models.py: all fields from data-model.md,
  from_api_response class methods
- [ ] T045 [US6] Implement log retrieval module in
  src/pylocal_akuvox/logs.py: get_door_logs(page=None),
  get_call_logs(page=None) with pagination helper — using
  `_http` client (FR-016, FR-017, R4, R9)
- [ ] T046 [US6] Wire log methods onto AkuvoxDevice in
  src/pylocal_akuvox/device.py: get_door_logs, get_call_logs
- [ ] T047 [US6] Verify US6 tests pass:
  `uv run pytest tests/unit/test_logs.py -x -q`

**Checkpoint**: US6 complete — log retrieval works
independently. SC-008 (structured entries) validated.

---

## Phase 9: User Story 7 — Auth Methods (P7)

**Goal**: Support all four Akuvox auth modes: None, AllowList,
Basic, Digest. Token explicitly excluded. (FR-002, SC-006)

**Independent Test**: Connect with each auth mode (mocked),
verify device info returned.

### Tests for User Story 7

- [ ] T048 [P] [US7] Write unit tests for auth mode integration
  in tests/unit/test_device.py: AkuvoxDevice with
  AuthMethod.NONE sends no headers, ALLOWLIST sends no headers,
  BASIC sends Authorization header via aiohttp.BasicAuth,
  DIGEST uses aiohttp DigestAuthMiddleware, verify each mode retrieves
  device info successfully (mock with aioresponses)

### Implementation for User Story 7

- [ ] T049 [US7] Integrate auth modes into `_http` client in
  src/pylocal_akuvox/_http.py: map AuthConfig to aiohttp
  auth parameter (None→no auth, AllowList→no auth, Basic→
  aiohttp.BasicAuth, Digest→aiohttp.DigestAuthMiddleware) (R3)
- [ ] T050 [US7] Verify US7 tests pass:
  `uv run pytest tests/unit/test_device.py -x -q`

**Checkpoint**: US7 complete — all auth modes work. SC-006
validated.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements spanning multiple user stories.

- [ ] T051 [P] Add comprehensive docstrings to all public
  methods and classes per SC-004: 100% coverage verified
  by interrogate
- [ ] T052 [P] Run full lint and type check suite:
  `uv run ruff check src/ tests/` and `uv run mypy src/`,
  verify `uv tree` shows ≤2 runtime deps (FR-008, SC-003)
- [ ] T053 Validate quickstart.md examples against mocked
  device in tests/unit/test_quickstart.py: each code example
  from quickstart.md runs without error
- [ ] T054 Run full test suite and verify coverage:
  `uv run pytest tests/ -x -q --tb=short`
- [ ] T055 Update src/pylocal_akuvox/`__init__`.py `__all__` to
  export all public types for clean star-imports

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS
  all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — first story to
  implement, creates AkuvoxDevice class
- **US2 (Phase 4)**: Depends on Phase 3 (uses AkuvoxDevice)
- **US3 (Phase 5)**: Depends on Phase 3 (uses AkuvoxDevice)
- **US4 (Phase 6)**: Depends on Phase 3 (uses AkuvoxDevice)
- **US5 (Phase 7)**: Depends on Phase 3 (uses AkuvoxDevice)
- **US6 (Phase 8)**: Depends on Phase 3 (uses AkuvoxDevice)
- **US7 (Phase 9)**: Depends on Phase 2 (modifies `_http`.py)
- **Polish (Phase 10)**: Depends on all desired stories

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no other story deps
- **US2 (P2)**: After US1 (needs AkuvoxDevice class)
- **US3 (P3)**: After US1 (needs AkuvoxDevice class) —
  can run in parallel with US2
- **US4 (P4)**: After US1 — can run in parallel with
  US2, US3
- **US5 (P5)**: After US1 — can run in parallel with
  US2, US3, US4
- **US6 (P6)**: After US1 — can run in parallel with
  US2, US3, US4, US5
- **US7 (P7)**: After Phase 2 — can run in parallel
  with US1+ (modifies `_http`.py only)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before operations modules
- Operations modules before device.py wiring
- Verification after all implementation tasks

### Parallel Opportunities

**Phase 2 (Foundational)**: T008, T009, T010, T011 in
parallel (different test files); T012, T013, T014 in parallel
(different source files).

**After US1**: US2, US3, US4, US5, US6 can all start in
parallel — they each add methods to device.py but touch
different operation modules. Coordinate device.py merges.

---

## Parallel Example: User Story 3 (MVP)

```text
# Tests first (all parallel — different files):
T025: User model tests in tests/unit/test_models.py
T026: PIN validation tests in tests/unit/test_users.py
T027: User CRUD tests in tests/unit/test_users.py

# Then implement sequentially:
T028: User model in src/pylocal_akuvox/models.py
T029: User operations in src/pylocal_akuvox/users.py
T030: Wire onto AkuvoxDevice in src/pylocal_akuvox/device.py
T031: Verify all US3 tests pass
```

---

## Implementation Strategy

### MVP First (US1 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (BLOCKS all stories)
3. Complete Phase 3: US1 — Connect to Device
4. Complete Phase 5: US3 — Manage Users and PINs
5. **STOP and VALIDATE**: Test MVP independently
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Connect works → First testable increment
3. US3 → User CRUD works → MVP! 🎯
4. US2 → Status queries → Dashboard support
5. US4 → Relay control → Door unlock
6. US5 → Schedules → Time-based access
7. US6 → Logs → Auditing
8. US7 → Auth modes → Broader device compat
9. Each story independently testable and deployable

---

## Summary

| Metric | Value |
| ----- | ----- |
| Total tasks | 55 |
| Setup tasks | 7 (T001–T007) |
| Foundational tasks | 10 (T008–T017) |
| US1 tasks | 4 (T018–T021) |
| US2 tasks | 3 (T022–T024) |
| US3 tasks | 7 (T025–T031) |
| US4 tasks | 4 (T032–T035) |
| US5 tasks | 6 (T036–T041) |
| US6 tasks | 6 (T042–T047) |
| US7 tasks | 3 (T048–T050) |
| Polish tasks | 5 (T051–T055) |
| Parallel opportunities | 19 tasks marked [P] |
| Suggested MVP scope | US1 + US3 (14 tasks) |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story for traceability
- Each user story is independently testable
- TDD enforced: write failing tests before implementation
- Commit after each task or logical group (Constitution V)
- Stop at any checkpoint to validate story independently
