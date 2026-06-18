<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: Apartment-Book Contact Schema Support (X915S)

**Feature Branch**: `013-apartment-book-contacts`
**Created**: 2026-06-18
**Status**: Draft
**Input**: Issue #121 — Akuvox **X915S** door phones (firmware
`2915.30.10.114`) expose a fundamentally different `/api/contact/*` schema
from door phones like the X916. The X915S uses an **apartment-book /
building model** rather than the simple contact model the library is built
around. Reads succeed but the parsed data loses information; contact writes
are not supported by the firmware via the public HTTP API at all. This is a
**device-class capability difference**, not a firmware quirk to paper over
with field aliases.

## Overview

The library models a `Contact` as a flat record with `name`, `id`, `phone`,
and `group`. That shape matches **door-phone** devices (X916, E18C) whose
`/api/contact/get` records carry an `ID` and a `Group`. The X915S — an
apartment intercom — instead returns an **apartment-book** record that has
**no `ID`** and **no `Group`**, and adds apartment/building fields the
library does not model: `APTName`, `APTNum`, `Building`, `Landline`.

Two distinct problems follow from this device-class difference:

1. **Read fidelity.** `list_contacts()` succeeds on the X915S (it returns
   the expected number of entries), but every returned `Contact` has
   `id=None` and the apartment-book metadata (`APTName`, `APTNum`,
   `Building`, `Landline`) is **silently discarded**. On apartment devices
   that metadata may be the only meaningful way to tell two records apart,
   so dropping it loses real information.

2. **Write capability signalling.** The X915S firmware does not support
   contact mutation over the public HTTP API at all: `POST
   /api/contact/add` and `/api/contact/set` return
   `{"retcode":-1,"action":"unknow","message":"unsupport action"}`, and
   every probed alternate endpoint (`/api/aptbook/*`, `/api/apartment/get`,
   `/api/phonebook/get`, `/api/building/get`, `/api/resident/get`,
   `/api/dial/get`) returns "No handlers for this request". A caller who
   attempts a contact write therefore deserves a **clear,
   capability-not-supported signal** — not a cryptic device error, a
   bare `NotImplementedError`, or a raw "unsupport action" string.

This feature makes apartment-book contact **reads** preserve the apartment
metadata, defines how a record is identified when there is no `ID`, and
guarantees that contact **writes** on a read-only device class surface a
single, actionable "this device class does not support contact mutation"
error. Door-phone devices keep their current behaviour byte-for-byte (the
new contact fields default to absent / `None`).

**This is not a greenfield addition — it completes existing partial
support.** The codebase already carries a capability framework that knows
about this device-class split; see "Existing Implementation" below. The
work here is **additive and reconciling**: surface fields the parser
already tolerates-but-discards, make the unsupported-write signal uniform
across all three mutating operations, and document the model. It MUST NOT
contradict the existing static capability matrix.

## Background and Evidence

### Schema comparison

| Field | X916 / door phone | X915S apartment-book |
|---|---|---|
| `ID` | present | **absent** |
| `Name` | present | present |
| `Phone` | present | present |
| `Group` | present | **absent** |
| `APTName` | absent | present |
| `APTNum` | absent | present |
| `Building` | absent | present |
| `Landline` | absent | present |

A representative X915S `GET /api/contact/get` record:

```json
{
  "APTName":  "1",
  "APTNum":   "1",
  "Building": "",
  "Landline": "",
  "Name":     "01_monitor",
  "Phone":    "192.168.0.10"
}
```

### Write evidence (X915S, firmware 2915.30.10.114)

```text
POST /api/contact/add   → {"retcode":-1,"action":"unknow","message":"unsupport action"}
POST /api/contact/set   → {"retcode":-1,"action":"unknow","message":"unsupport action"}
GET  /api/aptbook/get    → No handlers for this request
GET  /api/apartment/get  → No handlers for this request
GET  /api/phonebook/get  → No handlers for this request
GET  /api/building/get   → No handlers for this request
GET  /api/resident/get   → No handlers for this request
GET  /api/dial/get       → No handlers for this request
POST /api/aptbook/add    → No handlers for this request
```

