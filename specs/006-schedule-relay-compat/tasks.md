---
description: "Task list for feature 006-schedule-relay-compat"
---

<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Schedule-Relay Field Compatibility for E18 Firmware

**Input**: Design documents from `/specs/006-schedule-relay-compat/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, quickstart.md ✅
(No `data-model.md` or `contracts/` — not applicable per plan.md.)

**Tests**: MANDATORY per constitution Principle II (TDD) and FR-008. Unit
tests are written FIRST and must FAIL before the implementation tasks
land.

**Organization**: Tasks are grouped by user story so each story can be
implemented, tested, and validated independently. US1 and US2 are both P1
(US1 is the regression fix; US2 is the backward-compatibility guarantee).
US3 (P2) locks in that secondary-relay scheduling remains out of scope.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on
  incomplete tasks).
- **[Story]**: Which user story this task belongs to (US1, US2, US3).
- Exact file paths included in every task.

## Path Conventions

Single Python package:

- Source: `src/pylocal_akuvox/`
- Tests:  `tests/unit/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project scaffolding is required — the package, lint
config, test config, and dev tooling are already in place. The only setup
step is making sure the dev environment is synced so the new tests can be
executed locally and in CI.

- [ ] T001 Sync dev dependencies via `uv sync --group dev` from the repo
      root so `pytest`, `pytest-asyncio`, and `aioresponses` are available
      for the new unit tests.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None required.

The change is confined to two existing functions in
`src/pylocal_akuvox/users.py` and their unit-test module
`tests/unit/test_users.py`. No new modules, models, framework wiring,
config, or shared infrastructure is introduced. There is therefore no
foundational phase blocking the user-story phases.

**Checkpoint**: Proceed directly to Phase 3.

---

## Phase 3: User Story 1 — Add user succeeds on E18 firmware 18.30.11.21 (Priority: P1) 🎯 MVP

**Goal**: `add_user()` and `modify_user()` emit the primary-relay access
schedule under BOTH `ScheduleRelay` (un-hyphenated, existing) AND
`Schedule-Relay` (hyphenated, new) with identical values, so that E18
firmware `18.30.11.21` accepts the request and stores the schedule.

**Independent Test**: Against an Akuvox E18 device on firmware
`18.30.11.21`, call `add_user` with a primary-relay schedule, confirm the
device returns success, and confirm a follow-up `get_user` shows the
schedule stored on the primary relay. Then call `modify_user` to change
the schedule and verify success + correct stored value (Acceptance
Scenarios 1 & 2 of US1, SC-001 & SC-003).

### Tests for User Story 1 (MANDATORY — write FIRST, must FAIL before implementation)

- [ ] T002 [P] [US1] Add failing unit test
      `test_add_user_emits_dual_primary_relay_schedule_keys` in
      `tests/unit/test_users.py` that calls `add_user(...)` with a
      non-empty `schedule_relay` value, captures the outgoing HTTP request
      payload (via the existing mocked HTTP client pattern in that file),
      and asserts `item[0]["ScheduleRelay"] == item[0]["Schedule-Relay"]
      == <provided value>` and that both keys are present. This satisfies
      FR-001 and the first half of FR-008.

- [ ] T003 [P] [US1] Add failing unit test
      `test_modify_user_emits_dual_primary_relay_schedule_keys` in
      `tests/unit/test_users.py` that calls `modify_user(...)` with a new
      `schedule_relay` value, captures the outgoing payload, and asserts
      both `ScheduleRelay` and `Schedule-Relay` appear in `item[0]` with
      values equal to the new schedule. This satisfies FR-002 and the
      second half of FR-008.

- [ ] T004 [US1] Run `uv run pytest tests/unit/test_users.py -v` and
      confirm T002 and T003 FAIL (red phase) before any implementation in
      `src/pylocal_akuvox/users.py` begins. Record the failure mode in
      the commit message of the test commit per constitution Principle II.

### Implementation for User Story 1

