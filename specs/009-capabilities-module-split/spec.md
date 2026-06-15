<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: Refactor capabilities.py Under Aislop Size Limit

**Feature Branch**: `009-capabilities-module-split`
**Created**: 2026-06-15
**Status**: Draft
**Input**: Issue #140 — `aislop scan` flags `src/pylocal_akuvox/capabilities.py` (455 lines) with `complexity/file-too-large` against the project's 400-line threshold. This specification describes a pure-refactor split into focused sibling modules with no behavioral changes.

## Background and Evidence

`src/pylocal_akuvox/capabilities.py` currently weighs 455 lines and contains five orthogonal concerns:

1. **Type enumerations** — `Capability`, `CapabilityStatus`, `SchemaShape` (~70 lines)
2. **Profile dataclasses** — `FieldAliases`, `Provenance`, `DeviceCapabilities` (~152 lines)
3. **Pattern-matching logic** — `DeviceClassPattern`, `_parse_firmware_segments`, `lookup_capabilities` (~142 lines)
4. **Defaults constant** — `DEFAULT_USER_FIELD_ALIASES` (~15 lines)
5. **Boilerplate** — module docstring, imports, `__all__` (~50 lines)

The aislop `complexity/file-too-large` threshold is 400 lines. Splitting along the natural concern boundaries yields four files, each well under the threshold, with no change to runtime behavior.

This is a **BREAKING** refactor: the `pylocal_akuvox.capabilities` import subpath is removed entirely. Consumers must migrate to top-level `pylocal_akuvox` imports for the 5 public symbols. The 4 other symbols previously reachable via the old subpath become formally internal (importable only from their underscore modules).

## User Scenarios & Testing

### User Story 1 — Existing consumer imports continue working (Priority: P1)

A library consumer whose code uses `from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape` sees no change in behavior across the refactor. Their imports resolve, their type annotations remain valid, and runtime behavior is identical.

**Why this priority**: The top-level import path is the documented, supported API. Breaking it would be an unacceptable regression. Every other story depends on this guarantee holding.

