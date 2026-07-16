#!/usr/bin/env python3
"""Build the unpublished SZL proof-obligation companion dataset.

The builder is intentionally local and deterministic.  It verifies the source
receipts before copying any source artifact, emits no raw Brain text, and never
changes training, publication, DOI, or remote state.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
from collections import Counter
from typing import Any, Iterable, Mapping


PACKAGE_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = PACKAGE_DIR / "data"

SOURCE_CROSSWALK = pathlib.Path(
    "research/formula-training-admission/formula-id-crosswalk.json"
)
SOURCE_TRANCHE = pathlib.Path(
    "research/formula-training-admission/admission-tranche.jsonl"
)
SOURCE_RECEIPT = pathlib.Path(
    "research/formula-training-admission/artifact-receipt.json"
)
SOURCE_ADMISSION_MANIFEST = pathlib.Path(
    "research/formula-training-admission/admission-manifest.json"
)
SOURCE_BRAIN_MANIFEST = pathlib.Path(
    "research/brain-evidence-admission/evidence-manifest.json"
)
SOURCE_BRAIN_RESULTS = pathlib.Path(
    "research/brain-evidence-admission/evaluation-results.json"
)

FORMULA_SOURCE_COMMIT = "e4d269b309fe67264f1dfe64a65c3c5fb6ecf570"
FORMULA_ADMISSION_RECEIPT_COMMIT = (
    "b7b0f2996edf674d7365d37112371fa6690e7c0e"
)
BRAIN_SOURCE_COMMIT = "706894f52a45f80a5c440aeaafc52eec33fafc23"


class PackageError(RuntimeError):
    """Raised when a source receipt or release invariant fails closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(relative: pathlib.Path) -> dict[str, Any]:
    value = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackageError(f"SOURCE_NOT_OBJECT:{relative.as_posix()}")
    return value


