"""Offline negative-control tests for the read-only ORO evidence bridge."""
import hashlib
import unittest

from oro.brain_anatomy_contract import EvidenceHandle, evidence_projection, projection_digest


class BrainAnatomyContractTests(unittest.TestCase):
    def setUp(self):
        self.handle = EvidenceHandle('szl-second-brain', 'commit:abc123', hashlib.sha256(b'evidence').hexdigest())

    def test_locked_proof_is_read_only(self):
        value = evidence_projection(self.handle, formula='F1', proof_status='PROVEN')
        self.assertFalse(value['execution_authority'])
        self.assertFalse(value['promotion_authority'])
        self.assertEqual(len(projection_digest(value)), 64)

    def test_unlocked_proof_cannot_promote(self):
        with self.assertRaises(ValueError):
            evidence_projection(self.handle, formula='F2', proof_status='PROVEN')

    def test_conjecture_not_promoted(self):
        value = evidence_projection(self.handle, formula='Lambda', proof_status='CONJECTURE')
        self.assertEqual(value['proof_status'], 'CONJECTURE')

    def test_restricted_evidence_refused(self):
        with self.assertRaises(PermissionError):
            evidence_projection(EvidenceHandle('private', 'sha', self.handle.digest, 'PRIVATE'))

    def test_invalid_digest_refused(self):
        with self.assertRaises(ValueError):
            evidence_projection(EvidenceHandle('source', 'revision', 'bad'))

    def test_stable_digest(self):
        a = evidence_projection(self.handle)
        self.assertEqual(projection_digest(a), projection_digest(dict(reversed(list(a.items())))))


if __name__ == '__main__':
    unittest.main()
