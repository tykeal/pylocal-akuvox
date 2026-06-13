# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the example MVP diagnostic runner helpers."""

from __future__ import annotations

import json
from typing import Any, cast

import examples.mvp_test as mvp_test
import pytest

from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
)
from pylocal_akuvox.models import CallLogEntry, Contact, DeviceInfo, DoorLogEntry, User


class _FakeResponse:
    """Small response double for diagnostic response-handler tests."""

    def __init__(self, status: int, body: str) -> None:
        """Initialize the fake response status and body text."""
        self.status = status
        self._body = body

    async def text(self) -> str:
        """Return the configured response body."""
        return self._body


async def _fake_original_success_handler(resp: _FakeResponse) -> dict[str, Any]:
    """Return the response data like the library handler would on success."""
    body = json.loads(await resp.text())
    data = body.get("data", {})
    return cast("dict[str, Any]", data if isinstance(data, dict) else {})


async def _fake_original_device_error_handler(resp: _FakeResponse) -> dict[str, Any]:
    """Raise a device error like the library handler would on retcode failure."""
    body = json.loads(await resp.text())
    message = body.get("message", body.get("retmsg", ""))
    if not isinstance(message, str):
        message = str(message) if message is not None else ""
    raise AkuvoxDeviceError(message)


async def _fake_original_unsupported_handler(resp: _FakeResponse) -> dict[str, Any]:
    """Raise unsupported when the library handler would catch that message."""
    await resp.text()
    raise AkuvoxDeviceError("Api unsupported")


class _FakePrintDevice:
    """Device double that returns sample PII for stdout redaction tests."""

    async def get_info(self) -> DeviceInfo:
        """Return device identity with a sample MAC address."""
        return DeviceInfo(
            model="X916",
            mac_address="00:11:22:33:44:55",
            firmware_version="916.30.10.114",
            hardware_version="1.0",
        )

    async def list_users(self, *, page: int | None = None) -> list[User]:
        """Return one user containing sample private values."""
        return [
            User(
                id="42",
                name="Alice Resident",
                user_id="user-1234",
                private_pin="123456",
                schedule_relay="1001-1",
            )
        ]

    async def list_contacts(self, *, page: int | None = None) -> list[Contact]:
        """Return one contact containing sample private values."""
        return [
            Contact(
                id="7",
                name="Bob Visitor",
                phone="555-0100",
                group="Default",
            )
        ]

    async def get_door_logs(self, *, page: int | None = None) -> list[DoorLogEntry]:
        """Return one door log containing a sample private name."""
        return [
            DoorLogEntry(
                id="99",
                date="2026-06-13",
                time="08:00",
                name="Carol Door",
                code="card",
                door_type="1",
                status="OK",
            )
        ]

    async def get_call_logs(self, *, page: int | None = None) -> list[CallLogEntry]:
        """Return one call log containing a sample private name."""
        return [
            CallLogEntry(
                id="100",
                date="2026-06-13",
                time="08:01",
                name="Dave Caller",
                call_type="incoming",
                local_identity="100",
                count="1",
            )
        ]


async def _successful_step() -> str:
    """Return a value from a successful diagnostic step."""
    return "ok"


async def _device_error_step() -> None:
    """Raise a non-fatal device error."""
    raise AkuvoxDeviceError("No handlers for this request")


async def _skipped_step() -> None:
    """Raise an expected diagnostic skip."""
    raise mvp_test.TestStepSkipped("missing prerequisite")


async def _connection_error_step() -> None:
    """Raise a fatal connection error."""
    raise AkuvoxConnectionError("connection refused")


async def _authentication_error_step() -> None:
    """Raise a fatal authentication error."""
    raise AkuvoxAuthenticationError("bad credentials")


async def test_run_step_records_success() -> None:
    """Run a successful step and record its label."""
    results = mvp_test.TestResults()

    value = await mvp_test.run_step(results, "SUCCESS", _successful_step())

    assert value == "ok"
    assert results.passed == ["SUCCESS"]
    assert results.failed == []
    assert results.skipped == []


