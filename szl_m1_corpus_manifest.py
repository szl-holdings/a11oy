#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the deterministic, fail-closed M1 corpus decision ledgers.

This module is an accounting and evaluation-readiness tool.  It reads only
versioned local sources, performs no network calls, and never trains or promotes
a model.  Every Brain graph node receives an explicit decision.  External
metadata without an item-level license and person metadata are quarantined;
they are never silently converted into training text.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "model_release" / "m1"
GRAPH_LEDGER = OUT_DIR / "brain-ingest-ledger.jsonl"
FORMULA_LEDGER = OUT_DIR / "formula-curriculum-ledger.jsonl"
CORPUS_MANIFEST = OUT_DIR / "corpus-ingestion-manifest.json"
EVALUATION_MANIFEST = OUT_DIR / "evaluation-manifest.json"
PERSON_KINDS = {"person", "author"}
LOCAL_LICENSED_KINDS = {"estate", "endpoint", "topic", "surface", "formula"}
FORMULA_STATUS_VOCABULARY = ["KERNEL_ACCEPTED", "CONDITIONAL", "OPEN", "REFUTED"]
NUMERIC_NAMESPACE = "puriq.numeric-demo.v1"
THESIS_NAMESPACE = "knowledge.formula-history.v1"
NUMERIC_SOURCE_FAMILY = "puriq-numeric-demonstrations"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receipt(prefix: str, value: Any) -> str:
    return f"{prefix}:sha256:{_sha(_canonical(value))}"


def _source_family(node: dict[str, Any]) -> str:
    kind = str(node.get("kind") or "unknown").lower()
    source = str(node.get("source") or "").lower()
    if kind in PERSON_KINDS:
        return "authorship-person-metadata"
    if kind in {"formula", "formal_formula"}:
        # Graph membership and a matching short F-ID establish no proof
        # applicability. Keep both namespaces quarantined as index metadata.
        return "brain-raw-formal-index" if kind == "formal_formula" else "brain-raw-formula-index"
    if kind in {"estate", "endpoint", "topic", "surface"} and int(node.get("layer", -1)) >= 0:
        return "a11oy-versioned-runtime"
    if kind == "repo" or "github" in source or "gitlab" in source:
        return "repository-metadata"
    if kind == "paper" or "arxiv" in source:
        return "academic-publication-metadata"
    if kind in {"dataset", "benchmark"}:
        return "dataset-benchmark-metadata"
    if kind in {"standard", "org", "lab", "axis"}:
        return "research-landscape-metadata"
    return "other-graph-metadata"


def _split_for_family(family: str) -> str:
    # Raw Brain rows are inventory, never training data.  Admitted canonical
    # rows are built by the separate evidence/formula generators.
    return "QUARANTINE"


def _formula_status(formula_id: str, meta: dict[str, Any]) -> str:
    """Raw numeric and historical declarations carry no admitted proof binding.

    Neither an F-ID nor strings such as PROVED/REFUTED identify the statement,
    assumptions and source evidence that this curriculum would need to accept
    a proof or a refutation. Formal registry metadata is a separate namespace;
    this generator does not perform that admission.
    """
    return "OPEN"


def _formula_canonical_text(formula_id: str, meta: dict[str, Any], status: str) -> str:
    text_parts = [f"formula_id: {formula_id}", f"formula_status: {status}",
                  f"formula_namespace: {meta.get('formula_namespace', 'UNKNOWN')}",
                  "formal_binding: UNKNOWN_NOT_ASSERTED"]
    for field in ("name", "primitive", "identity_doc", "latex", "context", "source_file", "source_line"):
        if meta.get(field) not in (None, ""):
            text_parts.append(f"{field}: {meta[field]}")
    return "\n".join(text_parts)


def _formula_receipt_id(family: str, formula_id: str, meta: dict[str, Any]) -> tuple[str, str, str]:
    status = _formula_status(formula_id, meta)
    canonical_text = _formula_canonical_text(formula_id, meta, status)
    text_sha = _sha(canonical_text.encode("utf-8"))
    stable = {"source_family": family, "formula_id": formula_id,
              "formula_status": status, "canonical_text_sha256": text_sha}
    return _receipt("formula", stable), canonical_text, status


