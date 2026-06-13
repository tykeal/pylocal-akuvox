<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Probe API

**Phase**: 1 (PR 1)
**Owning module**: `src/pylocal_akuvox/capability_probe.py` and the
`AkuvoxDevice.probe_capabilities()` method on
`src/pylocal_akuvox/device.py`.
**Owning tests**: `tests/unit/test_capability_probe.py`.

## Public surface

```python
class AkuvoxDevice:
    async def probe_capabilities(
        self,
        *,
        timeout: float | None = None,
    ) -> DeviceCapabilities:
        """Inspect the connected device and return its capability profile.

        Args:
            timeout: Per-request probe timeout in seconds. None uses the
                default of 5.0. The total wall-clock cost is bounded by
                ``len(probe_steps) × timeout``; a typical run is much
                shorter because the probe issues calls sequentially and
                short-circuits on step-1 auth failure.

        Returns:
            A new ``DeviceCapabilities`` populated from observed
            responses. Replaces this connection's effective profile.

        Raises:
            AkuvoxAuthenticationError: Credentials rejected (HTTP 401/403)
                during the first ``GET /api/system/info`` call. The probe
                aborts cleanly after exactly 1 call and does not return a
                partial profile. **Later-step 401/403 does NOT raise this
                exception** — it records the affected capability as
                ``UNKNOWN`` and the probe continues per the
                Call-count invariant in §"Probe step sequence".
            AkuvoxConnectionError: Network/transport failure during any
                probe step.
            AkuvoxParseError: ``GET /api/system/info`` returned a payload
                that does not parse as a ``DeviceInfo``. The probe cannot
                proceed without device-class identification.

        """
```

The wrapper delegates to a module-level helper. Internally:

```python
# src/pylocal_akuvox/capability_probe.py
async def probe_capabilities(
    http: AkuvoxHttpClient,
    *,
    timeout: float = 5.0,
) -> DeviceCapabilities:
    """Module-level helper. The wrapper resolves ``timeout`` to ``5.0``
    when its caller passes ``None``, then calls this helper with the
    resolved value. ``capability_probe`` is a module of free functions
    (no class, no ``self``); the per-call timeout is threaded through
    each ``http._request_raw(..., timeout=timeout)`` invocation.
    """
```

After successful return, `device.capabilities is the_returned_value`
holds: subsequent public method calls on `device` consult this profile.

The returned `DeviceCapabilities` is **deeply immutable**: the
dataclass is `frozen=True`, and the four mapping fields
(`capabilities`, `field_aliases`, `schema_shapes`, `notes`) are wrapped
in `types.MappingProxyType` by `__post_init__` (with a defensive copy
of the input dict). Callers cannot mutate the profile after
construction — `device._capabilities.notes["evil"] = "x"` raises
`TypeError`. This is the invariant gating logic relies on (see
`data-model.md` §"`DeviceCapabilities`" class docstring and the test
enumerated in T028a).

## Probe step sequence (deterministic)

Each step is issued via the **raw HTTP helper** `_request_raw` documented
in the next subsection — NOT via the public `get()`/`post()` methods —
so the classifier can see HTTP status codes and raw response bodies
exactly as the wire delivered them.

**Call-count invariant** — the probe's call total depends on the
outcome of step 1:

- **Step-1 success path** (BOTH (i) HTTP 2xx on `/api/system/info`
  AND (ii) body parses successfully to `DeviceInfo`): the probe issues
  all 9 calls in order. The 9-call total holds even if any of steps
  2–9 returns HTTP 401/403, HTTP 500, `"No handlers"`, `"unsupported
  action"`, or any other non-fatal failure shape — those classify as
  `UNKNOWN`/`SUPPORTED`/`UNSUPPORTED` per the classification table
  below and the probe CONTINUES to the next step.