async def test_run_step_records_non_fatal_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Record device errors as failures without raising."""
    results = mvp_test.TestResults()

    await mvp_test.run_step(results, "LIST USERS", _device_error_step())

    assert results.failed == [("LIST USERS", "No handlers for this request")]
    assert "✗ LIST USERS: No handlers for this request" in capsys.readouterr().out


async def test_run_step_records_skip(capsys: pytest.CaptureFixture[str]) -> None:
    """Record expected skips separately from failures."""
    results = mvp_test.TestResults()

    await mvp_test.run_step(results, "SET DEVICE CONFIG", _skipped_step())

    assert results.skipped == [("SET DEVICE CONFIG", "missing prerequisite")]
    output = capsys.readouterr().out
    assert "⊘ SET DEVICE CONFIG skipped: missing prerequisite" in output


async def test_run_step_reraises_connection_errors() -> None:
    """Abort on connection failures."""
    results = mvp_test.TestResults()

    with pytest.raises(AkuvoxConnectionError):
        await mvp_test.run_step(results, "FATAL", _connection_error_step())

    assert results.total == 0


async def test_run_step_reraises_authentication_errors() -> None:
    """Abort on authentication failures."""
    results = mvp_test.TestResults()

    with pytest.raises(AkuvoxAuthenticationError):
        await mvp_test.run_step(results, "FATAL", _authentication_error_step())

    assert results.total == 0


def test_skip_step_records_dependency_skip(capsys: pytest.CaptureFixture[str]) -> None:
    """Record dependent steps skipped by the write-test chain."""
    results = mvp_test.TestResults()

    mvp_test.skip_step(results, "DELETE USER", "requires internal ID from ADD USER")

    assert results.skipped == [
        ("DELETE USER", "requires internal ID from ADD USER"),
    ]
    assert (
        "⊘ DELETE USER skipped: requires internal ID from ADD USER"
        in capsys.readouterr().out
    )


def test_summary_lists_all_result_buckets(capsys: pytest.CaptureFixture[str]) -> None:
    """Print counts and labels for passed, failed, and skipped steps."""
    results = mvp_test.TestResults()
    results.mark_passed("GET DEVICE INFO")
    results.mark_failed("LIST USERS", "No handlers for this request")
    results.mark_skipped("DELETE USER", "requires ADD USER")

    results.print_summary()

    output = capsys.readouterr().out
    assert "Total:      3" in output
    assert "✓ Passed:   1" in output
    assert "✗ Failed:   1" in output
    assert "⊘ Skipped:  1" in output
    assert "- GET DEVICE INFO" in output
    assert "- LIST USERS: No handlers for this request" in output
    assert "- DELETE USER: requires ADD USER" in output


def test_summary_prints_capability_matrix_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Print matrix-friendly status and observed read fields."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)
    diagnostics.begin_test("LIST USERS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/user/get",
        data=None,
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text='{"retcode":0,"message":"OK","data":{"item":[{"ID":"1",'
        '"Name":"Alice","Schedule":"1-1"}]}}',
        body=None,
        retcode=0,
        retmsg="OK",
        data={"item": [{"ID": "1", "Name": "Alice", "Schedule": "1-1"}]},
    )
    diagnostics.finish_test("passed")
    results.mark_passed("LIST USERS")

    results.print_summary()

    output = capsys.readouterr().out
    assert "Capability matrix data:" in output
    assert "capability=list_users status=supported endpoint=/api/user/get" in output
    assert "observed_fields=ID,Name,Schedule" in output
    action_not_supported = "".join(("unsup", "port action"))
    diagnostics.begin_test("ADD CONTACT")
    diagnostics.begin_http_event(
        method="POST",
        endpoint="/api/contact/set",
        data={"data": {"item": [{"Name": "Test", "Phone": "555"}]}},
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text=f'{{"retcode":-1,"retmsg":"{action_not_supported}"}}',
        body={"retcode": -1, "retmsg": action_not_supported},
        retcode=-1,
        retmsg=action_not_supported,
        data={},
    )
    diagnostics.finish_test("failed", action_not_supported)

    results.print_summary()

    output = capsys.readouterr().out
    assert (
        "capability=add_contact status=unsupported endpoint=/api/contact/set" in output
    )
    assert (
        f'failure_shape=http=200 retcode=-1 retmsg="{action_not_supported}"' in output
    )


def test_failure_signature_quotes_single_line_tokens() -> None:
    """Keep failure-shape summary tokens escaped and single-line."""
    event = mvp_test.DiagnosticHttpEvent(
        method="GET",
        endpoint="/api/user/get",
        http_status=200,
        retcode=-1,
        retmsg='bad "field"\nsecond line',
        exception_class="AkuvoxDeviceError",
        exception_message='bad "field" \\ path',
    )

    signature = event.failure_signature()

    assert 'retmsg="bad \\"field\\""' in signature
    assert 'exception="AkuvoxDeviceError: bad \\"field\\" \\\\ path"' in signature
    assert "\n" not in signature


async def test_diagnostic_handler_omits_successful_response_values() -> None:
    """Capture successful read schemas without serializing private values."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("LIST USERS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/user/get",
        data=None,
        params=None,
    )
    body = {
        "retcode": 0,
        "message": "OK",
        "data": {
            "item": [
                {
                    "ID": "42",
                    "Name": "Alice Resident",
                    "PrivatePIN": "123456",
                    "Phone": "555-0100",
                    "CardCode": "RFID-SECRET",
                    "Schedule": "1001-1",
                }
            ]
        },
    }
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_success_handler),
    )

    await handler(cast("Any", _FakeResponse(200, json.dumps(body))))
    diagnostics.finish_test("passed")

    report_text = json.dumps(diagnostics.to_json())
    assert "body_snippet" not in report_text
    for private_value in (
        "42",
        "Alice Resident",
        "123456",
        "555-0100",
        "RFID-SECRET",
        "1001-1",
    ):
        assert private_value not in report_text
    for key in ("ID", "Name", "PrivatePIN", "Phone", "CardCode", "Schedule"):
        assert key in report_text


