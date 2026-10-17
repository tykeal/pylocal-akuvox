# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Layout assertions for specs 009-capabilities-module-split + 010-probe-split.

These tests pin the post-refactor module shape so the changes cannot be
silently undone:

* The legacy ``pylocal_akuvox.capabilities`` and
  ``pylocal_akuvox.capability_probe`` subpaths must be gone
  (``ModuleNotFoundError`` on both bare-import and from-import forms).
* The four new capability-side underscore-prefixed sibling modules
  (spec 009) and the four new probe-side underscore-prefixed sibling
  modules (spec 010) must be importable via
  :func:`importlib.import_module` (proves the splits are real and
  not behaviour-equivalent shims).
* The five public symbols re-exported from the top-level package must
  resolve via identity to the corresponding members of the new
  underscore modules (proves the top-level re-export traces through
  the new modules, not through some accidental fallback).
* The five public symbol names must be present in
  :data:`pylocal_akuvox.__all__` (belt-and-suspenders against an
  accidental ``__all__`` edit).
* ``AkuvoxDevice.probe_capabilities`` remains the public consumer-
  facing handle for the capability probe (presence pin only — the
  behaviour suite lives in ``test_capability_probe.py``).
* ``pylocal_akuvox.capability_matrix`` keeps its public names while the
  per-device entries live in private ``_matrix_entries_*`` family
  modules (non-breaking split).
* ``pylocal_akuvox._diagnostic_report`` keeps the diagnostic report
  data structures while the redaction / field helpers live in the
  private ``_diagnostic_redaction`` sibling module (non-breaking split).
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, cast

import pytest

import pylocal_akuvox
import pylocal_akuvox._capability_profile as _profile
import pylocal_akuvox._capability_report as _report
import pylocal_akuvox._capability_types as _types


def test_capabilities_subpath_is_gone() -> None:
    """``import pylocal_akuvox.capabilities`` must raise ``ModuleNotFoundError``."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pylocal_akuvox.capabilities")


def test_capabilities_subpath_from_import_is_gone() -> None:
    """``from pylocal_akuvox.capabilities import Capability`` must raise.

    Uses ``exec()`` because a static ``from`` import at module top level
    would be evaluated at pytest-collection time, outside the
    ``pytest.raises`` context, and would itself raise
    ``ModuleNotFoundError`` post-split, preventing the test module from
    loading. ``ModuleNotFoundError`` is required specifically (not the
    wider ``ImportError`` superclass) so a hypothetical partial-shim
    regression — e.g. a re-resurrected ``pylocal_akuvox.capabilities``
    module that loads but no longer exports ``Capability`` — would
    raise the bare ``ImportError`` and fail this test loudly rather
    than slip through.
    """
    with pytest.raises(ModuleNotFoundError):
        exec("from pylocal_akuvox.capabilities import Capability")  # noqa: S102


def test_underscore_modules_importable() -> None:
    """Each of the four new underscore modules must import cleanly."""
    for name in (
        "pylocal_akuvox._capability_types",
        "pylocal_akuvox._capability_profile",
        "pylocal_akuvox._capability_matching",
        "pylocal_akuvox._capability_defaults",
    ):
        importlib.import_module(name)


def test_public_symbols_roundtrip_via_top_level() -> None:
    """The 5 public symbols must trace to their source underscore modules."""
    assert pylocal_akuvox.Capability is _types.Capability
    assert pylocal_akuvox.CapabilityStatus is _types.CapabilityStatus
    assert pylocal_akuvox.SchemaShape is _types.SchemaShape
    assert pylocal_akuvox.DeviceCapabilities is _profile.DeviceCapabilities
    assert pylocal_akuvox.FieldAliases is _profile.FieldAliases


def test_capability_symbols_in_top_level_all() -> None:
    """The 5 public capability names must be present in ``__all__``."""
    for name in (
        "Capability",
        "CapabilityStatus",
        "SchemaShape",
        "DeviceCapabilities",
        "FieldAliases",
    ):
        assert name in pylocal_akuvox.__all__, (
            f"{name!r} missing from pylocal_akuvox.__all__"
        )


def test_capability_probe_subpath_is_gone() -> None:
    """``import pylocal_akuvox.capability_probe`` must raise ``ModuleNotFoundError``.

    Per spec 010-capability-probe-split FR-002: the
    ``pylocal_akuvox.capability_probe`` module path is removed entirely
    post-split. No shim, no package — just a clean
    ``ModuleNotFoundError``. The migration path lives in
    ``docs/changelog.rst`` Unreleased "Breaking changes" subsection:
    consumers continue to call ``AkuvoxDevice.probe_capabilities()``.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pylocal_akuvox.capability_probe")