- [ ] T005 [US1] In `src/pylocal_akuvox/users.py`, modify `add_user()`
      (around the existing `"ScheduleRelay": schedule_relay,` line near
      L87) so the outgoing `item` dict ALSO contains
      `"Schedule-Relay": schedule_relay` with the same value, emitted
      unconditionally (no firmware probing, per FR-006). Do NOT add
      `ScheduleSRelay` or any `Schedule-SRelay` key (FR-003).

- [ ] T006 [US1] In `src/pylocal_akuvox/users.py`, modify `modify_user()`
      (around the existing `current["ScheduleRelay"] = schedule_relay`
      assignment near L175) so it ALSO assigns
      `current["Schedule-Relay"] = schedule_relay` with the same value,
      whenever the primary-relay schedule is part of the update. Ensure
      both keys are set together so the two variants can never carry
      conflicting values (FR-007). Do NOT add any `Schedule-SRelay` key.

- [ ] T007 [US1] Update the docstrings of `add_user()` and
      `modify_user()` in `src/pylocal_akuvox/users.py` to note that the
      primary-relay schedule is emitted under both `ScheduleRelay` and
      `Schedule-Relay` for cross-firmware compatibility (E18 18.30.11.21
      and older firmwares), and that this is an internal request-shaping
      detail with no impact on the public Python API (FR-005).

- [ ] T008 [US1] Run `uv run pytest tests/unit/test_users.py -v` and
      confirm T002 and T003 now PASS (green phase) and no previously
      passing test in that module has regressed.

**Checkpoint**: US1 is fully functional and independently verifiable on
real E18 hardware via the quickstart manual steps.

---

## Phase 4: User Story 2 — Existing firmwares continue to work unchanged (Priority: P1)

**Goal**: Lock in that the dual-write change does NOT alter observable
behavior on previously supported firmwares (e.g., X916 on `916.30.10.114`)
— same success/failure results, same stored schedule values, same
response-parsing path, no public API change.

**Independent Test**: Against any previously supported firmware, run the
existing `add_user` and `modify_user` flows with a primary-relay schedule
and confirm identical success results and stored schedule values vs. the
prior library release; confirm a subsequent read reports the schedule
under the un-hyphenated field name (Acceptance Scenarios 1 & 2 of US2,
SC-002, SC-005).

### Tests for User Story 2 (MANDATORY)

- [ ] T009 [P] [US2] Add unit test
      `test_add_user_preserves_existing_un_hyphenated_field` in
      `tests/unit/test_users.py` asserting that `add_user`'s outgoing
      `item[0]` still contains the existing `ScheduleRelay` key with the
      caller-provided value (i.e., the legacy field name is NOT removed
      or renamed). Covers SC-002 / US2 Acceptance Scenario 1 at the
      payload boundary.

- [ ] T010 [P] [US2] Add unit test
      `test_modify_user_preserves_existing_un_hyphenated_field` in
      `tests/unit/test_users.py` asserting the same invariant for
      `modify_user`'s outgoing payload.

- [ ] T011 [P] [US2] Add unit test
      `test_response_parsing_reads_un_hyphenated_primary_schedule` in
      `tests/unit/test_users.py` that stubs a `get_user` (or equivalent
      read) response carrying the primary-relay schedule under
      `ScheduleRelay` only, and asserts the library exposes that value
      unchanged to the caller. Covers FR-004 and US2 Acceptance Scenario
      2. If an equivalent test already exists, extend it with an explicit
      assertion that no hyphenated read-path was introduced.

### Implementation for User Story 2

- [ ] T012 [US2] Verify (no code change) that the public function
      signatures, parameter names, parameter types, and return shapes of
      `add_user()` and `modify_user()` in
      `src/pylocal_akuvox/users.py` are unchanged from the prior release
      (FR-005). Document this in the PR description.

- [ ] T013 [US2] Run `uv run pytest -v` for the full unit suite and
      confirm zero regressions in any existing test in
      `tests/unit/test_users.py` or elsewhere; investigate and fix any
      failure before proceeding.

**Checkpoint**: US1 (E18 fix) and US2 (backward compat) both pass
independently; the library is safe to release for every previously
supported firmware.

---

## Phase 5: User Story 3 — Secondary relay remains out of scope (Priority: P2)

