# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Adapter registry for capability variants with multiple transports.

Currently this module only houses the relay-trigger adapter family
(``/api/relay/trig`` for door phones, ``/fcgi/do?action=OpenDoor`` for
IT83 indoor monitors). The registry shape is deliberately generic
(``dict[tuple[Capability, str], Adapter]``) so future capabilities
that have multiple transport variants — e.g. a hypothetical
``DEVICE_CONFIG_SET`` over both ``/api/config/set`` and ``/web/...``
— can plug in without re-shaping the registry.

See ``specs/008-capability-matrix/contracts/adapter-dispatch.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pylocal_akuvox._capability_types import Capability
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pylocal_akuvox._http import AkuvoxHttpClient


@dataclass(frozen=True, kw_only=True)
class RelayTriggerArgs:
    """Bundle of parameters threaded through every relay-trigger adapter.

    Frozen and keyword-only so adapter call sites are unambiguous and
    so the args object is hashable for tests that want to assert
    structural equality across calls.
    """

    num: int
    mode: int = 0
    level: int = 0
    delay: int = 0


if TYPE_CHECKING:
    type RelayTriggerAdapter = Callable[
        [AkuvoxHttpClient, RelayTriggerArgs],
        Awaitable[None],
    ]


async def _api_relay_trigger(http: AkuvoxHttpClient, args: RelayTriggerArgs) -> None:
    """Relay trigger via ``/api/relay/trig`` (X916, X915S, E18C).

    The full ``num`` / ``mode`` / ``level`` / ``delay`` set is honoured
    because the door-phone API surface accepts all four. This is the
    long-standing transport for door phones; the only reason a device
    might fail this call at runtime is an unexpected firmware
    regression — the matrix records the door-phone classes as
    ``RELAY_TRIGGER_API = SUPPORTED``.
    """
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


async def _fcgi_relay_trigger(
    _http: AkuvoxHttpClient,
    _args: RelayTriggerArgs,
) -> None:
    """Guard the deprecated credential-less FCGI relay-trigger adapter.

    The vendor ``/fcgi/do?action=OpenDoor`` endpoint requires dedicated
    Open Relay Via HTTP credentials and the ``DoorNum`` query parameter.
    The capability-dispatch path cannot supply those per-call credentials,
    so it intentionally issues no request and directs callers to the
    credentialed public helper instead.
    """
    msg = (
        "FCGI relay trigger requires Open Relay Via HTTP credentials; "
        "call AkuvoxDevice.open_door_http(user=..., password=..., "
        "door_num=...) instead"
    )
    raise AkuvoxUnsupportedError(
        msg,
        capability=Capability.RELAY_TRIGGER_FCGI,
        reason="capability_missing",
    )


# Adapter registry — keyed by ``(Capability, variant_tag)``.
#
# The variant tag is redundant with the capability member today
# (one-to-one), but keeping it explicit avoids a future registry-shape
# divergence when a single ``Capability`` grows multiple transport
# variants. See ``adapter-dispatch.md`` §"Why ``tuple[Capability, str]``
# keys instead of ``Capability`` alone".
RELAY_TRIGGER_ADAPTERS: dict[
    tuple[Capability, str],
    RelayTriggerAdapter,
] = {
    (Capability.RELAY_TRIGGER_API, "api"): _api_relay_trigger,
    (Capability.RELAY_TRIGGER_FCGI, "fcgi"): _fcgi_relay_trigger,
}

# Preference order for default dispatch — API before FCGI. Only
# ``SUPPORTED`` counts for default dispatch (UNKNOWN does not
# auto-promote — firing the wrong relay variant would either trigger
# or fail to trigger a relay, the exact UX failure mode the
# three-valued model is written to prevent).
RELAY_TRIGGER_PREFERENCE: tuple[Capability, ...] = (
    Capability.RELAY_TRIGGER_API,
    Capability.RELAY_TRIGGER_FCGI,
)

# Mapping from capability member to its variant tag in
# :data:`RELAY_TRIGGER_ADAPTERS`. Kept in lock-step with the registry
# itself so a missing tag immediately raises
# :class:`KeyError` from the dispatch helper, surfacing
# adapter-author errors at the call site rather than silently falling
# through to a "no adapter" raise.
CAPABILITY_TO_VARIANT: dict[Capability, str] = {
    Capability.RELAY_TRIGGER_API: "api",
    Capability.RELAY_TRIGGER_FCGI: "fcgi",
}


__all__ = [
    "CAPABILITY_TO_VARIANT",
    "RELAY_TRIGGER_ADAPTERS",
    "RELAY_TRIGGER_PREFERENCE",
    "RelayTriggerArgs",
]