def test_capability_probe_subpath_from_import_is_gone() -> None:
    """``from pylocal_akuvox.capability_probe import probe_capabilities`` must raise.

    Uses ``exec()`` for the same reason as
    :func:`test_capabilities_subpath_from_import_is_gone`: a static
    ``from`` import at module top level would be evaluated at
    pytest-collection time, outside the ``pytest.raises`` context, and
    would itself raise ``ModuleNotFoundError`` post-split, preventing
    the test module from loading. ``ModuleNotFoundError`` is required
    specifically (not the wider ``ImportError`` superclass) so a
    hypothetical partial-shim regression — e.g. a re-resurrected
    ``pylocal_akuvox.capability_probe`` module that loads but no
    longer exports ``probe_capabilities`` — would raise the bare
    ``ImportError`` and fail this test loudly rather than slip through.
    Covers spec 010 FR-003.
    """
    with pytest.raises(ModuleNotFoundError):
        exec("from pylocal_akuvox.capability_probe import probe_capabilities")  # noqa: S102


def test_probe_underscore_modules_importable() -> None:
    """Each of the four new probe-side underscore modules must import cleanly."""
    for name in (
        "pylocal_akuvox._probe_outcomes",
        "pylocal_akuvox._probe_classifiers",
        "pylocal_akuvox._probe_parsers",
        "pylocal_akuvox._capability_probe",
    ):
        importlib.import_module(name)


def test_probe_capabilities_reachable_via_device() -> None:
    """``AkuvoxDevice.probe_capabilities`` remains the public consumer handle.

    Presence pin only — the behaviour suite lives in
    ``test_capability_probe.py``. Covers spec 010 FR-001 + User
    Story 1 acceptance scenario.
    """
    assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities)


def test_device_subpath_remains_importable() -> None:
    """``pylocal_akuvox.device`` remains a public import path."""
    module = importlib.import_module("pylocal_akuvox.device")

    assert getattr(module, "AkuvoxDevice") is pylocal_akuvox.AkuvoxDevice
    assert module.__file__ is not None
    module_path = Path(module.__file__)
    assert module_path.name == "device.py" or (
        module_path.suffix == ".pyc" and module_path.name.startswith("device.")
    )


def test_device_public_symbol_in_top_level_all() -> None:
    """``AkuvoxDevice`` remains part of the top-level public exports."""
    assert "AkuvoxDevice" in pylocal_akuvox.__all__


_REPORT_STEP_MODULES = (
    "pylocal_akuvox._report_steps",
    "pylocal_akuvox._report_instrumentation",
    "pylocal_akuvox._report_read_tests",
    "pylocal_akuvox._report_validation",
    "pylocal_akuvox._report_write_steps",
    "pylocal_akuvox._report_config_probe",
    "pylocal_akuvox._report_write_cleanup",
    "pylocal_akuvox._report_write_chains",
    "pylocal_akuvox._report_write_tests",
)


def test_capability_report_modules_importable() -> None:
    """The capability-report split modules must import cleanly."""
    for name in (
        "pylocal_akuvox._diagnostic_redaction",
        "pylocal_akuvox._diagnostic_report",
        *_REPORT_STEP_MODULES,
        "pylocal_akuvox._capability_report",
    ):
        importlib.import_module(name)


def test_capability_report_export_roundtrips() -> None:
    """The public report API must be re-exported from the package root."""
    assert pylocal_akuvox.run_capability_report is _report.run_capability_report
    assert "run_capability_report" in pylocal_akuvox.__all__


