<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Capability Probe Orchestration Module

**Owning module**: `src/pylocal_akuvox/_capability_probe.py`
**Owning tests**: `tests/unit/test_capability_probe.py` (all
end-to-end probe tests, including step-1 abort paths, the 9-call
sequence, idempotence, and the step-3 / step-4 side-effect dispatch),
`tests/unit/test_capability_module_layout.py` (import assertions per
FR-011)

## Internal-Consumer Surface

This module is the orchestration layer: it owns the seven step-path
constants, the `_LATER_STEPS` step-driver tuple, and the
`probe_capabilities` async function that drives the 9-call probe
sequence end to end.

```python
__all__ = [
    "probe_capabilities",
]
```

The step-path constants and `_LATER_STEPS` retain their leading
underscore and are NOT in `__all__`. They are private to the
orchestration. Tests that need to reason about specific step paths
(none do today, post-rewrite) would import them via
`from pylocal_akuvox._capability_probe import _PROBE_STEP_3_PATH`.

The single name in `__all__` (`probe_capabilities`) is **NOT**
underscore-prefixed because the function itself was never private
within the original module (it's the orchestration entry point that
`device.py` imports). Within the new layout, the underscore prefix
on the **module** signals "internal consumer surface only" while
the function name itself remains stable for `device.py`'s import.

## `probe_capabilities` — Invariant Public Behavior

This is the spec's **most important contract**. Every observable
behavior of `probe_capabilities` is preserved across the split. The
function is the one consumers reach (indirectly, through
`AkuvoxDevice.probe_capabilities()`), and it MUST behave identically.

### Signature (exact, must not change)

```python
async def probe_capabilities(
    http: AkuvoxHttpClient,
    *,
    timeout: float = 5.0,
) -> DeviceCapabilities:
```

