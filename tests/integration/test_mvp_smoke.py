# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""End-to-end smoke tests for ``examples/mvp_test.py`` (T077, T078).

Per ``specs/008-capability-matrix/research.md`` Decision 9 and the
quickstart §11 contract, these tests drive the script's
:func:`examples.mvp_test.run_all` flow against mocked devices and
assert that the capability-gated ``step()`` helper emits the right
``SKIP:`` / ``OK:`` wording for each device class.

Two device classes are exercised:

* **IT83** — indoor monitor. Write capabilities are ``UNKNOWN`` in
  the matrix, so ``add_user`` / ``add_contact`` must print the
  ``UNKNOWN``-flavoured SKIP message. The relay trigger
  (``RELAY_TRIGGER_FCGI``) is ``SUPPORTED`` and routes through the
  ``/fcgi/do?action=OpenDoor&relay=1`` adapter — the test asserts
  exactly one FCGI request and zero requests to ``/api/user/set`` /
  ``/api/contact/set``.

* **X916** — door-phone reference. Every gated read step is
  ``SUPPORTED``; the test asserts no ``SKIP:``-prefixed line is
  emitted (regression guard against the probe-then-skip flow
  over-skipping on a fully-supported device).
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any

import examples.mvp_test as mvp_test
import pytest
from aioresponses import aioresponses

if TYPE_CHECKING:
    from collections.abc import Iterator


_BASE_URL = "http://192.168.1.100"

# --- shared mocked-payload helpers ---------------------------------

_OK_ENVELOPE: dict[str, Any] = {"retcode": 0, "message": "ok", "data": {}}
_STATUS_PAYLOAD: dict[str, Any] = {
    "retcode": 0,
    "message": "ok",
    "data": {"SystemTime": "1700000000", "UpTime": "12345"},
}
_RELAY_STATUS_PAYLOAD: dict[str, Any] = {
    "retcode": 0,
    "message": "ok",
    "data": {"relay": "0"},
}
_CONFIG_PAYLOAD: dict[str, Any] = {
    "retcode": 0,
    "message": "ok",
    "data": {
        "Config.DoorSetting.RELAY.HoldDelayA": "5",
        "Config.Network.LAN.Type": "DHCP",
    },
}


def _system_info(model: str, firmware: str) -> dict[str, Any]:
    """Build a minimal ``/api/system/info`` payload for ``model`` / ``firmware``."""
    return {
        "retcode": 0,
        "message": "ok",
        "data": {
            "Status": {
                "Model": model,
                "MAC": "00:11:22:33:44:55",
                "FirmwareVersion": firmware,
                "HardwareVersion": "1.0",
                "Uptime": "0d",
                "WebLang": "0",
            }
        },
    }


def _make_args(*, host: str, write: bool) -> argparse.Namespace:
    """Build the argparse namespace ``run_all`` consumes for smoke tests."""
    return argparse.Namespace(
        host=host,
        auth="none",
        user=None,
        password=None,
        timeout=10,
        write=write,
        ssl=False,
        no_verify_ssl=False,
        json_report=None,
        redact_stdout=False,
    )


@pytest.fixture
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``examples.mvp_test``'s ``asyncio.sleep`` with a no-op.

    The script's between-group cooldown (``await asyncio.sleep(6)``
    × 4) would otherwise dominate test runtime.
    """
    import asyncio

    async def _instant(_seconds: float) -> None:
        """No-op replacement for ``asyncio.sleep`` during tests."""
        return

    monkeypatch.setattr(asyncio, "sleep", _instant)


def _register_common_probe(m: aioresponses, model: str, firmware: str) -> None:
    """Register the 9-step probe + system endpoints (repeatable).

    Probe URLs carry ``?page=1`` on the user/contact/log endpoints (per
    ``contracts/probe-api.md``); the list_* service methods called by
    the read tests hit the same paths *without* a query string, so we
    register both variants.
    """
    m.get(
        f"{_BASE_URL}/api/system/info",
        payload=_system_info(model, firmware),
        repeat=True,
    )
    m.get(f"{_BASE_URL}/api/system/status", payload=_STATUS_PAYLOAD, repeat=True)
    # Probe variants (with ?page=1)
    m.get(f"{_BASE_URL}/api/user/get?page=1", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/contact/get?page=1", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/doorlog/get?page=1", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/calllog/get?page=1", payload=_OK_ENVELOPE, repeat=True)
    # Read-test variants (no query string)
    m.get(f"{_BASE_URL}/api/user/get", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/contact/get", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/doorlog/get", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/calllog/get", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/schedule/get", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/group/get", payload=_OK_ENVELOPE, repeat=True)
    m.get(f"{_BASE_URL}/api/relay/status", payload=_RELAY_STATUS_PAYLOAD, repeat=True)


def _iter_request_paths(m: aioresponses) -> Iterator[str]:
    """Yield every recorded request's ``path[?query]`` from the request log."""
    for (_method, url), calls in m.requests.items():
        for _ in calls:
            qs = f"?{url.query_string}" if url.query_string else ""
            yield f"{url.path}{qs}"