async def test_redact_stdout_hides_printed_private_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Redact sample PII values from the script's stdout print paths."""
    device = cast("Any", _FakePrintDevice())

    await mvp_test.test_get_info(device, redact_stdout=True)
    await mvp_test.test_list_users(device, redact_stdout=True)
    await mvp_test.test_list_contacts(device, redact_stdout=True)
    await mvp_test.test_get_door_logs(device, redact_stdout=True)
    await mvp_test.test_get_call_logs(device, redact_stdout=True)

    output = capsys.readouterr().out
    assert mvp_test._REDACTED_VALUE in output
    for private_value in (
        "00:11:22:33:44:55",
        "Alice Resident",
        "user-1234",
        "123456",
        "Bob Visitor",
        "555-0100",
        "Carol Door",
        "Dave Caller",
    ):
        assert private_value not in output
    for label in ("MAC:", "Name=", "UserID=", "PIN=", "Phone="):
        assert label in output


async def test_stdout_redaction_is_default_off(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep interactive stdout values visible unless redaction is requested."""
    device = cast("Any", _FakePrintDevice())

    await mvp_test.test_get_info(device)
    await mvp_test.test_list_users(device)
    await mvp_test.test_list_contacts(device)
    await mvp_test.test_get_door_logs(device)
    await mvp_test.test_get_call_logs(device)

    output = capsys.readouterr().out
    for private_value in (
        "00:11:22:33:44:55",
        "Alice Resident",
        "user-1234",
        "123456",
        "Bob Visitor",
        "555-0100",
        "Carol Door",
        "Dave Caller",
    ):
        assert private_value in output


def test_redaction_helper_default_off_keeps_nested_values() -> None:
    """Keep nested values visible when redaction is disabled."""
    value = {"item": [{"Name": "Alice Resident", "PrivatePIN": "123456"}]}

    displayed = mvp_test._display_value("payload", value, redact_stdout=False)

    assert "Alice Resident" in displayed
    assert "123456" in displayed


async def test_diagnostic_handler_redacts_failed_response_values() -> None:
    """Redact sensitive values from failed response body snippets."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("ADD USER")
    diagnostics.begin_http_event(
        method="POST",
        endpoint="/api/user/set",
        data={"data": {"item": [{"Name": "Alice Resident"}]}},
        params=None,
    )
    body = {
        "retcode": -1,
        "retmsg": "bad field",
        "data": {
            "item": [
                {
                    "Name": "Alice Resident",
                    "MAC": "00:11:22:33:44:55",
                    "PrivatePIN": "123456",
                    "Phone": "555-0100",
                    "CardCode": "RFID-SECRET",
                }
            ]
        },
    }
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_device_error_handler),
    )

    with pytest.raises(AkuvoxDeviceError):
        await handler(cast("Any", _FakeResponse(200, json.dumps(body))))

    report_text = json.dumps(diagnostics.to_json())
    assert mvp_test._REDACTED_VALUE in report_text
    for private_value in (
        "Alice Resident",
        "00:11:22:33:44:55",
        "123456",
        "555-0100",
        "RFID-SECRET",
    ):
        assert private_value not in report_text


