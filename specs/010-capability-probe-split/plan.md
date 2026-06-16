<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Refactor capability_probe.py Under Aislop Size Limit

**Branch**: `010-capability-probe-split` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-capability-probe-split/spec.md`

## Summary

Issue #141 calls for a pure-refactor split of
`src/pylocal_akuvox/capability_probe.py` (currently 465 lines, flagged by
`aislop scan` for `complexity/file-too-large` against the 400-line
threshold) into four sibling underscore-prefixed modules along the
natural concern boundaries the spec already locks in: outcome
vocabulary, classifiers, parsers, and orchestration. The original
`capability_probe.py` is **deleted entirely** — there is no
`pylocal_akuvox.capability_probe` shim module and no
`capability_probe/` package; the subpath itself goes away (this is what
makes `import pylocal_akuvox.capability_probe` raise
`ModuleNotFoundError`). Unlike spec 009, NO symbol from the four new
modules is added to top-level `pylocal_akuvox.__all__` — the
consumer-facing handle remains `AkuvoxDevice.probe_capabilities()` (a
method on the already-public `AkuvoxDevice`), and the package
`__all__` is unchanged. This is the breaking change FR-002 / FR-003
mandate, and it MUST be flagged by `!` in the implementation commit
subject (FR-007).

This plan ships as **a single PR with three atomic commits** following
the precedent set by spec 009 / PR #148: (1) the `Refactor(probe)!`
implementation commit (the split + 2-file import rewrite + new layout
tests), (2) a `Docs(changelog)` commit announcing the breaking change,
and (3) a `Docs(tasks)` commit marking the 010 task list complete.
All three land in the same PR. The single-phase choice is justified
below: intermediate states do not compile, the breaking-change
announcement and the breaking change itself must land together, and
atomic-rename PRs are the easiest refactor PRs to review.

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also
exercises 3.14 forward.
**Primary Dependencies**: No new runtime or test dependencies. Tooling
(`ruff`, `mypy`, `interrogate`, `aislop`, `sphinx`, `pytest`,
`pytest-asyncio`, `aioresponses`) is unchanged.
**Storage**: N/A — library only; this is a pure structural refactor with
no behavior change.
**Testing**: pytest + pytest-asyncio. Existing `tests/unit/` is the
regression net (every test stays semantically green; only import lines
and one docstring change). The existing
`tests/unit/test_capability_module_layout.py` (added by spec 009) is
**extended** with four new probe-side test functions per FR-011 — no
new test file is created.
**Target Platform**: Library consumed by async Python applications on
Linux/macOS/Windows. No platform-specific change.
**Project Type**: Single Python package (`src/pylocal_akuvox/`).
**Performance Goals**: Runtime hot-path performance is unchanged — the
split touches no `async` boundary, no I/O code path, and no algorithm.
Module-import cost rises modestly (4 file opens + 4 parse passes
instead of 1, plus the same total source-byte volume), but this
happens once at package import and is dominated by `import pylocal_akuvox`
overhead which is already in the millisecond range; no measurable
impact on consumers. After import, `sys.modules` caching means
subsequent `from pylocal_akuvox._capability_probe import …` calls are
dict lookups, identical to today.
**Constraints**:

- **Behavior preservation** (per spec FR-001): every function body,
  enum member name, marker-tuple element, and step-path constant
  string is preserved verbatim. The only observable change from a
  relocation standpoint is that each relocated entity's `__module__`
  attribute reports the new underscore module name (e.g.
  `_ProbeOutcome.__module__` becomes
  `"pylocal_akuvox._probe_outcomes"` instead of
  `"pylocal_akuvox.capability_probe"`), which can affect `repr()` for
  bare classes / enum members and pickling round-trips that traverse
  `__module__`. **No production code or test in this repository
  inspects `__module__`** for these symbols (verified by grep against
  the live source); no consumer relies on pickle of these types per
  project scope. Function call results, attribute reads, exception
  types, async semantics, and method signatures are unchanged.
- **Backward compatible at the documented public surface**
  (constitution §III): `AkuvoxDevice.probe_capabilities()` continues
  to work unchanged. The 5 capability symbols already in top-level
  `pylocal_akuvox.__all__` (shipped by spec 009) are unaffected.
- **Breaking at the subpath surface**: the
  `pylocal_akuvox.capability_probe` import path is removed entirely;
  every symbol formerly reachable through it (the public
  `probe_capabilities` and the 8 underscore-prefixed white-box
  helpers — `_step_1_payload`, `_classify_response`, `_ProbeOutcome`,
  `_record_user_aliases`, `_record_user_schema_keys`,
  `_record_contact_shape`, `_extract_items`, `_summarise_system_status`)
  becomes reachable only via its new owning underscore module.
  Documented in changelog Unreleased "Breaking changes" subsection
  per FR-008.
- **Aislop-clean post-split**: each new module under the 400-line
  threshold (FR-004; verified per SC-002).
- **No `--no-verify` and no `--no-gpg-sign`** (constitution §V).
  Pre-commit hooks (which include `aislop ci --staged` per the
  pre-commit config update merged in PR #143) MUST pass on every
  commit. Aislop's hook is the very gate this refactor exists to
  satisfy — it MUST run green.

**Scale/Scope**:

- **Source files in `src/pylocal_akuvox/`**: 6 file operations total —
  **1 import-rewritten** (`device.py`, 1 line — FR-001 caps any
  other change), **4 created** (`_probe_outcomes.py`,
  `_probe_classifiers.py`, `_probe_parsers.py`, `_capability_probe.py`),
  **1 deleted** (`capability_probe.py`).
- **Documentation files**: 1 — `docs/changelog.rst` (Unreleased
  "Breaking changes" subsection extended with a new bullet; lands in
  the dedicated `Docs(changelog)` commit per the three-commit split).
- **Test files**: 2 — **1 import-rewritten + docstring-fixed**
  (`tests/unit/test_capability_probe.py`; 41 import-line rewrites
  per `data-model.md` plus the line-4 module docstring per FR-013)
  and **1 extended** (`tests/unit/test_capability_module_layout.py`;
  4 new test functions added per FR-011, plus a docstring sweep to
  mention spec 010 alongside spec 009).
- **Total touched**: 9 files (the spec's `data-model.md` "Total file
  touch count" of 9). The implementation commit's `git show --stat`
  will list 8 of these (the `capability_probe.py` deletion counts as
  one); the changelog edit lives in the separate `Docs(changelog)`
  commit, and the tasks-list completion lives in the
  `Docs(tasks)` commit.
- **Net LOC change**: small. New per-module headers (SPDX × 4,
  module docstring × 4, imports × 4, `__all__` × 4) add ~80 lines of
  overhead; the deleted `capability_probe.py` removes 465 lines.
  Net: ~-100 lines of source + ~+50 lines for the four new layout
  test functions.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2.
Re-checked after the file-by-file plan below — see "Post-Design
Re-Check".*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | Each new module gets the standard SPDX header pair, a focused module docstring describing its single concern, and full type annotations preserved verbatim from the source. No code body is modified — only relocated — so cyclomatic complexity for every existing function is unchanged. ruff, mypy, interrogate stay green; the only configuration change is none (the four new modules pick up the same project-wide ruff and mypy config). C901 limits are not approached because no method body changes. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | The four new layout-assertion tests added to `tests/unit/test_capability_module_layout.py` are written **first locally** (TDD red phase against `main`: the tests fail before the split because `capability_probe.py` still exists and the four new underscore modules do not). Once the four new modules + the deletion + the import rewrites are also staged, the tests pass. The published implementation commit is green at every CI gate — the "red" state exists only in the implementer's working tree during authoring, never in a pushed commit. The four new assertions cover (a) `import pylocal_akuvox.capability_probe` raises `ModuleNotFoundError`, (b) `from pylocal_akuvox.capability_probe import probe_capabilities` raises (via `exec()`), (c) the four new underscore modules import cleanly, (d) `AkuvoxDevice.probe_capabilities` is callable. For the import-rewrite portion of the existing `tests/unit/test_capability_probe.py`, that file IS the regression net — its 1500-line behavior suite exercised the old import paths, and rewriting its imports to the new paths confirms each new module exposes the symbols its consumers depend on. **No test assertion semantics change** — only the 41 `from pylocal_akuvox.capability_probe import …` lines flip to the new owning underscore module per the symbol→module table in `data-model.md`, plus the one-line module docstring fix at line 4. Coverage MUST be maintained at 100% branch on `pylocal_akuvox` (validation gate below). |
| **III. User Experience Consistency** | PASS | The documented public surface — `AkuvoxDevice.probe_capabilities()` — is unchanged. Existing consumer code that uses the public method (README line 64; `docs/quickstart.rst` lines 35, 36, 40, 50, 77; `examples/mvp_test.py` line 2098 — all enumerated in `data-model.md`) sees zero change. The breaking change is loud and well-bounded: anyone using `pylocal_akuvox.capability_probe.X` gets `ModuleNotFoundError` (FR-002 / FR-003) and finds the migration path in the Unreleased "Breaking changes" subsection of `docs/changelog.rst` (FR-008). Error message is Python's stock `ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'` — perfectly actionable and unambiguous. |
| **IV. Performance Requirements** | PASS | Pure structural refactor. No runtime hot path is touched. Module-import cost rises modestly (4 file opens + 4 parse passes vs. 1, total source-byte volume unchanged) — consistent with the Performance Goals note above. The increase is one-time at package import, well under millisecond-scale, and not measurable against existing `import pylocal_akuvox` overhead. After import, `sys.modules` caching makes subsequent symbol access identical to today. No event-loop blocking is introduced — the relocated `async def probe_capabilities` keeps its async signature and continues to await `AkuvoxHttpClient.request` exactly as today. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | The implementation lands as three atomic commits (one logical change each — see Phase Decomposition below). Implementation commit subject uses Conventional Commits with **`!` to flag the breaking change** per FR-007: `Refactor(probe)!: Split into submodules` (39 chars; well under the 50-char gitlint default). The `!` marker is the load-bearing requirement; the exact wording is the implementer's call but MUST contain `!` before the colon and stay ≤50 characters (verified with `git log -1 --format=%s | wc -c` returning ≤51). All four new files carry SPDX headers verbatim. DCO `-s` sign-off is mandatory on every commit. Pre-commit hooks (ruff, mypy, interrogate, REUSE, **aislop ci --staged**, pytest) MUST run green on every commit; `--no-verify` and `--no-gpg-sign` are prohibited. |
| **VI. Phased Development** | PASS — single phase | This is one logical change (file split + 2-file import rewrite + layout-test extension) with no intermediate user-visible value to deliver in stages — the codebase does not compile between "delete `capability_probe.py`" and "rewrite the 2 consumers" (`device.py` and `tests/unit/test_capability_probe.py`). Splitting into multiple PRs would require either an intermediate shim (which contradicts the explicit decision in `research.md` Decision 1 to break the subpath cleanly) or a broken `main` (which violates §VI's "checkpoint where all CI tests pass"). The single-phase choice is justified explicitly in Phase Decomposition below. |

**Result**: All gates pass. **Complexity Tracking** section below is
empty — no justified violations.

## Phase Decomposition

### Decision: ONE phase, single PR, three atomic commits

**Recommendation**: One phase, one PR, **three atomic commits**:

1. **`Refactor(probe)!: Split into submodules`** — the code change
   (4 new modules created, `capability_probe.py` deleted, 2 consumer
   files rewritten, layout test extended).
2. **`Docs(changelog): Announce 010-probe split`** — the user-facing
   announcement (Unreleased "Breaking changes" subsection bullet per
   FR-008). The implementation commit and the announcement commit
   land in the same PR so the breaking change and its announcement
   ship together (item 2 in the rationale below); separating them
   into distinct commits keeps `git blame` narratives focused
   (`Refactor` commit explains "what moved where", `Docs` commit
   explains "what consumers see").
3. **`Docs(tasks): Mark 010 task list complete`** — flips
   `[ ]` checkboxes to `[x]` in `specs/010-capability-probe-split/tasks.md`
   once `/speckit.implement` has driven the implementation through.
   This is a separate logical change from both the code refactor and
   the consumer-facing announcement, hence its own commit per AGENTS.md
   atomic-commit rule. (Mirrors PR #148's three-commit landing for
   spec 009: `4fc75e8` merge → `31f7e5a Docs(tasks)` → `61b2c96
   Docs(changelog)`.)

All three commits ship in the same PR, branch
`refactor/010-capability-probe-split` (or whatever non-protected name
the implementer picks; the spec branch naming convention is
informational, not load-bearing for branch protection).

### Rationale (why not two phases)

The instructions invite a justified two-phase decomposition, but every
property of this refactor argues against it — these are the same five
reasons spec 009 enumerated in `specs/009-capabilities-module-split/plan.md`,
all of which apply verbatim here:

1. **No intermediate state compiles.** Once `capability_probe.py` is
   deleted, both of its consumers (`device.py` line 22 and
   `tests/unit/test_capability_probe.py` — 41 lines) must already be
   rewritten to the new underscore module paths or the package fails
   to import. Conversely, rewriting consumers first while
   `capability_probe.py` still exists provides no value — the
   consumers would import from the new modules that don't exist yet,
   immediately breaking. Any phasing scheme requires either
   (a) a temporary `capability_probe.py` shim that re-exports
   `probe_capabilities` from `_capability_probe` — which contradicts
   the explicit Decision 1 in `research.md` (sibling-modules-with-no-shim
   is the deliberate clean break, and the user's locked design
   decision in the spec input is "BREAKING. Delete entirely.") — or
   (b) a temporary broken `main` between phases — which violates
   constitution §VI.
2. **The breaking-change announcement and the breaking change itself
   should land together.** FR-007's `!` marker on the implementation
   commit and FR-008's changelog entry name the same event. Splitting
   them across PRs would either announce a break before it happens
   (changelog ahead of code) or perform a break before it's announced
   (code ahead of changelog) — both are confusing and neither is
   needed. The three-commit landing inside ONE PR satisfies both the
   "atomic logical change" requirement (each commit is one thing) AND
   the "announce-with-the-break" requirement (both commits ship in
   the same merge).
3. **Atomic-rename PRs are the easiest refactor PRs to review.**
   Reviewers can verify the bijection between old and new (every
   symbol migrated, every consumer rewritten, no leftover) by reading
   a single diff. A multi-phase rollout would force reviewers to track
   partial state across PRs and risk merge-skew if the second PR
   landed against a slightly different `main` than the first.
4. **No-shim policy contradicts research.md.** `research.md` Decision
   1 explicitly rejects a `capability_probe.py` shim — both because
   it would silently preserve the dropped subpath (defeating FR-002)
   and because the user's locked design decision (#1 in the spec
   input) forecloses it. Any two-phase rollout that doesn't break
   `main` requires precisely such a shim. The two requirements are
   incompatible.
