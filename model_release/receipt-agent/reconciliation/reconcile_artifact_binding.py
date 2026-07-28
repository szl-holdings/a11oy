#!/usr/bin/env python3
"""Offline ReceiptAgent artifact-binding reconciliation.

The input fixture is a frozen observation captured from the public Hugging Face
Git repository.  This program performs no network access and does not download,
train, upload, promote, or deploy a model.  It separates three claims:

1. the repository-declared Ed25519 receipt signatures verified during the
   qualification run;
2. the exact qualified weight/adapter byte binding, including the ReceiptAgent
   signer's basename-plus-bytes digest domain; and
3. equivalence of every inference-bearing Git blob at the observed public head
   to the qualified revision.

Any inference-bearing drift, digest-domain mismatch, invalid qualification
self-digest, or promotion claim is a hard refusal.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "szl.receiptagent-artifact-reconciliation.v1"
FIXTURE_SCHEMA_VERSION = "szl.receiptagent-artifact-reconciliation-fixture.v1"
RECONCILED_STATE = "ARTIFACT_BYTES_RECONCILED_MEASURED_NOT_PROMOTED"
REPOSITORY = "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent"
QUALIFIED_REVISION = "fa73dc1bd8eeece727d0b5c1db52448ec0703e8b"
PUBLIC_HEAD_REVISION = "2e62cb5f8e6a17052da532305a467861094a2109"
HEX40 = set("0123456789abcdef")
HEX64 = HEX40
INFERENCE_BEARING_PATHS = frozenset(
    {
        "adapter/adapter_config.json",
        "adapter/adapter_model.safetensors",
        "chat_template.jinja",
        "config.json",
        "eval_receipt.signed.json",
        "generation_config.json",
        "model.safetensors",
        "owner_pubkey.json",
        "receiptagent.schema.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "training_receipt.signed.json",
    }
)


class ReconciliationRefusal(RuntimeError):
    """The frozen evidence cannot support artifact equivalence."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReconciliationRefusal(message)


def _strict_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    _require(set(value) == expected, f"{label} keys do not match the frozen contract")


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in HEX40 for character in value)
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def self_digest(value: dict[str, Any], field: str) -> str:
    unsigned = dict(value)
    unsigned.pop(field, None)
    return sha256_bytes(canonical_bytes(unsigned))


def receipt_digest(value: dict[str, Any]) -> str:
    return self_digest(value, "receipt_sha256")


def raw_and_receipt_digest(basename: str, content: bytes) -> tuple[str, str]:
    """Return raw bytes and ReceiptAgent signer-domain digests.

    The training signer used sha256(UTF8(basename) || raw_file_bytes) for each
    directory containing a single safetensors artifact.  It did not claim that
    this digest was the raw LFS object SHA-256.
    """

    return (
        sha256_bytes(content),
        sha256_bytes(basename.encode("utf-8") + content),
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path} must contain one JSON object")
    return value


def _verify_digest_vector(vector: dict[str, Any]) -> None:
    _strict_keys(
        vector,
        {
            "basename",
            "content_base64",
            "bytes",
            "raw_sha256",
            "receipt_directory_sha256",
        },
        "digest_test_vector",
    )
    content = base64.b64decode(vector["content_base64"], validate=True)
    _require(len(content) == vector["bytes"], "digest test-vector byte count mismatch")
    raw_sha, receipt_sha = raw_and_receipt_digest(vector["basename"], content)
    _require(raw_sha == vector["raw_sha256"], "raw digest domain test-vector mismatch")
    _require(
        receipt_sha == vector["receipt_directory_sha256"],
        "basename-plus-bytes digest domain test-vector mismatch",
    )
    _require(raw_sha != receipt_sha, "digest domains must remain explicitly distinct")


