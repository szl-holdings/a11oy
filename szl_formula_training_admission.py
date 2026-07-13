#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a deterministic, fail-closed formula admission tranche.

The builder joins only versioned local evidence.  It does not access the
network, start training, or transfer proof credit between formula namespaces.
The raw Brain is inventory-only: no raw node text is emitted into the tranche.

Taxonomy: governance / provenance.  This is an offline admission and receipt
builder; it serves no route and therefore needs no Dockerfile registration.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
from typing import Any, Iterable, Mapping, Sequence


ROOT = pathlib.Path(__file__).resolve().parent
OUTPUT_DIR = pathlib.Path("research/formula-training-admission")
CROSSWALK = OUTPUT_DIR / "formula-id-crosswalk.json"
TRANCHE = OUTPUT_DIR / "admission-tranche.jsonl"
MANIFEST = OUTPUT_DIR / "admission-manifest.json"
RECEIPT = OUTPUT_DIR / "artifact-receipt.json"

STATUS_VOCABULARY = ("KERNEL_ACCEPTED", "CONDITIONAL", "OPEN", "REFUTED")
LOCKED_IDS = frozenset({"F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"})
RUNTIME_NAMESPACE = "puriq-runtime-registry"
PROOF_NAMESPACE = "puriq-lean-proof-pack"
THESIS_NAMESPACE = "thesis-extracted-formulas"

KNOWLEDGE = pathlib.Path("knowledge.json")
STATIC_THESIS = pathlib.Path("static/thesis.json")
M1_MANIFEST = pathlib.Path("model_release/m1/corpus-ingestion-manifest.json")
M1_BRAIN_LEDGER = pathlib.Path("model_release/m1/brain-ingest-ledger.jsonl")
M1_FORMULA_LEDGER = pathlib.Path("model_release/m1/formula-curriculum-ledger.jsonl")
SZL_LAKE_MANIFEST = pathlib.Path("data/szl-lake/evidence-manifest.json")
SZL_LAKE_DATA = pathlib.Path("data/szl-lake/reranker-evidence.json")
CANONICAL_INDEX = pathlib.Path("research/brain-evidence-admission/canonical-index.json")
CANONICAL_EVIDENCE = pathlib.Path("research/brain-evidence-admission/evidence-manifest.json")
LEAN_TREE = pathlib.Path("proofs/lean-theorem-tree.json")
LEAN_SOURCES = (
    pathlib.Path("proofs/lutar-lean/Lutar/Puriq/Formulas/PuriqFormulaLean.lean"),
    pathlib.Path("proofs/lutar-lean/Lutar/Puriq/Formulas/ProvedFormulas.lean"),
    pathlib.Path("proofs/lutar-lean/Lutar/Round13/Lambda_Uniqueness.lean"),
)


