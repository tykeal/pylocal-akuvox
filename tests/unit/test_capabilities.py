# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the capability profile types in ``pylocal_akuvox.capabilities``.

Covers tasks T009-T013 and T028a from
``specs/008-capability-matrix/tasks.md``: the static type surface
(``Capability`` / ``CapabilityStatus`` / ``FieldAliases`` /
``SchemaShape`` / ``Provenance``), the ``DeviceCapabilities`` shape
and gating, and the ``DeviceClassPattern`` matcher with all three
firmware-band forms (glob / floor / exact).

See also ``contracts/probe-api.md`` and ``contracts/matrix-lookup.md``.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from pylocal_akuvox.capabilities import (
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
    DeviceClassPattern,
    FieldAliases,
    Provenance,
    SchemaShape,
)
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError
from pylocal_akuvox.models import DeviceInfo

# ---------- T009: Capability enum -------------------------------------------


_EXPECTED_CAPABILITY_MEMBERS = (
    "USER_LIST",
    "USER_ADD",
    "USER_MODIFY",
    "USER_DELETE",
    "SCHEDULE_LIST",
    "SCHEDULE_ADD",
    "SCHEDULE_MODIFY",
    "SCHEDULE_DELETE",
    "GROUP_LIST",
    "GROUP_ADD",
    "GROUP_MODIFY",
    "GROUP_DELETE",
    "CONTACT_LIST",
    "CONTACT_ADD",
    "CONTACT_MODIFY",
    "CONTACT_DELETE",
    "RELAY_TRIGGER_API",
    "RELAY_TRIGGER_FCGI",
    "RELAY_STATUS",
    "DEVICE_CONFIG_GET",
    "DEVICE_CONFIG_SET",
    "LOG_DOOR",
    "LOG_CALL",
    "KEY_DISCOVERY",
)


def test_capability_has_every_expected_member() -> None:
    """Every data-model.md row maps to a Capability member."""
    actual = {member.name for member in Capability}
    for expected in _EXPECTED_CAPABILITY_MEMBERS:
        assert expected in actual, f"Capability.{expected} missing"


def test_capability_values_are_lowercase_dot_form() -> None:
    """Each Capability value is a lowercase domain.action[.variant] string."""
    for member in Capability:
        assert isinstance(member.value, str)
        assert member.value == member.value.lower()
        # domain.action shape: at least one '.' segment.
        assert "." in member.value


def test_capability_iteration_is_stable() -> None:
    """Iterating the enum twice yields the same order."""
    first = [m.name for m in Capability]
    second = [m.name for m in Capability]
    assert first == second


def test_capability_not_enumerated_in_public_reexports() -> None:
    """Adding a Capability member is not a public-API change.

    The package's ``__all__`` re-exports the ``Capability`` class but
    does NOT enumerate its members; new members are additive.
    """
    import pylocal_akuvox

    for name in pylocal_akuvox.__all__:
        # The public re-export name is "Capability" (the class), not
        # any individual member.
        for member in Capability:
            assert name != member.name


# ---------- T010: CapabilityStatus enum -------------------------------------


def test_capability_status_three_members_with_lowercase_values() -> None:
    """SUPPORTED / UNSUPPORTED / UNKNOWN with lowercase string values."""
    assert CapabilityStatus.SUPPORTED.value == "supported"
    assert CapabilityStatus.UNSUPPORTED.value == "unsupported"
    assert CapabilityStatus.UNKNOWN.value == "unknown"
    assert {m.name for m in CapabilityStatus} == {
        "SUPPORTED",
        "UNSUPPORTED",
        "UNKNOWN",
    }


def test_capability_status_iteration_stable() -> None:
    """Iterating CapabilityStatus twice yields the same order."""
    a = [m.name for m in CapabilityStatus]
    b = [m.name for m in CapabilityStatus]
    assert a == b


# ---------- T011: FieldAliases / SchemaShape / Provenance -------------------


