# SPDX-License-Identifier: Apache-2.0
"""Fail-closed Brain evidence inventory, reranker proposal data, and local feed.

This service does not scrape, train, or promote a model.  It turns the Brain graph and
the canonical local corpus manifests into auditable *proposal* data.  Every raw graph
node receives a deterministic inventory decision.  Reranker rows are admitted only
when their evidence is an exact projection of a real Brain node and all declared
source hashes match verified local bytes.

GETs are pure reads.  The two POST paths are loopback-only writes:

* ``rows`` appends one validated, hash-linked local row;
* ``feed/refresh`` checkpoints one bounded local Ouroboros cycle.

Missing canonical manifests always produce ``BLOCKED`` dataset/model/evaluation
readiness and zero rows.  No threshold or proof status is upgraded.
"""

import datetime
import hashlib
import ipaddress
import json
import math
import os
import pathlib
import re
import tempfile
import threading
import time
from typing import Any, Mapping

import szl_braincorpus as _corpus_admission
import szl_brain_corpus as _brain_projection


SERVICE_SCHEMA = "szl.brain.reranker-readiness.v1"
SOURCE_SCHEMA = "szl.brain.reranker-source.v1"
ROW_SCHEMA = "szl.brain.reranker-row.v1"
LEDGER_SCHEMA = "szl.brain.reranker-ledger.v1"
FEED_SCHEMA = "szl.brain.ouroboros-feed.v1"
MODEL_SCHEMA = "szl.brain.reranker-model.v1"
EVAL_SCHEMA = "szl.brain.reranker-evaluation.v1"

READY = "READY"
BLOCKED = "BLOCKED"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"
UNKNOWN = "UNKNOWN"
UNVERIFIED = "UNVERIFIED"

EXAMPLE_TYPES = ("positive", "negative", "abstention", "refutation")
TARGETS = {"positive": 1.0, "negative": 0.0, "abstention": 0.0, "refutation": 0.0}
FEED_STAGES = (
    "DISCOVER", "FETCH", "HASH", "CLASSIFY", "DEDUP", "VERIFY",
    "ADMIT_OR_QUARANTINE", "EVALUATE", "RECEIPT", "REFRESH",
)

MAX_QUERY_CHARS = 1_024
MAX_EVIDENCE_CHARS = 12_000
MAX_ENTITY_CHARS = 160
MAX_ARTIFACT_EXAMPLES = 10_000
MAX_LOCAL_ROWS = 2_000
MAX_LEDGER_BYTES = 32 * 1024 * 1024
MAX_INVENTORY_PAGE = 500
MAX_DATASET_PAGE = 500
FEED_MIN_INTERVAL_S = 60
FEED_MAX_BACKOFF_S = 3_600
FEED_NODE_BUDGET = 20_000
FEED_SOURCE_BUDGET = 5_000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$")
_LOCK = threading.RLock()
_INVENTORY_CACHE: dict[str, Any] = {"key": None, "value": None}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _is_sha(value: Any) -> bool:
    return bool(_SHA256_RE.fullmatch(str(value or "").lower()))


def _repo_root(repo_root: pathlib.Path | str | None = None) -> pathlib.Path:
    return pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent).resolve()


def _runtime_path(name: str, environ: Mapping[str, str], explicit: str) -> pathlib.Path:
    configured = str(environ.get(explicit, "")).strip()
    if configured:
        return pathlib.Path(configured).expanduser().resolve()
    state_dir = str(environ.get("A11OY_RUNTIME_STATE_DIR", "")).strip()
    base = pathlib.Path(state_dir).expanduser().resolve() if state_dir else (
        pathlib.Path(tempfile.gettempdir()) / "a11oy-brain-reranker"
    ).resolve()
    return base / name


def _ledger_path(environ: Mapping[str, str]) -> pathlib.Path:
    return _runtime_path("validated-rows.jsonl", environ,
                         "A11OY_BRAIN_RERANKER_LEDGER")


def _feed_path(environ: Mapping[str, str]) -> pathlib.Path:
    return _runtime_path("ouroboros-feed.jsonl", environ,
                         "A11OY_BRAIN_FEED_LEDGER")


def _safe_read_json(path: pathlib.Path, maximum: int) -> tuple[Any | None, str | None]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            return None, f"FILE_TOO_LARGE:{len(raw)}>{maximum}"
        return json.loads(raw.decode("utf-8")), None
    except FileNotFoundError:
        return None, "FILE_NOT_FOUND"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"READ_FAILED:{type(exc).__name__}"


def _source_family(node: Mapping[str, Any]) -> str:
    raw = str(node.get("url") or node.get("source") or node.get("path") or
              node.get("derived_from") or "").strip()
    if raw.startswith(("http://", "https://")):
        try:
            from urllib.parse import urlsplit
            return (urlsplit(raw).hostname or UNKNOWN).lower()
        except Exception:
            return UNKNOWN
    if raw:
        return raw.replace("\\", "/").split("/", 1)[0][:160]
    return UNKNOWN


def _source_url(node: Mapping[str, Any]) -> str:
    raw = str(node.get("url") or "").strip()
    return raw if raw.startswith(("http://", "https://")) else UNKNOWN


def _revision(node: Mapping[str, Any]) -> str:
    for key in ("revision", "commit", "commit_sha", "sha", "version", "rev"):
        value = str(node.get(key) or "").strip()
        if value:
            return value[:200]
    return UNKNOWN


def _license(node: Mapping[str, Any]) -> str:
    for key in ("license", "license_id", "spdx", "spdx_id"):
        value = str(node.get(key) or "").strip()
        if value:
            return value[:200]
    return UNKNOWN


