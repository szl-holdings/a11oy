# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local POST admission contracts without importing the production application.

Only the named route bodies are compiled from source. Their effect dependencies
are stubs; these tests prove admission/order, not model execution or deployment.
"""

import ast
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.responses import JSONResponse


ROOT = Path(__file__).resolve().parents[1]
NON_OBJECT_JSON = ("null", "true", "false", "0", "1.5", '"value"', "[]", "[{}]")
MALFORMED_JSON = ("", "{", "not-json")
CAPABILITY_ROUTES = {
    "_sc_cap_decide": "/api/a11oy/v1/policy/decide",
    "_sc_cap_compliance": "/api/a11oy/v1/policy/compliance",
    "_sc_cap_ask": "/api/a11oy/v1/operator/ask",
}


class FakeApp:
    def __init__(self):
        self.posts = {}

    def post(self, path):
        def register(handler):
            assert path not in self.posts
            self.posts[path] = handler
            return handler

        return register


class LocalRequest:
    def __init__(self, raw):
        self.raw = raw
        self.json_calls = 0

    async def json(self):
        self.json_calls += 1
        return json.loads(self.raw)


class ReadTrackedBundle(dict):
    def __init__(self, value):
        super().__init__(value)
        self.reads = []

    def __getitem__(self, key):
        self.reads.append(key)
        return super().__getitem__(key)


def compile_functions(path, names, namespace, *, enclosing=None):
    """Keep real handler bodies/decorators while excluding module side effects."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if enclosing is not None:
        parents = [node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == enclosing]
        assert len(parents) == 1
        tree = parents[0]
    nodes = []
    for name in names:
        found = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == name]
        assert len(found) == 1, (path.name, name, len(found))
        nodes.append(copy.deepcopy(found[0]))
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)


@pytest.fixture
def capability_handlers():
    app = FakeApp()
    verdict = Mock(return_value={"decision": "allow", "receipt_hash": "fixture-only"})
    answer = AsyncMock(return_value={"answer": "fixture-only", "status": "DECLARED"})
    envelope = Mock(side_effect=lambda body, **_kwargs: body)
    controls = {name: {"framework": name, "fixture_only": True}
                for name in ("NIST", "STIG", "ISO27001")}
    bundle = ReadTrackedBundle({"compliance": controls})
    namespace = {
        "app": app, "_SCRequest": LocalRequest, "_SCJSON": JSONResponse,
        "JSONResponse": JSONResponse,
        "_sc_build_verdict": verdict, "_sc_operator_answer": answer,
        "gov_envelope": envelope, "_SC_BUNDLE": bundle,
    }
    compile_functions(ROOT / "serve.py", ["_sc_body", "_sc_rejected", *CAPABILITY_ROUTES], namespace)
    assert set(app.posts) == set(CAPABILITY_ROUTES.values())
    return SimpleNamespace(app=app, namespace=namespace, verdict=verdict,
                           answer=answer, envelope=envelope, bundle=bundle)


@pytest.mark.parametrize("handler_name", CAPABILITY_ROUTES)
@pytest.mark.parametrize("raw", NON_OBJECT_JSON + MALFORMED_JSON)
def test_capability_rejects_invalid_body_before_effects(capability_handlers, handler_name, raw):
    harness = capability_handlers
    request = LocalRequest(raw)
    response = asyncio.run(harness.app.posts[CAPABILITY_ROUTES[handler_name]](request))
    expected = ("invalid JSON body" if raw in MALFORMED_JSON
                else "JSON body must be an object")
    assert response.status_code == 400
    assert json.loads(response.body) == {"error": expected}
    assert request.json_calls == 1
    harness.verdict.assert_not_called()
    harness.answer.assert_not_awaited()
    harness.envelope.assert_not_called()
    assert harness.bundle.reads == []


@pytest.mark.parametrize("body", [{}, {"action": {"value": "noop"}, "request_id": "local"}])
def test_policy_object_reaches_verdict_once_unchanged(capability_handlers, body):
    harness = capability_handlers
    response = asyncio.run(harness.namespace["_sc_cap_decide"](LocalRequest(json.dumps(body))))
    assert response.status_code == 200
    assert json.loads(response.body) == harness.verdict.return_value
    harness.verdict.assert_called_once_with(body)
    harness.answer.assert_not_awaited()


@pytest.mark.parametrize("body,expected", [({}, ""), ({"question": "which formulas?"}, "which formulas?")])
def test_question_object_keeps_existing_default_and_payload(capability_handlers, body, expected):
    harness = capability_handlers
    response = asyncio.run(harness.namespace["_sc_cap_ask"](LocalRequest(json.dumps(body))))
    assert response.status_code == 200
    assert json.loads(response.body) == harness.answer.return_value
    harness.answer.assert_awaited_once_with(expected)
    harness.verdict.assert_not_called()


@pytest.mark.parametrize("body,expected", [({}, "NIST"), ({"framework": "STIG"}, "STIG"),
                                            ({"framework": "iso-27001"}, "ISO27001")])
