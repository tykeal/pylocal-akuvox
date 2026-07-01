..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Capability Report API
=====================

.. autofunction:: pylocal_akuvox.run_capability_report

``run_capability_report()`` generates the same redacted diagnostic report as
``examples/mvp_test.py`` from Python code. It accepts an ``AkuvoxDevice`` as the
connection template, runs the read-only probe, optionally runs write-capable CRUD
checks against throwaway entities, and returns a JSON-serializable dictionary.

Parameters
----------

``device``
   ``AkuvoxDevice`` used as the connection template.
``write``
   When ``False``, no create, modify, or delete requests are issued. When
   ``True``, the report includes user, schedule, group, contact, relay, config,
   and optional OpenDoor write evidence.
``open_door``
   Opts in to the physical OpenDoor HTTP relay test. The relay only actuates
   when write mode is enabled and both OpenDoor credentials are supplied.
``open_door_user`` / ``open_door_password``
   Relay-specific credentials supplied by the caller. The library does not read
   environment variables. Returned skip reasons preserve CLI-oriented hints and
   may mention ``AKUVOX_OPEN_DOOR_PASSWORD`` even though the API ignores it.
``timeout``
   Optional request timeout override for report-owned child connections.
``redact_stdout``
   Display-only field-aware redaction for emitted text, mirroring the CLI
   ``--redact-stdout`` flag. It never changes the returned report.
``emit``
   Optional callable receiving console lines. ``None`` keeps the library quiet;
   the CLI passes ``print`` for byte-identical output. Custom emitters and
   silent mode redirect process-wide stdout/stderr while the report runs, so
   avoid concurrent stdout/stderr writers during a report run.

Return schema
-------------

The returned dictionary has exactly four top-level keys: ``device``, ``auth``,
``observed_schemas``, and ``tests``. HTTP events are nested under each test
record. Optional test and HTTP-event fields are omitted when absent, except
``device.class``, ``device.model``, and ``device.firmware``, which may be
``None`` for unknown identity.

``capability_status`` is one of ``supported``, ``unsupported``, or
``inconclusive``. ``auth.method`` is one of ``none``, ``basic``, or ``digest``.
Failure ``body_snippet`` values are clipped redacted JSON strings and appear only
for HTTP or Akuvox retcode failures.

Redaction and safety
--------------------

Returned reports are always fully redacted and safe to paste into device-support
requests: the host is redacted, response body leaves are redacted, successful
bodies are omitted, and credentials, PINs, MAC addresses, names, phone numbers,
and OpenDoor passwords are not included.

Write mode uses fixed, recognizable throwaway entities and deletes created test
records before returning. OpenDoor remains an explicit credentialed opt-in.
