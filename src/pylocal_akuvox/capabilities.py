# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability profile types for the Akuvox device API.

This module defines the static type surface introduced by issue #123:

* :class:`Capability` — canonical capability identifiers.
* :class:`CapabilityStatus` — three-valued status (SUPPORTED /
  UNSUPPORTED / UNKNOWN).
* :class:`SchemaShape` — contact resource schema variants.
* :class:`FieldAliases` — observed field-name aliases for one logical
  field, in both read and write directions.
* :class:`Provenance` — bookkeeping for curated matrix entries.
* :class:`DeviceCapabilities` — the effective capability profile carried
  by an :class:`pylocal_akuvox.AkuvoxDevice`.
* :class:`DeviceClassPattern` — model-prefix + firmware-band matcher
  used as a curated-matrix key (full matrix arrives in Phase 2).

See ``specs/008-capability-matrix/data-model.md`` and
``specs/008-capability-matrix/contracts/{probe-api,matrix-lookup}.md``
for the contracts that drive the shapes here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pylocal_akuvox.models import DeviceInfo


class Capability(enum.Enum):
    """Canonical capability identifiers.

    String values use a ``domain.action[.variant]`` shape so they are
    grep-friendly and stable in serialized notes/provenance.

    The enum is **extensible**: new members append. Existing members do
    not change name or value (FR-001).
    """

    USER_LIST = "user.list"
    USER_ADD = "user.add"
    USER_MODIFY = "user.modify"
    USER_DELETE = "user.delete"
    SCHEDULE_LIST = "schedule.list"
    SCHEDULE_ADD = "schedule.add"
    SCHEDULE_MODIFY = "schedule.modify"
    SCHEDULE_DELETE = "schedule.delete"
    GROUP_LIST = "group.list"
    GROUP_ADD = "group.add"
    GROUP_MODIFY = "group.modify"
    GROUP_DELETE = "group.delete"
    CONTACT_LIST = "contact.list"
    CONTACT_ADD = "contact.add"
    CONTACT_MODIFY = "contact.modify"
    CONTACT_DELETE = "contact.delete"
    RELAY_TRIGGER_API = "relay.trigger.api"
    RELAY_TRIGGER_FCGI = "relay.trigger.fcgi"
    RELAY_STATUS = "relay.status"
    DEVICE_CONFIG_GET = "device.config.get"
    DEVICE_CONFIG_SET = "device.config.set"
    LOG_DOOR = "log.door"
    LOG_CALL = "log.call"
    KEY_DISCOVERY = "key.discovery"


