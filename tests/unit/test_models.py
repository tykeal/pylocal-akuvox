# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for data models."""

import pytest

from pylocal_akuvox.models import DeviceInfo, DeviceStatus, Relay


def test_device_info_from_api_response() -> None:
    """Verify DeviceInfo maps PascalCase API fields to snake_case."""
    data = {
        "Status": {
            "Model": "E16C",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "1.2.3",
            "HardwareVersion": "4.5.6",
            "Uptime": "10 days",
            "WebLang": "0",
        }
    }
    info = DeviceInfo.from_api_response(data)
    assert info.model == "E16C"
    assert info.mac_address == "AA:BB:CC:DD:EE:FF"
    assert info.firmware_version == "1.2.3"
    assert info.hardware_version == "4.5.6"
    assert info.uptime == "10 days"
    assert info.web_language == 0


def test_device_info_optional_fields() -> None:
    """Verify DeviceInfo optional fields default to None."""
    data = {
        "Status": {
            "Model": "E16C",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "1.2.3",
            "HardwareVersion": "4.5.6",
        }
    }
    info = DeviceInfo.from_api_response(data)
    assert info.uptime is None
    assert info.web_language is None


def test_device_info_invalid_web_language() -> None:
    """Verify invalid WebLang value defaults to None."""
    data = {
        "Status": {
            "Model": "E16C",
            "MAC": "00:11:22:33:44:55",
            "FirmwareVersion": "1.2.3",
            "HardwareVersion": "4.5.6",
            "WebLang": "invalid",
        }
    }
    info = DeviceInfo.from_api_response(data)
    assert info.web_language is None


def test_device_info_non_numeric_web_language_type() -> None:
    """Verify non-numeric WebLang type defaults to None."""
    data = {
        "Status": {
            "Model": "E16C",
            "MAC": "00:11:22:33:44:55",
            "FirmwareVersion": "1.2.3",
            "HardwareVersion": "4.5.6",
            "WebLang": ["not", "a", "number"],
        }
    }
    info = DeviceInfo.from_api_response(data)
    assert info.web_language is None


def test_device_status_from_api_response() -> None:
    """Verify DeviceStatus maps SystemTime and UpTime."""
    data = {"SystemTime": 1700000000, "UpTime": 86400}
    status = DeviceStatus.from_api_response(data)
    assert status.unix_time == 1700000000
    assert status.uptime == 86400


def test_relay_from_api_response() -> None:
    """Verify Relay maps number and state fields."""
    data = {"number": 1, "state": "open"}
    relay = Relay.from_api_response(data)
    assert relay.number == 1
    assert relay.state == "open"


def test_relay_optional_state() -> None:
    """Verify Relay state defaults to None."""
    data = {"number": 2}
    relay = Relay.from_api_response(data)
    assert relay.number == 2
    assert relay.state is None


def test_device_info_is_frozen() -> None:
    """Verify DeviceInfo is immutable."""
    data = {
        "Status": {
            "Model": "E16C",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "1.2.3",
            "HardwareVersion": "4.5.6",
        }
    }
    info = DeviceInfo.from_api_response(data)
    with pytest.raises(AttributeError):
        info.model = "X1"  # type: ignore[misc]


def test_device_status_is_frozen() -> None:
    """Verify DeviceStatus is immutable."""
    data = {"SystemTime": 100, "UpTime": 200}
    status = DeviceStatus.from_api_response(data)
    with pytest.raises(AttributeError):
        status.unix_time = 999  # type: ignore[misc]


def test_device_info_missing_required_field() -> None:
    """Verify missing required field raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"Status": {"Model": "E16C"}}
    with pytest.raises(AkuvoxParseError, match="Missing required field"):
        DeviceInfo.from_api_response(data)


def test_device_status_missing_required_field() -> None:
    """Verify missing required field raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"SystemTime": 100}
    with pytest.raises(AkuvoxParseError, match="Missing required field"):
        DeviceStatus.from_api_response(data)


def test_relay_missing_required_field() -> None:
    """Verify missing required field raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"state": "open"}
    with pytest.raises(AkuvoxParseError, match="Missing required field"):
        Relay.from_api_response(data)


def test_device_info_null_status_raises_parse_error() -> None:
    """Verify null Status value raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"Status": None}
    with pytest.raises(AkuvoxParseError, match="Expected 'Status' to be a dict"):
        DeviceInfo.from_api_response(data)
