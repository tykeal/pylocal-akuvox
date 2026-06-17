<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: OpenDoor HTTP Relay Unlock

**Feature Branch**: `012-open-door-http`
**Created**: 2026-06-17
**Status**: Draft
**Input**: Issue #122 — Add support for Akuvox's officially-documented
HTTP door-unlock command `/fcgi/do?action=OpenDoor`. This is a separate
relay-trigger mechanism from the existing `/api/relay/trig` endpoint and
is the only working unlock path on some device classes (notably the IT83
indoor monitor) where every `/api/relay/*` endpoint returns the
envelope `{"retcode":-1,"action":"unknow","message":"No hanlders for this request"}`. <!-- codespell:ignore hanlders -->
Investigation surfaced in
[tykeal/homeassistant-local-akuvox#130](https://github.com/tykeal/homeassistant-local-akuvox/issues/130);
vendor documentation: [Door Access Control Configuration → Door Unlock
via HTTP Command](https://knowledge.akuvox.com/docs/door-access-control-configuration-7#door-unlock-via-http-command).

## Overview

The library already exposes relay triggering through `/api/relay/trig`
(JSON body, gated by the library's general `AuthConfig`). That endpoint
works on door phones (X-series, R-series) but returns a
"No hanlders for this request" envelope on some device classes whose <!-- codespell:ignore hanlders -->
physical relay is nonetheless functional from the local touchscreen.

Akuvox documents a second, per-device unlock mechanism — "Open Relay Via
HTTP" — reached through `GET /fcgi/do?action=OpenDoor`. It carries a
**dedicated** username/password pair (configured in the device web UI
under **Phone → Relay → Open Relay Via HTTP**) directly in the URL query
string, and it does **not** necessarily return the JSON envelope that
`/api/*` endpoints produce.

This feature adds first-class, **credentialed** support for that
documented endpoint as a **separate, explicitly-chosen** trigger path.
Callers decide which mechanism to use; the library does not auto-detect
device support. Because the credential travels in clear text in the URL,
the feature carries an explicit security contract: credentials MUST be
URL-encoded (never raw-interpolated) and the password MUST be redacted
from any logging.

**This is not a greenfield addition — it corrects and completes an
existing partial implementation.** The codebase already ships a
capability-dispatched FCGI relay variant
(`Capability.RELAY_TRIGGER_FCGI`, the `_fcgi_relay_trigger` adapter in
`capability_adapters.py`, an IT83 entry in `capability_matrix.py`, and
relay-trigger dispatch wiring). That existing adapter issues
`GET /fcgi/do?action=OpenDoor&relay=<num>` via the raw (non-JSON)
request path **without sending any credentials** and using a `relay`
query parameter rather than the vendor-documented `DoorNum`. The vendor
endpoint requires the dedicated `UserName`/`Password` pair, so the
current contract would fail against a correctly-configured device. This
specification therefore defines the **corrected/migrated contract** (add
credentials, align the parameter name to the vendor docs, mandate
encoding and redaction) and the explicit caller-facing entry point from
issue #122, and it gives planning an explicit migration target rather
than treating the work as purely additive. See "Existing Partial
Implementation" below.

The scope of this specification is limited to `action=OpenDoor` on
`/fcgi/do`. Every other `/fcgi/` command (reboot, factory reset, etc.) is
explicitly out of scope.

## Background and Evidence

The two relay-trigger mechanisms differ in every material dimension:

| Aspect | Existing `/api/relay/trig` | New `/fcgi/do?action=OpenDoor` |
|---|---|---|
| Path | `/api/relay/trig` | `/fcgi/do` |
| HTTP method | POST (JSON body) | GET (query string) |
| Auth | Library general auth (basic / digest / allowlist) via `AuthConfig` | Dedicated HTTP-relay username/password passed as URL params |
| Response shape | JSON envelope (`retcode` / `message`) | Not necessarily JSON; status / HTML / plain text uncertain |
| Typical availability | Door phones (X-series, R-series) | Indoor monitors (IT83) and other classes; vendor's documented public unlock path |
| Credential exposure | Auth header / IP allowlist | Clear-text password in URL (visible in proxy / access logs) |

The library's existing HTTP layer already distinguishes a JSON-centric
path (`get` / `post`, which parse and translate the response envelope
through `_handle_response`) from a raw path (`_request_raw`, which returns
the unparsed `(status, body_text)` tuple and lets the caller classify the
outcome). The OpenDoor endpoint aligns with the raw, non-JSON-centric
path because its response shape is not guaranteed to be a JSON envelope.

Both mechanisms must coexist because each works on a disjoint set of
device classes, and callers must be able to choose explicitly.

### Existing Partial Implementation

The current `main` already contains FCGI relay-trigger scaffolding that
this feature must reconcile with the vendor docs rather than duplicate:

| Existing artifact | Location | Current behavior |
|---|---|---|
| `Capability.RELAY_TRIGGER_FCGI` | `_capability_types.py` | Capability member for the FCGI relay variant |
| `_fcgi_relay_trigger` adapter | `capability_adapters.py` | Issues `GET /fcgi/do?action=OpenDoor&relay=<num>` via `_request_raw`; maps 2xx→success, 401→auth error, other 4xx→request error, 5xx→device error; rejects non-zero `mode`/`level`/`delay` |
| Relay-trigger dispatch wiring | `capability_adapters.py` | `RELAY_TRIGGER_ADAPTERS`, `RELAY_TRIGGER_PREFERENCE` (API before FCGI), `CAPABILITY_TO_VARIANT` |
| IT83 matrix entry | `capability_matrix.py` | Marks `RELAY_TRIGGER_FCGI` `SUPPORTED` and `RELAY_TRIGGER_API` `UNSUPPORTED` for the IT83 device class, citing issues #122 / #130 |

The existing adapter's request contract **diverges from the vendor docs
in two material ways**:

1. **No credentials are sent.** The vendor endpoint requires
   `UserName` and `Password` query parameters (the dedicated "Open Relay
   Via HTTP" credential pair). The current adapter sends neither, so it
   would be rejected by a correctly-configured device.
2. **Wrong parameter name.** The current adapter uses `relay=<num>`,
   while the vendor docs specify `DoorNum=<n>`.

The current adapter does, however, already establish two correct
foundations this spec builds on: it uses the raw, non-JSON
`_request_raw` path (FR-004) and an HTTP-status-based success/failure
mapping (FR-008). This specification corrects the credential and
parameter-name gaps, adds the encoding/redaction contract, and defines
the caller-facing entry point. The relationship between the existing
capability-dispatched variant and the new credentialed entry point is a
material design decision captured under "Outstanding Clarifications".

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Unlock a door on a device where the JSON relay API fails (Priority: P1)

An operator has an Akuvox IT83 indoor monitor whose physical relay works
from the touchscreen but rejects every `/api/relay/*` call with
"No hanlders for this request". They have enabled **Open Relay Via HTTP** <!-- codespell:ignore hanlders -->
in the device web UI and set a dedicated username/password. They want to
unlock the door from the library by calling the documented OpenDoor
endpoint with those relay-specific credentials.

**Why this priority**: This is the entire reason the feature exists — it
is the only working programmatic unlock path on the affected device
classes. Without it the relay cannot be triggered at all.

**Independent Test**: Invoke the new OpenDoor method against a mocked HTTP
client and assert that exactly one `GET /fcgi/do` request is issued with
`action=OpenDoor`, the supplied `UserName` / `Password`, and the supplied
`DoorNum`, and that a success response completes without raising.

**Acceptance Scenarios**:

1. **Given** a device with Open Relay Via HTTP enabled and relay
   credentials `user="admin"`, `password="12345"`, **When** the operator
   calls the OpenDoor method with `door_num=1`, **Then** the library
   issues `GET /fcgi/do?action=OpenDoor&UserName=admin&Password=12345&DoorNum=1`
   and returns normally on a success response.
2. **Given** the operator omits `door_num`, **When** they call the
   OpenDoor method, **Then** the library defaults `DoorNum` to `1`.
3. **Given** a caller that holds an `AkuvoxDevice` facade, **When** they
   call the facade's OpenDoor passthrough, **Then** it delegates to the
   same relay helper without requiring a successful capability probe
   first (the call is **not** capability-gated; see FR-006).

---

### User Story 2 — Credentials are encoded and never leaked to logs (Priority: P1)

A security-conscious operator uses relay credentials that contain special
characters (spaces, `&`, `=`, `@`, non-ASCII). They need the request to
be constructed correctly regardless of credential content, and they need
assurance that the clear-text password never appears in the library's
debug logs.

**Why this priority**: The credential travels in the URL by vendor
design. Incorrect encoding would either break the request or, worse,
allow query-string injection; an unredacted password in logs would defeat
the operator's own log hygiene. Both are security-critical and must ship
with the feature, not after it.

**Independent Test**: Call the OpenDoor method with a password such as
`p@ss &word=1` and assert (a) the issued URL/query carries the
percent-encoded form, not the raw characters, and (b) any log record
emitted for the call shows the password replaced by a redaction
placeholder while still showing the rest of the request for
diagnosability.

**Acceptance Scenarios**:

1. **Given** `user="a b"` and `password="p@ss &word=1"`, **When** the
   OpenDoor method is called, **Then** each credential is URL-encoded in
   the query string (e.g. the space becomes `%20`/`+` and `&`/`=`/`@`
   are percent-encoded) and is never interpolated raw.
2. **Given** debug logging is enabled, **When** the OpenDoor request is
   logged, **Then** the `Password` value is replaced by a redaction
   placeholder and the literal password text does not appear anywhere in
   the log output.
3. **Given** debug logging is enabled, **When** the OpenDoor request is
   logged, **Then** the `UserName` and `DoorNum` and `action` remain
   visible so the call is still diagnosable.

---

### User Story 3 — Choose the correct mechanism with clear guidance (Priority: P2)

A developer integrating the library is unsure whether to call
`trigger_relay` (the `/api/relay/trig` path) or the new OpenDoor method.
They need documentation that explains when each applies and what
prerequisites and trade-offs each carries.

**Why this priority**: Two overlapping unlock mechanisms invite
misuse. Clear guidance prevents callers from defaulting to the wrong path
and then filing "relay does not work" reports. It is important but
secondary to the unlock capability itself.

**Independent Test**: Confirm the published documentation contains a
section that contrasts `/fcgi/do?action=OpenDoor` with `/api/relay/trig`,
states the device-side prerequisite (Open Relay Via HTTP enabled with
credentials configured), and states the clear-text-URL security
trade-off.

**Acceptance Scenarios**:

1. **Given** the project documentation, **When** a developer reads the
   relay section, **Then** it describes when to use
   `/fcgi/do?action=OpenDoor` versus `/api/relay/trig`.
2. **Given** the OpenDoor method's docstring, **When** a developer reads
   it, **Then** it states that the password is sent in clear text in the
   URL (visible in proxy / access logs) and that the device must have
   Open Relay Via HTTP enabled with a configured credential pair.

---

### User Story 4 — Optionally exercise OpenDoor from the MVP test script (Priority: P3)

A maintainer validating against real hardware wants the
`examples/mvp_test.py --write` smoke run to optionally fire the OpenDoor
endpoint, but only when they explicitly opt in and supply the relay
credentials, since those credentials are not part of the standard
`AuthConfig`.

**Why this priority**: This is a convenience for real-device validation.
It is valuable for the maintainer but not required for the library
capability to function.

**Independent Test**: Run `examples/mvp_test.py --write` without the
OpenDoor opt-in flag/credentials and confirm OpenDoor is skipped; run it
with the opt-in flag and credentials and confirm the OpenDoor call is
attempted exactly once.

**Acceptance Scenarios**:

1. **Given** `examples/mvp_test.py --write` is run without the OpenDoor
   opt-in flag, **When** the write tests run, **Then** the OpenDoor call
   is skipped and the absence is reported, not treated as a failure.
2. **Given** `examples/mvp_test.py --write` is run with the OpenDoor
   opt-in flag and relay credentials supplied, **When** the write tests
   run, **Then** the OpenDoor endpoint is exercised exactly once.

---

### Edge Cases

- **Special characters in credentials**: handled by mandatory
  URL-encoding (FR-002). A `&` or `=` in the password must not split or
  inject additional query parameters.
- **Invalid `door_num`**: a non-positive or non-integer `door_num` MUST be
  rejected with a validation error before any network request is issued,
  consistent with `trigger_relay`'s relay-number validation.
- **HTTP authentication failure (401 / 403)**: the dedicated relay
  credentials are wrong or Open Relay Via HTTP is disabled — the library
  MUST surface this as a recognizable failure rather than silently
  succeeding (see FR-004 and the clarification on response classification).
- **Non-JSON failure body**: the device may return HTML or plain text on
  error. The library MUST NOT assume a JSON envelope and MUST NOT raise a
  JSON-parse error as the user-visible outcome.
- **Server error (HTTP 500)**: treated as a failure outcome surfaced to
  the caller.
- **Transport failure** (connection refused, DNS failure, timeout):
  surfaced through the library's existing connection-error contract,
  identical to other endpoints.
- **Empty / whitespace credentials**: passing an empty username or
  password is the caller's responsibility; the library still encodes
  whatever it is given and does not invent a default credential.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 — Expose the documented OpenDoor endpoint**: The library MUST
  provide a relay helper and an `AkuvoxDevice` passthrough that issue
  `GET /fcgi/do` with `action=OpenDoor`, the caller-supplied `UserName`
  and `Password`, and `DoorNum`. The proposed names are a free function
  `open_door_http(http, *, user, password, door_num=1)` in `relay.py` and
  a thin `AkuvoxDevice.open_door_http(...)` passthrough; final names are
  confirmed during planning but the observable request contract above is
  fixed. This entry point supersedes the credential-less request issued by
  the existing `_fcgi_relay_trigger` adapter (see "Existing Partial
  Implementation" and FR-014/FR-015).

- **FR-002 — URL-encode credentials**: `UserName`, `Password`, and
  `DoorNum` MUST be URL-encoded as query parameters. Credentials MUST NOT
  be interpolated raw into the URL string. Special characters
  (`&`, `=`, `@`, space, non-ASCII) MUST be safely encoded so they cannot
  alter the query structure.

- **FR-003 — Redact the password from logs**: Any log output (debug or
  otherwise) that includes the request URL or parameters MUST replace the
  `Password` value with a redaction placeholder. The literal password
  MUST NOT appear in any log record. `UserName`, `DoorNum`, and `action`
  MAY remain visible for diagnosability.

- **FR-004 — Non-JSON response handling**: The OpenDoor path MUST NOT
  assume a JSON envelope and MUST NOT route through the JSON-centric
  response parser used by `/api/*` calls. It MUST use a raw / non-JSON
  response path and classify success versus failure without depending on
  a parseable JSON body. A non-JSON failure body MUST NOT surface as a
  JSON-parse error.

- **FR-005 — Validate `door_num` before any request**: A non-positive or
  non-integer `door_num` MUST raise the library's validation error
  (`AkuvoxValidationError`) before issuing a network request, mirroring
  the existing relay-number validation. Booleans MUST be rejected as
  non-integers (consistent with existing relay validation).

- **FR-006 — Not capability-gated**: The OpenDoor method MUST be callable
  as an explicit caller choice and MUST NOT require a successful
  capability probe or capability profile to be invoked. The library does
  not auto-detect whether a device class supports this mechanism.

- **FR-007 — Credentials separate from `AuthConfig`**: The OpenDoor
  credentials MUST be supplied per call (relay-specific user/password) and
  MUST NOT reuse or require the device's general HTTP `AuthConfig`
  (basic / digest / allowlist). The two credential sets are independent.

- **FR-008 — Failure is surfaced, success is silent**: On a success
  outcome the method returns normally (no value). On a failure outcome
  (including authentication failure and server error) the method MUST
  raise a library exception that names the failure cause; it MUST NOT
  silently return as if the door opened.

- **FR-009 — Security and prerequisite documented in the docstring**: The
  method's docstring MUST state (a) the clear-text-URL credential
  trade-off (password visible in proxy / device access logs, per vendor
  design) and (b) the device-side prerequisite that **Phone → Relay →
  Open Relay Via HTTP** is enabled with a configured username/password.

- **FR-010 — User-facing documentation contrasts the two mechanisms**:
  The published documentation MUST include guidance on when to use
  `/fcgi/do?action=OpenDoor` versus `/api/relay/trig`, including the
  prerequisite and the security trade-off.

- **FR-011 — Unit test coverage**: Unit tests MUST cover, at minimum:
  (a) URL/path/parameter construction (`action=OpenDoor`, `UserName`,
  `Password`, `DoorNum`); (b) URL-encoding of special characters in
  credentials; (c) password redaction in logging; (d) at least one
  success response shape; and (e) at least one failure response shape.
  Coverage MUST be maintained at the project's required level.

- **FR-012 — MVP script opt-in**: `examples/mvp_test.py` `--write` mode
  MUST optionally exercise the OpenDoor endpoint, gated behind an explicit
  opt-in flag and the relay-specific credentials. When the flag or
  credentials are absent, OpenDoor MUST be skipped (reported, not failed).

- **FR-013 — Scope boundary enforced**: The implementation MUST add only
  `action=OpenDoor` support on `/fcgi/do`. It MUST NOT add other `/fcgi/`
  commands and MUST NOT add device-class auto-detection of trigger
  mechanisms.

- **FR-014 — Correct the query parameter name to the vendor docs**: The
  request MUST use the vendor-documented `DoorNum=<n>` query parameter,
  not the `relay=<num>` parameter used by the current
  `_fcgi_relay_trigger` adapter. The corrected parameter name MUST be
  applied wherever the FCGI OpenDoor request is constructed so the
  library and the device agree on the relay identifier.

- **FR-015 — Reconcile credentials with the existing FCGI dispatch path**:
  The existing capability-dispatched FCGI variant (`_fcgi_relay_trigger`,
  reached through `trigger_relay` for `RELAY_TRIGGER_FCGI` devices) MUST
  NOT continue issuing a credential-less `/fcgi/do` request that a
  correctly-configured device would reject. The implementation MUST ensure
  every code path that issues `action=OpenDoor` either supplies the
  required `UserName`/`Password` (per FR-002/FR-003) or is updated/retired
  per the design decision in "Outstanding Clarifications". No code path may
  ship that sends the OpenDoor request without credentials once this
  feature lands.

### Key Entities *(include if feature involves data)*

- **OpenDoor request**: The outbound `GET /fcgi/do` call. Attributes:
  fixed `action=OpenDoor`, `UserName` (relay credential), `Password`
  (relay credential, clear-text in URL, redacted in logs), `DoorNum`
  (positive integer, default 1).
- **HTTP-relay credential pair**: The dedicated username/password
  configured in the device web UI under **Phone → Relay → Open Relay Via
  HTTP**. Independent of the library's `AuthConfig`. Supplied by the
  caller per OpenDoor invocation.
- **OpenDoor outcome**: Success (method returns, no value) or failure
  (library exception naming the cause: validation, authentication,
  server, or transport).

## Security Considerations *(mandatory)*

- **Clear-text credential in URL (by vendor design)**: The relay password
  is transmitted as a URL query parameter and will appear in plaintext on
  the wire (for non-TLS deployments) and in any intermediary that logs
  request lines — proxies, the device's own access log, etc. This is the
  documented Akuvox design and cannot be avoided while using this
  endpoint. The library MUST surface this trade-off prominently in the
  docstring (FR-009) and user documentation (FR-010) so callers make an
  informed choice.
- **Mandatory log redaction**: Because the credential is in the URL, the
  library's own logging is the one leak vector it fully controls. The
  password MUST be redacted everywhere the library logs the request
  (FR-003). Redaction must not depend on log level being low.
- **Encoding as an injection guard**: URL-encoding (FR-002) is both a
  correctness and a safety control — it prevents a credential containing
  `&` or `=` from injecting or overriding query parameters.
- **No credential persistence**: The relay credentials are passed per
  call and MUST NOT be stored, cached, or written to any diagnostics
  output by the library.
- **No weakening of existing auth**: This feature introduces an
  independent credential path and MUST NOT alter, relax, or bypass the
  existing `AuthConfig` behavior for `/api/*` endpoints (FR-007).

## Out of Scope *(mandatory)*

- **Other `/fcgi/` commands**: reboot, factory reset, and every other
  vendor command on the `/fcgi/` path family. Only `action=OpenDoor` is
  in scope.
- **The IT83's broader API gaps**: the fact that other `/api/*` endpoints
  are unsupported on that device class is a separate device-capability
  story and is not addressed here.
- **Auto-detection of trigger mechanism**: the library will not probe or
  guess which of `/api/relay/trig` or `/fcgi/do?action=OpenDoor` a given
  device class supports. Mechanism choice is the caller's responsibility.
  (The existing static IT83 capability-matrix entry is retained as-is;
  this exclusion is about runtime auto-detection, not the existing static
  matrix data.)
- **New capability-probe steps or new matrix device classes**: this
  feature does not add a probe step for OpenDoor and does not add matrix
  entries for additional device classes. It MAY correct the request
  contract used by the already-present `RELAY_TRIGGER_FCGI` adapter and
  IT83 matrix entry (per FR-014/FR-015 and the clarification below), but
  it does not extend the probe/matrix surface beyond what already ships.
- **TLS enforcement or transport hardening**: the feature does not change
  the library's transport/TLS posture; it documents the clear-text
  trade-off rather than mitigating it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can trigger an unlock on a device that rejects
  all `/api/relay/*` calls, using a single OpenDoor method call with the
  relay-specific credentials, with no prior capability probe required.
- **SC-002**: For any credential containing special characters
  (`&`, `=`, `@`, space, non-ASCII), the issued request preserves the
  intended `action`, `UserName`, `Password`, and `DoorNum` parameters
  with zero query-structure corruption — verified across the encoding
  test cases.
- **SC-003**: The clear-text password appears zero times in the library's
  log output across all tested success and failure paths.
- **SC-004**: An invalid `door_num` produces a validation error with zero
  network requests issued.
- **SC-005**: A failure response (authentication, server error, or
  non-JSON error body) results in a raised library exception in 100% of
  tested failure shapes, and never a silent success or a raw
  JSON-parse error.
- **SC-006**: A developer reading the documentation can correctly state,
  for a given device class and configuration, which of the two unlock
  mechanisms to use and what the security trade-off is.

## Assumptions

- The success-vs-failure signal is determined primarily from the HTTP
  status code, because the OpenDoor response body shape is not guaranteed
  to be JSON and has not yet been probed on real hardware. A 2xx status is
  treated as success and a non-2xx status as failure unless the
  clarification below establishes a body-content requirement.
- The default `DoorNum` is `1`, matching the vendor example and the
  single-relay common case.
- The library's existing raw, non-JSON request path (returning an
  unparsed status/body) is the appropriate foundation for FR-004; no new
  transport behavior (TLS, retries, throttling) is introduced.
- The OpenDoor method returns no value on success, consistent with
  `trigger_relay`.
- Redaction reuses the library's existing credential-redaction
  conventions rather than introducing a new redaction scheme.

## Outstanding Clarifications

- **[NEEDS CLARIFICATION: success/failure classification from the real
  device response]** — The OpenDoor response shape on real hardware
  (whether success is signaled purely by HTTP 2xx, or whether the body
  carries a meaningful marker such as a status keyword in HTML/plain
  text) has not been probed. The Assumptions section adopts an
  HTTP-status-based default (2xx = success, non-2xx = failure). If a real
  IT83 returns HTTP 200 with an error indication in the body, the
  classification rule in FR-004/FR-008 must be tightened to inspect that
  body marker. This must be confirmed against real hardware (or the
  vendor's expected responses) during planning/implementation. It does
  not block authoring the spec because the default behavior is well
  defined and the failure-shape tests (FR-011) can pin whichever rule is
  adopted.

- **[NEEDS CLARIFICATION: relationship between the new credentialed entry
  point and the existing capability-dispatched FCGI adapter]** — The
  codebase already dispatches `RELAY_TRIGGER_FCGI` through
  `trigger_relay` via the credential-less `_fcgi_relay_trigger` adapter.
  Issue #122 proposes a dedicated, non-capability-gated `open_door_http`
  method that takes per-call credentials. Planning must decide which of
  the following the implementation adopts (all satisfy FR-014/FR-015): (a)
  retire the credential-less adapter and route FCGI unlocks exclusively
  through the new credentialed method; (b) keep the capability dispatch
  but thread the relay credentials into the adapter (e.g. via a
  credential carrier on the trigger call); or (c) keep both — the
  capability adapter for credential-less/legacy devices and the explicit
  method for credentialed devices. The non-negotiable constraint is
  FR-015: no shipped path may issue the OpenDoor request without
  credentials against a device that requires them. This is flagged
  because the choice materially affects the public API surface and the
  capability-dispatch behavior; it does not block the spec because every
  option preserves the corrected request contract (FR-002, FR-003,
  FR-014) and the security requirements.

## Dependencies

- The device under control must have **Phone → Relay → Open Relay Via
  HTTP** enabled with a configured username/password (device-side
  prerequisite; outside the library's control).
- The library's existing HTTP client and validation/exception types
  (`AkuvoxValidationError`, the connection-error contract, and the raw
  non-JSON request path).
- The existing FCGI relay scaffolding that this feature corrects:
  `Capability.RELAY_TRIGGER_FCGI` (`_capability_types.py`), the
  `_fcgi_relay_trigger` adapter and dispatch registries
  (`capability_adapters.py`), and the IT83 matrix entry
  (`capability_matrix.py`).

## References

- Vendor documentation: Door Access Control Configuration → Door Unlock
  via HTTP Command —
  <https://knowledge.akuvox.com/docs/door-access-control-configuration-7#door-unlock-via-http-command>
- Triggering investigation: tykeal/homeassistant-local-akuvox#130 —
  <https://github.com/tykeal/homeassistant-local-akuvox/issues/130>
- Tracking issue: tykeal/pylocal-akuvox#122
