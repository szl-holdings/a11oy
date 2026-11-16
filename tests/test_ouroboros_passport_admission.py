#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline fixtures: these tests do not qualify a deployed model or a receipt issuer."""

import copy
import json
import threading
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from ouroboros_passport.cli import main as cli
from ouroboros_passport.evidence import receipt_digest
from ouroboros_passport.promotion import evaluate
from ouroboros_passport.serve import Handler
from ouroboros_passport.verifier import verify


TERMS = (
    "tenant_isolated", "source_authorized", "provenance_complete",
    "transform_chain_verified", "license_policy_clear", "split_disjoint",
    "evaluation_passed", "runtime_witnessed", "rollback_available",
)


def fixture_passport():
    passport = {
        "passport_version": "ouroboros-passport/0.1",
        "model_id": "SZLHOLDINGS/offline-fixture",
        "tenant": "fixture-tenant",
        "revision": "fixture-r1",
        "created_at": "2026-01-01T00:00:00Z",
        "parents": [],
        "sections": {"promotion": {"evidence": [
            {"name": term, "class": "MEASURED", "value": True, "source": "offline-fixture"}
            for term in TERMS
        ]}},
    }
    return seal(passport)


def seal(passport):
    passport.pop("digest", None)
    passport["digest"] = receipt_digest(passport)
    return passport


def observation(passport, term="evaluation_passed"):
    return next(ev for ev in passport["sections"]["promotion"]["evidence"]
                if ev["name"] == term)


@pytest.mark.parametrize("term", TERMS)
def test_measured_false_blocks_each_required_term(term):
    passport = fixture_passport()
    observation(passport, term)["value"] = False
    decision = evaluate(seal(passport))
    assert decision["eligible"] is False
    assert decision["decision"] == "CANDIDATE"
    assert any(item["term"] == term for item in decision["blocking"])


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false", "", [], {}, [True]])
def test_required_value_must_be_boolean_true(value):
    passport = fixture_passport()
    observation(passport)["value"] = value
    assert evaluate(seal(passport))["eligible"] is False


@pytest.mark.parametrize("cls", ["UNKNOWN", "ABSTAIN", "NOT_RUN", "BLOCKED"])
def test_true_value_does_not_override_evidence_class(cls):
    passport = fixture_passport()
    observation(passport)["class"] = cls
    assert evaluate(seal(passport))["eligible"] is False


@pytest.mark.parametrize("mode", ["missing_digest", "tampered"])
def test_promotion_requires_valid_digest(mode):
    passport = fixture_passport()
    if mode == "missing_digest":
        passport.pop("digest")
    else:
        passport["revision"] = "tampered-revision"
    decision = evaluate(passport)
    assert decision["eligible"] is False
    assert decision["passed"] == []


@pytest.mark.parametrize("duplicate_first", [False, True])
@pytest.mark.parametrize("duplicate_value", [False, True])
def test_duplicate_required_evidence_is_ambiguous_in_either_order(duplicate_first, duplicate_value):
    passport = fixture_passport()
    duplicate = copy.deepcopy(observation(passport))
    duplicate["value"] = duplicate_value
    other = {"evidence": [duplicate]}
    if duplicate_first:
        passport["sections"] = {"other": other, **passport["sections"]}
    else:
        passport["sections"]["other"] = other
    decision = evaluate(seal(passport))
    assert decision["eligible"] is False
    assert any(item["term"] == "evaluation_passed" for item in decision["blocking"])


@pytest.mark.parametrize("source", ["", None, "   ", [], {}, True])
def test_measured_source_must_be_nonempty_text(source):
    passport = fixture_passport()
    observation(passport)["source"] = source
    seal(passport)
    assert verify(passport)["valid"] is False
    assert evaluate(passport)["eligible"] is False


@pytest.mark.parametrize("passport", [None, [], "not-an-object", 1])
def test_nonobject_passport_is_a_blocked_decision(passport):
    decision = evaluate(passport)
    assert decision["eligible"] is False
    assert decision["passed"] == []