def test_compliance_object_keeps_framework_selection(capability_handlers, body, expected):
    harness = capability_handlers
    response = asyncio.run(harness.namespace["_sc_cap_compliance"](LocalRequest(json.dumps(body))))
    assert response.status_code == 200
    assert json.loads(response.body) == {"framework": expected, "fixture_only": True}
    assert harness.bundle.reads == ["compliance"]
    harness.verdict.assert_not_called()
    harness.answer.assert_not_awaited()


@pytest.fixture
def agentloop_handler():
    refused = Mock(return_value=None)
    tenant = Mock(return_value=None)
    run = Mock(return_value={"ok": False, "status_code": 200, "label": "UNAVAILABLE"})
    allowed = Mock(return_value=False)
    sign = Mock(side_effect=AssertionError("admission test must not sign"))
    namespace = {
        "JSONResponse": JSONResponse, "_refused": refused, "_tenant_refusal": tenant, "run_loop": run,
        "_exec_permitted": allowed, "sign_fn": sign, "ns": "a11oy",
        "_BRAINFEED_OK": False, "_CONJECTURE_NOTE": "Conjecture 1 remains open",
    }
    compile_functions(ROOT / "szl_agent_loop_governed.py", ["_run"], namespace,
                      enclosing="register")
    return SimpleNamespace(handler=namespace["_run"], refused=refused, tenant=tenant, run=run,
                           allowed=allowed, sign=sign)


@pytest.mark.parametrize("raw", NON_OBJECT_JSON + MALFORMED_JSON)
def test_agentloop_invalid_body_cannot_run_or_sign(agentloop_handler, raw):
    harness = agentloop_handler
    request = LocalRequest(raw)
    response = asyncio.run(harness.handler(request))
    expected = ("task is required" if raw in MALFORMED_JSON
                else "request body must be an object")
    assert response.status_code == 400
    assert json.loads(response.body)["error"] == expected
    harness.refused.assert_called_once_with(request, "Governed agent loop")
    harness.tenant.assert_called_once_with(request)
    assert request.json_calls == 1
    harness.run.assert_not_called()
    harness.allowed.assert_not_called()
    harness.sign.assert_not_called()


@pytest.mark.parametrize("raw", NON_OBJECT_JSON + MALFORMED_JSON + ('{"task":"local"}',))
def test_agentloop_authorization_refusal_still_precedes_parsing(agentloop_handler, raw):
    harness = agentloop_handler
    refusal = JSONResponse({"status": "BLOCKED"}, status_code=401)
    harness.refused.return_value = refusal
    request = LocalRequest(raw)
    response = asyncio.run(harness.handler(request))
    assert response is refusal
    assert request.json_calls == 0
    harness.refused.assert_called_once_with(request, "Governed agent loop")
    harness.tenant.assert_not_called()
    harness.run.assert_not_called()
    harness.allowed.assert_not_called()
    harness.sign.assert_not_called()


@pytest.mark.parametrize("status", [403, 503])
@pytest.mark.parametrize("raw", NON_OBJECT_JSON + MALFORMED_JSON + ('{"task":"local"}',))
def test_agentloop_tenant_refusal_precedes_parsing_and_effects(agentloop_handler, raw, status):
    harness = agentloop_handler
    refusal = JSONResponse({"status": "BLOCKED"}, status_code=status)
    harness.tenant.return_value = refusal
    request = LocalRequest(raw)
    assert asyncio.run(harness.handler(request)) is refusal
    harness.refused.assert_called_once_with(request, "Governed agent loop")
    harness.tenant.assert_called_once_with(request)
    assert request.json_calls == 0
    harness.run.assert_not_called()
    harness.allowed.assert_not_called()
    harness.sign.assert_not_called()


def test_agentloop_valid_object_preserves_explicit_local_options(agentloop_handler):
    harness = agentloop_handler
    body = {"task": "Describe the local boundary", "mode": "chat",
            "model_id": "local-unavailable-model", "max_retries": 0,
            "sandbox": False, "consult_brain": False, "allocate_energy": False}
    request = LocalRequest(json.dumps(body))
    response = asyncio.run(harness.handler(request))
    assert response.status_code == 200
    assert json.loads(response.body) == harness.run.return_value
    harness.run.assert_called_once_with(
        body["task"], harness.sign, ns="a11oy", mode="chat",
        model_id=body["model_id"], harness_profile_id="", eval_suite="",
        approval=None, max_retries=0, sandbox=False,
        consult_brain=False, allocate_energy=False, allow_exec=False)
    harness.allowed.assert_called_once_with(request)
    harness.sign.assert_not_called()


def test_agentloop_empty_object_remains_missing_task_refusal(agentloop_handler):
    harness = agentloop_handler
    response = asyncio.run(harness.handler(LocalRequest("{}")))
    assert response.status_code == 400
    assert json.loads(response.body)["error"] == "task is required"
    harness.run.assert_not_called()
    harness.sign.assert_not_called()
