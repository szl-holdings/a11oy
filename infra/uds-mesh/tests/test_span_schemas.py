"""
tests/test_span_schemas.py — Span schema validation tests for uds-mesh

Tests the a11oy.graph.* OTEL span schema (schemas/spans/a11oy.graph.yaml).
Uses text-based assertions since the file is a custom YAML dialect (not
standard YAML-parse-able). All assertions are grep-able from real files.

Run: pytest tests/test_span_schemas.py -v
"""
import os
import re
import pytest

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), '..', 'schemas', 'spans', 'a11oy.graph.yaml')


@pytest.fixture(scope='module')
def schema_text():
    with open(SCHEMA_FILE) as f:
        return f.read()


# ─── File-level tests (4 tests) ──────────────────────────────────────────────

class TestSchemaFile:
    def test_schema_file_exists(self):
        assert os.path.isfile(SCHEMA_FILE), f"Schema file not found: {SCHEMA_FILE}"

    def test_schema_file_nonempty(self):
        assert os.path.getsize(SCHEMA_FILE) > 500

    def test_schema_has_version_field(self, schema_text):
        assert 'version:' in schema_text

    def test_schema_has_schema_url(self, schema_text):
        assert 'schema_url:' in schema_text


# ─── Span name tests (8 tests) ───────────────────────────────────────────────

class TestSpanNames:
    def test_span_lambda_defined(self, schema_text):
        assert 'a11oy.graph.lambda' in schema_text

    def test_span_automorphism_defined(self, schema_text):
        assert 'a11oy.graph.automorphism' in schema_text

    def test_span_position_defined(self, schema_text):
        assert 'a11oy.graph.position' in schema_text

    def test_span_gcpn_propose_defined(self, schema_text):
        assert 'a11oy.graph.gcpn_propose' in schema_text

    def test_all_four_spans_present(self, schema_text):
        spans = ['a11oy.graph.lambda', 'a11oy.graph.automorphism',
                 'a11oy.graph.position', 'a11oy.graph.gcpn_propose']
        for span in spans:
            assert span in schema_text, f"Span '{span}' not defined in schema"

    def test_spans_section_present(self, schema_text):
        assert 'spans:' in schema_text or 'span_definitions:' in schema_text or \
               'a11oy.graph.lambda' in schema_text

    def test_example_lambda_present(self, schema_text):
        assert 'span: a11oy.graph.lambda' in schema_text

    def test_example_automorphism_present(self, schema_text):
        assert 'span: a11oy.graph.automorphism' in schema_text


# ─── Required attribute tests (8 tests) ──────────────────────────────────────

class TestRequiredAttributes:
    def test_attr_lambda_value(self, schema_text):
        assert 'szl.graph.lambda_value' in schema_text

    def test_attr_v_count(self, schema_text):
        assert 'szl.graph.v_count' in schema_text

    def test_attr_e_count(self, schema_text):
        assert 'szl.graph.e_count' in schema_text

    def test_attr_receipt_hash(self, schema_text):
        assert 'szl.graph.receipt_hash' in schema_text

    def test_attr_governance_drift(self, schema_text):
        assert 'szl.graph.governance_drift' in schema_text

    def test_json_schema_section_present(self, schema_text):
        assert 'json_schema' in schema_text

    def test_required_field_present(self, schema_text):
        assert 'required' in schema_text

    def test_szl_graph_prefix_used_consistently(self, schema_text):
        # All SZL attributes should use szl.graph prefix
        assert schema_text.count('szl.graph.') >= 5


# ─── Citation tests (8 tests) ────────────────────────────────────────────────

class TestCitations:
    def test_v17_t1_lean_citation(self, schema_text):
        assert 'V17.2-T1' in schema_text

    def test_v17_t2_lean_citation(self, schema_text):
        assert 'V17.2-T2' in schema_text

    def test_v17_t3_lean_citation(self, schema_text):
        assert 'V17.2-T3' in schema_text

    def test_graph2nn_paper_citation(self, schema_text):
        assert 'arXiv:2007.06559' in schema_text

    def test_pgnn_paper_citation(self, schema_text):
        assert 'arXiv:1906.04817' in schema_text

    def test_graphrnn_paper_citation(self, schema_text):
        assert 'arXiv:1802.08773' in schema_text

    def test_gcpn_paper_citation(self, schema_text):
        assert 'arXiv:1806.02473' in schema_text

    def test_pytorch_geometric_citation(self, schema_text):
        assert 'pytorch_geometric' in schema_text or 'PyG' in schema_text or \
               'PyTorch Geometric' in schema_text


# ─── Example tests (5 tests) ─────────────────────────────────────────────────

class TestExamples:
    def test_examples_section_present(self, schema_text):
        assert 'examples:' in schema_text or 'example' in schema_text.lower()

    def test_example_lambda_span_present(self, schema_text):
        assert 'span: a11oy.graph.lambda' in schema_text

    def test_example_position_span_present(self, schema_text):
        assert 'span: a11oy.graph.position' in schema_text

    def test_example_gcpn_span_present(self, schema_text):
        assert 'span: a11oy.graph.gcpn_propose' in schema_text

    def test_github_url_present(self, schema_text):
        assert 'github.com/szl-holdings' in schema_text
