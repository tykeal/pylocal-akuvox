# Implementation Plan: Split models.py into Domain-Grouped Modules

**Branch**: `007-models-split` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-models-split/spec.md`

## Summary

Split the 447-line `src/pylocal_akuvox/models.py` (originally reported as
448 lines in issue #126; one trailing-blank delta means it is 447 today)
into a `pylocal_akuvox/models/` **package** whose `__init__.py` is the
backwards-compatibility re-export shim, and whose submodules each own one
operational domain's dataclasses:

- `models/device.py` → `DeviceInfo`, `DeviceStatus`, `Relay`
- `models/config.py` → `DeviceConfig`
- `models/users.py` → `User`
- `models/schedules.py` → `AccessSchedule`
- `models/groups.py` → `Group`
- `models/logs.py` → `DoorLogEntry`, `CallLogEntry`
- `models/contacts.py` → `Contact`
- `models/__init__.py` → re-exports the ten public names and defines `__all__`

This is a pure structural refactor — no behavior, no public API, no new
dependencies. Every existing `from pylocal_akuvox.models import <Name>` keeps
working unchanged. The current `src/pylocal_akuvox/models.py` file is **deleted**
in the same change (replaced by the new package directory of the same name).

## Technical Context

**Language/Version**: Python 3.13.2+ (per `pyproject.toml`'s `requires-python`)
**Primary Dependencies**: None added. Existing runtime: `aiohttp` (HTTP), stdlib
`dataclasses`. The refactored modules import only stdlib (`dataclasses`,
`typing.Any`, `__future__.annotations`) and `pylocal_akuvox.exceptions` —
identical to the current `models.py`.
**Storage**: N/A (in-memory dataclasses parsed from API responses).
**Testing**: `pytest` with `pytest --cov` (existing `tests/unit/test_models.py`,
1029 lines, covers all ten classes). One new tiny test module
(`tests/unit/test_models_reexport.py`) containing three test functions is
added under `tests/unit/` to lock in the re-export contract.
**Target Platform**: Library — Linux/macOS/Windows wherever Python 3.13+ runs;
in production it is consumed by the Home Assistant Akuvox custom integration.
**Project Type**: Single project (library). No web/mobile split; `src/` +
`tests/` layout.
**Performance Goals**: None applicable. This is a structural refactor. Import
cost of `pylocal_akuvox.models` will gain a one-time `__init__.py` traversal of
seven sibling submodules; this is negligible (<1ms on cold import) and
incurred once per process.
**Constraints**:

- No file in the resulting `models/` package may exceed 400 lines (aislop
  `complexity/file-too-large` gate; spec FR-005, SC-001).
- The user-domain module (`models/users.py`) and the contact-domain module
  (`models/contacts.py`) must each be ≤ 250 lines to leave headroom for #123
  and #121 (spec SC-006).
- Re-exported classes must be the *same class object* as defined in their
  home module (spec FR-002) — i.e. plain `from .users import User`, no
  wrappers, no aliases, no `__getattr__` lazy shim (explicitly out of scope
  per spec).
- Domain submodules must not import from each other for re-export and must
  not import from the shim (spec FR-010, FR-011) — prevents cycles.
- No source edits required in `src/pylocal_akuvox/__init__.py`,
  `device.py`, `users.py` (the service module), `schedules.py`, `logs.py`,
  `groups.py`, `contacts.py`, `config.py`, `examples/`, `docs/`, or
  `tests/` for correctness (spec SC-003). Their existing
  `from pylocal_akuvox.models import …` lines continue to resolve via the
  shim.

**Scale/Scope**: 10 dataclasses, ~447 lines being redistributed across 8
files (7 submodules + 1 shim `__init__.py`). Single repository, single
branch, single feature.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2. Re-checked
after Phase 1 design — see "Post-Design Re-Check" below.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | Every new `.py` file gets the same SPDX header pair already used in `models.py`. Existing docstrings and type annotations move verbatim. No function bodies change → cyclomatic complexity is unchanged (currently all parsers are well under C901's 10). ruff, mypy, interrogate already pass on `models.py`; moving code does not change their results. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | The existing `tests/unit/test_models.py` (1029 lines) is the regression net for the moved behavior — it must remain green at every step. One **new** TDD test module containing three test functions is added *before* the move (red phase): `tests/unit/test_models_reexport.py` asserting class-identity (`pylocal_akuvox.models.User is pylocal_akuvox.models.users.User` for all ten classes), `__all__` contents, and top-level-package re-export. These tests fail against the current `models.py`-as-file layout because the submodule paths don't yet exist; they pass once the package is created (green). No production code is written without a failing test that justifies it. |
| **III. User Experience Consistency** | PASS | The documented public API surface is **preserved**: `pylocal_akuvox.__all__` (top-level package) stays byte-identical, and the ten model class names continue to resolve from `pylocal_akuvox.models` with the same identity and behavior. The shim newly introduces `pylocal_akuvox.models.__all__` (the pre-split `models.py` had none); by design this contains exactly the ten public model names and intentionally excludes four accidental module-level helper leaks (`AkuvoxParseError`, `Any`, `annotations`, `dataclass`) that today's bare star-import would expose. This is a deliberate clarification of the public contract — never-documented helper names are dropped — see spec FR-004 and the `from pylocal_akuvox.models import *` edge case. No documented public name is removed; no breaking change to the named-import surface. |
| **IV. Performance Requirements** | PASS | No performance-sensitive path touched. Import-time cost addition is a single package init traversing seven small sibling modules — negligible and not on any hot path. No event-loop blocking introduced. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | The refactor is one logical change and lands as a **single atomic commit** containing the new TDD test module, the seven new domain submodules, the new shim `__init__.py`, and the `git rm` of the old `models.py`. Committing the TDD test in isolation would leave it red and pre-commit's pytest hook would block; the single-commit recipe in T026 keeps the working tree green at every commit boundary. The commit follows `AGENTS.md` exactly: capitalized Conventional-Commit type with optional scope (`Refactor(models): Split into domain submodules`, ≤50 chars), `-s` DCO sign-off, and `Co-Authored-By:` trailers for the AI assistants used. Every new file ships with SPDX headers verbatim from the existing `models.py` header pair. Pre-commit hooks are not bypassed. |
| **VI. Phased Development** | PASS | The work is a single phase (the refactor itself), with a clear CI-green checkpoint at the end. Internal commit ordering inside that phase is captured in `tasks.md` later by `/speckit.tasks`. |

**Result**: All gates pass. **Complexity Tracking** section below is left
empty — there are no justified violations.

## Project Structure

### Documentation (this feature)

```text
specs/007-models-split/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec (input)
├── research.md          # Phase 0 output — design decisions
├── data-model.md        # Phase 1 output — module/class home map
├── quickstart.md        # Phase 1 output — reviewer/maintainer verification recipe
└── contracts/
    └── import-contract.md   # Phase 1 output — public import surface contract
