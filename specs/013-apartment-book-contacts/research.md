<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Research: Apartment-Book Contact Schema Support (X915S)

**Feature**: `013-apartment-book-contacts` | **Date**: 2026-06-18
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This document records the design decisions taken during planning, the
rationale, and the alternatives considered. All claims about existing code
were verified against the live `main` source (see "Source verification").

## Decision 1 — Apartment-book record identifier strategy (resolves Clarification 1)

**Decision**: **Option (c)** — the library **exposes the raw apartment-book
fields** (`apt_name`, `apt_num`, `building`, `landline`) and assigns **no
synthetic identity** (`id` stays `None` on the apartment-book shape). The
**documentation recommends** the `(apt_num, phone)` composite as the suggested
caller-side key, with `name` as a fallback, and explicitly states that the
library offers **no uniqueness guarantee**.

**Rationale**:

- The X915S apartment-book record carries **no device-assigned `ID`** and no
  group field (`Group`). The candidate key fields are not dependable:
  `Building` and `Landline` are frequently empty strings; `Phone` may be
  empty; `Name` is user-editable and not guaranteed unique. The library
  therefore **cannot**
  back a uniqueness/stability guarantee for any composite.
- FR-001 already requires surfacing all four apartment-book fields, so
  exposing them as the identity substrate is **free and additive**. `id`
  remains `None`, which is truthful (FR-003) rather than a misleading
  synthetic value.
