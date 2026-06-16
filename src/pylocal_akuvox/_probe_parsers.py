# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Response payload parsers and schema/alias recorders for the capability probe.

Authored under spec ``010-capability-probe-split`` (issue #141). This
module owns the step-1 envelope parser, the list-item extractor, and
the schema/alias recorders that mutate the probe's accumulator dicts
based on observed user / contact response shapes. Each recorder is
tolerant of malformed input — it returns silently rather than raising
— so the probe driver in :mod:`pylocal_akuvox._capability_probe` can
sequence them unconditionally.
"""

from __future__ import annotations

import json
from typing import Any

from pylocal_akuvox._capability_profile import FieldAliases
from pylocal_akuvox._capability_types import SchemaShape
from pylocal_akuvox.exceptions import AkuvoxParseError


def _step_1_payload(body: str) -> dict[str, Any]:
    """Decode and validate the ``/api/system/info`` envelope.

    Mirrors :meth:`pylocal_akuvox._http.AkuvoxHttpClient._parse_envelope`
    semantics so the probe accepts exactly what regular API calls
    accept, with one defensive tightening: ``retcode`` of ``True`` /
    ``False`` is rejected (``bool`` is a subclass of ``int`` in
    Python, so a naïve ``isinstance(retcode, int)`` would let
    ``{"retcode": true}`` through). This matches the consistent
    treatment in :func:`pylocal_akuvox._probe_classifiers._summarise_system_status`
    for step 2.
    Returns the inner ``data`` dict. Raises :class:`AkuvoxParseError`
    (with ``__cause__`` chained for the JSON sub-case) on every
    failure mode.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        msg = "step-1 body is not valid JSON"
        raise AkuvoxParseError(msg) from exc
    if (
        not isinstance(payload, dict)
        or "retcode" not in payload
        or not isinstance(payload["retcode"], int)
        or isinstance(payload["retcode"], bool)
    ):
        msg = f"step-1 envelope missing fields: {payload!r}"
        raise AkuvoxParseError(msg)
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return {}
    return data


def _extract_items(body: str) -> list[Any] | None:
    """Return the list of records under ``data.{Item|item}`` or ``None``.

    Real Akuvox responses have used both PascalCase ``"Item"`` (older
    firmware references in the spec contract) and lowercase ``"item"``
    (the form actually used by the rest of this library — see
    :mod:`pylocal_akuvox.users` / :mod:`pylocal_akuvox.contacts` /
    :mod:`pylocal_akuvox.logs`). The probe-side helpers accept either
    so they record observed schema details regardless of the device's
    case convention. Returns ``None`` for non-JSON bodies, non-dict
    payloads, or payloads where neither key holds a list.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None
    for key in ("Item", "item"):
        items = data.get(key)
        if isinstance(items, list):
            return items
    return None


def _record_user_aliases(field_aliases: dict[str, FieldAliases], body: str) -> None:
    """Update ``field_aliases["schedule_relay"]`` from a user-list body.

    Inspects the user records in ``data.{Item|item}`` (the standard
    list container shape — both case conventions accepted, see
    :func:`_extract_items`) for any of the three observed
    schedule-field aliases (``ScheduleRelay`` / ``Schedule-Relay`` /
    ``Schedule``) and records them in observed order. Tolerates
    malformed or minimal bodies — never raises.
    """
    items = _extract_items(body)
    if items is None:
        return

    candidates = ("ScheduleRelay", "Schedule-Relay", "Schedule")
    observed: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in candidates:
            if key in item and key not in observed:
                observed.append(key)
    if observed:
        field_aliases["schedule_relay"] = FieldAliases(
            read=tuple(observed),
            write=(),
        )


def _record_user_schema_keys(notes: dict[str, str], body: str) -> None:
    """Record observed schema-variant keys from a user-list body.

    Per ``contracts/probe-api.md`` §"Probe step sequence" row 3, the
    probe records the *presence* of ``Building`` / ``Room`` /
    ``EffectiveType`` keys on user items so a maintainer can debug
    schema variants across firmware. Records the comma-joined sorted
    list of observed keys under
    ``notes["user_schema_observed_keys"]`` (sorted to keep SC-002
    byte-equal idempotence). Accepts both ``data.Item`` and
    ``data.item`` per :func:`_extract_items`. Tolerates malformed or
    minimal bodies — never raises and writes nothing if no candidate
    key is observed.
    """
    items = _extract_items(body)
    if items is None:
        return

    candidates = ("Building", "Room", "EffectiveType")
    observed: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in candidates:
            if key in item:
                observed.add(key)
    if observed:
        notes["user_schema_observed_keys"] = ",".join(sorted(observed))


def _record_contact_shape(schema_shapes: dict[str, SchemaShape], body: str) -> None:
    """Update ``schema_shapes["contact"]`` from a contact-list body.

    Detects the apartment-book shape (the *distinctive* keys
    ``APTName`` / ``APTNum`` are unique to the apartment-book schema,
    so either of those alone is sufficient evidence; ``Building`` and
    ``Landline`` are too generic to be diagnostic on their own) vs
    the door-phone shape (every other shape — typically ``Name`` /
    ``Phone`` / ``ID``). Accepts both ``data.Item`` and ``data.item``
    per :func:`_extract_items`. Never raises on malformed input.
    """
    items = _extract_items(body)
    if not items:
        return
    first = items[0]
    if not isinstance(first, dict):
        return

    distinctive_apt_keys = {"APTName", "APTNum"}
    if any(k in first for k in distinctive_apt_keys):
        schema_shapes["contact"] = SchemaShape.APARTMENT_BOOK
    else:
        schema_shapes["contact"] = SchemaShape.DOOR_PHONE


__all__ = [
    "_extract_items",
    "_record_contact_shape",
    "_record_user_aliases",
    "_record_user_schema_keys",
    "_step_1_payload",
]
