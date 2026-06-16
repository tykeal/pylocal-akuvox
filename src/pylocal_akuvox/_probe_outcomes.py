# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Outcome enumeration and classification markers for the capability probe.

Authored under spec ``010-capability-probe-split`` (issue #141). This
module owns the discrete probe-step outcome vocabulary and the message
markers used by :mod:`pylocal_akuvox._probe_classifiers` to classify
device responses. It is the leaf of the probe-side dependency graph
and depends only on the standard library.
"""

from __future__ import annotations

import enum


class _ProbeOutcome(enum.Enum):
    """Discrete classification of a single probe-step response."""

    SUPPORTED = "supported"
    UNSUPPORTED_NO_HANDLER = "unsupported_no_handler"
    UNSUPPORTED_API = "unsupported_api"
    UNSUPPORTED_ACTION = "unsupported_action"
    INDETERMINATE = "indeterminate"


_NO_HANDLER_MARKERS = (
    "no handlers for this request",
    "no hanlders for this request",  # device typo (codespell:ignore)
)
_API_UNSUPPORTED_MARKER = "api unsupported"
_ACTION_UNSUPPORTED_MARKERS = (
    "unsupported action",
    "unsupport action",  # device typo (codespell:ignore)
)


__all__ = [
    "_ACTION_UNSUPPORTED_MARKERS",
    "_API_UNSUPPORTED_MARKER",
    "_NO_HANDLER_MARKERS",
    "_ProbeOutcome",
]
