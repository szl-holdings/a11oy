from __future__ import annotations

import base64
import copy
import dataclasses
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_nemo_v3_owner_dispatch.py"
SPEC = importlib.util.spec_from_file_location("nemo_owner_dispatch", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
dispatch_validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dispatch_validator
SPEC.loader.exec_module(dispatch_validator)

SOURCE_SHA = "a" * 40
BRIDGE_SHA = "b" * 40
ENVELOPE_SHA = "e" * 40
ENVELOPE_HASH = "c" * 64
PAYLOAD_HASH = "d" * 64
JOB_ID = "job-2026-nemo-v3-governed-attempt-16"
PREDECESSOR_JOB_ID = "job-2026-nemo-v3-governed-attempt-15"
PREDECESSOR_SOURCE_SHA = "9" * 40
PREDECESSOR_ENVELOPE_REVISION = "1" * 40
PREDECESSOR_EXECUTION_REVISION = "2" * 40
ACTIVE_OWNER_KEY_ID = "b8041281c81c4caa"
ACTIVE_OWNER_SPKI_BASE64 = (
    "MCowBQYDK2VwAyEAstuDm9wVQ7BrOuBRmIyEHsOtyOutChFfRvCDenCDB6c="
)
ACTIVE_OWNER_SPKI_SHA256 = (
    "b8041281c81c4caaea18112df5e8c99ea8472f0711fc796fc3072c27398af2cf"
)
RETIRED_OWNER_KEY_ID = "5c6cf59741ade920"
RETIRED_OWNER_SPKI_BASE64 = (
    "MCowBQYDK2VwAyEArBOmZZSDK+n7Qq1HJYbqNuX9YymnsRWbzSGHHnhsERM="
)


def _workflow(tmp_path: Path) -> Path:
    workflow = (
        tmp_path
        / ".github"
        / "workflows"
        / "nemo-v3-isolated-owner-dispatch.yml"
    )
    workflow.parent.mkdir(parents=True)
    workflow.write_bytes(b"name: exact protected owner workflow\n")
    return workflow


def _dispatch(workflow: Path, **overrides: Any) -> dict[str, Any]:
    selection: dict[str, Any] = {
        "contractVersion": dispatch_validator.DISPATCH_CONTRACT_VERSION,
        "jobId": JOB_ID,
        "envelopeRevision": ENVELOPE_SHA,
        "envelopeSha256": ENVELOPE_HASH,
        "payloadSha256": PAYLOAD_HASH,
        "sourceRevision": SOURCE_SHA,
        "workflowIdentity": dispatch_validator.WORKFLOW_IDENTITY,
        "workflowBlob": dispatch_validator.git_blob_sha(workflow),
        "workflowVersion": dispatch_validator.WORKFLOW_VERSION,
        "trainingImage": dispatch_validator.TRAINING_IMAGE,
        "candidateUpload": False,
        "modelCardUpload": False,
        "datasetUpload": False,
        "receiptsRepoId": dispatch_validator.RECEIPTS_REPOSITORY,
    }
    selection.update(overrides)
    return {"selection": selection}


def _selection_payload(dispatch: dict[str, Any]) -> dict[str, Any]:
    value = dispatch["selection"]
    assert isinstance(value, dict)
    return value


def _owner_binding(dispatch: dict[str, Any]) -> dict[str, Any]:
    selection = _selection_payload(dispatch)
    return {
        "workflowIdentity": selection["workflowIdentity"],
        "workflowBlob": selection["workflowBlob"],
        "workflowVersion": selection["workflowVersion"],
        "trainingImage": selection["trainingImage"],
        "candidateUpload": selection["candidateUpload"],
        "modelCardUpload": selection["modelCardUpload"],
        "datasetUpload": selection["datasetUpload"],
        "receiptsRepoId": selection["receiptsRepoId"],
    }


def _payload(
    dispatch: dict[str, Any],
    *,
    engine_key_id: str,
    engine_spki_sha256: str,
    execution_bridge_revision: str = BRIDGE_SHA,
    lineage_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selection = _selection_payload(dispatch)
    lineage: dict[str, Any] = {
        "predecessorJobId": PREDECESSOR_JOB_ID,
        "predecessorEnvelopeSha256": "0" * 64,
        "predecessorPayloadSha256": "0" * 64,
        "predecessorEnvelopeRevision": PREDECESSOR_ENVELOPE_REVISION,
        "predecessorExecutionBridgeRevision": (
            PREDECESSOR_EXECUTION_REVISION
        ),
        "transportEvidenceUrl": (
            "https://github.com/szl-holdings/a11oy/actions/runs/1"
        ),
        "failurePhase": "PRE_DISPATCH_VALIDATOR_REJECTED",
        "successorGeneration": 16,
        "automaticRetry": False,
        "eventCreated": False,
        "workflowRunCreated": False,
        "claimCreated": False,
        "trainingStarted": False,
        "modelRepositoryCodeImported": False,
        "holdoutsAccessed": False,
        "candidateProduced": False,
        "receiptIntentProduced": False,
        "terminalLedgerWritten": False,
        "scienceInputsReused": True,
    }
    if lineage_overrides:
        lineage.update(lineage_overrides)
    return {
        "jobId": selection["jobId"],
        "source": {
            "repoId": "szl-holdings/a11oy",
            "revision": selection["sourceRevision"],
            "licenseId": "apache-2.0",
        },
        "outputs": {
            "candidateId": "SZL-Nemo-v3-Nemotron-4B-Adapter",
            "private": True,
            "publishCandidate": False,
            "receiptsRepoId": selection["receiptsRepoId"],
        },
        "ownerDispatch": _owner_binding(dispatch),
        "authorization": {
            "coordinationMode": "FINAL_ACTIVE_TRUST_ROOT",
            "correctedBridgeRevision": execution_bridge_revision,
            "cryptographicContinuityClaimed": False,
            "decisionAt": "2026-07-30T16:28:27Z",
            "engineKeyId": engine_key_id,
            "enginePublicKeySpkiSha256": engine_spki_sha256,
            "oldKeyStatus": "VERIFY_ONLY",
            "previousEngineKeyId": "5c6cf59741ade920",
            "provisionalEngineKeyId": "815714c8d4ae3e4d",
            "provisionalKeyStatus": "VERIFY_ONLY",
            "recoveryIssueUrl": (
                "https://github.com/szl-holdings/szl-gpu-bridge/issues/25"
            ),
            "rotationMode": (
                "COORDINATED_FINAL_TRUST_ROOT_NEW_GENERATION"
            ),
            "settledA11oyRelockRunUrl": (
                "https://github.com/szl-holdings/a11oy/actions/runs/1"
            ),
        },
        "lineage": lineage,
    }


def _test_key() -> tuple[Ed25519PrivateKey, str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    spki = dispatch_validator.ED25519_SPKI_PREFIX + public_raw
    spki_base64 = base64.b64encode(spki).decode("ascii")
    key_id = hashlib.sha256(spki).hexdigest()[:16]
    return private_key, spki_base64, key_id


def _signed_envelope_bytes(
    payload: dict[str, Any],
    private_key: Ed25519PrivateKey,
    spki_base64: str,
    key_id: str,
) -> tuple[bytes, str]:
    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    signature = private_key.sign(
        dispatch_validator.dsse_pae(
            dispatch_validator.NEMO_V3_PAYLOAD_TYPE,
            payload_bytes,
        )
    )
    envelope = {
        "payloadType": dispatch_validator.NEMO_V3_PAYLOAD_TYPE,
        "payload": base64.b64encode(payload_bytes).decode("ascii"),
        "signatures": [
            {
                "keyid": key_id,
                "sig": base64.b64encode(signature).decode("ascii"),
            }
        ],
        "publicKeySpkiBase64": spki_base64,
    }
    envelope_bytes = (
        json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return envelope_bytes, hashlib.sha256(payload_bytes).hexdigest()


def _write_envelope(
    bridge_source: Path,
    dispatch: dict[str, Any],
    payload: dict[str, Any],
    private_key: Ed25519PrivateKey,
    spki_base64: str,
    key_id: str,
) -> Path:
    selection = _selection_payload(dispatch)
    envelope_bytes, payload_hash = _signed_envelope_bytes(
        payload,
        private_key,
        spki_base64,
        key_id,
    )
    path = (
        bridge_source
        / "queue"
        / "pending"
        / f"{selection['jobId']}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(envelope_bytes)
    selection["payloadSha256"] = payload_hash
    selection["envelopeSha256"] = hashlib.sha256(envelope_bytes).hexdigest()
    return path


def _write_predecessor_evidence(
    bridge_source: Path,
    dispatch: dict[str, Any],
    private_key: Ed25519PrivateKey,
    spki_base64: str,
    key_id: str,
    *,
    predecessor_execution_revision: str = PREDECESSOR_EXECUTION_REVISION,
) -> tuple[str, str]:
    selection = _selection_payload(dispatch)
    predecessor_payload = _payload(
        dispatch,
        engine_key_id=key_id,
        engine_spki_sha256=hashlib.sha256(
            base64.b64decode(spki_base64, validate=True)
        ).hexdigest(),
        execution_bridge_revision=predecessor_execution_revision,
    )
    predecessor_payload["jobId"] = PREDECESSOR_JOB_ID
    predecessor_payload["source"]["revision"] = PREDECESSOR_SOURCE_SHA
    envelope_bytes, payload_hash = _signed_envelope_bytes(
        predecessor_payload,
        private_key,
        spki_base64,
        key_id,
    )
    envelope_hash = hashlib.sha256(envelope_bytes).hexdigest()
    predecessor_path = (
        bridge_source
        / "queue"
        / "pending"
        / f"{PREDECESSOR_JOB_ID}.json"
    )
    predecessor_path.parent.mkdir(parents=True, exist_ok=True)
    predecessor_path.write_bytes(envelope_bytes)

    quarantine = {
        "kind": "szl-nemo-v3-queue-quarantine",
        "v": 1,
        "jobId": PREDECESSOR_JOB_ID,
        "recordedAt": "2026-07-31T00:30:00Z",
        "status": [
            "STALE_SOURCE",
            "PRE_DISPATCH_VALIDATOR_REJECTED",
            "NEVER_DISPATCH",
        ],
        "queuePath": f"queue/pending/{PREDECESSOR_JOB_ID}.json",
        "queueFileSha256": envelope_hash,
        "signedPayloadSha256": payload_hash,
        "engineKeyId": key_id,
        "sourceRevision": PREDECESSOR_SOURCE_SHA,
        "preserveEnvelope": True,
        "dispatchAuthorized": False,
        "replacement": {
            "sourceRevision": selection["sourceRevision"],
            "workflowBlob": selection["workflowBlob"],
            "workflowVersion": selection["workflowVersion"],
            "settledA11oyRelockRunUrl": (
                "https://github.com/szl-holdings/a11oy/actions/runs/1"
            ),
            "engineKeyId": key_id,
            "enginePublicKeySpkiSha256": hashlib.sha256(
                base64.b64decode(spki_base64, validate=True)
            ).hexdigest(),
            "reviewedJobId": selection["jobId"],
            "successorGeneration": 16,
        },
        "reason": "The predecessor is immutable never-dispatch evidence.",
    }
    quarantine_path = (
        bridge_source
        / "queue"
        / "quarantine"
        / f"{PREDECESSOR_JOB_ID}.json"
    )
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    quarantine_path.write_text(
        json.dumps(quarantine, indent=2) + "\n",
        encoding="utf-8",
    )
    return envelope_hash, payload_hash


def _valid_case(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    dict[str, Any],
    Any,
    Ed25519PrivateKey,
    str,
    str,
]:
    workflow = _workflow(tmp_path)
    bridge_source = tmp_path / "bridge"
    dispatch = _dispatch(workflow)
    private_key, spki_base64, key_id = _test_key()
    predecessor_envelope_hash, predecessor_payload_hash = (
        _write_predecessor_evidence(
            bridge_source,
            dispatch,
            private_key,
            spki_base64,
            key_id,
        )
    )
    _write_envelope(
        bridge_source,
        dispatch,
        _payload(
            dispatch,
            engine_key_id=key_id,
            engine_spki_sha256=hashlib.sha256(
                base64.b64decode(spki_base64, validate=True)
            ).hexdigest(),
            lineage_overrides={
                "predecessorEnvelopeSha256": predecessor_envelope_hash,
                "predecessorPayloadSha256": predecessor_payload_hash,
            },
        ),
        private_key,
        spki_base64,
        key_id,
    )
    selection = dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow,
    )
    return (
        workflow,
        bridge_source,
        dispatch,
        selection,
        private_key,
        spki_base64,
        key_id,
    )


def _verify(
    selection: Any,
    bridge_source: Path,
    spki_base64: str,
    key_id: str,
) -> Any:
    return dispatch_validator.verify_owner_envelope(
        selection,
        envelope_source=bridge_source,
        owner_spki_base64=spki_base64,
        owner_key_id=key_id,
    )


def _quarantine_record_path(
    bridge_source: Path,
    job_id: str = PREDECESSOR_JOB_ID,
) -> Path:
    return bridge_source / "queue" / "quarantine" / f"{job_id}.json"


def _git_executable() -> Path:
    value = shutil.which("git")
    if value is None:
        pytest.skip("git is required for Bridge history contract tests")
    return Path(value)


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        [str(_git_executable()), "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _history_case(
    tmp_path: Path,
) -> tuple[Any, Any, Path, Path, Path]:
    (
        workflow_path,
        envelope_source,
        dispatch,
        _selection,
        private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    shutil.rmtree(envelope_source / "queue")

    _git(envelope_source, "init")
    _git(envelope_source, "config", "user.name", "Contract Test")
    _git(
        envelope_source,
        "config",
        "user.email",
        "contract-test@example.invalid",
    )
    (envelope_source / "predecessor-runtime.py").write_text(
        "print('predecessor runtime')\n",
        encoding="utf-8",
    )
    _git(envelope_source, "add", "predecessor-runtime.py")
    _git(envelope_source, "commit", "-m", "predecessor runtime")
    predecessor_execution_revision = _git(
        envelope_source,
        "rev-parse",
        "HEAD",
    )

    _write_predecessor_evidence(
        envelope_source,
        dispatch,
        private_key,
        spki_base64,
        key_id,
        predecessor_execution_revision=predecessor_execution_revision,
    )
    predecessor_path = (
        envelope_source
        / "queue"
        / "pending"
        / f"{PREDECESSOR_JOB_ID}.json"
    )
    _git(
        envelope_source,
        "add",
        str(predecessor_path.relative_to(envelope_source)),
    )
    _git(envelope_source, "commit", "-m", "publish predecessor envelope")
    predecessor_envelope_revision = _git(
        envelope_source,
        "rev-parse",
        "HEAD",
    )

    (envelope_source / "runtime.py").write_text(
        "print('signed runtime')\n",
        encoding="utf-8",
    )
    _git(envelope_source, "add", "runtime.py")
    _git(envelope_source, "commit", "-m", "current runtime")
    execution_revision = _git(envelope_source, "rev-parse", "HEAD")

    predecessor_envelope_hash, predecessor_payload_hash = (
        _write_predecessor_evidence(
            envelope_source,
            dispatch,
            private_key,
            spki_base64,
            key_id,
            predecessor_execution_revision=predecessor_execution_revision,
        )
    )
    envelope_path = _write_envelope(
        envelope_source,
        dispatch,
        _payload(
            dispatch,
            engine_key_id=key_id,
            engine_spki_sha256=hashlib.sha256(
                base64.b64decode(spki_base64, validate=True)
            ).hexdigest(),
            execution_bridge_revision=execution_revision,
            lineage_overrides={
                "predecessorEnvelopeRevision": (
                    predecessor_envelope_revision
                ),
                "predecessorExecutionBridgeRevision": (
                    predecessor_execution_revision
                ),
                "predecessorEnvelopeSha256": predecessor_envelope_hash,
                "predecessorPayloadSha256": predecessor_payload_hash,
            },
        ),
        private_key,
        spki_base64,
        key_id,
    )
    _git(
        envelope_source,
        "add",
        str(envelope_path.relative_to(envelope_source)),
        (
            "queue/quarantine/"
            f"{PREDECESSOR_JOB_ID}.json"
        ),
    )
    _git(envelope_source, "commit", "-m", "publish envelope")
    envelope_revision = _git(envelope_source, "rev-parse", "HEAD")
    _git(
        envelope_source,
        "remote",
        "add",
        "origin",
        dispatch_validator.BRIDGE_REPOSITORY_URL,
    )
    _git(
        envelope_source,
        "update-ref",
        "refs/remotes/origin/main",
        envelope_revision,
    )

    execution_source = tmp_path / "execution"
    subprocess.run(
        [
            str(_git_executable()),
            "clone",
            "--no-local",
            str(envelope_source),
            str(execution_source),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    _git(execution_source, "checkout", "--detach", execution_revision)

    _selection_payload(dispatch)["envelopeRevision"] = envelope_revision
    selection = dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow_path,
    )
    evidence = _verify(
        selection,
        envelope_source,
        spki_base64,
        key_id,
    )
    assert evidence.execution_bridge_revision == execution_revision
    return (
        selection,
        evidence,
        envelope_source,
        execution_source,
        _git_executable(),
    )


def test_active_owner_key_pin_is_exact_and_self_authenticating() -> None:
    spki = base64.b64decode(ACTIVE_OWNER_SPKI_BASE64, validate=True)

    assert dispatch_validator.OWNER_KEY_ID == ACTIVE_OWNER_KEY_ID
    assert (
        dispatch_validator.OWNER_PUBLIC_KEY_SPKI_BASE64
        == ACTIVE_OWNER_SPKI_BASE64
    )
    assert spki.startswith(dispatch_validator.ED25519_SPKI_PREFIX)
    assert len(spki) == len(dispatch_validator.ED25519_SPKI_PREFIX) + 32
    assert hashlib.sha256(spki).hexdigest() == ACTIVE_OWNER_SPKI_SHA256
    assert ACTIVE_OWNER_SPKI_SHA256[:16] == ACTIVE_OWNER_KEY_ID


def test_valid_attempt_16_dispatch_verifies_exact_generic_replacement(
    tmp_path: Path,
) -> None:
    (
        _workflow_path,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)

    evidence = _verify(selection, bridge_source, spki_base64, key_id)

    assert evidence.job_id == JOB_ID
    assert evidence.envelope_revision == ENVELOPE_SHA
    assert evidence.execution_bridge_revision == BRIDGE_SHA
    assert evidence.execution_bridge_revision != evidence.envelope_revision
    assert evidence.source_revision == SOURCE_SHA
    assert evidence.envelope_sha256 == selection.envelope_sha256
    assert evidence.payload_sha256 == selection.payload_sha256
    assert evidence.workflow_blob == selection.workflow_blob
    assert evidence.engine_key_id == key_id
    assert Path(evidence.envelope_path).name == f"{JOB_ID}.json"
    assert evidence.predecessor_job_id == PREDECESSOR_JOB_ID
    assert (
        evidence.predecessor_envelope_revision
        == PREDECESSOR_ENVELOPE_REVISION
    )
    assert (
        evidence.predecessor_execution_bridge_revision
        == PREDECESSOR_EXECUTION_REVISION
    )
    assert evidence.predecessor_queue_path == (
        f"queue/pending/{PREDECESSOR_JOB_ID}.json"
    )


def test_signed_runtime_is_distinct_protected_bridge_history(
    tmp_path: Path,
) -> None:
    (
        selection,
        evidence,
        envelope_source,
        execution_source,
        git_executable,
    ) = _history_case(tmp_path)

    dispatch_validator.verify_bridge_history(
        selection,
        evidence,
        envelope_source=envelope_source,
        execution_source=execution_source,
        remote_main=selection.envelope_revision,
        git_executable=git_executable,
    )

    assert evidence.execution_bridge_revision != selection.envelope_revision


@pytest.mark.parametrize("dirty_checkout", ["envelope", "execution"])
def test_dirty_bridge_checkout_is_rejected(
    tmp_path: Path,
    dirty_checkout: str,
) -> None:
    (
        selection,
        evidence,
        envelope_source,
        execution_source,
        git_executable,
    ) = _history_case(tmp_path)
    target = (
        envelope_source
        if dirty_checkout == "envelope"
        else execution_source
    )
    (target / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match=f"{dirty_checkout} Bridge checkout is dirty",
    ):
        dispatch_validator.verify_bridge_history(
            selection,
            evidence,
            envelope_source=envelope_source,
            execution_source=execution_source,
            remote_main=selection.envelope_revision,
            git_executable=git_executable,
        )


def test_unprotected_signed_runtime_revision_is_rejected(
    tmp_path: Path,
) -> None:
    (
        selection,
        evidence,
        envelope_source,
        _execution_source,
        git_executable,
    ) = _history_case(tmp_path)
    rogue_source = tmp_path / "rogue"
    rogue_source.mkdir()
    _git(rogue_source, "init")
    _git(rogue_source, "config", "user.name", "Contract Test")
    _git(
        rogue_source,
        "config",
        "user.email",
        "contract-test@example.invalid",
    )
    (rogue_source / "rogue.py").write_text(
        "print('unprotected')\n",
        encoding="utf-8",
    )
    _git(rogue_source, "add", "rogue.py")
    _git(rogue_source, "commit", "-m", "unprotected runtime")
    rogue_revision = _git(rogue_source, "rev-parse", "HEAD")
    _git(
        envelope_source,
        "fetch",
        str(rogue_source),
        rogue_revision,
    )
    rogue_evidence = dataclasses.replace(
        evidence,
        execution_bridge_revision=rogue_revision,
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="merge-base --is-ancestor",
    ):
        dispatch_validator.verify_bridge_history(
            selection,
            rogue_evidence,
            envelope_source=envelope_source,
            execution_source=rogue_source,
            remote_main=selection.envelope_revision,
            git_executable=git_executable,
        )


def test_unprotected_predecessor_runtime_revision_is_rejected(
    tmp_path: Path,
) -> None:
    (
        selection,
        evidence,
        envelope_source,
        execution_source,
        git_executable,
    ) = _history_case(tmp_path)
    rogue_source = tmp_path / "rogue-predecessor"
    rogue_source.mkdir()
    _git(rogue_source, "init")
    _git(rogue_source, "config", "user.name", "Contract Test")
    _git(
        rogue_source,
        "config",
        "user.email",
        "contract-test@example.invalid",
    )
    (rogue_source / "rogue.py").write_text(
        "print('unprotected predecessor')\n",
        encoding="utf-8",
    )
    _git(rogue_source, "add", "rogue.py")
    _git(rogue_source, "commit", "-m", "unprotected predecessor")
    rogue_revision = _git(rogue_source, "rev-parse", "HEAD")
    _git(
        envelope_source,
        "fetch",
        str(rogue_source),
        rogue_revision,
    )
    rogue_evidence = dataclasses.replace(
        evidence,
        predecessor_execution_bridge_revision=rogue_revision,
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="merge-base --is-ancestor",
    ):
        dispatch_validator.verify_bridge_history(
            selection,
            rogue_evidence,
            envelope_source=envelope_source,
            execution_source=execution_source,
            remote_main=selection.envelope_revision,
            git_executable=git_executable,
        )


def test_mutable_protected_main_or_verified_path_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    (
        selection,
        evidence,
        envelope_source,
        execution_source,
        git_executable,
    ) = _history_case(tmp_path)

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="immutable full lowercase Git SHA",
    ):
        dispatch_validator.verify_bridge_history(
            selection,
            evidence,
            envelope_source=envelope_source,
            execution_source=execution_source,
            remote_main="main",
            git_executable=git_executable,
        )

    mismatched = dataclasses.replace(
        evidence,
        envelope_path=str(execution_source / "unverified.json"),
    )
    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="verified envelope path is absent",
    ):
        dispatch_validator.verify_bridge_history(
            selection,
            mismatched,
            envelope_source=envelope_source,
            execution_source=execution_source,
            remote_main=selection.envelope_revision,
            git_executable=git_executable,
        )


def test_retired_owner_key_is_rejected_by_default(tmp_path: Path) -> None:
    (
        _workflow_path,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        _spki_base64,
        _key_id,
    ) = _valid_case(tmp_path)
    envelope_path = (
        bridge_source / "queue" / "pending" / f"{JOB_ID}.json"
    )
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    envelope["publicKeySpkiBase64"] = RETIRED_OWNER_SPKI_BASE64
    envelope["signatures"][0]["keyid"] = RETIRED_OWNER_KEY_ID
    envelope_bytes = (
        json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    envelope_path.write_bytes(envelope_bytes)
    selection = dispatch_validator.DispatchSelection(
        **{
            **selection.__dict__,
            "envelope_sha256": hashlib.sha256(envelope_bytes).hexdigest(),
        }
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="public key is not the pinned owner key",
    ):
        dispatch_validator.verify_owner_envelope(
            selection,
            envelope_source=bridge_source,
        )


def test_transport_v3_uses_one_exact_top_level_property(tmp_path: Path) -> None:
    dispatch = _dispatch(_workflow(tmp_path))

    assert set(dispatch) == dispatch_validator._CLIENT_PAYLOAD_FIELDS
    assert len(dispatch) == 1
    assert (
        len(dispatch)
        <= dispatch_validator.GITHUB_CLIENT_PAYLOAD_PROPERTY_LIMIT
        == 10
    )
    assert (
        set(_selection_payload(dispatch))
        == dispatch_validator._SELECTION_FIELDS
    )


@pytest.mark.parametrize(
    "job_id",
    sorted(dispatch_validator.QUARANTINED_JOB_IDS),
)
def test_all_stale_attempt_ids_are_never_dispatchable(
    tmp_path: Path,
    job_id: str,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow, jobId=job_id)

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="quarantined or stale governed attempt",
    ):
        dispatch_validator.validate_dispatch(
            dispatch,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


@pytest.mark.parametrize("missing", sorted(dispatch_validator._SELECTION_FIELDS))
def test_missing_dispatch_field_fails_closed(
    tmp_path: Path,
    missing: str,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    _selection_payload(dispatch).pop(missing)

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="missing required fields",
    ):
        dispatch_validator.validate_dispatch(
            dispatch,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


def test_extra_dispatch_field_fails_closed(tmp_path: Path) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow, surprise="not admitted")

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="unsupported fields",
    ):
        dispatch_validator.validate_dispatch(
            dispatch,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


def test_legacy_direct_v2_payload_fails_closed(tmp_path: Path) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    legacy = _selection_payload(dispatch)
    legacy["contractVersion"] = "szl-nemo-owner-dispatch.v2"
    legacy["workflowVersion"] = "nemo-v3-owner-dispatch.v2"

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="repository-dispatch property limit",
    ):
        dispatch_validator.validate_dispatch(
            legacy,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "selection",
        {},
        {"selection": []},
        {"selection": {}, "extra": "not admitted"},
    ],
)
def test_wrong_wrapper_shape_fails_closed(
    tmp_path: Path,
    payload: Any,
) -> None:
    workflow = _workflow(tmp_path)

    with pytest.raises(dispatch_validator.DispatchValidationError):
        dispatch_validator.validate_dispatch(
            payload,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


def test_transport_over_github_property_limit_fails_closed(
    tmp_path: Path,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    dispatch.update({f"extra{index}": index for index in range(10)})

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="repository-dispatch property limit",
    ):
        dispatch_validator.validate_dispatch(
            dispatch,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"contractVersion": "szl-nemo-owner-dispatch.v2"},
            "version is not admitted",
        ),
        (
            {"contractVersion": "szl-nemo-owner-dispatch.v99"},
            "version is not admitted",
        ),
        (
            {"workflowVersion": "nemo-v3-owner-dispatch.v2"},
            "version is not admitted",
        ),
        ({"contractVersion": 3}, "version is not admitted"),
        ({"jobId": 4}, "non-empty string"),
        (
            {"jobId": next(iter(dispatch_validator.QUARANTINED_JOB_IDS))},
            "quarantined or stale governed attempt",
        ),
        ({"jobId": "../attempt-2"}, "new governed attempt"),
        ({"envelopeRevision": "main"}, "immutable full lowercase Git SHA"),
        ({"envelopeSha256": None}, "lowercase SHA-256 hex"),
        ({"payloadSha256": []}, "lowercase SHA-256 hex"),
        (
            {
                "envelopeRevision": (
                    next(iter(dispatch_validator.QUARANTINED_BRIDGE_REVISIONS))
                )
            },
            "quarantined Bridge revision",
        ),
        ({"sourceRevision": "e" * 40}, "does not equal github.sha"),
        ({"workflowBlob": "f" * 40}, "does not match checked-out bytes"),
        ({"workflowIdentity": "owner/repo/workflow@main"}, "workflow identity"),
        ({"workflowVersion": "mutable"}, "version is not admitted"),
        ({"trainingImage": "unsloth/unsloth:latest"}, "immutable approved"),
        ({"candidateUpload": True}, "candidateUpload must remain false"),
        ({"candidateUpload": 0}, "candidateUpload must remain false"),
        ({"modelCardUpload": True}, "modelCardUpload must remain false"),
        ({"datasetUpload": True}, "datasetUpload must remain false"),
        ({"receiptsRepoId": "SZLHOLDINGS/other"}, "not admitted"),
        ({"receiptsRepoId": []}, "not admitted"),
    ],
)
def test_malformed_or_weakened_dispatch_fails_closed(
    tmp_path: Path,
    overrides: dict[str, Any],
    message: str,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow, **overrides)

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match=message,
    ):
        dispatch_validator.validate_dispatch(
            dispatch,
            github_sha=SOURCE_SHA,
            workflow_path=workflow,
        )