**Goal**: Guarantee that the primary-relay dual-write pattern does not add
secondary-relay scheduling support. The current public API has no secondary
schedule parameter, so this feature must not introduce `ScheduleSRelay`,
`Schedule-SRelay`, or any other secondary-relay request key.

**Independent Test**: Capture outgoing add-user and modify-user payloads and
confirm the feature adds only `Schedule-Relay` alongside `ScheduleRelay`; no
secondary-relay request key is present. (US3 Acceptance Scenarios 1 & 2,
SC-004.)

### Tests for User Story 3 (MANDATORY)

- [ ] T014 [P] [US3] Add unit test
      `test_add_user_does_not_introduce_secondary_relay_keys` in
      `tests/unit/test_users.py` that calls `add_user` through the current
      public API and asserts the outgoing payload's `item[0]` contains no
      `ScheduleSRelay` or `Schedule-SRelay` key. Satisfies FR-003 and
      FR-008 (secondary-relay guard rail).

- [ ] T015 [P] [US3] Add unit test
      `test_modify_user_does_not_introduce_secondary_relay_keys` in
      `tests/unit/test_users.py` that performs the same assertion for
      `modify_user`'s outgoing payload when the primary-relay schedule is
      updated.

### Implementation for User Story 3

- [ ] T016 [US3] Inspect the changes made in T005 and T006 in
      `src/pylocal_akuvox/users.py` and confirm no secondary-relay key was
      introduced. If T014 or T015 fail, remove any such key. (No new
      implementation expected — this phase is a guard rail.)

- [ ] T017 [US3] Run `uv run pytest tests/unit/test_users.py -v` and
      confirm T014 and T015 PASS alongside all earlier tests.

**Checkpoint**: All three user stories are independently verifiable. The
secondary-relay boundary is locked in by automated tests so a future
well-intentioned "symmetry" change cannot accidentally broaden this fix.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, edge-case coverage, and release readiness
across all stories. No new behavior — only hardening.

- [ ] T018 [P] Add two unit tests in `tests/unit/test_users.py`
      covering FR-007 and the spec's "Unset primary schedule on modify"
      edge case:
      (a) `test_modify_user_omits_both_primary_relay_keys_when_schedule_unset`
      — call `modify_user(...)` without supplying `schedule_relay` (or
      with `schedule_relay=None`), capture the outgoing payload, and
      assert that NEITHER `ScheduleRelay` NOR `Schedule-Relay` is added
      to `item[0]` by this code path (consistency by joint absence).
      (b) `test_add_user_rejects_empty_primary_schedule` — call
      `add_user(...)` with `schedule_relay=""` and assert it raises
      `AkuvoxValidationError` before any HTTP request is issued,
      documenting that the "two keys disagreeing" risk does not arise
      for add-user.

- [ ] T019 [P] Add unit test
      `test_primary_dual_write_does_not_add_secondary_keys` in
      `tests/unit/test_users.py` covering the spec's "secondary relay
      remains out of scope" edge case: a primary-relay add or modify emits
      `ScheduleRelay` + `Schedule-Relay` (matching values) and no
      `ScheduleSRelay` or `Schedule-SRelay` key.

- [ ] T020 [P] Update `README.md` (or the appropriate user-facing doc) at
      the repo root with a short "Firmware compatibility" note pointing
      integrators to `specs/006-schedule-relay-compat/quickstart.md` and
      summarizing: zero caller-code changes required (SC-005), fixes E18
      `18.30.11.21`, preserves all previously supported firmwares.

- [ ] T021 Run the full local quality gate from the repo root —
      `uv run pytest`, `uv run ruff check .`, `uv run ruff format
      --check .`, `uv run mypy`, `uv run interrogate` (per constitution
      Principle I), and any pre-commit hook configured in the repo —
      and confirm everything passes with zero errors or warnings before
      opening the PR.

- [ ] T022 Manually execute `specs/006-schedule-relay-compat/quickstart.md`
      §"Verifying on real hardware" against both an Akuvox E18 device on
      `18.30.11.21` and at least one previously supported firmware (e.g.,
      X916 on `916.30.10.114`), confirming SC-001 through SC-004. Record
      the firmware versions tested in the PR description.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup, T001)**: No dependencies; do first.
