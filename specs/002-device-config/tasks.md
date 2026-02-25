<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Device Configuration Management

**Input**: Design documents from `/specs/002-device-config/`
**Prerequisites**: plan.md, spec.md, data-model.md,
contracts/relay-config-api.yaml

**Tests**: Unit-level tests are MANDATORY per the project
constitution (Principle II: TDD). Each phase follows
red-green-refactor.

**Organization**: Tasks are grouped by user story to enable
independent implementation and testing of each story.

**Note**: T001-T012 from the original tasks (relay-only scope)
have been completed and merged in PR #39. The tasks below
replace that implementation with the correct device-wide scope
using `/api/config/get` and `DeviceConfig`.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no deps)
- **[Story]**: Which user story (US1, US2, US3) or omitted for
  shared infrastructure tasks (Phase 1, Phase 5)
- Exact file paths included in each task

---

## Phase 1: Replace RelayConfig with DeviceConfig

**Purpose**: Replace the relay-only `RelayConfig` model and
`KEY_MAP` registry with a generic `DeviceConfig` model that
wraps all device configuration keys. Fix the endpoint from
`/api/relay/get` to `/api/config/get`.

**⚠️ TDD**: Per Constitution II, write the test for each unit
of production code BEFORE implementing it. Tasks are ordered
test-first within each logical unit.

- [x] T001 Rewrite `DeviceConfig` model tests in
  `tests/unit/test_models.py`. Remove all `RelayConfig` tests.
  Test `from_api_response()` with multi-key data (use realistic
  autop-format keys), empty data, and single-key data. Test
  `to_api_payload()` round-trip. Test `keys()`, `get()`,
  `__getitem__()`, `__contains__()`, `__len__()`. Verify frozen
  behavior.
- [x] T002 Replace `RelayConfig` with `DeviceConfig` frozen
  dataclass in `src/pylocal_akuvox/models.py`. Single field:
  `data: dict[str, str]`. Add `from_api_response()` classmethod
  (stringify all values), `to_api_payload()`, `keys()`,
  `get()`, `__getitem__()`, `__contains__()`, `__len__()`.
  Remove old `RelayConfig` class entirely.
- [x] T003 Rewrite `src/pylocal_akuvox/config.py`. Remove
  `KEY_MAP`, `reverse_key_map()`, and `_REVERSE_MAP`. Replace
  `get_relay_config()` with `get_device_config()` that calls
  `http.get("/api/config/get")` and returns
  `DeviceConfig.from_api_response(data)`.
- [x] T004 Rewrite `tests/unit/test_config.py`. Remove KEY_MAP
  tests. Write `get_device_config()` function tests: mock
  `AkuvoxHttpClient.get()` with multi-key response, verify
  `DeviceConfig` returned with all keys. Test device error and
  connection error cases.
- [x] T005 Update `src/pylocal_akuvox/device.py`: replace
  `get_relay_config()` with `get_device_config()`. Update lazy
  import, return type (`DeviceConfig`), and TYPE_CHECKING
  import.
- [x] T006 Rewrite facade tests in
  `tests/unit/test_device.py`. Replace `get_relay_config` tests
  with `get_device_config` tests. Verify delegation pattern.
- [x] T007 Update `src/pylocal_akuvox/__init__.py`: replace
  `RelayConfig` with `DeviceConfig` in imports and `__all__`.
- [x] T008 Rewrite `examples/mvp_test.py` config read test.
  Print total key count, sample relay keys, sample network
  keys. Show key count by category prefix.
- [x] T009 Run full test suite
  (`uv run pytest tests/ -x -q`) and linting
  (`uv run ruff check src/ tests/`). Verify 100% coverage is
  maintained. Fix any issues.

**Checkpoint**: `DeviceConfig` model works end-to-end.
`device.get_device_config()` returns all device keys. Live device
test shows full config. No KEY_MAP, no relay-specific fields.

---

## Phase 2: User Story 2 — Update Device Configuration (P2)

**Goal**: Developer can call `device.set_device_config()` with
a dict of autop-format key-value pairs. Live device test writes
and reads back config to verify.

**Independent Test**: Connect to a device, set a config value,
then read back and verify the new value was applied.

**FR Coverage**: FR-003, FR-004, FR-005, FR-009, FR-010
**SC Coverage**: SC-002, SC-003, SC-005, SC-006

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before
> implementation**