def reconcile(
    fixture: dict[str, Any],
    qualification_receipt: dict[str, Any],
) -> dict[str, Any]:
    _strict_keys(
        fixture,
        {
            "schema_version",
            "repository",
            "observed_at",
            "qualified_revision",
            "public_head_revision",
            "qualification_receipt",
            "signature_evidence",
            "digest_test_vectors",
            "inference_bearing_blobs",
            "public_head_delta",
            "authorization",
            "non_claims",
        },
        "fixture",
    )
    _require(
        fixture["schema_version"] == FIXTURE_SCHEMA_VERSION,
        "fixture schema version mismatch",
    )
    _require(fixture["repository"] == REPOSITORY, "repository mismatch")
    _require(
        fixture["qualified_revision"] == QUALIFIED_REVISION,
        "qualified revision mismatch",
    )
    _require(
        fixture["public_head_revision"] == PUBLIC_HEAD_REVISION,
        "public-head revision mismatch",
    )
    _require(
        qualification_receipt.get("schema_version")
        == "szl.receipt-agent-public-candidate-qualification-receipt.v1",
        "qualification receipt schema mismatch",
    )
    _require(
        receipt_digest(qualification_receipt)
        == qualification_receipt.get("receipt_sha256"),
        "qualification receipt self-digest mismatch",
    )
    _require(
        qualification_receipt.get("receipt_sha256")
        == fixture["qualification_receipt"]["receipt_sha256"],
        "fixture does not bind the qualification receipt",
    )
    _require(
        qualification_receipt.get("result") == "PASS"
        and qualification_receipt.get("maturity") == "MEASURED",
        "qualification is not a measured pass",
    )
    _require(
        qualification_receipt["candidate"]["repository"] == REPOSITORY
        and qualification_receipt["candidate"]["revision"] == QUALIFIED_REVISION,
        "qualification candidate identity mismatch",
    )

    signature_evidence = fixture["signature_evidence"]
    _strict_keys(
        signature_evidence,
        {"training", "evaluation", "trust_boundary"},
        "signature_evidence",
    )
    for kind in ("training", "evaluation"):
        frozen = signature_evidence[kind]
        receipt_value = qualification_receipt["candidate"][f"{kind}_receipt"]
        _require(frozen["verified"] is True, f"{kind} signature is not verified")
        _require(
            frozen["verified"] == receipt_value["verified"]
            and frozen["key_id"] == receipt_value["key_id"]
            and frozen["canonical_sha256"] == receipt_value["canonical_sha256"],
            f"{kind} signature evidence differs from the qualification receipt",
        )
    _require(
        signature_evidence["trust_boundary"]
        == "REPOSITORY_DECLARED_KEY_NOT_INDEPENDENTLY_PINNED",
        "signature trust boundary was overstated",
    )

    vectors = fixture["digest_test_vectors"]
    _require(len(vectors) == 2, "exactly two digest-domain vectors are required")
    for vector in vectors:
        _verify_digest_vector(vector)

    entries = fixture["inference_bearing_blobs"]
    _require(isinstance(entries, list), "inference-bearing blob inventory must be a list")
    paths = {entry["path"] for entry in entries}
    _require(paths == INFERENCE_BEARING_PATHS, "inference-bearing path set mismatch")
    _require(len(paths) == len(entries), "duplicate inference-bearing path")
    for entry in entries:
        _strict_keys(
            entry,
            {
                "path",
                "qualified_git_blob_sha1",
                "public_head_git_blob_sha1",
                "inference_bearing",
            },
            f"inference blob {entry.get('path')}",
        )
        _require(entry["inference_bearing"] is True, "inference path mislabeled")
        _require(
            _is_hex(entry["qualified_git_blob_sha1"], 40)
            and _is_hex(entry["public_head_git_blob_sha1"], 40),
            f"invalid Git blob identity: {entry['path']}",
        )
        _require(
            entry["qualified_git_blob_sha1"] == entry["public_head_git_blob_sha1"],
            f"inference-bearing public-head drift: {entry['path']}",
        )

    candidate = qualification_receipt["candidate"]
    fixture_binding = fixture["qualification_receipt"]["artifact_binding"]
    _strict_keys(
        fixture_binding,
        {"model_file", "adapter_file", "digest_domain"},
        "qualification_receipt.artifact_binding",
    )
    _require(
        fixture_binding["digest_domain"]
        == "SHA256_UTF8_BASENAME_CONCAT_RAW_FILE_BYTES",
        "artifact digest domain mismatch",
    )
    for key in ("model_file", "adapter_file"):
        frozen = fixture_binding[key]
        measured = candidate[key]
        _require(
            frozen["path"] == measured["path"]
            and frozen["bytes"] == measured["bytes"]
            and frozen["raw_sha256"] == measured["sha256"]
            and frozen["receipt_directory_sha256"]
            == measured["receipt_directory_sha256"],
            f"{key} differs from the measured qualification receipt",
        )
        _require(
            frozen["raw_sha256"] != frozen["receipt_directory_sha256"],
            f"{key} digest domains were collapsed",
        )

    delta = fixture["public_head_delta"]
    _require(
        delta
        == [
            {
                "path": "SZL_ESTATE_MANAGED.json",
                "change": "ADDED",
                "inference_bearing": False,
            }
        ],
        "public-head delta is not the frozen metadata-only change",
    )
    _require(
        fixture["authorization"]
        == {
            "trained": False,
            "uploaded": False,
            "promoted": False,
            "deployed": False,
        },
        "reconciliation cannot authorize training, upload, promotion, or deployment",
    )

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "state": RECONCILED_STATE,
        "maturity": "MEASURED",
        "observed_at": fixture["observed_at"],
        "repository": REPOSITORY,
        "qualified_revision": QUALIFIED_REVISION,
        "public_head_revision": PUBLIC_HEAD_REVISION,
        "receipt_signature_validity": {
            "training": True,
            "evaluation": True,
            "key_id": signature_evidence["training"]["key_id"],
            "trust_boundary": signature_evidence["trust_boundary"],
        },
        "exact_qualified_artifact_binding": {
            "verified": True,
            "qualification_receipt_sha256": qualification_receipt["receipt_sha256"],
            "model_raw_sha256": candidate["model_file"]["sha256"],
            "model_receipt_directory_sha256": candidate["model_file"][
                "receipt_directory_sha256"
            ],
            "adapter_raw_sha256": candidate["adapter_file"]["sha256"],
            "adapter_receipt_directory_sha256": candidate["adapter_file"][
                "receipt_directory_sha256"
            ],
            "digest_domain": fixture_binding["digest_domain"],
        },
        "current_public_head_equivalence": {
            "verified": True,
            "inference_bearing_blob_count": len(entries),
            "all_inference_bearing_git_blobs_equal": True,
            "non_inference_delta": delta,
        },
        "authorization": fixture["authorization"],
        "non_claims": fixture["non_claims"],
        "fixture_sha256": sha256_bytes(canonical_bytes(fixture)),
    }
    result["reconciliation_sha256"] = self_digest(result, "reconciliation_sha256")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--qualification-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()

    try:
        result = reconcile(load_json(args.fixture), load_json(args.qualification_receipt))
        if args.check:
            expected = load_json(args.check)
            _require(expected == result, "stored reconciliation artifact is stale")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ReconciliationRefusal) as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
