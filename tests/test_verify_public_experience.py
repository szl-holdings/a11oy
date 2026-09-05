#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Release verification must detect broken proof while withholding capabilities."""

import copy
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_public_experience as experience
from scripts import verify_public_experience as verifier


ROOT = Path(__file__).resolve().parents[1]


def hero(text=""):
    return '<section id="a11oy-experience"><div class="a11oy-experience-copy">' + " ".join(verifier.COPY) + text + '</div><p>Lots of nonhero copy is deliberately not counted.</p></section>'


def test_hero_scope_nested_markup_and_hidden_text():
    source = '<header class="hero">Unrelated legacy page hero</header>' + hero('<span hidden>' + " hidden" * 40 + '</span>')
    checks = verifier.hero_checks(source)
    assert all(check.ok for check in checks)
    assert "words=28" in next(check.detail for check in checks if check.name == "hero-word-budget")
    excessive = verifier.hero_checks(hero(" extra" * 10))
    assert not next(check.ok for check in excessive if check.name == "hero-word-budget")


def test_hidden_required_copy_cannot_supply_a_false_pass():
    source = '<section id="a11oy-experience"><div class="a11oy-experience-copy"><span hidden>' + " ".join(verifier.COPY) + '</span>Welcome</div></section>'
    assert not next(check.ok for check in verifier.hero_checks(source) if check.name == "hero-copy")
    assert not verifier.hero_checks(hero() + hero())[0].ok


@pytest.mark.parametrize("change", ["private", "unknown_asset", "external_host", "live_scenario", "arbitrary_action", "credential_uri"])
def test_registry_rejects_public_boundary_changes(change):
    registry = verifier.read_json(ROOT / "governance/public-estate.v1.json")
    projection = verifier.read_json(ROOT / "config/public-experience/estate-projection.v1.json")
    scenarios = verifier.read_json(ROOT / "config/public-experience/scenarios.v1.json")
    assert verifier.public_config_checks(registry, projection, scenarios)[0].ok
    if change == "private":
        projection["assets"][0]["public"] = False
    elif change == "unknown_asset":
        projection["assets"][0]["id"] = "internal-only-product"
    elif change == "external_host":
        registry["platforms"][0]["base_url"] = "https://unlisted.invalid"
    elif change == "live_scenario":
        scenarios["scenarios"][0]["data_state"] = "LIVE"
    elif change == "arbitrary_action":
        scenarios["scenarios"][0]["action"] = "execute.operation"
    else:
        scenarios["scenarios"][0]["evidence"][0]["uri"] = "https://user:credential@huggingface.co/source"
    assert not verifier.public_config_checks(registry, projection, scenarios)[0].ok


@pytest.mark.parametrize("url", ["https://user:secret@example.com", "https://example.com/?token=value", "https://example.com/path", "//example.com", "http://example.com", "https://example.com/#secret"])
def test_base_url_refuses_credential_and_redirect_hazards(url):
    with pytest.raises(ValueError):
        verifier.validated_base(url)
    assert verifier.validated_base("http://127.0.0.1:7860/") == "http://127.0.0.1:7860"


class Response(io.BytesIO):
    status = 200

    def __init__(self, value, content_type):
        super().__init__(value)
        self.headers = {"Content-Type": content_type}


class Opener:
    def __init__(self, response):
        self.response = response

    def open(self, request, timeout):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_html_200_and_oversized_json_do_not_pass_http_check():
    client = verifier.HttpClient("https://example.com")
    client.opener = Opener(Response(b'<html>SPA shell</html>', "text/html"))
    with pytest.raises(verifier.VerificationError, match="content type"):
        client.request(verifier.PREFIX + "/health")
    client.opener = Opener(Response(b" " * (verifier.MAX_RESPONSE_BYTES + 1), "application/json"))
    with pytest.raises(verifier.VerificationError, match="bounded byte"):
        client.request(verifier.PREFIX + "/health")


