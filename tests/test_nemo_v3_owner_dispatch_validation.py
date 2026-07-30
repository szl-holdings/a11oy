from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
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
ENVELOPE_HASH = "c" * 64
PAYLOAD_HASH = "d" * 64
JOB_ID = "job-2026-nemo-v3-governed-attempt-2"
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
    payload: dict[str, Any] = {
        "contractVersion": dispatch_validator.DISPATCH_CONTRACT_VERSION,
        "jobId": JOB_ID,
        "bridgeRevision": BRIDGE_SHA,
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
    payload.update(overrides)
    return payload


def _owner_binding(dispatch: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflowIdentity": dispatch["workflowIdentity"],
        "workflowBlob": dispatch["workflowBlob"],
        "workflowVersion": dispatch["workflowVersion"],
        "trainingImage": dispatch["trainingImage"],
        "candidateUpload": dispatch["candidateUpload"],
        "modelCardUpload": dispatch["modelCardUpload"],
        "datasetUpload": dispatch["datasetUpload"],
        "receiptsRepoId": dispatch["receiptsRepoId"],
    }


def _payload(dispatch: dict[str, Any]) -> dict[str, Any]:
    return {
        "jobId": dispatch["jobId"],
        "source": {
            "repoId": "szl-holdings/a11oy",
            "revision": dispatch["sourceRevision"],
            "licenseId": "apache-2.0",
        },
        "outputs": {
            "candidateId": "SZL-Nemo-v3-Nemotron-4B-Adapter",
            "private": True,
            "publishCandidate": False,
            "receiptsRepoId": dispatch["receiptsRepoId"],
        },
        "ownerDispatch": _owner_binding(dispatch),
        "lineage": {
            "predecessorJobId": dispatch_validator.QUARANTINED_JOB_ID,
            "automaticRetry": False,
        },
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


def _write_envelope(
    bridge_source: Path,
    dispatch: dict[str, Any],
    payload: dict[str, Any],
    private_key: Ed25519PrivateKey,
    spki_base64: str,
    key_id: str,
) -> Path:
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
    path = (
        bridge_source
        / "queue"
        / "pending"
        / f"{dispatch['jobId']}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(envelope_bytes)
    dispatch["payloadSha256"] = hashlib.sha256(payload_bytes).hexdigest()
    dispatch["envelopeSha256"] = hashlib.sha256(envelope_bytes).hexdigest()
    return path


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
    _write_envelope(
        bridge_source,
        dispatch,
        _payload(dispatch),
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
        bridge_source=bridge_source,
        owner_spki_base64=spki_base64,
        owner_key_id=key_id,
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


def test_valid_owner_dispatch_verifies_exact_signature_and_hashes(
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
    assert evidence.bridge_revision == BRIDGE_SHA
    assert evidence.source_revision == SOURCE_SHA
    assert evidence.envelope_sha256 == selection.envelope_sha256
    assert evidence.payload_sha256 == selection.payload_sha256
    assert evidence.workflow_blob == selection.workflow_blob


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
            bridge_source=bridge_source,
        )


@pytest.mark.parametrize("missing", sorted(dispatch_validator._DISPATCH_FIELDS))
def test_missing_dispatch_field_fails_closed(
    tmp_path: Path,
    missing: str,
) -> None:
    workflow = _workflow(tmp_path)
    dispatch = _dispatch(workflow)
    dispatch.pop(missing)

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


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"jobId": dispatch_validator.QUARANTINED_JOB_ID},
            "new governed attempt",
        ),
        ({"jobId": "../attempt-2"}, "new governed attempt"),
        ({"bridgeRevision": "main"}, "immutable full lowercase Git SHA"),
        (
            {
                "bridgeRevision": (
                    dispatch_validator.QUARANTINED_BRIDGE_REVISION
                )
            },
            "quarantined attempt-1 bridge revision",
        ),
        ({"sourceRevision": "e" * 40}, "does not equal github.sha"),
        ({"workflowBlob": "f" * 40}, "does not match checked-out bytes"),
        ({"workflowIdentity": "owner/repo/workflow@main"}, "workflow identity"),
        ({"workflowVersion": "mutable"}, "version is not admitted"),
        ({"trainingImage": "unsloth/unsloth:latest"}, "immutable approved"),
        ({"candidateUpload": True}, "candidateUpload must remain false"),
        ({"modelCardUpload": True}, "modelCardUpload must remain false"),
        ({"datasetUpload": True}, "datasetUpload must remain false"),
        ({"receiptsRepoId": "SZLHOLDINGS/other"}, "not admitted"),
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
    payload = _payload(dispatch)
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
            "retired attempt",
        ),
        (
            lambda payload: payload["lineage"].update({"automaticRetry": True}),
            "retired attempt",
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
    dispatch["envelopeSha256"] = hashlib.sha256(envelope_bytes).hexdigest()
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
    dispatch[field] = "0" * 64
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
            bridge_source=bridge_source,
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
    monkeypatch.setenv("OWNER_DISPATCH_JSON", json.dumps(dispatch))

    result = dispatch_validator.main(
        [
            "select",
            "--dispatch-json-env",
            "OWNER_DISPATCH_JSON",
            "--github-sha",
            SOURCE_SHA,
            "--workflow-path",
            str(workflow),
            "--workflow-blob",
            dispatch["workflowBlob"],
            "--github-env",
            str(github_env),
        ]
    )

    assert result == 0
    lines = github_env.read_text(encoding="utf-8").splitlines()
    assert lines == [
        f"JOB_ID={JOB_ID}",
        f"BRIDGE_REVISION={BRIDGE_SHA}",
        f"EXPECTED_ENVELOPE_SHA256={ENVELOPE_HASH}",
        f"EXPECTED_PAYLOAD_SHA256={PAYLOAD_HASH}",
        f"EXPECTED_WORKFLOW_BLOB={dispatch['workflowBlob']}",
    ]


def test_select_cli_rejects_missing_payload_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _workflow(tmp_path)
    monkeypatch.delenv("OWNER_DISPATCH_JSON", raising=False)

    result = dispatch_validator.main(
        [
            "select",
            "--dispatch-json-env",
            "OWNER_DISPATCH_JSON",
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
