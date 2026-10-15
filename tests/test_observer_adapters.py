#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Staged adapter tests. Local fixture models are never represented as live evidence.

Actual strict route/engine/eval/loop code executes with an isolated HTTP provider;
keys are temporary test keys; native owner callbacks retain exact signed bytes.
"""
import asyncio
import ast
import hashlib
from datetime import datetime, timezone
import base64
import copy
import importlib.util
import json
import sys
import threading
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

import observer_adapters as adapters
from tools import execution_acceptance as a

MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
SUITE = "native-adapter-fixture"
LIMITS = {"max_model_requests": 2, "max_output_tokens": 100, "max_elapsed_seconds": 30}
CREDS = {"authorization": "Bearer adapter-fixture-operator", "x-a11oy-tenant": "adapter-fixture-tenant"}


def actual_host_signer(private, pem, key_id, observed=None):
    """Compile the exact shipped host signer functions with temporary key globals."""
    source = Path(__file__).resolve().parents[1] / "serve.py"
    names = {"_a11oy_pae", "_a11oy_canonical", "_a11oy_sign_receipt"}
    selected = [node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(selected) == 3
    namespace = {"_A11OY_KEY_SOURCE": "persistent:temporary-test-key", "_A11OY_KEYID": key_id,
        "_A11OY_PRIV": private, "_A11OY_PUB_PEM": pem.decode(), "_A11OY_KEY_ERR": None,
        "_A11OY_PAYLOAD_TYPE": adapters.HOST_TYPE, "_b64v2": base64, "_hashv2": hashlib,
        "_jsonv2": json, "_dtv2": datetime, "_tzv2": timezone, "_ecv2": ec, "_hashesv2": hashes}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source) + ":actual-host-signer", "exec"), namespace)
    if observed is not None:
        canonical = namespace["_a11oy_canonical"]
        def observe(value):
            observed.append(copy.deepcopy(value))
            return canonical(value)
        namespace["_a11oy_canonical"] = observe
    return namespace["_a11oy_sign_receipt"]


def plan():
    nonce = "a" * 64
    bodies = {
        "policy-decide": {"agent": "execution-acceptance", "request_id": nonce + ":policy-decide",
                          "action": {"operation": "inspect-synthetic-record", "record_id": "acceptance-only"}},
        "policy-compliance": {"framework": "NIST"},
        "operator-ask": {"question": adapters.QUESTION},
        "eval-run": {"model_id": MODEL, "suite": SUITE, "execution_mode": "live", "execution_limits": LIMITS},
        "agentloop-run": {"model_id": MODEL, "eval_suite": SUITE, "task": "What is two plus two?",
                          "mode": "chat", "sandbox": False, "max_retries": 0, "consult_brain": False,
                          "allocate_energy": False, "execution_limits": LIMITS},
    }
    return {"run_nonce": nonce, "cases": [{"id": name, "path": path, "method": "POST", "body": bodies[name],
        "expected_status": 200, "response_assertions": {"/status": "REAL"},
        "readback_assertions": {"/schema": adapters.READBACK_SCHEMA}} for name, path in a.CONTRACTS.items()]}


class FixtureNativeOwner:
    """Explicit test storage hook: writes occur inside original native routines."""
    schema = adapters.HOOK_SCHEMA

    def __init__(self):
        self.records = {}
        self.recorded = []
        self.fail = False

    def _record(self, case_id, receipt):
        if self.fail:
            raise RuntimeError("fixture persistence unavailable")
        payload_hash = a.digest(a.decode(receipt["dsse"]["payload"], a.MAX_BYTES))
        self.records[payload_hash] = a.canonical({"schema": adapters.READBACK_SCHEMA, "case_id": case_id,
            "payload_sha256": payload_hash, "receipt": copy.deepcopy(receipt)})
        self.recorded.append(case_id)

    def record_eval(self, receipt):
        self._record("eval-run", receipt)

    def record_agentloop(self, receipt):
        self._record("agentloop-run", receipt)

    def read_eval(self, digest):
        return self.records[digest]

    def read_agentloop(self, digest):
        return self.records[digest]


@pytest.fixture
def world(monkeypatch, tmp_path):
    import a11oy_code_engine as engine
    import a11oy_vertical_feeds as vertical
    for name, value in {"A11OY_CODE_ADMIN_KEY": "adapter-fixture-operator",
                        "A11OY_CODE_TENANT": "adapter-fixture-tenant"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("A11OY_APPROVAL_INTERRUPT", raising=False)
    source = Path(__file__).resolve().parents[1]
    for name in ("szl_eval_arena", "szl_agent_loop_governed"):
        spec = importlib.util.spec_from_file_location(name, source / (name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, mod)
        spec.loader.exec_module(mod)
    arena, loop = sys.modules["szl_eval_arena"], sys.modules["szl_agent_loop_governed"]
    monkeypatch.setattr(engine, "_MODEL_BASE_URL", "https://fixture.example/v1")
    monkeypatch.setattr(engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.setattr(engine, "_HF_TOKEN", "fixture-provider")
    monkeypatch.setattr(engine, "_retrieve_with_identity", lambda *a, **k: ([], {}))
    monkeypatch.setattr(vertical, "_HAS_KHIPU", False)
    monkeypatch.setattr(vertical, "_HAS_DSSE", False)
    monkeypatch.setitem(arena._SUITES, SUITE, {"title": "Native fixture", "version": "1",
        "description": "Isolated local test, not live evidence", "cases": [{"id": "sum",
            "category": "correctness", "scorer": "exact", "input": "What is two plus two?", "expected": "4"}]})
    key = ec.generate_private_key(ec.SECP256R1())
    # Preflight reads an existing, explicitly test-only persistent source.
    key_path = tmp_path / "adapter-existing-fixture-key.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    for variable in ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM", "A11OY_RECEIPT_KEY_PEM"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("A11OY_RECEIPT_KEY_PATH", str(key_path))
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    key_id = a.digest(pem.strip())
    state = SimpleNamespace(calls=[], forums=[], signs=[], middleware=[], key=key, pem=pem,
                            key_id=key_id, arena=arena, loop=loop, owner=FixtureNativeOwner())
    def sign(payload):
        raw = a.canonical(payload)
        kind = adapters.NATIVE_TYPE.encode()
        pae = b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(raw)).encode() + b" " + raw
        state.signs.append(copy.deepcopy(payload))
        return {"payloadType": adapters.NATIVE_TYPE, "payload": base64.b64encode(raw).decode(),
            "signatures": [{"keyid": key_id, "sig": base64.b64encode(key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode()}],
            "signed": True, "_pae_sha256": a.digest(pae), "honesty": "TEMPORARY TEST KEY"}
    state.sign = sign
    import szl_dsse
    monkeypatch.setattr(szl_dsse, "signing_available", lambda: True)
    monkeypatch.setattr(szl_dsse, "active_public_key_pem", lambda: pem.decode())
    state.host_signer = actual_host_signer(key, pem, key_id, state.signs)
    monkeypatch.setattr(arena, "_sign", lambda body: (sign(body), {"available": True, "mode": "REAL"}))
    def forum(*args):
        state.forums.append(args)
        return {"ingested": False, "note": "test forum disabled"}
    monkeypatch.setattr(arena, "_ingest_forum", forum)
    monkeypatch.setattr(loop, "_ingest_forum", forum)
    original_client = httpx.Client
    def provider(request):
        assert request.url.host == "fixture.example"
        state.calls.append(request)
        return httpx.Response(200, json={"model": MODEL, "choices": [{"finish_reason": "stop",
            "message": {"role": "assistant", "content": getattr(state, "answer", "4")}}], "usage": {"completion_tokens": 1}})
    monkeypatch.setattr(httpx, "Client", lambda **kw: original_client(**{**kw, "transport": httpx.MockTransport(provider)}))
    app = FastAPI()
    @app.middleware("http")
    async def observe_middleware(request, call_next):
        state.middleware.append((request.method, request.url.path))
        return await call_next(request)
    # Fixture deterministic route implementation has explicit native local tables.
    namespace = {"app": app, "Request": Request, "JSONResponse": JSONResponse, "copy": copy,
        "_SC_AUDIT_LOCK": threading.RLock(), "_SC_AUDIT": deque(maxlen=200),
        "_SC_BUNDLE": {"compliance": {"NIST": {"framework": "NIST", "controls": [{"id": "fixture-control"}]}}},
        "_SC_PROVED_FORMULAS": list(adapters.LOCKED), "QUESTION": adapters.QUESTION,
        "FORMULA_SOURCE": adapters.FORMULA_SOURCE}
    exec('''
def _sc_ask(question):
    return {"question": question, "topic": "formulas", "grounded": True,
        "answer": "Declared locked table: " + ", ".join(_SC_PROVED_FORMULAS),
        "citations": [{"endpoint": FORMULA_SOURCE, "data": {"proved": _SC_PROVED_FORMULAS, "count": 8, "doctrine": "v11"}}],
        "receipt": {"signed": False, "dsse": {"signed": False}}}
@app.post("/api/a11oy/v1/policy/decide")
async def _sc_cap_decide(request: Request):
    body = await request.json()
    value = {"status": "REAL", "actionId": body["request_id"], "decision": "allow", "signals": [],
             "lambda_value": None, "receipt_hash": "0123456789abcdef"}
    with _SC_AUDIT_LOCK:
        _SC_AUDIT.append({**{k: value[k] for k in ("decision", "signals", "lambda_value", "receipt_hash")},
            "id": "fixture-audit-id", "request_id": body["request_id"], "agent": body["agent"],
            "action_preview": str(body["action"])[:120]})
    return JSONResponse(value)
@app.get("/api/a11oy/v1/policy/decisions/feed")
async def _sc_cap_feed():
    return JSONResponse({"status": "REAL", "verdicts": list(_SC_AUDIT)})
@app.post("/api/a11oy/v1/policy/compliance")
async def _sc_cap_compliance(request: Request):
    body = await request.json()
    return JSONResponse({"status": "REAL", **_SC_BUNDLE["compliance"][body["framework"]]})
@app.post("/api/a11oy/v1/operator/ask")
async def _sc_cap_ask(request: Request):
    body = await request.json()
    return JSONResponse({"status": "REAL", **_sc_ask(body["question"])})
''', namespace)
    state.namespace = namespace
    arena.register(app)
    loop.register(app, sign_fn=state.host_signer)
    app.state.execution_native_readbacks = state.owner
    state.app = app
    state.adapter = adapters.FixedAdapters(app, pem, key_id)
    state.plan = plan()
    yield state


def execute_all(world):
    world.adapter.preflight(world.plan)
    async def execute():
        return {case["id"]: await world.adapter.capture(case, CREDS) for case in world.plan["cases"]}
    return asyncio.run(execute())


def test_five_captures_use_original_middleware_real_native_signatures_and_readbacks(world):
    observations = execute_all(world)
    assert set(observations) == set(a.CONTRACTS)
    assert len(world.calls) == 3
    assert world.owner.recorded == ["eval-run", "eval-run", "agentloop-run"]
    assert len(world.middleware) == 6  # Five POSTs + actual native audit GET.
    for case in world.plan["cases"]:
        capture = observations[case["id"]]
        adapters.validate_native_observation(case, capture.response_status, capture.response_bytes,
            capture.readback_bytes, world.pem, world.key_id)


@pytest.mark.parametrize("missing", ["hooks", "writer_marker", "formula_source", "request_replayed", "budget",
    "native_eval_signer", "native_eval_key", "native_host_signer", "native_host_key"])
def test_entire_plan_preflight_denies_before_any_dispatch(world, missing, monkeypatch):
    if missing == "hooks":
        world.app.state.execution_native_readbacks = None
    elif missing == "writer_marker":
        endpoint = world.adapter._endpoint("POST", a.CONTRACTS["eval-run"])
        del endpoint.execution_native_readbacks_schema
    elif missing == "formula_source":
        world.namespace["FORMULA_SOURCE"] = "szl_brain.CANONICAL"
    elif missing == "request_replayed":
        world.namespace["_SC_AUDIT"].append({"request_id": world.plan["cases"][0]["body"]["request_id"]})
    elif missing == "budget":
        world.plan["cases"][-1]["body"]["execution_limits"] = {**LIMITS, "max_model_requests": 1}
    elif missing == "native_eval_signer":
        import szl_dsse
        monkeypatch.setattr(szl_dsse, "signing_available", lambda: False)
    elif missing == "native_eval_key":
        import szl_dsse
        replacement = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        monkeypatch.setattr(szl_dsse, "active_public_key_pem", lambda: replacement.decode())
    elif missing == "native_host_signer":
        world.host_signer.__globals__["_A11OY_KEY_SOURCE"] = "ephemeral"
    else:
        world.host_signer.__globals__["_A11OY_KEYID"] = "0" * 64
    with pytest.raises((ValueError, adapters.AdapterBlocked)):
        world.adapter.preflight(world.plan)
    assert world.middleware == [] and world.calls == [] and world.signs == [] and world.owner.recorded == []
    with pytest.raises(adapters.AdapterBlocked, match="PREFLIGHTED"):
        asyncio.run(world.adapter.capture(world.plan["cases"][0], CREDS))


@pytest.mark.parametrize("mutation", ["response_answer", "signed_body", "native_signature", "readback_receipt", "terminal_budget", "wrong_model", "wrong_chain"])
def test_offline_native_validator_rejects_tampered_evidence(world, mutation):
    observations = execute_all(world)
    case = world.plan["cases"][-1 if mutation == "wrong_chain" else -2]
    cap = observations[case["id"]]
    response, readback = a.strict_json(cap.response_bytes), a.strict_json(cap.readback_bytes)
    if mutation == "response_answer":
        response["results"][0]["answer"] = "forged"
    elif mutation == "signed_body":
        response["receipt"]["body"]["model_id"] = "forged"
    elif mutation == "native_signature":
        response["receipt"]["dsse"]["signatures"][0]["sig"] = base64.b64encode(b"bad").decode()
    elif mutation == "readback_receipt":
        readback["receipt"]["signing"]["mode"] = "forged"
    elif mutation == "terminal_budget":
        response["execution_budget"]["terminal"] = True
    elif mutation == "wrong_model":
        response["results"][0]["generation"]["model_slug"] = "other/model"
    else:
        response["steps"][0]["step_digest"] = "0" * 64
    with pytest.raises(ValueError):
        adapters.validate_native_observation(case, cap.response_status, a.canonical(response),
            a.canonical(readback), world.pem, world.key_id)


def test_failed_native_persistence_stops_nested_eval_and_composite_forum(world):
    world.adapter.preflight(world.plan)
    world.owner.fail = True
    with pytest.raises(ValueError):
        asyncio.run(world.adapter.capture(world.plan["cases"][-1], CREDS))
    assert len(world.calls) == 2
    assert world.forums == [] and world.owner.recorded == []


def test_consumed_case_cannot_retry_after_capture_or_ambiguous_failure(world):
    world.adapter.preflight(world.plan)
    case = world.plan["cases"][0]
    asyncio.run(world.adapter.capture(case, CREDS))
    with pytest.raises(adapters.AdapterBlocked, match="PREFLIGHTED_UNUSED_CASE_REQUIRED"):
        asyncio.run(world.adapter.capture(case, CREDS))
    assert len(world.middleware) == 2

@pytest.fixture
def storage_world(tmp_path, monkeypatch):
    from tests import test_observer_runtime as runtime_tests
    yield from runtime_tests.world.__wrapped__(tmp_path, monkeypatch)


def test_composed_producer_native_routes_store_snapshot_and_offline_consumer(world, storage_world, monkeypatch):
    """Actual five route implementations plus storage; only model transport is synthetic."""
    from tests.test_real_execution_routes import install_actual_deterministic_routes
    install_actual_deterministic_routes(world)
    import sqlite3
    import observer_runtime as runtime
    from tests import test_observer_runtime as runtime_tests
    from native_readbacks import NativeReadbacks
    sw = storage_world
    public_pem, key_id = runtime_tests.public(sw.runtime_private)
    def sign(payload):
        envelope = runtime_tests.envelope(payload, sw.runtime_private, adapters.NATIVE_TYPE)
        raw = a.decode(envelope["payload"], a.MAX_BYTES)
        kind = adapters.NATIVE_TYPE.encode()
        pae = b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(raw)).encode() + b" " + raw
        return {**envelope, "signed": True, "_pae_sha256": a.digest(pae), "honesty": "TEMPORARY TEST KEY"}
    monkeypatch.setattr(world.arena, "_sign", lambda body: (sign(body), {"available": True, "mode": "REAL"}))
    world.loop.register(world.app, sign_fn=actual_host_signer(sw.runtime_private, public_pem, key_id))
    import szl_dsse
    monkeypatch.setattr(szl_dsse, "active_public_key_pem", lambda: public_pem.decode())
    subject = runtime.Observer(sw.service, world.app, authority_file=sw.authority_file)
    assert subject.adapters is None
    world.app.state.execution_native_readbacks = NativeReadbacks(sw.service, public_pem, key_id)
    runtime.register(world.app, subject)
    def bind_fixed_cases(value):
        value["cases"] = copy.deepcopy(world.plan["cases"])
        value["cases"][0]["body"]["request_id"] = value["run_nonce"] + ":policy-decide"
        for case in value["cases"]:
            case_id = case["id"]
            case["response_assertions"] = {
                "policy-decide": {"/decision": "allow"}, "policy-compliance": {"/framework": "NIST"},
                "operator-ask": {"/topic": "formulas"}, "eval-run": {"/execution_complete": True},
                "agentloop-run": {"/ok": True}}[case_id]
            case["readback_assertions"] = ({"/record/case_id": case_id} if case_id == "agentloop-run"
                                           else {"/case_id": case_id})
    nonce, signed = runtime_tests.signed_plan(sw, subject=subject, mutate=bind_fixed_cases)
    async def execute():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world.app), base_url=a.ORIGIN) as client:
            response = await client.post(runtime.PREFIX + "/run", headers=runtime_tests.HEADERS,
                                         json={"plan": signed, "run_nonce": nonce})
            assert response.status_code == 200, response.text
            return response.content
    raw = asyncio.run(execute())
    value = a.strict_json(raw)
    assert len(world.calls) == 3
    assert len(value["bundle"]["observations"]) == 5
    assert runtime_tests.remote_rows(sw) == sorted((case_id, "COMPLETED") for case_id in a.CONTRACTS)
    snapshot = sw.root / "remote-readback.sqlite3"
    with sqlite3.connect(snapshot) as db:
        assert db.execute("SELECT COUNT(*) FROM execution_native_receipts").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM execution_native_links").fetchone()[0] == 3
    bundle = value["bundle"]
    context = subject.context_for_bundle_digest(a.digest(a.canonical(bundle)))
    assert a.validate(bundle, context)["binding_checks_passed"] is True
    consumer_path = Path(__file__).resolve().parents[1] / "szl_execution_readiness.py"
    spec = importlib.util.spec_from_file_location("composed_consumer_fixture", consumer_path)
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    admitted = consumer.validate_execution(bundle, context, source=context.source_revision)
    assert admitted["requiredExecutionCovered"] == admitted["passiveRequiredNotProbed"] == 5
    before = sw.backend.submits
    assert asyncio.run(subject.export(nonce, runtime_tests.HEADERS)) == raw
    assert sw.backend.submits == before
    # Parse the actual completed runtime export through the collector contract,
    # including archive_only; no hand-written wrapper fixture can hide drift.
    collector_path = Path(__file__).resolve().parents[1] / ".github/scripts/collect_execution_readiness.py"
    collector_spec = importlib.util.spec_from_file_location("composed_collector_fixture", collector_path)
    collector = importlib.util.module_from_spec(collector_spec)
    collector_spec.loader.exec_module(collector)
    collected_bundle, coverage = collector.validate_current_export(
        a.strict_json(asyncio.run(subject.export(nonce, runtime_tests.HEADERS))), context)
    assert a.canonical(collected_bundle) == a.canonical(bundle)
    assert coverage["requiredExecutionCovered"] == 5
    assert sw.backend.submits == before

    # Recreate both service and observer on a clean successor StateStore boot.
    # Recovery uses acknowledged immutable bytes and cannot grant current-boot
    # execution or readiness from the previous process's evidence.
    import a11oy_state_store as state_store
    from routers.series_a_control_plane import Service
    from tests.state_store_support import replica
    sw.clock.on_sleep.append(sw.writer.heartbeat_once)
    successor = replica(sw.root, "successor", sw.objects, sw.backend, sw.clock)
    try:
        successor.boot()
        successor.heartbeat_once()
        assert successor.claim_kind == state_store.CLAIM_CLEAN
        assert successor.boot_id != sw.writer.boot_id
        monkeypatch.setattr(state_store, "_ACTIVE", successor)
        service = Service()
        fresh_app = FastAPI()
        fresh = runtime.Observer(service, fresh_app, authority_file=sw.authority_file)
        fresh_app.state.execution_native_readbacks = NativeReadbacks(service, public_pem, key_id)
        runtime.register(fresh_app, fresh)
        def no_sign(*args, **kwargs):
            raise AssertionError("Archive recovery/export must not sign")
        monkeypatch.setattr(fresh, "_sign", no_sign)
        monkeypatch.setattr(service.signer, "sign", no_sign)
        before_recovery = sw.backend.submits
        providers_before = len(world.calls)
        restored = fresh.restore_completed_archives()
        assert restored == {"restored": 1, "read_only": True, "current_runtime_admitted": False}
        async def recover():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fresh_app), base_url=a.ORIGIN) as client:
                response = await client.get(runtime.PREFIX + "/exports/" + nonce, headers=runtime_tests.HEADERS)
                assert response.status_code == 200, response.text
                again = await client.get(runtime.PREFIX + "/exports/" + nonce, headers=runtime_tests.HEADERS)
                assert again.content == response.content
                replay = await client.post(runtime.PREFIX + "/run", headers=runtime_tests.HEADERS,
                                           json={"plan": signed, "run_nonce": nonce})
                assert replay.status_code == 409
                return a.strict_json(response.content)
        archive = asyncio.run(recover())
        assert archive["archive_only"] is True and archive["publication_eligible"] is False
        assert archive["execution_authorized"] is False
        assert a.canonical(archive["bundle"]) == a.canonical(bundle)
        with pytest.raises(runtime.ObserverBlocked, match="OBSERVATION_BUNDLE_NOT_ADMITTED"):
            fresh.context_for_bundle_digest(a.digest(a.canonical(bundle)))
        assert len(world.calls) == providers_before and sw.backend.submits == before_recovery
    finally:
        successor._close_watchers()


def test_compliance_readback_cannot_relabel_another_framework(world):
    world.adapter.preflight(world.plan)
    case = world.plan["cases"][1]
    capture = asyncio.run(world.adapter.capture(case, CREDS))
    response, readback = a.strict_json(capture.response_bytes), a.strict_json(capture.readback_bytes)
    response["framework"] = readback["record"]["framework"] = "STIG"
    with pytest.raises(adapters.AdapterBlocked, match="COMPLIANCE_RECORD_MISMATCH"):
        adapters.validate_native_observation(case, 200, a.canonical(response), a.canonical(readback), world.pem, world.key_id)


def test_agent_native_receipt_cannot_drift_from_admitted_suite(world, monkeypatch):
    world.adapter.preflight(world.plan)
    replacement = copy.deepcopy(world.arena._SUITES[SUITE])
    replacement["cases"][0]["input"] = "What is 2 plus 2?"
    monkeypatch.setitem(world.arena._SUITES, SUITE, replacement)
    with pytest.raises(adapters.AdapterBlocked, match="AGENT_PREFLIGHT_DRIFT"):
        asyncio.run(world.adapter.capture(world.plan["cases"][-1], CREDS))
    assert world.calls == []  # Reject changed suite before model dispatch.


def test_native_eval_and_agent_hashes_preserve_unicode_answer(world, monkeypatch):
    world.answer = "café"
    monkeypatch.setitem(world.arena._SUITES[SUITE]["cases"][0], "expected", world.answer)
    observations = execute_all(world)
    standalone = a.strict_json(observations["eval-run"].response_bytes)
    nested = a.strict_json(observations["agentloop-run"].response_bytes)["steps"][0]["final"]["eval"]["evidence"]
    assert standalone["results"][0]["answer"] == nested["results"][0]["answer"] == "café"


@pytest.mark.parametrize("configuration", ["absent", "missing_file", "empty_inline"])
def test_preflight_missing_persistent_source_never_loads_or_generates_replacement(world, monkeypatch, tmp_path, configuration):
    import a11oy_signing_key as key_loader
    import szl_dsse
    for variable in ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM", "A11OY_RECEIPT_KEY_PEM",
                     "A11OY_RECEIPT_KEY_PATH", "A11OY_RECEIPT_KEY_DIR", "A11OY_REQUIRE_PERSISTENT_SIGNING"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(key_loader, "_DEFAULT_KEY_DIR", str(tmp_path / "no-default-key"))
    if configuration == "missing_file":
        monkeypatch.setenv("A11OY_RECEIPT_KEY_PATH", str(tmp_path / "missing.pem"))
    elif configuration == "empty_inline":
        monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", "")
    discoveries = []
    def forbidden_loader(*args, **kwargs):
        discoveries.append("loader")
        raise AssertionError("preflight attempted replacement identity discovery")
    monkeypatch.setattr(szl_dsse, "signing_available", forbidden_loader)
    monkeypatch.setattr(ec, "generate_private_key", forbidden_loader)
    with pytest.raises(adapters.AdapterBlocked, match="PERSISTENT_SIGNER_CONFIGURATION_REQUIRED"):
        world.adapter.preflight(world.plan)
    assert discoveries == []
    assert world.calls == world.middleware == world.signs == world.owner.recorded == []
