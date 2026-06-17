# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Relay helpers for :class:`pylocal_akuvox.device.AkuvoxDevice`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox import relay
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
from pylocal_akuvox.capability_adapters import (
    CAPABILITY_TO_VARIANT,
    RELAY_TRIGGER_ADAPTERS,
    RELAY_TRIGGER_PREFERENCE,
    RelayTriggerArgs,
)
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError, AkuvoxValidationError
from pylocal_akuvox.relay import _validate_relay_trigger_args

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._device_runtime import _DeviceContext


def resolve_override_adapter(
    capabilities: DeviceCapabilities,
    adapter: Capability,
    *,
    allow_unknown: bool,
) -> Capability:
    """Resolve a caller-supplied relay adapter override."""
    if adapter not in RELAY_TRIGGER_PREFERENCE:
        allowed = ", ".join(c.value for c in RELAY_TRIGGER_PREFERENCE)
        msg = (
            f"adapter override {adapter.value!r} is not a relay-trigger "
            f"variant; allowed values: {allowed}"
        )
        raise AkuvoxValidationError(msg)
    status = capabilities.status_of(adapter)
    if status is CapabilityStatus.UNSUPPORTED:
        msg = (
            f"Adapter {adapter.value} requested but device "
            f"{capabilities.device_class} confirmed does not support it"
        )
        raise AkuvoxUnsupportedError(
            msg,
            capability=adapter,
            device_class=capabilities.device_class,
            reason="capability_missing",
        )
    if status is CapabilityStatus.UNKNOWN and not allow_unknown:
        msg = (
            f"Adapter {adapter.value} requested but its status is "
            f"unknown on {capabilities.device_class}; add a matrix entry "
            f"or set device.attempt_unknown_capability=True"
        )
        raise AkuvoxUnsupportedError(
            msg,
            capability=adapter,
            device_class=capabilities.device_class,
            reason="capability_unknown",
        )
    return adapter


def resolve_default_adapter(capabilities: DeviceCapabilities) -> Capability:
    """Walk the preference list and pick the first supported relay variant."""
    for candidate in RELAY_TRIGGER_PREFERENCE:
        if capabilities.status_of(candidate) is CapabilityStatus.SUPPORTED:
            return candidate

    first_unknown: Capability | None = next(
        (
            capability
            for capability in RELAY_TRIGGER_PREFERENCE
            if capabilities.status_of(capability) is CapabilityStatus.UNKNOWN
        ),
        None,
    )
    if first_unknown is not None:
        reason = "capability_unknown"
        reported = first_unknown
        msg_tail = (
            "; add a matrix entry or pass adapter= explicitly with "
            "device.attempt_unknown_capability=True"
        )
    else:
        reason = "capability_missing"
        reported = RELAY_TRIGGER_PREFERENCE[0]
        msg_tail = ""
    msg = (
        f"Device {capabilities.device_class} has no supported "
        f"relay-trigger variant{msg_tail}"
    )
    raise AkuvoxUnsupportedError(
        msg,
        capability=reported,
        device_class=capabilities.device_class,
        reason=reason,
    )


async def trigger_relay(
    ctx: _DeviceContext,
    *,
    num: int,
    mode: int = 0,
    level: int = 0,
    delay: int = 0,
    adapter: Capability | None = None,
) -> None:
    """Trigger a relay through the selected adapter implementation."""
    _validate_relay_trigger_args(num=num, mode=mode, level=level, delay=delay)

    args = RelayTriggerArgs(num=num, mode=mode, level=level, delay=delay)
    if adapter is not None:
        chosen = resolve_override_adapter(
            ctx.capabilities,
            adapter,
            allow_unknown=ctx.allow_unknown,
        )
    else:
        chosen = resolve_default_adapter(ctx.capabilities)

    variant = CAPABILITY_TO_VARIANT[chosen]
    fn = RELAY_TRIGGER_ADAPTERS.get((chosen, variant))
    if fn is None:
        msg = (
            f"No adapter registered for {chosen.value} "
            f"on {ctx.capabilities.device_class}"
        )
        raise AkuvoxUnsupportedError(
            msg,
            capability=chosen,
            device_class=ctx.capabilities.device_class,
            reason="adapter_missing",
        )
    await fn(ctx.client, args)


async def get_relay_status(ctx: _DeviceContext) -> dict[str, Any]:
    """Retrieve current relay states from the device."""
    ctx.capabilities.require(Capability.RELAY_STATUS, allow_unknown=ctx.allow_unknown)
    return await relay.get_relay_status(ctx.client)
