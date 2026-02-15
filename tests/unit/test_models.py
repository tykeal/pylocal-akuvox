# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for data models."""

import pytest

from pylocal_akuvox.models import (
    AccessSchedule,
    CallLogEntry,
    DeviceInfo,
    DeviceStatus,
    DoorLogEntry,
    Relay,
    User,
)


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


def test_device_status_invalid_type_raises_parse_error() -> None:
    """Verify non-integer SystemTime raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"SystemTime": "not-a-number", "UpTime": 100}
    with pytest.raises(AkuvoxParseError, match="Invalid type"):
        DeviceStatus.from_api_response(data)


def test_device_status_none_type_raises_parse_error() -> None:
    """Verify None SystemTime raises AkuvoxParseError via TypeError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"SystemTime": None, "UpTime": 100}
    with pytest.raises(AkuvoxParseError, match="Invalid type"):
        DeviceStatus.from_api_response(data)


def test_relay_invalid_number_type_raises_parse_error() -> None:
    """Verify non-integer relay number raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"number": "abc", "state": "open"}
    with pytest.raises(AkuvoxParseError, match="Invalid type for relay"):
        Relay.from_api_response(data)


def test_relay_none_number_raises_parse_error() -> None:
    """Verify None relay number raises AkuvoxParseError via TypeError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"number": None, "state": "open"}
    with pytest.raises(AkuvoxParseError, match="Invalid type for relay"):
        Relay.from_api_response(data)


# -- T025: User model tests --


def test_user_from_api_response_all_fields() -> None:
    """Verify User maps all PascalCase API fields to snake_case."""
    data = {
        "ID": "42",
        "Name": "Alice",
        "UserID": "2001",
        "PrivatePIN": "1234",
        "CardCode": "ABCD1234",
        "WebRelay": "1",
        "ScheduleRelay": "1001-1;",
        "LiftFloorNum": "3",
        "Type": "ordinary",
        "Source": "web",
        "SourceType": "Local",
    }
    user = User.from_api_response(data)
    assert user.id == "42"
    assert user.name == "Alice"
    assert user.user_id == "2001"
    assert user.private_pin == "1234"
    assert user.card_code == "ABCD1234"
    assert user.web_relay == "1"
    assert user.schedule_relay == "1001-1;"
    assert user.lift_floor_num == "3"
    assert user.user_type == "ordinary"
    assert user.source == "web"
    assert user.source_type == "Local"


def test_user_from_api_response_optional_defaults() -> None:
    """Verify User optional fields default to None."""
    data = {
        "ID": "1",
        "Name": "Bob",
        "UserID": "2002",
        "WebRelay": "0",
        "ScheduleRelay": "1001-1;",
    }
    user = User.from_api_response(data)
    assert user.private_pin is None
    assert user.card_code is None
    assert user.lift_floor_num is None
    assert user.user_type is None
    assert user.source is None
    assert user.source_type is None


def test_user_from_api_response_missing_name_raises() -> None:
    """Verify missing Name raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"ID": "1", "UserID": "2002", "WebRelay": "0", "ScheduleRelay": "1001-1;"}
    with pytest.raises(AkuvoxParseError, match="Missing required field"):
        User.from_api_response(data)


def test_user_from_api_response_missing_user_id_raises() -> None:
    """Verify missing UserID raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    data = {"ID": "1", "Name": "Bob", "WebRelay": "0", "ScheduleRelay": "1001-1;"}
    with pytest.raises(AkuvoxParseError, match="Missing required field"):
        User.from_api_response(data)


def test_user_is_frozen() -> None:
    """Verify User dataclass is immutable."""
    data = {
        "ID": "1",
        "Name": "Charlie",
        "UserID": "2003",
        "WebRelay": "0",
        "ScheduleRelay": "1001-1;",
    }
    user = User.from_api_response(data)
    with pytest.raises(AttributeError):
        user.name = "Dave"  # type: ignore[misc]


