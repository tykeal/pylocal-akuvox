<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Research: OpenDoor HTTP Relay Unlock

**Feature**: `012-open-door-http` | **Date**: 2026-06-17
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This document records the design decisions taken during planning, the
rationale, and the alternatives considered. All claims about existing code
were verified against the live `main` source (see "Source verification").

## Decision 1 — Success/failure classification (resolves Clarification 1)

**Decision**: Classify the OpenDoor outcome on **HTTP status** using the
existing raw request path `AkuvoxHttpClient._request_raw`, reusing the
exact status→exception mapping already established by
`_fcgi_relay_trigger`:

| Status | Outcome |
|--------|---------|
| `2xx` | success — `open_door_http` returns `None` |
| `401` | `AkuvoxAuthenticationError` |
| `403` + any other `4xx` | `AkuvoxRequestError` |
| `5xx` + any other non-`2xx` | `AkuvoxDeviceError` |
| transport (refused/DNS/timeout) | `AkuvoxConnectionError` (raised in `_request_raw`) |

**Rationale**:

- The OpenDoor endpoint is **not guaranteed** to return a JSON envelope —
  the IT83 FCGI handler returns text/plain or text/html on success, and the
  envelope parser would raise `AkuvoxParseError` on a successful unlock
  (FR-004). The raw path returns `(status, body_text)` unparsed.
- Reusing the `_fcgi_relay_trigger` mapping means integrators catch a
  single `Akuvox*` error family regardless of which path fired.
- The response body shape on real hardware has not been probed (spec
  Assumptions), so HTTP `2xx` is the only reliable success signal available
  today.

**Forward-compatibility**: classification is isolated in a single helper so
that, if a real IT83 is later found to return `HTTP 200` with an error
marker in the body, the rule can be tightened to inspect that marker
**without** touching request construction or redaction. The failure-shape
unit tests (FR-011) pin whichever rule is adopted.

**Alternatives considered**:

- *Body-content classification now* — rejected: no probed evidence of a
  body marker exists; designing around an unknown body shape would be
  speculative and would risk misclassifying a successful unlock as a
  failure.
- *Route through the JSON envelope path (`get`)* — rejected outright by
  FR-004: a non-JSON success body would raise `AkuvoxParseError`.

## Decision 2 — Existing adapter relationship (resolves Clarification 2)

**Decision**: **Option (a)** — retire the credential-less request from the
capability-dispatch path and route all real OpenDoor unlocks exclusively
through the new credentialed, non-capability-gated `open_door_http`.

**Implementation nuance**: convert `_fcgi_relay_trigger` from "issue a
credential-less `GET /fcgi/do?action=OpenDoor&relay=<num>`" into an
**actionable guard** that raises (e.g. `AkuvoxUnsupportedError`) directing
the caller to `AkuvoxDevice.open_door_http(...)`. Retain the
`RELAY_TRIGGER_FCGI` capability member, the dispatch registries
(`RELAY_TRIGGER_ADAPTERS`, `RELAY_TRIGGER_PREFERENCE`,
`CAPABILITY_TO_VARIANT`), and the IT83 matrix entry — all "as-is" per the
spec's Out-of-Scope retention note.

**Rationale**:

- FR-006 requires a method callable **without** a capability probe;
  FR-007 requires per-call credentials independent of `AuthConfig`. A clean
  standalone helper satisfies both.
- FR-015 forbids shipping any credential-less OpenDoor request. The guard
  issues **no** request, so it cannot violate FR-015.
- The current adapter never worked against a correctly configured device
  (no credentials, wrong `relay=` param), so there is no working behaviour
  being removed — only a broken, spec-violating path.
- Keeping the capability member + matrix entry as informational preserves
  the spec's "retain the static matrix as-is" instruction and avoids
  extending the probe/matrix surface (Out of Scope).

**Alternatives considered**:

