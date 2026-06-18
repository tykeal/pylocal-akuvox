..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Contacts
========

Contact schema shapes
---------------------

Akuvox exposes two contact models through ``/api/contact/*``. Door-phone
classes such as X916 and E18C use a flat contact record with ``ID``,
``Name``, ``Phone``, and ``Group``. Apartment-book classes such as X915S
use a building or apartment record with ``Name``, ``Phone``, ``APTName``,
``APTNum``, ``Building``, and ``Landline``. Apartment-book contact records
do not carry a device-assigned ``ID`` or ``Group``.

The shared :class:`pylocal_akuvox.Contact` model exposes apartment-book
metadata as ``apt_name``, ``apt_num``, ``building``, and ``landline``. These
fields are ``None`` for door-phone records. The active
``schema_shapes["contact"]`` capability selects the parser branch, so the
behaviour is device-class driven rather than hard-coded to one model.

Door-phone classes support contact reads and writes when their capability
profile marks the operation supported. Apartment-book contacts are read-only
over the public HTTP API; manage them out-of-band through the device web UI,
provisioning, or another vendor-supported channel.

.. automodule:: pylocal_akuvox.contacts
   :members:
   :undoc-members:
   :show-inheritance:
