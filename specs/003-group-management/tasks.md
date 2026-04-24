<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Group Management (CRUD)

**Input**: Design documents from
`/specs/003-group-management/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅,
data-model.md ✅, contracts/group-api.yaml ✅, quickstart.md ✅

**Tests**: Unit-level tests are MANDATORY per the project
constitution (Principle II: TDD). Each task that adds tests
follows the red-green-refactor cycle: write failing tests
first, then implement to make them pass.

**Organization**: Tasks are grouped by user story to enable
independent implementation and testing of each story.
User Story 5 (Device Facade) is distributed across US1–US4
as facade delegation tasks within each story phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/pylocal_akuvox/`
- **Tests**: `tests/unit/`
- **Docs**: `docs/`
- **Examples**: `examples/`

---

## Phase 1: Foundational (Group Model & Package Export)

**Purpose**: Define the `Group` frozen dataclass and export it
from the package namespace. This model is the prerequisite for
ALL user story phases.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write FIRST — must FAIL before implementation)

- [ ] T001 [P] Write Group model tests (creation with
  name+id, name-only, frozen immutability, kw_only
  enforcement, field defaults) in
  tests/unit/test_models.py
- [ ] T002 [P] Write Group.from_api_response tests (valid
  two-field parse, missing Name raises AkuvoxParseError,
  optional ID defaults to None, extra fields ignored) in
  tests/unit/test_models.py
- [ ] T003 [P] Write Group.to_api_payload tests (round-trip
  with id, round-trip without id omits ID key, Name always
  present) in tests/unit/test_models.py
- [ ] T004 [P] Write Group export test (Group importable
  from pylocal_akuvox, Group in \_\_all\_\_) in
  tests/unit/test_init.py

### Implementation (make tests PASS)

- [ ] T005 Implement Group frozen dataclass with
  from_api_response() and to_api_payload() in
  src/pylocal_akuvox/models.py
- [ ] T006 [P] Add Group to imports and \_\_all\_\_ list in
  src/pylocal_akuvox/\_\_init\_\_.py

**Checkpoint**: `Group` model is importable from
`pylocal_akuvox`, immutable, and round-trips through API
format. All T001–T004 tests pass.

---

## Phase 2: User Story 1 — List Groups from a Device (Priority: P1) 🎯 MVP

**Goal**: Retrieve groups from the device via
`GET /api/group/get`. Returns a list of `Group` objects with
pagination support. Empty collections for devices with no
groups.

**Independent Test**: Call `device.list_groups()` against
mocked HTTP responses and verify correct `Group` objects are
returned. Verify empty list for no groups. Verify
`AkuvoxParseError` for malformed responses.

**FR Coverage**: FR-001, FR-002, FR-009, FR-011, FR-012, FR-013, FR-014
**US5 Coverage**: Facade `list_groups()` delegation (SC-001 list, SC-002)

### Tests for User Story 1 (TDD — write FIRST, must FAIL)

- [ ] T007 [P] [US1] Write list_groups tests (populated
  response with multiple groups, empty item list returns
  empty collection, paginated request passes page param,
  malformed item missing Name raises AkuvoxParseError,
  non-list item field returns empty list, single group
  response) in tests/unit/test_groups.py
- [ ] T008 [P] [US1] Write facade list_groups delegation
  test (device.list_groups() delegates to
  groups.list_groups with correct http client and page
  param) in tests/unit/test_device.py

### Implementation for User Story 1

- [ ] T009 [US1] Create groups.py module with list_groups()
  async function (GET /api/group/get, parse data.item
  array, optional page param, defensive non-list handling)
  in src/pylocal_akuvox/groups.py
- [ ] T010 [US1] Add list_groups() facade method with lazy
  import and Group TYPE_CHECKING import to
  src/pylocal_akuvox/device.py

**Checkpoint**: `device.list_groups()` returns `list[Group]`
from mocked responses. All T007–T008 tests pass. US1 is
independently testable.

---

## Phase 3: User Story 2 — Add a New Group (Priority: P2)

**Goal**: Create a new group on the device via
`POST /api/group/add`. Client-side validation rejects empty
names before any network request. Device assigns the
internal ID.

**Independent Test**: Call `device.add_group(name="Staff")`
and verify correct POST body sent to `/api/group/add`.
Verify `AkuvoxValidationError` for empty name without any
HTTP call.

**FR Coverage**: FR-003, FR-004, FR-008, FR-011
**US5 Coverage**: Facade `add_group()` delegation (SC-001 add, SC-004)

### Tests for User Story 2 (TDD — write FIRST, must FAIL)

- [ ] T011 [P] [US2] Write add_group tests (successful add
  sends correct envelope to /api/group/add, empty name
  raises AkuvoxValidationError before HTTP, None name
  raises AkuvoxValidationError, device error response
  propagates AkuvoxDeviceError) in
  tests/unit/test_groups.py
- [ ] T012 [P] [US2] Write facade add_group delegation test
  (device.add_group() delegates to groups.add_group with
  correct http client and name kwarg) in
  tests/unit/test_device.py