async def test_missing_envelope_error_omits_response_values() -> None:
    """Avoid leaking response values in parse-error diagnostics."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("LIST USERS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/user/get",
        data=None,
        params=None,
    )
    body = {
        "Name": "Alice Resident",
        "Phone": "555-0100",
        "PrivatePIN": "123456",
    }
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_success_handler),
    )

    with pytest.raises(AkuvoxParseError) as exc_info:
        await handler(cast("Any", _FakeResponse(200, json.dumps(body))))
    diagnostics.record_exception(exc_info.value)
    diagnostics.finish_test("failed", str(exc_info.value))

    report_text = json.dumps(diagnostics.to_json())
    assert "Name" in report_text
    assert "Phone" in report_text
    assert "PrivatePIN" in report_text
    for private_value in ("Alice Resident", "555-0100", "123456"):
        assert private_value not in report_text


def test_failure_body_excerpt_is_clipped() -> None:
    """Clip long failed response snippets to the configured limit."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )
    long_value = "x" * 10_000

    diagnostics.record_http_response(
        status=200,
        body_text=json.dumps({"retcode": -1, "retmsg": "boom", "data": long_value}),
        body={"retcode": -1, "retmsg": "boom", "data": long_value},
        retcode=-1,
        retmsg="boom",
        data={},
    )

    tests = cast("list[dict[str, Any]]", diagnostics.to_json()["tests"])
    failure_shape = cast("dict[str, Any]", tests[0]["failure_shape"])
    body_snippet = cast("str", failure_shape["body_snippet"])
    assert len(body_snippet) <= mvp_test._BODY_SNIPPET_CHARS


def test_scalar_failure_body_excerpt_omits_value() -> None:
    """Omit scalar JSON failure values because they have no redactable keys."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=500,
        body_text='"Alice Resident"',
        body="Alice Resident",
        retcode=None,
        retmsg=None,
        data={},
    )

    report_text = json.dumps(diagnostics.to_json())
    assert "Alice Resident" not in report_text
    assert mvp_test._SCALAR_JSON_BODY_OMITTED in report_text


def test_unknown_success_status_body_gets_safe_excerpt() -> None:
    """Emit a privacy-safe snippet for HTTP 200 responses with no retcode."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=200,
        body_text="not-json Alice Resident",
        body=None,
        retcode=None,
        retmsg=None,
        data={},
    )

    report_text = json.dumps(diagnostics.to_json())
    assert "Alice Resident" not in report_text
    assert mvp_test._NON_JSON_BODY_OMITTED in report_text


def test_scalar_list_failure_body_excerpt_redacts_values() -> None:
    """Redact scalar values nested inside failed JSON response lists."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=500,
        body_text='{"data":["Alice Resident"],"retmsg":"boom"}',
        body={"data": ["Alice Resident"], "retmsg": "boom"},
        retcode=None,
        retmsg="boom",
        data={},
    )

    report_text = json.dumps(diagnostics.to_json())
    assert "Alice Resident" not in report_text
    assert mvp_test._REDACTED_VALUE in report_text


def test_positive_retcode_omits_body_excerpt() -> None:
    """Treat non-negative retcodes as success for body snippet capture."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET STATUS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/system/status",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=200,
        body_text='{"retcode":1,"message":"OK","data":{"Name":"Alice"}}',
        body={"retcode": 1, "message": "OK", "data": {"Name": "Alice"}},
        retcode=1,
        retmsg="OK",
        data={"Name": "Alice"},
    )
    diagnostics.finish_test("passed")

    report_text = json.dumps(diagnostics.to_json())
    assert "body_snippet" not in report_text
    assert "Alice" not in report_text


