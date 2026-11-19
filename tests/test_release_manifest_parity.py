# SPDX-License-Identifier: Apache-2.0
"""Repro for the Hub module-drift failure in a11oy#3768 (PUBLICATION_LAG).

Observed on PR #3768 (base 9467fa9): the job "Protected base matches immutable
HF repository" failed with ``PUBLICATION_LAG: runtime marker
source_sha=02fe789... does not [match the protected base]``. The source and the
served runtime had no shared, machine-checkable identity, so drift could only be
found by a late CI byte comparison. These tests pin the missing contract:

* one release manifest binds git commit, frontend bundle hash, API contract
  hash, HF model revision, deployment ID and rollback target;
* the generator fills it at build time from the tree and the environment (it
  never hardcodes values, and reports UNKNOWN instead of guessing);
* the runtime exposes the same build IDs read-only at ``/api/build`` and the
  frontend carries a release-id meta tag and footer;
* a manifest that disagrees with the deployed runtime is reported as drift.

Each test imports lazily so every missing piece fails on its own assertion.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHA_A = "9467fa988ff63c919954adbd8e23e930412321b5"  # protected base in #3768
SHA_B = "02fe78903c859aa7ef570b96bcb36724b5d59bb4"  # runtime marker in #3768
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fx"
    (repo / "console").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "console" / "index.html").write_text("<html>one</html>\n")
    (repo / "console" / "app.js").write_text("console.log(1)\n")
    (repo / "docs" / "api-contract.md").write_text("# contract v1\n")
    (repo / "Dockerfile").write_text(
        "ARG A11OY_ALLOY_GGUF_REPO=SZLHOLDINGS/SZL-Khipu-1.5B-GGUF\n"
        "ARG A11OY_ALLOY_GGUF_REV=67d60ec577730747055491640cfb91fc4a4b5d25\n"
    )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "one")
    return repo


def _run_generator(repo: Path, out: Path, env_extra: dict[str, str] | None = None, *args: str):
    env = {k: v for k, v in os.environ.items() if not k.startswith("A11OY_")}
    env.pop("GITHUB_SHA", None)
    env.update(env_extra or {})
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_release_manifest.py"),
            "--repo-root",
            str(repo),
            "--out",
            str(out),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_generator_fills_manifest_from_tree_and_env_not_hardcoded(tmp_path):
    repo = _fixture_repo(tmp_path)
    out = tmp_path / "m1.json"
    res = _run_generator(
        repo,
        out,
        {"A11OY_DEPLOYMENT_ID": "dep-001", "A11OY_ROLLBACK_TARGET": SHA_B},
    )
    assert res.returncode == 0, res.stderr
    m1 = json.loads(out.read_text())
    assert m1["git"]["commit"] == _git(repo, "rev-parse", "HEAD")
    assert HEX64.match(m1["frontend"]["bundle_sha256"])
    assert HEX64.match(m1["api_contract"]["sha256"])
    assert m1["model"]["revision"]["value"] == "67d60ec577730747055491640cfb91fc4a4b5d25"
    assert m1["deployment"]["id"]["value"] == "dep-001"
    assert m1["rollback"]["target"]["value"] == SHA_B

    # change the frontend + commit: commit, bundle hash and release id must move,
    # the untouched API contract hash must not.
    (repo / "console" / "app.js").write_text("console.log(2)\n")
    _git(repo, "commit", "-qam", "two")
    out2 = tmp_path / "m2.json"
    assert _run_generator(repo, out2, {"A11OY_DEPLOYMENT_ID": "dep-002"}).returncode == 0
    m2 = json.loads(out2.read_text())
    assert m2["git"]["commit"] != m1["git"]["commit"]
    assert m2["frontend"]["bundle_sha256"] != m1["frontend"]["bundle_sha256"]
    assert m2["api_contract"]["sha256"] == m1["api_contract"]["sha256"]
    assert m2["release_id"] != m1["release_id"]


def test_generator_reports_unknown_instead_of_guessing_and_can_require_complete(tmp_path):
    repo = _fixture_repo(tmp_path)
    out = tmp_path / "m.json"
    res = _run_generator(repo, out)
    assert res.returncode == 0, res.stderr
    m = json.loads(out.read_text())
    assert m["deployment"]["id"] == {"value": None, "state": "UNKNOWN", "source": "UNKNOWN"}
    assert m["rollback"]["target"]["state"] == "UNKNOWN"
    strict = _run_generator(repo, tmp_path / "s.json", None, "--require-complete")
    assert strict.returncode != 0
    assert "deployment.id" in strict.stderr


def test_manifest_validates_against_schema(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    repo = _fixture_repo(tmp_path)
    out = tmp_path / "m.json"
    assert _run_generator(repo, out, {"A11OY_DEPLOYMENT_ID": "dep-001"}).returncode == 0
    schema = json.loads((ROOT / "release-manifest.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(json.loads(out.read_text()), schema)


def test_verify_manifest_detects_drift_against_tree(tmp_path):
    import szl_release_manifest as rm

    repo = _fixture_repo(tmp_path)
    out = tmp_path / "m.json"
    assert _run_generator(repo, out).returncode == 0
    manifest = json.loads(out.read_text())
    assert rm.verify_manifest(manifest, repo) == []
    (repo / "console" / "index.html").write_text("<html>tampered</html>\n")
    codes = {f["code"] for f in rm.verify_manifest(manifest, repo)}
    assert "BUNDLE_HASH_MISMATCH" in codes


def test_publication_lag_is_reported_when_runtime_revision_differs_from_manifest():
    import szl_release_manifest as rm

    manifest = {"git": {"commit": SHA_A}}
    findings = rm.compare_runtime(manifest, {"revision": SHA_B})
    assert [f["code"] for f in findings] == ["PUBLICATION_LAG"]
    assert rm.compare_runtime(manifest, {"revision": SHA_A}) == []
    # an unknown runtime revision is not a match
    assert [f["code"] for f in rm.compare_runtime(manifest, {"revision": None})] == [
        "RUNTIME_REVISION_UNKNOWN"
    ]


def _client(monkeypatch, env: dict[str, str]):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import szl_runtime_contracts as contracts

    for key in list(os.environ):
        if key.startswith("A11OY_"):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    app = FastAPI()
    contracts.register(app)
    return TestClient(app)


def test_api_build_exposes_declared_ids_read_only_without_secrets(monkeypatch):
    env = {
        "A11OY_GIT_SHA": SHA_A,
        "A11OY_FRONTEND_BUNDLE_SHA256": "a" * 64,
        "A11OY_API_CONTRACT_SHA256": "b" * 64,
        "A11OY_MODEL_REVISION": "67d60ec577730747055491640cfb91fc4a4b5d25",
        "A11OY_DEPLOYMENT_ID": "dep-001",
        "A11OY_ROLLBACK_TARGET": SHA_B,
        "A11OY_RELEASE_ID": "c" * 12,
        "HF_TOKEN": "hf_must_never_appear",
    }
    client = _client(monkeypatch, env)
    res = client.get("/api/build")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"
    body = res.json()
    assert body["git"]["commit"] == SHA_A
    assert body["frontend"]["bundle_sha256"] == "a" * 64
    assert body["api_contract"]["sha256"] == "b" * 64
    assert body["model"]["revision"] == "67d60ec577730747055491640cfb91fc4a4b5d25"
    assert body["deployment"]["id"] == "dep-001"
    assert body["rollback"]["target"] == SHA_B
    assert body["release_id"] == "c" * 12
    assert "hf_must_never_appear" not in res.text
    assert client.post("/api/build").status_code in (404, 405)


def test_api_build_is_honest_when_nothing_is_declared(monkeypatch):
    body = _client(monkeypatch, {}).get("/api/build").json()
    assert body["status"] == "UNDECLARED"
    assert body["deployment"]["id"] is None
    assert "deployment.id" in body["unknown_fields"]


def test_frontend_carries_release_id_meta_and_footer():
    html = (ROOT / "console" / "index.html").read_text(encoding="utf-8")
    assert 'name="szl-release-id"' in html
    assert 'id="szl-build-footer"' in html
    assert "/assets/szl-build-badge.js" in html
    badge = (ROOT / "console" / "assets" / "szl-build-badge.js").read_text(encoding="utf-8")
    assert "/api/build" in badge
    assert not re.search(r"[0-9a-f]{40}", badge), "badge must not embed a build id"


def test_dockerfile_declares_build_id_args_and_ships_runtime_module():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for name in (
        "A11OY_FRONTEND_BUNDLE_SHA256",
        "A11OY_API_CONTRACT_SHA256",
        "A11OY_MODEL_REVISION",
        "A11OY_DEPLOYMENT_ID",
        "A11OY_ROLLBACK_TARGET",
        "A11OY_RELEASE_ID",
    ):
        assert f"ARG {name}=" in text, name
        assert f"{name}=${{{name}}}" in text, name
    assert "szl_release_manifest.py" in text
