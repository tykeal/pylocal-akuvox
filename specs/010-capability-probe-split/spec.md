<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: Refactor capability_probe.py Under Aislop Size Limit

**Feature Branch**: `010-capability-probe-split`
**Created**: 2026-06-16
**Status**: Draft
**Input**: Issue #141 — `aislop scan` flags
`src/pylocal_akuvox/capability_probe.py` (465 lines) with
`complexity/file-too-large` against the project's 400-line threshold.
This specification describes a pure-refactor split into focused sibling
underscore-prefixed modules with no behavioral changes.

## Background and Evidence

`src/pylocal_akuvox/capability_probe.py` currently weighs 465 lines and
contains four orthogonal concerns the issue explicitly suggests
extracting (issue #141 §"Suggested approach": "extract pure response
classifiers and schema-shape parsers first, then keep
`probe_capabilities()` as the orchestration layer"):

1. **Outcome enumeration + classification markers** — `_ProbeOutcome`
   enum and the three marker tuples/strings (`_NO_HANDLER_MARKERS`,
   `_API_UNSUPPORTED_MARKER`, `_ACTION_UNSUPPORTED_MARKERS`)
   (~25 lines)
2. **Pure response classifiers** — `_extract_message`,
   `_summarise_system_status`, `_classify_response`,
   `_outcome_to_status` (~110 lines)
3. **Step-1 payload + item extraction + schema/alias recorders** —
   `_step_1_payload`, `_extract_items`, `_record_user_aliases`,
   `_record_user_schema_keys`, `_record_contact_shape` (~150 lines)
4. **Orchestration** — the seven step-path constants, the `_LATER_STEPS`
   tuple, and the `async def probe_capabilities(...)` driver
   (~135 lines)

The aislop `complexity/file-too-large` threshold is 400 lines.
Splitting along these natural concern boundaries yields four files,
each well under the threshold, with no change to runtime behavior,
function signatures, async semantics, ordering, idempotence, timeout
handling, or observed capability outcomes.

This is a **BREAKING** refactor: the
`pylocal_akuvox.capability_probe` import subpath is removed entirely.
The only consumer-facing entry point — `AkuvoxDevice.probe_capabilities()`
— continues to work unchanged. Direct module imports
(`from pylocal_akuvox.capability_probe import probe_capabilities`,
`import pylocal_akuvox.capability_probe`) raise `ModuleNotFoundError`
post-refactor.

This refactor mirrors the structural pattern of spec
`009-capabilities-module-split` (PR #145 spec / PR #148 implementation
merged at SHA `4fc75e8`): four sibling underscore-prefixed modules at
the same package level, with the legacy non-underscore subpath
deliberately removed.

## User Scenarios & Testing

### User Story 1 — `device.probe_capabilities()` continues to work (Priority: P1)

A library consumer using the public surface — calling
`await device.probe_capabilities()` on an `AkuvoxDevice` — sees
identical behavior across the refactor: same 9-call sequence, same
classification rules, same observed `DeviceCapabilities` shape,
same exception types and timing. Their integration code is unchanged.

**Why this priority**: `AkuvoxDevice.probe_capabilities()` is the only
consumer-facing handle for the probe (the README "Capabilities"
section, `docs/quickstart.rst`, and `examples/mvp_test.py` all reach
it through `device`). Breaking its behavior would be an unacceptable
regression. Every other story depends on this guarantee holding.

**Independent Test**: Run the full test suite (`uv run pytest tests/`)
and confirm all tests pass, with particular attention to
`tests/unit/test_capability_probe.py` (which exercises both the public
`AkuvoxDevice.probe_capabilities()` path and the private helpers via
white-box imports). Per-test imports of underscore-prefixed helpers
will be rewritten to point at the new modules, but no test assertion
changes.

**Acceptance Scenarios**:

1. **Given** a consumer awaiting `device.probe_capabilities()`,
   **When** the call executes post-split, **Then** the returned
   `DeviceCapabilities` is byte-equal to what the pre-split orchestrator
   produced for the same recorded HTTP responses (preserves the
   idempotence guarantee documented in
   `specs/008-capability-matrix/contracts/probe-api.md` § "Idempotence",
   referenced as SC-002 of that contract — note that this spec's
   own SC-002 is the unrelated aislop-size criterion).
2. **Given** a consumer awaiting `device.probe_capabilities()` against
   a device that returns HTTP 401 on `/api/system/info`, **When** the
   call executes post-split, **Then** it raises `AkuvoxAuthenticationError`
   after exactly one HTTP call (preserves the step-1 abort contract).
3. **Given** the full test suite, **When** `uv run pytest tests/` is
   run post-split, **Then** all tests pass.

---

### User Story 2 — Old subpath gives a clear error (Priority: P1)

A consumer or maintainer attempting the old import path
`from pylocal_akuvox.capability_probe import probe_capabilities` (or
`import pylocal_akuvox.capability_probe`) gets a clear
`ModuleNotFoundError` and finds the migration path in the changelog
"Breaking changes" subsection: use the public
`AkuvoxDevice.probe_capabilities()` method.

**Why this priority**: A silent failure (empty module, partial import)
would be worse than a loud error. The breaking change must be
immediately obvious so consumers can find the documented migration
path.

**Independent Test**: A new test (or an extension of the existing
`tests/unit/test_capability_module_layout.py` — see FR-011 below)
asserts that both `import pylocal_akuvox.capability_probe` and
`from pylocal_akuvox.capability_probe import probe_capabilities`
raise `ModuleNotFoundError` specifically (not the wider `ImportError`
superclass).

**Acceptance Scenarios**:

1. **Given** a consumer attempting `import pylocal_akuvox.capability_probe`,
   **When** the import executes post-split, **Then** Python raises
   `ModuleNotFoundError`.
2. **Given** a consumer attempting
   `from pylocal_akuvox.capability_probe import probe_capabilities`,
   **When** the import executes post-split, **Then** Python raises
   `ModuleNotFoundError`.
3. **Given** a consumer encountering the error, **When** they consult
   the changelog, **Then** the Unreleased "Breaking changes"
   subsection names the dropped subpath and states the migration:
   call `AkuvoxDevice.probe_capabilities()` (the documented public
   method).

---

### User Story 3 — Maintainer finds focused, readable modules (Priority: P2)

A maintainer extending the probe (e.g., adding a step, adjusting a
classifier, fixing a parser) opens the underscore-prefixed module
relevant to their change and finds it focused on a single concern,
under the aislop threshold, and faster to read and navigate than the
original monolithic file.

**Why this priority**: Developer experience and long-term
maintainability motivate the split, but the library's external
behavior is unchanged. P2 because it primarily benefits internal
contributors.

**Independent Test**:
`uv run aislop scan --include 'src/pylocal_akuvox/_probe_outcomes.py,src/pylocal_akuvox/_probe_classifiers.py,src/pylocal_akuvox/_probe_parsers.py,src/pylocal_akuvox/_capability_probe.py'`
reports no `complexity/file-too-large` warnings for any of the four
new modules.

**Acceptance Scenarios**:

1. **Given** each of the four new underscore modules, **When**
   `aislop scan` is run, **Then** none is flagged as exceeding the
   400-line threshold.
2. **Given** a maintainer writing a white-box test for
   `_classify_response`, **When** they import
   `from pylocal_akuvox._probe_classifiers import _classify_response`,
   **Then** the import succeeds and the function is the same object
   with the same signature.
3. **Given** a maintainer reading `_probe_outcomes.py`, **When** they
   open the file, **Then** it contains only the `_ProbeOutcome` enum
   and the three marker constants — no classifier, parser, or
   orchestration logic.

## Functional Requirements

### FR-001: `AkuvoxDevice.probe_capabilities()` invariance

The public method `AkuvoxDevice.probe_capabilities` is unchanged
post-split:

- Same signature: `async def probe_capabilities(self, *, timeout: float | None = None) -> DeviceCapabilities`
- Same default-timeout resolution (`None` → `5.0`)
- Same 9-call deterministic sequence (step 1 `/api/system/info`,
  step 2 `/api/system/status`, steps 3–9 user / contact / schedule /
  group / doorlog / calllog / relay)
- Same outcome classification (the five `_ProbeOutcome` values —
  `SUPPORTED`, `UNSUPPORTED_NO_HANDLER`, `UNSUPPORTED_API`,
  `UNSUPPORTED_ACTION`, `INDETERMINATE` — map to `CapabilityStatus`
  exactly as today)
- Same idempotence (two probes against an unchanged device produce
  byte-equal `DeviceCapabilities`)
- Same exception contract: step-1 401 → `AkuvoxAuthenticationError`,
  step-1 403 → `AkuvoxRequestError`, step-1 5xx / non-401-403 4xx /
  transport failure → `AkuvoxConnectionError`, step-1 unparsable
  body → `AkuvoxParseError`. **Steps 2–9 transport-level failure**
  (e.g., aiohttp `ClientError`, connection refused, timeout) →
  `AkuvoxConnectionError` propagates with **no partial profile**
  (per `specs/008-capability-matrix/contracts/probe-api.md` Edge case 5; full enumeration in
  `contracts/capability-probe.md` § "Exception contract").
  Steps 2–9 HTTP-level failures (any received response with a
  status code) are folded into the returned profile and never
  raise.

The single permitted change to `device.py` under this spec is the
rewrite of its import line:

```python
from pylocal_akuvox.capability_probe import probe_capabilities as _probe_capabilities
```

becomes:

```python
from pylocal_akuvox._capability_probe import probe_capabilities as _probe_capabilities
```

No other change to `device.py` is permitted under this spec.

### FR-002: `import pylocal_akuvox.capability_probe` raises `ModuleNotFoundError`

Post-split, the `capability_probe.py` file is deleted. Attempting
`import pylocal_akuvox.capability_probe` must raise
`ModuleNotFoundError`. No `capability_probe/` package directory and
no `capability_probe.py` shim (empty or otherwise) is left behind.

### FR-003: `from pylocal_akuvox.capability_probe import X` raises error

For any name `X` (including the previously-public `probe_capabilities`
and the previously-importable internals `_step_1_payload`,
`_classify_response`, `_ProbeOutcome`, `_record_user_aliases`,
`_record_user_schema_keys`, `_record_contact_shape`, `_extract_items`,
`_summarise_system_status`),
`from pylocal_akuvox.capability_probe import X` raises
`ModuleNotFoundError`.

### FR-004: Each new submodule is below the aislop threshold

Each of the four new modules is under the 400-line aislop
`complexity/file-too-large` threshold:

| Module | Estimated lines |
|---|---|
| `_probe_outcomes.py` | ~50 |
| `_probe_classifiers.py` | ~140 |
| `_probe_parsers.py` | ~175 |
| `_capability_probe.py` | ~175 |

Estimates derived from the live source by counting each function /
constant / class block plus a per-module overhead of ~25 lines
(SPDX header + module docstring + imports + `__all__`). Even with
this overhead, all four stay comfortably under 400 lines.

### FR-005: Internal symbols importable from underscore modules

Every symbol previously defined in `capability_probe.py` is
importable from the new underscore module that owns it, with
identical name, signature, type, and behavior. The full module-layout
table lives in `data-model.md`. Summary:

- `_probe_outcomes`: `_ProbeOutcome`, `_NO_HANDLER_MARKERS`,
  `_API_UNSUPPORTED_MARKER`, `_ACTION_UNSUPPORTED_MARKERS`
- `_probe_classifiers`: `_extract_message`, `_summarise_system_status`,
  `_classify_response`, `_outcome_to_status`
- `_probe_parsers`: `_step_1_payload`, `_extract_items`,
  `_record_user_aliases`, `_record_user_schema_keys`,
  `_record_contact_shape`
- `_capability_probe`: `probe_capabilities`, the seven step-path
  constants `_PROBE_STEP_3_PATH` … `_PROBE_STEP_9_PATH`, and the
  `_LATER_STEPS` tuple

None of these are exported from the top-level `pylocal_akuvox`
package's `__all__`. The package top-level `__all__` is unchanged
by this refactor.

### FR-006: All existing tests pass unchanged in semantic behavior

All existing tests in `tests/` pass post-split. The only test changes
are mechanical import-path rewrites (the 41 `from
pylocal_akuvox.capability_probe import …` lines in
`tests/unit/test_capability_probe.py` are rewritten to point at the
new owning underscore module per `data-model.md`) plus a one-line
docstring fix at `tests/unit/test_capability_probe.py:4` (which
currently reads ``Tests for the capability probe in
``pylocal_akuvox.capability_probe``.`` and post-split must reference
either the new internal module path `pylocal_akuvox._capability_probe`
or, preferably, the public method form
`AkuvoxDevice.probe_capabilities`). Test assertion bodies do not
change.

### FR-007: Implementation commit uses `!` breaking-change marker

The implementation commit subject uses Conventional Commits `!` to
flag the breaking change. The subject must be ≤50 characters and
include `!` before the colon. Suggested subject (39 characters):

```text
Refactor(probe)!: Split into submodules
```

Equivalent forms (under 50 characters and with `!`) are acceptable;
the `!` and the breaking change it signals are not.

The `!` is required ONLY on the implementation commit. The spec
commit (this one) does NOT use `!` — its subject is
`Docs(spec): Add 010-capability-probe-split`.

### FR-008: Changelog "Breaking changes" subsection

`docs/changelog.rst` Unreleased section gains a "Breaking changes"
subsection entry calling out:

- The dropped `pylocal_akuvox.capability_probe` import subpath
- The fact that `import pylocal_akuvox.capability_probe` and
  `from pylocal_akuvox.capability_probe import probe_capabilities`
  now raise `ModuleNotFoundError`
- The migration path: continue calling
  `AkuvoxDevice.probe_capabilities()` (the documented public method)
  — no consumer-facing public symbol was renamed or removed

The implementation must place this entry at the same RST section
nesting depth as the existing 009-spec "Breaking changes" subsection
(level: `^^^^^^^^^^^^^^^^` underline) so adding it does not
re-parent the existing top-level "Added" or other subsections.
Per the carry-forward retro from 009 (item 5), changelog edits MUST
NOT promote or demote existing bullets by accident; if the
implementer is unsure of the resulting nesting, they verify by
running `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`
and visually checking the rendered Unreleased section.

### FR-009: README + quickstart sweep — no stale references

Both `README.md` and `docs/quickstart.rst` are spot-checked for
references to `pylocal_akuvox.capability_probe`. The result of this
sweep, performed during spec authoring, is documented in
`research.md` Decision 7: **zero references**. The two existing
mentions of the probe (`README.md` line 64;
`docs/quickstart.rst` lines 35, 36, 40, 50, 77) all use the public
`device.probe_capabilities()` form, which is unaffected by the
split. No README or quickstart edits are required, and the
implementer should not re-discover this — the spec confirms it here.

### FR-010: Sphinx extension and API page — no updates needed

`docs/_ext/capability_matrix.py` does not import or reference
`capability_probe` (verified during spec authoring; see
`research.md` Decision 7). `docs/api/capabilities.rst` does not
reference `capability_probe` either. Neither file requires updates
under this spec. Other API pages (`docs/api/device.rst` etc.) document
`AkuvoxDevice.probe_capabilities` via `automethod`, which resolves
through `AkuvoxDevice` and is unaffected by the split.

### FR-011: Layout-assertion test (extend existing file)

The existing `tests/unit/test_capability_module_layout.py` (added by
spec 009) is **extended** with new test functions covering the
capability-probe subpath removal — rather than creating a parallel
`test_probe_module_layout.py`. Justification:

1. The existing file already establishes the "subpath-is-gone +
   underscore-modules-importable" pattern with the precise pytest
   idiom needed (`pytest.raises(ModuleNotFoundError)`, `exec()` for
   the static `from`-import case, `importlib.import_module` for the
   `import`-form case).
2. A single layout-assertion file is the canonical home for
   "module shape pinning" assertions across the library. Splitting
   them across multiple files invites fragmentation.
3. The file is short (~90 lines today); adding ~50 lines for the
   probe assertions keeps it well under any size threshold.
4. Updating the file's module docstring to mention spec 010 alongside
   spec 009 documents that the file's scope has expanded.

Required additions to the file:

1. `test_capability_probe_subpath_is_gone` —
   `import pylocal_akuvox.capability_probe` raises
   `ModuleNotFoundError`.
2. `test_capability_probe_subpath_from_import_is_gone` —
   `from pylocal_akuvox.capability_probe import probe_capabilities`
   raises `ModuleNotFoundError` (uses `exec()` for the same reason
   as the existing 009 assertion).
3. `test_probe_underscore_modules_importable` — each of the four
   new underscore modules (`_probe_outcomes`, `_probe_classifiers`,
   `_probe_parsers`, `_capability_probe`) imports cleanly via
   `importlib.import_module`.
4. `test_probe_capabilities_reachable_via_device` — confirms
   `pylocal_akuvox.AkuvoxDevice.probe_capabilities` exists as an
   attribute and is callable. (Behavior coverage stays in
   `test_capability_probe.py`; this is just a presence-pin.)

Per the carry-forward retro from 009 (item 4), all `pytest.raises`
assertions for the subpath removal MUST use bare `ModuleNotFoundError`
— never `(ModuleNotFoundError, ImportError)` — so a hypothetical
partial-shim regression that loads `pylocal_akuvox.capability_probe`
but no longer exports `probe_capabilities` raises `ImportError` and
fails the test loudly.

### FR-012: Internal-import policy preserved

The internal imports between the four new modules use absolute
`from pylocal_akuvox._<module> import …` paths (matching the
009-precedent established in `_capability_*` modules and
`research.md` Decision 5 of 009). Cross-dependencies among the
four new modules are documented in `data-model.md` § "Cross-Module
Dependencies" and constructed to avoid cycles:

- `_probe_outcomes` → leaf (depends only on `enum`)
- `_probe_classifiers` → `_probe_outcomes`,
  `pylocal_akuvox._capability_types` (for `CapabilityStatus`)
- `_probe_parsers` → `pylocal_akuvox._capability_profile` (for
  `FieldAliases`), `pylocal_akuvox._capability_types` (for
  `SchemaShape`), `pylocal_akuvox.exceptions` (for
  `AkuvoxParseError`)
- `_capability_probe` → all three above + `_capability_types`,
  `_capability_profile`, `exceptions`, `models`, and `_http`
  (TYPE_CHECKING-only, matching the live source today)

`_probe_classifiers` does NOT import from `_probe_parsers`, and
`_probe_parsers` does NOT import from `_probe_classifiers`. They
are siblings at the same dependency level (both used by
`_capability_probe`) and have no compile-time dependency on each
other.

### FR-013: Pre-PR docstring sweep

Per the carry-forward retro from 009 (item 1), the implementation
agent MUST grep both the moved code AND the consuming code for stale
phrases left behind by the move:

- `"capability_probe"` (the old module name) in any `.py` or `.rst`
  file outside `specs/` — including the **test file's module
  docstring** at `tests/unit/test_capability_probe.py:4`, which
  must be updated alongside the import rewrites
- `"defined here"` / `"this module"` references that may have been
  written when the file was monolithic and now need to be
  re-anchored to the correct new module
- `"dataclass"` (a 009-flavored stale phrase — capability_probe.py
  itself never uses the word, but the implementer should still
  scan to catch any inadvertent paste-from-009 cross-pollination)
- `"lazy import"` and `"cycle"` (009 retro flagged both as
  phrases that may be stale post-refactor; for spec 010, the only
  pre-existing lazy-import was in `_capability_matching.py` and
  is unaffected, but the sweep catches accidental phrasing)
- Sphinx role markers `:mod:` and `:func:` and `:data:` referencing
  `pylocal_akuvox.capability_probe`

Findings are addressed in the same implementation commit. The
quickstart enumerates the exact `grep` invocations.

### FR-014: Inline RST literal hygiene

Per the carry-forward retro from 009 (item 2), any docstring
modified during the import-rewrite phase that contains a multi-line
literal block MUST use indented `::` literal blocks rather than
inline ``` `` ``` … ``` `` ``` cross-line literals. Sphinx-W does NOT
catch the inline-with-newline form, but it renders incorrectly.
Concretely: any docstring sample code or multi-line example that the
implementer adds to the new modules' docstrings (during the cut /
paste / re-add-docstring step) goes in a `::` block, not an inline
``\`\`…\`\`` span.

