# SPDX-License-Identifier: Apache-2.0
"""Fail-closed tests for the One Lathe Sigstore receipt boundary."""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SIGNER = ROOT / "scripts" / "sign_lathe_snapshot.py"
VERIFIER = ROOT / "scripts" / "verify_lathe_snapshot_receipt.py"
SNAPSHOT = ROOT / "artifacts" / "lathe" / "program-snapshot.v1.json"
REPOSITORY = "szl-holdings/a11oy"
REVISION = "1" * 40
IDENTITY = (
    "https://github.com/szl-holdings/a11oy/.github/workflows/"
    "one-lathe-receipt.yml@refs/heads/main"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


signer = _load_module("sign_lathe_snapshot", SIGNER)
verifier = _load_module("verify_lathe_snapshot_receipt", VERIFIER)


def _statement(snapshot: dict) -> dict:
    subject = signer.receipt_subject(
        snapshot,
        repository=REPOSITORY,
        source_revision=REVISION,
        workflow_identity=IDENTITY,
    )
    payload = signer.lathe.canonical_json_bytes(subject)
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": signer.SUBJECT_NAME,
                "digest": {"sha256": hashlib.sha256(payload).hexdigest()},
            }
        ],
        "predicateType": "https://szl-holdings.dev/attestations/governance-receipt/v1",
        "predicate": {
            "dsse_payload_type": signer.PAYLOAD_TYPE,
            "payload_b64": base64.b64encode(payload).decode("ascii"),
        },
    }


def _envelope(snapshot: dict) -> dict:
    statement_payload = base64.b64encode(
        json.dumps(_statement(snapshot), sort_keys=True, separators=(",", ":")).encode()
    ).decode("ascii")
    dsse = {
        "payloadType": "application/vnd.in-toto+json",
        "payload": statement_payload,
        "signatures": [{"keyid": "", "sig": "test-only-non-cryptographic"}],
    }
    return {
        **dsse,
        "_mode": "SIGSTORE-KEYLESS",
        "_sigstore": {"bundle": {"dsseEnvelope": copy.deepcopy(dsse)}},
    }


def test_committed_snapshot_is_a_valid_non_promoted_signing_subject() -> None:
    snapshot = signer.load_validated_snapshot(SNAPSHOT)
    assert snapshot["promotionEligible"] is False
    assert snapshot["receiptBinding"]["state"] != "BOUND"
    assert signer.receipt_subject(
        snapshot,
        repository=REPOSITORY,
        source_revision=REVISION,
        workflow_identity=IDENTITY,
    )


def test_subject_comparison_is_exact() -> None:
    snapshot = signer.load_validated_snapshot(SNAPSHOT)
    envelope = _envelope(snapshot)
    verifier.verify_subject(
        envelope,
        snapshot,
        repository=REPOSITORY,
        source_revision=REVISION,
        workflow_identity=IDENTITY,
    )

    tampered = copy.deepcopy(snapshot)
    tampered["risks"] = ["tampered"]
    try:
        verifier.verify_subject(
            envelope,
            tampered,
            repository=REPOSITORY,
            source_revision=REVISION,
            workflow_identity=IDENTITY,
        )
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("tampered snapshot unexpectedly matched the signed subject")


def test_outer_bundle_splice_is_rejected() -> None:
    snapshot = signer.load_validated_snapshot(SNAPSHOT)
    envelope = _envelope(snapshot)
    envelope["payload"] = base64.b64encode(b'{"attacker":true}').decode("ascii")
    try:
        verifier.verify_subject(
            envelope,
            snapshot,
            repository=REPOSITORY,
            source_revision=REVISION,
            workflow_identity=IDENTITY,
        )
    except ValueError as exc:
        assert "does not match the verified Sigstore bundle" in str(exc)
    else:
        raise AssertionError("outer/bundle splice unexpectedly passed")


def test_statement_semantics_are_pinned() -> None:
    snapshot = signer.load_validated_snapshot(SNAPSHOT)
    for mutation, message in (
        (("payloadType", "application/json"), "not in-toto JSON"),
        (("_type", "https://example.invalid/Statement/v1"), "wrong in-toto type"),
        (("predicateType", "https://example.invalid/predicate"), "wrong predicate type"),
    ):
        envelope = _envelope(snapshot)
        field, value = mutation
        if field == "payloadType":
            envelope["payloadType"] = value
            envelope["_sigstore"]["bundle"]["dsseEnvelope"]["payloadType"] = value
        else:
            statement = _statement(snapshot)
            statement[field] = value
            encoded = base64.b64encode(
                json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
            ).decode("ascii")
            envelope["payload"] = encoded
            envelope["_sigstore"]["bundle"]["dsseEnvelope"]["payload"] = encoded
        try:
            verifier.verify_subject(
                envelope,
                snapshot,
                repository=REPOSITORY,
                source_revision=REVISION,
                workflow_identity=IDENTITY,
            )
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"semantic mutation {field} unexpectedly passed")


def test_receipt_loader_refuses_oversized_and_symlink_inputs(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.dsse.json"
    oversized.write_bytes(b"{" + b" " * verifier.MAX_RECEIPT_BYTES + b"}")
    try:
        verifier.load_receipt_envelope(oversized)
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("oversized receipt unexpectedly loaded")

    target = tmp_path / "target.dsse.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.dsse.json"
    try:
        link.symlink_to(target)
    except OSError:
        return
    try:
        verifier.load_receipt_envelope(link)
    except ValueError as exc:
        assert "symbolic link" in str(exc)
    else:
        raise AssertionError("symlink receipt unexpectedly loaded")


def test_receipt_subject_rejects_unpinned_identity_and_bad_revision() -> None:
    snapshot = signer.load_validated_snapshot(SNAPSHOT)
    for revision, identity in (
        ("short", IDENTITY),
        (REVISION, IDENTITY.replace("refs/heads/main", "refs/heads/feature")),
    ):
        try:
            signer.receipt_subject(
                snapshot,
                repository=REPOSITORY,
                source_revision=revision,
                workflow_identity=identity,
            )
        except signer.LatheSigningError:
            pass
        else:
            raise AssertionError("unpinned receipt provenance unexpectedly passed")


def test_signer_refuses_without_real_oidc_and_emits_no_receipt(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SIGNER),
            "--snapshot",
            str(SNAPSHOT),
            "--out-dir",
            str(tmp_path),
            "--repository",
            REPOSITORY,
            "--source-revision",
            REVISION,
            "--workflow-identity",
            IDENTITY,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert not list(tmp_path.iterdir())


def test_verifier_refuses_placeholder_without_soft_pass(tmp_path: Path) -> None:
    placeholder = tmp_path / "placeholder.dsse.json"
    placeholder.write_text(
        json.dumps(
            {
                "payloadType": signer.PAYLOAD_TYPE,
                "payload": "e30=",
                "signatures": [],
                "_mode": "PLACEHOLDER",
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            str(placeholder),
            "--snapshot",
            str(SNAPSHOT),
            "--identity",
            IDENTITY,
            "--repository",
            REPOSITORY,
            "--source-revision",
            REVISION,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "not a real Sigstore keyless envelope" in result.stderr