- [x] T010 [P] [US2] Write `set_device_config()` function tests
  in `tests/unit/test_config.py`. Test: single key update,
  multiple keys update, empty dict raises
  `AkuvoxValidationError` (FR-004), negative retcode raises
  `AkuvoxDeviceError`. Verify the POST body uses
  `{"target": "config", "action": "set", "data": {...}}`
  envelope with autop-format keys (FR-009).
- [x] T011 [P] [US2] Write `AkuvoxDevice.set_device_config()`
  facade tests in `tests/unit/test_device.py`. Mock the config
  module function. Verify dict is forwarded correctly.

### Implementation for User Story 2

- [x] T012 [US2] Implement `set_device_config()` async function
  in `src/pylocal_akuvox/config.py`. Signature:
  `async def set_device_config(http: AkuvoxHttpClient,
  settings: dict[str, str]) -> None`. Validate at least one
  entry (FR-004). Build `{target, action, data}` envelope.
  Call `http.post("/api/config/set", data=body)`.
- [x] T013 [US2] Add `set_device_config()` facade method to
  `src/pylocal_akuvox/device.py`. Accept `dict[str, str]`,
  delegate to `config.set_device_config()`.
- [x] T014 [US2] Update `examples/mvp_test.py` to add a device
  config write test in the write-tests section (gated by
  `--write` flag). Write a value, read it back, verify the
  change. Follow existing write-test patterns.
- [x] T015 [US2] Run full test suite and linting. Verify 100%
  coverage maintained. Fix any issues.

**Checkpoint**: User Stories 1 AND 2 complete. Read and write
operations work independently. Live device test verifies
round-trip.

---

## Phase 3: User Story 3 — Discover Config Keys (P3)

**Goal**: Developer can inspect a `DeviceConfig` object to
discover all available configuration keys. Documentation is
complete.

**Independent Test**: Connect to a device, retrieve device
config, verify all available key names are accessible.

**FR Coverage**: FR-010, FR-011
**SC Coverage**: SC-006, SC-007

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T016 [P] [US3] Write key discovery-specific tests in
  `tests/unit/test_config.py`. Test that keys from a large
  config response can be grouped by category prefix, that
  specific relay/network keys are discoverable.

### Implementation for User Story 3

- [ ] T017 [US3] Verify `DeviceConfig.keys()` works correctly
  with realistic multi-category data. Ensure docstring explains
  the return value.
- [ ] T018 [US3] Update `examples/mvp_test.py` to add a key
  discovery test in the read-tests section. Print key count by
  category, list all unique category prefixes.
- [ ] T019 [US3] Update Sphinx API documentation in
  `docs/source/` for the updated `config` module, `DeviceConfig`
  model, and device facade methods. Remove references to
  `RelayConfig`.
- [ ] T020 [US3] Run full test suite and linting. Verify 100%
  coverage. Fix any issues.

**Checkpoint**: All user stories complete. Key discovery,
read, and write operations all work independently.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final quality and documentation polish.

- [ ] T021 [P] Review all new docstrings in `config.py`,
  `models.py` (DeviceConfig), and `device.py` (new methods)
  for completeness and consistency with existing docstring
  style (SC-006). Run `uv run interrogate src/` to verify
  docstring coverage.
- [ ] T022 [P] Run `uv run mypy src/` to verify type
  annotations are complete and correct. Fix any type errors.
- [ ] T023 Validate quickstart.md examples match the final
  implementation API. Update any signatures or imports that
  changed during implementation.
- [ ] T024 Run full integration verification: all tests pass,
  100% coverage, linting clean, mypy clean, docs build.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Replace RelayConfig)**: No dependencies — start
  immediately. Corrects the relay-only mistake from PR #39.
- **Phase 2 (US2)**: Depends on Phase 1 for DeviceConfig model
- **Phase 3 (US3)**: Depends on Phase 1 for DeviceConfig; depends
  on Phase 2 for test script read-back verification
- **Phase 4 (Polish)**: Depends on all phases complete

### Within Each Phase

- Tests MUST be written and FAIL before implementation
  (Constitution II — NON-NEGOTIABLE)
- Module functions before device facade methods
- Device facade before test script updates
- Verify tests pass after implementation

### Parallel Opportunities

- T010 and T011 can run in parallel (different test files)
- T021 and T022 can run in parallel (independent checks)

---

## Implementation Strategy

### Corrective First (Phase 1)

1. Complete Phase 1: Replace RelayConfig → DeviceConfig (T001-T009)
2. **STOP and VALIDATE**: Test against live device
3. Proceed to Phase 2 (US2), Phase 3 (US3), Phase 4 (Polish)

### Total: 24 tasks across 4 phases
