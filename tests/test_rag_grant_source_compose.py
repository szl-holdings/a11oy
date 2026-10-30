#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""R2/R3 registry composed with R6 synthesis through the three real Code routes.

Real SQLite generation, real ``SourceRightsRegistry`` with chunk bindings, the
controller factory, ``RegistryGrantSource``, ``hydrate_answer_evidence`` and
``AuthorizedRagSynthesis``, driven through ``/agent/run``, ``/agent/stream`` and
agentic ``/chat/stream``. The only destination is a local spy transport.
Identities, sources and grants are synthetic. No credential, network or model.
"""
import hashlib
import importlib
import json
import sqlite3

import pytest

import a11oy_agent_loop as agent
import a11oy_org_rag as rag
import a11oy_rag_grant_source as gsrc
import a11oy_rag_source_rights as sr
import a11oy_rag_synthesis_controller as ctl


MARKER = "SYNTHETIC_COMPOSED_SOURCE_TEXT"
POLICY = "a" * 64
C0, C1, C2 = "0" * 40, "1" * 40, "2" * 40
TASK = "synthesis"
VARIANTS = ("run", "stream", "chat")
REPO = "fixture"
PRINCIPAL_A = sr.VerifiedPrincipal("principal-a", "tenant-a", POLICY, True)


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
    monkeypatch.setenv("A11OY_WALLPA_FINALIZE", "0")
    conn = rag._db()
    rag._init_schema(conn)
    generation = rag._begin_generation(conn, "SYNTHETIC_COMPOSE")
    graph = rag.OrgGraph()
    graph.add_node(f"{rag.ORG}/{REPO}", "repo", repo=REPO)
    for index in range(6):
        text = f"synthesis {MARKER} document {index}. " + "é" * 700 + "\U0001D11E" * 200
        rag._ingest_text(graph, conn, repo=REPO, path=f"doc-{index}.md", raw=text,
                         source=f"gh:{rag.ORG}/{REPO}", category="app_code", embed_fn=None,
                         generation_id=generation)
    rag._persist_runtime_state(conn, graph, {"built": True, "mode": "SYNTHETIC_COMPOSE", "ts": 1.0,
                                             "repos": 1, "chunks": 6}, generation)
    conn.close()
    db = sqlite3.connect(str(tmp_path / "rag.sqlite3"))
    rows = db.execute("SELECT chunk_id, sha256 FROM org_chunks_gen WHERE generation_id=?",
                      (generation,)).fetchall()
    db.close()
    assert len(rows) == 6

    orchestrator = importlib.import_module("a11oy_code_orchestrator")
    generic_calls = []

    async def generic_model(*args, **kwargs):
        generic_calls.append(True)
        raise AssertionError("Generic fallback-walking model path must not run")

    monkeypatch.setattr(orchestrator, "agent_model_complete", generic_model)
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
    return {"orchestrator": orchestrator, "generation": generation, "rows": rows,
            "generic_calls": generic_calls, "monkeypatch": monkeypatch, "now": [1_000.0]}


class SpyTransport:
    def __init__(self):
        self.calls = []

    async def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, "options": kwargs})
        return {"text": "SYNTHETIC composed answer; no semantic quality claim.",
                "model": "SYNTHETIC_LOCAL_MODEL", "provider_id": "SYNTHETIC_LOCAL_SPY", "stub": False}


class Setup:
    """Registry + grant source + controller installation, with call recorders."""

    def __init__(self, env, *, visibility="public", owner="public", rights=("read", "index", "egress"),
                 store=sr.SHARED_PUBLIC_STORE, trust="LOCAL", principal=PRINCIPAL_A, bind=True,
                 grants=None, register=True, retention_until=None, grant_source_model=None):
        self.env = env
        self.registry = sr.SourceRightsRegistry(clock=lambda: env["now"][0])
        self.entry = None
        if register:
            self.entry = self.registry.register(
                org=rag.ORG, repo=REPO, commit_sha=C1, tenant_owner=owner, visibility=visibility,
                rights=set(rights), grants=grants, retention_until=retention_until)
            if bind:
                self.bind(self.entry.source_id)
        self.spy = SpyTransport()
        self.destination = ctl.FixedDestination("SYNTHETIC_LOCAL_SPY", "SYNTHETIC_LOCAL_MODEL", trust, self.spy)
        bound_destination = self.destination if grant_source_model is None else ctl.FixedDestination(
            "SYNTHETIC_LOCAL_SPY", grant_source_model, trust, self.spy)
        self.principal = principal
        self.verify_calls = []

        def verify(request, operator):
            self.verify_calls.append(dict(operator))
            return self.principal
        self.gs = gsrc.RegistryGrantSource(self.registry, verify=verify,
                                           destination=bound_destination, store=store)
        self.grants, self.transfers, self.subjects = [], [], []
        real_grant, real_transfer, real_resolve = self.gs.source_grant, self.gs.admit_transfer, self.gs.resolve_subject

        def source_grant(subject, handle):
            grant = real_grant(subject, handle)
            self.grants.append(grant)
            return grant

        def admit_transfer(decision):
            verdict = real_transfer(decision)
            self.transfers.append((decision, verdict))
            return verdict

        def resolve_subject(request, operator):
            subject = real_resolve(request, operator)
            self.subjects.append(subject)
            return subject
        self.gs.source_grant, self.gs.admit_transfer, self.gs.resolve_subject = source_grant, admit_transfer, resolve_subject
        ctl.configure(grant_source=self.gs, destination=self.destination)

    def bind(self, source_id, generation=None, sha=None):
        for chunk_id, chunk_sha in self.env["rows"]:
            self.registry.bind_chunk(generation or self.env["generation"], chunk_id, sha or chunk_sha, source_id)


def _sse(text):
    events = {}
    for part in text.split("\n\n"):
        lines = part.splitlines()
        if len(lines) >= 2 and lines[0].startswith("event: ") and lines[1].startswith("data: "):
            events[lines[0][7:]] = json.loads(lines[1][6:])
    return events


def call(env, variant, extra=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    env["orchestrator"].attach(app)
    client = TestClient(app)
    extra = dict(extra or {})
    if variant == "run":
        response = client.post("/api/a11oy/code/agent/run", json={"task": TASK, **extra})
        assert response.status_code == 200
        done = response.json()
    elif variant == "stream":
        response = client.post("/api/a11oy/code/agent/stream", json={"task": TASK, **extra})
        assert response.status_code == 200
        done = _sse(response.text)["done"]
    else:
        response = client.post("/api/a11oy/code/chat/stream", json={
            "agentic": True, "messages": [{"role": "user", "content": TASK}], **extra})
        assert response.status_code == 200
        done = _sse(response.text)["done"]
    assert not env["generic_calls"]
    assert MARKER not in response.text
    return done


def assert_refused(done, setup, reason):
    assert done["ok"] is False, done
    assert done["halt_reason"] == reason, done
    assert done["i_dont_know"] is True and not done.get("answer")
    assert setup.spy.calls == []


# --------------------------------------------------------------------------- #
# Admitted paths
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("variant", VARIANTS)
def test_admitted_public_source_makes_exactly_one_spy_call(env, variant):
    s = Setup(env)
    done = call(env, variant)
    assert done["ok"] is True and done["synthesis_admission"]["state"] == "AUTHORIZED_CONTENT_SUPPLIED"
    assert len(s.spy.calls) == 1 and s.spy.calls[0]["options"]["allow_fallback"] is False
    assert s.grants and all(g.allowed is True and g.source_revision == C1 and g.visibility == "PUBLIC"
                            and g.source_tenant_id is None for g in s.grants)
    assert [verdict for _, verdict in s.transfers] == [True, True]
    decision = s.transfers[0][0]
    assert decision.subject.tenant_id == "tenant-a" and decision.subject.principal_id == "principal-a"
    assert sorted(decision.source_revisions) == sorted(
        (env["generation"], cid, sha, C1) for cid, sha in env["rows"])
    sources = json.loads(s.spy.calls[0]["messages"][-1]["content"])["sources"]
    assert {src["source_revision"] for src in sources} == {C1}
    assert s.verify_calls and all(op["operator"] is True for op in s.verify_calls)


@pytest.mark.parametrize("variant", VARIANTS)
def test_owned_private_source_in_scoped_store_reaches_local_destination(env, variant):
    s = Setup(env, visibility="private", owner="tenant-a", store=sr.SCOPED_PRIVATE_STORE)
    done = call(env, variant)
    assert done["ok"] is True and len(s.spy.calls) == 1
    assert all(g.visibility == "PRIVATE" and g.source_tenant_id == "tenant-a" for g in s.grants)


# --------------------------------------------------------------------------- #
# Refusals before egress: zero spy calls
# --------------------------------------------------------------------------- #
CASES = [
    ("revoked_after_retrieval", "SOURCE_ACCESS_DENIED"),
    ("revoked_during_hydration", "SOURCE_ACCESS_DENIED"),
    ("retention_expires_during_hydration", "SOURCE_ACCESS_DENIED"),
    ("revision_mismatch_after_reregister", "SOURCE_ACCESS_DENIED"),
    ("revision_changed_before_transfer", "PROVIDER_ADMISSION_DENIED"),
    ("missing_egress_right", "PROVIDER_ADMISSION_DENIED"),
    ("missing_read_right", "SOURCE_ACCESS_DENIED"),
    ("cross_tenant_identical_chunk_id", "SOURCE_ACCESS_DENIED"),
    ("cross_tenant_with_explicit_grant", "SOURCE_TENANT_DENIED"),
    ("binding_sha_mismatch", "SOURCE_ACCESS_DENIED"),
    ("bound_to_other_source", "SOURCE_ACCESS_DENIED"),
    ("unbound_rows", "SOURCE_ACCESS_DENIED"),
    ("unregistered_repo", "SOURCE_ACCESS_DENIED"),
    ("retention_expired", "SOURCE_ACCESS_DENIED"),
    ("private_in_shared_store", "SOURCE_ACCESS_DENIED"),
    ("private_to_external", "SOURCE_ACCESS_DENIED"),
    ("destination_mismatch", "PROVIDER_ADMISSION_DENIED"),
    ("egress_admission_raises", "PROVIDER_ADMISSION_DENIED"),
]


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("case,reason", CASES)
def test_registry_refusals_happen_before_any_egress(env, variant, case, reason):
    orchestrator, mp = env["orchestrator"], env["monkeypatch"]
    kwargs = {}
    if case == "missing_egress_right":
        kwargs["rights"] = ("read", "index")
    elif case == "missing_read_right":
        kwargs["rights"] = ("index", "egress")
    elif case in ("cross_tenant_identical_chunk_id", "cross_tenant_with_explicit_grant"):
        kwargs.update(register=False, store=sr.SCOPED_PRIVATE_STORE)
    elif case == "unbound_rows":
        kwargs["bind"] = False
    elif case == "unregistered_repo":
        kwargs["register"] = False
    elif case == "retention_expired":
        kwargs["retention_until"] = env["now"][0] - 1
    elif case == "private_in_shared_store":
        kwargs.update(visibility="private", owner="tenant-a")
    elif case == "private_to_external":
        kwargs.update(visibility="private", owner="tenant-a", store=sr.SCOPED_PRIVATE_STORE, trust="EXTERNAL")
    elif case == "destination_mismatch":
        kwargs["grant_source_model"] = "OTHER_MODEL"
    elif case == "binding_sha_mismatch":
        kwargs["bind"] = False
    elif case == "bound_to_other_source":
        kwargs["bind"] = False
    elif case == "retention_expires_during_hydration":
        kwargs["retention_until"] = env["now"][0] + 10
    s = Setup(env, **kwargs)
    reg = s.registry

    if case in ("cross_tenant_identical_chunk_id", "cross_tenant_with_explicit_grant"):
        # Tenant A once owned this repo; identical chunk ids were bound in an
        # older generation. The repo now belongs to tenant B at a new revision.
        old = reg.register(org=rag.ORG, repo=REPO, commit_sha=C0, tenant_owner="tenant-a",
                           visibility="private", rights={"read", "index", "egress"})
        s.bind(old.source_id, generation="OLDER-GENERATION")
        reg.revoke(rag.ORG, REPO)
        grants = {"tenant-a": {"read", "egress"}} if case == "cross_tenant_with_explicit_grant" else None
        new = reg.register(org=rag.ORG, repo=REPO, commit_sha=C1, tenant_owner="tenant-b",
                           visibility="private", rights={"read", "index", "egress"}, grants=grants)
        s.bind(new.source_id)
    elif case == "binding_sha_mismatch":
        s.bind(s.entry.source_id, sha="f" * 64)
    elif case == "bound_to_other_source":
        other = reg.register(org=rag.ORG, repo="other", commit_sha=C2, tenant_owner="public",
                             visibility="public", rights={"read", "index", "egress"})
        s.bind(other.source_id)
    elif case == "egress_admission_raises":
        real = reg.admit_source

        def admit_source(org, repo, commit_sha, purpose, principal, **kw):
            if purpose == "egress":
                raise RuntimeError("registry backend unavailable")
            return real(org, repo, commit_sha, purpose, principal, **kw)
        reg.admit_source = admit_source

    if case in ("revoked_after_retrieval", "revision_mismatch_after_reregister"):
        original = orchestrator._agent_rag_query

        def changed(q, **kw):
            result = original(q, **kw)
            reg.revoke(rag.ORG, REPO)
            if case == "revision_mismatch_after_reregister":
                reg.register(org=rag.ORG, repo=REPO, commit_sha=C2, tenant_owner="public",
                             visibility="public", rights={"read", "index", "egress"})
            return result
        mp.setattr(orchestrator, "_agent_rag_query", changed)
    elif case in ("revoked_during_hydration", "retention_expires_during_hydration"):
        original_hydrate = rag.hydrate_answer_evidence

        def hydrate_then_revoke(subject, handles, *, authorizer):
            rows = original_hydrate(subject, handles, authorizer=authorizer)
            if case == "revoked_during_hydration":
                reg.revoke(rag.ORG, REPO)
            else:
                env["now"][0] += 100  # retention deadline passes while bytes are held
            return rows
        mp.setattr(rag, "hydrate_answer_evidence", hydrate_then_revoke)
    elif case == "revision_changed_before_transfer":
        def on_sixth_grant():
            reg.revoke(rag.ORG, REPO)
            entry = reg.register(org=rag.ORG, repo=REPO, commit_sha=C2, tenant_owner="public",
                                 visibility="public", rights={"read", "index", "egress"})
            s.bind(entry.source_id)
        real_grant = s.gs.source_grant

        def grant(subject, handle):
            result = real_grant(subject, handle)
            if len(s.grants) == 6:
                on_sixth_grant()
            return result
        s.gs.source_grant = grant

    done = call(env, variant)
    assert_refused(done, s, reason)
    if case == "private_to_external":
        assert s.grants and all(g.allowed is False for g in s.grants)
    if case == "cross_tenant_with_explicit_grant":
        # The registry admits the grant, but R6 keeps private text in its owner tenant.
        assert s.grants and s.grants[0].allowed is True and s.grants[0].source_tenant_id == "tenant-b"
    if reason == "PROVIDER_ADMISSION_DENIED":
        assert s.transfers and s.transfers[0][1] is False


# --------------------------------------------------------------------------- #
# Identity: body tenants carry no authority; anonymous and unverified fail closed
# --------------------------------------------------------------------------- #
BODY_TENANT = {"tenant_id": "tenant-b", "tenant": "tenant-b", "owner": "tenant-b",
               "principal_id": "principal-b"}


@pytest.mark.parametrize("variant", VARIANTS)
def test_body_supplied_tenant_is_ignored_for_owner(env, variant):
    s = Setup(env, visibility="private", owner="tenant-a", store=sr.SCOPED_PRIVATE_STORE)
    done = call(env, variant, extra=BODY_TENANT)
    assert done["ok"] is True and len(s.spy.calls) == 1
    assert all(sub.tenant_id == "tenant-a" and sub.principal_id == "principal-a" for sub in s.subjects)


@pytest.mark.parametrize("variant", VARIANTS)
def test_body_supplied_tenant_cannot_claim_another_tenants_source(env, variant):
    s = Setup(env, visibility="private", owner="tenant-b", store=sr.SCOPED_PRIVATE_STORE)
    done = call(env, variant, extra=BODY_TENANT)
    assert_refused(done, s, "SOURCE_ACCESS_DENIED")
    assert all(sub.tenant_id == "tenant-a" for sub in s.subjects)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("principal", ["none", "dict", "unauthenticated", "mutable_policy", "raises"])
def test_unverified_principal_keeps_content_admission_unavailable(env, variant, principal):
    s = Setup(env)
    if principal == "none":
        s.principal = None
    elif principal == "dict":
        s.principal = {"principal_id": "principal-a", "tenant_id": "tenant-a", "policy_revision": POLICY}
    elif principal == "unauthenticated":
        s.principal = sr.VerifiedPrincipal("principal-a", "tenant-a", POLICY, False)
    elif principal == "mutable_policy":
        s.principal = sr.VerifiedPrincipal("principal-a", "tenant-a", "main", True)
    else:
        s.gs._verify = lambda request, operator: (_ for _ in ()).throw(RuntimeError("verifier down"))
    done = call(env, variant)
    assert_refused(done, s, "CONTENT_ADMISSION_UNAVAILABLE")
    assert s.grants == [] and s.transfers == []


def test_anonymous_agentic_chat_is_unavailable_and_never_resolves_identity(env):
    s = Setup(env)
    env["monkeypatch"].setattr(env["orchestrator"]._opauth, "principal",
                               lambda request: {"operator": False, "two_person_attested": False})
    done = call(env, "chat")
    assert_refused(done, s, "CONTENT_ADMISSION_UNAVAILABLE")
    assert s.verify_calls == [] and s.grants == []


@pytest.mark.parametrize("path", ["/api/a11oy/code/agent/run", "/api/a11oy/code/agent/stream"])
def test_anonymous_agent_routes_are_blocked_before_any_lookup(env, path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    s = Setup(env)
    env["monkeypatch"].setattr(env["orchestrator"]._opauth, "principal",
                               lambda request: {"operator": False, "two_person_attested": False})
    app = FastAPI()
    env["orchestrator"].attach(app)
    response = TestClient(app).post(path, json={"task": TASK, **BODY_TENANT})
    assert response.status_code == 401
    assert s.verify_calls == [] and s.grants == [] and s.spy.calls == []


def test_same_chunk_id_follows_the_content_digest(env):
    del env
    reg = sr.SourceRightsRegistry()
    left = reg.register(org="org-a", repo="notes", commit_sha=C1, tenant_owner="public",
                        visibility="public", rights={"read", "index", "egress"})
    right = reg.register(org="org-b", repo="notes", commit_sha=C2, tenant_owner="public",
                         visibility="public", rights={"read", "index", "egress"})
    chunk_id, sha_left, sha_right = "c" * 24, "a" * 64, "b" * 64
    reg.bind_chunk("g1", chunk_id, sha_left, left.source_id)
    reg.bind_chunk("g1", chunk_id, sha_right, right.source_id)
    destination = ctl.FixedDestination("P", "M", "LOCAL", lambda *args, **kwargs: None)
    source = gsrc.RegistryGrantSource(reg, verify=lambda request, operator: PRINCIPAL_A,
                                      destination=destination)
    subject = agent.SynthesisSubject("principal-a", "tenant-a", POLICY, True)

    def handle(org: str, digest: str):
        return agent.SynthesisHandle("g1", "d" * 64, chunk_id, "n", "notes", "p",
                                     f"gh:{org}/notes", digest)

    granted = source.source_grant(subject, handle("org-a", sha_left))
    assert granted.allowed is True and granted.source_revision == C1 and granted.visibility == "PUBLIC"
    assert source.source_grant(subject, handle("org-a", sha_right)).allowed is False
    assert source.source_grant(subject, handle("org-b", sha_left)).allowed is False

    def decision(digest: str, revision: str):
        return ctl.TransferDecision(
            subject=subject, source_revisions=(("g1", chunk_id, digest, revision),),
            provider_id="P", model_id="M", trust_domain="LOCAL", purpose=gsrc.PURPOSE,
            task_sha256="e" * 64, history_forwarded=False, expression_authority="NONE")

    assert source.admit_transfer(decision(sha_left, C1)) is True
    assert source.admit_transfer(decision(sha_right, C2)) is True
    assert source.admit_transfer(decision(sha_right, C1)) is False
    assert source.admit_transfer(decision("f" * 64, C1)) is False


def test_grant_source_satisfies_controller_protocol(env):
    s = Setup(env)
    assert isinstance(s.gs, ctl.SynthesisGrantSource)
    with pytest.raises(sr.SourceRightsError):
        gsrc.RegistryGrantSource(object(), verify=lambda r, o: None, destination=s.destination)
