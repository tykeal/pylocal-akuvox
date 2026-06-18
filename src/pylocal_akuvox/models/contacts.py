# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contact / address-book data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pylocal_akuvox._capability_types import SchemaShape
from pylocal_akuvox.exceptions import AkuvoxParseError

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities


@dataclass(frozen=True, kw_only=True)
class Contact:
    """Contact entry in a door-phone or apartment-book address book.

    Door-phone records populate ``name``, optional ``id``, ``phone``,
    and ``group``. Apartment-book records may omit a device-assigned
    ``ID`` and additionally expose ``apt_name``, ``apt_num``,
    ``building``, and ``landline``. The library does not synthesize a
    unique identifier for apartment-book records. Apartment-book-only
    fields are read-fidelity fields and are intentionally omitted from
    :meth:`to_api_payload`.
    """

    name: str
    id: str | None = None
    phone: str | None = None
    group: str | None = None
    apt_name: str | None = None  # APTName
    apt_num: str | None = None  # APTNum
    building: str | None = None  # Building
    landline: str | None = None  # Landline

    @classmethod
    def from_api_response(
        cls,
        data: dict[str, Any],
        *,
        capabilities: DeviceCapabilities | None = None,
    ) -> Contact:
        """Create Contact from API response data.

        ``capabilities`` is an optional :class:`DeviceCapabilities`
        record. When supplied, the parser consults
        ``capabilities.schema_shapes.get("contact",
        SchemaShape.DOOR_PHONE)`` to choose between two parse paths:

        * :attr:`SchemaShape.DOOR_PHONE` (default): today's parser,
          byte-identical to the pre-refactor behaviour — requires
          ``Name`` (raises :class:`AkuvoxParseError` on missing
          ``Name``); optionally consumes ``ID``, ``Phone``, ``Group``.
        * :attr:`SchemaShape.APARTMENT_BOOK`: additive parser used by
          X915S current firmware. ``Name`` is required as on
          door-phone; ``ID`` is **not** required (apartment-book
          payloads from the device may omit it).
          Apartment-book-only fields are surfaced as ``apt_name``
          (``APTName``), ``apt_num`` (``APTNum``), ``building``
          (``Building``), and ``landline`` (``Landline``). Empty
          apartment-book strings are preserved as device-returned
          information.

        Omitting the ``capabilities`` kwarg (or supplying a record
        with no ``"contact"`` schema-shape entry) falls back to the
        door-phone path — preserving FR-016 for legacy callers.
        """
        shape = SchemaShape.DOOR_PHONE
        if capabilities is not None:
            shape = capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)

        try:
            name = data["Name"]
        except KeyError as exc:
            msg = f"Missing required field {exc} in contact data"
            raise AkuvoxParseError(msg) from exc

        if shape is SchemaShape.APARTMENT_BOOK:
            # Apartment-book payloads (X915S) may omit ``ID`` entirely.
            # ``Phone`` is read if present so a door-phone-style
            # payload still parses under the apartment-book branch.
            return cls(
                name=name,
                id=data.get("ID"),
                phone=data.get("Phone") or None,
                group=data.get("Group") or None,
                apt_name=data.get("APTName"),
                apt_num=data.get("APTNum"),
                building=data.get("Building"),
                landline=data.get("Landline"),
            )

        # Door-phone path — byte-identical to the pre-refactor parser.
        return cls(
            name=name,
            id=data.get("ID"),
            phone=data.get("Phone") or None,
            group=data.get("Group") or None,
        )

    def to_api_payload(self) -> dict[str, str]:
        """Convert to PascalCase dict for add/set API calls."""
        payload: dict[str, str] = {"Name": self.name}
        if self.id is not None:
            payload["ID"] = self.id
        if self.phone is not None:
            payload["Phone"] = self.phone
        if self.group is not None:
            payload["Group"] = self.group
        return payload
