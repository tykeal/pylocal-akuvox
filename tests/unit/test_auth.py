# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for authentication configuration."""

import pytest

from pylocal_akuvox.auth import AuthConfig, AuthMethod
from pylocal_akuvox.exceptions import AkuvoxValidationError


def test_auth_method_values() -> None:
    """Verify AuthMethod enum has expected values."""
    assert AuthMethod.NONE.value == "none"
    assert AuthMethod.ALLOWLIST.value == "allowlist"
    assert AuthMethod.BASIC.value == "basic"
    assert AuthMethod.DIGEST.value == "digest"


def test_auth_method_no_token() -> None:
    """Verify Token is not a valid AuthMethod value."""
    with pytest.raises(ValueError, match="token"):
        AuthMethod("token")


def test_none_auth_no_creds() -> None:
    """Verify NONE auth works without credentials."""
    config = AuthConfig(method=AuthMethod.NONE)
    assert config.method == AuthMethod.NONE
    assert config.username is None
    assert config.password is None


def test_allowlist_auth_no_creds() -> None:
    """Verify ALLOWLIST auth works without credentials."""
    config = AuthConfig(method=AuthMethod.ALLOWLIST)
    assert config.method == AuthMethod.ALLOWLIST


def test_none_rejects_username() -> None:
    """Verify NONE auth rejects credentials."""
    with pytest.raises(AkuvoxValidationError):
        AuthConfig(method=AuthMethod.NONE, username="user")


def test_none_rejects_password() -> None:
    """Verify NONE auth rejects password."""
    with pytest.raises(AkuvoxValidationError):
        AuthConfig(method=AuthMethod.NONE, password="pass")


def test_allowlist_rejects_creds() -> None:
    """Verify ALLOWLIST auth rejects credentials."""
    with pytest.raises(AkuvoxValidationError):
        AuthConfig(method=AuthMethod.ALLOWLIST, username="user", password="pass")


def test_basic_requires_both() -> None:
    """Verify BASIC requires both username and password."""
    with pytest.raises(AkuvoxValidationError):
        AuthConfig(method=AuthMethod.BASIC, username="user")


def test_basic_requires_password() -> None:
    """Verify BASIC requires password."""
    with pytest.raises(AkuvoxValidationError):
        AuthConfig(method=AuthMethod.BASIC)


def test_basic_with_creds() -> None:
    """Verify BASIC auth accepts valid credentials."""
    config = AuthConfig(method=AuthMethod.BASIC, username="admin", password="secret")
    assert config.username == "admin"
    assert config.password == "secret"


def test_digest_requires_both() -> None:
    """Verify DIGEST requires both username and password."""
    with pytest.raises(AkuvoxValidationError):
        AuthConfig(method=AuthMethod.DIGEST, password="pass")


def test_digest_with_creds() -> None:
    """Verify DIGEST auth accepts valid credentials."""
    config = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="secret")
    assert config.method == AuthMethod.DIGEST
