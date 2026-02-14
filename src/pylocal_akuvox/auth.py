# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Authentication configuration for Akuvox device connections."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from pylocal_akuvox.exceptions import AkuvoxValidationError


class AuthMethod(enum.Enum):
    """Supported authentication methods for Akuvox devices."""

    NONE = "none"
    ALLOWLIST = "allowlist"
    BASIC = "basic"
    DIGEST = "digest"


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration for connecting to an Akuvox device."""

    method: AuthMethod
    username: str | None = None
    password: str | None = None

    def __post_init__(self) -> None:
        """Validate authentication configuration."""
        if self.method in (AuthMethod.NONE, AuthMethod.ALLOWLIST):
            if self.username is not None or self.password is not None:
                msg = f"{self.method.value} auth must not include credentials"
                raise AkuvoxValidationError(msg)
        if self.method in (AuthMethod.BASIC, AuthMethod.DIGEST):
            if not self.username or not self.password:
                msg = f"{self.method.value} auth requires both username and password"
                raise AkuvoxValidationError(msg)
