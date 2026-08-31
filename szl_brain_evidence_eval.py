# SPDX-License-Identifier: Apache-2.0
"""Deterministic, canonical-only Brain retrieval evidence pilot.

This module does not train a model, admit raw graph nodes, access the network,
or change any trust threshold.  It builds a small lexical index only from the
three verified local corpus manifests already accepted by ``szl_braincorpus``.
Evaluation labels remain in a separate qrels file and are never copied into the
index.  Every output is content-addressed for independent replay.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import pathlib
import re
from typing import Any, Iterable, Mapping, Sequence

import szl_brain_reranker as _reranker
import szl_braincorpus as _corpus


SCHEMA_INDEX = "szl.brain.canonical-index.v1"
SCHEMA_RESULTS = "szl.brain.evidence-evaluation-results.v1"
SCHEMA_MANIFEST = "szl.brain.evidence-manifest.v1"
PROTOCOL_ID = "brain-canonical-retrieval-pilot-v1"
PREREGISTRATION_COMMIT_SHA = "3e465d9bc1f5abbdaf37c3aa30e7a08b422a6ab3"
OUTPUT_DIR = pathlib.Path("research/brain-evidence-admission")
PREREGISTRATION = OUTPUT_DIR / "preregistration.json"
QRELS = OUTPUT_DIR / "qrels.json"
INDEX = OUTPUT_DIR / "canonical-index.json"
RESULTS = OUTPUT_DIR / "evaluation-results.json"
MANIFEST = OUTPUT_DIR / "evidence-manifest.json"
EMPTY_LEDGER = OUTPUT_DIR / ".no-local-evaluation-rows.jsonl"


class EvidenceEvaluationError(RuntimeError):
    """Fail-closed protocol, admission, or receipt error."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _json_file_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2,
                       ensure_ascii=False) + "\n").encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _bytes_sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: pathlib.Path, maximum_bytes: int = 4 * 1024 * 1024) -> Any:
    raw = path.read_bytes()
    if len(raw) > maximum_bytes:
        raise EvidenceEvaluationError(f"FILE_TOO_LARGE:{path}:{len(raw)}")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceEvaluationError(f"INVALID_JSON:{path}:{type(exc).__name__}") from exc


