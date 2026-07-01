#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0
r"""Interactive CLI script to test pylocal-akuvox against a real device.

Examples:
  %(prog)s 192.168.1.100
  %(prog)s 192.168.1.100 --write
  %(prog)s 192.168.1.100 --ssl --no-verify-ssl
  %(prog)s 192.168.1.100 --json-report mvp-report.json
  %(prog)s 192.168.1.100 --auth basic --user admin --pass secret
  %(prog)s 192.168.1.100 --auth digest --user admin --pass secret --write
  %(prog)s 192.168.1.100 --write --open-door --open-door-user relay-user \
    --open-door-pass secret

JSON report:
  Top-level keys: device (model, firmware, redacted host), auth,
  observed_schemas, tests. Each test records name, label, status,
  capability_status, reason, endpoint, observed_fields, request_fields,
  failure_shape, and http_events. failure_shape and each http_event record
  method, endpoint, http status, retcode, retmsg, observed_fields,
  request_fields, exception class/message, and redacted body_snippet only
  for HTTP or Akuvox retcode failures.

"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
import traceback
from pathlib import Path

from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
    run_capability_report,
)
from pylocal_akuvox._diagnostic_report import (
    _BODY_SNIPPET_CHARS,
    _NON_JSON_BODY_OMITTED,
    _REDACTED_VALUE,
    _SCALAR_JSON_BODY_OMITTED,
    DiagnosticHttpEvent,
    DiagnosticReport,
    DiagnosticTestRecord,
    _clip,
    _decode_json_body,
    _display_value,
    _drop_none,
    _event_failed,
    _event_succeeded,
    _extract_observed_fields,
    _failure_body_snippet,
    _redact_json_values,
)
from pylocal_akuvox._report_steps import (
    SEPARATOR,
    TestResults,
    TestStepFailed,
    TestStepSkipped,
    _build_diagnostic_response_handler,
    _effective_status,
    _install_probed_capabilities,
    _open_door_skip_reason,
    _parse_diagnostic_envelope,
    _parse_response_shape,
    _probe_device_capabilities,
    _record_capability_skip,
    _run_open_door_write_step,
    _run_read_tests,
    _run_write_tests,
    create_device,
    print_header,
    run_step,
    skip_step,
    step,
    test_add_contact,
    test_add_group,
    test_add_schedule,
    test_add_user,
    test_delete_contact,
    test_delete_group,
    test_delete_schedule,
    test_delete_user,
    test_discover_config_keys,
    test_get_call_logs,
    test_get_device_config,
    test_get_door_logs,
    test_get_info,
    test_get_relay_status,
    test_get_status,
    test_list_contacts,
    test_list_groups,
    test_list_schedules,
    test_list_users,
    test_modify_contact,
    test_modify_schedule,
    test_modify_user,
    test_open_door,
    test_set_device_config,
    test_trigger_relay,
    test_validation,
    test_verify_contact_deletion,
    test_verify_group_deletion,
    test_verify_schedule_deletion,
    test_verify_user_deletion,
)
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
)

_OPEN_DOOR_PASSWORD_ENV = "AKUVOX_OPEN_DOOR_PASSWORD"

__all__ = [
    "DiagnosticHttpEvent",
    "DiagnosticReport",
    "DiagnosticTestRecord",
    "SEPARATOR",
    "TestResults",
    "TestStepFailed",
    "TestStepSkipped",
    "_BODY_SNIPPET_CHARS",
    "_NON_JSON_BODY_OMITTED",
    "_REDACTED_VALUE",
    "_SCALAR_JSON_BODY_OMITTED",
    "_build_diagnostic_response_handler",
    "_clip",
    "_decode_json_body",
    "_display_value",
    "_drop_none",
    "_effective_status",
    "_event_failed",
    "_event_succeeded",
    "_extract_observed_fields",
    "_failure_body_snippet",
    "_install_probed_capabilities",
    "_open_door_skip_reason",
    "_parse_diagnostic_envelope",
    "_parse_response_shape",
    "_probe_device_capabilities",
    "_record_capability_skip",
    "_redact_json_values",
    "_run_open_door_write_step",
    "_run_read_tests",
    "_run_write_tests",
    "build_auth",
    "create_device",
    "main",
    "print_header",
    "run_all",
    "run_step",
    "skip_step",
    "step",
    "test_add_contact",
    "test_add_group",
    "test_add_schedule",
    "test_add_user",
    "test_delete_contact",
    "test_delete_group",
    "test_delete_schedule",
    "test_delete_user",
    "test_discover_config_keys",
    "test_get_call_logs",
    "test_get_device_config",
    "test_get_door_logs",
    "test_get_info",
    "test_get_relay_status",
    "test_get_status",
    "test_list_contacts",
    "test_list_groups",
    "test_list_schedules",
    "test_list_users",
    "test_modify_contact",
    "test_modify_schedule",
    "test_modify_user",
    "test_open_door",
    "test_set_device_config",
    "test_trigger_relay",
    "test_validation",
    "test_verify_contact_deletion",
    "test_verify_group_deletion",
    "test_verify_schedule_deletion",
    "test_verify_user_deletion",
]


def build_auth(args: argparse.Namespace) -> AuthConfig | None:
    """Build AuthConfig from CLI arguments."""
    if args.auth == "none":
        return None
    method_map = {
        "basic": AuthMethod.BASIC,
        "digest": AuthMethod.DIGEST,
    }
    method = method_map[args.auth]
    return AuthConfig(method=method, username=args.user, password=args.password)


def _validate_open_door_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Validate and resolve OpenDoor-specific CLI arguments."""
    if not args.open_door:
        return
    if not args.write:
        parser.error("--open-door requires --write")
    if not args.open_door_user:
        parser.error("--open-door requires --open-door-user")
    if not args.open_door_password:
        args.open_door_password = os.environ.get(_OPEN_DOOR_PASSWORD_ENV)
    if not args.open_door_password:
        parser.error(
            f"--open-door requires --open-door-pass or {_OPEN_DOOR_PASSWORD_ENV}"
        )