### Implementation for User Story 2

- [ ] T013 [US2] Implement _mutation_body() private helper
  (target="group", action param, single-item data
  envelope) and add_group() with name validation in
  src/pylocal_akuvox/groups.py
- [ ] T014 [US2] Add add_group() facade method with lazy
  import to src/pylocal_akuvox/device.py

**Checkpoint**: `device.add_group(name="Staff")` sends
correct POST. Validation errors raised before network.
All T011–T012 tests pass. US2 is independently testable.

---

## Phase 4: User Story 3 — Modify an Existing Group (Priority: P3)

**Goal**: Update a group's name via `POST /api/group/set`.
No fetch-merge-write needed (only 2 fields). Client-side
validation requires both id and non-empty name.

**Independent Test**: Call
`device.modify_group(id="1", name="New Name")` and verify
correct POST body sent to `/api/group/set`. Verify
`AkuvoxValidationError` when name is missing/empty.

**FR Coverage**: FR-005, FR-006, FR-008, FR-011
**US5 Coverage**: Facade `modify_group()` delegation (SC-001 modify, SC-004)

### Tests for User Story 3 (TDD — write FIRST, must FAIL)

- [ ] T015 [P] [US3] Write modify_group tests (successful
  modify sends ID+Name to /api/group/set, empty name
  raises AkuvoxValidationError, None name raises
  AkuvoxValidationError, device error for non-existent
  ID propagates AkuvoxDeviceError) in
  tests/unit/test_groups.py
- [ ] T016 [P] [US3] Write facade modify_group delegation
  test (device.modify_group() delegates to
  groups.modify_group with correct http client, id, and
  name kwargs) in tests/unit/test_device.py

### Implementation for User Story 3

- [ ] T017 [US3] Implement modify_group() with id and name
  validation (no fetch-merge-write, POST /api/group/set
  with full payload) in src/pylocal_akuvox/groups.py
- [ ] T018 [US3] Add modify_group() facade method with lazy
  import to src/pylocal_akuvox/device.py

**Checkpoint**: `device.modify_group(id="1", name="New")`
sends correct POST. Validation errors raised before
network. All T015–T016 tests pass. US3 is independently
testable.

---

## Phase 5: User Story 4 — Delete a Group (Priority: P4)

**Goal**: Remove a group from the device via
`POST /api/group/del`. Delete is idempotent — non-existent
IDs return success (device returns retcode 0).

**Independent Test**: Call `device.delete_group(id="1")`
and verify correct POST body sent to `/api/group/del`.
Verify no error raised for non-existent ID (idempotent).

**FR Coverage**: FR-007, FR-008, FR-011
**US5 Coverage**: Facade `delete_group()` delegation (SC-001 delete, SC-004)

### Tests for User Story 4 (TDD — write FIRST, must FAIL)

- [ ] T019 [P] [US4] Write delete_group tests (successful
  delete sends ID to /api/group/del, idempotent delete
  of non-existent ID returns success, device error
  propagation) in tests/unit/test_groups.py
- [ ] T020 [P] [US4] Write facade delete_group delegation
  test (device.delete_group() delegates to
  groups.delete_group with correct http client and id
  kwarg) in tests/unit/test_device.py

### Implementation for User Story 4

- [ ] T021 [US4] Implement delete_group() (POST
  /api/group/del with ID-only payload, no existence
  check) in src/pylocal_akuvox/groups.py
- [ ] T022 [US4] Add delete_group() facade method with lazy
  import to src/pylocal_akuvox/device.py

**Checkpoint**: `device.delete_group(id="1")` sends correct
POST. Non-existent ID deletion succeeds (idempotent).
All T019–T020 tests pass. US4 is independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, MVP test script integration,
and final validation across all user stories.

- [ ] T023 [P] Create docs/api/groups.rst autodoc page for
  pylocal_akuvox.groups module
- [ ] T024 Add groups entry to toctree in
  docs/api/index.rst
- [ ] T025 [P] Add group management section (list, add,
  modify, delete examples) to docs/quickstart.rst
- [ ] T026 Update key features list to include group
  management in docs/index.rst
- [ ] T027 Add test_list_groups() to _run_read_tests() in
  examples/mvp_test.py
- [ ] T028 Add test_add_group() and test_delete_group() to
  _run_write_tests() in examples/mvp_test.py
- [ ] T029 Add group validation checks to test_validation()
  in examples/mvp_test.py
- [ ] T030 Run quickstart.md code examples against
  implementation to validate accuracy

**Checkpoint**: Sphinx docs build cleanly with group API
reference. `mvp_test.py --write` exercises group CRUD. All
documentation examples are accurate.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — can start
  immediately. BLOCKS all user stories.
- **US1 — List (Phase 2)**: Depends on Foundational
  (Group model must exist).
- **US2 — Add (Phase 3)**: Depends on US1 (groups.py
  module must exist from T009; `_mutation_body` added
  here).
