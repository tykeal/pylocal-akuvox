# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Async Python library for the Akuvox local HTTP API."""

import importlib.metadata

from pylocal_akuvox.auth import AuthConfig, AuthMethod
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxError,
    AkuvoxParseError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
    AkuvoxValidationError,
)
from pylocal_akuvox.models import (
    AccessSchedule,
    CallLogEntry,
    DeviceConfig,
    DeviceInfo,
    DeviceStatus,
    DoorLogEntry,
    Relay,
    User,
)

_DIST_NAME = "pylocal-akuvox"

try:
    __version__ = importlib.metadata.version(_DIST_NAME)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__: list[str] = [
    "AccessSchedule",
    "AkuvoxAuthenticationError",
    "AkuvoxConnectionError",
    "AkuvoxDevice",
    "AkuvoxDeviceError",
    "AkuvoxError",
    "AkuvoxParseError",
    "AkuvoxRequestError",
    "AkuvoxUnsupportedError",
    "AkuvoxValidationError",
    "AuthConfig",
    "AuthMethod",
    "CallLogEntry",
    "DeviceInfo",
    "DeviceStatus",
    "DoorLogEntry",
    "Relay",
    "DeviceConfig",
    "User",
]
