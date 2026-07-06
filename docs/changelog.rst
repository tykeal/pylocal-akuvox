..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Changelog
=========

Unreleased
----------

v1.3.0 (2026-07-06)
-------------------

Breaking changes
^^^^^^^^^^^^^^^^

* The ``pylocal_akuvox.capabilities`` import subpath has been removed
  (issue #140). ``import pylocal_akuvox.capabilities`` and
  ``from pylocal_akuvox.capabilities import X`` now raise
  ``ModuleNotFoundError``.

* The following four symbols, formerly reachable via the dropped
  subpath, are now formally internal and no longer publicly
  importable: ``Provenance`` (in
  ``pylocal_akuvox._capability_profile``), ``DeviceClassPattern`` and
  ``lookup_capabilities`` (in ``pylocal_akuvox._capability_matching``),
  and ``DEFAULT_USER_FIELD_ALIASES`` (in
  ``pylocal_akuvox._capability_defaults``).

* **Migration**: the five public symbols ``Capability``,
  ``CapabilityStatus``, ``DeviceCapabilities``, ``FieldAliases``, and
  ``SchemaShape`` remain re-exported unchanged from the top-level
  ``pylocal_akuvox`` package. Consumers should use
  ``from pylocal_akuvox import Capability, CapabilityStatus,
  DeviceCapabilities, FieldAliases, SchemaShape``. No consumer-facing
  public symbol has been renamed or removed.

* The ``pylocal_akuvox.capability_probe`` import subpath has been
  removed (issue #141). ``import pylocal_akuvox.capability_probe`` and
  ``from pylocal_akuvox.capability_probe import probe_capabilities``
  now raise ``ModuleNotFoundError``.

* **Migration**: continue calling
  ``AkuvoxDevice.probe_capabilities()`` — the documented public method
  on :class:`pylocal_akuvox.AkuvoxDevice` is unchanged and remains the
  consumer-facing handle for the capability probe. No consumer-facing
  public symbol has been renamed or removed. White-box callers (test
  suites, internal tooling) that previously imported helpers from the
  dropped subpath should switch to the new owning underscore modules:
  ``pylocal_akuvox._probe_outcomes``, ``pylocal_akuvox._probe_classifiers``,
  ``pylocal_akuvox._probe_parsers``, and ``pylocal_akuvox._capability_probe``.

  Refs #141.

Changed
^^^^^^^

* Contact writes (add, modify, delete) on apartment-book device classes
  now raise a uniform ``AkuvoxUnsupportedError`` with
  ``reason="capability_missing"`` before any I/O; device
  ``"unsupport action"`` / ``"unsupported action"`` envelopes now
  translate to ``AkuvoxUnsupportedError`` with
  ``reason="envelope_unsupported"``; and the public service-function
  ``schema_shape=`` write-deferral kwarg was removed.

  Refs #121.

* ``trigger_relay()`` on IT83-class devices now raises an actionable
  error directing callers to ``AkuvoxDevice.open_door_http()`` instead
  of issuing a credential-less OpenDoor request.

  Refs #122.

* Split the ``AkuvoxDevice`` implementation into focused internal
  ``_device_*`` helper modules while preserving ``pylocal_akuvox.device``
  and both public import forms.

  Refs #142.

Fixed
^^^^^

* Write-mode capability reports now backfill default user write aliases
  for unrecognized devices whose probe only observes schedule relay read
  aliases, allowing user add and modify diagnostics to reach the device.

  Refs #230.

* ``modify_user()`` now preserves and normalizes an existing schedule
  relay value when ``schedule_relay`` is left unchanged, preventing
  devices that require ``ScheduleRelay`` on user updates from rejecting
  PIN-only modifications.

  Refs #219.

* Capability probes on matrix-recognised devices now preserve curated
  write aliases while still refining observed read aliases, so
  ``add_user()`` and ``modify_user()`` can emit schedule relay keys after
  probing.

  Refs #216.

* Avoid a blocking package metadata read when ``AkuvoxDevice.__aenter__()``
  performs its connect-time capability matrix lookup.

  Refs #215.

* ``open_door_http()`` now checks the ``hcSingleResult`` marker returned
  by IT83-class ``/fcgi/do?action=OpenDoor`` responses so HTTP 200 with
  ``value='-1'`` raises an authentication error instead of reporting a
  false success.

  Refs #168.

Added
^^^^^

* Added R20K device-class support for the community-reported door-phone
  profile, including schedule and contact CRUD, group add / delete, API
  relay trigger, relay status, device config get, logs, and key
  discovery.

  Refs #229.

* Added A08S device-class support for user and schedule CRUD, API relay
  trigger and status, door logs, device config, and key discovery.
  Contacts, groups, and call logs are unsupported on this access-unit
  class.

  Refs #222.

* Added the public ``run_capability_report()`` API for generating the
  redacted capability report used by ``examples/mvp_test.py``.

  Refs #208.

* Added optional apartment-book ``Contact`` fields ``apt_name``,
  ``apt_num``, ``building``, and ``landline`` for preserving X915S
  contact metadata on reads.

  Refs #121.

* Added ``pylocal_akuvox.relay.open_door_http`` and
  ``AkuvoxDevice.open_door_http`` for credentialed
  ``/fcgi/do?action=OpenDoor`` relay unlocks.

  Refs #122.

* Added E18 device-class support with the full door-phone capability
  set and firmware floor ``18.30.10.118+``.

  Refs #207.

* Initial release of pylocal-akuvox
* Async-only Python library for Akuvox local HTTP API
* Device connection and info retrieval
* User and PIN management (CRUD)
* Relay control (trigger and status)
* Access schedule management (CRUD)
* Door and call log retrieval
* Authentication: None, AllowList, Basic, Digest
* SSL support with self-signed certificate handling
* Typed exception hierarchy for error handling
* Capability profile data model with ``Capability``,
  ``CapabilityStatus``, and immutable ``DeviceCapabilities`` records
* Built-in model-to-capability matrix with first-match lookup plus
  probe override-and-merge semantics
* Safe ``probe_capabilities()`` using a deterministic 9-call read-only
  sequence for device capability discovery
* ``AkuvoxDevice.attempt_unknown_capability`` opt-in for attempting
  operations whose capability status is ``UNKNOWN``
* Internal ``_request_raw`` helper used by the probe to classify raw
  status codes and device envelopes
* Capability-aware service kwargs (``field_aliases=``,
  ``schema_shape=``, ``capabilities=``) threaded through user/contact APIs
* Published docs include the capability matrix Sphinx directive for the
  live device support table
* Lowered OpenSSL security level to 0 in the no-verify SSL path to
  support older Akuvox devices (e.g. S562) that ship with 1024-bit DH
  parameters
