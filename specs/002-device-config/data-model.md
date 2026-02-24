<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Device Configuration Management

**Feature**: 002-device-config
**Date**: 2026-02-24

## Entities

### RelayConfig

Represents the complete relay configuration for an Akuvox device.
Frozen dataclass consistent with all existing models.

**Fields** (initial — expanded after live device testing):

- `hold_delay_a` (`str`): Door hold time for relay A
  (seconds). Source: `Config.DoorSetting.RELAY.HoldDelayA`
- `trig_delay_a` (`str`): Trigger delay for relay A
  (seconds). Source: `Config.DoorSetting.RELAY.TrigDelayA`
- `relay_name_a` (`str`): Display name for relay A.
  Source: `Config.DoorSetting.RELAY.RelayNameA`
- `hold_delay_b` (`str | None`): Door hold time for relay B
  (optional). Source: `Config.DoorSetting.RELAY.HoldDelayB`
- `trig_delay_b` (`str | None`): Trigger delay for relay B
  (optional). Source: `Config.DoorSetting.RELAY.TrigDelayB`
- `relay_name_b` (`str | None`): Display name for relay B
  (optional). Source: `Config.DoorSetting.RELAY.RelayNameB`
- `extra` (`dict[str, str] | None`): Additional keys returned by
  the device that are not part of the known field set. Defaults to
  `None` when no unknown keys are present.

**Notes**:

- All values are strings matching the device API convention
  (consistent with how autop-format keys are transmitted).
- Optional fields (relay B) default to `None` for single-relay
  devices.
- The exact set of fields will be confirmed during Phase 1 live
  device testing and expanded as needed. Additional keys
  discovered from the GET response will be added.
- HTTP relay access and other undocumented keys may appear;
  unknown keys are stored in an `extra` dict.

### Methods

**`from_api_response(data: dict[str, Any]) -> RelayConfig`**

Class method. Parses the envelope `data` dict from
`GET /api/relay/get`. Maps autop-format keys to snake_case
attributes. Unknown keys stored in `extra`.

**`to_api_payload(**overrides: str) -> dict[str, Any]`**

Static method. Produces the `{target, action, data}` body for
`POST /api/relay/set` from the provided keyword arguments.
Only includes keys present in `overrides`, allowing partial
updates. Converts snake_case attribute names back to
autop-format keys.

**`keys() -> list[str]`**

Instance method. Returns the list of autop-format key names that
this configuration contains, enabling key discovery (US3).

## Key Mapping Registry

A module-level dict in `config.py` maps between snake_case
attribute names and autop-format keys:

```text
KEY_MAP = {
    "hold_delay_a": "Config.DoorSetting.RELAY.HoldDelayA",
    "trig_delay_a": "Config.DoorSetting.RELAY.TrigDelayA",
    "relay_name_a": "Config.DoorSetting.RELAY.RelayNameA",
    ...
}
```

This registry serves three purposes:

1. Parsing GET responses (autop → snake_case)
2. Building SET requests (snake_case → autop)
3. Key discovery (US3)

## Relationships

```text
AkuvoxDevice ──delegates──▶ config.get_relay_config()
                            config.set_relay_config()
                                │
                                ▼
                          AkuvoxHttpClient
                                │
                                ▼
                     GET /api/relay/get
                     POST /api/relay/set
                                │
                                ▼
                          RelayConfig
```

## Validation Rules

- `set_relay_config()` MUST receive at least one key-value pair
  (FR-004). Empty updates raise `AkuvoxValidationError`.
- Key names MUST be valid entries in `KEY_MAP`. Unknown keys
  raise `AkuvoxValidationError`.
- Values are strings (matching device API convention). No
  additional type validation is performed — the device reports
  errors for invalid values.
