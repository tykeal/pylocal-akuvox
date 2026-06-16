..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Changelog
=========

Unreleased
----------

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

Added
^^^^^

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