**Independent Test**: Run the full test suite (`uv run pytest tests/`) and confirm all tests pass. Additionally, a dedicated assertion verifies the 5 public symbols are importable from `pylocal_akuvox` top-level with identical identity (`is` check against the source module's export).

**Acceptance Scenarios**:

1. **Given** a consumer importing `from pylocal_akuvox import Capability`, **When** the import executes post-split, **Then** the import succeeds and `Capability` is the same enum class with the same members and values.
2. **Given** a consumer using type annotations with `DeviceCapabilities`, **When** the code is type-checked with mypy post-split, **Then** no type errors arise from the refactor.
3. **Given** the full test suite, **When** `uv run pytest tests/` is run post-split, **Then** all tests pass (test imports may be rewritten to new paths, but assertions are unchanged).

---

### User Story 2 — Old subpath gives a clear error (Priority: P1)

A consumer attempting the old import path `from pylocal_akuvox.capabilities import Capability` gets a clear `ModuleNotFoundError` and finds the migration path in the changelog "Breaking changes" subsection.

**Why this priority**: A silent failure (empty module, partial import) would be worse than a loud error. The breaking change must be immediately obvious so consumers can find the documented migration path.

**Independent Test**: `tests/unit/test_capability_module_layout.py` asserts that `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`.

**Acceptance Scenarios**:

1. **Given** a consumer attempting `import pylocal_akuvox.capabilities`, **When** the import executes post-split, **Then** Python raises `ModuleNotFoundError`.
2. **Given** a consumer attempting `from pylocal_akuvox.capabilities import Capability`, **When** the import executes post-split, **Then** Python raises `ModuleNotFoundError` (or `ImportError` as its superclass).
3. **Given** a consumer encountering the error, **When** they consult the changelog, **Then** the Unreleased "Breaking changes" subsection names the dropped subpath and states the migration: use `from pylocal_akuvox import Capability, ...`.

---

### User Story 3 — Maintainer finds focused, readable modules (Priority: P2)

A maintainer extending the capability matrix or adding white-box tests imports from the underscore modules (`_capability_matching`, `_capability_types`, etc.) and finds each module focused on a single concern, under the aislop threshold, and faster to read and navigate than the original monolithic file.

**Why this priority**: Developer experience and long-term maintainability motivate the split, but the library's external behavior is unchanged. P2 because it primarily benefits internal contributors.

**Independent Test**: `uv run aislop scan src/pylocal_akuvox/_capability_*.py` reports no `complexity/file-too-large` warnings for any of the four new modules.

**Acceptance Scenarios**:

1. **Given** each of the four new underscore modules, **When** `aislop scan` is run, **Then** none is flagged as exceeding the 400-line threshold.
2. **Given** a maintainer writing a white-box test for `DeviceClassPattern`, **When** they import `from pylocal_akuvox._capability_matching import DeviceClassPattern`, **Then** the import succeeds and the class is the same object with the same interface.
3. **Given** a maintainer reading `_capability_types.py`, **When** they open the file, **Then** it contains only `Capability`, `CapabilityStatus`, and `SchemaShape` — no unrelated profile or matching logic.

## Functional Requirements

### FR-001: Public symbols remain importable from top-level

All 5 currently-public symbols remain importable from `pylocal_akuvox` top-level with identical names, types, and behavior:

- `Capability`
- `CapabilityStatus`
- `DeviceCapabilities`
- `FieldAliases`
- `SchemaShape`

Top-level `__all__` is unchanged — these 5 symbols (among others already in `__all__`) remain exactly as they are today.

### FR-002: `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`

Post-split, the `capabilities.py` file is deleted. Attempting `import pylocal_akuvox.capabilities` must raise `ModuleNotFoundError`.

### FR-003: `from pylocal_akuvox.capabilities import X` raises error

For any name `X`, `from pylocal_akuvox.capabilities import X` raises `ModuleNotFoundError` (or `ImportError` as its superclass).

### FR-004: Each new submodule is below the aislop threshold

Each of the four new modules is under 400 lines:

- `_capability_types.py`: ~120 lines
- `_capability_profile.py`: ~210 lines
- `_capability_matching.py`: ~210 lines
- `_capability_defaults.py`: ~40 lines

### FR-005: Internal symbols importable from underscore modules

All 4 internal symbols are importable from their respective underscore modules with identical names, types, and behavior:

- `Provenance` from `pylocal_akuvox._capability_profile`
- `DeviceClassPattern` from `pylocal_akuvox._capability_matching`
- `lookup_capabilities` from `pylocal_akuvox._capability_matching`
- `DEFAULT_USER_FIELD_ALIASES` from `pylocal_akuvox._capability_defaults`

These are NOT exported from top-level `__all__`.

### FR-006: All existing tests pass unchanged in semantic behavior

All existing tests in `tests/` pass post-split. Test imports may be rewritten to use new paths, but the test bodies — what they assert — do not change.

### FR-007: Implementation commit uses `!` breaking-change marker

The implementation commit subject uses Conventional Commits `!` to flag the breaking change, e.g.: `Refactor(capabilities)!: Split module into focused submodules`.

### FR-008: Changelog "Breaking changes" subsection

`docs/changelog.rst` Unreleased section gains a "Breaking changes" subsection (or equivalent) calling out:

- The dropped `pylocal_akuvox.capabilities` subpath
- The 4 no-longer-publicly-reachable internal symbols (`Provenance`, `DeviceClassPattern`, `lookup_capabilities`, `DEFAULT_USER_FIELD_ALIASES`)
- The migration path: use top-level `from pylocal_akuvox import ...` for the 5 public symbols

### FR-009: README spot-check — no stale references

`README.md` is verified to contain no `pylocal_akuvox.capabilities` references. The existing usage examples already use top-level `from pylocal_akuvox import …` — no changes needed. The implementer need not re-discover this; it is confirmed here.

### FR-010: Sphinx extension updated

`docs/_ext/capability_matrix.py` is updated to use the new underscore module path:

```python
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
```

This is a maintainer-internal Sphinx extension, not a public consumer integration, so the underscore import path is appropriate.

### FR-011: Layout-assertion test

A new test file `tests/unit/test_capability_module_layout.py` asserts:

1. `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`.
2. (Optional but recommended) Each of the 4 underscore modules is importable.
3. (Optional but recommended) The 5 public symbols round-trip via the top-level re-export (i.e., `pylocal_akuvox.Capability is pylocal_akuvox._capability_types.Capability`).

## Success Criteria

| ID | Criterion | Verification command |
|---|---|---|
| SC-001 | Full test suite green | `uv run pytest tests/` |
| SC-002 | No aislop `file-too-large` on new modules | `uv run aislop scan src/pylocal_akuvox/_capability_*.py` |
| SC-003 | Subpath removal confirmed | `uv run python -c "import pylocal_akuvox.capabilities"` exits with `ModuleNotFoundError` |
| SC-004 | Top-level imports work | `uv run python -c "from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape; print('ok')"` prints `ok` |
| SC-005 | Changelog entry present | `docs/changelog.rst` Unreleased section contains a "Breaking changes" subsection naming the dropped subpath and migration path |
| SC-006 | Commit subject has `!` | `git log -1 --format=%s` on the implementation commit contains `!` before the colon |

## Out of Scope

- **Behavior changes** — function signatures, types, runtime semantics are preserved exactly.
- **`capability_matrix.py` split** — tracked separately in issue #141.
- **`device.py` split** — tracked separately in issue #142.
- **Renaming any public or private symbol** — all names are preserved.
- **Adding any new public symbol** — top-level `__all__` is unchanged (no expansion).
- **`capability_probe.py` split** — tracked separately in issue #141.