- US4 is satisfied through documentation (FR-010), not a library guarantee:
  the docs name the recommended `(apt_num, phone)` composite and its limits.
  Two records differing only in apartment-book fields are distinguishable
  under that rule (US4 acceptance #1), and the "no device `ID`" constraint is
  stated (US4 acceptance #2).

**Alternatives considered**:

- **(a) composite `(APTNum, Phone)` minted as a synthetic `id`** — rejected.
  Stable only while both are populated and unique; ambiguous when `Phone` is
  empty or two records share `(APTNum, Phone)`. Worse, surfacing it on the
  `id` field would imply a device-assigned, stable identifier the data does
  not provide, misleading callers. The composite is still **recommended in
  docs** as a caller-side key — but the library does not mint it.
- **(b) use `Name` as the identifier** — rejected. `Name` is always present
  and human-meaningful but **editable** and **not unique**; it collapses
  US4's explicit same-`Name`/different-`APTNum`/`Phone` case, which is the
  scenario the identifier must disambiguate.

**Constraint to document (FR-010)**: apartment-book devices assign no `ID`
over the HTTP API; callers needing to correlate records should key on
`(apt_num, phone)` when both are populated (falling back to `name`), and the
library guarantees field **preservation**, not record **identity**.

## Decision 2 — Capability signalling: raise-only vs probe accessor (resolves Clarification 2)

**Decision**: **Option (a) — raise-only.** Rely on the existing capability
gate (`DeviceCapabilities.require`) plus the already-exposed
`AkuvoxDevice.capabilities` surface (`status_of(...)`, `supported_set`). Do
**not** add a contact-specific convenience accessor.

**Rationale**:

- FR-009's minimum bar is **already met**: `device.capabilities.status_of(
  Capability.CONTACT_ADD)` returns `CapabilityStatus.UNSUPPORTED` on the X915S
  **before** any write is attempted, and `supported_set` enumerates writable
  capabilities. No failed request is needed to discover support.
- A bespoke accessor (`contacts_writable`, `supports(...)`) would **expand the
  public API surface**, create a **second source of truth** to keep in sync
  with the capability profile, and contradict the spec's additive/minimal
  intent and Out-of-Scope note ("no new capability subsystem"). The sibling
  OpenDoor plan (012) likewise chose the minimal option.
- The ergonomic gap is closed with **documentation** (a one-line pre-flight
  `status_of(...)` snippet in the quickstart), not new API.

**Alternatives considered**:

- **(b) add a small convenience accessor** for pre-flight checks — viable and
  would satisfy FR-009, but rejected for surface-area and
  single-source-of-truth reasons. If integrator demand later materialises, it
  can be added non-breakingly on top of the existing profile.

## Decision 3 — Surface the fields on the existing model vs a new type (FR-001/FR-002)

**Decision**: Add four **optional, flat, default-`None`** fields
(`apt_name`, `apt_num`, `building`, `landline`) to the existing `Contact`
frozen dataclass — **not** a nested structure or a separate
`ApartmentContact` type.

**Rationale**:

- The spec's Assumptions explicitly choose flat optional fields ("rather than
  as a separate nested structure or a distinct contact type"), keeping the
  model additive and the door-phone path unchanged.
- `Contact` is `@dataclass(frozen=True, kw_only=True)`, so appending fields
  with defaults is backward-compatible: construction, equality, and hashing
  semantics are preserved; door-phone instances carry the new fields as
  `None`.
- A separate type would fork the parse/return signatures of `list_contacts`
  and ripple through `_device_contacts.py`, `device.py`, and callers — a
  larger, non-additive change the spec rules out.

**Empty-as-information nuance**: the apartment-book fields are populated with
**uncoerced** `data.get("APTName")` (etc.) so a present-but-empty `Building`
(`""`) is preserved, while an absent key yields `None`. This differs
deliberately from the existing `phone=data.get("Phone") or None` coercion,
which is retained unchanged on both branches for `phone`/`group`. The spec's
Edge Cases require that an empty apartment-book value be preserved as
information.

## Decision 4 — `"unsupport action"` envelope translation (FR-007)

**Decision**: Broaden `_http._handle_response`'s unsupported-message match to
also recognise `"unsupport action"` (the device's typo) and
`"unsupported action"`, **case-insensitively**, and raise
`AkuvoxUnsupportedError(message, reason="envelope_unsupported")`. Preserve the
existing `"Api unsupported"` translation (now also carrying the
`envelope_unsupported` reason).

**Rationale**:

- Today `_UNSUPPORTED_MSG = "Api unsupported"` is matched with a
  **case-sensitive** `in` test and the X915S `"unsupport action"` envelope
  does **not** match, so it falls through to `if retcode < 0: raise
  AkuvoxDeviceError(message)` — exactly the leak issue #121 describes.
- Matching case-insensitively against the lowercase markers preserves the
  `"Api unsupported"` behaviour (`"api unsupported" in message.lower()` still
  matches) while adding the action-unsupported family (FR-007).
- Setting `reason="envelope_unsupported"` makes the envelope-level signal
  classifiable; `envelope_unsupported` is already a member of the closed
  reason taxonomy documented in `exceptions.py` and audited by the existing
  reason-taxonomy test.

**Layering note**: the same markers already exist as
`_API_UNSUPPORTED_MARKER` / `_ACTION_UNSUPPORTED_MARKERS` in
`_probe_outcomes.py`. Importing them into `_http.py` would **invert** the
module layering (the capability probe depends on the HTTP client, not the
reverse), so `_http.py` keeps its **own local** marker constants. The minor
duplication is intentional; a future refactor could hoist the markers into a
shared standard-library-only leaf if desired (out of scope here).

**Alternatives considered**:

- *Import the markers from `_probe_outcomes`* — rejected to avoid the
  layering inversion described above.
- *Match only the exact `"unsupport action"` literal* — rejected: brittle
  against the correctly-spelled `"unsupported action"` variant the firmware
  family also emits (both are listed in `_ACTION_UNSUPPORTED_MARKERS`).

## Decision 5 — Uniform write rejection via the gate; remove the service deferral (FR-005/FR-006)

**Decision**: Make the **capability gate** the single uniform rejection
mechanism by marking `CONTACT_MODIFY` and `CONTACT_DELETE` `UNSUPPORTED` on
the X915S matrix entry (joining the existing `CONTACT_ADD: UNSUPPORTED`), and
**remove** the `APARTMENT_BOOK` → `NotImplementedError` deferral from the
service-layer `add_contact` / `modify_contact`.

**Rationale**:

- All three `AkuvoxDevice.{add,modify,delete}_contact` wrappers already call
  `ctx.capabilities.require(Capability.CONTACT_*, ...)`. With all three
  capabilities `UNSUPPORTED`, the gate raises
  `AkuvoxUnsupportedError(reason="capability_missing")` **before any I/O**,
  uniformly — the exact FR-005/FR-006 behaviour. `delete_contact` is
  shape-agnostic at the service layer, so the gate (not a service branch) is
  the only place uniformity can be enforced; that confirms the gate as the
  right mechanism.
- Keeping the service-layer `NotImplementedError` would leave a **different**
  exception type on a now-dead path (the gate fires first) and contradicts
  FR-005's "never a bare `NotImplementedError`". Removing it also deletes the
  now-vestigial `schema_shape=` kwarg those two functions consumed only for
  the deferral.
- For the rare **direct** service-layer caller (capability-unaware, bypassing
  the gate) the device's `"unsupport action"` envelope is now translated
  (Decision 4) to `AkuvoxUnsupportedError(reason="envelope_unsupported")` —
  so even that path yields the recognisable signal (FR-012).

**FR-013 compliance**: this is the **only** matrix change. `contact` stays
mapped to `APARTMENT_BOOK`; `CONTACT_LIST` stays `SUPPORTED`; door-phone
classes (X916, E18C) keep door-phone shape and full CRUD.

**Alternatives considered**:

- *Convert the service `NotImplementedError` into a service-raised
  `AkuvoxUnsupportedError`* — rejected: the service layer is intentionally
  capability-unaware (it has no `device_class` to populate the structured
  reason), and duplicating the rejection there is redundant with the
  authoritative gate. The envelope translation already covers direct callers.
- *Leave `CONTACT_MODIFY`/`CONTACT_DELETE` as `UNKNOWN` and rely on
  `attempt_unknown_capability` + envelope translation* — rejected: violates
  FR-006 (the three ops would behave **non-uniformly** — `add` raises
  `capability_missing` pre-flight while `modify`/`delete` either raise
  `capability_unknown` or reach the network), and contradicts the observed
  reality that the firmware rejects all three.

## Decision 6 — `to_api_payload()` is not extended (FR-004)

**Decision**: Leave `Contact.to_api_payload()` unchanged (emits only
`Name` / `ID` / `Phone` / `Group`).

**Rationale**: Apartment-book devices are read-only over HTTP, so no
apartment-book write payload is ever built; and door-phone writes must be
byte-identical (FR-004). Not emitting the apartment-book keys is the
guarantee. A unit test pins that a `Contact` carrying apt fields still
produces a payload with no `APTName`/`APTNum`/`Building`/`Landline` key.

## Decision 7 — Artifact scope

**Decision**: Produce `research.md`, `data-model.md`,
`contracts/apartment-book-read.md`, `contracts/contact-write-rejection.md`,
and `quickstart.md`.

**Rationale**: Unlike the OpenDoor plan (012), this feature **changes the
domain model** (`Contact` gains four fields and a parse-path behaviour),
which warrants a `data-model.md`. Two focused contract files separate the
read surface from the write-rejection/envelope surface. No more is produced —
no new endpoint or persistence exists.

## Source verification

Verified against live `main` source in the worktree at planning time:

- `src/pylocal_akuvox/models/contacts.py` — `Contact` is
  `@dataclass(frozen=True, kw_only=True)` with `name`/`id`/`phone`/`group`;
  `from_api_response` branches on
  `capabilities.schema_shapes.get("contact", DOOR_PHONE)`; the
  `APARTMENT_BOOK` and door-phone branches are **byte-identical today**
  (both `cls(name=…, id=data.get("ID"), phone=data.get("Phone") or None,
  group=data.get("Group") or None)`); `to_api_payload` emits only
  `Name`/`ID`/`Phone`/`Group`.
- `src/pylocal_akuvox/contacts.py` — service `add_contact` / `modify_contact`
  carry a `schema_shape=` kwarg and raise `NotImplementedError(
  _APARTMENT_BOOK_WRITE_DEFERRAL_MSG)` on the `APARTMENT_BOOK` shape;
  `delete_contact` is shape-agnostic (no `schema_shape=`); `list_contacts`
  threads `capabilities=`.
- `src/pylocal_akuvox/_device_contacts.py` — `_contact_shape(ctx)` resolves
  the shape; all four wrappers call
  `ctx.capabilities.require(Capability.CONTACT_*, allow_unknown=…)`; add/modify
  pass `schema_shape=_contact_shape(ctx)`; `list_contacts` passes
  `capabilities=ctx.capabilities`.
- `src/pylocal_akuvox/capability_matrix.py` — `_X915S_CURRENT` has
  `schema_shapes={"contact": SchemaShape.APARTMENT_BOOK}`,
  `CONTACT_LIST: SUPPORTED`, `CONTACT_ADD: UNSUPPORTED`, and **no**
  `CONTACT_MODIFY` / `CONTACT_DELETE` entries (→ `UNKNOWN` via `status_of`).
- `src/pylocal_akuvox/_capability_profile.py` — `require()` maps
  `UNSUPPORTED` → `reason="capability_missing"`, `UNKNOWN` →
  `capability_unknown` (or `device_unrecognized`) unless `allow_unknown`;
  `status_of` defaults absent capabilities to `UNKNOWN`; `supported_set`
  property exists.
- `src/pylocal_akuvox/_http.py` — `_UNSUPPORTED_MSG = "Api unsupported"`
  matched case-sensitively in `_handle_response`; `"unsupport action"` falls
  through to `AkuvoxDeviceError(message)` on `retcode < 0`. The raise has no
  `reason`.
- `src/pylocal_akuvox/_probe_outcomes.py` — defines
  `_API_UNSUPPORTED_MARKER = "api unsupported"` and
  `_ACTION_UNSUPPORTED_MARKERS = ("unsupported action", "unsupport action")`.
- `src/pylocal_akuvox/exceptions.py` — `AkuvoxUnsupportedError(message, *,
  capability=None, device_class=None, reason=None)`; closed reason set
  includes `capability_missing`, `capability_unknown`, `envelope_unsupported`.
- `src/pylocal_akuvox/_capability_types.py` — `SchemaShape.{DOOR_PHONE,
  APARTMENT_BOOK}`; `Capability.CONTACT_{LIST,ADD,MODIFY,DELETE}`;
  `CapabilityStatus.{SUPPORTED,UNSUPPORTED,UNKNOWN}`.
- `tests/unit/test_contacts.py`, `tests/unit/test_http.py` — existing contact
  and HTTP envelope test modules to extend.

### Live-source corrections to planning-doc assumptions

- The task brief's claim that "`_http.py` currently only translates the
  literal `Api unsupported` message" is **confirmed**, and additionally the
  existing translation raises `AkuvoxUnsupportedError` **without** a `reason`
  — so Phase 4 both broadens the match **and** upgrades the existing raise to
  `reason="envelope_unsupported"`.
- The brief notes the service `add_contact`/`modify_contact` "raise
  `NotImplementedError`". Confirmed — and they do so **gated on the
  `schema_shape=` kwarg**, which becomes dead once the matrix gate is
  authoritative; the plan removes the branch and the now-unused kwarg rather
  than leaving inconsistent dead code.
- **`GroupID` vs `Group`**: the merged spec describes the door-phone group
  field as `GroupID`, but the live `Contact` model reads and writes the
  `Group` API key (`data.get("Group")`, `payload["Group"]`), confirmed by the
  feature-004 live-device-tested data model. These planning docs therefore
  use `Group` (the real key) for the contact group field rather than the
  spec's loose `GroupID` wording. The apartment-book record carries no group
  field at all under either name.
