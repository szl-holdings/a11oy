# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Task-shape routing for bounded agent orchestration.

The router is intentionally advisory. It chooses an execution topology from
measured task properties; authorization remains in the existing policy and
receipt gates.
"""
from __future__ import annotations

from typing import Any


def classify_task(
    *,
    independent_units: int,
    dependency_depth: int,
    tool_count: int,
    proof_chain: bool = False,
    human_approval_required: bool = False,
) -> dict[str, Any]:
    """Select a topology without treating more agents as universally better.

    Parallel evidence mode is reserved for genuinely independent work with a
    shallow dependency graph. Proof, receipt, release, and human-approval
    chains remain centralized and sequential.
    """
    values = {
        "independent_units": independent_units,
        "dependency_depth": dependency_depth,
        "tool_count": tool_count,
    }
    if any(not isinstance(value, int) or value < 0 for value in values.values()):
        raise ValueError("task-shape counts must be non-negative integers")
    if proof_chain or human_approval_required:
        mode = "CENTRAL_SEQUENTIAL"
        reason = "proof_or_human_boundary"
    elif independent_units > 1 and dependency_depth <= 1 and tool_count <= 12:
        mode = "PARALLEL_EVIDENCE"
        reason = "decomposable_low_dependency"
    else:
        mode = "CENTRAL_SEQUENTIAL"
        reason = "sequential_or_tool_dense"
    return {
        "schema": "szl.task-shape/v1",
        "mode": mode,
        "reason": reason,
        "independent_units": independent_units,
        "dependency_depth": dependency_depth,
        "tool_count": tool_count,
        "proof_chain": proof_chain,
        "human_approval_required": human_approval_required,
        "authorization_effect": "NONE",
    }
