# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline command-centre route, provenance and failure-boundary tests."""

from datetime import datetime, timedelta, timezone
import inspect
import hashlib
import json

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from routers import command_centre as centre


@pytest.fixture
def client():
    app = FastAPI()
    app.add_api_route('/a11oy/atelier', lambda: {'legacy': True})
    centre.register(app)
    return TestClient(app)


def snapshot(age=0):
    return {'observed_at': (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
            'counts': {'models': 49, 'datasets_public': 34, 'kernels': 14, 'spaces_public': 24}}


@pytest.mark.parametrize('path', ['/command-centre', '/a11oy/atelier'])
def test_owned_page_and_security_headers(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert 'Command centre' in response.text
    assert response.headers['cache-control'] == 'no-store, no-transform'
    assert "default-src 'none'" in response.headers['content-security-policy']
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert client.head(path).status_code == 200


def test_owned_page_states_provider_retention_boundary(client):
    page = client.get('/a11oy/atelier').text
    assert 'store: false' in page
    assert 'API audit retention is 30 days by default' in page
    assert 'No server-side conversation history is retained' not in page
    runbook = (centre.ROOT.parents[1] / 'docs' / 'ATELIER_COMMAND_CENTRE.md').read_text(encoding='utf-8')
    assert 'Provider storage is disabled' not in runbook
    assert 'x-zero-data-retention' in runbook


@pytest.mark.parametrize('path', ['/command-centre/app.js', '/command-centre/style.css',
                                 '/command-centre/szl/szl-design-system.css',
                                 '/command-centre/szl/szl-console.css'])
def test_owned_assets(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert len(response.content) > 100
    assert client.head(path).status_code == 200


def test_manifest_has_source_order_not_mutation_or_inference(client, monkeypatch):
    monkeypatch.setenv('SZL_GIT_SHA', 'a' * 40)
    data = client.get('/api/a11oy/v1/command-centre/manifest').json()
    assert data['source_revision'] == 'a' * 40
    assert data['read_only'] is True
    assert data['external_mutation_performed'] is False
    assert data['inference_verified'] is False
    assert data['authorities']['source'] == 'szl-holdings/a11oy'
    assert data['release_order'][0] == 'protected_github_source'
    assert data['release_order'][1] == 'canonical_hf_publication'
    assert len(data['surfaces']) == 17
    assert all(s['href'].startswith(('/', 'https://')) for s in data['surfaces'])
    assert any(s['href'] == '/command-v2' for s in data['surfaces'])


@pytest.mark.parametrize('sha', ['', 'main', 'a' * 39, 'A' * 40, '<script>'])
def test_unverified_revision_is_not_asserted(monkeypatch, sha):
    monkeypatch.setenv('SZL_GIT_SHA', sha)
    assert centre.manifest()['source_revision'] is None


def test_inventory_uses_fixed_bounded_public_transport(monkeypatch):
    calls = []
    def transport(url, **kwargs):
        calls.append((url, kwargs))
        return snapshot(), None
    monkeypatch.setattr(centre, 'http_json', transport)
    data = centre.proof_inventory()
    assert data['state'] == 'OBSERVED_SNAPSHOT'
    assert data['inference_verified'] is False
    assert calls == [(centre.PROOF_INVENTORY, {'timeout': 12, 'max_response_bytes': 1048576,
                                             'max_redirects': 0, 'allow_private': False})]


def test_stale_inventory_is_explicit(monkeypatch):
    monkeypatch.setattr(centre, 'http_json', lambda *a, **k: (snapshot(90000), None))
    assert centre.proof_inventory()['state'] == 'STALE_SNAPSHOT'


@pytest.mark.parametrize('value', [None, True, -1, 100001, '49', 1.5])
def test_invalid_count_fails_closed(monkeypatch, value):
    data = snapshot()
    data['counts']['models'] = value
    monkeypatch.setattr(centre, 'http_json', lambda *a, **k: (data, None))
    result = centre.proof_inventory()
    assert result['state'] == 'UNAVAILABLE'
    assert result['counts'] is None


@pytest.mark.parametrize('value', [None, 'garbage', '2026-09-29T00:00:00',
                                 (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()])
def test_invalid_observation_fails_closed(monkeypatch, value):
    data = snapshot()
    data['observed_at'] = value
    monkeypatch.setattr(centre, 'http_json', lambda *a, **k: (data, None))
    assert centre.proof_inventory()['code'] == 'PROOF_INVENTORY_INVALID_TIME'


def test_transport_errors_are_safe(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('SECRET provider body')
    monkeypatch.setattr(centre, 'http_json', broken)
    result = centre.proof_inventory()
    assert result['code'] == 'PROOF_INVENTORY_UNAVAILABLE'
    assert 'SECRET' not in str(result)


def test_get_does_not_call_provider_or_store_credentials():
    code = (centre.ROOT / 'app.js').read_text(encoding='utf-8')
    assert 'localStorage' not in code
    assert 'sessionStorage' not in code
    assert 'innerHTML' not in code
    assert 'textContent' in code
    assert 'reasoning_effort' in code
    assert 'window.confirm' in code
    assert "json('/api/a11oy/v1/atelier/local/health')" in code
    assert "json('/api/a11oy/v1/atelier/local/turn'" in code
    assert 'localStorage' not in code


def test_css_has_existing_design_system():
    page = (centre.ROOT / 'index.html').read_text(encoding='utf-8')
    assert '/command-centre/szl/szl-design-system.css' in page
    assert '/command-centre/szl/szl-console.css' in page


def test_bundled_study_is_pinned_not_performance_evidence(client):
    response = client.get('/api/a11oy/v1/command-centre/study')
    assert response.status_code == 200
    data = response.json()
    assert data['schema'] == 'szl.atelier.model-intake.v1'
    assert data['collection']['ranking_is_quality'] is False
    assert data['collection']['metadata_is_successful_inference'] is False
    assert data['collection']['model_weights_downloaded'] is False
    assert data['collection']['public_code_executed'] is False
    models = data['collection']['models']
    assert len(models) == len({item['id'] for item in models}) == 17
    assert all(len(item['revision']) == 40 for item in models)
    assert all(item['deployment_admitted'] is False for item in models)


def test_missing_study_is_unavailable(client, monkeypatch, tmp_path):
    monkeypatch.setattr(centre, 'STUDY', tmp_path / 'missing.json')
    response = client.get('/api/a11oy/v1/command-centre/study')
    assert response.status_code == 503
    assert response.json()['inference_verified'] is False


def test_owned_assets_emit_body_not_zero_copy_pathsend(client):
    response = client.get('/command-centre')
    assert '</html>' in response.text
    assert 'id="turn-form"' in response.text
    assert 'id="local-turn-form"' in response.text
    assert 'This is not Grok' in response.text
    assert 'id="study-models"' in response.text
    assert 'FileResponse(' not in inspect.getsource(centre)


def test_missing_page_is_unavailable(client, monkeypatch, tmp_path):
    monkeypatch.setattr(centre, 'ROOT', tmp_path)
    response = client.get('/command-centre')
    assert response.status_code == 503
    assert response.json()['code'] == 'ASSET_UNAVAILABLE'


def test_vendor_exception_is_byte_bound_not_application_exemption():
    provenance = json.loads((centre.ROOT / 'szl' / 'SOURCE.json').read_text(encoding='utf-8'))
    assert provenance['version'] == '1.1.0'
    assert provenance['source_commit'] == '168c53a0252b55243e3fa75fa5e3c743b8efb806'
    for name, digest in provenance['sha256'].items():
        assert hashlib.sha256((centre.ROOT / 'szl' / name).read_bytes()).hexdigest() == digest
    from scripts.check_banned_tokens import Allowlist
    allowlist = Allowlist.load(str(centre.ROOT.parents[1] / '.doctrine-allowlist'))
    assert allowlist.is_allowed('routers/command_centre_web/szl/szl-design-system.css')
    assert not allowlist.is_allowed('routers/command_centre_web/app.js')
    assert not allowlist.is_allowed('routers/command_centre_web/index.html')