On the X915S, contacts are therefore **read-only via the HTTP API**.
Management presumably happens through the device web UI, provisioning, or a
non-HTTP-API channel — all out of scope here.

### Existing Implementation (reconciliation targets)

The current `main` already contains capability scaffolding that recognises
this device-class split. This spec reconciles with it rather than
duplicating or contradicting it:

| Existing artifact | Location | Current behaviour |
|---|---|---|
| `SchemaShape` enum (`DOOR_PHONE`, `APARTMENT_BOOK`) | `_capability_types.py` | Two contact-schema variants already defined |
| X915S matrix entry | `capability_matrix.py` | `schema_shapes={"contact": APARTMENT_BOOK}`; `CONTACT_LIST` `SUPPORTED`; `CONTACT_ADD` `UNSUPPORTED`; `CONTACT_MODIFY` / `CONTACT_DELETE` **absent → UNKNOWN** |
| `Contact` model | `models/contacts.py` | Flat `name` / `id` / `phone` / `group`; **no apartment-book fields** |
| `Contact.from_api_response` | `models/contacts.py` | Apartment-book branch tolerates a missing `ID` and the extra `APTName` / `APTNum` / `Building` / `Landline` keys, but currently **discards** them — the two branches are byte-identical today |
| `add_contact` / `modify_contact` (service) | `contacts.py` | Raise `NotImplementedError` (a write-deferral message) when the shape is `APARTMENT_BOOK`; `delete_contact` is shape-agnostic |
| Capability gate `DeviceCapabilities.require()` | `_capability_profile.py` | `UNSUPPORTED` → `AkuvoxUnsupportedError(reason="capability_missing")`; `UNKNOWN` (default) → `AkuvoxUnsupportedError(reason="capability_unknown")` unless the caller opts in via `attempt_unknown_capability=True` |
| HTTP envelope classifier | `_http.py` | Translates only the literal `"Api unsupported"` message to `AkuvoxUnsupportedError`; the X915S `"unsupport action"` message does **not** match, so it currently falls through to `AkuvoxDeviceError` |
| `AkuvoxUnsupportedError` | `exceptions.py` | Carries structured `capability`, `device_class`, `reason` (closed set includes `capability_missing`, `capability_unknown`, `envelope_unsupported`) |
| `AkuvoxDevice.capabilities` property | `device.py` | Exposes the effective `DeviceCapabilities` (callers can already call `status_of(...)` / read `supported_set`) |

Two concrete gaps follow from this table and drive the requirements below:

1. The apartment-book parse path already **accepts** the extra keys but the
   public `Contact` model has nowhere to put them, so they are dropped.
2. The unsupported-write signal is **inconsistent across the three mutating
   operations**: `CONTACT_ADD` is statically `UNSUPPORTED`
   (`capability_missing`), but `CONTACT_MODIFY` / `CONTACT_DELETE` are
   `UNKNOWN` (`capability_unknown`), and a caller who opts in with
   `attempt_unknown_capability=True` (or who reaches the network directly)
   would receive `AkuvoxDeviceError("unsupport action")` from the envelope
   classifier rather than a recognisable capability error.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Read apartment-book contacts without losing apartment metadata (Priority: P1)

An integrator connects to an X915S apartment intercom and lists its
contacts. They need each returned record to preserve the apartment-book
fields (`APTName`, `APTNum`, `Building`, `Landline`) so they can display or
correlate apartment/building information, instead of receiving records that
silently drop everything except name and phone.

**Why this priority**: This is the core data-fidelity fix. Without it the
library actively loses information that, on apartment devices, may be the
only way to distinguish records. Reads already work; the value is in not
throwing the metadata away.

**Independent Test**: Parse a known apartment-book payload (with `APTName`,
`APTNum`, `Building`, `Landline`, `Name`, `Phone`, and no `ID`) under the
apartment-book schema shape and assert the resulting record exposes all
four apartment-book fields with their source values and does not raise.

**Acceptance Scenarios**:

1. **Given** an X915S contact record
   `{"APTName":"1","APTNum":"1","Building":"","Landline":"","Name":"01_monitor","Phone":"192.168.0.10"}`,
   **When** it is parsed under the apartment-book schema shape, **Then** the
   returned contact exposes `name="01_monitor"`, `phone="192.168.0.10"`,
   and the apartment-book fields `apt_name="1"`, `apt_num="1"`,
   `building` and `landline` reflecting the (empty) source values, and the
   identifier field is absent / `None`.
2. **Given** an apartment-book payload that omits `ID`, **When** it is
   parsed, **Then** parsing succeeds (no error is raised for the missing
   `ID`) and the contact's identifier is `None`.
3. **Given** a full page of apartment-book records, **When**
   `list_contacts()` runs against an X915S, **Then** the count of returned
   contacts matches the device's record count and none of the
   apartment-book fields are dropped.

---

### User Story 2 — Get a clear "not supported" signal when writing on a read-only device (Priority: P1)

An integrator calls `add_contact`, `modify_contact`, or `delete_contact`
against an X915S, whose firmware does not support contact mutation over
HTTP. They need a single, recognisable, actionable error that says this
device class does not support contact mutation — not a cryptic
`"unsupport action"` device error, and not a bare `NotImplementedError`.

**Why this priority**: A cryptic or inconsistent failure is the exact pain
point issue #121 raises. Callers must be able to detect "this device can't
do that" reliably (one exception type, one reason taxonomy) and act on it,
across all three mutating operations.

**Independent Test**: Invoke each of the three contact-mutation operations
against an X915S capability profile and assert each raises
`AkuvoxUnsupportedError` (the recognisable capability error), with the same
reason classification, and with an actionable message that names the device
class and the unsupported operation — never `AkuvoxDeviceError`,
`NotImplementedError`, or a raw `"unsupport action"` string.

**Acceptance Scenarios**:

1. **Given** an X915S device profile, **When** the integrator calls
   `add_contact`, **Then** the call raises `AkuvoxUnsupportedError`
   identifying the device class and the contact-add capability, and the
   message suggests that contact management on this device class happens
   outside the HTTP API.
2. **Given** an X915S device profile, **When** the integrator calls
   `modify_contact` or `delete_contact`, **Then** each raises
   `AkuvoxUnsupportedError` with the **same** error type and reason
   classification as `add_contact` (the three mutating operations behave
   uniformly).
3. **Given** a caller who has opted into attempting unknown capabilities
   (`attempt_unknown_capability=True`) against a device whose contact-write
   status is not statically marked unsupported (e.g. an unrecognised device
   class) and so reaches the network, **When** the device returns the
   `"unsupport action"` envelope, **Then** the library surfaces it as
   `AkuvoxUnsupportedError` (not `AkuvoxDeviceError`), preserving the
   recognisable capability signal.

---

### User Story 3 — Door-phone devices keep their current behaviour (Priority: P1)

An existing integrator already uses the library against X916 / E18C
door-phone devices. After this change their reads and writes must behave
exactly as before: the new apartment-book fields default to absent / `None`
and never appear in payloads sent to door-phone devices.

**Why this priority**: This is a backward-compatibility guarantee. The
change is additive; it must not perturb the door-phone code path that the
existing user base depends on.

**Independent Test**: Parse a door-phone payload (with `ID`, `Name`,
`Phone`, `Group`) under the door-phone schema shape and assert the result
is unchanged from today (identifier, name, phone, group populated; the new
apartment-book fields all `None`), and that a door-phone write payload
contains none of the apartment-book keys.

**Acceptance Scenarios**:

1. **Given** a door-phone contact record with `ID`, `Name`, `Phone`,
   `Group`, **When** it is parsed under the door-phone schema shape,
   **Then** the result matches today's behaviour and the apartment-book
   fields are all `None`.
2. **Given** a caller constructing or sending a door-phone contact write,
   **When** the write payload is built, **Then** it contains no `APTName`,
   `APTNum`, `Building`, or `Landline` keys.
3. **Given** an existing caller that lists or adds contacts on a door-phone
   device, **When** they upgrade to this version, **Then** no source change
   is required and observable behaviour is unchanged.

---

