# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Static contracts for the five-space operator BIND surface on a-11-oy.com.

Locks BIND_AS_A11OY_PACKAGE honesty without pretending a local SAMPLE compile
is a live Hub, a production certificate, a Vite dump onto the flagship, or /console.
"""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import szl_five_space as op

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "web" / "five-space.html").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
NAV = (ROOT / "a11oy_nav_wireup.py").read_text(encoding="utf-8")


def test_first_paint_is_connecting_never_live_or_running() -> None:
    assert 'id="liveTag" aria-live="polite">OPERATOR · CONNECTING<' in PAGE
    assert 'id="organBadge">BIND · connecting<' in PAGE
    assert "first paint is <b>CONNECTING</b>" in PAGE.lower() or "First paint is <b>CONNECTING</b>" in PAGE
    assert "never fabricates <b>LIVE</b>, <b>RUNNING</b>, or <b>PASS</b>" in PAGE
    assert "OPERATOR · LIVE" not in PAGE
    assert "Hub RUNNING" not in PAGE or "UNAVAILABLE" in PAGE


def test_page_does_not_claim_certificate_or_flagship() -> None:
    assert "not a second flagship" in PAGE.lower()
    assert "not a production certificate" in PAGE.lower()
    assert "does not replace /console" in PAGE.lower()
    assert "BIND_AS_A11OY_PACKAGE" in PAGE
    assert "a11oy.com" in PAGE  # never-origin disclosure
    assert "Vite dump" in PAGE or "vite dump" in PAGE.lower()
    assert "sovereign=false" in PAGE


def test_five_named_spaces_present() -> None:
    for name in ("Command", "Loop", "Queue", "Memory", "Ledger"):
        assert name in PAGE
    assert 'data-space="command"' in PAGE
    assert 'data-space="ledger"' in PAGE
    assert "UNSIGNED-honest" in PAGE
    assert "a11oy.net/five-space/" in PAGE


def test_status_is_bind_unsigned_and_unmeasured() -> None:
    s = op.status()
    assert s["state"] == "BIND"
    assert s["honesty"]["certified"] is False
    assert s["honesty"]["proven_trust"] is False
    assert s["honesty"]["sovereign"] is False
    assert s["honesty"]["operator"] == "STRUCTURAL-ONLY"
    assert s["honesty"]["replaces_console"] is False
    assert s["honesty"]["vite_dump"] is False
    assert "UNAVAILABLE" in s["honesty"]["energy_joule"]
    assert s["product"]["certified"] is False
    assert s["product"]["path"] == "/five-space"
    assert [sp["id"] for sp in s["spaces"]] == [
        "command",
        "loop",
        "queue",
        "memory",
        "ledger",
    ]
    assert s["spaces"][1]["honesty"] == "SAMPLE"
    assert s["khipu_receipt"]["proven_trust"] is False
    assert s["khipu_receipt"]["signed"] is False
    assert s["khipu_receipt"]["signature_verified"] is False
    assert s["khipu_receipt"]["kind"] == "UNSIGNED-honest"
    assert s["proof"]["record"] == "https://a11oy.net/five-space/"


def test_healthz_never_claims_hub_running() -> None:
    h = op.healthz()
    assert h["ok"] is True
    assert h["hub_running"] is False
    assert h["certified"] is False
    assert h["proven_trust"] is False
    assert h["sovereign"] is False


def test_routes_wired_in_serve_and_image() -> None:
    assert 'app.add_api_route("/five-space", _ptg_serve("five-space.html"), methods=["GET", "HEAD"]' in SERVE
    assert 'app.add_api_route("/a11oy/five-space", _ptg_serve("five-space.html"), methods=["GET", "HEAD"]' in SERVE
    assert "import szl_five_space" in SERVE
    assert "COPY szl_five_space.py" in DOCKER
    assert "web/five-space.html" in DOCKER


def test_page_cites_two_origins_and_not_console() -> None:
    assert "a-11-oy.com/five-space" in PAGE
    assert "a11oy.net/five-space/" in PAGE
    assert "does not replace /console" in PAGE.lower()
    assert "not a second flagship" in PAGE.lower()


def test_landing_and_nav_cite_the_package() -> None:
    assert 'id="bind-five-space"' in LANDING
    assert 'href="/five-space"' in LANDING
    assert "Five-space operator" in LANDING
    assert "Honesty LIVE" not in LANDING
    assert '("/five-space"' in NAV
    assert '"/five-space": "Sovereign & Agentic Core"' in NAV


def test_zero_cdn_and_mobile() -> None:
    assert "cdn.jsdelivr.net" not in PAGE
    assert "fonts.googleapis.com" not in PAGE
    assert '<script src="http' not in PAGE
    assert "@media(max-width:760px)" in PAGE
    mobile_css = PAGE.split("@media(max-width:760px){", 1)[1].split(
        "@media(max-width:420px){", 1
    )[0]
    assert (
        '[data-related-surfaces="qa10"]'
        "{padding-bottom:calc(4.6rem + env(safe-area-inset-bottom))!important;}"
    ) in mobile_css
    assert 'class="table-scroll" role="region"' in PAGE
    assert "repeat(auto-fit,minmax(min(100%,180px),1fr))" in PAGE
    assert "min-height:44px" in PAGE


def _install_untrusted_dag(monkeypatch, signature=None, chain_claim=True):
    calls = []
    rows = [{"digest": "a" * 64, "signature": signature}]

    def emit(*_args, **_kwargs):
        calls.append("emit")
        row = {
            "signature": signature,
            "signature_verified": True,
            "chain_verified": chain_claim,
            "digest": "b" * 64,
        }
        rows.append(row)
        return row

    def sign(*_args, **_kwargs):
        calls.append("sign")
        return signature

    dag = SimpleNamespace(
        emit=emit,
        sign=sign,
        depth=lambda: len(rows),
        head=lambda: rows[-1]["digest"],
        verify_chain=lambda: {"ok": chain_claim},
    )

    def get_dag(*_args, **_kwargs):
        calls.append("get_dag")
        return dag

    monkeypatch.setitem(sys.modules, "szl_khipu", SimpleNamespace(get_dag=get_dag, sign=sign))
    return calls, rows, dag


def _assert_unsigned_content_projection(receipt):
    assert receipt["signature"] is None
    assert receipt["signed"] is False
    assert receipt["signature_verified"] is False
    assert receipt["signature_status"] == "UNSIGNED"
    assert receipt["signature_verification"] == "UNAVAILABLE"
    assert receipt["kind"] == "UNSIGNED-honest"
    assert receipt["proven_trust"] is False
    assert receipt["digest_kind"] == "CONTENT-HASH-ONLY"
    assert receipt["chain_verified"] is None
    assert receipt["chain_status"] == "UNAVAILABLE"
    assert receipt["seq"] is None
    assert receipt["prev"] is None
    assert receipt["chain_depth"] is None
    assert receipt["head_digest"] is None


@pytest.mark.parametrize(
    "signature",
    [None, "", "DSSE_PLACEHOLDER", "not-a-signature", " ", True, {"verified": True}, ["sig"]],
    ids=["absent", "empty", "placeholder", "arbitrary", "whitespace", "boolean", "object", "list"],
)
def test_unverified_signature_presence_never_promotes_signing(monkeypatch, signature):
    calls, rows, dag = _install_untrusted_dag(monkeypatch, signature=signature)
    before = json.dumps(rows, sort_keys=True), dag.depth(), dag.head()
    _assert_unsigned_content_projection(op.status()["khipu_receipt"])
    assert calls == []
    assert (json.dumps(rows, sort_keys=True), dag.depth(), dag.head()) == before


@pytest.mark.parametrize("chain_claim", [True, False, None, "true", 1, {"ok": True}])
def test_chain_claim_is_not_signature_or_current_content_evidence(monkeypatch, chain_claim):
    calls, _, _ = _install_untrusted_dag(monkeypatch, chain_claim=chain_claim)
    _assert_unsigned_content_projection(op.status()["khipu_receipt"])
    assert calls == []


def test_missing_khipu_is_explicit_unsigned_content_hash(monkeypatch):
    monkeypatch.setitem(sys.modules, "szl_khipu", None)
    result = op.status()
    receipt = result["khipu_receipt"]
    _assert_unsigned_content_projection(receipt)
    body = {
        "receipt_type": op._RECEIPT_TYPE,
        "organ": op._ORGAN_NAME,
        "state": "BIND",
        "sha": result["source"]["sha"],
        "certified": False,
        "proven_trust": False,
        "sovereign": False,
        "energy_joule": "UNAVAILABLE",
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert receipt["digest"] == receipt["payload_digest"] == hashlib.sha3_256(raw).hexdigest()
    assert receipt["alg"] == "sha3_256"
    assert "No receipt was appended" in receipt["note"]


def test_unavailable_khipu_provider_is_not_called(monkeypatch):
    calls = []

    def unavailable(*_args, **_kwargs):
        calls.append("provider")
        raise RuntimeError("optional hash-chain provider unavailable")

    monkeypatch.setitem(sys.modules, "szl_khipu", SimpleNamespace(get_dag=unavailable))
    _assert_unsigned_content_projection(op.status()["khipu_receipt"])
    assert calls == []


def test_repeated_status_and_selftest_do_not_append_or_sign(monkeypatch):
    calls, rows, dag = _install_untrusted_dag(monkeypatch, signature="DSSE_PLACEHOLDER")
    before = json.dumps(rows, sort_keys=True), dag.depth(), dag.head()
    digests = [op.status()["khipu_receipt"]["digest"] for _ in range(5)]
    assert len(set(digests)) == 1
    assert op._selftest()["ok"] is True
    assert calls == []
    assert (json.dumps(rows, sort_keys=True), dag.depth(), dag.head()) == before


@pytest.mark.parametrize("fallback_routes", [False, True], ids=["starlette", "fastapi-fallback"])
def test_assembled_get_and_head_leave_receipt_state_unchanged(monkeypatch, fallback_routes):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import starlette.routing

    calls, rows, dag = _install_untrusted_dag(monkeypatch, signature="DSSE_PLACEHOLDER")
    before = json.dumps(rows, sort_keys=True), dag.depth(), dag.head()
    app = FastAPI()
    if fallback_routes:
        def unavailable_route(*_args, **_kwargs):
            raise RuntimeError("exercise existing FastAPI registration fallback")

        with monkeypatch.context() as route_patch:
            route_patch.setattr(starlette.routing, "Route", unavailable_route)
            registration = op.register(app)
    else:
        registration = op.register(app)
    assert registration["routes"] == [
        "/api/a11oy/v1/five-space/healthz",
        "/api/a11oy/v1/five-space/status",
        "/v1/five-space/healthz",
        "/v1/five-space/status",
    ]
    with TestClient(app) as client:
        for _ in range(3):
            for path in registration["routes"]:
                response = client.get(path)
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("application/json")
                if path.endswith("/status"):
                    _assert_unsigned_content_projection(response.json()["khipu_receipt"])
                head = client.head(path)
                assert head.status_code == (405 if fallback_routes else 200)
    assert calls == []
    assert (json.dumps(rows, sort_keys=True), dag.depth(), dag.head()) == before


def test_receipt_truth_workflow_runs_the_scoped_suite_without_bypass():
    import yaml

    workflow = yaml.load(
        (ROOT / ".github/workflows/five-space-receipt-truth-tests.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["receipt-truth"]
    assert "if" not in job and "needs" not in job
    assert int(job["timeout-minutes"]) <= 10
    assert job["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert job["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    steps = job["steps"]
    assert steps[0]["uses"] == "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert steps[0]["with"]["persist-credentials"] == "false"
    assert steps[1]["uses"] == "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
    assert steps[1]["with"]["python-version"] == "3.12"
    assert "--require-hashes -r .github/requirements/ci-core.txt" in steps[2]["run"]
    assert steps[3]["run"] == (
        "python -m pytest -p no:cacheprovider tests/test_five_space_bind.py -q --tb=short"
    )
    for step in steps:
        assert "if" not in step and "continue-on-error" not in step
        assert "${{ secrets." not in json.dumps(step)
