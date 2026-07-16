from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_brain_row_evidence_assembler as assembler
from szl_brain_row_evidence_assembler import (
    AssemblyRefused,
    EVIDENCE_ROW_SCHEMA,
    INDEX_SCHEMA,
    PAYLOAD_TYPE,
    assemble,
)


KEYID = "test-brain-evidence-review-root"
HASH = "1" * 64


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def pae(payload_type: str, payload: bytes) -> bytes:
    encoded_type = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(encoded_type)).encode()
        + b" "
        + encoded_type
        + b" "
        + str(len(payload)).encode()
        + b" "
        + payload
    )


def ledger_row(node_id: str, content: str) -> dict:
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    return {
        "schema": "szl.m1-brain-ingest-decision/v1",
        "node_id": node_id,
        "canonical_text": content,
        "canonical_text_sha256": content_sha,
        "training_decision": "QUARANTINE",
        "training_eligible": False,
    }


def evidence_descriptor(name: str) -> dict:
    return {"path": f"evidence/{name}.json", "sha256": HASH}


def evidence_row(node_id: str, content_sha256: str) -> dict:
    return {
        "schema_version": EVIDENCE_ROW_SCHEMA,
        "node_id": node_id,
        "content_sha256": content_sha256,
        "source": {
            "identity": "source:example",
            "uri": "https://example.invalid/source",
            "revision": f"sha256:{'2' * 64}",
            "timestamp_utc": "2026-07-16T12:00:00Z",
            "evidence": evidence_descriptor("source"),
        },
        "rights": {
            "author": "author:verified-example",
            "rightsholder": "rightsholder:verified-example",
            "basis": "explicit-license-evidence",
            "license": "Apache-2.0",
            "permission_scope": "MODEL_TRAINING_AND_DISTRIBUTION",
            "evidence": evidence_descriptor("rights"),
        },
        "privacy": {
            "classification": "PUBLIC_NON_PERSONAL",
            "pii_result": "CLEAR",
            "method": "signed-human-and-tool-review",
            "evidence": evidence_descriptor("privacy"),
        },
        "contamination": {
            "result": "CLEAR",
            "method": "exact-and-near-duplicate-check",
            "checked_against": ["heldout:v1"],
            "evidence": evidence_descriptor("contamination"),
        },
        "review": {
            "state": "APPROVED",
            "reviewer": "reviewer:test-authority",
            "reviewed_at_utc": "2026-07-16T12:01:00Z",
            "reasons": ["evidence-complete"],
            "evidence": evidence_descriptor("review"),
        },
        "split": "TRAIN",
    }


def write_ledger(path: Path, rows: list[dict]) -> str:
    body = b"".join(canonical_bytes(row) + b"\n" for row in rows)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def write_keypair(tmp_path: Path):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_path = tmp_path / "review-root.pub.pem"
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_key, public_path


def write_signed_index(
    path: Path,
    private_key,
    ledger_sha256: str,
    rows: list[dict],
    *,
    mutate_payload_after_signing=None,
) -> None:
    payload = {
        "schema_version": INDEX_SCHEMA,
        "source_ledger_sha256": ledger_sha256,
        "generated_at_utc": "2026-07-16T12:02:00Z",
        "rows": rows,
    }
    payload_bytes = canonical_bytes(payload)
    signature = private_key.sign(
        pae(PAYLOAD_TYPE, payload_bytes), ec.ECDSA(hashes.SHA256())
    )
    if mutate_payload_after_signing is not None:
        mutate_payload_after_signing(payload)
        payload_bytes = canonical_bytes(payload)
    envelope = {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload_bytes).decode(),
        "signatures": [{"keyid": KEYID, "sig": base64.b64encode(signature).decode()}],
    }
    path.write_bytes(canonical_bytes(envelope) + b"\n")


