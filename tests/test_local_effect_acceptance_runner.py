# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pure offline acceptance contracts; no application import or external service."""

import base64
import copy
import hashlib
import importlib.util
import json
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "isolated_acceptance_contract_under_test",
    ROOT / "tools/readiness-harness/local_effect_acceptance.py",
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def baseline():
    rows = [
        {"path": runner.PREFIX + path, "result": "PASS", "statusCode": 200}
        for path in runner.ROUTES
    ]
    rows[3].update(
        result="UNAVAILABLE", statusCode=401, effectState="REFUSED_BEFORE_ROUTE",
        semantic={"authorizationRefused": True},
        before={"policy_decisions": 0, "forum_events": 0},
        after={"policy_decisions": 0, "forum_events": 0},
    )
    return rows


def offline_case():
    payload = {"task": "Describe the local test boundary.", "model_id": "__rehearsal_no_model__"}
    completion = {
        "state": "UNAVAILABLE", "requested_model_id": payload["model_id"],
        "complete": False, "model_qualified": False, "n_complete_steps": 0,
        "n_steps": 2,
        "reasons": ["SELECTED_MODEL_GENERATION_NOT_OBSERVED", "SELF_EVAL_INCOMPLETE_OR_UNAVAILABLE"],
    }
    step = {
        "mode": "chat", "sandbox": False, "state_changing": False,
        "retries": 0, "attempts": [{}],
        "final": {
            "engine": {
                "executed": False, "execution_status": "NOT_REQUESTED",
                "backend": {"backend": "local-deterministic", "configured": False, "offline": True},
            },
            "eval": {
                "honesty_label": "UNAVAILABLE", "accuracy": None, "receipt_signed": False,
                "evidence": {"aggregate": {
                    "n_cases": 8, "n_evaluated": 0, "n_unavailable": 8,
                    "accuracy": None, "model_qualified": False, "execution_complete": False,
                }},
            },
        },
    }
    body = {
        "orchestration_complete": True, "ok": False, "task": payload["task"],
        "mode": "chat", "brain_consulted": False, "energy_allocated": False,
        "run_id": "run-local-test", "completion": completion,
        "steps": [copy.deepcopy(step), copy.deepcopy(step)],
        "forum_ingest": {"ingested": True},
        "composite_receipt": {"body": {
            **payload, "run_id": "run-local-test", "completion": copy.deepcopy(completion),
        }},
    }
    return body, {"policy_decisions": 1, "forum_events": 5}, {"policy_decisions": 1, "forum_events": 8}, payload


def signed_composite(private=None, *, raw_payload=None):
    private = private or ec.generate_private_key(ec.SECP256R1())
    pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(pem.strip()).hexdigest()
    body = {"task": "local fixture", "run_id": "run-test", "model_id": "unavailable-test-model"}
    identity = {
        "keyid": fingerprint, "key_fingerprint_sha256": fingerprint,
        "key_scope": "PROCESS_BOOT_EPHEMERAL", "key_lifetime": "UNTIL_PROCESS_RESTART",
        "key_source": "ephemeral", "verify_key_url": "/api/a11oy/cosign.pub",
    }
    payload = raw_payload if raw_payload is not None else json.dumps(
        {**body, "_signing_identity": identity}, sort_keys=True, separators=(",", ":"),
    ).encode()
    typ = b"application/vnd.szl.receipt+json"
    pae = b"DSSEv1 " + str(len(typ)).encode() + b" " + typ + b" " + str(len(payload)).encode() + b" " + payload
    signature = private.sign(pae, ec.ECDSA(hashes.SHA256()))
    envelope = {
        "signed": True, "payloadType": typ.decode(), "payload": base64.b64encode(payload).decode(),
        "signatures": [{"keyid": fingerprint, "sig": base64.b64encode(signature).decode()}],
        "_pae_sha256": hashlib.sha256(pae).hexdigest(),
        "key_fingerprint_sha256": fingerprint, "key_scope": identity["key_scope"],
        "key_lifetime": identity["key_lifetime"], "verify_key_url": identity["verify_key_url"],
    }
    return {"body": body, "dsse": envelope, "signing": {"pae_sha256": hashlib.sha256(pae).hexdigest()}}, pem


