# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Default user field-alias constant for the Akuvox device API.

Split out from the former ``pylocal_akuvox.capabilities`` module per
spec ``009-capabilities-module-split`` so each focused submodule stays
under the project's 400-line aislop ``file-too-large`` threshold.

This module exports the single fallback constant used by the user
service functions in :mod:`pylocal_akuvox.users` (and the
:meth:`User.from_api_response` parser) when no capability record is
supplied for the ``schedule_relay`` logical field:

* :data:`DEFAULT_USER_FIELD_ALIASES` — the no-kwarg
  ``schedule_relay`` fallback chain.
"""

from __future__ import annotations

from pylocal_akuvox._capability_profile import FieldAliases

#: Default ``FieldAliases`` for the ``schedule_relay`` logical field.
#:
#: Used as the no-kwarg fallback when ``User.from_api_response``,
#: ``users.add_user``, ``users.modify_user``, and the corresponding
#: ``AkuvoxDevice`` wrapper methods are invoked without a capability
#: record (or with a capability record whose ``field_aliases`` mapping
#: does not include ``"schedule_relay"``). Matches today's hardcoded
#: chain byte-for-byte so direct service-function callers and legacy
#: ``User.from_api_response(data)`` callers see no observable change
#: post-refactor (FR-016 / SC-008). See ``research.md`` Decision 3
#: §"Read side" and §"Write side".
DEFAULT_USER_FIELD_ALIASES = FieldAliases(
    read=("ScheduleRelay", "Schedule-Relay", "Schedule"),
    write=("ScheduleRelay", "Schedule-Relay"),
)


__all__ = ["DEFAULT_USER_FIELD_ALIASES"]
