# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Foundational type vocabulary for the capability system.

Split out from the former ``pylocal_akuvox.capabilities`` module per
spec ``009-capabilities-module-split`` so each focused submodule stays
under the project's 400-line aislop ``file-too-large`` threshold.

This module exports the three foundational enums that downstream
modules — :mod:`pylocal_akuvox._capability_profile`,
:mod:`pylocal_akuvox._capability_matching`, and
:mod:`pylocal_akuvox._capability_defaults` — build on:

* :class:`Capability` — canonical capability identifiers.
* :class:`CapabilityStatus` — three-valued status (SUPPORTED /
  UNSUPPORTED / UNKNOWN).
* :class:`SchemaShape` — contact resource schema variants.
"""

from __future__ import annotations

import enum


class Capability(enum.Enum):
    """Canonical capability identifiers.

    String values use a ``domain.action[.variant]`` shape so they are
    grep-friendly and stable in serialized notes/provenance.

    The enum is **extensible**: new members append. Existing members do
    not change name or value (FR-001).
    """

    USER_LIST = "user.list"
    USER_ADD = "user.add"
    USER_MODIFY = "user.modify"
    USER_DELETE = "user.delete"
    SCHEDULE_LIST = "schedule.list"
    SCHEDULE_ADD = "schedule.add"
    SCHEDULE_MODIFY = "schedule.modify"
    SCHEDULE_DELETE = "schedule.delete"
    GROUP_LIST = "group.list"
    GROUP_ADD = "group.add"
    GROUP_MODIFY = "group.modify"
    GROUP_DELETE = "group.delete"
    CONTACT_LIST = "contact.list"
    CONTACT_ADD = "contact.add"
    CONTACT_MODIFY = "contact.modify"
    CONTACT_DELETE = "contact.delete"
    RELAY_TRIGGER_API = "relay.trigger.api"
    RELAY_TRIGGER_FCGI = "relay.trigger.fcgi"
    RELAY_STATUS = "relay.status"
    DEVICE_CONFIG_GET = "device.config.get"
    DEVICE_CONFIG_SET = "device.config.set"
    LOG_DOOR = "log.door"
    LOG_CALL = "log.call"
    KEY_DISCOVERY = "key.discovery"


class CapabilityStatus(enum.Enum):
    """Three-valued capability status.

    * ``SUPPORTED`` — confirmed positive evidence.
    * ``UNSUPPORTED`` — confirmed negative evidence (e.g. ``unsupported
      action`` envelope or ``No handlers for this request``).
    * ``UNKNOWN`` — no positive evidence either way; the conservative
      default returned by :meth:`DeviceCapabilities.status_of` for any
      capability not explicitly listed.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class SchemaShape(enum.Enum):
    """Contact resource schema variants observed across device classes."""

    DOOR_PHONE = "door_phone"
    APARTMENT_BOOK = "apartment_book"


__all__ = ["Capability", "CapabilityStatus", "SchemaShape"]
