#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the three default Brain reranker evidence packages from local bytes.

The output is deterministic and network-free.  It does not train, evaluate, scrape,
or award proof credit.  Every example is an exact projection of one current Brain
node and every source receipt binds the generated artifact to licensed repository
bytes.  ``--check`` verifies that committed outputs still match the current inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import types
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_read_only_fastapi_stub() -> None:
    """Permit graph projection in the minimal bundled build Python."""
    try:
        __import__("fastapi")
        return
    except ModuleNotFoundError:
        pass
    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = type("FastAPI", (), {})
    responses = types.ModuleType("fastapi.responses")
    response = type("Response", (), {"__init__": lambda self, *args, **kwargs: None})
    responses.JSONResponse = response
    responses.HTMLResponse = response
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


_install_read_only_fastapi_stub()
import szl_brain_reranker as rr  # noqa: E402
import szl_braincorpus as corpus  # noqa: E402


SOURCE_SPECS = {
    "szl_lake": {
        "entry_id": "brain-reranker-szl-lake-v1",
        "artifact": pathlib.Path("data/szl-lake/reranker-evidence.json"),
        "receipt": pathlib.Path("data/szl-lake/reranker-evidence.receipt.json"),
        "manifest": corpus.DEFAULT_MANIFESTS["szl_lake"],
        "assets": (
            "LICENSE",
            "szl_lake_store.py",
            "szl_lake_ingest.py",
            "brain/vault/repos/repo-szl-lake.md",
        ),
        "examples": (
            ("lake-repo-positive", "positive", "entity-szl_lake-0", "repo:szl-lake",
             "Which local Brain repository is identified by this evidence?"),
            ("lake-no-training-claim", "negative", "entity-szl_lake-10", "repo:szl-lake",
             "Does this repository-level evidence establish a completed GPU training run?"),
        ),
    },
    "lean_mathlib": {
        "entry_id": "brain-reranker-lean-mathlib-v1",
        "artifact": pathlib.Path("docs/thesis/v18/lean-reranker-evidence.json"),
        "receipt": pathlib.Path("docs/thesis/v18/lean-reranker-evidence.receipt.json"),
        "manifest": corpus.DEFAULT_MANIFESTS["lean_mathlib"],
        "assets": (
            "proofs/lutar-lean/LICENSE",
            "proofs/lutar-lean/lean-toolchain",
            "proofs/lutar-lean/lake-manifest.json",
            "proofs/lutar-lean/Lutar/Puriq/Formulas/ProvedFormulas.lean",
        ),
        "examples": (
            ("lean-repo-positive", "positive", "entity-lean_mathlib-11", "repo:lutar-lean",
             "Which local Lean repository is identified by this Brain evidence?"),
            ("lean-kernel-abstention", "abstention", "entity-lean_mathlib-0", "repo:lutar-lean",
             "Can this repository-level projection prove that every theorem compiled with zero sorry?"),
        ),
    },
    "formula": {
        "entry_id": "brain-reranker-formula-v1",
        "artifact": pathlib.Path("corpus/formulas/reranker-evidence.json"),
        "receipt": pathlib.Path("corpus/formulas/reranker-evidence.receipt.json"),
        "manifest": corpus.DEFAULT_MANIFESTS["formula"],
        "assets": (
            "LICENSE",
            "corpus/formulas/a11oy__szl_puriq_formulas.py",
            "corpus/formulas/lutar-lean__Lutar__Puriq__Formulas__ProvedFormulas.lean",
            "corpus/formulas/lutar-lean__PROVEN_FORMULAS.md",
        ),
        "examples": (
            ("formula-f1-reported-status", "positive", "entity-formula-0", "formula:F1",
             "What proof status does the current Brain projection report for formula F1?"),
            ("formula-f10-not-proved", "negative", "entity-formula-8", "formula:F10",
             "Does this evidence establish formula F10 as proved?"),
            ("formula-f23-abstain", "abstention", "entity-formula-5", "formula:F23",
             "Can this evidence justify promoting formula F23 from Conjecture 1 to a theorem?"),
            ("formula-f23-refute-claim", "refutation", "entity-formula-4", "formula:F23",
             "Does this evidence support the claim that formula F23 has been refuted?"),
        ),
    },
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _file_bytes(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _asset(path_value: str) -> dict[str, Any]:
    path = (ROOT / path_value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"asset escapes repository: {path_value}") from exc
    if not path.is_file():
        raise RuntimeError(f"required local asset missing: {path_value}")
    raw = path.read_bytes()
    return {
        "path": path_value,
        "sha256": _sha_bytes(raw),
        "license": "Apache-2.0",
        "bytes": len(raw),
    }


def _example(docs: dict[str, dict[str, str]], spec: tuple[str, str, str, str, str]) -> dict[str, Any]:
    example_id, example_type, entity_id, node_id, query = spec
    doc = docs.get(node_id)
    if not doc:
        raise RuntimeError(f"required Brain projection missing: {node_id}")
    if node_id.startswith("person:"):
        raise RuntimeError(f"person nodes are forbidden: {node_id}")
    if node_id == "formula:F1" and "Proof status: PROVED" not in doc["text"]:
        raise RuntimeError("F1 reported status changed; human review required")
    if node_id == "formula:F10" and "Proof status: UNATTEMPTED" not in doc["text"]:
        raise RuntimeError("F10 reported status changed; human review required")
    if node_id == "formula:F23" and "Proof status: CONJECTURE_1" not in doc["text"]:
        raise RuntimeError("F23 reported status changed; human review required")
    return {
        "example_id": example_id,
        "example_type": example_type,
        "target_relevance": rr.TARGETS[example_type],
        "query": query,
        "evidence_text": doc["text"],
        "entity_id": entity_id,
        "brain_node_id": doc["id"],
        "brain_node_sha256": rr._sha({
            "id": doc["id"], "text": doc["text"], "source": doc["source"],
        }),
        "brain_source_sha256": rr._sha_text(doc["source"]),
    }


def _with_content_hash(value: dict[str, Any]) -> dict[str, Any]:
    return {**value, "content_sha256": corpus.sha256_json(value)}


def build_outputs() -> dict[pathlib.Path, bytes]:
    docs, error = rr._brain_docs("a11oy")
    if error or not docs:
        raise RuntimeError(f"Brain projection unavailable: {error or 'EMPTY'}")
    outputs: dict[pathlib.Path, bytes] = {}
    for source_type, spec in SOURCE_SPECS.items():
        assets = [_asset(path) for path in spec["assets"]]
        artifact = _with_content_hash({
            "schema_version": rr.SOURCE_SCHEMA,
            "source_type": source_type,
            "evidence_class": "EXPERIMENTAL",
            "proof_credit": 0,
            "training_triggered": False,
            "network_used": False,
            "source_assets": assets,
            "examples": [_example(docs, row) for row in spec["examples"]],
        })
        artifact_bytes = _file_bytes(artifact)
        artifact_sha = _sha_bytes(artifact_bytes)
        receipt_body = {
            "schema_version": corpus.ARTIFACT_RECEIPT_SCHEMA,
            "verified": True,
            "artifact_sha256": artifact_sha,
            "source_assets": assets,
            "proof_credit": 0,
            "proof_status": "NOT_EVALUATED",
            "training_triggered": False,
            "network_used": False,
        }
        receipt = {**receipt_body, "receipt_sha256": corpus.sha256_json(receipt_body)}
        manifest = _with_content_hash({
            "schema_version": corpus.SCHEMA_VERSION,
            "source_type": source_type,
            "version": "brain-reranker-defaults-v1",
            "entries": [{
                "id": spec["entry_id"],
                "evidence_class": "EXPERIMENTAL",
                "source_path": spec["artifact"].as_posix(),
                "artifact_sha256": artifact_sha,
                "artifact_receipt": receipt,
                "sorry_count": 0,
            }],
        })
        outputs[spec["artifact"]] = artifact_bytes
        outputs[spec["receipt"]] = _file_bytes(receipt)
        outputs[spec["manifest"]] = _file_bytes(manifest)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="verify committed outputs without writing")
    args = parser.parse_args()
    outputs = build_outputs()
    mismatches: list[str] = []
    for relative, expected in outputs.items():
        path = ROOT / relative
        if args.check:
            if not path.is_file() or path.read_bytes() != expected:
                mismatches.append(relative.as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
    if mismatches:
        print("stale or missing: " + ", ".join(sorted(mismatches)), file=sys.stderr)
        return 1
    action = "verified" if args.check else "wrote"
    print(f"{action} {len(outputs)} deterministic local evidence files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
