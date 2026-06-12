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