5. **Aislop's gate is binary.** The whole point of issue #141 is to
   get `capability_probe.py` under the 400-line threshold. There is
   no partial credit — the file is either gone (refactor complete,
   gate passes) or it isn't.

A two-phase rollout would only make sense if (a) a downstream consumer
migration window were needed — but the only known downstream
(`tykeal/homeassistant-local-akuvox`) uses the public
`device.probe_capabilities()` method, not the module path, and is
unaffected per `data-model.md` § "README, quickstart, examples" — or
(b) the new layout were experimental — but it isn't; the split is
locked in by the spec.

### Single-phase deliverable summary

The steps below describe the **logical authoring order** the
implementer follows locally during TDD red-green-refactor; they are NOT
3 separate commits. Steps 1–6 ship in **one** atomic implementation
commit that is itself green at every CI gate. Step 7 is the
`Docs(changelog)` commit. Step 8 is the `Docs(tasks)` commit.

| Step | Deliverable | Owning commit |
|---|---|---|
| 1 | Author the four new probe-side test functions in `tests/unit/test_capability_module_layout.py` first (TDD red phase locally — they would fail on `main` because `capability_probe.py` still exists and the four new underscore modules do not; once steps 2–5 are also staged, the implementation commit as a whole is green). Update the file's module docstring to mention spec 010 alongside spec 009. | implementation commit |
| 2 | Create `src/pylocal_akuvox/_probe_outcomes.py`, `_probe_classifiers.py`, `_probe_parsers.py`, `_capability_probe.py` with relocated content + SPDX headers + module docstrings. Each new module's content is a verbatim cut from `capability_probe.py` plus per-module imports / `__all__` / docstring overhead. | implementation commit |
| 3 | Rewrite `src/pylocal_akuvox/device.py` line 22 import to point at `_capability_probe` (FR-001 caps the change to this single line). | implementation commit |
| 4 | Rewrite the 41 `from pylocal_akuvox.capability_probe import …` lines in `tests/unit/test_capability_probe.py` to the new owning underscore modules per the symbol→module table in `data-model.md` § "Test files". Apply the line-4 module docstring fix per FR-013 in the same commit (the docstring currently names the dropped subpath; per `data-model.md` the implementer SHOULD drop the module path entirely, not substitute the underscore path — the test file's purpose is behavior coverage, not module-shape pinning). | implementation commit |
| 5 | Delete `src/pylocal_akuvox/capability_probe.py` (entire 465-line file). | implementation commit |
| 6 | Run validation gates (see below); confirm 100% branch coverage maintained on `pylocal_akuvox`. Run the FR-013 docstring sweep + FR-014 inline-RST-literal hygiene check. | implementation commit (verification of the staged tree before `git commit`) |
| 7 | Add Unreleased "Breaking changes" subsection bullet to `docs/changelog.rst` (per FR-008). The new bullet sits at the same RST nesting depth (`^^^^^^^^^^^^^^^^` underline) as the existing 009 "Breaking changes" subsection — verify with `uv run --extra docs sphinx-build -W -b html docs docs/_build/html` that the rendered Unreleased section is not re-parented. | `Docs(changelog)` commit |
| 8 | Mark `specs/010-capability-probe-split/tasks.md` complete (flip `[ ]` to `[x]` for every task) once all gates have passed locally. | `Docs(tasks)` commit |

The implementation commit MUST be CI-green when pushed — pre-commit
hooks (which include `pytest` and `aislop ci --staged`) run on the
staged tree before the commit object is created, so no failing test
ever lands. The "red phase" referred to above is the local authoring
sequence (write tests → watch them fail against `main` → implement →
watch them pass on the staged tree), not a state of the published
commit.

The implementation commit subject MUST contain `!` per FR-007. The
recommended form (per `research.md` Decision 10) is
`Refactor(probe)!: Split into submodules` (39 chars; under the 50-char
gitlint default). The implementer MUST verify with
`git log -1 --format=%s | wc -c` (returns 40 for the suggested
subject — 39 chars + newline).

The `Docs(changelog)` commit subject is
`Docs(changelog): Announce 010-probe split` (41 chars). The
`Docs(tasks)` commit subject is `Docs(tasks): Mark 010 task list complete`
(40 chars).

## Project Structure

### Documentation (this feature)

```text
specs/010-capability-probe-split/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec (input)
├── research.md          # Phase 0 output — 10 decisions
├── data-model.md        # Module layout + 2-file affected-file list
├── quickstart.md        # 14-step verification recipe
├── contracts/
│   ├── probe-outcomes.md      # _probe_outcomes.py contract
│   ├── probe-classifiers.md   # _probe_classifiers.py contract
│   ├── probe-parsers.md       # _probe_parsers.py contract
│   └── capability-probe.md    # _capability_probe.py contract (orchestrator)
└── tasks.md             # NOT generated by this command — produced by /speckit.tasks
```

### Source Code (repository root)

Pre-feature (current state, abbreviated; `capabilities.py` is already
gone per spec 009):

```text
src/pylocal_akuvox/
├── __init__.py
├── _capability_types.py
├── _capability_profile.py
├── _capability_matching.py
├── _capability_defaults.py
├── capability_probe.py          # 465 lines — flagged by aislop (the file this spec eliminates)
├── capability_matrix.py
├── capability_adapters.py
├── device.py                    # 1 import from capability_probe (line 22)
└── …
```

Post-feature (only changed area shown; `capability_probe.py` is gone):

```text
src/pylocal_akuvox/
├── _probe_outcomes.py           # NEW — _ProbeOutcome enum + 3 marker constants (~50 lines)
├── _probe_classifiers.py        # NEW — _extract_message, _summarise_system_status, _classify_response, _outcome_to_status (~140 lines)
├── _probe_parsers.py            # NEW — _step_1_payload, _extract_items, _record_user_aliases, _record_user_schema_keys, _record_contact_shape (~175 lines)
├── _capability_probe.py         # NEW — 7 step-path constants, _LATER_STEPS, async probe_capabilities (~175 lines)
├── capability_probe.py          # DELETED
└── device.py                    # 1 import rewritten (line 22 → _capability_probe)
```

**Structure Decision**: Four sibling underscore-prefixed modules at the
package root, **with no `capability_probe/` package and no
`capability_probe.py` shim**. Locked in `research.md` Decision 1 —
sibling modules give a clean `ModuleNotFoundError` on the dropped
subpath, which neither a regular package (with `__init__.py`) nor a
PEP 420 namespace package would deliver.

## File-by-File Plan

### New module 1: `src/pylocal_akuvox/_probe_outcomes.py`

**Owns** (per `data-model.md` § "Module Layout Table" and
`contracts/probe-outcomes.md`):

- `_ProbeOutcome` (enum.Enum, str values) — five-valued internal
  classification
- `_NO_HANDLER_MARKERS` (constant, `tuple[str, ...]`) — error-message
  tokens identifying "no handler" responses
- `_API_UNSUPPORTED_MARKER` (constant, `str`) — single token
  identifying API-unsupported responses
- `_ACTION_UNSUPPORTED_MARKERS` (constant, `tuple[str, ...]`) —
  tokens identifying action-unsupported responses

**Public re-exports** (top-level): **none**. Per spec FR-005 and
`data-model.md` § "Module Layout Table", no symbol from this module
is added to top-level `pylocal_akuvox.__all__`.

**Module-top imports**:

```python
from __future__ import annotations

import enum
```

**`__all__`**:

```python
__all__ = [
    "_ACTION_UNSUPPORTED_MARKERS",
    "_API_UNSUPPORTED_MARKER",
    "_NO_HANDLER_MARKERS",
    "_ProbeOutcome",
]
```

**Sibling-module imports**: none. This is the leaf of the probe-side
dependency graph (per `data-model.md` § "`_probe_outcomes.py`" and
`research.md` Decision 1).

**Estimated size**: ~50 lines (per `research.md` Decision 4
arithmetic).

---

### New module 2: `src/pylocal_akuvox/_probe_classifiers.py`

**Owns**:

- `_extract_message` (function) — pure JSON-body → message-string
  helper
- `_summarise_system_status` (function) — pure
  `(status, body)` → optional summary helper used by step 2
- `_classify_response` (function) — pure
  `(status, body) → _ProbeOutcome` mapping
- `_outcome_to_status` (function) — pure
  `_ProbeOutcome → CapabilityStatus` mapping

**Public re-exports** (top-level): **none**.

**Module-top imports**:

```python
from __future__ import annotations

import json

from pylocal_akuvox._capability_types import CapabilityStatus
from pylocal_akuvox._probe_outcomes import (
    _ACTION_UNSUPPORTED_MARKERS,
    _API_UNSUPPORTED_MARKER,
    _NO_HANDLER_MARKERS,
    _ProbeOutcome,
)
```

**`__all__`**:

```python
__all__ = [
    "_classify_response",
    "_extract_message",
    "_outcome_to_status",
    "_summarise_system_status",
]
```

**Sibling-module imports**:

- `_probe_outcomes` (runtime, top-level) — for `_ProbeOutcome` and the
  three message-marker constants
- `pylocal_akuvox._capability_types` (runtime, top-level) — for
  `CapabilityStatus` (return type of `_outcome_to_status`)

**Cycle risk**: none. `_probe_outcomes` imports nothing first-party;
`_capability_types` is a pre-existing leaf module that does not import
from any probe module (verified at the live source). `_probe_classifiers`
does NOT import from `_probe_parsers` per `data-model.md` § "Cross-Module
Dependencies" and `research.md` Decision 8.

**Estimated size**: ~140 lines.

---

### New module 3: `src/pylocal_akuvox/_probe_parsers.py`

**Owns**:

- `_step_1_payload` (function) — extracts the
  `/api/system/info` payload from the raw step-1 body; raises
  `AkuvoxParseError` on unparsable bodies
- `_extract_items` (function) — pulls a list payload from a step-N
  body
- `_record_user_aliases` (function, side-effecting) — mutates a
  `dict[str, FieldAliases]` accumulator with discovered alias schemas
- `_record_user_schema_keys` (function, side-effecting) — mutates a
  `set[str]` accumulator with discovered schema keys
- `_record_contact_shape` (function, side-effecting) — mutates a
  `dict[Capability, SchemaShape]` accumulator with discovered contact
  shapes

**Public re-exports** (top-level): **none**.

**Module-top imports**:

```python
from __future__ import annotations

import json
from typing import Any

from pylocal_akuvox._capability_profile import FieldAliases
from pylocal_akuvox._capability_types import SchemaShape
from pylocal_akuvox.exceptions import AkuvoxParseError
```

**`__all__`**:

```python
__all__ = [
    "_extract_items",
    "_record_contact_shape",
    "_record_user_aliases",
    "_record_user_schema_keys",
    "_step_1_payload",
]
```

**Sibling-module imports**:

- `pylocal_akuvox._capability_profile` (runtime, top-level) — for
  `FieldAliases` (constructed inside `_record_user_aliases`)
- `pylocal_akuvox._capability_types` (runtime, top-level) — for
  `SchemaShape` (used inside `_record_contact_shape`)
- `pylocal_akuvox.exceptions` (runtime, top-level) — for
  `AkuvoxParseError` (raised by `_step_1_payload`)

**Cycle risk**: none. `_capability_profile` and `_capability_types` are
upstream of any probe module (per `data-model.md` § "Cross-Module
Dependencies"). `_probe_parsers` does NOT import from
`_probe_classifiers` per Decision 8.

**Estimated size**: ~175 lines.

---

### New module 4: `src/pylocal_akuvox/_capability_probe.py`

**Owns**:

- `_PROBE_STEP_3_PATH` … `_PROBE_STEP_9_PATH` (seven `str` constants)
- `_LATER_STEPS` (constant, ordered tuple of `(path, capability)` —
  the iteration order for steps 3–9)
- `probe_capabilities` (async function) — the orchestration driver

**Public re-exports** (top-level): **none**. The consumer-facing handle
is the `AkuvoxDevice.probe_capabilities()` method, which `device.py`
defines and which delegates to `_capability_probe.probe_capabilities()`.

**Module-top imports**:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._capability_profile import (
    DeviceCapabilities,
    FieldAliases,
)
from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox._probe_classifiers import (
    _classify_response,
    _outcome_to_status,
    _summarise_system_status,
)
from pylocal_akuvox._probe_outcomes import _ProbeOutcome
from pylocal_akuvox._probe_parsers import (
    _extract_items,
    _record_contact_shape,
    _record_user_aliases,
    _record_user_schema_keys,
    _step_1_payload,
)
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxParseError,
    AkuvoxRequestError,
)
from pylocal_akuvox.models import DeviceInfo

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient
```

**`__all__`**:

```python
__all__ = ["probe_capabilities"]
```

(The seven step-path constants and `_LATER_STEPS` are not re-exported;
they are orchestration internals consumed only inside this module.
Underscore-prefixed names are excluded from `__all__` — consistent with
the project's existing style.)

**Sibling-module imports**:

- `_probe_outcomes` (runtime, top-level) — for `_ProbeOutcome` (used
  in the step-3 / step-4 side-effect guard:
  `if outcome is _ProbeOutcome.SUPPORTED`)
- `_probe_classifiers` (runtime, top-level) — for `_classify_response`,
  `_outcome_to_status`, `_summarise_system_status`
- `_probe_parsers` (runtime, top-level) — for `_step_1_payload`,
  `_extract_items`, `_record_user_aliases`,
  `_record_user_schema_keys`, `_record_contact_shape`
- `pylocal_akuvox._capability_profile` (runtime, top-level) — for
  `DeviceCapabilities` (return type) and `FieldAliases` (accumulator
  type)
- `pylocal_akuvox._capability_types` (runtime, top-level) — for
  `Capability`, `CapabilityStatus`, `SchemaShape`
- `pylocal_akuvox.exceptions` (runtime, top-level) — for the four
  raised exception types
- `pylocal_akuvox.models` (runtime, top-level) — for `DeviceInfo`
  (used in `DeviceInfo.from_api_response(data)` on step 1)
- `pylocal_akuvox._http.AkuvoxHttpClient` (TYPE_CHECKING-only) —
  matches the live source today

**Cycle risk**: none. The probe-side dependency graph is a strict DAG:
`_probe_outcomes` → `_probe_classifiers` and `_probe_parsers` (siblings,
neither imports the other) → `_capability_probe` (depends on all three
plus the pre-existing `_capability_profile` / `_capability_types` /
`exceptions` / `models`). `device.py` depends on `_capability_probe`
only — no module imports back into `device.py`. After the split, the
orchestration module does NOT need direct `json` or `typing.Any`
imports — both are used only by the helpers, which now live in
`_probe_parsers.py` / `_probe_classifiers.py` (per `data-model.md`
§ "`_capability_probe.py`").

**Estimated size**: ~175 lines.

---

### Cross-module dependency graph (post-split)

```text
                _probe_outcomes.py             (leaf — depends on stdlib only)
                       ▲     ▲
                       │     │
                       │     │
        _probe_classifiers.py    _probe_parsers.py
                       ▲     ▲
                       │     │
                       │     │
                _capability_probe.py            (depends on all three above
                       ▲                         + _capability_profile /
                       │                         _capability_types /
                       │                         exceptions / models)
                       │
                  device.py                     (depends on _capability_probe
                                                 — only consumer in src/)
```

The graph is a DAG at module-import time. No back-edges, no lazy
imports needed (unlike spec 009 where `_capability_matching` ↔
`capability_matrix` required a function-body lazy import).
`_probe_classifiers` and `_probe_parsers` are siblings at the same
dependency level — neither imports the other (per `data-model.md`
§ "Cross-Module Dependencies" and `research.md` Decision 8).

## Import-Rewrite Plan

This refactor rewrites every `from pylocal_akuvox.capability_probe
import …` statement in **2 files** (per `data-model.md` § "Affected-File
List for Downstream Import Rewrites"). The mapping is mechanical and
follows the symbol→module table in `data-model.md` § "Module Layout
Table":

| Symbol | New owning module |
|---|---|
| `_ProbeOutcome` | `pylocal_akuvox._probe_outcomes` |
| `_NO_HANDLER_MARKERS` | `pylocal_akuvox._probe_outcomes` |
| `_API_UNSUPPORTED_MARKER` | `pylocal_akuvox._probe_outcomes` |
| `_ACTION_UNSUPPORTED_MARKERS` | `pylocal_akuvox._probe_outcomes` |
| `_extract_message` | `pylocal_akuvox._probe_classifiers` |
| `_summarise_system_status` | `pylocal_akuvox._probe_classifiers` |
| `_classify_response` | `pylocal_akuvox._probe_classifiers` |
| `_outcome_to_status` | `pylocal_akuvox._probe_classifiers` |
| `_step_1_payload` | `pylocal_akuvox._probe_parsers` |
| `_extract_items` | `pylocal_akuvox._probe_parsers` |
| `_record_user_aliases` | `pylocal_akuvox._probe_parsers` |
| `_record_user_schema_keys` | `pylocal_akuvox._probe_parsers` |
| `_record_contact_shape` | `pylocal_akuvox._probe_parsers` |
| `probe_capabilities` | `pylocal_akuvox._capability_probe` |

Where a single `from pylocal_akuvox.capability_probe import (A, B)`
block imports symbols that now live in different underscore modules,
the block splits into one statement per new module, ordered
alphabetically by module name (matches existing project ruff/isort
style). The four `_classify_response, _ProbeOutcome` co-imports in
`tests/unit/test_capability_probe.py` (lines 739, 748, 756, 766) each
split into two lines: one `from pylocal_akuvox._probe_classifiers
import _classify_response` and one
`from pylocal_akuvox._probe_outcomes import _ProbeOutcome`.

### Group A: Production source — package internals

| File | Sites | Rewrite strategy |
|---|---|---|
| `src/pylocal_akuvox/device.py` | 1 (top-level at line 22) | Rewrite single line. **Before**: `from pylocal_akuvox.capability_probe import probe_capabilities as _probe_capabilities`. **After**: `from pylocal_akuvox._capability_probe import probe_capabilities as _probe_capabilities`. Per FR-001, **no other change to `device.py` is permitted under this spec.** |

### Group B: Tests

`tests/unit/test_capability_probe.py` is the only test file requiring
import rewrites. **41 import-line rewrites** total: 1 static top-of-file
at line 29 plus 40 in-test deferred imports. Grouped by the new owning
underscore module (per `data-model.md` § "Test files (`tests/unit/`)"):

| Target module | Sites | Lines (from `data-model.md`) |
|---|---|---|
| `_capability_probe` (for `probe_capabilities` re-aliased as `_probe_helper`) | 1 | 29 |
| `_probe_classifiers` (for `_classify_response`, `_summarise_system_status`) | 10 | 739, 748, 756, 766 (each splits to a 2nd line for `_ProbeOutcome` — see below); 994, 1008, 1016, 1023, 1036, 1048 |
| `_probe_outcomes` (for `_ProbeOutcome` — co-imported on lines 739/748/756/766) | 4 | 739, 748, 756, 766 (the 2nd `from`-line each) |
| `_probe_parsers` (for `_step_1_payload`, `_extract_items`, `_record_user_aliases`, `_record_user_schema_keys`, `_record_contact_shape`) | 30 | 674, 773, 782, 791, 800, 809, 820, 829, 838, 847, 866, 875, 884, 893, 900, 907, 914, 921, 929, 940, 950, 965, 977, 1122, 1142, 1152, 1161, 1170, 1179, 1188 |

**Subtotal arithmetic**: 1 (`_capability_probe`) + 10 (`_probe_classifiers`)
+ 4 (`_probe_outcomes` — the second `from`-lines on the four co-import
sites) + 30 (`_probe_parsers`) = **45** new import statements emitted
from 41 source lines (because the four 2-symbol co-imports split into
two lines each, adding 4 net new lines). Net file-line growth:
**+4 lines** in `tests/unit/test_capability_probe.py`. Test assertion
bodies do not change.

**Module docstring fix** (per FR-013 and `data-model.md` § "Test files"):
the test file's line 4 currently reads
``"""Tests for the capability probe in ``pylocal_akuvox.capability_probe``."""``.
Post-rewrite, the implementer SHOULD drop the module path entirely
(e.g., ``"""Tests for the capability probe (capability profile runtime side)."""``)
rather than substitute the underscore path — the test file's purpose
is behavior coverage, not module-shape pinning, so the module path
adds nothing. This single docstring change ships in the same
implementation commit as the import rewrites.

### Group C: Documentation, Sphinx extension, README, examples

**No update needed.** Per `data-model.md` § "Documentation extensions"
and § "README, quickstart, examples", confirmed by the spec-time sweep
documented in `research.md` Decision 7:

| File | Status |
|---|---|
| `docs/_ext/capability_matrix.py` | No update — does not import or reference `capability_probe`. |
| `docs/api/*.rst` | No update — none of the API pages reference `pylocal_akuvox.capability_probe`. The probe is documented via `AkuvoxDevice.probe_capabilities` automethod on `device.rst`, which resolves through `AkuvoxDevice` and is unaffected. |
| `README.md` | No update — line 64 uses `await device.probe_capabilities()` (the public method form). |
| `docs/quickstart.rst` | No update — lines 35, 36, 40, 50, 77 all use the public method form. |
| `examples/mvp_test.py` | No update — line 2098 uses the public method form. |

Per FR-013, the implementation commit still runs a final
`grep -rn "pylocal_akuvox\.capability_probe"
src/ tests/ docs/ README.md examples/` to catch any docstring
references inside the four new modules that may have been mechanically
copy-pasted from the old module's self-referential docstring. Findings
are addressed in the same commit. The expected post-sweep state is
zero matches outside `docs/changelog.rst` (the migration-message hit
in the new "Breaking changes" subsection is allowed and expected) and
`specs/`.

## Subpath-Removal Verification Plan

The existing `tests/unit/test_capability_module_layout.py` (added by
spec 009; currently 89 lines with 5 test functions) is **extended**
with four new probe-side test functions per FR-011, rather than
creating a parallel `test_probe_module_layout.py`. The file's module
docstring is updated to mention spec 010 alongside spec 009.

### New assertion 1 — `test_capability_probe_subpath_is_gone`

```python
def test_capability_probe_subpath_is_gone() -> None:
    """``import pylocal_akuvox.capability_probe`` must raise ``ModuleNotFoundError``."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pylocal_akuvox.capability_probe")
```

This is the canonical assertion of the breaking change for the
`import` form (FR-002 / SC-003). Uses bare `ModuleNotFoundError`
(NOT the `(ModuleNotFoundError, ImportError)` tuple) per the
carry-forward retro from 009 (item 4) and the spec FR-011 mandate.

### New assertion 2 — `test_capability_probe_subpath_from_import_is_gone`

```python
def test_capability_probe_subpath_from_import_is_gone() -> None:
    """``from pylocal_akuvox.capability_probe import probe_capabilities`` must raise.

    Uses ``exec()`` because a static ``from`` import at module top
    level would be evaluated at pytest-collection time, outside the
    ``pytest.raises`` context, and would itself raise
    ``ModuleNotFoundError`` post-split, preventing the test module
    from loading. ``ModuleNotFoundError`` is required specifically
    (not the wider ``ImportError`` superclass) so a hypothetical
    partial-shim regression — e.g. a re-resurrected
    ``pylocal_akuvox.capability_probe`` module that loads but no
    longer exports ``probe_capabilities`` — would raise the bare
    ``ImportError`` and fail this test loudly rather than slip
    through.
    """
    with pytest.raises(ModuleNotFoundError):
        exec("from pylocal_akuvox.capability_probe import probe_capabilities")  # noqa: S102
```

Covers FR-003 (the `from`-import form). The wording mirrors the
existing 009 `test_capabilities_subpath_from_import_is_gone` docstring
verbatim except for the substituted module name.

### New assertion 3 — `test_probe_underscore_modules_importable`

```python
def test_probe_underscore_modules_importable() -> None:
    """Each of the four new probe-side underscore modules must import cleanly."""
    for name in (
        "pylocal_akuvox._probe_outcomes",
        "pylocal_akuvox._probe_classifiers",
        "pylocal_akuvox._probe_parsers",
        "pylocal_akuvox._capability_probe",
    ):
        importlib.import_module(name)
```

Covers FR-005 (internal symbols are importable from their respective
underscore modules) at the module level. Symbol-level imports are
covered by the existing `tests/unit/test_capability_probe.py` after
its own import rewrites (every helper is imported in at least one
test, so the test suite implicitly verifies symbol-level
importability).

### New assertion 4 — `test_probe_capabilities_reachable_via_device`

```python
def test_probe_capabilities_reachable_via_device() -> None:
    """``AkuvoxDevice.probe_capabilities`` must be callable post-split."""
    import pylocal_akuvox

    assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities)
```

Covers FR-001 + the spec's User Story 1 acceptance scenarios.
Behavior coverage (the byte-equal-DeviceCapabilities assertion, the
9-call sequence assertion, the step-1 401 → `AkuvoxAuthenticationError`
assertion) stays in `tests/unit/test_capability_probe.py` — this is a
**presence pin only**. The spec's per-scenario behavior assertions are
already exercised by the existing 1500-line test file; replicating
them in the layout-test file would be duplicate coverage and would
slow the layout-test's purpose (fast structural pinning).

A runtime smoke test against a mocked transport (i.e. instantiating
`AkuvoxDevice`, mocking `AkuvoxHttpClient.request`, and awaiting
`device.probe_capabilities()`) is **out of scope for the
layout-assertion file** and is delegated to the existing
`tests/unit/test_capability_probe.py` suite, which already contains
end-to-end mocked-transport coverage of the public method (see the
test file's "happy path", "401 abort", and "transport-error"
sections). The layout-assertion file deliberately stays at the
module-shape-pinning level so it remains fast and focused.

### Module docstring update

The existing `tests/unit/test_capability_module_layout.py` module
docstring (line 4) currently begins:

```text
"""Layout assertions for spec ``009-capabilities-module-split``.
```

Post-extension, it MUST mention spec 010 alongside spec 009. The
implementer SHOULD adopt:

```text
"""Layout assertions for specs ``009-capabilities-module-split`` and
``010-capability-probe-split``.
```

…and add a new bullet to the docstring's existing four-bullet list
calling out the probe-side scope (paraphrasing: "the legacy
``pylocal_akuvox.capability_probe`` subpath must be gone, the four
new probe-side underscore modules must be importable, and
``AkuvoxDevice.probe_capabilities`` must remain callable").

This satisfies `research.md` Decision 3's "documents that the file's
scope has expanded" intent.

## Validation Gates

Every gate below MUST pass green on the implementation commit (NOT on a
subsequent fix-up commit) before the PR is opened. The
`Docs(changelog)` and `Docs(tasks)` commits do not change source
behavior, so the gates are repeated on them but expected to remain
green trivially.

| Gate | Command | Pass criterion |
|---|---|---|
| **Unit tests** | `uv run pytest tests/ -x -q` | exit 0; all tests pass; the four new probe-side tests in `test_capability_module_layout.py` are picked up by `tests/unit/` discovery automatically (no conftest changes). |
| **Lint (source)** | `uv run ruff check src/ tests/` | exit 0; zero warnings. |
| **Type check** | `uv run mypy src/` | exit 0; zero errors (mypy strict per project config). |
| **Pre-commit (full)** | `git add -A && pre-commit run --all-files` | exit 0; includes ruff, mypy, interrogate, REUSE, **and `aislop ci --staged`** (the gate that motivates this whole spec — must report no `complexity/file-too-large` on any of the 4 new modules). The leading `git add -A` is required: the project's aislop hook is configured with `pass_filenames: false` and operates on the staged diff, so running `pre-commit run --all-files` against an unstaged tree would scan an empty staged set and report a false-green. The dedicated **Aislop new-module size** gate below is the belt-and-suspenders explicit check that does NOT depend on staging. |
| **Doc build** | `cd docs && uv run sphinx-build -W -b html . _build/html` | exit 0; treats warnings as errors (the `-W` flag); confirms the rewritten `device.py` import resolves at autodoc time and that the new "Breaking changes" changelog bullet's RST nesting is correct (does not re-parent the existing 009 entry — see FR-008 carry-forward retro from 009 item 5). |
| **Branch coverage** | `uv run pytest --cov=pylocal_akuvox --cov-branch --cov-report=term-missing tests/` | 100% branch coverage maintained on `pylocal_akuvox` (current baseline; SC implicitly maintained by spec FR-006). No new uncovered branches introduced — every relocated function is exercised by the same test that covered it pre-split, and the four new layout-assertion tests cover the new module-import surface. |
| **Aislop new-module size** | `uv run aislop scan --include 'src/pylocal_akuvox/_probe_outcomes.py,src/pylocal_akuvox/_probe_classifiers.py,src/pylocal_akuvox/_probe_parsers.py,src/pylocal_akuvox/_capability_probe.py'` | No `complexity/file-too-large` warnings on any of the 4 new modules (SC-002 explicit verification). Each must be under 400 lines. **Note** (carry-forward retro from 009 item 3): `aislop scan <files...>` rejects positional file arguments — the `--include 'a,b,c,d'` form is required. |
| **Aislop project-wide** | `uv run aislop scan` | `capability_probe.py` no longer appears in the `complexity/file-too-large` list (it has been deleted). `device.py` is still flagged — that is issue #142, out of scope for this spec. `capabilities.py` is already gone (shipped under spec 009 / PR #148). |
| **Subpath removal smoke test (import form)** | `uv run python -c "import pylocal_akuvox.capability_probe"` | Exits non-zero with `ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'`. SC-003. |
| **Subpath removal smoke test (from form)** | `uv run python -c "from pylocal_akuvox.capability_probe import probe_capabilities"` | Exits non-zero with `ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'`. SC-003. |
| **Public probe smoke test** | `uv run python -c "import pylocal_akuvox; assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities); print('ok')"` | Exits 0; prints `ok`. SC-004. |
| **Internal underscore-module smoke tests** | The four `uv run python -c "from pylocal_akuvox._probe_… import …; print('ok')"` invocations from `quickstart.md` Step 6 | All four print `ok` and exit 0. Belt-and-suspenders for FR-005 at the symbol level, complementing the layout test's module-level assertion. |
| **Original file gone** | `test ! -f src/pylocal_akuvox/capability_probe.py && echo deleted` | Prints `deleted` and exits 0. SC-008. |
| **Commit subject `!` and length** | `git log -1 --format=%s` and `git log -1 --format=%s \| wc -c` on the implementation commit | Subject contains `!` before the colon; `wc -c` returns ≤51 (50 chars + newline). The recommended subject `Refactor(probe)!: Split into submodules` returns 40. SC-006 / FR-007. |
| **Changelog entry** | `grep -B 2 -A 5 "capability_probe" docs/changelog.rst` | Output names the dropped subpath, the migration path (use `AkuvoxDevice.probe_capabilities()`), and the absence of a renamed/removed public symbol. The hit MUST be inside the Unreleased "Breaking changes" subsection at the same RST nesting depth as the existing 009 entry. SC-005 / FR-008. |
| **FR-013 docstring sweep** | `grep -rn "pylocal_akuvox\.capability_probe" src/ tests/ docs/ README.md examples/` | Zero hits outside `docs/changelog.rst` (the migration-message bullet is allowed) and `specs/`. Catches stale self-references inside the four new modules' docstrings. |
| **FR-014 inline RST literal hygiene** | Visual inspection of any new-module docstring containing multi-line examples (renders in `docs/_build/html/`) | Multi-line literal content uses indented `::` literal blocks, never inline ``` `` `` ``` cross-line literals. Sphinx-W does NOT catch the inline-with-newline form. |

The full set is reproducible from `quickstart.md` Steps 1–14, which the
implementer follows verbatim during PR self-review.

## Post-Design Re-Check

After authoring the file-by-file plan, import-rewrite plan, and
subpath-removal verification plan above:

| Principle | Status | Re-check Notes |
|-----------|--------|----------------|
| **I. Code Quality** | PASS | Each new module's imports are minimal and ordered (stdlib → first-party). No function body is modified, so cyclomatic complexity is unchanged on every preserved entity. The four new modules add ~80 lines of header overhead total (SPDX × 4, docstring × 4, imports × 4, `__all__` × 4) — comfortably below the 400-line threshold for each (largest projected: ~175 lines). ruff / mypy / interrogate pass because the rewritten imports follow project style and the relocated docstrings remain intact. |
| **II. TDD** | PASS | The four new layout-assertion tests are written first **locally** (TDD red phase against `main` only — they fail before any split happens because `capability_probe.py` still exists and the four new underscore modules do not). Once the four new modules + the deletion + the import rewrites are also staged, the tests pass; the published commit is green at every CI gate. This satisfies the "failing test first" constitution requirement without ever pushing a red commit. The existing 1500-line `test_capability_probe.py` exercises the new underscore modules' surface (after its imports are rewritten); no test assertion semantics change, so the regression net stays valid. Branch coverage is preserved at 100%. |
| **III. UX** | PASS | The documented public method (`AkuvoxDevice.probe_capabilities`) remains at its documented call site with identical signature and behavior. The breaking change (subpath removal) is loud (`ModuleNotFoundError`), well-bounded, and announced in the Unreleased "Breaking changes" subsection of `docs/changelog.rst` with the documented migration path. |
| **IV. Performance** | PASS | The dependency graph (post-split) is a strict DAG at module-import time — no back-edges and no lazy imports needed (unlike spec 009 where `_capability_matching` ↔ `capability_matrix` required a function-body lazy import). No new I/O or async boundaries are introduced. The relocated `async def probe_capabilities` continues to await `AkuvoxHttpClient.request` exactly as today. |
| **V. Atomic Commits** | PASS | Three atomic commits (`Refactor(probe)!`, `Docs(changelog)`, `Docs(tasks)`) — one logical change each, all in the same PR, all with DCO `-s` and dual co-author trailers (Claude + GitHub Copilot). SPDX headers on the four new files. Conventional Commits with capitalized type and `!` for the breaking change on the implementation commit (FR-007). Pre-commit hooks (including aislop) MUST run green; `--no-verify` and `--no-gpg-sign` are prohibited. |
| **VI. Phased Development** | PASS | Single phase, one PR. Justified above against five reasons — no intermediate compilable state exists, the changelog and code MUST land together, the atomic-rename property is the whole reason the refactor is reviewable, no-shim policy is locked in research.md, and aislop's gate is binary. |

**Result**: All gates pass post-design. **Complexity Tracking** below
remains empty.

## Complexity Tracking

> No constitutional violations to justify — left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none)    | (none)     | (none)                               |
