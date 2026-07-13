#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed operational gate for the M1 experimental PEFT candidate.

This module does not ship model weights, download artifacts, train, publish, or
call a remote provider.  It will run bounded inference only when every local
artifact and evidence receipt matches the immutable manifest, the local runtime
and GPU pass admission, and the operator binds the exact in-process provider
identity.  ``NOT_PROMOTED`` is always preserved and production use is rejected.
"""

from __future__ import annotations

import asyncio
import gc
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request


SCHEMA = "szl.m1-operational-gate/v1"
INFER_SCHEMA = "szl.m1-experimental-inference-request/v1"
RECEIPT_SCHEMA = "szl.m1-experimental-inference-receipt/v1"
READY = "READY_EXPERIMENTAL"
BLOCKED = "BLOCKED"
UNAVAILABLE = "UNAVAILABLE"
PASS = "PASS"
MANIFEST_DIR = Path(__file__).resolve().parent / "model_release" / "m1"
MANIFEST_PATH = MANIFEST_DIR / "operational-manifest.json"
PAGE_PATH = Path(__file__).resolve().parent / "web" / "m1-model.html"
_INFERENCE_LOCK = threading.Lock()


class ContractError(ValueError):
    """The caller supplied a request outside the fixed experimental contract."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _load_manifest() -> dict[str, Any]:
    value = _read_json(MANIFEST_PATH)
    if value.get("schema") != "szl.m1-operational-manifest/v1":
        raise ValueError("unsupported M1 manifest schema")
    if value.get("release_state") != "NOT_PROMOTED":
        raise ValueError("M1 manifest must remain NOT_PROMOTED")
    if (value.get("inference_policy") or {}).get("production_eligible") is not False:
        raise ValueError("M1 production eligibility must be false")
    return value


