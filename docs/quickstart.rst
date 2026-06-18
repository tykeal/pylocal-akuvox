..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

Quickstart
==========

Installation
------------

.. code-block:: bash

   pip install pylocal-akuvox

Connect and Get Device Info
---------------------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           info = await device.get_info()
           print(f"{info.model} — FW {info.firmware_version}")

   asyncio.run(main())

Probing capabilities
--------------------

When a connection opens, known device classes are matched against the
built-in device support matrix. For an unfamiliar device, or after a
firmware update, call :meth:`pylocal_akuvox.AkuvoxDevice.probe_capabilities`
to run the deterministic, non-destructive read probe. The returned
:class:`pylocal_akuvox.DeviceCapabilities` is also available as
``device.capabilities`` for later calls on the same connection.

Use the probe-then-act pattern so provisioning code only runs operations
that are confirmed for the attached device:

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice, Capability, CapabilityStatus

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           capabilities = await device.probe_capabilities()

           user_add_status = capabilities.status_of(Capability.USER_ADD)
           if user_add_status is CapabilityStatus.SUPPORTED:
               await device.add_user(
                   name="Alice",
                   user_id="2001",
                   web_relay="0",
                   schedule_relay="1001-1",
                   lift_floor_num="0",
                   private_pin="1234",
               )
           else:
               print("User creation is not confirmed for this device")

   asyncio.run(main())

``UNSUPPORTED`` operations always fail fast without a device request.
``UNKNOWN`` operations fail fast by default; set
``device.attempt_unknown_capability = True`` only when you intentionally
want to try an unproven device-side operation. See
:doc:`api/capabilities` for the live capability matrix.

.. note::

   The remaining examples call service methods directly for brevity.
   They assume the relevant capability is ``SUPPORTED``; for portable
   code, guard each operation with the probed or matrix profile as
   shown above.

Manage Users and PINs
---------------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           # Create a user with a PIN
           await device.add_user(
               name="Alice",
               user_id="2001",
               web_relay="0",
               schedule_relay="1001-1",
               lift_floor_num="0",
               private_pin="1234",
           )

           # List all users
           users = await device.list_users()
           for user in users:
               print(f"{user.name} (PIN set: {bool(user.private_pin)})")

           # Update a user's PIN
           await device.modify_user(id="1", private_pin="5678")

           # Delete a user
           await device.delete_user(id="1")

   asyncio.run(main())

Trigger a Door Relay
--------------------

Door-phone models that support the JSON relay API use
``trigger_relay()``, which sends ``/api/relay/trig`` with the
connection's ``AuthConfig``:

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           await device.trigger_relay(num=1, delay=5)

   asyncio.run(main())

IT83-class devices use Akuvox's separate Open Relay Via HTTP setting
instead. Enable **Phone → Relay → Open Relay Via HTTP** on the device
and pass those relay-specific credentials per call:

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           await device.open_door_http(
               user="relay-user",
               password="relay-password",
           )

   asyncio.run(main())

The vendor endpoint carries the OpenDoor password in the URL query
string, so it can appear in proxy or device access logs outside this
library. On firmware that returns the ``hcSingleResult`` OpenDoor
marker, ``open_door_http()`` treats ``0`` as success, ``-1`` as an Open
Relay Via HTTP credential failure, and other non-zero values as
device-side failures. Responses without that marker continue to use the
HTTP status for compatibility. On an IT83, ``trigger_relay()`` raises an
actionable error directing callers to ``AkuvoxDevice.open_door_http()``
instead of sending a credential-less OpenDoor request.

Retrieve Device Status
----------------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           status = await device.get_status()
           print(f"Uptime: {status.uptime}")

   asyncio.run(main())

Manage Schedules
----------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           # Create a weekly schedule
           await device.add_schedule(
               name="Weekday Access",
               schedule_type="1",
               week="12345",
               daily="08:00-18:00",
           )

           # List schedules
           schedules = await device.list_schedules()

           # Delete a schedule
           await device.delete_schedule(id="1001")

   asyncio.run(main())

Manage Groups
-------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           # List existing groups
           groups = await device.list_groups()
           for g in groups:
               print(f"[{g.id}] {g.name}")

           # Create a new group
           await device.add_group(name="Residents")

           # Rename a group
           await device.modify_group(id="1", name="Tenants")

           # Delete a group
           await device.delete_group(id="1")

   asyncio.run(main())

Manage Contacts
---------------

Door-phone devices expose contact records with a device ``ID`` and optional
``Group``. Apartment-book devices expose read-only records without ``ID``;
their additional ``apt_name``, ``apt_num``, ``building``, and ``landline``
fields come from ``APTName``, ``APTNum``, ``Building``, and ``Landline``.
Empty apartment-book ``building`` and ``landline`` values are preserved as
``""`` because the device returned those fields.