def test_mvp_against_it83(_no_sleep: None, capsys: pytest.CaptureFixture[str]) -> None:
    """T077 / SC-010 — IT83 SKIPs unknown writes, OKs FCGI relay trigger."""
    args = _make_args(host="192.168.1.100", write=True)

    with aioresponses() as m:
        _register_common_probe(m, model="IT83", firmware="83.30.10.4")
        # The IT83 matrix entry only marks ``KEY_DISCOVERY`` /
        # ``RELAY_TRIGGER_FCGI`` as ``SUPPORTED``; the shared probe
        # mock above happens to return ``retcode=0`` for several read
        # endpoints (``/api/user/get``, ``/api/contact/get``,
        # ``/api/schedule/get`` …) which the probe classifies as
        # ``SUPPORTED`` and merges *on top of* the matrix. This is
        # benign for the assertions below — ``add_user`` /
        # ``add_contact`` are write capabilities (``USER_ADD`` /
        # ``CONTACT_ADD``) which the probe never infers from read
        # success (FR-003: strict no-write-inference) and which the
        # IT83 matrix leaves ``UNKNOWN``, so the UNKNOWN-flavoured
        # SKIP wording is what the script emits regardless of probe
        # read-result classification. The
        # ``/api/config/get`` mock below is the realistic
        # ``KEY_DISCOVERY``-supported endpoint that
        # ``discover_config_keys`` calls.
        m.get(f"{_BASE_URL}/api/config/get", payload=_CONFIG_PAYLOAD, repeat=True)
        # The FCGI relay trigger returns a non-envelope text/plain body.
        m.get(
            f"{_BASE_URL}/fcgi/do?action=OpenDoor&relay=1",
            body="OK",
            status=200,
            content_type="text/plain",
        )

        import asyncio as _asyncio

        _asyncio.run(mvp_test.run_all(args))

        request_paths = list(_iter_request_paths(m))

    captured = capsys.readouterr().out

    # Decision 9 / quickstart §11 — UNKNOWN SKIPs use the
    # "status unknown ... (IT83)" wording.
    assert "  SKIP: add_user: status unknown on this device class (IT83)" in captured, (
        captured
    )
    assert (
        "  SKIP: add_contact: status unknown on this device class (IT83)" in captured
    ), captured
    # FCGI relay trigger is SUPPORTED on IT83 → OK line + actual hit.
    assert "  OK:   trigger_relay" in captured, captured

    fcgi_hits = [p for p in request_paths if "/fcgi/do" in p]
    assert len(fcgi_hits) == 1, (
        f"Expected exactly one FCGI relay-trigger request; got {fcgi_hits}"
    )
    assert all("/api/user/set" not in p for p in request_paths), request_paths
    assert all("/api/contact/set" not in p for p in request_paths), request_paths


def test_mvp_against_x916(_no_sleep: None, capsys: pytest.CaptureFixture[str]) -> None:
    """T078 — X916 reports OK for every read step with no SKIP: lines.

    Run in read-only mode (``--write=False``): all read capabilities
    are ``SUPPORTED`` on X916, so the probe-then-skip flow must not
    over-skip. The test also passes through the "SKIPPING WRITE
    TESTS" header which uses the legacy ``⊘ ... skipped:`` wording —
    that prefix is distinct from ``SKIP:`` and must not be confused.
    """
    args = _make_args(host="192.168.1.100", write=False)

    with aioresponses() as m:
        _register_common_probe(m, model="X916", firmware="916.30.10.114")
        # Read tests hit additional endpoints beyond the probe surface.
        m.get(f"{_BASE_URL}/api/config/get", payload=_CONFIG_PAYLOAD, repeat=True)

        import asyncio as _asyncio

        _asyncio.run(mvp_test.run_all(args))

    captured = capsys.readouterr().out

    # No SKIP-prefixed lines anywhere in the stdout transcript.
    skip_lines = [line for line in captured.splitlines() if line.startswith("  SKIP:")]
    assert skip_lines == [], (
        f"X916 over-skipped: {skip_lines}\n--- full output ---\n{captured}"
    )

    # Every gated read step emitted an OK banner.
    for name in (
        "list_users",
        "get_relay_status",
        "get_device_config",
        "discover_config_keys",
        "list_schedules",
        "list_groups",
        "list_contacts",
        "get_door_logs",
        "get_call_logs",
    ):
        assert f"  OK:   {name}" in captured, (
            f"Missing OK banner for {name!r}\n--- output ---\n{captured}"
        )
