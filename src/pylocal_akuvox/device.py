# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""High-level async interface for Akuvox device operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.capabilities import (
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
    lookup_capabilities,
)
from pylocal_akuvox.capability_adapters import (
    CAPABILITY_TO_VARIANT,
    RELAY_TRIGGER_ADAPTERS,
    RELAY_TRIGGER_PREFERENCE,
    RelayTriggerArgs,
)
from pylocal_akuvox.capability_probe import probe_capabilities as _probe_capabilities
from pylocal_akuvox.exceptions import AkuvoxUnsupportedError
from pylocal_akuvox.models import DeviceInfo, DeviceStatus

if TYPE_CHECKING:
    from pylocal_akuvox.auth import AuthConfig
    from pylocal_akuvox.models import (
        AccessSchedule,
        CallLogEntry,
        Contact,
        DeviceConfig,
        DoorLogEntry,
        Group,
        User,
    )


_DEVICE_NOT_IN_MATRIX_NOTE = (
    "Device not in capability matrix. Call "
    "device.probe_capabilities() to enumerate, or set "
    "device.attempt_unknown_capability=True to opt in to "
    "unknown-status operations."
)


def _conservative_empty_profile(info: DeviceInfo) -> DeviceCapabilities:
    """Build the FR-013 fallback profile for an unrecognised device.

    Every capability resolves to ``UNKNOWN`` (the empty
    ``capabilities`` mapping defaults via
    :meth:`DeviceCapabilities.status_of`). The
    ``device_not_in_matrix`` note is the discriminator that
    :meth:`DeviceCapabilities.require` uses to raise
    ``reason="device_unrecognized"`` rather than the more specific
    ``reason="capability_unknown"``.
    """
    return DeviceCapabilities(
        device_class=info.model,
        firmware_version=info.firmware_version,
        capabilities={},
        field_aliases={},
        schema_shapes={},
        notes={"device_not_in_matrix": _DEVICE_NOT_IN_MATRIX_NOTE},
    )


