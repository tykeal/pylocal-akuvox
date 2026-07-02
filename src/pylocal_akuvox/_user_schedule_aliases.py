# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Helpers for normalizing user schedule alias payloads."""

from __future__ import annotations

from typing import Any

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES


def _strip_schedule_aliases(current: dict[str, Any], all_aliases: list[str]) -> None:
    """Remove every known schedule alias from ``current``."""
    for alias in all_aliases:
        current.pop(alias, None)


def _write_schedule_aliases(
    current: dict[str, Any],
    write_aliases: tuple[str, ...],
    schedule_relay: object,
) -> None:
    """Write ``schedule_relay`` under every configured write alias."""
    for alias in write_aliases:
        current[alias] = schedule_relay


def _find_existing_schedule(
    current: dict[str, Any],
    read_aliases: tuple[str, ...],
) -> tuple[bool, str, object]:
    """Return whether a schedule was found plus its alias and value."""
    for alias in read_aliases:
        if alias in current:
            return True, alias, current[alias]
    return False, "", ""


def _preserve_schedule_without_write_alias(
    current: dict[str, Any],
    *,
    existing_schedule_alias: str,
    all_aliases: list[str],
) -> None:
    """Preserve primary schedule keys when no write alias is available."""
    aliases_to_keep = {
        alias for alias in DEFAULT_USER_FIELD_ALIASES.write if alias in current
    }
    if not aliases_to_keep:
        aliases_to_keep = {existing_schedule_alias}
    for alias in all_aliases:
        if alias not in aliases_to_keep:
            current.pop(alias, None)
