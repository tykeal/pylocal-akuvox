<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Contact Management (CRUD with Group Membership)

**Input**: Design documents from `/specs/004-contact-management/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅,
contracts/contact-api.yaml ✅, quickstart.md ✅

**Tests**: Unit-level tests are MANDATORY per the project constitution
(Principle II: TDD). Red-Green-Refactor cycle is strictly enforced — every
test MUST fail before its corresponding implementation is written.

**Organization**: Tasks are grouped by implementation phase from plan.md.
Each phase maps to user stories from spec.md and delivers an
independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/pylocal_akuvox/`
- **Tests**: `tests/unit/`
- **Docs**: `docs/`
- **Examples**: `examples/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project initialization needed — the repository already
has full infrastructure (pyproject.toml, ruff, mypy, pytest, pre-commit).
This phase establishes the new source and test files with SPDX headers.

- [ ] T001 Create empty `src/pylocal_akuvox/contacts.py` with SPDX header
  and module docstring
- [ ] T002 [P] Create empty `tests/unit/test_contacts.py` with SPDX header
  and module docstring

**Checkpoint**: Two new files exist with correct SPDX headers. Pre-commit
hooks pass. No logic yet.

---

## Phase 2: User Story 1 — List Contacts from a Device (Priority: P1) 🎯 MVP

**Goal**: Define the `Contact` frozen dataclass and implement
`list_contacts()` so a developer can retrieve address book entries from
the device. This is the foundation for all other contact operations.

**Independent Test**: Call `device.list_contacts()` and receive a list of
`Contact` objects. Malformed responses raise `AkuvoxParseError`. Empty
devices return an empty list.

**FR Coverage**: FR-001, FR-002, FR-014, FR-016, FR-017, FR-018, FR-019
**SC Coverage**: SC-001 (list), SC-002 (list), SC-003, SC-005

### Tests for User Story 1 (TDD Red Phase) 🔴

> **Write these tests FIRST. Ensure they FAIL before implementing.**

- [ ] T003 [P] [US1] Add Contact model tests to
  `tests/unit/test_models.py`: creation with all fields, creation with
  name only (defaults: id=None, phone="", group="Default"), frozen
  immutability, kw_only enforcement
- [ ] T004 [P] [US1] Add Contact `from_api_response()` tests to
  `tests/unit/test_models.py`: valid full response, valid name-only
  response (optional defaults), missing Name raises `AkuvoxParseError`,
  extra fields ignored
- [ ] T005 [P] [US1] Add Contact `to_api_payload()` tests to
  `tests/unit/test_models.py`: with ID present, without ID (None
  omitted), Phone and Group always included, round-trip consistency
- [ ] T006 [P] [US1] Add Contact export tests to
  `tests/unit/test_init.py`: `Contact` in `__all__`, `Contact`
  importable from `pylocal_akuvox`
- [ ] T007 [P] [US1] Add `list_contacts()` tests to
  `tests/unit/test_contacts.py`: populated response returns Contact list,
  empty response returns empty list, paginated request passes `?page=N`,
  malformed item (missing Name) raises `AkuvoxParseError`, non-list item
  field returns empty list
- [ ] T008 [US1] Add `list_contacts` facade delegation test to
  `tests/unit/test_contacts.py`: `device.list_contacts()` delegates to
  `contacts.list_contacts()` and returns Contact list

### Implementation for User Story 1 (TDD Green Phase) 🟢

- [ ] T009 [US1] Add `Contact` frozen dataclass to
  `src/pylocal_akuvox/models.py` with fields: name (str), id (str | None
  = None), phone (str = ""), group (str = "Default"); include
  `from_api_response()` and `to_api_payload()` methods following the
  `User` and `Group` model patterns
- [ ] T010 [US1] Export `Contact` from `src/pylocal_akuvox/__init__.py`:
  add import, add to `__all__` list (alphabetical order)
- [ ] T011 [US1] Implement `list_contacts()` and `_mutation_body()`
  helper in `src/pylocal_akuvox/contacts.py` following the `users.py`
  pattern: GET `/api/contact/get`, optional `page` parameter, parse
  `data.item` array, defensive non-list handling
- [ ] T012 [US1] Add `list_contacts()` facade method to
  `src/pylocal_akuvox/device.py`: lazy import of `contacts` module,
  delegate to `contacts.list_contacts(self._http, page=page)`, add
  `Contact` to TYPE_CHECKING imports

**Checkpoint**: `device.list_contacts()` returns `Contact` objects. All
Phase 2 tests green. CI passes. Contact model is importable from
top-level package.

---

## Phase 3: User Story 2 — Add a New Contact (Priority: P2)

**Goal**: Implement `add_contact()` with client-side name validation and
optional phone/group parameters. Uses the `_mutation_body()` helper from
Phase 2.

**Independent Test**: Call `device.add_contact(name="Alice")` and verify
no error. Call with empty name and verify `AkuvoxValidationError` is
raised before any network request.

**FR Coverage**: FR-003, FR-004, FR-005, FR-006, FR-012, FR-013, FR-016
**SC Coverage**: SC-001 (add), SC-002, SC-004

### Tests for User Story 2 (TDD Red Phase) 🔴

- [ ] T013 [P] [US2] Add `add_contact()` tests to
  `tests/unit/test_contacts.py`: success with name only (verify mutation
  envelope: target="contact", action="add"), success with name + phone +
  group, empty name raises `AkuvoxValidationError` before network request,
  device error propagation
- [ ] T014 [US2] Add `add_contact` facade delegation test to
  `tests/unit/test_contacts.py`: `device.add_contact(name=..., phone=...,
  group=...)` delegates to `contacts.add_contact()`

### Implementation for User Story 2 (TDD Green Phase) 🟢

- [ ] T015 [US2] Implement `add_contact()` in
  `src/pylocal_akuvox/contacts.py`: validate non-empty name, build payload
  dict (Name required; Phone, Group optional — omit if None), POST via
  `_mutation_body("add", payload)` to `/api/contact/set`
- [ ] T016 [US2] Add `add_contact()` facade method to
  `src/pylocal_akuvox/device.py`: keyword-only params name (str), phone
  (str | None = None), group (str | None = None)

**Checkpoint**: `device.add_contact(name="Alice")` works. Validation errors
raised client-side. All Phase 3 tests green. CI passes.

---

## Phase 4: User Story 3 — Modify an Existing Contact (Priority: P3)

**Goal**: Implement `modify_contact()` with fetch-merge-write pattern
(matching `modify_user()` in users.py) and the `_get_contact_by_id()`
private helper. This enables group membership management via
`modify_contact(id=..., group="Staff")`.

**Independent Test**: Modify a known contact's group and verify the
updated group appears in a subsequent list call. Verify the mutation
envelope includes all fields (fetch-merge-write preserves Name).

**FR Coverage**: FR-007, FR-008, FR-009, FR-012, FR-013, FR-016
**SC Coverage**: SC-001 (modify), SC-002, SC-004, SC-006, SC-007

### Tests for User Story 3 (TDD Red Phase) 🔴

- [ ] T017 [P] [US3] Add `_get_contact_by_id()` tests to
  `tests/unit/test_contacts.py`: found on first page, found on second
  page (pagination iteration), not found raises `AkuvoxDeviceError`,
  handles non-list item gracefully
- [ ] T018 [P] [US3] Add `modify_contact()` tests to
  `tests/unit/test_contacts.py`: name change (verify fetch-merge-write
  envelope includes all fields), group change (verify group membership
  update), phone change, multi-field update, non-existent ID raises
  `AkuvoxDeviceError`, no fields to change raises `AkuvoxValidationError`
- [ ] T019 [US3] Add `modify_contact` facade delegation test to
  `tests/unit/test_contacts.py`: `device.modify_contact(id=..., name=...,
  group=...)` delegates to `contacts.modify_contact()`

### Implementation for User Story 3 (TDD Green Phase) 🟢

- [ ] T020 [US3] Implement `_get_contact_by_id()` private helper in
  `src/pylocal_akuvox/contacts.py`: iterate pages via GET
  `/api/contact/get?page=N`, match on `item.get("ID") == internal_id`,
  raise `AkuvoxDeviceError` if not found after all pages exhausted (follow
  `_get_user_by_id()` pattern in users.py)
- [ ] T021 [US3] Implement `modify_contact()` in
  `src/pylocal_akuvox/contacts.py`: validate at least one of
  name/phone/group provided, fetch current record via
  `_get_contact_by_id()`, merge caller fields into fetched dict, POST via
  `_mutation_body("set", merged)` to `/api/contact/set`
- [ ] T022 [US3] Add `modify_contact()` facade method to
  `src/pylocal_akuvox/device.py`: keyword-only params id (str), name
  (str | None = None), phone (str | None = None), group (str | None =
  None)

**Checkpoint**: `device.modify_contact(id="1", group="Staff")` works.
Fetch-merge-write ensures Name is always present. Group membership changes
work via single modify call. All Phase 4 tests green. CI passes.

---

## Phase 5: User Story 4 — Delete a Contact (Priority: P4)

**Goal**: Implement `delete_contact()` supporting single and batch deletion.
Delete is NOT idempotent — non-existent IDs raise `AkuvoxDeviceError`.

**Independent Test**: Delete a known contact by ID and verify it no longer
appears in list results. Verify batch delete sends multiple items in a
single request.

**FR Coverage**: FR-010, FR-011, FR-012, FR-013, FR-016
**SC Coverage**: SC-001 (delete), SC-002, SC-004

### Tests for User Story 4 (TDD Red Phase) 🔴

- [ ] T023 [P] [US4] Add `delete_contact()` tests to
  `tests/unit/test_contacts.py`: single delete success (verify mutation
  envelope: target="contact", action="del", item=[{"ID": "1"}]), batch
  delete success (verify multiple items in single request), non-existent ID
  propagates device error
- [ ] T024 [US4] Add `delete_contact` facade delegation test to
  `tests/unit/test_contacts.py`: `device.delete_contact(id="1")` and
  `device.delete_contact(id=["1","2"])` delegate to
  `contacts.delete_contact()`

### Implementation for User Story 4 (TDD Green Phase) 🟢

- [ ] T025 [US4] Implement `delete_contact()` in
  `src/pylocal_akuvox/contacts.py`: accept `id: str | list[str]`, normalize
  single ID to list, build item array `[{"ID": x} for x in ids]`, POST via
  `_mutation_body("del", ...)` to `/api/contact/set` (note: `_mutation_body`
  may need adjustment to accept list of items for batch; update helper
  signature if needed)
- [ ] T026 [US4] Add `delete_contact()` facade method to
  `src/pylocal_akuvox/device.py`: keyword-only param id (str | list[str])

**Checkpoint**: `device.delete_contact(id="1")` and
`device.delete_contact(id=["1","2","3"])` work. Non-existent IDs raise
errors. All Phase 5 tests green. CI passes.

---

## Phase 6: User Story 5 — Access Contacts via the Device Facade (Priority: P5)

**Goal**: Verify the full facade integration — all four CRUD operations
work identically through the `AkuvoxDevice` facade as through the
`contacts` module directly. This phase is primarily a validation checkpoint
since facade methods were added incrementally in Phases 2–5.

**Independent Test**: Using only the `AkuvoxDevice` facade object, perform
list → add → list → modify → list → delete → list and verify each step.

**FR Coverage**: FR-015, FR-016
**SC Coverage**: SC-001 (all), SC-002

### Tests for User Story 5 (TDD Red Phase) 🔴

- [ ] T027 [US5] Add full CRUD integration test to
  `tests/unit/test_contacts.py`: using `AkuvoxDevice` facade, mock all HTTP
  calls, exercise list → add → modify → delete sequence, verify all
  operations delegate correctly and share the managed HTTP session

**Checkpoint**: Full facade CRUD integration test passes. All user story
tests green. CI passes.

---

## Phase 7: Polish & Cross-Cutting Concerns (Documentation & MVP Test Script)

**Purpose**: Complete documentation and live device test coverage per Phase 3
of plan.md.

### Documentation

- [ ] T028 [P] Create `docs/api/contacts.rst` autodoc page for
  `pylocal_akuvox.contacts` module (follow `docs/api/groups.rst` pattern)
- [ ] T029 [P] Add `contacts` entry to `docs/api/index.rst` toctree
  (alphabetical order, after `config`)
- [ ] T030 [P] Add contact management section to `docs/quickstart.rst` with
  list, add, modify, delete examples (reference
  `specs/004-contact-management/quickstart.md` for code snippets)
- [ ] T031 Update `docs/index.rst` key features list to include contacts
  (e.g., "users, groups, contacts, PINs, relays, schedules, and logs")

### MVP Test Script

- [ ] T032 Add `test_list_contacts()` to read tests section in
  `examples/mvp_test.py`: list contacts and display ID, Name, Phone, Group
  for each
- [ ] T033 Add contact write tests to `examples/mvp_test.py` under `--write`
  flag: `test_add_contact()` (add → verify in list), `test_modify_contact()`
  (modify group → verify group change), `test_delete_contact()` (delete →
  verify removal), with `_MUTATION_SETTLE_SECS` delays between operations
- [ ] T034 Add contact validation checks to `test_validation()` in
  `examples/mvp_test.py`: verify `add_contact(name="")` raises
  `AkuvoxValidationError`, verify `modify_contact(id="1")` with no fields
  raises `AkuvoxValidationError`

**Checkpoint**: `sphinx-build` succeeds with contact API reference.
`mvp_test.py --write` exercises contact CRUD against a live device. All
documentation examples are accurate. CI passes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (US1: List)**: Depends on Phase 1 — Contact model and list are
  foundation for all operations
- **Phase 3 (US2: Add)**: Depends on Phase 2 — uses `_mutation_body()` helper
  and Contact model
- **Phase 4 (US3: Modify)**: Depends on Phase 2 — uses `_mutation_body()`,
  `list_contacts()` (for `_get_contact_by_id`)
- **Phase 5 (US4: Delete)**: Depends on Phase 2 — uses `_mutation_body()` helper
- **Phase 6 (US5: Facade)**: Depends on Phases 2–5 — validates full CRUD integration
- **Phase 7 (Polish)**: Depends on Phases 2–5 — documents all operations

### User Story Dependencies

- **US1 (List)**: Foundation — no dependencies on other stories
- **US2 (Add)**: Depends on US1 for `_mutation_body()` helper (shared
  infrastructure within contacts.py)
- **US3 (Modify)**: Depends on US1 for `list_contacts()` (used by
  `_get_contact_by_id`)
- **US4 (Delete)**: Depends on US1 for `_mutation_body()` helper only. Can
  run in parallel with US2/US3
- **US5 (Facade)**: Depends on US1–US4 (validation of all operations)

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD Red)
2. Implement minimum code to make tests pass (TDD Green)
3. Refactor while keeping all tests green
4. Commit atomically with DCO sign-off and SPDX headers

### Parallel Opportunities

- **Phase 1**: T001 and T002 can run in parallel (different files)
- **Phase 2 tests**: T003, T004, T005, T006, T007 can all run in parallel
  (different test areas)
- **Phase 3 and Phase 5**: US2 (Add) and US4 (Delete) can theoretically run
  in parallel after US1 completes (both only depend on `_mutation_body`
  from US1)
- **Phase 7**: T028, T029, T030 can all run in parallel (different doc files)

---

## Parallel Example: User Story 1 (Phase 2)

```text
# Launch all model tests in parallel (different test sections):
T003: Contact model creation/frozen/kw_only tests in tests/unit/test_models.py
T004: Contact from_api_response() tests in tests/unit/test_models.py
T005: Contact to_api_payload() tests in tests/unit/test_models.py