### User Story 4 — Reliably reference an apartment-book record that has no ID (Priority: P2)

An integrator needs to correlate, deduplicate, or refer back to a specific
apartment-book contact across reads, but those records have no `ID`. They
need a documented, stable way to identify a record from the fields the
device does provide.

**Why this priority**: Without a defined identifier, callers cannot
reliably point at a specific apartment-book record. It is important but
secondary to preserving the data (US1) and signalling unsupported writes
(US2), and its exact form is an open design decision (see Outstanding
Clarifications).

**Independent Test**: Given two apartment-book records that differ only in
their apartment-book fields, confirm the documented identifier strategy
distinguishes them, and that the constraint (no device-assigned `ID` on
this device class) is stated in the published documentation.

**Acceptance Scenarios**:

1. **Given** two apartment-book records with the same `Name` but different
   `APTNum` / `Phone`, **When** the documented identifier strategy is
   applied, **Then** the two records are distinguishable from each other.
2. **Given** the published documentation, **When** an integrator reads the
   contacts section, **Then** it states what identifies an apartment-book
   record and that the device assigns no `ID` on this device class.

---

### User Story 5 — Understand which device classes use which contact model (Priority: P3)

A developer integrating the library wants to know, from documentation,
which device classes use the door-phone contact model and which use the
apartment-book model, what fields each carries, and that apartment-book
devices are read-only for contacts over HTTP.

**Why this priority**: Documentation prevents "why is `id` always `None`?"
and "why does `add_contact` fail?" reports. Valuable but not required for
the capability itself to function.

**Independent Test**: Confirm the published documentation contains a
section that contrasts the door-phone and apartment-book contact models,
lists the fields each carries, and states the read-only constraint for
apartment-book devices.

**Acceptance Scenarios**:

1. **Given** the project documentation, **When** a developer reads the
   contacts section, **Then** it describes the door-phone vs apartment-book
   models, names example device classes for each (e.g. X916 / E18C vs
   X915S), and states that apartment-book contacts are read-only over the
   HTTP API.

---

### Edge Cases

- **Empty apartment-book fields**: `Building` and `Landline` are frequently
  empty strings on the X915S. The parser MUST preserve the field as
  provided (an empty value is information: it says the device returned the
  key) and MUST NOT raise on emptiness.
- **Missing `ID` on apartment-book records**: never an error — the
  identifier is simply absent / `None` on this device class.
- **A door-phone-shaped payload arriving under the apartment-book branch**
  (or vice versa): parsing MUST remain tolerant — required `Name` is still
  required, and fields not present in a given payload simply default to
  absent / `None` rather than raising.
- **Write attempt with `attempt_unknown_capability=True`**: the opt-in must
  not turn a recognisable capability error into a cryptic device error; the
  `"unsupport action"` envelope MUST be translated to
  `AkuvoxUnsupportedError`.
- **Mixed device fleet**: a caller managing both door-phone and
  apartment-book devices in one process must get correct per-device
  behaviour driven by each device's capability profile, with no global
  state leaking between them.
- **Future apartment-book device classes**: the apartment-book model must
  not be hard-coded to "X915S only"; any device whose profile selects the
  apartment-book contact schema shape gets the same behaviour.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 — Preserve apartment-book metadata on read**: The contact model
  MUST gain optional apartment-book fields corresponding to `APTName`,
  `APTNum`, `Building`, and `Landline` (proposed public names `apt_name`,
  `apt_num`, `building`, `landline`; final names confirmed during
  planning). When a record is parsed under the apartment-book schema shape,
  these fields MUST be populated from the source record rather than
  discarded.

- **FR-002 — Apartment-book fields default absent for door-phone records**:
  The new apartment-book fields MUST default to `None` (absent) and MUST be
  `None` for records parsed under the door-phone schema shape. The model
  addition MUST be additive — existing fields (`name`, `id`, `phone`,
  `group`) keep their names, types, and meanings.

- **FR-003 — Tolerate a missing identifier on apartment-book records**:
  Parsing an apartment-book record that has no `ID` MUST succeed and yield a
  contact whose identifier is `None`. A missing `ID` MUST NOT raise a parse
  error on the apartment-book path. (The existing door-phone path is
  unchanged.)