- First positional parameter: `http` of type `AkuvoxHttpClient`
  (TYPE_CHECKING-only forward reference today; the runtime
  argument is the connection's shared HTTP client).
- Keyword-only `timeout` parameter with default `5.0`. Per-request
  timeout passed through to every `_request_raw` call.
- Returns: `DeviceCapabilities`. Provenance is `None` (the absent
  provenance is the "this came from a probe" marker, per
  `specs/008-capability-matrix/contracts/probe-api.md` and the live source line 459).
- `async def` (must not change).

### Call sequence (exact, must not change)

The probe issues exactly 9 calls in this order:

1. `GET /api/system/info` (step 1) — out-of-band auth/parse gate;
   step-1 401/403/5xx aborts the probe.
2. `GET /api/system/status` (step 2) — health probe; result
   collapsed by `_summarise_system_status` and recorded under
   `notes["system_status"]`.
3. `GET /api/user/get?page=1` (step 3) — probes `Capability.USER_LIST`;
   on `_ProbeOutcome.SUPPORTED` triggers `_record_user_aliases`
   AND `_record_user_schema_keys` side effects.
4. `GET /api/contact/get?page=1` (step 4) — probes
   `Capability.CONTACT_LIST`; on `_ProbeOutcome.SUPPORTED` triggers
   `_record_contact_shape` side effect.
5. `GET /api/schedule/get` (step 5) — probes
   `Capability.SCHEDULE_LIST`.
6. `GET /api/group/get` (step 6) — probes `Capability.GROUP_LIST`.
7. `GET /api/doorlog/get?page=1` (step 7) — probes
   `Capability.LOG_DOOR`.
8. `GET /api/calllog/get?page=1` (step 8) — probes
   `Capability.LOG_CALL`.
9. `GET /api/relay/status` (step 9) — probes
   `Capability.RELAY_STATUS`.

The seven step-path constants `_PROBE_STEP_3_PATH` …
`_PROBE_STEP_9_PATH` carry these literal paths. The `_LATER_STEPS`
tuple binds each of steps 3–9 to its slug, path, and
`Capability` marker, in this exact order.

### Idempotence guarantee

Two consecutive calls of `probe_capabilities` against an unchanged
device produce **byte-equal** `DeviceCapabilities` instances (the
idempotence guarantee documented in
`specs/008-capability-matrix/contracts/probe-api.md` § "Idempotence",
referenced as SC-002 of that contract — distinct from this spec's
own SC-002 about aislop file-size):

- `provenance` is `None` on both
- No wall-clock timestamp is written into `notes`
- `_summarise_system_status` collapses `SystemTime` / `UpTime`
  drift to a stable token (`"ok"`, `"retcode_<n>"`, `"unparsable"`,
  `"http_<status>"`)
- `_record_user_schema_keys` sorts its output before comma-joining
- `_record_user_aliases` records aliases in observed order, but
  the source iteration order (over `items`) is deterministic
  given an unchanged device

### Exception contract (exact, must not change)

| Trigger | Exception |
|---|---|
| Step 1 HTTP 401 | `AkuvoxAuthenticationError` (probe aborts after 1 call) |
| Step 1 HTTP 403 | `AkuvoxRequestError` (probe aborts after 1 call) |
| Step 1 HTTP 4xx (non-401, non-403) or 5xx | `AkuvoxConnectionError` (probe aborts) |
| Step 1 transport-level failure | `AkuvoxConnectionError` (raised by `_request_raw`; not caught) |
| Step 1 unparsable JSON / missing fields / bool retcode | `AkuvoxParseError` (raised by `_step_1_payload`) |
| Step 1 `DeviceInfo.from_api_response` failure | `AkuvoxParseError` (chained `__cause__` on the original `KeyError` / `TypeError` / `ValueError`) |
| Steps 2–9 transport-level failure (connection refused, timeout, etc.) | `AkuvoxConnectionError` (raised by `_request_raw`; **not** caught by the probe — propagates up and aborts the probe with **no partial profile returned**, per `specs/008-capability-matrix/contracts/probe-api.md` Edge case 5; covered by `tests/unit/test_capability_probe.py::test_probe_transport_refused_during_step_4_raises_no_partial`) |
| Steps 3–9 HTTP 401/403 | recorded as `CapabilityStatus.UNKNOWN`; probe continues; raw body recorded under `notes[f"{slug}_body"]` |
| Steps 3–9 HTTP non-2xx (other than 401/403) or 2xx with non-zero retcode / unparsable body | classified by `_classify_response`; recorded as appropriate `CapabilityStatus`; probe continues |
| Step 2 (any HTTP outcome short of transport failure) | recorded as a stable token under `notes["system_status"]` via `_summarise_system_status`; probe continues; never raises |

The probe NEVER raises on steps 2–9 from a successfully-received HTTP
response (any status code from 2xx through 5xx). Step 2 always
records `notes["system_status"]` regardless of HTTP status. Steps 3–9
fold every HTTP failure mode into the returned
`DeviceCapabilities`'s `capabilities` / `notes` accumulators.

The probe DOES raise on steps 2–9 when the underlying transport
fails (the response never arrives at all — e.g., aiohttp
`ClientError`, connection refused, DNS failure, timeout). In that
case `_request_raw` raises `AkuvoxConnectionError` and the probe
propagates it without recording a partial profile. This matches
`specs/008-capability-matrix/contracts/probe-api.md` Edge case 5 ("probe aborts and no partial
DeviceCapabilities is returned") and is preserved verbatim by the
refactor.

### Side-effect dispatch (exact, must not change)

After each later step's classification:

- If the recorded outcome is anything other than
  `_ProbeOutcome.SUPPORTED`, the raw body is recorded under
  `notes[f"{slug}_body"] = f"{step_status}: {step_body}"`.
- If `path == _PROBE_STEP_3_PATH` AND outcome is `SUPPORTED`,
  call `_record_user_aliases(field_aliases, step_body)` AND
  `_record_user_schema_keys(notes, step_body)`.
- If `path == _PROBE_STEP_4_PATH` AND outcome is `SUPPORTED`,
  call `_record_contact_shape(schema_shapes, step_body)`.

These side effects are part of the contract. Any change to the
guard condition (e.g., recording user aliases when the outcome is
`INDETERMINATE`) would be a behavior change and is out of scope.

### Returned `DeviceCapabilities` shape

```python
DeviceCapabilities(
    device_class=device_info.model,  # from step 1
    firmware_version=device_info.firmware_version,  # from step 1
    capabilities=capabilities,  # dict accumulator, includes KEY_DISCOVERY=SUPPORTED
    field_aliases=field_aliases,  # dict accumulator, possibly empty
    schema_shapes=schema_shapes,  # dict accumulator, possibly empty
    notes=notes,  # dict accumulator, includes system_status
    provenance=None,  # the "this came from a probe" marker
)
```

`DeviceCapabilities.__post_init__` wraps the four accumulator
dicts in `MappingProxyType` on construction; the orchestration
hands them in as plain dicts.

## What This Module Does NOT Export

- The `_ProbeOutcome` enum and marker constants — they live in
  `_probe_outcomes`
- The classifier helpers — they live in `_probe_classifiers`
- The parser / recorder helpers — they live in `_probe_parsers`

## Dependencies

- `pylocal_akuvox._probe_outcomes` — for `_ProbeOutcome` (used in
  step-3 / step-4 side-effect guard:
  `if outcome is _ProbeOutcome.SUPPORTED`)
- `pylocal_akuvox._probe_classifiers` — for `_classify_response`,
  `_outcome_to_status`, `_summarise_system_status`
- `pylocal_akuvox._probe_parsers` — for `_step_1_payload`,
  `_record_user_aliases`, `_record_user_schema_keys`,
  `_record_contact_shape`
- `pylocal_akuvox._capability_profile` — for `DeviceCapabilities`
  and `FieldAliases` (used in the `field_aliases` accumulator
  type annotation)
- `pylocal_akuvox._capability_types` — for `Capability`,
  `CapabilityStatus`, `SchemaShape`
- `pylocal_akuvox.exceptions` — for `AkuvoxAuthenticationError`,
  `AkuvoxConnectionError`, `AkuvoxParseError`, `AkuvoxRequestError`
- `pylocal_akuvox.models` — for `DeviceInfo` (used in
  `DeviceInfo.from_api_response(data)` on step 1)
- `TYPE_CHECKING`-only:
  `pylocal_akuvox._http.AkuvoxHttpClient`
- stdlib: `typing.TYPE_CHECKING`

After the split, the orchestration module does NOT need direct
`json` or `typing.Any` imports — both are used only by the
helpers (`_step_1_payload`, `_extract_items`,
`_summarise_system_status`, `_extract_message`) which now live in
`_probe_parsers.py` / `_probe_classifiers.py`. The orchestration
delegates body-parsing work to those helpers rather than calling
`json.loads` itself, and uses concrete types (no `Any`) in its
function signature and accumulator annotations.

## Top-Level Re-Export

This module does NOT have its `probe_capabilities` symbol added to
`pylocal_akuvox.__all__`. The consumer-facing handle is
`AkuvoxDevice.probe_capabilities()` (a method on the already-public
`AkuvoxDevice` class).

## Backward-Compatibility Note

The following old import paths would have resolved to names now in
this module:

| Old path | Symbol |
|---|---|
| `from pylocal_akuvox.capability_probe import probe_capabilities` | `probe_capabilities` |

Post-split, the old path raises `ModuleNotFoundError`. Internal
consumers (today: `device.py` only) MUST use
`from pylocal_akuvox._capability_probe import probe_capabilities`.
External consumers MUST use `device.probe_capabilities()` (the
public method on `AkuvoxDevice`).

## Behavior-Preservation Guarantee

Post-split, every observable behavior of `probe_capabilities` is
identical to today's implementation. The function body is moved
verbatim (modulo the import statements at the top of the new
module, which now import classifiers / parsers / outcomes from
their new homes). No reordering of HTTP calls, no change to the
9-step sequence, no change to the side-effect dispatch, no change
to the exception types or messages, no change to the returned
`DeviceCapabilities` shape.
