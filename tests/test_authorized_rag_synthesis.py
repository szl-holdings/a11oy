#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Actual SQLite retrieval/hydration/FSM/prompt tests with a local model spy.

Source records, caller identities and policy grants are synthetic local fixtures.
No credential, network request, provider inference, or runtime approval is used.
"""
import asyncio
import dataclasses
import hashlib
import json

import pytest

import a11oy_agent_loop as agent
import a11oy_org_rag as rag


MARKER = "SYNTHETIC_SOURCE_CONTENT_MUST_STAY_INSIDE_AUTHORIZED_SYNTHESIS"
POLICY_REVISION = "a" * 64
SOURCE_REVISION = "b" * 40


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(tmp_path / "rag.sqlite3"))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(rag, "_maybe_embedder", lambda load=False: None)
    monkeypatch.setattr(agent, "_active_flux_tier_hint", lambda task: None)
    monkeypatch.setattr(agent, "_span", lambda name: agent._SpanShim(name))
    monkeypatch.setattr(agent, "REFLECT_DB", str(tmp_path / "reflection.sqlite3"))
    monkeypatch.setenv("A11OY_WALLPA_FINALIZE", "0")
    conn = rag._db()
    rag._init_schema(conn)
    generation = rag._begin_generation(conn, "SYNTHETIC_LOCAL_TEST")
    graph = rag.OrgGraph()
    graph.add_node("szl-holdings/fixture", "repo", repo="fixture")
    # Each real stored chunk is longer than query's 1200-character excerpt.
    # The compiler must hydrate the original and verify its full digest first.
    bodies = {}
    for index in range(6):
        text = f"synthesis {MARKER} document {index}. " + "é" * 1220
        bodies[f"source-{index}.txt"] = text
        rag._ingest_text(graph, conn, repo="fixture", path=f"source-{index}.txt", raw=text,
                         source="fixture:source-registry", category="app_code", embed_fn=None,
                         generation_id=generation)
    rag._persist_runtime_state(conn, graph, {
        "built": True, "mode": "SYNTHETIC_LOCAL_TEST", "ts": 1.0, "repos": 1, "chunks": 6,
    }, generation)
    conn.close()
    result = rag.query("synthesis", k=6)
    assert result["ok"] and len(result["chunks"]) == 6
    assert all(hashlib.sha256(chunk["text"].encode()).hexdigest() != chunk["sha256"]
               for chunk in result["chunks"])
    return {"generation": generation, "retrieval": result, "bodies": bodies}


class LocalModelSpy:
    def __init__(self):
        self.calls = []
        self.failure = False
        self.model = "SYNTHETIC_LOCAL_MODEL"
        self.extra_result = {}

    async def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, "options": kwargs})
        if self.failure:
            raise RuntimeError(MARKER)
        return {"text": "SYNTHETIC local answer; no semantic quality claim.",
                "model": self.model, "stub": False, **self.extra_result}


class PolicyFixture:
    def __init__(self, runtime, *, visibility="PUBLIC", trust_domain="LOCAL"):
        self.subject = agent.SynthesisSubject("fixture-principal", "fixture-tenant", POLICY_REVISION, True)
        self.visibility, self.trust_domain = visibility, trust_domain
        self.source_tenant = "fixture-tenant" if visibility == "PRIVATE" else None
        self.allowed, self.provider_allowed = True, True
        self.source_revision = SOURCE_REVISION
        self.hydrations = []
        self.authorizations = []
        self.provider_requests = []
        self.spy = LocalModelSpy()
        self.registry = {
            (chunk["chunk_id"], chunk["node_id"], chunk["sha256"], chunk["source"])
            for chunk in runtime["retrieval"]["chunks"]
        }
        self.after_hydrate = None
        self.subject_override = None

    def authorize(self, subject, handle):
        self.authorizations.append(handle)
        known = (handle.chunk_id, handle.node_id, handle.sha256, handle.source) in self.registry
        return agent.SynthesisSourceGrant(
            self.subject_override or subject, handle, self.source_revision,
            self.visibility, self.source_tenant, self.allowed if known else False)

    def authorize_provider(self, subject, grants, binding):
        self.provider_requests.append(binding)
        assert subject == self.subject
        assert all(grant.subject == subject for grant in grants)
        return self.provider_allowed

    def hydrate(self, subject, handles):
        self.hydrations.append(handles)
        rows = rag.hydrate_answer_evidence(
            subject, handles, authorizer=lambda s, h: self.authorize(s, h).allowed is True)
        if self.after_hydrate:
            self.after_hydrate(rows)
        return rows

    def adapter(self):
        return agent.AuthorizedRagSynthesis(
            subject=self.subject, authorizer=self.authorize, hydrator=self.hydrate,
            backend=agent.SynthesisBackend("SYNTHETIC_LOCAL_SPY", self.spy.model,
                                           self.trust_domain, self.spy),
            provider_admitter=self.authorize_provider)


def run_loop(runtime, adapter=None, retrieval=None, monkeypatch=None):
    receipts, events, generic_calls = [], [], []

    def emit_receipt(action, payload):
        receipts.append({"action": action, "payload": payload})
        return {"hash": hashlib.sha256(json.dumps(receipts[-1], sort_keys=True).encode()).hexdigest(),
                "chain_verified": False, "signed": False}

    async def generic_model(*args, **kwargs):
        generic_calls.append(True)
        raise AssertionError("Unscoped provider path must not run")

    loop = agent.AgentLoop(
        rag_query=retrieval or (lambda query: rag.query(query, k=6)),
        model_complete=generic_model, answer_synthesizer=adapter,
        khipu_emit=emit_receipt)
    result = asyncio.run(loop.run("synthesis", history=[{"role": "user", "content": "UNBOUND_HISTORY"}],
                                  emit=lambda name, value: events.append(value)))
    assert not generic_calls
    assert result["step_count"] <= result["guards"]["max_steps"]
    assert MARKER not in json.dumps({"result": result, "events": events, "receipts": receipts})
    return result, receipts, events


def test_actual_retrieval_hydration_evidence_and_prompt_are_bound_without_public_text(runtime):
    policy = PolicyFixture(runtime)
    result, receipts, events = run_loop(runtime, policy.adapter())
    assert result["ok"] and result["final_state"] == agent.S_FINALIZE
    assert result["synthesis_admission"]["state"] == "AUTHORIZED_CONTENT_SUPPLIED"
    assert result["synthesis_admission"]["semantic_support_verified"] is False
    assert len(policy.spy.calls) == 1
    messages = policy.spy.calls[0]["messages"]
    assert "UNBOUND_HISTORY" not in json.dumps(messages)
    content = json.loads(messages[-1]["content"])
    assert len(content["sources"]) == 6
    for source in content["sources"]:
        original = runtime["bodies"][source["path"]]
        assert source["source_content_sha256"] == hashlib.sha256(original.encode()).hexdigest()
        assert source["source_revision"] == SOURCE_REVISION
        assert source["generation_id"] == runtime["generation"]
        assert MARKER in source["text"]
        assert source["excerpt_sha256"] == hashlib.sha256(source["text"].encode()).hexdigest()
        start, end = source["excerpt_utf8_range"]
        assert start == 0 and end <= 2048
        assert original.encode()[start:end].decode() == source["text"]
    assert result["synthesis_admission"]["context_sha256"] == hashlib.sha256(messages[-1]["content"].encode()).hexdigest()
    assert all(request["history_forwarded"] is False for request in policy.provider_requests)
    assert len(policy.hydrations) == 1 and len(policy.provider_requests) == 2


def test_missing_controller_admission_abstains_before_generic_model(runtime):
    result, _, _ = run_loop(runtime)
    assert result["ok"] is False and result["i_dont_know"] is True
    assert result["halt_reason"] == "CONTENT_ADMISSION_UNAVAILABLE"


@pytest.mark.parametrize("case,reason", [
    ("anonymous", "SYNTHESIS_SUBJECT_UNAVAILABLE"),
    ("missing_tenant", "SYNTHESIS_SUBJECT_UNAVAILABLE"),
    ("mutable_policy", "SYNTHESIS_SUBJECT_UNAVAILABLE"),
    ("source_denied", "SOURCE_ACCESS_DENIED"),
    ("truthy_source", "SOURCE_ACCESS_DENIED"),
    ("unknown_visibility", "SOURCE_VISIBILITY_UNKNOWN"),
    ("private_external", "PRIVATE_SOURCE_EGRESS_DENIED"),
    ("wrong_owner", "SOURCE_TENANT_DENIED"),
    ("wrong_subject", "SOURCE_ACCESS_DENIED"),
    ("missing_revision", "SOURCE_REVISION_UNAVAILABLE"),
    ("provider_denied", "PROVIDER_ADMISSION_DENIED"),
    ("truthy_provider", "PROVIDER_ADMISSION_DENIED"),
])
def test_identity_visibility_tenant_and_provider_authority_precede_full_hydration(runtime, case, reason):
    policy = PolicyFixture(runtime)
    if case == "anonymous":
        policy.subject = dataclasses.replace(policy.subject, authenticated=False)
    elif case == "missing_tenant":
        policy.subject = dataclasses.replace(policy.subject, tenant_id="")
    elif case == "mutable_policy":
        policy.subject = dataclasses.replace(policy.subject, policy_revision="main")
    elif case in ("source_denied", "truthy_source"):
        policy.allowed = False if case == "source_denied" else 1
    elif case == "unknown_visibility":
        policy.visibility = "UNKNOWN"
    elif case == "private_external":
        policy.visibility, policy.source_tenant, policy.trust_domain = "PRIVATE", "fixture-tenant", "EXTERNAL"
    elif case == "wrong_owner":
        policy.visibility, policy.source_tenant = "PRIVATE", "other-tenant"
    elif case == "wrong_subject":
        policy.subject_override = dataclasses.replace(policy.subject, tenant_id="other-tenant")
    elif case == "missing_revision":
        policy.source_revision = "main"
    elif case in ("provider_denied", "truthy_provider"):
        policy.provider_allowed = False if case == "provider_denied" else 1
    result, _, _ = run_loop(runtime, policy.adapter())
    assert result["ok"] is False and result["halt_reason"] == reason
    assert not policy.spy.calls and not policy.hydrations


def test_private_local_source_requires_explicit_scope_and_does_not_acquire_voice_egress(runtime, monkeypatch):
    policy = PolicyFixture(runtime, visibility="PRIVATE")
    monkeypatch.setenv("A11OY_WALLPA_FINALIZE", "1")
    monkeypatch.setattr(agent, "_wallpa_speak_final", lambda *a, **k: pytest.fail("Unadmitted expression egress"))
    result, _, _ = run_loop(runtime, policy.adapter())
    assert result["ok"] and len(policy.spy.calls) == 1
    assert result["wallpa"]["status"] == "DISABLED"


@pytest.mark.parametrize("mutation", ["hash", "source", "generation", "handle_plane", "missing_hash"])
def test_unbound_or_unknown_retrieval_identity_cannot_reach_model(runtime, mutation):
    policy = PolicyFixture(runtime)

    def changed(query):
        result = rag.query(query, k=6)
        if mutation == "generation":
            result["generation_digest_sha256"] = "c" * 64
        elif mutation == "handle_plane":
            result["chunks"][0]["retrieval_plane"] = "brain_handle"
        elif mutation == "missing_hash":
            result["chunks"][0].pop("sha256")
        else:
            result["chunks"][0]["sha256" if mutation == "hash" else "source"] = "d" * 64
        return result

    result, _, _ = run_loop(runtime, policy.adapter(), changed)
    assert result["ok"] is False and not policy.spy.calls


def test_full_content_tamper_after_retrieval_fails_even_when_excerpt_looks_plausible(runtime):
    policy = PolicyFixture(runtime)

    def changed(query):
        result = rag.query(query, k=6)
        conn = rag._db()
        conn.execute("UPDATE org_chunks_gen SET body=body || ' tampered suffix' WHERE chunk_id=?",
                     (result["chunks"][0]["chunk_id"],))
        conn.commit()
        conn.close()
        return result

    result, _, _ = run_loop(runtime, policy.adapter(), changed)
    assert result["ok"] is False and result["halt_reason"] == "SOURCE_HYDRATION_UNAVAILABLE"
    assert not policy.spy.calls


@pytest.mark.parametrize("mutation", ["revoked_source", "revoked_provider", "changed_content", "changed_handle"])
def test_admission_is_rechecked_after_hydration_and_before_egress(runtime, mutation):
    policy = PolicyFixture(runtime)

    def after(rows):
        if mutation == "revoked_source":
            policy.allowed = False
        elif mutation == "revoked_provider":
            policy.provider_allowed = False
        elif mutation == "changed_content":
            rows[0]["content"] += "changed"
        else:
            rows[0]["handle"] = dataclasses.replace(rows[0]["handle"], source="fixture:other")
    policy.after_hydrate = after
    result, _, _ = run_loop(runtime, policy.adapter())
    assert result["ok"] is False and not policy.spy.calls


def test_backend_exception_cannot_echo_private_source_text_into_failure_trace(runtime):
    policy = PolicyFixture(runtime, visibility="PRIVATE")
    policy.spy.failure = True
    result, receipts, events = run_loop(runtime, policy.adapter())
    assert result["ok"] is False and result["halt_reason"] == "SYNTHESIS_BACKEND_FAILED"
    assert MARKER not in json.dumps({"result": result, "receipts": receipts, "events": events})


def test_custom_admission_exception_cannot_publish_arbitrary_uppercase_source_content(runtime):
    async def rejected(**kwargs):
        raise agent.SynthesisAdmissionError(MARKER)

    result, _, _ = run_loop(runtime, rejected)
    assert result["halt_reason"] == "SYNTHESIS_ADMISSION_REJECTED"


@pytest.mark.parametrize("failure", [{"ok": False}, {"ok": 0}, {"error": MARKER}])
def test_explicit_backend_failure_cannot_become_success(runtime, failure):
    policy = PolicyFixture(runtime)
    policy.spy.extra_result = failure
    result, _, _ = run_loop(runtime, policy.adapter())
    assert result["ok"] is False and result["halt_reason"] == "SYNTHESIS_RESPONSE_UNAVAILABLE"
    assert len(policy.spy.calls) == 1  # admitted local spy returned a failed response


@pytest.mark.parametrize("case", ["empty", "stub", "voice", "bad_hash", "false_count", "bad_provider"])
def test_fsm_rejects_malformed_controller_success_envelopes(runtime, case, monkeypatch):
    monkeypatch.setenv("A11OY_WALLPA_FINALIZE", "1")
    monkeypatch.setattr(agent, "_wallpa_speak_final", lambda *a, **k: pytest.fail("Unadmitted expression"))

    async def malformed(**kwargs):
        envelope = {"text": "SIMULATED callback response", "model": "SIMULATED", "stub": False,
                    "_expression_authorized": False,
                    "synthesis_admission": {"state": "AUTHORIZED_CONTENT_SUPPLIED", "source_count": 6,
                        "context_sha256": "a" * 64, "semantic_support_verified": False,
                        "provider_id": "SIMULATED", "model_id": "SIMULATED", "trust_domain": "LOCAL"}}
        if case == "empty":
            return {}
        if case == "stub":
            envelope["stub"] = True
        elif case == "voice":
            envelope["_expression_authorized"] = True
        elif case == "bad_hash":
            envelope["synthesis_admission"]["context_sha256"] = "short"
        elif case == "false_count":
            envelope["synthesis_admission"]["source_count"] = True
        else:
            envelope["synthesis_admission"]["trust_domain"] = "UNKNOWN"
        return envelope

    result, _, _ = run_loop(runtime, malformed)
    assert result["ok"] is False and result["halt_reason"] == "SYNTHESIS_RESPONSE_UNAVAILABLE"


@pytest.mark.parametrize("case", ["metadata", "error", "exception", "malformed_chunk"])
def test_retrieval_metadata_and_errors_cannot_publish_source_text_before_admission(runtime, case):
    policy = PolicyFixture(runtime)

    def retrieval(query):
        if case == "exception":
            raise RuntimeError(MARKER)
        if case == "error":
            return {"ok": False, "i_dont_know": True, "honest_note": MARKER, "error": MARKER}
        result = rag.query(query, k=6)
        if case == "malformed_chunk":
            result["chunks"] = [MARKER]
        else:
            for chunk in result["chunks"]:
                chunk["evidence"] = {key: MARKER for key in ("path", "source", "corpus", "citation", "sha256")}
                chunk["lambda"] = MARKER
        return result

    result, receipts, events = run_loop(runtime, policy.adapter(), retrieval)
    serialized = json.dumps({"result": result, "events": events, "receipts": receipts})
    assert all(chunk["sha256"] not in serialized for chunk in runtime["retrieval"]["chunks"])
    if case == "metadata":
        assert result["ok"] and len(policy.spy.calls) == 1
    else:
        assert result["ok"] is False and not policy.spy.calls


def test_direct_hydrator_requires_explicit_identity_and_strict_authorization(runtime):
    result = runtime["retrieval"]
    chunk = result["chunks"][0]
    handle = agent.SynthesisHandle(result["generation_id"], result["generation_digest_sha256"],
                                   *(chunk[key] for key in ("chunk_id", "node_id", "repo", "path", "source", "sha256")))
    subject = agent.SynthesisSubject("fixture-principal", "fixture-tenant", POLICY_REVISION, True)
    with pytest.raises(agent.SynthesisAdmissionError, match="ACCESS_DENIED"):
        rag.hydrate_answer_evidence(subject, (handle,), authorizer=lambda s, h: 1)
    with pytest.raises(agent.SynthesisAdmissionError, match="SUBJECT_UNAVAILABLE"):
        rag.hydrate_answer_evidence(dataclasses.replace(subject, authenticated=False), (handle,),
                                    authorizer=lambda s, h: True)
    with pytest.raises(agent.SynthesisAdmissionError, match="SUBJECT_UNAVAILABLE"):
        rag.hydrate_answer_evidence(dataclasses.replace(subject, tenant_id=""), (handle,),
                                    authorizer=lambda s, h: True)
