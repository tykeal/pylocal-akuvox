# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for the ``pylocal_akuvox.models`` re-export shim.

These tests lock the public import surface of ``pylocal_akuvox.models``
after the 007-models-split refactor:

- ``pylocal_akuvox.models.__all__`` exposes exactly the ten historic
  public model class names (FR-004).
- Each name imported through the shim is the *same* Python class object
  as the one defined in its per-domain home submodule (FR-002).
- ``pylocal_akuvox.__all__`` continues to expose the ten model names
  (FR-003).
"""

import pylocal_akuvox.models as shim
from pylocal_akuvox.models import (
    AccessSchedule,
    CallLogEntry,
    Contact,
    DeviceConfig,
    DeviceInfo,
    DeviceStatus,
    DoorLogEntry,
    Group,
    Relay,
    User,
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