class AkuvoxDevice:
    """Async context manager for communicating with an Akuvox device."""

    def __init__(
        self,
        host: str,
        auth: AuthConfig | None = None,
        timeout: int = 10,
        *,
        use_ssl: bool = False,
        verify_ssl: bool = True,
        request_delay: float = 0.25,
    ) -> None:
        """Initialize the device connection parameters.

        Args:
            host: Device host name or IP address.
            auth: Optional authentication configuration.
            timeout: Total request timeout in seconds.
            use_ssl: Whether to use HTTPS for requests.
            verify_ssl: Whether to verify TLS certificates.
            request_delay: Delay in seconds after each successful request.

        """
        self._http = AkuvoxHttpClient(
            host=host,
            auth=auth,
            timeout=timeout,
            use_ssl=use_ssl,
            verify_ssl=verify_ssl,
            request_delay=request_delay,
        )
        self._capabilities: DeviceCapabilities | None = None
        # Populated once by ``__aenter__`` from ``/api/system/info``.
        # ``get_info()`` returns this cached value on subsequent calls so
        # the device-info request observed at the ``async with`` boundary
        # is the only one that hits the network for static identification
        # data — see ``contracts/matrix-lookup.md`` §"Connect-time
        # integration".
        self._info: DeviceInfo | None = None
        # Per FR-021 (`spec.md`): integrator opt-in for ``UNKNOWN``
        # status capabilities. ``False`` (the default) makes the
        # per-method gate raise ``AkuvoxUnsupportedError(
        # reason="capability_unknown")`` for any UNKNOWN capability.
        # ``True`` lets the call through; the runtime envelope-level
        # classifier in ``_http.py`` then either succeeds or surfaces
        # the device's verbatim error. This setting NEVER bypasses
        # confirmed-``UNSUPPORTED`` capabilities.
        self.attempt_unknown_capability: bool = False

    @property
    def capabilities(self) -> DeviceCapabilities | None:
        """Return the effective capability profile for this connection.

        ``None`` until a profile is established. The profile is
        populated:

        1. By :meth:`__aenter__` from the curated
           :data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`
           (or the conservative-empty fallback for unrecognised
           devices) — Phase 2.
        2. Optionally replaced by an explicit
           :meth:`probe_capabilities` call, which merges probe
           observations on top of the matrix-derived profile per
           ``contracts/probe-api.md`` §"Edge cases" item 7.
        """
        return self._capabilities

    def _require_capabilities(self) -> DeviceCapabilities:
        """Return ``self._capabilities`` or raise if unestablished.

        Defensive helper for the per-method gate. ``__aenter__``
        always sets ``self._capabilities`` (matrix entry or
        conservative-empty fallback) before any service call can run,
        so a ``None`` here means the integrator is calling a service
        method without ever entering the async context manager — a
        usage error that should fail loudly.
        """
        if self._capabilities is None:
            msg = (
                "Device capabilities have not been initialised; "
                "use ``async with AkuvoxDevice(...) as device`` to "
                "enter the context manager before calling service "
                "methods"
            )
            raise AkuvoxUnsupportedError(
                msg,
                reason="device_unrecognized",
            )
        return self._capabilities

    async def probe_capabilities(
        self, *, timeout: float | None = None
    ) -> DeviceCapabilities:
        """Run a non-destructive capability probe against the connected device.

        Args:
            timeout: Per-request probe timeout in seconds. ``None``
                resolves to the documented default of ``5.0`` per
                ``contracts/probe-api.md`` §"Public surface".

        Returns:
            A new :class:`DeviceCapabilities` populated from observed
            responses. Replaces this connection's effective profile.
            If a matrix-derived profile already exists (from
            :meth:`__aenter__`), the probe result is merged on top
            using the 9-cell merge table from
            ``contracts/probe-api.md`` §"Edge cases" item 7: probe
            ``SUPPORTED`` / ``UNSUPPORTED`` always wins; probe
            ``UNKNOWN`` never regresses a matrix-confirmed
            ``SUPPORTED`` / ``UNSUPPORTED``.

        Raises:
            AkuvoxAuthenticationError: HTTP 401 on step 1.
            AkuvoxRequestError: HTTP 403 on step 1.
            AkuvoxConnectionError: Transport-level failure or HTTP
                5xx / non-401/403 4xx on step 1.
            AkuvoxParseError: Step 1 returned an unparsable
                ``/api/system/info`` payload.

        """
        resolved_timeout = 5.0 if timeout is None else timeout
        probe_result = await _probe_capabilities(self._http, timeout=resolved_timeout)
        merged = _merge_probe_with_matrix(self._capabilities, probe_result)
        self._capabilities = merged
        return merged

    async def __aenter__(self) -> AkuvoxDevice:
        """Open the underlying HTTP session and populate capabilities.

        Per ``contracts/matrix-lookup.md`` §"Connect-time integration",
        immediately after ``_http.__aenter__()`` we issue the existing
        ``/api/system/info`` call and look up the device's curated
        matrix entry. If the matrix has no entry for this
        (model, firmware) tuple, we install the conservative-empty
        FR-013 fallback profile that fails fast for every capability
        with ``reason="device_unrecognized"``.

        ``get_info()`` errors propagate (auth, parse, connection) so
        the integrator sees them at the ``async with`` boundary; the
        context manager has not "succeeded" if the device was not
        reachable for capability discovery.
        """
        await self._http.__aenter__()
        info = await self.get_info()
        self._info = info
        profile = lookup_capabilities(info)
        if profile is None:
            profile = _conservative_empty_profile(info)
        self._capabilities = profile
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the underlying HTTP session."""
        await self._http.__aexit__(exc_type, exc_val, exc_tb)

    async def get_info(self) -> DeviceInfo:
        """Retrieve device identification data.

        Not capability-gated: ``KEY_DISCOVERY`` is the prerequisite
        for matrix lookup itself, so gating it would create a
        chicken-and-egg loop. See ``data-model.md`` §"Explicit
        out-of-scope" and the ``test_every_public_device_method_has
        _capability_gate`` introspection audit's
        ``_INFRA_OUT_OF_SCOPE`` set.

        After ``__aenter__`` runs successfully, this method returns
        the cached :class:`DeviceInfo` from the connect-time discovery
        call rather than re-fetching. Device identification data
        (model, firmware, MAC) is static for the duration of a
        connection, so caching avoids a redundant round-trip while
        preserving the public surface.
        """
        if self._info is not None:
            return self._info
        data = await self._http.get("/api/system/info")
        return DeviceInfo.from_api_response(data)

    async def get_status(self) -> DeviceStatus:
        """Retrieve device operational status.

        Not capability-gated: this endpoint is part of the universal
        connect-time discovery surface (see ``get_info``).
        """
        data = await self._http.get("/api/system/status")
        return DeviceStatus.from_api_response(data)

    async def add_user(
        self,
        *,
        name: str,
        user_id: str,
        web_relay: str | None = None,
        schedule_relay: str,
        lift_floor_num: str,
        private_pin: str | None = None,
        card_code: str | None = None,
    ) -> None:
        """Add a local user to the device."""
        self._require_capabilities().require(
            Capability.USER_ADD,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import users

        await users.add_user(
            self._http,
            name=name,
            user_id=user_id,
            web_relay=web_relay,
            schedule_relay=schedule_relay,
            lift_floor_num=lift_floor_num,
            private_pin=private_pin,
            card_code=card_code,
        )

    async def list_users(self, *, page: int | None = None) -> list[User]:
        """List users from the device."""
        self._require_capabilities().require(
            Capability.USER_LIST,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import users

        return await users.list_users(self._http, page=page)

    async def modify_user(
        self,
        *,
        id: str,
        name: str | None = None,
        user_id: str | None = None,
        private_pin: str | None = None,
        card_code: str | None = None,
        web_relay: str | None = None,
        schedule_relay: str | None = None,
        lift_floor_num: str | None = None,
    ) -> None:
        """Modify an existing user on the device."""
        self._require_capabilities().require(
            Capability.USER_MODIFY,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import users

        await users.modify_user(
            self._http,
            id=id,
            name=name,
            user_id=user_id,
            private_pin=private_pin,
            card_code=card_code,
            web_relay=web_relay,
            schedule_relay=schedule_relay,
            lift_floor_num=lift_floor_num,
        )

    async def delete_user(self, *, id: str) -> None:
        """Delete a user from the device."""
        self._require_capabilities().require(
            Capability.USER_DELETE,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import users

        await users.delete_user(self._http, id=id)

    async def trigger_relay(
        self,
        *,
        num: int,
        mode: int = 0,
        level: int = 0,
        delay: int = 0,
        adapter: Capability | None = None,
    ) -> None:
        """Trigger a relay to unlock a door or gate.

        Adapter-gated (NOT via :meth:`DeviceCapabilities.require`):
        the gate is the ``RELAY_TRIGGER_ADAPTERS`` registry scan
        below. Device classes whose API variant returned
        "No handlers for this request" (IT83 indoor monitors, per
        issue #122) are dispatched to the FCGI variant; door phones
        (X916 / X915S / E18C) are dispatched to the API variant.

        This is the documented exception in the introspection audit
        (``_ADAPTER_GATED = {"trigger_relay"}``). See
        ``contracts/adapter-dispatch.md`` §"Dispatch order".

        Args:
            num: Relay number (positive integer).
            mode: 0 = Auto Close (default), 1 = Manual. Honoured by
                the API variant only — the FCGI variant rejects
                non-zero values with :class:`AkuvoxValidationError`.
            level: 0 = NO-COM (default), 1 = NC-COM. Same caveat.
            delay: Close delay in seconds (0-65535). Same caveat.
            adapter: Optional caller override pinning a specific
                variant (e.g. ``Capability.RELAY_TRIGGER_FCGI``).
                Must be ``SUPPORTED`` on the device — or ``UNKNOWN``
                with :attr:`attempt_unknown_capability` set — or the
                call raises :class:`AkuvoxUnsupportedError`.

        """
        # Local validation BEFORE adapter dispatch so callers see the
        # validation error regardless of the device class. This
        # mirrors the existing ``relay.trigger_relay`` validation
        # (see ``relay.py``); the adapter functions also re-validate
        # the FCGI-specific subset.
        from pylocal_akuvox.relay import _validate_relay_trigger_args

        _validate_relay_trigger_args(num=num, mode=mode, level=level, delay=delay)

        args = RelayTriggerArgs(num=num, mode=mode, level=level, delay=delay)
        caps = self._require_capabilities()

        if adapter is not None:
            chosen = self._resolve_override_adapter(caps, adapter)
        else:
            chosen = self._resolve_default_adapter(caps)

        variant = CAPABILITY_TO_VARIANT[chosen]
        fn = RELAY_TRIGGER_ADAPTERS.get((chosen, variant))
        if fn is None:
            msg = f"No adapter registered for {chosen.value} on {caps.device_class}"
            raise AkuvoxUnsupportedError(
                msg,
                capability=chosen,
                device_class=caps.device_class,
                reason="adapter_missing",
            )
        await fn(self._http, args)

    def _resolve_override_adapter(
        self, caps: DeviceCapabilities, adapter: Capability
    ) -> Capability:
        """Resolve a caller-supplied ``adapter=`` override to a chosen capability.

        Per ``contracts/adapter-dispatch.md`` §"Dispatch order" step
        1: an explicit override picks the requested variant unless
        the device confirms it ``UNSUPPORTED`` (always raises) or
        ``UNKNOWN`` without the integrator opt-in (raises unless
        ``attempt_unknown_capability=True``).
        """
        status = caps.status_of(adapter)
        if status is CapabilityStatus.UNSUPPORTED:
            msg = (
                f"Adapter {adapter.value} requested but device "
                f"{caps.device_class} confirmed does not support it"
            )
            raise AkuvoxUnsupportedError(
                msg,
                capability=adapter,
                device_class=caps.device_class,
                reason="capability_missing",
            )
        if status is CapabilityStatus.UNKNOWN and not self.attempt_unknown_capability:
            msg = (
                f"Adapter {adapter.value} requested but its status is "
                f"unknown on {caps.device_class}; add a matrix entry "
                f"or set device.attempt_unknown_capability=True"
            )
            raise AkuvoxUnsupportedError(
                msg,
                capability=adapter,
                device_class=caps.device_class,
                reason="capability_unknown",
            )
        return adapter

    def _resolve_default_adapter(self, caps: DeviceCapabilities) -> Capability:
        """Walk the preference list and pick the first ``SUPPORTED`` variant.

        Per ``contracts/adapter-dispatch.md`` §"Dispatch order" step
        2: ``UNKNOWN`` does NOT auto-promote — the wrong variant
        firing or failing to fire a relay is the exact UX failure the
        three-valued model is written to prevent. If no variant is
        ``SUPPORTED`` we raise either ``capability_unknown`` (at
        least one variant has UNKNOWN status) or
        ``capability_missing`` (every variant is UNSUPPORTED).
        """
        for candidate in RELAY_TRIGGER_PREFERENCE:
            if caps.status_of(candidate) is CapabilityStatus.SUPPORTED:
                return candidate

        any_unknown = any(
            caps.status_of(c) is CapabilityStatus.UNKNOWN
            for c in RELAY_TRIGGER_PREFERENCE
        )
        if any_unknown:
            reason = "capability_unknown"
            msg_tail = (
                "; add a matrix entry or pass adapter= explicitly with "
                "device.attempt_unknown_capability=True"
            )
        else:
            reason = "capability_missing"
            msg_tail = ""
        msg = (
            f"Device {caps.device_class} has no supported "
            f"relay-trigger variant{msg_tail}"
        )
        raise AkuvoxUnsupportedError(
            msg,
            capability=Capability.RELAY_TRIGGER_API,
            device_class=caps.device_class,
            reason=reason,
        )

    async def get_relay_status(self) -> dict[str, Any]:
        """Retrieve current relay states from the device."""
        self._require_capabilities().require(
            Capability.RELAY_STATUS,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import relay

        return await relay.get_relay_status(self._http)

    async def get_device_config(self) -> DeviceConfig:
        """Retrieve full device configuration."""
        self._require_capabilities().require(
            Capability.DEVICE_CONFIG_GET,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import config

        return await config.get_device_config(self._http)

    async def set_device_config(self, settings: dict[str, str]) -> None:
        """Update device configuration settings."""
        self._require_capabilities().require(
            Capability.DEVICE_CONFIG_SET,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import config

        await config.set_device_config(self._http, settings)

    async def add_schedule(
        self,
        *,
        schedule_type: str,
        name: str | None = None,
        week: str | None = None,
        daily: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
        sun: str | None = None,
        mon: str | None = None,
        tue: str | None = None,
        wed: str | None = None,
        thur: str | None = None,
        fri: str | None = None,
        sat: str | None = None,
    ) -> None:
        """Add an access schedule to the device."""
        self._require_capabilities().require(
            Capability.SCHEDULE_ADD,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import schedules

        await schedules.add_schedule(
            self._http,
            schedule_type=schedule_type,
            name=name,
            week=week,
            daily=daily,
            date_start=date_start,
            date_end=date_end,
            time_start=time_start,
            time_end=time_end,
            sun=sun,
            mon=mon,
            tue=tue,
            wed=wed,
            thur=thur,
            fri=fri,
            sat=sat,
        )

    async def list_schedules(self, *, page: int | None = None) -> list[AccessSchedule]:
        """List schedules from the device."""
        self._require_capabilities().require(
            Capability.SCHEDULE_LIST,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import schedules

        return await schedules.list_schedules(self._http, page=page)

    async def modify_schedule(
        self,
        *,
        id: str,
        name: str | None = None,
        schedule_type: str | None = None,
        week: str | None = None,
        daily: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
        sun: str | None = None,
        mon: str | None = None,
        tue: str | None = None,
        wed: str | None = None,
        thur: str | None = None,
        fri: str | None = None,
        sat: str | None = None,
    ) -> None:
        """Modify an existing schedule on the device."""
        self._require_capabilities().require(
            Capability.SCHEDULE_MODIFY,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import schedules

        await schedules.modify_schedule(
            self._http,
            id=id,
            name=name,
            schedule_type=schedule_type,
            week=week,
            daily=daily,
            date_start=date_start,
            date_end=date_end,
            time_start=time_start,
            time_end=time_end,
            sun=sun,
            mon=mon,
            tue=tue,
            wed=wed,
            thur=thur,
            fri=fri,
            sat=sat,
        )

    async def delete_schedule(self, *, id: str) -> None:
        """Delete a schedule from the device."""
        self._require_capabilities().require(
            Capability.SCHEDULE_DELETE,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import schedules

        await schedules.delete_schedule(self._http, id=id)

    async def list_groups(
        self,
        *,
        page: int | None = None,
    ) -> list[Group]:
        """List groups from the device."""
        self._require_capabilities().require(
            Capability.GROUP_LIST,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import groups

        return await groups.list_groups(self._http, page=page)

    async def add_group(self, *, name: str) -> None:
        """Add a group to the device."""
        self._require_capabilities().require(
            Capability.GROUP_ADD,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import groups

        await groups.add_group(self._http, name=name)

    async def modify_group(
        self,
        *,
        id: str,
        name: str,
    ) -> None:
        """Modify an existing group on the device."""
        self._require_capabilities().require(
            Capability.GROUP_MODIFY,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import groups

        await groups.modify_group(self._http, id=id, name=name)

    async def delete_group(self, *, id: str) -> None:
        """Delete a group from the device."""
        self._require_capabilities().require(
            Capability.GROUP_DELETE,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import groups

        await groups.delete_group(self._http, id=id)

    async def list_contacts(
        self,
        *,
        page: int | None = None,
    ) -> list[Contact]:
        """List contacts from the device."""
        self._require_capabilities().require(
            Capability.CONTACT_LIST,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import contacts

        return await contacts.list_contacts(self._http, page=page)

    async def add_contact(
        self,
        *,
        name: str,
        phone: str | None = None,
        group: str | None = None,
    ) -> None:
        """Add a contact to the device address book."""
        self._require_capabilities().require(
            Capability.CONTACT_ADD,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import contacts

        await contacts.add_contact(
            self._http,
            name=name,
            phone=phone,
            group=group,
        )

    async def modify_contact(
        self,
        *,
        id: str,
        name: str | None = None,
        phone: str | None = None,
        group: str | None = None,
    ) -> None:
        """Modify an existing contact on the device."""
        self._require_capabilities().require(
            Capability.CONTACT_MODIFY,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import contacts

        await contacts.modify_contact(
            self._http,
            id=id,
            name=name,
            phone=phone,
            group=group,
        )

    async def delete_contact(self, *, id: str | list[str]) -> None:
        """Delete one or more contacts from the device."""
        self._require_capabilities().require(
            Capability.CONTACT_DELETE,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import contacts

        await contacts.delete_contact(self._http, id=id)

    async def get_door_logs(self, *, page: int | None = None) -> list[DoorLogEntry]:
        """Retrieve door access logs from the device."""
        self._require_capabilities().require(
            Capability.LOG_DOOR,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import logs

        return await logs.get_door_logs(self._http, page=page)

    async def get_call_logs(self, *, page: int | None = None) -> list[CallLogEntry]:
        """Retrieve call logs from the device."""
        self._require_capabilities().require(
            Capability.LOG_CALL,
            allow_unknown=self.attempt_unknown_capability,
        )
        from pylocal_akuvox import logs

        return await logs.get_call_logs(self._http, page=page)


def _merge_probe_with_matrix(
    matrix: DeviceCapabilities | None,
    probe: DeviceCapabilities,
) -> DeviceCapabilities:
    """Merge a probe-derived profile on top of a matrix-derived profile.

    Per ``contracts/probe-api.md`` §"Edge cases" item 7 / 9-cell merge
    table:

    * Probe ``SUPPORTED`` / ``UNSUPPORTED`` always wins (newer
      first-hand observation).
    * Probe ``UNKNOWN`` never regresses a matrix-confirmed
      ``SUPPORTED`` / ``UNSUPPORTED`` (absence of evidence is not
      evidence of absence).
    * Capabilities the probe did not touch carry through unchanged
      from the matrix.

    The probe deliberately omits write capabilities (FR-003: "no
    write inference from read signals"), so write capabilities in
    ``matrix.capabilities`` are preserved verbatim — the read-side
    UNSUPPORTED signal of one endpoint never propagates to its
    sibling write capability.

    Returns the probe profile unchanged when ``matrix`` is ``None``
    (probe-only flow with no matrix entry — the integrator either
    has an unrecognised device or constructed the device without
    entering the context manager first).
    """
    if matrix is None:
        return probe

    # Start from the matrix mapping (preserves write capabilities and
    # any capabilities the probe did not exercise) and overlay probe
    # observations using the 9-cell rule.
    merged: dict[Capability, CapabilityStatus] = dict(matrix.capabilities)
    for capability, probe_status in probe.capabilities.items():
        if probe_status is CapabilityStatus.UNKNOWN:
            # Probe UNKNOWN never regresses a matrix-confirmed value.
            # If the matrix has no entry, ``status_of`` would already
            # default to UNKNOWN — so leaving the slot absent is
            # equivalent and keeps the merged mapping minimal.
            if capability not in merged:
                merged[capability] = CapabilityStatus.UNKNOWN
            continue
        # Probe SUPPORTED or UNSUPPORTED always wins.
        merged[capability] = probe_status

    # field_aliases / schema_shapes / notes: probe observations win
    # for keys the probe explicitly recorded, otherwise the matrix
    # value carries through. The probe never deletes entries.
    field_aliases = dict(matrix.field_aliases)
    field_aliases.update(probe.field_aliases)
    schema_shapes = dict(matrix.schema_shapes)
    schema_shapes.update(probe.schema_shapes)
    notes = dict(matrix.notes)
    notes.update(probe.notes)
    # The conservative-empty profile installed by ``__aenter__`` for an
    # unrecognised device carries a ``"device_not_in_matrix"`` discriminator
    # note that ``DeviceCapabilities.require`` keys off to choose
    # ``reason="device_unrecognized"`` (capabilities.py). Once a probe has
    # successfully enumerated the device, that condition no longer applies:
    # a still-UNKNOWN capability should raise ``capability_unknown`` (probed
    # but indeterminate), not ``device_unrecognized`` (never probed). Strip
    # the discriminator key before constructing the merged profile.
    notes.pop("device_not_in_matrix", None)

    return DeviceCapabilities(
        device_class=probe.device_class,
        firmware_version=probe.firmware_version,
        capabilities=merged,
        field_aliases=field_aliases,
        schema_shapes=schema_shapes,
        notes=notes,
        # Provenance comes from the matrix entry (the probe never
        # writes provenance per ``contracts/probe-api.md`` §"Provenance
        # produced by the probe").
        provenance=matrix.provenance,
    )
