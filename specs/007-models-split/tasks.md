# Tasks: Split models.py into Domain-Grouped Modules

**Input**: Design documents from `/specs/007-models-split/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓,
contracts/import-contract.md ✓, quickstart.md ✓

**Tests**: Unit-level tests are MANDATORY per the project constitution
(Principle II: TDD). The new TDD contract test
(`tests/unit/test_models_reexport.py`) is written **before** the move (red),
then made green by creating the new package layout. The existing
`tests/unit/test_models.py` (1029 lines) is the regression net for the moved
behavior and must remain green at every commit boundary.

**Organization**: Tasks are grouped by user story (US1 = import
compatibility, US2 = file-size gate, US3 = future-change locality, US4 =
test-suite organization & coverage) to enable independent verification of
each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- All file paths are absolute or repository-relative from
  `/home/tykeal/repos/personal/homeassistant/pylocal-akuvox/`.

## Path Conventions

- **Single project layout** (per `plan.md` §"Project Structure"):
  - Library source: `src/pylocal_akuvox/`
  - Tests: `tests/unit/`
- The refactor replaces `src/pylocal_akuvox/models.py` (file) with
  `src/pylocal_akuvox/models/` (package). The package directory cannot
  coexist with the file at the same import path — `models.py` is deleted
  in the same change set that introduces the package.

---

## Phase 1: Setup (Baseline Capture)

**Purpose**: Capture pre-refactor measurements so the post-refactor checks
in US2, US4, and Polish can prove non-regression (SC-001, SC-005, SC-004).

- [ ] T001 Confirm working tree is clean and on branch `007-models-split`:
  run `git status` and `git rev-parse --abbrev-ref HEAD` from the repo
  root; abort if either reports unexpected state.
- [ ] T002 [P] Capture pre-split file-size baseline by running
  `wc -l src/pylocal_akuvox/models.py` and recording the result (expected:
  447 — issue #126 originally reported 448; the one-line delta is
  immaterial, both exceed the 400 gate). This is the SC-001 / FR-005
  reference for the post-split file-size check in T016.
- [ ] T003 [P] Capture pre-split model-layer coverage baseline by
  running:
  ```bash
  uv run pytest tests/unit/test_models.py -q
  uv run coverage report --include='src/pylocal_akuvox/models/*'
  ```
  and recording the single aggregate **Cover %** value reported for
  `src/pylocal_akuvox/models.py` (today the only file matching the
  glob). This single number is the SC-005 reference for the
  non-regression check in T022. Per-class breakdowns are not produced
  by `coverage.py` directly and are not required — the aggregate
  number is the enforceable measurement. Verified at the time of
  spec authoring: the existing run reports
  `src/pylocal_akuvox/models.py 240 0 32 0 100%` (i.e. 100% line +
  100% branch coverage), so the post-split aggregate must also be
  100%.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verify the consumer-import inventory in
`contracts/import-contract.md` §2 still matches the current tree before
making any structural change. Protects against silent drift between spec
authoring and implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase confirms the
baseline.

- [ ] T004 Verify the consumer-import inventory in
  `specs/007-models-split/contracts/import-contract.md` §2 still matches
  the repo state: run `git grep -nE "from pylocal_akuvox\.models( |$)|from
  pylocal_akuvox\.models import" -- src/ tests/ examples/ docs/` and
  confirm the set of files matches the documented consumer list (no new
  consumers have appeared since the contract was written). If drift is
  found, update `contracts/import-contract.md` §2 first, then proceed.
  Additionally, verify the spec.md Assumption "the current ten model
  classes are the complete set" still holds by running
  `git grep -cE "^class (DeviceInfo|DeviceStatus|Relay|User|AccessSchedule|DoorLogEntry|CallLogEntry|DeviceConfig|Group|Contact)\b" -- src/pylocal_akuvox/models.py`
  and confirming the result is exactly **10**. (A simpler but
  complementary check: `grep -cE "^class " src/pylocal_akuvox/models.py`
  should also return 10.) Do **not** use a generic
  `git grep "^@dataclass" -- src/pylocal_akuvox/` drift check —
  `src/pylocal_akuvox/auth.py:23` already has a legitimate non-model
  `@dataclass(frozen=True) class AuthConfig:` that is intentionally
  out of scope for this refactor (it is consumed by `auth.py` itself,
  not exported via `pylocal_akuvox.models`, and stays put). If the
  10-name count differs (a new model class was added, or one was
  removed), update spec.md and `contracts/import-contract.md` to reflect
  the new set before proceeding.