async def run_all(args: argparse.Namespace) -> None:
    """Run all MVP tests against the device."""
    auth = build_auth(args)
    auth_desc = args.auth if args.auth != "none" else "allowlist (no auth)"
    ssl_desc = ""
    if args.ssl:
        ssl_desc = " [HTTPS"
        ssl_desc += ", no cert verify" if args.no_verify_ssl else ""
        ssl_desc += "]"

    print(f"\n🔌 Connecting to {args.host} ({auth_desc}{ssl_desc})")
    print(f"   Timeout: {args.timeout}s\n")

    try:
        device = AkuvoxDevice(
            args.host,
            auth=auth,
            timeout=args.timeout,
            use_ssl=args.ssl,
            verify_ssl=not args.no_verify_ssl,
        )
        report = await run_capability_report(
            device,
            write=args.write,
            open_door=getattr(args, "open_door", False),
            open_door_user=getattr(args, "open_door_user", None),
            open_door_password=getattr(args, "open_door_password", None),
            timeout=args.timeout,
            redact_stdout=args.redact_stdout,
            emit=print,
        )
    except AkuvoxConnectionError as exc:
        print(f"\n✗ Connection failed: {exc}")
        sys.exit(1)
    except AkuvoxAuthenticationError as exc:
        print(f"\n✗ Authentication failed: {exc}")
        sys.exit(1)
    except AkuvoxError as exc:
        print(f"\n✗ Akuvox error: {exc}")
        traceback.print_exc()
        sys.exit(1)

    if args.json_report is not None:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\n  JSON report written: {report_path}")


def main() -> None:
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test pylocal-akuvox MVP against a real Akuvox device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("host", help="Device IP address or hostname")
    parser.add_argument(
        "--auth",
        choices=["none", "basic", "digest"],
        default="none",
        help="Authentication method (default: none / allowlist)",
    )
    parser.add_argument("--user", default=None, help="Auth username")
    parser.add_argument(
        "--pass",
        "--password",
        dest="password",
        default=None,
        help="Auth password (or set AKUVOX_PASSWORD env var)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--ssl",
        action="store_true",
        help="Use HTTPS instead of HTTP",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Skip SSL certificate verification (for self-signed certs)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Enable write tests (add/modify/delete a test user)",
    )
    parser.add_argument(
        "--json-report",
        metavar="PATH",
        default=None,
        help="Write a structured JSON diagnostic report to PATH",
    )
    parser.add_argument(
        "--redact-stdout",
        action="store_true",
        help=(
            "Redact PII values (PIN, MAC, names, phones, etc.) in stdout "
            "output. Use when sharing terminal logs. JSON body excerpts "
            "(--json-report) are always redacted regardless."
        ),
    )
    parser.add_argument(
        "--open-door",
        action="store_true",
        help="With --write, also exercise credentialed OpenDoor HTTP relay 1",
    )
    parser.add_argument(
        "--open-door-user",
        default=None,
        help="OpenDoor HTTP relay username",
    )
    parser.add_argument(
        "--open-door-pass",
        dest="open_door_password",
        default=None,
        help=(
            f"OpenDoor HTTP relay password (or set {_OPEN_DOOR_PASSWORD_ENV} env var)"
        ),
    )

    args = parser.parse_args()

    if args.no_verify_ssl and not args.ssl:
        args.ssl = True

    _validate_open_door_args(args, parser)

    if args.auth in ("basic", "digest"):
        if not args.user:
            parser.error(f"--auth {args.auth} requires --user")
        if not args.password:
            args.password = os.environ.get("AKUVOX_PASSWORD")
        if not args.password:
            args.password = getpass.getpass("Device password: ")
    else:
        args.password = None
    asyncio.run(run_all(args))


if __name__ == "__main__":
    main()
