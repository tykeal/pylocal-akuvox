..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Device Support Matrix
=====================

This page documents the *capability matrix* — the curated table that
:meth:`pylocal_akuvox.AkuvoxDevice.__aenter__` consults at connect time to
decide which operations are known-good, known-bad, or untested on the
attached device class.

Three CapabilityStatus values are used uniformly. ``SUPPORTED`` is
positive evidence (a maintainer or community reporter has executed the
operation against a real device and confirmed it works on the listed
firmware band). ``UNSUPPORTED`` is negative evidence (the device
returned an "unsupported action" envelope or "No handlers for this
request" for that operation). ``UNKNOWN`` is the absence of evidence —
the matrix maintainer has not classified the operation either way; the
per-call gate fails fast unless the integrator opts in with
``device.attempt_unknown_capability = True``.

Public types
------------

.. autoclass:: pylocal_akuvox.Capability
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pylocal_akuvox.CapabilityStatus
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pylocal_akuvox.DeviceCapabilities
   :members:
   :undoc-members:
   :show-inheritance:

Matrix entries (live)
---------------------

The table below is rendered at documentation build time directly from
``pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX``. If the matrix
constant changes, the table updates automatically on the next build.
The per-class sections that follow give the supplied evidence for each
``(model prefix, firmware band)`` pair documented here.

.. capability-matrix::

Device classes
--------------

X916
~~~~

Door-phone reference baseline. Maintainer's bench unit. All read /
write CRUD operations on users, schedules, groups, and contacts are
``SUPPORTED``; relay trigger uses the API variant
(``Capability.RELAY_TRIGGER_API``); ``ScheduleRelay`` and
``Schedule-Relay`` are both accepted on read and emitted on write
(the dual-write contract from issues #99 / #101).

X915S
~~~~~

Door-phone variant on the X915S product line. Reads the bare
``Schedule`` key in user payloads (issue #118 / PR #120), so the
matrix entry lists ``Schedule`` first in the
``schedule_relay`` field-alias read order. ``add_contact`` is
``UNSUPPORTED`` on this variant per the "unsupported action" envelope
observation in issue #121; ``modify_contact`` / ``delete_contact``
were not specifically exercised and remain ``UNKNOWN``. Contact
payloads use the apartment-book schema shape.

E18C
~~~~

Door-phone variant. Same capability set as X916 modulo firmware
band; aliasing matches X916 byte-for-byte.

IT83
~~~~

Indoor-monitor product line (community reporter, issue #122 /
#130). The ``/api/relay/*`` endpoints return "No handlers for this
request" on this device class
(``Capability.RELAY_TRIGGER_API`` and ``Capability.RELAY_STATUS``
are both ``UNSUPPORTED``); the ``/fcgi/do?action=OpenDoor`` variant
(``Capability.RELAY_TRIGGER_FCGI``) works. All user / contact /
schedule / group operations remain ``UNKNOWN`` — the community
reporter did not exercise them.

Contributing a new device class
-------------------------------

Adding support for a new firmware band whose variation is limited to
the known axes (endpoint availability, field-name aliasing, schema
shape, action availability) requires a single-file edit to
:mod:`pylocal_akuvox.capability_matrix`. The recipe below is the
worked walkthrough referenced from
``specs/008-capability-matrix/contracts/matrix-lookup.md``
§"Adding a new entry":

1. Add a new ``(DeviceClassPattern(...), DeviceCapabilities(...))``
   tuple to :data:`CAPABILITY_MATRIX` in the most-specific-first
   position. ``DeviceClassPattern`` accepts a ``model_prefix``
   (matched with :py:meth:`str.startswith` against the device's
   reported model) and a ``firmware_band`` in one of three forms —
   exact (``"83.30.10.4"``), glob (``"916.30.10.*"``), or floor
   (``"2915.30.10.114+"``).
2. Populate the entry's ``capabilities`` mapping with the
   per-capability :class:`pylocal_akuvox.CapabilityStatus` values
   for which there is positive evidence. Capabilities for which there
   is no positive evidence either way may be omitted from the
   mapping; they default to ``UNKNOWN``. Maintainers are encouraged
   to omit rather than guess.
3. Record confirmed-negative evidence (e.g. an "unsupported action"
   envelope was observed for the operation) as ``UNSUPPORTED`` so the
   per-call gate fails fast instead of suggesting the integrator
   opt in.
4. If the entry uses field aliases or schema shapes that already have
   matrix-language coverage (e.g. another existing entry has
   :attr:`pylocal_akuvox.SchemaShape.APARTMENT_BOOK`), no further
   code change is required.
5. If the entry uses a brand-new schema shape (e.g. a different
   contact-payload structure) add the new variant to
   :class:`pylocal_akuvox.SchemaShape` and to the corresponding
   parser's dispatch — this is **not** a large refactor; it is a
   one-line addition to the central enum plus a parser branch.
   Field-alias keys, by contrast, are plain strings stored in
   ``DeviceCapabilities.field_aliases`` and do **not** require an
   enum addition; a new alias can be introduced by listing it in the
   entry alone. New :class:`pylocal_akuvox.Capability` members
   should be reserved for genuinely new operations or endpoints,
   not for alias variants of existing ones.
6. Add a new test case in ``tests/unit/test_matrix.py`` asserting the
   entry's provenance and selected capability deltas.
7. Update this page (``docs/api/capabilities.rst``) to mention the
   new device class. The consistency test in
   ``tests/unit/test_docs_matrix_consistency.py`` will fail CI if
   the page omits a matrix-registered prefix or mentions an unknown
   prefix in a heading.

The same recipe is exercised programmatically by
``tests/unit/test_matrix.py::test_add_hypothetical_entry`` (see
``specs/008-capability-matrix/quickstart.md`` step 9).
