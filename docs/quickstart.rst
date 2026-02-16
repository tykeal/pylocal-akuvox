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
               schedule_relay="1001-1;",
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

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           await device.trigger_relay(num=1, delay=5)

   asyncio.run(main())

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
                   schedule_relay="1001-1;",
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
