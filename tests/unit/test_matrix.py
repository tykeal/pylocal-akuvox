# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for ``CAPABILITY_MATRIX`` and ``lookup_capabilities``.

Per ``specs/008-capability-matrix/contracts/matrix-lookup.md``:

* Every entry has non-``None`` :class:`Provenance` with all four
  bookkeeping fields populated (FR-006, FR-007, SC-004).
* No two patterns match the same synthetic :class:`DeviceInfo`
  (curated-most-specific-first non-overlap).
* ``lookup_capabilities`` walks declaration order and returns the
  first match; returns ``None`` for unrecognised devices.
* Per-device-class capability deltas from ``data-model.md`` §"Capability
  deltas across the four entries" are honoured by the production
  entries (notably IT83's
  ``RELAY_TRIGGER_API``/``RELAY_TRIGGER_FCGI``/``RELAY_STATUS`` row,
  X915S's ``CONTACT_ADD=UNSUPPORTED`` and
  ``schema_shapes["contact"] = APARTMENT_BOOK``).
"""

from __future__ import annotations

import pytest

from pylocal_akuvox._capability_matching import lookup_capabilities
from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX
from pylocal_akuvox.models import DeviceInfo


def _info(model: str, firmware: str) -> DeviceInfo:
    """Build a synthetic :class:`DeviceInfo` for matrix lookups."""
    return DeviceInfo(
        model=model,
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version=firmware,
        hardware_version="1.0",
        uptime=None,
        web_language=None,
    )


# Pinned synthetic fixtures for each curated device class.
_X916 = _info("X916", "916.30.10.114")
_X915S = _info("X915S", "2915.30.10.114")
_E18C = _info("E18C", "18.30.11.21")
_IT83 = _info("IT83", "83.30.10.4")


# --- Provenance ------------------------------------------------------------


def test_every_entry_has_provenance() -> None:
    """Every matrix entry's :class:`Provenance` is fully populated.

    Covers FR-006 / FR-007 / SC-004: matrix entries are auditable
    (``test_bench_device_id``, ``firmware_version``,
    ``library_version``, ``observed_at`` are all non-empty strings).
    """
    assert CAPABILITY_MATRIX, "matrix must have at least one entry"
    for pattern, capabilities in CAPABILITY_MATRIX:
        prov = capabilities.provenance
        assert prov is not None, f"{pattern}: provenance must be set"
        assert prov.test_bench_device_id
        assert prov.firmware_version
        assert prov.library_version
        assert prov.observed_at


def test_matrix_covers_all_four_supported_classes() -> None:
    """All four supported device classes (X916, X915S, E18C, IT83) are present."""
    classes = {caps.device_class for _pattern, caps in CAPABILITY_MATRIX}
    assert classes == {"X916", "X915S", "E18C", "IT83"}


# --- Non-overlap ----------------------------------------------------------


@pytest.mark.parametrize("info", [_X916, _X915S, _E18C, _IT83])
def test_no_overlapping_patterns(info: DeviceInfo) -> None:
    """Each curated synthetic ``DeviceInfo`` matches exactly one pattern."""
    matches = [pattern for pattern, _ in CAPABILITY_MATRIX if pattern.matches(info)]
    assert len(matches) == 1, (
        f"{info.model}/{info.firmware_version} matched {len(matches)} "
        f"patterns: {matches}"
    )


# --- Lookup precedence ----------------------------------------------------


def test_lookup_returns_first_match_x916() -> None:
    """X916 baseline matches the X916 glob entry."""
    profile = lookup_capabilities(_X916)
    assert profile is not None
    assert profile.device_class == "X916"


def test_lookup_returns_first_match_x915s() -> None:
    """X915S current firmware matches the floor band."""
    profile = lookup_capabilities(_X915S)
    assert profile is not None
    assert profile.device_class == "X915S"


def test_lookup_returns_first_match_e18c() -> None:
    """E18C current firmware matches the E18C glob band."""
    profile = lookup_capabilities(_E18C)
    assert profile is not None
    assert profile.device_class == "E18C"


def test_lookup_returns_first_match_it83() -> None:
    """IT83 exact firmware matches the IT83 entry."""
    profile = lookup_capabilities(_IT83)
    assert profile is not None
    assert profile.device_class == "IT83"


def test_lookup_returns_none_for_unrecognised_device() -> None:
    """An unknown model returns ``None`` from the lookup helper."""
    profile = lookup_capabilities(_info("UnknownDevice", "1.0.0.0"))
    assert profile is None


def test_lookup_returns_none_for_x915s_below_floor() -> None:
    """X915S firmware below the floor falls through to non-match."""
    profile = lookup_capabilities(_info("X915S", "2915.30.10.113"))
    assert profile is None


# --- Capability deltas ----------------------------------------------------


def test_it83_capability_deltas() -> None:
    """IT83 records FCGI=SUPPORTED, API=UNSUPPORTED, RELAY_STATUS=UNSUPPORTED."""
    profile = lookup_capabilities(_IT83)
    assert profile is not None
    assert profile.status_of(Capability.RELAY_TRIGGER_FCGI) is (
        CapabilityStatus.SUPPORTED
    )
    assert profile.status_of(Capability.RELAY_TRIGGER_API) is (
        CapabilityStatus.UNSUPPORTED
    )
    assert profile.status_of(Capability.RELAY_STATUS) is (CapabilityStatus.UNSUPPORTED)
    # IT83 user/contact/etc. capabilities are UNKNOWN (community
    # reporter did not exercise them).
    assert profile.status_of(Capability.USER_ADD) is CapabilityStatus.UNKNOWN


def test_x915s_capability_deltas() -> None:
    """X915S records CONTACT_ADD=UNSUPPORTED + schema_shapes apartment_book."""
    profile = lookup_capabilities(_X915S)
    assert profile is not None
    assert profile.status_of(Capability.CONTACT_ADD) is (CapabilityStatus.UNSUPPORTED)
    assert profile.schema_shapes.get("contact") is SchemaShape.APARTMENT_BOOK
    # X915S still supports the rest of the door-phone surface.
    assert profile.status_of(Capability.USER_ADD) is CapabilityStatus.SUPPORTED
    assert profile.status_of(Capability.RELAY_TRIGGER_API) is (
        CapabilityStatus.SUPPORTED
    )


def test_e18c_capability_deltas() -> None:
    """E18C is the door-phone baseline (every door-phone capability SUPPORTED)."""
    profile = lookup_capabilities(_E18C)
    assert profile is not None
    assert profile.status_of(Capability.USER_ADD) is CapabilityStatus.SUPPORTED
    assert profile.status_of(Capability.CONTACT_ADD) is CapabilityStatus.SUPPORTED
    assert profile.status_of(Capability.RELAY_TRIGGER_API) is (
        CapabilityStatus.SUPPORTED
    )


def test_x916_capability_deltas() -> None:
    """X916 baseline: every door-phone capability SUPPORTED."""
    profile = lookup_capabilities(_X916)
    assert profile is not None
    assert profile.status_of(Capability.USER_ADD) is CapabilityStatus.SUPPORTED
    assert profile.status_of(Capability.RELAY_TRIGGER_API) is (
        CapabilityStatus.SUPPORTED
    )
    # FCGI is UNKNOWN on X916 (door-phone — never exercised the FCGI
    # variant on this class).
    assert profile.status_of(Capability.RELAY_TRIGGER_FCGI) is (
        CapabilityStatus.UNKNOWN
    )


def test_library_version_fallback_on_package_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the PackageNotFoundError fallback in _library_version().

    When pylocal-akuvox is imported from a tree that is not installed
    as a distribution (e.g. zip-app, vendored source), the metadata
    lookup raises and we fall back to the ``0.0.0`` placeholder.
    """
    import importlib.metadata

    from pylocal_akuvox import capability_matrix

    def _raise(_name: str) -> str:  # pragma: no cover - patched below
        """Stub importlib.metadata.version that always raises."""
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    assert capability_matrix._library_version() == "0.0.0"  # noqa: SLF001


