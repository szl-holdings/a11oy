"""Offline negative-control tests for the read-only ORO evidence bridge."""
import hashlib
import unittest

from oro.brain_anatomy_contract import (
    LOCKED_PROVEN, EvidenceHandle, evidence_projection, projection_digest,
)


class BrainAnatomyContractTests(unittest.TestCase):
    def setUp(self):
        self.handle = EvidenceHandle(
            'szl-second-brain', 'commit:' + 'a' * 40,
            hashlib.sha256(b'evidence').hexdigest(),
        )

    def test_locked_formula_stays_unverified_and_read_only(self):
        self.assertEqual(LOCKED_PROVEN, {'F1', 'F4', 'F7', 'F11', 'F12', 'F18', 'F19', 'F22'})
        value = evidence_projection(self.handle, formula='F1')
        self.assertEqual(value['proof_status'], 'UNVERIFIED')
        self.assertFalse(value['execution_authority'])
        self.assertFalse(value['promotion_authority'])
        self.assertEqual(len(projection_digest(value)), 64)

    def test_no_formula_can_self_attest_proven(self):
        for formula in ('F1', 'F2', None):
            with self.subTest(formula=formula), self.assertRaisesRegex(ValueError, 'cannot verify'):
                evidence_projection(self.handle, formula=formula, proof_status='PROVEN')

    def test_conjecture_not_promoted(self):
        value = evidence_projection(self.handle, formula='Lambda', proof_status='CONJECTURE')
        self.assertEqual(value['proof_status'], 'CONJECTURE')

    def test_formula_identifier_cannot_carry_content(self):
        with self.assertRaisesRegex(ValueError, 'formula identifier'):
            evidence_projection(self.handle, formula='secret value\nwith content')

    def test_restricted_evidence_refused(self):
        with self.assertRaises(PermissionError):
            evidence_projection(EvidenceHandle('private', self.handle.revision, self.handle.digest, 'PRIVATE'))

    def test_invalid_digest_refused(self):
        for digest in ('bad', 'A' * 64, 'a' * 63):
            with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'SHA-256'):
                evidence_projection(EvidenceHandle('source', self.handle.revision, digest))

    def test_immutable_sha256_revision_accepted(self):
        handle = EvidenceHandle('szl-holdings/a11oy/source.json',
                                'sha256:' + 'b' * 64, self.handle.digest)
        self.assertEqual(evidence_projection(handle)['revision'], handle.revision)

    def test_mutable_or_malformed_revisions_refused(self):
        for revision in ('', 'main', 'commit:abc123', 'commit:' + 'A' * 40,
                         'commit:' + 'a' * 39, 'sha256:' + 'b' * 63,
                         'sha256:' + 'B' * 64, 'sha256:' + 'b' * 40):
            with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, 'immutable'):
                evidence_projection(EvidenceHandle('source', revision, self.handle.digest))

    def test_unsafe_or_unbounded_sources_refused(self):
        for source in ('', '../private', '/absolute/path', 'folder//file',
                       'folder/./file', 'folder/../file', 'C:/Users/private',
                       'https://example.invalid/file', 'source\nsecret',
                       'source\ud800', 'x' * 257):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'source'):
                evidence_projection(EvidenceHandle(source, self.handle.revision, self.handle.digest))

    def test_stable_digest(self):
        a = evidence_projection(self.handle)
        self.assertEqual(projection_digest(a), projection_digest(dict(reversed(list(a.items())))))


if __name__ == '__main__':
    unittest.main()
