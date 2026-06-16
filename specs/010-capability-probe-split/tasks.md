<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Refactor capability_probe.py Under Aislop Size Limit

**Input**: Design documents from `/specs/010-capability-probe-split/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md,
contracts/probe-outcomes.md, contracts/probe-classifiers.md,
contracts/probe-parsers.md, contracts/capability-probe.md, quickstart.md
**Branch**: `010-capability-probe-split` (or
`refactor/010-capability-probe-split` — non-protected; the spec branch
naming convention is informational only) is the implementation branch
that will host the single atomic refactor PR. The spec, plan, and this
tasks artifact each ship on their own short-lived `docs/010-…` branch.

**Tests are MANDATORY** per constitution §II (TDD). The four new
probe-side test functions added to
`tests/unit/test_capability_module_layout.py` are authored first
locally — RED against `main` because `capability_probe.py` still
exists and the four new underscore modules do not — and only go GREEN
once the four new modules + the deletion of `capability_probe.py` +
the import rewrites in the two consumer files are also staged. The
published implementation commit is green at every CI gate.

**Atomic commits** per AGENTS.md §"Atomic Commits" + §"Task List
Updates Are Separate Commits": this refactor lands as **ONE PR
containing exactly THREE commits** —

1. The `Refactor(probe)!: Split into submodules` implementation commit
   (single atomic commit covering all four new modules + the 1-line
   `device.py` rewrite + the 41-line + 1-docstring rewrite of
   `tests/unit/test_capability_probe.py` + the deletion of
   `capability_probe.py` + the layout-test extension). The `!` is
   mandatory per FR-007.
2. The `Docs(changelog): Announce 010-probe split` commit (separate
   atomic commit; FR-008 — the changelog entry rides in the same PR
   but is its own commit per AGENTS.md §"Task List Updates Are
   Separate Commits" reasoning applied to the
   documentation/announcement boundary).
3. The `Docs(tasks): Mark 010 task list complete` checkbox-flip commit
   (final commit in the PR; marks every task in this file complete).

**Phasing**: ONE phase, ONE PR (per `plan.md` §"Phase Decomposition").
The phases below are an authoring/verification ordering — they do NOT
correspond to separate PRs.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files,
  no incomplete dependencies between them).
- This refactor has only **one user story** at the implementation
  level — the atomic split itself — so no per-story labels are used;
  the spec's US1 / US2 / US3 priorities are mapped via the FR / SC
  coverage table at the end of this file.
- Every task names exact file path(s) and the FR(s) / SC(s) /
  contract(s) it implements or verifies.

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, `tests/unit/`,
`docs/_ext/`, `docs/`. Spec artifacts in
`specs/010-capability-probe-split/`.

---

## Phase 1: Setup (baseline + working-tree hygiene)

**Purpose**: Capture the pre-refactor baseline so post-refactor
validation gates can compare numerically, and prepare the working tree
for the implementation branch.

- [ ] T001 Capture pre-refactor baseline metrics on `main` at the
  current head: (a) test count from
  `uv run pytest tests/ --collect-only -q | tail -1`; (b) branch
  coverage by running `uv run pytest tests/` and reading the
  generated repo-root `coverage.xml` (`<coverage line-rate>` and
  `<coverage branch-rate>` attributes — must be 1.0 / 100% for
  `pylocal_akuvox`); (c) line count for the doomed file with
  `wc -l src/pylocal_akuvox/capability_probe.py` (expected:
  ~465, per `plan.md` §"Summary"; the implementer's local
  `wc -l` against `main` at refresh time is the canonical
  source — minor drift of ±1–2 lines from intermediate
  housekeeping commits is acceptable, the load-bearing
  invariant is "above the 400-line aislop threshold"); (d) the current `uv run aislop scan`
  output — confirm `capability_probe.py` is flagged with
  `complexity/file-too-large`. `device.py` is also flagged but is
  out of scope (issue #142). `capabilities.py` is already gone
  (shipped under spec 009 / PR #148). Record the (a)–(c) numbers in
  the implementation PR description so SC-001, FR-006, and FR-004
  have explicit before/after comparisons. Covers FR-006 baseline +
  SC-001 baseline + FR-004 baseline.
- [ ] T002 Create the implementation worktree on a fresh branch off
  `main`:
  `git worktree add ../pylocal-akuvox-010 -b 010-capability-probe-split main`.
  All subsequent edits in Phases 2–8 happen in that worktree. The
  spec PR (#149) and plan PR (#150) shipped on their own
  `docs/010-…` branches and have already merged at SHA `8ea1029` or
  later; the tasks PR (this file) similarly ships on its own
  `docs/010-capability-probe-tasks` branch; the implementation
  branch above is the FOURTH and final 010-related branch.
- [ ] T003 Spot-check FR-009 / FR-010: run
  `grep -nE 'pylocal_akuvox\.capability_probe' README.md docs/quickstart.rst examples/mvp_test.py docs/_ext/capability_matrix.py` and
  confirm zero matches. The spec attests this is true on `main`
  (per `research.md` Decision 7); this task records the verification
  in the implementer's local notes so the PR description can cite
  the check. Covers FR-009 + FR-010.

---

## Phase 2: TDD red — extend the layout-assertion test FIRST

**Purpose**: Per constitution §II, write the failing tests before any
code change. The four new test functions are RED against `main`
(because `capability_probe.py` still exists, so
`import pylocal_akuvox.capability_probe` succeeds and Assertion 1
fails; and the four new underscore modules do not exist yet, so
Assertion 3 fails too). Once the four new underscore modules + the
deletion of `capability_probe.py` + the two consumer-import rewrites
are also staged in the SAME commit, the tests go GREEN. The published
commit is therefore green at every CI gate; the "red phase" only ever
exists in the implementer's working tree during authoring. **This task
does NOT create the new module files** — those come in Phase 3.

- [ ] T004 Extend `tests/unit/test_capability_module_layout.py` —
  the existing ~89-line file added by spec 009 (verify with
  `wc -l` against `main` at refresh time; the file is short and
  may have drifted ±1–2 lines from intermediate housekeeping
  commits) — with the four new probe-side test functions per
  FR-011 and `plan.md` §"Subpath-Removal Verification Plan". Update the file's module
  docstring (line 4) to mention spec 010 alongside spec 009 — the
  exact replacement text is spelled out verbatim in `plan.md`
  §"Subpath-Removal Verification Plan / Module docstring update"
  (it rewrites the existing single-spec heading and one of the
  bullets to cover both specs). Add a new bullet to the existing
  four-bullet docstring list calling out the probe-side scope.
  Add the four new test functions verbatim from `plan.md`
  §"Subpath-Removal Verification Plan":

  1. `test_capability_probe_subpath_is_gone` — uses
     `pytest.raises(ModuleNotFoundError)` (bare; **NEVER** the
     `(ModuleNotFoundError, ImportError)` tuple form per the
     carry-forward retro from 009 item 4 and FR-011) wrapping
     `importlib.import_module("pylocal_akuvox.capability_probe")`.
     Covers FR-002 / SC-003 (import form).
  2. `test_capability_probe_subpath_from_import_is_gone` — uses
     `pytest.raises(ModuleNotFoundError)` (bare) wrapping
     `exec("from pylocal_akuvox.capability_probe import probe_capabilities")`
     with a `# noqa: S102` (the `exec()` is intentional; documented
     in the docstring why a static `from`-import at module top
     level cannot be used). Covers FR-003 / SC-003 (from-import
     form).
  3. `test_probe_underscore_modules_importable` — uses
     `importlib.import_module` to import each of
     `pylocal_akuvox._probe_outcomes`, `_probe_classifiers`,
     `_probe_parsers`, `_capability_probe` and asserts each call
     returns without raising. Covers FR-005 at module level.
  4. `test_probe_capabilities_reachable_via_device` —
     `import pylocal_akuvox; assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities)`.
     **Presence pin only** — no behavior assertions (those stay in
     `tests/unit/test_capability_probe.py`). Covers FR-001 + spec
     User Story 1.

  Locally run
  `uv run pytest tests/unit/test_capability_module_layout.py -v`;
  expected output: assertion 1 FAILS (because `capability_probe.py`
  still exists on `main` so `import pylocal_akuvox.capability_probe`
  succeeds); assertion 2 FAILS (the static `exec` import succeeds
  on `main`); assertion 3 FAILS (no `_probe_*` modules exist yet);
  assertion 4 PASSES (the public method already works on `main`).
  At least three assertions FAIL — that is the red proof. Do NOT
  commit yet — T004 stages a file that only goes green once the
  rest of Phases 3 + 4 + 5 + 6 are also staged. Covers FR-011 +
  spec User Story 2 acceptance scenarios #1 and #2.