def test_field_aliases_is_frozen_kw_only_dataclass() -> None:
    """FieldAliases.read/.write are tuples and the dataclass is frozen."""
    fa = FieldAliases(read=("Schedule", "ScheduleRelay"), write=("ScheduleRelay",))
    assert fa.read == ("Schedule", "ScheduleRelay")
    assert fa.write == ("ScheduleRelay",)
    with pytest.raises(Exception):  # noqa: B017,PT011 - frozen dataclass
        fa.read = ("X",)  # type: ignore[misc]


def test_field_aliases_is_kw_only() -> None:
    """FieldAliases must be constructed with keyword arguments."""
    with pytest.raises(TypeError):
        FieldAliases(("a",), ("b",))  # type: ignore[misc]


def test_schema_shape_members() -> None:
    """SchemaShape exposes the documented members with stable values."""
    assert SchemaShape.DOOR_PHONE.value == "door_phone"
    assert SchemaShape.APARTMENT_BOOK.value == "apartment_book"


def test_provenance_carries_required_fields() -> None:
    """Provenance fields round-trip and are immutable."""
    prov = Provenance(
        test_bench_device_id="X916-bench-001",
        firmware_version="916.30.10.114",
        library_version="0.5.0",
        observed_at="2026-01-15",
    )
    assert prov.test_bench_device_id == "X916-bench-001"
    assert prov.firmware_version == "916.30.10.114"
    assert prov.library_version == "0.5.0"
    assert prov.observed_at == "2026-01-15"
    with pytest.raises(Exception):  # noqa: B017,PT011 - frozen dataclass
        prov.firmware_version = "x"  # type: ignore[misc]


def test_provenance_is_kw_only() -> None:
    """Provenance must be constructed with keyword arguments."""
    with pytest.raises(TypeError):
        Provenance("x", "y", "z", "2026-01-01")  # type: ignore[misc]


# ---------- T012: DeviceCapabilities ----------------------------------------


def _make_caps(
    capabilities: dict[Capability, CapabilityStatus] | None = None,
    *,
    device_class: str = "X916",
    firmware_version: str = "916.30.10.114",
) -> DeviceCapabilities:
    """Build a minimal DeviceCapabilities for tests."""
    return DeviceCapabilities(
        device_class=device_class,
        firmware_version=firmware_version,
        capabilities=capabilities or {},
        field_aliases={},
        schema_shapes={},
        notes={},
    )


def test_status_of_returns_unknown_for_missing_capability() -> None:
    """Absent → UNKNOWN default per data-model.md §DeviceCapabilities."""
    dc = _make_caps()
    assert dc.status_of(Capability.USER_LIST) is CapabilityStatus.UNKNOWN


def test_require_does_not_raise_when_supported() -> None:
    """require() passes silently for SUPPORTED."""
    dc = _make_caps({Capability.USER_LIST: CapabilityStatus.SUPPORTED})
    dc.require(Capability.USER_LIST)


def test_require_raises_for_unsupported_with_capability_and_class_in_message() -> None:
    """UNSUPPORTED → AkuvoxUnsupportedError carrying capability + device class."""
    dc = _make_caps(
        {Capability.CONTACT_ADD: CapabilityStatus.UNSUPPORTED},
        device_class="X915S",
    )
    with pytest.raises(AkuvoxUnsupportedError) as excinfo:
        dc.require(Capability.CONTACT_ADD)
    msg = str(excinfo.value)
    assert Capability.CONTACT_ADD.value in msg
    assert "X915S" in msg


def test_require_raises_for_unknown_default_message_mentions_unknown_status() -> None:
    """UNKNOWN with default ``allow_unknown=False`` raises with discriminator."""
    dc = _make_caps()  # USER_ADD is absent → UNKNOWN
    with pytest.raises(AkuvoxUnsupportedError) as excinfo:
        dc.require(Capability.USER_ADD)
    msg = str(excinfo.value)
    assert "unknown status" in msg


def test_require_with_allow_unknown_does_not_raise_for_unknown() -> None:
    """allow_unknown=True bypasses the UNKNOWN raise."""
    dc = _make_caps()
    dc.require(Capability.USER_ADD, allow_unknown=True)


