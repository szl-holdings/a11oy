# SPDX-License-Identifier: Apache-2.0
"""Canonical A11oy environment admission for the ORO control plane."""
from __future__ import annotations

import os
from collections.abc import MutableMapping

from .core import OROStateError


def require_production_environment(
    environment: MutableMapping[str, str] | None = None,
) -> str:
    """Default the canonical mount to production and reject weaker overrides."""
    selected = os.environ if environment is None else environment
    configured = selected.get("SZL_ORO_ENV")
    if configured is None:
        selected["SZL_ORO_ENV"] = "production"
        return "production"
    if configured.strip().lower() != "production":
        raise OROStateError("canonical ORO mount requires SZL_ORO_ENV=production")
    selected["SZL_ORO_ENV"] = "production"
    return "production"