@pytest.mark.parametrize("sections", [
    None, [], {"bad": None}, {"bad": {"evidence": {}}},
    {"bad": {"evidence": [None]}},
    {"bad": {"evidence": [{"name": [], "class": "MEASURED", "source": "fixture", "value": True}]}},
])
def test_malformed_evidence_is_a_blocked_decision(sections):
    passport = fixture_passport()
    passport["sections"] = sections
    assert evaluate(seal(passport))["eligible"] is False


def test_nonserializable_passport_fails_closed():
    passport = fixture_passport()
    passport["unsupported"] = object()
    assert verify(passport)["valid"] is False
    assert evaluate(passport)["eligible"] is False


def test_complete_fixture_is_eligible_without_mutating_it():
    passport = fixture_passport()
    original = copy.deepcopy(passport)
    result = evaluate(passport)
    assert result["eligible"] is True
    assert result["decision"] == "PROMOTED"
    assert set(result["passed"]) == set(TERMS)
    assert result["blocking"] == []
    assert passport == original


@pytest.fixture
def server():
    passport = fixture_passport()

    class FixtureHandler(Handler):
        passports = {passport["model_id"]: passport, "plain": copy.deepcopy(passport)}

    with HTTPServer(("127.0.0.1", 0), FixtureHandler) as httpd:
        thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True,
        )
        thread.start()
        try:
            yield "http://127.0.0.1:" + str(httpd.server_port), FixtureHandler.passports
        finally:
            httpd.shutdown()
            thread.join(timeout=2)
            assert not thread.is_alive()


@pytest.mark.parametrize("model_path", [
    "SZLHOLDINGS/offline-fixture", "SZLHOLDINGS%2Foffline-fixture", "plain",
])
@pytest.mark.parametrize("route", ["anatomy", "promotion"])
def test_real_http_handles_namespaced_and_encoded_ids_and_queries(server, model_path, route):
    origin, passports = server
    before = copy.deepcopy(passports)
    with urlopen(origin + "/v1/models/" + model_path + "/" + route + "?view=json", timeout=2) as response:
        assert response.status == 200
        body = json.load(response)
    if route == "anatomy":
        assert body["passport"]["model_id"] == "SZLHOLDINGS/offline-fixture"
        assert body["verification"]["valid"] is True
    else:
        assert body["eligible"] is True
    assert passports == before


@pytest.mark.parametrize("mutation", ["false_value", "tampered"])
def test_real_http_cannot_promote_failed_or_tampered_passport(server, mutation):
    origin, passports = server
    passport = passports["SZLHOLDINGS/offline-fixture"]
    if mutation == "false_value":
        observation(passport)["value"] = False
        seal(passport)
    else:
        passport["revision"] = "tampered"
    with urlopen(origin + "/v1/models/SZLHOLDINGS/offline-fixture/promotion", timeout=2) as response:
        assert json.load(response)["eligible"] is False


def test_digest_and_inventory_routes_ignore_query_strings(server):
    origin, passports = server
    digest = passports["SZLHOLDINGS/offline-fixture"]["digest"]
    for path in ("/healthz?view=json", "/v1/models?view=json", "/v1/passports/" + digest + "?view=json"):
        with urlopen(origin + path, timeout=2) as response:
            assert response.status == 200
            assert isinstance(json.load(response), dict)


def test_unknown_model_remains_not_found(server):
    origin, _ = server
    with pytest.raises(HTTPError) as error:
        urlopen(origin + "/v1/models/SZLHOLDINGS/missing/anatomy", timeout=2)
    assert error.value.code == 404


@pytest.mark.parametrize("command", ["verify", "promote"])
@pytest.mark.parametrize("valid", [False, True])
def test_cli_exit_status_matches_the_result(tmp_path, capsys, command, valid):
    passport = fixture_passport()
    if not valid:
        passport.pop("digest")
    path = tmp_path / "fixture.passport.json"
    path.write_text(json.dumps(passport), encoding="utf-8")
    assert cli([command, str(path)]) == (0 if valid else 1)
    body = json.loads(capsys.readouterr().out)
    assert body["valid" if command == "verify" else "eligible"] is valid


def test_cli_measured_failure_is_nonzero(tmp_path, capsys):
    passport = fixture_passport()
    observation(passport)["value"] = False
    path = tmp_path / "fixture.passport.json"
    path.write_text(json.dumps(seal(passport)), encoding="utf-8")
    assert cli(["promote", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["eligible"] is False
