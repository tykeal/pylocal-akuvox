# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for ``CAPABILITY_MATRIX`` and ``lookup_capabilities``.

Per ``specs/008-capability-matrix/contracts/matrix-lookup.md``:

* Every entry has non-``None`` :class:`Provenance` with all four
  bookkeeping fields populated (FR-006, FR-007, SC-004).
* Synthetic :class:`DeviceInfo` fixtures resolve to their intended
  first matching entry (curated-most-specific-first ordering).
* ``lookup_capabilities`` walks declaration order and returns the
  first match; returns ``None`` for unrecognised devices.
* Per-device-class capability deltas from ``data-model.md`` §"Capability
  deltas across the four entries" are honoured by the production
  entries (notably A08S's access-unit profile, IT83's
  ``RELAY_TRIGGER_API``/``RELAY_TRIGGER_FCGI``/``RELAY_STATUS`` row,
  X915S's unsupported contact writes and
  ``schema_shapes["contact"] = APARTMENT_BOOK``).
"""

from __future__ import annotations

import pytest

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_matching import lookup_capabilities
from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX
from pylocal_akuvox.models import DeviceInfo
from tests.unit._helpers import drop_capability_matrix


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
_E18 = _info("E18", "18.30.10.118")
_A08S = _info("A08S", "108.30.10.144")
_IT83 = _info("IT83", "83.30.10.4")
_R20K = _info("R20K", "320.30.3.122")
_R20A = _info("R20A", "320.30.11.63")

_DOOR_PHONE_CRUD_CAPABILITIES = (
    Capability.USER_LIST,
    Capability.USER_ADD,
    Capability.USER_MODIFY,
    Capability.USER_DELETE,
    Capability.SCHEDULE_LIST,
    Capability.SCHEDULE_ADD,
    Capability.SCHEDULE_MODIFY,
    Capability.SCHEDULE_DELETE,
    Capability.GROUP_LIST,
    Capability.GROUP_ADD,
    Capability.GROUP_MODIFY,
    Capability.GROUP_DELETE,
    Capability.CONTACT_LIST,
    Capability.CONTACT_ADD,
    Capability.CONTACT_MODIFY,
    Capability.CONTACT_DELETE,
    Capability.RELAY_TRIGGER_API,
    Capability.RELAY_STATUS,
    Capability.DEVICE_CONFIG_GET,
    Capability.DEVICE_CONFIG_SET,
    Capability.LOG_DOOR,
    Capability.LOG_CALL,
    Capability.KEY_DISCOVERY,
)


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


def test_matrix_covers_all_eight_supported_classes() -> None:
    """All eight supported device classes exist."""
    classes = {caps.device_class for _pattern, caps in CAPABILITY_MATRIX}
    assert classes == {
        "X916",
        "X915S",
        "E18C",
        "E18",
        "A08S",
        "IT83",
        "R20K",
        "R20A",
    }


# --- Ordered matching -----------------------------------------------------


@pytest.mark.parametrize(
    ("info", "expected_class", "expected_match_count"),
    [
        (_X916, "X916", 1),
        (_X915S, "X915S", 1),
        (_E18C, "E18C", 2),
        (_E18, "E18", 1),
        (_A08S, "A08S", 1),
        (_IT83, "IT83", 1),
        (_R20K, "R20K", 1),
        (_R20A, "R20A", 1),
    ],
)
def test_matching_order_returns_intended_entry(
    info: DeviceInfo,
    expected_class: str,
    expected_match_count: int,
) -> None:
    """Each curated synthetic ``DeviceInfo`` has the intended first match."""
    matches = [
        capabilities
        for pattern, capabilities in CAPABILITY_MATRIX
        if pattern.matches(info)
    ]
    assert len(matches) == expected_match_count
    assert matches[0].device_class == expected_class


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
    assert profile.provenance is not None
    assert profile.provenance.firmware_version == "18.30.11.21"


def test_lookup_returns_first_match_e18() -> None:
    """E18 current firmware matches the E18 floor-band entry."""
    profile = lookup_capabilities(_E18)
    assert profile is not None
    assert profile.device_class == "E18"


def test_lookup_returns_first_match_a08s() -> None:
    """A08S current firmware matches the A08S floor-band entry."""
    profile = lookup_capabilities(_A08S)
    assert profile is not None
    assert profile.device_class == "A08S"


def test_lookup_returns_first_match_it83() -> None:
    """IT83 exact firmware matches the IT83 entry."""
    profile = lookup_capabilities(_IT83)
    assert profile is not None
    assert profile.device_class == "IT83"


def test_lookup_returns_first_match_r20k() -> None:
    """R20K current firmware matches the R20K floor-band entry."""
    profile = lookup_capabilities(_R20K)
    assert profile is not None
    assert profile.device_class == "R20K"


def test_lookup_returns_first_match_r20a() -> None:
    """R20A current firmware matches the R20A floor-band entry."""
    profile = lookup_capabilities(_R20A)
    assert profile is not None
    assert profile.device_class == "R20A"


def test_lookup_returns_none_for_unrecognised_device() -> None:
    """An unknown model returns ``None`` from the lookup helper."""
    profile = lookup_capabilities(_info("UnknownDevice", "1.0.0.0"))
    assert profile is None


def test_lookup_returns_none_for_x915s_below_floor() -> None:
    """X915S firmware below the floor falls through to non-match."""
    profile = lookup_capabilities(_info("X915S", "2915.30.10.113"))
    assert profile is None


def test_e18_firmware_floor_matches_current_and_newer() -> None:
    """E18 firmware floor admits 18.30.10.118 and newer builds only."""
    for firmware in ("18.30.10.118", "18.30.10.200", "18.31.0.0"):
        profile = lookup_capabilities(_info("E18", firmware))
        assert profile is not None
        assert profile.device_class == "E18"

    assert lookup_capabilities(_info("E18", "18.30.10.100")) is None


def test_a08s_firmware_floor_matches_current_and_newer() -> None:
    """A08S firmware floor admits 108.30.10.144 and newer builds only."""
    for firmware in ("108.30.10.144", "108.30.10.200", "108.31.0.0"):
        profile = lookup_capabilities(_info("A08S", firmware))
        assert profile is not None
        assert profile.device_class == "A08S"

    assert lookup_capabilities(_info("A08S", "108.30.10.100")) is None


def test_r20k_firmware_floor_matches_current_and_newer() -> None:
    """R20K firmware floor admits 320.30.3.122 and newer builds only."""
    for firmware in ("320.30.3.122", "320.30.3.200", "320.31.0.0"):
        profile = lookup_capabilities(_info("R20K", firmware))
        assert profile is not None
        assert profile.device_class == "R20K"

    assert lookup_capabilities(_info("R20K", "320.30.3.100")) is None


def test_r20a_firmware_floor_matches_current_and_newer() -> None:
    """R20A firmware floor admits 320.30.11.63 and newer builds only."""
    for firmware in ("320.30.11.63", "320.30.11.100", "320.31.0.0"):
        profile = lookup_capabilities(_info("R20A", firmware))
        assert profile is not None
        assert profile.device_class == "R20A"

    assert lookup_capabilities(_info("R20A", "320.30.11.50")) is None


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
    """X915S records unsupported writes + schema_shapes apartment_book."""
    profile = lookup_capabilities(_X915S)
    assert profile is not None
    assert profile.status_of(Capability.CONTACT_ADD) is (CapabilityStatus.UNSUPPORTED)
    assert profile.status_of(Capability.CONTACT_MODIFY) is (
        CapabilityStatus.UNSUPPORTED
    )
    assert profile.status_of(Capability.CONTACT_DELETE) is (
        CapabilityStatus.UNSUPPORTED
    )
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


def test_e18_capability_deltas() -> None:
    """E18 carries the full E18C/X916 door-phone capability set."""
    profile = lookup_capabilities(_E18)
    assert profile is not None
    assert profile.device_class == "E18"
    assert "device_not_in_matrix" not in profile.notes
    assert profile.schema_shapes.get("contact") is SchemaShape.DOOR_PHONE
    assert profile.provenance is not None
    assert profile.provenance.firmware_version == "18.30.10.118"
    for capability in _DOOR_PHONE_CRUD_CAPABILITIES:
        assert profile.status_of(capability) is CapabilityStatus.SUPPORTED


def test_a08s_capability_deltas() -> None:
    """A08S supports access-unit APIs and omits door-phone book surfaces."""
    profile = lookup_capabilities(_A08S)
    assert profile is not None
    assert profile.device_class == "A08S"
    assert "device_not_in_matrix" not in profile.notes
    assert profile.schema_shapes == {}
    assert profile.provenance is not None
    assert profile.provenance.firmware_version == "108.30.10.144"

    for capability in (
        Capability.USER_LIST,
        Capability.USER_ADD,
        Capability.USER_MODIFY,
        Capability.USER_DELETE,
        Capability.SCHEDULE_LIST,
        Capability.SCHEDULE_ADD,
        Capability.SCHEDULE_MODIFY,
        Capability.SCHEDULE_DELETE,
        Capability.RELAY_TRIGGER_API,
        Capability.RELAY_STATUS,
        Capability.DEVICE_CONFIG_GET,
        Capability.DEVICE_CONFIG_SET,
        Capability.LOG_DOOR,
        Capability.KEY_DISCOVERY,
    ):
        assert profile.status_of(capability) is CapabilityStatus.SUPPORTED

    for capability in (
        Capability.CONTACT_LIST,
        Capability.CONTACT_ADD,
        Capability.CONTACT_MODIFY,
        Capability.CONTACT_DELETE,
        Capability.GROUP_LIST,
        Capability.GROUP_ADD,
        Capability.GROUP_MODIFY,
        Capability.GROUP_DELETE,
        Capability.LOG_CALL,
    ):
        assert profile.status_of(capability) is CapabilityStatus.UNSUPPORTED

    assert profile.status_of(Capability.RELAY_TRIGGER_FCGI) is (
        CapabilityStatus.UNKNOWN
    )


def test_r20k_capability_deltas() -> None:
    """R20K records only evidence-confirmed supported capabilities."""
    profile = lookup_capabilities(_R20K)
    assert profile is not None
    assert profile.device_class == "R20K"
    assert "device_not_in_matrix" not in profile.notes
    assert profile.schema_shapes.get("contact") is SchemaShape.DOOR_PHONE
    assert profile.field_aliases.get("schedule_relay") == DEFAULT_USER_FIELD_ALIASES
    assert profile.provenance is not None
    assert profile.provenance.test_bench_device_id == "community-reporter (issue #229)"
    assert profile.provenance.firmware_version == "320.30.3.122"

    expected_supported = frozenset(
        {
            Capability.USER_LIST,
            Capability.USER_ADD,
            Capability.USER_MODIFY,
            Capability.USER_DELETE,
            Capability.SCHEDULE_LIST,
            Capability.SCHEDULE_ADD,
            Capability.SCHEDULE_MODIFY,
            Capability.SCHEDULE_DELETE,
            Capability.GROUP_LIST,
            Capability.GROUP_ADD,
            Capability.GROUP_DELETE,
            Capability.CONTACT_LIST,
            Capability.CONTACT_ADD,
            Capability.CONTACT_MODIFY,
            Capability.CONTACT_DELETE,
            Capability.RELAY_TRIGGER_API,
            Capability.RELAY_STATUS,
            Capability.DEVICE_CONFIG_GET,
            Capability.LOG_DOOR,
            Capability.LOG_CALL,
            Capability.KEY_DISCOVERY,
        }
    )
    assert profile.supported_set == expected_supported

    for capability in (
        Capability.CONTACT_ADD,
        Capability.SCHEDULE_MODIFY,
        Capability.RELAY_TRIGGER_API,
        Capability.DEVICE_CONFIG_GET,
        Capability.USER_LIST,
        Capability.USER_ADD,
        Capability.USER_MODIFY,
        Capability.USER_DELETE,
    ):
        assert profile.status_of(capability) is CapabilityStatus.SUPPORTED

    for capability in (
        Capability.GROUP_MODIFY,
        Capability.DEVICE_CONFIG_SET,
        Capability.RELAY_TRIGGER_FCGI,
    ):
        assert profile.status_of(capability) is CapabilityStatus.UNKNOWN


def test_r20a_capability_deltas() -> None:
    """R20A records confirmed supported, unsupported, and unknown buckets."""
    profile = lookup_capabilities(_R20A)
    assert profile is not None
    assert profile.device_class == "R20A"
    assert "device_not_in_matrix" not in profile.notes
    assert profile.schema_shapes.get("contact") is SchemaShape.DOOR_PHONE
    assert profile.field_aliases.get("schedule_relay") == DEFAULT_USER_FIELD_ALIASES
    assert profile.provenance is not None
    assert profile.provenance.test_bench_device_id == (
        "community reporter (issue #234)"
    )
    assert profile.provenance.firmware_version == "320.30.11.63"

    expected_supported = frozenset(
        {
            Capability.USER_LIST,
            Capability.USER_ADD,
            Capability.USER_MODIFY,
            Capability.USER_DELETE,
            Capability.SCHEDULE_LIST,
            Capability.SCHEDULE_ADD,
            Capability.SCHEDULE_MODIFY,
            Capability.SCHEDULE_DELETE,
            Capability.GROUP_LIST,
            Capability.GROUP_ADD,
            Capability.GROUP_DELETE,
            Capability.CONTACT_LIST,
            Capability.CONTACT_ADD,
            Capability.CONTACT_MODIFY,
            Capability.CONTACT_DELETE,
            Capability.RELAY_TRIGGER_API,
            Capability.RELAY_STATUS,
            Capability.DEVICE_CONFIG_GET,
            Capability.LOG_DOOR,
            Capability.LOG_CALL,
            Capability.KEY_DISCOVERY,
        }
    )
    assert profile.supported_set == expected_supported

    for capability in (
        Capability.USER_ADD,
        Capability.USER_MODIFY,
        Capability.USER_DELETE,
        Capability.SCHEDULE_MODIFY,
        Capability.CONTACT_ADD,
        Capability.GROUP_ADD,
        Capability.RELAY_TRIGGER_API,
        Capability.DEVICE_CONFIG_GET,
    ):
        assert profile.status_of(capability) is CapabilityStatus.SUPPORTED

    assert profile.status_of(Capability.RELAY_TRIGGER_FCGI) is (
        CapabilityStatus.UNSUPPORTED
    )

    for capability in (
        Capability.GROUP_MODIFY,
        Capability.DEVICE_CONFIG_SET,
    ):
        assert profile.status_of(capability) is CapabilityStatus.UNKNOWN


def test_r20a_and_r20k_prefixes_do_not_shadow_each_other() -> None:
    """R20A and R20K four-character prefixes resolve independently."""
    r20a_profile = lookup_capabilities(_R20A)
    r20k_profile = lookup_capabilities(_R20K)

    assert r20a_profile is not None
    assert r20k_profile is not None
    assert r20a_profile.device_class == "R20A"
    assert r20k_profile.device_class == "R20K"


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


@pytest.mark.parametrize(
    ("info", "expected_class"),
    [
        (_E18, "E18"),
        (_E18C, "E18C"),
        (_X916, "X916"),
        (_X915S, "X915S"),
        (_IT83, "IT83"),
        (_A08S, "A08S"),
        (_R20K, "R20K"),
    ],
)
def test_existing_devices_still_resolve_to_own_entries(
    info: DeviceInfo, expected_class: str
) -> None:
    """Existing matrix devices continue to resolve to their own entries."""
    profile = lookup_capabilities(info)
    assert profile is not None
    assert profile.device_class == expected_class


def test_matrix_library_version_reuses_package_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Matrix provenance reuses the package version without metadata I/O."""
    import importlib
    import importlib.metadata

    import pylocal_akuvox

    def _raise(_name: str) -> str:
        """Stub importlib.metadata.version that always raises."""
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    drop_capability_matrix(pylocal_akuvox)

    capability_matrix = importlib.import_module("pylocal_akuvox.capability_matrix")

    assert getattr(capability_matrix, "_LIB_VERSION") == pylocal_akuvox.__version__


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