- **Step-1 auth-failure path** (HTTP 401 or HTTP 403 on
  `/api/system/info`): the probe issues exactly **1** call, then
  raises `AkuvoxAuthenticationError` and aborts. No `DeviceCapabilities`
  is returned. (Without credentials, classifying the rest of the
  capability surface is meaningless — every endpoint would return
  401/403 and produce a profile with every capability `UNKNOWN`,
  which is indistinguishable from a misconfigured probe.)
- **Later-step 401/403** (steps 2–9): the affected step's capability
  marker is recorded as `UNKNOWN`, with `notes["<endpoint_slug>_body"]
  = "<status_code>: <body>"` (e.g. `notes["user_get_body"] = "401:
  Authentication required"`). The probe CONTINUES to the next step
  and still totals 9 calls. Rationale: a per-endpoint 401 after a
  successful step-1 auth is unusual but not impossible (per-endpoint
  ACL on some firmware), and the device-class identification from
  step 1 is still valid; partial classification is more useful than
  a hard abort.

**Step-1 failure modes** — every step-1 outcome that is not the
success path is a fatal abort that returns no `DeviceCapabilities`
(no partial profiles, preserving SC-002 byte-equal idempotence):

| Step-1 outcome | Probe behaviour | Calls | Exception |
|---|---|---|---|
| HTTP 2xx + body parses to `DeviceInfo` | continue to steps 2–9 | 9 | — (returns `DeviceCapabilities`) |
| HTTP 401/403 | abort | 1 | `AkuvoxAuthenticationError` |
| HTTP 2xx + body unparsable to `DeviceInfo` (3 sub-cases: invalid JSON; envelope missing/malformed `retcode`; `DeviceInfo.from_api_response(data)` raises on missing required fields) | abort | 1 | `AkuvoxParseError` |
| HTTP 5xx, or HTTP 4xx other than 401/403 (e.g. 404) | abort | 1 | `AkuvoxConnectionError` (wrap) |
| Transport failure (timeout, connection refused, DNS) | abort | 0–1 | `AkuvoxConnectionError` |

The table below specifies each step's URL, its capability marker, and
per-step notes:

| # | Method | URL | Capability marker | Notes |
|---|--------|-----|-------------------|-------|
| 1 | GET | `/api/system/info`             | `KEY_DISCOVERY` | Mandatory; classifies device class + firmware. Issued via `_request_raw("GET", "/api/system/info", timeout=probe_timeout)`. The probe inspects the returned tuple: if `status in (401, 403)`, raises `AkuvoxAuthenticationError` itself (short-circuit). |
| 2 | GET | `/api/system/status`           | (none — health probe) | Device-health probe only. Result recorded as a free-form note under `DeviceCapabilities.notes["system_status"]` (raw body or short summary like `"ok"` / `"http_500"`). Does NOT classify any capability — `/api/system/status` is universal device-health, NOT relay status. (`RELAY_STATUS` is classified solely by step 9 below.) Per spec FR-011 + `data-model.md` §"Explicit out-of-scope", `AkuvoxDevice.get_status()` is not capability-gated, so step 2's role is connectivity sanity-check + a free-form note for maintainers. |
| 3 | GET | `/api/user/get?page=1`         | `USER_LIST`    | Records observed `ScheduleRelay`/`Schedule-Relay`/`Schedule` field aliases (read direction); records observed presence of `Building`/`Room`/`EffectiveType` for note. |
| 4 | GET | `/api/contact/get?page=1`      | `CONTACT_LIST` | Records observed schema shape (`APTName`/`APTNum`/`Building`/`Landline` → `APARTMENT_BOOK`; otherwise `DOOR_PHONE`). |
| 5 | GET | `/api/schedule/get`            | `SCHEDULE_LIST`| |
| 6 | GET | `/api/group/get`               | `GROUP_LIST`   | |
| 7 | GET | `/api/log/door/get?page=1`     | `LOG_DOOR`     | |
| 8 | GET | `/api/log/call/get?page=1`     | `LOG_CALL`     | |
| 9 | GET | `/api/relay/status`            | `RELAY_STATUS` (sole classifier) | An IT83-style "No handlers" here is the FCGI-only signal. Step 9 is the ONLY probe call that classifies `RELAY_STATUS`; step 2's `/api/system/status` is a distinct device-health endpoint and does not set this capability. |

