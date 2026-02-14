# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Exception hierarchy for Akuvox device communication errors."""


class AkuvoxError(Exception):
    """Base exception for all Akuvox-related errors."""


class AkuvoxConnectionError(AkuvoxError):
    """Network or timeout failure communicating with the device."""


class AkuvoxAuthenticationError(AkuvoxError):
    """Authentication rejected by the device (HTTP 401)."""


class AkuvoxRequestError(AkuvoxError):
    """Invalid request parameters (HTTP 400)."""


class AkuvoxDeviceError(AkuvoxError):
    """Device-side error (HTTP 500 or non-zero retcode)."""


class AkuvoxParseError(AkuvoxError):
    """Non-JSON or malformed response from the device."""


class AkuvoxUnsupportedError(AkuvoxError):
    """API endpoint not supported by the device firmware."""


class AkuvoxValidationError(AkuvoxError):
    """Local validation failure before sending request."""
