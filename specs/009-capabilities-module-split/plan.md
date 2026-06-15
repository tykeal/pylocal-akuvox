<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Refactor capabilities.py Under Aislop Size Limit

**Branch**: `009-capabilities-module-split` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-capabilities-module-split/spec.md`

## Summary

Issue #140 calls for a pure-refactor split of `src/pylocal_akuvox/capabilities.py`
(currently 455 lines, flagged by `aislop scan` for `complexity/file-too-large`
against the 400-line threshold) into four sibling underscore-prefixed modules
along the natural concern boundaries the spec already locks in: types,
profile, matching, and defaults. The original `capabilities.py` is **deleted
entirely** — there is no `pylocal_akuvox.capabilities` shim module and no
`capabilities/` package; the subpath itself goes away (this is what makes
`import pylocal_akuvox.capabilities` raise `ModuleNotFoundError`). The
package's existing top-level re-export pattern in `pylocal_akuvox/__init__.py`
is preserved — it simply pulls the 5 public symbols from the new underscore
modules instead of from `capabilities.py`. This is the breaking change
FR-002/FR-003 mandate, and it MUST be flagged by `!` in the implementation
commit subject (FR-007). The 5 top-level public symbols (`Capability`,
`CapabilityStatus`, `DeviceCapabilities`,
`FieldAliases`, `SchemaShape`) remain importable from `pylocal_akuvox` with
identical identity (`is`-equality), so any consumer using the documented
top-level path sees no change. The 4 de-facto internals (`Provenance`,
`DeviceClassPattern`, `lookup_capabilities`, `DEFAULT_USER_FIELD_ALIASES`)
become formally internal — reachable only via their owning underscore module.

This plan ships as **a single PR with a single atomic implementation commit**
(plus a separate documentation commit if the changelog entry is logically
distinct — see Phase Decomposition below). The split + 20-file import
rewrite + new layout test + changelog entry land together because (a) the
intermediate states do not compile (deleting `capabilities.py` without
rewriting its consumers breaks every test) and (b) atomic-rename PRs are
the easiest refactor PRs to review — the delta is mechanical and reviewers
can verify the bijection between old and new without holding partial state
in their heads.

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also exercises
3.14 forward.
**Primary Dependencies**: No new runtime or test dependencies. Tooling
(`ruff`, `mypy`, `interrogate`, `aislop`, `sphinx`, `pytest`,
`pytest-asyncio`, `aioresponses`) is unchanged.
**Storage**: N/A — library only; this is a pure structural refactor with
no behavior change.
**Testing**: pytest + pytest-asyncio. Existing `tests/unit/` is the
regression net (every test stays semantically green; only import lines
change). One new test file is added: `tests/unit/test_capability_module_layout.py`.
**Target Platform**: Library consumed by async Python applications on
Linux/macOS/Windows. No platform-specific change.
**Project Type**: Single Python package (`src/pylocal_akuvox/`).
**Performance Goals**: Runtime hot-path performance is unchanged — the
split touches no `async` boundary, no I/O code path, and no algorithm.
Module-import cost rises modestly (4 file opens + 4 parse passes
instead of 1, plus the same total source-byte volume), but this
happens once at package import and is dominated by `import pylocal_akuvox`
overhead which is already in the millisecond range; no measurable impact
on consumers. After import, `sys.modules` caching means subsequent
`from pylocal_akuvox import …` calls are dict lookups, identical to today.
**Constraints**:

- **Behavior preservation** (FR per spec): every function body, dataclass
  field declaration, enum member name, and enum value is preserved
  verbatim. The only observable changes from a relocation standpoint
  are: each relocated class's `__module__` attribute reports the new
  underscore module name (e.g. `Capability.__module__` becomes
  `"pylocal_akuvox._capability_types"` instead of
  `"pylocal_akuvox.capabilities"`), which can affect `repr()` for
  bare classes, pickling round-trips that traverse `__module__`, and
  debug logging. **No production code or test in this repository
  inspects `__module__`** (verified by grep); no consumer relies on
  pickle of these types per project scope. Function call results,
  attribute reads, exception types, and method signatures are
  unchanged.
- **Backward compatible at the top-level public surface** (constitution
  §III). The 5 public symbols remain reachable from `pylocal_akuvox`
  with identical names and identity.
- **Breaking at the subpath surface** (the 4 internals + the dropped
  `pylocal_akuvox.capabilities` import path). Documented in changelog
  Unreleased "Breaking changes" subsection per FR-008.
- **Aislop-clean post-split**: each new module under the 400-line
  threshold (FR-004; verified per SC-002).
- **No `--no-verify` and no `--no-gpg-sign`** (constitution §V).
  Pre-commit hooks (now including `aislop ci --staged` per the recent
  pre-commit config update merged in PR #143) MUST pass on the
  implementation commit. Aislop's hook is the very gate this refactor
  exists to satisfy — it MUST run green.

**Scale/Scope**:

- **Source files in `src/pylocal_akuvox/`**: 15 file operations total —
  **10 import-rewritten** (`__init__.py`, `capability_matrix.py`,
  `capability_probe.py`, `capability_adapters.py`, `device.py`,
  `users.py`, `contacts.py`, `exceptions.py`, `models/users.py`,
  `models/contacts.py`), **4 created** (`_capability_types.py`,
  `_capability_profile.py`, `_capability_matching.py`,
  `_capability_defaults.py`), **1 deleted** (`capabilities.py`).
- **Documentation files**: 2 — `docs/_ext/capability_matrix.py`
  (1 import rewritten) and `docs/changelog.rst` (Unreleased "Breaking
  changes" subsection added; lands in the same PR per FR-008).
- **Test files**: 10 — **9 import-rewritten** (`test_capabilities.py`,
  `test_pattern.py`, `test_dispatch.py`, `test_users.py`,
  `test_contacts.py`, `test_device.py`, `test_matrix.py`,
  `test_unsupported_error.py`, `test_capability_probe.py`) and **1 new**
  (`test_capability_module_layout.py`).
- **Total touched**: 27 files (20 import-rewritten — i.e. the spec's
  "20 affected files" count enumerated in `data-model.md`
  §"Affected-File List" — plus 4 new source modules, 1 new test file,
  1 changelog edit, and 1 deletion). The implementation commit's
  `git show --stat` will list 26 of these (the deletion counts as one
  of the 27); the changelog edit may live in the separate
  documentation commit per the Phase Decomposition.
- **Net LOC change**: small. New per-module headers (SPDX × 4, module
  docstring × 4, imports × 4, `__all__` × 4) add ~80 lines of overhead;
  the deleted `capabilities.py` removes 455 lines. Net: ~-110 lines of
  source + ~+50 lines for the new layout test.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2. Re-checked
after the file-by-file plan below — see "Post-Design Re-Check".*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | Each new module gets the standard SPDX header pair, a focused module docstring describing its single concern, and full type annotations preserved verbatim from the source. No code body is modified — only relocated — so cyclomatic complexity for every existing function is unchanged. ruff, mypy, interrogate stay green; the only configuration change is none (the four new modules pick up the same project-wide ruff and mypy config). C901 limits are not approached because no method body changes. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | The new layout-assertion test in `tests/unit/test_capability_module_layout.py` is written **first locally** (TDD red phase against `main`: the test fails before the split, because `capabilities.py` still exists). Once the 4 new underscore modules are staged alongside the deletion of `capabilities.py`, the test passes. The published implementation commit is green at every CI gate — the "red" state exists only in the implementer's working tree during authoring, never in a pushed commit. The test asserts `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`, that the 4 underscore modules import successfully, and that the 5 public symbols round-trip via top-level (`pylocal_akuvox.Capability is pylocal_akuvox._capability_types.Capability`). For the import-rewrite portion, the existing `tests/unit/test_*.py` files ARE the regression net — they exercised the old import paths, and rewriting their imports to the new paths confirms each new module exposes the symbols its consumers depend on. **No test assertion semantics change** — only `from pylocal_akuvox.capabilities import …` lines flip to `from pylocal_akuvox._capability_types import …` / `_capability_profile` / `_capability_matching` / `_capability_defaults` per the symbol→module table in the Import-Rewrite Plan below. Coverage MUST be maintained at 100% branch on `pylocal_akuvox` (validation gate below). |
| **III. User Experience Consistency** | PASS | The 5 documented public symbols remain at their documented import path (`from pylocal_akuvox import …`). Existing consumer code that uses the top-level path sees zero change. The breaking change is loud and well-bounded: anyone using `pylocal_akuvox.capabilities.X` gets `ModuleNotFoundError` (FR-002/FR-003) and finds the migration path in the Unreleased "Breaking changes" subsection of `docs/changelog.rst` (FR-008). Error message is Python's stock `ModuleNotFoundError: No module named 'pylocal_akuvox.capabilities'` — perfectly actionable and unambiguous. |
| **IV. Performance Requirements** | PASS | Pure structural refactor. No runtime hot path is touched. Module-import cost rises modestly (4 file opens + 4 parse passes vs. 1, total source-byte volume unchanged) — consistent with the Performance Goals note above. The increase is one-time at package import, well under millisecond-scale, and not measurable against existing `import pylocal_akuvox` overhead. After import, `sys.modules` caching makes subsequent symbol access identical to today. No event-loop blocking is introduced — no `async` boundaries are crossed by the refactor. The `__init__.py` re-export pattern was already in use; this refactor only changes the source modules behind the re-exports. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | The implementation lands as a single atomic commit (or two — see Phase Decomposition for the implementation/changelog split). Commit subject uses Conventional Commits with **`!` to flag the breaking change** per FR-007. The spec's example wording (`Refactor(capabilities)!: Split module into focused submodules`) is 61 chars and exceeds the 50-char Conventional-Commits soft cap; the implementer SHOULD use a tighter form such as `Refactor(capabilities)!: Split into submodules` (46 chars) or another ≤50-char wording that retains the `!` marker. The `!` marker is the load-bearing requirement; the exact wording is the implementer's call. All four new files carry SPDX headers verbatim. DCO `-s` sign-off is mandatory. Pre-commit hooks (ruff, mypy, interrogate, REUSE, **aislop ci --staged**, pytest) MUST run green on every commit; `--no-verify` is prohibited. |
| **VI. Phased Development** | PASS — single phase | This is one logical change (file split + import rewrite) with no intermediate user-visible value to deliver in stages — the codebase does not compile between "delete `capabilities.py`" and "rewrite all 20 consumers". Splitting into multiple PRs would require either an intermediate shim (which contradicts the explicit decision to break the subpath cleanly per Decision 1 in research.md) or a broken `main` (which violates §VI's "checkpoint where all CI tests pass"). The single-phase choice is justified explicitly in Phase Decomposition below. |

**Result**: All gates pass. **Complexity Tracking** section below is empty —
no justified violations.

## Phase Decomposition

### Decision: ONE phase, single PR

**Recommendation**: One phase, one PR, **one atomic implementation commit**
plus optionally **one separate documentation commit** for the changelog
entry (the `docs/changelog.rst` Unreleased "Breaking changes" subsection
per FR-008). The two-commit split keeps the `Refactor(capabilities)!` commit
focused on the code change and the `Docs(changelog)` commit focused on the
user-facing announcement; reviewers and `git blame` benefit from the
separation. Both commits land in the same PR.

### Rationale (why not two phases)

The instructions invite a justified two-phase decomposition, but every
property of this refactor argues against it:

1. **No intermediate state compiles.** Once `capabilities.py` is deleted,
   every one of its 20 consumers must already be rewritten to the new
   underscore module paths or the package fails to import. Conversely,
   rewriting consumers first while `capabilities.py` still exists provides
   no value — the consumers would import from the new modules that don't
   exist yet, immediately breaking. Any phasing scheme requires either
   (a) a temporary `capabilities.py` shim that re-exports from the
   underscore modules — which contradicts the explicit Decision 1 in
   `research.md` (sibling-modules-with-no-shim is the deliberate clean
   break), or (b) a temporary broken `main` between phases — which
   violates constitution §VI.
2. **The breaking-change announcement and the breaking change itself
   should land together.** FR-007's `!` marker on the implementation
   commit and FR-008's changelog entry name the same event. Splitting
   them across PRs would either announce a break before it happens
   (changelog ahead of code) or perform a break before it's announced
   (code ahead of changelog) — both are confusing and neither is needed.
3. **Atomic-rename PRs are the easiest refactor PRs to review.**
   Reviewers can verify the bijection between old and new (every symbol
   migrated, every consumer rewritten, no leftover) by reading a single
   diff. A multi-phase rollout would force reviewers to track partial
   state across PRs and risk merge-skew if the second PR landed against
   a slightly different `main` than the first.
4. **Loss of the rename property if split.** Git tracks `capabilities.py`
   → `_capability_*.py` as a delete + 4 adds in either case (no
   rename-detection threshold survives splitting one file into four),
   but the human reviewer benefit of "one diff, one decision" is real
   and is forfeited by phasing.
5. **Aislop's gate is binary.** The whole point of issue #140 is to get
   `capabilities.py` under the 400-line threshold. There is no partial
   credit — the file is either gone (refactor complete, gate passes) or
   it isn't.

A two-phase rollout would only make sense if (a) a downstream consumer
migration window were needed — but the only known downstream
(`tykeal/homeassistant-local-akuvox`) uses top-level imports and is
unaffected, per the spec FR-009 spot-check — or (b) the new layout were
experimental — but it isn't; the split is locked in by the spec.

### Single-phase deliverable summary

The steps below describe the **logical authoring order** the implementer
follows locally during TDD red-green-refactor; they are NOT 9 separate
commits. All 8 source/test changes (steps 1–8) ship in **one** atomic
implementation commit that is itself green at every CI gate. Step 9
(changelog) is the optional second commit in the same PR.

| Step | Deliverable | Owning commit |
|---|---|---|
| 1 | Author `tests/unit/test_capability_module_layout.py` first (TDD red phase locally — the test would fail on `main` because `capabilities.py` still exists; once steps 2–7 are also staged, the implementation commit as a whole is green) | implementation commit |
| 2 | Create `src/pylocal_akuvox/_capability_types.py`, `_capability_profile.py`, `_capability_matching.py`, `_capability_defaults.py` with relocated content + SPDX headers + module docstrings | implementation commit |
| 3 | Rewrite `__init__.py` re-exports to point at the new underscore modules | implementation commit |
| 4 | Rewrite all 9 internal `src/pylocal_akuvox/*.py` consumers' imports | implementation commit |
| 5 | Rewrite `docs/_ext/capability_matrix.py` import | implementation commit |
| 6 | Rewrite all 9 `tests/unit/test_*.py` consumers' imports | implementation commit |
| 7 | Delete `src/pylocal_akuvox/capabilities.py` | implementation commit |
| 8 | Run validation gates (see below); confirm 100% branch coverage maintained on `pylocal_akuvox` | implementation commit (verification of the staged tree before `git commit`) |
| 9 | Add Unreleased "Breaking changes" subsection to `docs/changelog.rst` | documentation commit (separate but in same PR) |

The implementation commit MUST be CI-green when pushed — pre-commit
hooks (which include `pytest (100% coverage)`) run on the staged tree
before the commit object is created, so no failing test ever lands.
The "red phase" referred to above is the local authoring sequence
(write test → watch it fail against `main` → implement → watch it pass
on the staged tree), not a state of the published commit.

The implementation commit subject MUST contain `!` per FR-007. A
recommended form is `Refactor(capabilities)!: Split into submodules`
(46 chars; under the 50-char Conventional-Commits soft cap). The spec's
own example wording (`Refactor(capabilities)!: Split module into focused
submodules`) is 61 chars and overflows; the implementer SHOULD pick a
tighter form. The `!` marker is the only load-bearing constraint here.

The documentation commit subject is `Docs(changelog): Announce
009-capabilities split` (48 chars).

## Project Structure

### Documentation (this feature)

```text
specs/009-capabilities-module-split/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec (input)
├── research.md          # Phase 0 output — 7 decisions
├── data-model.md        # Module layout + 20-file affected-file list
├── quickstart.md        # 9-step verification recipe
├── contracts/
│   ├── capability-types.md     # _capability_types.py contract
│   ├── capability-profile.md   # _capability_profile.py contract
│   ├── capability-matching.md  # _capability_matching.py contract
│   └── capability-defaults.md  # _capability_defaults.py contract
└── tasks.md             # NOT generated by this command — produced by /speckit.tasks
```

### Source Code (repository root)

Pre-feature (current state, abbreviated):

```text
src/pylocal_akuvox/
├── __init__.py                  # Re-exports 5 public capability symbols from capabilities
├── capabilities.py              # 455 lines — flagged by aislop (the file this spec eliminates)
├── capability_matrix.py         # Imports from pylocal_akuvox.capabilities
├── capability_probe.py          # Imports from pylocal_akuvox.capabilities
├── capability_adapters.py       # Imports from pylocal_akuvox.capabilities
├── device.py                    # Top-level + 4 deferred imports from capabilities
├── users.py                     # Top-level + TYPE_CHECKING from capabilities
├── contacts.py                  # Top-level + TYPE_CHECKING from capabilities
├── exceptions.py                # TYPE_CHECKING-only from capabilities
└── models/
    ├── users.py                 # TYPE_CHECKING + deferred from capabilities
    └── contacts.py              # TYPE_CHECKING + deferred from capabilities
```

Post-feature (only changed area shown; `capabilities.py` is gone):

```text
src/pylocal_akuvox/
├── __init__.py                  # Re-exports 5 public symbols from _capability_types and _capability_profile
├── _capability_types.py         # NEW — Capability, CapabilityStatus, SchemaShape (~120 lines)
├── _capability_profile.py       # NEW — FieldAliases, Provenance, DeviceCapabilities (~210 lines)
├── _capability_matching.py      # NEW — _parse_firmware_segments, DeviceClassPattern, lookup_capabilities (~210 lines)
├── _capability_defaults.py      # NEW — DEFAULT_USER_FIELD_ALIASES (~40 lines)
├── capabilities.py              # DELETED
├── capability_matrix.py         # Imports rewritten to underscore modules
├── capability_probe.py          # Imports rewritten to underscore modules
├── capability_adapters.py       # Imports rewritten to underscore modules
├── device.py                    # Imports rewritten (top-level + 4 deferred sites)
├── users.py                     # Imports rewritten (top-level + TYPE_CHECKING)
├── contacts.py                  # Imports rewritten (top-level + TYPE_CHECKING)
├── exceptions.py                # Imports rewritten (TYPE_CHECKING only — to _capability_types)
└── models/
    ├── users.py                 # Imports rewritten (TYPE_CHECKING + deferred)
    └── contacts.py              # Imports rewritten (TYPE_CHECKING + deferred)
```

**Structure Decision**: Four sibling underscore-prefixed modules at the
package root, **with no `capabilities/` package and no `capabilities.py`
shim**. The decision is locked in `research.md` Decision 1 — sibling
modules give a clean `ModuleNotFoundError` on the dropped subpath, which
neither a regular package (with `__init__.py`) nor a PEP 420 namespace
package would deliver.

## File-by-File Plan

### New module 1: `src/pylocal_akuvox/_capability_types.py`

**Owns** (per `data-model.md` and `contracts/capability-types.md`):

- `Capability` (enum.Enum, str values) — canonical capability identifiers
- `CapabilityStatus` (enum.Enum, str values) — three-valued status
- `SchemaShape` (enum.Enum, str values) — contact schema discriminator

**Public re-exports** (top-level, via `pylocal_akuvox.__init__`): all three.

**Module-top imports**:

```python
from __future__ import annotations

import enum
```

**`__all__`**:

```python
__all__ = ["Capability", "CapabilityStatus", "SchemaShape"]
```

**Sibling-module imports**: none. This is the leaf of the dependency
graph — every other capability module may import from it without cycle
risk (per `data-model.md` §"`_capability_types.py`").

**Estimated size**: ~120 lines (per `research.md` Decision 4 arithmetic).

---

### New module 2: `src/pylocal_akuvox/_capability_profile.py`

**Owns**:

- `FieldAliases` (frozen dataclass, kw_only)
- `Provenance` (frozen dataclass, kw_only) — **internal-only**
- `DeviceCapabilities` (frozen dataclass, kw_only) — with `status_of()` and
  `require()` methods; uses `MappingProxyType` in `__post_init__`

**Public re-exports** (top-level): `FieldAliases`, `DeviceCapabilities`.
`Provenance` is **NOT** re-exported (internal — see `contracts/capability-profile.md`).

**Module-top imports**:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

if TYPE_CHECKING:
    from collections.abc import Mapping
```

**`__all__`**:

```python
__all__ = ["DeviceCapabilities", "FieldAliases", "Provenance"]
```

**Sibling-module imports**:

- `_capability_types` (runtime, top-level) — for `Capability`,
  `CapabilityStatus`, `SchemaShape`
- `pylocal_akuvox.exceptions` (runtime, top-level) — for
  `AkuvoxUnsupportedError` (raised by `DeviceCapabilities.require()`)

**Cycle risk**: none. `_capability_types` has no sibling imports;
`exceptions.py` only imports `Capability` under `TYPE_CHECKING` (verified
in current `exceptions.py:11`), so no runtime cycle is possible.

**Estimated size**: ~210 lines.

---

### New module 3: `src/pylocal_akuvox/_capability_matching.py`

**Owns**:

- `_parse_firmware_segments` (private function) — single-underscore
  prefix; not in `__all__` but importable for white-box testing
- `DeviceClassPattern` (frozen dataclass, kw_only) — **internal-only**
- `lookup_capabilities` (function) — **internal-only**

**Public re-exports** (top-level): **none**.

**Module-top imports**:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pylocal_akuvox._capability_profile import DeviceCapabilities

if TYPE_CHECKING:
    from pylocal_akuvox.models import DeviceInfo
```

**Lazy import (runtime, inside `lookup_capabilities` body)**:

```python
def lookup_capabilities(device_info: DeviceInfo) -> DeviceCapabilities | None:
    from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX
    ...
```

This preserves the existing circular-dependency break at the current
`capabilities.py:446–449` site (per `data-model.md` §"`_capability_matching.py`"
and `contracts/capability-matching.md` "Dependencies"). Without the lazy
import, `_capability_matching` ↔ `capability_matrix` would form a hard
cycle at module import time because `capability_matrix.py` imports
`DeviceClassPattern` from `_capability_matching`.

**`__all__`**:

```python
__all__ = ["DeviceClassPattern", "lookup_capabilities"]
```

**Sibling-module imports**:

- `_capability_profile` (runtime, top-level) — for `DeviceCapabilities`
  return type
- `pylocal_akuvox.models` (TYPE_CHECKING only) — for `DeviceInfo`
  annotation
- `pylocal_akuvox.capability_matrix` (lazy, function-body) — for
  `CAPABILITY_MATRIX`

**Cycle risk**: none. Top-level imports go down the dependency graph
only (`_capability_profile` → `_capability_types`); the back-edge to
`capability_matrix` is broken by the lazy import.

**Estimated size**: ~210 lines.

---

### New module 4: `src/pylocal_akuvox/_capability_defaults.py`

**Owns**:

- `DEFAULT_USER_FIELD_ALIASES` (constant, type `FieldAliases`) —
  **internal-only**

**Public re-exports** (top-level): **none**.

**Module-top imports**:

```python
from __future__ import annotations

from pylocal_akuvox._capability_profile import FieldAliases
```

**`__all__`**:

```python
__all__ = ["DEFAULT_USER_FIELD_ALIASES"]
```

**Sibling-module imports**:

- `_capability_profile` (runtime, top-level) — for `FieldAliases` (the
  constant's type)

**Cycle risk**: none. `_capability_profile` is upstream and does not
import from `_capability_defaults`.

**Estimated size**: ~40 lines.

---

### Cross-module dependency graph (post-split)

```text
            _capability_types.py          (leaf — depends on stdlib only)
                    ▲
                    │
                    │
        _capability_profile.py            (depends on _capability_types + exceptions)
                ▲           ▲
                │           │
                │           │
    _capability_matching.py    _capability_defaults.py
                │
                │ (lazy, function-body)
                ▼
        capability_matrix.py              (depends on _capability_types,
                                           _capability_profile,
                                           _capability_matching at module top)
```

The graph is a DAG at module-import time. The single back-edge
(`_capability_matching` → `capability_matrix`) is gated by a lazy
function-body import, exactly as it is in today's `capabilities.py`.

## Import-Rewrite Plan

This refactor rewrites every `from pylocal_akuvox.capabilities import …`
statement in 20 files. The mapping is mechanical and follows the symbol→module
table in `data-model.md` §"Module Layout Table":

| Symbol | New owning module |
|---|---|
| `Capability` | `pylocal_akuvox._capability_types` |
| `CapabilityStatus` | `pylocal_akuvox._capability_types` |
| `SchemaShape` | `pylocal_akuvox._capability_types` |
| `FieldAliases` | `pylocal_akuvox._capability_profile` |
| `Provenance` | `pylocal_akuvox._capability_profile` |
| `DeviceCapabilities` | `pylocal_akuvox._capability_profile` |
| `DeviceClassPattern` | `pylocal_akuvox._capability_matching` |
| `lookup_capabilities` | `pylocal_akuvox._capability_matching` |
| `DEFAULT_USER_FIELD_ALIASES` | `pylocal_akuvox._capability_defaults` |
| `_parse_firmware_segments` | `pylocal_akuvox._capability_matching` (private) |

Where a single `from pylocal_akuvox.capabilities import (A, B, C)` block
imports symbols that now live in different underscore modules, the block
splits into one statement per new module, ordered alphabetically by module
name (matches existing project ruff/isort style).

### Group A: Production source — package internals

| File | Sites | Rewrite strategy |
|---|---|---|
| `src/pylocal_akuvox/__init__.py` | 1 (top-level re-export block at line 9) | Replace single `from pylocal_akuvox.capabilities import (Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape)` block with two blocks ordered alphabetically by module name (matches existing project isort/ruff style): (i) `from pylocal_akuvox._capability_profile import (DeviceCapabilities, FieldAliases)`; (ii) `from pylocal_akuvox._capability_types import (Capability, CapabilityStatus, SchemaShape)`. **Top-level `__all__` is untouched** — same 5 names appear there as today (FR-001). |
| `src/pylocal_akuvox/capability_matrix.py` | 1 (top-level block at line 35) | Split per symbol→module table. Imports `Capability`, `CapabilityStatus`, `SchemaShape` from `_capability_types`; `DeviceCapabilities`, `FieldAliases`, `Provenance` from `_capability_profile`; `DeviceClassPattern` from `_capability_matching`. Note: `Provenance` is now an underscore-module-only import — appropriate because `capability_matrix.py` is internal. |
| `src/pylocal_akuvox/capability_probe.py` | 1 (top-level block at line 30) | Split per symbol→module table. Mostly `_capability_types` and `_capability_profile`. |
| `src/pylocal_akuvox/capability_adapters.py` | 1 (top-level at line 22, single name `Capability`) | `from pylocal_akuvox._capability_types import Capability`. |
| `src/pylocal_akuvox/device.py` | 5 sites: top-level block at line 13; deferred imports at lines 333, 385 (both `DEFAULT_USER_FIELD_ALIASES`); 802, 828 (both `SchemaShape`) | Top-level block: split per table. Lines 333, 385: `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`. Lines 802, 828: `from pylocal_akuvox._capability_types import SchemaShape`. |
| `src/pylocal_akuvox/users.py` | 2 sites: top-level at line 11 (`DEFAULT_USER_FIELD_ALIASES`); `TYPE_CHECKING` block at line 17 (`DeviceCapabilities, FieldAliases`) | Line 11: `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`. Line 17: `from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases`. |
| `src/pylocal_akuvox/contacts.py` | 2 sites: top-level at line 19 (`SchemaShape`); `TYPE_CHECKING` block at line 25 (`DeviceCapabilities`) | Line 19: `from pylocal_akuvox._capability_types import SchemaShape`. Line 25: `from pylocal_akuvox._capability_profile import DeviceCapabilities`. |
| `src/pylocal_akuvox/exceptions.py` | 1 site: `TYPE_CHECKING` block at line 11 (`Capability`) | `from pylocal_akuvox._capability_types import Capability`. |
| `src/pylocal_akuvox/models/users.py` | 2 sites: `TYPE_CHECKING` at line 14 (`DeviceCapabilities`); deferred at line 57 (`DEFAULT_USER_FIELD_ALIASES`) | Line 14: `from pylocal_akuvox._capability_profile import DeviceCapabilities`. Line 57: `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`. Also rewrite the docstring `:data:` cross-reference at line 49 per `research.md` Decision 7 strategy (a) — spell out the value inline. |
| `src/pylocal_akuvox/models/contacts.py` | 2 sites: `TYPE_CHECKING` at line 14 (`DeviceCapabilities`); deferred at line 61 (`SchemaShape`) | Line 14: `from pylocal_akuvox._capability_profile import DeviceCapabilities`. Line 61: `from pylocal_akuvox._capability_types import SchemaShape`. |

Additionally, **docstring cross-reference rewrites** per `research.md`
Decision 7 (separate from import statements):

- `src/pylocal_akuvox/users.py` lines 78, 153, 282 — `:data:\`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES\`` → strategy (a): spell out value inline.
- `src/pylocal_akuvox/capability_matrix.py` lines 8, 12 — `pylocal_akuvox.capabilities` references → strategy (c): use underscore path.

### Group B: Sphinx extension

| File | Sites | Rewrite strategy |
|---|---|---|
| `docs/_ext/capability_matrix.py` | 1 site: top-level at line 30 | `from pylocal_akuvox._capability_types import Capability, CapabilityStatus`. Per FR-010, the underscore path is appropriate here because this is a maintainer-internal Sphinx extension, not a public consumer integration. |

### Group C: Tests

All test imports are rewritten per the symbol→module table. Tests asserting
on internal-only symbols (`Provenance`, `DeviceClassPattern`,
`lookup_capabilities`, `DEFAULT_USER_FIELD_ALIASES`) MUST import from the
underscore modules — the spec's Decision 6 (white-box test imports)
locks this in.

| File | Sites (line refs from current `main`) | Rewrite strategy |
|---|---|---|
| `tests/unit/test_capabilities.py` | 1 main block at line 22 + module docstring (line 4) cross-reference | Split block per symbol→module table. Rewrite docstring `capabilities` reference to underscore path (Decision 7 strategy c). |
| `tests/unit/test_pattern.py` | 1 site at line 25 (`DeviceClassPattern`) | `from pylocal_akuvox._capability_matching import DeviceClassPattern`. |
| `tests/unit/test_dispatch.py` | 1 site at line 37 (`Capability`) | `from pylocal_akuvox._capability_types import Capability`. |
| `tests/unit/test_users.py` | 13 sites (lines 22, 844, 898, 924, 965, 1002, 1041, 1103, 1164, 1243, 1277, 1397, 1432) — most are inline-in-test deferred imports | Rewrite each per symbol→module table. `Capability`/`CapabilityStatus` → `_capability_types`; `DeviceCapabilities`/`FieldAliases` → `_capability_profile`; `DEFAULT_USER_FIELD_ALIASES` → `_capability_defaults`. |
| `tests/unit/test_contacts.py` | 10 sites (lines 22, 554, 589, 615, 646, 677, 699, 720, 789, 855) — most are inline-in-test deferred | Rewrite each per table. Mostly `SchemaShape`/`Capability`/`CapabilityStatus` → `_capability_types`; `DeviceCapabilities` → `_capability_profile`. |
| `tests/unit/test_device.py` | 8 sites (lines 573, 606, 703, 851, 870, 889, 985, 1107) — inline-in-test deferred | Rewrite each per table. Includes `lookup_capabilities` (line 703) → `_capability_matching`. |
| `tests/unit/test_matrix.py` | 2 sites (lines 26, 241) | Split per table — references `DeviceClassPattern`, `Provenance`, `DeviceCapabilities`, `FieldAliases`, `Capability`, `CapabilityStatus` → split across `_capability_matching`, `_capability_profile`, `_capability_types`. |
| `tests/unit/test_unsupported_error.py` | 1 site at line 28 (`Capability`) | `from pylocal_akuvox._capability_types import Capability`. |
| `tests/unit/test_capability_probe.py` | 2 sites (lines 24, 1489) | Split per table — `Capability`/`CapabilityStatus` → `_capability_types`; `DeviceCapabilities` → `_capability_profile`. |

**Total test-file import rewrites**: 9 files (matches `data-model.md`
§"Test files (`tests/unit/`)" exactly).

## Subpath-Removal Verification Plan

A new test file `tests/unit/test_capability_module_layout.py` is added to
enforce the breaking-change boundary in CI. It carries SPDX headers, a
module docstring naming the spec, and the following assertions per FR-011:

### Assertion 1 — `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`

```python
def test_capabilities_subpath_is_gone() -> None:
    """The old subpath import path must raise ModuleNotFoundError."""
    import pytest

    with pytest.raises(ModuleNotFoundError):
        import pylocal_akuvox.capabilities  # noqa: F401
```

This is the canonical assertion of the breaking change (FR-002 / SC-003).

### Assertion 2 — `from pylocal_akuvox.capabilities import X` raises error

```python
def test_capabilities_subpath_from_import_is_gone() -> None:
    """from-import on the old subpath must also raise."""
    import pytest

    with pytest.raises((ModuleNotFoundError, ImportError)):
        exec("from pylocal_akuvox.capabilities import Capability")
```

Covers FR-003 (catches both `ModuleNotFoundError` and its `ImportError`
superclass — Python guarantees one of these is raised).

### Assertion 3 — All four new underscore modules import successfully

```python
def test_underscore_modules_importable() -> None:
    """Each of the four new internal modules is importable."""
    import importlib

    for name in (
        "pylocal_akuvox._capability_types",
        "pylocal_akuvox._capability_profile",
        "pylocal_akuvox._capability_matching",
        "pylocal_akuvox._capability_defaults",
    ):
        importlib.import_module(name)
```

Covers FR-005 (internal symbols are importable from their respective
underscore modules) at the module level — symbol-level imports are
covered by the existing `tests/unit/test_capabilities.py` after its
own import rewrites.

### Assertion 4 — Top-level public symbols round-trip via `_capability_types` / `_capability_profile`

```python
def test_public_symbols_roundtrip_via_top_level() -> None:
    """Top-level pylocal_akuvox.X is the same object as its source module."""
    import pylocal_akuvox
    import pylocal_akuvox._capability_profile as profile_mod
    import pylocal_akuvox._capability_types as types_mod

    assert pylocal_akuvox.Capability is types_mod.Capability
    assert pylocal_akuvox.CapabilityStatus is types_mod.CapabilityStatus
    assert pylocal_akuvox.SchemaShape is types_mod.SchemaShape
    assert pylocal_akuvox.DeviceCapabilities is profile_mod.DeviceCapabilities
    assert pylocal_akuvox.FieldAliases is profile_mod.FieldAliases
```

Identity equality (`is`) is the strongest possible round-trip assertion —
it confirms the re-export does not accidentally wrap or copy. Covers
FR-001 + the spec's User Story 1 acceptance scenario #1.

### Assertion 5 — Top-level `__all__` is unchanged for the 5 capability symbols

```python
def test_capability_symbols_in_top_level_all() -> None:
    """The 5 public capability symbols remain in pylocal_akuvox.__all__."""
    import pylocal_akuvox

    for name in (
        "Capability",
        "CapabilityStatus",
        "DeviceCapabilities",
        "FieldAliases",
        "SchemaShape",
    ):
        assert name in pylocal_akuvox.__all__
```

Belt-and-suspenders — guards against an accidental `__all__` edit that
would silently de-publicise a symbol while leaving the import working.

## Validation Gates

Every gate below MUST pass green on the implementation commit (NOT
on a subsequent fix-up commit) before the PR is opened. The
documentation commit (changelog) does not change source behavior, so
the gates are repeated on it but expected to remain green trivially.

| Gate | Command | Pass criterion |
|---|---|---|
| **Unit tests** | `uv run pytest tests/ -x -q` | exit 0; all tests pass; the new `test_capability_module_layout.py` is included automatically by `tests/unit/` discovery |
| **Lint (source)** | `uv run ruff check src/ tests/` | exit 0; zero warnings |
| **Type check** | `uv run mypy src/` | exit 0; zero errors (mypy strict per project config) |
| **Pre-commit (full)** | `git add -A && pre-commit run --all-files` | exit 0; includes ruff, mypy, interrogate, REUSE, **and `aislop ci --staged`** (the gate that motivates this whole spec — must report no `complexity/file-too-large` on any of the 4 new modules). The leading `git add -A` is required: the project's aislop hook is configured with `pass_filenames: false` and operates on the staged diff, so running `pre-commit run --all-files` against an unstaged tree would scan an empty staged set and report a false-green. The dedicated **Aislop new-module size** gate below is the belt-and-suspenders explicit check that does NOT depend on staging. |
| **Doc build** | `cd docs && uv run sphinx-build -W -b html . _build/html` | exit 0; treats warnings as errors (the `-W` flag); confirms the rewritten `docs/_ext/capability_matrix.py` import works at autodoc time |
| **Branch coverage** | `uv run pytest --cov=pylocal_akuvox --cov-branch --cov-report=term-missing tests/` | 100% branch coverage maintained on `pylocal_akuvox` (current baseline; SC implicitly maintained by spec FR-006). No new uncovered branches introduced. |
| **Aislop new-module size** | `uv run aislop scan src/pylocal_akuvox/_capability_*.py` | No `complexity/file-too-large` warnings on any of the 4 new modules (SC-002 explicit verification). Each must be under 400 lines. |
| **Aislop project-wide** | `uv run aislop scan` | `capabilities.py` no longer appears in the `complexity/file-too-large` list (it has been deleted). `device.py` and `capability_probe.py` are still flagged — those are issues #142 and #141, out of scope. |
| **Subpath removal smoke test** | `uv run python -c "import pylocal_akuvox.capabilities"` | exits non-zero with `ModuleNotFoundError: No module named 'pylocal_akuvox.capabilities'`. SC-003. |
| **Top-level imports smoke test** | `uv run python -c "from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape; print('ok')"` | exits 0; prints `ok`. SC-004. |
| **Commit subject `!`** | `git log -1 --format=%s` on the implementation commit | output contains `!` before the colon, matching `Refactor(capabilities)!: …`. SC-006. |
| **Changelog entry** | `grep -A 5 "Breaking changes" docs/changelog.rst` | output names the dropped subpath, the 4 internal symbols, and the migration path. SC-005. |

The full set is reproducible from `quickstart.md` Steps 1–9, which the
implementer follows verbatim during PR self-review.

## Post-Design Re-Check

After authoring the file-by-file plan, import-rewrite plan, and
subpath-removal verification plan above:

| Principle | Status | Re-check Notes |
|-----------|--------|----------------|
| **I. Code Quality** | PASS | Each new module's imports are minimal and ordered (stdlib → first-party). No dataclass body, enum body, or function body is modified, so cyclomatic complexity is unchanged on every preserved entity. The four new modules add ~80 lines of header overhead total (SPDX × 4, docstring × 4, imports × 4, `__all__` × 4) — comfortably below the 400-line threshold for each. ruff/mypy/interrogate pass because the rewritten imports follow project style and the relocated docstrings remain intact. |
| **II. TDD** | PASS | The new layout-assertion test in `tests/unit/test_capability_module_layout.py` is written first **locally** (TDD red phase against `main` only — the test fails before any split happens). Once the 4 new underscore modules + the `capabilities.py` deletion are also staged, the test passes; the published commit is green at every CI gate. This satisfies the "failing test first" constitution requirement without ever pushing a red commit. The 9 existing test files exercise the new underscore modules' surface (after their imports are rewritten); no test assertion semantics change, so the regression net stays valid. Branch coverage is preserved at 100%. |
| **III. UX** | PASS | The 5 documented public symbols remain at `pylocal_akuvox.X`. The breaking change (subpath removal + 4 internals demoted) is loud (`ModuleNotFoundError`), well-bounded, and announced in the Unreleased "Breaking changes" subsection of `docs/changelog.rst` with the documented migration path. |
| **IV. Performance** | PASS | The dependency graph (post-split) is a DAG at module-import time. The single back-edge is gated by the existing lazy import (preserved verbatim). No new I/O or async boundaries are introduced. |
| **V. Atomic Commits** | PASS | Single implementation commit + optional documentation commit, both with DCO `-s` and dual co-author trailers (Claude + GitHub Copilot). SPDX headers on the 4 new files and the new test file. Conventional Commits with capitalized type and `!` for the breaking change (FR-007). Pre-commit hooks (including aislop) MUST run green; `--no-verify` is prohibited. |
| **VI. Phased Development** | PASS | Single phase, one PR. Justified above — no intermediate compilable state exists, the changelog and code MUST land together, and the atomic-rename property is the whole reason the refactor is reviewable. |

**Result**: All gates pass post-design. **Complexity Tracking** below
remains empty.

## Complexity Tracking

> No constitutional violations to justify — left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none)    | (none)     | (none)                               |
