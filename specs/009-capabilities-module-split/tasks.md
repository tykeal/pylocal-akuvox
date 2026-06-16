<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Refactor capabilities.py Under Aislop Size Limit

**Input**: Design documents from `/specs/009-capabilities-module-split/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md,
contracts/capability-types.md, contracts/capability-profile.md,
contracts/capability-matching.md, contracts/capability-defaults.md,
quickstart.md
**Branch**: `009-capabilities-module-split` is the implementation branch
that will host the single atomic refactor PR. The spec/plan/tasks
artifacts each ship on their own short-lived `docs/009-…` branch.

**Tests are MANDATORY** per constitution §II (TDD). The single new
behavioral test file (`tests/unit/test_capability_module_layout.py`)
is authored first locally — RED against `main` because
`capabilities.py` still exists — and only goes GREEN once the four new
underscore modules are staged alongside the deletion of
`capabilities.py`. The published implementation commit is green at
every CI gate.

**Atomic commits** per AGENTS.md §"Atomic Commits" + §"Task List
Updates Are Separate Commits": this refactor lands as **ONE PR
containing exactly THREE commits** —

1. The `Refactor(capabilities)!: …` implementation commit (single atomic
   commit covering all four new modules + the `__init__.py` rewrite +
   all 19 consumer-import rewrites + the deletion of `capabilities.py`
   + the new layout test). The `!` is mandatory per FR-007.
2. The `Docs(changelog): …` commit (separate atomic commit; FR-008 —
   the changelog entry rides in the same PR but is its own commit
   per AGENTS.md §"Task List Updates Are Separate Commits" reasoning
   applied to the documentation/announcement boundary).
3. The `Docs(tasks): …` checkbox-flip commit (final commit in the PR;
   marks every task in this file complete).

**Phasing**: ONE phase, ONE PR (per `plan.md` §"Phase Decomposition").
The phases below are an authoring/verification ordering — they do NOT
correspond to separate PRs.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no
  incomplete dependencies).
- This refactor has only **one user story** at the implementation level
  — the atomic split itself — so no per-story labels are used; the spec's
  US1 / US2 / US3 priorities are mapped via the FR / SC coverage table at
  the end of this file.
- Every task names exact file path(s) and the FR(s) / SC(s) /
  contract(s) it implements or verifies.

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, `tests/unit/`,
`docs/_ext/`, `docs/`. Spec artifacts in
`specs/009-capabilities-module-split/`.

---

## Phase 1: Setup (baseline + working-tree hygiene)

**Purpose**: Capture the pre-refactor baseline so post-refactor
validation gates can compare numerically, and prepare the working tree
for the implementation branch.

- [x] T001 Capture pre-refactor baseline metrics on `main` at the
  current head: (a) test count from `uv run pytest tests/ --collect-only -q | tail -1`;
  (b) branch coverage by running `uv run pytest tests/` and reading
  the generated repo-root `coverage.xml`
  (`<coverage line-rate>` and `<coverage branch-rate>` attributes —
  must be 1.0 / 100% for `pylocal_akuvox`); (c) line count for the
  doomed file with `wc -l src/pylocal_akuvox/capabilities.py`
  (expected: 455, FR-004 baseline); (d) the current
  `uv run aislop scan` output — confirm `capabilities.py` is flagged
  with `complexity/file-too-large` and that `device.py` /
  `capability_probe.py` are also flagged (those two are out of scope
  per spec §"Out of Scope" — issues #142 and #141). Record the (a)–(c)
  numbers in the implementation PR description so SC-001, FR-006, and
  FR-004 have explicit before/after comparisons. Covers FR-006 baseline
  + SC-001 baseline + FR-004 baseline.
- [x] T002 Create the implementation worktree on a fresh branch off
  `main`:
  `git worktree add ../pylocal-akuvox-009 -b 009-capabilities-module-split main`.
  All subsequent edits in Phases 2–8 happen in that worktree. The
  spec PR (#145), plan PR (#146), and this tasks PR each shipped on
  their own `docs/009-…` branch and have already merged; the
  implementation branch above is the FOURTH and final 009-related
  branch.
- [x] T003 Spot-check FR-009: run
  `grep -nE 'pylocal_akuvox\.capabilities' README.md` and confirm
  zero matches. The spec already attests this is true on `main`; this
  task records the verification in the implementer's local notes so
  the PR description can cite the check. Covers FR-009.

---

## Phase 2: TDD red — author the layout-assertion test FIRST

**Purpose**: Per constitution §II, write the failing test before any
code change. The test is RED against `main` (because `capabilities.py`
still exists, so `import pylocal_akuvox.capabilities` succeeds and
Assertion 1 fails). Once the four new underscore modules + the
deletion of `capabilities.py` are also staged in the SAME commit, the
test goes GREEN. The published commit is therefore green at every CI
gate; the "red phase" only ever exists in the implementer's working
tree during authoring. **This task does NOT create the new module
files** — those come in Phase 3.

- [x] T004 Create `tests/unit/test_capability_module_layout.py` with
  SPDX header pair, module docstring naming spec
  `009-capabilities-module-split`, and **all five assertions** verbatim
  from `plan.md` §"Subpath-Removal Verification Plan":

  1. `test_capabilities_subpath_is_gone` — asserts
     `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`
     (uses `pytest.raises(ModuleNotFoundError)`). FR-002 / SC-003.
  2. `test_capabilities_subpath_from_import_is_gone` — asserts
     `from pylocal_akuvox.capabilities import Capability` raises
     `(ModuleNotFoundError, ImportError)` (catches both because
     `ModuleNotFoundError` is a subclass of `ImportError` and the
     wider tuple is forward-compatible with future Python versions
     that might narrow). Uses `exec()` because a static
     `from pylocal_akuvox.capabilities import Capability` at the
     test module's top level would be evaluated at module-import /
     pytest-collection time — outside the `pytest.raises` context —
     and would itself raise `ModuleNotFoundError` post-split,
     preventing the test module from loading. FR-003.
  3. `test_underscore_modules_importable` — uses `importlib.import_module`
     to import each of `pylocal_akuvox._capability_types`,
     `_capability_profile`, `_capability_matching`,
     `_capability_defaults` and asserts each call returns without
     raising. FR-005.
  4. `test_public_symbols_roundtrip_via_top_level` — for each of the 5
     public symbols (`Capability`, `CapabilityStatus`, `SchemaShape`,
     `DeviceCapabilities`, `FieldAliases`), asserts identity equality
     (`is`) between `pylocal_akuvox.X` and the symbol in its source
     underscore module (`_capability_types` or `_capability_profile`).
     FR-001 + spec User Story 1 acceptance scenario #1.
  5. `test_capability_symbols_in_top_level_all` — asserts each of the
     5 public capability names is present in
     `pylocal_akuvox.__all__` (belt-and-suspenders against an
     accidental `__all__` edit). FR-001.

  Locally run `uv run pytest tests/unit/test_capability_module_layout.py -v`;
  expected output: Assertion 1 FAILS (because `capabilities.py` still
  exists); Assertions 3–5 may pass or fail depending on whether the
  underscore modules exist yet (they do not, so 3 also FAILS); Assertion 2
  fails (the static-`exec` import succeeds because the subpath
  resolves on `main`); Assertion 4 fails (no
  `_capability_types` / `_capability_profile` modules exist). At least
  one assertion FAILS — that is the red proof. Do NOT commit yet —
  T004 stages a file that only goes green once the rest of Phase 3 + 4
  + 8 are also staged. Covers FR-011.

---

## Phase 3: Core implementation — create the four new underscore modules

**Purpose**: Author the four sibling underscore-prefixed modules as
described in `plan.md` §"File-by-File Plan" and the four `contracts/`
files. Each module gets a verbatim cut-paste of the relevant chunk of
`capabilities.py` (no body changes) plus a fresh SPDX header pair,
focused module docstring, ordered imports, and `__all__`. **No imports
in any other file change yet** — `capabilities.py` is still intact at
the end of this phase, so the package continues to import cleanly.

The four modules form a strict dependency chain
(`_capability_types` ← `_capability_profile` ← {`_capability_matching`,
`_capability_defaults`}), so they MUST be created **in dependency
order**. None of T005–T008 can be parallelised; each module's imports
must resolve against the already-staged earlier modules.

- [x] T005 Create `src/pylocal_akuvox/_capability_types.py` per
  `contracts/capability-types.md` and `plan.md` §"New module 1". SPDX
  header pair; module docstring naming spec
  `009-capabilities-module-split` and the single concern ("foundational
  type vocabulary for the capability system"). Imports:
  `from __future__ import annotations` and `import enum`. Cut-paste the
  bodies of `Capability`, `CapabilityStatus`, and `SchemaShape` enums
  **verbatim** from `src/pylocal_akuvox/capabilities.py` — no member
  rename, no value change, no method addition.
  `__all__ = ["Capability", "CapabilityStatus", "SchemaShape"]`.
  Verify locally:
  `uv run python -c "from pylocal_akuvox._capability_types import Capability, CapabilityStatus, SchemaShape; print('ok')"`
  prints `ok`. Covers FR-004 (this module ≤120 lines), FR-005 (the
  three types listed in `_capability_types`), and the
  `contracts/capability-types.md` Public Surface clause.
- [x] T006 Create `src/pylocal_akuvox/_capability_profile.py` per
  `contracts/capability-profile.md` and `plan.md` §"New module 2". SPDX
  header pair; module docstring naming the single concern (capability
  profile dataclasses: `FieldAliases`, `Provenance`,
  `DeviceCapabilities`). Imports per plan: `from __future__ import
  annotations`, `from dataclasses import dataclass, field`,
  `from types import MappingProxyType`, `from typing import TYPE_CHECKING`;
  first-party `from pylocal_akuvox._capability_types import (Capability,
  CapabilityStatus, SchemaShape)` and
  `from pylocal_akuvox.exceptions import AkuvoxUnsupportedError`; under
  `TYPE_CHECKING:` `from collections.abc import Mapping`. Cut-paste
  the bodies of `FieldAliases`, `Provenance`, and `DeviceCapabilities`
  (including `__post_init__`, `status_of`, `require`, `supported_set`)
  **verbatim** from `capabilities.py`.
  `__all__ = ["DeviceCapabilities", "FieldAliases", "Provenance"]`
  (alphabetical). Verify locally:
  `uv run python -c "from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases, Provenance; print('ok')"`.
  Covers FR-004 (≤210 lines), FR-005 (`Provenance` from
  `_capability_profile`), and `contracts/capability-profile.md`.
  **Cycle check** before commit: confirm
  `pylocal_akuvox.exceptions` only imports `Capability` under
  `TYPE_CHECKING` (currently `exceptions.py:11`) — if not, the import
  added here would form a runtime cycle.
- [x] T007 Create `src/pylocal_akuvox/_capability_matching.py` per
  `contracts/capability-matching.md` and `plan.md` §"New module 3". SPDX
  header pair; module docstring naming the single concern (firmware
  band parsing + device-class pattern matching + matrix dispatch).
  Top-level imports: `from __future__ import annotations`,
  `from dataclasses import dataclass, field`,
  `from typing import TYPE_CHECKING`; first-party
  `from pylocal_akuvox._capability_profile import DeviceCapabilities`;
  under `TYPE_CHECKING:`
  `from pylocal_akuvox.models import DeviceInfo`. Cut-paste
  `_parse_firmware_segments`, `DeviceClassPattern` (full body
  including `__post_init__` and `matches()`), and `lookup_capabilities`
  **verbatim** from `capabilities.py` — including the **lazy
  function-body import** `from pylocal_akuvox.capability_matrix import
  CAPABILITY_MATRIX` inside `lookup_capabilities` (this preserves the
  existing circular-dependency break at the current
  `capabilities.py:446–449` site; without it the new module would form
  a hard cycle with `capability_matrix.py`, which itself imports
  `DeviceClassPattern` from `_capability_matching` post-split per Phase 5
  T011).
  `__all__ = ["DeviceClassPattern", "lookup_capabilities"]`
  (`_parse_firmware_segments` is single-underscore-prefixed and is
  intentionally NOT in `__all__` — but is importable from the module
  for white-box testing per spec Decision 6). Verify locally:
  `uv run python -c "from pylocal_akuvox._capability_matching import DeviceClassPattern, lookup_capabilities, _parse_firmware_segments; print('ok')"`.
  Covers FR-004 (≤210 lines), FR-005 (`DeviceClassPattern`,
  `lookup_capabilities` from `_capability_matching`), and
  `contracts/capability-matching.md`.
- [x] T008 Create `src/pylocal_akuvox/_capability_defaults.py` per
  `contracts/capability-defaults.md` and `plan.md` §"New module 4". SPDX
  header pair; module docstring naming the single concern (default
  user field-alias constant). Imports: `from __future__ import
  annotations` and `from pylocal_akuvox._capability_profile import
  FieldAliases`. Cut-paste `DEFAULT_USER_FIELD_ALIASES` **verbatim**
  from `capabilities.py`.
  `__all__ = ["DEFAULT_USER_FIELD_ALIASES"]`. Verify locally:
  `uv run python -c "from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES; print('ok')"`.
  Covers FR-004 (≤40 lines), FR-005 (`DEFAULT_USER_FIELD_ALIASES` from
  `_capability_defaults`), and `contracts/capability-defaults.md`.

---

## Phase 4: Core implementation — wire `__init__.py` re-exports through the new modules

**Purpose**: Bridge step. Once the four new modules exist (Phase 3),
flip the top-level package's re-export source from `capabilities` to
the new underscore modules. After this single edit and BEFORE deleting
`capabilities.py` or rewriting any consumer, `pylocal_akuvox.Capability`
and the other 4 public symbols already trace through the new
underscore modules — validates the bijection without breaking
anything (`capabilities.py` still exists; consumers' imports through
the old path also still work). This is the load-bearing safety net of
the refactor: at the end of Phase 4, the package imports cleanly via
two paths (old + new), making the rest of the migration mechanical.

- [x] T009 In `src/pylocal_akuvox/__init__.py` line 9, replace the
  single `from pylocal_akuvox.capabilities import (Capability,
  CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape)`
  block with two blocks ordered alphabetically by module name (matches
  existing project ruff/isort style):
  (i) `from pylocal_akuvox._capability_profile import (DeviceCapabilities, FieldAliases)`;
  (ii) `from pylocal_akuvox._capability_types import (Capability, CapabilityStatus, SchemaShape)`.
  **Top-level `__all__` is untouched** — same 5 capability names
  appear there as today (FR-001). Verify locally:
  `uv run python -c "import pylocal_akuvox; assert pylocal_akuvox.Capability.__module__ == 'pylocal_akuvox._capability_types'; print('ok')"`
  prints `ok` (proves the re-export now traces through the new
  module). Also re-run T004's layout test: Assertion 4
  (round-trip via top-level) now PASSES; Assertion 1 (subpath gone)
  still FAILS because `capabilities.py` is still present. Covers
  FR-001.
- [x] T010 Run a smoke import check after T009:
  `uv run python -c "from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape; print('ok')"` —
  this is the SC-004 verification command and MUST print `ok` cleanly.
  Then run `uv run python -c "import pylocal_akuvox.capabilities; print('still here')"` —
  this MUST also print `still here` (because `capabilities.py` has not
  been deleted yet; subpath imports continue to work until Phase 8
  T031). Confirms the bijection: both old and new paths resolve to
  the same Python objects after T009. Covers FR-001 verification mid-flight.

---

## Phase 5: Migration — production source consumer rewrites

**Purpose**: Rewrite all 9 production-source `from
pylocal_akuvox.capabilities import …` sites in `src/pylocal_akuvox/`
(excluding `__init__.py`, which was rewritten in Phase 4 T009) to use
the new underscore modules per the symbol→module table in
`data-model.md` §"Module Layout Table" and `plan.md`
§"Import-Rewrite Plan" Group A. **No `[P]` markers** here per the
user-direction in the task generation prompt: the import-rewrite
surface is conceptually shared even though each file is distinct, so
ordering them sequentially keeps the diff easy to review.

After each task completes, re-run `uv run pytest tests/ -x -q` locally
to confirm nothing has regressed (because `capabilities.py` still
exists, both old and new import paths resolve, so partial migration
states all stay green). The full pytest gate runs in Phase 9 T032.

- [x] T011 Rewrite `src/pylocal_akuvox/capability_matrix.py`. Replace
  the line-35 block `from pylocal_akuvox.capabilities import (…)` with
  three blocks ordered alphabetically by underscore-module name:
  `_capability_matching` for `DeviceClassPattern`;
  `_capability_profile` for `DeviceCapabilities`, `FieldAliases`,
  `Provenance`; `_capability_types` for `Capability`,
  `CapabilityStatus`, `SchemaShape`. Also rewrite the lines 8 and 12
  RST cross-references per `research.md` Decision 7 strategy (c) —
  use the underscore path (e.g. `:mod:\`pylocal_akuvox._capability_types\``).
  Internal-only file, so the underscore path is appropriate.
  Covers FR-005 (consumer-side) + FR-006.