def _freshness(node: Mapping[str, Any]) -> tuple[str, str]:
    for key in ("retrieved_at", "captured_at", "updated_at", "published_at", "timestamp", "date"):
        value = str(node.get(key) or "").strip()
        if value:
            return value[:200], "SOURCE_TIMESTAMP"
    return UNKNOWN, "UNVERIFIED"


def _node_content(node: Mapping[str, Any]) -> dict[str, Any]:
    """Hash only source-authored graph fields; never request time or derived verdicts."""
    return {str(k): node[k] for k in sorted(node) if not str(k).startswith("_")}


def _canonical_key(node: Mapping[str, Any], content_sha256: str) -> str:
    url = _source_url(node)
    if url != UNKNOWN:
        return "url:" + url.rstrip("/").lower()
    formula = str(node.get("formula_id") or "").strip().upper()
    if formula:
        return "formula:" + formula
    title = str(node.get("title") or node.get("label") or "").strip().lower()
    kind = str(node.get("kind") or "node").strip().lower()
    if title:
        return f"{kind}:{title}"
    return "content:" + content_sha256


def _graph_nodes(ns: str = "a11oy") -> tuple[list[dict[str, Any]], str | None]:
    try:
        import a11oy_brain_graph as graph
        built = graph.get_brain_graph(ns)
        nodes = built.get("nodes") if isinstance(built, dict) else None
        if not isinstance(nodes, list):
            return [], "GRAPH_NODES_UNAVAILABLE"
        return [dict(n) for n in nodes if isinstance(n, dict)], None
    except Exception as exc:
        return [], f"GRAPH_UNAVAILABLE:{type(exc).__name__}"


def _canonical_context(repo_root: pathlib.Path | str | None,
                       environ: Mapping[str, str]) -> dict[str, Any]:
    root = _repo_root(repo_root)
    status = _corpus_admission.build_corpus_status(root, environ)
    sources = status.get("sources") if isinstance(status, dict) else []
    source_map: dict[tuple[str, str], dict[str, Any]] = {}
    complete = True
    reasons: list[str] = []
    for source in sources if isinstance(sources, list) else []:
        source_type = str(source.get("source_type") or "")
        source_status = str(source.get("status") or "")
        manifest_hash = str(source.get("manifest_sha256") or "").lower()
        if source_status not in {"INGESTED_LOCAL", "PARTIAL_QUARANTINE"} or not _is_sha(manifest_hash):
            complete = False
            reasons.append(f"{source_type}:{source_status or 'SOURCE_UNAVAILABLE'}")
        manifest_path, boundary, origin, path_error = _corpus_admission._safe_manifest_path(
            source_type, root, environ,
        )
        for entry in source.get("entries", []) if isinstance(source.get("entries"), list) else []:
            if not entry.get("artifact_verified"):
                continue
            source_path = str(entry.get("source_path") or "")
            artifact = (boundary / pathlib.Path(source_path)).resolve() if source_path else None
            if artifact is None or not _corpus_admission._inside(artifact, boundary):
                continue
            source_map[(source_type, str(entry.get("id") or ""))] = {
                "source_type": source_type,
                "source_entry_id": str(entry.get("id") or ""),
                "manifest_sha256": manifest_hash,
                "manifest_path": manifest_path,
                "manifest_origin": origin,
                "artifact_path": artifact,
                "artifact_sha256": str(entry.get("artifact_sha256") or "").lower(),
                "proof_receipt": entry.get("proof_receipt"),
                "evidence_class": entry.get("effective_class"),
            }
        if path_error:
            complete = False
            reasons.append(f"{source_type}:{path_error}")
    if len(sources or []) != len(_corpus_admission.SOURCE_TYPES):
        complete = False
        reasons.append("CANONICAL_SOURCE_ROSTER_INCOMPLETE")
    return {
        "complete": complete,
        "reasons": sorted(set(reasons)),
        "status": status,
        "source_map": source_map,
        "root": root,
    }


def _brain_docs(ns: str) -> tuple[dict[str, dict[str, str]], str | None]:
    try:
        docs = _brain_projection.corpus(ns, limit=20_000, include_people=True)
    except Exception as exc:
        return {}, f"BRAIN_PROJECTION_FAILED:{type(exc).__name__}"
    result: dict[str, dict[str, str]] = {}
    for doc in docs if isinstance(docs, list) else []:
        if isinstance(doc, dict) and doc.get("id"):
            result[str(doc["id"])] = {
                "id": str(doc["id"]), "text": str(doc.get("text") or ""),
                "source": str(doc.get("source") or ""),
            }
    return result, None if result else "BRAIN_PROJECTION_EMPTY"


