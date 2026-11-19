# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
'''Sovereign requests carry the CF Access pair for the declared model origin.

The energy operator probes a public origin behind Cloudflare Access and
private tailnet nodes through one code path. Anonymous requests to that
origin get a login redirect and the node reads falsely DEGRADED; the tailnet
nodes must not receive the credentials. Partial configuration fails closed.
'''
import httpx
import pytest

import szl_energy_operator as eo
from szl_model_access import (
    ACCESS_ID_ENV,
    ACCESS_ORIGIN_ENV,
    ACCESS_SECRET_ENV,
    ModelAccessConfigurationError,
)

ORIGIN = 'https://meter2.a-11-oy.com'
TAILNET = 'http://100.70.130.45:11434'


@pytest.fixture(autouse=True)
def _full_access(monkeypatch):
    monkeypatch.setenv(ACCESS_ORIGIN_ENV, ORIGIN)
    monkeypatch.setenv(ACCESS_ID_ENV, 'access-id.value')
    monkeypatch.setenv(ACCESS_SECRET_ENV, 'access-secret.value')
    monkeypatch.setenv('A11OY_GPU_TOKEN', 'gpu-token')


class _FakeResp:
    def raise_for_status(self):
        return None

    def json(self):
        return {'choices': [{'message': {'content': 'ok'}}],
                'usage': {'completion_tokens': 1}}


class _FakeClient:
    captured = {}

    def __init__(self, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        _FakeClient.captured = {'url': url, 'headers': dict(headers or {})}
        return _FakeResp()


def test_merge_helper_is_scoped_to_the_declared_origin():
    base = {'Authorization': 'Bearer gpu-token'}
    merged = eo._with_model_access_headers(base, ORIGIN + '/v1/models')
    assert merged['CF-Access-Client-Id'] == 'access-id.value'
    assert merged['CF-Access-Client-Secret'] == 'access-secret.value'
    assert merged['Authorization'] == 'Bearer gpu-token'
    assert eo._with_model_access_headers(base, TAILNET + '/v1') == base


def test_partial_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv(ACCESS_SECRET_ENV, raising=False)
    with pytest.raises(ModelAccessConfigurationError):
        eo._with_model_access_headers({'User-Agent': 'x'}, ORIGIN + '/v1')
    assert eo._http_reachable(ORIGIN + '/v1', timeout=0.1) is False


def test_ollama_generate_sends_access_pair_for_origin(monkeypatch):
    monkeypatch.setattr(httpx, 'Client', _FakeClient)
    tokens, text = eo._ollama_generate(ORIGIN + '/v1', 'llama3.1:8b', 'ping', timeout=1)
    assert (tokens, text) == (1, 'ok')
    assert _FakeClient.captured['url'] == ORIGIN + '/v1/chat/completions'
    assert _FakeClient.captured['headers']['CF-Access-Client-Id'] == 'access-id.value'
    assert _FakeClient.captured['headers']['Authorization'] == 'Bearer gpu-token'


def test_ollama_generate_sends_no_access_pair_for_tailnet(monkeypatch):
    monkeypatch.setattr(httpx, 'Client', _FakeClient)
    eo._ollama_generate(TAILNET + '/v1', 'llama3.1:8b', 'ping', timeout=1)
    assert 'CF-Access-Client-Id' not in _FakeClient.captured['headers']


def test_ollama_embed_sends_access_pair_for_origin(monkeypatch):
    monkeypatch.setattr(httpx, 'Client', _FakeClient)
    length, _ = eo._ollama_embed(ORIGIN + '/v1', 'bge-large', 'text', timeout=1)
    assert _FakeClient.captured['url'] == ORIGIN + '/api/embeddings'
    assert _FakeClient.captured['headers']['CF-Access-Client-Id'] == 'access-id.value'


def test_ollama_embed_sends_no_access_pair_for_tailnet(monkeypatch):
    monkeypatch.setattr(httpx, 'Client', _FakeClient)
    eo._ollama_embed(TAILNET + '/v1', 'bge-large', 'text', timeout=1)
    assert _FakeClient.captured['url'] == TAILNET + '/api/embeddings'
    assert 'CF-Access-Client-Id' not in _FakeClient.captured['headers']
