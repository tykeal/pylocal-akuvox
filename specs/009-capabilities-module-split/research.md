<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Research: Capabilities Module Split

**Feature**: 009-capabilities-module-split
**Date**: 2026-06-15

## Unknowns from Technical Context

None block authoring. The split is purely structural — all symbols, types,
and runtime behavior are preserved. The only decisions concern layout,
import-path policy, and enforcement of the breaking change.

---

## Decision 1: Layout — Sibling Top-Level `_`-Prefixed Modules

**Decision**: Split `capabilities.py` into four sibling modules at the
same package level, each prefixed with `_`:

- `src/pylocal_akuvox/_capability_types.py`
- `src/pylocal_akuvox/_capability_profile.py`
- `src/pylocal_akuvox/_capability_matching.py`
- `src/pylocal_akuvox/_capability_defaults.py`

**Rationale**:

1. A `capabilities/` package with an empty `__init__.py` would still
   resolve `import pylocal_akuvox.capabilities` (as a regular Python
   package). Sibling modules give a clean `ModuleNotFoundError` — the
   cleanest possible break.
2. The `_` prefix idiomatically signals "internal, use top-level
   `pylocal_akuvox` re-exports."
3. No `capabilities/__init__.py` exists that could be misread as an
   opportunity to re-add a re-export and silently reinstate the subpath.
4. Keeps the package flat — no new directory nesting for what is still a
   single-package library.

**Alternatives considered**:

- **`capabilities/` package with `__init__.py` re-exports**: Rejected.
  Would preserve the old `import pylocal_akuvox.capabilities` path,
  defeating the explicit decision to break it. Even an empty
  `__init__.py` keeps the import path resolvable as a regular package.
- **`capabilities/` package with NO `__init__.py` (PEP 420 implicit
  namespace package)**: Rejected. Unlike the regular-package variant
  above, a directory without `__init__.py` is a true PEP 420 namespace
  package; it still resolves on `sys.path` in many configurations,
  making behavior ambiguous and implementation-dependent.
- **Non-prefixed sibling modules** (e.g. `capability_types.py`):
  Rejected. Without the `_` prefix, these look like public submodules
  that consumers might import directly. The underscore makes the
  internal status unambiguous.

---

## Decision 2: Public-Surface Contraction

**Decision**: Keep top-level `__all__` unchanged — the same 5 symbols
currently exported from `pylocal_akuvox` remain:

- `Capability`
- `CapabilityStatus`
- `DeviceCapabilities`
- `FieldAliases`
- `SchemaShape`

The 4 de-facto internals that were reachable via the old
`pylocal_akuvox.capabilities` subpath become formally internal:

- `Provenance`
- `DeviceClassPattern`
- `lookup_capabilities`
- `DEFAULT_USER_FIELD_ALIASES`

This IS the breaking change. These 4 names were in `capabilities.__all__`
and importable via `from pylocal_akuvox.capabilities import Provenance`,
but they were never documented as user-facing public API. They are
matrix-author / maintainer internals.

**Rationale**: Expanding top-level `__all__` with 4 additional symbols
that are only useful to library maintainers and white-box tests would
pollute the consumer-facing surface and create maintenance obligations
(semver stability guarantees) for names that were never intended to be
public.

**Alternatives considered**:

- **Promote all 4 to top-level `__all__`**: Rejected. They are
  internal-only — `Provenance` is matrix metadata, `DeviceClassPattern`
  is a matrix key, `lookup_capabilities` is the internal dispatcher,
  `DEFAULT_USER_FIELD_ALIASES` is a default constant. None are
  consumer-facing.