```

`tasks.md` is intentionally **not** generated here; it is produced later by
`/speckit.tasks`.

### Source Code (repository root)

Pre-refactor (current state, abbreviated to the affected paths):

```text
src/pylocal_akuvox/
├── __init__.py              # Re-exports 10 model names from .models
├── _http.py
├── auth.py
├── config.py                # Service module (consumes DeviceConfig)
├── contacts.py              # Service module (consumes Contact)
├── device.py                # Service module (consumes DeviceInfo, DeviceStatus)
├── exceptions.py
├── groups.py                # Service module (consumes Group)
├── logs.py                  # Service module (consumes DoorLog/CallLog entries)
├── models.py                # ← 447 lines, monolith — split target
├── py.typed
├── relay.py
├── schedules.py             # Service module (consumes AccessSchedule)
└── users.py                 # Service module (consumes User)

tests/unit/
├── test_models.py           # 1029 lines, covers all 10 classes — kept as-is
└── …                        # other module tests (test_device.py, test_config.py, …)
```

Post-refactor (only the changed area is shown; everything else is byte-for-byte
identical):

```text
src/pylocal_akuvox/
├── __init__.py              # UNCHANGED — still imports 10 names from pylocal_akuvox.models
├── _http.py                 # UNCHANGED
├── auth.py                  # UNCHANGED
├── config.py                # UNCHANGED (still imports DeviceConfig from pylocal_akuvox.models)
├── contacts.py              # UNCHANGED (still imports Contact from pylocal_akuvox.models)
├── device.py                # UNCHANGED (still imports DeviceInfo/DeviceStatus from pylocal_akuvox.models)
├── exceptions.py            # UNCHANGED
├── groups.py                # UNCHANGED (still imports Group from pylocal_akuvox.models)
├── logs.py                  # UNCHANGED (still imports CallLogEntry/DoorLogEntry from pylocal_akuvox.models)
├── models/                  # NEW — package replaces the old models.py file
│   ├── __init__.py          # Re-export shim: imports the 10 names from submodules; defines __all__
│   ├── config.py            # NEW — DeviceConfig
│   ├── contacts.py          # NEW — Contact
│   ├── device.py            # NEW — DeviceInfo, DeviceStatus, Relay
│   ├── groups.py            # NEW — Group
│   ├── logs.py              # NEW — DoorLogEntry, CallLogEntry
│   ├── schedules.py         # NEW — AccessSchedule
│   └── users.py             # NEW — User
├── py.typed                 # UNCHANGED
├── relay.py                 # UNCHANGED
├── schedules.py             # UNCHANGED (still imports AccessSchedule from pylocal_akuvox.models)
└── users.py                 # UNCHANGED (still imports User from pylocal_akuvox.models)

