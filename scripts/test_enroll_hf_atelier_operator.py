#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest


SCRIPT = Path(__file__).with_name("enroll_hf_atelier_operator.py")
SPEC = importlib.util.spec_from_file_location("enroll_hf_atelier_operator", SCRIPT)
assert SPEC and SPEC.loader
enroll = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enroll)

MAIN = "a" * 40
SPACE = "b" * 40
TEST_BEARER = "T" * 64  # Synthetic fixture, never a live credential.


class FakeApi:
    def __init__(self):
        self.sha = SPACE
        self.secrets = {}
        self.variables = {}
        self.writes = []
        self.fail_write = False

    def space_info(self, *, repo_id):
        assert repo_id == enroll.SPACE_ID
        return SimpleNamespace(sha=self.sha)

    def get_space_secrets(self, *, repo_id):
        assert repo_id == enroll.SPACE_ID
        return dict(self.secrets)

    def get_space_variables(self, *, repo_id):
        assert repo_id == enroll.SPACE_ID
        return dict(self.variables)

    def add_space_secret(self, *, repo_id, key, value, description):
        assert repo_id == enroll.SPACE_ID
        self.writes.append((key, value, description))
        if self.fail_write:
            raise RuntimeError("provider failure containing " + TEST_BEARER)
        self.secrets[key] = {"name": key}