def test_require_with_allow_unknown_still_raises_for_unsupported() -> None:
    """allow_unknown=True does NOT bypass UNSUPPORTED."""
    dc = _make_caps(
        {Capability.CONTACT_ADD: CapabilityStatus.UNSUPPORTED},
        device_class="X915S",
    )
    with pytest.raises(AkuvoxUnsupportedError):
        dc.require(Capability.CONTACT_ADD, allow_unknown=True)


def test_supported_set_returns_only_supported_keys() -> None:
    """supported_set returns a frozenset of SUPPORTED capabilities."""
    dc = _make_caps(
        {
            Capability.USER_LIST: CapabilityStatus.SUPPORTED,
            Capability.CONTACT_LIST: CapabilityStatus.SUPPORTED,
            Capability.RELAY_STATUS: CapabilityStatus.UNSUPPORTED,
            Capability.LOG_DOOR: CapabilityStatus.UNKNOWN,
        }
    )
    s = dc.supported_set
    assert isinstance(s, frozenset)
    assert s == frozenset({Capability.USER_LIST, Capability.CONTACT_LIST})


# ---------- T013: DeviceClassPattern ----------------------------------------


def _di(model: str, firmware: str) -> DeviceInfo:
    """Build a synthetic DeviceInfo fixture for pattern matching."""
    return DeviceInfo(
        model=model,
        mac_address="00:00:00:00:00:00",
        firmware_version=firmware,
        hardware_version="x",
    )


def test_pattern_glob_matches_within_band() -> None:
    """Glob band matches every observed firmware whose prefix matches."""
    p = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert p.matches(_di("X916", "916.30.10.0")) is True
    assert p.matches(_di("X916", "916.30.10.114")) is True
    assert p.matches(_di("X916S", "916.30.10.50")) is True


def test_pattern_glob_rejects_outside_band() -> None:
    """Glob band rejects firmwares outside the prefix."""
    p = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert p.matches(_di("X916", "916.30.11.0")) is False
    assert p.matches(_di("E18C", "916.30.10.0")) is False


def test_pattern_floor_excludes_below_floor() -> None:
    """Floor band rejects firmwares strictly below the floor."""
    p = DeviceClassPattern(model_prefix="X915S", firmware_band="2915.30.10.114+")
    # The X915S edge case from the spec: 113 must NOT match a 114+ floor.
    assert p.matches(_di("X915S", "2915.30.10.113")) is False
    assert p.matches(_di("X915S", "2915.30.10.114")) is True
    assert p.matches(_di("X915S", "2915.30.10.115")) is True
    assert p.matches(_di("X915S", "2915.31.0.0")) is True


def test_pattern_exact_match() -> None:
    """Exact band matches one and only one firmware tuple."""
    p = DeviceClassPattern(model_prefix="IT83", firmware_band="83.30.10.4")
    assert p.matches(_di("IT83", "83.30.10.4")) is True
    assert p.matches(_di("IT83", "83.30.10.5")) is False
    assert p.matches(_di("IT83", "83.30.10.3")) is False


def test_pattern_rejects_nonmatching_model_prefix() -> None:
    """A firmware-only match does not satisfy the pattern."""
    p = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert p.matches(_di("E18C", "916.30.10.0")) is False


def test_pattern_non_numeric_firmware_does_not_raise() -> None:
    """A wholly non-numeric firmware returns False without raising."""
    p = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert p.matches(_di("X916", "abcdef")) is False


def test_pattern_strips_non_numeric_trailing_label() -> None:
    """Firmware like '916.30.10.114-beta' parses to (916,30,10,114)."""
    p = DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*")
    assert p.matches(_di("X916", "916.30.10.114-beta")) is True


def test_pattern_rejects_wildcard_in_non_trailing_position() -> None:
    """Bad band like '916.30.*.10' raises ValueError at construction."""
    with pytest.raises(ValueError, match="firmware_band"):
        DeviceClassPattern(model_prefix="X", firmware_band="916.30.*.10")


def test_pattern_rejects_multiple_wildcards_in_glob_form() -> None:
    """Bad band like '*.30.10.*' (multiple stars) raises ValueError."""
    with pytest.raises(ValueError, match="trailing segment"):
        DeviceClassPattern(model_prefix="X", firmware_band="*.30.10.*")