def prepare(tmp_path: Path, evidence_rows: list[dict] | None = None):
    ledger_rows = [ledger_row("node:a", "alpha"), ledger_row("node:b", "beta")]
    ledger_path = tmp_path / "brain-ingest-ledger.jsonl"
    ledger_sha = write_ledger(ledger_path, ledger_rows)
    private_key, public_path = write_keypair(tmp_path)
    index_path = tmp_path / "row-evidence.dsse.json"
    if evidence_rows is None:
        evidence_rows = [
            evidence_row("node:a", ledger_rows[0]["canonical_text_sha256"])
        ]
    write_signed_index(index_path, private_key, ledger_sha, evidence_rows)
    return ledger_rows, ledger_path, ledger_sha, private_key, public_path, index_path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_assembles_only_signed_exact_matches_and_emits_content_free_gap(tmp_path: Path):
    rows, ledger, ledger_sha, _, public_key, index = prepare(tmp_path)
    output = tmp_path / "out"

    manifest = assemble(
        ledger, index, public_key, KEYID, output, expected_rows=2
    )

    candidates = read_jsonl(output / "brain-training-candidate.v2.jsonl")
    gaps = read_jsonl(output / "brain-row-evidence-gap-queue.v1.jsonl")
    assert len(candidates) == 1
    assert candidates[0]["node_id"] == "node:a"
    assert candidates[0]["content"] == "alpha"
    assert candidates[0]["content_sha256"] == rows[0]["canonical_text_sha256"]
    assert candidates[0]["rights"]["author"] == "author:verified-example"
    assert len(gaps) == 1
    assert gaps[0] == {
        "schema_version": "szl.brain-row-evidence-gap.v1",
        "row_key_sha256": hashlib.sha256(
            b"szl.brain-row-evidence-key.v1\0"
            + canonical_bytes(
                {
                    "node_id": "node:b",
                    "content_sha256": rows[1]["canonical_text_sha256"],
                }
            )
        ).hexdigest(),
        "missing_evidence": ["SIGNED_ROW_EVIDENCE"],
    }
    assert "content" not in gaps[0]
    assert "node:b" not in json.dumps(gaps[0])
    assert rows[1]["canonical_text_sha256"] not in json.dumps(gaps[0])
    assert "canonical_text" not in json.dumps(gaps[0])
    assert manifest["source_ledger"]["sha256"] == ledger_sha
    assert manifest["signed_evidence_index"]["signature_verified"] is True
    assert manifest["coverage"] == {
        "signed_evidence_rows": 1,
        "candidate_rows": 1,
        "gap_rows": 1,
        "complete_partition": True,
    }
    assert manifest["outputs"]["candidate"]["state"] == "UNADMITTED_CANDIDATES"