**Checkpoint**: Baseline captured, consumer inventory verified — user story
work can begin.

---

## Phase 3: User Story 1 - Existing import paths keep working (Priority: P1) 🎯 MVP

**Goal**: After the split, every existing
`from pylocal_akuvox.models import <Name>` statement (for all ten public
classes) continues to resolve to the *same class object* with the *same
behavior*, without any source edit on the consumer side.
`pylocal_akuvox.__all__` (top-level package) remains byte-identical.
`pylocal_akuvox.models.__all__` is **newly introduced** by the shim
(today's `models.py` defines none); by design it contains exactly the
ten public model names and intentionally excludes the four accidental
helper-name leaks (`AkuvoxParseError`, `Any`, `annotations`,
`dataclass`) that bare star-import exposes today — a deliberate
clarification of the public contract per spec FR-004 and the
`from pylocal_akuvox.models import *` edge case, not a regression.

**Independent Test**: Run the full pre-existing test suite unchanged
(`uv run pytest`); every test that imports from `pylocal_akuvox.models`
must pass. Additionally the new TDD contract test
`tests/unit/test_models_reexport.py` (T005) must pass, asserting class
identity through the shim, the new `pylocal_akuvox.models.__all__`
contents (exactly the ten public names), and that `pylocal_akuvox.__all__`
continues to expose the same ten names it always has.

### Tests for User Story 1 (TDD red phase) ⚠️

> **NOTE: Write this test FIRST and confirm it FAILS before any
> implementation task in this phase. The failure must be an `ImportError`
> on `pylocal_akuvox.models.users` (etc.) because the submodules do not
> yet exist.**

- [ ] T005 [US1] Create `tests/unit/test_models_reexport.py` with the
  three test functions specified verbatim in
  `specs/007-models-split/contracts/import-contract.md` §3
  (`test_models_all_contains_exactly_the_ten_public_names`,
  `test_class_identity_is_preserved_through_shim`,
  `test_top_level_package_all_still_exposes_the_ten_names`) including the
  `EXPECTED_PUBLIC_NAMES` constant and submodule imports
  (`from pylocal_akuvox.models import users as users_mod`, etc.). Add the
  SPDX header pair at the top of the file. Run
  `uv run pytest tests/unit/test_models_reexport.py -v` and **confirm
  the test fails** (ImportError / ModuleNotFoundError on
  `pylocal_akuvox.models.users` and siblings).

### Implementation for User Story 1 (TDD green phase)

> **Atomicity note**: T005 + T006-T014 together form one logical change
> set. The repository is in a broken state if `models.py` is deleted
> (T014) before `models/__init__.py` (T013) exists, or if the package
> directory coexists with the file, or if the TDD test from T005 is
> committed in isolation (it would be red and pre-commit's pytest hook
> would block the commit). Implement T006-T012 first (the package
> directory can coexist with `models.py` because nothing yet imports its
> submodules), then perform T013 and T014 back-to-back. **All tasks in
> this phase (T005 through T014) land in a single atomic commit** per
> Principle V (Atomic Commits) and per T026 — see T026 for the full
> commit recipe (subject ≤50 chars, capitalized Conventional Commit
> type, `-s` sign-off, `Co-Authored-By:` trailers, no `--no-verify`).

- [ ] T006 [P] [US1] Create `src/pylocal_akuvox/models/device.py` and
  move the `DeviceInfo`, `DeviceStatus`, and `Relay` `@dataclass` blocks
  verbatim from `src/pylocal_akuvox/models.py` lines 14-119 (per
  `data-model.md` §"Class Home Map" rows 1-3). Include the SPDX header
  pair, `"""Device-domain data models (identity, live status,
  relays)."""` module docstring, and the four imports listed for
  `models/device.py` in `data-model.md` §"Per-File Composition" table:
  `from __future__ import annotations`, `from dataclasses import
  dataclass`, `from typing import Any`, `from pylocal_akuvox.exceptions
  import AkuvoxParseError`. Preserve all class docstrings, field
  defaults, method signatures, and `from_api_response` parsing behavior
  unchanged (FR-007). Target file size: ~115 lines (≤ 400, per
  `data-model.md` budget table).
- [ ] T007 [P] [US1] Create `src/pylocal_akuvox/models/users.py` and
  move the `User` `@dataclass` block verbatim from
  `src/pylocal_akuvox/models.py` lines 120-191 (per `data-model.md` row
  4). Include the SPDX header pair, `"""User-domain data model."""`
  module docstring, and the four imports listed for `models/users.py`
  in `data-model.md` §"Per-File Composition" table (same set as T006).
  Preserve the `ScheduleRelay` / `Schedule-Relay` / `Schedule` fallback
  chain in `User.from_api_response` exactly as written (FR-007). Target
  file size: ~81 lines (≤ 250 per SC-006).
- [ ] T008 [P] [US1] Create `src/pylocal_akuvox/models/schedules.py` and
  move the `AccessSchedule` `@dataclass` block verbatim from
  `src/pylocal_akuvox/models.py` lines 192-275 (per `data-model.md` row
  5). Include the SPDX header pair,
  `"""Access-schedule (time-window) data model."""` module docstring,
  and the four imports listed for `models/schedules.py` in
  `data-model.md` §"Per-File Composition" table. Target file size:
  ~93 lines.
- [ ] T009 [P] [US1] Create `src/pylocal_akuvox/models/logs.py` and move
  the `DoorLogEntry` and `CallLogEntry` `@dataclass` blocks verbatim
  from `src/pylocal_akuvox/models.py` lines 276-341 (per `data-model.md`
  rows 6-7). Include the SPDX header pair,
  `"""Event-log data models (door-open and call records)."""` module
  docstring, and the four imports listed for `models/logs.py` in
  `data-model.md` §"Per-File Composition" table. Target file size:
  ~75 lines.
- [ ] T010 [P] [US1] Create `src/pylocal_akuvox/models/config.py` and
  move the `DeviceConfig` `@dataclass` block verbatim from
  `src/pylocal_akuvox/models.py` lines 342-387 (per `data-model.md` row
  8). Include the SPDX header pair,
  `"""Device-configuration data model."""` module docstring, and **only
  the three imports `DeviceConfig` actually uses**:
  `from __future__ import annotations`, `from dataclasses import
  dataclass`, `from typing import Any`. **Do NOT import
  `AkuvoxParseError`** — `DeviceConfig.from_api_response` does not raise
  (verified against `models.py:342-387`), and an unused import would
  trigger ruff `F401` and fail the quality gate (FR-013). This is the
  only domain submodule that omits the `AkuvoxParseError` import; see
  the per-file import table in `data-model.md` §"Per-File Composition".
  Target file size: ~55 lines.
- [ ] T011 [P] [US1] Create `src/pylocal_akuvox/models/groups.py` and
  move the `Group` `@dataclass` block verbatim from
  `src/pylocal_akuvox/models.py` lines 388-414 (per `data-model.md` row
  9). Include the SPDX header pair,
  `"""Organizational-group data model."""` module docstring, and the
  four imports listed for `models/groups.py` in `data-model.md`
  §"Per-File Composition" table. Target file size: ~36 lines.
- [ ] T012 [P] [US1] Create `src/pylocal_akuvox/models/contacts.py` and
  move the `Contact` `@dataclass` block verbatim from
  `src/pylocal_akuvox/models.py` lines 415-447 (per `data-model.md` row
  10). Include the SPDX header pair,
  `"""Contact / address-book data model."""` module docstring, and the
  four imports listed for `models/contacts.py` in `data-model.md`
  §"Per-File Composition" table. Target file size: ~42 lines (≤ 250 per
  SC-006). (T006-T012 are all [P] — different files, no dependencies on
  each other.)
- [ ] T013 [US1] Create `src/pylocal_akuvox/models/__init__.py` as the
  re-export shim, using the *exact* content specified in
  `specs/007-models-split/data-model.md` §"Re-Export Shim
  (`models/__init__.py`)": SPDX header pair, the package-level docstring
  explaining the backwards-compatibility purpose and pointing readers at
  the per-domain home modules, `from __future__ import annotations`,
  seven `from pylocal_akuvox.models.<sub> import <Name>` lines, and the
  alphabetically-sorted `__all__: list[str] = [...]` of the ten public
  names (FR-001, FR-003, FR-004, FR-015). Depends on T006-T012.
- [ ] T014 [US1] Delete the old monolith `src/pylocal_akuvox/models.py`
  with `git rm src/pylocal_akuvox/models.py`. Python cannot resolve both
  the file and the package at the same import path; the package replaces
  the file. Depends on T013 (the shim must exist before the file is
  removed so that `from pylocal_akuvox.models import …` continues to
  resolve mid-test-run). T013 and T014 land in the same commit.
- [ ] T015 [US1] Verify TDD test is now GREEN: run
  `uv run pytest tests/unit/test_models_reexport.py -v` and confirm all
  three assertions pass. Additionally run
  `uv run pytest tests/unit/test_models.py -q` to confirm the existing
  1029-line regression suite still passes with zero failures and zero
  skips (FR-007, FR-012, SC-002).

**Checkpoint**: User Story 1 fully functional and testable
independently — every existing named import works, class identity is
preserved through the shim, the newly-introduced
`pylocal_akuvox.models.__all__` exposes exactly the ten public model
names (per spec FR-004), and the pre-existing model regression suite is
still green.

---

## Phase 4: User Story 2 - aislop file-size gate passes for the model layer (Priority: P1)

**Goal**: After the split, no file in the model layer (`models/__init__.py`
+ the seven domain submodules) exceeds the aislop 400-line
`complexity/file-too-large` threshold, and the previously-emitted warning
on `models.py` is gone.

**Independent Test**: `wc -l src/pylocal_akuvox/models/*.py` shows every
file ≤ 400 lines, and re-running the aislop / file-size linter step that
previously flagged `models.py` produces no warnings on the new files.

### Implementation for User Story 2

- [ ] T016 [US2] Verify file-size compliance by running
  `wc -l src/pylocal_akuvox/models/*.py` and confirming every file is
  ≤ 400 lines (FR-005, SC-001). Cross-check against the budget table in
  `data-model.md` §"File-Size Budget (post-split)"; flag any file that
  exceeded its projected size by > 20%.
- [ ] T017 [US2] Confirm the aislop `complexity/file-too-large` warning
  is resolved. **Tooling note**: aislop is an external code-review tool
  (it surfaced the original 400-line warning on `models.py` via issue
  #126); it is **not** wired into this project's local lint config
  (`ruff.toml`) or CI workflows (`.github/workflows/`). Verification is
  therefore: (a) `src/pylocal_akuvox/models.py` no longer exists
  (`test ! -e src/pylocal_akuvox/models.py`), so the previously-reported
  warning has nowhere to attach; and (b) `wc -l
  src/pylocal_akuvox/models/*.py` (already done in T016) shows every new
  file is well under 400 lines, so a future aislop run on the new files
  will not re-emit the warning. If aislop is re-run externally on this
  branch, no `complexity/file-too-large` warnings should appear under
  `src/pylocal_akuvox/models/`.

**Checkpoint**: User Stories 1 AND 2 both pass independently — imports
preserved AND the file-size gate is clean.

---

## Phase 5: User Story 3 - Future change locality for #123 and #121 (Priority: P2)

**Goal**: The post-split layout puts `User` in a user-domain-only module
and `Contact` in a contact-domain-only module, each substantially under
250 lines so the anticipated #123 (capability-driven `from_api_response`
alias rewrite) and #121 (apartment-book contact fields) changes are
single-file diffs that won't re-trigger the file-size gate. The layout
leaves a conventional, documented place for a future
`pylocal_akuvox/capabilities.py` cross-cutting sibling without expanding
any domain module.

**Independent Test**: Walk `src/pylocal_akuvox/models/` and confirm
`users.py` contains only `User`, `contacts.py` contains only `Contact`,
both files are ≤ 250 lines (SC-006), and the package-level docstring in
`models/__init__.py` (or `data-model.md` / `plan.md`) documents where the
future cross-cutting module will live.

### Implementation for User Story 3

- [ ] T018 [US3] Verify `src/pylocal_akuvox/models/users.py` contains
  exactly one `@dataclass` block (`User`) with no other domain classes,
  and that `wc -l src/pylocal_akuvox/models/users.py` is ≤ 250 lines
  (SC-006, FR-008). Confirms #123's planned `from_api_response` rewrite
  is a single-file change.
- [ ] T019 [US3] Verify `src/pylocal_akuvox/models/contacts.py` contains
  exactly one `@dataclass` block (`Contact`) with no other domain
  classes, and that `wc -l src/pylocal_akuvox/models/contacts.py` is
  ≤ 250 lines (SC-006, FR-008). Confirms #121's apartment-book field
  additions (`APTName`, `APTNum`, `Building`, `Landline`) land as a
  single-file change with comfortable headroom.
- [ ] T020 [US3] Verify the package-level docstring in
  `src/pylocal_akuvox/models/__init__.py` documents that cross-cutting
  types introduced by #123 belong as a sibling module
  (`src/pylocal_akuvox/capabilities.py`) outside the `models/` package,
  not inside any domain module (FR-009). The shim docstring specified in
  `data-model.md` §"Re-Export Shim" already includes this sentence (the
  "Cross-cutting types …" paragraph), so this task is a verification
  that T013 used the documented content unchanged. If the sentence is
  missing for any reason, restore it from `data-model.md` rather than
  inventing new wording.

**Checkpoint**: User Stories 1, 2, AND 3 all pass independently — imports
preserved, file-size gate clean, and the layout provides documented
locality for upcoming #123 / #121 work.

---

## Phase 6: User Story 4 - Test suite remains organized and complete (Priority: P2)

**Goal**: The full test suite continues to pass after the split with no
removed or skipped scenarios, and the **aggregate Cover %** for the
model layer (matched by `coverage report --include='src/pylocal_akuvox/models/*'`)
is ≥ the pre-split baseline captured in T003 (SC-005). Per-class
coverage breakdowns are not required and not produced by `coverage.py`
at the granularity originally implied; the moved classes are
byte-for-byte identical, so the aggregate is the only signal that can
meaningfully regress.  `tests/unit/test_models.py` is intentionally
**not** split (per research §R4 decision); the choice is reaffirmed by
the green post-refactor run.

**Independent Test**: `uv run pytest` exits 0 with the same number of
collected tests as pre-split (modulo the three new tests added by T005);
`uv run coverage report --include='src/pylocal_akuvox/models/*'` shows an
aggregate Cover % ≥ baseline.

### Implementation for User Story 4

- [ ] T021 [US4] Run `uv run pytest` from the repo root and confirm: full
  test suite passes with zero failures, zero unexpected skips, and
  collected-test count = pre-split count + 3 (the three new tests in
  `tests/unit/test_models_reexport.py` from T005). Satisfies FR-012.
- [ ] T022 [US4] Run:
  ```bash
  uv run pytest -q
  uv run coverage report --include='src/pylocal_akuvox/models/*'
  ```
  and compare the single aggregate **Cover %** reported for the
  `src/pylocal_akuvox/models/*` glob (now matching the eight files inside
  the `models/` package: `__init__.py` plus the seven domain submodules)
  against the baseline aggregate captured in T003 (which was 100% on
  `models.py` alone). The post-split aggregate MUST be ≥ baseline
  (SC-005). A small *increase* from the three new re-export tests
  raising coverage on the new shim file is acceptable and expected.
  Per-class numbers are not required — the aggregate is the
  enforceable measurement; since the moved classes are unchanged
  bytes-for-bytes, the only way the aggregate can regress is via a
  new uncovered line in the shim, which the T015 test already covers.

**Checkpoint**: All four user stories pass independently — the refactor
is complete and validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Run the full quality gate, end-to-end quickstart verification,
and confirm the atomic-commit / compliance principle is satisfied.

- [ ] T023 [P] Run all eleven steps of
  `specs/007-models-split/quickstart.md` end-to-end against the working
  tree and confirm every step produces the expected output. This is the
  reviewer-facing dry-run of SC-001 through SC-007.
- [ ] T024 [P] Run the full quality gate (FR-013, SC-004) from the repo
  root: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy`, `uv run interrogate`, `uv run reuse lint`. Each command
  must exit 0 with no new warnings or errors compared to `main`. In
  particular, `reuse lint` must confirm every new file under
  `src/pylocal_akuvox/models/` carries the SPDX header pair (FR-014), and
  `interrogate` must confirm every new module and class has a docstring
  preserved from the original (FR-015). Additionally, run the docs
  build to confirm the spec's Sphinx edge case ("any broken doc builds
  must be fixed as part of this work"):
  `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`
  must exit 0. The `-W` flag promotes warnings (e.g. autodoc import
  failures) to errors, so a green run proves the `automodule
  pylocal_akuvox.models` directive in `docs/api/models.rst` still
  resolves the ten model classes through the new shim.
- [ ] T025 Confirm zero downstream import edits are required (SC-003) by
  scanning consumer code only — explicitly excluding the new shim
  package itself (whose new `from pylocal_akuvox.models.<sub> import …`
  lines are *expected* churn, not downstream breakage), the spec
  artifacts, and the new TDD test module:
  ```bash
  git diff main \
      -- 'src/' 'tests/' 'examples/' 'docs/' \
         ':!src/pylocal_akuvox/models/**' \
         ':!specs/**' \
         ':!tests/unit/test_models_reexport.py' \
      | grep -E '^[-+].*from pylocal_akuvox\.models' \
      | grep -v '^[-+]\{3\}'
  ```
  Expected: **no output**. The pathspec exclusions ensure the grep does
  not falsely flag the shim's own new imports
  (`src/pylocal_akuvox/models/__init__.py`) or the new contract test
  (`tests/unit/test_models_reexport.py`, which legitimately adds new
  `from pylocal_akuvox.models import <sub> as <sub>_mod` lines per
  `contracts/import-contract.md` §3 — these import each submodule
  *through the shim* so the test exercises the re-export surface
  rather than bypassing it). Any non-shim, non-test consumer edit that
  *does* surface must be reverted — the spec forbids requiring
  downstream edits for correctness.
- [ ] T026 Stage and commit the refactor per Principle V (Atomic Commits
  & Compliance) and the project conventions in `AGENTS.md` §"Commit
  conventions". The TDD test module (T005) and the package split
  (T006-T014) MUST land in **one atomic commit** — committing the test
  in isolation would leave the test red and pre-commit's pytest hook
  would block the commit. The single commit therefore contains both
  the new `tests/unit/test_models_reexport.py` (red→green TDD test) and
  the `src/pylocal_akuvox/models/` package + `git rm` of the old
  `src/pylocal_akuvox/models.py`, leaving the working tree green. The
  commit MUST follow `AGENTS.md`:

    - **Capitalized Conventional-Commit type** with optional scope; subject
      line **≤ 50 characters**. Suggested:
      `Refactor(models): Split into domain submodules`
      (47 chars — fits).
    - **Body lines** MUST wrap at **≤ 80 characters** per `AGENTS.md`
      §"Line Length Limits" (lines 60-61). URLs in the body are exempt
      (gitlint is configured per `AGENTS.md` to allow over-length URL
      lines). Run `git log -1 --format=%B | awk '{ print length, $0 }'`
      after authoring to spot-check; pre-commit's gitlint hook will
      enforce this and fail the commit if any non-URL body line
      exceeds 80.
    - **`-s` flag** on `git commit -s` for the DCO sign-off
      (`Signed-off-by:` trailer).
    - **`Co-Authored-By:` trailers** for the AI assistants used,
      formatted exactly per `AGENTS.md` §"Co-author trailer table":
      `Co-Authored-By: Claude <claude@anthropic.com>` and
      `Co-Authored-By: GitHub Copilot <copilot@github.com>`.
    - **Body** SHOULD reference issue #126 (closes) and #123 / #121
      (coordinates with) per spec §"Related Issues".
    - **Pre-commit hooks MUST run and pass** — bypassing with
      `--no-verify` is **PROHIBITED** (Constitution Principle V,
      `AGENTS.md`). If a hook fails, fix the cause and re-commit; do
      NOT `git reset` to a pre-hook state and do NOT use
      `--no-verify`.

  After the commit lands locally and passes hooks, push the branch and
  open a PR linking to `specs/007-models-split/spec.md`. The PR title
  SHOULD match the commit subject.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately on the
  branch.
- **Foundational (Phase 2)**: Depends on Setup; verifies consumer
  inventory has not drifted. BLOCKS all user stories.
- **User Story 1 (Phase 3, P1, MVP)**: Depends on Foundational. Contains
  the bulk of the refactor work (TDD test + 7 submodules + shim + old
  file deletion).
- **User Story 2 (Phase 4, P1)**: Depends on US1 (file-size check only
  meaningful once the new files exist).
- **User Story 3 (Phase 5, P2)**: Depends on US1 (locality check only
  meaningful once the new files exist).
- **User Story 4 (Phase 6, P2)**: Depends on US1 (coverage / test-suite
  check only meaningful once the new layout is in place).
- **Polish (Phase 7)**: Depends on all four user stories completing.

### User Story Dependencies

- **US1 (P1)** is the MVP and the only story that produces new source
  code. US2, US3, US4 are all *verification* phases that confirm
  properties US1 already gave us. They could be run in any order after
  US1 completes; they are listed in priority order for clarity.
- **US2, US3, US4** are independently testable against the post-US1
  tree and have no dependencies on each other.

### Within User Story 1

- T005 (write failing TDD test) MUST come before any of T006-T014.
- T006-T012 (create the seven domain submodules) are all `[P]` — they
  touch different files and have no dependencies on each other.
- T013 (create shim `__init__.py`) depends on T006-T012 (the seven
  `from pylocal_akuvox.models.<sub> import …` lines require the
  submodules to exist).
- T014 (delete `models.py`) depends on T013 (the shim must be in place
  before the file is removed so existing imports continue to resolve).
- T015 (verify green) depends on T014.

### Parallel Opportunities

- **Setup**: T002 and T003 are `[P]` — independent baseline captures.
- **US1**: T006-T012 are all `[P]` — seven independent file creations.
  In a multi-developer scenario these could be split across a team, but
  in the typical single-developer flow they are usually written in one
  sitting by following the data-model.md home map sequentially.
- **Polish**: T023 and T024 are `[P]` — quickstart verification and the
  quality-gate run touch the working tree read-only and can be run in
  parallel terminals.
- US2, US3, US4 verification phases can be run in any order (or in
  parallel) once US1 completes.

---

## Parallel Example: User Story 1 Implementation

```bash
# After T005 is red, create the seven domain submodules in parallel
# (each writes a different file under src/pylocal_akuvox/models/):
Task: "Create src/pylocal_akuvox/models/device.py with DeviceInfo, DeviceStatus, Relay (T006)"
Task: "Create src/pylocal_akuvox/models/users.py with User (T007)"
Task: "Create src/pylocal_akuvox/models/schedules.py with AccessSchedule (T008)"
Task: "Create src/pylocal_akuvox/models/logs.py with DoorLogEntry, CallLogEntry (T009)"
Task: "Create src/pylocal_akuvox/models/config.py with DeviceConfig (T010)"
Task: "Create src/pylocal_akuvox/models/groups.py with Group (T011)"
Task: "Create src/pylocal_akuvox/models/contacts.py with Contact (T012)"

# Then serialize the final two steps in the same working state:
Task: "Create src/pylocal_akuvox/models/__init__.py shim (T013)"
Task: "git rm src/pylocal_akuvox/models.py (T014)"
Task: "uv run pytest tests/unit/test_models_reexport.py tests/unit/test_models.py -v (T015)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003).
2. Complete Phase 2: Foundational (T004).
3. Complete Phase 3: User Story 1 (T005-T015).
4. **STOP and VALIDATE**: At this point every existing import works,
   class identity is preserved, and the pre-existing model regression
   suite is green. The refactor's correctness goal is met. The remaining
   phases are verifications that prove additional spec properties.

### Incremental Delivery (Recommended)

1. Setup + Foundational → branch is ready to accept the refactor.
2. US1 (MVP) → imports preserved, regression suite green. Stage but do
   not yet commit.
3. US2 → confirm file-size gate is clean.
4. US3 → confirm locality for #123 / #121.
5. US4 → confirm coverage non-regression.
6. Polish (T023-T026) → full quality gate, downstream-edit check, atomic
   commit + sign-off, PR opened.

Because US2-US4 are pure verification (no new source code), they can
realistically all be performed in a single review pass once US1 is in
place. They are kept as separate phases here only to map cleanly to the
spec's user-story structure and to make traceability between tasks and
acceptance criteria explicit.

### Single-Developer Flow (Most Likely)

This is a small refactor (≈ 26 tasks, single feature branch, single
developer). The realistic execution is:

1. Capture baselines (T001-T003), verify consumer inventory (T004).
2. Write `tests/unit/test_models_reexport.py` (T005); confirm RED.
3. Create the seven submodules (T006-T012), then the shim (T013), then
   `git rm` the monolith (T014). Confirm tests green (T015).
4. Run file-size and aislop checks (T016-T017).
5. Spot-check locality (T018-T020).
6. Run the full test suite + coverage (T021-T022).
7. Run quickstart + full quality gate + downstream-edit guard
   (T023-T025).
8. Commit (T026) with sign-off and Conventional Commit prefixes; open
   PR.

---

## Notes

- `[P]` tasks = different files, no dependencies.
- `[Story]` label maps task to its user story for traceability.
- The TDD test (T005) MUST be RED before T006-T014 and MUST be GREEN
  after T015. This is the explicit verification of Principle II
  compliance.
- Every new `.py` file under `src/pylocal_akuvox/models/` MUST carry the
  same SPDX header pair currently on `src/pylocal_akuvox/models.py`
  (FR-014, T024 reuse lint).
- Every commit MUST use `git commit -s` (DCO sign-off) and a Conventional
  Commit type prefix (Principle V). Pre-commit hooks MUST NOT be bypassed
  with `--no-verify` (T026).
- Avoid: introducing any behavior change while moving classes; adding
  `__getattr__` lazy-loading to the shim (forbidden by spec
  Out-of-Scope); editing any non-shim consumer of
  `pylocal_akuvox.models` (would violate SC-003).
