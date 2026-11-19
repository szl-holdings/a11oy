# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
'''model_access_headers_for_origin: scoped to the declared origin, fail closed.

Multi-node callers probe one declared public origin (Cloudflare Access) and
private tailnet nodes through one code path: the pair must be sent only for
the declared origin, and a partial configuration must never produce an
anonymous request to a possibly-Access-gated origin.
'''
import pytest

from szl_model_access import (
    ACCESS_ID_ENV,
    ACCESS_ORIGIN_ENV,
    ACCESS_SECRET_ENV,
    ModelAccessConfigurationError,
    model_access_headers_for_origin,
)

ORIGIN = 'https://meter2.a-11-oy.com'


@pytest.fixture
def full_config(monkeypatch):
    monkeypatch.setenv(ACCESS_ORIGIN_ENV, ORIGIN)
    monkeypatch.setenv(ACCESS_ID_ENV, 'access-id.value')
    monkeypatch.setenv(ACCESS_SECRET_ENV, 'access-secret.value')


def test_all_absent_preserves_legacy_behavior(monkeypatch):
    for name in (ACCESS_ORIGIN_ENV, ACCESS_ID_ENV, ACCESS_SECRET_ENV):
        monkeypatch.delenv(name, raising=False)
    assert model_access_headers_for_origin('https://example.com/v1') == {}


def test_matching_origin_returns_pair(full_config):
    pair = model_access_headers_for_origin(ORIGIN + '/v1/chat/completions')
    assert pair == {'CF-Access-Client-Id': 'access-id.value',
                    'CF-Access-Client-Secret': 'access-secret.value'}


def test_other_origin_gets_no_credentials(full_config):
    assert model_access_headers_for_origin('https://elsewhere.example/v1') == {}
    assert model_access_headers_for_origin('http://100.70.130.45:11434/v1') == {}
    assert model_access_headers_for_origin('http://127.0.0.1:4000/v1') == {}


def test_port_80_https_mismatch_is_not_the_origin(full_config):
    assert model_access_headers_for_origin('http://meter2.a-11-oy.com') == {}


def test_partial_configuration_fails_closed_whatever_the_url(monkeypatch):
    monkeypatch.setenv(ACCESS_ORIGIN_ENV, ORIGIN)
    monkeypatch.delenv(ACCESS_ID_ENV, raising=False)
    monkeypatch.delenv(ACCESS_SECRET_ENV, raising=False)
    with pytest.raises(ModelAccessConfigurationError):
        model_access_headers_for_origin(ORIGIN + '/v1')
    with pytest.raises(ModelAccessConfigurationError):
        model_access_headers_for_origin('http://100.70.130.45:11434')


def test_invalid_origin_env_fails_closed(monkeypatch):
    monkeypatch.setenv(ACCESS_ORIGIN_ENV, 'http://meter2.a-11-oy.com')
    monkeypatch.setenv(ACCESS_ID_ENV, 'access-id.value')
    monkeypatch.setenv(ACCESS_SECRET_ENV, 'access-secret.value')
    with pytest.raises(ModelAccessConfigurationError):
        model_access_headers_for_origin(ORIGIN + '/v1')