- **Phase 2 (Foundational)**: Empty — does not gate anything.
- **Phase 3 (US1)**: Depends on T001. Tests (T002, T003) before
  implementation (T005–T007); T004 enforces the red phase; T008 enforces
  the green phase.
- **Phase 4 (US2)**: Depends on T001. T009–T011 can be authored at the
  same time as Phase 3 tests; T012–T013 should run after Phase 3
  implementation lands so the full suite is exercised against the new
  code.
- **Phase 5 (US3)**: Depends on T001 and on Phase 3 implementation
  existing (T005, T006) so T016 can audit it; tests T014/T015 can be
  authored at any time.
- **Phase 6 (Polish)**: Depends on Phases 3–5 being complete.

### User Story Dependencies

- US1 (P1): Independent. Delivers the regression fix.
- US2 (P1): Independent in scope (asserts no-op on legacy firmwares) but
  validates the SAME code edits made for US1. In practice US1 and US2
  ship in the same commit; their test sets are independent and can be
  authored in parallel.
- US3 (P2): Independent. Guards against an over-correction.

### Within Each User Story

- Tests are authored and confirmed FAILING before implementation
  (constitution Principle II).
- Implementation tasks edit `src/pylocal_akuvox/users.py` — these are
  NOT marked [P] within a phase because they touch the same file.
- After implementation, the corresponding test tasks are re-run to
  confirm green.

### Parallel Opportunities

- T002, T003, T009, T010, T011, T014, T015 are all in
  `tests/unit/test_users.py` but are independent test functions and can
  be authored in parallel (committed together) — marked [P] for that
  reason. If your workflow serializes edits to a single file, do them
  back-to-back instead.
- T005 and T006 both touch `src/pylocal_akuvox/users.py` (different
  functions) — do sequentially in one editing session and one commit.
- T018, T019, T020 in Phase 6 touch independent
  tests/docs and can be done in parallel.

---

## Parallel Example: User Story 1

```bash
# Author the two failing payload-assertion tests together
# (single file, independent test functions):
Task: "T002 [US1] Add failing test test_add_user_emits_dual_primary_relay_schedule_keys in tests/unit/test_users.py"
Task: "T003 [US1] Add failing test test_modify_user_emits_dual_primary_relay_schedule_keys in tests/unit/test_users.py"

# Then sequentially in src/pylocal_akuvox/users.py:
Task: "T005 [US1] Add Schedule-Relay key to add_user outgoing item dict"
Task: "T006 [US1] Add Schedule-Relay key to modify_user current update"
```

---

## Implementation Strategy

### MVP (US1 only)

1. T001 (sync deps).
2. T002–T004 (write failing US1 tests, confirm red).
3. T005–T008 (implement dual-write, confirm green).
4. STOP and VALIDATE on a real E18 device per
   `quickstart.md` §"Verifying on real hardware" step 1. This alone
   restores the regression and is the smallest shippable increment.

### Incremental delivery (recommended single PR)

Because the same two-line edit satisfies US1, US2, and US3
simultaneously, and the spec is explicit that backward compatibility is
a release blocker, ship all three phases in a single PR:

1. Setup (T001).
2. US1 tests + implementation (T002–T008).
3. US2 tests + verification (T009–T013).
4. US3 tests + audit (T014–T017).
5. Polish (T018–T022).
6. Open PR; CI runs the unit suite; maintainer performs T022 manual
   hardware sign-off; merge.

### Parallel team strategy

Not applicable — the change is ~2 lines of production code in a single
file. One developer should own the entire feature to keep the commit
atomic per constitution Principle V.

---

## Notes

- [P] tasks = independent (different functions or different files), safe
  to author in parallel; commit grouping is up to the implementer.
- All test tasks live in `tests/unit/test_users.py`; all production
  changes live in `src/pylocal_akuvox/users.py`.
- Verify tests fail before implementing (constitution II).
- Keep the implementation as a single atomic commit (constitution V);
  test commits may be separate but should land in the same PR.
- Do NOT introduce any firmware version detection (FR-006).
- Do NOT add secondary-relay scheduling fields (FR-003) — this is enforced
  by T014/T015.
