# SPDX-License-Identifier: Apache-2.0
"""Test actual publisher inputs, captured outputs, and credentialless build parity."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1" * 40


def load(name):
    spec = importlib.util.spec_from_file_location("test_"+name, ROOT/"scripts"/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def renderer():
    return load("hf_publish_vertical_flagships_v4_impl")


@pytest.mark.parametrize("line", ["fastapi==0.141.1", "starlette==1.6.0", "pip==26.2.1"])
def test_emitted_runtime_uses_qualified_versions(line):
    assert line in renderer().REQ.splitlines()


def test_emitted_runtime_uses_qualified_nonroot_image():
    docker = renderer().DOCKER
    assert "sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf" in docker
    assert "USER szl\n" in docker and "--uid 1000" in docker
    assert "'pip==26.2.1'" in docker and "python -m pip check" in docker


def test_no_drift_between_runtime_module_and_actual_publisher():
    r, contract = renderer(), load("hf_flagship_runtime_contract")
    assert r.REQ == r._BASE.REQ == contract.REQUIREMENTS
    assert r.DOCKER == r._BASE.DOCKER == contract.DOCKERFILE
    r._sync_contract()
    assert r._BASE.REQ == contract.REQUIREMENTS
    assert r._BASE.DOCKER == contract.DOCKERFILE


def test_lock_is_complete_well_formed_and_unique():
    rows = [l for l in renderer().REQ.splitlines() if l and not l.startswith("#")]
    assert len(rows) == 23
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", l) for l in rows)
    names=[l.split("==")[0].lower().replace("_", "-") for l in rows]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("slug", ["finance", "terra", "counsel", "sentra"])
def test_generated_surfaces_keep_original_templates_and_routing(slug):
    r = renderer()
    assert sum(row["slug"] == slug for row in r.FLAGSHIPS) == 1
    assert slug in r.DOMAIN_HTML and slug in r.DOMAIN_CSS
    assert "@app.get(\"/api/finance/providers\")" in r.APP
    assert '"USE_PRIVATE_CANONICAL_SOURCE_ENDPOINT",403' in r.APP
    assert "CANONICAL_PROVENANCE_MISMATCH" in r.APP


def test_bundle_matches_every_byte_submitted_by_existing_publisher(tmp_path, monkeypatch):
    emit, r = load("materialize_finance_runtime"), renderer()
    expected = emit.payloads(r, REVISION, 123)
    observed = {}
    class RecordingApi:
        def __init__(self, **kw): assert kw == {"token":"INERT_TEST_TOKEN"}
        def repo_exists(self, **kw): return True
        def auth_check(self, **kw): assert kw["write"] is True
        def upload_file(self, **kw):
            assert kw["repo_id"]=="SZLHOLDINGS/finance" and kw["repo_type"]=="space"
            observed[kw["path_in_repo"]]=kw["path_or_fileobj"]
        def restart_space(self, repo_id): assert repo_id=="SZLHOLDINGS/finance"
    r.FLAGSHIPS = tuple(row for row in r.FLAGSHIPS if row["slug"] == "finance")
    monkeypatch.setattr(r._BASE, "HfApi", RecordingApi)
    monkeypatch.setattr(r._BASE, "token_from_env", lambda: ("INERT_TEST_TOKEN", "fixture"))
    monkeypatch.setattr(r._BASE, "load_terra_forge_bundle", lambda: ("UNUSED_TEST_FIXTURE", {}))
    monkeypatch.setattr(r._BASE, "observe_flagship", lambda row: None)
    monkeypatch.setattr(r._BASE, "observation_passes", lambda *a, **k: True)
    monkeypatch.setenv("GITHUB_SHA", REVISION)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.chdir(tmp_path)
    assert r.main() == 0
    assert observed == expected
    assert set(observed)=={"app.py","Dockerfile","requirements.txt","config.json","index.html","panels.html","README.md"}


def test_build_harness_does_not_instantiate_provider_or_use_network(tmp_path):
    emitter=load("materialize_finance_runtime")
    with patch("huggingface_hub.HfApi", side_effect=AssertionError("provider forbidden")), \
         patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
        evidence=emitter.materialize(tmp_path/"build",REVISION,321)
    assert evidence["provider_mutations"]==0 and evidence["deployment_verified"] is False
    for name,digest in evidence["files"].items():
        assert hashlib.sha256((tmp_path/"build"/name).read_bytes()).hexdigest()==digest


@pytest.mark.parametrize("revision,run_id", [("0"*40,1),("1"*39,1),("A"*40,1),("1"*41,1),(None,1),(REVISION,0),(REVISION,True),(REVISION,"2")])
def test_invalid_source_identity_refused_before_output(tmp_path,revision,run_id):
    emitter=load("materialize_finance_runtime")
    with pytest.raises(ValueError): emitter.materialize(tmp_path/"build",revision,run_id)
    assert not (tmp_path/"build").exists()


def test_output_refuses_existing_tree_and_symlink(tmp_path):
    emitter=load("materialize_finance_runtime")
    destination=tmp_path/"existing";destination.mkdir()
    marker=destination/"keep.txt";marker.write_text("keep")
    for path in (destination,tmp_path/"link"):
        if path!=destination:path.symlink_to(destination,target_is_directory=True)
        with pytest.raises(FileExistsError): emitter.materialize(path,REVISION,1)
    assert marker.read_text()=="keep"
    assert list(destination.iterdir())==[marker]


def test_runtime_change_is_in_existing_artifact_identity():
    emit,r=load("materialize_finance_runtime"),renderer()
    first=json.loads(emit.payloads(r,REVISION,12)["config.json"])
    r.REQ += "# changed fixture\n"
    second=json.loads(emit.payloads(r,REVISION,12)["config.json"])
    assert first["artifact_set_sha256"]!=second["artifact_set_sha256"]


def test_generated_application_serves_same_routes_and_denies_private_feeds(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    emit=load("materialize_finance_runtime")
    output=tmp_path/"runtime";emit.materialize(output,REVISION,1)
    monkeypatch.chdir(output)
    ns={"__name__":"generated_finance_test"}
    exec(compile((output/"app.py").read_text(),"generated-app.py","exec"),ns)
    with TestClient(ns["app"]) as client:
        for path in ("/","/panels","/healthz","/readyz"):
            assert client.get(path).status_code==200
        assert client.get("/").content==(output/"index.html").read_bytes()
        assert client.get("/api/finance/observations/alpaca-quotes").status_code==403
        assert client.get("/api/finance/observations/fred-series").status_code==403
        assert client.post("/orders",json={}).status_code==404


def test_requirements_emitter_is_stdlib_only_and_does_not_read_credentials():
    completed=subprocess.run([sys.executable,"-I",str(ROOT/"scripts/hf_flagship_runtime_contract.py")],capture_output=True,text=True,check=True)
    assert completed.stdout==renderer().REQ
    assert completed.stderr==""


def test_workflow_tests_the_emitted_lock_and_runs_generated_container():
    import yaml
    workflow=yaml.safe_load((ROOT/".github/workflows/finance-source-contracts.yml").read_text())
    text=(ROOT/".github/workflows/finance-source-contracts.yml").read_text()
    assert "hf_flagship_runtime_contract.py > finance-runtime.txt" in text
    assert "-r finance-runtime.txt -c finance-runtime.txt" in text
    assert "fastapi==0.141.1 starlette==1.6.0" not in text
    assert "materialize_finance_runtime.py" in text
    assert "--network none --read-only" in text
    assert "-p 127.0.0.1:17860:7860" in text
    assert "docker network create --internal" not in text
    assert "tests/smoke_generated_finance_runtime.py" in text
    assert "pip_audit --strict" in text
    assert workflow["permissions"] == {"contents":"read"}
    assert "merge_group" in workflow.get("on",workflow.get(True,{}))
    assert "secrets." not in text


@pytest.mark.parametrize("slug", ["terra", "counsel", "sentra"])
def test_sibling_generated_apps_retain_readiness_and_no_finance_routes(tmp_path, monkeypatch, slug):
    """Exercise sibling API assembly; this is not their full branded browser build."""
    from fastapi.testclient import TestClient
    emit, r = load("materialize_finance_runtime"), renderer()
    files = emit.payloads(r, REVISION, 1)
    item = next(row for row in r.FLAGSHIPS if row["slug"] == slug)
    panels = r.html(item).encode()
    config = json.loads(files["config.json"])
    config.update(slug=slug, title=item["title"], vertical=item["vertical"],
                  product_source=item["source"], hf_repository=r.ORG + "/" + slug,
                  upstream=item["upstream"], landing_sha256=hashlib.sha256(panels).hexdigest(),
                  panels_sha256=hashlib.sha256(panels).hexdigest())
    # Fixture configuration is never retained as a deployment receipt.
    files.update({"config.json": json.dumps(config).encode(),
                  "index.html": panels, "panels.html": panels})
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    monkeypatch.chdir(tmp_path)
    ns = {"__name__": "generated_sibling_fixture"}
    with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
        exec(compile(r.APP, "generated-sibling.py", "exec"), ns)
    # Windows creates a loopback socketpair when starting its event loop. Start
    # the client first; forbid every socket connection during application reads.
    with TestClient(ns["app"]) as client:
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            assert client.get("/").content == panels
            assert client.get("/readyz").json()["ready"] is True
            assert client.get("/healthz").json()["domain"] == slug
            assert client.get("/api/finance/providers").status_code == 404


def test_requirements_contract_rejects_unsupported_renderer():
    from types import SimpleNamespace
    contract = load("hf_flagship_runtime_contract")
    bad = SimpleNamespace(REQ="unchanged", DOCKER=None, APP="app")
    with pytest.raises(TypeError):
        contract.apply_runtime_contract(bad)
    assert bad.REQ == "unchanged" and bad.DOCKER is None
