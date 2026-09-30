# SPDX-License-Identifier: Apache-2.0
"""Qualify real-response witness semantics using explicit synthetic transport."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
import pytest
from .test_finance_release_boundaries import projection

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1" * 40
analytics = importlib.import_module("verticals.puriq-markets.runtime.analytics")
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def witness():
    gate = load("hf_finance_functional_gate")
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION},
        fetch=lambda plan: json.dumps([[plan.parameters["start"] + i * 86400, 50, 200, 100,
                                       100 + i * .1 + i % 5, 1] for i in range(260)][::-1]).encode())
    fixture = analytics.compute(client, "signals", "AAPL", "fixture")
    live = analytics.compute(client, "signals", "BTC-USD", "coinbase")
    states = {}

    def request(path, content):
        if path == "/api/build-info":
            body = {"schema": "szl.build-info/v1", "source_repository": "szl-holdings/a11oy",
                    "source_revision": REVISION, "hf_repository": "SZLHOLDINGS/finance"}
        elif path == "/api/finance/providers":
            body = client.registry()
        elif path.endswith("signals/AAPL?origin=fixture"):
            body = fixture
        elif path.endswith("quote/AAPL?origin=fixture"):
            body = analytics.compute(client, "quote", "AAPL", "fixture")
        elif path.endswith("/portfolio"):
            body = analytics.portfolio(client, content)
        elif path.endswith("/receipts/verify"):
            valid = analytics.verify(content)
            body = analytics.envelope(client, "receipt-verification",
                {"verified": valid, "state": "INTEGRITY_VALID" if valid else "INVALID", "authenticity_established": False}, {})
        elif "/observations/fred-series" in path:
            return 403, json.dumps({"error": "USE_PRIVATE_CANONICAL_SOURCE_ENDPOINT", "execution_enabled": False}).encode()
        else:
            body = live
        body = deepcopy(body)
        if path in states:
            body = states[path](body)
        return 200, json.dumps(body).encode()
    return gate, request, states


def test_all_public_functional_contracts_accept_only_exact_source(witness):
    gate, request, _ = witness
    result = gate.observe_finance(REVISION, request=request)
    assert result["complete"] is True
    assert result["live_coinbase_verified"] is True
    assert len(result["probes"]) == 9
    assert result["receipt_authenticity_established"] is False
    assert all(row["accepted"] for row in result["probes"])


@pytest.mark.parametrize("path,mutate", [
    ("/api/build-info", lambda b: {**b, "source_revision": "2" * 40}),
    ("/api/finance/v2/signals/AAPL?origin=fixture", lambda b: {"ok": False, "error": "CANONICAL_INTERNAL_ERROR"}),
    ("/api/finance/v2/signals/BTC-USD", lambda b: {**b, "truth_label": "MEASURED"}),
    ("/api/finance/providers", lambda b: {**b, "sources": b["sources"][:-1]}),
])
def test_healthy_shell_cannot_mask_failed_or_misbound_functionality(witness, path, mutate):
    gate, request, states = witness
    states[path] = mutate
    result = gate.observe_finance(REVISION, request=request)
    assert result["complete"] is False
    assert any(not row["accepted"] for row in result["probes"])


def test_no_raw_transport_error_or_upstream_body_is_retained(witness):
    gate, _, _ = witness
    def request(path, content):
        raise OSError("secret and arbitrary upstream payload")
    result = gate.observe_finance(REVISION, request=request)
    assert result["complete"] is False
    assert "secret" not in json.dumps(result)
    assert all(not row["accepted"] for row in result["probes"])


def test_automatic_projection_follows_relock_and_shares_existing_writer():
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/hf-sync.yml").read_text())
    job = workflow["jobs"]["publish-finance-projection"]
    assert job["needs"] == "relock"
    assert job["env"]["SZL_FLAGSHIP_SCOPE"] == "finance"
    assert job["concurrency"] == {"group": "hf-publish-vertical-flagships", "cancel-in-progress": False}
    text = json.dumps(job)
    assert "hf_exact_main_ownership.py" in text
    assert "hf_publish_vertical_flagships_v4.py" in text
    assert "create_repo" not in text


def test_existing_publisher_requires_functional_success_for_finance(monkeypatch):
    publisher = load("hf_publish_vertical_flagships_v4_impl")
    monkeypatch.setattr(publisher, "_base_observation_passes", lambda *a, **kw: True)
    arguments = {"source_revision": REVISION, "workflow_run_id": "1"}
    assert not publisher.observation_passes({"slug": "finance"}, **arguments)
    assert not publisher.observation_passes({"slug": "finance", "finance_functional": {"complete": False}}, **arguments)
    assert publisher.observation_passes({"slug": "finance", "finance_functional": {"complete": True}}, **arguments)
    assert publisher.observation_passes({"slug": "terra"}, **arguments)


@pytest.mark.parametrize("failure,code", [
    ("_FinanceTimeoutException", "CANONICAL_SOURCE_TIMEOUT"),
    ("_FinanceTransportError", "CANONICAL_SOURCE_TRANSPORT_UNAVAILABLE"),
    ("internal", "CANONICAL_INTERNAL_ERROR"),
])
def test_exact_generated_runtime_distinguishes_safe_fault_layers(projection, failure, code):
    from types import SimpleNamespace
    http, state = projection
    namespace = state["namespace"]
    fault = NameError("arbitrary secret text") if failure == "internal" else namespace[failure]("arbitrary secret text")
    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 5, "follow_redirects": False, "trust_env": False}
        def __enter__(self):
            raise fault
        def __exit__(self, *args):
            pass
    namespace["httpx"] = SimpleNamespace(Client=Client)
    reply = http.get("/api/finance/providers")
    assert reply.status_code == 503 and reply.json()["error"] == code
    assert "secret" not in reply.text