tests/unit/
├── test_models.py           # UNCHANGED — already imports from pylocal_akuvox.models (shim)
├── test_models_reexport.py  # NEW — TDD red→green: locks the import contract & __all__
└── …                        # other module tests untouched
```

> The submodule filenames inside `models/` deliberately mirror the existing
> service module filenames at the package root (`models/device.py` ↔
> `device.py`, `models/users.py` ↔ `users.py`, etc.). This makes the
> "where do I add a field for thing X?" question a single mental step: the
> dataclass lives at `models/<thing>.py`, the service that consumes it lives
> at `<thing>.py`. No name collisions occur because they live in different
> packages.

**Structure Decision**: `pylocal_akuvox.models` becomes a **package**
(`models/__init__.py` as the shim), **not** a flat shim file with a sibling
`_models/` package. Justification:

1. **One structure for one job.** With a package, the public namespace
   (`pylocal_akuvox.models`) and the on-disk home of the submodules
   (`pylocal_akuvox/models/`) match exactly. A flat-shim approach would
   need two structures (`models.py` *and* a sibling private directory) for
   the same conceptual unit.
2. **No top-level namespace pollution.** Putting domain submodules under
   `pylocal_akuvox/models/` keeps the project root flat at exactly the
   modules that exist today (`device.py`, `users.py`, `schedules.py`, …).
   A flat-shim approach would have to invent `_models/` or scatter
   `*_models.py` files alongside the service modules.
3. **No naming collisions.** A user-domain dataclass module called
   `users.py` can coexist with the service module `pylocal_akuvox/users.py`
   precisely because the dataclass module lives at
   `pylocal_akuvox/models/users.py`. With a flat shim, the dataclass file
   would need a different name (e.g. `user_models.py`), creating awkward
   per-domain naming.
4. **Future cross-cutting room.** The package shape leaves
   `pylocal_akuvox/capabilities.py` (for #123) as the obvious, conventional
   sibling next to `device.py` / `users.py` / `contacts.py` — exactly the
   location the spec calls out in FR-009. No domain model module needs to
   grow to host cross-cutting types.

Both options were explicitly permitted by the spec (key entity:
"re-export surface: either a shim file or the `__init__.py` of a `models/`
package"); package wins on the four points above. Trade-offs and the rejected
alternative are documented in detail in `research.md`.

## Phase 0 — Research (complete)

See [research.md](./research.md). All decisions are settled; no
`NEEDS CLARIFICATION` markers remain in this plan.

Topics resolved:

1. **Shim file vs `models/` package** → package (justified above; full
   trade-off analysis in research.md).
2. **`AccessSchedule` + `Group` together vs split** → split into
   `models/schedules.py` and `models/groups.py` (mirrors existing service
   modules `schedules.py` / `groups.py`).
3. **`DeviceConfig` with device vs separate** → separate
   (`models/config.py`); mirrors existing `config.py` service module.
4. **Split `tests/unit/test_models.py` to mirror new layout?** → no (spec
   says optional; keeping it as one file preserves git-blame continuity
   on the parsing tests and keeps the diff minimal). Mirroring can be
   done later cheaply.
5. **`__module__` change risk** → confirmed non-issue via repository scan:
   no code or test asserts on `Model.__module__` string values.
6. **Pickling risk** → confirmed non-issue: no model instances are pickled
   in `src/`, `tests/`, or `examples/`. Documented in research.md as
   "verified, no action".
7. **Sphinx `docs/api/models.rst` impact** → uses
   `.. automodule:: pylocal_akuvox.models :members:`. With the re-exports
   in `models/__init__.py` and the **newly introduced** explicit
   `pylocal_akuvox.models.__all__` listing the ten public model names
   (today's `models.py` has none — see spec FR-004), autodoc walks
   exactly that list and keeps rendering the same ten classes. The four
   accidental helper-name leaks (`AkuvoxParseError`, `Any`,
   `annotations`, `dataclass`) that bare star-import would expose today
   were never rendered by autodoc anyway (they have no docstrings or
   are imported names from other modules), so dropping them via the new
   `__all__` is invisible to the docs build. No docs source edit
   required for correctness; an optional follow-up to render per-domain
   pages is out of scope here.
8. **aislop / file-size gate behavior** → 400-line ceiling, enforced
   per-file. Largest planned new file is `models/device.py` at ≈ 130
   lines including SPDX header and imports — well under the threshold.

## Phase 1 — Design Artifacts (complete)

Generated alongside this plan:

- [data-model.md](./data-model.md) — for each of the ten dataclasses:
  current home → new home, line-range of the move, and the fact that
  field set / method signatures / parsing behavior are unchanged. Also
  contains a line-count budget table showing the projected size of each
  new file.
- [contracts/import-contract.md](./contracts/import-contract.md) — the
  one and only "contract" this feature has: the stable public-import
  surface. Lists the ten names that must remain importable from
  `pylocal_akuvox.models` and the `__all__` requirement, and pins these
  facts to the new TDD test module `tests/unit/test_models_reexport.py`.
- [quickstart.md](./quickstart.md) — copy-pasteable verification recipe
  for a reviewer: how to confirm import compatibility, class identity,
  `__all__`, file-size compliance, full quality gate (`uv run pytest`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run interrogate`, REUSE check), and coverage non-regression.