def _receipted(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(payload)
    result[field] = _sha(payload)
    return result


def _protocol(root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    prereg = _load_json(root / PREREGISTRATION)
    qrels = _load_json(root / QRELS)
    if prereg.get("schema_version") != "szl.brain.evidence-evaluation-preregistration.v1":
        raise EvidenceEvaluationError("PREREGISTRATION_SCHEMA_MISMATCH")
    if qrels.get("schema_version") != "szl.brain.evidence-qrels.v1":
        raise EvidenceEvaluationError("QRELS_SCHEMA_MISMATCH")
    if prereg.get("protocol_id") != PROTOCOL_ID or qrels.get("protocol_id") != PROTOCOL_ID:
        raise EvidenceEvaluationError("PROTOCOL_ID_MISMATCH")
    labels = prereg.get("evidence_labels") or {}
    if labels.get("training_eligible") is not False or qrels.get("training_eligible") is not False:
        raise EvidenceEvaluationError("EVALUATION_LABELS_MUST_NOT_BE_TRAINING_ELIGIBLE")
    if labels.get("separate_from_index") is not True:
        raise EvidenceEvaluationError("QRELS_SEPARATION_NOT_DECLARED")
    queries = qrels.get("queries")
    if not isinstance(queries, list) or not queries:
        raise EvidenceEvaluationError("QRELS_EMPTY")
    bounds = prereg.get("bounds") or {}
    if len(queries) > int(bounds.get("max_queries", 0)):
        raise EvidenceEvaluationError("QUERY_BOUND_EXCEEDED")
    seen: set[str] = set()
    for item in queries:
        query_id = str(item.get("query_id") or "")
        query = str(item.get("query") or "")
        action = str(item.get("expected_action") or "")
        relevant = item.get("relevant_document_ids")
        if not query_id or query_id in seen:
            raise EvidenceEvaluationError("QUERY_ID_INVALID_OR_DUPLICATE")
        seen.add(query_id)
        if not query or len(query) > int(bounds.get("max_query_chars", 0)):
            raise EvidenceEvaluationError(f"QUERY_INVALID:{query_id}")
        if action not in {"ANSWER", "ABSTAIN"} or not isinstance(relevant, list):
            raise EvidenceEvaluationError(f"QREL_INVALID:{query_id}")
        if (action == "ANSWER") != bool(relevant):
            raise EvidenceEvaluationError(f"QREL_ACTION_RELEVANCE_CONFLICT:{query_id}")
    return prereg, qrels


def _source_admission(root: pathlib.Path, prereg: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    status = _corpus.build_corpus_status(root, environ={})
    allowed = set(prereg["admission"]["allowed_source_types"])
    admitted: dict[tuple[str, str], dict[str, Any]] = {}
    for source in status.get("sources", []):
        source_type = str(source.get("source_type") or "")
        if source_type not in allowed:
            continue
        for entry in source.get("entries", []):
            receipt = entry.get("artifact_receipt") or {}
            assets = receipt.get("source_assets") or []
            licenses = sorted({str(asset.get("license") or "UNKNOWN") for asset in assets})
            license_ok = bool(assets) and all(value not in {"", "UNKNOWN", "UNLICENSED"}
                                              for value in licenses)
            valid = (
                entry.get("artifact_verified") is True
                and entry.get("artifact_receipt_valid") is True
                and receipt.get("verified") is True
                and license_ok
            )
            if not valid:
                continue
            admitted[(source_type, str(entry.get("id") or ""))] = {
                "artifact_sha256": str(entry.get("artifact_sha256") or ""),
                "artifact_receipt_sha256": str(receipt.get("receipt_sha256") or ""),
                "evidence_class": str(entry.get("effective_class") or "UNKNOWN"),
                "licenses": licenses,
                "proof_credit": int(entry.get("proof_credit") or 0),
                "trust_uplift_eligible": bool(entry.get("trust_uplift_eligible")),
            }
    return admitted


def build_canonical_index(repo_root: pathlib.Path | str | None = None) -> dict[str, Any]:
    root = pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent).resolve()
    prereg, _ = _protocol(root)
    bounds = prereg["bounds"]
    inventory = _reranker.build_inventory(repo_root=root, environ={})
    raw_count = int((inventory.get("inventory") or {}).get("raw_node_count") or 0)
    if raw_count > int(bounds["max_raw_nodes_observed"]):
        raise EvidenceEvaluationError("RAW_NODE_BOUND_EXCEEDED")
    dataset = _reranker.build_dataset(repo_root=root, environ={},
                                      ledger_path=root / EMPTY_LEDGER)
    if (dataset.get("dataset_readiness") or {}).get("status") != _reranker.READY:
        raise EvidenceEvaluationError("CANONICAL_DATASET_NOT_READY")
    rows = dataset.get("rows") or []
    if len(rows) > int(bounds["max_canonical_rows"]):
        raise EvidenceEvaluationError("CANONICAL_ROW_BOUND_EXCEEDED")
    admitted_sources = _source_admission(root, prereg)
    documents: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_key = (str(row.get("source_type") or ""),
                      str(row.get("source_entry_id") or ""))
        source = admitted_sources.get(source_key)
        if source is None:
            raise EvidenceEvaluationError(f"ROW_SOURCE_NOT_ADMITTED:{source_key}")
        if source["artifact_sha256"] != row.get("source_artifact_sha256"):
            raise EvidenceEvaluationError(f"ROW_ARTIFACT_HASH_MISMATCH:{source_key}")
        if source["artifact_receipt_sha256"] != row.get("source_receipt_sha256"):
            raise EvidenceEvaluationError(f"ROW_RECEIPT_HASH_MISMATCH:{source_key}")
        document_id = str(row.get("brain_node_id") or "")
        text = str(row.get("evidence_text") or "")
        if not document_id or not text or len(text) > int(bounds["max_document_chars"]):
            raise EvidenceEvaluationError("DOCUMENT_INVALID_OR_OVERSIZED")
        document = {
            "document_id": document_id,
            "text": text,
            "brain_node_sha256": str(row.get("brain_node_sha256") or ""),
            "brain_source_sha256": str(row.get("brain_source_sha256") or ""),
            "source_type": source_key[0],
            "source_entry_id": source_key[1],
            "source_manifest_sha256": str(row.get("source_manifest_sha256") or ""),
            "source_artifact_sha256": str(row.get("source_artifact_sha256") or ""),
            "source_receipt_sha256": str(row.get("source_receipt_sha256") or ""),
            "license_status": "VERIFIED",
            "licenses": source["licenses"],
            "source_timestamp_status": "UNKNOWN",
            "evidence_class": source["evidence_class"],
            "proof_credit": 0,
            "trust_uplift_eligible": False,
            "training_eligible": False,
        }
        prior = documents.get(document_id)
        if prior is not None and prior != document:
            raise EvidenceEvaluationError(f"DOCUMENT_ID_COLLISION:{document_id}")
        documents[document_id] = document
    if len(documents) > int(bounds["max_unique_documents"]):
        raise EvidenceEvaluationError("UNIQUE_DOCUMENT_BOUND_EXCEEDED")
    if not documents:
        raise EvidenceEvaluationError("NO_CANONICAL_DOCUMENTS")
    inventory_summary = inventory.get("inventory") or {}
    payload = {
        "schema_version": SCHEMA_INDEX,
        "protocol_id": PROTOCOL_ID,
        "preregistration_commit_sha": PREREGISTRATION_COMMIT_SHA,
        "preregistration_content_sha256": _sha(prereg),
        "source_dataset_sha256": dataset.get("dataset_sha256"),
        "source_inventory_sha256": inventory.get("inventory_sha256"),
        "canonical_rows_observed": len(rows),
        "unique_document_count": len(documents),
        "raw_graph": {
            "observed_node_count": raw_count,
            "admitted_to_index": 0,
            "excluded_from_index": raw_count,
            "quarantined_node_count": int(inventory_summary.get("quarantined_node_count") or 0),
            "reason_counts": inventory_summary.get("reason_counts") or {},
        },
        "admission_boundary": {
            "canonical_sources_only": True,
            "verified_artifact_required": True,
            "valid_artifact_receipt_required": True,
            "known_source_asset_licenses_required": True,
            "evaluation_labels_present": False,
        },
        "documents": [documents[key] for key in sorted(documents)],
        "claims_boundary": {
            "proof_credit": 0,
            "model_trust_delta": 0,
            "training_triggered": False,
            "network_used": False,
        },
    }
    return _receipted(payload, "index_receipt_sha256")


def _tokens(text: str, prereg: Mapping[str, Any]) -> list[str]:
    ranking = prereg["ranking"]
    stopwords = set(ranking["stopwords"])
    return [token for token in re.findall(ranking["token_pattern"], text.lower())
            if token not in stopwords]


def _rank(query: str, documents: Sequence[Mapping[str, Any]],
          prereg: Mapping[str, Any]) -> list[dict[str, Any]]:
    doc_tokens = [_tokens(str(doc["text"]), prereg) for doc in documents]
    query_tokens = _tokens(query, prereg)
    if not query_tokens:
        return []
    document_frequency: collections.Counter[str] = collections.Counter()
    for tokens in doc_tokens:
        document_frequency.update(set(tokens))
    count = len(documents)
    average_length = sum(len(tokens) for tokens in doc_tokens) / max(count, 1)
    k1 = float(prereg["ranking"]["k1"])
    b = float(prereg["ranking"]["b"])
    unique_query = set(query_tokens)
    ranked: list[dict[str, Any]] = []
    for document, tokens in zip(documents, doc_tokens):
        frequencies = collections.Counter(tokens)
        score = 0.0
        for term in query_tokens:
            tf = frequencies.get(term, 0)
            if not tf:
                continue
            df = document_frequency[term]
            inverse_document_frequency = math.log(1.0 + (count - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1.0 - b + b * len(tokens) / max(average_length, 1.0))
            score += inverse_document_frequency * (tf * (k1 + 1.0)) / denominator
        document_terms = set(tokens)
        coverage = len(unique_query.intersection(document_terms)) / len(unique_query)
        ranked.append({
            "document_id": document["document_id"],
            "bm25_score": round(score, 12),
            "query_token_coverage": round(coverage, 12),
        })
    return sorted(ranked, key=lambda item: (-item["bm25_score"],
                                             str(item["document_id"])))


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else 0.0


def evaluate(index: Mapping[str, Any], prereg: Mapping[str, Any],
             qrels: Mapping[str, Any]) -> dict[str, Any]:
    documents = index.get("documents") or []
    document_ids = {str(doc.get("document_id")) for doc in documents}
    threshold = float(prereg["abstention"]["minimum_top_query_token_coverage"])
    top_limit = max(int(value) for value in prereg["ranking"]["top_k"])
    per_query: list[dict[str, Any]] = []
    answerable: list[dict[str, Any]] = []
    unanswerable: list[dict[str, Any]] = []
    for qrel in qrels["queries"]:
        relevant = [str(value) for value in qrel["relevant_document_ids"]]
        missing = sorted(set(relevant) - document_ids)
        if missing:
            raise EvidenceEvaluationError(
                f"QREL_REFERENCES_MISSING_DOCUMENT:{qrel['query_id']}:{','.join(missing)}")
        ranked = _rank(str(qrel["query"]), documents, prereg)
        top = ranked[0] if ranked else None
        predicted_action = "ANSWER" if (
            top is not None and float(top["bm25_score"]) > 0.0
            and float(top["query_token_coverage"]) >= threshold
        ) else "ABSTAIN"
        position = next((position for position, item in enumerate(ranked, start=1)
                         if item["document_id"] in relevant), None)
        recall_at_1 = 1.0 if position is not None and position <= 1 else 0.0
        recall_at_3 = 1.0 if position is not None and position <= 3 else 0.0
        reciprocal_rank = 1.0 / position if position else 0.0
        ndcg_at_3 = (1.0 / math.log2(position + 1.0)
                     if position is not None and position <= 3 else 0.0)
        result = {
            "query_id": qrel["query_id"],
            "expected_action": qrel["expected_action"],
            "predicted_action": predicted_action,
            "relevant_document_ids": relevant,
            "retrieved": ranked[:top_limit],
            "relevant_rank": position,
            "recall_at_1": recall_at_1,
            "recall_at_3": recall_at_3,
            "reciprocal_rank": round(reciprocal_rank, 12),
            "ndcg_at_3": round(ndcg_at_3, 12),
            "action_correct": predicted_action == qrel["expected_action"],
        }
        per_query.append(result)
        (answerable if relevant else unanswerable).append(result)
    raw_graph = index["raw_graph"]
    raw_count = int(raw_graph["observed_node_count"])
    freshness_unknown = int((raw_graph.get("reason_counts") or {}).get("FRESHNESS_UNKNOWN", 0))
    timestamp_known = max(raw_count - freshness_unknown, 0)
    canonical_timestamp_known = sum(
        1 for document in documents if document.get("source_timestamp_status") == "VERIFIED"
    )
    license_known = sum(1 for document in documents
                        if document.get("license_status") == "VERIFIED")
    metrics = {
        "query_count": len(per_query),
        "answerable_query_count": len(answerable),
        "unanswerable_query_count": len(unanswerable),
        "recall_at_1": round(_mean(item["recall_at_1"] for item in answerable), 12),
        "recall_at_3": round(_mean(item["recall_at_3"] for item in answerable), 12),
        "mean_reciprocal_rank": round(_mean(item["reciprocal_rank"] for item in answerable), 12),
        "ndcg_at_3": round(_mean(item["ndcg_at_3"] for item in answerable), 12),
        "answerable_abstention_rate": round(_mean(
            1.0 if item["predicted_action"] == "ABSTAIN" else 0.0 for item in answerable
        ), 12),
        "unanswerable_abstention_accuracy": round(_mean(
            1.0 if item["predicted_action"] == "ABSTAIN" else 0.0 for item in unanswerable
        ), 12),
        "overall_action_accuracy": round(_mean(
            1.0 if item["action_correct"] else 0.0 for item in per_query
        ), 12),
        "canonical_license_coverage": round(license_known / len(documents), 12),
        "canonical_source_timestamp_coverage": round(
            canonical_timestamp_known / len(documents), 12
        ),
        "raw_graph_source_timestamp_coverage": round(
            timestamp_known / raw_count if raw_count else 0.0, 12
        ),
    }
    payload = {
        "schema_version": SCHEMA_RESULTS,
        "protocol_id": PROTOCOL_ID,
        "preregistration_commit_sha": PREREGISTRATION_COMMIT_SHA,
        "preregistration_content_sha256": _sha(prereg),
        "qrels_content_sha256": _sha(qrels),
        "index_receipt_sha256": index["index_receipt_sha256"],
        "metrics": metrics,
        "per_query": per_query,
        "claims_boundary": {
            "label": "MEASURED_LOCAL_PILOT",
            "proof_credit": 0,
            "model_trust_delta": 0,
            "model_promotion_allowed": False,
            "training_triggered": False,
            "network_used": False,
            "external_validity": "NOT_ESTABLISHED",
        },
    }
    return _receipted(payload, "results_receipt_sha256")


def build_artifacts(repo_root: pathlib.Path | str | None = None) -> dict[str, dict[str, Any]]:
    root = pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent).resolve()
    prereg, qrels = _protocol(root)
    index = build_canonical_index(root)
    results = evaluate(index, prereg, qrels)
    code_bytes = pathlib.Path(__file__).read_bytes()
    index_bytes = _json_file_bytes(index)
    results_bytes = _json_file_bytes(results)
    artifact_receipts = {
        PREREGISTRATION.as_posix(): _bytes_sha((root / PREREGISTRATION).read_bytes()),
        QRELS.as_posix(): _bytes_sha((root / QRELS).read_bytes()),
        INDEX.as_posix(): _bytes_sha(index_bytes),
        RESULTS.as_posix(): _bytes_sha(results_bytes),
        "szl_brain_evidence_eval.py": _bytes_sha(code_bytes),
    }
    manifest_payload = {
        "schema_version": SCHEMA_MANIFEST,
        "protocol_id": PROTOCOL_ID,
        "preregistration_commit_sha": PREREGISTRATION_COMMIT_SHA,
        "status": "COMPLETE_LOCAL_PILOT",
        "label": "MEASURED_LOCAL_PILOT",
        "artifact_receipts": artifact_receipts,
        "index_receipt_sha256": index["index_receipt_sha256"],
        "results_receipt_sha256": results["results_receipt_sha256"],
        "metrics": results["metrics"],
        "admission_summary": {
            "canonical_rows_observed": index["canonical_rows_observed"],
            "unique_document_count": index["unique_document_count"],
            "raw_graph_nodes_observed": index["raw_graph"]["observed_node_count"],
            "raw_graph_nodes_admitted": 0,
            "raw_graph_nodes_excluded": index["raw_graph"]["excluded_from_index"],
        },
        "paper_ready_claims": [
            "A deterministic local pilot was executed over the content-addressed canonical evidence subset.",
            "No raw graph node entered the evaluation index.",
            "Evaluation qrels remained separate from the index and ineligible for training.",
            "License, freshness, ranking, and abstention metrics were computed from committed local evidence.",
        ],
        "limitations": [
            "The corpus has only five unique canonical documents and fifteen manually judged queries.",
            "There is one adjudicator and no inter-rater reliability measurement.",
            "Canonical source timestamps are absent, so semantic source freshness remains UNKNOWN.",
            "The baseline is lexical BM25; no learned reranker or independent external corpus was evaluated.",
            "Results do not generalize to the 9,000-plus-node raw Brain graph, which remained excluded.",
        ],
        "claims_boundary": {
            "proof_credit": 0,
            "model_trust_delta": 0,
            "model_promotion_allowed": False,
            "training_triggered": False,
            "network_used": False,
            "doi_minted": False,
            "peer_reviewed": False,
        },
    }
    manifest = _receipted(manifest_payload, "manifest_receipt_sha256")
    return {"index": index, "results": results, "manifest": manifest}


def write_artifacts(repo_root: pathlib.Path | str | None = None) -> dict[str, dict[str, Any]]:
    root = pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent).resolve()
    artifacts = build_artifacts(root)
    targets = {
        root / INDEX: artifacts["index"],
        root / RESULTS: artifacts["results"],
        root / MANIFEST: artifacts["manifest"],
    }
    for path, value in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_json_file_bytes(value))
    return artifacts


def verify_committed(repo_root: pathlib.Path | str | None = None) -> dict[str, Any]:
    root = pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent).resolve()
    rebuilt = build_artifacts(root)
    mismatches: list[str] = []
    for key, relative in (("index", INDEX), ("results", RESULTS), ("manifest", MANIFEST)):
        path = root / relative
        if not path.is_file() or path.read_bytes() != _json_file_bytes(rebuilt[key]):
            mismatches.append(str(relative))
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "manifest_receipt_sha256": rebuilt["manifest"]["manifest_receipt_sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write deterministic artifacts")
    parser.add_argument("--verify", action="store_true", help="verify committed artifacts")
    args = parser.parse_args(argv)
    if args.write:
        artifacts = write_artifacts()
        print(json.dumps({
            "ok": True,
            "manifest_receipt_sha256": artifacts["manifest"]["manifest_receipt_sha256"],
            "metrics": artifacts["results"]["metrics"],
        }, sort_keys=True))
        return 0
    if args.verify:
        result = verify_committed()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    artifacts = build_artifacts()
    print(json.dumps(artifacts["manifest"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
