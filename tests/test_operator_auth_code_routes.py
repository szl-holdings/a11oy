#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Golden verdicts for the deny-by-default operator gate on code execution paths.

Anonymous callers must never execute code, run tools, write state, or read chat
history; a request body can never assert two-person attestation. Every sandbox
reached through a11oy_code_engine.governed_turn needs allow_exec from the header
principal, and a withheld execution is labelled NOT_EXECUTED, never as a run.
"""
import asyncio
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="a11oy-opauth-")
os.environ.setdefault("A11OY_CODE_DB", str(Path(_TMP) / "code.db"))
os.environ.setdefault("A11OY_CODE_SANDBOX", str(Path(_TMP) / "sandbox"))
os.environ.setdefault("A11OY_REACT_DB", str(Path(_TMP) / "react.sqlite3"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.applications import Starlette  # noqa: E402

import a11oy_code_as_action as gcak  # noqa: E402
import a11oy_code_engine as engine  # noqa: E402
import a11oy_code_orchestrator as orchestrator  # noqa: E402
import a11oy_governed_kernel as gk  # noqa: E402
import szl_operator_auth as opauth  # noqa: E402

OPERATOR = "op-test-secret-not-real"
APPROVER = "approver-test-secret-not-real"
OPERATOR_ONLY = {"Authorization": f"Bearer {OPERATOR}"}
BOTH = {"Authorization": f"Bearer {OPERATOR}", opauth.SECOND_APPROVER_HEADER: APPROVER}
SECRETS = {opauth.OPERATOR_KEY_ENV: OPERATOR, opauth.SECOND_APPROVER_KEY_ENV: APPROVER}


def _client() -> TestClient:
    app = FastAPI()
    orchestrator.attach(app)
    return TestClient(app)


def _unsigned(payload):
    return {"signed": False, "signatures": [], "payloadType": "application/test+json"}


def _fake_sandbox(counter: list):
    def _run(code, lang="python", **_kw):
        counter.append(code)
        return {"ok": True, "stdout": "ran\n", "stderr": "", "exit": 0,
                "elapsed_ms": 1.0, "isolation": "test double"}
    return _run


def _sse_events(text: str) -> list:
    import json
    out = []
    for chunk in text.split("\n\n"):
        event, data = None, ""
        for line in chunk.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if event:
            out.append((event, json.loads(data) if data else {}))
    return out


class PrincipalResolution(unittest.TestCase):
    def test_no_secrets_configured_nobody_is_operator(self):
        with patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: "", opauth.SECOND_APPROVER_KEY_ENV: ""}):
            who = opauth.principal_from_headers({"Authorization": "Bearer "})
        self.assertEqual(who, {"operator": False, "two_person_attested": False})

    def test_same_secret_twice_is_not_two_people(self):
        env = {opauth.OPERATOR_KEY_ENV: OPERATOR, opauth.SECOND_APPROVER_KEY_ENV: OPERATOR}
        with patch.dict(os.environ, env):
            who = opauth.principal_from_headers(
                {"Authorization": f"Bearer {OPERATOR}", opauth.SECOND_APPROVER_HEADER: OPERATOR})
        self.assertTrue(who["operator"])
        self.assertFalse(who["two_person_attested"])

    def test_operator_plus_distinct_approver_attests(self):
        with patch.dict(os.environ, SECRETS):
            who = opauth.principal_from_headers(
                {"authorization": f"bearer {OPERATOR}", "X-A11oy-Second-Approver": APPROVER})
        self.assertEqual(who, {"operator": True, "two_person_attested": True})

    def test_exec_permitted_denies_on_resolver_error(self):
        self.assertFalse(opauth.exec_permitted(object()))


class AnonymousIsDenied(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, SECRETS)
        self.env.start()
        self.client = _client()

    def tearDown(self):
        self.env.stop()

    def test_run_denied_even_when_body_claims_attestation(self):
        with patch.object(orchestrator, "run_code") as ran:
            r = self.client.post("/api/a11oy/code/run",
                                 json={"language": "python", "code": "print(1)",
                                       "two_person_attested": True})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["status"], "BLOCKED")
        ran.assert_not_called()

    def test_run_denied_for_operator_without_second_approver(self):
        with patch.object(orchestrator, "run_code") as ran:
            r = self.client.post("/api/a11oy/code/run", headers=OPERATOR_ONLY,
                                 json={"language": "python", "code": "print(1)"})
        self.assertEqual(r.status_code, 401)
        ran.assert_not_called()

    def test_run_allowed_with_both_credentials(self):
        fake = {"stdout": "1\n", "stderr": "", "code": 0}
        with patch.object(orchestrator, "run_code", return_value=dict(fake)) as ran:
            r = self.client.post("/api/a11oy/code/run", headers=BOTH,
                                 json={"language": "python", "code": "print(1)"})
        self.assertEqual(r.status_code, 200, r.text)
        ran.assert_called_once()

    def test_kernel_exec_denied_anonymous(self):
        with patch.object(gk, "get_kernel") as get_kernel:
            r = self.client.post("/api/a11oy/code/kernel/run1/exec", json={"code": "print(1)"})
        self.assertEqual(r.status_code, 401)
        get_kernel.assert_not_called()

    def test_kernel_exec_rejects_bad_run_id_before_any_kernel(self):
        for bad in ("a.b", "x" * 65):
            with self.subTest(run_id=bad), patch.object(gk, "get_kernel") as get_kernel:
                r = self.client.post(f"/api/a11oy/code/kernel/{bad}/exec", headers=BOTH,
                                     json={"code": "print(1)"})
                self.assertEqual(r.status_code, 400, r.text)
                get_kernel.assert_not_called()

    def test_state_and_history_routes_denied_anonymous(self):
        for method, path in [("post", "/api/a11oy/code/rag/index"),
                             ("post", "/api/a11oy/code/rag/refresh"),
                             ("post", "/api/a11oy/code/rag/seed"),
                             ("get", "/api/a11oy/code/conversations?user_id=founder"),
                             ("get", "/api/a11oy/code/conversations/x"),
                             ("get", "/api/a11oy/code/conversations/x/export"),
                             ("get", "/api/a11oy/code/profile/founder"),
                             ("post", "/api/a11oy/code/profile/founder")]:
            with self.subTest(path=path):
                r = getattr(self.client, method)(path, json={}) if method == "post" \
                    else self.client.get(path)
                self.assertEqual(r.status_code, 401, f"{method.upper()} {path} -> {r.status_code}")

    def test_issue_key_requires_operator(self):
        r = self.client.post("/api/a11oy/code/v1/keys", json={"owner": "x"})
        self.assertEqual(r.status_code, 403)

    def test_agent_run_and_stream_denied_anonymous(self):
        with patch.object(orchestrator._agent, "run_agent", new=AsyncMock()) as run_agent:
            for path in ("/api/a11oy/code/agent/run", "/api/a11oy/code/agent/stream"):
                with self.subTest(path=path):
                    r = self.client.post(path, json={"task": "read the repo",
                                                     "two_person_attested": True})
                    self.assertEqual(r.status_code, 401)
                    self.assertEqual(r.json()["status"], "BLOCKED")
        run_agent.assert_not_called()

    def test_agent_run_operator_gets_principal_bound_gate(self):
        seen = {}

        def fake_puriq(action, ctx):
            seen.update(ctx)
            return {"allow": False, "score": 0.0, "lambda": 0.0, "reason": "test"}

        async def fake_run_agent(task, **kw):
            kw["puriq_decide"]("fs_read", {"authorized": True, "two_person_attested": True})
            return {"ok": True}

        with patch.object(orchestrator._agent, "run_agent", new=fake_run_agent), \
                patch.object(orchestrator, "puriq_decide", new=fake_puriq):
            r = self.client.post("/api/a11oy/code/agent/run", headers=OPERATOR_ONLY,
                                 json={"task": "read the repo"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((seen["authorized"], seen["two_person_attested"]), (True, False))


class ChatStreamMemory(unittest.TestCase):
    """Anonymous chat never reads stored history by id and is never persisted."""

    def setUp(self):
        self.env = patch.dict(os.environ, SECRETS)
        self.env.start()
        self.client = _client()
        self.patches = [
            patch.object(orchestrator, "inference_backend_ready", return_value=False),
            patch.object(orchestrator, "_serving_base", return_value=("http://127.0.0.1:9", False)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()

    def _stream(self, headers):
        body = {"message": "hello", "conversation_id": "victim-conv", "user_id": "founder"}
        with patch.object(orchestrator, "mem_get_conversation",
                          return_value={"messages": [{"role": "user", "content": "secret"}]}) as get, \
                patch.object(orchestrator, "mem_upsert_conversation") as upsert, \
                patch.object(orchestrator, "mem_add_message") as add:
            r = self.client.post("/api/a11oy/code/chat/stream", headers=headers, json=body)
        return r, get, upsert, add

    def test_anonymous_does_not_read_or_persist(self):
        r, get, upsert, add = self._stream({})
        self.assertEqual(r.status_code, 200, r.text)
        get.assert_not_called()
        upsert.assert_not_called()
        add.assert_not_called()
        route = dict(_sse_events(r.text))["route"]
        self.assertNotEqual(route["conversation_id"], "victim-conv")

    def test_operator_keeps_history_and_persistence(self):
        r, get, upsert, add = self._stream(OPERATOR_ONLY)
        self.assertEqual(r.status_code, 200, r.text)
        get.assert_called_once_with("victim-conv")
        upsert.assert_called_once()
        self.assertEqual(add.call_count, 2)  # user turn + assistant stub
        route = dict(_sse_events(r.text))["route"]
        self.assertEqual(route["conversation_id"], "victim-conv")


class ToolsNeedAuthorization(unittest.TestCase):
    def test_execute_tool_denies_unauthorized_before_dispatch(self):
        with patch.object(orchestrator, "_dispatch_tool") as dispatch:
            out = asyncio.run(orchestrator.execute_tool("fs_read", {"path": "x"}, None,
                                                        two_person_attested=True))
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual({k: out["gate"][k] for k in ("allow", "score", "lambda")},
                         {"allow": False, "score": 0.0, "lambda": 0.0})
        self.assertTrue(out["gate"]["reason"])
        dispatch.assert_not_called()

    def test_run_tests_is_state_changing_and_operator_only_is_denied(self):
        self.assertIn("run_tests", orchestrator.STATE_CHANGING_TOOLS)
        with patch.object(orchestrator, "_dispatch_tool") as dispatch:
            out = asyncio.run(orchestrator.execute_tool(
                "run_tests", {"command": "python3 -m pytest -q"}, None,
                two_person_attested=False, authorized=True))
        self.assertFalse(out["ok"])
        self.assertFalse(out["gate"]["allow"])
        dispatch.assert_not_called()

    def test_puriq_without_stated_authorization_denies(self):
        decision = orchestrator.puriq_decide("fs_read", {"risk": "low"})
        self.assertFalse(decision["allow"])

    def test_principal_runner_cannot_widen_attestation(self):
        seen = {}

        async def fake_execute(name, args, client, two_person_attested=False, authorized=False):
            seen.update(two_person_attested=two_person_attested, authorized=authorized)
            return {"ok": False}

        runner = orchestrator._principal_tool_runner(None, {"operator": False,
                                                            "two_person_attested": False})
        with patch.object(orchestrator, "execute_tool", fake_execute):
            asyncio.run(runner("shell_exec", {}, two_person_attested=True, authorized=True))
        self.assertEqual(seen, {"two_person_attested": False, "authorized": False})

    def test_principal_puriq_anonymous_cannot_mint_allow(self):
        gate = orchestrator._principal_puriq({"operator": False, "two_person_attested": False})
        decision = gate("fs_read", {"risk": "low", "authorized": True,
                                    "two_person_attested": True})
        self.assertFalse(decision["allow"])


class CodeAsActionRoutes(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, SECRETS)
        self.env.start()
        app = Starlette()
        gcak.register(app, "a11oy", None)
        self.client = TestClient(app)
        self.run_id = gcak._STORE.create("golden")

    def tearDown(self):
        self.env.stop()

    def _post(self, phase, headers):
        body = {"code": "x = 1", "run_id": self.run_id}
        fake = MagicMock(return_value={"verdict": "ALLOW", "executed": True})
        with patch.object(gcak, "run_cell", fake):
            r = self.client.post(f"/api/a11oy/v1/agent/code/{phase}", headers=headers, json=body)
        return r, fake

    def test_compose_and_revise_verdicts(self):
        for phase in ("compose", "revise"):
            for label, headers, status, calls in (("anonymous", {}, 401, 0),
                                                  ("operator only", OPERATOR_ONLY, 401, 0),
                                                  ("both", BOTH, 200, 1)):
                with self.subTest(phase=phase, caller=label):
                    r, fake = self._post(phase, headers)
                    self.assertEqual(r.status_code, status, r.text)
                    self.assertEqual(fake.call_count, calls)
                    if status == 401:
                        self.assertEqual(r.json()["status"], "BLOCKED")

    def test_cell_without_kernel_is_not_executed_and_not_metered(self):
        verdict = {"verdict": "ALLOW", "allowed": True, "security": {}, "restraint": {},
                   "lambda": {}}
        operator = MagicMock()
        fake_energy = types.SimpleNamespace(get_operator=MagicMock(return_value=operator))
        fake_prov = types.SimpleNamespace(build_composite=MagicMock(return_value={}))
        with patch.object(gcak, "evaluate_gate", return_value=verdict), \
                patch.object(gk, "get_kernel", return_value=None), \
                patch.dict(sys.modules, {"szl_energy_operator": fake_energy,
                                         "szl_provenance_receipt": fake_prov}):
            cell = gcak.run_cell(self.run_id, "x = 1")
        receipt = cell["receipt"]
        self.assertFalse(cell["executed"])
        self.assertFalse(receipt["executed"])
        self.assertIn("NOT EXECUTED", receipt["honest_label"])
        self.assertIsNone(receipt["energy"]["ledger_seq"])
        fake_energy.get_operator.assert_not_called()
        operator.submit_external_job.assert_not_called()


class KernelCapacity(unittest.TestCase):
    def setUp(self):
        self.registry = patch.dict(gk._KERNELS, clear=True)
        self.registry.start()
        self.cap = patch.object(gk, "MAX_KERNELS", 2)
        self.cap.start()

    def tearDown(self):
        self.cap.stop()
        self.registry.stop()

    def test_lru_idle_kernel_is_evicted_to_free_a_slot(self):
        old = gk.get_kernel("old", create=True)
        gk.get_kernel("new", create=True)
        old.last_used = time.time() - 60
        k = gk.get_kernel("third", create=True)
        self.assertIsNotNone(k)
        self.assertNotIn("old", gk._KERNELS)
        self.assertEqual(set(gk._KERNELS), {"new", "third"})
        out = old.exec_cell("print(1)")  # a stale handle never respawns a worker
        self.assertFalse(out["executed"])
        self.assertIsNone(old._proc)

    def test_dead_kernel_is_evicted_before_a_live_idle_one(self):
        dead = gk.get_kernel("dead", create=True)
        gk.get_kernel("idle", create=True)
        dead._spawned_at = time.time()  # spawned once, worker gone
        dead.last_used = time.time() + 60  # most recent, yet dead goes first
        self.assertIsNotNone(gk.get_kernel("third", create=True))
        self.assertEqual(set(gk._KERNELS), {"idle", "third"})

    def test_busy_kernels_are_never_evicted_and_cap_answers_none(self):
        for rid in ("a", "b"):
            gk.get_kernel(rid, create=True)._busy = 1
        self.assertIsNone(gk.get_kernel("c", create=True))
        self.assertEqual(set(gk._KERNELS), {"a", "b"})

    def test_max_kernels_env_parse_is_defensive(self):
        for raw, want in (("banana", 4), ("", 4), ("0", 1), (" 7 ", 7)):
            with self.subTest(raw=raw), patch.dict(os.environ, {"A11OY_MAX_KERNELS": raw}):
                self.assertEqual(gk._max_kernels_from_env(), want)

    def test_kernel_exec_429_when_every_slot_is_busy(self):
        with patch.dict(os.environ, SECRETS):
            for rid in ("a", "b"):
                gk.get_kernel(rid, create=True)._busy = 1
            fake_gate = {"allow": True, "score": 1.0, "lambda": 1.0, "reason": "test"}
            with patch.object(orchestrator, "puriq_decide", return_value=fake_gate):
                r = _client().post("/api/a11oy/code/kernel/c/exec", headers=BOTH,
                                   json={"code": "print(1)"})
        self.assertEqual(r.status_code, 429, r.text)
        self.assertEqual(r.json()["status"], "BLOCKED")
        self.assertFalse(r.json()["executed"])


class GovernedTurnChokepoint(unittest.TestCase):
    """Every path into a11oy_code_engine._sandbox_exec needs allow_exec."""

    def setUp(self):
        self.env = patch.dict(os.environ, SECRETS)
        self.env.start()
        self.calls = []
        self.patches = [patch.object(engine, "_sandbox_exec", _fake_sandbox(self.calls)),
                        patch.object(engine, "_model_configured", return_value=False)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()

    def test_default_is_not_executed_and_receipt_says_so(self):
        signed = []
        run = engine.governed_turn("code", "write a python function that returns 5 primes",
                                   lambda p: signed.append(p) or _unsigned(p), "a11oy",
                                   sandbox=True)
        self.assertEqual(self.calls, [])
        self.assertEqual(run["decision"], "ALLOW")
        self.assertFalse(run["executed"])
        self.assertFalse(run["sandbox"]["executed"])
        self.assertTrue(run["execution_status"].startswith("NOT_EXECUTED"))
        self.assertFalse(signed[-1]["executed"])
        self.assertNotIn("ran in the governed sandbox", run["summary"])
        self.assertFalse(run["receipt_chain"][-1]["body"]["executed"])

    def test_explicit_allow_exec_runs_once(self):
        run = engine.governed_turn("code", "write a python function that returns 5 primes",
                                   _unsigned, "a11oy", sandbox=True, allow_exec=True)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(run["executed"])
        self.assertEqual(run["execution_status"], "EXECUTED")

    def _app(self, register):
        app = Starlette()
        register(app)
        return TestClient(app)

    def _assert_route(self, client, method, path, body):
        # Anonymous is refused (401 BLOCKED) before any model call, gate or receipt;
        # the operator alone reaches the route but never the sandbox; only the
        # two-person principal executes.
        for label, headers, want_status, want_exec in (("anonymous", {}, 401, False),
                                                       ("operator only", OPERATOR_ONLY, 200, False),
                                                       ("both", BOTH, 200, True)):
            with self.subTest(path=path, caller=label):
                self.calls.clear()
                r = client.request(method, path, headers=headers, json=body)
                self.assertEqual(r.status_code, want_status, r.text[:400])
                if want_status == 401:
                    self.assertEqual(r.json()["status"], "BLOCKED")
                self.assertEqual(bool(self.calls), want_exec)

    def test_engine_run_and_turn_routes(self):
        client = self._app(lambda app: engine.register(app, "a11oy", _unsigned))
        body = {"prompt": "write a python function that returns 5 primes",
                "mode": "code", "sandbox": True, "two_person_attested": True}
        for path in ("/api/a11oy/v1/code/run", "/api/a11oy/v1/code/turn"):
            self._assert_route(client, "POST", path, body)

    def test_runloop_runstep_route(self):
        import a11oy_code_runloop as runloop
        client = self._app(lambda app: runloop.register(app, "a11oy", _unsigned))
        body = {"prompt": "write a python function that returns 5 primes",
                "mode": "code", "sandbox": True, "two_person_attested": True}
        self._assert_route(client, "POST", "/api/a11oy/v1/code/runstep", body)

    def test_agentloop_run_route(self):
        import szl_agent_loop_governed as aloop
        client = self._app(lambda app: aloop.register(app, ns="a11oy", sign_fn=_unsigned))
        body = {"task": "write a python function that returns 5 primes", "mode": "code",
                "max_retries": 0, "consult_brain": False, "allocate_energy": False}
        self._assert_route(client, "POST", "/api/a11oy/v1/agentloop/run", body)

    def test_verify_transcript_never_executes_on_get(self):
        import szl_verify_transcript as vt
        client = self._app(lambda app: vt.register(app, ns="a11oy", sign_fn=_unsigned))
        with patch.object(vt, "build_transcript",
                          return_value={"ok": True, "status_code": 200}) as build:
            for method, headers, want in (("GET", {}, False), ("GET", BOTH, False),
                                          ("POST", OPERATOR_ONLY, False), ("POST", BOTH, True)):
                with self.subTest(method=method, headers=sorted(headers)):
                    build.reset_mock()
                    r = client.request(method, "/api/a11oy/v1/verify/transcript",
                                       headers=headers,
                                       json={"mode": "code"} if method == "POST" else None)
                    self.assertEqual(r.status_code, 200, r.text[:400])
                    self.assertIs(build.call_args.kwargs["allow_exec"], want)
            build.reset_mock()
            r = client.post("/api/a11oy/v1/verify/transcript", json={"mode": "code"})
            self.assertEqual(r.status_code, 401, r.text[:400])
            build.assert_not_called()

    def test_runloop_plan_and_approve_refuse_anonymous(self):
        import a11oy_code_runloop as runloop
        client = self._app(lambda app: runloop.register(app, "a11oy", _unsigned))
        for path, body in (("/api/a11oy/v1/code/plan", {"task": "t"}),
                           ("/api/a11oy/v1/code/approve",
                            {"checkpoint_id": "c", "approver": "a"})):
            with self.subTest(path=path):
                self.assertEqual(client.post(path, json=body).status_code, 401)
                self.assertEqual(client.post(path, json=body, headers=OPERATOR_ONLY).status_code,
                                 200)

    def test_consensus_refuses_anonymous(self):
        client = self._app(lambda app: engine.register(app, "a11oy", _unsigned))
        path = "/api/a11oy/v1/code/consensus"
        self.assertEqual(client.post(path, json={"prompt": "p"}).status_code, 401)
        self.assertEqual(client.post(path, json={"prompt": "p"}, headers=OPERATOR_ONLY).status_code,
                         200)

    def test_build_transcript_threads_allow_exec_to_the_loop(self):
        import szl_verify_transcript as vt
        with patch.object(vt._aloop, "run_loop", return_value={}) as run_loop:
            vt.build_transcript("t", sign_fn=_unsigned, mode="code")
            self.assertIs(run_loop.call_args.kwargs["allow_exec"], False)
            vt.build_transcript("t", sign_fn=_unsigned, mode="code", allow_exec=True)
            self.assertIs(run_loop.call_args.kwargs["allow_exec"], True)


class ReactWriteRoutes(unittest.TestCase):
    def test_write_routes_denied_anonymous(self):
        import a11oy_react_core as react
        with patch.dict(os.environ, SECRETS):
            app = Starlette()
            react.register(app, ns="a11oy")
            client = TestClient(app)
            for path in ("run", "resume", "reflect", "memory/add", "skills/admit"):
                with self.subTest(path=path):
                    r = client.post(f"/api/a11oy/v1/agent/react/{path}",
                                    json={"goal": "g", "run_id": "r", "text": "t",
                                          "reflection": "t", "name": "n", "recipe": "r"})
                    self.assertEqual(r.status_code, 401, r.text[:300])
                    self.assertEqual(r.json()["status"], "BLOCKED")
            r = client.post("/api/a11oy/v1/agent/react/memory/add", headers=OPERATOR_ONLY,
                            json={"text": "operator note"})
            self.assertEqual(r.status_code, 200, r.text[:300])


class KenMcpCall(unittest.TestCase):
    def test_body_cannot_assert_two_person(self):
        import szl_ken as ken

        async def allow_gate(plan, state):
            return {"decision": "allow"}

        async def dispatch(plan, state):
            return {"tool": plan["tool"], "success": True}

        app = FastAPI()
        app.include_router(ken.make_ken_router("killinchu", ken.get_default_tools("killinchu"),
                                               dispatch_fn=dispatch))
        client = TestClient(app)
        body = {"name": "halt_drone", "arguments": {}, "two_person_attested": True,
                "attestation": "yes"}
        with patch.dict(os.environ, SECRETS), patch.object(ken, "a11oy_gate", allow_gate):
            self.assertEqual(client.post("/api/killinchu/v1/mcp/call", json=body).status_code, 403)
            self.assertEqual(client.post("/api/killinchu/v1/mcp/call", headers=OPERATOR_ONLY,
                                         json=body).status_code, 403)
            self.assertEqual(client.post("/api/killinchu/v1/mcp/call", headers=BOTH,
                                         json=body).status_code, 200)


# ---------------------------------------------------------------------------
# Route-level gate: szl_operator_auth.PROTECTED_ROUTES + OperatorGateMiddleware.
# ---------------------------------------------------------------------------
class GateTable(unittest.TestCase):
    def test_safe_methods_are_never_gated(self):
        for method in ("GET", "HEAD", "OPTIONS", "get"):
            with self.subTest(method=method):
                self.assertIsNone(opauth.protected_action(method, "/api/a11oy/code/run"))

    def test_unsafe_methods_on_protected_paths_are_gated(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "post"):
            with self.subTest(method=method):
                self.assertIsNotNone(opauth.protected_action(method, "/api/a11oy/code/run"))

    def test_path_normalisation_cannot_slip_past(self):
        for path in ("/api/a11oy/code/run/", "//api/a11oy/code/run",
                     "/api//a11oy/code//run", "/api/a11oy/code/kernel/abc/exec/"):
            with self.subTest(path=path):
                self.assertIsNotNone(opauth.protected_action("POST", path))

    def test_near_misses_and_public_routes_are_not_gated(self):
        for path in ("/api/a11oy/code/runner", "/api/a11oy/code/chat/stream",
                     "/api/a11oy/v1/code/chat", "/api/a11oy/v1/agent/react/memory/search",
                     "/api/a11oy/v1/honest", "/mcp"):
            with self.subTest(path=path):
                self.assertIsNone(opauth.protected_action("POST", path))

    def test_constitution_reads_stay_public_and_writes_are_gated(self):
        for leaf in ("state", "ontology", "memory", "ledger"):
            path = f"/api/a11oy/v1/constitution/{leaf}"
            with self.subTest(path=path):
                self.assertIsNone(opauth.protected_action("GET", path))
                self.assertIsNotNone(opauth.protected_action("POST", path))


class GateMiddleware(unittest.TestCase):
    """The middleware answers before the downstream app is ever invoked."""

    def setUp(self):
        self.reached = []

        async def downstream(scope, receive, send):
            self.reached.append((scope["method"], scope["path"]))
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b"{}"})

        self.client = TestClient(opauth.OperatorGateMiddleware(downstream))

    def test_anonymous_wrong_and_empty_credentials_never_reach_the_handler(self):
        with patch.dict(os.environ, SECRETS):
            for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": "Bearer "},
                            {"Authorization": f"Basic {OPERATOR}"},
                            {opauth.SECOND_APPROVER_HEADER: APPROVER}):
                with self.subTest(headers=sorted(headers)):
                    r = self.client.post("/api/a11oy/code/run", headers=headers,
                                         json={"code": "print(1)"})
                    self.assertEqual(r.status_code, 401)
                    self.assertEqual(r.headers.get("www-authenticate"), "Bearer")
                    self.assertEqual(r.json()["status"], "BLOCKED")
                    self.assertNotIn(OPERATOR, r.text)
                    self.assertNotIn(APPROVER, r.text)
        self.assertEqual(self.reached, [])

    def test_unset_secret_denies_everyone(self):
        with patch.dict(os.environ, {opauth.OPERATOR_KEY_ENV: "",
                                     opauth.SECOND_APPROVER_KEY_ENV: ""}):
            for headers in ({}, {"Authorization": "Bearer "}, OPERATOR_ONLY):
                with self.subTest(headers=sorted(headers)):
                    r = self.client.post("/khipu/sign", headers=headers, json={})
                    self.assertEqual(r.status_code, 401)
                    self.assertFalse(r.json()["credential_configured"])
        self.assertEqual(self.reached, [])

    def test_operator_and_public_requests_pass_through(self):
        with patch.dict(os.environ, SECRETS):
            self.assertEqual(self.client.post("/api/a11oy/code/run", headers=OPERATOR_ONLY,
                                              json={}).status_code, 200)
            self.assertEqual(self.client.get("/api/a11oy/code/run").status_code, 200)
            self.assertEqual(self.client.post("/api/a11oy/v1/honest", json={}).status_code, 200)
        self.assertEqual(self.reached, [("POST", "/api/a11oy/code/run"),
                                        ("GET", "/api/a11oy/code/run"),
                                        ("POST", "/api/a11oy/v1/honest")])

    def test_install_is_idempotent_and_innermost(self):
        from starlette.middleware.cors import CORSMiddleware
        app = FastAPI()
        app.add_middleware(CORSMiddleware, allow_origins=["https://a-11-oy.com"])
        self.assertTrue(opauth.install_gate(app))
        self.assertFalse(opauth.install_gate(app))
        self.assertIs(app.user_middleware[-1].cls, opauth.OperatorGateMiddleware)
        self.assertEqual(
            sum(m.cls is opauth.OperatorGateMiddleware for m in app.user_middleware), 1)


# Write routes whose path looks side-effecting but which were reviewed and stay
# public: pure compute/verify/score, model-only answers without tools or
# persistence, or their own credential registry. A NEW route caught by the keyword
# net must be gated in PROTECTED_ROUTES or reviewed here; the test fails otherwise.
REVIEWED_PUBLIC_WRITE_ROUTES = {
    "/api/a11oy/v1/atelier/turn":
        "own gdw_auth credential registry (atelier:write); anonymous refusal tested in test_atelier_grok.py",
    "/api/a11oy/v1/atelier/local/turn":
        "own gdw_auth credential registry (atelier:write); anonymous refusal tested in test_atelier_grok_local.py",
    "/api/a11oy/v1/atelier/cpu-lab/turn":
        "own gdw_auth credential registry (atelier:write); anonymous refusal tested in test_atelier_grok_cpu_lab.py",
    "/api/a11oy/chaski/onboard/step": "session-scoped onboarding step (in-memory, per session id)",
    "/api/a11oy/code/chat/stream": "anonymous: model-only, tools disabled, never persisted",
    "/api/a11oy/v1/agent/cycle": "own credential registry (gdw_auth) + A11OY_OUROBOROS flag",
    "/api/a11oy/v1/agent/operate": "bounded model proposals over the brain; no tool dispatch",
    "/api/a11oy/v1/agent/react/memory/search": "read-only memory search",
    "/api/a11oy/v1/agent/run": "oversight simulation; no tool dispatch",
    "/api/a11oy/v1/agent/verify-chain": "verification of a caller-supplied chain",
    "/api/a11oy/v1/brain/agent/receipt": "read traversal + unsigned digest",
    "/api/a11oy/v1/brain/memory/receipt": "aggregate + unsigned digest; body ignored",
    "/api/a11oy/v1/brain/verdict/sign": "signs a server-computed verdict, not caller output",
    "/api/a11oy/v1/composer/run": "deterministic formula chain",
    "/api/a11oy/v1/dream/promote": "promotion always denied; compute only",
    "/api/a11oy/v1/edge/run": "deterministic demo",
    "/api/a11oy/v1/eval/run": "model-only eval over a fixed suite",
    "/api/a11oy/v1/gdw/step": "own credential registry (gdw_auth, step:write scope)",
    "/api/a11oy/v1/govern/agentos/snapshot": "aggregate + unsigned digest; body ignored",
    "/api/a11oy/v1/kverify/run": "bounded deterministic benchmark",
    "/api/a11oy/v1/loopforge/run": "bounded deterministic loop",
    "/api/a11oy/v1/memory/readiness/assess": "readiness assessment compute",
    "/api/a11oy/v1/numerics/run/{engine}":
        "three fixed numeric operations, no source accepted, network-isolated launcher",
    "/api/a11oy/v1/operator/ask": "read-only question over in-process state",
    "/api/a11oy/v1/ouroboros/run-all": "own credential registry (gdw_auth) + deployment flag",
    "/api/a11oy/v1/oversight/run": "deterministic oversight scenario",
    "/api/a11oy/v1/specdec/run": "bounded deterministic benchmark",
    "/api/a11oy/v1/trajectory/ingest": "stateless parse of the posted sample",
    "/api/a11oy/v1/warhacker/run/{problem}": "deterministic demo engine",
    "/api/a11oy/v1/warhacker/run/{problem}/{demo}": "deterministic demo engine",
    "/api/a11oy/v1/wh-demo/run/{problem}": "deterministic demo engine",
    "/api/a11oy/v4/agent/ask": "model-only voter fan-out; no tools",
    "/mcp": "JSON-RPC; sign_receipt is operator-only in the handler",
    "/mcp/": "JSON-RPC; sign_receipt is operator-only in the handler",
    "/v1/agent/run": "oversight simulation alias",
    "/v1/agent/verify-chain": "verification alias",
    "/v1/edge/run": "deterministic demo alias",
    "/v1/gdw/step": "own credential registry alias",
    "/v1/kverify/run": "benchmark alias",
    "/v1/oversight/run": "oversight alias",
    "/v1/specdec/run": "benchmark alias",
    "/v1/trajectory/ingest": "stateless parse alias",
    "/v1/warhacker/run/{problem}": "demo alias",
    "/v1/warhacker/run/{problem}/{demo}": "demo alias",
    "/v1/wh-demo/run/{problem}": "demo alias",
}

_SIDE_EFFECT_NET = (r"exec|/run\b|/run/|sign\b|inject|append|/write|operator|agent|mcp|/keys|"
                    r"ingest|record|/cap\b|start|stop|checkpoint|archive|command|chaos|promote|"
                    r"admit|memory|/act\b|bridge|stream|stt|turn|loop|step")


class ServeAppGate(unittest.TestCase):
    """The REAL application: every protected route refuses anonymous callers."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import serve
        from fastapi.routing import _IncludedRouter
        cls.serve = serve
        routes = []

        def walk(items, prefix=""):
            for r in items:
                if isinstance(r, _IncludedRouter):
                    walk(r.original_router.routes,
                         prefix + (getattr(r.include_context, "prefix", "") or ""))
                elif getattr(r, "methods", None):
                    routes.append((prefix + r.path, frozenset(r.methods)))

        walk(serve.app.routes)
        cls.write_routes = sorted({(p, m) for p, m in routes
                                   if m - {"GET", "HEAD", "OPTIONS"}},
                                  key=lambda item: (item[0], sorted(item[1])))
        cls.client = TestClient(serve.app)

    @staticmethod
    def _sample(path):
        import re
        return re.sub(r"\{[^}]+\}", "x", path)

    @staticmethod
    def _write_method(methods):
        return sorted(methods - {"GET", "HEAD", "OPTIONS"})[0]

    def setUp(self):
        self.env = patch.dict(os.environ, SECRETS)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def _protected_real_routes(self):
        out = []
        for path, methods in self.write_routes:
            method = self._write_method(methods)
            if opauth.protected_action(method, self._sample(path)):
                out.append((method, path))
        return out

    def test_gate_is_installed_innermost(self):
        self.assertIs(self.serve.app.user_middleware[-1].cls, opauth.OperatorGateMiddleware)

    def test_every_table_entry_matches_a_real_route(self):
        import re
        for pattern, action, _category in opauth.PROTECTED_ROUTES:
            rx = re.compile(r"\A" + pattern + r"\Z")
            with self.subTest(pattern=pattern):
                self.assertTrue(any(rx.match(self._sample(p)) for p, _m in self.write_routes),
                                f"{pattern} ({action}) matches no registered write route")

    def test_every_protected_route_refuses_anonymous_and_wrong_bearer(self):
        routes = self._protected_real_routes()
        self.assertGreaterEqual(len(routes), 60)
        for method, path in routes:
            for headers in ({}, {"Authorization": "Bearer wrong"}):
                with self.subTest(method=method, path=path, headers=sorted(headers)):
                    r = self.client.request(method, self._sample(path), headers=headers,
                                            json={"code": "import os; print(os.environ)",
                                                  "two_person_attested": True})
                    self.assertEqual(r.status_code, 401, r.text[:200])
                    self.assertEqual(r.json()["status"], "BLOCKED")

    def test_anonymous_never_reaches_execution_or_signing(self):
        import szl_dsse
        with patch.object(engine, "governed_turn") as turn, \
                patch.object(orchestrator, "run_code") as run_code, \
                patch.object(szl_dsse, "sign_payload") as sign:
            for path in ("/api/a11oy/code/run", "/api/a11oy/v1/code/run",
                         "/api/a11oy/v1/code/turn", "/api/a11oy/code/kernel/k1/exec",
                         "/khipu/sign", "/api/a11oy/khipu/sign"):
                with self.subTest(path=path):
                    r = self.client.post(path, json={"code": "print(1)", "prompt": "print(1)"})
                    self.assertEqual(r.status_code, 401)
        turn.assert_not_called()
        run_code.assert_not_called()
        sign.assert_not_called()

    def test_side_effect_routes_are_gated_or_reviewed(self):
        import re
        net = re.compile(_SIDE_EFFECT_NET)
        unreviewed = []
        for path, methods in self.write_routes:
            method = self._write_method(methods)
            if opauth.protected_action(method, self._sample(path)):
                continue
            if net.search(path) and path not in REVIEWED_PUBLIC_WRITE_ROUTES:
                unreviewed.append(f"{method} {path}")
        self.assertEqual(unreviewed, [], "gate these in PROTECTED_ROUTES or review them")

    def test_public_reads_still_work(self):
        for path in ("/api/a11oy/v1/honest", "/api/a11oy/v1/constitution/memory", "/mcp"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_operator_reaches_the_engine_but_only_two_person_executes(self):
        calls = []
        with patch.object(engine, "_sandbox_exec", _fake_sandbox(calls)), \
                patch.object(engine, "_model_configured", return_value=False):
            body = {"prompt": "write a python function that returns 5 primes"}
            r = self.client.post("/api/a11oy/v1/code/run", headers=OPERATOR_ONLY, json=body)
            self.assertEqual(r.status_code, 200, r.text[:300])
            self.assertFalse(r.json()["executed"])
            self.assertEqual(calls, [])
            r = self.client.post("/api/a11oy/v1/code/run", headers=BOTH, json=body)
            self.assertEqual(r.status_code, 200, r.text[:300])
            self.assertTrue(r.json()["executed"])
            self.assertEqual(len(calls), 1)
        r = self.client.post("/api/a11oy/v1/code/consensus", headers=OPERATOR_ONLY,
                             json={"prompt": "p"})
        self.assertEqual(r.status_code, 200)

    def test_mcp_sign_receipt_is_operator_only_and_reads_stay_open(self):
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "sign_receipt", "arguments": {"payload": {"forged": True}}}}
        r = self.client.post("/mcp", json=call)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["code"], -32001)
        r = self.client.post("/mcp", json=call, headers=OPERATOR_ONLY)
        self.assertEqual(r.status_code, 200)
        self.assertIn("result", r.json())
        listing = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 2,
                                                 "method": "tools/list"})
        self.assertEqual(listing.status_code, 200)
        policy = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "policy_check", "arguments": {}}})
        self.assertEqual(policy.status_code, 200)

    def test_refusal_keeps_cors_for_allowed_origin(self):
        r = self.client.post("/api/a11oy/code/run", headers={"Origin": "https://a-11-oy.com"},
                             json={})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.headers.get("access-control-allow-origin"), "https://a-11-oy.com")


if __name__ == "__main__":
    unittest.main()