class AdmissionError(RuntimeError):
    """Raised when a source or honesty invariant cannot be established."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_value(value: Any) -> str:
    return _sha_bytes(_canonical_bytes(value))


def _sha_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(root: pathlib.Path, relative: pathlib.Path) -> Any:
    path = root / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"INVALID_JSON:{relative}:{type(exc).__name__}") from exc


def _read_jsonl(root: pathlib.Path, relative: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with (root / relative).open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise AdmissionError(f"JSONL_ROW_NOT_OBJECT:{relative}:{line_number}")
                rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"INVALID_JSONL:{relative}:{type(exc).__name__}") from exc
    return rows


def _receipted(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(payload)
    result[field] = _sha_value(payload)
    return result


def _natural_formula_key(formula_id: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"([A-Za-z_-]*?)(\d+)", formula_id)
    if match:
        return match.group(1), int(match.group(2)), formula_id
    return formula_id, -1, formula_id


def _lean_inventory(root: pathlib.Path) -> dict[str, Any]:
    declarations: set[str] = set()
    files: list[dict[str, Any]] = []
    pattern = re.compile(r"(?m)^\s*(?:theorem|lemma|def)\s+([A-Za-z0-9_'.]+)\b")
    for relative in LEAN_SOURCES:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        found = sorted(set(pattern.findall(text)))
        declarations.update(found)
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha_file(path),
                "declaration_count": len(found),
            }
        )
    tree = _load_json(root, LEAN_TREE)
    return {
        "declarations": declarations,
        "files": files,
        "tree": {
            "path": LEAN_TREE.as_posix(),
            "sha256": _sha_file(root / LEAN_TREE),
            "commit": str((tree.get("meta") or {}).get("commit") or "UNKNOWN"),
            "total_declarations": int(
                (tree.get("meta") or {}).get("total_declarations") or 0
            ),
            "note": str((tree.get("meta") or {}).get("note") or ""),
        },
    }


def _brain_and_m1_state(root: pathlib.Path) -> dict[str, Any]:
    from a11oy_brain_graph import get_brain_graph
    import szl_brain_reranker

    graph = get_brain_graph(refresh=True)
    inventory = szl_brain_reranker.build_inventory(repo_root=root, environ={})
    summary = inventory.get("inventory") or {}
    raw_count = int(summary.get("raw_node_count") or 0)
    decisions = int(summary.get("decision_count") or 0)
    quarantined = int(summary.get("quarantined_node_count") or 0)
    if raw_count != 9464 or decisions != raw_count or quarantined != raw_count:
        raise AdmissionError(
            f"RAW_BRAIN_BOUNDARY_MISMATCH:{raw_count}:{decisions}:{quarantined}"
        )
    current_nodes = list(graph.get("nodes") or [])
    current_ids = {str(node.get("id") or "") for node in current_nodes}
    if len(current_nodes) != raw_count or len(current_ids) != raw_count or "" in current_ids:
        raise AdmissionError("RAW_BRAIN_NODE_IDS_INVALID")

    m1_manifest = _load_json(root, M1_MANIFEST)
    m1_ids: set[str] = set()
    m1_training_eligible = 0
    m1_rows = 0
    with (root / M1_BRAIN_LEDGER).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            node_id = str(row.get("node_id") or "")
            if not node_id or node_id in m1_ids:
                raise AdmissionError(f"M1_NODE_ID_INVALID:{line_number}:{node_id}")
            m1_ids.add(node_id)
            if row.get("training_eligible") is not False or row.get("training_decision") != "QUARANTINE":
                m1_training_eligible += 1
            m1_rows += 1
    manifest_rows = int(
        (((m1_manifest.get("ledgers") or {}).get("brain_nodes") or {}).get("rows"))
        or 0
    )
    if manifest_rows != m1_rows or m1_rows != raw_count:
        raise AdmissionError(f"M1_LEDGER_COUNT_MISMATCH:{manifest_rows}:{m1_rows}")
    added = sorted(current_ids - m1_ids)
    removed = sorted(m1_ids - current_ids)
    if added or removed:
        raise AdmissionError(f"UNEXPECTED_M1_DRIFT:{added}:{removed}")
    if m1_training_eligible:
        raise AdmissionError(f"M1_RAW_TRAINING_ELIGIBILITY:{m1_training_eligible}")

    formula_nodes = {
        str(node.get("formula_id")): node
        for node in current_nodes
        if node.get("kind") == "formula" and node.get("formula_id")
    }
    if len(formula_nodes) != 23:
        raise AdmissionError(f"BRAIN_FORMULA_COUNT_MISMATCH:{len(formula_nodes)}")
    return {
        "graph": graph,
        "formula_nodes": formula_nodes,
        "inventory": inventory,
        "current_ids": current_ids,
        "m1_ids": m1_ids,
        "m1_manifest": m1_manifest,
        "m1_rows": m1_rows,
        "added": added,
        "removed": removed,
    }


def _m1_formula_index(root: pathlib.Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows = _read_jsonl(root, M1_FORMULA_LEDGER)
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("source_family") or ""), str(row.get("formula_id") or ""))
        if not all(key) or key in result:
            raise AdmissionError(f"M1_FORMULA_KEY_INVALID:{key}")
        result[key] = row
    if len(rows) != 123:
        raise AdmissionError(f"M1_FORMULA_COUNT_MISMATCH:{len(rows)}")
    return result


def _proof_status(
    item: Mapping[str, Any],
    static_item: Mapping[str, Any],
    declarations: set[str],
    summary_locked: set[str],
) -> tuple[str, list[str]]:
    formula_id = str(item["id"])
    lean_ref = str(item.get("lean_ref") or "")
    exact_ref = lean_ref in declarations
    item_locked = item.get("locked_kernel") is True
    static_locked = static_item.get("locked_kernel") is True
    reasons: list[str] = [
        "EXACT_LEAN_REFERENCE_PRESENT" if exact_ref else "EXACT_LEAN_REFERENCE_MISSING"
    ]
    if formula_id == "F23":
        reasons.extend(
            [
                "UNCONDITIONAL_UNIQUENESS_REFUTED_BY_MAX_AGG_COUNTEREXAMPLE",
                "CONDITIONAL_FACTORIZATION_THEOREM_DOES_NOT_RESTORE_UNCONDITIONAL_CLAIM",
            ]
        )
        return "REFUTED", reasons
    if (
        formula_id in LOCKED_IDS
        and formula_id in summary_locked
        and item_locked
        and static_locked
        and exact_ref
    ):
        reasons.append("ITEM_LEVEL_LOCKED_BINDING_AGREES")
        return "KERNEL_ACCEPTED", reasons
    if formula_id in LOCKED_IDS:
        reasons.append("LOCKED_SUMMARY_ITEM_BINDING_DISAGREES_OR_IS_UNRESOLVED")
    elif "axiom-gated" in str(item.get("maturity") or "").lower():
        reasons.append("DECLARED_AXIOM_GATED")
    else:
        reasons.append("EXPERIMENTAL_OR_UNPINNED_PROOF_SCOPE")
    return "CONDITIONAL", reasons


def _crosswalk_records(root: pathlib.Path, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    import szl_puriq_formulas

    knowledge = _load_json(root, KNOWLEDGE)
    static = _load_json(root, STATIC_THESIS)
    m1 = _m1_formula_index(root)
    lean = _lean_inventory(root)
    declarations: set[str] = lean["declarations"]
    proof_items = {str(item["id"]): item for item in knowledge.get("puriq_formulas") or []}
    static_items = {str(item["id"]): item for item in static.get("proven_formulas") or []}
    runtime_items = {str(key): value for key, value in szl_puriq_formulas.FORMULA_META.items()}
    expected = {f"F{index}" for index in range(1, 24)}
    if set(proof_items) != expected or set(static_items) != expected or set(runtime_items) != expected:
        raise AdmissionError("PURIQ_ID_SET_MISMATCH")
    summary_locked = set((knowledge.get("proof_summary") or {}).get("locked_ids") or [])
    if summary_locked != LOCKED_IDS:
        raise AdmissionError(f"LOCKED_SUMMARY_MISMATCH:{sorted(summary_locked)}")

    records: list[dict[str, Any]] = []
    for formula_id in sorted(expected, key=_natural_formula_key):
        runtime = runtime_items[formula_id]
        proof = proof_items[formula_id]
        brain_node = state["formula_nodes"][formula_id]
        historical = m1[("canonical-formula-registry", formula_id)]
        runtime_name = str(runtime.get("name") or "")
        proof_name = str(proof.get("name") or "")
        if runtime_name == proof_name:
            raise AdmissionError(f"NAMESPACE_COLLISION_NOT_EXPLICIT:{formula_id}")
        runtime_symbol = f"_{formula_id.lower()}"
        executable = callable(getattr(szl_puriq_formulas, runtime_symbol, None))
        if not executable:
            raise AdmissionError(f"RUNTIME_SYMBOL_MISSING:{formula_id}:{runtime_symbol}")
        runtime_status = "CONDITIONAL" if formula_id in LOCKED_IDS else "OPEN"
        runtime_reasons = [
            "ID_COLLISION_DIFFERENT_STATEMENT",
            "PROOF_TRANSFER_BLOCKED",
            "EXECUTABLE_TEST_IS_NOT_FORMAL_PROOF",
        ]
        if formula_id in LOCKED_IDS:
            runtime_reasons.append("RELATED_SAME_ID_PROOF_REQUIRES_SEMANTIC_REBINDING")
        else:
            runtime_reasons.append("NO_ACCEPTED_PROOF_FOR_RUNTIME_CLAIM")
        claim = {
            "name": runtime_name,
            "primitive": runtime.get("primitive"),
            "identity_doc": runtime.get("identity_doc"),
        }
        stable_node = {key: value for key, value in brain_node.items() if key != "degree"}
        records.append(
            {
                "schema_version": "szl.formula-crosswalk-record.v1",
                "record_id": f"{RUNTIME_NAMESPACE}:{formula_id}",
                "formula_namespace": RUNTIME_NAMESPACE,
                "formula_id": formula_id,
                "canonical_name": runtime_name,
                "claim_sha256": _sha_value(claim),
                "resolved_status": runtime_status,
                "status_reasons": runtime_reasons,
                "executable": True,
                "runtime_symbol": runtime_symbol,
                "runtime_harness": runtime.get("harness"),
                "declared_proof_status": runtime.get("proof_status"),
                "declared_lean_name": runtime.get("lean_name"),
                "declared_lean_reference_present": str(runtime.get("lean_name") or "")
                in declarations,
                "brain_node_id": brain_node.get("id"),
                "brain_node_sha256": _sha_value(stable_node),
                "historical_m1_status": historical.get("formula_status"),
                "same_id_other_namespace": f"{PROOF_NAMESPACE}:{formula_id}",
                "same_id_other_name": proof_name,
                "semantic_relation": "ID_COLLISION_DIFFERENT_STATEMENT",
                "proof_transfer_allowed": False,
                "split": "HOLDOUT",
                "admission_decision": "HOLDOUT_NAMESPACE_DISAMBIGUATION",
                "training_eligible": False,
            }
        )

    for formula_id in sorted(expected, key=_natural_formula_key):
        proof = proof_items[formula_id]
        static_item = static_items[formula_id]
        status, reasons = _proof_status(proof, static_item, declarations, summary_locked)
        claim = {
            "name": proof.get("name"),
            "statement": proof.get("statement"),
        }
        records.append(
            {
                "schema_version": "szl.formula-crosswalk-record.v1",
                "record_id": f"{PROOF_NAMESPACE}:{formula_id}",
                "formula_namespace": PROOF_NAMESPACE,
                "formula_id": formula_id,
                "canonical_name": proof.get("name"),
                "claim_sha256": _sha_value(claim),
                "resolved_status": status,
                "status_reasons": reasons,
                "executable": False,
                "lean_ref": proof.get("lean_ref"),
                "lean_ref_present": str(proof.get("lean_ref") or "") in declarations,
                "declared_maturity": proof.get("maturity"),
                "declared_locked_item": proof.get("locked_kernel") is True,
                "declared_locked_summary": formula_id in summary_locked,
                "static_locked_item": static_item.get("locked_kernel") is True,
                "static_name": static_item.get("name"),
                "static_lean_ref": static_item.get("lean_ref"),
                "same_id_other_namespace": f"{RUNTIME_NAMESPACE}:{formula_id}",
                "same_id_other_name": runtime_items[formula_id].get("name"),
                "semantic_relation": "ID_COLLISION_DIFFERENT_STATEMENT",
                "proof_transfer_allowed": False,
                "conditional_variant": (
                    {
                        "lean_ref": "lambda_unique_of_factors",
                        "status": "CONDITIONAL",
                        "unconditional_counterexample": "maxAgg_ne_Lambda",
                    }
                    if formula_id == "F23"
                    else None
                ),
                "split": "HOLDOUT",
                "admission_decision": (
                    "HOLDOUT_REFUTATION"
                    if status == "REFUTED"
                    else "HOLDOUT_STATUS_PRESERVATION"
                ),
                "training_eligible": False,
            }
        )

    thesis_rows = knowledge.get("formulas") or []
    if len(thesis_rows) != 100:
        raise AdmissionError(f"THESIS_FORMULA_COUNT_MISMATCH:{len(thesis_rows)}")
    for item in sorted(thesis_rows, key=lambda value: _natural_formula_key(str(value["id"]))):
        formula_id = str(item["id"])
        historical = m1[("thesis-formula-corpus", formula_id)]
        records.append(
            {
                "schema_version": "szl.formula-crosswalk-record.v1",
                "record_id": f"{THESIS_NAMESPACE}:{formula_id}",
                "formula_namespace": THESIS_NAMESPACE,
                "formula_id": formula_id,
                "canonical_name": None,
                "claim_sha256": _sha_value(
                    {"latex": item.get("latex"), "context": item.get("context")}
                ),
                "resolved_status": "OPEN",
                "status_reasons": [
                    "EXTRACTED_THESIS_FRAGMENT",
                    "NO_ITEM_LEVEL_PROOF_BINDING",
                    "ABSTENTION_REQUIRED",
                ],
                "executable": False,
                "source_file": item.get("source_file"),
                "source_line": item.get("source_line"),
                "maturity": item.get("maturity"),
                "latex_sha256": _sha_bytes(str(item.get("latex") or "").encode("utf-8")),
                "context_sha256": _sha_bytes(str(item.get("context") or "").encode("utf-8")),
                "historical_m1_status": historical.get("formula_status"),
                "proof_transfer_allowed": False,
                "split": "HOLDOUT",
                "admission_decision": "HOLDOUT_ABSTENTION",
                "training_eligible": False,
            }
        )
    return sorted(records, key=lambda row: str(row["record_id"]))


def _build_crosswalk(root: pathlib.Path, state: Mapping[str, Any]) -> dict[str, Any]:
    records = _crosswalk_records(root, state)
    statuses = collections.Counter(str(row["resolved_status"]) for row in records)
    namespaces = collections.Counter(str(row["formula_namespace"]) for row in records)
    if set(statuses) != set(STATUS_VOCABULARY):
        raise AdmissionError(f"STATUS_VOCABULARY_NOT_COVERED:{dict(statuses)}")
    payload = {
        "schema_version": "szl.formula-id-crosswalk.v1",
        "status_vocabulary": list(STATUS_VOCABULARY),
        "namespace_policy": {
            "formula_ids_are_namespace_scoped": True,
            "same_id_implies_same_statement": False,
            "proof_transfer_requires_explicit_semantic_binding": True,
            "default_proof_transfer_allowed": False,
        },
        "summary": {
            "record_count": len(records),
            "namespace_counts": dict(sorted(namespaces.items())),
            "resolved_status_counts": {
                status: statuses.get(status, 0) for status in STATUS_VOCABULARY
            },
            "executable_records": sum(bool(row["executable"]) for row in records),
            "holdout_records": sum(row["split"] == "HOLDOUT" for row in records),
            "training_eligible_records": sum(
                bool(row["training_eligible"]) for row in records
            ),
            "same_id_cross_namespace_collisions": 23,
            "proof_transfer_blocked_records": sum(
                row.get("proof_transfer_allowed") is False for row in records
            ),
            "declared_locked_ids": sorted(LOCKED_IDS, key=_natural_formula_key),
            "locally_item_bound_kernel_records": statuses.get("KERNEL_ACCEPTED", 0),
            "locked_count_changed": False,
        },
        "records": records,
    }
    return _receipted(payload, "crosswalk_receipt_sha256")


def _lake_rows(root: pathlib.Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_json(root, SZL_LAKE_MANIFEST)
    data = _load_json(root, SZL_LAKE_DATA)
    entries = manifest.get("entries") or []
    if len(entries) != 1:
        raise AdmissionError(f"SZL_LAKE_ENTRY_COUNT_MISMATCH:{len(entries)}")
    entry = entries[0]
    data_sha = _sha_file(root / SZL_LAKE_DATA)
    if str(entry.get("artifact_sha256") or "") != data_sha:
        raise AdmissionError("SZL_LAKE_ARTIFACT_HASH_MISMATCH")
    receipt = entry.get("artifact_receipt") or {}
    if receipt.get("verified") is not True or receipt.get("proof_status") != "NOT_EVALUATED":
        raise AdmissionError("SZL_LAKE_RECEIPT_BOUNDARY_MISMATCH")
    rows: list[dict[str, Any]] = []
    for example in sorted(data.get("examples") or [], key=lambda item: str(item["example_id"])):
        payload = {
            "schema_version": "szl.formula-admission-tranche-record.v1",
            "record_id": f"szl-lake:{example['example_id']}",
            "record_kind": "SZL_LAKE_EVIDENCE",
            "formula_namespace": None,
            "formula_id": None,
            "resolved_status": None,
            "evidence_status": "NOT_EVALUATED",
            "example_type": example.get("example_type"),
            "query_sha256": _sha_bytes(str(example.get("query") or "").encode("utf-8")),
            "evidence_text_sha256": _sha_bytes(
                str(example.get("evidence_text") or "").encode("utf-8")
            ),
            "target_relevance": example.get("target_relevance"),
            "source_artifact_sha256": data_sha,
            "split": "HOLDOUT",
            "admission_decision": "HOLDOUT_EVIDENCE_ONLY",
            "training_eligible": False,
        }
        rows.append(_receipted(payload, "record_receipt_sha256"))
    if len(rows) != 2:
        raise AdmissionError(f"SZL_LAKE_EXAMPLE_COUNT_MISMATCH:{len(rows)}")
    return rows, {
        "manifest_path": SZL_LAKE_MANIFEST.as_posix(),
        "manifest_sha256": _sha_file(root / SZL_LAKE_MANIFEST),
        "artifact_path": SZL_LAKE_DATA.as_posix(),
        "artifact_sha256": data_sha,
        "example_count": len(rows),
        "proof_status": "NOT_EVALUATED",
        "admission": "HOLDOUT_EVIDENCE_ONLY",
    }


def _tranche_rows(crosswalk: Mapping[str, Any], lake_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in crosswalk["records"]:
        payload = {
            "schema_version": "szl.formula-admission-tranche-record.v1",
            "record_id": record["record_id"],
            "record_kind": "FORMULA_STATUS_METADATA",
            "formula_namespace": record["formula_namespace"],
            "formula_id": record["formula_id"],
            "claim_sha256": record["claim_sha256"],
            "resolved_status": record["resolved_status"],
            "executable": record["executable"],
            "proof_transfer_allowed": record.get("proof_transfer_allowed", False),
            "split": record["split"],
            "admission_decision": record["admission_decision"],
            "training_eligible": record["training_eligible"],
        }
        rows.append(_receipted(payload, "record_receipt_sha256"))
    rows.extend(lake_rows)
    return sorted(rows, key=lambda row: str(row["record_id"]))


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(row) + b"\n" for row in rows)


def _build_manifest(
    root: pathlib.Path,
    state: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    tranche_rows: Sequence[Mapping[str, Any]],
    crosswalk_bytes: bytes,
    tranche_bytes: bytes,
    lake_summary: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_index = _load_json(root, CANONICAL_INDEX)
    canonical_evidence = _load_json(root, CANONICAL_EVIDENCE)
    documents = canonical_index.get("documents") or []
    if len(documents) != 5 or any(doc.get("training_eligible") is not False for doc in documents):
        raise AdmissionError("QUERY_READY_CONTEXT_BOUNDARY_MISMATCH")
    inventory = state["inventory"]
    inv = inventory["inventory"]
    status_counts = crosswalk["summary"]["resolved_status_counts"]
    holdout_rows = sum(row.get("split") == "HOLDOUT" for row in tranche_rows)
    train_rows = sum(row.get("split") == "TRAIN" for row in tranche_rows)
    if train_rows or holdout_rows != len(tranche_rows):
        raise AdmissionError("TRANCHE_SPLIT_BOUNDARY_MISMATCH")
    m1_manifest = state["m1_manifest"]
    payload = {
        "schema_version": "szl.formula-training-admission-manifest.v1",
        "status": "COMPLETE_FAIL_CLOSED_HOLDOUT_ONLY",
        "workflow": {
            "name": "A11OY_EVIDENCE_ADMISSION",
            "stages": [
                {
                    "stage": "DORMANT_RAW",
                    "record_count": inv["raw_node_count"],
                    "training_text_rows_emitted": 0,
                    "decision": "QUARANTINE_AGGREGATE_ONLY",
                },
                {
                    "stage": "NORMALIZED_ARTIFACT",
                    "record_count": len(tranche_rows),
                    "decision": "BOUNDED_METADATA_ONLY",
                },
                {
                    "stage": "FORMULA_LINK",
                    "record_count": crosswalk["summary"]["record_count"],
                    "decision": "NAMESPACE_SCOPED_PROOF_TRANSFER_BLOCKED",
                },
                {
                    "stage": "ADMISSION_DECISION",
                    "train_rows": train_rows,
                    "holdout_rows": holdout_rows,
                    "quarantined_raw_nodes": inv["quarantined_node_count"],
                },
                {
                    "stage": "QUERY_READY_CONTEXT",
                    "document_count": len(documents),
                    "source": CANONICAL_INDEX.as_posix(),
                    "training_eligible": False,
                    "latency": {"status": "NOT_EVALUATED", "milliseconds": None},
                },
            ],
        },
        "source_snapshot": {
            "brain": {
                "raw_node_count": inv["raw_node_count"],
                "distinct_artifact_count": state["graph"]["distinct_artifacts"],
                "person_metadata_count": state["graph"]["person_node_count"],
                "formula_node_count": len(state["formula_nodes"]),
                "graph_content_sha256": inv["graph_content_sha256"],
                "inventory_sha256": inventory["inventory_sha256"],
                "quarantined_node_count": inv["quarantined_node_count"],
                "reason_counts": inv["reason_counts"],
                "training_text_rows_emitted": 0,
            },
            "m1_alignment": {
                "manifest_path": M1_MANIFEST.as_posix(),
                "manifest_sha256": _sha_file(root / M1_MANIFEST),
                "brain_ledger_path": M1_BRAIN_LEDGER.as_posix(),
                "brain_ledger_sha256": _sha_file(root / M1_BRAIN_LEDGER),
                "brain_ledger_rows": state["m1_rows"],
                "current_raw_nodes": inv["raw_node_count"],
                "aligned": True,
                "current_only_node_ids": state["added"],
                "m1_only_node_ids": state["removed"],
                "training_state": m1_manifest.get("training_state"),
                "raw_training_eligible_rows": 0,
                "admission": "CURRENT_INVENTORY_ONLY_ALL_ROWS_QUARANTINED",
            },
            "lean_mathlib": {
                "inventory": _lean_inventory(root)["tree"],
                "source_files": _lean_inventory(root)["files"],
                "binding_rule": "exact declaration plus agreeing item-level status required",
            },
            "thesis": {
                "knowledge_path": KNOWLEDGE.as_posix(),
                "knowledge_sha256": _sha_file(root / KNOWLEDGE),
                "static_path": STATIC_THESIS.as_posix(),
                "static_sha256": _sha_file(root / STATIC_THESIS),
                "extracted_formula_count": 100,
                "proof_pack_formula_count": 23,
            },
            "szl_lake": dict(lake_summary),
            "canonical_query_context": {
                "index_path": CANONICAL_INDEX.as_posix(),
                "index_sha256": _sha_file(root / CANONICAL_INDEX),
                "evidence_manifest_path": CANONICAL_EVIDENCE.as_posix(),
                "evidence_manifest_sha256": _sha_file(root / CANONICAL_EVIDENCE),
                "unique_document_count": len(documents),
                "canonical_rows_observed": canonical_index.get("canonical_rows_observed"),
                "status": canonical_evidence.get("status"),
                "latency_status": "NOT_EVALUATED",
            },
        },
        "decision_summary": {
            "tranche_rows": len(tranche_rows),
            "train_rows": train_rows,
            "holdout_rows": holdout_rows,
            "formula_crosswalk_rows": crosswalk["summary"]["record_count"],
            "szl_lake_rows": lake_summary["example_count"],
            "resolved_status_counts": status_counts,
            "executable_formula_records": crosswalk["summary"]["executable_records"],
            "raw_brain_nodes_quarantined": inv["quarantined_node_count"],
            "raw_brain_rows_emitted": 0,
            "brain_formula_duplicates_index_only": len(state["formula_nodes"]),
            "training_admission": "BLOCKED_PENDING_NAMESPACE_AND_SOURCE_RECONCILIATION",
        },
        "artifacts": {
            "crosswalk": {
                "path": CROSSWALK.as_posix(),
                "bytes": len(crosswalk_bytes),
                "sha256": _sha_bytes(crosswalk_bytes),
                "receipt_sha256": crosswalk["crosswalk_receipt_sha256"],
            },
            "tranche": {
                "path": TRANCHE.as_posix(),
                "bytes": len(tranche_bytes),
                "rows": len(tranche_rows),
                "sha256": _sha_bytes(tranche_bytes),
            },
            "receipt_path": RECEIPT.as_posix(),
        },
        "blockers": [
            "F1-F23 are reused by different runtime and proof-pack statements; same-ID proof transfer is forbidden.",
            "Only item-level source agreement can resolve KERNEL_ACCEPTED; summary counts are not sufficient.",
            "SZL-Lake has two experimental examples and proof status NOT_EVALUATED.",
            "The canonical query pilot contains no committed latency measurement.",
        ],
        "claims_boundary": {
            "network_used": False,
            "raw_node_text_emitted": False,
            "training_triggered": False,
            "model_promoted": False,
            "proof_credit_added": 0,
            "locked_count_changed": False,
            "latency_claimed": False,
            "external_service_mutated": False,
        },
    }
    return _receipted(payload, "manifest_receipt_sha256")


def build_artifacts(repo_root: pathlib.Path | str | None = None) -> dict[str, Any]:
    root = pathlib.Path(repo_root or ROOT).resolve()
    state = _brain_and_m1_state(root)
    crosswalk = _build_crosswalk(root, state)
    lake_rows, lake_summary = _lake_rows(root)
    rows = _tranche_rows(crosswalk, lake_rows)
    crosswalk_bytes = _json_bytes(crosswalk)
    tranche_bytes = _jsonl_bytes(rows)
    manifest = _build_manifest(
        root, state, crosswalk, rows, crosswalk_bytes, tranche_bytes, lake_summary
    )
    manifest_bytes = _json_bytes(manifest)
    receipt_payload = {
        "schema_version": "szl.formula-training-admission-artifact-receipt.v1",
        "artifacts": {
            CROSSWALK.as_posix(): _sha_bytes(crosswalk_bytes),
            TRANCHE.as_posix(): _sha_bytes(tranche_bytes),
            MANIFEST.as_posix(): _sha_bytes(manifest_bytes),
        },
        "manifest_receipt_sha256": manifest["manifest_receipt_sha256"],
        "crosswalk_receipt_sha256": crosswalk["crosswalk_receipt_sha256"],
        "network_used": False,
        "training_triggered": False,
        "signature_status": "UNSIGNED_CONTENT_RECEIPT",
    }
    receipt = _receipted(receipt_payload, "artifact_receipt_sha256")
    return {
        "crosswalk": crosswalk,
        "tranche_rows": rows,
        "manifest": manifest,
        "receipt": receipt,
    }


def write_artifacts(repo_root: pathlib.Path | str | None = None) -> dict[str, Any]:
    root = pathlib.Path(repo_root or ROOT).resolve()
    artifacts = build_artifacts(root)
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    (root / CROSSWALK).write_bytes(_json_bytes(artifacts["crosswalk"]))
    (root / TRANCHE).write_bytes(_jsonl_bytes(artifacts["tranche_rows"]))
    (root / MANIFEST).write_bytes(_json_bytes(artifacts["manifest"]))
    (root / RECEIPT).write_bytes(_json_bytes(artifacts["receipt"]))
    return artifacts


def verify_committed(repo_root: pathlib.Path | str | None = None) -> dict[str, Any]:
    root = pathlib.Path(repo_root or ROOT).resolve()
    artifacts = build_artifacts(root)
    expected = {
        CROSSWALK: _json_bytes(artifacts["crosswalk"]),
        TRANCHE: _jsonl_bytes(artifacts["tranche_rows"]),
        MANIFEST: _json_bytes(artifacts["manifest"]),
        RECEIPT: _json_bytes(artifacts["receipt"]),
    }
    mismatches = [
        relative.as_posix()
        for relative, content in expected.items()
        if not (root / relative).is_file() or (root / relative).read_bytes() != content
    ]
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "manifest_receipt_sha256": artifacts["manifest"]["manifest_receipt_sha256"],
        "artifact_receipt_sha256": artifacts["receipt"]["artifact_receipt_sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write deterministic artifacts")
    parser.add_argument("--verify", action="store_true", help="verify committed artifacts")
    args = parser.parse_args(argv)
    if args.write:
        artifacts = write_artifacts()
        print(
            json.dumps(
                {
                    "ok": True,
                    "status": artifacts["manifest"]["status"],
                    "decision_summary": artifacts["manifest"]["decision_summary"],
                    "artifact_receipt_sha256": artifacts["receipt"][
                        "artifact_receipt_sha256"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.verify:
        result = verify_committed()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    print(json.dumps(build_artifacts()["manifest"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
