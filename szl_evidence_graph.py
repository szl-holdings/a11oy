# SPDX-License-Identifier: Apache-2.0
"""Canonical Evidence Graph (CEG) primitives.

The CEG is deliberately small and append-only.  It does not mint readiness,
signatures, energy measurements, or authority.  It turns independently
observed facts into deterministic, hash-addressed edges that can be queried,
replayed, and compared across deployments.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA = "szl.evidence-edge/v1"
GRAPH_SCHEMA = "szl.evidence-graph/v1"
VERDICTS = frozenset({"VERIFIED", "OBSERVED", "DEGRADED", "UNAVAILABLE"})
_MAX_EDGES = 256
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> str:
    """Return the byte-stable JSON representation used for receipt IDs."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: Any) -> str:
    """Hash JSON values canonically, or bytes directly."""
    if isinstance(value, bytes):
        raw = value
    else:
        raw = canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_map(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _validate_sha256(value: str | None, field: str) -> None:
    if value is not None and value != "" and not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class EvidenceEdge:
    """One immutable, content-addressed edge in the evidence graph."""

    subject: Mapping[str, Any]
    source_revision: str | None = None
    artifact_sha256: str | None = None
    runtime: Mapping[str, Any] = None  # type: ignore[assignment]
    evidence: Mapping[str, Any] = None  # type: ignore[assignment]
    authority: Mapping[str, Any] = None  # type: ignore[assignment]
    parents: tuple[str, ...] = ()
    invariant_ids: tuple[str, ...] = ()
    verdict: str = "OBSERVED"
    reason: str | None = None

    def __post_init__(self) -> None:
        subject = _clean_map(self.subject)
        runtime = _clean_map(self.runtime)
        evidence = _clean_map(self.evidence)
        authority = _clean_map(self.authority)
        if not subject.get("kind") or not subject.get("id"):
            raise ValueError("subject.kind and subject.id are required")
        if self.verdict not in VERDICTS:
            raise ValueError(f"unsupported verdict: {self.verdict}")
        if self.source_revision is not None and not self.source_revision:
            raise ValueError("source_revision cannot be empty")
        _validate_sha256(self.artifact_sha256, "artifact_sha256")
        if not isinstance(authority.get("execution_authorized", False), bool):
            raise ValueError("authority.execution_authorized must be boolean")
        if len(self.parents) > 64:
            raise ValueError("an edge may reference at most 64 parents")
        if len(self.invariant_ids) > 64:
            raise ValueError("an edge may reference at most 64 invariants")
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "parents", tuple(sorted(set(self.parents))))
        object.__setattr__(self, "invariant_ids", tuple(sorted(set(self.invariant_ids))))

    def payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "subject": dict(self.subject),
            "source_revision": self.source_revision,
            "artifact_sha256": self.artifact_sha256,
            "runtime": dict(self.runtime),
            "evidence": dict(self.evidence),
            "authority": dict(self.authority),
            "parents": list(self.parents),
            "invariant_ids": list(self.invariant_ids),
            "verdict": self.verdict,
            "reason": self.reason,
        }

    @property
    def receipt_id(self) -> str:
        return "edge-" + sha256_hex(self.payload())

    def as_dict(self) -> dict[str, Any]:
        result = self.payload()
        result["receipt_id"] = self.receipt_id
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceEdge":
        if value.get("schema", SCHEMA) != SCHEMA:
            raise ValueError("unsupported evidence edge schema")
        edge = cls(
            subject=_clean_map(value.get("subject")),
            source_revision=value.get("source_revision"),
            artifact_sha256=value.get("artifact_sha256"),
            runtime=_clean_map(value.get("runtime")),
            evidence=_clean_map(value.get("evidence")),
            authority=_clean_map(value.get("authority")),
            parents=tuple(value.get("parents") or ()),
            invariant_ids=tuple(value.get("invariant_ids") or ()),
            verdict=value.get("verdict", "OBSERVED"),
            reason=value.get("reason"),
        )
        supplied_id = value.get("receipt_id")
        if supplied_id is not None and supplied_id != edge.receipt_id:
            raise ValueError("receipt_id does not match canonical edge payload")
        return edge


def _coerce_edges(edges: Iterable[EvidenceEdge | Mapping[str, Any]]) -> list[EvidenceEdge]:
    result = []
    for item in edges:
        result.append(item if isinstance(item, EvidenceEdge) else EvidenceEdge.from_dict(item))
    return result