.. code-block:: python

   import asyncio
   from pylocal_akuvox import (
       AkuvoxDevice,
       AkuvoxUnsupportedError,
       Capability,
       CapabilityStatus,
   )

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           # List all contacts
           contacts = await device.list_contacts()
           for c in contacts:
               if c.id is None:
                   key = (c.apt_num, c.phone)
                   print(
                       f"{c.name}: apt={c.apt_num} phone={c.phone} "
                       f"building={c.building!r} landline={c.landline!r}"
                   )
                   # Use the caller-side key only when both parts are present.
                   # Fall back to c.name when the pair is incomplete.
                   if all(key):
                       print(f"caller key: {key}")
               else:
                   print(f"{c.name} ({c.group}): {c.phone}")

           status = device.capabilities.status_of(Capability.CONTACT_ADD)
           if status is CapabilityStatus.SUPPORTED:
               # Add a contact to a group on door-phone devices
               await device.add_contact(
                   name="Alice",
                   phone="5551234",
                   group="Residents",
               )

               # Move a contact to another group
               await device.modify_contact(id="1", group="Staff")

               # Delete a contact
               await device.delete_contact(id="1")

               # Batch delete
               await device.delete_contact(id=["2", "3"])
           elif status is CapabilityStatus.UNSUPPORTED:
               try:
                   await device.add_contact(name="Alice", phone="5551234")
               except AkuvoxUnsupportedError as err:
                   assert err.reason == "capability_missing"
                   print("Contact writes are not supported on this device")
           else:
               print("Contact writes are not confirmed for this device")

   asyncio.run(main())

Apartment-book records have no device-assigned ``ID``. The library does not
create a synthetic identifier or guarantee uniqueness. When both fields are
available, use a caller-side ``(apt_num, phone)`` composite key; fall back to
``name`` when needed. Two records with the same ``name`` remain
distinguishable when their ``apt_num`` or ``phone`` values differ.

Retrieve Logs
-------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           # Door access logs
           door_logs = await device.get_door_logs()
           for entry in door_logs:
               print(f"{entry.date} {entry.time}: {entry.name} — {entry.status}")

           # Call logs
           call_logs = await device.get_call_logs()
           for entry in call_logs:
               print(f"{entry.date} {entry.time}: {entry.call_type} — {entry.name}")

   asyncio.run(main())

Authentication Modes
--------------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

   async def main():
       # No auth (default — no credentials needed)
       async with AkuvoxDevice("192.168.1.100") as device:
           info = await device.get_info()

       # Basic Auth
       auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="secret")
       async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
           info = await device.get_info()

       # Digest Auth
       auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="secret")
       async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
           info = await device.get_info()

   asyncio.run(main())

SSL Connections
---------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       # SSL with certificate verification (recommended for production)
       async with AkuvoxDevice("192.168.1.100", use_ssl=True) as device:
           info = await device.get_info()

       # SSL with self-signed certificate (skip verification)
       # WARNING: Only use verify_ssl=False on trusted networks for
       # testing. Disabling verification exposes you to MITM attacks.
       async with AkuvoxDevice("192.168.1.100", use_ssl=True, verify_ssl=False) as device:
           info = await device.get_info()

   asyncio.run(main())

.. note::

   When using self-signed certificates, prefer importing the device's
   certificate into your trust store so that you can keep
   ``verify_ssl=True`` in production deployments.

.. warning::

   Some older Akuvox devices (e.g. the S562 indoor monitor) ship with
   legacy 1024-bit Diffie-Hellman parameters that OpenSSL's default
   security level rejects with a ``dh key too small`` handshake error.
   When ``verify_ssl=False``, this library lowers OpenSSL's security
   level to ``0`` so these legacy handshakes succeed. This relaxation
   is **only** active in the no-verify path; the verified path
   (``verify_ssl=True``) uses Python's OpenSSL defaults unchanged.
   Because it weakens TLS protections, it is intended for trusted LAN
   use only.

Error Handling
--------------

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice
   from pylocal_akuvox.exceptions import (
       AkuvoxConnectionError,
       AkuvoxAuthenticationError,
       AkuvoxValidationError,
   )

   async def main():
       try:
           async with AkuvoxDevice("192.168.1.100") as device:
               await device.add_user(
                   name="Bob",
                   user_id="2002",
                   web_relay="0",
                   schedule_relay="1001-1",
                   lift_floor_num="0",
                   private_pin="12ab",
               )
       except AkuvoxConnectionError as e:
           print(f"Cannot reach device: {e}")
       except AkuvoxAuthenticationError as e:
           print(f"Auth failed: {e}")
       except AkuvoxValidationError as e:
           print(f"Invalid input: {e}")

   asyncio.run(main())