def test_run_capability_report_signature_unchanged() -> None:
    """The public report API keeps its keyword options and defaults."""
    params = inspect.signature(_report.run_capability_report).parameters

    assert {name: param.default for name, param in params.items()} == {
        "device": inspect.Parameter.empty,
        "write": False,
        "open_door": False,
        "open_door_user": None,
        "open_door_password": None,
        "timeout": None,
        "redact_stdout": False,
        "emit": None,
    }


def test_report_options_bundle_runner_options() -> None:
    """The private runner takes a frozen options bundle, not loose kwargs."""
    options = _report._ReportOptions(
        write=True,
        open_door=True,
        open_door_user="relay-user",
        open_door_password="relay-secret",
        timeout=5.0,
        redact_stdout=True,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        cast("Any", options).write = False
    assert "relay-secret" not in repr(options)
    assert list(inspect.signature(_report._run_capability_report).parameters) == [
        "device",
        "options",
    ]


def test_device_underscore_modules_importable() -> None:
    """Each focused device helper module must import cleanly."""
    for name in (
        "pylocal_akuvox._device_profiles",
        "pylocal_akuvox._device_runtime",
        "pylocal_akuvox._device_users",
        "pylocal_akuvox._device_relays",
        "pylocal_akuvox._device_access",
        "pylocal_akuvox._device_contacts",
        "pylocal_akuvox._device_config_logs",
    ):
        importlib.import_module(name)


def _module_line_count(module_name: str) -> int:
    """Return the source line count for an importable module."""
    module = importlib.import_module(module_name)
    assert module.__file__ is not None
    path = Path(module.__file__)
    if path.suffix == ".pyc":
        source_path = Path(importlib.util.source_from_cache(str(path)))
        if not source_path.exists():
            pytest.skip(f"source file not available for {module_name}")
        path = source_path
    return len(path.read_text(encoding="utf-8").splitlines())


def test_device_modules_under_aislop_limit() -> None:
    """The retained facade and helper modules must stay below 400 lines."""
    for name in (
        "pylocal_akuvox.device",
        "pylocal_akuvox._device_profiles",
        "pylocal_akuvox._device_runtime",
        "pylocal_akuvox._device_users",
        "pylocal_akuvox._device_relays",
        "pylocal_akuvox._device_access",
        "pylocal_akuvox._device_contacts",
        "pylocal_akuvox._device_config_logs",
    ):
        assert _module_line_count(name) < 400


_MATRIX_FAMILY_MODULES = (
    "pylocal_akuvox._matrix_entries_e_series",
    "pylocal_akuvox._matrix_entries_indoor_access",
    "pylocal_akuvox._matrix_entries_r_series",
    "pylocal_akuvox._matrix_entries_x_series",
)


def test_matrix_split_modules_importable() -> None:
    """The matrix provenance and device-family modules must import cleanly."""
    for name in ("pylocal_akuvox._matrix_provenance", *_MATRIX_FAMILY_MODULES):
        importlib.import_module(name)


def test_capability_matrix_public_names_still_resolve() -> None:
    """Names importable before the split still resolve on the public path."""
    import pylocal_akuvox._capability_defaults as defaults
    import pylocal_akuvox._capability_matching as matching

    module = importlib.import_module("pylocal_akuvox.capability_matrix")

    assert module.__all__ == ["CAPABILITY_MATRIX"]
    assert isinstance(module.CAPABILITY_MATRIX, tuple)
    expected = {
        "Capability": _types.Capability,
        "CapabilityStatus": _types.CapabilityStatus,
        "SchemaShape": _types.SchemaShape,
        "DeviceCapabilities": _profile.DeviceCapabilities,
        "FieldAliases": _profile.FieldAliases,
        "Provenance": _profile.Provenance,
        "DeviceClassPattern": matching.DeviceClassPattern,
        "DEFAULT_USER_FIELD_ALIASES": defaults.DEFAULT_USER_FIELD_ALIASES,
    }
    for name, symbol in expected.items():
        assert getattr(module, name) is symbol, name


def test_capability_matrix_entries_come_from_family_modules() -> None:
    """Every registered entry must be defined by a device-family module."""
    module = importlib.import_module("pylocal_akuvox.capability_matrix")
    family_entries = [
        value
        for name in _MATRIX_FAMILY_MODULES
        for value in vars(importlib.import_module(name)).values()
        if isinstance(value, _profile.DeviceCapabilities)
    ]

    registered = [entry for _pattern, entry in module.CAPABILITY_MATRIX]

    assert len(registered) == len(family_entries)
    for entry in registered:
        assert any(entry is candidate for candidate in family_entries)


def test_capability_matrix_modules_under_aislop_limit() -> None:
    """The matrix facade and its split modules must stay below 400 lines."""
    for name in (
        "pylocal_akuvox.capability_matrix",
        "pylocal_akuvox._matrix_provenance",
        *_MATRIX_FAMILY_MODULES,
    ):
        assert _module_line_count(name) < 400


def test_diagnostic_report_split_keeps_structures_and_moves_helpers() -> None:
    """Report classes stay put; redaction helpers live in the sibling."""
    report = importlib.import_module("pylocal_akuvox._diagnostic_report")
    redaction = importlib.import_module("pylocal_akuvox._diagnostic_redaction")

    for name in (
        "DiagnosticHttpEvent",
        "DiagnosticReport",
        "DiagnosticTestRecord",
        "_event_failed",
        "_event_succeeded",
    ):
        assert getattr(report, name).__module__ == report.__name__, name
    for name in (
        "_clip",
        "_decode_json_body",
        "_display_value",
        "_drop_none",
        "_failure_body_snippet",
        "_first_line",
        "_redact_json_values",
    ):
        assert getattr(redaction, name).__module__ == redaction.__name__, name


def test_diagnostic_report_modules_under_aislop_limit() -> None:
    """The diagnostic report and redaction modules stay below 400 lines."""
    for name in (
        "pylocal_akuvox._diagnostic_report",
        "pylocal_akuvox._diagnostic_redaction",
    ):
        assert _module_line_count(name) < 400


def test_report_steps_split_keeps_framework_and_moves_steps() -> None:
    """The step framework stays put; step groups live in focused siblings."""
    expected = {
        "pylocal_akuvox._report_steps": (
            "TestResults",
            "TestStepFailed",
            "TestStepSkipped",
            "run_step",
            "step",
        ),
        "pylocal_akuvox._report_instrumentation": (
            "_probe_device_capabilities",
            "create_device",
        ),
        "pylocal_akuvox._report_read_tests": ("_run_read_tests",),
        "pylocal_akuvox._report_validation": ("test_validation",),
        "pylocal_akuvox._report_write_steps": ("test_add_user", "test_open_door"),
        "pylocal_akuvox._report_config_probe": ("test_set_device_config",),
        "pylocal_akuvox._report_write_cleanup": ("_best_effort_delete",),
        "pylocal_akuvox._report_write_chains": ("_run_user_write_tests",),
        "pylocal_akuvox._report_write_tests": ("_WriteOptions", "_run_write_tests"),
    }
    for module_name, names in expected.items():
        module = importlib.import_module(module_name)
        for name in names:
            assert getattr(module, name).__module__ == module_name, name


def test_write_options_bundle_write_test_options() -> None:
    """The write-test runner takes a frozen options bundle, not loose kwargs."""
    write_tests = importlib.import_module("pylocal_akuvox._report_write_tests")
    options = write_tests._WriteOptions(
        open_door=True,
        open_door_user="relay-user",
        open_door_password="relay-secret",
        redact_stdout=True,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        cast("Any", options).open_door = False
    assert "relay-secret" not in repr(options)
    assert list(inspect.signature(write_tests._run_write_tests).parameters) == [
        "device_kwargs",
        "results",
        "capabilities",
        "options",
    ]


def test_report_step_modules_under_aislop_limit() -> None:
    """The report-step framework and its split modules stay below 400 lines."""
    for name in _REPORT_STEP_MODULES:
        assert _module_line_count(name) < 400, name