def read_jsonl(relative: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (REPO_ROOT / relative).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise PackageError(
                    f"SOURCE_ROW_NOT_OBJECT:{relative.as_posix()}:{line_number}"
                )
            rows.append(value)
    return rows


def verify_receipted(value: Mapping[str, Any], field: str, label: str) -> None:
    observed = value.get(field)
    payload = dict(value)
    payload.pop(field, None)
    expected = sha256_bytes(canonical_bytes(payload))
    if observed != expected:
        raise PackageError(f"INVALID_CONTENT_RECEIPT:{label}")


def verify_sources(
    crosswalk: Mapping[str, Any],
    tranche: Iterable[Mapping[str, Any]],
    source_receipt: Mapping[str, Any],
) -> None:
    verify_receipted(crosswalk, "crosswalk_receipt_sha256", "crosswalk")
    for row in tranche:
        verify_receipted(row, "record_receipt_sha256", str(row.get("record_id")))
    verify_receipted(source_receipt, "artifact_receipt_sha256", "artifact-receipt")

    artifacts = source_receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise PackageError("SOURCE_RECEIPT_ARTIFACTS_MISSING")
    for source_path, expected_digest in artifacts.items():
        observed = sha256_file(REPO_ROOT / source_path)
        if observed != expected_digest:
            raise PackageError(f"SOURCE_DIGEST_MISMATCH:{source_path}")


def required_actions(record: Mapping[str, Any]) -> list[str]:
    status = record["resolved_status"]
    reasons = set(record.get("status_reasons") or [])
    actions: list[str] = []

    if record.get("semantic_relation") == "ID_COLLISION_DIFFERENT_STATEMENT":
        actions.append("DISAMBIGUATE_FORMULA_NAMESPACE")

    if status == "KERNEL_ACCEPTED":
        actions.append("PRESERVE_EXACT_BINDING_AND_CONTENT_HASH")
    elif status == "CONDITIONAL":
        if "EXACT_LEAN_REFERENCE_MISSING" in reasons:
            actions.append("BIND_EXACT_LEAN_DECLARATION")
        if "EXPERIMENTAL_OR_UNPINNED_PROOF_SCOPE" in reasons:
            actions.append("PIN_PROOF_SCOPE_REVISION_AND_BUILD_RECEIPT")
        if "LOCKED_SUMMARY_ITEM_BINDING_DISAGREES_OR_IS_UNRESOLVED" in reasons:
            actions.append("RECONCILE_ITEM_LEVEL_STATUS")
        if not any(action != "DISAMBIGUATE_FORMULA_NAMESPACE" for action in actions):
            actions.append("RESOLVE_CONDITIONS_BEFORE_PROOF_CLAIM")
    elif status == "OPEN":
        actions.append("PROVIDE_KERNEL_CHECKED_PROOF_OR_RETAIN_OPEN_STATUS")
    elif status == "REFUTED":
        actions.append("PRESERVE_REFUTATION_EVIDENCE_AND_BLOCK_PROOF_CLAIM")
    else:
        raise PackageError(f"UNKNOWN_FORMULA_STATUS:{status}")
    return actions


def obligation_state(status: str) -> str:
    return {
        "KERNEL_ACCEPTED": "SATISFIED_LOCAL_ITEM_BINDING",
        "CONDITIONAL": "ACTION_REQUIRED_CONDITIONAL",
        "OPEN": "ACTION_REQUIRED_OPEN",
        "REFUTED": "CONFLICT_RECORDED_REFUTED",
    }[status]


def build_queue(
    crosswalk: Mapping[str, Any],
    tranche: Iterable[Mapping[str, Any]],
    source_receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tranche_by_id = {
        row["record_id"]: row
        for row in tranche
        if row.get("record_kind") == "FORMULA_STATUS_METADATA"
    }
    rows: list[dict[str, Any]] = []
    for source in crosswalk["records"]:
        record_id = source["record_id"]
        tranche_row = tranche_by_id.get(record_id)
        if tranche_row is None:
            raise PackageError(f"TRANCHE_BINDING_MISSING:{record_id}")
        if tranche_row.get("claim_sha256") != source.get("claim_sha256"):
            raise PackageError(f"TRANCHE_CLAIM_MISMATCH:{record_id}")

        status = source["resolved_status"]
        payload: dict[str, Any] = {
            "schema_version": "szl.proof-obligation-record.v1",
            "queue_id": f"proof-obligation:{record_id}",
            "record_id": record_id,
            "formula_id": source["formula_id"],
            "formula_namespace": source["formula_namespace"],
            "canonical_name": source["canonical_name"],
            "claim_sha256": source["claim_sha256"],
            "resolved_status": status,
            "obligation_state": obligation_state(status),
            "queue_membership": (
                "AUDIT_ONLY" if status == "KERNEL_ACCEPTED" else "ACTION_REQUIRED"
            ),
            "required_actions": required_actions(source),
            "status_reasons": list(source.get("status_reasons") or []),
            "lean_reference": {
                "identifier": source.get("lean_ref"),
                "observed": bool(source.get("lean_ref_present")),
            },
            "namespace_collision": {
                "relation": source.get("semantic_relation"),
                "other_namespace": source.get("same_id_other_namespace"),
                "other_name": source.get("same_id_other_name"),
            },
            "proof_transfer_allowed": False,
            "split": "HOLDOUT",
            "training_eligible": False,
            "receipt_scope": {
                "source_artifact_receipt_sha256": source_receipt[
                    "artifact_receipt_sha256"
                ],
                "source_crosswalk_receipt_sha256": crosswalk[
                    "crosswalk_receipt_sha256"
                ],
                "source_record_receipt_sha256": tranche_row[
                    "record_receipt_sha256"
                ],
            },
        }
        payload["queue_record_sha256"] = sha256_bytes(canonical_bytes(payload))
        rows.append(payload)
    return rows


def build_brain_summary(
    brain_manifest: Mapping[str, Any], brain_results: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "szl.proof-obligation-brain-summary.v1",
        "source": {
            "commit": BRAIN_SOURCE_COMMIT,
            "manifest_path": SOURCE_BRAIN_MANIFEST.as_posix(),
            "manifest_file_sha256": sha256_file(REPO_ROOT / SOURCE_BRAIN_MANIFEST),
            "manifest_receipt_sha256": brain_manifest["manifest_receipt_sha256"],
            "results_path": SOURCE_BRAIN_RESULTS.as_posix(),
            "results_file_sha256": sha256_file(REPO_ROOT / SOURCE_BRAIN_RESULTS),
            "results_receipt_sha256": brain_results["results_receipt_sha256"],
            "protocol_id": brain_manifest["protocol_id"],
        },
        "evidence_label": brain_manifest["label"],
        "pilot_status": brain_manifest["status"],
        "admission_summary": brain_manifest["admission_summary"],
        "metrics": brain_manifest["metrics"],
        "limitations": brain_manifest["limitations"],
        "inclusion_boundary": {
            "raw_brain_content_included": False,
            "canonical_document_text_included": False,
            "query_text_included": False,
            "per_query_results_included": False,
            "summary_metrics_included": True,
            "training_eligible": False,
        },
        "claims_boundary": {
            **brain_manifest["claims_boundary"],
            "independent_replication": False,
            "external_validity": "NOT_ESTABLISHED",
            "peer_reviewed": False,
        },
    }


def file_entry(path: pathlib.Path, rows: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": path.relative_to(PACKAGE_DIR).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if rows is not None:
        entry["rows"] = rows
    return entry


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_bytes(pretty_bytes(value))


def write_jsonl(path: pathlib.Path, rows: Iterable[Mapping[str, Any]]) -> int:
    row_list = list(rows)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in row_list:
            stream.write(canonical_bytes(row).decode("utf-8") + "\n")
    return len(row_list)


def build() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    crosswalk = load_json(SOURCE_CROSSWALK)
    tranche = read_jsonl(SOURCE_TRANCHE)
    source_receipt = load_json(SOURCE_RECEIPT)
    brain_manifest = load_json(SOURCE_BRAIN_MANIFEST)
    brain_results = load_json(SOURCE_BRAIN_RESULTS)
    verify_sources(crosswalk, tranche, source_receipt)

    crosswalk_target = DATA_DIR / "formula-id-crosswalk.json"
    tranche_target = DATA_DIR / "admission-tranche.jsonl"
    receipt_target = DATA_DIR / "source-artifact-receipt.json"
    admission_manifest_target = DATA_DIR / "source-admission-manifest.json"
    shutil.copyfile(REPO_ROOT / SOURCE_CROSSWALK, crosswalk_target)
    shutil.copyfile(REPO_ROOT / SOURCE_TRANCHE, tranche_target)
    shutil.copyfile(REPO_ROOT / SOURCE_RECEIPT, receipt_target)
    shutil.copyfile(
        REPO_ROOT / SOURCE_ADMISSION_MANIFEST, admission_manifest_target
    )

    queue = build_queue(crosswalk, tranche, source_receipt)
    queue_target = DATA_DIR / "proof-obligation-queue.jsonl"
    queue_rows = write_jsonl(queue_target, queue)

    brain_summary = build_brain_summary(brain_manifest, brain_results)
    brain_target = DATA_DIR / "brain-evidence-summary.json"
    write_json(brain_target, brain_summary)

    status_counts = Counter(row["resolved_status"] for row in queue)
    membership_counts = Counter(row["queue_membership"] for row in queue)
    tranche_kind_counts = Counter(row["record_kind"] for row in tranche)
    manifest: dict[str, Any] = {
        "schema_version": "szl.proof-obligation-dataset-release.v1",
        "title": "SZL Proof-Obligation Queue and Receipt-Scoped Formula Crosswalk",
        "version": "0.1.0",
        "record_type": "dataset",
        "publication": {
            "state": "UNPUBLISHED_CANDIDATE",
            "doi": "PENDING",
            "doi_url": "PENDING",
            "peer_reviewed": False,
            "zenodo_deposition_created": False,
            "remote_mutation_performed": False,
            "publish_allowed": False,
            "blockers": [
                "HUMAN_RELEASE_APPROVAL_REQUIRED",
                "ROW_LEVEL_RIGHTS_AND_LICENSE_REVIEW_REQUIRED",
                "ARCHIVE_UPLOAD_AND_READBACK_NOT_RUN",
                "DOI_NOT_MINTED",
            ],
        },
        "dataset": {
            "formula_crosswalk_rows": len(crosswalk["records"]),
            "admission_tranche_rows": len(tranche),
            "proof_obligation_queue_rows": queue_rows,
            "queue_membership_counts": dict(sorted(membership_counts.items())),
            "resolved_status_counts": dict(sorted(status_counts.items())),
            "tranche_kind_counts": dict(sorted(tranche_kind_counts.items())),
            "training_eligible_rows": 0,
            "split": "HOLDOUT_ONLY",
        },
        "source_snapshots": {
            "formula_admission": {
                "crosswalk_and_tranche_commit": FORMULA_SOURCE_COMMIT,
                "admission_manifest_and_receipt_commit": (
                    FORMULA_ADMISSION_RECEIPT_COMMIT
                ),
                "artifact_receipt_sha256": source_receipt[
                    "artifact_receipt_sha256"
                ],
                "crosswalk_receipt_sha256": crosswalk[
                    "crosswalk_receipt_sha256"
                ],
            },
            "brain_evidence": {
                "commit": BRAIN_SOURCE_COMMIT,
                "protocol_id": brain_manifest["protocol_id"],
                "manifest_receipt_sha256": brain_manifest[
                    "manifest_receipt_sha256"
                ],
                "results_receipt_sha256": brain_results[
                    "results_receipt_sha256"
                ],
            },
        },
        "artifacts": {
            "formula_crosswalk": file_entry(crosswalk_target, len(crosswalk["records"])),
            "admission_tranche": file_entry(tranche_target, len(tranche)),
            "source_artifact_receipt": file_entry(receipt_target),
            "source_admission_manifest": file_entry(admission_manifest_target),
            "proof_obligation_queue": file_entry(queue_target, queue_rows),
            "brain_evidence_summary": file_entry(brain_target),
        },
        "schemas": {
            "release_manifest": "schemas/release-manifest.schema.json",
            "proof_obligation_record": "schemas/proof-obligation-record.schema.json",
        },
        "license": {
            "spdx": "Apache-2.0",
            "scope": "Package-authored metadata, schemas, and deterministic transformations.",
            "upstream_rights_rule": (
                "The package license does not cure unknown or incompatible rights in "
                "any upstream source; publication remains blocked pending item-level review."
            ),
        },
        "claims_boundary": {
            "mathematical_proof_added": False,
            "proof_credit_added": 0,
            "raw_brain_text_included": False,
            "model_training_triggered": False,
            "model_promotion_allowed": False,
            "training_eligibility_claimed": False,
            "independent_replication_claimed": False,
            "peer_review_claimed": False,
        },
        "prohibited_claims": [
            "THE_DATASET_IS_TRAINING_ELIGIBLE",
            "A_FORMULA_ID_ALONE_TRANSFERS_PROOF_BETWEEN_NAMESPACES",
            "EXECUTABILITY_IMPLIES_MATHEMATICAL_PROOF",
            "THE_LOCAL_RETRIEVAL_PILOT_ESTABLISHES_EXTERNAL_VALIDITY",
            "THIS_UNPUBLISHED_PACKAGE_HAS_A_DOI_OR_PEER_REVIEW",
        ],
    }
    manifest_path = PACKAGE_DIR / "release-manifest.json"
    write_json(manifest_path, manifest)

    checksum_paths = sorted(
        path
        for path in PACKAGE_DIR.rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS"
        and "__pycache__" not in path.parts
    )
    with (PACKAGE_DIR / "SHA256SUMS").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        for path in checksum_paths:
            stream.write(
                f"{sha256_file(path)}  {path.relative_to(PACKAGE_DIR).as_posix()}\n"
            )
    return manifest


if __name__ == "__main__":
    built = build()
    print(
        json.dumps(
            {
                "status": built["publication"]["state"],
                "doi": built["publication"]["doi"],
                "queue_rows": built["dataset"]["proof_obligation_queue_rows"],
                "training_eligible_rows": built["dataset"][
                    "training_eligible_rows"
                ],
            },
            sort_keys=True,
        )
    )
