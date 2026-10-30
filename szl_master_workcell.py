#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
"""Read-only master implementation workcell status.

The workcell artifact is a source-bound coordination report.  This module
serves it without probing providers, invoking inference, signing receipts, or
granting execution authority.  A missing or malformed artifact is an honest
503/UNAVAILABLE response; it is never replaced with an empty or green payload.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse


BASE = Path(__file__).resolve().parent
ARTIFACT_PATH = BASE / "data" / "master_workcell_dag_20261027.json"
SCHEMA = "szl.master-workcell.v1"
HONEST_LABELS = frozenset({
    "MEASURED", "REPORTED", "DECLARED", "SIMULATED", "SAMPLE", "MODELED",
    "ROADMAP", "UNKNOWN", "UNAVAILABLE", "BLOCKED",
})
REQUIRED_KEYS = frozenset({
    "schema", "dag_schema", "workcell_id", "generated_at", "repository", "doctrine",
    "status", "label",
    "integration_summary", "nodes", "edges", "blockers", "next_milestones",
})


class WorkcellArtifactError(ValueError):
    """The committed coordination artifact does not satisfy its read contract."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkcellArtifactError("duplicate object key")
        result[key] = value
    return result


def _label(value: Any, field: str) -> str:
    if type(value) is not str or value not in HONEST_LABELS:
        raise WorkcellArtifactError(f"{field} has an invalid honesty label")
    return value


def _validate(payload: Any) -> dict[str, Any]:
    if type(payload) is not dict or set(payload) != REQUIRED_KEYS:
        raise WorkcellArtifactError("artifact has an invalid top-level shape")
    if payload.get("schema") != SCHEMA:
        raise WorkcellArtifactError("artifact schema mismatch")
    if payload.get("dag_schema") != "szl.workcell.dag/v1":
        raise WorkcellArtifactError("artifact DAG schema mismatch")
    _label(payload.get("status"), "status")
    _label(payload.get("label"), "label")
    if type(payload.get("repository")) is not dict:
        raise WorkcellArtifactError("repository metadata is missing")
    doctrine = payload.get("doctrine")
    if type(doctrine) is not dict:
        raise WorkcellArtifactError("doctrine metadata is missing")
    locked = doctrine.get("locked_formula_ids")
    if locked != ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]:
        raise WorkcellArtifactError("locked formula set is not exact")
    if doctrine.get("locked_formula_count") != 8:
        raise WorkcellArtifactError("locked formula count is not eight")
    if doctrine.get("trust_ceiling") != 0.97:
        raise WorkcellArtifactError("trust ceiling is not 0.97")
    summary = payload.get("integration_summary")
    if type(summary) is not dict:
        raise WorkcellArtifactError("integration summary is missing")
    _label(summary.get("overall"), "integration_summary.overall")
    if payload.get("status") != summary.get("overall"):
        raise WorkcellArtifactError("top-level status disagrees with integration summary")
    for key, item in summary.items():
        if key == "overall":
            continue
        if type(item) is not dict:
            raise WorkcellArtifactError(f"integration summary {key} is not an object")
        _label(item.get("status"), f"integration_summary.{key}.status")
        if "evidence_class" in item:
            _label(item.get("evidence_class"), f"integration_summary.{key}.evidence_class")
    nodes = payload.get("nodes")
    if type(nodes) is not list or not nodes:
        raise WorkcellArtifactError("nodes must be a non-empty list")
    ids = set()
    for index, node in enumerate(nodes):
        if type(node) is not dict or type(node.get("id")) is not str:
            raise WorkcellArtifactError(f"node {index} is invalid")
        if node["id"] in ids:
            raise WorkcellArtifactError("node IDs must be unique")
        ids.add(node["id"])
        _label(node.get("status"), f"nodes[{index}].status")
        if "evidence_class" in node:
            _label(node.get("evidence_class"), f"nodes[{index}].evidence_class")
        if type(node.get("depends_on")) is not list:
            raise WorkcellArtifactError(f"nodes[{index}].depends_on must be a list")
    edges = payload.get("edges")
    if type(edges) is not list:
        raise WorkcellArtifactError("edges must be a list")
    for index, edge in enumerate(edges):
        if (type(edge) is not dict or type(edge.get("from")) is not str
                or type(edge.get("to")) is not str or type(edge.get("relation")) is not str):
            raise WorkcellArtifactError(f"edge {index} is invalid")
        if edge["from"] not in ids or edge["to"] not in ids:
            raise WorkcellArtifactError(f"edge {index} references an unknown node")
    if type(payload.get("blockers")) is not list or type(payload.get("next_milestones")) is not list:
        raise WorkcellArtifactError("blockers and next_milestones must be lists")
    return payload


def load_artifact(path: Path | None = None) -> tuple[dict[str, Any], str]:
    """Load and validate the immutable-in-image JSON artifact."""
    path = ARTIFACT_PATH if path is None else path
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    return _validate(payload), digest


def _unavailable(reason: str) -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "label": "UNAVAILABLE",
            "read_only": True,
            "reason": reason,
        },
        status_code=503,
        headers={"Cache-Control": "no-store"},
    )


def register(app, ns: str = "a11oy") -> dict[str, Any]:
    """Register the GET-only workcell status endpoint before catch-alls."""
    marker = "master_workcell_status_registered"
    if getattr(app.state, marker, False):
        return {"registered": True, "route": f"/api/{ns}/v1/workcell/status"}

    router = APIRouter()

    @router.get(f"/api/{ns}/v1/workcell/status")
    def workcell_status():
        try:
            payload, digest = load_artifact()
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            return _unavailable("workcell artifact unavailable or invalid")
        response = dict(payload)
        response.update({
            "ok": True,
            "read_only": True,
            "status": payload["status"],
            "label": payload["label"],
            "artifact_sha256": digest,
            "authority": "source_report",
            "runtime_readiness": "UNKNOWN",
            "provider_publication": "UNKNOWN",
        })
        return JSONResponse(response, headers={"Cache-Control": "no-store"})

    existing = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[existing:]
    del app.router.routes[existing:]
    app.router.routes[0:0] = added
    setattr(app.state, marker, True)
    return {"registered": True, "route": f"/api/{ns}/v1/workcell/status", "routeCount": len(added)}