- **FR-004 — Door-phone read/write behaviour unchanged**: For the
  door-phone schema shape, contact parsing and any contact write payload
  MUST be byte-identical to today's behaviour. The apartment-book fields
  MUST never be emitted in a door-phone write payload.

- **FR-005 — Single recognisable error for unsupported contact writes**:
  When any of `add_contact`, `modify_contact`, or `delete_contact` is
  invoked against a device class whose contact mutations are unsupported
  (the X915S apartment-book case), the library MUST raise
  `AkuvoxUnsupportedError`. It MUST NOT surface `AkuvoxDeviceError`, a bare
  `NotImplementedError`, or the raw `"unsupport action"` string as the
  user-visible outcome of the gated call path.

- **FR-006 — Uniform signalling across all three mutating operations**:
  `add_contact`, `modify_contact`, and `delete_contact` MUST behave
  uniformly on a read-only contact device class — same exception type and
  same reason classification — so callers do not have to special-case one
  operation differently from the others. To achieve this, the X915S matrix
  entry MUST mark `CONTACT_MODIFY` and `CONTACT_DELETE` consistently with
  `CONTACT_ADD` (i.e. as unsupported) rather than leaving them in the
  default `UNKNOWN` state.

- **FR-007 — Translate the `"unsupport action"` envelope to a capability
  error**: When a contact write reaches the device (for example because the
  caller opted into `attempt_unknown_capability=True`) and the device
  returns the `{"retcode":-1,"action":"unknow","message":"unsupport
  action"}` envelope, the library MUST translate it to
  `AkuvoxUnsupportedError` (with the `envelope_unsupported` reason), not
  `AkuvoxDeviceError`. The existing `"Api unsupported"` translation MUST be
  preserved.

- **FR-008 — Actionable error message**: The unsupported-write error
  message MUST name the device class and the attempted contact operation
  and MUST indicate that contact management on this device class is not
  available over the HTTP API (so the integrator knows to use the device
  web UI / provisioning instead). This satisfies the constitution's
  "errors must be actionable" requirement.

- **FR-009 — Caller can determine write support before attempting**: A
  caller MUST be able to determine, without triggering a failed write,
  whether contact mutation is supported on the connected device — at
  minimum through the already-exposed capability profile
  (`AkuvoxDevice.capabilities` / capability status lookup). Whether to add a
  dedicated convenience accessor for this is an open decision (see
  Outstanding Clarifications); the requirement is that the capability is
  discoverable in advance.

- **FR-010 — Documented identifier strategy for apartment-book records**:
  The library MUST document what identifies an apartment-book contact record
  given the absence of a device-assigned `ID`, and the constraint that
  follows. The exact strategy (e.g. a composite of apartment number and
  phone, the `Name`, or exposing the raw fields for the caller to key on) is
  an open decision (see Outstanding Clarifications), but the chosen rule and
  its limitations MUST be stated.

- **FR-011 — Documentation of device-class contact models**: The published
  documentation MUST contrast the door-phone and apartment-book contact
  models — the fields each carries, example device classes for each, and
  the read-only constraint for apartment-book devices over the HTTP API.

- **FR-012 — No silent or failing writes against read-only devices**: No
  code path may silently attempt — and no shipped path may cryptically fail
  — a contact write against an apartment-book device. Every contact-write
  entry point MUST resolve to the recognisable `AkuvoxUnsupportedError`
  signal (per FR-005 / FR-006 / FR-007).

- **FR-013 — Consistency with the static capability matrix**: This feature
  MUST NOT contradict the existing static capability matrix. The X915S entry
  MUST keep `contact` mapped to the apartment-book schema shape and
  `CONTACT_LIST` `SUPPORTED`; the only matrix change permitted is making the
  contact-mutation capabilities uniformly unsupported per FR-006. Door-phone
  classes (X916, E18C) keep their door-phone schema shape and full contact
  CRUD support.

