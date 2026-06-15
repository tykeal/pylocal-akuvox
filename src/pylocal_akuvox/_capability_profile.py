# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability profile dataclasses for the Akuvox device API.

Split out from the former ``pylocal_akuvox.capabilities`` module per
spec ``009-capabilities-module-split`` so each focused submodule stays
under the project's 400-line aislop ``file-too-large`` threshold.

This module exports the three immutable record types used to describe
the effective capability profile for a connected device:

* :class:`FieldAliases` — observed field-name aliases for one logical
  field, in both read and write directions.
* :class:`Provenance` — bookkeeping for curated matrix entries.
* :class:`DeviceCapabilities` — the effective capability profile
  carried by an :class:`pylocal_akuvox.AkuvoxDevice`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, kw_only=True)
class FieldAliases:
    """Observed field-name aliases for one logical field.

    Both directions are tuples (immutable) so ``FieldAliases`` instances
    are themselves hashable and bytes-equal-comparable across probe
    runs. (The enclosing :class:`DeviceCapabilities` is *not* hashable
    because it wraps its mappings in :class:`types.MappingProxyType`
    for deep immutability — equality is the relevant invariant for the
    SC-002 idempotence contract.)
    """

    read: tuple[str, ...]
    write: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class Provenance:
    """Bookkeeping for curated matrix entries.

    Only set on entries inside ``CAPABILITY_MATRIX``; probe-derived
    profiles carry ``provenance=None`` per
    ``contracts/probe-api.md`` §"Provenance produced by the probe".
    """

    test_bench_device_id: str
    firmware_version: str
    library_version: str
    observed_at: str


@dataclass(frozen=True, kw_only=True)
class DeviceCapabilities:
    """Effective capability profile carried by one :class:`AkuvoxDevice`.

    All four mapping fields (``capabilities``, ``field_aliases``,
    ``schema_shapes``, ``notes``) are wrapped in
    :class:`types.MappingProxyType` by :meth:`__post_init__`, so
    post-construction mutation raises :class:`TypeError`. Constructors
    accept plain ``dict`` for ergonomic call-sites; the read-only
    wrapping is applied transparently. This enforces the deep
    immutability invariant gating logic relies on (a caller cannot do
    ``device._capabilities.notes["evil"] = "x"`` to corrupt the
    profile). See test ``test_device_capabilities_is_deeply_immutable``.
    """

    device_class: str
    firmware_version: str
    capabilities: Mapping[Capability, CapabilityStatus]
    field_aliases: Mapping[str, FieldAliases]
    schema_shapes: Mapping[str, SchemaShape]
    notes: Mapping[str, str] = field(default_factory=dict)
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        """Wrap every mapping field in a defensive read-only view.

        Defensively copies the input dict first so callers cannot retain
        a write handle to the underlying storage. Uses
        :func:`object.__setattr__` because the dataclass is
        ``frozen=True``.
        """
        for name in ("capabilities", "field_aliases", "schema_shapes", "notes"):
            object.__setattr__(
                self,
                name,
                MappingProxyType(dict(getattr(self, name))),
            )

    def status_of(self, capability: Capability) -> CapabilityStatus:
        """Return the status for ``capability``, defaulting to UNKNOWN.

        If ``capability not in self.capabilities``, returns
        :attr:`CapabilityStatus.UNKNOWN` (the "absent → UNKNOWN"
        default). This is the canonical representation: write
        capabilities the probe did not classify are absent from
        ``capabilities``, not present-with-UNKNOWN. ``status_of``
        collapses both shapes into the same observable behaviour so
        callers never need to distinguish.
        """
        return self.capabilities.get(capability, CapabilityStatus.UNKNOWN)

    def require(self, capability: Capability, *, allow_unknown: bool = False) -> None:
        """Raise :class:`AkuvoxUnsupportedError` unless gated SUPPORTED.

        With ``allow_unknown=True``, ``UNKNOWN`` status falls through
        (does not raise); the runtime HTTP attempt then either succeeds
        or surfaces ``AkuvoxUnsupportedError`` from the envelope-level
        translation in ``_http.py``. ``UNSUPPORTED`` always raises
        regardless of the ``allow_unknown`` flag.

        Per ``contracts/unsupported-error.md`` §"Raise-site contract"
        this raise populates the structured fields ``capability``,
        ``device_class``, and ``reason`` on the resulting exception so
        the integrator (and the closed-set
        ``test_reason_taxonomy_closed`` audit) can observe which
        capability gate fired and which three-valued status fired it.
        """
        status = self.status_of(capability)
        if status is CapabilityStatus.SUPPORTED:
            return
        if status is CapabilityStatus.UNSUPPORTED:
            msg = (
                f"Device class {self.device_class} does not support {capability.value}"
            )
            raise AkuvoxUnsupportedError(
                msg,
                capability=capability,
                device_class=self.device_class,
                reason="capability_missing",
            )
        # status is UNKNOWN
        if allow_unknown:
            return
        # Distinguish "device unrecognised" (no matrix entry, every
        # capability is UNKNOWN) from "device recognised but this
        # specific capability has UNKNOWN status". The discriminator
        # is the presence of the ``device_not_in_matrix`` note that
        # ``AkuvoxDevice.__aenter__`` writes on the conservative-empty
        # fallback profile (see ``contracts/matrix-lookup.md``
        # §"Connect-time integration").
        if "device_not_in_matrix" in self.notes:
            msg = (
                f"Device {self.device_class} not in capability matrix; "
                f"call device.probe_capabilities() to enumerate, or set "
                f"device.attempt_unknown_capability=True to opt in"
            )
            raise AkuvoxUnsupportedError(
                msg,
                capability=capability,
                device_class=self.device_class,
                reason="device_unrecognized",
            )
        msg = (
            f"Capability {capability.value} has unknown status on "
            f"{self.device_class}; add a matrix entry or set "
            f"device.attempt_unknown_capability=True to opt in"
        )
        raise AkuvoxUnsupportedError(
            msg,
            capability=capability,
            device_class=self.device_class,
            reason="capability_unknown",
        )

    @property
    def supported_set(self) -> frozenset[Capability]:
        """Return the set of capabilities whose status is SUPPORTED."""
        return frozenset(
            cap
            for cap, status in self.capabilities.items()
            if status is CapabilityStatus.SUPPORTED
        )


__all__ = ["DeviceCapabilities", "FieldAliases", "Provenance"]