- **US3 — Modify (Phase 4)**: Depends on US2
  (`_mutation_body` helper must exist from T013).
- **US4 — Delete (Phase 5)**: Depends on US2
  (`_mutation_body` helper must exist from T013). Can
  run in parallel with US3.
- **Polish (Phase 6)**: Depends on all user stories being
  complete (US1–US4).

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only → **MVP delivery point**
- **US2 (P2)**: Depends on US1 (groups.py exists) → builds on MVP
- **US3 (P3)**: Depends on US2 (_mutation_body exists) → can parallel with US4
- **US4 (P4)**: Depends on US2 (_mutation_body exists) → can parallel with US3
- **US5 (P5)**: Distributed — facade tasks are embedded in US1–US4 phases

### Within Each User Story (TDD Order)

1. Write tests in test_groups.py — must FAIL (red)
2. Write facade test in test_device.py — must FAIL (red)
3. Implement module function in groups.py — tests pass (green)
4. Add facade method in device.py — facade test passes (green)
5. Refactor if needed (refactor)

### Parallel Opportunities

**Within Foundational (Phase 1)**:

- T001, T002, T003 can run in parallel (same file but independent test functions)
- T004 can run in parallel with T001–T003 (different file)
- T005 and T006 can run in parallel (different files)

**Within Each User Story Phase**:

- Test task (test_groups.py) and facade test task (test_device.py) can run in parallel

**Across User Stories**:

- US3 and US4 can run in parallel after US2 completes
  (both depend on _mutation_body, touch same files but
  independent functions)

**Within Polish (Phase 6)**:

- T023 and T025 can run in parallel (different files)
- T027, T028, T029 are sequential (same file: mvp_test.py)

---

## Parallel Example: User Story 1

```text
# Step 1 — Write failing tests in parallel (red):
T007: list_groups behavioral tests in tests/unit/test_groups.py
T008: facade delegation test in tests/unit/test_device.py

# Step 2 — Implement (green):
T009: Create groups.py with list_groups() → T007 tests pass
T010: Add facade method to device.py → T008 test passes
```

## Parallel Example: User Stories 3 & 4 (after US2 completes)

```text
# Developer A: US3 (Modify)         # Developer B: US4 (Delete)
T015: modify tests (test_groups.py)  T019: delete tests (test_groups.py)
T016: facade test (test_device.py)   T020: facade test (test_device.py)
T017: modify_group() (groups.py)     T021: delete_group() (groups.py)
T018: facade method (device.py)      T022: facade method (device.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (Group model + export)
2. Complete Phase 2: User Story 1 — List Groups
3. **STOP and VALIDATE**: `device.list_groups()` works end-to-end
4. Deploy/demo — developers can discover existing groups

### Incremental Delivery

1. Foundational → Group model importable from `pylocal_akuvox`
2. US1 (List) → Developers can read groups → **MVP!**
3. US2 (Add) → Developers can create groups
4. US3 (Modify) + US4 (Delete) → Full CRUD lifecycle
5. Polish → Documentation and live device test coverage
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after Foundational:

1. Team completes Foundational together
2. Developer A: US1 → US2 (sequential, builds groups.py)
3. Once US2 complete: Developer A takes US3, Developer B takes US4 (parallel)
4. Polish phase: split docs (T023–T026) and mvp_test (T027–T029)

---

## File Impact Summary

| File | Phase | Action |
| --- | --- | --- |
| `src/pylocal_akuvox/models.py` | Foundational | Add Group dataclass |
| `src/pylocal_akuvox/__init__.py` | Foundational | Add Group export |
| `src/pylocal_akuvox/groups.py` | US1–US4 | **NEW**: list/add/modify/delete |
| `src/pylocal_akuvox/device.py` | US1–US4 | Add 4 facade methods + import |
| `tests/unit/test_models.py` | Foundational | Add Group model tests |
| `tests/unit/test_init.py` | Foundational | Add Group export test |
| `tests/unit/test_groups.py` | US1–US4 | **NEW**: all group operation tests |
| `tests/unit/test_device.py` | US1–US4 | Add facade delegation tests |
| `docs/api/groups.rst` | Polish | **NEW**: autodoc page |
| `docs/api/index.rst` | Polish | Add groups to toctree |
| `docs/quickstart.rst` | Polish | Add group examples |
| `docs/index.rst` | Polish | Update features list |
| `examples/mvp_test.py` | Polish | Add group read/write/validation tests |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- TDD is mandatory: every implementation task is preceded by a failing test task
- US5 (Device Facade) has no separate phase — facade tasks are embedded in US1–US4
- Groups use separate endpoints per mutation
  (`/api/group/{add,set,del}`) unlike users/schedules
  which use a single `/api/{entity}/set` endpoint
- No fetch-merge-write for modify: only 2 fields (ID + Name), send payload directly
- Delete is idempotent: non-existent ID returns success (retcode 0)
- All new code requires SPDX license headers per project conventions
- Commit after each task or logical group; DCO sign-off required