def _result(state: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {"state": state, "reason": reason, **evidence}


def _configured_root(env_name: str) -> Path | None:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _confined_file(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("artifact path must be relative")
    target = (root / relative).resolve(strict=False)
    try:
        target.relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError("artifact path escapes configured root") from exc
    return target


def _verify_file(root: Path | None, spec: dict[str, Any]) -> dict[str, Any]:
    relative = str(spec.get("path") or "")
    public = {"path": relative, "expected_sha256": spec.get("sha256"), "expected_bytes": spec.get("bytes")}
    if root is None:
        return _result(UNAVAILABLE, "artifact root is not configured", **public)
    try:
        path = _confined_file(root, relative)
    except ValueError as exc:
        return _result(BLOCKED, str(exc), **public)
    if not path.is_file():
        return _result(UNAVAILABLE, "required local artifact is absent", **public)
    try:
        size = path.stat().st_size
        expected_size = int(spec["bytes"])
        if size != expected_size:
            return _result(BLOCKED, "artifact byte length mismatch", actual_bytes=size, **public)
        digest = _digest_file(path)
    except (OSError, ValueError, KeyError) as exc:
        return _result(UNAVAILABLE, f"artifact could not be verified ({type(exc).__name__})", **public)
    if digest != str(spec.get("sha256") or "").lower():
        return _result(BLOCKED, "artifact SHA-256 mismatch", actual_sha256=digest, **public)
    return _result(PASS, "exact byte length and SHA-256 match", actual_sha256=digest, actual_bytes=size, **public)


def _rollup_files(root: Path | None, specs: list[dict[str, Any]], label: str) -> dict[str, Any]:
    files = [_verify_file(root, spec) for spec in specs]
    states = {entry["state"] for entry in files}
    state = BLOCKED if BLOCKED in states else UNAVAILABLE if UNAVAILABLE in states else PASS
    return {
        "state": state,
        "reason": f"{label}: {sum(item['state'] == PASS for item in files)}/{len(files)} exact files verified",
        "verified_files": sum(item["state"] == PASS for item in files),
        "required_files": len(files),
        "files": files,
    }


def _json_after_verified(root: Path | None, spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    checked = _verify_file(root, spec)
    if checked["state"] != PASS or root is None:
        return checked, None
    try:
        return checked, _read_json(_confined_file(root, str(spec["path"])))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        public = {key: value for key, value in checked.items() if key not in {"state", "reason"}}
        return _result(BLOCKED, f"verified receipt is not valid JSON ({type(exc).__name__})", **public), None


def _metadata_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    evidence = manifest["evidence"]
    candidate_check, candidate = _json_after_verified(MANIFEST_DIR, evidence["candidate_manifest"])
    evaluation_check, evaluation = _json_after_verified(MANIFEST_DIR, evidence["evaluation_manifest"])
    if candidate_check["state"] != PASS or evaluation_check["state"] != PASS:
        state = BLOCKED if BLOCKED in {candidate_check["state"], evaluation_check["state"]} else UNAVAILABLE
        return _result(state, "candidate or evaluation manifest integrity failed", candidate=candidate_check, evaluation=evaluation_check)

    expected_base = manifest["base"]
    candidate_base = candidate.get("base") if candidate else {}
    mismatches: list[str] = []
    for key in ("repository", "revision", "architecture", "license", "license_evidence"):
        if candidate_base.get(key) != expected_base.get(key):
            mismatches.append(f"base.{key}")
    if not candidate or candidate.get("candidate_id") != manifest["candidate_id"]:
        mismatches.append("candidate_id")
    if candidate and candidate.get("release_state") != "NOT_PROMOTED":
        mismatches.append("release_state")
    if candidate and candidate.get("quality_claim") != "NOT_ESTABLISHED":
        mismatches.append("quality_claim")
    if not evaluation or evaluation.get("candidate_id") != manifest["candidate_id"]:
        mismatches.append("evaluation.candidate_id")
    if evaluation and evaluation.get("promotion_decision") != "NOT_PROMOTED":
        mismatches.append("evaluation.promotion_decision")
    corpus_spec = (manifest.get("evidence") or {}).get("corpus_ingestion_manifest") or {}
    corpus_policy = manifest.get("corpus_policy") or {}
    proposal = (candidate or {}).get("full_corpus_proposal") or {}
    expected_proposal = {
        "relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
        "manifest_path": corpus_spec.get("path"),
        "manifest_sha256": corpus_spec.get("sha256"),
        "brain_raw_nodes": corpus_policy.get("expected_raw_nodes"),
        "brain_distinct_artifacts": corpus_policy.get("expected_distinct_artifacts"),
        "formula_records": corpus_policy.get("expected_formula_records"),
        "training_state": "NOT_RUN",
    }
    if proposal != expected_proposal:
        mismatches.append("full_corpus_proposal")
    reload_meta = ((evaluation or {}).get("measured") or {}).get("offline_reload") or {}
    if reload_meta.get("state") != "PASS":
        mismatches.append("evaluation.offline_reload.state")
    if mismatches:
        return _result(BLOCKED, "metadata consistency check failed", mismatches=mismatches,
                       candidate=candidate_check, evaluation=evaluation_check)
    return _result(
        PASS,
        "immutable candidate and evaluation metadata are consistent",
        candidate=candidate_check,
        evaluation=evaluation_check,
        repository=expected_base["repository"],
        revision=expected_base["revision"],
        architecture=expected_base["architecture"],
        license=expected_base["license"],
        license_evidence=expected_base["license_evidence"],
        license_verification_scope="metadata consistency only; not an independent legal opinion",
        evaluation_state=evaluation.get("evaluation_state"),
        unrun_suites=list(evaluation.get("required_unrun_suites") or []),
        corpus_relation=proposal.get("relation"), corpus_manifest_sha256=proposal.get("manifest_sha256"),
        quality_claim="NOT_ESTABLISHED",
        release_state="NOT_PROMOTED",
    )


def _audit_corpus_ledger(spec: dict[str, Any], *, expected_schema: str,
                         evaluation_receipt_id: str, kind: str) -> dict[str, Any]:
    checked = _verify_file(MANIFEST_DIR, spec)
    if checked["state"] != PASS:
        return checked
    try:
        path = _confined_file(MANIFEST_DIR, str(spec["path"]))
        expected_rows = int(spec["rows"])
    except (KeyError, TypeError, ValueError) as exc:
        return _result(BLOCKED, f"ledger specification is invalid ({type(exc).__name__})", file=checked)

    rows = 0
    artifact_rows = 0
    receipts: set[str] = set()
    identities: set[str] = set()
    family_splits: dict[str, str] = {}
    decisions: Counter[str] = Counter()
    formula_status: Counter[str] = Counter()
    formula_bindings: dict[str, dict[str, str | None]] = {}
    errors: list[str] = []
    vocabulary = {"KERNEL_ACCEPTED", "CONDITIONAL", "OPEN", "REFUTED"}
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    errors.append(f"line {line_number}: blank row")
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"line {line_number}: invalid JSON")
                    continue
                rows += 1
                if not isinstance(row, dict) or row.get("schema") != expected_schema:
                    errors.append(f"line {line_number}: schema mismatch")
                    continue
                receipt_id = str(row.get("receipt_id") or "")
                if not receipt_id or receipt_id in receipts:
                    errors.append(f"line {line_number}: absent or duplicate receipt_id")
                receipts.add(receipt_id)
                identity = str(row.get("node_id") if kind == "brain" else f"{row.get('source_family')}:{row.get('formula_id')}")
                if not identity or identity in identities:
                    errors.append(f"line {line_number}: absent or duplicate row identity")
                identities.add(identity)
                if row.get("evaluation_receipt_id") != evaluation_receipt_id:
                    errors.append(f"line {line_number}: evaluation receipt binding mismatch")
                canonical_text = row.get("canonical_text")
                if not isinstance(canonical_text, str) or not canonical_text:
                    errors.append(f"line {line_number}: canonical text absent")
                elif _digest_bytes(canonical_text.encode("utf-8")) != row.get("canonical_text_sha256"):
                    errors.append(f"line {line_number}: canonical text digest mismatch")
                family = str(row.get("source_family") or "")
                split = str(row.get("source_family_split") or "")
                if not family or split not in {"TRAIN", "HOLDOUT", "QUARANTINE"}:
                    errors.append(f"line {line_number}: invalid source-family split")
                elif family in family_splits and family_splits[family] != split:
                    errors.append(f"line {line_number}: source family crosses partitions")
                else:
                    family_splits[family] = split
                decision = str(row.get("training_decision") or "")
                decisions[decision] += 1
                if kind == "brain":
                    if row.get("brain_anatomy_receipt_id") != receipt_id or not receipt_id.startswith("brain-node:sha256:"):
                        errors.append(f"line {line_number}: Brain Anatomy receipt binding mismatch")
                    if row.get("artifact_role") == "DISTINCT_ARTIFACT":
                        artifact_rows += 1
                    license_state = ((row.get("license") or {}).get("state"))
                    if license_state == "UNKNOWN_ITEM_LEVEL_LICENSE" and decision != "QUARANTINE":
                        errors.append(f"line {line_number}: unknown-license row escaped quarantine")
                    if row.get("formula_status") is not None:
                        formula_id = str(row.get("formula_id") or "")
                        if (not formula_id or formula_id in formula_bindings or
                                row.get("formula_status") not in vocabulary or
                                not str(row.get("formula_receipt_id") or "").startswith("formula:sha256:")):
                            errors.append(f"line {line_number}: formula node status/receipt invalid")
                        else:
                            formula_bindings[formula_id] = {
                                "formula_receipt_id": str(row["formula_receipt_id"]),
                                "brain_anatomy_receipt_id": receipt_id,
                            }
                else:
                    status = str(row.get("formula_status") or "")
                    formula_status[status] += 1
                    if not receipt_id.startswith("formula:sha256:") or row.get("formula_receipt_id") != receipt_id:
                        errors.append(f"line {line_number}: formula receipt binding mismatch")
                    if status not in vocabulary or split != "HOLDOUT":
                        errors.append(f"line {line_number}: formula status/split invalid")
                    expected_role = "HOLDOUT_POSITIVE" if status == "KERNEL_ACCEPTED" else (
                        "HOLDOUT_NEGATIVE" if status == "REFUTED" else "HOLDOUT_ABSTENTION"
                    )
                    if decision != expected_role:
                        errors.append(f"line {line_number}: formula role does not match status")
                    if bool(row.get("abstention_required")) != (status in {"OPEN", "CONDITIONAL"}):
                        errors.append(f"line {line_number}: abstention label mismatch")
                    if bool(row.get("negative_example")) != (status == "REFUTED"):
                        errors.append(f"line {line_number}: negative-example label mismatch")
                    if row.get("brain_anatomy_receipt_id"):
                        formula_bindings[str(row.get("formula_id") or "")] = {
                            "formula_receipt_id": receipt_id,
                            "brain_anatomy_receipt_id": str(row["brain_anatomy_receipt_id"]),
                        }
                if len(errors) >= 20:
                    break
    except OSError as exc:
        return _result(UNAVAILABLE, f"ledger could not be read ({type(exc).__name__})", file=checked)

    if rows != expected_rows:
        errors.append(f"row count {rows} != expected {expected_rows}")
    if errors:
        return _result(BLOCKED, "corpus ledger semantic verification failed", file=checked,
                       errors=errors[:20], rows_observed=rows, rows_expected=expected_rows)
    return _result(
        PASS, "exact ledger bytes and every decision row verified",
        file=checked, rows=rows, distinct_artifact_rows=artifact_rows,
        source_family_split=dict(sorted(family_splits.items())),
        decisions=dict(sorted(decisions.items())), formula_status=dict(sorted(formula_status.items())),
        formula_bindings=dict(sorted(formula_bindings.items())),
    )


def _corpus_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    evidence = manifest.get("evidence") or {}
    policy = manifest.get("corpus_policy") or {}
    try:
        summary_check, summary = _json_after_verified(MANIFEST_DIR, evidence["corpus_ingestion_manifest"])
        if summary_check["state"] != PASS or summary is None:
            return summary_check
        if summary.get("schema") != "szl.m1-corpus-ingestion-manifest/v1":
            return _result(BLOCKED, "corpus ingestion manifest schema mismatch", file=summary_check)
        evaluation_spec = evidence["evaluation_manifest"]
        evaluation_receipt_id = f"m1-evaluation:sha256:{evaluation_spec['sha256']}"
        brain = _audit_corpus_ledger(
            evidence["brain_ingest_ledger"], expected_schema="szl.m1-brain-ingest-decision/v1",
            evaluation_receipt_id=evaluation_receipt_id, kind="brain",
        )
        formulas = _audit_corpus_ledger(
            evidence["formula_curriculum_ledger"], expected_schema="szl.m1-formula-curriculum-decision/v1",
            evaluation_receipt_id=evaluation_receipt_id, kind="formula",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _result(BLOCKED, f"corpus evidence configuration invalid ({type(exc).__name__})")
    if BLOCKED in {brain["state"], formulas["state"]}:
        return _result(BLOCKED, "corpus ledger integrity or semantic gate failed", manifest=summary_check,
                       brain_ledger=brain, formula_ledger=formulas)
    if UNAVAILABLE in {brain["state"], formulas["state"]}:
        return _result(UNAVAILABLE, "corpus ledger is unavailable", manifest=summary_check,
                       brain_ledger=brain, formula_ledger=formulas)

    coverage = summary.get("coverage") or {}
    source = summary.get("source_snapshot") or {}
    ledgers = summary.get("ledgers") or {}
    resulting = summary.get("resulting_evaluation_receipt") or {}
    expected_nodes = int(policy.get("expected_raw_nodes", -1))
    expected_artifacts = int(policy.get("expected_distinct_artifacts", -1))
    expected_formulas = int(policy.get("expected_formula_records", -1))
    mismatches: list[str] = []
    if summary.get("candidate_id") != manifest.get("candidate_id"):
        mismatches.append("candidate_id")
    if summary.get("release_state") != "NOT_PROMOTED" or summary.get("training_state") != "NOT_RUN":
        mismatches.append("release/training state")
    if summary.get("training_relation") != policy.get("training_relation"):
        mismatches.append("training relation")
    if source.get("raw_node_count") != expected_nodes or brain.get("rows") != expected_nodes:
        mismatches.append("raw node coverage")
    if source.get("distinct_artifact_count") != expected_artifacts or brain.get("distinct_artifact_rows") != expected_artifacts:
        mismatches.append("distinct artifact coverage")
    if coverage.get("node_decisions_total") != expected_nodes or coverage.get("node_decisions_expected") != expected_nodes or coverage.get("node_decision_coverage") != 1.0:
        mismatches.append("decision coverage")
    if coverage.get("formula_records_current_versioned_sources") != expected_formulas or formulas.get("rows") != expected_formulas:
        mismatches.append("formula coverage")
    if resulting.get("receipt_id") != evaluation_receipt_id or resulting.get("sha256") != evaluation_spec.get("sha256"):
        mismatches.append("evaluation receipt binding")
    if resulting.get("state") != "INCOMPLETE" or resulting.get("promotion_decision") != "NOT_PROMOTED":
        mismatches.append("evaluation/promotion boundary")
    if brain.get("formula_bindings") != formulas.get("formula_bindings"):
        mismatches.append("Brain/formula Anatomy receipt crosswalk")
    for summary_name, evidence_name in (("brain_nodes", "brain_ingest_ledger"), ("formulas", "formula_curriculum_ledger")):
        declared = ledgers.get(summary_name) or {}
        expected = evidence.get(evidence_name) or {}
        if any(declared.get(key) != expected.get(key) for key in ("path", "bytes", "sha256")):
            mismatches.append(f"{summary_name} ledger binding")
    family_split = summary.get("source_family_split") or {}
    if policy.get("require_source_family_isolation") is not True or any(
        not isinstance(value, dict) or value.get("split") not in {"TRAIN", "HOLDOUT", "QUARANTINE"}
        for value in family_split.values()
    ):
        mismatches.append("source family isolation")
    if policy.get("allow_unknown_license_for_training") is not False:
        mismatches.append("unknown-license policy")
    if mismatches:
        return _result(BLOCKED, "corpus manifest coverage contract mismatch", mismatches=mismatches,
                       manifest=summary_check, brain_ledger=brain, formula_ledger=formulas)
    return _result(
        PASS,
        "full Brain decision coverage and formula holdout curriculum verified; quarantines retained",
        manifest=summary_check, brain_ledger=brain, formula_ledger=formulas,
        corpus_receipt_id=f"m1-corpus:sha256:{evidence['corpus_ingestion_manifest']['sha256']}",
        evaluation_receipt_id=evaluation_receipt_id,
        coverage=coverage, source_snapshot=source, source_family_split=family_split,
        training_state="NOT_RUN", training_relation=summary.get("training_relation"),
        quality_claim="NOT_ESTABLISHED", release_state="NOT_PROMOTED",
    )


def _training_evidence(manifest: dict[str, Any], run_root: Path | None) -> dict[str, Any]:
    checked, receipt = _json_after_verified(run_root, manifest["evidence"]["training_receipt"])
    if checked["state"] != PASS or receipt is None:
        return checked
    mismatches: list[str] = []
    base = receipt.get("base_model") or {}
    if receipt.get("schema") != "szl.bounded-lora-training-receipt/v1":
        mismatches.append("schema")
    if receipt.get("state") != "COMPLETED":
        mismatches.append("state")
    if receipt.get("evidence_label") != "MEASURED":
        mismatches.append("evidence_label")
    if receipt.get("receipt_sha256") != manifest["evidence"]["training_receipt"]["internal_sha256"]:
        mismatches.append("receipt_sha256")
    if base.get("repo") != manifest["base"]["repository"]:
        mismatches.append("base_model.repo")
    if base.get("revision") != manifest["base"]["revision"]:
        mismatches.append("base_model.revision")
    if base.get("network_download_allowed") is not False:
        mismatches.append("base_model.network_download_allowed")
    if (receipt.get("evaluation") or {}).get("quality_claim") != "NOT_ESTABLISHED":
        mismatches.append("evaluation.quality_claim")
    if (receipt.get("artifacts") or {}).get("promotion_state") != "NOT_PROMOTED":
        mismatches.append("artifacts.promotion_state")
    receipt_files = {item.get("path"): item for item in (receipt.get("artifacts") or {}).get("files", [])}
    for expected in manifest["adapter"]["files"]:
        actual = receipt_files.get(expected["path"])
        if not actual or actual.get("sha256") != expected["sha256"] or actual.get("bytes") != expected["bytes"]:
            mismatches.append(f"artifacts.files:{expected['path']}")
    if mismatches:
        return _result(BLOCKED, "training receipt content does not match the operational manifest",
                       mismatches=mismatches, file=checked)
    return _result(PASS, "training receipt integrity and lineage match", file=checked,
                   measured_state="COMPLETED", quality_claim="NOT_ESTABLISHED",
                   release_state="NOT_PROMOTED")


def _reload_evidence(manifest: dict[str, Any], run_root: Path | None) -> dict[str, Any]:
    checked, receipt = _json_after_verified(run_root, manifest["evidence"]["reload_receipt"])
    if checked["state"] != PASS or receipt is None:
        return checked
    adapter_sha = next(
        item["sha256"] for item in manifest["adapter"]["files"]
        if item["path"] == "adapter/adapter_model.safetensors"
    )
    mismatches = []
    if receipt.get("schema") != "szl.adapter-reload-smoke/v1":
        mismatches.append("schema")
    if receipt.get("state") != "PASS":
        mismatches.append("state")
    if receipt.get("offline") is not True:
        mismatches.append("offline")
    if receipt.get("adapter_model_sha256") != adapter_sha:
        mismatches.append("adapter_model_sha256")
    if not receipt.get("generated_text_sha256"):
        mismatches.append("generated_text_sha256")
    if mismatches:
        return _result(BLOCKED, "offline reload receipt content mismatch", mismatches=mismatches, file=checked)
    return _result(PASS, "offline reload receipt verified", file=checked,
                   interpretation="COMPATIBILITY_ONLY_NOT_QUALITY",
                   generated_text_sha256=receipt["generated_text_sha256"])


def _runtime_provider(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest["provider"]["id"]
    configured = os.environ.get("A11OY_M1_PROVIDER_ID", "").strip()
    if os.environ.get("A11OY_M1_BASE_URL", "").strip():
        return _result(BLOCKED, "remote provider/base URL is forbidden for M1", expected_provider_id=expected)
    if not configured:
        return _result(UNAVAILABLE, "A11OY_M1_PROVIDER_ID is not configured", expected_provider_id=expected)
    if configured != expected:
        return _result(BLOCKED, "configured provider identity mismatch", expected_provider_id=expected)
    packages = {name: importlib.util.find_spec(name) is not None for name in ("torch", "transformers", "peft")}
    if not all(packages.values()):
        return _result(UNAVAILABLE, "local PEFT runtime dependencies are unavailable",
                       provider_id=configured, transport="IN_PROCESS_ONLY", packages=packages)
    return _result(PASS, "exact local in-process provider identity and runtime are available",
                   provider_id=configured, transport="IN_PROCESS_ONLY", network_allowed=False, packages=packages)


def _gpu_snapshot() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
    if not executable:
        return _result(UNAVAILABLE, "nvidia-smi is unavailable")
    query = [
        executable,
        "--query-gpu=index,name,memory.total,memory.free,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(query, capture_output=True, text=True, timeout=3, check=False, shell=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return _result(UNAVAILABLE, f"GPU telemetry unavailable ({type(exc).__name__})")
    if completed.returncode != 0:
        return _result(UNAVAILABLE, "nvidia-smi telemetry command failed")
    target = os.environ.get("A11OY_M1_GPU_INDEX", "0").strip()
    rows = []
    for raw in completed.stdout.splitlines():
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 6:
            continue
        try:
            rows.append({
                "index": parts[0], "name": parts[1], "total_memory_mib": int(float(parts[2])),
                "free_memory_mib": int(float(parts[3])), "utilization_pct": int(float(parts[4])),
                "temperature_c": int(float(parts[5])),
            })
        except ValueError:
            continue
    selected = next((row for row in rows if row["index"] == target), None)
    if selected is None:
        return _result(UNAVAILABLE, "configured GPU index was not reported", gpu_index=target)
    return _result(PASS, "live GPU telemetry measured", **selected)


def _gpu_admission(manifest: dict[str, Any]) -> dict[str, Any]:
    snapshot = _gpu_snapshot()
    if snapshot["state"] != PASS:
        return snapshot
    policy = manifest["gpu_admission"]
    reasons = []
    if snapshot["name"] != manifest["provider"]["expected_gpu_name"]:
        reasons.append("GPU identity mismatch")
    if snapshot["free_memory_mib"] < policy["minimum_free_memory_mib"]:
        reasons.append("insufficient free GPU memory")
    if snapshot["utilization_pct"] > policy["maximum_utilization_pct"]:
        reasons.append("GPU utilization exceeds admission ceiling")
    if snapshot["temperature_c"] > policy["maximum_temperature_c"]:
        reasons.append("GPU temperature exceeds admission ceiling")
    if reasons:
        return _result(BLOCKED, "; ".join(reasons), telemetry=snapshot, policy=policy)
    return _result(PASS, "live GPU identity and resource admission pass", telemetry=snapshot, policy=policy)


def operational_status() -> dict[str, Any]:
    try:
        manifest = _load_manifest()
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        return {
            "schema": SCHEMA, "candidate_id": "a11oy-evidence-1.5b-sft-lora",
            "operational_state": BLOCKED, "release_state": "NOT_PROMOTED",
            "production_eligible": False, "inference_mode": "DISABLED",
            "reason": f"operational manifest invalid ({type(exc).__name__})", "checks": {},
        }

    run_root = _configured_root("A11OY_M1_RUN_ROOT")
    base_root = _configured_root("A11OY_M1_BASE_SNAPSHOT")
    metadata = _metadata_evidence(manifest)
    corpus = _corpus_evidence(manifest)
    base = _rollup_files(base_root, manifest["base"]["files"], "base snapshot")
    adapter = _rollup_files(run_root, manifest["adapter"]["files"], "adapter")
    training = _training_evidence(manifest, run_root)
    reload = _reload_evidence(manifest, run_root)
    provider = _runtime_provider(manifest)
    gpu = _gpu_admission(manifest)

    tokenizer_paths = {"added_tokens.json", "merges.txt", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json", "vocab.json"}
    tokenizer_files = [item for item in base["files"] if item["path"] in tokenizer_paths]
    tokenizer_state = BLOCKED if any(item["state"] == BLOCKED for item in tokenizer_files) else (
        UNAVAILABLE if any(item["state"] == UNAVAILABLE for item in tokenizer_files) else PASS
    )
    tokenizer = {
        "state": tokenizer_state,
        "reason": f"tokenizer: {sum(item['state'] == PASS for item in tokenizer_files)}/{len(tokenizer_files)} exact files verified",
        "files": tokenizer_files,
    }
    checks = {
        "metadata": metadata, "corpus_ingestion": corpus,
        "base_weights": base, "adapter_weights": adapter,
        "tokenizer": tokenizer, "training_receipt": training, "offline_reload": reload,
        "evaluation_receipt": {
            "state": metadata["state"],
            "reason": "evaluation receipt integrity verified; broad quality evaluation remains incomplete" if metadata["state"] == PASS else metadata["reason"],
            "quality_claim": "NOT_ESTABLISHED", "release_state": "NOT_PROMOTED",
            "evaluation_state": metadata.get("evaluation_state"), "unrun_suites": metadata.get("unrun_suites", []),
        },
        "provider_identity": provider, "gpu_admission": gpu,
    }
    mandatory = [entry["state"] for entry in checks.values()]
    state = BLOCKED if BLOCKED in mandatory else UNAVAILABLE if UNAVAILABLE in mandatory else READY
    enabled = state == READY
    stages = {
        "corpus": {
            "state": "FULL_DECISION_LEDGER_VERIFIED" if corpus["state"] == PASS else corpus["state"],
            "raw_nodes": (corpus.get("coverage") or {}).get("node_decisions_total"),
            "distinct_artifacts": (corpus.get("coverage") or {}).get("distinct_artifacts"),
            "quarantined_or_excluded": (corpus.get("coverage") or {}).get("quarantined_or_excluded_nodes"),
            "formula_records": (corpus.get("coverage") or {}).get("formula_records_current_versioned_sources"),
            "training": "NOT_RUN",
        },
        "weights": {"state": PASS if base["state"] == adapter["state"] == tokenizer["state"] == PASS else state,
                    "base": base["state"], "adapter": adapter["state"], "tokenizer": tokenizer["state"]},
        "load": {"state": "READY_TO_LOAD" if provider["state"] == reload["state"] == gpu["state"] == PASS else state,
                 "provider": provider["state"], "offline_reload": reload["state"], "gpu": gpu["state"]},
        "evaluation": {"state": "EVIDENCE_VERIFIED_WITH_LIMITS" if metadata["state"] == PASS else metadata["state"],
                       "quality_claim": "NOT_ESTABLISHED", "promotion": "NOT_PROMOTED"},
        "inference": {"state": "ENABLED_EXPERIMENTAL_LOCAL_ONLY" if enabled else "DISABLED",
                      "production": "BLOCKED", "network": "DISABLED"},
    }
    return {
        "schema": SCHEMA, "candidate_id": manifest["candidate_id"], "checked_at": _now(),
        "operational_state": state, "release_state": "NOT_PROMOTED", "quality_claim": "NOT_ESTABLISHED",
        "production_eligible": False, "inference_mode": "EXPERIMENTAL_LOCAL_ONLY" if enabled else "DISABLED",
        "effectors": {"network": "DISABLED", "download": "DISABLED", "training": "DISABLED", "publishing": "DISABLED"},
        "configured": {"run_root": run_root is not None, "base_snapshot": base_root is not None,
                       "provider_identity": bool(os.environ.get("A11OY_M1_PROVIDER_ID", "").strip())},
        "stages": stages, "checks": checks,
        "corpus_coverage": corpus.get("coverage", {}),
    }


async def _bounded_json(request: Request, maximum: int) -> dict[str, Any]:
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) < 0 or int(declared) > maximum:
                raise ContractError(f"request body exceeds {maximum} bytes")
        except ValueError as exc:
            raise ContractError("content-length must be a non-negative integer") from exc
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > maximum:
            raise ContractError(f"request body exceeds {maximum} bytes")
        body.extend(chunk)
    try:
        value = json.loads(bytes(body).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("body must be one JSON object") from exc
    if not isinstance(value, dict):
        raise ContractError("body must be one JSON object")
    return value


def _parse_inference_request(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    required = {"schema", "prompt", "max_new_tokens", "temperature", "requested_tier", "provider_id"}
    if set(payload) != required:
        raise ContractError(f"fields must be exactly {sorted(required)}")
    if payload.get("schema") != INFER_SCHEMA:
        raise ContractError("unsupported inference request schema")
    if payload.get("requested_tier") != "EXPERIMENTAL_LOCAL_ONLY":
        raise ContractError("production and promoted tiers are forbidden for M1")
    if payload.get("provider_id") != manifest["provider"]["id"]:
        raise ContractError("request provider identity mismatch")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > manifest["inference_policy"]["max_prompt_chars"]:
        raise ContractError("prompt must be non-empty and within the character limit")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in prompt):
        raise ContractError("prompt contains disallowed control characters")
    max_new_tokens = payload.get("max_new_tokens")
    if not isinstance(max_new_tokens, int) or isinstance(max_new_tokens, bool) or not 1 <= max_new_tokens <= manifest["inference_policy"]["max_new_tokens"]:
        raise ContractError("max_new_tokens is outside the bounded policy")
    temperature = payload.get("temperature")
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool) or not 0 <= float(temperature) <= 1:
        raise ContractError("temperature must be within [0,1]")
    return {"prompt": prompt, "max_new_tokens": max_new_tokens, "temperature": float(temperature),
            "provider_id": payload["provider_id"]}


def _local_peft_inference(parsed: dict[str, Any], manifest: dict[str, Any]) -> str:
    """Load exact local paths with local_files_only and run one bounded turn."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    run_root = _configured_root("A11OY_M1_RUN_ROOT")
    base_root = _configured_root("A11OY_M1_BASE_SNAPSHOT")
    if run_root is None or base_root is None:
        raise RuntimeError("artifact roots unavailable")
    adapter_root = _confined_file(run_root, "adapter/adapter_config.json").parent
    gpu_index = int(os.environ.get("A11OY_M1_GPU_INDEX", "0"))
    model = None
    tuned = None
    try:
        torch.cuda.set_device(gpu_index)
        tokenizer = AutoTokenizer.from_pretrained(str(adapter_root), local_files_only=True, trust_remote_code=False)
        model = AutoModelForCausalLM.from_pretrained(
            str(base_root), local_files_only=True, trust_remote_code=False, device_map={"": gpu_index}
        )
        tuned = PeftModel.from_pretrained(
            model, str(adapter_root), local_files_only=True, is_trainable=False
        )
        tuned.eval()
        inputs = tokenizer(parsed["prompt"], return_tensors="pt", truncation=True, max_length=384)
        inputs = {key: value.to(f"cuda:{gpu_index}") for key, value in inputs.items()}
        kwargs: dict[str, Any] = {
            "max_new_tokens": parsed["max_new_tokens"], "use_cache": True,
            "do_sample": parsed["temperature"] > 0,
        }
        if parsed["temperature"] > 0:
            kwargs["temperature"] = parsed["temperature"]
        with torch.inference_mode():
            output = tuned.generate(**inputs, **kwargs)
        new_tokens = output[0, inputs["input_ids"].shape[1]:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        if not text:
            raise RuntimeError("local model returned no generated text")
        return text
    finally:
        del tuned, model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def run_inference(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        manifest = _load_manifest()
        parsed = _parse_inference_request(payload, manifest)
    except (OSError, ValueError, json.JSONDecodeError, KeyError, ContractError) as exc:
        return {"schema": SCHEMA, "state": BLOCKED, "release_state": "NOT_PROMOTED",
                "production_eligible": False, "error": str(exc)}, 422

    status = operational_status()
    if status["operational_state"] != READY:
        code = 409 if status["operational_state"] == BLOCKED else 503
        return {"schema": SCHEMA, "state": status["operational_state"], "release_state": "NOT_PROMOTED",
                "production_eligible": False, "inference": None, "gate": status}, code
    if not _INFERENCE_LOCK.acquire(blocking=False):
        return {"schema": SCHEMA, "state": BLOCKED, "release_state": "NOT_PROMOTED",
                "production_eligible": False, "error": "bounded M1 concurrency slot is busy"}, 429
    started = time.perf_counter()
    try:
        # Re-run the full exact gate immediately before executing. No hash cache is
        # used, so a changed file or GPU state fails closed.
        preflight = operational_status()
        if preflight["operational_state"] != READY:
            code = 409 if preflight["operational_state"] == BLOCKED else 503
            return {"schema": SCHEMA, "state": preflight["operational_state"],
                    "release_state": "NOT_PROMOTED", "production_eligible": False,
                    "inference": None, "gate": preflight}, code
        try:
            text = _local_peft_inference(parsed, manifest)
        except Exception as exc:
            return {"schema": SCHEMA, "state": UNAVAILABLE, "release_state": "NOT_PROMOTED",
                    "production_eligible": False, "inference": None,
                    "error": f"local inference failed ({type(exc).__name__}); no output fabricated"}, 503
        receipt_core = {
            "schema": RECEIPT_SCHEMA, "candidate_id": manifest["candidate_id"],
            "release_state": "NOT_PROMOTED", "quality_claim": "NOT_ESTABLISHED",
            "tier": "EXPERIMENTAL_LOCAL_ONLY", "provider_id": manifest["provider"]["id"],
            "prompt_sha256": _digest_bytes(parsed["prompt"].encode("utf-8")),
            "output_sha256": _digest_bytes(text.encode("utf-8")),
            "max_new_tokens": parsed["max_new_tokens"], "temperature": parsed["temperature"],
            "duration_ms": round((time.perf_counter() - started) * 1000, 3), "completed_at": _now(),
            "network": "DISABLED", "production_eligible": False,
            "corpus_receipt_id": preflight["checks"]["corpus_ingestion"]["corpus_receipt_id"],
            "evaluation_receipt_id": preflight["checks"]["corpus_ingestion"]["evaluation_receipt_id"],
            "corpus_relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
        }
        receipt = {**receipt_core, "receipt_sha256": _digest_bytes(_canonical(receipt_core)),
                   "signature_state": "UNSIGNED_DETERMINISTIC_DIGEST_ONLY"}
        return {"schema": SCHEMA, "state": "RESULT", "release_state": "NOT_PROMOTED",
                "quality_claim": "NOT_ESTABLISHED", "production_eligible": False,
                "inference": {"text": text, "provider_id": manifest["provider"]["id"]},
                "receipt": receipt}, 200
    finally:
        _INFERENCE_LOCK.release()


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    from fastapi.responses import FileResponse, JSONResponse

    prefix = f"/api/{ns}/v1/models/m1"
    before = {id(route) for route in app.router.routes}

    @app.get(prefix)
    async def m1_status() -> JSONResponse:
        return JSONResponse(operational_status())

    @app.post(f"{prefix}/infer")
    async def m1_infer(request: Request) -> JSONResponse:
        try:
            manifest = _load_manifest()
            payload = await _bounded_json(request, int(manifest["inference_policy"]["max_request_bytes"]))
        except (ContractError, OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
            return JSONResponse({"schema": SCHEMA, "state": BLOCKED, "release_state": "NOT_PROMOTED",
                                 "production_eligible": False, "error": str(exc)}, status_code=422)
        result, status_code = await asyncio.to_thread(run_inference, payload)
        return JSONResponse(result, status_code=status_code)

    @app.get("/models/m1")
    async def m1_page() -> Any:
        if not PAGE_PATH.is_file():
            return JSONResponse({"state": UNAVAILABLE, "error": "M1 status page is unavailable"}, status_code=503)
        return FileResponse(PAGE_PATH, media_type="text/html")

    added = [route for route in app.router.routes if id(route) not in before]
    for route in added:
        app.router.routes.remove(route)
    for route in reversed(added):
        app.router.routes.insert(0, route)
    return {"registered": True, "routes": [prefix, f"{prefix}/infer", "/models/m1"],
            "release_state": "NOT_PROMOTED", "production_eligible": False}


__all__ = [
    "BLOCKED", "ContractError", "INFER_SCHEMA", "PASS", "READY", "SCHEMA",
    "UNAVAILABLE", "operational_status", "register", "run_inference",
]
