#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Execute the exact repository serve route/helper/table source, not stand-in responses."""
import ast
import asyncio
import base64
import collections
import copy
import datetime
import hashlib
import json
import secrets
import threading
from pathlib import Path
from fastapi import Request
from starlette.responses import JSONResponse
from tests.test_observer_adapters import world, CREDS, execute_all
from tools import execution_acceptance as a
import observer_adapters as adapters


def install_actual_deterministic_routes(world):
    source = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(source.read_text())
    names = {'_gov_now_iso', 'gov_envelope', '_sc_run_inspection', '_sc_compute_lambda', '_sc_build_verdict',
        '_sc_log_verdict', '_sc_now', '_sc_sha', '_sc_receipt', '_sc_classify', '_sc_ask',
        '_sc_operator_answer', '_sc_body', '_sc_rejected', '_sc_cap_feed', '_sc_cap_decide',
        '_sc_cap_compliance', '_sc_cap_ask'}
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node = copy.deepcopy(node)
            node.decorator_list = []
            functions.append(node)
    assert len(functions) == len(names)
    assignments = {target.id: node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)}
    raw = next(node.value for node in ast.walk(assignments['_SC_BUNDLE'])
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 100)
    namespace = {'_sc_json': json, '_sc_hashlib': hashlib, '_sc_datetime': datetime,
        '_sc_secrets': secrets, '_SCRequest': Request, '_SCJSON': JSONResponse,
        'JSONResponse': JSONResponse,
        '_SC_AUDIT_LOCK': threading.Lock(), '_SC_AUDIT': collections.deque(maxlen=200),
        '_SC_BUNDLE': json.loads(base64.b64decode(raw))}
    for name in ('_SC_THREAT_SIGNATURES', '_SC_LAMBDA_GATE_FLOOR', '_SC_PROVED_FORMULAS'):
        namespace[name] = ast.literal_eval(assignments[name])
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    paths = {a.CONTRACTS[name] for name in ('policy-decide', 'policy-compliance', 'operator-ask')} | {adapters.FEED}
    world.app.router.routes[:] = [route for route in world.app.router.routes if getattr(route, 'path', '') not in paths]
    for case in world.plan['cases'][:3]:
        world.app.add_api_route(case['path'], namespace[adapters.ENDPOINTS[case['id']]], methods=['POST'])
    world.app.add_api_route(adapters.FEED, namespace['_sc_cap_feed'], methods=['GET'])
    return namespace


def test_all_five_captures_include_actual_serve_deterministic_sources(world):
    namespace = install_actual_deterministic_routes(world)
    observed = execute_all(world)
    assert len(observed) == 5 and len(world.calls) == 3
    assert len(namespace['_SC_AUDIT']) == 1
    policy = a.strict_json(observed['policy-decide'].response_bytes)
    assert policy['decision'] == 'allow' and policy['lambda_value'] == 1.0
    compliance = a.strict_json(observed['policy-compliance'].readback_bytes)
    assert len(compliance['record']['controls']) == 8
    operator = a.strict_json(observed['operator-ask'].response_bytes)
    assert operator['citations'][0]['endpoint'] == 'serve._SC_PROVED_FORMULAS'
    assert operator['receipt']['signed'] is False
    for case in world.plan['cases']:
        capture = observed[case['id']]
        adapters.validate_native_observation(case, capture.response_status, capture.response_bytes,
            capture.readback_bytes, world.pem, world.key_id)