- **Keep `capabilities.py` as a thin re-export shim**: Rejected. The
  explicit goal (issue #140) is to remove the oversized file and break
  the import path cleanly so it cannot silently reappear.

---

## Decision 3: Subpath-Removal Enforcement

**Decision**: Add an explicit assertion test in
`tests/unit/test_capability_module_layout.py` that verifies
`import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`.

**Rationale**: A deliberately breaking change must be enforced by CI.
If anyone accidentally reintroduces the path (e.g., creates a file
named `capabilities.py` during a merge conflict resolution), the test
fails loudly.

**Alternatives considered**:

- **Rely on ruff/mypy lint rules**: Rejected. No standard lint rule
  catches "module should not exist." A lint rule could ban imports of
  the path from *within* the codebase, but cannot detect the module's
  mere existence. Too soft for a deliberately breaking decision.
- **Rely on aislop scan**: Rejected. Aislop checks file size, not
  import-path semantics. It would not catch a reinstated empty
  `capabilities.py`.

---

## Decision 4: Module Size Targets

**Decision**: Target sizes for the four new modules, all under the
400-line aislop threshold:

| Module | Estimated lines | Content |
|---|---|---|
| `_capability_types.py` | ~120 | SPDX header (~5), module docstring (~10), imports (~10), `Capability` enum (~50), `CapabilityStatus` enum (~15), `SchemaShape` enum (~10), `__all__` (~15) |
| `_capability_profile.py` | ~210 | SPDX header (~5), module docstring (~10), imports (~15), `FieldAliases` (~20), `Provenance` (~15), `DeviceCapabilities` (~120), `__all__` (~10), inter-class whitespace (~15) |
| `_capability_matching.py` | ~210 | SPDX header (~5), module docstring (~10), imports (~20), `_parse_firmware_segments` (~26), `DeviceClassPattern` (~100), `lookup_capabilities` (~30), `__all__` (~10), whitespace (~9) |
| `_capability_defaults.py` | ~40 | SPDX header (~5), module docstring (~5), imports (~5), `DEFAULT_USER_FIELD_ALIASES` constant (~15), `__all__` (~5), whitespace (~5) |

**Arithmetic from the current 455-line file**:

- Header + module docstring + imports + TYPE_CHECKING block: ~39 lines
- `__all__` definition: ~11 lines
- `Capability` enum: ~50 lines
- `CapabilityStatus` enum: ~15 lines
- `SchemaShape` enum: ~10 lines
- `FieldAliases` dataclass: ~20 lines
- `Provenance` dataclass: ~15 lines
- `DeviceCapabilities` dataclass: ~122 lines
- `_parse_firmware_segments` function: ~26 lines
- `DeviceClassPattern` dataclass: ~116 lines
- `DEFAULT_USER_FIELD_ALIASES` constant: ~15 lines
- `lookup_capabilities` function: ~30 lines
- Remaining whitespace/comments: ~3 lines

Each new file adds its own SPDX header (~5 lines), module docstring
(~5–10 lines), imports (~10–20 lines), and `__all__` (~5–15 lines).
Even with this overhead, all four stay well under 400 lines.

---

## Decision 5: Internal-Import Paths Within the Library

**Decision**: Internal modules use direct underscore-module imports:

```python
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
```

They do NOT import via the top-level `pylocal_akuvox` re-export.

**Rationale**:

1. Avoids circular-import risk during package bootstrap. The top-level
   `__init__.py` imports FROM the underscore modules; if those modules
   import back from `pylocal_akuvox`, a circular dependency arises.
2. Makes intent explicit: "this is internal-to-internal usage."
3. Top-level `pylocal_akuvox` import path is for consumers and for
   tests verifying the consumer surface.

**Alternatives considered**:

- **Import from top-level everywhere**: Rejected due to circular-import
  risk and because it obscures the dependency graph (harder to trace
  which internal module depends on what).
- **Relative imports** (e.g., `from ._capability_types import ...`):
  Acceptable but not preferred. The project's existing style uses
  absolute imports throughout. Consistency wins.

---

## Decision 6: White-Box Test Imports

**Decision**: Tests asserting on internal invariants will import from
the underscore modules directly:

```python
from pylocal_akuvox._capability_matching import DeviceClassPattern
from pylocal_akuvox._capability_profile import Provenance
from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
```

This is intentional. The white-box surface is the underscore module,
not the (no-longer-existent) `pylocal_akuvox.capabilities`.

**Affected test files** (all under `tests/unit/`):

- `test_capabilities.py` — tests the full surface (types, profile, matching)
- `test_pattern.py` — tests `DeviceClassPattern` specifically
- `test_dispatch.py` — tests `lookup_capabilities`
- `test_users.py` — may reference `DEFAULT_USER_FIELD_ALIASES`
- `test_contacts.py` — references `SchemaShape`
- `test_device.py` — references `DeviceCapabilities`
- `test_matrix.py` — references `Provenance`, `DeviceClassPattern`
- `test_unsupported_error.py` — references `Capability`
- `test_capability_probe.py` — references multiple capability types

**Rationale**: The old `from pylocal_akuvox.capabilities import ...`
path is removed. Tests that need internal symbols must use the new
canonical internal path. Tests verifying the consumer surface use
top-level `from pylocal_akuvox import ...`.

---

## Decision 7: Handling of Docstring Cross-References

**Decision**: Source-code RST cross-references that spell out
`pylocal_akuvox.capabilities.X` must be updated. Strategy varies by
audience:

**User-facing docstrings** (rendered in API docs):

- Rewrite to spell out the value inline or use a generic
  `:mod:\`pylocal_akuvox\`` reference.
- Do NOT leak the `_capability_defaults` internal path to user-facing
  rendered docs.

**Internal-only cross-references** (e.g., `capability_matrix.py` module
docstring):

- Rewrite to the new underscore path (e.g.,
  `:mod:\`pylocal_akuvox._capability_types\``).

**Concrete locations requiring updates**:

| File | Lines | Current reference | Strategy |
|---|---|---|---|
| `src/pylocal_akuvox/users.py` | 78, 153, 282 | `:data:\`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES\`` | (a) Spell out value inline |
| `src/pylocal_akuvox/models/users.py` | 49 | `:data:\`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES\`` | (a) Spell out value inline |
| `src/pylocal_akuvox/capability_matrix.py` | 8, 12 | References to `pylocal_akuvox.capabilities` | (c) Use underscore path |
| `tests/unit/test_capabilities.py` | 4 | Module docstring mentioning `capabilities` module | (c) Use underscore path |

**Alternatives considered**:

- **(b) Rewrite all to generic `:mod:\`pylocal_akuvox\`` reference**:
  Rejected for `DEFAULT_USER_FIELD_ALIASES` references because the
  docstring is informational and should name the constant's semantics,
  not just the package.
- **(c) Use underscore path everywhere**: Rejected for user-facing
  docstrings because it leaks an internal module name to API doc
  readers.