def test_transport_report_never_echoes_response_body_or_capability():
    client = verifier.HttpClient("https://example.com")
    client.opener = Opener(HTTPError("https://example.com", 403, "expcap1.secret-value", {}, None))
    with pytest.raises(verifier.VerificationError) as result:
        client.request(verifier.PREFIX + "/health")
    assert "403" in str(result.value)
    assert "secret-value" not in str(result.value)


class ServiceClient:
    def __init__(self):
        service = experience.PublicExperienceService()
        app = FastAPI()
        experience.register(app, service=service)
        self.client = TestClient(app, base_url="https://testserver")
        self.methods = []

    def request(self, path, *, method="GET", payload=None, headers=None, media="application/json"):
        self.methods.append(method)
        fields = {"Origin": "https://testserver", **(headers or {})}
        response = self.client.request(method, path, json=payload, headers=fields)
        assert response.status_code in {200, 201}, (path, response.status_code)
        return response.text if media == "text/event-stream" else response.json()


def test_read_only_default_and_all_five_explicit_simulations(capsys):
    client = ServiceClient()
    checks = verifier.http_checks(client)
    assert all(check.ok for check in checks)
    assert client.methods == ["GET", "GET", "GET"]
    client = ServiceClient()
    checks = verifier.http_checks(client, exercise=True)
    assert all(check.ok for check in checks), [(check.name, check.detail) for check in checks if not check.ok]
    assert len([check for check in checks if check.name.startswith("simulation:")]) == 5
    report = json.dumps([verifier.asdict(check) for check in checks])
    assert "expcap1." not in report and "capability_token" not in report
    assert "stage=POLICY_DENIED" in report and "stage=VERIFICATION_FAILED" in report
    assert "signer=UNSIGNED" in report and "integrity=PARTIAL" in report
    assert capsys.readouterr().out == ""


def test_failed_preflight_blocks_simulation_posts():
    client = ServiceClient()
    original = client.request

    def broken(path, **kwargs):
        response = original(path, **kwargs)
        if path.endswith("/health"):
            response["data_state"] = "LIVE"
        return response

    client.request = broken
    checks = verifier.http_checks(client, exercise=True)
    assert any(not check.ok for check in checks)
    assert "POST" not in client.methods


def test_event_chain_tampering_and_unclosed_sse_fail():
    service = experience.PublicExperienceService()
    view, _ = service.create_session(experience.CreateSessionRequest(scenario_id="screen-vessel"), idempotency_key=None, origin="https://testserver")
    receipt = service.get_receipt(view.receipt_id).model_dump(mode="json", by_alias=True)
    events = receipt["events"]
    assert verifier.validate_event_chain(events, view.session_id, view.scenario_id)
    changed = copy.deepcopy(events)
    changed[0]["action"] = "simulate.changed"
    with pytest.raises(verifier.VerificationError, match="digest"):
        verifier.validate_event_chain(changed, view.session_id, view.scenario_id)
    with pytest.raises(verifier.VerificationError, match="end marker"):
        verifier.parse_events("")


def test_missing_tools_are_required_failure_and_scope_stays_honest(monkeypatch, tmp_path, capsys):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(verifier.subprocess, "run", missing)
    result = verifier.run_command(tmp_path, ["missing-tool"], "build")
    assert result.required is True and result.ok is False
    monkeypatch.setattr(verifier, "static_checks", lambda root: [verifier.Check("source", True, "fixture")])
    output = tmp_path / "evidence.json"
    assert verifier.main(["--repo", str(tmp_path), "--strict", "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["status"] == "PASS_FOR_REQUESTED_SCOPE"
    assert report["scope"]["production_image_build"] == "NOT_RUN"
    assert report["scope"]["browser_accessibility_performance"] == "NOT_RUN"
    assert report["scope"]["deployment_identity"] == "NOT_VERIFIED"
    assert "PASS_FOR_REQUESTED_SCOPE" in capsys.readouterr().out
