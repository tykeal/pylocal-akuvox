# Data Model — 007-models-split

**Branch**: `007-models-split`
**Status**: Pure structural refactor — **no field, method, default, validation,
parsing rule, or exception type changes**. This document is a *home map*, not
a schema change.

## Scope

This feature relocates ten existing `@dataclass(frozen=True[, kw_only=True])`
classes from `src/pylocal_akuvox/models.py` into per-domain submodules under a
new `src/pylocal_akuvox/models/` package. Each class is moved verbatim:

- All fields, types, defaults — unchanged.
- All `from_api_response` classmethods, including key fallback chains (e.g.
  `User`'s `ScheduleRelay`/`Schedule-Relay`/`Schedule` lookup) — unchanged.
- All `to_api_payload` methods — unchanged.
- All docstrings (class-level and method-level) — preserved verbatim.
- All raised exception types (`AkuvoxParseError` from
  `pylocal_akuvox.exceptions`) — unchanged.
- Class identity post-move: each class is the **same Python class object**
  as before. Re-export is via plain `from .<submodule> import <Name>` in
  `models/__init__.py`; there is no wrapper, alias, or subclass.

## Class Home Map

Current line ranges are taken from `src/pylocal_akuvox/models.py` HEAD on
branch `007-models-split` (447-line file; originally reported as 448 in
issue #126 — the one-line delta is immaterial, both exceed the 400-line
gate). Each class is moved as a contiguous block including the
`@dataclass(...)` decorator line.

| # | Class             | Current location (lines)              | New home                          | Domain rationale |
|---|-------------------|---------------------------------------|------------------------------------|------------------|
| 1 | `DeviceInfo`      | `models.py:14-54`  (decorator + body) | `models/device.py`                 | Device identity / system info; consumed by service `device.py`. |
| 2 | `DeviceStatus`    | `models.py:55-86`                     | `models/device.py`                 | Live state of the same device; consumed alongside `DeviceInfo` in `device.py`. |
| 3 | `Relay`           | `models.py:87-119`                    | `models/device.py`                 | Sub-component of a device, returned in the same status responses as `DeviceStatus`. |
| 4 | `User`            | `models.py:120-191`                   | `models/users.py`                  | User-only domain; kept narrow so #123's capability-driven `from_api_response` rewrite is a single-file change (FR-008, US3). |
| 5 | `AccessSchedule`  | `models.py:192-275`                   | `models/schedules.py`              | Access-control time schedule; consumed by service `schedules.py`. |
| 6 | `DoorLogEntry`    | `models.py:276-309`                   | `models/logs.py`                   | Door-open event-log record; consumed by service `logs.py`. |
| 7 | `CallLogEntry`    | `models.py:310-341`                   | `models/logs.py`                   | Call event-log record; consumed alongside `DoorLogEntry` in `logs.py`. |
| 8 | `DeviceConfig`    | `models.py:342-387`                   | `models/config.py`                 | Device configuration document; fetched via a distinct config endpoint and consumed by service `config.py` (separate from `device.py` per R3). |
| 9 | `Group`           | `models.py:388-414`                   | `models/groups.py`                 | Organizational group; consumed by service `groups.py`. |
| 10| `Contact`         | `models.py:415-447`                   | `models/contacts.py`               | Address-book entry; consumed by service `contacts.py`. Kept narrow so #121's apartment-book field additions are a single-file change (FR-008, US3). |

## Per-File Composition

Each new `.py` file under `src/pylocal_akuvox/models/` has the structure:

```python
# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""<one-line per-domain module docstring>."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# from pylocal_akuvox.exceptions import AkuvoxParseError  # only when used

# <pasted class block(s), verbatim>
```

Imports MUST be **minimal per file** — only what each module actually
uses — so that ruff's `F401` unused-import check does not fail. Verified
against `src/pylocal_akuvox/models.py` HEAD: every class block uses both
`@dataclass` and `Any`, but only nine of the ten classes raise
`AkuvoxParseError` from their own methods. Per-file required imports:

| New file              | `__future__.annotations` | `dataclass` | `Any` | `AkuvoxParseError` |
|-----------------------|:------------------------:|:-----------:|:-----:|:------------------:|
| `models/device.py`    | ✅ | ✅ | ✅ | ✅ (DeviceInfo L31/L52, DeviceStatus L70/L81/L84, Relay L101/L109/L112 raise) |
| `models/users.py`     | ✅ | ✅ | ✅ | ✅ (User L150/L168 raise) |
| `models/schedules.py` | ✅ | ✅ | ✅ | ✅ (AccessSchedule L243 raises) |
| `models/logs.py`      | ✅ | ✅ | ✅ | ✅ (DoorLogEntry L307, CallLogEntry L339 raise) |
| `models/groups.py`    | ✅ | ✅ | ✅ | ✅ (Group L405 raises) |
| `models/contacts.py`  | ✅ | ✅ | ✅ | ✅ (Contact L436 raises) |
| `models/config.py`    | ✅ | ✅ | ✅ | ❌ **MUST NOT import** — `DeviceConfig` does not raise (verified via `grep -n "raise" src/pylocal_akuvox/models.py` against lines 342-387, no hits). Adding the import would trigger ruff `F401 unused import` and fail the quality gate. |

`DeviceConfig` is the lone exception. All other domain modules MUST
include the `from pylocal_akuvox.exceptions import AkuvoxParseError` line
because their classes raise it. This per-file minimality rule supersedes
any earlier guidance suggesting a uniform import block.

## Re-Export Shim (`models/__init__.py`)

The shim is the single point of public re-export and the only file that
defines `__all__` for the `pylocal_akuvox.models` namespace.

```python
# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Backwards-compatibility re-export surface for pylocal_akuvox data models.

This package re-exports the ten public data-model classes from their
per-domain home modules so that existing
``from pylocal_akuvox.models import <Name>`` imports continue to resolve
without source edits on the consumer side. For new code, importing directly
from the per-domain home (e.g. ``from pylocal_akuvox.models.users import
User``) is also fine.

Cross-cutting types that are not specific to one domain (for example the
``Capability`` enum and ``DeviceCapabilities`` dataclass introduced by
issue #123) belong as a sibling module at the package root — i.e.
``pylocal_akuvox/capabilities.py`` — parallel to the existing service
modules, and explicitly NOT inside this ``models/`` package. See spec
FR-009 and plan §R9.
"""

from __future__ import annotations

from pylocal_akuvox.models.config import DeviceConfig
from pylocal_akuvox.models.contacts import Contact
from pylocal_akuvox.models.device import DeviceInfo, DeviceStatus, Relay
from pylocal_akuvox.models.groups import Group
from pylocal_akuvox.models.logs import CallLogEntry, DoorLogEntry
from pylocal_akuvox.models.schedules import AccessSchedule
from pylocal_akuvox.models.users import User

__all__: list[str] = [
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
```

The `__all__` list is **alphabetically sorted** and matches the alphabetical
sort order already used in `pylocal_akuvox/__init__.py`'s `__all__`. The set
of ten names is identical to the names currently importable from `models.py`,
satisfying FR-001, FR-003, and FR-004.

## File-Size Budget (post-split)

| New file               | Projected lines | Limit | Headroom |
|------------------------|-----------------|-------|----------|
| `models/__init__.py`   | ~40             | 400   | ~360     |
| `models/device.py`     | ~115            | 400   | ~285     |
| `models/config.py`     | ~55             | 400   | ~345     |
| `models/users.py`      | ~81             | 400   | ~319     |
| `models/schedules.py`  | ~93             | 400   | ~307     |
| `models/groups.py`     | ~36             | 400   | ~364     |
| `models/logs.py`       | ~75             | 400   | ~325     |
| `models/contacts.py`   | ~42             | 400   | ~358     |

`models/users.py` and `models/contacts.py` are well under the 250-line
SC-006 target, so the anticipated #123 and #121 additions will not
re-trigger the gate.

## Old File

`src/pylocal_akuvox/models.py` is **deleted** in the same change. Python
cannot resolve both `models.py` and `models/` at the same import path; the
package replaces the file.

## State Transitions

N/A — these are immutable (`frozen=True`) value objects. No lifecycle.

## Validation Rules

Unchanged. All validation lives inside the per-class `from_api_response`
methods (raising `AkuvoxParseError` on missing required fields) and is moved
verbatim with the class.

## Relationships

The dataclasses have no runtime relationships to each other — there are no
foreign-key fields, no nested-instance fields. Each class parses its own slice
of an API response independently. This is what makes the per-domain split
clean: there are no cross-module dataclass dependencies to manage.
