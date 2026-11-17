# SPDX-License-Identifier: Apache-2.0
"""Canonical Evidence Graph (CEG) primitives.

The CEG represents observer-supplied facts as immutable, hash-addressed edges.
It does not persist an append-only ledger or mint readiness, signatures,
energy measurements, or authority. Snapshots can be queried, replayed, and
compared across deployments without authenticating the observer's claims.
"""

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Iterable, Mapping

# Keep response annotations resolvable by FastAPI. The guarded import keeps
# the graph primitives importable in bare, non-serving test environments.
try:
    from fastapi.responses import JSONResponse
except ImportError:  # FastAPI is optional for pure primitives
    JSONResponse = None  # type: ignore[assignment,misc]

SCHEMA = "szl.evidence-edge/v1"
GRAPH_SCHEMA = "szl.evidence-graph/v1"
VERDICTS = frozenset({"VERIFIED", "OBSERVED", "DEGRADED", "UNAVAILABLE"})
_MAX_EDGES = 256
_MAX_INPUT_EDGES = 1024
_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_BOOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SOURCE_KEYS = ("A11OY_SOURCE_REVISION", "GIT_COMMIT", "SOURCE_REVISION", "SZL_GIT_SHA")
_RUNTIME_KEYS = ("A11OY_RUNTIME_REVISION", "HF_REVISION")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _json_value(value: Any, *, active: set[int] | None = None) -> Any:
    """Return detached JSON data, rejecting values with no strict JSON encoding."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("evidence JSON numbers must be finite")
        return value
    if not isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"unsupported evidence JSON type: {type(value).__name__}")
    if active is None:
        active = set()
    identity = id(value)
    if identity in active:
        raise ValueError("evidence JSON cannot contain cycles")
    active.add(identity)
    try:
        if isinstance(value, Mapping):
            if any(type(key) is not str for key in value):
                raise ValueError("evidence JSON object keys must be strings")
            return {key: _json_value(item, active=active) for key, item in value.items()}
        return [_json_value(item, active=active) for item in value]
    finally:
        active.remove(identity)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def canonical_json(value: Any) -> str:
    """Return deterministic, strict JSON; this is not an RFC 8785 encoder."""
    return json.dumps(
        _json_value(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def sha256_hex(value: Any) -> str:
    """Hash JSON values canonically, or bytes directly."""
    if isinstance(value, bytes):
        raw = value
    else:
        raw = canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_map(value: Mapping[str, Any] | None, field: str) -> Mapping[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return _freeze_json(_json_value(value))


def _names(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        type(item) is not str or not item for item in value
    ):
        raise ValueError(f"{field} must be an array of nonempty strings")
    if len(value) > 64:
        raise ValueError(f"an edge may reference at most 64 {field}")
    return tuple(sorted(set(value)))


def _validate_sha256(value: str | None, field: str) -> None:
    if value is not None and (type(value) is not str or not _SHA256_RE.fullmatch(value)):
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
        subject = _clean_map(self.subject, "subject")
        runtime = _clean_map(self.runtime, "runtime")
        evidence = _clean_map(self.evidence, "evidence")
        authority = _clean_map(self.authority, "authority")
        if any(type(subject.get(key)) is not str or not subject[key] for key in ("kind", "id")):
            raise ValueError("subject.kind and subject.id must be nonempty strings")
        if type(self.verdict) is not str or self.verdict not in VERDICTS:
            raise ValueError(f"unsupported verdict: {self.verdict}")
        if self.source_revision is not None and (type(self.source_revision) is not str or not self.source_revision):
            raise ValueError("source_revision must be a nonempty string or null")
        if self.reason is not None and type(self.reason) is not str:
            raise ValueError("reason must be a string or null")
        _validate_sha256(self.artifact_sha256, "artifact_sha256")
        if not isinstance(authority.get("execution_authorized", False), bool):
            raise ValueError("authority.execution_authorized must be boolean")
        parents = _names(self.parents, "parents")
        invariant_ids = _names(self.invariant_ids, "invariant_ids")
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "parents", parents)
        object.__setattr__(self, "invariant_ids", invariant_ids)
        # Reject invalid UTF-8 strings before this edge can be referenced by a parent.
        canonical_json(self.payload()).encode("utf-8")

    def payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "subject": _json_value(self.subject),
            "source_revision": self.source_revision,
            "artifact_sha256": self.artifact_sha256,
            "runtime": _json_value(self.runtime),
            "evidence": _json_value(self.evidence),
            "authority": _json_value(self.authority),
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
        if not isinstance(value, Mapping):
            raise ValueError("evidence edge must be an object")
        value = _json_value(value)
        if value.get("schema", SCHEMA) != SCHEMA:
            raise ValueError("unsupported evidence edge schema")
        edge = cls(
            subject=value.get("subject"),
            source_revision=value.get("source_revision"),
            artifact_sha256=value.get("artifact_sha256"),
            runtime=value.get("runtime"),
            evidence=value.get("evidence"),
            authority=value.get("authority"),
            parents=value.get("parents", ()),
            invariant_ids=value.get("invariant_ids", ()),
            verdict=value.get("verdict", "OBSERVED"),
            reason=value.get("reason"),
        )
        supplied_id = value.get("receipt_id")
        if supplied_id is not None and supplied_id != edge.receipt_id:
            raise ValueError("receipt_id does not match canonical edge payload")
        return edge


def _coerce_edges(edges: Iterable[EvidenceEdge | Mapping[str, Any]]) -> list[EvidenceEdge]:
    result = []
    for index, item in enumerate(edges):
        if index >= _MAX_INPUT_EDGES:
            raise ValueError(f"evidence input exceeds {_MAX_INPUT_EDGES} edges")
        result.append(item if isinstance(item, EvidenceEdge) else EvidenceEdge.from_dict(item))
    return result


def graph_snapshot(
    edges: Iterable[EvidenceEdge | Mapping[str, Any]],
    *,
    max_edges: int = _MAX_EDGES,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Hash exactly the returned edges; bound both input work and output size."""
    if type(max_edges) is not int or not 1 <= max_edges <= _MAX_EDGES:
        raise ValueError(f"max_edges must be between 1 and {_MAX_EDGES}")
    normalized = _coerce_edges(edges)
    ordered = sorted({edge.receipt_id: edge for edge in normalized}.values(), key=lambda e: e.receipt_id)
    bounded = ordered[:max_edges]
    all_ids = {edge.receipt_id for edge in ordered}
    included_ids = {edge.receipt_id for edge in bounded}
    parent_ids = {parent for edge in bounded for parent in edge.parents}
    verdict_counts = {name: 0 for name in sorted(VERDICTS)}
    invariant_counts: dict[str, int] = {}
    for edge in bounded:
        verdict_counts[edge.verdict] += 1
        for invariant in edge.invariant_ids:
            invariant_counts[invariant] = invariant_counts.get(invariant, 0) + 1
    edge_dicts = [edge.as_dict() for edge in bounded]
    return {
        "schema": GRAPH_SCHEMA,
        "bounded": len(ordered) > len(bounded),
        "max_edges": max_edges,
        "input_limit": _MAX_INPUT_EDGES,
        "edge_count": len(bounded),
        "total_input_edges": len(ordered),
        # Retained for v1 clients. Hash order is not chronology or ledger order.
        "receipt_head": bounded[-1].receipt_id if bounded else None,
        "receipt_head_semantics": "LEXICOGRAPHIC_LAST_RECEIPT_ID",
        "ledger_head": None,
        "causal_heads": sorted(included_ids - parent_ids),
        "causal_heads_scope": "RETURNED_EDGES",
        "dangling_parent_count": len(parent_ids - included_ids),
        "missing_parent_count": len(parent_ids - all_ids),
        "missing_parent_ids": sorted(parent_ids - all_ids),
        "omitted_parent_count": len((parent_ids & all_ids) - included_ids),
        "omitted_parent_ids": sorted((parent_ids & all_ids) - included_ids),
        "unresolved_parent_count": 0,
        "verdict_counts": verdict_counts,
        "invariant_counts": dict(sorted(invariant_counts.items())),
        "digest_sha256": sha256_hex({"schema": GRAPH_SCHEMA, "edges": edge_dicts}),
        "digest_scope": "RETURNED_EDGES",
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
    max_edges: int = _MAX_EDGES,
) -> dict[str, Any]:
    """Filter before the selection limit; retain the source digest separately."""
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError(f"unsupported verdict: {verdict}")
    source_edges = _coerce_edges(snapshot.get("edges", []))
    source_dicts = [edge.as_dict() for edge in source_edges]
    source_digest = sha256_hex({"schema": GRAPH_SCHEMA, "edges": source_dicts})
    if snapshot.get("schema") != GRAPH_SCHEMA or snapshot.get("digest_sha256") != source_digest:
        raise ValueError("source snapshot digest does not match its edges")
    selected = []
    for edge in source_edges:
        if subject_kind is not None and edge.subject.get("kind") != subject_kind:
            continue
        if subject_id is not None and edge.subject.get("id") != subject_id:
            continue
        if verdict is not None and edge.verdict != verdict:
            continue
        if invariant_id is not None and invariant_id not in edge.invariant_ids:
            continue
        selected.append(edge)
    result = graph_snapshot(selected, max_edges=max_edges, observed_at=snapshot.get("observed_at"))
    included = {edge["receipt_id"] for edge in result["edges"]}
    known = {edge.receipt_id for edge in source_edges}
    parents = {parent for edge in result["edges"] for parent in edge["parents"]}
    source_bounded = bool(snapshot.get("bounded", False))
    # An unbounded query can still omit parents from an earlier selection.
    # Explicit empty classifications preserve unresolved legacy references.
    known_omitted = set(snapshot.get("omitted_parent_ids", []))
    known_missing = set(snapshot.get(
        "missing_parent_ids", [] if source_bounded else parents - known,
    ))
    omitted = (parents & (known | known_omitted)) - included
    missing = (parents & known_missing) - known - known_omitted
    unresolved = parents - included - omitted - missing
    result.update({
        "selected_edge_count": result["edge_count"],
        "matched_edge_count": len({edge.receipt_id for edge in selected}),
        "source_digest_sha256": source_digest,
        "source_edge_count": len(source_edges),
        "source_bounded": bool(snapshot.get("bounded", False)),
        "source_total_input_edges": snapshot.get("total_input_edges", len(source_edges)),
        "missing_parent_count": len(missing),
        "missing_parent_ids": sorted(missing),
        "omitted_parent_count": len(omitted),
        "omitted_parent_ids": sorted(omitted),
        "unresolved_parent_count": len(unresolved),
        "query": {
            "subject_kind": subject_kind, "subject_id": subject_id,
            "verdict": verdict, "invariant_id": invariant_id,
        },
    })
    return result


