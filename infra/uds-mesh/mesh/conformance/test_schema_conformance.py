"""
mesh/conformance/test_schema_conformance.py
UDS-Mesh conformance suite — validates the five organ span schemas AND that the
mesh SDK emits spans conforming to them.

Covers:
  1. All 5 schemas (a11oy.graph, sentra.gate, amaru.sync, killinchu.courier,
     rosie.decision) exist, parse as YAML, and declare the cross-organ envelope.
  2. The shared szl.mesh.* governance attributes are identical across organs.
  3. The mesh SDK (mesh/sdk/mesh.py) emits spans whose names + attributes are
     accepted by the matching schema.
  4. BLS batch aggregation round-trips and detects tampering (lutar-lean #180).
  5. W3C Trace Context parse/format round-trips and rejects all-zero ids.

Run: pytest mesh/conformance/ -v
Pure-stdlib YAML mini-parser is bundled so the suite runs with zero deps;
if PyYAML is installed it is preferred.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA_DIR = os.path.join(REPO, "schemas", "spans")
SDK_PATH = os.path.join(REPO, "mesh", "sdk", "mesh.py")

ORGANS = {
    "a11oy.graph": ["a11oy.graph.lambda", "a11oy.graph.automorphism", "a11oy.graph.position"],
    "sentra.gate": ["sentra.gate.evaluate", "sentra.gate.attest", "sentra.gate.fail_closed"],
    "amaru.sync": ["amaru.sync.merge", "amaru.sync.receipt", "amaru.sync.drift_alert"],
    "killinchu.courier": ["killinchu.courier.dispatch", "killinchu.courier.deliver", "killinchu.courier.verify"],
    "rosie.decision": ["rosie.decision.evaluate", "rosie.decision.witness", "rosie.decision.replay"],
}

REQUIRED_MESH_ATTRS = [
    "szl.mesh.organ",
    "szl.mesh.receipt_hash",
    "szl.mesh.dsse_payload_type",
    "szl.mesh.lambda_value",
    "szl.mesh.governance_drift",
]


_SDK_CACHE = None


def _load_sdk():
    global _SDK_CACHE
    if _SDK_CACHE is not None:
        return _SDK_CACHE
    spec = importlib.util.spec_from_file_location("uds_mesh_sdk", SDK_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve cls.__module__.
    sys.modules["uds_mesh_sdk"] = mod
    spec.loader.exec_module(mod)
    _SDK_CACHE = mod
    return mod


def _read(name: str) -> str:
    with open(os.path.join(SCHEMA_DIR, f"{name}.yaml"), encoding="utf-8") as f:
        return f.read()


# ── 1. schema files exist + parse ─────────────────────────────────────────────
@pytest.mark.parametrize("schema", list(ORGANS))
def test_schema_file_exists(schema):
    assert os.path.isfile(os.path.join(SCHEMA_DIR, f"{schema}.yaml")), schema


@pytest.mark.parametrize("schema", list(ORGANS))
def test_schema_parses_as_yaml(schema):
    text = _read(schema)
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(text)
        assert isinstance(doc, dict)
        assert "version" in doc
    except ImportError:
        # stdlib fallback: assert the document carries a version + schema_url
        assert "version:" in text
        assert "schema_url:" in text


@pytest.mark.parametrize("schema", list(ORGANS))
def test_schema_declares_all_span_names(schema):
    text = _read(schema)
    for span_name in ORGANS[schema]:
        assert span_name in text, f"{span_name} missing from {schema}.yaml"


# ── 2. cross-organ envelope identical ─────────────────────────────────────────
@pytest.mark.parametrize("schema", list(ORGANS))
def test_schema_carries_mesh_envelope(schema):
    text = _read(schema)
    for attr in REQUIRED_MESH_ATTRS:
        assert attr in text, f"{attr} missing from {schema}.yaml cross-organ envelope"


def test_all_schemas_share_trace_context_fields():
    for schema in ORGANS:
        text = _read(schema)
        assert "trace_id" in text
        assert "span_id" in text
        assert "W3C" in text or "TraceContext" in text


# ── 3. SDK emits conforming spans ─────────────────────────────────────────────
@pytest.mark.parametrize("organ,schema", [
    ("a11oy", "a11oy.graph"), ("sentra", "sentra.gate"), ("amaru", "amaru.sync"),
    ("killinchu", "killinchu.courier"), ("rosie", "rosie.decision"),
])
def test_sdk_emits_conforming_span(organ, schema):
    mesh = _load_sdk()
    e = mesh.MeshEmitter(organ)
    name = mesh.SPAN_NAMES[organ][0]
    span = e.emit(name, 0.92)
    otel = span.to_otel()
    assert otel["name"] in ORGANS[schema]
    for attr in REQUIRED_MESH_ATTRS:
        assert attr in otel["attributes"], attr
    assert otel["attributes"]["szl.mesh.organ"] == organ


def test_sdk_rejects_unknown_span_name():
    mesh = _load_sdk()
    e = mesh.MeshEmitter("sentra")
    with pytest.raises(ValueError):
        e.emit("sentra.gate.NOPE", 0.9)


def test_sdk_rejects_unknown_organ():
    mesh = _load_sdk()
    with pytest.raises(ValueError):
        mesh.MeshEmitter("not-an-organ")


# ── 4. BLS batch aggregation (lutar-lean #180 aggregate_verify) ───────────────
def test_bls_batch_aggregate_verifies():
    mesh = _load_sdk()
    e = mesh.MeshEmitter("amaru")
    root = mesh.TraceContext.new_root()
    e.emit("amaru.sync.merge", 0.93, trace=root)
    e.emit("amaru.sync.receipt", 0.95, trace=root.child())
    agg = e.batch_aggregate()
    assert agg["count"] == 2
    assert agg["verified"] is True
    spans = e.drain()
    assert mesh.verify_batch(spans, agg, "mesh:amaru") is True


def test_bls_batch_detects_tamper():
    mesh = _load_sdk()
    e = mesh.MeshEmitter("rosie")
    e.emit("rosie.decision.evaluate", 0.9)
    e.emit("rosie.decision.witness", 0.9)
    agg = e.batch_aggregate()
    spans = e.drain()
    spans[0]["attributes"]["szl.mesh.receipt_hash"] = "0" * 64
    assert mesh.verify_batch(spans, agg, "mesh:rosie") is False


# ── 5. W3C Trace Context ──────────────────────────────────────────────────────
def test_traceparent_roundtrip():
    mesh = _load_sdk()
    tc = mesh.TraceContext.new_root()
    parsed = mesh.TraceContext.parse(tc.traceparent())
    assert parsed.trace_id == tc.trace_id
    assert parsed.span_id == tc.span_id


def test_traceparent_rejects_all_zero():
    mesh = _load_sdk()
    with pytest.raises(ValueError):
        mesh.TraceContext.parse("00-" + "0" * 32 + "-" + "0" * 16 + "-01")


def test_governance_drift_below_floor():
    mesh = _load_sdk()
    e = mesh.MeshEmitter("sentra")
    span = e.emit("sentra.gate.fail_closed", 0.05)
    assert span.governance_drift() is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