- [x] T012 Rewrite `src/pylocal_akuvox/capability_probe.py`. Replace
  the line-30 `from pylocal_akuvox.capabilities import (…)` block per
  the symbol→module table — split into `_capability_types` and
  `_capability_profile` blocks ordered alphabetically by module name.
  No docstring cross-references in this file per
  `research.md` Decision 7 audit. Covers FR-005 + FR-006.
- [x] T013 Rewrite `src/pylocal_akuvox/capability_adapters.py`.
  Replace line-22 `from pylocal_akuvox.capabilities import Capability`
  with `from pylocal_akuvox._capability_types import Capability`.
  Single-line edit. Covers FR-005 + FR-006.
- [x] T014 Rewrite `src/pylocal_akuvox/device.py` — five sites in one
  task because they all live in the same file:
  (i) line 13 top-level block split per symbol→module table;
  (ii) line 333 deferred `from pylocal_akuvox.capabilities import DEFAULT_USER_FIELD_ALIASES`
  → `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`;
  (iii) line 385 same as (ii);
  (iv) line 802 deferred `from pylocal_akuvox.capabilities import SchemaShape`
  → `from pylocal_akuvox._capability_types import SchemaShape`;
  (v) line 828 same as (iv).
  Note: line numbers cited from `main` at SHA `fe461d7` — re-run
  `grep -n 'from pylocal_akuvox.capabilities' src/pylocal_akuvox/device.py`
  before editing to refresh against current state. Covers FR-005 + FR-006.