def _explicit_revision(environ: Mapping[str, str], keys: tuple[str, ...]) -> str | None:
    values = {environ[key] for key in keys if environ.get(key)}
    if any(not isinstance(value, str) or not _REVISION_RE.fullmatch(value) for value in values):
        raise ValueError("MALFORMED_EXPLICIT_RUNTIME_IDENTITY")
    if len(values) > 1:
        raise ValueError("CONFLICTING_EXPLICIT_RUNTIME_IDENTITIES")
    return next(iter(values), None)


def environment_snapshot(
    *, max_edges: int = _MAX_EDGES, environ: Mapping[str, str] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Capture explicit full revision IDs without inferring identity or authority."""
    captured_at = observed_at or _utc_now()
    environ = os.environ if environ is None else environ
    try:
        source_revision = _explicit_revision(environ, _SOURCE_KEYS)
        runtime_revision = _explicit_revision(environ, _RUNTIME_KEYS)
    except ValueError as exc:
        return {
            "schema": GRAPH_SCHEMA, "state": "DEGRADED", "reason": str(exc),
            "captured_at": captured_at,
            "graph": graph_snapshot([], max_edges=max_edges, observed_at=captured_at),
        }
    if not source_revision and not runtime_revision:
        return {
            "schema": GRAPH_SCHEMA,
            "state": "UNAVAILABLE",
            "reason": "NO_EXPLICIT_RUNTIME_IDENTITY_CONFIGURED",
            "captured_at": captured_at,
            "graph": graph_snapshot([], max_edges=max_edges, observed_at=captured_at),
        }
    edge = EvidenceEdge(
        subject={"kind": "runtime", "id": runtime_revision or source_revision},
        source_revision=source_revision,
        runtime={"revision": runtime_revision} if runtime_revision else {},
        evidence={"kind": "process_environment", "measured_state": "OBSERVED", "observed_at": captured_at},
        authority={"execution_authorized": False, "method": "environment-only"},
        invariant_ids=("identity-explicit",),
        verdict="OBSERVED",
        reason="Identity was supplied explicitly by the runtime environment; no readiness claim is made.",
    )
    return {
        "schema": GRAPH_SCHEMA,
        "state": "OBSERVED",
        "reason": "EXPLICIT_RUNTIME_IDENTITY_CONFIGURED",
        "captured_at": captured_at,
        "graph": graph_snapshot([edge], max_edges=max_edges, observed_at=captured_at),
    }


def _cached_source_witness(app: Any, runtime_edges: list[dict[str, Any]]) -> tuple[EvidenceEdge | None, dict[str, Any]]:
    """Read the observer's cached statement, never initiate verification or work."""
    unavailable = {
        "state": "UNAVAILABLE", "status": None, "reason": "SOURCE_WITNESS_UNAVAILABLE",
        "source_revision": None, "hf_revision": None, "runtime_boot_id": None,
        "local_bytes_evidence": "UNAVAILABLE", "execution_authority": False,
        "scope": "FINAL_APP_SOURCE_COPY_FILES",
    }
    observer = getattr(app.state, "szl_execution_observer", None)
    identity = getattr(observer, "process_identity", None)
    if identity is None:
        return None, unavailable
    try:
        raw = identity.snapshot()
    except Exception:
        return None, {**unavailable, "reason": "SOURCE_WITNESS_READ_FAILED"}
    if not isinstance(raw, Mapping):
        return None, {**unavailable, "reason": "SOURCE_WITNESS_INVALID"}
    source, revision, boot = (raw.get(key) for key in ("source_revision", "hf_revision", "runtime_boot_id"))
    service = getattr(observer, "service", None)
    valid = (
        raw.get("status") == "REPORTED"
        and raw.get("error") is None
        and raw.get("method") == "GITHUB_ATTESTED_SOURCE_COPY_SET"
        and raw.get("scope") == "FINAL_APP_SOURCE_COPY_FILES"
        and all(raw.get(key) is False for key in (
            "hardware_attestation", "image_attestation", "execution_authority",
        ))
        and boot == getattr(identity, "boot_id", None)
        and boot == getattr(service, "runtime_boot_id", None)
        and raw.get("local_bytes_evidence") == "MEASURED"
        and isinstance(source, str) and bool(_REVISION_RE.fullmatch(source))
        and isinstance(revision, str) and bool(_REVISION_RE.fullmatch(revision))
        and isinstance(boot, str) and bool(_BOOT_RE.fullmatch(boot))
        and all(isinstance(raw.get(key), str) and _SHA256_RE.fullmatch(raw[key])
                for key in ("marker_sha256", "binding_sha256"))
    )
    if not valid:
        return None, {
            **unavailable, "state": "DEGRADED",
            "status": "BLOCKED" if raw.get("status") == "BLOCKED" else None,
            "reason": "SOURCE_WITNESS_BLOCKED" if raw.get("status") == "BLOCKED" else "SOURCE_WITNESS_INVALID",
        }
    runtime = runtime_edges[0] if runtime_edges else None
    source_matches = bool(runtime and runtime.get("source_revision") == source)
    runtime_revision = runtime.get("runtime", {}).get("revision") if runtime else None
    conflict = bool(runtime and (
        (runtime.get("source_revision") is not None and not source_matches)
        or (runtime_revision is not None and runtime_revision != revision)
    ))
    parents = (runtime["receipt_id"],) if source_matches and not conflict else ()
    reason = "SOURCE_WITNESS_IDENTITY_CONFLICT" if conflict else "CACHED_SOURCE_WITNESS_REPORTED"
    status = {
        "state": "DEGRADED" if conflict else "OBSERVED", "status": "REPORTED",
        "reason": reason, "source_revision": source, "hf_revision": revision,
        "runtime_boot_id": boot, "local_bytes_evidence": "MEASURED",
        "execution_authority": False, "scope": "FINAL_APP_SOURCE_COPY_FILES",
    }
    edge = EvidenceEdge(
        subject={"kind": "runtime-source-witness", "id": boot},
        source_revision=source,
        runtime={"revision": revision, "boot_id": boot},
        evidence={
            "kind": "cached_runtime_source_witness", "witness_status": "REPORTED",
            "local_bytes_evidence": "MEASURED", "marker_sha256": raw["marker_sha256"],
            "binding_sha256": raw["binding_sha256"], "claims_verified": False,
            "relationship": "same-source-observation" if parents else "unbound-observation",
            "hardware_attestation": False, "image_attestation": False,
        },
        authority={"execution_authorized": False, "method": "cached-observer-report"},
        parents=parents, invariant_ids=("source-consistency",),
        verdict="DEGRADED" if conflict else "OBSERVED",
        reason="Cached process witness reported by the runtime; CEG does not reverify or authorize execution.",
    )
    return edge, status


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def edge_assessment(
    edge: Mapping[str, Any], *, runtime_source: str | None, now: datetime,
) -> dict[str, Any]:
    """Describe temporal/source relationships without upgrading the edge verdict."""
    evidence = edge.get("evidence", {})
    kind = evidence.get("kind")
    scope = {
        "process_environment": "RUNTIME_OBSERVATION",
        "cached_runtime_source_witness": "RUNTIME_SOURCE_WITNESS",
        "receipt-artifact": "HISTORICAL_ARTIFACT",
    }.get(kind, "OBSERVER_SUPPLIED")
    observed_raw, until_raw = evidence.get("observed_at"), evidence.get("valid_until")
    observed, until = _timestamp(observed_raw), _timestamp(until_raw)
    freshness = "UNKNOWN"
    if ((observed_raw is not None and observed is None)
            or (until_raw is not None and until is None)
            or (observed is not None and observed > now)
            or (until is not None and (observed is None or until <= observed))):
        freshness = "INVALID"
    elif until is not None:
        freshness = "EXPIRED" if until <= now else "WITHIN_DECLARED_WINDOW"
    source = edge.get("source_revision")
    relation = (
        "UNBOUND" if source is None else
        "RUNTIME_IDENTITY_UNAVAILABLE" if runtime_source is None else
        "MATCHES_RUNTIME_OBSERVATION" if source == runtime_source else "DIFFERENT_SOURCE"
    )
    return {
        "scope": scope, "freshness": freshness, "source_relation": relation,
        "observed_at": observed_raw, "valid_until": until_raw,
    }


def _load_receipt_bundle(path: Any) -> tuple[tuple[EvidenceEdge, ...], dict[str, Any]]:
    """Load a reviewed release artifact once, without any network or signing."""
    try:
        from szl_evidence_receipts import MAX_BUNDLE_BYTES, decode_bundle
    except ImportError:
        return (), {"state": "UNAVAILABLE", "reason": "RECEIPT_READER_UNAVAILABLE"}
    try:
        with open(path, "rb") as stream:
            raw = stream.read(MAX_BUNDLE_BYTES + 1)
    except OSError:
        return (), {"state": "UNAVAILABLE", "reason": "RECEIPT_BUNDLE_UNREADABLE"}
    try:
        edges = tuple(decode_bundle(raw))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return (), {"state": "UNAVAILABLE", "reason": "RECEIPT_BUNDLE_INVALID"}
    return edges, {
        "state": "OBSERVED",
        "reason": "BUNDLED_RECEIPT_OBSERVATIONS",
        "edge_count": len(edges),
        "file_sha256": sha256_hex(raw),
        "signature_status": "UNSIGNED",
        "claims_verified": False,
        "scope": "Historical artifact bytes checked at import; no live readiness or authority.",
    }


def register(
    app: Any, *, ns: str = "a11oy", receipt_bundle_path: Any = None,
) -> tuple[str, str]:
    """Register read-only routes over a captured environment and fixed artifact."""
    from pathlib import Path
    from fastapi import Query

    base = f"/api/{ns}/v1/evidence"
    bundle_path = (
        Path(__file__).with_name("evidence_graph_receipts.json")
        if receipt_bundle_path is None else receipt_bundle_path
    )
    receipt_edges, receipt_status = _load_receipt_bundle(bundle_path)
    captured = environment_snapshot()
    runtime_edges = captured["graph"]["edges"]
    runtime_source = runtime_edges[0]["source_revision"] if runtime_edges else None

    def current_snapshot(limit: int) -> dict[str, Any]:
        witness_edge, witness_status = _cached_source_witness(app, runtime_edges)
        edges = [*runtime_edges, *receipt_edges]
        if witness_edge is not None:
            edges.append(witness_edge)
        current = {
            **captured,
            "runtime_identity_state": captured["state"],
            "state_meaning": "EVIDENCE_AVAILABILITY_ONLY",
            "execution_authority": False,
            "retrieved_at": _utc_now(),
            "receipt_bundle": dict(receipt_status),
            "provenance_witness": witness_status,
            "graph": graph_snapshot(edges, max_edges=limit, observed_at=captured["captured_at"]),
        }
        current["graph"]["observed_at_semantics"] = "PROCESS_ENVIRONMENT_CAPTURE_TIME"
        blockers = []
        if captured["state"] != "OBSERVED":
            blockers.append(captured["reason"])
        if receipt_status["state"] != "OBSERVED":
            blockers.append(receipt_status["reason"])
        if witness_status["state"] != "OBSERVED":
            blockers.append(witness_status["reason"])
        if captured["state"] == "OBSERVED":
            if receipt_status["state"] != "OBSERVED":
                current.update(state="DEGRADED", reason="RECEIPT_BUNDLE_UNAVAILABLE")
            elif witness_status["state"] == "DEGRADED":
                current.update(state="DEGRADED", reason=witness_status["reason"])
        current["blockers"] = blockers
        now = datetime.now(timezone.utc)
        current["edge_assessments"] = {
            edge["receipt_id"]: edge_assessment(edge, runtime_source=runtime_source, now=now)
            for edge in current["graph"]["edges"]
        }
        return current

    @app.get(base + "/graph")
    async def evidence_graph(
        limit: int = Query(_MAX_EDGES, ge=1, le=_MAX_EDGES),
    ) -> JSONResponse:
        return JSONResponse(current_snapshot(limit), headers={"Cache-Control": "no-store"})

    @app.get(base + "/query")
    async def evidence_query(
        subject_kind: str | None = None,
        subject_id: str | None = None,
        verdict: str | None = None,
        invariant_id: str | None = None,
        limit: int = Query(_MAX_EDGES, ge=1, le=_MAX_EDGES),
    ) -> JSONResponse:
        # The fixed bundle is capped at 128 edges; two runtime observations fit
        # below 256. Apply the caller's output limit only after filtering.
        current = current_snapshot(_MAX_EDGES)
        try:
            selected = query_snapshot(
                current["graph"],
                subject_kind=subject_kind, subject_id=subject_id,
                verdict=verdict, invariant_id=invariant_id, max_edges=limit,
            )
        except ValueError:
            return JSONResponse(
                {"schema": GRAPH_SCHEMA, "state": "UNAVAILABLE", "reason": "INVALID_EVIDENCE_QUERY"},
                status_code=400, headers={"Cache-Control": "no-store"},
            )
        selected["observed_at_semantics"] = "PROCESS_ENVIRONMENT_CAPTURE_TIME"
        assessments = current["edge_assessments"]
        return JSONResponse({
            **current, "graph": selected,
            "edge_assessments": {edge["receipt_id"]: assessments[edge["receipt_id"]] for edge in selected["edges"]},
        }, headers={"Cache-Control": "no-store"})

    return base + "/graph", base + "/query"