- **FR-014 — Unit test coverage**: Unit tests MUST cover, at minimum: (a)
  apartment-book parse preserving all four apartment-book fields; (b)
  apartment-book parse tolerating a missing `ID`; (c) door-phone parse
  unchanged with apartment-book fields `None`; (d) each of the three
  contact-mutation operations raising `AkuvoxUnsupportedError` uniformly on
  the X915S profile; and (e) the `"unsupport action"` envelope translating
  to `AkuvoxUnsupportedError`. Coverage MUST be maintained at the project's
  required level.

### Key Entities *(include if feature involves data)*

- **Contact (door-phone shape)**: Flat record with `name`, `id`, `phone`,
  `group`. Used by X916 / E18C. Unchanged by this feature except that it
  gains the new apartment-book fields as always-`None` on this shape.
- **Contact (apartment-book shape)**: Same model surface, parsed from an
  X915S record. `id` is `None` (device assigns none); `group` is `None`
  (no `Group`); the apartment-book fields `apt_name`, `apt_num`,
  `building`, `landline` carry the device-provided values.
- **Contact schema shape**: The per-device selector (door-phone vs
  apartment-book) already carried by the device capability profile; it
  drives which parse/format path applies.
- **Unsupported-contact-write outcome**: A raised `AkuvoxUnsupportedError`
  carrying the contact capability, the device class, and a reason
  classification — the recognisable signal that contact mutation is not
  available on this device class.

## Device-Class / Capability Model *(mandatory)*

This feature is fundamentally about a **device-class capability
difference**, expressed through the library's existing capability framework
rather than ad-hoc field aliases:

| Device class (example) | Contact schema shape | Contact reads | Contact writes (add/modify/delete) | Distinguishing record fields |
|---|---|---|---|---|
| X916 / E18C (door phone) | door-phone | Supported | Supported | `ID`, `Name`, `Phone`, `Group` |
| X915S (apartment intercom) | apartment-book | Supported (read-only) | **Unsupported** over HTTP API | `Name`, `Phone`, `APTName`, `APTNum`, `Building`, `Landline` (no `ID`, no `Group`) |

- The device's effective contact schema shape is selected by its capability
  profile (`schema_shapes["contact"]`), already `APARTMENT_BOOK` for the
  X915S in the static matrix.
- The read path branches on that shape to populate (apartment-book) or omit
  (door-phone) the apartment-book fields.
- The write path is gated by the contact-mutation capabilities. For the
  X915S those capabilities are unsupported; the gate raises the recognisable
  capability error before (or, on opt-in, in place of) a cryptic device
  error.
- The model is **device-class-driven, not hard-coded to X915S**: any future
  device whose profile selects the apartment-book contact shape inherits
  identical behaviour.

## Out of Scope *(mandatory)*

- **Contact writes on X915S / apartment-book devices**: the firmware does
  not support `add` / `set` over the HTTP API, and no alternate write
  endpoint exists on the probed firmware. This feature makes the
  unsupported state **clear**; it does not add write support, nor attempt
  the web-UI / provisioning channels.
- **Non-HTTP-API provisioning channels**: the device web UI, autoprovision
  files, or any other management surface for apartment-book contacts.
- **New `/api/aptbook/*`, `/api/apartment/*`, `/api/building/*`, etc.
  endpoints**: all probed as absent ("No handlers for this request") on the
  current firmware; not added or relied upon.
- **New capability-probe steps or new matrix device classes**: this feature
  reconciles the existing X915S entry (per FR-006/FR-013) and surfaces
  already-tolerated fields. It does not add a new probe step or new device
  classes to the matrix.
- **Closed sibling issues**: #118 (X915S `Schedule` field-name parsing,
  fixed in PR #120) and #119 (X915S `add_user` HTTP 500, resolved by a
  firmware update) are separate and already resolved; they are not reworked
  here.
- **Changing door-phone contact behaviour**: the door-phone path is held
  byte-identical (FR-004).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an apartment-book contact record, 100% of the four
  apartment-book fields present in the source (`APTName`, `APTNum`,
  `Building`, `Landline`) are preserved on the parsed record — zero are
  dropped — verified across the parse test cases.
- **SC-002**: Listing contacts on an X915S returns the same number of
  records the device reports, and parsing never fails on a missing `ID`.
