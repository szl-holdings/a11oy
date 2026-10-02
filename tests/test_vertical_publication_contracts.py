"""Publication probes must use the admitted Python runtime's current contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

frontier = load('frontier_probe', 'scripts/hf_publish_vertical_services_frontier_v3.py')
intelligence = load('intelligence_probe', 'scripts/hf_publish_vertical_services_intelligence_v4.py')

def test_hatun_requests_the_observed_payload_digest_and_never_a_receipt_handle():
    payload = frontier.hatun_review_payload({'state': 'OBSERVED', 'vertical': 'finance',
        'connector_id': 'polymarket-markets', 'payload_sha256': 'a' * 64, 'receipt_id': 'b' * 64})
    assert payload['evidence_sha256'] == ['a' * 64]
    assert 'evidence_refs' not in payload
    assert 'b' * 64 not in str(payload)

@pytest.mark.parametrize('bad', [None, {}, {'receipt_id': 'a' * 64},
    {'state': 'OBSERVED', 'payload_sha256': 'short'},
    {'state': 'UNAVAILABLE', 'vertical': 'finance', 'connector_id': 'polymarket-markets', 'payload_sha256': 'a' * 64},
    {'state': 'OBSERVED', 'vertical': 'terra', 'connector_id': 'polymarket-markets', 'payload_sha256': 'a' * 64},
    {'state': 'OBSERVED', 'vertical': 'finance', 'connector_id': 'coinbase-spot', 'payload_sha256': 'a' * 64},
    {'state': 'OBSERVED', 'vertical': 'finance', 'connector_id': 'polymarket-markets', 'payload_sha256': 'A' * 64}])
def test_missing_or_wrongly_scoped_payload_never_becomes_fabricated_evidence(bad):
    payload = frontier.hatun_review_payload(bad)
    assert payload['evidence_sha256'] == []
    assert 'evidence_refs' not in payload

CORE = {
    'khipu-1.5b': 'SZLHOLDINGS/SZL-Khipu-1.5B',
    'receipt-agent': 'SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2',
    'a11oy-mini': 'SZLHOLDINGS/A11OY-MINI',
}
PUBLIC = {'alias': 'khipu-gguf-public', 'repo_id': 'SZLHOLDINGS/SZL-Khipu-1.5B-GGUF', 'credential_value_exposed': False}

def core_rows():
    return [{'alias': alias, 'repo_id': repo, 'credential_value_exposed': False} for alias, repo in CORE.items()]

def test_the_current_finance_profile_requires_its_four_exact_source_owned_models():
    assert intelligence.MODEL_ASSETS.get(PUBLIC['alias']) == PUBLIC['repo_id']
    assert intelligence.profile_models_match('finance', core_rows() + [PUBLIC])
    assert not intelligence.profile_models_match('finance', core_rows())
    for vertical in ('sentra', 'lyte', 'killinchu', 'terra', 'counsel'):
        assert intelligence.profile_models_match(vertical, core_rows())
        assert not intelligence.profile_models_match(vertical, core_rows() + [PUBLIC])

@pytest.mark.parametrize('rows', [None, [], [PUBLIC] * 4, core_rows() + [dict(PUBLIC, repo_id='OTHER/unreviewed')],
    core_rows() + [dict(PUBLIC, credential_value_exposed=True)],
    core_rows() + [dict(PUBLIC, alias='unknown')], core_rows() + [dict(PUBLIC, alias=[])],
    core_rows() + [PUBLIC, PUBLIC]])
def test_added_profile_support_does_not_admit_duplicates_unknown_assets_or_credentials(rows):
    assert not intelligence.profile_models_match('finance', rows)
