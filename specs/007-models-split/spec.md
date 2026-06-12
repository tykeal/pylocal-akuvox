# Feature Specification: Split models.py into Domain-Grouped Modules

**Feature Branch**: `007-models-split`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "Split `src/pylocal_akuvox/models.py` (currently 448 lines, exceeds the aislop 400-line threshold) into smaller domain-grouped modules. Maintain full backwards compatibility — all existing imports from `pylocal_akuvox.models` MUST continue to work via re-exports. No public API changes. No behavior changes — purely a structural refactor."
**Related Issues**: Closes #126; coordinates with #123 (capability matrix epic) and #121 (apartment-book contact fields)

## Overview

`src/pylocal_akuvox/models.py` currently holds every data model class for the
library in a single ~448-line file (447 lines today; reported as 448 in
issue #126 at the time it was filed). This exceeds the project's 400-line
aislop file-size threshold and is the only blocker keeping that gate from
going green for this module. The same monolith is also the file that the
capability-matrix epic (#123) and the apartment-book contact extension
(#121) need to modify next, so the longer it stays a single grab-bag the
more painful those follow-ups become.

This feature splits the monolith into domain-grouped modules organized under a
`models/` package, while preserving `pylocal_akuvox.models` as a stable public
import surface. No public API changes. No behavior changes. No new
functionality. The work is a pure structural refactor whose value is measured
in maintainability, future-change locality, and a passing aislop gate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Existing import paths keep working (Priority: P1)

A downstream consumer of the library (including this project's own
`pylocal_akuvox/__init__.py`, the `users.py`/`device.py`/`schedules.py`/etc.
submodules, the example scripts, and every test module) imports model classes
from `pylocal_akuvox.models` today. After the split, every one of those import
statements must continue to resolve to the same class object with the same
behavior — without any source edit on the consumer side.

**Why this priority**: This is the entire backwards-compatibility contract.
If a single existing import breaks, the refactor is a regression rather than
an improvement, and downstream users (including the Home Assistant
integration) will fail to load.

**Independent Test**: Run the full existing test suite unchanged after the
split. Every test that imports from `pylocal_akuvox.models` (notably
`tests/unit/test_models.py`) must pass without modification to its import
lines.

**Acceptance Scenarios**:

1. **Given** an existing module `from pylocal_akuvox.models import User`,
   **When** the module is imported after the split, **Then** `User` is the
   same class with the same fields, methods, and parsing behavior as before.
2. **Given** `from pylocal_akuvox.models import (AccessSchedule, CallLogEntry,
   Contact, DeviceConfig, DeviceInfo, DeviceStatus, DoorLogEntry, Group,
   Relay, User)` (the consolidated re-export block in
   `pylocal_akuvox/__init__.py`), **When** the package is imported, **Then**
   all ten names resolve and `pylocal_akuvox.__all__` exposes them unchanged.
3. **Given** a downstream user runs `python -c "import pylocal_akuvox; print(pylocal_akuvox.User)"`,
   **When** executed against the post-split package, **Then** it prints the
   same fully-qualified output it did pre-split (or differs only in the
   internal module path, not in the imported name's availability or
   behavior).
4. **Given** the public API surface advertised in `pylocal_akuvox.__all__`,
   **When** compared before and after the split, **Then** the set of
   exported names is identical.

---

### User Story 2 - aislop file-size gate passes for the model layer (Priority: P1)

The aislop quality gate flags `src/pylocal_akuvox/models.py` as
`complexity/file-too-large` (max 400 lines, currently 447 — originally
reported as 448 in issue #126). After the split, no file in the model
layer — including the `models/__init__.py` re-export shim — should
exceed the 400-line threshold.

**Why this priority**: Closing this gate is the proximate reason the issue
was filed. Leaving the threshold violated (in any of the new files) means
the split has only moved the problem rather than solved it.

**Independent Test**: Inspect line counts of every file in the resulting
`src/pylocal_akuvox/models/` directory (and the re-export shim, if a separate
file is used). Every file must be ≤ 400 lines. Re-run aislop / file-size
linting; the previous warning must be gone and no new file-size warnings
introduced.

**Acceptance Scenarios**:

1. **Given** the post-split layout, **When** the file-size threshold check
   runs, **Then** no model-layer file exceeds 400 lines.
2. **Given** the previously failing aislop warning on `models.py`, **When**
   the gate runs after the split, **Then** that specific warning no longer
   appears.

---

### User Story 3 - Future change locality for #123 and #121 (Priority: P2)

The capability matrix epic (#123) will refactor `User.from_api_response` to
read field aliases from a capability record instead of the current hard-coded
`ScheduleRelay` / `Schedule-Relay` / `Schedule` chain, and will introduce a
new cross-cutting `Capability` enum plus `DeviceCapabilities` dataclass. The
apartment-book work (#121) will extend `Contact` with `APTName`, `APTNum`,
`Building`, and `Landline` fields. Both should land as small, localized
diffs against the new module layout rather than triggering another
restructure.

**Why this priority**: The whole reason this split is sequenced ahead of #123
(per the #126 coordination comment) is to make those follow-ups cheap.
A split that grouped, say, `User` with `Contact` would force #121 and #123
to fight each other in the same file again. P2 (not P1) because it's
about future ergonomics rather than today's correctness — but it's a stated
prerequisite for the epic ordering.

**Independent Test**: Walk the post-split module layout and confirm that
(a) `User` lives in its own user-domain module so the
`from_api_response` alias refactor is a single-file change, (b) `Contact`
lives in its own contact-domain module so the apartment-book field additions
are a single-file change, and (c) there is a clear, conventional location
for a future sibling `capabilities.py` (or equivalent) for cross-cutting
types that does not require carving up an existing domain module.

**Acceptance Scenarios**:

1. **Given** the post-split layout, **When** a reviewer locates `User`,
   **Then** it is in a user-domain module containing user-related types only
   (so #123's `from_api_response` alias rewrite affects exactly one source
   file).
2. **Given** the post-split layout, **When** a reviewer locates `Contact`,
   **Then** it is in a contact-domain module that has obvious room to grow
   the apartment-book fields without touching unrelated models.
3. **Given** the package layout, **When** #123 needs to add `Capability` /
   `DeviceCapabilities`, **Then** there is a documented, natural place to
   add a sibling module (e.g. `pylocal_akuvox/capabilities.py` or a parallel
   module next to `models/`) without modifying or expanding any domain
   model module just to host cross-cutting types.

---

### User Story 4 - Test suite remains organized and complete (Priority: P2)

`tests/unit/test_models.py` covers parsing behavior for all ten model
classes. After the split, the tests must continue to exercise the same
behavior with the same coverage. Whether the test file is left intact (still
importing from `pylocal_akuvox.models`) or also split to mirror the new
module layout is an implementation choice, but coverage of model parsing
behavior must not regress.

**Why this priority**: Tests are how we prove no behavior changed. They are
P2 because correctness is validated by them, but their organization is a
secondary concern relative to the import-compatibility and gate-passing
P1 goals.

**Independent Test**: Diff the set of test functions and the parsing
scenarios they cover before and after. `uv run pytest` must pass; coverage
for the affected model classes must not drop.

**Acceptance Scenarios**:

1. **Given** the existing model tests, **When** the test suite runs against
   the post-split layout, **Then** every test that previously passed still
   passes, with no skipped or removed parsing scenarios.
2. **Given** code coverage measurement, **When** taken before and after the
   split, **Then** coverage of the moved model classes does not decrease.

---

### Edge Cases

- **Circular imports**: `User.from_api_response` and other parsers raise
  `AkuvoxParseError` from `pylocal_akuvox.exceptions`. The split modules
  must continue to import only from `pylocal_akuvox.exceptions` (and stdlib),
  not from each other or from `pylocal_akuvox.models` (the shim), to avoid
  introducing import cycles.
- **`from pylocal_akuvox.models import *`**: The current `models.py`
  defines no `__all__`, so star-imports today expose **fourteen** names:
  the ten public model classes PLUS four accidental module-level leaks
  (`AkuvoxParseError`, `Any`, `annotations`, `dataclass`). The new shim
  introduces an explicit `__all__` listing exactly the ten public model
  names, which means star-import consumers will *no longer* receive the
  four leaked helper names. This is a deliberate clarification of the
  public contract — none of `AkuvoxParseError`, `Any`, `annotations`, or
  `dataclass` were ever documented as belonging to `pylocal_akuvox.models`,
  and a quick repository audit (`git grep "from pylocal_akuvox.models import \*"`)
  shows zero in-repo consumers rely on them via star-import. If any
  external consumer is found to depend on one of these accidental leaks,
  they should fix their import to point at the canonical home
  (`pylocal_akuvox.exceptions.AkuvoxParseError`, `typing.Any`, etc.); a
  one-line edit on their side. The ten *documented* public model names
  remain unchanged in availability and behavior.
- **`isinstance` / class identity**: Each re-exported class must be the
  *same* class object as the one defined in its new home module — not a
  subclass, alias, or wrapper. A `from pylocal_akuvox.models import User`
  followed by `isinstance(x, User)` must behave identically to the
  pre-split state.
- **Dataclass `__module__` attribute**: After the move, `User.__module__`
  will report the new home module (e.g. `pylocal_akuvox.models.users`)
  rather than `pylocal_akuvox.models`. This is acceptable as long as no
  consumer code or test asserts on `__module__` string values; if any do,
  they must be updated as part of this work and the change called out.
- **Sphinx / docs cross-references**: If `docs/` references model classes
  by fully qualified path, those references should resolve via the
  re-export shim (Sphinx `autodoc` typically does); any broken doc builds
  must be fixed as part of this work.
- **Pickling / serialization**: After the move,
  `User.__module__` becomes `pylocal_akuvox.models.users` (the new home
  module) rather than `pylocal_akuvox.models` (the shim). Old pickle
  payloads written against the shim path (`pylocal_akuvox.models.User`)
  would therefore fail to deserialize after the split. This was
  investigated and is a confirmed non-issue: no production code, test
  fixture, or example in `src/`, `tests/`, or `examples/` pickles a
  model instance (verified via `git grep -E 'pickle|cloudpickle|dill|
  shelve|joblib'`), and no on-disk cache serializes dataclasses. The
  `__module__` change therefore cannot break any deserialization
  round-trip in this repository.
- **Editor / IDE "go to definition"**: After the split, IDE jumps from a
  `from pylocal_akuvox.models import User` line will land in the shim
  rather than the class body. This is expected and not a regression of
  the public contract.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST preserve every existing import statement of
  the form `from pylocal_akuvox.models import <Name>` for all ten current
  model classes: `DeviceInfo`, `DeviceStatus`, `Relay`, `User`,
  `AccessSchedule`, `DoorLogEntry`, `CallLogEntry`, `DeviceConfig`,
  `Group`, `Contact`.
- **FR-002**: Each re-exported name MUST resolve to the *same class object*
  as its definition in the new home module (not a subclass, alias, or
  proxy), so `isinstance` checks and class identity comparisons continue
  to work.
- **FR-003**: `pylocal_akuvox.__all__` and the public API surface of the
  top-level `pylocal_akuvox` package MUST remain unchanged for the ten
  model names.
- **FR-004**: The `models` import surface MUST expose an `__all__`
  containing exactly the ten existing public model names so that
  `from pylocal_akuvox.models import *` produces the same set of public
  model names as before. The current `models.py` has no `__all__`, so
  star-imports today *additionally* leak the four module-level helper
  names `AkuvoxParseError`, `Any`, `annotations`, and `dataclass` (the
  imports needed to define the dataclasses). Those four names are
  accidental leaks, were never part of the public contract, and are
  intentionally NOT preserved by the new `__all__`. This is a deliberate
  clarification of the public surface — see edge-case
  "`from pylocal_akuvox.models import *`" below — not a backwards-
  incompatible change to the documented public API.
- **FR-005**: No source file in the post-split model layer (including the
  re-export shim and the `models/__init__.py` if `models` becomes a
  package) may exceed 400 lines.
- **FR-006**: Each new domain module SHOULD be substantially smaller than
  400 lines, leaving headroom for the additions in #123 (capability-driven
  alias refactor in the user-domain module) and #121 (apartment-book
  fields on the contact-domain module) without immediately re-triggering
  the file-size threshold.
- **FR-007**: The split MUST NOT change any model class's fields, defaults,
  method signatures, `from_api_response` parsing behavior, error messages,
  or raised exception types. This is a pure move/re-export refactor.
- **FR-008**: Model classes MUST be grouped by domain. The chosen grouping
  MUST place `User` in a user-domain module by itself (or with
  user-domain-only siblings) and `Contact` in a contact-domain module
  (or with contact-domain-only siblings), so that the anticipated #123
  and #121 changes are localized to a single file each.
- **FR-009**: The package layout MUST leave room for a future sibling
  cross-cutting module (e.g. `pylocal_akuvox/capabilities.py` or
  equivalent) for types that are not domain-specific. Cross-cutting
  types from #123 MUST NOT be wedged into a domain model module by this
  refactor.
- **FR-010**: Domain modules MUST NOT import from each other for the sole
  purpose of re-exporting. Each domain module owns its own classes; the
  shim is the single re-export point.
- **FR-011**: Domain modules MUST NOT import from `pylocal_akuvox.models`
  (the shim) to avoid import cycles. Allowed imports are stdlib,
  `pylocal_akuvox.exceptions`, and (if genuinely needed) other domain
  modules by their concrete module path.
- **FR-012**: The full existing test suite MUST pass after the split with
  no test code changes that alter assertion behavior. Test imports MAY be
  left pointing at `pylocal_akuvox.models` (relying on the shim) or
  optionally updated to the new module paths; either is acceptable as
  long as coverage does not decrease.
- **FR-013**: The full project quality gate MUST pass post-split:
  `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy`, `uv run interrogate`, and `uv run reuse lint` (REUSE
  compliance, paired with FR-014). The aislop
  `complexity/file-too-large` warning on `models.py` MUST no longer
  appear, and no new file-size warnings may be introduced on the new
  files.
- **FR-014**: REUSE / SPDX headers MUST be present on every new source
  file at the top, matching the existing convention used in the current
  `models.py` (`SPDX-FileCopyrightText` and `SPDX-License-Identifier`
  lines), so the REUSE compliance check continues to pass.
- **FR-015**: Public docstrings on moved classes and methods MUST be
  preserved verbatim. The module-level docstring of the new `models`
  shim MUST clearly state that the module is a backwards-compatibility
  re-export surface and point readers at the per-domain home modules.

### Key Entities *(structural — files and groupings, not data)*

This feature reorganizes the following entities. The exact final filenames
and whether `models` becomes a package vs. a shim file is a design choice
to be made in `/speckit.plan`; the entity *grouping* below is the
specification-level constraint.

- **Device-domain module**: Houses `DeviceInfo`, `DeviceStatus`, and `Relay`.
  These are tightly coupled — `DeviceStatus` and `Relay` describe the same
  device that `DeviceInfo` identifies, and they are typically fetched and
  consumed together by `pylocal_akuvox/device.py`.
- **Device-config module**: Houses `DeviceConfig`. May live with the
  device-domain module or as its own sibling — it shares the device
  subject but is fetched via a distinct config endpoint and consumed by
  `pylocal_akuvox/config.py`. Splitting it out is acceptable; combining
  it with the device-domain module is also acceptable as long as the
  combined file stays comfortably below 400 lines.
- **User-domain module**: Houses `User` and only `User` (or other
  user-only types if they emerge later). Kept narrow specifically so
  that #123's `from_api_response` capability-driven alias rewrite is a
  single-file change.
- **Access / schedule module(s)**: Houses `AccessSchedule` and `Group`.
  These may share a single module (both are access-control concepts) or
  be split into `schedules` and `groups` modules. Either grouping is
  acceptable provided each file stays well under 400 lines.
- **Logs module**: Houses `DoorLogEntry` and `CallLogEntry`. These are
  both event-log records consumed by `pylocal_akuvox/logs.py` and
  belong together.
- **Contact-domain module**: Houses `Contact`. Kept narrow specifically
  so that #121's apartment-book field additions are a single-file
  change with room to grow.
- **`pylocal_akuvox.models` re-export surface**: Either a shim file or
  the `__init__.py` of a `models/` package. Its sole responsibility is
  to import all ten public model names from their home modules and
  expose them under the historical `pylocal_akuvox.models` namespace,
  with a correct `__all__`. Contains no model definitions of its own.
- **Cross-cutting placeholder (documentation only)**: The package layout
  must leave conceptual room for a future sibling module — e.g.
  `pylocal_akuvox/capabilities.py` — for cross-cutting types introduced
  by #123. This feature does not create that module; it just documents
  where it will go and ensures no domain module has been bloated to
  preempt its purpose.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the split, no file in the model layer exceeds 400
  lines, and the aislop `complexity/file-too-large` warning previously
  emitted for `src/pylocal_akuvox/models.py` no longer appears in lint
  output.
- **SC-002**: 100% of the ten existing public model names
  (`DeviceInfo`, `DeviceStatus`, `Relay`, `User`, `AccessSchedule`,
  `DoorLogEntry`, `CallLogEntry`, `DeviceConfig`, `Group`, `Contact`)
  remain importable from `pylocal_akuvox.models` with unchanged behavior
  and unchanged class identity. Note: the four accidental star-import
  leaks (`AkuvoxParseError`, `Any`, `annotations`, `dataclass`) are
  intentionally NOT covered by this criterion — see FR-004 and the
  star-import edge case for the clarified contract.
- **SC-003**: Zero downstream import statements in the project itself
  (`src/`, `tests/`, `examples/`, `docs/`) require modification for the
  refactor to land — for the **named-import** form
  (`from pylocal_akuvox.models import <Name>`) of the ten public model
  classes. Import updates may be made *optionally* for cleanliness but
  MUST NOT be required for correctness. Star-import consumers
  (`from pylocal_akuvox.models import *`) that relied on the four
  accidental helper-name leaks (`AkuvoxParseError`, `Any`, `annotations`,
  `dataclass`) are explicitly carved out: the deliberate `__all__`
  introduction drops those leaks. A repository audit confirms zero
  in-repo star-import consumers exist, so this carve-out is theoretical.
- **SC-004**: The full quality gate (`uv run pytest`, `uv run ruff check
  .`, `uv run ruff format --check .`, `uv run mypy`, `uv run
  interrogate`, plus REUSE compliance) passes on the resulting branch
  with no new warnings or errors introduced.
- **SC-005**: Overall test coverage of the model layer (the eight files
  under `src/pylocal_akuvox/models/` taken together — submodules + shim
  `__init__.py`) is ≥ the pre-split coverage of `src/pylocal_akuvox/models.py`
  captured in T003. Measured via `coverage report
  --include='src/pylocal_akuvox/models*'` (matches both the pre-split
  file `models.py` and the post-split package `models/`). A small
  *increase* due to the new re-export contract test is acceptable. This
  criterion is a **single number** comparison, not a per-class table —
  per-class line counts are not directly produced by `coverage.py` and
  the moved classes are unchanged so per-class coverage cannot regress
  unless the aggregate does.
- **SC-006**: The user-domain module containing `User` and the
  contact-domain module containing `Contact` are each substantially
  smaller than 400 lines (target: ≤ 250 lines each) so that the
  anticipated #123 and #121 additions land without pushing either
  module back over the threshold.
- **SC-007**: A reviewer reading the new layout can locate any of the
  ten model classes by domain name in under 10 seconds without
  searching the shim file — i.e., the domain grouping is intuitive
  enough that the per-domain filenames serve as documentation.

## Assumptions

- The 400-line threshold is the aislop default for
  `complexity/file-too-large` (per issue #126's "max: 400" /
  "448 lines" message; the file is 447 lines today, the one-line
  delta is immaterial — both exceed 400). This feature targets that
  exact threshold.
- `pylocal_akuvox.models` is treated as a public API surface by
  downstream consumers (including the Home Assistant integration that
  drives this library), so backwards compatibility of imports is a hard
  requirement rather than a courtesy.
- The current ten model classes are the complete set to split. No
  unmoved or undiscovered model classes live elsewhere in `src/`. (If
  any are found during planning, they may be folded into the
  appropriate domain module without changing this spec's intent.)
- Splitting the test file (`tests/unit/test_models.py`) to mirror the
  new module layout is *optional* and a planning-stage decision. This
  spec does not require the test file to be split, only that coverage
  is preserved and the suite continues to pass.
- The Sphinx documentation in `docs/` references models via autodoc
  (not hard-coded module paths in prose). If hard-coded paths are
  found, they will be updated as part of this work and the assumption
  revisited.
- No production consumer asserts on `Model.__module__` string values.
  If a consumer is found that does, this spec's "pure refactor" claim
  is preserved by treating the `__module__` change as documented
  behavior of the move and updating the consumer.
- A future `pylocal_akuvox.capabilities` module (or equivalent
  cross-cutting home for #123's types) will be introduced by #123, not
  by this feature. This feature only guarantees structural room for it.

## Out of Scope

- Adding, removing, or modifying any model class field, method, default,
  validation, or parsing rule. (Belongs to #121, #123, and future
  feature work.)
- Introducing the `Capability` enum, `DeviceCapabilities` dataclass, or
  any other cross-cutting type from #123. This feature only *makes room*
  for them.
- Adding `APTName`, `APTNum`, `Building`, `Landline`, or any other
  apartment-book field to `Contact`. (Belongs to #121.)
- Refactoring `User.from_api_response` to read aliases from a capability
  record. (Belongs to #123.)
- Splitting `tests/unit/test_models.py` to mirror the new module layout.
  (Optional, may be done as planning sees fit, but not a spec
  requirement.)
- Changing the public API of any non-model module (`device.py`,
  `users.py`, `contacts.py`, etc.).
- Renaming any model class or any public model name.
- Introducing a `__getattr__`-based lazy-loading shim. The re-export
  surface is expected to be a plain, explicit import block.

## Dependencies

- **Depends on**: nothing; this is a pure refactor that can land
  immediately against `main`.
- **Blocks (by sequencing convention, not by code)**: #123 (capability
  matrix epic). #123 is expected to be picked up after this feature
  merges, per the coordination comment on #126. #121 (apartment-book
  contact fields) is similarly easier to land once `Contact` is in its
  own narrow module, though #121 could technically proceed in parallel
  if needed.
