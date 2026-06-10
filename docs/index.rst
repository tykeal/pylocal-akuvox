..
   SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
   SPDX-License-Identifier: Apache-2.0

pylocal-akuvox
==============

Async Python library for the Akuvox local HTTP API.

**pylocal-akuvox** provides a single :class:`~pylocal_akuvox.AkuvoxDevice`
object for communicating with Akuvox intercoms and access controllers on the
LAN. It supports user/PIN management, relay control, schedule management,
and log retrieval over the device's local HTTP API.

Key features:

* **Async-only** — designed for ``asyncio`` event loops and Home Assistant
* **Single runtime dependency** — only ``aiohttp``
* **Full device management** — users, groups, contacts, PINs, relays, schedules, and logs
* **Multiple auth modes** — None, AllowList, Basic, and Digest
* **SSL support** — including self-signed certificate handling
* **Legacy TLS compatibility** — automatic OpenSSL SECLEVEL relaxation for older Akuvox devices (e.g. S562) when certificate verification is disabled
* **Comprehensive error handling** — typed exception hierarchy

.. code-block:: python

   import asyncio
   from pylocal_akuvox import AkuvoxDevice

   async def main():
       async with AkuvoxDevice("192.168.1.100") as device:
           info = await device.get_info()
           print(f"{info.model} — FW {info.firmware_version}")

   asyncio.run(main())

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quickstart
   api/index
   changelog
