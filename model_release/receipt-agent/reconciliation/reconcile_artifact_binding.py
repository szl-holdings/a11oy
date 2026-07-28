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


def git_blob_sha1(value: bytes) -> str:
    header = b"blob " + str(len(value)).encode("ascii") + b"\0"
    return hashlib.sha1(header + value, usedforsecurity=False).hexdigest()


def git_object_sha1(kind: str, value: bytes) -> str:
    _require(kind in {"commit", "tree"}, "unsupported Git object kind")
    header = kind.encode("ascii") + b" " + str(len(value)).encode("ascii") + b"\0"
    return hashlib.sha1(header + value, usedforsecurity=False).hexdigest()


def lfs_pointer_git_blob_sha1(raw_sha256: str, size: int) -> str:
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{raw_sha256}\n"
        f"size {size}\n"
    ).encode("ascii")
    return git_blob_sha1(pointer)


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


def _verify_revision_git_evidence(
    evidence: dict[str, Any],
    *,
    label: str,
    expected_revision: str,
) -> dict[str, str]:
    _strict_keys(
        evidence,
        {"revision", "commit_object_base64", "trees"},
        f"{label}_git_evidence",
    )
    _require(evidence["revision"] == expected_revision, f"{label} evidence revision mismatch")
    commit_object = base64.b64decode(evidence["commit_object_base64"], validate=True)
    _require(
        git_object_sha1("commit", commit_object) == expected_revision,
        f"{label} commit object identity mismatch",
    )
    commit_lines = commit_object.splitlines()
    _require(
        commit_lines
        and commit_lines[0].startswith(b"tree ")
        and len(commit_lines[0]) == 45,
        f"{label} commit object lacks one root tree",
    )
    root_tree_sha1 = commit_lines[0][5:].decode("ascii")
    _require(_is_hex(root_tree_sha1, 40), f"{label} root tree identity is invalid")

    tree_records = evidence["trees"]
    _require(isinstance(tree_records, list), f"{label} tree evidence must be a list")
    trees_by_path: dict[str, dict[str, Any]] = {}
    for tree in tree_records:
        _strict_keys(tree, {"path", "tree_sha1", "entries"}, f"{label} tree")
        path = tree["path"]
        _require(
            isinstance(path, str)
            and (path == "" or (not path.startswith("/") and not path.endswith("/"))),
            f"{label} tree path is invalid",
        )
        _require(path not in trees_by_path, f"{label} duplicate tree path: {path}")
        _require(_is_hex(tree["tree_sha1"], 40), f"{label} tree identity is invalid: {path}")
        entries = tree["entries"]
        _require(isinstance(entries, list), f"{label} tree entries must be a list: {path}")
        names: set[str] = set()
        serialized = bytearray()
        for entry in entries:
            _strict_keys(
                entry,
                {"mode", "type", "object_sha1", "name"},
                f"{label} tree entry",
            )
            name = entry["name"]
            _require(
                isinstance(name, str)
                and name
                and "/" not in name
                and "\0" not in name,
                f"{label} tree entry name is invalid",
            )
            _require(name not in names, f"{label} duplicate tree entry: {path}/{name}")
            names.add(name)
            is_tree = entry["type"] == "tree"
            _require(
                (is_tree and entry["mode"] == "040000")
                or (entry["type"] == "blob" and entry["mode"] in {"100644", "100755"}),
                f"{label} tree entry mode/type mismatch: {path}/{name}",
            )
            _require(
                _is_hex(entry["object_sha1"], 40),
                f"{label} tree entry identity is invalid: {path}/{name}",
            )
            object_mode = "40000" if is_tree else entry["mode"]
            serialized.extend(object_mode.encode("ascii"))
            serialized.extend(b" ")
            serialized.extend(name.encode("utf-8"))
            serialized.extend(b"\0")
            serialized.extend(bytes.fromhex(entry["object_sha1"]))
        _require(
            git_object_sha1("tree", bytes(serialized)) == tree["tree_sha1"],
            f"{label} tree object identity mismatch: {path or '<root>'}",
        )
        trees_by_path[path] = tree

    root = trees_by_path.get("")
    _require(root is not None, f"{label} root tree evidence is missing")
    _require(
        root["tree_sha1"] == root_tree_sha1,
        f"{label} root tree does not bind to the commit object",
    )

    blobs: dict[str, str] = {}
    visited_trees: set[str] = set()

    def walk_tree(path: str, expected_tree_sha1: str) -> None:
        tree = trees_by_path.get(path)
        _require(tree is not None, f"{label} referenced tree evidence is missing: {path}")
        _require(
            tree["tree_sha1"] == expected_tree_sha1,
            f"{label} referenced tree identity mismatch: {path}",
        )
        visited_trees.add(path)
        for entry in tree["entries"]:
            child_path = f"{path}/{entry['name']}" if path else entry["name"]
            if entry["type"] == "tree":
                walk_tree(child_path, entry["object_sha1"])
            else:
                _require(child_path not in blobs, f"{label} duplicate blob path: {child_path}")
                blobs[child_path] = entry["object_sha1"]

    walk_tree("", root_tree_sha1)
    _require(
        visited_trees == set(trees_by_path),
        f"{label} tree evidence contains an unreachable tree",
    )
    return blobs


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
            "git_object_evidence",
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

    git_evidence = fixture["git_object_evidence"]
    _strict_keys(
        git_evidence,
        {"qualified", "public_head"},
        "git_object_evidence",
    )
    qualified_tree_blobs = _verify_revision_git_evidence(
        git_evidence["qualified"],
        label="qualified",
        expected_revision=QUALIFIED_REVISION,
    )
    public_head_tree_blobs = _verify_revision_git_evidence(
        git_evidence["public_head"],
        label="public-head",
        expected_revision=PUBLIC_HEAD_REVISION,
    )

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
        _require(
            qualified_tree_blobs.get(entry["path"])
            == entry["qualified_git_blob_sha1"],
            f"qualified path/blob is not bound to the declared revision: {entry['path']}",
        )
        _require(
            public_head_tree_blobs.get(entry["path"])
            == entry["public_head_git_blob_sha1"],
            f"public-head path/blob is not bound to the declared revision: {entry['path']}",
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
    entry_by_path = {entry["path"]: entry for entry in entries}
    lfs_pointer_blobs: dict[str, str] = {}
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
        _require(
            _is_hex(frozen["raw_sha256"], 64),
            f"{key} raw SHA-256 is invalid",
        )
        _require(
            isinstance(frozen["bytes"], int)
            and not isinstance(frozen["bytes"], bool)
            and frozen["bytes"] > 0,
            f"{key} byte count is invalid",
        )
        recorded_blob = entry_by_path.get(frozen["path"])
        _require(
            recorded_blob is not None,
            f"{key} is absent from the frozen Git tree",
        )
        pointer_blob = lfs_pointer_git_blob_sha1(
            frozen["raw_sha256"],
            frozen["bytes"],
        )
        _require(
            pointer_blob == recorded_blob["qualified_git_blob_sha1"],
            f"{key} raw artifact claim does not bind to the frozen LFS pointer",
        )
        lfs_pointer_blobs[key] = pointer_blob

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
        set(public_head_tree_blobs) - set(qualified_tree_blobs)
        == {"SZL_ESTATE_MANAGED.json"}
        and set(qualified_tree_blobs) - set(public_head_tree_blobs) == set()
        and all(
            qualified_tree_blobs[path] == public_head_tree_blobs[path]
            for path in qualified_tree_blobs
        ),
        "complete revision tree delta is not the frozen metadata-only addition",
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
            "model_lfs_pointer_git_blob_sha1": lfs_pointer_blobs["model_file"],
            "adapter_lfs_pointer_git_blob_sha1": lfs_pointer_blobs["adapter_file"],
            "digest_domain": fixture_binding["digest_domain"],
        },
        "current_public_head_equivalence": {
            "verified": True,
            "qualified_commit_git_object_verified": True,
            "public_head_commit_git_object_verified": True,
            "complete_revision_tree_delta_verified": True,
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
