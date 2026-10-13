"""Negative-control tests for read-only ORO DAG projection."""
import hashlib
import unittest

from oro.brain_anatomy_contract import EvidenceHandle
from oro.evidence_dag import EvidenceNode, project_dag


def node(name, parents=(), status='UNVERIFIED', formula=None, classification='PUBLIC'):
    handle = EvidenceHandle('szl-second-brain', 'commit:immutable', hashlib.sha256(name.encode()).hexdigest(), classification)
    return EvidenceNode(name, handle, parents, formula, status)


class EvidenceDagTests(unittest.TestCase):
    def test_topological_order_and_read_only(self):
        result = project_dag([node('child', ('root',)), node('root')])
        self.assertEqual([n['node_id'] for n in result['nodes']], ['root', 'child'])
        self.assertFalse(result['execution_authority'])

    def test_cycle_refused(self):
        with self.assertRaisesRegex(ValueError, 'cycle'):
            project_dag([node('a', ('b',)), node('b', ('a',))])

    def test_missing_parent_refused(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            project_dag([node('a', ('missing',))])

    def test_duplicate_refused(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            project_dag([node('a'), node('a')])

    def test_unproved_formula_refused(self):
        with self.assertRaises(ValueError):
            project_dag([node('a', status='PROVEN', formula='F2')])

    def test_private_source_refused(self):
        with self.assertRaises(PermissionError):
            project_dag([node('a', classification='PRIVATE')])

    def test_deterministic(self):
        a, b = node('a'), node('b', ('a',))
        self.assertEqual(project_dag([a, b]), project_dag([b, a]))


if __name__ == '__main__':
    unittest.main()
