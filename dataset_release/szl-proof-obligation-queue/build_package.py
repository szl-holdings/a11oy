#!/usr/bin/env python3
"""Verify and reproduce the frozen, unpublished proof-obligation package.

Retained package bytes are the build inputs. Mutable research artifacts are
compared only in a separate diagnostic; they cannot silently replace the
historical source snapshot. This command writes no package or remote state.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
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
    required = {SOURCE_CROSSWALK.as_posix(), SOURCE_TRANCHE.as_posix(),
                SOURCE_ADMISSION_MANIFEST.as_posix()}
    if set(artifacts) != required:
        raise PackageError("SOURCE_RECEIPT_ARTIFACT_SET_MISMATCH")
    for source_path, expected_digest in artifacts.items():
        observed = sha256_file(PACKAGE_DIR / RETAINED_SOURCES[source_path])
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


# The retained release manifest is reviewed historical evidence. This digest
# deliberately does not follow mutable research/ output or regenerate itself.
FROZEN_RELEASE_MANIFEST_SHA256 = "091387a1e3a397f61df5a4cd14c89fb6c232d8e5e9be83bd40a0b9c798bb9c4d"
RETAINED_SOURCES = {
    SOURCE_CROSSWALK.as_posix(): "data/formula-id-crosswalk.json",
    SOURCE_TRANCHE.as_posix(): "data/admission-tranche.jsonl",
    SOURCE_RECEIPT.as_posix(): "data/source-artifact-receipt.json",
    SOURCE_ADMISSION_MANIFEST.as_posix(): "data/source-admission-manifest.json",
}
RETAINED_ARTIFACTS = {
    "formula_crosswalk": "data/formula-id-crosswalk.json",
    "admission_tranche": "data/admission-tranche.jsonl",
    "source_artifact_receipt": "data/source-artifact-receipt.json",
    "source_admission_manifest": "data/source-admission-manifest.json",
    "proof_obligation_queue": "data/proof-obligation-queue.jsonl",
    "brain_evidence_summary": "data/brain-evidence-summary.json",
}


def verify_frozen_release() -> dict[str, Any]:
    path = PACKAGE_DIR / "release-manifest.json"
    if sha256_file(path) != FROZEN_RELEASE_MANIFEST_SHA256:
        raise PackageError("FROZEN_RELEASE_MANIFEST_CHANGED")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if set(manifest["artifacts"]) != set(RETAINED_ARTIFACTS):
        raise PackageError("RETAINED_ARTIFACT_SET_MISMATCH")
    for key, relative in RETAINED_ARTIFACTS.items():
        item = manifest["artifacts"][key]
        target = PACKAGE_DIR / relative
        if item["path"] != relative:
            raise PackageError(f"RETAINED_ARTIFACT_PATH_MISMATCH:{key}")
        if target.stat().st_size != item["bytes"] or sha256_file(target) != item["sha256"]:
            raise PackageError(f"RETAINED_ARTIFACT_DIGEST_MISMATCH:{key}")
    source = manifest["source_snapshots"]
    if (source["formula_admission"]["crosswalk_and_tranche_commit"] != FORMULA_SOURCE_COMMIT
            or source["formula_admission"]["admission_manifest_and_receipt_commit"]
            != FORMULA_ADMISSION_RECEIPT_COMMIT
            or source["brain_evidence"]["commit"] != BRAIN_SOURCE_COMMIT):
        raise PackageError("FROZEN_SOURCE_COMMIT_MISMATCH")
    return manifest


def current_source_status() -> dict[str, Any]:
    """Compare current bytes without treating agreement as source freshness."""
    manifest = verify_frozen_release()
    brain = load_json(PACKAGE_DIR / RETAINED_ARTIFACTS["brain_evidence_summary"])
    expected = {
        source: sha256_file(PACKAGE_DIR / retained)
        for source, retained in RETAINED_SOURCES.items()
    }
    expected[SOURCE_BRAIN_MANIFEST.as_posix()] = brain["source"]["manifest_file_sha256"]
    expected[SOURCE_BRAIN_RESULTS.as_posix()] = brain["source"]["results_file_sha256"]
    observations = []
    for relative, retained_digest in sorted(expected.items()):
        try:
            observed = sha256_file(REPO_ROOT / relative)
        except OSError:
            observed = None
        observations.append({
            "path": relative, "retained_sha256": retained_digest,
            "current_sha256": observed,
            "state": "BYTE_MATCH" if observed == retained_digest else
                     ("UNAVAILABLE" if observed is None else "NOT_CURRENT"),
        })
    return {
        "state": "BYTE_MATCH" if all(row["state"] == "BYTE_MATCH" for row in observations)
                 else "NOT_CURRENT",
        "scope": "Historical package comparison; no new source, proof or freshness claim.",
        "package_version": manifest["version"], "package_modified": False,
        "sources": observations,
    }


def build() -> dict[str, Any]:
    """Reproduce the historical queue in memory and verify retained bytes."""
    manifest = verify_frozen_release()
    crosswalk = load_json(PACKAGE_DIR / RETAINED_ARTIFACTS["formula_crosswalk"])
    tranche = read_jsonl(PACKAGE_DIR / RETAINED_ARTIFACTS["admission_tranche"])
    source_receipt = load_json(PACKAGE_DIR / RETAINED_ARTIFACTS["source_artifact_receipt"])
    admission = load_json(PACKAGE_DIR / RETAINED_ARTIFACTS["source_admission_manifest"])
    verify_sources(crosswalk, tranche, source_receipt)
    verify_receipted(admission, "manifest_receipt_sha256", "source-admission-manifest")
    if (source_receipt["crosswalk_receipt_sha256"] != crosswalk["crosswalk_receipt_sha256"]
            or source_receipt["manifest_receipt_sha256"] != admission["manifest_receipt_sha256"]):
        raise PackageError("RETAINED_SOURCE_RECEIPT_BINDING_MISMATCH")
    source = manifest["source_snapshots"]["formula_admission"]
    if (source["artifact_receipt_sha256"] != source_receipt["artifact_receipt_sha256"]
            or source["crosswalk_receipt_sha256"] != crosswalk["crosswalk_receipt_sha256"]):
        raise PackageError("RELEASE_SOURCE_RECEIPT_BINDING_MISMATCH")
    queue = build_queue(crosswalk, tranche, source_receipt)
    reproduced = b"".join(canonical_bytes(row) + b"\n" for row in queue)
    retained = (PACKAGE_DIR / RETAINED_ARTIFACTS["proof_obligation_queue"]).read_bytes()
    if reproduced != retained:
        raise PackageError("FROZEN_QUEUE_REPRODUCTION_MISMATCH")
    return manifest


if __name__ == "__main__":
    built = build()
    print(
        json.dumps(
            {
                "status": built["publication"]["state"],
                "reproduction": "FROZEN_RETAINED_INPUTS_VERIFIED",
                "current_source": current_source_status(),
                "doi": built["publication"]["doi"],
                "queue_rows": built["dataset"]["proof_obligation_queue_rows"],
                "training_eligible_rows": built["dataset"][
                    "training_eligible_rows"
                ],
            },
            sort_keys=True,
        )
    )
