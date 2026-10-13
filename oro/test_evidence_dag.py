"""Negative-control tests for read-only ORO DAG projection."""
import hashlib
import unittest

from oro.brain_anatomy_contract import EvidenceHandle
from oro.evidence_dag import MAX_EDGES, MAX_ID_LENGTH, MAX_NODES, EvidenceNode, project_dag


def node(name, parents=(), status='UNVERIFIED', formula=None, classification='PUBLIC'):
    handle = EvidenceHandle('szl-second-brain', 'commit:' + 'a' * 40,
                            hashlib.sha256(name.encode()).hexdigest(), classification)
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
        a, b = node('a'), node('b')
        child = node('child', ('b', 'a'))
        expected = project_dag([child, b, a])
        self.assertEqual([row['node_id'] for row in expected['nodes']], ['a', 'b', 'child'])
        self.assertEqual(expected['nodes'][-1]['parents'], ['a', 'b'])
        self.assertEqual(expected, project_dag([a, node('child', ('a', 'b')), b]))

    def test_node_limit_stops_generator_after_one_extra_item(self):
        consumed = []

        def incoming():
            index = 0
            while True:
                consumed.append(index)
                yield node(f'n{index}')
                index += 1

        with self.assertRaisesRegex(ValueError, 'node limit'):
            project_dag(incoming())
        self.assertEqual(len(consumed), MAX_NODES + 1)

    def test_edge_limit_and_exact_boundary(self):
        roots = [node(f'r{index}') for index in range(8)]
        root_ids = tuple(root.node_id for root in roots)
        boundary = roots + [node(f'c{index}', root_ids) for index in range(MAX_EDGES // 8)]
        self.assertEqual(len(project_dag(boundary)['nodes']), len(boundary))
        with self.assertRaisesRegex(ValueError, 'edge limit'):
            project_dag(boundary + [node('overflow', root_ids)])

    def test_malformed_ids_and_duplicate_parents_refused(self):
        malformed = (
            ([node('')], 'node'),
            ([node(' '), node('root')], 'node'),
            ([node('x' * (MAX_ID_LENGTH + 1))], 'node'),
            ([node('child', ('',)), node('root')], 'parent'),
            ([node('child', (None,)), node('root')], 'parent'),
            ([node('child', ('x' * (MAX_ID_LENGTH + 1),))], 'parent'),
            ([node('child', ('root', 'root')), node('root')], 'Duplicate DAG parent'),
            ([node('child', 'root'), node('root')], 'parents'),
        )
        for rows, message in malformed:
            with self.subTest(rows=rows, message=message):
                with self.assertRaisesRegex(ValueError, message):
                    project_dag(rows)

    def test_deep_cycle_refused_without_recursive_walk(self):
        rows = [node(f'n{index}', (f'n{index - 1}',) if index else ())
                for index in range(MAX_NODES)]
        self.assertEqual(len(project_dag(reversed(rows))['nodes']), MAX_NODES)
        rows[0] = node('n0', (f'n{MAX_NODES - 1}',))
        with self.assertRaisesRegex(ValueError, 'cycle'):
            project_dag(rows)


if __name__ == '__main__':
    unittest.main()
