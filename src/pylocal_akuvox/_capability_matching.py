# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability matrix matching for the Akuvox device API.

Split out from the former ``pylocal_akuvox.capabilities`` module per
spec ``009-capabilities-module-split`` so each focused submodule stays
under the project's 400-line aislop ``file-too-large`` threshold.

This module exports the firmware-band parser and device-class pattern
matcher that the curated ``CAPABILITY_MATRIX`` lookup walks:

* :func:`_parse_firmware_segments` — single-underscore-prefixed helper
  intentionally kept importable for white-box testing per spec
  Decision 6, but NOT in ``__all__``.
* :class:`DeviceClassPattern` — model-prefix + firmware-band matcher.
* :func:`lookup_capabilities` — matrix dispatch entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox.models import DeviceInfo


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
    lazily inside the function body to avoid an import cycle:
    ``capability_matrix`` imports :class:`DeviceClassPattern` (defined
    in *this* module) at module load to type its
    ``(DeviceClassPattern, DeviceCapabilities)`` entries, so a
    top-level reverse import of ``CAPABILITY_MATRIX`` from this module
    would close the loop on first access.
    """
    # Lazy import to break the circular dependency between this
    # module and ``capability_matrix`` (which imports
    # ``DeviceClassPattern`` from this module at load time).
    from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX

    for pattern, capabilities in CAPABILITY_MATRIX:
        if pattern.matches(device_info):
            return capabilities
    return None


__all__ = ["DeviceClassPattern", "lookup_capabilities"]
