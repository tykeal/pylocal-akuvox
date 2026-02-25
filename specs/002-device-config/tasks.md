<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Device Configuration Management

**Input**: Design documents from `/specs/002-device-config/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/relay-config-api.yaml

**Tests**: Unit-level tests are MANDATORY per the project
constitution (Principle II: TDD). Each phase follows
red-green-refactor.

**Organization**: Tasks are grouped by user story to enable
independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no deps)
- **[Story]**: Which user story (US1, US2, US3)
- Exact file paths included in each task

---

## Phase 1: Setup & Foundation (Shared Infrastructure)

**Purpose**: Create the new module skeleton, key mapping registry,
and foundational unit tests. All user stories depend on this phase.

**⚠️ TDD**: Per Constitution II, write the test for each unit of
production code BEFORE implementing it. Tasks are ordered
test-first within each logical unit.

- [ ] T001 Write KEY_MAP unit tests in
  `tests/unit/test_config.py` (new file, SPDX header). Test
  that KEY_MAP contains all expected keys, that reverse lookup
  works, and that KEY_MAP values match the autop-format pattern
  `Config.DoorSetting.RELAY.*`.
- [ ] T002 Create `src/pylocal_akuvox/config.py` with module
  docstring, SPDX header, KEY_MAP registry mapping snake_case
  attribute names to autop-format keys
  (`Config.DoorSetting.RELAY.*`), and reverse-lookup helper.
  Include known keys: `hold_delay_a`, `trig_delay_a`,
  `relay_name_a`, `hold_delay_b`, `trig_delay_b`,
  `relay_name_b`. Follow the pattern in
  `src/pylocal_akuvox/relay.py` for imports and TYPE_CHECKING
  guard.
- [ ] T003 Write `RelayConfig` model unit tests in
  `tests/unit/test_models.py`. Test `from_api_response()` with
  full data, partial data (relay B missing), extra unknown keys,
  and empty data. Test `to_api_payload()` round-trip. Test
  `keys()` returns correct autop-format key names. Follow
  existing test patterns in the file.
- [ ] T004 Add `RelayConfig` frozen dataclass to
  `src/pylocal_akuvox/models.py`. Fields: `hold_delay_a` (str),
  `trig_delay_a` (str), `relay_name_a` (str), `hold_delay_b`
  (str | None), `trig_delay_b` (str | None), `relay_name_b`
  (str | None), `extra` (dict[str, str] | None). Add
  `from_api_response()` classmethod that maps autop-format keys
  to snake_case attributes using `KEY_MAP` from `config.py`.
  Store unrecognized keys in `extra`. Add `to_api_payload()`
  instance method returning `dict[str, str]` (snake_case →
  autop-format) following the `User`/`AccessSchedule` pattern.
  Add `keys()` instance method returning list of autop-format
  key names present in this config (FR-011).
- [ ] T005 Export `RelayConfig` from
  `src/pylocal_akuvox/__init__.py`: add to import block and
  `__all__` list, maintaining alphabetical order.
- [ ] T006 Run `uv run pytest tests/ -x -q` and
  `uv run ruff check src/ tests/` to verify all tests pass and
  linting is clean. Fix any issues.

**Checkpoint**: Module skeleton exists with passing tests.
`RelayConfig` can be instantiated and serialized. No device
communication yet.

---

## Phase 2: User Story 1 — Read Relay Configuration (P1) 🎯 MVP

**Goal**: Developer can call `device.get_relay_config()` and
receive a `RelayConfig` object. Live device test reads config
successfully.

**Independent Test**: Connect to a device, call get relay
configuration, verify known relay settings are returned with
expected structure.

**FR Coverage**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008,
FR-010
**SC Coverage**: SC-001, SC-003, SC-004, SC-005, SC-006

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T007 [P] [US1] Write `get_relay_config()` function tests
  in `tests/unit/test_config.py`. Mock `AkuvoxHttpClient.get()`
  to return a relay config envelope. Test: successful retrieval
  returns `RelayConfig`, negative retcode raises
  `AkuvoxDeviceError` (handled by `_http.py`), connection
  failure raises `AkuvoxConnectionError`. Use `aioresponses`
  pattern from existing tests (e.g., `test_relay.py`).
- [ ] T008 [P] [US1] Write `AkuvoxDevice.get_relay_config()`
  facade tests in `tests/unit/test_device.py`. Mock the config
  module function. Verify delegation pattern matches existing
  facade methods (e.g., `get_info`, `get_status`).

### Implementation for User Story 1

- [ ] T009 [US1] Implement `get_relay_config()` async function
  in `src/pylocal_akuvox/config.py`. Signature:
  `async def get_relay_config(http: AkuvoxHttpClient) ->
  RelayConfig`. Call `http.get("/api/relay/get")` and parse
  with `RelayConfig.from_api_response()`. Follow the pattern
  in `relay.py:get_relay_status()`.
- [ ] T010 [US1] Add `get_relay_config()` facade method to
  `src/pylocal_akuvox/device.py`. Use lazy import
  (`from pylocal_akuvox import config`) inside the method body,
  matching the existing pattern for `users`, `logs`, etc.
  Return type: `RelayConfig`. Add TYPE_CHECKING import for
  `RelayConfig`.
- [ ] T011 [US1] Update `examples/mvp_test.py` to add a relay
  config read test in the read-tests section. Print all relay
  config fields. Follow the existing test function pattern
  (async function, pass/fail tracking, error handling).
- [ ] T012 [US1] Run full test suite
  (`uv run pytest tests/ -x -q`) and linting
  (`uv run ruff check src/ tests/`). Verify 100% coverage is
  maintained. Fix any issues.

**Checkpoint**: User Story 1 complete. `device.get_relay_config()`
works end-to-end. Live device test reads config successfully.

---

## Phase 3: User Story 2 — Update Relay Configuration (P2)

**Goal**: Developer can call `device.set_relay_config()` with
key-value pairs. Live device test writes and reads back config
to verify.

**Independent Test**: Connect to a device, set a relay config
value, then read back and verify the new value was applied.

**FR Coverage**: FR-003, FR-004, FR-005, FR-009, FR-010
**SC Coverage**: SC-002, SC-003, SC-005, SC-006

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T013 [P] [US2] Write `set_relay_config()` function tests
  in `tests/unit/test_config.py`. Test: single key update,
  multiple keys update, empty kwargs raises
  `AkuvoxValidationError` (FR-004), unknown key raises
  `AkuvoxValidationError`, negative retcode raises
  `AkuvoxDeviceError`. Verify the POST body uses
  `{"target": "relay", "action": "set", "data": {...}}`
  envelope with autop-format keys (FR-009).
- [ ] T014 [P] [US2] Write `AkuvoxDevice.set_relay_config()`
  facade tests in `tests/unit/test_device.py`. Mock the config
  module function. Verify kwargs are forwarded correctly.

### Implementation for User Story 2

- [ ] T015 [US2] Implement `set_relay_config()` async function
  in `src/pylocal_akuvox/config.py`. Signature:
  `async def set_relay_config(http: AkuvoxHttpClient,
  **kwargs: str) -> None`. Validate at least one kwarg
  (FR-004). Validate all keys exist in KEY_MAP. Build
  `{target, action, data}` envelope with autop-format keys.
  Call `http.post("/api/relay/set", data=body)`.
- [ ] T016 [US2] Add `set_relay_config()` facade method to
  `src/pylocal_akuvox/device.py`. Accept `**kwargs: str`,
  delegate to `config.set_relay_config()`. Add docstring
  listing available kwargs.
- [ ] T017 [US2] Update `examples/mvp_test.py` to add a relay
  config write test in the write-tests section (gated by
  `--write` flag). Write a value, read it back, verify the
  change. Follow existing write-test patterns.
- [ ] T018 [US2] Run full test suite and linting. Verify 100%
  coverage maintained. Fix any issues.

**Checkpoint**: User Stories 1 AND 2 complete. Read and write
operations work independently. Live device test verifies
round-trip.

---

## Phase 4: User Story 3 — Discover Config Keys (P3)

**Goal**: Developer can inspect a `RelayConfig` object to
discover all available configuration keys. Documentation is
complete.

**Independent Test**: Connect to a device, retrieve relay config,
verify the returned structure exposes all available key names.

**FR Coverage**: FR-010, FR-011
**SC Coverage**: SC-006, SC-007

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T019 [P] [US3] Write key **discovery-specific** tests in
  `tests/unit/test_config.py`. Focus on US3 scenarios that
  differ from the basic T003 tests: keys returned from a
  response containing extra/unknown keys, verifying that
  autop-format keys correctly map back to supported snake_case
  `set_relay_config()` keyword arguments (via reverse `KEY_MAP`
  lookup), and empty extra dict case. Do NOT duplicate the
  basic `keys()` return-value tests already covered by T003.

### Implementation for User Story 3

- [ ] T020 [US3] Verify and refine `RelayConfig.keys()`
  implementation in `src/pylocal_akuvox/models.py`. Ensure it
  returns autop-format keys for all populated fields and includes
  extra keys. Add comprehensive docstring explaining the return
  value and its relationship to `set_relay_config()` kwargs.
- [ ] T021 [US3] Update `examples/mvp_test.py` to add a key
  discovery test in the read-tests section. Print all available
  keys from a live device response. Follow existing test
  function pattern.
- [ ] T022 [US3] Update Sphinx API documentation in
  `docs/source/` for the new `config` module, `RelayConfig`
  model, and device facade methods. Add automodule directive
  for `pylocal_akuvox.config`. Ensure `RelayConfig` appears in
  the models documentation.
- [ ] T023 [US3] Run full test suite and linting. Verify 100%
  coverage. Fix any issues.

**Checkpoint**: All user stories complete. Key discovery,
read, and write operations all work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final quality and documentation polish.

- [ ] T024 [P] Review all new docstrings in `config.py`,
  `models.py` (RelayConfig), and `device.py` (new methods)
  for completeness and consistency with existing docstring
  style (SC-006). Run `uv run interrogate src/` to verify
  docstring coverage.
- [ ] T025 [P] Run `uv run mypy src/` to verify type
  annotations are complete and correct. Fix any type errors.
- [ ] T026 Validate quickstart.md examples match the final
  implementation API. Update any signatures or imports that
  changed during implementation.
- [ ] T027 Run full integration verification: all tests pass,
  100% coverage, linting clean, mypy clean, docs build.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup & Foundation (Phase 1)**: No dependencies — can start
  immediately. Tests are interleaved with production code per
  TDD (Constitution II).
- **US1 (Phase 2)**: Depends on Phase 1
- **US2 (Phase 3)**: Depends on Phase 1 for code; depends on
  Phase 2 (US1) for test script read-back verification in
  `examples/mvp_test.py`
- **US3 (Phase 4)**: Depends on Phase 1 for code (keys() method
  created in Phase 1); depends on Phase 2 (US1) for test script
  validation with realistic device data
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories
- **US2 (P2)**: No code dependency on US1 (both use
  `config.py` independently). Test script read-back uses US1
  but is not a blocking dependency.
- **US3 (P3)**: `keys()` method exists from Phase 1. No code
  dependency on US1/US2. Documentation depends on all being
  implemented.

### Within Each Phase

- Tests MUST be written and FAIL before implementation
  (Constitution II — NON-NEGOTIABLE)
- Module functions before device facade methods
- Device facade before test script updates
- Verify tests pass after implementation

### Parallel Opportunities

- T007 and T008 can run in parallel (different test files)
- T013 and T014 can run in parallel (different test files)
- T024 and T025 can run in parallel (independent checks)

---

## Parallel Example: User Story 1

```text
# Write tests first (parallel — different files):
T007: get_relay_config() tests in tests/unit/test_config.py
T008: Device facade tests in tests/unit/test_device.py

# Then implement sequentially:
T009: get_relay_config() in src/pylocal_akuvox/config.py
T010: Facade method in src/pylocal_akuvox/device.py
T011: Test script update in examples/mvp_test.py
T012: Full test suite verification
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup & Foundation (T001-T006)
2. Complete Phase 2: User Story 1 (T007-T012)
3. **STOP and VALIDATE**: Test US1 against live device
4. Deploy/demo if ready

### Incremental Delivery

1. Setup & Foundation → Foundation ready (tests + code interleaved)
2. Add US1 → Test → Deploy (MVP!)
3. Add US2 → Test → Deploy (config write)
4. Add US3 → Test → Deploy (key discovery + docs)
5. Polish → Final release

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each story is independently completable and testable
- TDD: Write tests, verify they fail, then implement
- Commit after each task or logical group (atomic commits)
- Stop at any checkpoint to validate story independently
- Total: 27 tasks across 5 phases