- [x] T015 Rewrite `src/pylocal_akuvox/users.py` — two import sites
  plus three docstring sites:
  (i) line 11
  `from pylocal_akuvox.capabilities import DEFAULT_USER_FIELD_ALIASES`
  → `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`;
  (ii) line 17 `TYPE_CHECKING` block
  `from pylocal_akuvox.capabilities import DeviceCapabilities, FieldAliases`
  → `from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases`;
  (iii)–(v) lines 78, 153, 282 — RST cross-references
  `:data:\`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES\``.
  Per `research.md` Decision 7 strategy (a) — these are user-facing
  rendered docstrings, so spell out the value inline rather than
  retain the dropped subpath. Consult
  `src/pylocal_akuvox/_capability_defaults.py` (after T008 stages it)
  for the canonical literal value, then replace the `:data:` ref with
  a prose description that names the constant's intent and quotes
  the literal value (e.g. "the default user field aliases —
  ``FieldAliases(read=(...), write=(...))``"). Do NOT leak the
  `_capability_defaults` underscore path into user-facing rendered
  docs. Covers FR-005 + FR-006 + FR-009.
- [x] T016 Rewrite `src/pylocal_akuvox/contacts.py` — two sites:
  (i) line 19
  `from pylocal_akuvox.capabilities import SchemaShape`
  → `from pylocal_akuvox._capability_types import SchemaShape`;
  (ii) line 25 `TYPE_CHECKING` block
  `from pylocal_akuvox.capabilities import DeviceCapabilities`
  → `from pylocal_akuvox._capability_profile import DeviceCapabilities`.
  Covers FR-005 + FR-006.
- [x] T017 Rewrite `src/pylocal_akuvox/exceptions.py` — single site at
  line 11 (`TYPE_CHECKING` block):
  `from pylocal_akuvox.capabilities import Capability`
  → `from pylocal_akuvox._capability_types import Capability`.
  This rewrite does NOT introduce a runtime cycle because the import
  remains under `TYPE_CHECKING:` (verified pre-edit). Covers FR-005 +
  FR-006.
- [x] T018 Rewrite `src/pylocal_akuvox/models/users.py` — two import
  sites plus one docstring site:
  (i) line 14 `TYPE_CHECKING` block
  `from pylocal_akuvox.capabilities import DeviceCapabilities`
  → `from pylocal_akuvox._capability_profile import DeviceCapabilities`;
  (ii) line 57 deferred
  `from pylocal_akuvox.capabilities import DEFAULT_USER_FIELD_ALIASES`
  → `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`;
  (iii) line 49 RST cross-reference
  `:data:\`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES\`` —
  per `research.md` Decision 7 strategy (a), spell out the value
  inline (same prose-replacement pattern as users.py lines 78/153/282
  in T015 — consult `_capability_defaults.py` for the canonical
  literal). Covers FR-005 + FR-006 + FR-009.
- [x] T019 Rewrite `src/pylocal_akuvox/models/contacts.py` — two
  sites: (i) line 14 `TYPE_CHECKING` block
  `from pylocal_akuvox.capabilities import DeviceCapabilities`
  → `from pylocal_akuvox._capability_profile import DeviceCapabilities`;
  (ii) line 61 deferred
  `from pylocal_akuvox.capabilities import SchemaShape`
  → `from pylocal_akuvox._capability_types import SchemaShape`. No
  docstring cross-references in this file. Covers FR-005 + FR-006.

---

## Phase 6: Migration — Sphinx extension

- [x] T020 Rewrite `docs/_ext/capability_matrix.py` line 30:
  `from pylocal_akuvox.capabilities import Capability, CapabilityStatus`
  → `from pylocal_akuvox._capability_types import Capability, CapabilityStatus`.
  Per FR-010, the underscore path is appropriate here because this is
  a maintainer-internal Sphinx extension, not a public consumer
  integration. Covers FR-010 + FR-006.

---

## Phase 7: Migration — test consumer rewrites

**Purpose**: Rewrite all 9 `from pylocal_akuvox.capabilities import …`
sites across the test suite per `plan.md` §"Import-Rewrite Plan"
Group C and the symbol→module table. White-box tests asserting on
internal symbols (`Provenance`, `DeviceClassPattern`,
`lookup_capabilities`, `DEFAULT_USER_FIELD_ALIASES`) MUST import
from the underscore modules per spec Decision 6 — black-box tests
verifying the public surface use top-level
`from pylocal_akuvox import …`. **No test assertion semantics change**
— only the import lines flip.

- [x] T021 Rewrite `tests/unit/test_capabilities.py`. Site at line 22
  (single block) splits per symbol→module table across
  `_capability_types`, `_capability_profile`, `_capability_matching`,
  and `_capability_defaults`. Module docstring at line 4 mentions
  `capabilities` module — rewrite to underscore path per
  `research.md` Decision 7 strategy (c) (e.g. "Tests for the
  capability profile types in
  ``pylocal_akuvox._capability_types`` and
  ``pylocal_akuvox._capability_profile``"). Covers FR-006.
- [x] T022 Rewrite `tests/unit/test_pattern.py`. Single site at line
  25: `from pylocal_akuvox.capabilities import DeviceClassPattern`
  → `from pylocal_akuvox._capability_matching import DeviceClassPattern`.
  Covers FR-006 + spec US3 acceptance scenario #2.
- [x] T023 Rewrite `tests/unit/test_dispatch.py`. Single site at line
  37: `from pylocal_akuvox.capabilities import Capability`
  → `from pylocal_akuvox._capability_types import Capability`.
  Covers FR-006.
- [x] T024 Rewrite `tests/unit/test_users.py` — 13 sites total
  (lines 22, 844, 898, 924, 965, 1002, 1041, 1103, 1164, 1243, 1277,
  1397, 1432). Most are inline-in-test deferred imports. For each
  site, split per symbol→module table:
  `Capability`/`CapabilityStatus` → `_capability_types`;
  `DeviceCapabilities`/`FieldAliases` → `_capability_profile`;
  `DEFAULT_USER_FIELD_ALIASES` → `_capability_defaults`. Note: line
  numbers are from `main` at SHA `fe461d7` — refresh with
  `grep -n 'from pylocal_akuvox.capabilities' tests/unit/test_users.py`
  before editing. Covers FR-006.
- [x] T025 Rewrite `tests/unit/test_contacts.py` — 10 sites total
  (lines 22, 554, 589, 615, 646, 677, 699, 720, 789, 855). Split per
  symbol→module table; mostly
  `SchemaShape`/`Capability`/`CapabilityStatus` → `_capability_types`,
  `DeviceCapabilities` → `_capability_profile`. Refresh line numbers
  with grep before editing. Covers FR-006.
- [x] T026 Rewrite `tests/unit/test_device.py` — 8 sites total (lines
  573, 606, 703, 851, 870, 889, 985, 1107). Split per symbol→module
  table; line 703 includes `lookup_capabilities` →
  `_capability_matching`. Refresh line numbers with grep before
  editing. Covers FR-006.
- [x] T027 Rewrite `tests/unit/test_matrix.py` — 2 sites (lines 26,
  241). Split each per symbol→module table — covers
  `DeviceClassPattern` (`_capability_matching`),
  `Provenance`/`DeviceCapabilities`/`FieldAliases`
  (`_capability_profile`),
  `Capability`/`CapabilityStatus` (`_capability_types`).
  Covers FR-006 + spec US3 acceptance scenario #2.
- [x] T028 Rewrite `tests/unit/test_unsupported_error.py`. Single site
  at line 28: `from pylocal_akuvox.capabilities import Capability`
  → `from pylocal_akuvox._capability_types import Capability`.
  Covers FR-006.
- [x] T029 Rewrite `tests/unit/test_capability_probe.py` — 2 sites
  (lines 24, 1489). Split per symbol→module table —
  `Capability`/`CapabilityStatus` → `_capability_types`;
  `DeviceCapabilities` → `_capability_profile`. Refresh line numbers
  with grep before editing. Covers FR-006.
- [x] T030 Sanity gate: after T021–T029, run
  `grep -RnE '^[[:space:]]*from pylocal_akuvox\.capabilities' tests/ src/ docs/` —
  the leading `^[[:space:]]*` anchor matches active import
  statements ONLY (top-level OR indented) and EXCLUDES string-form
  references inside `pytest.raises` / `exec()` blocks in
  `tests/unit/test_capability_module_layout.py`, which intentionally
  document the dropped path without importing from it. Pass criterion:
  ZERO matches. As a belt-and-suspenders cross-check, also run
  `grep -RnE 'from pylocal_akuvox\.capabilities' tests/unit/test_capability_module_layout.py`
  — the only matches must be inside `with pytest.raises(...)` blocks
  or string literals passed to `exec(...)`; visually confirm none are
  active import statements. Also re-run
  `uv run pytest tests/ -x -q` — all tests still pass because
  `capabilities.py` is still present (unused, but resolvable). Covers
  FR-006 mid-flight verification.

---

## Phase 8: Migration — delete the old `capabilities.py`

**Purpose**: With every consumer (Phases 4–7) now importing from the
new underscore modules, `capabilities.py` is unused. Delete it. After
this task, the layout test (T004) goes green: Assertion 1 now passes
(`import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`).
Assertions 2–5 already passed at the end of Phase 4. The implementation
is now complete in source-code terms.

- [x] T031 Delete `src/pylocal_akuvox/capabilities.py`
  (`git rm src/pylocal_akuvox/capabilities.py`). Re-run T004's layout
  test:
  `uv run pytest tests/unit/test_capability_module_layout.py -v` —
  ALL FIVE assertions now PASS. Re-run the full test suite:
  `uv run pytest tests/ -x -q` — all tests pass. Covers FR-002 +
  FR-003 + FR-011 (the test now goes green) + the spec's US2 (loud
  `ModuleNotFoundError` on the dropped subpath).

---

## Phase 9: Validation gates

**Purpose**: Run every gate listed in `plan.md` §"Validation Gates"
against the staged tree before creating the commit. Each gate maps to
one or more SCs and the corresponding constitution principle. **Every
gate MUST pass green** before Phase 10's commit object is created;
the pre-commit hooks in T036 are the load-bearing enforcement.

These tasks are run in order against the staged-but-not-yet-committed
tree. The `[P]` markers below are conservative — most gates touch only
the staged tree (read-only) so are technically parallel-safe, but the
implementer is encouraged to run them in series so output streams stay
readable.

- [x] T032 **Unit tests gate** — run `uv run pytest tests/ -x -q`.
  Pass criterion: exit 0; all tests pass; the new
  `test_capability_module_layout.py` is included automatically by
  `tests/unit/` discovery (5 new test functions). Covers SC-001.
- [x] T033 **Branch coverage gate** — run
  `uv run pytest --cov=pylocal_akuvox --cov-branch --cov-report=term-missing tests/`.
  Pass criterion: 100% branch coverage maintained on `pylocal_akuvox`
  (matches T001 baseline). No new uncovered branches. The four new
  modules contain only relocated code; coverage that previously
  exercised those entities through `capabilities.py` now exercises
  them through the underscore modules — the rewritten test imports in
  Phase 7 ensure this. Covers SC-001 + FR-006.
- [x] T034 **Lint gate** — run `uv run ruff check src/ tests/`. Pass
  criterion: exit 0; zero warnings. The four new modules' imports
  must be ordered (stdlib → first-party) per project ruff/isort
  config. Covers constitution §I.
- [x] T035 **Type-check gate** — run `uv run mypy src/`. Pass
  criterion: exit 0; zero errors (mypy strict per project config).
  The relocation does not alter any function signature or dataclass
  field type, so no new mypy errors are expected. Covers constitution
  §I + spec US1 acceptance scenario #2.
- [x] T036 **Pre-commit (full) gate** — run
  `git add -A && pre-commit run --all-files`. The leading
  `git add -A` is **mandatory**: the project's aislop hook is
  configured with `pass_filenames: false` and operates on the staged
  diff; running `pre-commit run --all-files` against an unstaged tree
  would scan an empty staged set and report a false-green. Pass
  criterion: exit 0; ruff, mypy, interrogate, REUSE, codespell,
  gitlint, **`aislop ci --staged`**, AND **`pytest (100% coverage)`**
  all pass. The `pytest (100% coverage)` hook is configured to run on
  every commit per `.pre-commit-config.yaml` and will fail the gate
  if any test or branch-coverage threshold regresses — listing it
  explicitly avoids confusion if `pre-commit run --all-files` fails
  despite ruff/mypy/aislop passing. The aislop hook is the very gate
  this refactor exists to satisfy — it MUST run green and MUST report
  no `complexity/file-too-large` against any of the four new modules.
  This is the load-bearing pre-commit check; T037–T038 are
  belt-and-suspenders. Covers SC-001 + SC-002 (per-module size
  limit) + constitution §V (no `--no-verify`).
- [x] T037 [P] **Aislop new-module size scan (explicit)** — run
  `uv run aislop scan src/pylocal_akuvox/_capability_types.py src/pylocal_akuvox/_capability_profile.py src/pylocal_akuvox/_capability_matching.py src/pylocal_akuvox/_capability_defaults.py`.
  Pass criterion: NO `complexity/file-too-large` warnings on any of
  the four new modules; each is under 400 lines. This is the explicit
  per-module verification of FR-004 and SC-002 (does not depend on
  staging state). The `[P]` marker reflects that this scan is
  read-only and fully independent of T036's pre-commit run.
- [x] T038 [P] **Aislop project-wide scan** — run
  `uv run aislop scan`. Pass criterion: `capabilities.py` no longer
  appears in the `complexity/file-too-large` list (it has been
  deleted in T031). `device.py` and `capability_probe.py` will still
  be flagged — those are issues #142 and #141 respectively, out of
  scope per spec §"Out of Scope". Covers SC-002 at project level.
- [x] T039 [P] **Doc build gate** — run
  `cd docs && uv run sphinx-build -W -b html . _build/html`. The
  `-W` flag treats warnings as errors. Pass criterion: exit 0;
  confirms the rewritten `docs/_ext/capability_matrix.py` import (T020)
  works at autodoc time, and that no rewritten docstring (T015 / T018
  user-facing rewrites) introduced a malformed RST reference. Covers
  FR-010 + FR-006 + FR-009.
- [x] T040 **Subpath removal smoke test** — run
  `uv run python -c "import pylocal_akuvox.capabilities"`. Pass
  criterion: exits non-zero with
  `ModuleNotFoundError: No module named 'pylocal_akuvox.capabilities'`.
  Covers SC-003 + FR-002.
- [x] T041 **Top-level imports smoke test** — run
  `uv run python -c "from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape; print('ok')"`.
  Pass criterion: exits 0; prints `ok`. Covers SC-004 + FR-001.

---

## Phase 10: Polish — atomic implementation commit

**Purpose**: Stage the entire implementation tree (4 new modules +
`__init__.py` rewrite + 19 consumer rewrites + new layout test +
deletion of `capabilities.py`) as ONE atomic commit. The `!` marker
in the subject is the load-bearing FR-007 requirement.

- [x] T042 Stage every file changed in Phases 2–8 with `git add`:
  the four new underscore modules, the rewritten `__init__.py`, the
  9 rewritten production sources (T011–T019),
  `docs/_ext/capability_matrix.py` (T020), the 9 rewritten test files
  (T021–T029), the new `tests/unit/test_capability_module_layout.py`
  (T004), and the deleted `src/pylocal_akuvox/capabilities.py` (T031,
  via `git rm`). Verify with `git status` and `git diff --staged
  --stat`: expected **26 files** in the stat — **5 added** (4 new
  underscore modules + 1 new layout test) + **1 deleted**
  (`capabilities.py`) + **20 modified** (`__init__.py` + 9 src
  consumers + 1 sphinx + 9 tests). Confirm with
  `git diff --staged --name-only | wc -l` returning `26`.
- [x] T043 Commit the staged tree as the **atomic implementation
  commit** with subject **exactly**
  `Refactor(capabilities)!: Split into submodules` (46 chars; verify
  with `echo -n "Refactor(capabilities)!: Split into submodules" |
  wc -c` → `46`; under the project's 50-char subject-line limit per
  AGENTS.md §"Conventional Commits"). The capitalised type
  `Refactor` is per AGENTS.md §"Conventional Commits"; the `!` before
  the colon is **mandatory** per FR-007 and is the load-bearing
  marker that triggers the breaking-change announcement chain.
  Commit body:
  - First paragraph: name the spec (`009-capabilities-module-split`)
    and issue (`#140`).
  - Second paragraph: enumerate the 4 new modules and the 1 deleted
    module.
  - Third paragraph: list the breaking-change demotions (subpath
    removed; 4 internals moved to underscore modules).
  - Final lines: DCO `-s` sign-off, `Refs #140`, and a
    `Co-Authored-By:` trailer for **each AI model actually used** to
    author the implementation (e.g.
    `Co-Authored-By: Claude <claude@anthropic.com>` if Claude was
    used; `Co-Authored-By: GitHub Copilot <copilot@github.com>` if
    Copilot was used; both if both were used) per AGENTS.md
    §"AI Co-Authorship Requirements" (lines 66–74). Do NOT include
    a trailer for a model that did not contribute.
  All body lines ≤80 chars. Use `git commit -s` — DCO sign-off is
  mandatory. **Never use `--no-verify`** (constitution §V); the
  pre-commit hooks (run again here) MUST pass green. If pre-commit
  fails, fix in place and re-`git commit -s` (do NOT `git reset`,
  per AGENTS.md §"If Pre-Commit Fails"; do NOT `git commit --amend
  --no-verify`). Verify post-commit with `git log -1 --format=%s` —
  output MUST contain `!` before the colon (SC-006). Covers FR-007 +
  SC-006 + constitution §V.

---

## Phase 11: Polish — documentation commit (changelog)

**Purpose**: Land the breaking-change announcement as a separate
atomic commit on the same PR. Per `plan.md` §"Phase Decomposition"
and AGENTS.md §"Atomic Commits", the changelog edit is logically
distinct from the source-code change, so it gets its own commit
even though it ships in the same PR.

- [x] T044 Edit `docs/changelog.rst` Unreleased section: add a
  "Breaking changes" subsection (RST sub-heading using the project's
  existing changelog conventions — match style of any prior breaking
  change entries in this file, or use a `^^^^^^^^^^^^^^^^` underline
  one level below the `Unreleased` heading). The subsection MUST
  name:
  - **The dropped subpath**: `pylocal_akuvox.capabilities` is removed.
    `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`.
  - **The 4 demoted internals**: `Provenance`, `DeviceClassPattern`,
    `lookup_capabilities`, `DEFAULT_USER_FIELD_ALIASES` are no longer
    publicly reachable; they live in their respective underscore
    modules and are formally internal.
  - **The migration path**: consumers should use
    `from pylocal_akuvox import Capability, CapabilityStatus,
    DeviceCapabilities, FieldAliases, SchemaShape` (the existing
    documented top-level imports). No consumer-facing public symbol
    has been renamed or removed.
  - **The issue reference**: `Refs #140`.
  Covers FR-008 + spec US2 acceptance scenario #3.
- [x] T045 Stage `docs/changelog.rst` and commit as a SEPARATE atomic
  commit with subject **exactly**
  `Docs(changelog): Announce 009-capabilities split` (48 chars).
  Use `git commit -s` (DCO mandatory) with a `Co-Authored-By:`
  trailer for each AI model actually used to author the changelog
  edit (per AGENTS.md §"AI Co-Authorship Requirements" lines 66–74 —
  see T043 for the trailer-format details). Body explains: paragraph
  1 — what is being announced (the `009-capabilities-module-split`
  breaking change); paragraph 2 — the migration path summary; final
  lines — `Refs #140` + DCO + the appropriate co-author trailer(s).
  Body lines ≤80 chars. Pre-commit hooks pass green; `--no-verify`
  is prohibited (constitution §V). Verify post-commit:
  `grep -A 5 "Breaking changes" docs/changelog.rst` output names the
  dropped subpath, the 4 demoted internals, and the migration path.
  Covers FR-008 + SC-005.

---

## Phase 12: Polish — PR open + Copilot review loop + task-list flip

**Purpose**: Push the branch, open the PR, drive the Copilot review
loop to clean, then commit the task-list flip as the FINAL commit in
the PR (per AGENTS.md §"Task List Updates Are Separate Commits"). The
actual `gh pr merge` action happens AFTER T048 in the unnumbered
"After T048 — Merge & cleanup" prose section below — this phase ends
with three commits on the PR branch and all review threads resolved.

- [x] T046 Push the branch
  (`git push -u origin 009-capabilities-module-split`) and open the
  PR with `gh pr create --base main`. PR title MUST match the
  implementation commit subject **exactly**
  (`Refactor(capabilities)!: Split into submodules`). PR body
  summarises:
  - The four new modules + their line-count budgets (per FR-004).
  - The implementation commit's file shape: **26 files**
    (5 added + 1 deleted + 20 modified) — see T042 stat breakdown.
  - The breaking-change summary mirrored from the changelog entry
    (T044).
  - The four validation-gate confirmations from Phase 9 (test count,
    coverage, aislop on new modules, sphinx -W).
  - `Refs #140`.
  Confirm exactly TWO commits in the PR with
  `gh pr view --json commits` at this point — the
  `Refactor(capabilities)!` commit and the `Docs(changelog)` commit.
  T048 below adds a third (the task-list flip) before the post-task
  merge action.
- [x] T047 Run the Copilot review loop:
  `gh copilot-review --wait --wait-timeout 20min <PR>`. **Note**:
  `copilot-review` is a local `gh` extension / alias used by this
  project's maintainers to drive the GitHub Copilot PR-reviewer
  bot from the CLI; it is not a built-in `gh` subcommand. A
  contributor without that extension can equivalently request the
  Copilot PR review via the GitHub web UI ("Reviewers" panel → add
  `github-copilot[bot]`) and then poll for the review with
  `gh pr view <PR> --json reviews`. Address each review comment in
  turn — make the change locally, commit as a follow-up squash-target
  commit (subject like `Fixup: <reviewer-comment-summary>`), push.
  Cap: 3 rounds expected, 10 rounds maximum. After the final pass,
  **before T048's task-list flip and the post-task merge**, **resolve
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
  failure** (AGENTS.md §"If Pre-Commit Fails"). If review introduces
  fix-ups, those are squashed into the appropriate commit
  (`git rebase -i` and `fixup` the right commit; the PR remains a
  clean 2-commit shape before T048 adds the third).
- [x] T048 In the implementation worktree (after T047's review loop
  closes and all review threads are resolved), edit
  `specs/009-capabilities-module-split/tasks.md`: flip every
  `- [ ]` to `- [x]` for every task T001 through T048 (this task
  itself is the last to flip — flip it to `- [x]` as part of the
  edit). Stage the file and commit as a SEPARATE atomic commit with
  subject **exactly** `Docs(tasks): Mark 009 task list complete`
  (40 chars). Use `git commit -s` with a `Co-Authored-By:` trailer
  for each AI model actually used to author the task-list flip (per
  AGENTS.md §"AI Co-Authorship Requirements" lines 66–74 — see T043
  for the trailer-format details). Body: brief paragraph naming the
  spec and PR; `Refs #140`; DCO + the appropriate co-author
  trailer(s). Push and confirm `gh pr view --json commits` reports
  exactly THREE commits in the PR (`Refactor(capabilities)!`,
  `Docs(changelog)`, `Docs(tasks)`).
  **This is the final numbered task in tasks.md** — same pattern as
  spec 008's T029/T056/T072/T087 per-phase task-list updates. The
  actual `gh pr merge` action is described in the prose footer below
  and is NOT tracked as a numbered task because it adds no commit.
  **Never use `--no-verify`** (constitution §V); **never `git reset`
  after a pre-commit hook failure** (AGENTS.md §"If Pre-Commit
  Fails"). Covers AGENTS.md §"Task List Updates Are Separate Commits".

---

### After T048 — Merge & cleanup (not a numbered task; no new commit)

After T048 commits and pushes the third commit on the PR, perform the
merge and worktree cleanup:

1. **Merge order matters** because of a known worktree-cleanup gotcha
   (lesson learned on plan PR #146): `gh pr merge --delete-branch`
   will fail if the local worktree still references the branch. Pick
   ONE of these orderings:
   - **(a) worktree-first**: from the repo root / main checkout, run
     `git worktree remove <worktree-path> --force` FIRST, then
     `gh pr merge <PR> --merge --delete-branch`. The `--force` flag
     is needed because the worktree carries reflog state that
     `gh pr merge --delete-branch`'s underlying `git branch -D`
     would refuse to delete.
   - **(b) merge-first**: `gh pr merge <PR> --merge --delete-branch`
    first; the local branch deletion will fail; clean up after with
    `git worktree remove <worktree-path> --force` and
    `git branch -D 009-capabilities-module-split`.
2. **End state**: the worktree is gone, the local branch is deleted,
   `main` is fast-forwarded to the merged commit, and
   `gh pr view <PR> --json state` reports `MERGED`.
3. **Final post-merge verification on `main`**:
   - `uv run python -c "import pylocal_akuvox.capabilities"` → exits
     non-zero with `ModuleNotFoundError` (SC-003);
   - `uv run python -c "from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape; print('ok')"`
     → prints `ok` (SC-004);
   - `git log --format=%s main | grep '^Refactor(capabilities)!'`
     finds the implementation commit subject containing `!` before
     the colon (SC-006).
4. After the post-merge verification clears, every FR / SC has been
   verified end-to-end on `main` and issue #140 can be closed.

---

## Dependencies

- **T001 → T002 → T003** (Setup): sequential. Baseline must come
  first.
- **T004** (TDD red): runs after T002 but is independent of T003.
  Cannot be skipped — it is the FR-011 deliverable and the
  constitution §II proof.
- **T005 → T006** (module creation): strictly sequential.
  `_capability_profile` imports from `_capability_types`, so the
  latter must exist first.
- **T006 → T007**, **T006 → T008** (module creation): both require
  `_capability_profile` to be staged. T007 and T008 do NOT depend on
  each other (`_capability_matching` and `_capability_defaults` are
  siblings) but are NOT marked `[P]` per the user-direction in the
  task generation prompt.
- **T009** (`__init__.py` rewrite): requires T005 and T006. Does NOT
  require T007 or T008 (no public re-exports come from those
  modules), but is gated behind both for atomicity — if `__init__.py`
  re-exports from `_capability_types`/`_capability_profile` while
  `_capability_matching`/`_capability_defaults` don't yet exist,
  consumer code in T011–T019 / T020 / T021–T029 cannot be rewritten
  to point at them.
- **T010** (smoke check): requires T009.
- **T011–T019** (production source rewrites): all require T010.
  Sequential per user-direction (no `[P]`); within each task, the
  multi-site files (T014 device.py, T015 users.py) handle all sites
  in one task.
- **T020** (sphinx): requires T010. Independent of T011–T019.
- **T021–T029** (test rewrites): require T010. Sequential per
  user-direction.
- **T030** (sanity grep gate): requires ALL of T011–T029 + T020.
- **T031** (delete `capabilities.py`): requires T030 (zero `from
  pylocal_akuvox.capabilities` matches confirmed). After T031, T004's
  layout test goes green.
- **T032–T041** (validation gates): all require T031. T032/T033/T034/
  T035 can serialise; T037/T038/T039 are `[P]` after T036.
- **T042 → T043** (stage + atomic commit): sequential. T042 stages,
  T043 commits.
- **T044 → T045** (changelog edit + commit): sequential. Independent
  of T042/T043 in source terms but logically follows the
  implementation commit so the PR ordering is
  Refactor → Docs(changelog) → Docs(tasks).
- **T046 → T047 → T048** (push, review, flip): sequential. T048
  (task-list flip) is the FINAL numbered task and lands as the third
  PR commit; the actual `gh pr merge` is an unnumbered post-task
  action.

---

## Parallel-execution opportunities

This refactor is intentionally sequential at the import-rewrite layer
(per the user-direction). Genuine parallelism is limited to:

- **Phase 9**: After T036 (the load-bearing pre-commit gate),
  T037/T038/T039 are read-only and `[P]`-safe — run aislop new-module
  scan, aislop project-wide scan, and sphinx-build concurrently.
- **None** in Phases 3, 5, 7. The dependency chain in module creation
  (T005 → T006 → {T007, T008}) and the user-direction on
  import-rewrite tasks remove all `[P]` from those phases.

---

## Coverage Map: FR / SC → Tasks

For pre-merge auditing. Every FR-001 through FR-011 and SC-001
through SC-006 must appear in the right column.

### Functional Requirements

| Requirement | Implementing tasks | Verifying tasks |
|---|---|---|
| **FR-001** Public symbols remain importable from top-level | T009 | T004 (assertions 4 + 5), T010, T041 |
| **FR-002** `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError` | T031 | T004 (assertion 1), T040 |
| **FR-003** `from pylocal_akuvox.capabilities import X` raises | T031 | T004 (assertion 2) |
| **FR-004** Each new submodule below 400-line aislop threshold | T005, T006, T007, T008 | T036, T037 |
| **FR-005** Internal symbols importable from underscore modules | T005, T006, T007, T008 | T004 (assertion 3) |
| **FR-006** All existing tests pass unchanged in semantic behavior | T011–T019, T020, T021–T029 | T030, T032, T033 |
| **FR-007** Implementation commit uses `!` breaking-change marker | T043 | T043 (post-commit `git log` check); post-merge re-check in the unnumbered "After T048 — Merge & cleanup" verification list |
| **FR-008** Changelog "Breaking changes" subsection | T044, T045 | T045 (post-commit `grep` check) |
| **FR-009** README spot-check — no stale references | T003 (verify); T015, T018 (docstring rewrites) | T039 (sphinx -W) |
| **FR-010** Sphinx extension updated | T020 | T039 |
| **FR-011** Layout-assertion test | T004 | T031, T032 |

### Success Criteria

| Criterion | Verification task |
|---|---|
| **SC-001** Full test suite green | T032 (+ T033 coverage) |
| **SC-002** No aislop `file-too-large` on new modules | T036, T037, T038 |
| **SC-003** Subpath removal confirmed | T040, T004 (assertion 1); post-merge re-run in the unnumbered "After T048" verification list |
| **SC-004** Top-level imports work | T041, T004 (assertion 4); post-merge re-run in the unnumbered "After T048" verification list |
| **SC-005** Changelog entry present | T045 (post-commit `grep` check) |
| **SC-006** Commit subject has `!` | T043 (post-commit check); post-merge re-check in the unnumbered "After T048" verification list |

### Contracts

| Contract | Tasks |
|---|---|
| `contracts/capability-types.md` | T005 (creation), T021 (test rewrites), T004 assertion 4 |
| `contracts/capability-profile.md` | T006 (creation), T021 (test rewrites), T004 assertion 4 |
| `contracts/capability-matching.md` | T007 (creation), T022, T027 (test rewrites), T004 assertion 3 |
| `contracts/capability-defaults.md` | T008 (creation), T024 (test references), T004 assertion 3 |

---

## Implementation Strategy

**MVP scope (smallest shippable increment)**: This refactor IS the
MVP. There is no smaller shippable slice — `plan.md` §"Phase
Decomposition" justifies the single-PR atomic-rename pattern as the
only viable shape. The whole point is for the file split to land
atomically with its consumers.

**Incremental delivery**:

1. **Spec PR (#145)**: artifacts. MERGED.
2. **Plan PR (#146)**: artifacts. MERGED.
3. **Tasks PR (this file)**: artifacts. About to merge.
4. **Implementation PR**: code + changelog + task-list flip (Phases
   2–12 above). Single PR, three commits.

**Parallelisable work**:

- Within Phase 9: T037/T038/T039 are `[P]`-safe.
- All other phases: SEQUENTIAL.

**Risk hedges**:

- **Cycle risk during module authoring**: T006 includes a pre-edit
  cycle audit on `pylocal_akuvox.exceptions` to confirm `Capability`
  is imported only under `TYPE_CHECKING`. T007 preserves the lazy
  `capability_matrix` import inside `lookup_capabilities` verbatim —
  removing it would create a hard cycle with `capability_matrix.py`.
  Both risks are documented in `plan.md` §"Cycle risk" sections.
- **Line numbers drift**: Phase 5 / Phase 7 cite line numbers from
  `main` at SHA `fe461d7`. Each multi-site task (T014, T024, T025,
  T026, T029) instructs the implementer to refresh with grep before
  editing. If line numbers have drifted, the symbol→module table is
  the canonical reference.
- **Branch-protection unresolved-conversations merge block**: T047
  embeds the GraphQL `resolveReviewThread` recipe up-front to avoid
  the pre-merge stall pattern observed on PR #146.
- **Worktree cleanup ordering**: the unnumbered "After T048 — Merge
  & cleanup" prose section documents both viable orderings (worktree-
  first vs merge-first) so the implementer can pick whichever fits
  their local state.
- **Pre-commit hook failures during T043 / T045 / T048**: constitution
  §V prohibits `--no-verify`; AGENTS.md §"If Pre-Commit Fails"
  prohibits `git reset` after a hook failure (the constitution echoes
  "do NOT reset; do NOT bypass" at §V step 5). Each commit task in
  those phases includes the relevant reminders.

---

## Anomalies / open questions

None at task-generation time. All FR / SC / contract artifacts have
explicit task coverage; the dependency chain is acyclic; commit
subjects are verified ≤50 chars; the `!` mandate has a dedicated
task (T043); the changelog entry is a separate commit (T044/T045);
the atomic checkbox-flip commit (T048) is the final task. Three
rubber-duck rounds anticipated; cap 10.