### Raw HTTP helper (`_request_raw`)

The probe needs to see HTTP status codes, response bodies, and envelope
shapes (`{"retcode": -1, "message": "..."}`) **before** any error
translation, so it can drive `_classify_response(status, body) ->
_ProbeOutcome`. The public `AkuvoxHttpClient.get()` / `.post()` route
through `_handle_response` (`_http.py:177-204`), which translates HTTP
4xx/5xx into `AkuvoxRequestError`/`AkuvoxAuthenticationError`/
`AkuvoxDeviceError`, translates `"unsupported action"` envelopes into
`AkuvoxUnsupportedError`, and translates `retcode < 0` into
`AkuvoxDeviceError` — hiding exactly the signals the probe needs to
classify.

Phase 1 therefore adds a low-level sibling helper:

```python
async def _request_raw(
    self,
    method: str,
    path: str,
    *,
    params: Mapping[str, str] | None = None,
    data: Mapping[str, Any] | None = None,
    timeout: float | None = None,
) -> tuple[int, str]:
    """Issue an HTTP request and return ``(status, raw_body_text)``.

    Bypasses ``_handle_response`` translation: returns the raw HTTP
    status and the unparsed body text for every non-transport outcome,
    including HTTP 4xx/5xx and JSON envelopes with ``retcode < 0`` or
    ``message == "unsupported action"``. The probe is the sole intended
    consumer.

    Raises ``AkuvoxConnectionError`` only for transport-level failures
    (connection refused, DNS failure, asyncio ``TimeoutError`` — same
    wrapper as the existing public methods). Authentication
    classification (status 401/403) is the **caller's** responsibility:
    the probe inspects the returned tuple itself and raises
    ``AkuvoxAuthenticationError`` on step 1 when ``status in (401, 403)``.
    """
```

`_request_raw` is private (underscore prefix) — it is NOT part of the
documented public API surface, so the FR-011 introspection audit
(`tasks.md` T038) skips it via its `not name.startswith("_")` filter.
The capability-probe module is a sibling of `_http.py` inside the
`pylocal_akuvox` package, so the underscore-prefix access is
intra-package and intentional.


**Write capabilities** (all `*_ADD` / `*_MODIFY` / `*_DELETE` capabilities — i.e. `USER_ADD`, `USER_MODIFY`, `USER_DELETE`, `CONTACT_ADD`, `CONTACT_MODIFY`, `CONTACT_DELETE`, `SCHEDULE_ADD`, `SCHEDULE_MODIFY`, `SCHEDULE_DELETE`, `GROUP_ADD`, `GROUP_MODIFY`, `GROUP_DELETE`, `DEVICE_CONFIG_SET`, plus the relay-trigger variants `RELAY_TRIGGER_API` / `RELAY_TRIGGER_FCGI`) are **never inferred
by the probe under any circumstance**: a probe that has not actually
exercised the write path cannot safely conclude the path is either
supported or unsupported. **The probe does NOT record write
capabilities in `DeviceCapabilities.capabilities` at all** — they are
**absent** from the mapping. The canonical observation is then
`status_of(write_capability) == CapabilityStatus.UNKNOWN` (per the
"absent → UNKNOWN" default contract on `DeviceCapabilities.status_of`;
see `data-model.md` §"`DeviceCapabilities`"). This "absent" shape (vs
"present-with-UNKNOWN") is the canonical representation: it keeps the
probe-output mapping minimal, it makes the matrix-merge rule's "matrix
UNKNOWN means absent-from-matrix" branch and the probe-`UNKNOWN`
branch behaviourally identical, and it gives `status_of` a single
source-of-truth for "no positive evidence either way". **A read
endpoint returning `"unsupported action"` does NOT propagate to its
write counterpart(s)** — the read capability may be recorded as
`UNSUPPORTED` (or, depending on body shape, `SUPPORTED`) per the
classification table below, and the `unsupported action` body is
preserved verbatim in `DeviceCapabilities.notes` under a per-endpoint
key (e.g. `notes["contact_get_body"]`) for maintainer review, but every
write capability in the same domain (`*_ADD`, `*_MODIFY`, `*_DELETE`)
stays **absent** from `capabilities` (i.e. `status_of(...) == UNKNOWN`).
Only curated matrix entries — populated from hardware-bench observation
of write attempts — promote a write capability to `SUPPORTED` or
`UNSUPPORTED` (or explicitly record `UNKNOWN`). This intentionally
favours fail-fast behaviour on unrecognised devices over a
guessed-positive that would surface as a cryptic device-side error at
call time AND over a guessed-negative that would lock out a write path
that the read-endpoint signal does not actually disqualify (read and
write endpoints are independently routed on observed devices; one's
rejection envelope is not evidence about the other). The earlier,
rejected heuristic (read-success + non-indoor model prefix → write
supported) is **not** used; see the "Alternatives considered" item
below. The earlier, also-rejected heuristic
(read-`unsupported action` → write-`UNSUPPORTED`) is likewise **not**
used; the probe records the read-endpoint signal in `notes` under a
per-endpoint key (e.g. `notes["contact_get_body"]`) and leaves write
status to curated matrix evidence.

