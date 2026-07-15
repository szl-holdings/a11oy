"""Fail-closed Brain training-admission regression tests."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

import szl_brain_training_admission as admission


_PRIVATE_KEYS: dict[tuple[str, str], Ed25519PrivateKey] = {}
TRUSTED_KEY_ID = "test-release-authority-ed25519-2026"
TRUSTED_ISSUER = "did:web:test.szlh.example:release-authority"
TRUSTED_TOOL = "szl-test-evidence-issuer/1.0.0"


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
    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    revision = "git:" + "a" * 40
    uri = f"repo://szl-holdings/a11oy/{suffix}"
    method = "EXACT_SHA256_AGAINST_FROZEN_EVAL"
    references = ["frozen-eval:v1"]
    source_evidence = _signed_file(
        root / f"source-{suffix}.json",
        schema=admission.SOURCE_EVIDENCE_SCHEMA,
        statement={
            "candidate_content_sha256": content_sha,
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
            "basis": "PROJECT_AUTHORED_SCHEMA_GENERATED",
            "license": "Apache-2.0",
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
    return {
        "schema_version": admission.CANDIDATE_SCHEMA,
        "node_id": node_id,
        "content": content,
        "content_sha256": content_sha,
        "source": {
            "uri": uri,
            "revision": revision,
            "timestamp_utc": timestamp,
            "evidence": source_evidence,
        },
        "rights": {
            "basis": "PROJECT_AUTHORED_SCHEMA_GENERATED",
            "license": "Apache-2.0",
            "evidence": rights_evidence,
        },
        "contamination": {
            "result": "CLEAR",
            "method": method,
            "checked_against": references,
            "evidence": contamination_evidence,
        },
        "split": split,
    }


def _policy(
    root: Path,
    protected: frozenset[str] = frozenset(),
    *,
    ledger_entries: list[dict[str, str]] | None = None,
    include_ledger: bool = True,
) -> admission.AdmissionPolicy:
    signer = _ensure_signer(root)
    return admission.AdmissionPolicy(
        as_of_utc="2026-07-15T00:00:00Z",
        evidence_root=root,
        max_age_days=30,
        protected_eval_content_sha256=protected,
        trusted_evidence_signers=(signer[1],),
        split_ledger_evidence=(
            _split_ledger(root, ledger_entries, protected=protected, signer=signer)
            if include_ledger
            else None
        ),
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
    assert train_decision["source"]["revision_state"] == "PINNED_IDENTIFIER_WITH_SIGNED_EVIDENCE"
    assert train_decision["source"]["status"] == "VERIFIED_SIGNED_BINDING"
    assert train_decision["rights"]["status"] == "VERIFIED_SIGNED_CONTENT_RIGHTS_BINDING"
    assert train_decision["contamination"]["observed_result"] == "CLEAR_WITH_SIGNED_RUN_RECEIPT"
    assert eval_decision["admission_decision"] == "ADMIT_EVAL"
    assert eval_decision["training_eligible"] is False
    assert eval_decision["contamination"]["observed_result"] == "PROTECTED_EVAL_MEMBER"
    assert report["claims_boundary"]["training_triggered"] is False
    assert report["claims_boundary"]["model_promotion_allowed"] is False
    unsigned = dict(report)
    receipt = unsigned.pop("report_receipt_sha256")
    assert admission.sha256_bytes(admission.canonical_bytes(unsigned)) == receipt


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
    no_ledger = admission.admit_rows(
        [row], _policy(tmp_path, protected, include_ledger=False)
    )["decisions"][0]
    assert "SPLIT_LEDGER_REQUIRED" in no_ledger["reason_codes"]


def test_signed_ledger_must_bind_the_exact_frozen_eval_set(tmp_path: Path):
    row = _candidate(
        tmp_path,
        suffix="ledger-eval-binding",
        node_id="brain:ledger-eval-binding:001",
        content="The prior ledger freezes the exact protected evaluation set.",
        split="TRAIN",
    )
    signer = _ensure_signer(tmp_path)
    protected = frozenset({hashlib.sha256(b"frozen-set-b").hexdigest()})
    descriptor_for_other_set = _split_ledger(
        tmp_path,
        protected=frozenset({hashlib.sha256(b"frozen-set-a").hexdigest()}),
        signer=signer,
    )
    policy = admission.AdmissionPolicy(
        as_of_utc="2026-07-15T00:00:00Z",
        evidence_root=tmp_path,
        max_age_days=30,
        protected_eval_content_sha256=protected,
        trusted_evidence_signers=(signer[1],),
        split_ledger_evidence=descriptor_for_other_set,
    )

    decision = admission.admit_rows([row], policy)["decisions"][0]

    assert decision["admission_decision"] == "QUARANTINE"
    assert (
        "SPLIT_LEDGER_PROTECTED_EVAL_BINDING_MISMATCH" in decision["reason_codes"]
    )


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
    assert decision["source"]["revision"] == "main"
    assert decision["source"]["revision_state"] == "UNVERIFIED"
    assert report["claims_boundary"]["provenance_inferred"] is False


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
        assert decision["dedup_group"] == f"sha256:{train['content_sha256']}"


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
    final_report = admission.admit_file(
        jsonl_input,
        output,
        _policy(evidence, frozenset({evaluation["content_sha256"]})),
    )

    assert final_report["artifacts"]["admitted_train"]["rows"] == 1
    assert final_report["artifacts"]["admitted_eval"]["rows"] == 1
    assert final_report["artifacts"]["quarantine"]["rows"] == 0
    for artifact in final_report["artifacts"].values():
        path = output / artifact["path"]
        assert admission.sha256_file(path) == artifact["sha256"]
    committed = json.loads((output / "admission-report.json").read_text(encoding="utf-8"))
    assert committed["report_receipt_sha256"] == final_report["report_receipt_sha256"]