def test_baseline_requires_all_five_exact_ordered_contracts():
    assert runner.baseline_passed(baseline()) is True
    assert runner.baseline_passed(baseline()[:-1]) is False
    assert runner.baseline_passed(list(reversed(baseline()))) is False
    assert runner.baseline_passed([]) is False
    assert runner.baseline_passed(None) is False


@pytest.mark.parametrize("index", [0, 1, 2, 4])
def test_baseline_failure_or_unattempted_route_cannot_pass(index):
    rows = baseline()
    rows[index]["result"] = "UNAVAILABLE"
    rows[index]["attempts"] = 0
    assert runner.baseline_passed(rows) is False


def test_agentloop_refusal_is_not_execution_success_and_requires_no_state_delta():
    rows = baseline()
    rows[3]["after"]["forum_events"] += 1
    assert runner.baseline_passed(rows) is False
    rows = baseline()
    rows[3].update(statusCode=200, result="PASS")
    assert runner.baseline_passed(rows) is False


@pytest.mark.parametrize("rows", [[None], ["invalid"], [{"path": "wrong"}], {}])
def test_malformed_baseline_fails_closed(rows):
    assert runner.baseline_passed(rows) is False


def test_offline_loop_records_orchestration_not_model_execution():
    body, before, after, payload = offline_case()
    assert runner.offline_loop_passed(200, body, before, after, payload) is True
    assert runner.offline_loop_passed(503, body, before, after, payload) is False


@pytest.mark.parametrize("change", ["weak", "missing_run_id", "wrong_task", "wrong_model", "state_delta", "execution", "model_evaluation"])
def test_offline_loop_rejects_incomplete_or_contradictory_evidence(change):
    body, before, after, payload = offline_case()
    if change == "weak":
        body = {"completion": {"complete": False, "model_qualified": False}}
    elif change == "missing_run_id":
        body.pop("run_id")
        body["composite_receipt"]["body"].pop("run_id")
    elif change == "wrong_task":
        body["task"] = "unrelated"
    elif change == "wrong_model":
        body["completion"]["requested_model_id"] = "another-model"
    elif change == "state_delta":
        after["forum_events"] += 1
    elif change == "execution":
        body["steps"][0]["final"]["engine"]["executed"] = True
    else:
        body["steps"][0]["final"]["eval"]["evidence"]["aggregate"].update(
            n_evaluated=8, n_unavailable=0, accuracy=1.0, model_qualified=True,
        )
    assert runner.offline_loop_passed(200, body, before, after, payload) is False


def test_ephemeral_signature_is_simulated_with_only_same_process_trust():
    composite, pem = signed_composite()
    result = runner.verify_ephemeral_receipt(composite, pem)
    assert result["evidenceClass"] == "SIMULATED"
    assert result["signatureVerified"] is True
    assert result["keyScope"] == "PROCESS_BOOT_EPHEMERAL"
    assert result["keyTrust"] == "SAME_LOCAL_PROCESS_ONLY"
    assert result["publicKeySha256"] == hashlib.sha256(pem.strip()).hexdigest()


def test_signature_controls_reject_each_tamper_without_changing_input():
    composite, pem = signed_composite()
    original = copy.deepcopy(composite)
    result = runner.signature_controls(composite, pem)
    assert result["evidenceClass"] == "SIMULATED"
    assert result["contractPassed"] is True
    assert result["tamperRejected"] == dict.fromkeys(["payload", "signature", "outer_body", "fingerprint"], True)
    assert composite == original


def test_wrong_ephemeral_key_is_rejected():
    composite, _ = signed_composite()
    _, wrong_pem = signed_composite()
    with pytest.raises(InvalidSignature):
        runner.verify_ephemeral_receipt(composite, wrong_pem)