## Response classification

Each step's response is classified by the helper
`_classify_response(status, body) -> _ProbeOutcome`. Outcomes map
directly to a `CapabilityStatus` recorded against the step's read
capability marker; if the step has no read marker (e.g. step 1's
`KEY_DISCOVERY` is the device-class probe), the outcome shapes the
notes record only.

| Observed | `_ProbeOutcome` | Recorded `CapabilityStatus` for the read marker |
|----------|-----------------|--------------------------------------------------|
| HTTP 2xx + envelope `retcode: 0` | `SUPPORTED`              | `SUPPORTED`. |
| HTTP 2xx + envelope contains `"No handlers for this request"` | `UNSUPPORTED_NO_HANDLER` | `UNSUPPORTED`. Note recorded under `notes["<endpoint_slug>_body"]` (e.g. `notes["relay_status_body"]`). |
| HTTP 2xx + envelope contains `"No hanlders for this request"` (device typo) | `UNSUPPORTED_NO_HANDLER` | Same as the corrected spelling. <!-- codespell:ignore hanlders --> |
| HTTP 2xx + envelope contains `"unsupported action"` | `UNSUPPORTED_ACTION` | `SUPPORTED` for the read capability (the endpoint exists; the read action was honoured). Note recorded under `notes["<endpoint_slug>_body"]` with the raw body. **The write counterpart remains `UNKNOWN`** — the probe does NOT propagate read-endpoint signals to write capabilities; only a curated matrix entry can promote a write to a non-`UNKNOWN` status (see §"Probe step sequence" Write-capabilities paragraph). |
| HTTP 5xx | `INDETERMINATE` | `UNKNOWN`. Note records the raw status + body under `notes["<endpoint_slug>_body"]` so a maintainer can decide. (Spec edge case "HTTP 500"; X915S `2915.30.10.113`.) |
| HTTP 4xx (other than 401/403) | `INDETERMINATE` | `UNKNOWN`. Note recorded under `notes["<endpoint_slug>_body"]`. |
| HTTP 401 / 403 on step 1 | (raise) | Probe aborts with `AkuvoxAuthenticationError`. |
| HTTP 401 / 403 on later steps | `INDETERMINATE` | `UNKNOWN`; probe continues. (A device that requires fresh auth per endpoint is unusual; the report flags it.) |
| Transport error | (raise) | Probe aborts with `AkuvoxConnectionError`. |

Capabilities the probe did not classify (because the step did not
execute, or because the capability has no associated probe step at all
— every write capability falls into this bucket) are simply absent
from the returned `DeviceCapabilities.capabilities` mapping;
`status_of(capability)` returns `UNKNOWN` for them by default.