def graph_snapshot(
    edges: Iterable[EvidenceEdge | Mapping[str, Any]],
    *,
    max_edges: int = _MAX_EDGES,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build a bounded, deterministic graph summary.

    Edges are sorted by receipt ID before bounding, so two readers with the same
    input produce the same digest.  Bounding is explicit in the response and
    never presented as a complete ledger.
    """
    if not isinstance(max_edges, int) or not 1 <= max_edges <= _MAX_EDGES:
        raise ValueError(f"max_edges must be between 1 and {_MAX_EDGES}")
    normalized = _coerce_edges(edges)
    ordered = sorted({edge.receipt_id: edge for edge in normalized}.values(), key=lambda e: e.receipt_id)
    bounded = ordered[:max_edges]
    included_ids = {edge.receipt_id for edge in bounded}
    parent_ids = {parent for edge in bounded for parent in edge.parents}
    verdict_counts = {name: 0 for name in sorted(VERDICTS)}
    invariant_counts: dict[str, int] = {}
    for edge in bounded:
        verdict_counts[edge.verdict] += 1
        for invariant in edge.invariant_ids:
            invariant_counts[invariant] = invariant_counts.get(invariant, 0) + 1
    edge_dicts = [edge.as_dict() for edge in bounded]
    digest = sha256_hex({"schema": GRAPH_SCHEMA, "edges": edge_dicts})
    return {
        "schema": GRAPH_SCHEMA,
        "bounded": len(ordered) > len(bounded),
        "max_edges": max_edges,
        "edge_count": len(bounded),
        "total_input_edges": len(ordered),
        "receipt_head": bounded[-1].receipt_id if bounded else None,
        "dangling_parent_count": len(parent_ids - included_ids),
        "verdict_counts": verdict_counts,
        "invariant_counts": dict(sorted(invariant_counts.items())),
        "digest_sha256": digest,
        "observed_at": observed_at or _utc_now(),
        "edges": edge_dicts,
    }


def query_snapshot(
    snapshot: Mapping[str, Any],
    *,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    verdict: str | None = None,
    invariant_id: str | None = None,
) -> dict[str, Any]:
    """Filter a snapshot without changing its original graph digest."""
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError(f"unsupported verdict: {verdict}")
    selected = []
    for item in snapshot.get("edges", []):
        subject = item.get("subject", {})
        if subject_kind and subject.get("kind") != subject_kind:
            continue
        if subject_id and subject.get("id") != subject_id:
            continue
        if verdict and item.get("verdict") != verdict:
            continue
        if invariant_id and invariant_id not in item.get("invariant_ids", []):
            continue
        selected.append(item)
    result = dict(snapshot)
    result["edges"] = selected
    result["selected_edge_count"] = len(selected)
    result["query"] = {
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "verdict": verdict,
        "invariant_id": invariant_id,
    }
    return result


def environment_snapshot(*, max_edges: int = _MAX_EDGES) -> dict[str, Any]:
    """Expose only explicitly configured runtime identity as an observation.

    Empty configuration is a truthful UNAVAILABLE response; this helper never
    infers source identity from a hostname, path, or mutable display label.
    """
    source_revision = (
        os.environ.get("A11OY_SOURCE_REVISION")
        or os.environ.get("GIT_COMMIT")
        or os.environ.get("SOURCE_REVISION")
        # The canonical Space exposes this explicit build identity in build-info.
        or os.environ.get("SZL_GIT_SHA")
    )
    runtime_revision = os.environ.get("A11OY_RUNTIME_REVISION") or os.environ.get("HF_REVISION")
    if not source_revision and not runtime_revision:
        return {
            "schema": GRAPH_SCHEMA,
            "state": "UNAVAILABLE",
            "reason": "NO_EXPLICIT_RUNTIME_IDENTITY_CONFIGURED",
            "graph": graph_snapshot([], max_edges=max_edges),
        }
    edge = EvidenceEdge(
        subject={"kind": "runtime", "id": runtime_revision or source_revision},
        source_revision=source_revision,
        runtime={"revision": runtime_revision} if runtime_revision else {},
        evidence={"kind": "process_environment", "measured_state": "OBSERVED", "observed_at": _utc_now()},
        authority={"execution_authorized": False, "method": "environment-only"},
        invariant_ids=("identity-explicit",),
        verdict="OBSERVED",
        reason="Identity was supplied explicitly by the runtime environment; no readiness claim is made.",
    )
    return {
        "schema": GRAPH_SCHEMA,
        "state": "OBSERVED",
        "reason": "EXPLICIT_RUNTIME_IDENTITY_CONFIGURED",
        "graph": graph_snapshot([edge], max_edges=max_edges),
    }


def register(app: Any, *, ns: str = "a11oy") -> tuple[str, str]:
    """Register read-only graph and query routes on a FastAPI application."""
    from fastapi import Query
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/evidence"

    @app.get(base + "/graph")
    async def evidence_graph(
        limit: int = Query(_MAX_EDGES, ge=1, le=_MAX_EDGES),
    ) -> Any:
        return JSONResponse(environment_snapshot(max_edges=limit)

    @app.get(base + "/query")
    async def evidence_query(
        subject_kind: str | None = None,
        subject_id: str | None = None,
        verdict: str | None = None,
        invariant_id: str | None = None,
        limit: int = Query(_MAX_EDGES, ge=1, le=_MAX_EDGES),
    ) -> Any:
        current = environment_snapshot(max_edges=limit)
        try:
            selected = query_snapshot(
                current["graph"],
                subject_kind=subject_kind,
                subject_id=subject_id,
                verdict=verdict,
                invariant_id=invariant_id,
            )
        except ValueError as exc:
            return JSONResponse({"schema": GRAPH_SCHEMA, "state": "UNAVAILABLE", "reason": str(exc)}, status_code=400)
        return JSONResponse({**current, "graph": selected})

    return base + "/graph", base + "/query"
