<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Phase 1 Data Model: Capability Probe, Matrix, and Surfacing

**Feature**: 008-capability-matrix
**Status**: Phase 1 design — types and homes are stable; matrix entries
are populated in Phase 2.

## Scope

This feature introduces a small set of new entity types living *outside*
the `models/` package (per the spec-007 cross-cutting note: see
`specs/007-models-split/data-model.md` lines 105–110, which explicitly
reserves `pylocal_akuvox/capabilities.py` for issue #123's types). It
also evolves one existing exception class additively. No existing model
class in `pylocal_akuvox.models.*` is restructured by Phase 1 or Phase 2;
Phase 3 changes one *parser* in `models/users.py` and one *parser* in
`models/contacts.py` but does not change their fields or class identity.

## Entity → Home Map

| # | Entity | Kind | Home | Phase | Mutability | Notes |
|---|--------|------|------|-------|-----------|-------|
| 1 | `Capability` | `enum.Enum` (str values) | `pylocal_akuvox/capabilities.py` | 1 | immutable | Canonical capability identifiers. New members are additive (FR-001). |
| 2 | `CapabilityStatus` | `enum.Enum` (str values) | `pylocal_akuvox/capabilities.py` | 1 | immutable | Three-valued status: `SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`. Default for any capability not explicitly listed in a `DeviceCapabilities.capabilities` mapping is `UNKNOWN` (returned by `status_of`). |
| 3 | `FieldAliases` | `@dataclass(frozen=True, kw_only=True)` | `pylocal_akuvox/capabilities.py` | 1 | immutable | `read: tuple[str, ...]`, `write: tuple[str, ...]` — both directions of one logical field. |
| 4 | `SchemaShape` | `enum.Enum` (str values) | `pylocal_akuvox/capabilities.py` | 1 | immutable | `DOOR_PHONE`, `APARTMENT_BOOK`. Phase 3's contact selector reads this. |
| 5 | `Provenance` | `@dataclass(frozen=True, kw_only=True)` | `pylocal_akuvox/capabilities.py` | 1 | immutable | `test_bench_device_id: str`, `firmware_version: str`, `library_version: str`, `observed_at: str` (ISO-8601 date). |
| 6 | `DeviceCapabilities` | `@dataclass(frozen=True, kw_only=True)` | `pylocal_akuvox/capabilities.py` | 1 | immutable | The effective profile carried by an `AkuvoxDevice`. See §"DeviceCapabilities" below. |
| 7 | `DeviceClassPattern` | `@dataclass(frozen=True, kw_only=True)` | `pylocal_akuvox/capabilities.py` | 1 | immutable | Matrix key. Carries `model_prefix: str` and `firmware_band: str`; exposes `matches(device_info: DeviceInfo) -> bool`. Construction validates the firmware-band form (glob/floor/exact). |
| 8 | `CAPABILITY_MATRIX` | module-level constant `tuple[tuple[DeviceClassPattern, DeviceCapabilities], ...]` | `pylocal_akuvox/capability_matrix.py` | 2 | immutable | Curated, ordered most-specific-first. Initial entries: X916, X915S (current FW), E18C (current FW), IT83. |
| 9 | `RelayTriggerAdapter` | `Callable` type alias | `pylocal_akuvox/capability_adapters.py` | 2 | (callable) | `Callable[[AkuvoxHttpClient, RelayTriggerArgs], Awaitable[None]]`. |
| 10 | `RelayTriggerArgs` | `@dataclass(frozen=True, kw_only=True)` | `pylocal_akuvox/capability_adapters.py` | 2 | immutable | `num: int`, `mode: int`, `level: int`, `delay: int` — already today's `trigger_relay` parameters, just packaged. |
| 11 | `RELAY_TRIGGER_ADAPTERS` | module-level constant `dict[tuple[Capability, str], RelayTriggerAdapter]` | `pylocal_akuvox/capability_adapters.py` | 2 | immutable (after import) | Two entries today: `(RELAY_TRIGGER_API, "api")` → `_api_relay_trigger`, `(RELAY_TRIGGER_FCGI, "fcgi")` → `_fcgi_relay_trigger`. |
| 12 | `AkuvoxUnsupportedError` | exception | `pylocal_akuvox/exceptions.py` (existing file) | 2 (evolved) | (exception) | Existing class evolved additively per `contracts/unsupported-error.md`. New `reason="capability_unknown"` value covers the three-valued UNKNOWN-status raise path. |

## `Capability` enum members

The Phase 1 enum surfaces the operations the public `AkuvoxDevice` already
exposes plus the relay-variant distinction needed for adapter dispatch.
String values use a `domain.action[.variant]` shape so they are
grep-friendly and stable in serialized notes/provenance.

| Member | Value (string) | Maps to |
|--------|----------------|---------|
| `USER_LIST`               | `"user.list"`              | `device.list_users()` |
| `USER_ADD`                | `"user.add"`               | `device.add_user()` |
| `USER_MODIFY`             | `"user.modify"`            | `device.modify_user()` |
| `USER_DELETE`             | `"user.delete"`            | `device.delete_user()` |
| `SCHEDULE_LIST`           | `"schedule.list"`          | `device.list_schedules()` |
| `SCHEDULE_ADD`            | `"schedule.add"`           | `device.add_schedule()` |
| `SCHEDULE_MODIFY`         | `"schedule.modify"`        | `device.modify_schedule()` |
| `SCHEDULE_DELETE`         | `"schedule.delete"`        | `device.delete_schedule()` |
| `GROUP_LIST`              | `"group.list"`             | `device.list_groups()` |
| `GROUP_ADD`               | `"group.add"`              | `device.add_group()` |
| `GROUP_MODIFY`            | `"group.modify"`           | `device.modify_group()` |
| `GROUP_DELETE`            | `"group.delete"`           | `device.delete_group()` |
| `CONTACT_LIST`            | `"contact.list"`           | `device.list_contacts()` |
| `CONTACT_ADD`             | `"contact.add"`            | `device.add_contact()` |
| `CONTACT_MODIFY`          | `"contact.modify"`         | `device.modify_contact()` |
| `CONTACT_DELETE`          | `"contact.delete"`         | `device.delete_contact()` |
| `CONTACT_SCHEMA_APARTMENT`| `"contact.schema.apartment"` | (flag; consulted by `Contact.from_api_response` in Phase 3) |
| `RELAY_TRIGGER_API`       | `"relay.trigger.api"`      | `device.trigger_relay()` via `/api/relay/trig` |
| `RELAY_TRIGGER_FCGI`      | `"relay.trigger.fcgi"`     | `device.trigger_relay()` via `/fcgi/do?action=OpenDoor` |
| `RELAY_STATUS`            | `"relay.status"`           | `device.get_relay_status()` |
| `DEVICE_CONFIG_GET`       | `"device.config.get"`      | `device.get_device_config()` |
| `DEVICE_CONFIG_SET`       | `"device.config.set"`      | `device.set_device_config()` |
| `LOG_DOOR`                | `"log.door"`               | `device.get_door_logs()` |
| `LOG_CALL`                | `"log.call"`               | `device.get_call_logs()` |
| `KEY_DISCOVERY`           | `"key.discovery"`          | (covers `/api/system/info`-style introspection used by the probe) |

**Explicit out-of-scope** (public `AkuvoxDevice` methods NOT capability-gated by FR-011):

- `AkuvoxDevice.get_info()` → `/api/system/info` is universally available on every Akuvox device (it is the very endpoint the probe uses to identify the device class, see `contracts/probe-api.md` step 1). Gating it would create a chicken-and-egg cycle since matrix lookup itself runs after `get_info()`. Treated as an unconditional always-available endpoint.
- `AkuvoxDevice.get_status()` → `/api/system/status` is paired with `get_info()` and used by the probe sequence; same rationale.
- `AkuvoxDevice.probe_capabilities()` → this is the method that CREATES the effective `DeviceCapabilities` profile. Gating it behind a capability check would be a chicken-and-egg cycle (no profile exists yet at the moment it is called). It is the explicit integrator opt-in for first-hand evidence-gathering and is never blocked by capability state.

**Adapter-gated exception** (gated, but not via the literal `self._capabilities.require(...)` audit-string):

- `AkuvoxDevice.trigger_relay()` → gated structurally via the per-variant `RELAY_TRIGGER_ADAPTERS` registry lookup in `capability_adapters.py` (see `contracts/adapter-dispatch.md` §"Dispatch order"). The adapter-registry scan consults `self._capabilities.status_of(Capability.RELAY_TRIGGER_API)` / `status_of(Capability.RELAY_TRIGGER_FCGI)` and raises `AkuvoxUnsupportedError(reason="adapter_missing")` when no SUPPORTED adapter exists. The FR-011 introspection audit (`tests/unit/test_device.py::test_every_public_device_method_has_capability_gate`) treats `trigger_relay` as a documented exception and asserts the gating happens through the adapter registry call instead.

These three methods deliberately do NOT consult `self._capabilities.require(...)` directly. T049 leaves `get_info`/`get_status`/`probe_capabilities` unchanged; T050 handles `trigger_relay` via the adapter registry.

The enum is **extensible**: new members append. Existing members do not
change name or value (FR-001's "extensible without breaking existing
callers").

## `DeviceCapabilities` shape

```python
class CapabilityStatus(enum.Enum):
    """Three-valued capability status."""

    SUPPORTED = "supported"      # confirmed positive evidence
    UNSUPPORTED = "unsupported"  # confirmed negative evidence (e.g. unsupported action)
    UNKNOWN = "unknown"          # no positive evidence either way


@dataclass(frozen=True, kw_only=True)
class DeviceCapabilities:
    """The effective capability profile carried by one connection.

    All four mapping fields (``capabilities``, ``field_aliases``,
    ``schema_shapes``, ``notes``) are wrapped in
    ``types.MappingProxyType`` by ``__post_init__`` so post-construction
    mutation raises ``TypeError``. Constructors accept plain ``dict``
    for ergonomic call-sites; the read-only wrapping is applied
    transparently. This enforces the **deep immutability invariant**
    that gating logic relies on (a caller cannot do
    ``device._capabilities.notes["evil"] = "x"`` to corrupt the
    profile). See immutability test enumerated in T028a.
    """

    device_class: str
    firmware_version: str
    capabilities: Mapping[Capability, CapabilityStatus]
    field_aliases: Mapping[str, FieldAliases]   # logical-field name → aliases
    schema_shapes: Mapping[str, SchemaShape]     # resource name → shape
    notes: Mapping[str, str] = field(default_factory=dict)
    provenance: Provenance | None = None         # None when probe-derived

    def __post_init__(self) -> None:
        """Wrap each mapping field in a read-only view (``MappingProxyType``).

        Defensively copies the input dict first so callers cannot retain
        a write handle to the underlying storage. Uses
        ``object.__setattr__`` because the dataclass is ``frozen=True``.
        """
        # for each mapping field: object.__setattr__(self, name,
        #     MappingProxyType(dict(getattr(self, name))))

    def status_of(self, capability: Capability) -> CapabilityStatus:
        """Return the status for capability, defaulting to UNKNOWN.

        **Contract**: if ``capability not in self.capabilities``, returns
        ``CapabilityStatus.UNKNOWN`` (the "absent → UNKNOWN" default).
        This is the canonical representation: write capabilities the
        probe did not classify are **absent** from ``capabilities``,
        not present-with-UNKNOWN. ``status_of`` collapses both shapes
        into the same observable behaviour so callers never need to
        distinguish.
        """
        return self.capabilities.get(capability, CapabilityStatus.UNKNOWN)

    def require(self, capability: Capability, *, allow_unknown: bool = False) -> None:
        """Raise AkuvoxUnsupportedError unless the capability is SUPPORTED.

        With ``allow_unknown=True``, UNKNOWN status falls through (does
        not raise); the runtime HTTP attempt then either succeeds or
        surfaces ``AkuvoxUnsupportedError(reason="envelope_unsupported")``
        from ``_http.py:201``. UNSUPPORTED always raises regardless of
        the ``allow_unknown`` flag.
        """

    @property
    def supported_set(self) -> frozenset[Capability]:
        """Derived view: the set of capabilities whose status is SUPPORTED.

        Provided for introspection and the docs-render path; matches the
        set-shaped view in the spec's Key Entities prose.
        """
```

Method `require(capability)` is the per-call gate used by every public
`AkuvoxDevice.*` method in Phase 2. It raises:

- `AkuvoxUnsupportedError(reason="capability_missing")` when the
  status is `UNSUPPORTED`.
- `AkuvoxUnsupportedError(reason="capability_unknown")` when the
  status is `UNKNOWN` and `allow_unknown=False`.

Both raises populate `capability=`, `device_class=`, and a
human-readable message.

`AkuvoxDevice` exposes a settable boolean attribute
`attempt_unknown_capability` (default `False`). When set, the per-method
gate calls `require(capability, allow_unknown=True)`. This is the
explicit opt-in escape hatch for integrators on devices that do not yet
have a matrix entry.

## `FieldAliases` and the schedule-relay logical field

The Phase 3 refactor recognizes one logical field today:

| Logical name | Read alias list (X916 default) | Write alias list (X916 default) | E18C override | X915S override (current) |
|--------------|--------------------------------|---------------------------------|---------------|--------------------------|
| `schedule_relay` | `("ScheduleRelay", "Schedule-Relay", "Schedule")` | `("ScheduleRelay", "Schedule-Relay")` | same as X916 (E18C accepts both writes; spec line 119 collision rule) | `read=("Schedule", "ScheduleRelay", "Schedule-Relay")` (current FW returns `Schedule`); write same as X916 |

Default fallback (used by `User.from_api_response` when no capability
record is supplied) is byte-identical to the X916 entry. This is what
preserves FR-016 / SC-008 (existing tests stay green).

## `SchemaShape` values

| Member | Value | Resource | Used by |
|--------|-------|----------|---------|
| `DOOR_PHONE`     | `"door_phone"`     | `contact` | Default `Contact.from_api_response` path (X916, E18C). |
| `APARTMENT_BOOK` | `"apartment_book"` | `contact` | X915S (current FW) — adds `APTName`, `APTNum`, `Building`, `Landline`; removes `ID` requirement (FR-015). |

Phase 3's `Contact.from_api_response(data, *, capabilities)` reads
`capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)` to
choose the parse path. The default is `DOOR_PHONE` — preserving
today's behavior for any direct caller.

## `DeviceClassPattern` semantics (firmware band forms)

Construction validates the form. Stored fields after parse:

| Form | Example | Stored representation |
|------|---------|------------------------|
| Glob  | `"916.30.10.*"`     | `_band_kind = "glob"`,  `_band_segments = (916, 30, 10, "*")` |
| Floor | `"2915.30.10.114+"` | `_band_kind = "floor"`, `_band_floor = (2915, 30, 10, 114)` |
| Exact | `"83.30.10.4"`      | `_band_kind = "exact"`, `_band_segments = (83, 30, 10, 4)` |

`matches(device_info)` returns `True` iff:

- `device_info.model.startswith(self.model_prefix)`, **and**
- the firmware version (also parsed to a `tuple[int, ...]`) satisfies
  the form: glob requires segment-by-segment equality up to the `*`;
  floor requires `observed >= floor`; exact requires byte-equality
  after parse.

Bad input (e.g. `"916.30.*.10"` — wildcard not in the trailing position)
raises `ValueError` at pattern construction time, surfacing matrix-author
errors at import time.

## `CAPABILITY_MATRIX` initial entries (Phase 2)

Ordered most-specific-first; the first matching pattern wins:

```python
CAPABILITY_MATRIX = (
    # IT83 indoor monitor — exact firmware match
    (DeviceClassPattern(model_prefix="IT83", firmware_band="83.30.10.4"),
     _IT83_83_30_10_4),
    # X915S current firmware — floor match (excludes the historical 113)
    (DeviceClassPattern(model_prefix="X915S", firmware_band="2915.30.10.114+"),
     _X915S_CURRENT),
    # E18C current firmware — glob match
    (DeviceClassPattern(model_prefix="E18C", firmware_band="18.30.11.*"),
     _E18C_CURRENT),
    # X916 baseline — glob match (last because most permissive)
    (DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*"),
     _X916_BASELINE),
)
```

The four `_DeviceCapabilities` literals each carry a populated
`Provenance` naming the test-bench device, firmware version, and the
library version at which the entry was added. Provenance for IT83 names
the community-reporter device per spec dependency note line 205.

### Capability deltas across the four entries

Legend: **S** = `SUPPORTED` (positive evidence), **U** = `UNSUPPORTED`
(confirmed-negative evidence, e.g. an `unsupported action` envelope was
specifically observed for this operation), **?** = `UNKNOWN` (no
positive evidence either way; default for any capability not listed in
the matrix entry's `capabilities` mapping). UNKNOWN is the conservative
default — it produces fail-fast `AkuvoxUnsupportedError(reason=
"capability_unknown")` from the per-call gate unless the integrator
opts in via `device.attempt_unknown_capability=True`.

| Capability | X916 | X915S (current) | E18C (current) | IT83 |
|------------|------|-----------------|----------------|------|
| `USER_LIST`               | S | S | S | ? |
| `USER_ADD`                | S | S | S | ? |
| `USER_MODIFY`             | S | S | S | ? |
| `USER_DELETE`             | S | S | S | ? |
| `SCHEDULE_LIST`           | S | S | S | ? |
| `SCHEDULE_ADD`            | S | S | S | ? |
| `SCHEDULE_MODIFY`         | S | S | S | ? |
| `SCHEDULE_DELETE`         | S | S | S | ? |
| `GROUP_LIST`              | S | S | S | ? |
| `GROUP_ADD`               | S | S | S | ? |
| `GROUP_MODIFY`            | S | S | S | ? |
| `GROUP_DELETE`            | S | S | S | ? |
| `CONTACT_LIST`            | S | S | S | ? |
| `CONTACT_ADD`             | S | **U** (door-phone `add_contact` write-attempt confirmed `unsupported action` on bench — issue #121) | S | ? |
| `CONTACT_MODIFY`          | S | **?** (no hardware-bench write evidence cited; door-phone-shape `modify_contact` has not been independently tested on X915S — see issue #121 which covered ADD only. Defaults to UNKNOWN per FR-003 "no evidence → UNKNOWN"; gate's `attempt_unknown_capability=True` opt-in is the escape hatch.) | S | ? |
| `CONTACT_DELETE`          | S | **?** (no hardware-bench write evidence cited; door-phone-shape `delete_contact` has not been independently tested on X915S — same situation as MODIFY. Defaults to UNKNOWN per FR-003.) | S | ? |
| `CONTACT_SCHEMA_APARTMENT`| ? | S | ? | ? |
| `RELAY_TRIGGER_API`       | S | S | S | **U** (no-handler confirmed) |
| `RELAY_TRIGGER_FCGI`      | ? | ? | ? | **S** (community-reporter evidence) |
| `RELAY_STATUS`            | S | S | S | **U** (no-handler confirmed) |
| `DEVICE_CONFIG_GET`       | S | S | S | ? |
| `DEVICE_CONFIG_SET`       | S | S | S | ? |
| `LOG_DOOR`                | S | S | S | ? |
| `LOG_CALL`                | S | S | S | ? |
| `KEY_DISCOVERY`           | S | S | S | S |

Notes on the IT83 column:

- `RELAY_TRIGGER_API`, `RELAY_STATUS`: `UNSUPPORTED` because the
  community-reporter evidence in issue #122 specifically observed
  `/api/relay/*` returning "No handlers for this request". Confirmed
  negative.
- `RELAY_TRIGGER_FCGI`: `SUPPORTED` from the same community-reporter
  evidence — the `/fcgi/do?action=OpenDoor` path is what works on this
  device.
- Every other IT83 capability is `UNKNOWN`. The community reporter
  did not exercise user/contact/schedule/group writes on the IT83. The
  spec's evidence summary describes those writes as "likely also
  unsupported", but "likely" is not "confirmed"; the matrix records
  only what we have positive evidence for. Calling these against an
  IT83 raises `AkuvoxUnsupportedError(reason="capability_unknown")`
  with a message instructing the integrator to either add a matrix
  entry or set `device.attempt_unknown_capability=True`.
- Future evidence (hardware-bench observation or a more thorough
  community report) can promote IT83 `UNKNOWN` entries to `SUPPORTED`
  or `UNSUPPORTED` additively, with no code changes outside the
  matrix.

Notes on the `CONTACT_SCHEMA_APARTMENT` row:

- This capability is a *flag* (the apartment-book schema is in use)
  not an *operation*. `SUPPORTED` for X915S means "this device uses
  the apartment-book schema for contacts"; `UNKNOWN` for the others
  means "we have no positive evidence the apartment-book schema
  applies to this device" — Phase 3's contact parser falls back to
  the door-phone shape when the flag's status is anything other than
  `SUPPORTED`. This is one of the exceptions where `UNKNOWN` does
  *not* trigger fail-fast: the contact parser does not call
  `require()` on this flag; it consults `schema_shapes` directly. See
  the Phase 3 refactor notes for why this distinction is safe (the
  door-phone parse path is the historical default and is byte-compatible
  with all currently-supported devices).

## Public re-exports (`pylocal_akuvox/__init__.py`)

Phase 1 adds:

- `Capability` (re-exported from `capabilities.py`)
- `CapabilityStatus` (re-exported from `capabilities.py`)
- `DeviceCapabilities` (re-exported from `capabilities.py`)
- `FieldAliases` (re-exported from `capabilities.py`)
- `SchemaShape` (re-exported from `capabilities.py`)

Phase 2 adds:

- (`AkuvoxUnsupportedError` is already re-exported; no new top-level
  name added — the structured fields are accessed off the existing
  re-export.)

`probe_capabilities()` is **not** re-exported as a top-level function;
it is a method on `AkuvoxDevice` (matching the spec text "the integrator
calls `device.probe_capabilities()`"). Callers reach it via the existing
`AkuvoxDevice` re-export.

`CAPABILITY_MATRIX`, `RELAY_TRIGGER_ADAPTERS`, the adapter callables, and
`DeviceClassPattern` are **not** re-exported at the package root —
they are implementation modules consumed by `device.py` and the docs
build. Direct imports like `from pylocal_akuvox.capability_matrix import
CAPABILITY_MATRIX` remain available for the doc renderer and the
consistency test.

## Class identity post-Phase-3

`User`, `Contact`, and the eight other model classes remain the same
Python class objects after Phase 3 — same `id()`, same `__qualname__`,
same `dataclass.fields()`. Only their `from_api_response` classmethods
gain an optional `capabilities` kwarg with a sensible default. This
mirrors spec-007's "class identity preserved" rule and keeps every
pickle/repr/import contract identical.

## Constraints driven by Phase 3 (recorded for the contracts)

1. `User.from_api_response(data)` (no kwargs) MUST continue to work and
   MUST produce identical results to today for any input dict that
   today parses. This is enforced by the unchanged passing of every
   pre-existing test in `tests/unit/test_models.py` covering `User`.
2. `users.add_user(...)` and `users.modify_user(...)` MUST emit the
   exact same payload bytes today produced for X916, X915S, and E18C
   (FR-016). Phase 3's PR re-runs the existing #99/#101 tests to
   verify.
3. `Contact.from_api_response(data)` (no kwargs) MUST continue to
   accept the today's door-phone input and MUST raise
   `AkuvoxParseError` on missing `Name` exactly as today; the
   apartment-book path is *additive* and only taken when explicitly
   selected via the `capabilities` kwarg.

## State Transitions

Per-connection effective profile lifecycle:

```text
[no profile]
    │
    │  device.__aenter__() → GET /api/system/info → matrix lookup
    ▼
[matrix-derived OR conservative-unrecognized]
    │
    │  device.probe_capabilities()
    ▼
[merged effective profile — matrix ∪ probe per 9-cell table]
    │
    │  another device.probe_capabilities()
    ▼
[merged effective profile — refreshed]
```

The "merged effective profile" state is produced by the 9-cell
probe-vs-matrix merge rule in `contracts/probe-api.md` Edge case 7 and
the diagram in `contracts/matrix-lookup.md` §"Probe-vs-matrix
precedence": **probe `SUPPORTED` or `UNSUPPORTED` always wins, but
probe `UNKNOWN` PRESERVES any matrix-confirmed status** (so a
hardware-bench-verified matrix `UNSUPPORTED` for, e.g., `CONTACT_ADD`
on X915S — confirmed by the door-phone `add_contact` write attempt
returning `unsupported action` per issue #121 — is never silently
flipped back to `UNKNOWN` by a re-probe that didn't exercise the write
capability, since per FR-003 the probe never classifies write
capabilities). This is critical for FR-009 correctness and means
re-probing is always safe and additive.

The transition is one-way per phase: Phase 1 supports only the
[no profile] → [merged effective profile] step (no matrix yet — the
"merged" state degenerates to the pure probe-derived case when the
matrix component is empty). Phase 2 introduces the
[matrix-derived OR conservative-unrecognized] state on connect, at
which point the merge rule starts mattering. Phase 3 and 4 add no new
states.
