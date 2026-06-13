# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""a11oy.harvest — vendored wasted-energy harvest module.

Doctrine (binding):
  - NO free-energy / over-unity. Harvests ALREADY-WASTED grid energy only.
  - joules_label ALWAYS "sample" off-box; only on-box NVML flips it to "measured".
  - All feeds are FREE and PUBLIC (no token).
  - Reactive turns are NEVER gated by harvest posture.
  - Locked-8 theorems untouched.
"""
from .wasted_energy_harvest import (
    current_harvest_posture,
    harvest_provenance,
    scan_world_renshare,
    HarvestPosture,
    FeedReading,
    POSTURE_RANK,
)
from .harvest_budget import plan_soak, SoakPlan

__all__ = [
    "current_harvest_posture",
    "harvest_provenance",
    "scan_world_renshare",
    "HarvestPosture",
    "FeedReading",
    "POSTURE_RANK",
    "plan_soak",
    "SoakPlan",
]