def test_refuses_duplicate_signed_evidence_keys(tmp_path: Path):
    rows, ledger, ledger_sha, private_key, public_key, index = prepare(tmp_path)
    duplicate = evidence_row("node:a", rows[0]["canonical_text_sha256"])
    write_signed_index(index, private_key, ledger_sha, [duplicate, duplicate])

    with pytest.raises(AssemblyRefused, match="duplicate row key"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_refuses_node_hash_mismatch_in_signed_evidence(tmp_path: Path):
    rows, ledger, ledger_sha, private_key, public_key, index = prepare(tmp_path)
    mismatched = evidence_row("node:a", rows[1]["canonical_text_sha256"])
    write_signed_index(index, private_key, ledger_sha, [mismatched])

    with pytest.raises(AssemblyRefused, match="content hash mismatches"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_refuses_unknown_signed_evidence_key(tmp_path: Path):
    _, ledger, ledger_sha, private_key, public_key, index = prepare(tmp_path)
    unknown = evidence_row("node:unknown", hashlib.sha256(b"unknown").hexdigest())
    write_signed_index(index, private_key, ledger_sha, [unknown])

    with pytest.raises(AssemblyRefused, match="absent from the M1 ledger"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_refuses_tampered_signed_payload(tmp_path: Path):
    rows, ledger, ledger_sha, private_key, public_key, index = prepare(tmp_path)
    signed_row = evidence_row("node:a", rows[0]["canonical_text_sha256"])
    write_signed_index(
        index,
        private_key,
        ledger_sha,
        [signed_row],
        mutate_payload_after_signing=lambda payload: payload["rows"][0]["review"].update(
            {"reviewer": "reviewer:attacker"}
        ),
    )

    with pytest.raises(AssemblyRefused, match="signature did not verify"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_refuses_missing_rights_without_inference(tmp_path: Path):
    rows, ledger, ledger_sha, private_key, public_key, index = prepare(tmp_path)
    incomplete = evidence_row("node:a", rows[0]["canonical_text_sha256"])
    del incomplete["rights"]["author"]
    write_signed_index(index, private_key, ledger_sha, [incomplete])
    output = tmp_path / "out"

    with pytest.raises(AssemblyRefused, match="rights fields are not exact"):
        assemble(ledger, index, public_key, KEYID, output, expected_rows=2)
    assert not output.exists()


def test_refuses_index_bound_to_another_ledger(tmp_path: Path):
    _, ledger, _, private_key, public_key, index = prepare(tmp_path)
    write_signed_index(index, private_key, "f" * 64, [])

    with pytest.raises(AssemblyRefused, match="different M1 ledger"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_refuses_corrupt_ledger_content_hash(tmp_path: Path):
    rows, ledger, _, private_key, public_key, index = prepare(tmp_path)
    rows[0]["canonical_text"] = "changed-after-hash"
    ledger_sha = write_ledger(ledger, rows)
    write_signed_index(index, private_key, ledger_sha, [])

    with pytest.raises(AssemblyRefused, match="content hash mismatch"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_refuses_duplicate_m1_node_key(tmp_path: Path):
    duplicate = ledger_row("node:a", "alpha")
    ledger = tmp_path / "brain-ingest-ledger.jsonl"
    ledger_sha = write_ledger(ledger, [duplicate, duplicate])
    private_key, public_key = write_keypair(tmp_path)
    index = tmp_path / "row-evidence.dsse.json"
    write_signed_index(index, private_key, ledger_sha, [])

    with pytest.raises(AssemblyRefused, match="duplicates a row key"):
        assemble(ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2)


def test_receipt_hash_binds_verified_index_bytes_if_path_is_replaced(
    tmp_path: Path, monkeypatch
):
    _, ledger, _, _, public_key, index = prepare(tmp_path)
    verified_bytes = index.read_bytes()
    original_reader = assembler._read_stable_regular_file

    def replace_after_read(path, max_bytes, label):
        data = original_reader(path, max_bytes, label)
        if label == "signed evidence index":
            path.write_bytes(b'{"replaced":true}\n')
        return data

    monkeypatch.setattr(assembler, "_read_stable_regular_file", replace_after_read)
    manifest = assemble(
        ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2
    )

    assert manifest["signed_evidence_index"]["index_file_sha256"] == hashlib.sha256(
        verified_bytes
    ).hexdigest()
    assert manifest["signed_evidence_index"]["index_file_sha256"] != hashlib.sha256(
        index.read_bytes()
    ).hexdigest()


def test_key_fingerprint_binds_verified_pem_bytes_if_path_is_replaced(
    tmp_path: Path, monkeypatch
):
    _, ledger, _, _, public_key, index = prepare(tmp_path)
    verified_pem = public_key.read_bytes()
    replacement = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    original_reader = assembler._read_stable_regular_file

    def replace_after_read(path, max_bytes, label):
        data = original_reader(path, max_bytes, label)
        if label == "evidence public key":
            path.write_bytes(replacement)
        return data

    monkeypatch.setattr(assembler, "_read_stable_regular_file", replace_after_read)
    manifest = assemble(
        ledger, index, public_key, KEYID, tmp_path / "out", expected_rows=2
    )

    assert manifest["signed_evidence_index"][
        "public_key_file_sha256"
    ] == hashlib.sha256(verified_pem).hexdigest()
    assert manifest["signed_evidence_index"][
        "public_key_file_sha256"
    ] != hashlib.sha256(public_key.read_bytes()).hexdigest()


def test_real_m1_ledger_keeps_all_9464_rows_in_content_free_gaps_without_evidence(
    tmp_path: Path,
):
    ledger = (
        Path(__file__).resolve().parents[1]
        / "model_release"
        / "m1"
        / "brain-ingest-ledger.jsonl"
    )
    ledger_sha = hashlib.sha256(ledger.read_bytes()).hexdigest()
    private_key, public_key = write_keypair(tmp_path)
    index = tmp_path / "empty-row-evidence.dsse.json"
    write_signed_index(index, private_key, ledger_sha, [])
    output = tmp_path / "real-m1-out"

    manifest = assemble(ledger, index, public_key, KEYID, output)

    assert (output / "brain-training-candidate.v2.jsonl").read_bytes() == b""
    gap_bytes = (output / "brain-row-evidence-gap-queue.v1.jsonl").read_bytes()
    assert gap_bytes.count(b"\n") == 9_464
    assert b"canonical_text" not in gap_bytes
    assert manifest["coverage"] == {
        "signed_evidence_rows": 0,
        "candidate_rows": 0,
        "gap_rows": 9_464,
        "complete_partition": True,
    }