**Agent context update**: `.specify/scripts/bash/update-agent-context.sh
copilot` was run to refresh the Copilot-agent context file with the
"models package" technology entry and the new project structure summary.

### Post-Design Re-Check (Constitution gates)

Re-evaluated after producing data-model.md, contracts, and quickstart:

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality | PASS | Design adds no new code paths, only relocates existing ones. All eight new files specified with SPDX headers and preserved docstrings. |
| II. TDD | PASS | `tests/unit/test_models_reexport.py` is specified as the first artifact written (red), with the package layout being the implementation that makes it green. |
| III. UX Consistency | PASS | Import contract document (`contracts/import-contract.md` §1) explicitly forbids any change to the *named-import* public surface (the ten public model classes), and explicitly documents the deliberate clarification: introducing `pylocal_akuvox.models.__all__` (which does not exist today) drops four never-documented star-import leaks (`AkuvoxParseError`, `Any`, `annotations`, `dataclass`). See spec FR-004 and edge case. |
| IV. Performance | PASS | No design element introduces blocking or hot-path import cost. |
| V. Atomic Commits & Compliance | PASS | Commit plan ordering preserves atomicity; SPDX headers mandated per new file; sign-off and conventional commit types specified. |
| VI. Phased Development | PASS | Single phase, single CI-green checkpoint at the end. |

No new violations introduced by the design. The Complexity Tracking
section below remains intentionally empty.

## Complexity Tracking

> No constitution violations require justification. This section is
> intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)*  | *(n/a)*    | *(n/a)*                              |
