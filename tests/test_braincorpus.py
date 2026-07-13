"""Focused contract tests for bounded Brain corpus admission."""

import hashlib
import json
from pathlib import Path

import szl_braincorpus as corpus

KERNEL = "1" * 40
LEAN = "2" * 40
MATHLIB = "3" * 40
TOOLCHAIN = {
    "kernel_commit": KERNEL,
    "lean_commit": LEAN,
    "mathlib_commit": MATHLIB,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt(artifact_sha: str, **overrides):
    body = {
        "schema_version": corpus.PROOF_RECEIPT_SCHEMA,
        "verified": True,
        "artifact_sha256": artifact_sha,
        "sorry_count": 0,
        **TOOLCHAIN,
    }
    body.update(overrides)
    return {**body, "receipt_sha256": corpus.sha256_json(body)}


def _artifact_receipt(artifact_sha: str, source_path: str, source_sha: str, **overrides):
    body = {
        "schema_version": corpus.ARTIFACT_RECEIPT_SCHEMA,
        "verified": True,
        "artifact_sha256": artifact_sha,
        "source_assets": [{
            "path": source_path, "sha256": source_sha, "license": "Apache-2.0",
        }],
        "proof_credit": 0,
    }
    body.update(overrides)
    return {**body, "receipt_sha256": corpus.sha256_json(body)}


def _manifest(source_type: str, entries, **overrides):
    body = {
        "schema_version": corpus.SCHEMA_VERSION,
        "source_type": source_type,
        "version": "test-v1",
        "toolchain": dict(TOOLCHAIN),
        "entries": list(entries),
    }
    body.update(overrides)
    return body


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _source(status, source_type: str):
    return next(row for row in status["sources"] if row["source_type"] == source_type)


def test_missing_canonical_sources_stay_source_unavailable(tmp_path):
    got = corpus.build_corpus_status(tmp_path, environ={})
    assert [row["status"] for row in got["sources"]] == [
        "SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE",
    ]
    assert got["summary"]["proof_credit"] == 0
    assert got["summary"]["missing_sources"] == 3
    assert got["summary"]["network_access"] is False
    assert got["summary"]["writes_performed"] == 0


def test_proved_requires_verified_bytes_and_exact_zero_sorry_receipt(tmp_path):
    artifact = b"theorem F7 : True := by trivial\n"
    artifact_path = tmp_path / "proofs" / "F7.lean"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(artifact)
    artifact_sha = _sha(artifact)
    manifest = _manifest("formula", [{
        "id": "F7",
        "evidence_class": "PROVED",
        "source_path": "proofs/F7.lean",
        "artifact_sha256": artifact_sha,
        "sorry_count": 0,
        "proof_receipt": _receipt(artifact_sha),
    }])
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], manifest)

    got = corpus.build_corpus_status(tmp_path, environ={})
    row = _source(got, "formula")["entries"][0]
    assert row["artifact_verified"] is True
    assert row["proof_receipt_valid"] is True
    assert row["effective_class"] == "PROVED"
    assert row["disposition"] == "ADMITTED_PROOF_EVIDENCE"
    assert row["proof_credit"] == 1
    assert got["summary"]["proof_credit"] == 1


def test_proved_declaration_without_exact_receipt_is_quarantined(tmp_path):
    artifact = b"theorem F4 : True := by trivial\n"
    (tmp_path / "proofs").mkdir()
    (tmp_path / "proofs" / "F4.lean").write_bytes(artifact)
    sha = _sha(artifact)
    short_commit_receipt = _receipt(sha, lean_commit="deadbeef")
    # Recompute after mutation so the digest itself is valid; the exact-commit rule still fails.
    short_commit_receipt["receipt_sha256"] = corpus.sha256_json({
        key: value for key, value in short_commit_receipt.items() if key != "receipt_sha256"
    })
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], _manifest("formula", [{
        "id": "F4", "evidence_class": "PROVED", "source_path": "proofs/F4.lean",
        "artifact_sha256": sha, "sorry_count": 0, "proof_receipt": short_commit_receipt,
    }]))
    row = _source(corpus.build_corpus_status(tmp_path, environ={}), "formula")["entries"][0]
    assert row["effective_class"] == "UNKNOWN"
    assert row["proof_credit"] == 0
    assert row["disposition"] == "QUARANTINED"
    assert "KERNEL_RECEIPT_INVALID_LEAN_COMMIT" in row["quarantine_reasons"]


def test_artifact_hash_mismatch_never_receives_proof_credit(tmp_path):
    artifact = b"actual bytes"
    (tmp_path / "proofs").mkdir()
    (tmp_path / "proofs" / "F1.lean").write_bytes(artifact)
    claimed = "a" * 64
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], _manifest("formula", [{
        "id": "F1", "evidence_class": "PROVED", "source_path": "proofs/F1.lean",
        "artifact_sha256": claimed, "sorry_count": 0,
        "proof_receipt": _receipt(claimed),
    }]))
    row = _source(corpus.build_corpus_status(tmp_path, environ={}), "formula")["entries"][0]
    assert row["artifact_verified"] is False
    assert row["proof_credit"] == 0
    assert "ARTIFACT_SHA256_MISMATCH" in row["quarantine_reasons"]