# Launch export + list tests in parallel (different files):
T006: Contact export tests in tests/unit/test_init.py
T007: list_contacts() tests in tests/unit/test_contacts.py
```

---

## Parallel Example: Documentation (Phase 7)

```text
# Launch all doc tasks in parallel (different files):
T028: Create docs/api/contacts.rst
T029: Update docs/api/index.rst toctree
T030: Update docs/quickstart.rst with contact examples
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: US1 — Contact Model & List (T003–T012)
3. **STOP and VALIDATE**: `device.list_contacts()` works, Contact model is
   importable, all tests green
4. This delivers immediate read-only value

### Incremental Delivery

1. Phase 1 + Phase 2 → **MVP: List contacts** (US1 complete)
2. Add Phase 3 → **Add contacts** (US1 + US2 complete)
3. Add Phase 4 → **Modify contacts + group membership** (US1–US3 complete)
4. Add Phase 5 → **Delete contacts** (US1–US4 complete, full CRUD)
5. Add Phase 6 → **Facade validation** (US5 complete)
6. Add Phase 7 → **Documentation + live test script** (feature complete)

Each phase adds value without breaking previous phases.

### Commit Strategy (Atomic, per Constitution Principle V)

Each task or logical group of tasks within a phase = one atomic commit:

- TDD Red: test commit (tests fail — this is expected)
- TDD Green: implementation commit (tests pass)
- Refactor: cleanup commit (tests still pass)
- All commits: DCO sign-off (`git commit -s`), Conventional Commits format