def _resign_mutated_payload(
    *,
    bridge_source: Path,
    dispatch: dict[str, Any],
    private_key: Ed25519PrivateKey,
    spki_base64: str,
    key_id: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    envelope_path = (
        bridge_source / "queue" / "pending" / f"{JOB_ID}.json"
    )
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    payload = json.loads(
        base64.b64decode(envelope["payload"], validate=True).decode("utf-8")
    )
    mutate(payload)
    _write_envelope(
        bridge_source,
        dispatch,
        payload,
        private_key,
        spki_base64,
        key_id,
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["source"].update({"revision": "e" * 40}),
            "source revision",
        ),
        (
            lambda payload: payload["ownerDispatch"].update(
                {"workflowBlob": "f" * 40}
            ),
            "protected workflow and output boundary",
        ),
        (
            lambda payload: payload["ownerDispatch"].update(
                {"trainingImage": "unsloth/unsloth:latest"}
            ),
            "protected workflow and output boundary",
        ),
        (
            lambda payload: payload["ownerDispatch"].update(
                {"candidateUpload": True}
            ),
            "protected workflow and output boundary",
        ),
        (
            lambda payload: payload["ownerDispatch"].update(
                {"modelCardUpload": True}
            ),
            "protected workflow and output boundary",
        ),
        (
            lambda payload: payload["ownerDispatch"].update(
                {"datasetUpload": True}
            ),
            "protected workflow and output boundary",
        ),
        (
            lambda payload: payload["ownerDispatch"].update(
                {"receiptsRepoId": "SZLHOLDINGS/other"}
            ),
            "protected workflow and output boundary",
        ),
        (
            lambda payload: payload["outputs"].update(
                {"publishCandidate": True}
            ),
            "candidate publication boundary",
        ),
        (
            lambda payload: payload["outputs"].update(
                {"receiptsRepoId": "SZLHOLDINGS/other"}
            ),
            "receipt repository",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"predecessorJobId": "job-2026-nemo-v3-governed-attempt-9"}
            ),
            "immediately preceding attempt",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"predecessorJobId": "job-2026-nemo-v3-governed-attempt-4"}
            ),
            "immediately preceding attempt",
        ),
        (
            lambda payload: payload["lineage"].pop("predecessorJobId"),
            "missing required fields",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"predecessorEnvelopeSha256": "3" * 64}
            ),
            "hashes do not match immutable quarantine evidence",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"predecessorPayloadSha256": "4" * 64}
            ),
            "hashes do not match immutable quarantine evidence",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"successorGeneration": 6}
            ),
            "generation does not match",
        ),
        (
            lambda payload: payload["lineage"].update({"automaticRetry": True}),
            "cannot retry or replace science inputs",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"scienceInputsReused": False}
            ),
            "cannot retry or replace science inputs",
        ),
        (
            lambda payload: payload["lineage"].update(
                {"unexpected": "not admitted"}
            ),
            "unsupported fields",
        ),
        (
            lambda payload: payload["authorization"].update(
                {"correctedBridgeRevision": "main"}
            ),
            "immutable full lowercase Git SHA",
        ),
        (
            lambda payload: payload["authorization"].update(
                {"correctedBridgeRevision": ENVELOPE_SHA}
            ),
            "envelope publication revision must remain data-only",
        ),
        (
            lambda payload: payload["authorization"].update(
                {
                    "correctedBridgeRevision": next(
                        iter(
                            dispatch_validator.QUARANTINED_BRIDGE_REVISIONS
                        )
                    )
                }
            ),
            "quarantined Bridge runtime revision",
        ),
        (
            lambda payload: payload["authorization"].update(
                {"engineKeyId": "0" * 16}
            ),
            "engine identity",
        ),
        (
            lambda payload: payload["authorization"].update(
                {"enginePublicKeySpkiSha256": "0" * 64}
            ),
            "engine identity",
        ),
        (
            lambda payload: payload["authorization"].update(
                {"settledA11oyRelockRunUrl": "main"}
            ),
            "relock must be an immutable A11oy workflow run URL",
        ),
        (
            lambda payload: payload["authorization"].update(
                {"extraAuthority": "forbidden"}
            ),
            "unsupported fields",
        ),
    ],
)
def test_signed_envelope_binding_regressions_fail_closed(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    (
        workflow,
        bridge_source,
        dispatch,
        _selection,
        private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    _resign_mutated_payload(
        bridge_source=bridge_source,
        dispatch=dispatch,
        private_key=private_key,
        spki_base64=spki_base64,
        key_id=key_id,
        mutate=mutate,
    )
    selection = dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow,
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match=message,
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda record: record.update(
                {"status": ["PRE_DISPATCH_VALIDATOR_REJECTED"]}
            ),
            "status must be unique and NEVER_DISPATCH",
        ),
        (
            lambda record: record.update({"dispatchAuthorized": True}),
            "not immutable dispatch denial",
        ),
        (
            lambda record: record["replacement"].update(
                {"reviewedJobId": "job-2026-nemo-v3-governed-attempt-8"}
            ),
            "replacement does not bind this successor",
        ),
        (
            lambda record: record["replacement"].update(
                {"sourceRevision": "7" * 40}
            ),
            "replacement does not bind this successor",
        ),
        (
            lambda record: record["replacement"].update(
                {"workflowBlob": "6" * 40}
            ),
            "replacement does not bind this successor",
        ),
        (
            lambda record: record["replacement"].update(
                {"workflowVersion": "nemo-v3-owner-dispatch.v3"}
            ),
            "replacement does not bind this successor",
        ),
        (
            lambda record: record["replacement"].update(
                {
                    "settledA11oyRelockRunUrl": (
                        "https://github.com/szl-holdings/a11oy/actions/runs/2"
                    )
                }
            ),
            "replacement does not bind this successor",
        ),
        (
            lambda record: record["replacement"].update(
                {"settledA11oyRelockRunUrl": "main"}
            ),
            "relock must be an immutable A11oy workflow run URL",
        ),
        (
            lambda record: record["replacement"].update(
                {"successorGeneration": 17}
            ),
            "does not bind the immediate successor",
        ),
        (
            lambda record: record["replacement"].update(
                {"successorGeneration": True}
            ),
            "does not bind the immediate successor",
        ),
        (
            lambda record: record["replacement"].pop("workflowVersion"),
            "missing required fields",
        ),
        (
            lambda record: record["replacement"].pop(
                "settledA11oyRelockRunUrl"
            ),
            "missing required fields",
        ),
        (
            lambda record: record["replacement"].pop("successorGeneration"),
            "missing required fields",
        ),
        (
            lambda record: record["replacement"].update(
                {"ignoredAuthority": "forbidden"}
            ),
            "unsupported fields",
        ),
        (
            lambda record: record.update({"queueFileSha256": "5" * 64}),
            "hashes do not match immutable quarantine evidence",
        ),
        (
            lambda record: record.update({"sourceRevision": "8" * 40}),
            "source does not match its record",
        ),
        (
            lambda record: record.update({"v": True}),
            "not immutable dispatch denial",
        ),
    ],
)
def test_predecessor_quarantine_tampering_fails_closed(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    (
        _workflow,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    quarantine_path = _quarantine_record_path(bridge_source)
    record = json.loads(quarantine_path.read_text(encoding="utf-8"))
    mutate(record)
    quarantine_path.write_text(
        json.dumps(record, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match=message,
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


def test_duplicate_predecessor_replacement_field_fails_closed(
    tmp_path: Path,
) -> None:
    (
        _workflow,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    quarantine_path = _quarantine_record_path(bridge_source)
    record = json.loads(quarantine_path.read_text(encoding="utf-8"))
    serialized = json.dumps(record, separators=(",", ":"))
    field = (
        '"workflowVersion":"'
        + dispatch_validator.WORKFLOW_VERSION
        + '"'
    )
    assert serialized.count(field) == 1
    quarantine_path.write_text(
        serialized.replace(field, f"{field},{field}", 1),
        encoding="utf-8",
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="duplicate JSON field: workflowVersion",
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


def test_missing_predecessor_or_quarantined_current_attempt_fails_closed(
    tmp_path: Path,
) -> None:
    (
        _workflow,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    quarantine_path = _quarantine_record_path(bridge_source)
    preserved_record = quarantine_path.read_bytes()
    quarantine_path.unlink()

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="no immutable quarantine record",
    ):
        _verify(selection, bridge_source, spki_base64, key_id)

    quarantine_path.write_bytes(preserved_record)
    _quarantine_record_path(bridge_source, JOB_ID).write_bytes(
        preserved_record
    )
    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="current governed attempt already has a quarantine record",
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


def test_mutated_predecessor_envelope_fails_closed(
    tmp_path: Path,
) -> None:
    (
        _workflow,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    predecessor_path = (
        bridge_source
        / "queue"
        / "pending"
        / f"{PREDECESSOR_JOB_ID}.json"
    )
    predecessor_path.write_bytes(predecessor_path.read_bytes() + b" ")

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="envelope bytes do not match lineage",
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


def test_wrong_owner_signature_fails_closed(tmp_path: Path) -> None:
    (
        workflow,
        bridge_source,
        dispatch,
        _selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    envelope_path = (
        bridge_source / "queue" / "pending" / f"{JOB_ID}.json"
    )
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    signature = bytearray(base64.b64decode(envelope["signatures"][0]["sig"]))
    signature[0] ^= 1
    envelope["signatures"][0]["sig"] = base64.b64encode(signature).decode(
        "ascii"
    )
    envelope_bytes = (
        json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    envelope_path.write_bytes(envelope_bytes)
    _selection_payload(dispatch)["envelopeSha256"] = hashlib.sha256(
        envelope_bytes
    ).hexdigest()
    selection = dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow,
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="signature verification failed",
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("envelopeSha256", "envelope bytes"),
        ("payloadSha256", "payload bytes"),
    ],
)
def test_exact_hash_mismatch_fails_closed(
    tmp_path: Path,
    field: str,
    message: str,
) -> None:
    (
        workflow,
        bridge_source,
        dispatch,
        _selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    _selection_payload(dispatch)[field] = "0" * 64
    selection = dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow,
    )

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match=message,
    ):
        _verify(selection, bridge_source, spki_base64, key_id)


def test_envelope_path_must_be_regular_and_job_controlled(
    tmp_path: Path,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    selection = dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow,
    )
    bridge_source = tmp_path / "bridge"
    envelope_directory = (
        bridge_source / "queue" / "pending" / f"{JOB_ID}.json"
    )
    envelope_directory.mkdir(parents=True)

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="regular non-symlink",
    ):
        dispatch_validator.verify_owner_envelope(
            selection,
            envelope_source=bridge_source,
        )


def test_atomic_claim_rejects_replay_without_overwrite(tmp_path: Path) -> None:
    (
        _workflow_path,
        bridge_source,
        _dispatch_payload,
        selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    evidence = _verify(selection, bridge_source, spki_base64, key_id)
    bridge_root = tmp_path / "owner-runtime"

    claim_path = dispatch_validator.create_new_claim(
        selection,
        evidence,
        bridge_root=bridge_root,
        run_id="123",
        run_attempt="1",
    )
    original = claim_path.read_bytes()
    claim = json.loads(original)
    assert claim["jobId"] == JOB_ID
    assert claim["bridgeRevision"] == BRIDGE_SHA
    assert claim["executionBridgeRevision"] == BRIDGE_SHA
    assert claim["envelopeRevision"] == ENVELOPE_SHA
    assert claim["dispatchedRevision"] == SOURCE_SHA
    assert claim["envelopeSha256"] == selection.envelope_sha256
    assert claim["payloadSha256"] == selection.payload_sha256

    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="already claimed",
    ):
        dispatch_validator.create_new_claim(
            selection,
            evidence,
            bridge_root=bridge_root,
            run_id="124",
            run_attempt="2",
        )
    assert claim_path.read_bytes() == original


def test_strict_json_rejects_duplicate_fields() -> None:
    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="duplicate JSON field",
    ):
        dispatch_validator.strict_json_loads(
            '{"jobId":"one","jobId":"two"}',
            "fixture",
        )


@pytest.mark.parametrize(
    "raw",
    [
        '{"selection":{},"selection":{}}',
        '{"selection":{"jobId":"one","jobId":"two"}}',
    ],
)
def test_strict_json_rejects_duplicate_wrapper_or_selection_fields(
    raw: str,
) -> None:
    with pytest.raises(
        dispatch_validator.DispatchValidationError,
        match="duplicate JSON field",
    ):
        dispatch_validator.strict_json_loads(raw, "fixture")


def test_selection_does_not_mutate_input(tmp_path: Path) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    before = copy.deepcopy(dispatch)

    dispatch_validator.validate_dispatch(
        dispatch,
        github_sha=SOURCE_SHA,
        workflow_path=workflow,
    )

    assert dispatch == before


def test_select_cli_writes_only_validated_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    github_env = tmp_path / "github.env"
    monkeypatch.setenv("OWNER_DISPATCH_V3_JSON", json.dumps(dispatch))

    result = dispatch_validator.main(
        [
            "select",
            "--dispatch-json-env",
            "OWNER_DISPATCH_V3_JSON",
            "--github-sha",
            SOURCE_SHA,
            "--workflow-path",
            str(workflow),
            "--workflow-blob",
            _selection_payload(dispatch)["workflowBlob"],
            "--github-env",
            str(github_env),
        ]
    )

    assert result == 0
    lines = github_env.read_text(encoding="utf-8").splitlines()
    assert lines == [
        f"JOB_ID={JOB_ID}",
        f"ENVELOPE_REVISION={ENVELOPE_SHA}",
        f"EXPECTED_ENVELOPE_SHA256={ENVELOPE_HASH}",
        f"EXPECTED_PAYLOAD_SHA256={PAYLOAD_HASH}",
        (
            "EXPECTED_WORKFLOW_BLOB="
            f"{_selection_payload(dispatch)['workflowBlob']}"
        ),
    ]


def test_verify_cli_writes_only_signed_execution_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        workflow,
        envelope_source,
        dispatch,
        _selection,
        _private_key,
        spki_base64,
        key_id,
    ) = _valid_case(tmp_path)
    github_env = tmp_path / "verified.env"
    monkeypatch.setenv("OWNER_DISPATCH_V3_JSON", json.dumps(dispatch))
    monkeypatch.setattr(dispatch_validator, "OWNER_KEY_ID", key_id)
    monkeypatch.setattr(
        dispatch_validator,
        "OWNER_PUBLIC_KEY_SPKI_BASE64",
        spki_base64,
    )

    result = dispatch_validator.main(
        [
            "verify-envelope",
            "--dispatch-json-env",
            "OWNER_DISPATCH_V3_JSON",
            "--github-sha",
            SOURCE_SHA,
            "--workflow-path",
            str(workflow),
            "--workflow-blob",
            _selection_payload(dispatch)["workflowBlob"],
            "--envelope-source",
            str(envelope_source),
            "--github-env",
            str(github_env),
        ]
    )

    assert result == 0
    lines = github_env.read_text(encoding="utf-8").splitlines()
    assert lines == [
        f"EXECUTION_BRIDGE_REVISION={BRIDGE_SHA}",
        f"ENGINE_KEY_ID={key_id}",
        (
            "VERIFIED_ENVELOPE_PATH="
            f"{envelope_source.resolve() / 'queue' / 'pending' / (JOB_ID + '.json')}"
        ),
    ]


def test_select_cli_rejects_missing_payload_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _workflow(tmp_path)
    monkeypatch.delenv("OWNER_DISPATCH_V3_JSON", raising=False)

    result = dispatch_validator.main(
        [
            "select",
            "--dispatch-json-env",
            "OWNER_DISPATCH_V3_JSON",
            "--github-sha",
            SOURCE_SHA,
            "--workflow-path",
            str(workflow),
            "--workflow-blob",
            dispatch_validator.git_blob_sha(workflow),
            "--github-env",
            str(tmp_path / "github.env"),
        ]
    )

    assert result == 2