@pytest.mark.parametrize("mutation", ["payload", "signature", "outer_body", "keyid", "pae", "signing_pae", "scope", "unsigned", "extra_signature"])
def test_receipt_tampering_and_claim_substitution_are_rejected(mutation):
    composite, pem = signed_composite()
    envelope = composite["dsse"]
    if mutation == "payload":
        envelope["payload"] = base64.b64encode(base64.b64decode(envelope["payload"]) + b" ").decode()
    elif mutation == "signature":
        signature = bytearray(base64.b64decode(envelope["signatures"][0]["sig"]))
        signature[-1] ^= 1
        envelope["signatures"][0]["sig"] = base64.b64encode(signature).decode()
    elif mutation == "outer_body":
        composite["body"]["task"] = "not the signed task"
    elif mutation == "keyid":
        envelope["signatures"][0]["keyid"] = "0" * 64
    elif mutation == "pae":
        envelope["_pae_sha256"] = "0" * 64
    elif mutation == "signing_pae":
        composite["signing"]["pae_sha256"] = "0" * 64
    elif mutation == "scope":
        envelope["key_scope"] = "DEPLOYMENT_PERSISTENT"
    elif mutation == "unsigned":
        envelope["signed"] = False
    else:
        envelope["signatures"].append(copy.deepcopy(envelope["signatures"][0]))
    with pytest.raises((InvalidSignature, ValueError)):
        runner.verify_ephemeral_receipt(composite, pem)


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff'])
def test_cryptographically_signed_but_ambiguous_json_is_rejected(payload):
    composite, pem = signed_composite(raw_payload=payload)
    with pytest.raises(ValueError):
        runner.verify_ephemeral_receipt(composite, pem)


def test_rsa_public_key_cannot_be_mislabeled_as_ephemeral_ecdsa():
    composite, _ = signed_composite()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(ValueError, match="unexpected_local_key_type"):
        runner.verify_ephemeral_receipt(composite, pem)


def mock_git(monkeypatch, root, *, patch=b"local tracked diff", tracked=b"tracked.txt\0removed.txt\0", untracked=b"new.txt\0"):
    calls = []
    def git(command, *, timeout):
        assert timeout == 30
        assert command[:3] == ["git", "-C", str(root)]
        args = command[3:]
        calls.append(args)
        if args == ["rev-parse", "HEAD"]:
            return b"a" * 40 + b"\n"
        if args == ["diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--"]:
            return patch
        if args == ["diff", "--name-only", "-z", "HEAD"]:
            return tracked
        if args == ["ls-files", "--others", "--exclude-standard", "-z"]:
            return untracked
        pytest.fail("unexpected git command")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "bounded_git_output", git)
    return calls


def test_source_manifest_binds_untracked_modified_and_deleted_files(tmp_path, monkeypatch):
    (tmp_path / "tracked.txt").write_bytes(b"tracked candidate bytes")
    (tmp_path / "new.txt").write_bytes(b"new acceptance runner")
    calls = mock_git(monkeypatch, tmp_path)
    result = runner.source_manifest()
    assert result["baseRevision"] == "a" * 40
    assert result["binding"] == "LOCAL_CANDIDATE_BASE_PLUS_PATCH_AND_FILE_HASHES"
    assert result["changedFiles"] == {
        "new.txt": hashlib.sha256(b"new acceptance runner").hexdigest(),
        "removed.txt": "DELETED",
        "tracked.txt": hashlib.sha256(b"tracked candidate bytes").hexdigest(),
    }
    assert result["candidateSha256"] == runner.digest({key: value for key, value in result.items() if key != "candidateSha256"})
    assert len(calls) == 4
    (tmp_path / "new.txt").write_bytes(b"one-byte-different local candidate")
    assert runner.source_manifest()["candidateSha256"] != result["candidateSha256"]


def test_source_manifest_rejects_paths_outside_checkout(tmp_path, monkeypatch):
    mock_git(monkeypatch, tmp_path, tracked=b"../outside.txt\0", untracked=b"")
    with pytest.raises(RuntimeError, match="source_path_not_ordinary"):
        runner.source_manifest()


def test_source_manifest_rejects_excessive_file_count(tmp_path, monkeypatch):
    mock_git(monkeypatch, tmp_path, tracked=b"a\0b\0", untracked=b"")
    monkeypatch.setattr(runner, "MAX_SOURCE_FILES", 1)
    with pytest.raises(RuntimeError, match="source_file_count_limit_exceeded"):
        runner.source_manifest()


