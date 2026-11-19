# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Regressions for the public proof-identity and numerical-sample boundary."""
import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_formula_registry as authority
import szl_puriq_formulas as surface


@pytest.fixture
def client():
    app = FastAPI()
    surface.register(app)
    with TestClient(app) as result:
        yield result


def test_canonical_statements_and_numeric_namespaces_do_not_alias(client):
    response = client.get("/api/a11oy/v1/puriq/formulas")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    formal = body["formal_registry"]
    assert formal["locked_proven_ids"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert formal["locked_proven_count"] == 8
    expected = {
        "F1": ("Replay-Hash Determinism", "Euler-Khipu DAG Identity"),
        "F11": ("Ayni Reciprocity Conservation", "Frustum A-Shrink Law"),
        "F12": ("Kuramoto Additive Fragment", "CRT-Hukulla Schedule"),
    }
    for fid, (formal_name, demo_name) in expected.items():
        proof = formal["formulas"][fid]
        sample = body["numeric_demos"][fid]
        assert proof["name"] == formal_name
        assert sample["name"] == demo_name
        assert proof["record_id"] != sample["record_id"]
        assert sample["proof_status"] == "UNVERIFIED"
        assert sample["locked"] is False
        assert sample["formal_formula_id"] is None
        assert sample["formal_binding"] == "UNKNOWN_NOT_ASSERTED"
        assert proof["runtime_applicability"] == "NOT_ESTABLISHED"
        assert proof["source"]["commit"] in proof["source_url"]
        assert proof["source"]["path"] in proof["source_url"]
    assert body["formulas"] == body["numeric_demos"]
    assert body["execution_authority"] is False
    assert all(not item["can_authorize_action"] for item in formal["formulas"].values())
    assert formal["formulas"]["F23"]["maturity"] == "CONJECTURE_1_ADVISORY"
    assert formal["formulas"]["F23"]["can_constrain_execution"] is False
    assert formal["signature_status"] == "UNSIGNED"


def test_html_and_json_share_validated_authority_and_sample_limits(client):
    body = client.get("/api/a11oy/v1/puriq/formulas").json()
    page = client.get("/formulas")
    assert page.status_code == 200
    assert 'data-registry-digest="' + body["formal_registry"]["registry_digest"] + '"' in page.text
    for record in body["formal_registry"]["formulas"].values():
        assert record["name"] in page.text
        assert record["source_url"] in page.text
    assert "No receipts are minted or signed by this page" in page.text
    assert "UNKNOWN_NOT_ASSERTED" in page.text
    assert "SAMPLE" in page.text
    assert "live self-evaluation + Khipu receipts" not in page.text
    assert "signed Yachay" not in page.text


def test_repeated_reads_are_reproducible_samples_without_receipts(client):
    first = client.get("/api/a11oy/v1/puriq/formulas").json()
    second = client.get("/api/a11oy/v1/puriq/formulas").json()
    assert first == second
    for fid, row in first["numeric_demos"].items():
        detail = client.get(f"/api/a11oy/v1/puriq/formulas/{fid.lower()}")
        assert detail.status_code == 200
        assert detail.json() == row
        assert row["evidence_class"] == "SAMPLE"
        assert row["last_receipts"] == []
        assert row["receipt_minted"] is False
        assert row["chain_verified"] is False
        assert row["last_eval_ts"] is None


@pytest.mark.parametrize("failure", [FileNotFoundError, ValueError])
def test_authority_failure_never_falls_back_to_historical_proof_claims(client, monkeypatch, failure):
    def unavailable(**kwargs):
        raise failure("private path or parser details must not be exposed")

    monkeypatch.setattr(authority, "load_registry", unavailable)
    for path in ("/api/a11oy/v1/puriq/formulas", "/api/a11oy/v1/puriq/formal-registry",
                 "/api/a11oy/v1/puriq/formal-registry/F1", "/formulas"):
        response = client.get(path)
        assert response.status_code == 503
        assert "UNAVAILABLE" in response.text
        assert "private path" not in response.text
    page = client.get("/formulas").text
    assert "Eight locked records" not in page
    assert "Formal identities come from the validated" not in page
    assert "Formal coverage is UNAVAILABLE" in page
    payload = client.get("/api/a11oy/v1/puriq/formulas").json()
    assert payload["formal_registry"]["formulas"] == {}
    assert payload["summary"]["proved_count"] is None
    sample = client.get("/api/a11oy/v1/puriq/formulas/F1").json()
    assert sample["proof_status"] == "UNVERIFIED"
    assert sample["formal_binding"] == "UNKNOWN_NOT_ASSERTED"


def test_rehashed_semantic_registry_tampering_is_rejected(client, monkeypatch, tmp_path):
    document = copy.deepcopy(authority.load_registry())
    document["payload"]["formulas"][0]["name"] = "Euler-Khipu DAG Identity"
    document["registry_digest"]["value"] = authority.compute_payload_digest(document["payload"])
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    original = authority.load_registry
    monkeypatch.setattr(authority, "load_registry", lambda **kwargs: original(path=path, verify=True))
    response = client.get("/api/a11oy/v1/puriq/formal-registry")
    assert response.status_code == 503
    assert response.json()["formulas"] == {}


def test_legacy_claims_cannot_upgrade_numeric_projection(monkeypatch):
    legacy = copy.deepcopy(surface.FORMULA_META)
    legacy["F2"].update(proof_status="PROVED", lean_status="PROVED", locked=True,
                        can_authorize_action=True, theorem_refs=["fabricated"])
    monkeypatch.setattr(surface, "FORMULA_META", legacy)
    row = surface.numeric_demo_metadata()["F2"]
    assert row["proof_status"] == "UNVERIFIED"
    assert row["locked"] is row["can_authorize_action"] is False
    assert "theorem_refs" not in row


@pytest.mark.parametrize("field,value", [
    ("scope", "All nonlinear networks converge under arbitrary initial conditions."),
    ("caveat", "This proves every deployed implementation and grants execution authority."),
    ("scope", ["invalid non-string scope"]),
    ("caveat", {"claim": "invalid non-string caveat"}),
])
def test_rehashed_proof_scope_cannot_expand_reviewed_authority(client, monkeypatch, tmp_path, field, value):
    document = copy.deepcopy(authority.load_registry())
    row = next(item for item in document["payload"]["formulas"] if item["id"] == "F12")
    row[field] = value
    document["registry_digest"]["value"] = authority.compute_payload_digest(document["payload"])
    path = tmp_path / "expanded-scope.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    original = authority.load_registry
    monkeypatch.setattr(authority, "load_registry", lambda **kwargs: original(path=path, verify=True))
    assert client.get("/api/a11oy/v1/puriq/formal-registry").status_code == 503
    response = client.get("/formulas")
    assert response.status_code == 503
    assert "UNAVAILABLE" in response.text


def test_unknown_and_uncovered_identifiers_return_real_json_404(client):
    for path in ("/api/a11oy/v1/puriq/formulas/F999",
                 "/api/a11oy/v1/puriq/formal-registry/F2"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
    assert client.get("/api/a11oy/v1/puriq/formal-registry/F1").json()["name"] == "Replay-Hash Determinism"


def test_fuel_sample_rejects_invalid_observation_and_honors_check_failure(monkeypatch):
    assert surface._fuel_bound_holds(3, 2, 2, 1)
    assert surface._fuel_bound_holds(0, 5, 0, 0)
    assert not surface._fuel_bound_holds(3, 2, 3, 0)
    assert not surface._fuel_bound_holds(3, 2, 2, 2)
    assert not surface._fuel_bound_holds(3, 2, True, 2)
    monkeypatch.setattr(surface, "_fuel_bound_holds", lambda *args: False)
    assert surface.live_snapshot()["F19"]["identity_holds"] is False


def test_html_escapes_demo_metadata(monkeypatch):
    legacy = copy.deepcopy(surface.FORMULA_META)
    legacy["F1"]["name"] = '<script>alert("sample")</script>'
    monkeypatch.setattr(surface, "FORMULA_META", legacy)
    page = surface._render_html()
    assert '<script>alert("sample")</script>' not in page
    assert "&lt;script&gt;" in page


@pytest.mark.parametrize("matrix,expected", [
    ((-4.792262904649927, -2.9681771040370175, -0.0025286602280480963, 3.7412489924208394), -0.0025286602280480963),
    ((1, -1, -1, 1), 0),
    ((3, 2, 4, 1), 2),
    ((2, 2, 2, 2), 2),
])
def test_game_sample_value_respects_pure_and_mixed_equilibria(matrix, expected):
    value, holds = surface._zero_sum_2x2_value(*matrix)
    assert holds is True
    assert value == pytest.approx(expected)
    assert min(matrix) <= value <= max(matrix)


def test_sample_failure_and_missing_observations_are_visible(client):
    samples = client.get("/api/a11oy/v1/puriq/formulas").json()["numeric_demos"]
    assert samples["F10"]["identity_holds"] is False
    assert samples["F10"]["sample_check"] == "FAIL"
    assert "1.5e-6" in samples["F10"]["identity_doc"]
    assert samples["F23"]["identity_holds"] is None
    assert samples["F23"]["sample_check"] == "NOT_EVALUATED"
    assert "action-space cardinality unavailable" in samples["F23"]["sample_inputs"]
    page = client.get("/formulas").text
    assert "FAIL (sample only)" in page
    assert "NOT EVALUATED (sample only)" in page
