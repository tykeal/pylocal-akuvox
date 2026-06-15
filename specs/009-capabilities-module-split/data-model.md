<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Data Model: Capabilities Module Split

**Feature**: 009-capabilities-module-split
**Date**: 2026-06-15

## Scope

This is a pure refactor — no new data model is introduced. The underlying
capability data model is fully specified in
`specs/008-capability-matrix/data-model.md`. This document describes the
**module layout** (which symbol lives where post-split) and the
**affected-file list** for downstream import rewrites.

## Module Layout Table

| Symbol | Kind | Today | Post-split | Public re-export |
|---|---|---|---|---|
| `Capability` | enum | `capabilities.py` | `_capability_types.py` | yes (`pylocal_akuvox.Capability`) |
| `CapabilityStatus` | enum | `capabilities.py` | `_capability_types.py` | yes (`pylocal_akuvox.CapabilityStatus`) |
| `SchemaShape` | enum | `capabilities.py` | `_capability_types.py` | yes (`pylocal_akuvox.SchemaShape`) |
| `FieldAliases` | dataclass | `capabilities.py` | `_capability_profile.py` | yes (`pylocal_akuvox.FieldAliases`) |
| `Provenance` | dataclass | `capabilities.py` | `_capability_profile.py` | **no** (internal) |
| `DeviceCapabilities` | dataclass | `capabilities.py` | `_capability_profile.py` | yes (`pylocal_akuvox.DeviceCapabilities`) |
| `_parse_firmware_segments` | function | `capabilities.py` | `_capability_matching.py` | n/a (private) |
| `DeviceClassPattern` | dataclass | `capabilities.py` | `_capability_matching.py` | **no** (internal) |
| `lookup_capabilities` | function | `capabilities.py` | `_capability_matching.py` | **no** (internal) |
| `DEFAULT_USER_FIELD_ALIASES` | constant | `capabilities.py` | `_capability_defaults.py` | **no** (internal) |

## Cross-Module Dependencies

Each new module's import dependencies on its siblings and the rest of
the package:

### `_capability_types.py`

- **Depends on**: stdlib only (`enum`)
- **No sibling imports**
- This is the leaf of the dependency graph — all other capability
  modules may import from it without risk of cycles.

### `_capability_profile.py`

- **Depends on**:
  - `_capability_types` — for `Capability`, `CapabilityStatus`, `SchemaShape`
  - `pylocal_akuvox.exceptions` — for `AkuvoxUnsupportedError` (used
    inside `DeviceCapabilities.require()`)
  - stdlib: `dataclasses`, `types.MappingProxyType`

### `_capability_matching.py`

- **Depends on**:
  - `_capability_profile` — for `DeviceCapabilities` (return type of
    `lookup_capabilities`)
  - `TYPE_CHECKING`-only: `pylocal_akuvox.models` — for `DeviceInfo`
    (used in `DeviceClassPattern.matches()` type annotation)
  - Lazy import (runtime, inside function body): `pylocal_akuvox.capability_matrix`
    — for `CAPABILITY_MATRIX` (preserves the existing circular-dependency
    break; see current `capabilities.py` lines 446–449)
  - stdlib: `dataclasses`, `typing`

### `_capability_defaults.py`

- **Depends on**:
  - `_capability_profile` — for `FieldAliases` (the type of the
    constant value)

## Affected-File List for Downstream Import Rewrites

The following files currently import from `pylocal_akuvox.capabilities`
and must be rewritten to use the new underscore module paths or
top-level re-exports:

### Package internals (`src/pylocal_akuvox/`)

| File | Current import style | Post-split import source |
|---|---|---|
| `__init__.py` | Re-exports from `capabilities` | Re-exports from `_capability_types`, `_capability_profile` |
| `capability_matrix.py` | `from pylocal_akuvox.capabilities import ...` | `from pylocal_akuvox._capability_types import ...` etc. |
| `capability_probe.py` | `from pylocal_akuvox.capabilities import ...` | `from pylocal_akuvox._capability_types import ...` etc. |
| `capability_adapters.py` | `from pylocal_akuvox.capabilities import ...` | `from pylocal_akuvox._capability_types import ...` etc. |
| `device.py` | Top-level + 4 deferred imports from `capabilities` | Top-level + deferred from underscore modules |
| `users.py` | Top-level + `TYPE_CHECKING` from `capabilities` | Top-level + `TYPE_CHECKING` from underscore modules |
| `contacts.py` | Top-level + `TYPE_CHECKING` from `capabilities` | Top-level + `TYPE_CHECKING` from underscore modules |
| `exceptions.py` | `TYPE_CHECKING` only from `capabilities` | `TYPE_CHECKING` from `_capability_types` |
| `models/users.py` | `TYPE_CHECKING` + deferred from `capabilities` | `TYPE_CHECKING` + deferred from underscore modules |
| `models/contacts.py` | `TYPE_CHECKING` + deferred from `capabilities` | `TYPE_CHECKING` + deferred from underscore modules |

### Documentation extensions

| File | Current import | Post-split import |
|---|---|---|
| `docs/_ext/capability_matrix.py` | `from pylocal_akuvox.capabilities import Capability, CapabilityStatus` | `from pylocal_akuvox._capability_types import Capability, CapabilityStatus` |

### Test files (`tests/unit/`)

| File | Current import | Post-split import source |
|---|---|---|
| `test_capabilities.py` | `from pylocal_akuvox.capabilities import ...` | From respective underscore modules |
| `test_pattern.py` | `from pylocal_akuvox.capabilities import DeviceClassPattern, ...` | `from pylocal_akuvox._capability_matching import ...` |
| `test_dispatch.py` | `from pylocal_akuvox.capabilities import Capability` | `from pylocal_akuvox._capability_types import Capability` |
| `test_users.py` | `from pylocal_akuvox.capabilities import ...` | From respective underscore modules |
| `test_contacts.py` | `from pylocal_akuvox.capabilities import ...` | From respective underscore modules |
| `test_device.py` | `from pylocal_akuvox.capabilities import ...` | From respective underscore modules |
| `test_matrix.py` | `from pylocal_akuvox.capabilities import ...` | `from pylocal_akuvox._capability_matching import ...` / `_capability_profile` |
| `test_unsupported_error.py` | `from pylocal_akuvox.capabilities import Capability` | `from pylocal_akuvox._capability_types import Capability` |
| `test_capability_probe.py` | `from pylocal_akuvox.capabilities import ...` | From respective underscore modules |

### New test file (to be created)

| File | Purpose |
|---|---|
| `tests/unit/test_capability_module_layout.py` | Asserts subpath removal (`import pylocal_akuvox.capabilities` → `ModuleNotFoundError`) and underscore-module importability |
