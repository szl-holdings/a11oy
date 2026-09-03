from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"
PROBE = ROOT / "tools" / "readiness-harness" / "probe_runner.mjs"
TABS = ROOT / "tools" / "readiness-harness" / "tabs.json"

SPEC = importlib.util.spec_from_file_location("gen_tabs_matrix_unavailable", GENERATOR)
assert SPEC and SPEC.loader
matrix_generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix_generator)


def _node_binary() -> str:
    node = shutil.which("node")
    if node:
        return node
    runtime_nodes = (
        Path(sys.executable).resolve().parent.parent / "node" / "bin" / "node.exe",
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe",
    )
    for runtime_node in runtime_nodes:
        if runtime_node.is_file():
            return str(runtime_node)
    pytest.skip("Node.js is required for readiness-runner contract tests")


def _node_eval(source: str) -> subprocess.CompletedProcess[str]:
    module_url = PROBE.resolve().as_uri()
    program = (
        'import assert from "node:assert/strict";\n'
        f'import * as probe from {json.dumps(module_url)};\n'
        + source
    )
    return subprocess.run(
        [_node_binary(), "--input-type=module", "--eval", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_generated_legal_schemas_declare_typed_source_envelopes() -> None:
    matrix = matrix_generator.build()
    schemas = matrix["schemas"]

    assert schemas["devb_legal_matter"]["sourceEnvelopePaths"] == ["opinions"]
    assert schemas["vert_legal_feed"]["sourceEnvelopePaths"] == [
        "federal_register",
        "court_filings",
    ]
    assert "opinions.value" in schemas["devb_legal_matter"]["requiredPaths"]
    assert "opinions.value.items" not in schemas["devb_legal_matter"]["requiredPaths"]
    assert "court_filings.value" in schemas["vert_legal_feed"]["requiredPaths"]
    assert "court_filings.value.items" not in schemas["vert_legal_feed"]["requiredPaths"]

    checked_in = json.loads(TABS.read_text(encoding="utf-8"))
    assert checked_in["schemas"]["devb_legal_matter"] == schemas["devb_legal_matter"]
    assert checked_in["schemas"]["vert_legal_feed"] == schemas["vert_legal_feed"]


def test_probe_schema_accepts_null_only_for_exact_unavailable_evidence() -> None:
    result = _node_eval(
        """
const citation = { source_url: "https://www.courtlistener.com/help/api/rest/" };
const observedAt = "2026-09-03T00:42:00Z";
const matter = {
  surface: "matter",
  term: "insurance",
  opinions: {
    value: { items: [{ url: "https://www.courtlistener.com/opinion/1/" }] },
    freshness: { status: "live", fetched_at: observedAt },
  },
  sources_cited: [citation],
  doctrine: {},
};
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, true);

matter.opinions = {
  value: null,
  freshness: { status: "UNAVAILABLE", fetched_at: observedAt, error: "TimeoutError" },
};
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, true);

matter.opinions.freshness.status = "live";
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.freshness.status = "unavailable";
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.freshness.status = "UNAVAILABLE";
matter.opinions.value = { items: [] };
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
matter.opinions.value = null;
delete matter.opinions.freshness.fetched_at;
assert.equal(probe.validateSchema("devb_legal_matter", matter).ok, false);
"""
    )
    assert result.returncode == 0, result.stderr


def test_vertical_legal_schema_handles_observed_and_unavailable_sources_independently() -> None:
    result = _node_eval(
        """
const observedAt = "2026-09-03T00:42:00Z";
const legal = {
  vertical: "legal",
  federal_register: {
    value: { items: [{ html_url: "https://www.federalregister.gov/documents/1" }] },
    freshness: { status: "live", fetched_at: observedAt },
  },
  court_filings: {
    value: null,
    freshness: { status: "UNAVAILABLE", fetched_at: observedAt, error: "TimeoutError" },
  },
  sources_cited: [
    { source_url: "https://www.federalregister.gov/developers/documentation/api/v1" },
    { source_url: "https://www.courtlistener.com/help/api/rest/" },
  ],
  doctrine: {},
};
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, true);

legal.court_filings = {
  value: { items: [{ url: "https://www.courtlistener.com/opinion/1/" }] },
  freshness: { status: "cached", fetched_at: observedAt },
};
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, true);

legal.federal_register.value = null;
legal.federal_register.freshness.status = "UNAVAILABLE";
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, true);
legal.federal_register.freshness.status = "cached";
assert.equal(probe.validateSchema("vert_legal_feed", legal).ok, false);
"""
    )
    assert result.returncode == 0, result.stderr