- **SC-003**: Each of the three contact-mutation operations
  (`add_contact`, `modify_contact`, `delete_contact`) on a read-only
  apartment-book device produces the recognisable `AkuvoxUnsupportedError`
  in 100% of tested paths — never `AkuvoxDeviceError`,
  `NotImplementedError`, or a raw `"unsupport action"` string — and all
  three share the same reason classification.
- **SC-004**: A caller can determine, before issuing any write, whether
  contact mutation is supported on the connected device, using the exposed
  capability information alone.
- **SC-005**: Door-phone contact reads and writes are unchanged: parsing a
  door-phone record yields the same result as the prior version (with the
  new fields `None`), and no door-phone write payload contains an
  apartment-book key — verified across the door-phone test cases.
- **SC-006**: A developer reading the documentation can correctly state,
  for a given device class, which contact model it uses, which fields that
  model carries, whether contacts are writable over HTTP, and what
  identifies an apartment-book record.

## Assumptions

- The apartment-book fields are surfaced as **optional, flat fields** on the
  existing contact model (defaulting to `None`), per the issue's suggested
  approach — rather than as a separate nested structure or a distinct
  contact type. This keeps the model additive and the door-phone path
  unchanged.
- Field values are preserved **as the device returns them** (including empty
  strings); the library does not normalise, coerce, or invent apartment-book
  values.
- The `"unsupport action"` message is a stable, recognisable marker for
  "operation unsupported by this firmware" in the same family as the
  already-handled `"Api unsupported"` envelope, and matching it is safe.
- Making `CONTACT_MODIFY` / `CONTACT_DELETE` uniformly unsupported for the
  X915S reflects observed reality (the firmware rejects all contact writes)
  and is consistent with the already-present `CONTACT_ADD: UNSUPPORTED`
  entry; it does not regress any device that currently relies on those
  operations being attempted.
- The existing capability framework (schema shapes, the capability gate, the
  structured `AkuvoxUnsupportedError`) is the correct foundation; no new
  capability subsystem is introduced.

## Outstanding Clarifications

- **[NEEDS CLARIFICATION: apartment-book record identifier strategy]** —
  Apartment-book records carry no device-assigned `ID`. The library must
  document what identifies such a record (FR-010), but the exact rule is an
  open design decision with trade-offs: (a) a **composite of
  `(APTNum, Phone)`** — stable while both are populated, but ambiguous if
  two records share an apartment number and a phone, or if `Phone` is
  empty; (b) **`Name`** — human-meaningful and always present, but not
  guaranteed unique and editable; (c) **expose the raw apartment-book
  fields and let the caller choose a key** — most flexible, but provides no
  library-level identity guarantee. Planning must pick one (and state its
  uniqueness limitations). It does not block authoring the spec because the
  data-preservation requirement (FR-001) is independent of which identity
  rule is chosen, and the chosen rule can be pinned by tests later.

- **[NEEDS CLARIFICATION: capability probe/accessor vs raise-only on
  write]** — The library already lets a caller inspect the capability
  profile (`AkuvoxDevice.capabilities`) and already raises a recognisable
  error on a gated write, so the minimum bar of FR-009 is met today. The
  open decision is whether to **also** add a dedicated, ergonomic accessor
  (for example a `supports(...)` / `contacts_writable` style convenience, or
  a contact-specific capability query) so integrators do not have to reach
  into the capability profile manually. Options: (a) **raise-only** — rely
  solely on the existing gate plus the existing `capabilities` property; (b)
  **add a small convenience accessor** for pre-flight checks. This is
  flagged because it affects the public API surface; it does not block the
  spec because either option satisfies FR-009.

## Dependencies

- The existing capability framework: `SchemaShape`, the per-device
  capability profile and its `require()` gate, the static capability matrix
  (including the X915S entry), and the structured `AkuvoxUnsupportedError`
  with its reason taxonomy.
- The existing contact read/write service module and the `Contact` data
  model (extended additively here).
- Hardware for verification: the maintainer's X915S at `192.168.0.2`
  (firmware `2915.30.10.114`).