async def test_unsupported_message_delegates_to_original_handler() -> None:
    """Let the library classify unsupported messages even with retcode >= 0."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET RELAY STATUS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/relay/status",
        data=None,
        params=None,
    )
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_unsupported_handler),
    )
    body = {"retcode": 0, "message": "Api unsupported", "data": {}}

    with pytest.raises(AkuvoxDeviceError):
        await handler(cast("Any", _FakeResponse(200, json.dumps(body))))


def test_observed_fields_excludes_failure_events() -> None:
    """Report observed fields only from successful response events."""
    record = mvp_test.DiagnosticTestRecord(label="LIST USERS")
    record.events.append(
        mvp_test.DiagnosticHttpEvent(
            method="GET",
            endpoint="/api/user/get",
            http_status=200,
            retcode=-1,
            observed_fields=["Name"],
        )
    )

    assert record.observed_fields == []


def test_observed_fields_include_nested_response_keys() -> None:
    """Expose nested object keys for schema comparison."""
    fields = mvp_test._extract_observed_fields(
        {
            "Status": {
                "Model": "X916",
                "MAC": "00:11:22:33:44:55",
                "FirmwareVersion": "916.30.10.114",
            }
        }
    )

    assert fields == ["FirmwareVersion", "MAC", "Model", "Status"]


async def test_exception_capture_uses_first_line_only() -> None:
    """Store only the first line of multi-line exception messages."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    async def fail_with_multiline() -> None:
        """Raise a multi-line exception for diagnostic capture."""
        raise ValueError("first line\nsecond line")

    await mvp_test.run_step(results, "MULTILINE", fail_with_multiline())

    tests = cast("list[dict[str, Any]]", diagnostics.to_json()["tests"])
    failure_shape = cast("dict[str, Any]", tests[0]["failure_shape"])
    assert failure_shape["exception_message"] == "first line"
    assert "second line" not in json.dumps(diagnostics.to_json())


def test_write_json_round_trip(tmp_path: Any) -> None:
    """Write a JSON report and load the same structure back."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("LIST USERS")
    diagnostics.finish_test("passed")
    report_path = tmp_path / "mvp-diagnostic-report.json"
    diagnostics.write_json(report_path)
    loaded = json.loads(report_path.read_text(encoding="utf-8"))

    assert loaded == diagnostics.to_json()


def test_json_report_redacts_device_host() -> None:
    """Avoid leaking private device hostnames or IPs in shareable reports."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )

    report = diagnostics.to_json()
    device = cast("dict[str, Any]", report["device"])

    assert device["host"] == mvp_test._REDACTED_VALUE
    assert "192.0.2.10" not in json.dumps(report)


def test_json_report_includes_failure_shape() -> None:
    """Export structured failure shape and request field names."""
    action_not_supported = "".join(("unsup", "port action"))
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="digest",
        use_ssl=True,
        verify_ssl=False,
    )
    diagnostics.begin_test("ADD CONTACT")
    diagnostics.begin_http_event(
        method="POST",
        endpoint="/api/contact/set",
        data={
            "target": "contact",
            "action": "add",
            "data": {"item": [{"Name": "Test", "Phone": "555", "Group": "Default"}]},
        },
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text=f'{{"retcode":-1,"retmsg":"{action_not_supported}","data":{{}}}}',
        body=None,
        retcode=-1,
        retmsg=action_not_supported,
        data={},
    )
    diagnostics.record_exception(AkuvoxDeviceError(action_not_supported))
    diagnostics.finish_test("failed", action_not_supported)

    report = diagnostics.to_json()

    tests = cast("list[dict[str, Any]]", report["tests"])
    test = tests[0]
    failure_shape = cast("dict[str, Any]", test["failure_shape"])
    assert test["name"] == "add_contact"
    assert test["capability_status"] == "unsupported"
    assert test["endpoint"] == "/api/contact/set"
    assert failure_shape["retcode"] == -1
    assert failure_shape["retmsg"] == action_not_supported
    assert test["request_fields"] == [
        "Group",
        "Name",
        "Phone",
        "action",
        "data",
        "item",
        "target",
    ]
