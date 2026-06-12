# Import Contract — `pylocal_akuvox.models`

**Branch**: `007-models-split`
**Type**: Stable public import surface (library — no HTTP/GraphQL API)
**Status**: Frozen for this feature; any change here is a breaking change.

This library has no HTTP, GraphQL, or RPC contracts to capture; its public
contract is the set of names that downstream consumers (notably the Home
Assistant Akuvox integration) import from `pylocal_akuvox` and
`pylocal_akuvox.models`. This feature is a *pure refactor* and **must not
change** that contract.

## 1. The contract

Every consumer of `pylocal_akuvox.models` SHALL continue to import any of
the following ten names with their pre-refactor behavior and class
identity:

| # | Name             | Type                            |
|---|------------------|---------------------------------|
| 1 | `AccessSchedule` | `@dataclass(frozen=True, kw_only=True)` |
| 2 | `CallLogEntry`   | `@dataclass(frozen=True, kw_only=True)` |
| 3 | `Contact`        | `@dataclass(frozen=True, kw_only=True)` |
| 4 | `DeviceConfig`   | `@dataclass(frozen=True, kw_only=True)` |
| 5 | `DeviceInfo`     | `@dataclass(frozen=True)`               |
| 6 | `DeviceStatus`   | `@dataclass(frozen=True)`               |
| 7 | `DoorLogEntry`   | `@dataclass(frozen=True, kw_only=True)` |
| 8 | `Group`          | `@dataclass(frozen=True, kw_only=True)` |
| 9 | `Relay`          | `@dataclass(frozen=True)`               |
| 10| `User`           | `@dataclass(frozen=True, kw_only=True)` |

In addition:

- `pylocal_akuvox.models.__all__` SHALL be exactly the sorted list of those
  ten names (no extras, none missing). The current `models.py` has no
  `__all__`, so `from pylocal_akuvox.models import *` today exposes
  **fourteen** names: the ten public model classes plus four accidental
  module-level helper leaks (`AkuvoxParseError`, `Any`, `annotations`,
  `dataclass`). The introduction of an explicit `__all__` is a
  **deliberate clarification of the public contract**, not a regression:
  the four leaked helper names were never part of the documented public
  surface, and a repository audit
  (`git grep "from pylocal_akuvox.models import \*"`) confirms zero
  in-repo consumers rely on them via star-import. See spec FR-004 and
  the corresponding edge-case for the full rationale.
- `pylocal_akuvox.__all__` SHALL continue to expose all ten names (this is
  upstream of `models`; the file itself is **not edited** by this feature,
  so this is preserved trivially).
- Each name, when imported through the shim, SHALL be the **same
  `type` object** as when imported directly from its home submodule:
  `pylocal_akuvox.models.User is pylocal_akuvox.models.users.User` (and
  analogously for all ten). This is the class-identity / `isinstance`
  guarantee.

## 2. Consumers that exercise the contract today

Discovered via `git grep "from pylocal_akuvox.models"` and
`git grep "from \\.models"` on the pre-split tree:

**In `src/`:**

- `pylocal_akuvox/__init__.py` — imports all ten names in one block.
- `pylocal_akuvox/device.py` — `DeviceInfo`, `DeviceStatus` (top-level);
  `DeviceConfig`, plus optional types under `TYPE_CHECKING`.
- `pylocal_akuvox/users.py` — `User`.
- `pylocal_akuvox/schedules.py` — `AccessSchedule`.
- `pylocal_akuvox/logs.py` — `CallLogEntry`, `DoorLogEntry`.
- `pylocal_akuvox/groups.py` — `Group`.
- `pylocal_akuvox/contacts.py` — `Contact`.
- `pylocal_akuvox/config.py` — `DeviceConfig` (under `TYPE_CHECKING`, plus
  a runtime aliased import).

**In `tests/`:**

- `tests/unit/test_models.py` — bulk import of all ten (line 8) plus ten
  in-function `DeviceConfig` re-imports.
- `tests/unit/test_device.py` — `DeviceInfo`, `DeviceStatus`,
  `DeviceConfig`.
- `tests/unit/test_config.py` — `DeviceConfig`.

**In `examples/` and `docs/`:** none reference `pylocal_akuvox.models` by a
hard-coded class path that this feature would invalidate (`docs/api/models.rst`
uses `automodule` against the shim package name and resolves through
re-exports).

**Outcome**: Zero of these consumers require source edits for the refactor to
land correctly. Any optional cleanup (e.g. switching a service module to
import directly from its model submodule) is **opt-in** and not part of
this feature.

## 3. Contract verification

A new dedicated test module locks the contract in CI:

**File**: `tests/unit/test_models_reexport.py` (NEW)

**Must include the following assertions** (representative — exact wording
during implementation):

```python
import pylocal_akuvox.models as shim
from pylocal_akuvox.models import (
    AccessSchedule, CallLogEntry, Contact, DeviceConfig, DeviceInfo,
    DeviceStatus, DoorLogEntry, Group, Relay, User,
)
from pylocal_akuvox.models import config as config_mod
from pylocal_akuvox.models import contacts as contacts_mod
from pylocal_akuvox.models import device as device_mod
from pylocal_akuvox.models import groups as groups_mod
from pylocal_akuvox.models import logs as logs_mod
from pylocal_akuvox.models import schedules as schedules_mod
from pylocal_akuvox.models import users as users_mod


EXPECTED_PUBLIC_NAMES: list[str] = [
    "AccessSchedule",
    "CallLogEntry",
    "Contact",
    "DeviceConfig",
    "DeviceInfo",
    "DeviceStatus",
    "DoorLogEntry",
    "Group",
    "Relay",
    "User",
]


def test_models_all_contains_exactly_the_ten_public_names() -> None:
    """FR-004: shim __all__ exposes exactly the ten historic public names."""
    assert sorted(shim.__all__) == EXPECTED_PUBLIC_NAMES


def test_class_identity_is_preserved_through_shim() -> None:
    """FR-002: each re-export is the *same* class object as its home definition."""
    assert User is users_mod.User
    assert Contact is contacts_mod.Contact
    assert DeviceInfo is device_mod.DeviceInfo
    assert DeviceStatus is device_mod.DeviceStatus
    assert Relay is device_mod.Relay
    assert DeviceConfig is config_mod.DeviceConfig
    assert Group is groups_mod.Group
    assert AccessSchedule is schedules_mod.AccessSchedule
    assert DoorLogEntry is logs_mod.DoorLogEntry
    assert CallLogEntry is logs_mod.CallLogEntry


def test_top_level_package_all_still_exposes_the_ten_names() -> None:
    """FR-003: pylocal_akuvox.__all__ continues to expose the ten model names."""
    import pylocal_akuvox

    for name in EXPECTED_PUBLIC_NAMES:
        assert name in pylocal_akuvox.__all__
        assert getattr(pylocal_akuvox, name) is getattr(shim, name)
```

These tests are written **before** the move (TDD red phase): on the current
tree they fail because `pylocal_akuvox.models.users` (etc.) do not exist as
modules. They pass after the move and shim are in place (TDD green phase),
and remain in CI forever to prevent silent contract regression.

## 4. Contract change policy

After this feature merges, any future change that would:

- remove a name from this list, **or**
- change the public class identity of any of these ten,

is a **breaking change** and SHALL be treated as a major-version concern per
Constitution Principle III (UX Consistency). Adding new model classes
(`pylocal_akuvox.capabilities.Capability` etc. from #123) is additive and
NOT governed by this contract — those classes live outside `models/` per
plan §R9.