- **(b) thread credentials through `trigger_relay` dispatch** — rejected:
  overloads the capability-gated `trigger_relay` signature with FCGI-only
  per-call relay credentials, and the call remains **capability-gated**,
  contradicting FR-006. It also blurs FR-007's "credentials independent of
  `AuthConfig`" boundary by mixing relay credentials into the
  capability-dispatch flow.
- **(c) keep both, credential-less adapter retained** — rejected:
  forbidden by FR-015; a credential-less OpenDoor request cannot ship.
- **(a) with full registry removal** (delete the FCGI registry entries and
  drop `RELAY_TRIGGER_FCGI` from `RELAY_TRIGGER_PREFERENCE` /
  `CAPABILITY_TO_VARIANT`) — viable and FR-compliant, but rejected as the
  primary path because it deletes the matrix-referenced capability the spec
  says to **retain as-is** and causes more churn (the IT83 matrix entry and
  `_capability_types` member would have to change). The guard approach is
  the minimal change that still guarantees FR-015.

**Consequence (documented as a `Changed` changelog entry)**:
`trigger_relay(num=1)` on an IT83 changes from "issue a broken,
credential-less request" to "raise an actionable error pointing at
`open_door_http`". This is a behaviour change to a non-functional path, not
a public-signature break.

## Decision 3 — URL construction & single-encoder rule (FR-002)

**Decision**: Build an ordered parameter mapping
(`action=OpenDoor`, `UserName`, `Password`, `DoorNum`) from **raw**
credential values and hand it to a **single** URL encoder. The recommended
mechanism is the `params=` argument already accepted by `_request_raw`
(aiohttp/yarl encodes each value once). Credentials are never
string-interpolated into the path.

**Rationale**:

- A single encoding pass prevents both under-encoding (a `&`/`=` in the
  password splitting/injecting query parameters — a security control per
  the spec) and double-encoding (a `%` in a credential becoming `%25`).
- The existing `_fcgi_relay_trigger` builds the query inline in the path
  string (`/fcgi/do?action=OpenDoor&relay={num}`). That is safe only for
  plain integers; for arbitrary credentials it would re-encode unsafely.
  Moving to `params=` reuses the library's established encoder.

**Alternatives considered**:

- *`urllib.parse.urlencode({...}, quote_via=urllib.parse.quote)` then pass
  the pre-built query in the path* — viable and fully under the library's
  control, but risks double-encoding when handed back to aiohttp/yarl;
  acceptable only if the encoded query is passed in a way that bypasses
  re-encoding. Kept as the fallback if `params=` ordering/encoding proves
  unsuitable during implementation.
- *Manual f-string interpolation* — rejected outright by FR-002 (no raw
  interpolation).

## Decision 4 — Redaction & logging (FR-003)

**Decision**: Add a module-level `logging.getLogger(__name__)` to
`relay.py` and emit at most a **DEBUG** record built by a dedicated
`_redacted_open_door_query(...)` helper that renders the query with the
`Password` value replaced by a `<redacted>` placeholder while keeping
`action`, `UserName`, and `DoorNum` visible. The raw password is never
passed to a log call nor embedded in any exception message.

**Rationale**:

- `src/pylocal_akuvox/` currently emits **no** logs (verified — no
  `logging` import or `getLogger` call anywhere in `src/`), so there is no
  pre-existing request-logging leak. FR-003 still mandates that *any* log
  the library emits redact the password, so the redaction is built in from
  the start.
- The placeholder string `<redacted>` matches the existing
  `examples/mvp_test.py` convention (`_REDACTED_VALUE = "<redacted>"`),
  satisfying the spec's "reuse existing redaction conventions" assumption
  rather than inventing a new scheme.
- Redaction is unconditional (not gated on log level), per the Security
  Considerations section.

**Alternatives considered**:

- *No logging at all* — would technically satisfy FR-003 vacuously, but a
  redacted DEBUG line aids diagnosability (the spec explicitly wants
  `action`/`UserName`/`DoorNum` to remain visible) without leaking the
  secret.
- *A library-wide redaction filter* — out of scope; introduces a new
  redaction scheme the spec asked to avoid.

## Decision 5 — Validation (FR-005)