def test_nonproved_classes_are_content_verified_but_quarantined_from_trust(tmp_path):
    artifact = b"open conjecture"
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "F19.md").write_bytes(artifact)
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], _manifest("formula", [{
        "id": "F19", "evidence_class": "OPEN", "source_path": "notes/F19.md",
        "artifact_sha256": _sha(artifact),
    }]))
    row = _source(corpus.build_corpus_status(tmp_path, environ={}), "formula")["entries"][0]
    assert row["artifact_verified"] is True
    assert row["effective_class"] == "OPEN"
    assert row["disposition"] == "QUARANTINED_NON_PROOF"
    assert row["proof_credit"] == 0
    assert row["trust_uplift_eligible"] is False


def test_artifact_receipt_binds_local_licensed_assets_without_proof_uplift(tmp_path):
    artifact = b"grounded reranker examples"
    source = b"source bytes"
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "artifacts" / "rows.json").write_bytes(artifact)
    (tmp_path / "assets" / "source.txt").write_bytes(source)
    artifact_sha = _sha(artifact)
    receipt = _artifact_receipt(artifact_sha, "assets/source.txt", _sha(source))
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], _manifest("formula", [{
        "id": "formula-source-v1", "evidence_class": "EXPERIMENTAL",
        "source_path": "artifacts/rows.json", "artifact_sha256": artifact_sha,
        "artifact_receipt": receipt,
    }]))
    row = _source(corpus.build_corpus_status(tmp_path, environ={}), "formula")["entries"][0]
    assert row["artifact_verified"] is True
    assert row["artifact_receipt_valid"] is True
    assert row["artifact_receipt"]["source_asset_count"] == 1
    assert row["artifact_receipt"]["proof_credit"] == 0
    assert row["proof_credit"] == 0
    assert row["disposition"] == "QUARANTINED_NON_PROOF"


def test_tampered_artifact_receipt_is_quarantined(tmp_path):
    artifact = b"grounded reranker examples"
    source = b"source bytes"
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "artifacts" / "rows.json").write_bytes(artifact)
    (tmp_path / "assets" / "source.txt").write_bytes(source)
    artifact_sha = _sha(artifact)
    receipt = _artifact_receipt(artifact_sha, "assets/source.txt", "0" * 64)
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], _manifest("formula", [{
        "id": "formula-source-v1", "evidence_class": "EXPERIMENTAL",
        "source_path": "artifacts/rows.json", "artifact_sha256": artifact_sha,
        "artifact_receipt": receipt,
    }]))
    row = _source(corpus.build_corpus_status(tmp_path, environ={}), "formula")["entries"][0]
    assert row["artifact_receipt_valid"] is False
    assert row["effective_class"] == "UNKNOWN"
    assert "ARTIFACT_RECEIPT_ASSET_SHA_MISMATCH:0" in row["quarantine_reasons"]


def test_conflicting_formula_ids_are_quarantined_across_sources(tmp_path):
    a = b"formula variant a"
    b = b"formula variant b"
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "F12-a.txt").write_bytes(a)
    (tmp_path / "artifacts" / "F12-b.txt").write_bytes(b)
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["formula"], _manifest("formula", [{
        "id": "F12", "evidence_class": "EXPERIMENTAL",
        "source_path": "artifacts/F12-a.txt", "artifact_sha256": _sha(a),
    }]))
    _write_json(tmp_path / corpus.DEFAULT_MANIFESTS["lean_mathlib"], _manifest("lean_mathlib", [{
        "id": "f12", "evidence_class": "OPEN",
        "source_path": "artifacts/F12-b.txt", "artifact_sha256": _sha(b),
    }]))
    got = corpus.build_corpus_status(tmp_path, environ={})
    assert got["formula_id_conflicts"] == [{
        "formula_id": "F12", "reason": "F_ID_CONFLICT", "variants": 2,
        "sources": ["formula", "lean_mathlib"],
    }]
    rows = [entry for source in got["sources"] for entry in source["entries"]]
    assert all(row["disposition"] == "QUARANTINED" for row in rows)
    assert all(row["effective_class"] == "UNKNOWN" for row in rows)
    assert got["summary"]["proof_credit"] == 0


def test_explicit_manifest_is_bounded_to_its_directory(tmp_path):
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    external.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    manifest_path = external / "formula.json"
    _write_json(manifest_path, _manifest("formula", [{
        "id": "F22", "evidence_class": "OPEN", "source_path": "../outside.txt",
        "artifact_sha256": _sha(b"outside"),
    }]))
    got = corpus.build_corpus_status(repo, environ={
        corpus.MANIFEST_ENV["formula"]: str(manifest_path),
    })
    source = _source(got, "formula")
    assert source["manifest_path"] == "<explicit-config>/formula.json"
    row = source["entries"][0]
    assert row["artifact_verified"] is False
    assert "ARTIFACT_PATH_ESCAPES_BOUNDARY" in row["quarantine_reasons"]
    assert row["proof_credit"] == 0


def test_legacy_manifest_is_not_silently_translated(tmp_path):
    path = tmp_path / corpus.DEFAULT_MANIFESTS["lean_mathlib"]
    _write_json(path, {"generated": "2026-05-28", "files": []})
    source = _source(corpus.build_corpus_status(tmp_path, environ={}), "lean_mathlib")
    assert source["status"] == "MANIFEST_QUARANTINED"
    assert source["errors"] == ["SCHEMA_VERSION_MISMATCH"]
    assert source["proof_credit"] == 0


def test_static_info_declares_zero_effectors():
    got = corpus.info()
    assert got["schema_version"] == corpus.SCHEMA_VERSION
    assert got["effectors"] == 0
    assert got["network_access"] is False
    assert got["gpu_training"] is False
    assert got["request_selected_paths"] is False