def test_pattern_rejects_glob_with_star_in_segment() -> None:
    """Bad band like '9*6.30.10.*' (star inside non-trailing segment)."""
    with pytest.raises(ValueError, match="firmware_band"):
        DeviceClassPattern(model_prefix="X", firmware_band="9*6.30.10.*")


def test_pattern_rejects_glob_missing_dot_before_wildcard() -> None:
    """Bad band like '916.30.10*' (no '.' between segment and '*') raises ValueError.

    Without explicit validation, ``split('.')[:-1]`` would silently drop
    the trailing ``"10*"`` and treat the band as the glob ``"916.30.*"``,
    causing incorrect matches.
    """
    with pytest.raises(ValueError, match="trailing wildcard must be"):
        DeviceClassPattern(model_prefix="X", firmware_band="916.30.10*")


def test_pattern_rejects_empty_band() -> None:
    """Empty firmware_band raises ValueError."""
    with pytest.raises(ValueError, match="firmware_band"):
        DeviceClassPattern(model_prefix="X", firmware_band="")


def test_pattern_rejects_non_numeric_segment_in_glob() -> None:
    """Non-numeric segment in a glob form raises ValueError."""
    with pytest.raises(ValueError, match="firmware_band"):
        DeviceClassPattern(model_prefix="X", firmware_band="abc.30.10.*")


def test_pattern_rejects_non_numeric_segment_in_floor() -> None:
    """Non-numeric segment in a floor form raises ValueError."""
    with pytest.raises(ValueError, match="firmware_band"):
        DeviceClassPattern(model_prefix="X", firmware_band="abc.30.10.4+")


def test_pattern_rejects_non_numeric_segment_in_exact() -> None:
    """Non-numeric segment in an exact form raises ValueError."""
    with pytest.raises(ValueError, match="firmware_band"):
        DeviceClassPattern(model_prefix="X", firmware_band="abc.30.10.4")


def test_pattern_glob_with_short_observed_firmware() -> None:
    """A shorter observed firmware than the glob's prefix segments fails."""
    p = DeviceClassPattern(model_prefix="X", firmware_band="916.30.10.*")
    assert p.matches(_di("X", "916.30")) is False


def test_pattern_floor_with_shorter_observed_padded_with_zeros() -> None:
    """Floor matches when padding both sides to equal length."""
    p = DeviceClassPattern(model_prefix="X", firmware_band="2915.30.10.0+")
    # observed (2915, 30, 10) padded → (2915, 30, 10, 0) which equals floor
    assert p.matches(_di("X", "2915.30.10")) is True


# ---------- T028a: DeepImmutability ----------------------------------------


def test_device_capabilities_is_deeply_immutable() -> None:
    """All four mappings wrap as MappingProxyType and reject mutation."""
    initial_notes = {"a": "b"}
    dc = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={Capability.USER_LIST: CapabilityStatus.SUPPORTED},
        field_aliases={"schedule_relay": FieldAliases(read=("Schedule",), write=())},
        schema_shapes={"contact": SchemaShape.DOOR_PHONE},
        notes=initial_notes,
    )
    # Each mapping field is a MappingProxyType.
    assert isinstance(dc.capabilities, MappingProxyType)
    assert isinstance(dc.field_aliases, MappingProxyType)
    assert isinstance(dc.schema_shapes, MappingProxyType)
    assert isinstance(dc.notes, MappingProxyType)

    # Mutation attempts raise TypeError.
    with pytest.raises(TypeError):
        dc.notes["evil"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        dc.capabilities[Capability.USER_ADD] = (  # type: ignore[index]
            CapabilityStatus.SUPPORTED
        )
    with pytest.raises(TypeError):
        dc.field_aliases["x"] = FieldAliases(  # type: ignore[index]
            read=(), write=()
        )
    with pytest.raises(TypeError):
        dc.schema_shapes["x"] = SchemaShape.DOOR_PHONE  # type: ignore[index]

    # Defensive copy: post-construction mutation of the input does not
    # leak into the wrapped view.
    initial_notes["c"] = "d"
    assert dict(dc.notes) == {"a": "b"}
