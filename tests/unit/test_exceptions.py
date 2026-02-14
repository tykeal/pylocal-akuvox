# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for exception hierarchy."""

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


def test_akuvox_error_is_base() -> None:
    """Verify AkuvoxError is the base exception."""
    err = AkuvoxError("test")
    assert isinstance(err, Exception)
    assert str(err) == "test"


def test_connection_error_inherits() -> None:
    """Verify AkuvoxConnectionError inherits from AkuvoxError."""
    err = AkuvoxConnectionError("timeout")
    assert isinstance(err, AkuvoxError)
    assert str(err) == "timeout"


def test_authentication_error_inherits() -> None:
    """Verify AkuvoxAuthenticationError inherits from AkuvoxError."""
    err = AkuvoxAuthenticationError("401")
    assert isinstance(err, AkuvoxError)


def test_request_error_inherits() -> None:
    """Verify AkuvoxRequestError inherits from AkuvoxError."""
    err = AkuvoxRequestError("bad param")
    assert isinstance(err, AkuvoxError)


def test_device_error_inherits() -> None:
    """Verify AkuvoxDeviceError inherits from AkuvoxError."""
    err = AkuvoxDeviceError("internal")
    assert isinstance(err, AkuvoxError)


def test_parse_error_inherits() -> None:
    """Verify AkuvoxParseError inherits from AkuvoxError."""
    err = AkuvoxParseError("not json")
    assert isinstance(err, AkuvoxError)


def test_unsupported_error_inherits() -> None:
    """Verify AkuvoxUnsupportedError inherits from AkuvoxError."""
    err = AkuvoxUnsupportedError("api unsupported")
    assert isinstance(err, AkuvoxError)


def test_validation_error_inherits() -> None:
    """Verify AkuvoxValidationError inherits from AkuvoxError."""
    err = AkuvoxValidationError("invalid pin")
    assert isinstance(err, AkuvoxError)


def test_all_subtypes_distinct() -> None:
    """Verify all exception subtypes are distinct classes."""
    subtypes = [
        AkuvoxConnectionError,
        AkuvoxAuthenticationError,
        AkuvoxRequestError,
        AkuvoxDeviceError,
        AkuvoxParseError,
        AkuvoxUnsupportedError,
        AkuvoxValidationError,
    ]
    assert len(set(subtypes)) == 7


def test_repr_is_actionable() -> None:
    """Verify repr includes class name and message."""
    err = AkuvoxConnectionError("192.168.1.1 timed out")
    assert "AkuvoxConnectionError" in repr(err)
    assert "192.168.1.1 timed out" in repr(err)
