..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Changelog
=========

Unreleased
----------

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
