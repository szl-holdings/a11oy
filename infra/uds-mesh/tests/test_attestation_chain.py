"""
tests/test_attestation_chain.py — DSSE receipt chain tests for uds-mesh

Validates extended-attestations.jsonl: hash chain integrity, required fields,
SLSA predicate format, and chain ordering.

Run: pytest tests/test_attestation_chain.py -v
"""
import json
import os
import hashlib
import pytest

ATTESTATIONS_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'extended-attestations.jsonl'
)


@pytest.fixture(scope='module')
def attestations():
    records = []
    with open(ATTESTATIONS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ─── File-level tests (3 tests) ──────────────────────────────────────────────

class TestAttestationFile:
    def test_file_exists(self):
        assert os.path.isfile(ATTESTATIONS_FILE)

    def test_file_nonempty(self):
        assert os.path.getsize(ATTESTATIONS_FILE) > 0

    def test_at_least_one_record(self, attestations):
        assert len(attestations) >= 1


# ─── Record structure tests (8 tests) ────────────────────────────────────────

class TestRecordStructure:
    def test_first_record_has_v(self, attestations):
        assert 'v' in attestations[0]

    def test_first_record_version_1(self, attestations):
        assert attestations[0]['v'] == 1

    def test_all_records_have_ts(self, attestations):
        for r in attestations:
            assert 'ts' in r, f"Missing 'ts' in record: {r}"

    def test_all_records_have_subject(self, attestations):
        for r in attestations:
            assert 'subject' in r, f"Missing 'subject' in record: {r}"

    def test_all_records_have_predicate(self, attestations):
        for r in attestations:
            assert 'predicate' in r, f"Missing 'predicate' in record: {r}"

    def test_all_records_have_hash(self, attestations):
        for r in attestations:
            assert 'hash' in r, f"Missing 'hash' in record: {r}"

    def test_all_records_have_signer(self, attestations):
        for r in attestations:
            assert 'signer' in r, f"Missing 'signer' in record: {r}"

    def test_all_records_have_step(self, attestations):
        for r in attestations:
            assert 'step' in r, f"Missing 'step' in record: {r}"


# ─── Predicate / SLSA tests (4 tests) ────────────────────────────────────────

class TestSLSAPredicate:
    def test_predicate_is_slsa_provenance(self, attestations):
        for r in attestations:
            pred = r.get('predicate', '')
            assert 'slsa.dev' in pred or 'in-toto' in pred, \
                f"Non-SLSA predicate: {pred}"

    def test_predicate_v1_format(self, attestations):
        for r in attestations:
            pred = r.get('predicate', '')
            assert '/v1' in pred or '/v0' in pred, \
                f"Unexpected predicate version: {pred}"

    def test_signer_is_did(self, attestations):
        for r in attestations:
            signer = r.get('signer', '')
            assert signer.startswith('did:'), f"Non-DID signer: {signer}"

    def test_hash_is_hex_64(self, attestations):
        import re
        for r in attestations:
            h = r.get('hash', '')
            assert re.match(r'^[0-9a-f]{64}$', h), \
                f"Invalid hash format (expected 64-char hex): {h}"


# ─── Chain integrity tests (5 tests) ─────────────────────────────────────────

class TestChainIntegrity:
    def test_first_record_prev_is_null(self, attestations):
        assert attestations[0].get('prev') is None

    def test_each_prev_matches_prior_hash(self, attestations):
        """Each record's prev must equal the previous record's hash."""
        for i in range(1, len(attestations)):
            prev_hash = attestations[i - 1]['hash']
            curr_prev = attestations[i].get('prev')
            assert curr_prev == prev_hash, (
                f"Chain break at record {i}: "
                f"prev={curr_prev!r} != prior hash={prev_hash!r}"
            )

    def test_chain_is_ordered_by_ts(self, attestations):
        ts_list = [r['ts'] for r in attestations]
        assert ts_list == sorted(ts_list), "Attestation chain not ordered by timestamp"

    def test_no_duplicate_hashes(self, attestations):
        hashes = [r['hash'] for r in attestations]
        assert len(hashes) == len(set(hashes)), "Duplicate hashes detected in chain"

    def test_source_tree_record_present(self, attestations):
        steps = [r['step'] for r in attestations]
        assert 'source-tree-merkle' in steps, "Missing source-tree-merkle step"