def _node_canonical_text(node: dict[str, Any]) -> str:
    fields = [
        f"title: {str(node.get('title') or '').strip()}",
        f"kind: {str(node.get('kind') or 'unknown')}",
        f"evidence_label: {str(node.get('label') or 'UNKNOWN')}",
    ]
    for key in ("axis", "organ", "primitive", "source", "url", "path", "note"):
        value = node.get(key)
        if value not in (None, ""):
            fields.append(f"{key}: {str(value).strip()}")
    return "\n".join(fields)


def _graph_formula_receipts(nodes: Iterable[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in nodes:
        if (node.get("kind") == "formula" and node.get("formula_id")
                and node.get("formula_namespace") == NUMERIC_NAMESPACE):
            stable = {key: value for key, value in node.items() if key not in {"degree"}}
            result[str(node["formula_id"])] = _receipt("brain-node", stable)
    return result


def _build_node_rows(nodes: list[dict[str, Any]], evaluation_receipt_id: str,
                     formula_receipts: dict[str, str]) -> list[dict[str, Any]]:
    from szl_puriq_formulas import numeric_demo_metadata

    numeric_metadata = numeric_demo_metadata()
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for node in sorted(nodes, key=lambda item: str(item.get("id") or "")):
        node_id = str(node.get("id") or "")
        if not node_id or node_id in seen_ids:
            raise ValueError(f"Brain node id is absent or duplicated: {node_id!r}")
        seen_ids.add(node_id)
        stable = {key: value for key, value in node.items() if key not in {"degree"}}
        receipt_id = _receipt("brain-node", stable)
        family = _source_family(node)
        split = _split_for_family(family)
        kind = str(node.get("kind") or "unknown").lower()
        is_person = kind in PERSON_KINDS
        locally_licensed = int(node.get("layer", -1)) >= 0 and kind in LOCAL_LICENSED_KINDS
        is_formula = kind in {"formula", "formal_formula"}
        formula_id = str(node.get("formula_id") or "") if is_formula else ""
        namespace = node.get("formula_namespace") if is_formula else None
        formula_status = _formula_status(formula_id, numeric_metadata.get(formula_id, {})) if formula_id else None
        if is_person:
            safety = "QUARANTINE_PERSON_METADATA"
        elif is_formula:
            safety = "QUARANTINE_RAW_GRAPH_DUPLICATE_FORMULA"
        elif not locally_licensed:
            safety = "QUARANTINE_LICENSE_UNKNOWN"
        else:
            safety = "QUARANTINE_RAW_GRAPH_NOT_ADMITTED"
        decision = "QUARANTINE"
        canonical_text = _node_canonical_text(node)
        capture = node.get("captured_at") or node.get("harvested_at")
        freshness = "CAPTURED_SOURCE_DATE" if capture else (
            "VERSION_BOUND_NOT_TIME_FRESH" if locally_licensed else "UNKNOWN_NO_SOURCE_TIMESTAMP"
        )
        rows.append({
            "schema": "szl.m1-brain-ingest-decision/v1",
            "receipt_id": receipt_id,
            "brain_anatomy_receipt_id": receipt_id,
            "node_id": node_id,
            "canonical_artifact_id": node_id if not is_person else None,
            "artifact_role": "ATTRIBUTION_METADATA" if is_person else "DISTINCT_ARTIFACT",
            "kind": kind,
            "source_family": family,
            "source_family_split": split,
            "provenance": {
                "source": node.get("source") or node.get("derived_from") or "versioned-local-graph",
                "url": node.get("url"),
                "captured_at": capture,
                "evidence_label": node.get("label") or "UNKNOWN",
                "graph_node_receipt_id": receipt_id,
            },
            "license": {
                "spdx": "Apache-2.0" if locally_licensed else None,
                "state": "VERSIONED_REPOSITORY_LICENSE" if locally_licensed else "UNKNOWN_ITEM_LEVEL_LICENSE",
                "evidence": "LICENSE" if locally_licensed else None,
            },
            "freshness": {"state": freshness, "captured_at": capture},
            "safety_decision": safety,
            "training_decision": decision,
            "training_eligible": False,
            "formula_id": formula_id or None,
            **({"formula_namespace": namespace, "formal_binding": "UNKNOWN_NOT_ASSERTED"}
               if is_formula else {}),
            "formula_status": formula_status,
            "formula_receipt_id": (formula_receipts.get(formula_id)
                                   if formula_id and namespace == NUMERIC_NAMESPACE else None),
            "evaluation_receipt_id": evaluation_receipt_id,
            "canonical_text": canonical_text,
            "canonical_text_sha256": _sha(canonical_text.encode("utf-8")),
        })
    return rows


def _build_formula_rows(nodes: list[dict[str, Any]], evaluation_receipt_id: str) -> list[dict[str, Any]]:
    from szl_puriq_formulas import numeric_demo_metadata

    graph_receipts = _graph_formula_receipts(nodes)
    rows: list[dict[str, Any]] = []
    sources: list[tuple[str, str, dict[str, Any]]] = [
        (NUMERIC_SOURCE_FAMILY, formula_id, dict(meta))
        for formula_id, meta in numeric_demo_metadata().items()
    ]
    knowledge = json.loads((ROOT / "knowledge.json").read_text(encoding="utf-8"))
    for item in knowledge.get("formulas") or []:
        if isinstance(item, dict) and item.get("id"):
            sources.append(("thesis-formula-corpus", str(item["id"]), {
                **item, "formula_namespace": THESIS_NAMESPACE,
                "formal_binding": "UNKNOWN_NOT_ASSERTED",
            }))

    seen: set[tuple[str, str]] = set()
    for family, formula_id, meta in sorted(sources, key=lambda item: (item[0], item[1])):
        key = (family, formula_id)
        if key in seen:
            raise ValueError(f"formula source duplicate: {key}")
        seen.add(key)
        receipt_id, canonical_text, status = _formula_receipt_id(family, formula_id, meta)
        role = "HOLDOUT_ABSTENTION"
        namespace = NUMERIC_NAMESPACE if family == NUMERIC_SOURCE_FAMILY else THESIS_NAMESPACE
        rows.append({
            "schema": "szl.m1-formula-curriculum-decision/v1",
            "receipt_id": receipt_id,
            "formula_receipt_id": receipt_id,
            "brain_anatomy_receipt_id": (graph_receipts.get(formula_id)
                                         if namespace == NUMERIC_NAMESPACE else None),
            "formula_id": formula_id,
            "formula_namespace": namespace,
            "record_id": f"{namespace}:{formula_id}",
            "formal_binding": "UNKNOWN_NOT_ASSERTED",
            "can_authorize_action": False,
            "source_family": family,
            "source_family_split": "HOLDOUT",
            "formula_status": status,
            "training_decision": role,
            "training_eligible": False,
            "abstention_required": True,
            "negative_example": False,
            "provenance": {
                "source": "szl_puriq_formulas.numeric_demo_metadata" if family == NUMERIC_SOURCE_FAMILY else "knowledge.json#/formulas",
                "authority": "NUMERIC_DEMONSTRATION_ONLY" if family == NUMERIC_SOURCE_FAMILY else "HISTORICAL_DECLARATION_ONLY",
                "source_file": meta.get("source_file"),
                "source_line": meta.get("source_line"),
            },
            "license": {"spdx": "Apache-2.0", "state": "VERSIONED_REPOSITORY_LICENSE", "evidence": "LICENSE"},
            "freshness": {"state": "VERSION_BOUND_NOT_TIME_FRESH", "captured_at": None},
            "safety_decision": "ALLOW_HOLDOUT_ONLY",
            "evaluation_receipt_id": evaluation_receipt_id,
            "canonical_text": canonical_text,
            "canonical_text_sha256": _sha(canonical_text.encode("utf-8")),
        })
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _load_proposal_bindings() -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the proposal-only write boundary before regenerating artifacts."""
    candidate = json.loads((OUT_DIR / "candidate-manifest.json").read_text(encoding="utf-8"))
    operational = json.loads((OUT_DIR / "operational-manifest.json").read_text(encoding="utf-8"))
    identity = "a11oy-evidence-1.5b-sft-lora"
    for document in (candidate, operational):
        if (document.get("candidate_id") != identity
                or document.get("release_state") != "NOT_PROMOTED"
                or document.get("quality_claim") != "NOT_ESTABLISHED"):
            raise ValueError("M1_PROPOSAL_REFRESH_REQUIRES_UNPROMOTED_CANDIDATE")
    proposal = candidate.get("full_corpus_proposal") or {}
    policy = operational.get("corpus_policy") or {}
    relation = "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER"
    if (proposal.get("relation") != relation or proposal.get("training_state") != "NOT_RUN"
            or proposal.get("manifest_path") != CORPUS_MANIFEST.name
            or policy.get("training_relation") != relation
            or policy.get("require_raw_brain_training_quarantine") is not True):
        raise ValueError("M1_PROPOSAL_REFRESH_CANNOT_REBIND_TRAINED_DATA")
    evidence = operational.get("evidence") or {}
    paths = {
        "candidate_manifest": "candidate-manifest.json",
        "corpus_ingestion_manifest": CORPUS_MANIFEST.name,
        "brain_ingest_ledger": GRAPH_LEDGER.name,
        "formula_curriculum_ledger": FORMULA_LEDGER.name,
    }
    if any(not isinstance(evidence.get(key), dict)
           or evidence[key].get("path") != name for key, name in paths.items()):
        raise ValueError("M1_PROPOSAL_EVIDENCE_PATH_MISMATCH")
    return candidate, operational


def _refresh_proposal_bindings(manifest: dict[str, Any],
                               bindings: tuple[dict[str, Any], dict[str, Any]]) -> None:
    """Refresh only source-proposal counts and digests, never trained identities.

    This is the producer's acyclic write order: ledgers -> corpus manifest ->
    candidate proposal -> operational evidence references. Adapter, base,
    dataset, training/reload receipts and promotion policy remain unchanged.
    """
    candidate, operational = bindings
    coverage = manifest["coverage"]
    raw_count = manifest["source_snapshot"]["raw_node_count"]
    distinct = manifest["source_snapshot"]["distinct_artifact_count"]
    formulas = coverage["formula_records_current_versioned_sources"]
    candidate["full_corpus_proposal"].update({
        "manifest_sha256": _sha_file(CORPUS_MANIFEST),
        "brain_raw_nodes": raw_count,
        "brain_distinct_artifacts": distinct,
        "formula_records": formulas,
    })
    candidate_path = OUT_DIR / "candidate-manifest.json"
    candidate_path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False, sort_keys=True)
                              + "\n", encoding="utf-8", newline="\n")
    operational["corpus_policy"].update({
        "expected_raw_nodes": raw_count,
        "expected_distinct_artifacts": distinct,
        "expected_formula_records": formulas,
    })
    paths = {
        "candidate_manifest": candidate_path,
        "corpus_ingestion_manifest": CORPUS_MANIFEST,
        "brain_ingest_ledger": GRAPH_LEDGER,
        "formula_curriculum_ledger": FORMULA_LEDGER,
    }
    for key, path in paths.items():
        operational["evidence"][key].update({"bytes": path.stat().st_size, "sha256": _sha_file(path)})
    operational["evidence"]["brain_ingest_ledger"]["rows"] = raw_count
    operational["evidence"]["formula_curriculum_ledger"]["rows"] = formulas
    (OUT_DIR / "operational-manifest.json").write_text(
        json.dumps(operational, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")


def build() -> dict[str, Any]:
    from a11oy_brain_graph import get_brain_graph

    bindings = _load_proposal_bindings()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = get_brain_graph(refresh=True)
    nodes = list(graph.get("nodes") or [])
    expected_raw_nodes = len(nodes)
    raw_node_count = expected_raw_nodes
    if raw_node_count <= 0:
        raise ValueError("Brain graph must contain at least one node")
    distinct = sum(1 for node in nodes if str(node.get("kind") or "").lower() not in PERSON_KINDS)
    expected_distinct_artifacts = distinct
    if expected_distinct_artifacts > raw_node_count:
        raise ValueError(
            f"distinct artifacts {expected_distinct_artifacts} cannot exceed raw nodes {raw_node_count}"
        )

    evaluation_sha = _sha_file(EVALUATION_MANIFEST)
    evaluation_receipt_id = f"m1-evaluation:sha256:{evaluation_sha}"
    from szl_puriq_formulas import numeric_demo_metadata
    formula_receipts = {
        formula_id: _formula_receipt_id(NUMERIC_SOURCE_FAMILY, formula_id, dict(meta))[0]
        for formula_id, meta in numeric_demo_metadata().items()
    }
    node_rows = _build_node_rows(nodes, evaluation_receipt_id, formula_receipts)
    formula_rows = _build_formula_rows(nodes, evaluation_receipt_id)
    _write_jsonl(GRAPH_LEDGER, node_rows)
    _write_jsonl(FORMULA_LEDGER, formula_rows)

    node_decisions = Counter(row["training_decision"] for row in node_rows)
    node_safety = Counter(row["safety_decision"] for row in node_rows)
    formula_status = Counter(row["formula_status"] for row in formula_rows)
    formula_roles = Counter(row["training_decision"] for row in formula_rows)
    source_families: dict[str, dict[str, Any]] = {}
    for row in [*node_rows, *formula_rows]:
        family = row["source_family"]
        entry = source_families.setdefault(family, {"split": row["source_family_split"], "rows": 0})
        if entry["split"] != row["source_family_split"]:
            raise ValueError(f"source family leakage across splits: {family}")
        entry["rows"] += 1

    stable_nodes = [{key: value for key, value in node.items() if key != "degree"}
                    for node in sorted(nodes, key=lambda item: str(item.get("id") or ""))]
    graph_snapshot_sha = _sha(_canonical(stable_nodes))
    manifest = {
        "schema": "szl.m1-corpus-ingestion-manifest/v1",
        "candidate_id": "a11oy-evidence-1.5b-sft-lora",
        "release_state": "NOT_PROMOTED",
        "training_state": "NOT_RUN",
        "training_relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
        "quality_claim": "NOT_ESTABLISHED",
        "source_snapshot": {
            "brain_graph_receipt_id": f"brain-graph:sha256:{graph_snapshot_sha}",
            "brain_graph_sha256": graph_snapshot_sha,
            "raw_node_count": raw_node_count,
            "distinct_artifact_count": expected_distinct_artifacts,
            "person_metadata_count": raw_node_count - expected_distinct_artifacts,
            "link_count_reported_by_graph": graph.get("link_count"),
            "versioned_sources_only": True,
            "network_fetches": 0,
        },
        "ledgers": {
            "brain_nodes": {"path": GRAPH_LEDGER.name, "rows": len(node_rows), "bytes": GRAPH_LEDGER.stat().st_size,
                            "sha256": _sha_file(GRAPH_LEDGER), "schema": "szl.m1-brain-ingest-decision/v1"},
            "formulas": {"path": FORMULA_LEDGER.name, "rows": len(formula_rows), "bytes": FORMULA_LEDGER.stat().st_size,
                         "sha256": _sha_file(FORMULA_LEDGER), "schema": "szl.m1-formula-curriculum-decision/v1"},
        },
        "coverage": {
            "node_decisions_total": len(node_rows),
            "node_decisions_expected": raw_node_count,
            "node_decision_coverage": 1.0,
            "distinct_artifacts": expected_distinct_artifacts,
            "person_metadata": raw_node_count - expected_distinct_artifacts,
            "node_decisions": dict(sorted(node_decisions.items())),
            "node_safety": dict(sorted(node_safety.items())),
            "raw_nodes_training_quarantined": sum(not bool(row["training_eligible"]) for row in node_rows),
            "training_eligible_nodes": sum(bool(row["training_eligible"]) for row in node_rows),
            "formula_records_current_versioned_sources": len(formula_rows),
            "formula_requested_200_claim": "NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES",
            "formula_status_vocabulary": FORMULA_STATUS_VOCABULARY,
            "formula_status": {status: formula_status.get(status, 0) for status in FORMULA_STATUS_VOCABULARY},
            "formula_roles": dict(sorted(formula_roles.items())),
            "abstention_examples": sum(bool(row["abstention_required"]) for row in formula_rows),
            "negative_examples": sum(bool(row["negative_example"]) for row in formula_rows),
            "quarantined_or_excluded_nodes": sum(not bool(row["training_eligible"]) for row in node_rows),
            "missing_item_level_license_nodes": sum(row["license"]["state"] == "UNKNOWN_ITEM_LEVEL_LICENSE" for row in node_rows),
            "missing_source_timestamp_nodes": sum(row["freshness"]["state"] == "UNKNOWN_NO_SOURCE_TIMESTAMP" for row in node_rows),
        },
        "source_family_split": dict(sorted(source_families.items())),
        "leakage_policy": "all rows from one source_family have exactly one split; formula families are HOLDOUT; quarantined rows are never training text",
        "resulting_evaluation_receipt": {
            "receipt_id": evaluation_receipt_id,
            "path": EVALUATION_MANIFEST.name,
            "bytes": EVALUATION_MANIFEST.stat().st_size,
            "sha256": evaluation_sha,
            "state": "INCOMPLETE",
            "promotion_decision": "NOT_PROMOTED",
        },
    }
    CORPUS_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    _refresh_proposal_bindings(manifest, bindings)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=True, sort_keys=True))