The `"No handlers"` typo and the corrected spelling are matched
case-insensitively against `body.get("message", "")`.

## Idempotence

Two consecutive `probe_capabilities()` calls against an unchanged device
MUST return `DeviceCapabilities` instances comparing equal **exactly**.
There is no timestamp inside the probe-derived profile (per §"Provenance
produced by the probe" above — no `notes["probed_at"]`-style key is
written), and probe-derived profiles carry `provenance=None`, so the
test does not need any per-field normalisation. The contract test
asserts:

```python
a = await device.probe_capabilities()
b = await device.probe_capabilities()
assert a == b
```

(SC-002.)

## Non-destructive guarantee

Across the entire probe execution, the request log MUST NOT contain any
of:

- `POST /api/user/set`
- `POST /api/contact/set`
- `POST /api/schedule/set`
- `POST /api/group/set`
- `POST /api/relay/trig`
- `GET /fcgi/do?action=OpenDoor`
- any URL containing `/add`, `/set`, `/del`, or `/trig`

The contract test enforces this by asserting the `aioresponses` request
log against a denylist regex (FR-003, SC-001).

## Edge cases (covered by contract tests)

1. **No-handler typo**: a mocked response with
   `{"retcode": -1, "message": "No handlers for this request"}` for
   `/api/relay/status` results in `RELAY_STATUS` recorded as
   `UNSUPPORTED`, identical behaviour to the corrected spelling.
2. **`unsupported action` on contacts**: a mocked
   `{"retcode": -1, "message": "unsupported action"}` from
   `/api/contact/get` MUST result in `CONTACT_LIST` recorded as
   `SUPPORTED` (the endpoint exists; the read action was honoured)
   and the raw body MUST be recorded under
   `DeviceCapabilities.notes["contact_get_body"] = "<raw body>"`
   verbatim. **`CONTACT_ADD` (and any other write capability) MUST
   remain `UNKNOWN`**: the probe does NOT propagate the
   read-endpoint signal to the write capability. Only a curated
   matrix entry can promote a write capability to `SUPPORTED` or
   `UNSUPPORTED`.
3. **HTTP 500 on `/api/user/get`**: `USER_LIST` recorded as
   `UNKNOWN`; note recorded with the 500 body for maintainer review.
   The probe does not infer write capabilities from a 500 read
   response — `USER_ADD`/`USER_MODIFY`/`USER_DELETE` remain absent
   from `capabilities` (i.e. `UNKNOWN`).
4. **HTTP 401 on step 1**: probe raises `AkuvoxAuthenticationError`; no
   `DeviceCapabilities` is returned.
5. **Transport refused on step 4**: probe raises
   `AkuvoxConnectionError`; no partial `DeviceCapabilities` is returned.
   (Steps 1–3 having succeeded does not produce a partial report;
   capability inference requires the full sequence.)
6. **All steps succeed on an X916**: returned `DeviceCapabilities` has
   `device_class="X916"`, `firmware_version=` the value reported by
   `/api/system/info`, `capabilities` mapping every read capability
   to `SUPPORTED` and every write capability **absent** (i.e.
   `status_of(...)` returns `UNKNOWN`), and
   `field_aliases["schedule_relay"].read` reflecting the order
   `("ScheduleRelay", "Schedule-Relay", "Schedule")` based on which
   names actually appeared in the user-list response.
