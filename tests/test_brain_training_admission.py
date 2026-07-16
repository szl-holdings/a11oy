"""Fail-closed Brain training-admission regression tests."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

import szl_brain_training_admission as admission


_PRIVATE_KEYS: dict[tuple[str, str], Ed25519PrivateKey] = {}
TRUSTED_KEY_ID = "test-release-authority-ed25519-2026"
TRUSTED_ISSUER = "did:web:test.szlh.example:release-authority"
TRUSTED_TOOL = "szl-test-evidence-issuer/1.0.0"
TRUSTED_REVIEWER = "reviewer:szl:test"
REVIEW_KEY_ID = "test-reviewer-ed25519-2026"
POLICY_ROOT_KEY_ID = "test-policy-root-ed25519-2026"
ARTIFACT_KEY_ID = "test-artifact-signer-ed25519-2026"
TEST_AUTHOR = "author:szl:test"
TEST_RIGHTSHOLDER = "rightsholder:szl:test"
EVIDENCE_PURPOSES = (
    admission.PURPOSE_CONTAMINATION,
    admission.PURPOSE_PRIVACY,
    admission.PURPOSE_RIGHTS,
    admission.PURPOSE_SOURCE,
    admission.PURPOSE_SPLIT_LEDGER,
)


def _canonical_file(path: Path, value: object) -> dict[str, str]:
    content = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    path.write_bytes(content)
    return {
        "path": path.name,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _ensure_signer(
    root: Path,
    *,
    key_id: str = TRUSTED_KEY_ID,
    issuer: str = TRUSTED_ISSUER,
    tool_identity: str = TRUSTED_TOOL,
    purposes: tuple[str, ...] = EVIDENCE_PURPOSES,
    subject_id: str | None = None,
) -> tuple[Ed25519PrivateKey, admission.TrustedEvidenceSigner]:
    cache_key = (str(root.resolve()), key_id)
    private_key = _PRIVATE_KEYS.get(cache_key)
    if private_key is None:
        private_key = Ed25519PrivateKey.generate()
        _PRIVATE_KEYS[cache_key] = private_key
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_path = root / f"{key_id}.pem"
    key_path.write_bytes(public_bytes)
    signer = admission.TrustedEvidenceSigner(
        key_id=key_id,
        issuer=issuer,
        tool_identity=tool_identity,
        public_key_path=key_path.name,
        public_key_sha256=hashlib.sha256(public_bytes).hexdigest(),
        purposes=tuple(sorted(purposes)),
        subject_id=subject_id,
    )
    return private_key, signer


def _signed_file(
    path: Path,
    *,
    schema: str,
    statement: dict[str, object],
    signer: tuple[Ed25519PrivateKey, admission.TrustedEvidenceSigner],
) -> dict[str, str]:
    private_key, identity = signer
    payload = {
        "schema_version": schema,
        "issuer": identity.issuer,
        "tool_identity": identity.tool_identity,
        "issued_at_utc": "2026-07-14T12:00:00Z",
        "statement": statement,
    }
    signature = private_key.sign(admission.canonical_bytes(payload))
    envelope = {
        **payload,
        "signature": {
            "algorithm": admission.SIGNATURE_ALGORITHM,
            "key_id": identity.key_id,
            "value_base64": base64.b64encode(signature).decode("ascii"),
        },
    }
    return _canonical_file(path, envelope)


def _signer_record(signer: admission.TrustedEvidenceSigner) -> dict[str, object]:
    return {
        "key_id": signer.key_id,
        "issuer": signer.issuer,
        "tool_identity": signer.tool_identity,
        "public_key_path": signer.public_key_path,
        "public_key_sha256": signer.public_key_sha256,
        "purposes": list(signer.purposes),
        "subject_id": signer.subject_id,
    }


def _split_ledger(
    root: Path,
    entries: list[dict[str, str]] | None = None,
    *,
    protected: frozenset[str] = frozenset(),
    signer: tuple[Ed25519PrivateKey, admission.TrustedEvidenceSigner] | None = None,
) -> dict[str, str]:
    signer = signer or _ensure_signer(root)
    normalized = sorted(
        entries or [], key=lambda item: (item["content_sha256"], item["split"])
    )
    return _signed_file(
        root / "frozen-split-ledger.json",
        schema=admission.SPLIT_LEDGER_SCHEMA,
        statement={
            "ledger_id": "test-frozen-ledger:v1",
            "as_of_utc": "2026-07-14T12:00:00Z",
            "previous_ledger_sha256": None,
            "protected_eval_set_sha256": admission.sha256_bytes(
                admission.canonical_bytes(sorted(protected))
            ),
            "entries": normalized,
        },
        signer=signer,
    )


def _candidate(
    root: Path,
    *,
    suffix: str,
    node_id: str,
    content: str,
    split: str,
    timestamp: str = "2026-07-01T00:00:00Z",
) -> dict[str, object]:
    signer = _ensure_signer(root)
    reviewer_signer = _ensure_signer(
        root,
        key_id=REVIEW_KEY_ID,
        tool_identity="szl-test-reviewer/1.0.0",
        purposes=(admission.PURPOSE_REVIEW,),
        subject_id=TRUSTED_REVIEWER,
    )
    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    revision = "git:" + "a" * 40
    uri = f"repo://szl-holdings/a11oy/{suffix}"
    source_identity = f"source:szl:a11oy:{suffix}"
    method = "EXACT_SHA256_AGAINST_FROZEN_EVAL"
    references = ["frozen-eval:v1"]
    source_evidence = _signed_file(
        root / f"source-{suffix}.json",
        schema=admission.SOURCE_EVIDENCE_SCHEMA,
        statement={
            "candidate_content_sha256": content_sha,
            "source_identity": source_identity,
            "source_uri": uri,
            "source_revision": revision,
        },
        signer=signer,
    )
    rights_evidence = _signed_file(
        root / f"rights-{suffix}.json",
        schema=admission.RIGHTS_EVIDENCE_SCHEMA,
        statement={
            "candidate_content_sha256": content_sha,
            "source_uri": uri,
            "source_revision": revision,
            "author": TEST_AUTHOR,
            "rightsholder": TEST_RIGHTSHOLDER,
            "basis": "PROJECT_AUTHORED_SCHEMA_GENERATED",
            "license": "Apache-2.0",
            "permission_scope": "TRAIN_DERIVATIVE_AND_REDISTRIBUTE",
        },
        signer=signer,
    )
    privacy_method = "DETERMINISTIC_PII_SCAN_V1"
    privacy_evidence = _signed_file(
        root / f"privacy-{suffix}.json",
        schema=admission.PRIVACY_EVIDENCE_SCHEMA,
        statement={
            "candidate_content_sha256": content_sha,
            "classification": "PUBLIC",
            "pii_result": "CLEAR",
            "method": privacy_method,
        },
        signer=signer,
    )
    checked_against_sha = admission.sha256_bytes(admission.canonical_bytes(references))
    run_receipt = {
        "run_id": f"scan-{suffix}-001",
        "completed_at_utc": "2026-07-14T11:55:00Z",
        "tool_identity": TRUSTED_TOOL,
        "method": method,
        "candidate_content_sha256": content_sha,
        "checked_against_sha256": checked_against_sha,
        "result": "CLEAR",
    }
    contamination_evidence = _signed_file(
        root / f"contamination-{suffix}.json",
        schema=admission.CONTAMINATION_EVIDENCE_SCHEMA,
        statement={
            "result": "CLEAR",
            "method": method,
            "candidate_content_sha256": content_sha,
            "checked_against_sha256": checked_against_sha,
            "run_receipt": run_receipt,
            "run_receipt_sha256": admission.sha256_bytes(
                admission.canonical_bytes(run_receipt)
            ),
        },
        signer=signer,
    )
    reviewed_at = "2026-07-14T11:59:00Z"
    review_evidence = _signed_file(
        root / f"review-{suffix}.json",
        schema=admission.REVIEW_EVIDENCE_SCHEMA,
        statement={
            "candidate_content_sha256": content_sha,
            "node_id": node_id,
            "state": "APPROVED",
            "reviewer": TRUSTED_REVIEWER,
            "reviewed_at_utc": reviewed_at,
            "reasons": [],
        },
        signer=reviewer_signer,
    )
    return {
        "schema_version": admission.CANDIDATE_SCHEMA,
        "node_id": node_id,
        "content": content,
        "content_sha256": content_sha,
        "source": {
            "identity": source_identity,
            "uri": uri,
            "revision": revision,
            "timestamp_utc": timestamp,
            "evidence": source_evidence,
        },
        "rights": {
            "author": TEST_AUTHOR,
            "rightsholder": TEST_RIGHTSHOLDER,
            "basis": "PROJECT_AUTHORED_SCHEMA_GENERATED",
            "license": "Apache-2.0",
            "permission_scope": "TRAIN_DERIVATIVE_AND_REDISTRIBUTE",
            "evidence": rights_evidence,
        },
        "privacy": {
            "classification": "PUBLIC",
            "pii_result": "CLEAR",
            "method": privacy_method,
            "evidence": privacy_evidence,
        },
        "contamination": {
            "result": "CLEAR",
            "method": method,
            "checked_against": references,
            "evidence": contamination_evidence,
        },
        "review": {
            "state": "APPROVED",
            "reviewer": TRUSTED_REVIEWER,
            "reviewed_at_utc": reviewed_at,
            "reasons": [],
            "evidence": review_evidence,
        },
        "split": split,
    }


def _policy(
    root: Path,
    protected: frozenset[str] = frozenset(),
    *,
    ledger_entries: list[dict[str, str]] | None = None,
    ledger_protected: frozenset[str] | None = None,
    expected_ledger_head: str | None = None,
    include_ledger: bool = True,
    enable_train_admission: bool = True,
) -> admission.AdmissionPolicy:
    evidence_signer = _ensure_signer(root)
    reviewer_signer = _ensure_signer(
        root,
        key_id=REVIEW_KEY_ID,
        tool_identity="szl-test-reviewer/1.0.0",
        purposes=(admission.PURPOSE_REVIEW,),
        subject_id=TRUSTED_REVIEWER,
    )
    artifact_signer = _ensure_signer(
        root,
        key_id=ARTIFACT_KEY_ID,
        tool_identity="szl-test-artifact-signer/1.0.0",
        purposes=(admission.PURPOSE_ARTIFACT,),
    )
    root_signer = _ensure_signer(
        root,
        key_id=POLICY_ROOT_KEY_ID,
        tool_identity="szl-test-policy-root/1.0.0",
        purposes=(admission.PURPOSE_POLICY_ROOT,),
    )
    ledger = (
        _split_ledger(
            root,
            ledger_entries,
            protected=(protected if ledger_protected is None else ledger_protected),
            signer=evidence_signer,
        )
        if include_ledger
        else None
    )
    common = dict(
        as_of_utc="2026-07-15T00:00:00Z",
        evidence_root=root,
        max_age_days=30,
        allowed_reviewers=(TRUSTED_REVIEWER,),
        protected_eval_content_sha256=protected,
        trusted_evidence_signers=(
            evidence_signer[1],
            reviewer_signer[1],
            artifact_signer[1],
        ),
        split_ledger_evidence=ledger,
        expected_split_ledger_evidence_sha256=(
            expected_ledger_head
            if expected_ledger_head is not None
            else (ledger["sha256"] if ledger is not None else None)
        ),
        policy_root_signer=root_signer[1],
        artifact_signer_key_id=ARTIFACT_KEY_ID,
    )
    template = admission.AdmissionPolicy(
        **common,
        enable_train_admission=False,
    )
    statement = admission._policy_binding_statement(template)
    statement["enable_train_admission"] = enable_train_admission
    policy_bundle = _signed_file(
        root / "rooted-policy-bundle.json",
        schema=admission.POLICY_BUNDLE_SCHEMA,
        statement=statement,
        signer=root_signer,
    )
    return admission.AdmissionPolicy(
        **common,
        enable_train_admission=enable_train_admission,
        policy_bundle_evidence=policy_bundle,
    )


def _unrooted_inspection_policy(
    root: Path, protected: frozenset[str]
) -> admission.AdmissionPolicy:
    evidence_signer = _ensure_signer(root)
    reviewer_signer = _ensure_signer(
        root,
        key_id=REVIEW_KEY_ID,
        tool_identity="szl-test-reviewer/1.0.0",
        purposes=(admission.PURPOSE_REVIEW,),
        subject_id=TRUSTED_REVIEWER,
    )
    artifact_signer = _ensure_signer(
        root,
        key_id=ARTIFACT_KEY_ID,
        tool_identity="szl-test-artifact-signer/1.0.0",
        purposes=(admission.PURPOSE_ARTIFACT,),
    )
    ledger = _split_ledger(root, protected=protected, signer=evidence_signer)
    return admission.AdmissionPolicy(
        as_of_utc="2026-07-15T00:00:00Z",
        evidence_root=root,
        max_age_days=30,
        allowed_reviewers=(TRUSTED_REVIEWER,),
        enable_train_admission=False,
        protected_eval_content_sha256=protected,
        trusted_evidence_signers=(
            evidence_signer[1],
            reviewer_signer[1],
            artifact_signer[1],
        ),
        split_ledger_evidence=ledger,
        expected_split_ledger_evidence_sha256=ledger["sha256"],
        artifact_signer_key_id=ARTIFACT_KEY_ID,
    )


def _artifact_signing_key(root: Path) -> admission.ArtifactSigningKey:
    private_key, _signer = _ensure_signer(
        root,
        key_id=ARTIFACT_KEY_ID,
        tool_identity="szl-test-artifact-signer/1.0.0",
        purposes=(admission.PURPOSE_ARTIFACT,),
    )
    path = root / "artifact-signing-private.pem"
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return admission.ArtifactSigningKey(
        signer_key_id=ARTIFACT_KEY_ID,
        private_key_path=path.name,
    )


def test_fully_bound_train_and_eval_rows_are_admitted_without_promotion(tmp_path: Path):
    train = _candidate(
        tmp_path,
        suffix="train",
        node_id="brain:train:001",
        content="Project-authored governed training example.",
        split="TRAIN",
    )
    evaluation = _candidate(
        tmp_path,
        suffix="eval",
        node_id="brain:eval:001",
        content="Frozen evaluation-only example.",
        split="EVAL",
    )
    report = admission.admit_rows(
        [train, evaluation],
        _policy(tmp_path, frozenset({evaluation["content_sha256"]})),
    )

    assert report["state"] == "ADMISSION_COMPLETE"
    assert report["summary"] == {
        "observed_rows": 2,
        "admitted_train_rows": 1,
        "admitted_eval_rows": 1,
        "quarantined_rows": 0,
        "dedup_group_count": 2,
        "reason_counts": {},
    }
    train_decision, eval_decision = report["decisions"]
    assert train_decision["canonical_status"] == "CANONICAL"
    assert train_decision["training_eligible"] is True
    assert train_decision["evaluation_eligible"] is False
    assert train_decision["freshness"]["state"] == "FRESH"
    assert train_decision["source"]["identity"] == "source:szl:a11oy:train"
    assert train_decision["source"]["revision_state"] == "PINNED_IDENTIFIER_WITH_SIGNED_EVIDENCE"
    assert train_decision["source"]["status"] == "VERIFIED_SIGNED_BINDING"
    assert train_decision["rights"]["status"] == "VERIFIED_SIGNED_CONTENT_RIGHTS_BINDING"
    assert train_decision["rights"]["author"] == TEST_AUTHOR
    assert train_decision["rights"]["rightsholder"] == TEST_RIGHTSHOLDER
    assert (
        train_decision["rights"]["permission_scope"]
        == "TRAIN_DERIVATIVE_AND_REDISTRIBUTE"
    )
    assert train_decision["privacy"]["status"] == "VERIFIED_SIGNED_PII_CLEARANCE"
    assert train_decision["privacy"]["pii_result"] == "CLEAR"
    assert (
        train_decision["review"]["status"]
        == "VERIFIED_SIGNED_ALLOWLISTED_REVIEW"
    )
    assert train_decision["review"]["reviewer"] == TRUSTED_REVIEWER
    assert train_decision["contamination"]["observed_result"] == "CLEAR_WITH_SIGNED_RUN_RECEIPT"
    assert eval_decision["admission_decision"] == "ADMIT_EVAL"
    assert eval_decision["training_eligible"] is False
    assert eval_decision["contamination"]["observed_result"] == "PROTECTED_EVAL_MEMBER"
    assert report["claims_boundary"]["training_triggered"] is False
    assert report["claims_boundary"]["model_promotion_allowed"] is False
    unsigned = dict(report)
    receipt = unsigned.pop("report_receipt_sha256")
    assert admission.sha256_bytes(admission.canonical_bytes(unsigned)) == receipt


def test_train_rows_are_zero_eligible_by_default_even_when_all_evidence_passes(
    tmp_path: Path,
):
    row = _candidate(
        tmp_path,
        suffix="default-off",
        node_id="brain:default-off:001",
        content="A complete record still needs an explicit gradient admission switch.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    report = admission.admit_rows(
        [row], _policy(tmp_path, protected, enable_train_admission=False)
    )
    decision = report["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert decision["training_eligible"] is False
    assert "TRAIN_ADMISSION_DISABLED_BY_POLICY" in decision["reason_codes"]
    assert report["claims_boundary"]["default_gradient_eligibility"] is False


def test_privacy_rightsholder_and_reviewer_obligations_fail_closed(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="governance-gaps",
        node_id="brain:governance-gaps:001",
        content="Rights, privacy, and review are separate admission obligations.",
        split="TRAIN",
    )
    row["rights"]["rightsholder"] = "unknown"
    row["privacy"]["pii_result"] = "DETECTED"
    row["review"]["reviewer"] = "reviewer:untrusted:external"
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    decision = admission.admit_rows([row], _policy(tmp_path, protected))["decisions"][0]

    assert decision["training_eligible"] is False
    assert {
        "RIGHTS_EVIDENCE_BINDING_MISMATCH:rightsholder",
        "PII_DETECTED",
        "PRIVACY_EVIDENCE_BINDING_MISMATCH:pii_result",
        "REVIEWER_NOT_ALLOWLISTED",
        "REVIEW_EVIDENCE_BINDING_MISMATCH:reviewer",
    }.issubset(set(decision["reason_codes"]))
    assert decision["content_included"] is False


def test_eval_rows_must_be_members_of_the_frozen_held_out_set(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="unfrozen-eval",
        node_id="brain:unfrozen-eval:001",
        content="An evaluation row is not held out merely because it says EVAL.",
        split="EVAL",
    )
    protected = frozenset({hashlib.sha256(b"other-eval-row").hexdigest()})

    decision = admission.admit_rows([row], _policy(tmp_path, protected))["decisions"][0]

    assert decision["evaluation_eligible"] is False
    assert "EVAL_CONTENT_NOT_IN_FROZEN_SET" in decision["reason_codes"]


def test_eval_admission_requires_a_root_signed_policy(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="unrooted-eval",
        node_id="brain:unrooted-eval:001",
        content="Held-out evaluation is a release artifact, not unsigned inspection.",
        split="EVAL",
    )
    protected = frozenset({str(row["content_sha256"])})

    decision = admission.admit_rows(
        [row], _unrooted_inspection_policy(tmp_path, protected)
    )["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert decision["evaluation_eligible"] is False
    assert "EVAL_ROOTED_ADMISSION_POLICY_REQUIRED" in decision["reason_codes"]


def test_confined_reader_rejects_non_regular_and_unstable_files(
    tmp_path: Path, monkeypatch,
):
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises(admission.AdmissionInputError) as non_regular:
        admission._read_confined_bytes_once(tmp_path, directory.name, 1024)
    assert str(non_regular.value) == "EVIDENCE_FILE_NOT_REGULAR"

    evidence = tmp_path / "unstable.json"
    evidence.write_bytes(b'{"stable":true}')
    real_fstat = admission.os.fstat
    calls = 0

    def unstable_fstat(file_descriptor: int):
        nonlocal calls
        calls += 1
        observed = real_fstat(file_descriptor)
        if calls == 2:
            fields = list(observed)
            fields[6] = observed.st_size + 1
            return admission.os.stat_result(fields)
        return observed

    monkeypatch.setattr(admission.os, "fstat", unstable_fstat)
    with pytest.raises(admission.AdmissionInputError) as unstable:
        admission._read_confined_bytes_once(tmp_path, evidence.name, 1024)
    assert str(unstable.value) == "EVIDENCE_FILE_UNSTABLE"


def test_confined_reader_rejects_symlink_evidence_when_supported(tmp_path: Path):
    target = tmp_path / "target.json"
    target.write_bytes(b'{"target":true}')
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target.name)
    except OSError:
        pytest.skip("host does not permit creating symlinks")

    with pytest.raises(admission.AdmissionInputError) as error:
        admission._read_confined_bytes_once(tmp_path, link.name, 1024)
    assert str(error.value) == "EVIDENCE_FILE_NOT_REGULAR"


def test_non_string_reference_and_review_reason_values_quarantine_without_crash(
    tmp_path: Path,
):
    row = _candidate(
        tmp_path,
        suffix="structured-invalid",
        node_id="brain:structured-invalid:001",
        content="Untrusted structured values must be reason-coded, not raised.",
        split="TRAIN",
    )
    row["contamination"]["checked_against"] = [{"not": "a reference"}]
    row["review"]["reasons"] = [{"not": "a reason code"}]
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    decision = admission.admit_rows([row], _policy(tmp_path, protected))["decisions"][0]

    assert decision["training_eligible"] is False
    assert "CONTAMINATION_REFERENCE_SET_INVALID" in decision["reason_codes"]
    assert "REVIEW_REASONS_INVALID" in decision["reason_codes"]


def test_rehashed_but_cryptographically_tampered_evidence_is_rejected(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="tamper",
        node_id="brain:tamper:001",
        content="Signed source binding cannot be rewritten by the caller.",
        split="TRAIN",
    )
    evidence_path = tmp_path / row["source"]["evidence"]["path"]
    envelope = json.loads(evidence_path.read_text(encoding="utf-8"))
    envelope["issued_at_utc"] = "2026-07-13T12:00:00Z"
    # Rehashing the edited file defeats a plain file-hash check, but not Ed25519.
    row["source"]["evidence"] = _canonical_file(evidence_path, envelope)
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    decision = admission.admit_rows([row], _policy(tmp_path, protected))["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert "SOURCE_EVIDENCE_SIGNATURE_INVALID" in decision["reason_codes"]
    assert decision["source"]["status"] == "UNVERIFIED"


def test_public_key_and_evidence_replacement_after_policy_pin_is_rejected(
    tmp_path: Path,
):
    row = _candidate(
        tmp_path,
        suffix="key-swap",
        node_id="brain:key-swap:001",
        content="A pinned public key cannot be swapped after policy construction.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})
    policy = _policy(tmp_path, protected)
    trusted = next(
        item for item in policy.trusted_evidence_signers if item.key_id == TRUSTED_KEY_ID
    )
    attacker_private = Ed25519PrivateKey.generate()
    attacker_public = attacker_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (tmp_path / trusted.public_key_path).write_bytes(attacker_public)
    source_path = tmp_path / row["source"]["evidence"]["path"]
    source_envelope = json.loads(source_path.read_text(encoding="utf-8"))
    attacker_identity = admission.TrustedEvidenceSigner(
        key_id=trusted.key_id,
        issuer=trusted.issuer,
        tool_identity=trusted.tool_identity,
        public_key_path=trusted.public_key_path,
        public_key_sha256=hashlib.sha256(attacker_public).hexdigest(),
        purposes=trusted.purposes,
    )
    row["source"]["evidence"] = _signed_file(
        source_path,
        schema=admission.SOURCE_EVIDENCE_SCHEMA,
        statement=source_envelope["statement"],
        signer=(attacker_private, attacker_identity),
    )

    decision = admission.admit_rows([row], policy)["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert "SOURCE_EVIDENCE_SIGNATURE_INVALID" in decision["reason_codes"]


def test_wrong_purpose_signer_cannot_issue_source_evidence(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="purpose-swap",
        node_id="brain:purpose-swap:001",
        content="Review authority does not imply source authority.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})
    policy = _policy(tmp_path, protected)
    source_path = tmp_path / row["source"]["evidence"]["path"]
    source_envelope = json.loads(source_path.read_text(encoding="utf-8"))
    reviewer = _ensure_signer(
        tmp_path,
        key_id=REVIEW_KEY_ID,
        tool_identity="szl-test-reviewer/1.0.0",
        purposes=(admission.PURPOSE_REVIEW,),
        subject_id=TRUSTED_REVIEWER,
    )
    row["source"]["evidence"] = _signed_file(
        source_path,
        schema=admission.SOURCE_EVIDENCE_SCHEMA,
        statement=source_envelope["statement"],
        signer=reviewer,
    )

    decision = admission.admit_rows([row], policy)["decisions"][0]

    assert "SOURCE_EVIDENCE_SIGNER_PURPOSE_NOT_ALLOWED" in decision["reason_codes"]


def test_root_signed_policy_bundle_rejects_policy_mutation(tmp_path: Path):
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})
    policy = _policy(tmp_path, protected)

    with pytest.raises(admission.AdmissionInputError) as excinfo:
        dataclasses.replace(policy, max_age_days=31)

    assert str(excinfo.value).startswith("POLICY_BUNDLE_VERIFICATION_FAILED:")


def test_self_attested_key_not_in_policy_allowlist_is_rejected(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="self-attested",
        node_id="brain:self-attested:001",
        content="An attacker cannot introduce a new trust root with the evidence.",
        split="TRAIN",
    )
    evidence_path = tmp_path / row["source"]["evidence"]["path"]
    trusted_envelope = json.loads(evidence_path.read_text(encoding="utf-8"))
    attacker = _ensure_signer(
        tmp_path,
        key_id="attacker-controlled-key",
        issuer="did:web:attacker.invalid",
        tool_identity="attacker-self-attestor/1.0",
    )
    row["source"]["evidence"] = _signed_file(
        evidence_path,
        schema=admission.SOURCE_EVIDENCE_SCHEMA,
        statement=trusted_envelope["statement"],
        signer=attacker,
    )
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    decision = admission.admit_rows([row], _policy(tmp_path, protected))["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert "SOURCE_EVIDENCE_SIGNER_NOT_ALLOWLISTED" in decision["reason_codes"]


def test_trusted_signature_does_not_override_misbound_run_receipt(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="misbound-run",
        node_id="brain:misbound-run:001",
        content="Semantic receipt binding remains independently enforced.",
        split="TRAIN",
    )
    evidence_path = tmp_path / row["contamination"]["evidence"]["path"]
    envelope = json.loads(evidence_path.read_text(encoding="utf-8"))
    statement = envelope["statement"]
    statement["run_receipt"]["candidate_content_sha256"] = "f" * 64
    statement["run_receipt_sha256"] = admission.sha256_bytes(
        admission.canonical_bytes(statement["run_receipt"])
    )
    # The trusted fixture key signs this malformed statement.  Signature alone
    # must not grant admission when the run receipt is bound to other content.
    row["contamination"]["evidence"] = _signed_file(
        evidence_path,
        schema=admission.CONTAMINATION_EVIDENCE_SCHEMA,
        statement=statement,
        signer=_ensure_signer(tmp_path),
    )
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    decision = admission.admit_rows([row], _policy(tmp_path, protected))["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert (
        "CONTAMINATION_RUN_RECEIPT_BINDING_MISMATCH:candidate_content_sha256"
        in decision["reason_codes"]
    )


def test_train_requires_frozen_eval_hashes_and_signed_prior_ledger(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="missing-policy-inputs",
        node_id="brain:missing-policy-inputs:001",
        content="Training is blocked unless both frozen boundaries exist.",
        split="TRAIN",
    )
    no_eval = admission.admit_rows([row], _policy(tmp_path))["decisions"][0]
    assert "FROZEN_EVAL_HASHES_REQUIRED_FOR_TRAIN" in no_eval["reason_codes"]

    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})
    with pytest.raises(admission.AdmissionInputError) as excinfo:
        _policy(tmp_path, protected, include_ledger=False)
    assert str(excinfo.value) == "POLICY_TRAIN_ROOTED_AUTHORIZATION_REQUIRED"


def test_signed_ledger_must_bind_the_exact_frozen_eval_set(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="ledger-eval-binding",
        node_id="brain:ledger-eval-binding:001",
        content="The prior ledger freezes the exact protected evaluation set.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"frozen-set-b").hexdigest()})
    policy = _policy(
        tmp_path,
        protected,
        ledger_protected=frozenset(
            {hashlib.sha256(b"frozen-set-a").hexdigest()}
        ),
    )

    decision = admission.admit_rows([row], policy)["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert (
        "SPLIT_LEDGER_PROTECTED_EVAL_BINDING_MISMATCH" in decision["reason_codes"]
    )


def test_signed_but_stale_split_ledger_is_rejected_against_pinned_head(
    tmp_path: Path,
):
    row = _candidate(
        tmp_path,
        suffix="stale-ledger",
        node_id="brain:stale-ledger:001",
        content="A signed older ledger cannot roll back split history.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})
    policy = _policy(tmp_path, protected, expected_ledger_head="f" * 64)

    decision = admission.admit_rows([row], policy)["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert "SPLIT_LEDGER_HEAD_MISMATCH" in decision["reason_codes"]


def test_prior_run_content_and_split_collisions_fail_closed(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="cross-run",
        node_id="brain:cross-run:001",
        content="A hash cannot migrate from frozen evaluation into training.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"different-frozen-eval").hexdigest()})
    conflict = admission.admit_rows(
        [row],
        _policy(
            tmp_path,
            protected,
            ledger_entries=[
                {"content_sha256": row["content_sha256"], "split": "EVAL"}
            ],
        ),
    )["decisions"][0]
    assert "CROSS_RUN_SPLIT_CONFLICT" in conflict["reason_codes"]
    assert conflict["contamination"]["observed_result"] == "CROSS_RUN_SPLIT_MATCH"

    reuse = admission.admit_rows(
        [row],
        _policy(
            tmp_path,
            protected,
            ledger_entries=[
                {"content_sha256": row["content_sha256"], "split": "TRAIN"}
            ],
        ),
    )["decisions"][0]
    assert "CROSS_RUN_CONTENT_REUSE" in reuse["reason_codes"]
    assert reuse["contamination"]["observed_result"] == "PRIOR_RUN_CONTENT_MATCH"


def test_missing_provenance_bad_rights_and_uncleared_contamination_are_quarantined(
    tmp_path: Path,
):
    row = _candidate(
        tmp_path,
        suffix="bad",
        node_id="brain:bad:001",
        content="This row must never enter gradients.",
        split="TRAIN",
    )
    row["source"]["revision"] = "main"
    row["rights"]["license"] = "UNKNOWN"
    row["contamination"]["result"] = "UNKNOWN"
    report = admission.admit_rows([row], _policy(tmp_path))
    decision = report["decisions"][0]

    assert report["state"] == "ALL_QUARANTINED"
    assert decision["canonical_status"] == "QUARANTINED"
    assert decision["training_eligible"] is False
    assert decision["content_included"] is False
    assert "content" not in decision
    assert {
        "SOURCE_IMMUTABLE_REVISION_REQUIRED",
        "SOURCE_EVIDENCE_BINDING_MISMATCH:source_revision",
        "LICENSE_NOT_ALLOWED",
        "RIGHTS_EVIDENCE_BINDING_MISMATCH:license",
        "CONTAMINATION_NOT_CLEARED",
        "CONTAMINATION_EVIDENCE_BINDING_MISMATCH:result",
    }.issubset(set(decision["reason_codes"]))
    assert decision["source"] == {"status": "UNVERIFIED"}
    serialized = admission.canonical_bytes(decision)
    assert b"main" not in serialized
    assert TEST_AUTHOR.encode() not in serialized
    assert TRUSTED_REVIEWER.encode() not in serialized
    assert report["claims_boundary"]["provenance_inferred"] is False


def test_quarantine_artifacts_do_not_repeat_sensitive_candidate_metadata(
    tmp_path: Path,
):
    row = _candidate(
        tmp_path,
        suffix="redaction",
        node_id="brain:redaction:001",
        content="PRIVATE-CONTENT-MARKER",
        split="TRAIN",
    )
    row["source"]["uri"] = "https://example.invalid/source?token=URI-SECRET-MARKER"
    row["rights"]["author"] = "author:PRIVATE-AUTHOR-MARKER"
    protected = frozenset({hashlib.sha256(b"frozen-eval").hexdigest()})

    report = admission.admit_rows([row], _policy(tmp_path, protected))
    serialized = admission.canonical_bytes(report)

    assert report["decisions"][0]["admission_decision"] == "QUARANTINE"
    for marker in (
        b"PRIVATE-CONTENT-MARKER",
        b"URI-SECRET-MARKER",
        b"PRIVATE-AUTHOR-MARKER",
        TRUSTED_REVIEWER.encode(),
        b"source-redaction.json",
    ):
        assert marker not in serialized


def test_same_content_across_train_and_eval_quarantines_both_splits(tmp_path: Path):
    train = _candidate(
        tmp_path,
        suffix="overlap-train",
        node_id="brain:overlap:train",
        content="Exact cross-split duplicate.",
        split="TRAIN",
    )
    evaluation = _candidate(
        tmp_path,
        suffix="overlap-eval",
        node_id="brain:overlap:eval",
        content="Exact cross-split duplicate.",
        split="EVAL",
    )
    report = admission.admit_rows(
        [train, evaluation],
        _policy(tmp_path, frozenset({evaluation["content_sha256"]})),
    )

    assert report["summary"]["quarantined_rows"] == 2
    assert report["summary"]["reason_counts"]["DEDUP_GROUP_SPLIT_CONFLICT"] == 2
    for decision in report["decisions"]:
        assert decision["admission_decision"] == "QUARANTINE"
        assert decision["contamination"]["observed_result"] == "CROSS_SPLIT_CONTENT_MATCH"
        assert decision["dedup_group"] is None
        assert train["content_sha256"] not in admission.canonical_bytes(decision).decode()


def test_protected_eval_match_blocks_train_even_when_declared_clear(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="protected",
        node_id="brain:protected:001",
        content="Protected evaluation content.",
        split="TRAIN",
    )
    report = admission.admit_rows(
        [row], _policy(tmp_path, frozenset({row["content_sha256"]}))
    )
    decision = report["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert "PROTECTED_EVAL_CONTENT_IN_TRAIN" in decision["reason_codes"]
    assert decision["contamination"]["observed_result"] == "PROTECTED_EVAL_MATCH"


def test_json_and_jsonl_inputs_emit_content_addressed_split_ledgers(tmp_path: Path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    train = _candidate(
        evidence,
        suffix="file-train",
        node_id="brain:file:train",
        content="Train file row.",
        split="TRAIN",
    )
    evaluation = _candidate(
        evidence,
        suffix="file-eval",
        node_id="brain:file:eval",
        content="Eval file row.",
        split="EVAL",
    )
    json_input = tmp_path / "candidates.json"
    json_input.write_text(json.dumps({"rows": [train, evaluation]}), encoding="utf-8")
    assert len(admission.load_candidate_rows(json_input)) == 2

    jsonl_input = tmp_path / "candidates.jsonl"
    jsonl_input.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in (train, evaluation)
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    policy = _policy(evidence, frozenset({evaluation["content_sha256"]}))
    final_report = admission.admit_file(
        jsonl_input,
        output,
        policy,
        artifact_signing_key=_artifact_signing_key(evidence),
    )

    schema_root = (
        Path(__file__).resolve().parents[1]
        / "model_release"
        / "brain-row-admission"
        / "schemas"
    )
    candidate_schema = json.loads(
        (schema_root / "candidate.schema.json").read_text(encoding="utf-8")
    )
    decision_schema = json.loads(
        (schema_root / "decision.schema.json").read_text(encoding="utf-8")
    )
    report_schema = json.loads(
        (schema_root / "report.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(candidate_schema).validate(train)
    Draft202012Validator(candidate_schema).validate(evaluation)
    for decision in final_report["decisions"]:
        Draft202012Validator(decision_schema).validate(decision)
    Draft202012Validator(report_schema).validate(final_report)

    assert final_report["artifacts"]["admitted_train"]["rows"] == 1
    assert final_report["artifacts"]["admitted_eval"]["rows"] == 1
    assert final_report["artifacts"]["quarantine"]["rows"] == 0
    for artifact in final_report["artifacts"].values():
        path = output / artifact["path"]
        assert admission.sha256_file(path) == artifact["sha256"]
    committed = json.loads((output / "admission-report.json").read_text(encoding="utf-8"))
    assert committed["report_receipt_sha256"] == final_report["report_receipt_sha256"]
    manifest_path = output / "admission-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_schema = json.loads(
        (schema_root / "artifact-manifest.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(artifact_schema).validate(manifest)
    unsigned_manifest = dict(manifest)
    unsigned_manifest.pop("signature")
    manifest_receipt = unsigned_manifest.pop("manifest_receipt_sha256")
    assert (
        admission.sha256_bytes(admission.canonical_bytes(unsigned_manifest))
        == manifest_receipt
    )
    assert manifest["schema_version"] == admission.ARTIFACT_MANIFEST_SCHEMA
    assert manifest["report"]["sha256"] == admission.sha256_file(
        output / "admission-report.json"
    )
    assert manifest["decision_set"]["rows"] == 2
    assert manifest["input_manifest"] == final_report["input_manifest"]
    assert admission.verify_artifact_manifest(manifest, policy) == []
    tampered = json.loads(json.dumps(manifest))
    tampered["decision_set"]["rows"] = 99
    unsigned_tampered = dict(tampered)
    unsigned_tampered.pop("signature")
    unsigned_tampered.pop("manifest_receipt_sha256")
    tampered["manifest_receipt_sha256"] = admission.sha256_bytes(
        admission.canonical_bytes(unsigned_tampered)
    )
    assert "ARTIFACT_MANIFEST_SIGNATURE_INVALID" in admission.verify_artifact_manifest(
        tampered, policy
    )


def test_versioned_machine_schemas_cover_every_new_row_obligation():
    schema_root = (
        Path(__file__).resolve().parents[1]
        / "model_release"
        / "brain-row-admission"
        / "schemas"
    )
    candidate = json.loads(
        (schema_root / "candidate.schema.json").read_text(encoding="utf-8")
    )
    artifact_manifest = json.loads(
        (schema_root / "artifact-manifest.schema.json").read_text(encoding="utf-8")
    )
    decision = json.loads(
        (schema_root / "decision.schema.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (schema_root / "report.schema.json").read_text(encoding="utf-8")
    )

    for schema in (candidate, decision, report, artifact_manifest):
        Draft202012Validator.check_schema(schema)

    assert candidate["properties"]["schema_version"]["const"] == admission.CANDIDATE_SCHEMA
    assert {
        "source",
        "rights",
        "privacy",
        "contamination",
        "review",
        "split",
    }.issubset(set(candidate["required"]))
    assert {
        "author",
        "rightsholder",
        "permission_scope",
    }.issubset(set(candidate["properties"]["rights"]["required"]))
    assert artifact_manifest["properties"]["schema_version"]["const"] == (
        admission.ARTIFACT_MANIFEST_SCHEMA
    )
    assert decision["properties"]["schema_version"]["const"] == admission.DECISION_SCHEMA
    assert report["properties"]["schema_version"]["const"] == admission.REPORT_SCHEMA


def test_decision_schema_rejects_rehashed_contradictory_admission_flags(
    tmp_path: Path,
):
    evaluation = _candidate(
        tmp_path,
        suffix="schema-eval",
        node_id="brain:schema:eval",
        content="Frozen schema evaluation row.",
        split="EVAL",
    )
    train = _candidate(
        tmp_path,
        suffix="schema-train",
        node_id="brain:schema:train",
        content="Schema train row.",
        split="TRAIN",
    )
    report = admission.admit_rows(
        [train, evaluation],
        _policy(tmp_path, frozenset({evaluation["content_sha256"]})),
    )
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "model_release"
            / "brain-row-admission"
            / "schemas"
            / "decision.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    contradictory = json.loads(json.dumps(report["decisions"][0]))
    contradictory["training_eligible"] = False
    receipt_body = dict(contradictory)
    receipt_body.pop("decision_receipt_sha256")
    contradictory["decision_receipt_sha256"] = admission.sha256_bytes(
        admission.canonical_bytes(receipt_body)
    )

    assert list(validator.iter_errors(contradictory))


def test_cli_requires_explicit_reviewer_and_train_switch_and_emits_manifest(
    tmp_path: Path, capsys,
):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    signer = _ensure_signer(evidence)
    reviewer_signer = _ensure_signer(
        evidence,
        key_id=REVIEW_KEY_ID,
        tool_identity="szl-test-reviewer/1.0.0",
        purposes=(admission.PURPOSE_REVIEW,),
        subject_id=TRUSTED_REVIEWER,
    )
    artifact_signer = _ensure_signer(
        evidence,
        key_id=ARTIFACT_KEY_ID,
        tool_identity="szl-test-artifact-signer/1.0.0",
        purposes=(admission.PURPOSE_ARTIFACT,),
    )
    root_signer = _ensure_signer(
        evidence,
        key_id=POLICY_ROOT_KEY_ID,
        tool_identity="szl-test-policy-root/1.0.0",
        purposes=(admission.PURPOSE_POLICY_ROOT,),
    )
    row = _candidate(
        evidence,
        suffix="cli",
        node_id="brain:cli:001",
        content="The CLI preserves the same fail-closed admission contract.",
        split="TRAIN",
    )
    protected = frozenset({hashlib.sha256(b"frozen-cli-eval").hexdigest()})
    candidate_path = tmp_path / "candidate.jsonl"
    candidate_path.write_text(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    protected_path = tmp_path / "protected.json"
    protected_path.write_text(json.dumps(sorted(protected)), encoding="utf-8")
    reviewer_path = tmp_path / "reviewers.json"
    reviewer_path.write_text(json.dumps([TRUSTED_REVIEWER]), encoding="utf-8")
    trust_store_path = tmp_path / "trust-store.json"
    trust_store_path.write_text(
        json.dumps(
            {
                "schema_version": admission.TRUST_STORE_SCHEMA,
                "signers": [
                    _signer_record(item)
                    for item in (
                        signer[1], reviewer_signer[1], artifact_signer[1]
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    split_descriptor = _split_ledger(evidence, protected=protected, signer=signer)
    split_descriptor_path = tmp_path / "split-descriptor.json"
    split_descriptor_path.write_text(
        json.dumps(split_descriptor),
        encoding="utf-8",
    )
    root_store_path = tmp_path / "policy-root.json"
    root_store_path.write_text(
        json.dumps(
            {
                "schema_version": admission.TRUST_STORE_SCHEMA,
                "signers": [_signer_record(root_signer[1])],
            }
        ),
        encoding="utf-8",
    )
    template = admission.AdmissionPolicy(
        as_of_utc="2026-07-15T00:00:00Z",
        evidence_root=evidence,
        max_age_days=30,
        allowed_reviewers=(TRUSTED_REVIEWER,),
        protected_eval_content_sha256=protected,
        trusted_evidence_signers=(
            signer[1], reviewer_signer[1], artifact_signer[1]
        ),
        split_ledger_evidence=split_descriptor,
        expected_split_ledger_evidence_sha256=split_descriptor["sha256"],
        policy_root_signer=root_signer[1],
        artifact_signer_key_id=ARTIFACT_KEY_ID,
    )
    policy_statement = admission._policy_binding_statement(template)
    policy_statement["enable_train_admission"] = True
    policy_descriptor = _signed_file(
        evidence / "cli-rooted-policy.json",
        schema=admission.POLICY_BUNDLE_SCHEMA,
        statement=policy_statement,
        signer=root_signer,
    )
    policy_descriptor_path = tmp_path / "policy-descriptor.json"
    policy_descriptor_path.write_text(json.dumps(policy_descriptor), encoding="utf-8")
    artifact_private = _artifact_signing_key(evidence)
    output = tmp_path / "output"

    exit_code = admission.main(
        [
            "--input",
            str(candidate_path),
            "--output-dir",
            str(output),
            "--evidence-root",
            str(evidence),
            "--as-of-utc",
            "2026-07-15T00:00:00Z",
            "--max-age-days",
            "30",
            "--protected-eval-hashes",
            str(protected_path),
            "--trust-store",
            str(trust_store_path),
            "--split-ledger-evidence",
            str(split_descriptor_path),
            "--expected-split-ledger-evidence-sha256",
            split_descriptor["sha256"],
            "--reviewer-allowlist",
            str(reviewer_path),
            "--policy-root-signer",
            str(root_store_path),
            "--policy-bundle-evidence",
            str(policy_descriptor_path),
            "--artifact-signer-key-id",
            ARTIFACT_KEY_ID,
            "--artifact-signing-private-key",
            artifact_private.private_key_path,
            "--enable-train-admission",
        ]
    )

    assert exit_code == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["ok"] is True
    assert emitted["summary"]["admitted_train_rows"] == 1
    assert emitted["artifact_manifest_sha256"] == admission.sha256_file(
        output / "admission-manifest.json"
    )
