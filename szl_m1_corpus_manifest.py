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
EXPECTED_RAW_NODES = 9462
EXPECTED_DISTINCT_ARTIFACTS = 4227
PERSON_KINDS = {"person", "author"}
LOCAL_LICENSED_KINDS = {"estate", "endpoint", "topic", "surface", "formula"}
FORMULA_STATUS_VOCABULARY = ["KERNEL_ACCEPTED", "CONDITIONAL", "OPEN", "REFUTED"]


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
    if kind == "formula":
        return "canonical-formula-registry"
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
    if family == "a11oy-versioned-runtime":
        return "TRAIN"
    if family in {"canonical-formula-registry", "thesis-formula-corpus"}:
        return "HOLDOUT"
    return "QUARANTINE"


def _formula_status(formula_id: str, meta: dict[str, Any]) -> str:
    locked = {"F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"}
    if formula_id in locked and str(meta.get("proof_status")) == "PROVED" and str(meta.get("lean_status")) == "PROVED":
        return "KERNEL_ACCEPTED"
    evidence = " ".join(str(meta.get(key) or "") for key in ("proof_status", "lean_status", "maturity", "status")).upper()
    if "REFUT" in evidence:
        return "REFUTED"
    if "CONDITIONAL" in evidence or "AXIOM-GATED" in evidence:
        return "CONDITIONAL"
    return "OPEN"


def _formula_canonical_text(formula_id: str, meta: dict[str, Any], status: str) -> str:
    text_parts = [f"formula_id: {formula_id}", f"formula_status: {status}"]
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
        if node.get("kind") == "formula" and node.get("formula_id"):
            stable = {key: value for key, value in node.items() if key not in {"degree"}}
            result[str(node["formula_id"])] = _receipt("brain-node", stable)
    return result


def _build_node_rows(nodes: list[dict[str, Any]], evaluation_receipt_id: str,
                     formula_receipts: dict[str, str]) -> list[dict[str, Any]]:
    from szl_puriq_formulas import FORMULA_META

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
        formula_id = str(node.get("formula_id") or "") if kind == "formula" else ""
        formula_status = _formula_status(formula_id, FORMULA_META.get(formula_id, {})) if formula_id else None
        if is_person:
            safety, decision = "QUARANTINE_PERSON_METADATA", "QUARANTINE"
        elif not locally_licensed:
            safety, decision = "QUARANTINE_LICENSE_UNKNOWN", "QUARANTINE"
        elif kind == "formula":
            safety, decision = "FORMULA_DUPLICATE_INDEX_ONLY", "INDEX_ONLY_DUPLICATE_FORMULA"
        else:
            safety, decision = "ALLOW_VERSIONED_LOCAL_METADATA", "INCLUDE_TRAIN_CONTEXT"
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
            "formula_id": formula_id or None,
            "formula_status": formula_status,
            "formula_receipt_id": formula_receipts.get(formula_id) if formula_id else None,
            "evaluation_receipt_id": evaluation_receipt_id,
            "canonical_text": canonical_text,
            "canonical_text_sha256": _sha(canonical_text.encode("utf-8")),
        })
    return rows


def _build_formula_rows(nodes: list[dict[str, Any]], evaluation_receipt_id: str) -> list[dict[str, Any]]:
    from szl_puriq_formulas import FORMULA_META

    graph_receipts = _graph_formula_receipts(nodes)
    rows: list[dict[str, Any]] = []
    sources: list[tuple[str, str, dict[str, Any]]] = [
        ("canonical-formula-registry", formula_id, dict(meta))
        for formula_id, meta in FORMULA_META.items()
    ]
    knowledge = json.loads((ROOT / "knowledge.json").read_text(encoding="utf-8"))
    for item in knowledge.get("formulas") or []:
        if isinstance(item, dict) and item.get("id"):
            sources.append(("thesis-formula-corpus", str(item["id"]), dict(item)))

    seen: set[tuple[str, str]] = set()
    for family, formula_id, meta in sorted(sources, key=lambda item: (item[0], item[1])):
        key = (family, formula_id)
        if key in seen:
            raise ValueError(f"formula source duplicate: {key}")
        seen.add(key)
        receipt_id, canonical_text, status = _formula_receipt_id(family, formula_id, meta)
        if status == "KERNEL_ACCEPTED":
            role = "HOLDOUT_POSITIVE"
        elif status == "REFUTED":
            role = "HOLDOUT_NEGATIVE"
        else:
            role = "HOLDOUT_ABSTENTION"
        rows.append({
            "schema": "szl.m1-formula-curriculum-decision/v1",
            "receipt_id": receipt_id,
            "formula_receipt_id": receipt_id,
            "brain_anatomy_receipt_id": graph_receipts.get(formula_id),
            "formula_id": formula_id,
            "source_family": family,
            "source_family_split": "HOLDOUT",
            "formula_status": status,
            "training_decision": role,
            "abstention_required": status in {"OPEN", "CONDITIONAL"},
            "negative_example": status == "REFUTED",
            "provenance": {
                "source": "szl_puriq_formulas.FORMULA_META" if family == "canonical-formula-registry" else "knowledge.json#/formulas",
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


def build() -> dict[str, Any]:
    from a11oy_brain_graph import get_brain_graph

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = get_brain_graph(refresh=True)
    nodes = list(graph.get("nodes") or [])
    if len(nodes) != EXPECTED_RAW_NODES:
        raise ValueError(f"expected {EXPECTED_RAW_NODES} Brain nodes, observed {len(nodes)}")
    distinct = sum(1 for node in nodes if str(node.get("kind") or "").lower() not in PERSON_KINDS)
    if distinct != EXPECTED_DISTINCT_ARTIFACTS:
        raise ValueError(f"expected {EXPECTED_DISTINCT_ARTIFACTS} distinct artifacts, observed {distinct}")

    evaluation_sha = _sha_file(EVALUATION_MANIFEST)
    evaluation_receipt_id = f"m1-evaluation:sha256:{evaluation_sha}"
    from szl_puriq_formulas import FORMULA_META
    formula_receipts = {
        formula_id: _formula_receipt_id("canonical-formula-registry", formula_id, dict(meta))[0]
        for formula_id, meta in FORMULA_META.items()
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
            "raw_node_count": len(node_rows),
            "distinct_artifact_count": distinct,
            "person_metadata_count": len(node_rows) - distinct,
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
            "node_decisions_expected": EXPECTED_RAW_NODES,
            "node_decision_coverage": 1.0,
            "distinct_artifacts": distinct,
            "person_metadata": len(node_rows) - distinct,
            "node_decisions": dict(sorted(node_decisions.items())),
            "node_safety": dict(sorted(node_safety.items())),
            "formula_records_current_versioned_sources": len(formula_rows),
            "formula_requested_200_claim": "NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES",
            "formula_status_vocabulary": FORMULA_STATUS_VOCABULARY,
            "formula_status": {status: formula_status.get(status, 0) for status in FORMULA_STATUS_VOCABULARY},
            "formula_roles": dict(sorted(formula_roles.items())),
            "abstention_examples": sum(bool(row["abstention_required"]) for row in formula_rows),
            "negative_examples": sum(bool(row["negative_example"]) for row in formula_rows),
            "quarantined_or_excluded_nodes": sum(value for key, value in node_decisions.items() if key.startswith("QUARANTINE")),
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
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=True, sort_keys=True))