def gh_reader(*, status="completed", conclusion="success", sha=MAIN,
              status_sequence=None, active_count=1, main_count=1):
    commit_reads = 0

    def read(args):
        nonlocal commit_reads
        assert args[0] == "api" and len(args) == 2
        if args[1] == f"repos/{enroll.GITHUB_REPO}/commits/main":
            commit_reads += 1
            return {"sha": sha}
        path, separator, query_string = args[1].partition("?")
        assert separator and path == (
            f"repos/{enroll.GITHUB_REPO}/actions/workflows/hf-sync.yml/runs"
        )
        query = parse_qs(query_string)
        assert query.get("per_page") == ["1"]
        statuses = status_sequence or (status,)
        current = statuses[min((commit_reads - 1) // 2, len(statuses) - 1)]
        run = {"id": 10, "status": "completed" if current == "action_required" else current,
               "conclusion": "action_required" if current == "action_required" else conclusion,
               "head_sha": sha, "head_branch": "main"}
        if "status" in query:
            selected = query["status"][0]
            assert selected in enroll._PUBLISHER_HOLD_FILTERS
            count = active_count if selected == current else 0
        else:
            assert query.get("head_sha") == [sha]
            assert query.get("branch") == ["main"]
            count = main_count
        return {"total_count": count, "workflow_runs": [run] if count else []}
    return read


@pytest.fixture
def writable_disk(monkeypatch):
    monkeypatch.setattr(enroll.shutil, "disk_usage",
                        lambda _path: SimpleNamespace(free=10_000_000_000))


def test_plan_is_read_only_and_reports_no_secret_value():
    api = FakeApi()
    result = enroll.plan(api, gh_reader())
    assert result == {
        "state": "PRECHECK_PASS_NOT_INSTALLED",
        "repo_id": enroll.SPACE_ID,
        "protected_main_sha": MAIN,
        "space_sha": SPACE,
        "secret_name": enroll.SECRET_NAME,
        "secret_value_read": "false",
    }
    assert api.writes == []


@pytest.mark.parametrize("status", [
    "queued", "in_progress", "requested", "pending", "waiting", "action_required",
])
def test_plan_holds_when_publisher_is_not_idle(status):
    with pytest.raises(enroll.EnrollmentHold, match="PUBLISHER_NOT_IDLE"):
        enroll.plan(FakeApi(), gh_reader(status=status, conclusion=None,
                                         active_count=1_200))


def test_plan_does_not_accept_old_success_after_new_failure():
    with pytest.raises(enroll.EnrollmentHold, match="CURRENT_MAIN_NOT_PUBLISHED"):
        enroll.plan(FakeApi(), gh_reader(conclusion="failure", main_count=2))


def test_plan_refuses_inconsistent_status_count():
    source = gh_reader()

    def gh(args):
        result = source(args)
        if "status=queued" in args[1]:
            return {"total_count": 1, "workflow_runs": []}
        return result

    with pytest.raises(enroll.EnrollmentHold, match="PUBLISHER_STATE_UNKNOWN"):
        enroll.plan(FakeApi(), gh)


def test_plan_refuses_moved_main_after_multi_read_snapshot():
    source = gh_reader()
    main_reads = 0

    def gh(args):
        nonlocal main_reads
        if args[1] == f"repos/{enroll.GITHUB_REPO}/commits/main":
            main_reads += 1
            return {"sha": MAIN if main_reads == 1 else "c" * 40}
        return source(args)

    with pytest.raises(enroll.EnrollmentHold,
                       match="PROTECTED_MAIN_MOVED_DURING_SNAPSHOT"):
        enroll.plan(FakeApi(), gh)


def test_plan_refuses_existing_secret_without_reading_or_overwriting_it():
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"value": "masked"}
    with pytest.raises(enroll.EnrollmentHold, match="EXISTING_REGISTRY_REQUIRES_ROTATION"):
        enroll.plan(api, gh_reader())
    assert api.writes == []


def test_plan_refuses_public_variable_name_collision():
    api = FakeApi()
    api.variables[enroll.SECRET_NAME] = {"value": "not-a-secret"}
    with pytest.raises(enroll.EnrollmentHold, match="SECRET_VARIABLE_COLLISION"):
        enroll.plan(api, gh_reader())


def _apply(api, path, **overrides):
    arguments = dict(
        expected_main_sha=MAIN, expected_space_sha=SPACE,
        owner_id="owner:stephen", key_id="atelier-operator-test",
        gh_json=gh_reader(), protect=lambda _payload: b"synthetic-sealed-bytes",
        vault_path=path, token_factory=lambda _n: TEST_BEARER,
    )
    arguments.update(overrides)
    return enroll.apply(api, **arguments)


def test_apply_writes_only_digest_registry_and_encrypted_local_vault(tmp_path, writable_disk):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    result = _apply(api, vault)
    assert result["state"] == "SECRET_NAME_PRESENT_DIGEST_UNVERIFIED"
    assert result["bearer_disclosed"] == "false"
    assert len(api.writes) == 1
    name, value, _description = api.writes[0]
    assert name == enroll.SECRET_NAME
    assert TEST_BEARER not in value
    assert '"token":' not in value
    registry = json.loads(value)
    assert registry == {"version": 1, "credentials": [{
        "owner_id": "owner:stephen", "namespace": "a11oy",
        "key_id": "atelier-operator-test",
        "token_sha256": hashlib.sha256(TEST_BEARER.encode()).hexdigest(),
        "scopes": ["atelier:write"], "revoked": False,
    }]}
    assert vault.read_bytes() == enroll._VAULT_MAGIC + b"synthetic-sealed-bytes"
    assert TEST_BEARER.encode() not in vault.read_bytes()


def test_apply_holds_when_plan_revision_changes_before_vault(tmp_path, writable_disk):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    with pytest.raises(enroll.EnrollmentHold, match="PLAN_REVISION_CHANGED"):
        _apply(api, vault, expected_space_sha="c" * 40)
    assert not vault.exists() and api.writes == []


def test_apply_holds_on_low_storage_before_token_generation(tmp_path, monkeypatch):
    api = FakeApi()
    token_calls = []
    monkeypatch.setattr(enroll.shutil, "disk_usage",
                        lambda _path: SimpleNamespace(free=1))
    with pytest.raises(enroll.EnrollmentHold, match="LOCAL_STORAGE_LOW"):
        _apply(api, tmp_path / "operator.dpapi",
               token_factory=lambda n: token_calls.append(n))
    assert token_calls == [] and api.writes == []


def test_apply_holds_after_vault_when_writer_appears(tmp_path, writable_disk):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"

    with pytest.raises(enroll.EnrollmentHold, match="PUBLISHER_NOT_IDLE"):
        _apply(api, vault, gh_json=gh_reader(
            status_sequence=("completed", "in_progress")))
    assert vault.exists() and api.writes == []


def test_ambiguous_provider_failure_never_exposes_bearer(tmp_path, writable_disk):
    api = FakeApi()
    api.fail_write = True
    vault = tmp_path / "operator.dpapi"
    with pytest.raises(enroll.EnrollmentHold) as error:
        _apply(api, vault)
    assert error.value.code == "HF_WRITE_OUTCOME_UNKNOWN_VAULT_RETAINED"
    assert TEST_BEARER not in str(error.value)
    assert vault.exists()


def test_explicit_resume_reuses_same_vault_digest_after_ambiguous_write(tmp_path, writable_disk):
    api = FakeApi()
    api.fail_write = True
    vault = tmp_path / "operator.dpapi"
    protected = {}

    def protect(payload):
        protected["plain"] = payload
        return b"synthetic-sealed-bytes"

    with pytest.raises(enroll.EnrollmentHold, match="HF_WRITE_OUTCOME_UNKNOWN"):
        _apply(api, vault, protect=protect)
    first_registry = api.writes[0][1]
    api.fail_write = False
    result = enroll.resume(
        api, expected_main_sha=MAIN, expected_space_sha=SPACE,
        key_id="atelier-operator-test", gh_json=gh_reader(),
        unprotect=lambda _: protected["plain"], vault_path=vault,
    )
    assert result["state"] == "SECRET_NAME_PRESENT_DIGEST_UNVERIFIED"
    assert api.writes[1][1] == first_registry
    assert TEST_BEARER not in json.dumps(result)
    assert TEST_BEARER not in api.writes[1][1]


def test_resume_refuses_existing_remote_registry_before_decryption(tmp_path, writable_disk):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"value": "masked"}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    with pytest.raises(enroll.EnrollmentHold, match="EXISTING_REGISTRY_REQUIRES_ROTATION"):
        enroll.resume(
            api, expected_main_sha=MAIN, expected_space_sha=SPACE,
            key_id="atelier-operator-test", gh_json=gh_reader(),
            unprotect=lambda _: pytest.fail("DPAPI was called"), vault_path=vault,
        )
    assert api.writes == []


def test_resume_holds_if_source_or_space_revision_changed(tmp_path, writable_disk):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    with pytest.raises(enroll.EnrollmentHold, match="PLAN_REVISION_CHANGED"):
        enroll.resume(
            api, expected_main_sha="c" * 40, expected_space_sha=SPACE,
            key_id="atelier-operator-test", gh_json=gh_reader(),
            unprotect=lambda _: pytest.fail("DPAPI was called"), vault_path=vault,
        )
    assert api.writes == []


def test_resume_holds_if_writer_appears_after_vault_read(tmp_path, writable_disk):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    record = {"version": 1, "repo_id": enroll.SPACE_ID,
              "owner_id": "owner:stephen", "key_id": "atelier-operator-test",
              "token": TEST_BEARER,
              "token_sha256": hashlib.sha256(TEST_BEARER.encode()).hexdigest()}
    with pytest.raises(enroll.EnrollmentHold, match="PUBLISHER_NOT_IDLE"):
        enroll.resume(
            api, expected_main_sha=MAIN, expected_space_sha=SPACE,
            key_id="atelier-operator-test", gh_json=gh_reader(
                status_sequence=("completed", "queued")),
            unprotect=lambda _: json.dumps(record).encode(), vault_path=vault,
        )
    assert api.writes == []