def build_inventory(ns: str = "a11oy", repo_root: pathlib.Path | str | None = None,
                    environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return one decision for every raw graph node, plus canonical/dedupe posture."""
    env = os.environ if environ is None else environ
    canonical = _canonical_context(repo_root, env)
    nodes, graph_error = _graph_nodes(ns)
    graph_hash = _sha([_node_content(n) for n in nodes]) if nodes else None
    cache_key = _sha({"graph": graph_hash, "canonical": [
        (s.get("source_type"), s.get("manifest_sha256"), s.get("status"))
        for s in (canonical["status"].get("sources") or [])
    ]})
    with _LOCK:
        if _INVENTORY_CACHE.get("key") == cache_key and _INVENTORY_CACHE.get("value") is not None:
            return _INVENTORY_CACHE["value"]

    seen: dict[str, str] = {}
    decisions: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    canonical_count = 0
    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or f"raw-index:{index}")
        content_sha = _sha(_node_content(node))
        key = _canonical_key(node, content_sha)
        duplicate_of = seen.get(key)
        if duplicate_of is None:
            seen[key] = node_id
            canonical_count += 1
        source_identity = str(node.get("source") or node.get("url") or node.get("path") or
                              node.get("derived_from") or UNKNOWN)[:500]
        retrieved_at, freshness_basis = _freshness(node)
        reason_codes: list[str] = []
        if duplicate_of:
            reason_codes.append("DUPLICATE_CANONICAL_KEY")
        if source_identity == UNKNOWN:
            reason_codes.append("PROVENANCE_UNKNOWN")
        if _revision(node) == UNKNOWN:
            reason_codes.append("REVISION_UNKNOWN")
        if _license(node) == UNKNOWN:
            reason_codes.append("LICENSE_UNKNOWN")
        if retrieved_at == UNKNOWN:
            reason_codes.append("FRESHNESS_UNKNOWN")
        if not canonical["complete"]:
            reason_codes.append("CANONICAL_MANIFESTS_REQUIRED")
        decision = "ADMITTED_TO_CANONICAL_MAP" if not reason_codes else "QUARANTINED"
        if decision == "QUARANTINED":
            for reason in reason_codes:
                reasons[reason] = reasons.get(reason, 0) + 1
        anatomy_core = {
            "raw_index": index,
            "brain_node_id": node_id,
            "node_content_sha256": content_sha,
            "source_identity": source_identity,
            "source_url": _source_url(node),
            "source_family": _source_family(node),
            "source_revision": _revision(node),
            "license": _license(node),
            "robots_policy": "NOT_APPLICABLE_LOCAL_SNAPSHOT",
            "retrieved_at": retrieved_at,
            "freshness_basis": freshness_basis,
            "canonical_key_sha256": _sha_text(key),
            "canonical_node_id": duplicate_of or node_id,
            "deduplicated": bool(duplicate_of),
            "formula_id": str(node.get("formula_id") or UNKNOWN),
            "proof_status": str(node.get("proof_status") or UNKNOWN),
            "admission_decision": decision,
            "reason_codes": reason_codes,
            "split_assignment": "NOT_ASSIGNED",
            "training_eligible": False,
            "model_receipt_sha256": UNKNOWN,
            "evaluation_receipt_sha256": UNKNOWN,
        }
        decisions.append({**anatomy_core, "anatomy_record_sha256": _sha(anatomy_core)})

    inventory_core = {
        "graph_content_sha256": graph_hash,
        "raw_node_count": len(nodes),
        "decision_count": len(decisions),
        "canonical_node_count": canonical_count,
        "quarantined_node_count": sum(d["admission_decision"] == "QUARANTINED" for d in decisions),
        "reason_counts": dict(sorted(reasons.items())),
    }
    value = {
        "ok": graph_error is None,
        "label": "MEASURED" if graph_error is None else UNAVAILABLE,
        "schema_version": SERVICE_SCHEMA,
        "inventory": inventory_core,
        "inventory_sha256": _sha(inventory_core),
        "canonical_manifests_complete": canonical["complete"],
        "canonical_manifest_reasons": canonical["reasons"],
        "decisions": decisions,
        "graph_error": graph_error,
        "note": "Every raw node has one decision; no node is silently dropped.",
    }
    with _LOCK:
        _INVENTORY_CACHE.update({"key": cache_key, "value": value})
    return value


def _row_core(example: Mapping[str, Any], source: Mapping[str, Any],
              doc: Mapping[str, str], origin: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    example_type = str(example.get("example_type") or "").strip().lower()
    query = str(example.get("query") or "").strip()
    evidence = str(example.get("evidence_text") or "")
    example_id = str(example.get("example_id") or "").strip()
    entity_id = str(example.get("entity_id") or "").strip()
    node_id = str(example.get("brain_node_id") or "").strip()
    try:
        target = float(example.get("target_relevance"))
    except (TypeError, ValueError):
        target = math.nan
    if not _ID_RE.fullmatch(example_id): errors.append("INVALID_EXAMPLE_ID")
    if not _ID_RE.fullmatch(entity_id): errors.append("INVALID_ENTITY_ID")
    if not query or len(query) > MAX_QUERY_CHARS: errors.append("INVALID_QUERY")
    if not evidence or len(evidence) > MAX_EVIDENCE_CHARS: errors.append("INVALID_EVIDENCE")
    if example_type not in EXAMPLE_TYPES: errors.append("INVALID_EXAMPLE_TYPE")
    if example_type in TARGETS and target != TARGETS[example_type]: errors.append("TARGET_TYPE_MISMATCH")
    if node_id != doc.get("id"): errors.append("BRAIN_NODE_ID_MISMATCH")
    if evidence != doc.get("text"): errors.append("EVIDENCE_NOT_EXACT_BRAIN_PROJECTION")
    node_hash = _sha({"id": doc.get("id"), "text": doc.get("text"), "source": doc.get("source")})
    source_hash = _sha_text(doc.get("source"))
    declared_node_hash = str(example.get("brain_node_sha256") or "").lower()
    declared_source_hash = str(example.get("brain_source_sha256") or "").lower()
    if declared_node_hash != node_hash: errors.append("BRAIN_NODE_HASH_MISMATCH")
    if declared_source_hash != source_hash: errors.append("BRAIN_SOURCE_HASH_MISMATCH")
    if errors:
        return None, sorted(set(errors))
    source_receipt = (source.get("proof_receipt") or {}).get("receipt_sha256")
    if not _is_sha(source_receipt):
        source_receipt = _sha({
            "source_manifest_sha256": source["manifest_sha256"],
            "source_artifact_sha256": source["artifact_sha256"],
            "brain_node_sha256": node_hash,
            "brain_source_sha256": source_hash,
        })
    core = {
        "schema_version": ROW_SCHEMA,
        "example_id": example_id,
        "example_type": example_type,
        "target_relevance": target,
        "query": query,
        "evidence_text": evidence,
        "entity_id": entity_id,
        "source_type": source["source_type"],
        "source_entry_id": source["source_entry_id"],
        "source_manifest_sha256": source["manifest_sha256"],
        "source_artifact_sha256": source["artifact_sha256"],
        "source_receipt_sha256": source_receipt,
        "brain_node_id": node_id,
        "brain_node_sha256": node_hash,
        "brain_source_sha256": source_hash,
        "origin": origin,
    }
    return {**core, "row_receipt_sha256": _sha(core)}, []


def _load_embedded_rows(canonical: Mapping[str, Any], docs: Mapping[str, dict[str, str]]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    rejected: list[dict] = []
    for source in canonical["source_map"].values():
        payload, error = _safe_read_json(source["artifact_path"], _corpus_admission.MAX_ARTIFACT_BYTES)
        if error or not isinstance(payload, dict) or payload.get("schema_version") != SOURCE_SCHEMA:
            continue
        examples = payload.get("examples")
        if not isinstance(examples, list):
            rejected.append({"source_entry_id": source["source_entry_id"],
                             "reasons": ["EXAMPLES_MUST_BE_ARRAY"]})
            continue
        for raw in examples[:MAX_ARTIFACT_EXAMPLES]:
            if not isinstance(raw, dict):
                rejected.append({"source_entry_id": source["source_entry_id"],
                                 "reasons": ["EXAMPLE_NOT_OBJECT"]})
                continue
            doc = docs.get(str(raw.get("brain_node_id") or ""), {})
            row, reasons = _row_core(raw, source, doc, "CANONICAL_ARTIFACT")
            if row:
                rows.append(row)
            else:
                rejected.append({"source_entry_id": source["source_entry_id"],
                                 "example_id": raw.get("example_id"), "reasons": reasons})
    return rows, rejected


def _read_jsonl(path: pathlib.Path, maximum: int) -> tuple[list[Any], list[str]]:
    if not path.is_file():
        return [], []
    try:
        if path.stat().st_size > maximum:
            return [], [f"LEDGER_TOO_LARGE:{path.stat().st_size}>{maximum}"]
        rows, errors = [], []
        with path.open("r", encoding="utf-8") as handle:
            for i, line in enumerate(handle):
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    errors.append(f"INVALID_JSON_LINE:{i + 1}")
        return rows, errors
    except OSError as exc:
        return [], [f"LEDGER_READ_FAILED:{type(exc).__name__}"]


def _load_local_rows(path: pathlib.Path, canonical: Mapping[str, Any],
                     docs: Mapping[str, dict[str, str]]) -> tuple[list[dict], dict[str, Any]]:
    records, errors = _read_jsonl(path, MAX_LEDGER_BYTES)
    rows: list[dict] = []
    prev = "0" * 64
    valid_chain = not errors
    for i, record in enumerate(records[:MAX_LOCAL_ROWS]):
        if not isinstance(record, dict) or record.get("schema_version") != LEDGER_SCHEMA:
            errors.append(f"INVALID_LEDGER_RECORD:{i}")
            valid_chain = False
            continue
        stored_prev = str(record.get("prev_hash") or "")
        stored_hash = str(record.get("entry_sha256") or "")
        raw = record.get("row")
        computed = _sha({"prev_hash": stored_prev, "row": raw})
        if stored_prev != prev or stored_hash != computed or not isinstance(raw, dict):
            errors.append(f"CHAIN_MISMATCH:{i}")
            valid_chain = False
            continue
        source = canonical["source_map"].get((str(raw.get("source_type")),
                                               str(raw.get("source_entry_id"))))
        doc = docs.get(str(raw.get("brain_node_id") or ""), {})
        if source is None:
            errors.append(f"SOURCE_BINDING_GONE:{i}")
            valid_chain = False
            continue
        row, reasons = _row_core(raw, source, doc, "LOCAL_VALIDATED_APPEND")
        if row is None or row.get("row_receipt_sha256") != raw.get("row_receipt_sha256"):
            errors.append(f"ROW_REVALIDATION_FAILED:{i}:{','.join(reasons)}")
            valid_chain = False
            continue
        row["ledger_entry_sha256"] = stored_hash
        rows.append(row)
        prev = stored_hash
    return rows, {"chain_valid": valid_chain, "record_count": len(records),
                  "valid_row_count": len(rows), "head_sha256": prev,
                  "errors": errors}


def _split_group(row: Mapping[str, Any]) -> str:
    group = f"{row['source_type']}|{row['source_entry_id']}|{row['entity_id']}"
    bucket = int(hashlib.sha256(("split-v1|" + group).encode()).hexdigest()[:8], 16) % 10
    return "train" if bucket < 7 else ("eval" if bucket < 9 else "test")


def _verify_optional_manifest(path: pathlib.Path, schema: str, dataset_hash: str,
                              model_hash: str | None = None) -> dict[str, Any]:
    payload, error = _safe_read_json(path, 2 * 1024 * 1024)
    if error:
        return {"status": BLOCKED, "reasons": [error], "receipt_sha256": UNKNOWN}
    reasons: list[str] = []
    if not isinstance(payload, dict) or payload.get("schema_version") != schema:
        reasons.append("SCHEMA_MISMATCH")
    else:
        body = {k: v for k, v in payload.items() if k != "content_sha256"}
        if payload.get("content_sha256") != _sha(body): reasons.append("CONTENT_HASH_MISMATCH")
        if payload.get("dataset_sha256") != dataset_hash: reasons.append("DATASET_HASH_MISMATCH")
        if model_hash is not None and payload.get("model_sha256") != model_hash:
            reasons.append("MODEL_HASH_MISMATCH")
    return {"status": READY if not reasons else BLOCKED, "reasons": reasons,
            "receipt_sha256": (payload or {}).get("receipt_sha256", UNKNOWN),
            "manifest": payload if not reasons else None}


def build_dataset(ns: str = "a11oy", repo_root: pathlib.Path | str | None = None,
                  environ: Mapping[str, str] | None = None,
                  ledger_path: pathlib.Path | str | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    canonical = _canonical_context(repo_root, env)
    docs, doc_error = _brain_docs(ns)
    if not canonical["complete"] or doc_error:
        reasons = list(canonical["reasons"])
        if doc_error: reasons.append(doc_error)
        return {
            "ok": True, "schema_version": SERVICE_SCHEMA, "label": UNAVAILABLE,
            "rows": [], "dataset_sha256": None,
            "dataset_readiness": {"status": BLOCKED, "reasons": sorted(set(reasons))},
            "evaluation_readiness": {"status": BLOCKED, "reasons": ["DATASET_BLOCKED"]},
            "model_readiness": {"status": BLOCKED, "reasons": ["DATASET_BLOCKED"]},
            "split_counts": {"train": 0, "eval": 0, "test": 0},
            "example_type_counts": {name: 0 for name in EXAMPLE_TYPES},
            "quarantined_rows": [], "ledger": {"chain_valid": True, "record_count": 0},
            "canonical_manifests_complete": canonical["complete"],
            "training_triggered": False,
        }
    embedded, rejected = _load_embedded_rows(canonical, docs)
    ledger = pathlib.Path(ledger_path).resolve() if ledger_path else _ledger_path(env)
    appended, ledger_state = _load_local_rows(ledger, canonical, docs)
    rows_by_receipt: dict[str, dict] = {}
    for row in embedded + appended:
        rows_by_receipt.setdefault(row["row_receipt_sha256"], row)
    rows = list(rows_by_receipt.values())
    for row in rows:
        row["split"] = _split_group(row)
    rows.sort(key=lambda r: (r["split"], r["source_type"], r["entity_id"], r["example_id"]))
    type_counts = {name: sum(r["example_type"] == name for r in rows) for name in EXAMPLE_TYPES}
    split_counts = {name: sum(r["split"] == name for r in rows) for name in ("train", "eval", "test")}
    groups: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        key = (row["source_type"], row["source_entry_id"], row["entity_id"])
        groups.setdefault(key, set()).add(row["split"])
    leakage = sum(len(v) > 1 for v in groups.values())
    reasons = []
    missing_types = [name for name, count in type_counts.items() if count == 0]
    if not rows: reasons.append("ZERO_GROUNDED_ROWS")
    if missing_types: reasons.append("MISSING_REQUIRED_EXAMPLE_TYPES:" + ",".join(missing_types))
    if leakage: reasons.append(f"SOURCE_ENTITY_SPLIT_LEAKAGE:{leakage}")
    if not ledger_state["chain_valid"]: reasons.append("LOCAL_LEDGER_CHAIN_INVALID")
    dataset_hash = _sha([{k: row[k] for k in sorted(row) if k != "ledger_entry_sha256"}
                         for row in rows]) if rows else None
    dataset_status = READY if not reasons else BLOCKED

    model_path = _runtime_path("model-manifest.json", env,
                               "A11OY_BRAIN_RERANKER_MODEL_MANIFEST")
    model = _verify_optional_manifest(model_path, MODEL_SCHEMA, dataset_hash or "") \
        if dataset_status == READY else {"status": BLOCKED, "reasons": ["DATASET_BLOCKED"],
                                         "receipt_sha256": UNKNOWN}
    model_hash = ((model.get("manifest") or {}).get("model_sha256")
                  if model.get("status") == READY else None)
    eval_path = _runtime_path("evaluation-manifest.json", env,
                              "A11OY_BRAIN_RERANKER_EVAL_MANIFEST")
    if dataset_status != READY:
        evaluation = {"status": BLOCKED, "reasons": ["DATASET_BLOCKED"],
                      "receipt_sha256": UNKNOWN}
    elif model.get("status") != READY:
        evaluation = {"status": BLOCKED, "reasons": ["MODEL_BLOCKED"],
                      "receipt_sha256": UNKNOWN}
    elif not split_counts["test"]:
        evaluation = {"status": BLOCKED, "reasons": ["TEST_SPLIT_EMPTY"],
                      "receipt_sha256": UNKNOWN}
    else:
        evaluation = _verify_optional_manifest(eval_path, EVAL_SCHEMA,
                                               dataset_hash or "", model_hash)
    return {
        "ok": True, "schema_version": SERVICE_SCHEMA, "label": "MEASURED",
        "rows": rows, "dataset_sha256": dataset_hash,
        "dataset_readiness": {"status": dataset_status, "reasons": reasons},
        "model_readiness": model, "evaluation_readiness": evaluation,
        "split_counts": split_counts, "example_type_counts": type_counts,
        "source_entity_group_count": len(groups), "split_leakage_group_count": leakage,
        "quarantined_rows": rejected, "ledger": ledger_state,
        "canonical_manifests_complete": True, "training_triggered": False,
    }


def append_validated_row(payload: Mapping[str, Any], ns: str = "a11oy",
                         repo_root: pathlib.Path | str | None = None,
                         environ: Mapping[str, str] | None = None,
                         ledger_path: pathlib.Path | str | None = None) -> tuple[dict, int]:
    """Append one hash-bound row after revalidating all local source bytes."""
    env = os.environ if environ is None else environ
    canonical = _canonical_context(repo_root, env)
    if not canonical["complete"]:
        return {"ok": False, "status": BLOCKED, "reasons": canonical["reasons"],
                "row": None}, 503
    docs, doc_error = _brain_docs(ns)
    if doc_error:
        return {"ok": False, "status": BLOCKED, "reasons": [doc_error], "row": None}, 503
    source = canonical["source_map"].get((str(payload.get("source_type") or ""),
                                           str(payload.get("source_entry_id") or "")))
    if source is None:
        return {"ok": False, "status": BLOCKED, "reasons": ["SOURCE_BINDING_NOT_VERIFIED"],
                "row": None}, 422
    required_hashes = {
        "source_manifest_sha256": source["manifest_sha256"],
        "source_artifact_sha256": source["artifact_sha256"],
    }
    mismatch = [key + "_MISMATCH" for key, expected in required_hashes.items()
                if str(payload.get(key) or "").lower() != expected]
    doc = docs.get(str(payload.get("brain_node_id") or ""), {})
    row, reasons = _row_core(payload, source, doc, "LOCAL_VALIDATED_APPEND")
    if mismatch or row is None:
        return {"ok": False, "status": BLOCKED,
                "reasons": sorted(set(mismatch + reasons)), "row": None}, 422
    path = pathlib.Path(ledger_path).resolve() if ledger_path else _ledger_path(env)
    with _LOCK:
        existing, state = _load_local_rows(path, canonical, docs)
        if not state["chain_valid"]:
            return {"ok": False, "status": BLOCKED,
                    "reasons": ["LOCAL_LEDGER_CHAIN_INVALID"], "row": None}, 409
        if state["record_count"] >= MAX_LOCAL_ROWS:
            return {"ok": False, "status": BLOCKED,
                    "reasons": ["LOCAL_ROW_LIMIT_REACHED"], "row": None}, 429
        if any(r["row_receipt_sha256"] == row["row_receipt_sha256"] for r in existing):
            return {"ok": True, "status": READY, "duplicate": True, "row": row}, 200
        prev = state["head_sha256"]
        record = {"schema_version": LEDGER_SCHEMA, "prev_hash": prev, "row": row}
        record["entry_sha256"] = _sha({"prev_hash": prev, "row": row})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return {"ok": True, "status": READY, "duplicate": False,
            "row": {**row, "ledger_entry_sha256": record["entry_sha256"]}}, 201


def _last_feed_state(path: pathlib.Path) -> dict[str, Any]:
    records, errors = _read_jsonl(path, MAX_LEDGER_BYTES)
    prev = "0" * 64
    valid = not errors
    last = None
    for i, record in enumerate(records):
        if not isinstance(record, dict) or record.get("schema_version") != FEED_SCHEMA:
            valid = False; errors.append(f"INVALID_FEED_RECORD:{i}"); continue
        stored = str(record.get("receipt_sha256") or "")
        body = {k: v for k, v in record.items() if k != "receipt_sha256"}
        if record.get("prev_hash") != prev or stored != _sha(body):
            valid = False; errors.append(f"FEED_CHAIN_MISMATCH:{i}"); continue
        prev, last = stored, record
    return {"chain_valid": valid, "record_count": len(records), "head_sha256": prev,
            "last": last, "errors": errors}


def feed_status(ns: str = "a11oy", repo_root: pathlib.Path | str | None = None,
                environ: Mapping[str, str] | None = None,
                feed_path: pathlib.Path | str | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    path = pathlib.Path(feed_path).resolve() if feed_path else _feed_path(env)
    state = _last_feed_state(path)
    enabled = str(env.get("A11OY_BRAIN_FEED_ENABLED", "0")).strip().lower() in {"1", "true", "yes"}
    killed = str(env.get("A11OY_BRAIN_FEED_KILL_SWITCH", "1")).strip().lower() not in {"0", "false", "no"}
    last = state.get("last") or {}
    return {
        "ok": True, "schema_version": FEED_SCHEMA,
        "status": (DEGRADED if enabled and not killed and state["chain_valid"] else UNAVAILABLE),
        "enabled": enabled, "kill_switch_engaged": killed,
        "network_access": False, "training_trigger": False,
        "stages": list(FEED_STAGES),
        "bounds": {"node_budget": FEED_NODE_BUDGET, "per_source_budget": FEED_SOURCE_BUDGET,
                   "minimum_interval_seconds": FEED_MIN_INTERVAL_S,
                   "maximum_backoff_seconds": FEED_MAX_BACKOFF_S,
                   "network_rate_limit": "ZERO_NETWORK_REQUESTS"},
        "checkpoint": last.get("checkpoint", "NOT_STARTED"),
        "last_successful_receipt": last.get("receipt_sha256", UNKNOWN),
        "last_inventory_sha256": last.get("inventory_sha256", UNKNOWN),
        "admitted_count": last.get("admitted_count", 0),
        "quarantined_count": last.get("quarantined_count", 0),
        "freshness_state": last.get("freshness_state", UNKNOWN),
        "next_refresh_utc": last.get("next_refresh_utc", UNKNOWN),
        "backoff_seconds": last.get("backoff_seconds", 0),
        "receipt_chain": {k: state[k] for k in ("chain_valid", "record_count", "head_sha256", "errors")},
    }


def refresh_feed(ns: str = "a11oy", repo_root: pathlib.Path | str | None = None,
                 environ: Mapping[str, str] | None = None,
                 feed_path: pathlib.Path | str | None = None) -> tuple[dict, int]:
    """Run one bounded local-only cycle; no network fetch and no training trigger."""
    env = os.environ if environ is None else environ
    path = pathlib.Path(feed_path).resolve() if feed_path else _feed_path(env)
    status = feed_status(ns, repo_root, env, path)
    if not status["enabled"] or status["kill_switch_engaged"]:
        return {**status, "ok": False, "reason": "FEED_DISABLED_OR_KILLED"}, 503
    state = _last_feed_state(path)
    last = state.get("last") or {}
    now = time.time()
    try:
        last_epoch = datetime.datetime.fromisoformat(str(last.get("completed_at"))).timestamp()
    except Exception:
        last_epoch = 0.0
    if last_epoch and now - last_epoch < FEED_MIN_INTERVAL_S:
        return {**status, "ok": False, "reason": "REFRESH_RATE_LIMITED"}, 429
    inventory = build_inventory(ns, repo_root, env)
    if inventory["inventory"]["raw_node_count"] > FEED_NODE_BUDGET:
        return {**status, "ok": False, "reason": "NODE_BUDGET_EXCEEDED"}, 503
    dataset = build_dataset(ns, repo_root, env)
    completed = _now()
    next_refresh = (datetime.datetime.now(datetime.timezone.utc) +
                    datetime.timedelta(seconds=FEED_MIN_INTERVAL_S)).isoformat()
    record = {
        "schema_version": FEED_SCHEMA,
        "prev_hash": state["head_sha256"],
        "checkpoint": f"inventory:{inventory['inventory_sha256']}:rows:{len(dataset['rows'])}",
        "completed_at": completed,
        "inventory_sha256": inventory["inventory_sha256"],
        "dataset_sha256": dataset.get("dataset_sha256") or UNKNOWN,
        "raw_node_count": inventory["inventory"]["raw_node_count"],
        "admitted_count": inventory["inventory"]["raw_node_count"] - inventory["inventory"]["quarantined_node_count"],
        "quarantined_count": inventory["inventory"]["quarantined_node_count"],
        "dataset_row_count": len(dataset["rows"]),
        "dataset_status": dataset["dataset_readiness"]["status"],
        "freshness_state": ("VERIFIED_SOURCE_TIMESTAMPS_PRESENT" if any(
            d["freshness_basis"] == "SOURCE_TIMESTAMP" for d in inventory["decisions"]
        ) else "UNVERIFIED"),
        "next_refresh_utc": next_refresh,
        "backoff_seconds": 0,
        "source_policy": {"network": "DENIED", "robots": "NOT_APPLICABLE_LOCAL_SNAPSHOT",
                          "license_unknown_quarantined": True, "provenance_required": True},
        "stage_results": [
            {"stage": stage, "status": (READY if stage != "EVALUATE" or
                                          dataset["evaluation_readiness"]["status"] == READY
                                          else BLOCKED)}
            for stage in FEED_STAGES
        ],
        "training_triggered": False,
    }
    record["receipt_sha256"] = _sha(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush(); os.fsync(handle.fileno())
    return {"ok": True, "status": DEGRADED, "receipt": record,
            "note": "Local evidence checkpoint written; no network or training occurred."}, 201


def anatomy_receipt(node_id: str, ns: str = "a11oy",
                    repo_root: pathlib.Path | str | None = None,
                    environ: Mapping[str, str] | None = None,
                    feed_path: pathlib.Path | str | None = None) -> tuple[dict, int]:
    inventory = build_inventory(ns, repo_root, environ)
    item = next((d for d in inventory["decisions"] if d["brain_node_id"] == node_id), None)
    if item is None:
        return {"ok": False, "status": UNAVAILABLE, "reason": "NODE_NOT_FOUND",
                "receipt_sha256": UNKNOWN}, 404
    feed = feed_status(ns, repo_root, environ, feed_path)
    loop_receipt = (feed["last_successful_receipt"]
                    if feed["last_inventory_sha256"] == inventory["inventory_sha256"]
                    else UNKNOWN)
    payload = {
        **item,
        "inventory_sha256": inventory["inventory_sha256"],
        "loop_checkpoint": feed["checkpoint"],
        "loop_receipt_sha256": loop_receipt,
        "receipt_state": "VERIFIED_CHAIN_REFERENCE" if loop_receipt != UNKNOWN else UNVERIFIED,
        "model_receipt_sha256": UNKNOWN,
        "evaluation_receipt_sha256": UNKNOWN,
        "note": "GET returns existing deterministic anatomy and loop linkage; it mints no receipt.",
    }
    return {"ok": True, "label": inventory["label"], "receipt_anatomy": payload,
            "receipt_sha256": loop_receipt}, 200


def service_status(ns: str = "a11oy", repo_root: pathlib.Path | str | None = None,
                   environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    dataset = build_dataset(ns, repo_root, environ)
    inventory = build_inventory(ns, repo_root, environ)
    feed = feed_status(ns, repo_root, environ)
    readiness = (
        dataset["dataset_readiness"]["status"],
        dataset["model_readiness"]["status"],
        dataset["evaluation_readiness"]["status"],
    )
    operational = all(state == READY for state in readiness)
    return {
        "ok": True, "schema_version": SERVICE_SCHEMA,
        # The inventory can be measured while the train/eval/model pipeline is still
        # unavailable.  Keep those truths separate so the estate rollup cannot turn
        # a measured node count into an operational model claim.
        "status": READY if operational else BLOCKED,
        "label": "MEASURED" if operational else UNAVAILABLE,
        "inventory_label": inventory["label"],
        "inventory": inventory["inventory"],
        "inventory_sha256": inventory["inventory_sha256"],
        "dataset": {"status": dataset["dataset_readiness"]["status"],
                    "reasons": dataset["dataset_readiness"]["reasons"],
                    "row_count": len(dataset["rows"]),
                    "dataset_sha256": dataset.get("dataset_sha256"),
                    "split_counts": dataset["split_counts"],
                    "example_type_counts": dataset["example_type_counts"]},
        "evaluation": dataset["evaluation_readiness"],
        "model": dataset["model_readiness"],
        "feed": feed,
        "training_triggered": False,
    }


def info() -> dict[str, Any]:
    return {
        "service": "a11oy.brain.evidence-reranker",
        "schema_version": SERVICE_SCHEMA,
        "readiness_dimensions": ["dataset", "evaluation", "model"],
        "required_example_types": list(EXAMPLE_TYPES),
        "split_rule": "sha256(source_type|source_entry_id|entity_id), 70/20/10",
        "feed_stages": list(FEED_STAGES),
        "network_access": False, "training_trigger": False,
        "write_paths": ["loopback validated-row append", "loopback feed checkpoint"],
        "bounds": {"local_rows": MAX_LOCAL_ROWS, "inventory_page": MAX_INVENTORY_PAGE,
                   "dataset_page": MAX_DATASET_PAGE, "node_budget": FEED_NODE_BUDGET},
        "honesty": "Missing canonical manifests or hashes => BLOCKED with zero rows.",
    }


def _loopback(host: Any) -> bool:
    value = str(host or "").strip().lower()
    if value in {"localhost", "testclient", "testserver"}: return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _local_request(request: Any) -> bool:
    """Require both transport peer and Host/URL to be loopback.

    Checking only ``request.client`` is not sufficient behind a same-host reverse
    proxy: a public request can otherwise appear to originate from 127.0.0.1.
    """
    client_host = getattr(getattr(request, "client", None), "host", None)
    url_host = getattr(getattr(request, "url", None), "hostname", None)
    return _loopback(client_host) and _loopback(url_host)


def register(app: Any, ns: str = "a11oy") -> list[str]:
    """Register bounded API routes before the SPA catch-all."""
    from fastapi.responses import JSONResponse
    base = f"/api/{ns}/v1/brain/reranker"
    paths: list[str] = []

    @app.get(base + "/info")
    def _info():
        return JSONResponse(info())
    paths.append(base + "/info")

    @app.get(base + "/status")
    def _status():
        return JSONResponse(service_status(ns))
    paths.append(base + "/status")

    # The holographic/frontier registry matches a surface id by exact route
    # segment.  This additive alias makes the ``brainreranker`` surface visible
    # to the estate status rollup while the structured canonical API remains
    # ``/brain/reranker/status``.
    @app.get(f"/api/{ns}/v1/brainreranker/status")
    def _surface_status():
        return JSONResponse(service_status(ns))
    paths.append(f"/api/{ns}/v1/brainreranker/status")

    @app.get(base + "/inventory")
    def _inventory(offset: int = 0, limit: int = 100, decision: str = ""):
        result = build_inventory(ns)
        selected = result["decisions"]
        if decision:
            selected = [d for d in selected if d["admission_decision"] == decision.upper()]
        start = max(0, int(offset)); page = selected[start:start + max(1, min(MAX_INVENTORY_PAGE, int(limit)))]
        return JSONResponse({k: v for k, v in result.items() if k != "decisions"} | {
            "offset": start, "limit": len(page), "total": len(selected),
            "next_offset": start + len(page) if start + len(page) < len(selected) else None,
            "decisions": page,
        })
    paths.append(base + "/inventory")

    @app.get(base + "/dataset")
    def _dataset(split: str = "", offset: int = 0, limit: int = 100):
        result = build_dataset(ns)
        selected = result["rows"]
        if split:
            selected = [r for r in selected if r["split"] == split.lower()]
        start = max(0, int(offset)); page = selected[start:start + max(1, min(MAX_DATASET_PAGE, int(limit)))]
        return JSONResponse({k: v for k, v in result.items() if k != "rows"} | {
            "offset": start, "limit": len(page), "total": len(selected),
            "next_offset": start + len(page) if start + len(page) < len(selected) else None,
            "rows": page,
        })
    paths.append(base + "/dataset")

    @app.get(base + "/feed")
    def _feed():
        return JSONResponse(feed_status(ns))
    paths.append(base + "/feed")

    @app.get(f"/api/{ns}/v1/anatomy/brain-receipt/{{node_id:path}}")
    def _anatomy(node_id: str):
        body, status = anatomy_receipt(node_id, ns)
        return JSONResponse(body, status_code=status)
    paths.append(f"/api/{ns}/v1/anatomy/brain-receipt/{{node_id:path}}")

    async def _append(request):
        if not _local_request(request):
            return JSONResponse({"ok": False, "status": BLOCKED,
                                 "reasons": ["LOCAL_CLIENT_REQUIRED"]}, status_code=403)
        try:
            payload = await request.json()
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return JSONResponse({"ok": False, "status": BLOCKED,
                                 "reasons": ["JSON_OBJECT_REQUIRED"]}, status_code=400)
        body, status = append_validated_row(payload, ns)
        return JSONResponse(body, status_code=status)

    async def _refresh(request):
        if not _local_request(request):
            return JSONResponse({"ok": False, "status": BLOCKED,
                                 "reason": "LOCAL_CLIENT_REQUIRED"}, status_code=403)
        body, status = refresh_feed(ns)
        return JSONResponse(body, status_code=status)

    try:
        import fastapi
        _append.__annotations__["request"] = fastapi.Request
        _refresh.__annotations__["request"] = fastapi.Request
    except Exception:
        pass
    app.router.add_route(base + "/rows", _append, methods=["POST"])
    app.router.add_route(base + "/feed/refresh", _refresh, methods=["POST"])
    paths.extend([base + "/rows", base + "/feed/refresh"])
    return paths
