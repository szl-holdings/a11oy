# SPDX-License-Identifier: Apache-2.0
"""Front/backend boundary regressions. Synthetic data; no provider writes."""
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from test_finance_release_boundaries import projection

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1" * 40
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")


def module(name):
    spec = importlib.util.spec_from_file_location('workspace_' + name, ROOT/'scripts'/(name+'.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def overview():
    bodies = {'polymarket-markets': b'[]', 'kalshi-markets': b'{"markets":[]}',
              'coinbase-ticker': b'{"price":"100","bid":"99","ask":"101"}',
              'treasury-rates': b'{"data":[]}'}
    client = transport.FinanceClient(fetch=lambda p: bodies[p.source],
        environ={'SZL_GIT_SHA': REVISION}, clock=lambda: 1800000000)
    children = {key: client.observe(key) for key in bodies}
    assert all(child['ok'] for child in children.values())
    return {'schema':'szl.finance.overview/v1','source_revision':REVISION,
        'execution_enabled':False,'ok':True,'state':'SNAPSHOTS_AVAILABLE','data':children,
        'sources_requested':4,'sources_available':4,'event_equivalence':'NOT_ESTABLISHED'}


def test_landing_reader_uses_validated_finance_transport(projection):
    http, state = projection
    state.update(body=overview(), status=200)
    result = http.get('/api/live', headers={'Authorization':'INERT_CALLER_SECRET','Cookie':'inert=fixture'})
    assert result.status_code == 200
    body = result.json()
    assert body['status'] == 'SNAPSHOT' and body['status'] != 'LIVE'
    assert body['live_provider_verified'] is False and body['execution_enabled'] is False
    assert body['data'] == state['body']
    assert result.headers['cache-control'] == 'private, no-store'
    assert state['calls'][0][0] == 'https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/overview'
    assert not {'authorization','cookie'} & {key.lower() for key in state['calls'][0][1]}


@pytest.mark.parametrize('change', ['revision','nested_revision','schema','execution','coverage','truth','digest'])
def test_landing_path_returns_503_for_validated_refusals(projection, change):
    http, state = projection
    body = overview()
    if change == 'revision': body['source_revision'] = '2'*40
    elif change == 'nested_revision': body['data']['coinbase-ticker']['source_revision'] = '2'*40
    elif change == 'schema': body['schema'] = 'fake'
    elif change == 'execution': body['execution_enabled'] = True
    elif change == 'coverage': body['sources_requested'] = 3
    elif change == 'truth': body['data']['coinbase-ticker']['truth_label'] = 'MEASURED'
    else: body['data']['coinbase-ticker']['data']['price'] = '999'
    state.update(body=body, status=200)
    response = http.get('/api/live')
    assert response.status_code == 503
    result = response.json()
    assert result['status'] == 'UNAVAILABLE' and 'data' not in result['data']
    assert result['execution_enabled'] is False


def test_partial_overview_stays_unavailable_not_http_success(projection):
    http, state = projection
    body = overview()
    client = transport.FinanceClient(environ={'SZL_GIT_SHA':REVISION})
    body['data']['coinbase-ticker'] = client._unavailable('coinbase-ticker',1800000000,'UPSTREAM_HTTP_503')
    body.update(ok=False,state='DEGRADED',sources_available=3)
    state.update(body=body,status=200)
    response = http.get('/api/live')
    assert response.status_code == 503 and response.json()['status'] == 'UNAVAILABLE'
    assert response.json()['data']['sources_available'] == 3


@pytest.mark.parametrize('status', [302,403,404,422,500,503])
def test_landing_transport_failures_are_not_live(projection,status):
    http, state = projection
    state.update(status=status,body={'error':'INERT_SENSITIVE_UPSTREAM_TEXT'})
    result = http.get('/api/live')
    assert result.status_code == 503 and 'INERT_SENSITIVE' not in result.text


def test_finance_research_route_is_existing_page_not_a_second_app(projection):
    http,state=projection
    assert http.get('/research').content == http.get('/').content
    assert http.post('/research').status_code == 405
    assert state['calls'] == []


def test_workspace_changes_only_finance_and_has_no_side_effects():
    workspace=module('hf_finance_workspace')
    base=module('_hf_publish_vertical_flagships_v4_impl_base')
    previous_html=deepcopy(base.DOMAIN_HTML);previous_css=deepcopy(base.DOMAIN_CSS)
    with patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN')):
        workspace.apply_workspace(base)
    for slug in previous_html.keys()-{'finance'}:
        assert base.DOMAIN_HTML[slug] == previous_html[slug]
        assert base.DOMAIN_CSS[slug] == previous_css[slug]
    assert base.DOMAIN_HTML['finance'] == workspace.HTML
    assert base.DOMAIN_CSS['finance'] == previous_css['finance'] + workspace.CSS


def test_workspace_contract_rejects_unsupported_renderer_without_mutation():
    workspace=module('hf_finance_workspace')
    candidate=SimpleNamespace(DOMAIN_HTML={'finance':'old'},DOMAIN_CSS=None)
    with pytest.raises(TypeError):workspace.apply_workspace(candidate)
    assert candidate.DOMAIN_HTML=={'finance':'old'}


def test_workbench_retains_text_only_rendering_and_no_credential_storage():
    code=module('hf_finance_workspace').SCRIPT
    for forbidden in ('innerHTML','outerHTML','insertAdjacentHTML','localStorage','sessionStorage','eval(','new Function','Bearer '):
        assert forbidden not in code
    assert "credentials:'omit'" in code and "redirect:'error'" in code
    assert "method:'GET'" in code and '4000000' in code
    assert 'AbortController' in code and 'generation!==queryEpoch' in code
    assert 'body.execution_enabled===false' in code


def test_actual_publisher_workbench_is_in_landing_artifact_identity():
    renderer=module('hf_publish_vertical_flagships_v4_impl')
    emit=module('materialize_finance_runtime')
    files=emit.payloads(renderer,REVISION,1)
    config=json.loads(files['config.json'])
    assert b'data-szl-finance-workspace="1"' in files['index.html']
    assert b'id="fin-source"' in files['panels.html']
    assert config['landing_sha256']==hashlib.sha256(files['index.html']).hexdigest()
    assert config['panels_sha256']==hashlib.sha256(files['panels.html']).hexdigest()


def test_current_finance_source_ids_are_exactly_represented():
    import re
    sources=importlib.import_module('verticals.puriq-markets.runtime.sources').SOURCES
    code=module('hf_finance_workspace').SCRIPT
    represented=set(re.findall(r"'([a-z]+-[a-z-]+)'\s*:\s*\{",code))
    assert represented==set(sources)
    assert {key for key,spec in sources.items() if spec['private']}=={'fred-series','alpaca-quote','alpaca-bars'}
