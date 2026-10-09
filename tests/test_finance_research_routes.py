#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the research audit's canonical and emitted HTTP boundaries."""
from copy import deepcopy
import importlib
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from .test_finance_release_boundaries import projection

routes = importlib.import_module('verticals.puriq-markets.runtime.routes')
transport = importlib.import_module('verticals.puriq-markets.runtime.transport')
REVISION = '1' * 40
PAYLOAD = {'as_of': '2024-12-31', 'records': [
    {'entity': 'A', 'period': 2023, 'value': 0, 'state': 'observed', 'available_at': '2024-01-01'},
    {'entity': 'B', 'period': 2023, 'value': 0, 'state': 'suppressed', 'available_at': '2024-01-01'}]}


@pytest.fixture
def canonical(monkeypatch):
    client = transport.FinanceClient(environ={'SZL_SOURCE_REVISION': REVISION},
        fetch=lambda plan: pytest.fail('audit attempted provider access'))
    monkeypatch.setattr(routes, 'CLIENT', client)
    app = FastAPI()
    routes.register(app)
    return TestClient(app), client


def test_canonical_audit_is_repeatable_bound_and_stateless(canonical):
    http, _ = canonical
    path = routes.PREFIX + '/research/audit'
    response = http.post(path, json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body == http.post(path, json=PAYLOAD).json()
    assert body['inputs'] == PAYLOAD
    assert body['inputs_sha256'] == transport.digest(PAYLOAD)
    assert body['result']['summary']['kept_records'] == 1
    assert body['result']['summary']['kept_zero_records'] == 1
    assert body['receipt']['payload_sha256'] == transport.digest({k:v for k,v in body.items() if k != 'receipt'})
    assert body['execution_enabled'] is False and body['receipt']['signed'] is False
    assert body['source_revision'] == REVISION
    assert response.headers['cache-control'] == 'private, no-store'
    assert http.get(path).status_code == 405
    assert http.post(path + '?execute=true', json=PAYLOAD).status_code == 422


@pytest.mark.parametrize('raw', [b'{"records":[],"records":[]}', b'{"value":NaN}',
    b'{"value":1e999}', b'{"value":1e-400}', b'\xff', b'[' * 2000, b' ' * 160001, b'null', b'[]'])
def test_canonical_rejects_malformed_or_oversized_json(canonical, raw):
    http, _ = canonical
    assert http.post(routes.PREFIX + '/research/audit', content=raw).status_code == 422


def test_unbound_audit_never_claims_source_identity(canonical):
    http, client = canonical
    client.environ.clear()
    response = http.post(routes.PREFIX + '/research/audit', json=PAYLOAD)
    assert response.status_code == 503 and response.json()['error'] == 'CANONICAL_SOURCE_UNBOUND'


def configure_projection(projection, monkeypatch):
    http, state = projection
    monkeypatch.setattr(routes, 'CLIENT', transport.FinanceClient(environ={'SZL_SOURCE_REVISION': REVISION}))
    state.update(body=routes.research_envelope(PAYLOAD), status=200)
    original = state['namespace']['httpx'].Client
    class Client(original):
        def stream(self, method, target, headers, content=None):
            assert method == 'POST' and json.loads(content) == PAYLOAD
            assert target.endswith('/api/a11oy/v1/finance/research/audit')
            assert not {'authorization', 'cookie', 'x-szl-finance-read-token'} & {k.lower() for k in headers}
            return super().stream('GET', target, headers)
    state['namespace']['httpx'] = SimpleNamespace(Client=Client)
    return http, state


def test_emitted_projection_preserves_audit_and_drops_caller_credentials(projection, monkeypatch):
    http, state = configure_projection(projection, monkeypatch)
    response = http.post('/api/finance/research/audit', json=PAYLOAD,
        headers={'Authorization': 'synthetic-secret', 'Cookie': 'fixture=value'})
    assert response.status_code == 200 and response.json() == state['body']
    state['calls'].clear()
    assert http.get('/api/finance/research/audit').status_code == 405
    assert http.post('/api/finance/research/audit?origin=fixture', json=PAYLOAD).status_code == 422
    assert http.post('/api/finance/research/audit', content=b' ' * 160001).status_code == 422
    assert not state['calls']


@pytest.mark.parametrize('change', ['revision','input','digest','signature','execution','schema'])
def test_projection_rejects_misbound_or_tampered_audit(projection, monkeypatch, change):
    http, state = configure_projection(projection, monkeypatch)
    body = deepcopy(state['body'])
    if change == 'revision': body['source_revision'] = '2' * 40
    elif change == 'input': body['inputs']['records'][0]['value'] = 999
    elif change == 'digest': body['receipt']['payload_sha256'] = '0' * 64
    elif change == 'signature': body['receipt']['signed'] = True
    elif change == 'execution': body['execution_enabled'] = True
    else: body['result']['schema'] = 'other'
    state['body'] = body
    response = http.post('/api/finance/research/audit', json=PAYLOAD)
    assert response.status_code == 503
    assert 'result' not in response.json()


@pytest.mark.parametrize('change', [
    'as_of', 'status', 'source_verified', 'dates_verified', 'source_url', 'input_label',
    'fitted', 'estimates_verified', 'estimate_label', 'estimates', 'threshold_kind',
    'summary_missing', 'summary_shape', 'count_boolean', 'negative_count', 'count_mismatch',
    'coverage_missing', 'coverage_shape', 'coverage_mismatch', 'cells_shape', 'cell_shape',
    'attrition_shape', 'group_shape', 'robustness_shape', 'issues_shape', 'flag_shape', 'records_shape',
])
def test_projection_rejects_rehashed_false_claims_and_invalid_nested_contract(projection, monkeypatch, change):
    http, state = configure_projection(projection, monkeypatch)
    body = deepcopy(state['body'])
    result = body['result']
    if change == 'as_of': result['as_of'] = '1900-01-01'
    elif change == 'status': result['status'] = 'BLOCKED'
    elif change == 'source_verified': result['inputs']['externally_verified'] = True
    elif change == 'dates_verified': result['inputs']['release_dates_verified'] = True
    elif change == 'source_url': result['inputs']['source_url'] = 'https://example.org/other'
    elif change == 'input_label': result['inputs']['truth_label'] = 'MEASURED'
    elif change == 'fitted': result['robustness']['computed'] = True
    elif change == 'estimates_verified': result['robustness']['externally_verified'] = True
    elif change == 'estimate_label': result['robustness']['truth_label'] = 'MEASURED'
    elif change == 'estimates': result['robustness']['specifications'] = [{'label': 'Invented', 'estimate': 1}]
    elif change == 'threshold_kind': result['robustness']['small_cluster_threshold_kind'] = 'VALIDITY_TEST'
    elif change == 'summary_missing': result.pop('summary')
    elif change == 'summary_shape': result['summary'] = []
    elif change == 'count_boolean': result['summary']['kept_records'] = True
    elif change == 'negative_count': result['summary']['kept_records'] = -1
    elif change == 'count_mismatch': result['summary']['kept_records'] = 2
    elif change == 'coverage_missing': result.pop('coverage')
    elif change == 'coverage_shape': result['coverage'] = []
    elif change == 'coverage_mismatch': result['coverage']['eligible_cells'] = 2
    elif change == 'cells_shape': result['coverage']['cells'] = {}
    elif change == 'cell_shape': result['coverage']['cells'] = [None]
    elif change == 'attrition_shape': result['attrition'] = []
    elif change == 'group_shape': result['attrition']['groups'] = [None]
    elif change == 'robustness_shape': result['robustness'] = []
    elif change == 'issues_shape': result['issues'] = {}
    elif change == 'flag_shape': result['robustness']['flags'] = [None]
    else: result['record_audit'] = []
    receipt = body['receipt']
    receipt['payload_sha256'] = transport.digest({k:v for k,v in body.items() if k != 'receipt'})
    receipt['receipt_sha256'] = transport.digest({k:v for k,v in receipt.items() if k != 'receipt_sha256'})
    state['body'] = body
    response = http.post('/api/finance/research/audit', json=PAYLOAD)
    assert response.status_code == 503
    assert response.json()['error'] == 'CANONICAL_SCHEMA_INVALID'
    assert 'result' not in response.json()


def test_nonzero_underflow_is_rejected_before_canonical_forwarding(projection, monkeypatch, canonical):
    http, state = configure_projection(projection, monkeypatch)
    raw = json.dumps(PAYLOAD).replace('"value": 0', '"value": 1e-400', 1).encode()
    canonical_http, _ = canonical
    assert canonical_http.post(routes.PREFIX + '/research/audit', content=raw).status_code == 422
    assert http.post('/api/finance/research/audit', content=raw).status_code == 422
    assert not state['calls']


@pytest.mark.parametrize('literal', ['0.0', '-0.000e300', '5e-324', '-1e308'])
def test_finite_numbers_and_real_zero_remain_accepted_by_projection_parser(projection, literal):
    _, state = projection
    parsed = state['namespace']['_finance_json'](literal)
    assert parsed == float(literal)
