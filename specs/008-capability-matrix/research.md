<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Phase 0 Research: Capability Probe, Matrix, and Surfacing

**Feature**: 008-capability-matrix
**Date**: 2026-06-13

## Unknowns from Technical Context

None block authoring. Language, runtime, dependencies, testing framework,
project structure, target platform, and packaging backend (`hatch` via
`uv-dynamic-versioning`, pure-Python wheels, no extra package-data
declared in `pyproject.toml`) are all already established. The spec does
introduce eleven design topics that must be settled before Phase 1 begins;
each is captured below as a numbered decision with rationale and
alternatives considered.

---

## Decision 1: Probe ordering and timeout bounding

**Decision**: The probe issues a fixed, ordered sequence of **read-only**
calls — at most one per logical capability class — and short-circuits on
authentication failure. Order:

1. `GET /api/system/info` — establishes device class + firmware version.
   This is the *only* call whose absence aborts the probe (without
   `info`, the probe cannot classify the device).
2. `GET /api/system/status` — **device-health connectivity check only**.
   The result is recorded as a free-form summary in
   `DeviceCapabilities.notes["system_status"]` (e.g. `"ok"` /
   `"http_500"` / raw body for unusual responses). **Step 2 does NOT
   classify any capability**: `/api/system/status` is the universal
   device-health endpoint, NOT a relay-status marker (`/api/system/*`
   and `/api/relay/*` are independent namespaces — IT83 returns
   "No handlers" only on `/api/relay/*` while still serving
   `/api/system/*`). Per `spec.md` FR-011 + `data-model.md` §"Explicit
   out-of-scope", `AkuvoxDevice.get_status()` is itself not
   capability-gated, so step 2's only roles are (i) connectivity
   sanity-check on the way to step 9 and (ii) a free-form note for
   maintainers. **`RELAY_STATUS` is classified solely by step 9.**
3. `GET /api/user/get?page=1` — user-list + user-schema capability marker.
4. `GET /api/contact/get?page=1` — contact-list + contact-schema
   capability marker (probe records whether `ID` is present in any item
   to set the apartment-book-schema flag).
5. `GET /api/schedule/get` — schedule-list capability marker.
6. `GET /api/group/get` — group-list capability marker.
7. `GET /api/log/door/get?page=1` — door-log capability marker.
8. `GET /api/log/call/get?page=1` — call-log capability marker.
9. `GET /api/relay/status` — **sole `RELAY_STATUS` classifier** and the
   `/api/relay/*` namespace marker (the apartment-book / IT83 indoor
   monitors return "No handlers" here while still serving
   `/api/system/*`).

Step 9 is **not** redundant with step 2: step 2 is a health probe that
writes only `notes["system_status"]` and classifies nothing; step 9 is
the only step that sets `RELAY_STATUS`. Splitting them this way means
the `/api/relay/*` namespace signal (which drives the FCGI-vs-API
adapter inference, per Decision 2) is unambiguous and independent of
device-health noise. Cross-reference: `contracts/probe-api.md` §"Probe
step sequence" steps 2 and 9; `spec.md` FR-011; `data-model.md`
§"Explicit out-of-scope".

