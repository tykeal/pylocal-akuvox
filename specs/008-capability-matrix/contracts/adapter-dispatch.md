<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Adapter Dispatch (Relay-Trigger Variants)

**Phase**: 2 (PR 2)
**Owning module**: `src/pylocal_akuvox/capability_adapters.py`
**Caller**: `src/pylocal_akuvox/relay.py::trigger_relay` (and its
shim on `AkuvoxDevice.trigger_relay`).
**Owning tests**: `tests/unit/test_dispatch.py`,
`tests/unit/test_relay.py` (existing, kept green by ensuring the
default API path adapter is selected when both today's tests and the
X916 matrix entry agree).

## The shape

```python
# pylocal_akuvox/capability_adapters.py


@dataclass(frozen=True, kw_only=True)
class RelayTriggerArgs:
    num: int
    mode: int = 0
    level: int = 0
    delay: int = 0


RelayTriggerAdapter: TypeAlias = Callable[
    [AkuvoxHttpClient, RelayTriggerArgs],
    Awaitable[None],
]


async def _api_relay_trigger(http: AkuvoxHttpClient, args: RelayTriggerArgs) -> None:
    """Relay trigger via /api/relay/trig (X916, X915S, E18C)."""
    body = {
        "target": "relay",
        "action": "trig",
        "data": {
            "num": args.num,
            "mode": args.mode,
            "level": args.level,
            "delay": args.delay,
        },
    }
    await http.post("/api/relay/trig", data=body)


async def _fcgi_relay_trigger(http: AkuvoxHttpClient, args: RelayTriggerArgs) -> None:
    """Relay trigger via /fcgi/do?action=OpenDoor (IT83 indoor monitor).

    Per issue #122. Note: the FCGI variant accepts only ``num`` (mapped
    onto a relay ID query parameter); ``mode``, ``level``, and ``delay``
    are not supported on this transport. Callers passing non-default
    values for those fields against an FCGI-only device receive an
    ``AkuvoxValidationError`` raised here at the adapter boundary.
    """
    if args.mode != 0 or args.level != 0 or args.delay != 0:
        raise AkuvoxValidationError(
            "FCGI relay trigger does not support mode/level/delay; "
            "only num is honored on this device class"
        )
    await http.get(f"/fcgi/do?action=OpenDoor&relay={args.num}")


RELAY_TRIGGER_ADAPTERS: dict[
    tuple[Capability, str],
    RelayTriggerAdapter,
] = {
    (Capability.RELAY_TRIGGER_API, "api"): _api_relay_trigger,
    (Capability.RELAY_TRIGGER_FCGI, "fcgi"): _fcgi_relay_trigger,
}
```

## Dispatch order

> **FR-011 gating note**: `AkuvoxDevice.trigger_relay()` is gated **structurally** via this adapter-registry scan (the `status_of(...)` calls below + the `adapter_missing` raise at the end), NOT via a literal `self._capabilities.require(...)` call. This makes it an explicit exception to the FR-011 introspection audit in `tests/unit/test_device.py::test_every_public_device_method_has_capability_gate` (see `data-model.md` §"Adapter-gated exception" and `tasks.md` T038 + T049). The exception is documented in the audit test's `_ADAPTER_GATED = {"trigger_relay"}` set.

`AkuvoxDevice.trigger_relay()` Phase-2 implementation:

```python
async def trigger_relay(
    self,
    *,
    num: int,
    mode: int = 0,
    level: int = 0,
    delay: int = 0,
    adapter: Capability | None = None,
) -> None:
    args = RelayTriggerArgs(num=num, mode=mode, level=level, delay=delay)
    caps = self._capabilities

    # 1. Caller override path.
    if adapter is not None:
        status = caps.status_of(adapter)
        if status is CapabilityStatus.UNSUPPORTED:
            raise AkuvoxUnsupportedError(
                f"Adapter {adapter.value} requested but device "
                f"{caps.device_class} confirmed does not support it",
                capability=adapter,
                device_class=caps.device_class,
                reason="capability_missing",
            )
        if status is CapabilityStatus.UNKNOWN and not self.attempt_unknown_capability:
            raise AkuvoxUnsupportedError(
                f"Adapter {adapter.value} requested but its status is "
                f"unknown on {caps.device_class}; add a matrix entry "
                f"or set device.attempt_unknown_capability=True",
                capability=adapter,
                device_class=caps.device_class,
                reason="capability_unknown",
            )
        chosen = adapter
    else:
        # 2. Preference order: API before FCGI. Only SUPPORTED counts
        # for default dispatch — UNKNOWN does not auto-promote because
        # firing the wrong relay-trigger variant would trigger a
        # cryptic device-side error, exactly the failure mode the
        # three-valued model is written to prevent.
        chosen = None
        for candidate in _RELAY_TRIGGER_PREFERENCE:
            if caps.status_of(candidate) is CapabilityStatus.SUPPORTED:
                chosen = candidate
                break
        if chosen is None:
            # No SUPPORTED variant. Decide between capability_missing
            # (every variant is UNSUPPORTED) and capability_unknown
            # (at least one variant is UNKNOWN) for the error reason.
            any_unknown = any(
                caps.status_of(c) is CapabilityStatus.UNKNOWN
                for c in _RELAY_TRIGGER_PREFERENCE
            )
            reason = "capability_unknown" if any_unknown else "capability_missing"
            msg_tail = (
                "; add a matrix entry or pass adapter= explicitly with "
                "device.attempt_unknown_capability=True"
                if any_unknown
                else ""
            )
            raise AkuvoxUnsupportedError(
                f"Device {caps.device_class} has no supported "
                f"relay-trigger variant{msg_tail}",
                capability=Capability.RELAY_TRIGGER_API,  # canonical
                device_class=caps.device_class,
                reason=reason,
            )

    # 3. Look up adapter for the chosen capability.
    variant = _CAPABILITY_TO_VARIANT[chosen]  # "api" | "fcgi"
    fn = RELAY_TRIGGER_ADAPTERS.get((chosen, variant))
    if fn is None:
        raise AkuvoxUnsupportedError(
            f"No adapter registered for {chosen.value} on {caps.device_class}",
            capability=chosen,
            device_class=caps.device_class,
            reason="adapter_missing",
        )
    await fn(self._http, args)
```