def test_apply_never_overwrites_existing_local_vault(tmp_path, writable_disk):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(b"existing-user-data")
    with pytest.raises(enroll.EnrollmentHold, match="LOCAL_VAULT_ALREADY_EXISTS"):
        _apply(api, vault)
    assert vault.read_bytes() == b"existing-user-data"
    assert api.writes == []


@pytest.mark.parametrize("key_id", ["con", "nul.txt", "atelier:operator", "atelier."])
def test_apply_rejects_key_ids_unsafe_for_windows_vault(tmp_path, writable_disk, key_id):
    api = FakeApi()
    with pytest.raises(enroll.EnrollmentHold, match="CREDENTIAL_KEY_ID_UNSAFE_FOR_VAULT"):
        _apply(api, tmp_path / "operator.dpapi", key_id=key_id)
    assert api.writes == []


def test_copy_requires_explicit_clipboard_acknowledgement(tmp_path):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    seen = []
    with pytest.raises(enroll.EnrollmentHold,
                       match="CLIPBOARD_RISK_ACKNOWLEDGEMENT_REQUIRED"):
        enroll.copy_for_browser(
            api,
            key_id="atelier-operator-test", acknowledged=False,
            vault_path=vault, unprotect=lambda _: seen.append("decrypt"),
            clipboard_copy=lambda _: seen.append("copy"),
        )
    assert seen == []


def test_copy_handoff_never_prints_bearer(tmp_path, capsys):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"name": enroll.SECRET_NAME}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    record = {"version": 1, "repo_id": enroll.SPACE_ID,
              "owner_id": "owner:stephen", "key_id": "atelier-operator-test",
              "token": TEST_BEARER,
              "token_sha256": hashlib.sha256(TEST_BEARER.encode()).hexdigest()}
    copied = []
    result = enroll.copy_for_browser(
        api,
        key_id="atelier-operator-test", acknowledged=True,
        gh_json=gh_reader(),
        vault_path=vault, unprotect=lambda _: json.dumps(record).encode(),
        clipboard_copy=copied.append,
    )
    assert copied == [TEST_BEARER]
    assert result["state"] == "COPIED_TO_CLIPBOARD_TRANSIENT_RISK"
    assert result["bearer_printed"] == "false"
    assert result["remote_registry"] == "NAME_PRESENT_DIGEST_UNVERIFIED"
    assert result["protected_main_sha"] == MAIN
    assert result["space_sha"] == SPACE
    assert TEST_BEARER not in json.dumps(result)
    assert capsys.readouterr() == ("", "")


def test_copy_rejects_tampered_vault_payload(tmp_path):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"name": enroll.SECRET_NAME}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    record = {"version": 1, "repo_id": enroll.SPACE_ID,
              "owner_id": "owner:stephen", "key_id": "atelier-operator-test",
              "token": TEST_BEARER, "token_sha256": "0" * 64}
    copied = []
    with pytest.raises(enroll.EnrollmentHold, match="LOCAL_VAULT_MALFORMED"):
        enroll.copy_for_browser(
            api,
            key_id="atelier-operator-test", acknowledged=True,
            gh_json=gh_reader(),
            vault_path=vault, unprotect=lambda _: json.dumps(record).encode(),
            clipboard_copy=copied.append,
        )
    assert copied == []


def test_copy_rejects_empty_sealed_payload_before_dpapi(tmp_path):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"name": enroll.SECRET_NAME}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC)
    with pytest.raises(enroll.EnrollmentHold, match="LOCAL_VAULT_MALFORMED"):
        enroll.copy_for_browser(
            api,
            key_id="atelier-operator-test", acknowledged=True,
            gh_json=gh_reader(),
            vault_path=vault, unprotect=lambda _: pytest.fail("DPAPI was called"),
        )


