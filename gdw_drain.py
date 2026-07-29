"""Compatibility entry point for the single generation-fenced GDW drain."""

from __future__ import annotations

from typing import Any, Dict, Optional

from gdw_runtime import drain_once
from gdw_workspace import GDWWorkspace


def drain_effects(
    workspace: GDWWorkspace,
    *,
    limit: int = 100,
    worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Delegate to the runtime's only claim, export, and completion path."""

    report = drain_once(
        limit=limit,
        worker_id=worker_id,
        workspace=workspace,
    )
    integrity = workspace.integrity(global_scope=True)
    return {
        "schema": "szl.gdw-effect-drain/v2",
        **report,
        "integrity_ok": integrity["ok"],
        "database_generation_id": integrity["database_generation_id"],
        "credential_values_recorded": False,
    }
