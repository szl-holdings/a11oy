"""Tests for the OTLP bridge (WU-3): round-trip + anchor-attr preservation + receipt."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from mesh.otlp_bridge import OtlpBridge, parse_otlp_json, to_otlp_json  # noqa: E402


def sample_spans():
    return [
        {
            "trace_id": "a" * 32,
            "span_id": "b" * 16,
            "name": "rosie.decision.evaluate",
            "start_ns": 1700000000000000000,
            "end_ns": 1700000000500000000,
            "attributes": {
                "szl.anchor_formula.id": "F1",
                "szl.lean_commit_sha": "c7c0ba17",
                "szl.mesh.organ": "rosie",
                "retries": 2,
                "ok": True,
            },
            "status": 1,
        }
    ]


def test_otlp_shape():
    req = to_otlp_json(sample_spans())
    rs = req["resourceSpans"]
    assert len(rs) == 1
    sp = rs[0]["scopeSpans"][0]["spans"][0]
    assert sp["name"] == "rosie.decision.evaluate"
    # ns timestamps are strings per OTLP/HTTP-JSON
    assert isinstance(sp["startTimeUnixNano"], str)
    assert sp["startTimeUnixNano"] == "1700000000000000000"


def test_round_trip_identity():
    spans = sample_spans()
    back = parse_otlp_json(to_otlp_json(spans))
    assert back[0]["trace_id"] == spans[0]["trace_id"]
    assert back[0]["span_id"] == spans[0]["span_id"]
    assert back[0]["name"] == spans[0]["name"]
    assert back[0]["start_ns"] == spans[0]["start_ns"]
    assert back[0]["end_ns"] == spans[0]["end_ns"]


def test_anchor_attributes_preserved():
    back = parse_otlp_json(to_otlp_json(sample_spans()))
    a = back[0]["attributes"]
    assert a["szl.anchor_formula.id"] == "F1"
    assert a["szl.lean_commit_sha"] == "c7c0ba17"
    assert a["szl.mesh.organ"] == "rosie"
    assert a["retries"] == 2 and a["ok"] is True


def test_typed_attribute_round_trip():
    back = parse_otlp_json(to_otlp_json(sample_spans()))
    a = back[0]["attributes"]
    assert isinstance(a["retries"], int)
    assert isinstance(a["ok"], bool)


def test_bridge_inproc_success_and_receipt():
    bridge = OtlpBridge()  # default in-proc transport
    res = bridge.export(sample_spans())
    assert res["code"] == "SUCCESS"
    assert res["accepted"] == 1
    assert res["batch_receipt"]["payloadType"].endswith("mesh-otlp-batch-receipt+json")


def test_bridge_failure_is_honest():
    def boom(_req):
        raise RuntimeError("transport down")

    bridge = OtlpBridge(transport=boom)
    res = bridge.export(sample_spans())
    assert res["code"] == "FAILURE"
    assert "transport down" in res["error"]
    # receipt still present, marked for a 0-accepted FAILURE batch
    assert "batch_receipt" in res


def test_empty_batch():
    bridge = OtlpBridge()
    res = bridge.export([])
    assert res["code"] == "SUCCESS" and res["accepted"] == 0


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