@pytest.mark.parametrize("install_state", ["held", "failed"])
def test_copy_refuses_vault_without_remote_secret_after_install_hold(
    tmp_path, writable_disk, install_state,
):
    api = FakeApi()
    vault = tmp_path / "operator.dpapi"
    if install_state == "failed":
        api.fail_write = True
        expected_hold = "HF_WRITE_OUTCOME_UNKNOWN_VAULT_RETAINED"
        overrides = {}
    else:
        expected_hold = "PUBLISHER_NOT_IDLE"
        overrides = {"gh_json": gh_reader(
            status_sequence=("completed", "in_progress"))}
    with pytest.raises(enroll.EnrollmentHold, match=expected_hold):
        _apply(api, vault, **overrides)
    assert vault.exists()
    copied = []
    with pytest.raises(enroll.EnrollmentHold, match="REMOTE_REGISTRY_NOT_VISIBLE"):
        enroll.copy_for_browser(
            api, key_id="atelier-operator-test", acknowledged=True,
            gh_json=gh_reader(), vault_path=vault,
            unprotect=lambda _: pytest.fail("DPAPI was called"),
            clipboard_copy=copied.append,
        )
    assert copied == []


def test_copy_refuses_active_publisher_before_vault_decryption(tmp_path):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"name": enroll.SECRET_NAME}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    copied = []
    with pytest.raises(enroll.EnrollmentHold, match="PUBLISHER_NOT_IDLE"):
        enroll.copy_for_browser(
            api, key_id="atelier-operator-test", acknowledged=True,
            gh_json=gh_reader(status="in_progress"), vault_path=vault,
            unprotect=lambda _: pytest.fail("DPAPI was called"),
            clipboard_copy=copied.append,
        )
    assert copied == []


def test_copy_refuses_secret_disappearing_during_handoff(tmp_path):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"name": enroll.SECRET_NAME}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    record = {"version": 1, "repo_id": enroll.SPACE_ID,
              "owner_id": "owner:stephen", "key_id": "atelier-operator-test",
              "token": TEST_BEARER,
              "token_sha256": hashlib.sha256(TEST_BEARER.encode()).hexdigest()}
    copied = []

    def decrypt_and_remove(_):
        api.secrets.pop(enroll.SECRET_NAME)
        return json.dumps(record).encode()

    with pytest.raises(enroll.EnrollmentHold, match="REMOTE_REGISTRY_NOT_VISIBLE"):
        enroll.copy_for_browser(
            api, key_id="atelier-operator-test", acknowledged=True,
            gh_json=gh_reader(), vault_path=vault,
            unprotect=decrypt_and_remove, clipboard_copy=copied.append,
        )
    assert copied == []


def test_copy_refuses_space_revision_change_during_handoff(tmp_path):
    api = FakeApi()
    api.secrets[enroll.SECRET_NAME] = {"name": enroll.SECRET_NAME}
    vault = tmp_path / "operator.dpapi"
    vault.write_bytes(enroll._VAULT_MAGIC + b"synthetic-sealed-bytes")
    record = {"version": 1, "repo_id": enroll.SPACE_ID,
              "owner_id": "owner:stephen", "key_id": "atelier-operator-test",
              "token": TEST_BEARER,
              "token_sha256": hashlib.sha256(TEST_BEARER.encode()).hexdigest()}
    copied = []

    def decrypt_and_change_revision(_):
        api.sha = "c" * 40
        return json.dumps(record).encode()

    with pytest.raises(enroll.EnrollmentHold,
                       match="REMOTE_REVISION_CHANGED_BEFORE_COPY"):
        enroll.copy_for_browser(
            api, key_id="atelier-operator-test", acknowledged=True,
            gh_json=gh_reader(), vault_path=vault,
            unprotect=decrypt_and_change_revision, clipboard_copy=copied.append,
        )
    assert copied == []


@pytest.mark.skipif(os.name != "nt", reason="Windows user DPAPI only")
def test_windows_dpapi_round_trip_uses_current_user():
    sample = b"synthetic-dpapi-round-trip"
    sealed = enroll._dpapi_protect(sample)
    assert sealed != sample
    assert enroll._dpapi_unprotect(sealed) == sample