The `/fcgi/do?action=OpenDoor` adapter is **not probed** by sending a
trigger — that would fire a relay. The probe records
`RELAY_TRIGGER_FCGI` with status `UNKNOWN` (see Decision 2). Only
matrix entries — populated from hardware-bench observation, e.g. the
IT83 community-reporter evidence in issue #122 — promote
`RELAY_TRIGGER_FCGI` to `SUPPORTED`. The earlier, rejected heuristic
("infer FCGI availability from `/api/relay/*` absence + indoor-monitor
model prefix") is **not** used: see Decision 2's rejected-alternative
note on read-to-write inference, which applies for the same reason.

Each call uses the existing `AkuvoxHttpClient` and is bounded by the
configurable `probe_timeout` (default 5 s, separate from the regular
`timeout`). The probe runs sequentially — not concurrently — so an offline
or slow device cannot fan out into N parallel timeouts. Total probe time
is bounded by `len(steps) × probe_timeout` worst case (≈ 45 s default for
9 steps), but the typical case is closer to `len(steps) ×
single_request_latency` (sub-second on a healthy LAN).

**Rationale**:

- Sequential issue keeps the probe gentle on devices with single-threaded
  HTTP handlers (observed on IT83).
- Bounding timeout per-call (not just total) means a device that
  silently drops one request does not stall the whole probe.
- 401/403 short-circuits: if `system/info` returns auth-failure, the
  probe raises `AkuvoxAuthenticationError` immediately and produces no
  partial report (FR-004, edge case "auth failure during probe").

**Alternatives considered**:

1. **Concurrent gather of all probe calls.** Rejected: pessimistic
   timeout fan-out on devices with single-threaded HTTP. The latency win
   on a healthy LAN (≤ 1 s saved) is not worth the worst-case cost.
2. **Adaptive probe driven by `system/info` result** (e.g. on a
   confirmed IT83 skip the `/api/user/get` probe because the matrix
   marks user-write capabilities as `UNKNOWN`). **Rejected**: the probe
   must be deterministic and complete. Skipping steps based on matrix
   defaults would (a) cause the probe to report `UNKNOWN` for a
   capability that the device might actually support if firmware has
   changed (the matrix is a curated default, not ground truth — the
   whole point of the probe is to challenge the matrix), and (b)
   contradict `contracts/probe-api.md` §"Probe step sequence" which
   mandates exactly nine calls and `contracts/probe-api.md` edge case 7
   (the 9-cell merge table) which depends on the probe classifying
   every read capability as `SUPPORTED` / `UNSUPPORTED` / `UNKNOWN`.
   Matrix lookup happens in Phase 2 (`AkuvoxDevice.__aenter__`); the
   probe is the explicit opt-in to challenge that lookup. Skipping
   probe steps based on matrix defaults would collapse those two
   distinct mechanisms into one and defeat the merge table.
3. **Probe writes (e.g. add and immediately delete a synthetic user).**
   Rejected: violates FR-003 (probe must be non-destructive). Also
   leaves observable state on devices that fail mid-sequence.

---

## Decision 2: Capability storage shape (three-valued status)

**Decision**: `DeviceCapabilities` is a `@dataclass(frozen=True, kw_only=True)`
holding:

- `device_class: str` — e.g. `"X916"`, `"X915S"`, `"E18C"`, `"IT83"`.
- `firmware_version: str` — e.g. `"916.30.10.114"`.
- `capabilities: Mapping[Capability, CapabilityStatus]` — the per-capability
  status profile. `CapabilityStatus` is a three-valued `enum.Enum`:
  `SUPPORTED` (the device is confirmed to handle this capability),
  `UNSUPPORTED` (the device is confirmed to reject this capability,
  e.g. an `unsupported action` envelope was specifically observed), and
  `UNKNOWN` (the library has no positive evidence either way — the
  default for any capability not explicitly listed in the mapping).
- `field_aliases: Mapping[str, FieldAliases]` — keyed by logical field
  name (e.g. `"schedule_relay"`); value is a `FieldAliases` frozen
  dataclass with `read: tuple[str, ...]` (consulted in order, first
  present wins) and `write: tuple[str, ...]` (every name emitted with
  the same value).
- `schema_shapes: Mapping[str, SchemaShape]` — keyed by resource (e.g.
  `"contact"`); value is an enum-like marker (`SchemaShape.DOOR_PHONE`
  or `SchemaShape.APARTMENT_BOOK`).
- `notes: Mapping[str, str]` — keyed mapping of note-key → value/summary
  (e.g. `notes["system_status"] = "ok"` or
  `notes["contact_get_body"] = "<raw unsupported-action body>"`). Replaces
  the earlier tuple-of-strings shape so the probe (and matrix loader)
  can write keyed entries without colliding.
- `provenance: Provenance | None` — `None` for probe-derived profiles;
  `Provenance(test_bench_device_id, firmware_version, library_version, observed_at)`
  for matrix-derived profiles.

`DeviceCapabilities` exposes:

- `status_of(capability) -> CapabilityStatus` — returns the explicit
  status for `capability`, or `UNKNOWN` if absent from the mapping.
- `require(capability, *, allow_unknown=False) -> None` — the per-call
  gate. Raises `AkuvoxUnsupportedError` unless the status is `SUPPORTED`
  (or `UNKNOWN` when `allow_unknown=True`).
- `supported_set` — derived `frozenset[Capability]` returning the
  capabilities whose explicit status is `SUPPORTED`. Provided so
  introspection callers and the docs-render path can keep the
  set-shaped view that the spec's Key Entities prose describes.

`Capability` is a `enum.Enum` with **string values** that match the
canonical capability identifier so the public surface is grep-friendly
(e.g. `Capability.RELAY_TRIGGER_API.value == "relay.trigger.api"`).
`CapabilityStatus` likewise carries lowercase string values
(`"supported"`, `"unsupported"`, `"unknown"`) safe to serialise into
notes / provenance (notes values are plain `str`).

A per-`AkuvoxDevice` boolean attribute `attempt_unknown_capability`
(default `False`) is the explicit opt-in for callers who want
`UNKNOWN`-status operations to fall through to an actual HTTP attempt
rather than fail fast. When `True`, `require(capability)` is called
with `allow_unknown=True` for that capability; the device's runtime
response then either succeeds or raises whichever error the legacy
HTTP layer surfaces (typically `AkuvoxUnsupportedError(reason=
"envelope_unsupported")` from `_http.py:201` on `Api unsupported`).
**The default is fail-fast** — explicit opt-in keeps the spec's
"clear, fail-fast errors instead of cryptic device responses" UX
intact unless the integrator deliberately disables it.

**Rationale**:

- The three-valued model captures a distinction the original
  `frozenset[Capability]` model conflated: "we have positive evidence
  this works" vs. "we have positive evidence this fails" vs. "we have
  no evidence either way". Conflating UNKNOWN with UNSUPPORTED was a
  reasonable initial pass, but it would have surfaced false negatives
  on probe-derived profiles for read capabilities the probe genuinely
  did not exercise. Conflating UNKNOWN with SUPPORTED (the rejected
  read-to-write inference heuristic) would have surfaced as cryptic
  device-side errors at call time — exactly the UX failure the spec is
  written to eliminate (issue #123 goals; FR-013 spirit).
- The default mapping behaviour (`status_of(missing_capability)`
  returns `UNKNOWN`) keeps the data structure compact: matrix entries
  list only what they have evidence for; an absent capability is
  implicitly UNKNOWN with no per-entry boilerplate.
- The `attempt_unknown_capability` opt-in addresses the integrator who
  has a device that *should* work but lacks a matrix entry yet — they
  can flip the flag, exercise the operation, and feed observed
  behaviour back to a future matrix entry. It is **not** how the
  library auto-learns (out-of-scope item 3 still holds: probe results
  do not mutate the shipped matrix); it is a per-connection escape
  hatch.
- Frozen dataclass + `Mapping[Capability, CapabilityStatus]` (typically
  backed by an immutable `MappingProxyType` over a dict literal in
  matrix entries) is hashable for tests via the `(device_class,
  firmware_version, frozenset(capabilities.items()), …)` tuple.
- `FieldAliases` carries both read and write lists because the spec's
  edge case "field-name alias collision" (line 119 of spec.md) requires
  both directions: writes emit every name, reads consult the list in
  order. Using a single `tuple[str, ...]` would conflate them.
- Provenance metadata is structured (not freeform string) so the
  doc-vs-matrix consistency test (Phase 4) can introspect it.

**Alternatives considered**:

1. **`frozenset[Capability]` (the original Phase-1 plan).** Rejected
   on the read-to-write-inference safety argument above. The
   three-valued generalisation costs one enum and one accessor; the
   correctness win is large.
2. **Two sets: `supported: frozenset[Capability]` and `unsupported:
   frozenset[Capability]` (UNKNOWN = absent from both).** Rejected:
   redundant with the mapping; consistency rules ("not in both
   simultaneously") have to be enforced by validators that the
   mapping shape makes structurally impossible.
3. **`set[Capability]` only, no field_aliases / schema_shapes.**
   Rejected: Phase 3's refactor (FR-014, FR-015) requires the alias
   lists and schema flags to be on the same record so the parser can
   consult them in one lookup.
4. **Pydantic / `attrs`.** Rejected: introduces a runtime dependency the
   library does not currently take. Frozen `@dataclass` covers the
   immutability + equality semantics we need.
5. **`Capability` / `CapabilityStatus` as `enum.IntEnum`.** Rejected:
   integer values are not stable across reorderings; `enum.Enum[str]`
   carries the canonical name verbatim and is safe to serialise.
6. **`attempt_unknown_capability` as a constructor kwarg on
   `AkuvoxDevice` rather than a settable attribute.** Considered;
   either is acceptable. Kept as a settable attribute so an integrator
   can flip the flag for one specific call without rebuilding the
   device. A future revision may add a context-manager
   (`device.allow_unknown(): …`) for scoped opt-in if needed.

---

## Decision 3: Field-name alias mechanism (Phase 3 refactor)

**Decision**:

- **Read side (consume)**: `User.from_api_response(data, *, capabilities)`
  takes the `DeviceCapabilities` (or just its `field_aliases`) as a kwarg.
  The current hardcoded chain at `src/pylocal_akuvox/models/users.py:35-44`
  is replaced by:

  ```python
  for key in capabilities.field_aliases["schedule_relay"].read:
      if key in data:
          schedule_relay = data[key]
          break
  ```

  When no capability record is supplied (legacy callers that have the
  raw dict), a module-level `DEFAULT_USER_FIELD_ALIASES = FieldAliases(read=("ScheduleRelay", "Schedule-Relay", "Schedule"), write=("ScheduleRelay", "Schedule-Relay"))`
  preserves today's behavior. This default is **also** what Phase 2's
  unrecognized-device fallback uses, and is identical to the X916 matrix
  entry's user-aliases — so refactoring Phase 3 cannot regress against
  existing direct callers of `User.from_api_response(data)`.

- **Write side (emit)**: `users.add_user` and `users.modify_user` are
  module-level free functions that take `http: AkuvoxHttpClient` and
  have no `self`, so they cannot consult a `_capabilities` attribute
  directly. The Phase 3 contract (per tasks.md T064) is: each function
  accepts an optional keyword-only `field_aliases: FieldAliases | None
  = None` parameter. The service function emits the schedule value
  under each name in `field_aliases.write` (defaulting to
  `DEFAULT_USER_FIELD_ALIASES.write` when the kwarg is `None` or
  omitted). The capability extraction lives on the **`AkuvoxDevice`
  wrapper layer**: `AkuvoxDevice.add_user(...)` extracts
  `self._capabilities.field_aliases.get("schedule_relay",
  DEFAULT_USER_FIELD_ALIASES)` and passes it as `field_aliases=` to
  the service function. This split keeps service modules
  capability-unaware (they only depend on `_http.py` types and the
  capability dataclasses for typing), and centralises the gate on the
  `AkuvoxDevice` wrappers (per FR-011 audit, tasks.md T038/T049).
  Today's unconditional dual-write becomes the matrix default at the
  wrapper layer, not a hardcoded payload in the service function.

**Rationale**:

- A single source of truth (the capability record) replaces two parallel
  hardcoded lists in `users.py` and `models/users.py`. New firmware
  bands need only a matrix entry change (FR-017, SC-007).
- The default fallback preserves bytes-on-the-wire compatibility with
  every supported device today (FR-016). Tests for #99/#101 and
  #118/#120 remain green with no logic changes.
- Calling `from_api_response(data)` with no `capabilities` arg is still
  legal — the kwarg defaults to a sentinel that resolves to
  `DEFAULT_USER_FIELD_ALIASES` — so external consumers that imported
  `User` directly are not broken.

**Alternatives considered**:

1. **Method on `User`: `User.field_aliases_for(capabilities)`.**
   Rejected: hides the consult site inside a method on the model class;
   the goal of the refactor is to make consult sites *explicit* and
   driven by the capability record.
2. **A global module-level mutable mapping that callers pre-populate.**
   Rejected: violates the "no auto-update of matrix at runtime"
   constraint (out-of-scope item 3 in spec) and would surprise users
   with action-at-a-distance.
3. **Per-device subclasses of `User`.** Rejected: explosion of types,
   and the spec's whole point is to *avoid* device-class branching in
   model code.

---

## Decision 4: Adapter dispatch design

**Decision**: A flat **registry** keyed by `(Capability, str)` where the
second element is a variant tag (e.g. `"api"`, `"fcgi"`):

```python
RELAY_TRIGGER_ADAPTERS: dict[tuple[Capability, str], RelayTriggerAdapter] = {
    (Capability.RELAY_TRIGGER_API, "api"): _api_relay_trigger,
    (Capability.RELAY_TRIGGER_FCGI, "fcgi"): _fcgi_relay_trigger,
}
```

Dispatch order: at `device.trigger_relay()` call time, iterate the
device's `supported` set in a documented preference order
(`RELAY_TRIGGER_API` before `RELAY_TRIGGER_FCGI` — i.e. prefer the
modern endpoint where both are present) and call the first registered
adapter. Callers may override via a new optional kwarg:
`device.trigger_relay(..., adapter=Capability.RELAY_TRIGGER_FCGI)`. If the
override names a capability the device does not support, raise
`AkuvoxUnsupportedError` *with the override capability* in the
structured fields.

**Rationale**:

- Flat dict + documented preference order is trivial to test and reason
  about. No metaclass magic.
- The `(Capability, str)` key shape generalizes: future capabilities
  with multiple variants (e.g. `device.set_config` over `/api/*` vs
  `/web/*`) plug in by adding registry entries, no scaffolding change.
- Keeping the override hook as an explicit kwarg satisfies FR-012's
  "callers MUST be able to override".

**Alternatives considered**:

1. **Polymorphic adapter classes with `__init_subclass__` registration.**
   Rejected: more LOC, more import-order sensitivity, and harder to
   inspect from a test.
2. **Capability-keyed lookup only (no variant tag).** Rejected: the
   override kwarg needs a stable identifier independent of which
   capabilities the matrix happens to enumerate today.
3. **Dispatch at the matrix-entry level (each entry carries a
   bound adapter).** Rejected: matrix authors would need to know about
   adapters; we want matrix authors to declare *what is supported*, not
   *how to call it*. The registry stays in `capability_adapters.py`,
   the matrix stays in `capability_matrix.py`.

---

## Decision 5: Matrix authoring format

**Decision**: The matrix is a **Python literal** (`tuple[tuple[DeviceClassPattern, DeviceCapabilities], ...]`)
in `src/pylocal_akuvox/capability_matrix.py`. No TOML/YAML/JSON.

**Rationale**:

- The library distributes pure-Python wheels via `hatch` +
  `uv-dynamic-versioning`. `pyproject.toml` declares no
  `tool.hatch.build.targets.wheel.force-include` for static data files.
  Adding TOML/YAML would require declaring package data, configuring
  wheel inclusion, and either taking a YAML runtime dep (`pyyaml`) or
  parsing TOML via stdlib `tomllib` at import time. Each step is
  avoidable cost.
- Matrix authoring is a maintainer activity (not an end-user activity);
  matching the project's idiom of "Python data in Python files" keeps
  the diff legible and avoids a parse step on every import.
- Type checking, IDE go-to-definition, and `enum`-value autocompletion
  all work on the literal. None work on a YAML/TOML string unless we
  add a schema layer.
- Phase 4's docs page renders the matrix via an autodoc helper that
  imports `capability_matrix.CAPABILITY_MATRIX` and produces a
  reStructuredText table — reading the values from Python is the
  shortest path.

**Alternatives considered**:

1. **TOML in `src/pylocal_akuvox/data/capability_matrix.toml`.**
   Rejected: adds packaging configuration (`[tool.hatch.build.targets.wheel]
   include = …`), a parse step at import time, and a schema validator to
   prevent typos that the Python literal catches via mypy.
2. **YAML.** Rejected: adds a runtime dependency.
3. **JSON.** Rejected: no comments. Matrix entries benefit from
   per-entry rationale comments which JSON forbids.

---

## Decision 6: Pattern matching for device class

**Decision**: `DeviceClassPattern(model_prefix: str, firmware_band: str)`
where:

- `model_prefix` is a literal model-name prefix matched against
  `DeviceInfo.model` via `device_info.model.startswith(pattern.model_prefix)`.
  Examples: `"X916"`, `"X915S"`, `"E18C"`, `"IT83"`.
- `firmware_band` is one of three forms, parsed at pattern construction
  time (so import-time errors surface bad patterns):
  - **Glob**: `"916.30.10.*"` — last segment is a wildcard.
  - **Floor**: `"2915.30.10.114+"` — exact major/minor and a floor patch
    (≥ 114). Match: `parse_version(observed) >= parse_version(floor)`
    using a stdlib-only tuple-of-ints comparison (each version split on
    `.`, padded, compared as `tuple[int, ...]`).
  - **Exact**: `"83.30.10.4"` — no wildcard, must match byte-for-byte.

Match precedence when multiple patterns match the same device: the
first matching entry in `CAPABILITY_MATRIX` wins. The matrix is ordered
**most-specific first** (exact > floor > glob) by convention; a Phase 1
unit test asserts there are no overlapping patterns within the curated
matrix.

**Rationale**:

- The three forms cover the four observed cases exactly: X916 takes a
  glob, X915S takes a floor (so #119's old `2915.30.10.113` does not
  match the current entry), E18C takes a glob, IT83 takes an exact match.
- Stdlib-only version comparison avoids the `packaging` dependency for
  a use case that does not need PEP 440 semantics.
- Import-time pattern validation catches typos in matrix entries before
  any test runs.

**Alternatives considered**:

1. **`re.compile` regex patterns.** Rejected: matrix entries become
   harder to read and small typos are silent. Globs and floors cover
   100% of observed cases.
2. **`packaging.version.Version` for floor matching.** Rejected: the
   library does not currently take `packaging`. Tuple-of-ints
   comparison is sufficient because Akuvox firmware versions are
   strict dotted integers.

---

## Decision 7: Probe vs. matrix precedence

**Decision**:

- `device.connect()` (executed via the async-context-manager
  `__aenter__`) calls `GET /api/system/info` (already does this for
  `get_info()`); the result is fed to a matrix lookup. If a pattern
  matches, the device's effective profile is set from the matrix entry
  — **no list endpoints are probed** (FR-008). If no pattern matches,
  the effective profile is set to a conservative
  `DeviceCapabilities(device_class="<observed>", capabilities={})`
  (every key absent → `status_of(...)` returns
  `CapabilityStatus.UNKNOWN`) whose every operation raises
  `AkuvoxUnsupportedError` with reason `"capability_unknown"` and a
  message instructing the caller to either set
  `device.attempt_unknown_capability=True` or call
  `probe_capabilities()` (FR-013).
- The integrator may call `await device.probe_capabilities()` at any
  time; the result replaces the effective profile for the lifetime of
  that connection (FR-009).
- The library never auto-probes on first call (FR-013); the conservative
  profile produced by an unrecognized-device path is what callers see
  until they explicitly probe.

**Rationale**:

- Matches the spec's precedence rule line-for-line (FR-008, FR-009,
  FR-013).
- Auto-probing would surprise integrators with extra round-trips and
  contradict the per-call-cost expectation (Phase 1 acceptance scenario
  6 in User Story 2 explicitly tests the *explicit* probe wins).
- Conservative-on-unknown gives integrators a clear "you need to
  probe" message instead of a half-populated profile.

**Alternatives considered**:

1. **Auto-probe on first call when matrix lookup misses.** Rejected by
   the spec (FR-013).
2. **Persist probe results across connections.** Rejected: out of scope
   per spec out-of-scope item 3 ("no auto-update of matrix from probe
   results").

---

## Decision 8: `AkuvoxUnsupportedError` UX

**Decision**: Evolve the existing class additively. The current shape
(`src/pylocal_akuvox/exceptions.py:31-32`) is a one-line stub:

```python
class AkuvoxUnsupportedError(AkuvoxError):
    """API endpoint not supported by the device firmware."""
```

After Phase 2 it becomes:

```python
class AkuvoxUnsupportedError(AkuvoxError):
    """Operation unsupported by the connected device.

    Args:
        message: Human-readable reason for the failure.
        capability: The Capability whose absence triggered this error,
            or None when raised from a layer that does not yet have
            capability context (e.g. the legacy _http.py envelope-message
            classifier).
        device_class: The detected device class string (e.g. "IT83"),
            or None if unrecognized at the time of the raise.
        reason: Structured reason code, one of:
            "capability_missing"  | "capability_unknown" |
            "device_unrecognized" | "adapter_missing"    |
            "envelope_unsupported" (legacy).

    """

    def __init__(
        self,
        message: str,
        *,
        capability: Capability | None = None,
        device_class: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.capability = capability
        self.device_class = device_class
        self.reason = reason
```

The existing call site at `src/pylocal_akuvox/_http.py:201`
(`raise AkuvoxUnsupportedError(message)`) continues to work unchanged
because every new parameter is keyword-only with a `None` default. The
existing test at `tests/unit/test_http.py:226` continues to pass.

The reason taxonomy is fixed in code (not a free string) because Phase
4's mvp_test integration discriminates messages by reason code.

**Rationale**:

- Backward compatible: no required new arg.
- Structured fields satisfy FR-010 ("missing capability, detected
  device class, and a human-readable reason").
- Distinguishing "device cannot do this" (`capability_missing`),
  "we have no positive evidence either way for this capability"
  (`capability_unknown` — the new three-valued status; see Decision 2),
  and "library does not yet implement this for this device class"
  (`adapter_missing`) is required by spec edge case "Adapter dispatch
  with no matching adapter" and by the fail-fast UX goal in
  Decision 2's rationale.
- `capability_unknown` is what the per-method gate raises when a
  probe-derived profile records the operation as `UNKNOWN` (e.g. any
  write capability after a probe against an unrecognised device) and
  the integrator has not opted in via `attempt_unknown_capability`.
  The message names the device class and directs the caller to either
  add a matrix entry or opt in.
- Keeping the legacy `envelope_unsupported` reason on the `_http.py`
  raise gives Phase 4 a discriminator to classify "the device returned
  the well-known unsupported envelope at runtime, even though the
  matrix said the capability was supported" — useful as a probe-vs-matrix
  staleness signal.

**Alternatives considered**:

1. **New exception class `AkuvoxCapabilityError`.** Rejected: spec
   FR-010 names `AkuvoxUnsupportedError` explicitly. Adding a new class
   would break `__all__` and require import-line edits in the
   downstream Home Assistant component.
2. **Required `capability` kwarg.** Rejected: would break the existing
   `_http.py:201` call site and the legacy test.

---

## Decision 9: mvp_test integration shape (Phase 4)

**Decision**: At startup (after `AkuvoxDevice.__aenter__` returns),
`examples/mvp_test.py` calls `await device.probe_capabilities()` once and
stores the result. Each demo step is wrapped:

```python
async def step(name: str, capability: Capability, fn: Callable[[], Awaitable[None]]) -> None:
    status = device.capabilities.status_of(capability)
    if status is CapabilityStatus.UNSUPPORTED:
        print(f"  SKIP: {name}: not supported on this device class "
              f"({device.capabilities.device_class})")
        return
    if status is CapabilityStatus.UNKNOWN:
        print(f"  SKIP: {name}: capability unknown for this device class "
              f"({device.capabilities.device_class}); "
              f"add a matrix entry or set device.attempt_unknown_capability=True")
        return
    try:
        await fn()
        print(f"  OK:   {name}")
    except AkuvoxUnsupportedError as exc:
        print(f"  SKIP: {name}: {exc} (reason={exc.reason})")
```

Snapshot-style stdout assertions in `tests/integration/test_mvp_smoke.py`
(introduced in Phase 4) feed mocked devices through the script and
confirm that against an IT83 the user-write and contact-write steps emit
the SKIP prefix (SC-010). The two SKIP paths (UNSUPPORTED vs UNKNOWN)
produce distinguishable messages so the integrator can tell apart "we
know this device cannot do it" from "we don't know yet — add a matrix
entry".

**Rationale**:

- Probe runs exactly once — explicit per FR-019.
- The integrator sees actionable output: which capability is missing
  or unknown, which device class is connected, and the structured
  reason code.
- The skip paths catch the post-Phase-2 fail-fast
  `AkuvoxUnsupportedError` (both `capability_missing` and
  `capability_unknown` reasons) *and* any rare matrix-vs-actual
  mismatch where the device emits `Api unsupported` at runtime even
  though the matrix marked the capability as present
  (`envelope_unsupported`).

**Alternatives considered**:

1. **Do not probe; let the fail-fast errors carry the SKIP message.**
   Rejected: defeats the FR-019 requirement that steps be *skipped*
   rather than attempted-and-failed.
2. **Probe before every step.** Rejected: needlessly chatty.

---

## Decision 10: Backward compatibility through the Phase 3 refactor

**Decision**:

- Phase 3 ships **no test logic changes** to the existing #99/#101
  (E18C dual-write) or #118/#120 (X915S `Schedule` read) tests. The
  refactor's correctness is established by those tests staying green
  *unchanged* (FR-016, SC-008). Phase 3 may add *new* tests that assert
  "the alias list is read from the capability record" but does not
  rewrite existing tests.
- The X916 matrix entry's `field_aliases["schedule_relay"]` is set to
  `FieldAliases(read=("ScheduleRelay", "Schedule-Relay", "Schedule"), write=("ScheduleRelay", "Schedule-Relay"))`
  — i.e. exactly today's hardcoded behavior — and is also used as the
  conservative-fallback default for unrecognized devices. This means
  the Phase 3 refactor is observably a no-op against any device the
  library currently recognizes *or* against any device it does not yet
  recognize, modulo the new `AkuvoxUnsupportedError` raises that
  Phase 2 already introduced.
- No deprecation warnings are emitted: the migration is silent because
  the public API's externally observable behavior does not change.
  Internal callers of `User.from_api_response(data)` (today's signature
  with no kwargs) continue to work via the default fallback.

**Rationale**:

- A "silent migration" is appropriate here because the public API
  surface is unchanged. Deprecation warnings would imply an upcoming
  break that is not planned.
- Anchoring Phase 3's correctness to the unchanged passing of existing
  regression tests is the most defensible TDD posture.

**Alternatives considered**:

1. **Emit a `DeprecationWarning` when `User.from_api_response(data)` is
   called without a `capabilities` kwarg.** Rejected: there is no
   future plan to remove the no-kwarg form; the warning would be noise.
2. **Drop the no-kwarg form entirely.** Rejected: breaks downstream
   imports.

---

## Decision 11: Documentation surface

**Decision**:

- New page: `docs/api/capabilities.rst` containing:
  - `:autoclass: pylocal_akuvox.Capability` with member listing.
  - `:autoclass: pylocal_akuvox.DeviceCapabilities`.
  - A directly-rendered table of `CAPABILITY_MATRIX` produced by a
    sphinx custom directive (`.. capability-matrix::`) that imports
    `pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX` and emits a
    reST grid table at build time.
  - A "Contributing a new device class" section with a worked example.
- The page is added to `docs/index.rst`'s toctree.
- A pytest test (`tests/unit/test_docs_matrix_consistency.py`)
  asserts:
  1. Every `DeviceClassPattern.model_prefix` in `CAPABILITY_MATRIX` is
     mentioned in `docs/api/capabilities.rst`.
  2. Every device class mentioned in `docs/api/capabilities.rst` is
     present in the matrix.

The test consumes the .rst as plain text (no sphinx parse) — looks for
`"X916"`, `"X915S"`, `"E18C"`, `"IT83"` headings. This is enough for
SC-009 without dragging sphinx into the unit-test dependency surface.

**Rationale**:

- Autodoc on the enum + dataclass means the public-API docs stay in
  sync with code.
- The custom directive avoids hand-maintained tables that go stale
  (the failure mode SC-009 was written to prevent).
- The consistency test is a unit test (not a doc-build test) so it
  runs without sphinx in CI; sphinx remains a docs-only optional
  dep.

**Alternatives considered**:

1. **Hand-maintained table.** Rejected: predictable drift, exactly the
   failure mode SC-009 is written to catch.
2. **Custom sphinx extension that parses the matrix in `conf.py`.**
   Acceptable, but the small inline directive is simpler. Revisit if
   the matrix grows past ~10 entries.
3. **External wiki page.** Rejected: separation of concerns issue —
   docs that ship with the library cannot drift from the matrix; an
   external wiki can.

---

## Summary of New Modules and Their Owners

| Module | Phase | Approx. LOC | Contents |
|--------|-------|-------------|----------|
| `src/pylocal_akuvox/capabilities.py`        | 1 | 250–350 | `Capability` enum, `CapabilityStatus` enum, `DeviceCapabilities`, `DeviceClassPattern`, `FieldAliases`, `SchemaShape`, `Provenance` |
| `src/pylocal_akuvox/capability_probe.py`    | 1 | 200–300 | `probe_capabilities()`, response classifier |
| `src/pylocal_akuvox/capability_matrix.py`   | 2 | 150–250 | `CAPABILITY_MATRIX` literal (4 entries today) |
| `src/pylocal_akuvox/capability_adapters.py` | 2 | 100–200 | `RELAY_TRIGGER_ADAPTERS` registry + adapter callables |

All four modules carry the project SPDX header pair and a one-line module
docstring per constitution §I.

## Summary of Touched Modules

| Module | Phase | Touch |
|--------|-------|-------|
| `src/pylocal_akuvox/exceptions.py` | 2 | Additive evolution of `AkuvoxUnsupportedError` |
| `src/pylocal_akuvox/device.py`     | 1, 2 | Phase 1: `probe_capabilities()` + `capabilities` property; Phase 2: matrix lookup on connect + per-method gate |
| `src/pylocal_akuvox/relay.py`      | 2 | Adapter registry dispatch |
| `src/pylocal_akuvox/users.py`      | 2, 3 | Phase 2: capability gate; Phase 3: write-alias-list-driven payload |
| `src/pylocal_akuvox/contacts.py`   | 2, 3 | Phase 2: capability gate; Phase 3: schema-shape-driven payload |
| `src/pylocal_akuvox/{config,groups,logs,schedules}.py` | 2 | Capability gate |
| `src/pylocal_akuvox/models/users.py`    | 3 | Read-alias chain consults capability record |
| `src/pylocal_akuvox/models/contacts.py` | 3 | Apartment-book schema selection |
| `src/pylocal_akuvox/__init__.py`        | 1, 2 | Re-exports new public names |
| `examples/mvp_test.py`                  | 4 | Probe-then-skip-supported |
| `docs/api/capabilities.rst`             | 4 | New page (autodoc + matrix render) |
| `docs/api/index.rst`                    | 4 | Toctree entry |