def test_user_to_api_payload_add() -> None:
    """Verify to_api_payload produces correct PascalCase dict for add."""
    data = {
        "ID": "1",
        "Name": "Alice",
        "UserID": "2001",
        "PrivatePIN": "1234",
        "WebRelay": "0",
        "ScheduleRelay": "1001-1;",
        "LiftFloorNum": "0",
    }
    user = User.from_api_response(data)
    payload = user.to_api_payload()
    assert payload["Name"] == "Alice"
    assert payload["UserID"] == "2001"
    assert payload["PrivatePIN"] == "1234"
    assert payload["WebRelay"] == "0"
    assert payload["ScheduleRelay"] == "1001-1;"
    assert payload["LiftFloorNum"] == "0"


def test_user_to_api_payload_excludes_none() -> None:
    """Verify to_api_payload excludes None-valued optional fields."""
    data = {
        "Name": "Bob",
        "UserID": "2002",
        "WebRelay": "0",
        "ScheduleRelay": "1001-1;",
    }
    user = User.from_api_response(data)
    payload = user.to_api_payload()
    assert "ID" not in payload
    assert "PrivatePIN" not in payload
    assert "CardCode" not in payload
    assert "LiftFloorNum" not in payload


def test_user_to_api_payload_all_optional_fields() -> None:
    """Verify to_api_payload includes card_code and user_type when set."""
    data = {
        "ID": "1",
        "Name": "Alice",
        "UserID": "2001",
        "PrivatePIN": "1234",
        "CardCode": "RFID999",
        "WebRelay": "0",
        "ScheduleRelay": "1001-1;",
        "LiftFloorNum": "3",
        "Type": "admin",
        "Source": "web",
        "SourceType": "Local",
    }
    user = User.from_api_response(data)
    payload = user.to_api_payload()
    assert payload["ID"] == "1"
    assert payload["CardCode"] == "RFID999"
    assert payload["Type"] == "admin"
    assert payload["LiftFloorNum"] == "3"


def test_user_from_api_response_missing_web_relay() -> None:
    """Verify from_api_response handles missing WebRelay gracefully."""
    data = {
        "ID": "5",
        "Name": "Cloud User",
        "UserID": "9001",
        "ScheduleRelay": "40313-1",
        "SourceType": "2",
    }
    user = User.from_api_response(data)
    assert user.web_relay is None
    assert user.name == "Cloud User"


def test_user_to_api_payload_excludes_web_relay_when_none() -> None:
    """Verify to_api_payload omits WebRelay when it is None."""
    data = {
        "Name": "Cloud User",
        "UserID": "9001",
        "ScheduleRelay": "40313-1",
    }
    user = User.from_api_response(data)
    payload = user.to_api_payload()
    assert "WebRelay" not in payload


# === AccessSchedule model tests (T036) ===


def test_access_schedule_from_api_response_all_fields() -> None:
    """Verify AccessSchedule maps all PascalCase fields."""
    data = {
        "ID": "1001",
        "Name": "Weekday Access",
        "Type": "1",
        "DateStart": "20260101",
        "DateEnd": "20261231",
        "TimeStart": "08:00",
        "TimeEnd": "18:00",
        "Week": "12345",
        "Daily": "08:00-18:00",
        "DisplayID": "D1",
        "SourceType": "1",
        "Mode": "1",
        "Sun": "0",
        "Mon": "1",
        "Tue": "1",
        "Wed": "1",
        "Thur": "1",
        "Fri": "1",
        "Sat": "0",
    }
    schedule = AccessSchedule.from_api_response(data)
    assert schedule.id == "1001"
    assert schedule.name == "Weekday Access"
    assert schedule.schedule_type == "1"
    assert schedule.date_start == "20260101"
    assert schedule.date_end == "20261231"
    assert schedule.time_start == "08:00"
    assert schedule.time_end == "18:00"
    assert schedule.week == "12345"
    assert schedule.daily == "08:00-18:00"
    assert schedule.display_id == "D1"
    assert schedule.source_type == "1"
    assert schedule.mode == "1"
    assert schedule.sun == "0"
    assert schedule.mon == "1"
    assert schedule.tue == "1"
    assert schedule.wed == "1"
    assert schedule.thur == "1"
    assert schedule.fri == "1"
    assert schedule.sat == "0"