**Decision**: Add `_validate_door_num(door_num)` mirroring the existing
`_validate_relay_trigger_args` `num` check: raise `AkuvoxValidationError`
for a non-positive value, a non-integer, or a `bool` (an `int` subclass),
**before** any network request.

**Rationale**: consistency with `trigger_relay`'s relay-number validation
(the spec explicitly requires the same `bool`-rejection behaviour) and a
guarantee of zero network requests on invalid input (SC-004).

## Decision 6 — Public surface & naming (FR-001)

**Decision**: Free function `open_door_http(http, *, user, password,
door_num=1) -> None` in `relay.py`; thin
`AkuvoxDevice.open_door_http(*, user, password, door_num=1) -> None`
passthrough that calls the free function directly (no `_context()`,
no capability `require`). The free function is **not** added to top-level
`pylocal_akuvox.__all__` — consistent with `trigger_relay`, which is also
reached via `pylocal_akuvox.relay` rather than the package root.

**Rationale**: matches the established relay API layout
(`relay.trigger_relay` + `AkuvoxDevice.trigger_relay`) and keeps the
passthrough non-gated per FR-006.

## Decision 7 — Artifact scope

**Decision**: Produce `research.md`, `contracts/open-door-http.md`, and
`quickstart.md`; **omit** a standalone `data-model.md`.

**Rationale**: the feature adds no domain entity or persistence. The spec's
three "Key Entities" are fully captured by the request/response/error
contract; a separate data model would be redundant. This matches the
plan-stage guidance to avoid over-producing artifacts for a small helper.

## Source verification

Verified against live `main` source in the worktree at planning time:

- `src/pylocal_akuvox/relay.py` — `trigger_relay`,
  `_validate_relay_trigger_args` (the `bool`/range validation pattern
  reused for `door_num`), `get_relay_status`.
- `src/pylocal_akuvox/_http.py` — `_request_raw` returns
  `(status, body_text)`, acquires `self._lock`, honours
  `_post_request_delay`, accepts `params=`/`data=`, wraps transport errors
  as `AkuvoxConnectionError`; `_handle_response` status mapping;
  **no logging anywhere in `src/`**.
- `src/pylocal_akuvox/capability_adapters.py` — `_fcgi_relay_trigger`
  issues `GET /fcgi/do?action=OpenDoor&relay={num}` via `_request_raw`,
  no credentials, status mapping 2xx/401/4xx/5xx; `RelayTriggerArgs`;
  `RELAY_TRIGGER_ADAPTERS`, `RELAY_TRIGGER_PREFERENCE`,
  `CAPABILITY_TO_VARIANT`.
- `src/pylocal_akuvox/_device_relays.py` — `trigger_relay`,
  `resolve_default_adapter`, `resolve_override_adapter` dispatch flow.
- `src/pylocal_akuvox/device.py` — `AkuvoxDevice.trigger_relay`
  passthrough (the model for `open_door_http`).
- `src/pylocal_akuvox/_capability_types.py` — `Capability.RELAY_TRIGGER_API`
  / `RELAY_TRIGGER_FCGI` members.
- `src/pylocal_akuvox/capability_matrix.py` — `_IT83_83_30_10_4` entry
  (`RELAY_TRIGGER_API = UNSUPPORTED`, `RELAY_TRIGGER_FCGI = SUPPORTED`).
- `src/pylocal_akuvox/exceptions.py` — `AkuvoxAuthenticationError`,
  `AkuvoxRequestError`, `AkuvoxDeviceError`, `AkuvoxConnectionError`,
  `AkuvoxParseError`, `AkuvoxUnsupportedError`, `AkuvoxValidationError`.
- `tests/unit/test_dispatch.py` — existing assertions pinning the IT83
  FCGI route to `/fcgi/do?action=OpenDoor&relay=1` (to be updated in
  Phase 4).
- `examples/mvp_test.py` — `argparse` flags, `--write` gating around
  `_run_write_tests`, `_REDACTED_VALUE = "<redacted>"`,
  `test_trigger_relay`.