## Success Criteria

| ID | Criterion | Verification command |
|---|---|---|
| SC-001 | Full test suite green | `uv run pytest tests/` |
| SC-002 | No aislop `file-too-large` on new modules | `uv run aislop scan --include 'src/pylocal_akuvox/_probe_outcomes.py,src/pylocal_akuvox/_probe_classifiers.py,src/pylocal_akuvox/_probe_parsers.py,src/pylocal_akuvox/_capability_probe.py'` |
| SC-003 | Subpath removal confirmed | `uv run python -c "import pylocal_akuvox.capability_probe"` exits non-zero with `ModuleNotFoundError` |
| SC-004 | Public probe still works via device | `uv run python -c "import pylocal_akuvox; assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities); print('ok')"` prints `ok` |
| SC-005 | Changelog entry present | `docs/changelog.rst` Unreleased section "Breaking changes" subsection names the dropped `pylocal_akuvox.capability_probe` subpath and states the migration (use `AkuvoxDevice.probe_capabilities()`) |
| SC-006 | Commit subject has `!` and ≤50 chars | `git log -1 --format=%s` on the implementation commit contains `!` before the colon and `wc -c` returns ≤51 (50 chars + trailing newline) |
| SC-007 | Sphinx -W clean | `uv run --extra docs sphinx-build -W -b html docs docs/_build/html` exits 0 |
| SC-008 | Original file is gone | `test ! -f src/pylocal_akuvox/capability_probe.py && echo deleted` prints `deleted` and exits 0 |
| SC-009 | Layout assertions pass | `uv run pytest tests/unit/test_capability_module_layout.py -v` exits 0 with 4 new probe tests passing alongside the existing 5 capability tests |

## Out of Scope

- **Behavior changes** — function signatures, return types,
  async-ness, ordering, idempotence, timeout handling, and observed
  capability outcomes are preserved exactly.
- **`device.py` split** — tracked separately in issue #142 (out of
  scope for this spec).
- **`capabilities.py` split** — already shipped under issue #140 /
  spec 009 / PR #148.
- **Renaming any function or constant** — all symbol names are
  preserved verbatim.
- **Adding new probe steps or removing existing ones** — the 9-call
  sequence and its step-path constants are untouched.
- **Type-level changes** beyond what is necessary to keep imports
  resolving across the new module boundaries.
- **Promoting any internal symbol to the top-level package
  `__all__`** — the public surface of `pylocal_akuvox` is unchanged
  by this refactor.
- **`tests/unit/test_capability_probe.py` body changes** — only
  the `from pylocal_akuvox.capability_probe import …` lines are
  rewritten; assertion logic is untouched.