---

## Summary

| Metric | Value |
| --- | --- |
| **Total tasks** | 34 |
| **Phase 1 (Setup)** | 2 tasks |
| **Phase 2 (US1: List)** | 10 tasks (6 test + 4 impl) |
| **Phase 3 (US2: Add)** | 4 tasks (2 test + 2 impl) |
| **Phase 4 (US3: Modify)** | 6 tasks (3 test + 3 impl) |
| **Phase 5 (US4: Delete)** | 4 tasks (2 test + 2 impl) |
| **Phase 6 (US5: Facade)** | 1 task (integration test) |
| **Phase 7 (Polish)** | 7 tasks (docs + mvp script) |
| **Parallel opportunities** | 14 tasks marked [P] |
| **New source files** | 1 (`contacts.py`) |
| **Modified source files** | 3 (`models.py`, `__init__.py`, `device.py`) |
| **New test files** | 1 (`test_contacts.py`) |
| **Modified test files** | 2 (`test_models.py`, `test_init.py`) |
| **New doc files** | 1 (`contacts.rst`) |
| **Modified doc files** | 3 (`index.rst`, `api/index.rst`, `quickstart.rst`) |
| **MVP scope** | Phase 1 + Phase 2 (US1: List Contacts) |

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- TDD is mandatory per constitution — every test MUST fail before its implementation
- Follow `users.py` single-endpoint pattern (not `groups.py` separate-endpoint pattern)
- `_mutation_body()` uses `target: "contact"` (verified in contract)
- `_get_contact_by_id()` follows `_get_user_by_id()` pagination loop pattern
- Delete accepts `str | list[str]` for batch support
- Commit after each task or logical TDD red/green pair
- Pre-commit hooks MUST pass on every commit (no `--no-verify`)