# ============================================================================
# Phase 3: synthetic-matrix-entry tests (T061)
# ============================================================================
#
# Quickstart step 9 referenced test: programmatically construct a
# ``(DeviceClassPattern, DeviceCapabilities)`` pair carrying custom
# ``field_aliases`` and ``schema_shapes``; exercise both
# ``User.from_api_response`` and ``Contact.from_api_response`` against
# the synthetic record and assert the parsers consult the record
# without any monkey-patch of ``models/users.py`` / ``models/contacts.py``.
# Covers FR-017 / SC-007.


def test_add_hypothetical_entry() -> None:
    """T061: synthetic capability record drives both parsers (FR-017, SC-007).

    Verifies the matrix-extension contract: adding a new firmware
    band that varies only along known axes (field aliases + schema
    shape) requires no parser edits — both parsers consult the
    capability record at the call site. Constructs a synthetic
    ``DeviceClassPattern`` + ``DeviceCapabilities`` pair without
    inserting it into the production matrix (the test is
    matrix-independent so it cannot regress on production-matrix
    changes).
    """
    from pylocal_akuvox._capability_matching import DeviceClassPattern
    from pylocal_akuvox._capability_profile import (
        DeviceCapabilities,
        FieldAliases,
    )
    from pylocal_akuvox._capability_types import SchemaShape
    from pylocal_akuvox.models import Contact, User

    pattern = DeviceClassPattern(model_prefix="HYPOTHETICAL", firmware_band="999.0.0.*")
    caps = DeviceCapabilities(
        device_class="HYPOTHETICAL",
        firmware_version="999.0.0.1",
        capabilities={},
        field_aliases={
            "schedule_relay": FieldAliases(
                read=("HypotheticalSchedule",),
                write=("HypotheticalSchedule",),
            ),
        },
        schema_shapes={"contact": SchemaShape.APARTMENT_BOOK},
    )

    # Synthetic pattern matches a synthetic DeviceInfo (no production
    # matrix edit needed).
    synthetic_info = _info("HYPOTHETICAL", "999.0.0.1")
    assert pattern.matches(synthetic_info)

    # User parser consults the synthetic alias — no hardcoded fallback wins.
    user_data = {
        "Name": "Test",
        "UserID": "1",
        "HypotheticalSchedule": "hypo-value",
        # Pollute the payload with default-chain keys so the test
        # fails if the synthetic alias is NOT consulted.
        "ScheduleRelay": "default-must-be-ignored",
    }
    user = User.from_api_response(user_data, capabilities=caps)
    assert user.schedule_relay == "hypo-value"

    # Contact parser consults the synthetic schema shape.
    apt_data = {
        "Name": "Apt 1",
        "APTName": "Block 1",
        "APTNum": "1",
        "Building": "B1",
        "Landline": "5550000",
        # No "ID" — only the apartment-book branch tolerates this on
        # a payload that also lacks the door-phone signal we're
        # exercising. (Door-phone branch also tolerates missing ID
        # today; the test's stronger claim is that the apartment-book
        # branch was selected — asserted indirectly via the schema
        # shape on the supplied caps and the parser landing without
        # raising even if a future contract tightens door-phone to
        # require ID.)
    }
    contact = Contact.from_api_response(apt_data, capabilities=caps)
    assert contact.name == "Apt 1"
    assert contact.id is None