7. **All steps succeed on an X916 followed by matrix-merged probe**
   (Phase 2 behaviour, listed here for the cross-phase contract): if
   the probe runs against a device that also has a matching matrix
   entry, the **9-cell merge table** below applies. The driving
   principle: **a probe `UNKNOWN` never regresses a matrix-confirmed
   status (no information ≠ negative information); a probe
   `SUPPORTED` or `UNSUPPORTED` is newer first-hand evidence and
   wins over any matrix value**. Capabilities the probe did not
   touch at all are merge-irrelevant — the matrix value carries
   through unchanged.

   | Probe \ Matrix     | `SUPPORTED`               | `UNSUPPORTED`               | `UNKNOWN` (or absent) |
   |--------------------|---------------------------|------------------------------|------------------------|
   | **`SUPPORTED`**    | `SUPPORTED` (probe wins)  | `SUPPORTED` (probe wins; newer evidence) | `SUPPORTED` (probe wins) |
   | **`UNSUPPORTED`**  | `UNSUPPORTED` (probe wins; newer evidence) | `UNSUPPORTED` (probe wins) | `UNSUPPORTED` (probe wins) |
   | **`UNKNOWN`**      | **`SUPPORTED`** (matrix preserved) | **`UNSUPPORTED`** (matrix preserved) | `UNKNOWN` |

   The third row is the safety-critical row: a transient probe
   `UNKNOWN` (e.g. HTTP 500 on a read endpoint that the matrix knows
   to be `SUPPORTED`) MUST NOT degrade the matrix's curated knowledge
   for that connection. Concretely, the merge rule is:
   - **For each capability the probe explicitly classified as
     `SUPPORTED` or `UNSUPPORTED`**, the probe value wins (per FR-009
     "probe results take precedence over matrix defaults" — newer
     first-hand evidence overrides curated defaults).
   - **For each capability the probe classified as `UNKNOWN`**
     (whether explicitly recorded `UNKNOWN` from an indeterminate
     response, or implicitly because the probe did not exercise the
     write path, or because the read endpoint returned HTTP 500), the
     matrix value is **preserved** if non-`UNKNOWN`; otherwise the
     status stays `UNKNOWN`.
   - **For each capability the probe did not touch at all**, the
     pre-probe profile's value carries through unchanged.

   This rule is what makes "explicit probe on a recognised device"
   useful (read-side staleness detection) without accidentally
   degrading write support — or transient-read support — on a
   recognised device. The same table is referenced from
   `contracts/matrix-lookup.md` §"Probe-vs-matrix interaction".
8. **Idempotence across two runs**: two consecutive probes against an
   unchanged device produce `DeviceCapabilities` instances comparing
   **byte-equal** (`assert a == b`). No per-field normalisation is
   required: probe-derived profiles carry `provenance=None` and no
   wall-clock timestamp is written into `notes` (per §"Idempotence" and
   §"Provenance produced by the probe").

## Provenance produced by the probe

A probe-derived `DeviceCapabilities` carries `provenance=None` —
provenance is reserved for *curated matrix entries* (FR-007). The probe
report's "this came from a probe" marker is simply the absent
`provenance` (i.e. `dc.provenance is None`). The Phase 4 doc
consistency test relies on `provenance is None` to recognize "this is
a runtime profile, not a matrix entry".

**No probe-timestamp is written into `notes`.** Earlier drafts wrote a
`"derived from probe at <ISO-8601 timestamp>"` note; that has been
removed because it caused two back-to-back probes to produce
inequal `DeviceCapabilities` (breaking SC-002 idempotence). The
"`provenance is None`" marker is sufficient to distinguish probe-derived
from matrix-derived profiles; no consumer requires the probe to
self-record the wall-clock time. If a maintainer wants the wall-clock
of a probe run for debugging, they can wrap the call:
`t = datetime.now(); dc = await device.probe_capabilities()`.

## Out-of-scope for the probe contract

- Probing the FCGI relay path: never done (the FCGI variant only
  reaches `SUPPORTED` via a curated matrix entry; the probe leaves
  `RELAY_TRIGGER_FCGI` as `UNKNOWN` unless a matrix entry is also
  consulted via the merge rule above).
- Probing write endpoints: never done. Write capabilities only reach
  a non-`UNKNOWN` status via a curated matrix entry (hardware-bench
  observation of write attempts). Read-endpoint signals — including
  the `"unsupported action"` envelope — never propagate to write
  capabilities; the probe records such signals only in
  `DeviceCapabilities.notes` under a per-endpoint key (e.g.
  `notes["contact_get_body"]`).
- Vendor-doc cross-referencing: out of scope per spec dependencies
  line 206 (matrix is grounded in observed behavior).
