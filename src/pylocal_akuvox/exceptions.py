# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Exception hierarchy for Akuvox device communication errors."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylocal_akuvox.capabilities import Capability


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
    """Operation unsupported by the connected device.

    Carries optional structured fields when raised from the
    capability-aware surfacing layer (the per-method gate in
    :class:`pylocal_akuvox.AkuvoxDevice` and the relay-trigger adapter
    dispatch in :mod:`pylocal_akuvox.capability_adapters`); falls back
    to a message-only form when raised from the legacy HTTP-envelope
    classifier in :mod:`pylocal_akuvox._http` (for example when the
    device returns the well-known ``Api unsupported`` envelope).

    Backward compatibility is preserved: ``AkuvoxUnsupportedError(msg)``
    still constructs an instance with ``.args == (msg,)``,
    ``str(exc) == msg``, and every structured field set to ``None``.

    Attributes:
        capability: The :class:`pylocal_akuvox.Capability` whose
            absence triggered this error, or ``None`` when raised from
            a layer without capability context.
        device_class: The detected device class string
            (e.g. ``"IT83"``), or ``None`` if unrecognised at the time
            of the raise.
        reason: Structured reason code drawn from the closed set
            ``{"capability_missing", "capability_unknown",
            "device_unrecognized", "adapter_missing",
            "envelope_unsupported", None}``. See
            ``specs/008-capability-matrix/contracts/unsupported-error.md``
            for the full taxonomy.

    """

    def __init__(
        self,
        message: str,
        *,
        capability: Capability | None = None,
        device_class: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Construct an unsupported-operation error.

        Args:
            message: Human-readable description of the failure.
            capability: Optional :class:`Capability` that was rejected.
            device_class: Optional device-class string (e.g. ``"IT83"``).
            reason: Optional structured reason code; see class docstring
                for the closed set.

        """
        super().__init__(message)
        self.capability = capability
        self.device_class = device_class
        self.reason = reason


class AkuvoxValidationError(AkuvoxError):
    """Local validation failure before sending request."""