---

## Phase 3: Core implementation — create the four new underscore modules

**Purpose**: Author the four sibling underscore-prefixed modules as
described in `plan.md` §"File-by-File Plan" and the four `contracts/`
files. Each module gets a verbatim cut-paste of the relevant chunk of
`capability_probe.py` (no body changes) plus a fresh SPDX header pair,
focused module docstring, ordered imports, and `__all__`. **No imports
in any other file change yet** — `capability_probe.py` is still intact
at the end of this phase (each new module does NOT yet replace it,
since `device.py` and `tests/unit/test_capability_probe.py` still
import from the old path), so the package remains importable through
both old and new paths until Phase 6's deletion.

The probe-side dependency DAG is strict (per `plan.md` §"Cross-module
dependency graph (post-split)" and `data-model.md` §"Cross-Module
Dependencies"):

- `_probe_outcomes.py` → leaf (depends on stdlib `enum` only)
- `_probe_classifiers.py` → depends on `_probe_outcomes` +
  `_capability_types`
- `_probe_parsers.py` → depends on `_capability_profile`,
  `_capability_types`, `exceptions` — does **NOT** depend on
  `_probe_outcomes` or `_probe_classifiers`
- `_capability_probe.py` → depends on all three siblings +
  `_capability_profile` / `_capability_types` / `exceptions` /
  `models` (+ `_http` under `TYPE_CHECKING`)

Therefore: T005 (`_probe_outcomes`) MUST go first; T006
(`_probe_classifiers`, depends on `_probe_outcomes`) and T007
(`_probe_parsers`, no sibling dependency) can run **in parallel**
once T005 is staged; T008 (`_capability_probe`) runs last.

- [ ] T005 Create `src/pylocal_akuvox/_probe_outcomes.py` per
  `contracts/probe-outcomes.md` and `plan.md` §"New module 1:
  `src/pylocal_akuvox/_probe_outcomes.py`". SPDX header pair; module
  docstring naming spec `010-capability-probe-split` and the single
  concern ("outcome enumeration and classification markers for the
  capability probe"). Imports:
  `from __future__ import annotations` and `import enum`. Cut-paste
  the bodies of `_ProbeOutcome` (enum), `_NO_HANDLER_MARKERS`,
  `_API_UNSUPPORTED_MARKER`, and `_ACTION_UNSUPPORTED_MARKERS`
  **verbatim** from `src/pylocal_akuvox/capability_probe.py` — no
  member rename, no value change, no method addition.
  `__all__ = ["_ACTION_UNSUPPORTED_MARKERS", "_API_UNSUPPORTED_MARKER", "_NO_HANDLER_MARKERS", "_ProbeOutcome"]`
  (alphabetical, underscore-prefixed names included since these are
  the module's only symbols and downstream sibling modules use them).
  Verify locally:
  `uv run python -c "from pylocal_akuvox._probe_outcomes import _ProbeOutcome, _NO_HANDLER_MARKERS, _API_UNSUPPORTED_MARKER, _ACTION_UNSUPPORTED_MARKERS; print('ok')"`
  prints `ok`. Covers FR-004 (this module ≤50 lines), FR-005 (the
  four symbols listed in `_probe_outcomes`), FR-012 (no first-party
  imports — leaf module), and the
  `contracts/probe-outcomes.md` Public Surface clause.
- [ ] T006 [P] Create `src/pylocal_akuvox/_probe_classifiers.py` per
  `contracts/probe-classifiers.md` and `plan.md` §"New module 2:
  `src/pylocal_akuvox/_probe_classifiers.py`". SPDX header pair;
  module docstring naming the single concern ("pure response
  classifiers — body extraction, system-status summary, outcome
  classification, outcome→status mapping"). Imports per plan:
  `from __future__ import annotations`, `import json`; first-party
  `from pylocal_akuvox._capability_types import CapabilityStatus`
  and `from pylocal_akuvox._probe_outcomes import (_ACTION_UNSUPPORTED_MARKERS, _API_UNSUPPORTED_MARKER, _NO_HANDLER_MARKERS, _ProbeOutcome)`
  (alphabetical by module). Cut-paste the bodies of
  `_extract_message`, `_summarise_system_status`,
  `_classify_response`, and `_outcome_to_status` **verbatim** from
  `capability_probe.py`.
  `__all__ = ["_classify_response", "_extract_message", "_outcome_to_status", "_summarise_system_status"]`
  (alphabetical). Verify locally:
  `uv run python -c "from pylocal_akuvox._probe_classifiers import _classify_response, _outcome_to_status, _summarise_system_status, _extract_message; print('ok')"`.
  Covers FR-004 (≤140 lines), FR-005 (the four classifier symbols),
  FR-012 (absolute first-party imports, no sibling cycle —
  `_probe_classifiers` does NOT import from `_probe_parsers`), and
  `contracts/probe-classifiers.md`.
- [ ] T007 [P] Create `src/pylocal_akuvox/_probe_parsers.py` per
  `contracts/probe-parsers.md` and `plan.md` §"New module 3:
  `src/pylocal_akuvox/_probe_parsers.py`". SPDX header pair; module
  docstring naming the single concern ("response payload parsers
  and schema/alias recorders for the capability probe"). Imports
  per plan: `from __future__ import annotations`, `import json`,
  `from typing import Any`; first-party
  `from pylocal_akuvox._capability_profile import FieldAliases`,
  `from pylocal_akuvox._capability_types import SchemaShape`,
  `from pylocal_akuvox.exceptions import AkuvoxParseError`
  (alphabetical by module). Cut-paste the bodies of
  `_step_1_payload`, `_extract_items`, `_record_user_aliases`,
  `_record_user_schema_keys`, and `_record_contact_shape`
  **verbatim** from `capability_probe.py`.
  `__all__ = ["_extract_items", "_record_contact_shape", "_record_user_aliases", "_record_user_schema_keys", "_step_1_payload"]`
  (alphabetical). Verify locally:
  `uv run python -c "from pylocal_akuvox._probe_parsers import _step_1_payload, _extract_items, _record_user_aliases, _record_user_schema_keys, _record_contact_shape; print('ok')"`.
  Covers FR-004 (≤175 lines), FR-005 (the five parser symbols),
  FR-012 (absolute first-party imports, no sibling cycle —
  `_probe_parsers` does NOT import from `_probe_classifiers` or
  `_probe_outcomes`), and `contracts/probe-parsers.md`.
- [ ] T008 Create `src/pylocal_akuvox/_capability_probe.py` per
  `contracts/capability-probe.md` and `plan.md` §"New module 4:
  `src/pylocal_akuvox/_capability_probe.py`". SPDX header pair;
  module docstring naming the single concern ("orchestration of the
  9-call capability probe sequence"). Imports per plan, all
  alphabetical by module:
  `from __future__ import annotations`, `from typing import TYPE_CHECKING`;
  first-party
  `from pylocal_akuvox._capability_profile import (DeviceCapabilities, FieldAliases)`,
  `from pylocal_akuvox._capability_types import (Capability, CapabilityStatus, SchemaShape)`,
  `from pylocal_akuvox._probe_classifiers import (_classify_response, _outcome_to_status, _summarise_system_status)`,
  `from pylocal_akuvox._probe_outcomes import _ProbeOutcome`,
  `from pylocal_akuvox._probe_parsers import (_extract_items, _record_contact_shape, _record_user_aliases, _record_user_schema_keys, _step_1_payload)`,
  `from pylocal_akuvox.exceptions import (AkuvoxAuthenticationError, AkuvoxConnectionError, AkuvoxParseError, AkuvoxRequestError)`,
  `from pylocal_akuvox.models import DeviceInfo`; under
  `TYPE_CHECKING:` `from pylocal_akuvox._http import AkuvoxHttpClient`.
  **Do NOT add a top-level `import json` or `from typing import Any`** —
  per `data-model.md` §"`_capability_probe.py`", the orchestration
  module no longer needs them after the helpers move to siblings.
  Cut-paste the seven step-path constants
  (`_PROBE_STEP_3_PATH` … `_PROBE_STEP_9_PATH`), the `_LATER_STEPS`
  tuple, and the `async def probe_capabilities(...)` driver
  **verbatim** from `capability_probe.py`.
  `__all__ = ["probe_capabilities"]` (the seven step-path
  constants and `_LATER_STEPS` are intentionally excluded —
  underscore-prefixed and consumed only inside this module).
  Verify locally:
  `uv run python -c "from pylocal_akuvox._capability_probe import probe_capabilities; print('ok')"`.
  Covers FR-004 (≤175 lines), FR-005
  (`probe_capabilities` from `_capability_probe`), FR-012
  (probe-side DAG is acyclic — no lazy imports needed), and
  `contracts/capability-probe.md`.

---

## Phase 4: Migration — production source consumer rewrite

**Purpose**: Rewrite the **single** production-source
`from pylocal_akuvox.capability_probe import …` site in
`src/pylocal_akuvox/device.py`. Per FR-001 only the import line is
permitted to change in this file under this spec.

After this task `device.py` imports `probe_capabilities` from the new
underscore module. `capability_probe.py` still exists (deletion is
T011), so the package continues to import cleanly through both
paths during this transitional state.

- [ ] T009 Rewrite `src/pylocal_akuvox/device.py` line 22 (single
  import line). **Before**:
  `from pylocal_akuvox.capability_probe import probe_capabilities as _probe_capabilities`.
  **After**:
  `from pylocal_akuvox._capability_probe import probe_capabilities as _probe_capabilities`.
  Re-run `grep -n 'from pylocal_akuvox.capability_probe' src/pylocal_akuvox/device.py`
  before editing to refresh the line number against current state.
  **Per FR-001, no other change to `device.py` is permitted under
  this spec.** After the edit, run
  `uv run python -c "import pylocal_akuvox; from pylocal_akuvox import AkuvoxDevice; assert callable(AkuvoxDevice.probe_capabilities); print('ok')"` —
  must print `ok`. Covers FR-001 (consumer rewrite preserves the
  public method) + FR-005 (consumer-side) + FR-006.

---

## Phase 5: Migration — test consumer rewrites

**Purpose**: Rewrite all 41 `from pylocal_akuvox.capability_probe
import …` sites in `tests/unit/test_capability_probe.py` per the
symbol→module table in `data-model.md` §"Test files
(`tests/unit/`)" and `plan.md` §"Import-Rewrite Plan" Group B. **No
test assertion semantics change** — only the import lines flip, plus
the line-4 module docstring fix per FR-013. The 41 source lines
expand to 45 emitted statements because four 2-symbol co-imports
(lines 739, 748, 756, 766 — each
`from pylocal_akuvox.capability_probe import _classify_response, _ProbeOutcome`)
each split into two lines: one
`from pylocal_akuvox._probe_classifiers import _classify_response`
and one
`from pylocal_akuvox._probe_outcomes import _ProbeOutcome`
(alphabetical by module name, matching project ruff/isort style).

After this task all 42 of the `from pylocal_akuvox.capability_probe`
matches across `src/`, `tests/`, and `docs/` are gone (1 from T009 +
41 from T010). `capability_probe.py` is unused but not yet deleted —
T011 handles the deletion. The package continues to import cleanly
through both old and new paths until T011.

- [ ] T010 Rewrite `tests/unit/test_capability_probe.py` — 41
  import-line rewrites (1 static top-of-file at line 29 + 40
  in-test deferred imports) plus the line-4 module docstring fix
  per FR-013. All edits in one task because they all live in the
  same file. Refresh line numbers with
  `grep -n 'from pylocal_akuvox.capability_probe' tests/unit/test_capability_probe.py`
  before editing — `data-model.md` §"Test files" line numbers were
  captured against `main` at SHA `4fc75e8` and may have drifted
  slightly.

  Symbol→module mapping (from `data-model.md` §"Module Layout
  Table"):

  - `probe_capabilities` → `_capability_probe` (1 hit, line 29 —
    static top-of-file `from pylocal_akuvox.capability_probe import
    probe_capabilities as _probe_helper` →
    `from pylocal_akuvox._capability_probe import probe_capabilities
    as _probe_helper`)
  - `_classify_response`, `_summarise_system_status` →
    `_probe_classifiers` (10 in-test hits — lines 739, 748, 756,
    766, 994, 1008, 1016, 1023, 1036, 1048; lines 739/748/756/766
    are 2-symbol co-imports that each split into two lines)
  - `_ProbeOutcome` → `_probe_outcomes` (4 hits — the second
    `from`-line emitted for each of the 4 co-import sites at lines
    739, 748, 756, 766)
  - `_step_1_payload`, `_extract_items`, `_record_user_aliases`,
    `_record_user_schema_keys`, `_record_contact_shape` →
    `_probe_parsers` (30 in-test hits — lines 674, 773, 782, 791,
    800, 809, 820, 829, 838, 847, 866, 875, 884, 893, 900, 907,
    914, 921, 929, 940, 950, 965, 977, 1122, 1142, 1152, 1161,
    1170, 1179, 1188)

  **Subtotal arithmetic**: 1 + 10 + 4 + 30 = 45 emitted
  statements from 41 source lines (the four 2-symbol co-imports
  split into two lines each, adding +4 net file-lines). Net
  file-line growth: **+4 lines** in
  `tests/unit/test_capability_probe.py`. Test assertion bodies do
  NOT change.

  **Module docstring fix (FR-013)**: the test file's module
  docstring is multi-line (it begins at line 4 and continues for
  several more lines describing what the suite covers); **only
  the first line of that docstring** currently mentions the
  dropped subpath via an inline RST literal pointing at
  `pylocal_akuvox.capability_probe`. The fix is to **rewrite
  ONLY that first line** to drop the module path entirely (per
  `data-model.md` §"Test files" and `plan.md` §"Import-Rewrite
  Plan" Group B "Module docstring fix"); a suitable replacement
  is a single-line summary like "Tests for the capability probe
  (capability profile runtime side)." with the leading `"""`
  preserved and no module-path RST literal. Do NOT replace or
  remove the rest of the multi-line docstring (the bullet list
  naming task references, the contract pointer, etc.) — those
  lines stay untouched and continue to describe what the suite
  covers. Do NOT substitute the underscore path on the first
  line either; the test file's purpose is behavior coverage, not
  module-shape pinning, so the module path adds nothing.
  Module-shape pinning lives in
  `tests/unit/test_capability_module_layout.py` (extended in
  T004).

  After the edit, run
  `grep -nE 'from pylocal_akuvox.capability_probe|pylocal_akuvox\.capability_probe' tests/unit/test_capability_probe.py` —
  pass criterion: ZERO matches (the docstring no longer references
  the dropped subpath, and every import line has been rewritten).
  Run `uv run pytest tests/unit/test_capability_probe.py -x -q` —
  all tests still pass because `capability_probe.py` still exists
  AND every import now points at the new underscore modules (the
  new modules were staged in Phase 3, so their symbols resolve).
  Covers FR-005 (consumer-side) + FR-006 + FR-013 (module docstring
  fix).

---

## Phase 6: Migration — delete the old `capability_probe.py`

**Purpose**: With both consumers (T009 `device.py`, T010 test file)
now importing from the new underscore modules, `capability_probe.py`
is unused. Delete it. After this task, T004's layout test goes green:
all four new probe-side assertions now pass. The implementation is
now complete in source-code terms.

- [ ] T011 Delete `src/pylocal_akuvox/capability_probe.py`
  (`git rm src/pylocal_akuvox/capability_probe.py`). Re-run T004's
  layout test:
  `uv run pytest tests/unit/test_capability_module_layout.py -v` —
  all 9 assertions now PASS (5 existing capability-side from spec
  009 + 4 new probe-side from T004). Re-run the full test suite:
  `uv run pytest tests/ -x -q` — all tests pass. Covers FR-002 +
  FR-003 + FR-011 (the test now goes green) + spec User Story 2
  (loud `ModuleNotFoundError` on the dropped subpath).

---

## Phase 7: Validation gates

**Purpose**: Run every gate listed in `plan.md` §"Validation Gates"
against the staged tree before creating the implementation commit.
Each gate maps to one or more SCs and the corresponding constitution
principle. **Every gate MUST pass green** before Phase 8's commit
object is created; the pre-commit hooks in T016 are the load-bearing
enforcement.

These tasks are run in order against the staged-but-not-yet-committed
tree. The `[P]` markers below are conservative — most gates touch
only the staged tree (read-only) so are technically parallel-safe,
but the implementer is encouraged to run them in series so output
streams stay readable. Genuine `[P]` candidates are explicitly
flagged.

- [ ] T012 **Unit tests gate** — run `uv run pytest tests/ -x -q`.
  Pass criterion: exit 0; all tests pass; the four new probe-side
  test functions in `test_capability_module_layout.py` (T004) are
  picked up automatically by `tests/unit/` discovery; the rewritten
  `test_capability_probe.py` (T010) passes with imports resolving
  through the new underscore modules. Covers SC-001.
- [ ] T013 **Branch coverage gate** — run
  `uv run pytest --cov=pylocal_akuvox --cov-branch --cov-report=term-missing tests/`.
  Pass criterion: 100% branch coverage maintained on `pylocal_akuvox`
  (matches T001 baseline). No new uncovered branches. The four new
  modules contain only relocated code; coverage that previously
  exercised those entities through `capability_probe.py` now
  exercises them through the underscore modules — the rewritten
  test imports in T010 ensure this. Covers SC-001 + FR-006.
- [ ] T014 **Lint gate** — run `uv run ruff check src/ tests/`.
  Pass criterion: exit 0; zero warnings. The four new modules'
  imports must be ordered (stdlib → first-party, alphabetical
  within each group) per project ruff/isort config. Covers
  constitution §I.
- [ ] T015 **Type-check gate** — run `uv run mypy src/`. Pass
  criterion: exit 0; zero errors (mypy strict per project config).
  The relocation does not alter any function signature or
  dataclass field type, so no new mypy errors are expected.
  Covers constitution §I + spec User Story 1 acceptance scenario.
- [ ] T016 **Pre-commit (full) gate** — run
  `git add -A && pre-commit run --all-files`. The leading
  `git add -A` is **mandatory**: the project's aislop hook is
  configured with `pass_filenames: false` and operates on the
  staged diff; running `pre-commit run --all-files` against an
  unstaged tree would scan an empty staged set and report a
  false-green. Pass criterion: exit 0; ruff, mypy, interrogate,
  REUSE, codespell, gitlint, **`aislop ci --staged`**, AND
  **`pytest (100% coverage)`** all pass. The aislop hook is the
  very gate this refactor exists to satisfy — it MUST run green
  and MUST report no `complexity/file-too-large` against any of
  the four new modules. This is the load-bearing pre-commit check;
  T017–T019 are belt-and-suspenders. Covers SC-001 + SC-002
  (per-module size limit) + constitution §V (no `--no-verify`).
- [ ] T017 [P] **Aislop new-module size scan (explicit)** — run
  `uv run aislop scan --include 'src/pylocal_akuvox/_probe_outcomes.py,src/pylocal_akuvox/_probe_classifiers.py,src/pylocal_akuvox/_probe_parsers.py,src/pylocal_akuvox/_capability_probe.py'`.
  Pass criterion: NO `complexity/file-too-large` warnings on any
  of the four new modules; each is under 400 lines. **Note**
  (carry-forward retro from 009 item 3): `aislop scan <files…>`
  rejects positional file arguments — the
  `--include 'a,b,c,d'` form is required (comma-separated, no
  spaces inside the quoted list, single quotes around the whole
  list). NEVER use positional file args. This is the explicit
  per-module verification of FR-004 and SC-002 (does not depend
  on staging state). The `[P]` marker reflects that this scan is
  read-only and fully independent of T016's pre-commit run.
- [ ] T018 [P] **Aislop project-wide scan** — run
  `uv run aislop scan`. Pass criterion: `capability_probe.py` no
  longer appears in the `complexity/file-too-large` list (it has
  been deleted in T011). `device.py` will still be flagged —
  that is issue #142, out of scope per spec §"Out of Scope".
  `capabilities.py` is already gone (shipped under spec 009 / PR
  #148). Covers SC-002 at project level.
- [ ] T019 [P] **Doc build gate** — run
  `cd docs && uv run sphinx-build -W -b html . _build/html`. The
  `-W` flag treats warnings as errors. Pass criterion: exit 0;
  confirms the rewritten `device.py` import (T009) works at
  autodoc time, and that the new "Breaking changes" changelog
  bullet (added in Phase 9 T031) — when the build is rerun after
  Phase 9 — has correct RST nesting (does not re-parent the
  existing 009 entry; carry-forward retro from 009 item 5). For
  this Phase 7 run, the changelog bullet has not yet been added
  (lives in the Phase 9 commit), so this gate verifies only the
  source-code import resolution. Covers FR-010 + SC-007.
- [ ] T020 **Subpath removal smoke test (import form)** — run
  `uv run python -c "import pylocal_akuvox.capability_probe"`.
  Pass criterion: exits non-zero with
  `ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'`.
  Covers SC-003 + FR-002.
- [ ] T021 **Subpath removal smoke test (from form)** — run
  `uv run python -c "from pylocal_akuvox.capability_probe import probe_capabilities"`.
  Pass criterion: exits non-zero with
  `ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'`.
  Covers SC-003 + FR-003.
- [ ] T022 **Public probe smoke test** — run
  `uv run python -c "import pylocal_akuvox; assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities); print('ok')"`.
  Pass criterion: exits 0; prints `ok`. Covers SC-004 + FR-001 +
  spec User Story 1 acceptance scenario.
- [ ] T023 **Internal underscore-module smoke tests** — run the
  four `uv run python -c "from pylocal_akuvox._probe_… import …; print('ok')"`
  invocations from `quickstart.md` Step 6:
  `from pylocal_akuvox._probe_outcomes import _ProbeOutcome`,
  `from pylocal_akuvox._probe_classifiers import _classify_response, _outcome_to_status, _summarise_system_status`,
  `from pylocal_akuvox._probe_parsers import _step_1_payload, _extract_items, _record_user_aliases, _record_user_schema_keys, _record_contact_shape`,
  `from pylocal_akuvox._capability_probe import probe_capabilities`.
  Pass criterion: all four print `ok` and exit 0. Belt-and-suspenders
  for FR-005 at the symbol level, complementing T004 assertion 3's
  module-level pin.
- [ ] T024 **Original file gone smoke test** — run
  `test ! -f src/pylocal_akuvox/capability_probe.py && echo deleted`.
  Pass criterion: prints `deleted` and exits 0 (the file is
  absent — the desired post-split state). Non-zero exit if the
  file still exists (refactor incomplete). Covers SC-008.
- [ ] T025 **Pre-PR import-form sanity grep (FR-013 hard
  requirement)** — run
  `grep -rnE "from pylocal_akuvox.capability_probe|import pylocal_akuvox.capability_probe" src/ tests/ docs/ README.md examples/`
  (`-E` selects extended regex so `|` is the alternation operator
  without backslash-escaping; this is portable across GNU,
  BSD/macOS, and busybox grep implementations).
  Pass criterion: **ZERO hits** anywhere in `src/`, `tests/`,
  `docs/`, `README.md`, `examples/` (exclusions: `specs/` is
  allowed because spec/plan/tasks artifacts legitimately discuss
  the dropped subpath; the changelog bullet added in Phase 9 T031
  also lives outside this grep's path set on this Phase 7 run
  since it has not yet been added). This is the user-required
  hard sanity check — it MUST hit zero for the implementation
  commit to be considered complete. Covers FR-013 (subpath
  removal) + the user's hard requirement "Pre-PR
  `grep -rn 'from pylocal_akuvox.capability_probe' src/ tests/
  docs/` returns ZERO hits post-refactor".
- [ ] T026 **FR-013 stale-phrase consumer sweep (single
  dedicated task)** — run
  `grep -rnE "defined here|this module|lazy import|cycle|dataclass|capability_probe" src/pylocal_akuvox/_probe_outcomes.py src/pylocal_akuvox/_probe_classifiers.py src/pylocal_akuvox/_probe_parsers.py src/pylocal_akuvox/_capability_probe.py src/pylocal_akuvox/device.py tests/unit/test_capability_probe.py`.
  Pass criterion: each surviving match must be reviewed manually:
  - `"this module"` is allowed as a self-reference inside a
    single new module's docstring (e.g.
    `_capability_probe`'s top-level docstring saying "this module
    implements the capability probe orchestration"). NOT allowed
    when it points back at the old monolithic
    `capability_probe.py`.
  - `"dataclass"`, `"lazy import"`, `"cycle"` are 009-flavored
    stale phrases — none apply to the live `capability_probe.py`
    source today, so any match means the implementer accidentally
    pasted from spec 009 or its test file. MUST be removed.
  - `"defined here"` references that were monolithic-file-relative
    must be re-anchored to the correct new module.
  - `"capability_probe"` matches inside docstrings or comments must
    be renamed to the underscore path or dropped entirely (the
    test file's line-4 docstring fix is part of T010 but verify
    here that the fix landed). The literal name appears in module
    docstrings of `_capability_probe.py` and is a self-reference —
    confirm it correctly points at the **new** module path.
  Covers FR-013 (user/contact stale-phrase sweep across consuming
  code) + the user's hard requirement "Pre-PR sweep for stale
  phrases … in CONSUMING code (not just moved code) — single
  dedicated task".
- [ ] T027 **FR-014 inline RST literal hygiene scan** — for every
  file touched by the refactor (the four new modules, `device.py`,
  `tests/unit/test_capability_probe.py`,
  `tests/unit/test_capability_module_layout.py`, and — once Phase
  9 T031 lands — `docs/changelog.rst`), search for inline
  back-tick literals that span newlines using the portable ERE
  command shown below (the pattern is two literal back-ticks,
  followed by any non-back-tick characters, anchored at end of
  line; `-E` is portable across GNU and BSD `grep`, unlike `-P`):

  ```sh
  grep -nE '``[^`]*$' \
    src/pylocal_akuvox/_probe_outcomes.py \
    src/pylocal_akuvox/_probe_classifiers.py \
    src/pylocal_akuvox/_probe_parsers.py \
    src/pylocal_akuvox/_capability_probe.py \
    src/pylocal_akuvox/device.py \
    tests/unit/test_capability_probe.py \
    tests/unit/test_capability_module_layout.py
  ```

  Pass
  criterion: any surviving match must be reviewed by hand and, if
  the back-tick literal genuinely spans newlines, converted to an
  indented `::` literal block per FR-014 (Sphinx-W does NOT catch
  the inline-with-newline form, but it renders incorrectly). Also
  visually inspect `docs/_build/html/` rendered output for the
  four new modules' docstrings if any were modified beyond a
  verbatim cut-paste. Covers FR-014 (carry-forward retro from
  009 item 2) + the user's hard requirement "Inline RST
  `` `` … `` literals containing newlines: search for them in
  ALL touched files, convert to indented `::` blocks".
- [ ] T028 **FR-009 / FR-010 Sphinx role / data reference sweep**
  (carry-forward retro item) — run
  `grep -rnE ':mod:\`pylocal_akuvox\.capability_probe\`|:func:\`pylocal_akuvox\.capability_probe\.|:data:\`pylocal_akuvox\.capability_probe\.' docs/ src/ tests/ README.md`.
  Pass criterion: zero matches. The pre-spec sweep (`research.md`
  Decision 7) confirmed zero hits today; this final-check rerun
  catches any hits that may have been re-introduced via
  copy-paste during the refactor. Covers FR-009 + FR-010 +
  `quickstart.md` Step 14.

---

## Phase 8: Polish — atomic implementation commit

**Purpose**: Stage the entire implementation tree (4 new modules + 1
src consumer rewrite + 1 test consumer rewrite + new layout-test
extension + deletion of `capability_probe.py`) as ONE atomic commit.
The `!` marker in the subject is the load-bearing FR-007 requirement
and triggers the breaking-change announcement chain.

- [ ] T029 Stage every file changed in Phases 2–6 with `git add`:
  the four new underscore modules (T005–T008), the rewritten
  `src/pylocal_akuvox/device.py` (T009), the rewritten
  `tests/unit/test_capability_probe.py` (T010 — imports + line-4
  docstring), the extended
  `tests/unit/test_capability_module_layout.py` (T004 — 4 new test
  functions + module docstring update), and the deleted
  `src/pylocal_akuvox/capability_probe.py` (T011, via `git rm`).
  Verify with `git status` and `git diff --staged --stat`:
  expected **8 files** in the stat — **4 added** (the 4 new
  underscore modules: `_probe_outcomes.py`,
  `_probe_classifiers.py`, `_probe_parsers.py`,
  `_capability_probe.py`) + **1 deleted**
  (`capability_probe.py`) + **3 modified** (`device.py`,
  `tests/unit/test_capability_probe.py`,
  `tests/unit/test_capability_module_layout.py`). The
  layout-test file is **modified** not added since it already
  exists from spec 009. Confirm with
  `git diff --staged --name-only | wc -l` returning `8`. **The changelog edit is NOT included here** — it lives in
  Phase 9's `Docs(changelog)` commit.
- [ ] T030 Commit the staged tree as the **atomic implementation
  commit** with subject **exactly**
  `Refactor(probe)!: Split into submodules` (39 chars; verify with
  `echo -n "Refactor(probe)!: Split into submodules" | wc -c` →
  `39`; well under the project's 50-char subject-line limit per
  AGENTS.md §"Conventional Commits"). The capitalised type
  `Refactor` is per AGENTS.md §"Conventional Commits"; the `!`
  before the colon is **mandatory** per FR-007 and is the
  load-bearing marker that triggers the breaking-change
  announcement chain — this is the dedicated task that fulfills
  the user's hard requirement "the `!` mandate from FR-007 maps
  to a task that explicitly directs the implementer to use
  `Refactor(probe)!: Split into submodules` (verify exact subject
  39 chars)". Equivalent forms (with `!` and ≤50 chars) are
  acceptable per FR-007, but the recommended form is what
  `research.md` Decision 10 picked.

  Commit body:

  - First paragraph: name the spec (`010-capability-probe-split`)
    and issue (`#141`).
  - Second paragraph: enumerate the 4 new modules and the 1
    deleted module.
  - Third paragraph: name the breaking change (subpath
    `pylocal_akuvox.capability_probe` removed; both
    bare-`import` and `from`-import forms now raise
    `ModuleNotFoundError`).
  - Final lines: DCO `-s` sign-off, `Refs #141`, and a
    `Co-Authored-By:` trailer for **each AI model actually used**
    to author the implementation (e.g.
    `Co-Authored-By: Claude <claude@anthropic.com>` if Claude was
    used; `Co-Authored-By: GitHub Copilot <copilot@github.com>`
    if Copilot was used; both if both were used) per AGENTS.md
    §"AI Co-Authorship Requirements".

  All body lines ≤80 chars. Use `git commit -s` — DCO sign-off is
  mandatory. **Never use `--no-verify`** (constitution §V); the
  pre-commit hooks (run again here) MUST pass green. If pre-commit
  fails, fix in place and re-`git commit -s` (do NOT `git reset`,
  per AGENTS.md §"If Pre-Commit Fails"; do NOT
  `git commit --amend --no-verify`). Verify post-commit with
  `git log -1 --format=%s` — output MUST contain `!` before the
  colon, and `git log -1 --format=%s | wc -c` MUST return 40 (39
  chars + newline). If the contributor uses signed commits
  (recommended for repository maintainers; optional for
  drive-by contributors per the constitution / AGENTS.md silence
  on this), additionally verify with `git log -1 --show-signature`
  reporting "Good signature" — branch protection on this
  repository rejects unverified-email signatures, so anyone
  pushing a signed commit must ensure their `user.email` matches
  whichever address is bound to their signing key. Covers FR-007
  + SC-006 + constitution §V.

---

## Phase 9: Polish — documentation commit (changelog)

**Purpose**: Land the breaking-change announcement as a separate
atomic commit on the same PR. Per `plan.md` §"Phase Decomposition"
and AGENTS.md §"Atomic Commits", the changelog edit is logically
distinct from the source-code change, so it gets its own commit
even though it ships in the same PR.

- [ ] T031 Edit `docs/changelog.rst` Unreleased section: add a
  "Breaking changes" subsection (RST sub-heading) **at the same
  RST nesting depth as the existing 009-spec "Breaking changes"
  subsection** — level: `^^^^^^^^^^^^^^^^` underline (16 carets,
  matching the 009 entry's underline character count). This is
  the user's hard requirement "Changelog 'Breaking changes' RST
  sectioning matches sibling-level `^^^^…` (FR-008) so existing
  bullets don't get reparented" — verify by visually checking the
  rendered Unreleased section in `docs/_build/html/` after the
  Phase 7 T019 sphinx -W run is repeated against the staged
  changelog edit.

  Subsection MUST name:

  - **The dropped subpath**:
    `pylocal_akuvox.capability_probe` is removed.
    `import pylocal_akuvox.capability_probe` and
    `from pylocal_akuvox.capability_probe import probe_capabilities`
    both raise `ModuleNotFoundError`.
  - **The migration path**: continue calling
    `AkuvoxDevice.probe_capabilities()` (the documented public
    method) — no consumer-facing public symbol was renamed or
    removed.
  - **The issue reference**: `Refs #141`.

  Per FR-014, any multi-line literal in the new bullet MUST use
  indented `::` literal blocks, **not** inline RST double-back-tick
  cross-line spans (Sphinx-W does NOT catch the
  inline-with-newline form). After staging the edit, re-run
  `cd docs && uv run sphinx-build -W -b html . _build/html` and
  visually inspect the rendered Unreleased section — confirm the
  new "Breaking changes" subsection sits AT THE SAME LEVEL as
  the existing 009 entry and does NOT re-parent any existing
  top-level "Added" / "Changed" / "Fixed" / "Removed" subsection.
  Covers FR-008 + spec User Story 2 acceptance scenario #3 +
  the user's hard requirement on RST sectioning depth.
- [ ] T032 Stage `docs/changelog.rst` and commit as a SEPARATE
  atomic commit with subject **exactly**
  `Docs(changelog): Announce 010-probe split` (41 chars; verify
  with `echo -n "Docs(changelog): Announce 010-probe split" | wc -c`
  → `41`; under the 50-char limit). This is the dedicated task
  that fulfills the user's hard requirement "The changelog entry
  (FR-008) maps to a task creating a separate `Docs(changelog):
  …` commit on the same PR. Subject ≤50 chars". Use
  `git commit -s` (DCO mandatory) with a `Co-Authored-By:`
  trailer for each AI model actually used to author the changelog
  edit (per AGENTS.md §"AI Co-Authorship Requirements" — see
  T030 for the trailer-format details). Body explains: paragraph
  1 — what is being announced (the
  `010-capability-probe-split` breaking change); paragraph 2 —
  the migration path summary; final lines — `Refs #141` + DCO +
  the appropriate co-author trailer(s). Body lines ≤80 chars.
  Pre-commit hooks pass green; `--no-verify` is prohibited
  (constitution §V). Verify post-commit:
  `grep -B 2 -A 5 "capability_probe" docs/changelog.rst` output
  names the dropped subpath and the migration path, and lives in
  the Unreleased "Breaking changes" subsection at the
  `^^^^^^^^^^^^^^^^` underline level. Covers FR-008 + SC-005.

---

## Phase 10: Polish — PR open + Copilot review loop

**Purpose**: Push the branch, open the PR, drive the Copilot review
loop to clean. The task-list flip (T035) lands as the FINAL commit
in the PR per AGENTS.md §"Task List Updates Are Separate Commits".
The actual `gh pr merge` action happens AFTER T035 in the unnumbered
"After T035 — Merge & cleanup" prose section below — this phase
ends with three commits on the PR branch and all review threads
resolved.

- [ ] T033 Push the branch
  (`git push -u origin 010-capability-probe-split`) and open the
  PR with `gh pr create --base main`. PR title MUST match the
  implementation commit subject **exactly**
  (`Refactor(probe)!: Split into submodules`). PR body
  summarises:

  - The four new modules + their line-count budgets (per FR-004
    estimates: outcomes ~50, classifiers ~140, parsers ~175,
    capability_probe ~175 — all under the 400-line aislop
    threshold).
  - The implementation commit's file shape: **8 files**
    (4 added + 1 deleted + 3 modified — see T029 stat
    breakdown).
  - The breaking-change summary mirrored from the changelog
    entry (T031).
  - The validation-gate confirmations from Phase 7 (test count,
    coverage, aislop on new modules, sphinx -W,
    subpath-removal smoke tests).
  - `Refs #141`.

  Confirm exactly TWO commits in the PR with
  `gh pr view --json commits` at this point — the
  `Refactor(probe)!` commit and the `Docs(changelog)` commit.
  T035 below adds a third (the task-list flip) before the
  post-task merge action.
- [ ] T034 Run the Copilot review loop:
  `gh copilot-review --wait --wait-timeout 20min <PR>`. **Note**:
  `copilot-review` is a local `gh` extension / alias used by this
  project's maintainers to drive the GitHub Copilot PR-reviewer
  bot from the CLI; it is not a built-in `gh` subcommand. A
  contributor without that extension can equivalently request the
  Copilot PR review via the GitHub web UI ("Reviewers" panel →
  add `github-copilot[bot]`) and then poll for the review with
  `gh pr view <PR> --json reviews`. Address each review comment
  in turn — make the change locally, commit as a follow-up
  squash-target commit (subject like
  `Fixup: <reviewer-comment-summary>`), push. Cap: 3 rounds
  expected, 10 rounds maximum. After the final pass, **before
  T035's task-list flip and the post-task merge**, **resolve
  every review thread via the GitHub GraphQL `resolveReviewThread`
  mutation**: branch protection now blocks unresolved-conversations
  merges (lesson learned on PR #146). Pseudo-recipe per thread:

  ```bash
  gh api graphql -f query='query { repository(owner:"<OWNER>", name:"<REPO>") { pullRequest(number: <PR>) { reviewThreads(first: 50) { nodes { id isResolved } } } } }'
  # for each thread node where isResolved is false:
  gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "<id>"}) { thread { isResolved } } }'
  ```

  Verify with the `reviewThreads` query that every thread reports
  `isResolved: true`. **Do NOT use `--no-verify`** during fix-up
  commits (constitution §V); **do NOT `git reset` after a hook
  failure** (AGENTS.md §"If Pre-Commit Fails"). If review
  introduces fix-ups, those are squashed into the appropriate
  commit (`git rebase -i` and `fixup` the right commit; the PR
  remains a clean 2-commit shape before T035 adds the third).

  After any amend + force-push, **if the contributor uses signed
  commits** (recommended for repository maintainers; optional for
  drive-by contributors — neither the constitution nor AGENTS.md
  mandates signed commits as a project-wide policy), verify the
  signature post-push with
  `gh api repos/<OWNER>/<REPO>/commits/<HEAD_SHA> --jq '.commit.verification'` —
  expected `verified: true, reason: "valid"`. If
  `verified: false` is reported and the contributor wants the
  signature to verify (for example because branch protection on
  this repository rejects unverified-email signatures on the
  signed-commits path the maintainer uses), ensure
  `git config user.email` matches the email registered to the
  contributor's GPG signing key (for the repo owner that is
  `tykeal@bardicgrove.org`; other contributors use whichever
  email is bound to their own signing key), then run
  `git commit --amend --reset-author -s --no-edit` and re-push.
  Contributors who don't sign commits at all can skip this
  paragraph entirely.

---

## Phase 11: Polish — task-list flip (final commit)

- [ ] T035 In the implementation worktree (after T034's review
  loop closes and all review threads are resolved), edit
  `specs/010-capability-probe-split/tasks.md`: flip every
  `- [ ]` to `- [x]` for every task T001 through T035 (this
  task itself is the last to flip — flip it to `- [x]` as part
  of the edit). Stage the file and commit as a SEPARATE atomic
  commit with subject **exactly**
  `Docs(tasks): Mark 010 task list complete` (40 chars; verify
  with `echo -n "Docs(tasks): Mark 010 task list complete" | wc -c`
  → `40`). Use `git commit -s` with a `Co-Authored-By:` trailer
  for each AI model actually used to author the task-list flip
  (per AGENTS.md §"AI Co-Authorship Requirements" — see T030 for
  the trailer-format details). Body: brief paragraph naming the
  spec and PR; `Refs #141`; DCO + the appropriate co-author
  trailer(s). Push and confirm `gh pr view --json commits`
  reports exactly THREE commits in the PR
  (`Refactor(probe)!`, `Docs(changelog)`, `Docs(tasks)`).
  **This is the final numbered task in tasks.md** — same pattern
  as spec 009's T048. The actual `gh pr merge` action is
  described in the prose footer below and is NOT tracked as a
  numbered task because it adds no commit. **Never use
  `--no-verify`** (constitution §V); **never `git reset` after a
  pre-commit hook failure** (AGENTS.md §"If Pre-Commit Fails").
  Covers AGENTS.md §"Task List Updates Are Separate Commits".

---

### After T035 — Merge & cleanup (not a numbered task; no new commit)

After T035 commits and pushes the third commit on the PR, perform
the merge and worktree cleanup:

1. **Merge order matters** because of a known worktree-cleanup
   gotcha (lesson learned on plan PR #146):
   `gh pr merge --delete-branch` will fail if the local worktree
   still references the branch. Pick ONE of these orderings:
   - **(a) worktree-first**: from the repo root / main checkout,
     run `git worktree remove <worktree-path> --force` FIRST,
     then `gh pr merge <PR> --merge --delete-branch`. The
     `--force` flag is needed because the worktree carries reflog
     state that `gh pr merge --delete-branch`'s underlying
     `git branch -D` would refuse to delete.
   - **(b) merge-first**: `gh pr merge <PR> --merge --delete-branch`
     first; the local branch deletion will fail; clean up after
     with `git worktree remove <worktree-path> --force` and
     `git branch -D 010-capability-probe-split`.
2. **End state**: the worktree is gone, the local branch is
   deleted, `main` is fast-forwarded to the merged commit, and
   `gh pr view <PR> --json state` reports `MERGED`.
3. **Final post-merge verification on `main`**:
   - `uv run python -c "import pylocal_akuvox.capability_probe"`
     → exits non-zero with `ModuleNotFoundError` (SC-003);
   - `uv run python -c "from pylocal_akuvox.capability_probe import probe_capabilities"`
     → exits non-zero with `ModuleNotFoundError` (SC-003);
   - `uv run python -c "import pylocal_akuvox; assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities); print('ok')"`
     → prints `ok` (SC-004);
   - `git log --format=%s main | grep '^Refactor(probe)!'` finds
     the implementation commit subject containing `!` before the
     colon (SC-006).
4. After the post-merge verification clears, every FR / SC has
   been verified end-to-end on `main` and issue #141 can be
   closed.

---

## Dependencies

- **T001 → T002 → T003** (Setup): sequential. Baseline must come
  first.
- **T004** (TDD red): runs after T002 but is independent of T003.
  Cannot be skipped — it is the FR-011 deliverable and the
  constitution §II proof.
- **T005 → {T006, T007}** (module creation): T005
  (`_probe_outcomes`) MUST be staged first because T006
  (`_probe_classifiers`) imports from it. T007 (`_probe_parsers`)
  has no sibling dependency, so once T005 is staged T006 and T007
  can run **in parallel** (`[P]` markers on both). T008
  (`_capability_probe`) depends on all three siblings and runs
  last — sequential.
- **T009** (`device.py` rewrite): requires T008 (the new
  `_capability_probe` module must exist for the import to
  resolve).
- **T010** (test consumer rewrite): requires T005, T006, T007,
  T008 (every new underscore module must exist for the test
  imports to resolve). Independent of T009 in source terms but
  conventionally runs after.
- **T011** (delete `capability_probe.py`): requires T009 + T010
  (zero `from pylocal_akuvox.capability_probe` matches confirmed
  by re-running the grep before this task). After T011, T004's
  layout test goes green.
- **T012–T028** (validation gates): all require T011.
  T012/T013/T014/T015/T016 serialise; T017/T018/T019 are `[P]`
  after T016. T020–T028 are read-only smoke checks and could
  also be `[P]` but are kept sequential for output readability.
- **T029 → T030** (stage + atomic commit): sequential. T029
  stages, T030 commits.
- **T031 → T032** (changelog edit + commit): sequential.
  Independent of T029/T030 in source terms but logically follows
  the implementation commit so the PR ordering is
  Refactor → Docs(changelog) → Docs(tasks).
- **T033 → T034 → T035** (push, review, flip): sequential. T035
  (task-list flip) is the FINAL numbered task and lands as the
  third PR commit; the actual `gh pr merge` is an unnumbered
  post-task action.

---

## Parallel-execution opportunities

The probe-side dependency DAG is strict (per `plan.md`
§"Cross-module dependency graph (post-split)") — no lazy imports,
no back-edges. Genuine parallelism opportunities:

- **Phase 3**: T006 (`_probe_classifiers`) and T007
  (`_probe_parsers`) are `[P]`-safe once T005 (`_probe_outcomes`)
  is staged. `_probe_classifiers` depends on `_probe_outcomes`
  but NOT on `_probe_parsers`; `_probe_parsers` depends on
  neither sibling. The two modules can be authored concurrently.
- **Phase 7**: After T016 (the load-bearing pre-commit gate),
  T017/T018/T019 are read-only and `[P]`-safe — run aislop
  new-module scan, aislop project-wide scan, and sphinx-build
  concurrently.
- **Phases 4, 5, 6**: SEQUENTIAL. Each phase has a single task,
  so `[P]` is moot.

---

## Coverage Map: FR / SC → Tasks

For pre-merge auditing. Every FR-001 through FR-014 and SC-001
through SC-009 must appear in the right column.

### Functional Requirements

| Requirement | Implementing tasks | Verifying tasks |
|---|---|---|
| **FR-001** `AkuvoxDevice.probe_capabilities()` invariance | T009 (rewrite preserves the public method) | T004 (assertion 4), T012, T013, T022 |
| **FR-002** `import pylocal_akuvox.capability_probe` raises `ModuleNotFoundError` | T011 | T004 (assertion 1), T020 |
| **FR-003** `from pylocal_akuvox.capability_probe import X` raises | T011 | T004 (assertion 2), T021 |
| **FR-004** Each new submodule below 400-line aislop threshold | T005, T006, T007, T008 | T016, T017 |
| **FR-005** Internal symbols importable from underscore modules | T005, T006, T007, T008 | T004 (assertion 3), T023 |
| **FR-006** All existing tests pass unchanged in semantic behavior | T009, T010 | T012, T013 |
| **FR-007** Implementation commit uses `!` breaking-change marker | T030 | T030 (post-commit `git log` check); post-merge re-check in the unnumbered "After T035 — Merge & cleanup" verification list |
| **FR-008** Changelog "Breaking changes" subsection | T031, T032 | T032 (post-commit `grep` check), T019 (sphinx -W rerun against staged changelog) |
| **FR-009** README + quickstart sweep — no stale references | T003 (verify) | T028 (Sphinx role / data reference sweep) |
| **FR-010** Sphinx extension and API page — no updates needed | T003 (verify) | T019, T028 |
| **FR-011** Layout-assertion test (extend existing file) | T004 | T011 (test goes green), T012 |
| **FR-012** Internal-import policy preserved | T005, T006, T007, T008 | T012 (full test suite confirms no cycle), T015 (mypy strict) |
| **FR-013** Pre-PR docstring sweep | T010 (line-4 docstring fix), T026 (stale-phrase consumer sweep) | T025 (import-form sanity grep), T026 |
| **FR-014** Inline RST literal hygiene | T031 (changelog edit follows the rule) | T027 (inline RST literal hygiene scan) |

### Success Criteria

| Criterion | Verification task |
|---|---|
| **SC-001** Full test suite green | T012 (+ T013 coverage) |
| **SC-002** No aislop `file-too-large` on new modules | T016, T017, T018 |
| **SC-003** Subpath removal confirmed | T020 (import form), T021 (from form), T004 assertions 1+2; post-merge re-run in the unnumbered "After T035" verification list |
| **SC-004** Public probe still works via device | T022, T004 assertion 4; post-merge re-run in the unnumbered "After T035" verification list |
| **SC-005** Changelog entry present | T032 (post-commit `grep` check) |
| **SC-006** Commit subject has `!` and ≤50 chars | T030 (post-commit check); post-merge re-check in the unnumbered "After T035" verification list |
| **SC-007** Sphinx -W clean | T019 |
| **SC-008** Original file is gone | T011 (delete), T024 (smoke check) |
| **SC-009** Layout assertions pass | T011 (turns the test green), T012 |

### Contracts

| Contract | Tasks |
|---|---|
| `contracts/probe-outcomes.md` | T005 (creation), T010 (test rewrites land at `_probe_outcomes`), T004 assertion 3 |
| `contracts/probe-classifiers.md` | T006 (creation), T010 (test rewrites land at `_probe_classifiers`), T004 assertion 3 |
| `contracts/probe-parsers.md` | T007 (creation), T010 (test rewrites land at `_probe_parsers`), T004 assertion 3 |
| `contracts/capability-probe.md` | T008 (creation), T009 (`device.py` consumer rewrite), T010 (test top-of-file rewrite), T004 assertion 3 + 4 |

---

## Implementation Strategy

**MVP scope (smallest shippable increment)**: This refactor IS the
MVP. There is no smaller shippable slice — `plan.md` §"Phase
Decomposition" justifies the single-PR atomic-rename pattern as the
only viable shape. The whole point is for the file split to land
atomically with its consumers.

**Incremental delivery**:

1. **Spec PR (#149)**: artifacts. MERGED at SHA `f34fa70` (merge
   `ea217ab`).
2. **Plan PR (#150)**: artifacts. MERGED at SHA `d9e1269` (merge
   `8ea1029`).
3. **Tasks PR (this file)**: artifacts. About to merge.
4. **Implementation PR**: code + changelog + task-list flip
   (Phases 2–11 above). Single PR, three commits.

**Parallelisable work**:

- Within Phase 3: T006/T007 are `[P]`-safe after T005.
- Within Phase 7: T017/T018/T019 are `[P]`-safe after T016.
- All other phases: SEQUENTIAL.

**Risk hedges**:

- **Cycle risk during module authoring**: The probe-side
  dependency DAG is strict (per `plan.md` §"Cross-module dependency
  graph (post-split)"). T006 imports only from `_probe_outcomes` +
  `_capability_types`; T007 imports only from
  `_capability_profile` + `_capability_types` + `exceptions`. T008
  imports from all three siblings + the pre-existing capability +
  exceptions + models modules. No back-edges, no lazy imports
  needed (unlike spec 009 where `_capability_matching` ↔
  `capability_matrix` required a function-body lazy import).
- **Line numbers drift**: Phase 5 T010 cites line numbers from
  `main` at SHA `4fc75e8`. The task instructs the implementer to
  refresh with `grep -n` before editing. If line numbers have
  drifted, the symbol→module table in `data-model.md` is the
  canonical reference.
- **Branch-protection unresolved-conversations merge block**: T034
  embeds the GraphQL `resolveReviewThread` recipe up-front to
  avoid the pre-merge stall pattern observed on PR #146.
- **Worktree cleanup ordering**: the unnumbered "After T035 —
  Merge & cleanup" prose section documents both viable orderings
  (worktree-first vs merge-first) so the implementer can pick
  whichever fits their local state.
- **GPG signature mismatch on amend + force-push**: T034 includes
  the `gh api ... .commit.verification` recheck recipe and the
  `git config user.email <signing-identity>` +
  `git commit --amend --reset-author -s --no-edit` recovery
  pattern (the email must match whichever address is bound to the
  committer's GPG signing key — for the repo owner that is
  `tykeal@bardicgrove.org`).
- **Pre-commit hook failures during T030 / T032 / T035**:
  constitution §V prohibits `--no-verify`; AGENTS.md §"If
  Pre-Commit Fails" prohibits `git reset` after a hook failure
  (the constitution echoes "do NOT reset; do NOT bypass" at §V
  step 5). Each commit task in those phases includes the relevant
  reminders.
- **FR-013 stale-phrase contamination from spec-009 paste-overs**:
  T026 enumerates the four 009-flavored phrases (`dataclass`,
  `lazy import`, `cycle`, `defined here`) explicitly. None apply
  to the live `capability_probe.py` source today, so any match
  signals a paste-from-009 accident.
- **FR-014 inline-RST-literal renderer trap**: T027 scans every
  touched file for cross-line back-tick literals. Sphinx-W does
  NOT catch this form, so the grep is the only mechanical defense.

---

## Anomalies / open questions

None at task-generation time. All FR-001 through FR-014 / SC-001
through SC-009 / contract artifacts have explicit task coverage;
the dependency DAG is acyclic; commit subjects are verified
≤50 chars (39 / 41 / 40); the `!` mandate has a dedicated task
(T030); the changelog entry is a separate commit (T031/T032); the
atomic checkbox-flip commit (T035) is the final numbered task.
Three rubber-duck rounds anticipated; cap 10.