class CapabilityStatus(enum.Enum):
    """Three-valued capability status.

    * ``SUPPORTED`` — confirmed positive evidence.
    * ``UNSUPPORTED`` — confirmed negative evidence (e.g. ``unsupported
      action`` envelope or ``No handlers for this request``).
    * ``UNKNOWN`` — no positive evidence either way; the conservative
      default returned by :meth:`DeviceCapabilities.status_of` for any
      capability not explicitly listed.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class SchemaShape(enum.Enum):
    """Contact resource schema variants observed across device classes."""

    DOOR_PHONE = "door_phone"
    APARTMENT_BOOK = "apartment_book"


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


def _parse_firmware_segments(firmware: str) -> tuple[int, ...] | None:
    """Parse ``firmware`` into an integer tuple, returning None on failure.

    Splits on ``.`` and discards any non-numeric trailing label
    (e.g. ``"916.30.10.114-beta"`` → ``(916, 30, 10, 114)``). A wholly
    non-numeric firmware string returns ``None`` so callers can treat
    it as a non-match without raising.
    """
    parts = firmware.split(".")
    out: list[int] = []
    for part in parts:
        # Strip any non-numeric trailing label like "-beta".
        digits: list[str] = []
        for ch in part:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        if not digits:
            # Wholly non-numeric segment — accept what we have so far
            # but only if at least one numeric segment was consumed.
            break
        out.append(int("".join(digits)))
    if not out:
        return None
    return tuple(out)


@dataclass(frozen=True, kw_only=True)
class DeviceClassPattern:
    """Model-prefix + firmware-band matcher used as a matrix key.

    Construction validates the firmware-band form (glob / floor /
    exact). Bad input (e.g. ``"916.30.*.10"`` — wildcard not in the
    trailing position) raises :class:`ValueError` at construction time,
    surfacing matrix-author errors at import time.

    The parsed-form fields (``_band_kind``, ``_band_floor``,
    ``_band_segments``) are populated from ``firmware_band`` by
    :meth:`__post_init__` and are excluded from equality / repr so two
    patterns with the same ``model_prefix`` + ``firmware_band`` compare
    equal regardless of the parsed shape.
    """

    model_prefix: str
    firmware_band: str
    _band_kind: str = field(init=False, compare=False, repr=False)
    _band_segments: tuple[int | str, ...] = field(
        init=False, compare=False, repr=False, default=()
    )
    _band_floor: tuple[int, ...] = field(
        init=False, compare=False, repr=False, default=()
    )

    def __post_init__(self) -> None:
        """Parse ``firmware_band`` into one of three internal forms."""
        band = self.firmware_band
        if not band:
            msg = f"firmware_band must be non-empty, got {band!r}"
            raise ValueError(msg)

        if band.endswith("*"):
            raw_segments = band.split(".")
            if raw_segments[-1] != "*":
                # Catches malformed forms like "916.30.10*" (no '.'
                # between the trailing numeric segment and the
                # wildcard). Without this check `split('.')[:-1]`
                # would silently drop the "10*" segment and treat
                # the band as the glob "916.30.*".
                msg = (
                    f"firmware_band {band!r}: trailing wildcard must be "
                    f"its own segment (e.g. '916.30.10.*', not "
                    f"'916.30.10*')"
                )
                raise ValueError(msg)
            non_wild = raw_segments[:-1]
            if any(seg == "*" for seg in non_wild) or "*" in "".join(non_wild):
                msg = (
                    f"firmware_band {band!r}: '*' must be the only "
                    f"wildcard and must occupy the trailing segment"
                )
                raise ValueError(msg)
            try:
                numeric = tuple(int(seg) for seg in non_wild)
            except ValueError as exc:
                msg = f"firmware_band {band!r}: non-numeric segment in glob form"
                raise ValueError(msg) from exc
            object.__setattr__(self, "_band_kind", "glob")
            segments: tuple[int | str, ...] = (*numeric, "*")
            object.__setattr__(self, "_band_segments", segments)
        elif band.endswith("+"):
            try:
                numeric = tuple(int(seg) for seg in band[:-1].split("."))
            except ValueError as exc:
                msg = f"firmware_band {band!r}: non-numeric segment in floor form"
                raise ValueError(msg) from exc
            object.__setattr__(self, "_band_kind", "floor")
            object.__setattr__(self, "_band_floor", numeric)
        else:
            if "*" in band or "+" in band:
                msg = (
                    f"firmware_band {band!r}: malformed exact form "
                    f"(unexpected wildcard / floor marker)"
                )
                raise ValueError(msg)
            try:
                numeric = tuple(int(seg) for seg in band.split("."))
            except ValueError as exc:
                msg = f"firmware_band {band!r}: non-numeric segment in exact form"
                raise ValueError(msg) from exc
            object.__setattr__(self, "_band_kind", "exact")
            object.__setattr__(self, "_band_segments", tuple(numeric))

    def matches(self, device_info: DeviceInfo) -> bool:
        """Return True iff ``device_info`` matches this pattern.

        Both the model prefix and the firmware band must match. A
        wholly non-numeric firmware string returns ``False`` (does not
        raise) so unknown-format firmwares are simply non-matches.
        """
        if not device_info.model.startswith(self.model_prefix):
            return False

        observed = _parse_firmware_segments(device_info.firmware_version)
        if observed is None:
            return False

        if self._band_kind == "glob":
            non_wild = tuple(
                int(seg) for seg in self._band_segments[:-1] if isinstance(seg, int)
            )
            if len(observed) < len(non_wild):
                return False
            return observed[: len(non_wild)] == non_wild
        if self._band_kind == "floor":
            length = max(len(observed), len(self._band_floor))
            obs_padded = observed + (0,) * (length - len(observed))
            floor_padded = self._band_floor + (0,) * (length - len(self._band_floor))
            return obs_padded >= floor_padded
        # exact
        exact_segments = tuple(
            int(seg) for seg in self._band_segments if isinstance(seg, int)
        )
        return observed == exact_segments


__all__ = [
    "Capability",
    "CapabilityStatus",
    "DeviceCapabilities",
    "DeviceClassPattern",
    "FieldAliases",
    "Provenance",
    "SchemaShape",
    "lookup_capabilities",
]


def lookup_capabilities(device_info: DeviceInfo) -> DeviceCapabilities | None:
    """Return the first matching ``CAPABILITY_MATRIX`` entry, or ``None``.

    Walks :data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX` in
    declaration order (curated most-specific-first) and returns the
    first ``DeviceCapabilities`` whose paired
    :class:`DeviceClassPattern` matches ``device_info``. Returns
    ``None`` for an unrecognised device — callers should fall back to
    a conservative-empty profile and direct the integrator to
    :meth:`AkuvoxDevice.probe_capabilities` (FR-013).

    The :mod:`pylocal_akuvox.capability_matrix` module is imported
    lazily inside the function body to avoid an import cycle: that
    module imports the dataclasses defined here, so a top-level
    import would form a cycle on first access.
    """
    # Lazy import to break the circular dependency between this
    # module and ``capability_matrix`` (which imports our enums and
    # dataclasses at module load).
    from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX

    for pattern, capabilities in CAPABILITY_MATRIX:
        if pattern.matches(device_info):
            return capabilities
    return None