@pytest.mark.parametrize("bound", ["MAX_SOURCE_FILE_BYTES", "MAX_SOURCE_TOTAL_BYTES"])
def test_source_manifest_rejects_oversize_file_before_read(tmp_path, monkeypatch, bound):
    (tmp_path / "tracked.txt").write_bytes(b"12345")
    mock_git(monkeypatch, tmp_path, tracked=b"tracked.txt\0", untracked=b"")
    monkeypatch.setattr(runner, bound, 4)
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: pytest.fail("oversize source must not be opened"))
    with pytest.raises(RuntimeError, match="source_file_byte_limit_exceeded"):
        runner.source_manifest()


def test_source_manifest_enforces_cumulative_byte_budget(tmp_path, monkeypatch):
    (tmp_path / "a").write_bytes(b"123")
    (tmp_path / "b").write_bytes(b"456")
    mock_git(monkeypatch, tmp_path, tracked=b"a\0b\0", untracked=b"")
    monkeypatch.setattr(runner, "MAX_SOURCE_TOTAL_BYTES", 5)
    with pytest.raises(RuntimeError, match="source_file_byte_limit_exceeded"):
        runner.source_manifest()


def test_source_manifest_rejects_directories(tmp_path, monkeypatch):
    (tmp_path / "directory").mkdir()
    mock_git(monkeypatch, tmp_path, tracked=b"directory\0", untracked=b"")
    with pytest.raises(RuntimeError, match="source_path_not_ordinary"):
        runner.source_manifest()


@pytest.mark.parametrize("raw,code,passes", [(b"1234", 0, True), (b"12345", 0, False), (b"", 1, False)])
def test_git_capture_is_bounded_and_requires_success(monkeypatch, raw, code, passes):
    killed = []
    process = SimpleNamespace(stdout=io.BytesIO(raw), kill=lambda: killed.append(True),
                              wait=lambda **_kwargs: code)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(runner, "MAX_SOURCE_COMMAND_BYTES", 4)
    if passes:
        assert runner.bounded_git_output(["git"], timeout=30) == raw
    else:
        with pytest.raises(RuntimeError, match="source_command_failed_or_limit_exceeded"):
            runner.bounded_git_output(["git"], timeout=30)
    assert bool(killed) is (len(raw) > 4)


def test_child_environment_excludes_inherited_authority(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_TOKEN", "fixture-no-authority")
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-no-authority")
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", "fixture-not-a-key")
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "fixture-no-authority")
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted.invalid")
    env = runner.child_environment(tmp_path)
    assert set(env) <= {"SystemRoot", "WINDIR", "COMSPEC", "PATH", "TEMP", "TMP", "HOME",
                        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PYTHONIOENCODING"}
    assert env["HOME"] == str(tmp_path)


def test_direct_child_requires_interpreter_isolation_before_reading_source(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.sys, "flags", SimpleNamespace(isolated=False, no_site=False))
    with pytest.raises(RuntimeError, match="local_child_requires_isolated"):
        runner.child(tmp_path, "a" * 40)


def test_git_capture_timeout_kills_and_reaps(monkeypatch):
    calls = []
    def wait(*, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise runner.subprocess.TimeoutExpired("git", timeout)
        return -9
    killed = []
    process = SimpleNamespace(stdout=io.BytesIO(b""), wait=wait, kill=lambda: killed.append(True))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: process)
    with pytest.raises(RuntimeError, match="source_command_failed_or_limit_exceeded"):
        runner.bounded_git_output(["git"], timeout=30)
    assert calls == [30, 10]
    assert killed == [True]


def test_output_directory_cannot_invalidate_its_own_source_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    for path in (tmp_path, tmp_path / "evidence"):
        with pytest.raises(ValueError, match="outside_source_checkout"):
            runner.output_directory(path)
    assert runner.output_directory(tmp_path.parent / "external-evidence") == tmp_path.parent / "external-evidence"