def test_access_schedule_from_api_response_minimal() -> None:
    """Verify AccessSchedule with only required Type field."""
    data = {"Type": "0"}
    schedule = AccessSchedule.from_api_response(data)
    assert schedule.schedule_type == "0"
    assert schedule.id is None
    assert schedule.name is None
    assert schedule.week is None
    assert schedule.daily is None
    assert schedule.sun is None


def test_access_schedule_missing_type_raises() -> None:
    """Verify missing Type raises AkuvoxParseError."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    with pytest.raises(AkuvoxParseError, match="Missing required field.*Type"):
        AccessSchedule.from_api_response({"Name": "Test"})


def test_access_schedule_to_api_payload() -> None:
    """Verify to_api_payload includes non-None fields."""
    schedule = AccessSchedule(
        schedule_type="1",
        id="1001",
        name="Test",
        week="12345",
        daily="08:00-18:00",
    )
    payload = schedule.to_api_payload()
    assert payload == {
        "Type": "1",
        "ID": "1001",
        "Name": "Test",
        "Week": "12345",
        "Daily": "08:00-18:00",
    }


def test_access_schedule_to_api_payload_minimal() -> None:
    """Verify to_api_payload with only required fields."""
    schedule = AccessSchedule(schedule_type="2")
    payload = schedule.to_api_payload()
    assert payload == {"Type": "2"}


def test_access_schedule_to_api_payload_all_fields() -> None:
    """Verify to_api_payload includes date, time, and day fields."""
    schedule = AccessSchedule(
        schedule_type="0",
        id="100",
        name="Full",
        date_start="20260101",
        date_end="20261231",
        time_start="08:00",
        time_end="18:00",
        week="12345",
        daily="08:00-18:00",
        display_id="D1",
        source_type="1",
        mode="1",
        sun="0",
        mon="1",
        tue="1",
        wed="1",
        thur="1",
        fri="1",
        sat="0",
    )
    payload = schedule.to_api_payload()
    assert payload["DateStart"] == "20260101"
    assert payload["DateEnd"] == "20261231"
    assert payload["TimeStart"] == "08:00"
    assert payload["TimeEnd"] == "18:00"
    assert payload["Week"] == "12345"
    assert payload["Daily"] == "08:00-18:00"
    assert payload["DisplayID"] == "D1"
    assert payload["SourceType"] == "1"
    assert payload["Mode"] == "1"
    assert payload["Sun"] == "0"
    assert payload["Mon"] == "1"
    assert payload["Tue"] == "1"
    assert payload["Wed"] == "1"
    assert payload["Thur"] == "1"
    assert payload["Fri"] == "1"
    assert payload["Sat"] == "0"


def test_access_schedule_day_fields_mapped() -> None:
    """Verify individual day fields (Sun-Sat) are mapped."""
    data = {
        "Type": "1",
        "Sun": "1",
        "Mon": "0",
        "Tue": "1",
        "Wed": "0",
        "Thur": "1",
        "Fri": "0",
        "Sat": "1",
    }
    schedule = AccessSchedule.from_api_response(data)
    assert schedule.sun == "1"
    assert schedule.mon == "0"
    assert schedule.tue == "1"
    assert schedule.wed == "0"
    assert schedule.thur == "1"
    assert schedule.fri == "0"
    assert schedule.sat == "1"


# -- T042: DoorLogEntry model tests --


def test_door_log_entry_from_api_response() -> None:
    """Verify DoorLogEntry maps PascalCase API fields."""
    data = {
        "ID": "42",
        "Date": "2026-01-15",
        "Time": "09:30:00",
        "Name": "Alice",
        "Code": "1234",
        "Type": "PIN",
        "Relay": "1",
        "Status": "Succ",
    }
    entry = DoorLogEntry.from_api_response(data)
    assert entry.id == "42"
    assert entry.date == "2026-01-15"
    assert entry.time == "09:30:00"
    assert entry.name == "Alice"
    assert entry.code == "1234"
    assert entry.door_type == "PIN"
    assert entry.relay == "1"
    assert entry.status == "Succ"
    assert entry.access_mode is None


def test_door_log_entry_with_access_mode() -> None:
    """Verify DoorLogEntry maps optional AccessMode field."""
    data = {
        "ID": "43",
        "Date": "2026-01-15",
        "Time": "10:00:00",
        "Name": "Bob",
        "Code": "5678",
        "Type": "Card",
        "Relay": "2",
        "Status": "Failed",
        "AccessMode": "1",
    }
    entry = DoorLogEntry.from_api_response(data)
    assert entry.access_mode == "1"
    assert entry.status == "Failed"


def test_door_log_entry_without_relay() -> None:
    """Verify DoorLogEntry works when Relay is absent (e.g. X916)."""
    data = {
        "ID": "44",
        "Date": "2026-01-15",
        "Time": "11:00:00",
        "Name": "Charlie",
        "Code": "Unknown",
        "Type": "Face",
        "Status": "Failed",
    }
    entry = DoorLogEntry.from_api_response(data)
    assert entry.relay is None
    assert entry.access_mode is None


def test_door_log_entry_missing_required_field() -> None:
    """Verify AkuvoxParseError on missing required field."""
    data = {
        "ID": "42",
        "Date": "2026-01-15",
        "Time": "09:30:00",
        # Name missing
        "Code": "1234",
        "Type": "PIN",
        "Relay": "1",
        "Status": "Succ",
    }
    from pylocal_akuvox.exceptions import AkuvoxParseError

    with pytest.raises(AkuvoxParseError, match="Name"):
        DoorLogEntry.from_api_response(data)


# -- T042: CallLogEntry model tests --


def test_call_log_entry_from_api_response() -> None:
    """Verify CallLogEntry maps PascalCase API fields."""
    data = {
        "ID": "100",
        "Date": "2026-01-15",
        "Time": "14:30:00",
        "Name": "Front Door",
        "Type": "Received",
        "LocalIdentity": "sip:100@192.168.1.1",
        "Num": "3",
    }
    entry = CallLogEntry.from_api_response(data)
    assert entry.id == "100"
    assert entry.date == "2026-01-15"
    assert entry.time == "14:30:00"
    assert entry.name == "Front Door"
    assert entry.call_type == "Received"
    assert entry.local_identity == "sip:100@192.168.1.1"
    assert entry.count == "3"
    assert entry.pic_url is None


def test_call_log_entry_with_pic_url() -> None:
    """Verify CallLogEntry maps optional PicUrl field."""
    data = {
        "ID": "101",
        "Date": "2026-01-15",
        "Time": "15:00:00",
        "Name": "Back Door",
        "Type": "Missed",
        "LocalIdentity": "sip:200@192.168.1.1",
        "Num": "1",
        "PicUrl": "http://device/pics/101.jpg",
    }
    entry = CallLogEntry.from_api_response(data)
    assert entry.pic_url == "http://device/pics/101.jpg"
    assert entry.call_type == "Missed"


def test_call_log_entry_missing_required_field() -> None:
    """Verify AkuvoxParseError on missing required field."""
    data = {
        "ID": "100",
        "Date": "2026-01-15",
        "Time": "14:30:00",
        "Name": "Front Door",
        # Type missing
        "LocalIdentity": "sip:100@192.168.1.1",
        "Num": "3",
    }
    from pylocal_akuvox.exceptions import AkuvoxParseError

    with pytest.raises(AkuvoxParseError, match="Type"):
        CallLogEntry.from_api_response(data)


def test_call_log_entry_all_call_types() -> None:
    """Verify all documented call type values are accepted."""
    base = {
        "ID": "1",
        "Date": "2026-01-15",
        "Time": "12:00:00",
        "Name": "Test",
        "LocalIdentity": "sip:1@host",
        "Num": "1",
    }
    for call_type in ("Dialed", "Received", "Missed", "Forwarded", "Unknow"):
        entry = CallLogEntry.from_api_response({**base, "Type": call_type})
        assert entry.call_type == call_type


def test_door_log_entry_status_values() -> None:
    """Verify both Succ and Failed status values are accepted."""
    base = {
        "ID": "1",
        "Date": "2026-01-15",
        "Time": "12:00:00",
        "Name": "Test",
        "Code": "0000",
        "Type": "PIN",
        "Relay": "1",
    }
    succ = DoorLogEntry.from_api_response({**base, "Status": "Succ"})
    assert succ.status == "Succ"
    fail = DoorLogEntry.from_api_response({**base, "Status": "Failed"})
    assert fail.status == "Failed"
