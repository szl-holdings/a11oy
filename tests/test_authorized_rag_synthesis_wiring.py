#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""R6 wiring: the admitted synthesis capability through all three Code routes.

Executes the real SQLite generation writer, org retrieval, the agent FSM, the
controller factory, ``hydrate_answer_evidence`` and ``AuthorizedRagSynthesis``
behind ``/agent/run``, ``/agent/stream`` and agentic ``/chat/stream``. The only
destination is a local spy transport. Identities, grants and sources are
synthetic. No credential, network request or model inference is used.
"""
import dataclasses
import hashlib
import importlib
import json

import pytest

import a11oy_agent_loop as agent
import a11oy_org_rag as rag
import a11oy_rag_synthesis_controller as ctl


MARKER = "SYNTHETIC_SOURCE_CONTENT_MUST_STAY_INSIDE_AUTHORIZED_SYNTHESIS"
HISTORY_MARKER = "UNBOUND_HISTORY_MUST_NOT_EGRESS"
SYSTEM_MARKER = "UNBOUND_SYSTEM_PROMPT_MUST_NOT_EGRESS"
TOOL_MARKER = "TOOL_OUTPUT_MUST_NOT_EGRESS"
POLICY_REVISION = "a" * 64
SOURCE_REVISION = "b" * 40
TASK = "synthesis"
VARIANTS = ("run", "stream", "chat")


def _publish_generation(label, suffix=""):
    conn = rag._db()
    rag._init_schema(conn)
    generation = rag._begin_generation(conn, label)
    graph = rag.OrgGraph()
    graph.add_node("szl-holdings/fixture", "repo", repo="fixture")
    bodies = {}
    for index in range(6):
        # Multi-byte text longer than both the 1,200-char query excerpt and the
        # 2,048-byte synthesis excerpt; 4-byte code points straddle the cut.
        text = (f"synthesis {MARKER} document {index}{suffix}. " + "é" * 900
                + "\U0001D11E" * 300 + "漢" * 100)
        bodies[f"source-{index}.txt"] = text
        rag._ingest_text(graph, conn, repo="fixture", path=f"source-{index}.txt", raw=text,
                         source="fixture:source-registry", category="app_code", embed_fn=None,
                         generation_id=generation)
    rag._persist_runtime_state(conn, graph, {
        "built": True, "mode": label, "ts": 1.0, "repos": 1, "chunks": 6,
    }, generation)
    conn.close()
    return generation, bodies


@pytest.fixture
def env(monkeypatch, tmp_path):
    for key, name in (("A11OY_CODE_DB", "code.db"), ("A11OY_CODE_SANDBOX", "sandbox"),
                      ("A11OY_REACT_DB", "react.sqlite3"), ("A11OY_AGENT_REFLECT_DB", "reflect.db")):
        monkeypatch.setenv(key, str(tmp_path / name))
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(tmp_path / "rag.sqlite3"))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(rag, "_maybe_embedder", lambda load=False: None)
    monkeypatch.setattr(agent, "_active_flux_tier_hint", lambda task: None)
    monkeypatch.setattr(agent, "_span", lambda name: agent._SpanShim(name))
    monkeypatch.setattr(agent, "REFLECT_DB", str(tmp_path / "reflection.sqlite3"))
    # Voice/expression is a separate destination; it must stay unreachable.
    monkeypatch.setenv("A11OY_WALLPA_FINALIZE", "1")
    monkeypatch.setattr(agent, "_wallpa_speak_final",
                        lambda *a, **k: pytest.fail("Unadmitted expression egress"))
    generation, bodies = _publish_generation("SYNTHETIC_LOCAL_TEST")
    retrieval = rag.query(TASK, k=6)
    assert retrieval["ok"] and len(retrieval["chunks"]) == 6
    assert all(hashlib.sha256(c["text"].encode()).hexdigest() != c["sha256"] for c in retrieval["chunks"])

    orchestrator = importlib.import_module("a11oy_code_orchestrator")
    generic_calls, tool_calls = [], []

    async def generic_model(*args, **kwargs):
        generic_calls.append(True)
        raise AssertionError("Generic fallback-walking model path must not run")

    async def tool_spy(name, args, client, **kwargs):
        tool_calls.append(name)
        return {"ok": True, "output": TOOL_MARKER, "stdout": TOOL_MARKER}

    monkeypatch.setattr(orchestrator, "agent_model_complete", generic_model)
    monkeypatch.setattr(orchestrator, "execute_tool", tool_spy)
    monkeypatch.setattr(orchestrator._opauth, "principal",
                        lambda request: {"operator": True, "two_person_attested": False})
    monkeypatch.setattr(orchestrator, "_get_client", lambda: object())
    monkeypatch.setattr(orchestrator, "route", lambda *a, **kw: {
        "tier": "SIMULATED", "model": "uninvoked", "license_class": "GREEN", "reason": "unit route"})
    monkeypatch.setattr(orchestrator, "_serving_base", lambda: pytest.fail("Agentic path must not probe a model"))
    monkeypatch.setattr(orchestrator, "mem_get_conversation", lambda key: {"messages": []})
    monkeypatch.setattr(orchestrator, "mem_upsert_conversation", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "mem_add_message", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "khipu_emit", lambda *a, **kw: {
        "receipt_id": "SYNTHETIC_RECEIPT", "hash": None, "chain_verified": False, "signed": False})
    monkeypatch.setattr(orchestrator._agent, "recent_reflections", lambda limit: [])
    monkeypatch.setattr(ctl, "_STATE", {"grant_source": None, "destination": None})
    return {"orchestrator": orchestrator, "generation": generation, "bodies": bodies,
            "retrieval": retrieval, "generic_calls": generic_calls, "tool_calls": tool_calls,
            "monkeypatch": monkeypatch}


class SpyTransport:
    def __init__(self, provider_id="SYNTHETIC_LOCAL_SPY", model="SYNTHETIC_LOCAL_MODEL"):
        self.provider_id, self.model = provider_id, model
        self.calls, self.extra, self.failure = [], {}, False

    async def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, "options": kwargs})
        if self.failure:
            raise RuntimeError(MARKER)
        return {"text": "SYNTHETIC local answer; no semantic quality claim.",
                "model": self.model, "provider_id": self.provider_id, "stub": False, **self.extra}


class GrantSource:
    """Synthetic implementation of the R2/R3-owned SynthesisGrantSource protocol."""

    def __init__(self, retrieval, *, visibility="PUBLIC"):
        self.subject = agent.SynthesisSubject("fixture-principal", "fixture-tenant", POLICY_REVISION, True)
        self.visibility = visibility
        self.source_tenant = "fixture-tenant" if visibility == "PRIVATE" else None
        self.allowed, self.provider_allowed = True, True
        self.source_revision = SOURCE_REVISION
        self.subject_override = None
        self.registry = {(c["chunk_id"], c["node_id"], c["sha256"], c["source"]) for c in retrieval["chunks"]}
        self.grant_calls, self.decisions, self.resolved = [], [], []
        self.on_grant = None      # hook(call_index) for revocation during hydration
        self.on_decision = None   # hook(call_index)

    def resolve_subject(self, request, operator):
        self.resolved.append(dict(operator))
        return self.subject

    def source_grant(self, subject, handle):
        self.grant_calls.append(handle)
        if self.on_grant:
            self.on_grant(len(self.grant_calls))
        known = (handle.chunk_id, handle.node_id, handle.sha256, handle.source) in self.registry
        return agent.SynthesisSourceGrant(
            self.subject_override or subject, handle, self.source_revision,
            self.visibility, self.source_tenant, self.allowed if known else False)

    def admit_transfer(self, decision):
        self.decisions.append(decision)
        if self.on_decision:
            self.on_decision(len(self.decisions))
        return self.provider_allowed


def install(env, *, visibility="PUBLIC", trust_domain="LOCAL", transport=None):
    grants = GrantSource(env["retrieval"], visibility=visibility)
    spy = transport or SpyTransport()
    ctl.configure(grant_source=grants, destination=ctl.FixedDestination(
        "SYNTHETIC_LOCAL_SPY", "SYNTHETIC_LOCAL_MODEL", trust_domain, spy))
    return grants, spy


def _sse(text):
    events = {}
    for part in text.split("\n\n"):
        lines = part.splitlines()
        if len(lines) >= 2 and lines[0].startswith("event: ") and lines[1].startswith("data: "):
            events[lines[0][7:]] = json.loads(lines[1][6:])
    return events


def call(env, variant, task=TASK):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    orchestrator = env["orchestrator"]
    app = FastAPI()
    orchestrator.attach(app)
    client = TestClient(app)
    history = [{"role": "user", "content": HISTORY_MARKER},
               {"role": "assistant", "content": HISTORY_MARKER}]
    if variant == "run":
        response = client.post("/api/a11oy/code/agent/run", json={"task": task, "history": history})
        assert response.status_code == 200
        done = response.json()
    elif variant == "stream":
        response = client.post("/api/a11oy/code/agent/stream", json={"task": task, "history": history})
        assert response.status_code == 200
        done = _sse(response.text)["done"]
    else:
        messages = [{"role": "system", "content": SYSTEM_MARKER}, *history, {"role": "user", "content": task}]
        response = client.post("/api/a11oy/code/chat/stream", json={"agentic": True, "messages": messages})
        assert response.status_code == 200
        done = _sse(response.text)["done"]
    assert not env["generic_calls"], "generic agent_model_complete was invoked"
    assert MARKER not in response.text, "raw source text reached the public response"
    return done, response.text


def egress_text(spy):
    return json.dumps([c["messages"] for c in spy.calls], ensure_ascii=False)


def assert_refused(done, reason, spy, *, calls=0):
    assert done["ok"] is False
    assert done["halt_reason"] == reason
    assert done["synthesis_admission"]["reason"] == reason
    assert done["i_dont_know"] is True
    assert not done.get("answer")
    assert len(spy.calls) == calls
    if "served_by" in done:  # chat route projection
        assert done["served_by"] in ("NOT_CONFIRMED", "NOT_INVOKED") and done["model"] is None


# --------------------------------------------------------------------------- #
# Default posture: no grants -> unchanged unavailable behaviour
# --------------------------------------------------------------------------- #
def _shape(value):
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(v) for v in value]
    return type(value).__name__


@pytest.mark.parametrize("variant", VARIANTS)
def test_absent_grants_keep_unavailable_with_unchanged_shape(env, variant):
    done, _ = call(env, variant)
    assert done["ok"] is False and done["halt_reason"] == "CONTENT_ADMISSION_UNAVAILABLE"
    assert done["synthesis_admission"] == {"state": "UNAVAILABLE", "reason": "CONTENT_ADMISSION_UNAVAILABLE"}
    wired = _shape(done)
    # Same request with the factory module removed == behaviour at the pin.
    env["monkeypatch"].setattr(env["orchestrator"], "_synthctl", None)
    baseline, _ = call(env, variant)
    assert _shape(baseline) == wired
    assert baseline["halt_reason"] == done["halt_reason"]
    assert baseline["synthesis_admission"] == done["synthesis_admission"]


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("missing", ["destination", "grant_source"])
def test_half_configured_controller_stays_unavailable(env, variant, missing):
    grants, spy = install(env)
    gs, dest = ctl.configured()
    ctl.configure(grant_source=None if missing == "grant_source" else gs,
                  destination=None if missing == "destination" else dest)
    done, _ = call(env, variant)
    assert_refused(done, "CONTENT_ADMISSION_UNAVAILABLE", spy)
    assert not grants.grant_calls and not grants.decisions


# --------------------------------------------------------------------------- #
# Admitted path: exact identity, Unicode hashes, no unbound context in egress
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("variant", VARIANTS)
def test_admitted_synthesis_binds_exact_sources_and_forwards_nothing_unbound(env, variant):
    grants, spy = install(env)
    done, text = call(env, variant)
    assert done["ok"] is True, done
    admission = done["synthesis_admission"]
    assert admission["state"] == "AUTHORIZED_CONTENT_SUPPLIED"
    assert admission["semantic_support_verified"] is False
    assert admission["provider_id"] == "SYNTHETIC_LOCAL_SPY" and admission["model_id"] == "SYNTHETIC_LOCAL_MODEL"
    assert len(spy.calls) == 1
    options = spy.calls[0]["options"]
    assert options["allow_fallback"] is False
    assert options["provider_id"] == "SYNTHETIC_LOCAL_SPY" and options["model_id"] == "SYNTHETIC_LOCAL_MODEL"
    messages = spy.calls[0]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    payload = egress_text(spy)
    for marker in (HISTORY_MARKER, SYSTEM_MARKER, TOOL_MARKER):
        assert marker not in payload
    content = json.loads(messages[-1]["content"])
    assert set(content) == {"task", "sources"} and content["task"] == TASK
    assert len(content["sources"]) == 6
    for source in content["sources"]:
        original = env["bodies"][source["path"]].encode("utf-8")
        assert source["source_content_sha256"] == hashlib.sha256(original).hexdigest()
        assert source["generation_id"] == env["generation"]
        assert source["source_revision"] == SOURCE_REVISION
        start, end = source["excerpt_utf8_range"]
        assert start == 0 and 0 < end <= 2048
        assert original[start:end].decode("utf-8") == source["text"]
        assert source["excerpt_sha256"] == hashlib.sha256(original[start:end]).hexdigest()
        assert source["excerpt_sha256"] != source["source_content_sha256"]
    assert admission["context_sha256"] == hashlib.sha256(messages[-1]["content"].encode("utf-8")).hexdigest()
    # One exact decision binding, asked twice (initial + pre-egress), never widened.
    assert len(grants.decisions) == 2 and grants.decisions[0] == grants.decisions[1]
    decision = grants.decisions[0]
    assert decision.subject == grants.subject and decision.purpose == "ANSWER_SYNTHESIS"
    assert (decision.provider_id, decision.model_id, decision.trust_domain) == (
        "SYNTHETIC_LOCAL_SPY", "SYNTHETIC_LOCAL_MODEL", "LOCAL")
    assert decision.task_sha256 == hashlib.sha256(TASK.encode()).hexdigest()
    assert decision.history_forwarded is False and decision.expression_authority == "NONE"
    expected = sorted((env["generation"], c["chunk_id"], c["sha256"], SOURCE_REVISION)
                      for c in env["retrieval"]["chunks"])
    assert sorted(decision.source_revisions) == expected
    # initial + hydration + pre-egress recheck, for each of 6 sources
    assert len(grants.grant_calls) == 18
    assert grants.resolved and all(op["operator"] is True for op in grants.resolved)
    if variant == "chat":
        assert done["served_by"] == "SYNTHETIC_LOCAL_SPY" and done["model"] == "SYNTHETIC_LOCAL_MODEL"


@pytest.mark.parametrize("variant", VARIANTS)
def test_private_source_reaches_only_local_destination_for_same_tenant(env, variant):
    grants, spy = install(env, visibility="PRIVATE")
    done, _ = call(env, variant)
    assert done["ok"] is True and len(spy.calls) == 1


# --------------------------------------------------------------------------- #
# Pre-egress refusals: zero calls to the destination
# --------------------------------------------------------------------------- #
REFUSALS = [
    ("wrong_subject", "SOURCE_ACCESS_DENIED"),
    ("wrong_tenant", "SOURCE_TENANT_DENIED"),
    ("mutable_policy", "SYNTHESIS_SUBJECT_UNAVAILABLE"),
    ("unauthenticated_subject", "SYNTHESIS_SUBJECT_UNAVAILABLE"),
    ("private_external", "PRIVATE_SOURCE_EGRESS_DENIED"),
    ("unknown_visibility", "SOURCE_VISIBILITY_UNKNOWN"),
    ("mutable_source_revision", "SOURCE_REVISION_UNAVAILABLE"),
    ("source_false", "SOURCE_ACCESS_DENIED"),
    ("source_truthy_int", "SOURCE_ACCESS_DENIED"),
    ("source_truthy_str", "SOURCE_ACCESS_DENIED"),
    ("source_truthy_yes", "SOURCE_ACCESS_DENIED"),
    ("provider_false", "PROVIDER_ADMISSION_DENIED"),
    ("provider_truthy_int", "PROVIDER_ADMISSION_DENIED"),
    ("provider_truthy_str", "PROVIDER_ADMISSION_DENIED"),
    ("source_revoked_during_hydration", "SOURCE_ACCESS_DENIED"),
    ("revision_changed_during_hydration", "SOURCE_AUTHORIZATION_CHANGED"),
    ("provider_revoked_during_hydration", "PROVIDER_ADMISSION_DENIED"),
    ("generation_changed", "SOURCE_HYDRATION_UNAVAILABLE"),
    ("generation_digest_changed", "SOURCE_HYDRATION_UNAVAILABLE"),
    ("content_tampered", "SOURCE_HYDRATION_UNAVAILABLE"),
]


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("case,reason", REFUSALS)
def test_refusals_happen_before_any_egress(env, variant, case, reason):
    private_external = case == "private_external"
    grants, spy = install(env, visibility="PRIVATE" if case in ("wrong_tenant", "private_external") else "PUBLIC",
                          trust_domain="EXTERNAL" if private_external else "LOCAL")
    orchestrator, monkeypatch = env["orchestrator"], env["monkeypatch"]
    if case == "wrong_subject":
        grants.subject_override = dataclasses.replace(grants.subject, principal_id="other-principal")
    elif case == "wrong_tenant":
        grants.source_tenant = "other-tenant"
    elif case == "mutable_policy":
        grants.subject = dataclasses.replace(grants.subject, policy_revision="main")
    elif case == "unauthenticated_subject":
        grants.subject = dataclasses.replace(grants.subject, authenticated=False)
    elif case == "unknown_visibility":
        grants.visibility = "UNKNOWN"
    elif case == "mutable_source_revision":
        grants.source_revision = "main"
    elif case == "source_false":
        grants.allowed = False
    elif case == "source_truthy_int":
        grants.allowed = 1
    elif case == "source_truthy_str":
        grants.allowed = "true"
    elif case == "source_truthy_yes":
        grants.allowed = "yes"
    elif case == "provider_false":
        grants.provider_allowed = False
    elif case == "provider_truthy_int":
        grants.provider_allowed = 1
    elif case == "provider_truthy_str":
        grants.provider_allowed = "True"
    elif case in ("source_revoked_during_hydration", "revision_changed_during_hydration",
                  "provider_revoked_during_hydration"):
        original_hydrate = rag.hydrate_answer_evidence

        def hydrate_then_change(subject, handles, *, authorizer):
            rows = original_hydrate(subject, handles, authorizer=authorizer)
            # Policy changes while the controller holds hydrated bytes in memory.
            if case == "source_revoked_during_hydration":
                grants.allowed = False
            elif case == "revision_changed_during_hydration":
                grants.source_revision = "c" * 40
            else:
                grants.provider_allowed = False
            return rows
        monkeypatch.setattr(rag, "hydrate_answer_evidence", hydrate_then_change)
    elif case in ("generation_changed", "generation_digest_changed", "content_tampered"):
        original = orchestrator._agent_rag_query

        def changed(q, **kw):
            result = original(q, **kw)
            if case == "generation_changed":
                _publish_generation("SYNTHETIC_REPUBLISHED", suffix=" republished")
            elif case == "generation_digest_changed":
                result["generation_digest_sha256"] = "c" * 64
            else:
                conn = rag._db()
                conn.execute("UPDATE org_chunks_gen SET body=body || ' tampered' WHERE chunk_id=?",
                             (result["chunks"][0]["chunk_id"],))
                conn.commit()
                conn.close()
            return result
        monkeypatch.setattr(orchestrator, "_agent_rag_query", changed)
    done, _ = call(env, variant)
    assert_refused(done, reason, spy, calls=0)
    if case.endswith("_during_hydration"):
        # Refused by the post-hydration recheck: 6 initial + 6 hydration checks
        # passed, and the 13th (first pre-egress) check observed the change.
        assert len(grants.grant_calls) >= 13


# --------------------------------------------------------------------------- #
# Destination identity: wrong model, stub/error, fallback attempted
# --------------------------------------------------------------------------- #
RESPONSE_REFUSALS = [
    ("wrong_model", {"model": "OTHER_MODEL"}),
    ("wrong_provider", {"provider_id": "OTHER_PROVIDER"}),
    ("fallback_reported", {"fallback_used": True}),
    ("fallback_model_reported", {"fallback_model": "OTHER_MODEL"}),
    ("stub", {"stub": True}),
    ("missing_stub_flag", {"stub": None}),
    ("error", {"error": MARKER}),
    ("ok_false", {"ok": False}),
    ("empty_text", {"text": "   "}),
]


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("case,extra", RESPONSE_REFUSALS)
def test_destination_response_identity_is_enforced(env, variant, case, extra):
    grants, spy = install(env)
    spy.extra = dict(extra)
    done, text = call(env, variant)
    # Egress went only to the one admitted destination; its answer is refused.
    assert_refused(done, "SYNTHESIS_RESPONSE_UNAVAILABLE", spy, calls=1)
    assert "OTHER_MODEL" not in text and "OTHER_PROVIDER" not in text


@pytest.mark.parametrize("variant", VARIANTS)
def test_destination_exception_is_content_free(env, variant):
    grants, spy = install(env, visibility="PRIVATE")
    spy.failure = True
    done, text = call(env, variant)
    assert_refused(done, "SYNTHESIS_BACKEND_FAILED", spy, calls=1)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("transport", ["agent_model_complete", "_call_model_resilient"])
def test_fallback_walking_transport_is_never_admitted(env, variant, transport):
    grants, _ = install(env)
    orchestrator = env["orchestrator"]
    gs, dest = ctl.configured()
    ctl.configure(grant_source=gs, destination=ctl.FixedDestination(
        dest.provider_id, dest.model_id, dest.trust_domain, getattr(orchestrator, transport)))
    done, _ = call(env, variant)
    assert done["ok"] is False and done["halt_reason"] == "CONTENT_ADMISSION_UNAVAILABLE"
    assert not env["generic_calls"] and not grants.grant_calls and not grants.decisions


@pytest.mark.parametrize("variant", ["chat"])
def test_anonymous_chat_turn_cannot_obtain_capability(env, variant):
    grants, spy = install(env)
    env["monkeypatch"].setattr(env["orchestrator"]._opauth, "principal",
                               lambda request: {"operator": False, "two_person_attested": False})
    done, _ = call(env, variant)
    assert_refused(done, "CONTENT_ADMISSION_UNAVAILABLE", spy)
    assert not grants.resolved


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("subject", ["none", "raises", "dict"])
def test_unresolved_subject_stays_unavailable(env, variant, subject):
    grants, spy = install(env)

    def resolve(request, operator):
        if subject == "raises":
            raise RuntimeError(MARKER)
        return None if subject == "none" else {"principal_id": "x", "tenant_id": "y"}
    grants.resolve_subject = resolve
    done, _ = call(env, variant)
    assert_refused(done, "CONTENT_ADMISSION_UNAVAILABLE", spy)


def test_capability_and_fixed_backend_are_single_use(env):
    import asyncio
    grants, spy = install(env)
    synth = env["orchestrator"]._answer_synthesizer_for(None, {"operator": True, "two_person_attested": False})
    assert synth is not None
    retrieval = rag.query(TASK, k=6)
    first = asyncio.run(synth(task=TASK, retrievals=(retrieval,)))
    assert first["synthesis_admission"]["state"] == "AUTHORIZED_CONTENT_SUPPLIED"
    checks = (len(grants.grant_calls), len(grants.decisions), len(spy.calls))
    with pytest.raises(agent.SynthesisAdmissionError):
        asyncio.run(synth(task=TASK, retrievals=(retrieval,)))
    # The reused capability is refused before any authorization or egress.
    assert (len(grants.grant_calls), len(grants.decisions), len(spy.calls)) == checks
    backend = ctl._fixed_backend(ctl.configured()[1])
    asyncio.run(backend.complete([{"role": "user", "content": "x"}]))
    with pytest.raises(agent.SynthesisAdmissionError):
        asyncio.run(backend.complete([{"role": "user", "content": "x"}]))
    assert len(spy.calls) == 2


@pytest.mark.parametrize("variant", VARIANTS)
def test_tool_output_from_act_step_never_enters_egress_payload(env, variant):
    # "show" makes the deterministic planner add a repo_map ACT step, which
    # executes through the route's principal-bound tool runner (a local spy).
    grants, spy = install(env)
    # Synthetic receipt fixture that reports durable persistence, so the real
    # PURIQ gate admits a read-only repo_map step. It isolates egress-payload
    # content; PURIQ persistence itself is covered by its own suites.
    env["monkeypatch"].setattr(env["orchestrator"], "khipu_emit", lambda *a, **kw: {
        "receipt_id": "SYNTHETIC_RECEIPT", "hash": "0" * 64, "chain_verified": True,
        "persistence_state": "SQLITE", "signed": False})
    task = "synthesis show"
    done, _ = call(env, variant, task=task)
    assert env["tool_calls"] == ["repo_map"], env["tool_calls"]
    assert done["ok"] is True and len(spy.calls) == 1, done
    payload = egress_text(spy)
    for marker in (TOOL_MARKER, HISTORY_MARKER, SYSTEM_MARKER):
        assert marker not in payload
    assert json.loads(spy.calls[0]["messages"][-1]["content"])["task"] == task