Where `_RELAY_TRIGGER_PREFERENCE = (Capability.RELAY_TRIGGER_API,
Capability.RELAY_TRIGGER_FCGI)` and `_CAPABILITY_TO_VARIANT = {
RELAY_TRIGGER_API: "api", RELAY_TRIGGER_FCGI: "fcgi" }` are
module-level constants in `capability_adapters.py`.

## Per-device-class behaviour (test cases for `test_dispatch.py`)

Default dispatch consults `status_of(...) is CapabilityStatus.SUPPORTED`
for each variant in preference order. UNKNOWN status does **not**
auto-promote: trying the wrong relay-trigger variant against a device
that does not handle it would fire — or fail to fire — a relay, the
exact UX failure mode the three-valued model is written to prevent.

| Device class | Per-variant status | `device.trigger_relay(num=1)` issues | Override `adapter=RELAY_TRIGGER_FCGI` (or API) |
|--------------|---------------------|----------------------------------------|------------------------|
| X916         | API=`SUPPORTED`, FCGI=`UNKNOWN` | `POST /api/relay/trig` | FCGI override → `AkuvoxUnsupportedError(reason="capability_unknown")`, no HTTP issued (unless `attempt_unknown_capability=True`) |
| X915S (current) | API=`SUPPORTED`, FCGI=`UNKNOWN` | `POST /api/relay/trig` | as above |
| E18C (current)  | API=`SUPPORTED`, FCGI=`UNKNOWN` | `POST /api/relay/trig` | as above |
| IT83         | API=`UNSUPPORTED` (no-handler confirmed), FCGI=`SUPPORTED` | `GET  /fcgi/do?action=OpenDoor&relay=1` | API override → `AkuvoxUnsupportedError(reason="capability_missing")`, no HTTP issued |
| Unknown (conservative-empty profile) | API=`UNKNOWN`, FCGI=`UNKNOWN` | `AkuvoxUnsupportedError(reason="capability_unknown")`, no HTTP issued | both overrides → `capability_unknown` unless `attempt_unknown_capability=True` |

(SC-005 covers the IT83 row's `RELAY_TRIGGER_API` override
distinguishing-confirmed-negative-from-unknown; SC-006 covers the X916
vs IT83 default-dispatch divergence.)

## Adding a new variant

To add a future variant (say, a hypothetical
`/cgi-bin/door` adapter for some new device class):

1. Add a `Capability` member, e.g. `RELAY_TRIGGER_CGI = "relay.trigger.cgi"`.
2. Implement `_cgi_relay_trigger(http, args)` in
   `capability_adapters.py`.
3. Add `(RELAY_TRIGGER_CGI, "cgi"): _cgi_relay_trigger` to
   `RELAY_TRIGGER_ADAPTERS`.
4. Insert `RELAY_TRIGGER_CGI` into `_RELAY_TRIGGER_PREFERENCE` at the
   desired position.
5. Add `RELAY_TRIGGER_CGI: "cgi"` to `_CAPABILITY_TO_VARIANT`.
6. Update the matrix entry for the device class to map
   `RELAY_TRIGGER_CGI` to `CapabilityStatus.SUPPORTED` in its
   `capabilities` mapping (and, where appropriate, mark the previously
   handled variants as `UNSUPPORTED` or leave them as `UNKNOWN`).
7. Add a test row in `test_dispatch.py`.

No edits to `device.py`, `relay.py`, or any other module are required.

## Why `tuple[Capability, str]` keys instead of `Capability` alone

The variant tag exists so future capabilities with multiple
implementations (e.g. `device.set_config` over `/api/*` vs `/web/*`) can
plug into the same registry pattern with the same shape:
`SET_CONFIG_ADAPTERS: dict[tuple[Capability, str], SetConfigAdapter]`.
For relay trigger today, the variant tag is redundant with the
capability member (one-to-one). Keeping it explicit avoids a future
registry-shape divergence.

## What is NOT a contract

- The exact registry **module location** within
  `capability_adapters.py` is not part of the public contract; tests
  consume `RELAY_TRIGGER_ADAPTERS` only via attribute access on the
  module. Refactoring the module internals later is fine as long as
  `RELAY_TRIGGER_ADAPTERS`, `RelayTriggerArgs`, and the two adapter
  callables remain importable by name.
- The dispatch helper functions (`_RELAY_TRIGGER_PREFERENCE`,
  `_CAPABILITY_TO_VARIANT`) are private implementation details; tests
  exercise them via `trigger_relay()` only.
