<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Capability Types Module

**Owning module**: `src/pylocal_akuvox/_capability_types.py`
**Owning tests**: `tests/unit/test_capabilities.py` (enum surface),
`tests/unit/test_capability_module_layout.py` (import assertions)

## Public Surface

This module exports three enumerations that form the foundational type
vocabulary for the capability system:

```python
__all__ = ["Capability", "CapabilityStatus", "SchemaShape"]
```

### `Capability` (enum.Enum, str values)

Canonical capability identifiers. Members use `domain.action[.variant]`
string values. New members are additive only (FR-001 from spec 008).

### `CapabilityStatus` (enum.Enum, str values)

Three-valued status: `SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`.

### `SchemaShape` (enum.Enum, str values)

Contact schema shape discriminator: `DOOR_PHONE`, `APARTMENT_BOOK`.

## Top-Level Re-Export

All three symbols are re-exported from `pylocal_akuvox.__init__` and
appear in the package-level `__all__`:

- `pylocal_akuvox.Capability`
- `pylocal_akuvox.CapabilityStatus`
- `pylocal_akuvox.SchemaShape`

## What This Module Does NOT Export

- `FieldAliases` — lives in `_capability_profile`
- `Provenance` — lives in `_capability_profile`
- `DeviceCapabilities` — lives in `_capability_profile`
- `DeviceClassPattern` — lives in `_capability_matching`
- `lookup_capabilities` — lives in `_capability_matching`
- `DEFAULT_USER_FIELD_ALIASES` — lives in `_capability_defaults`

## Dependencies

- stdlib `enum` only. No sibling-module or third-party imports.

## Backward-Compatibility Note

The following old import paths would have resolved to names now in this
module:

| Old path | Symbol |
|---|---|
| `from pylocal_akuvox.capabilities import Capability` | `Capability` |
| `from pylocal_akuvox.capabilities import CapabilityStatus` | `CapabilityStatus` |
| `from pylocal_akuvox.capabilities import SchemaShape` | `SchemaShape` |

Post-split, these old paths raise `ModuleNotFoundError`. Consumers must
use `from pylocal_akuvox import Capability, CapabilityStatus, SchemaShape`.
