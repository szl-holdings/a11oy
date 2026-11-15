# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""A missing chain_verified flag is not verification.

The seven call sites that used to default a missing key to True now default
it to False. An explicit True stays verified. An explicit False stays unverified.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="a11oy-chain-verified-"))
os.environ.setdefault("A11OY_CODE_DB", str(_TMP / "code.db"))
os.environ.setdefault("A11OY_AGENT_REFLECT_DB", str(_TMP / "reflect.db"))
os.environ.setdefault("A11OY_CODE_SANDBOX", str(_TMP / "sandbox"))
os.environ.setdefault("A11OY_REACT_DB", str(_TMP / "react.sqlite3"))

import a11oy_agent_loop as agent_loop
import a11oy_code_orchestrator as orchestrator
import a11oy_warhacker_obs as warhacker
import szl_anatomy_3d as anatomy
from fastapi import FastAPI


def _decision(chain_verified):
    context = {
        "risk": "low",
        "authorized": True,
        "has_provenance": True,
        "license_class": "GREEN",
    }
    if chain_verified is not None:
        context["chain_verified"] = chain_verified
    return orchestrator.puriq_decide("fs_read", context)


def test_missing_chain_verified_trips_hukla_and_zeroes_khipu_factor():
    missing = _decision(None)
    explicit_true = _decision(True)
    explicit_false = _decision(False)

    assert "T01" in missing["hukla_fired"]
    assert missing["score"] == 0.0
    assert missing["allow"] is False

    assert "T01" not in explicit_true["hukla_fired"]
    assert explicit_true["score"] > 0.0

    assert "T01" in explicit_false["hukla_fired"]
    assert explicit_false["score"] == 0.0


def test_agent_halt_does_not_treat_a_missing_receipt_flag_as_verified():
    loop = agent_loop.AgentLoop(khipu_emit=lambda action, payload: {"hash": "abc"})
    halted = loop._halt([], "probe", "task")
    assert halted["chain_verified"] is False

    verified = agent_loop.AgentLoop(
        khipu_emit=lambda action, payload: {"hash": "abc", "chain_verified": True}
    )._halt([], "probe", "task")
    assert verified["chain_verified"] is True


def test_agent_finalize_does_not_treat_a_missing_receipt_flag_as_verified():
    async def synthesize(task, retrievals):
        return {
            "ok": True,
            "stub": False,
            "model": "unit-model",
            "text": "cited answer",
            "_expression_authorized": False,
            "synthesis_admission": {
                "state": "AUTHORIZED_CONTENT_SUPPLIED",
                "source_count": 1,
                "context_sha256": "ab" * 32,
                "semantic_support_verified": False,
                "provider_id": "unit",
                "model_id": "unit-model",
                "trust_domain": "LOCAL",
            },
        }

    loop = agent_loop.AgentLoop(
        khipu_emit=lambda action, payload: {"hash": "abc"},
        rag_query=lambda q: {"ok": True, "chunks": [{"path": f"src-{i}"} for i in range(6)]},
        answer_synthesizer=synthesize,
        puriq_decide=lambda action, context: {
            "allow": True, "score": 1.0, "lambda": 1.0, "reason": "unit",
            "khipu_receipt": {"hash": "abc"},
        },
    )
    result = asyncio.run(loop.run("summarize the notes"))
    assert result["ok"] is True
    assert result["chain_verified"] is False


class _Dag:
    def __init__(self, record):
        self._record = record

    def emit(self, op, payload):
        return dict(self._record)

    def tail(self, n):
        return [dict(self._record)]

    def verify_chain(self):
        return {"ok": False, "depth": 1, "broken_at": None}

    def depth(self):
        return 1

    def head(self):
        return "h"


def _install_khipu(record):
    module = types.ModuleType("szl_khipu")
    module.get_dag = lambda *args, **kwargs: _Dag(record)
    sys.modules["szl_khipu"] = module
    return module


def test_receipt_fallback_does_not_treat_a_missing_flag_as_verified():
    _install_khipu({"digest": "d", "seq": 1})
    app = FastAPI()
    receipt = warhacker._emit_receipt(app, None, {"op": "observe"})
    assert receipt["chain_verified"] is False

    _install_khipu({"digest": "d", "seq": 1, "chain_verified": True})
    verified = warhacker._emit_receipt(app, None, {"op": "observe"})
    assert verified["chain_verified"] is True


def test_span_fallback_does_not_treat_a_missing_flag_as_verified():
    _install_khipu({"digest": "abcd", "seq": 1, "action": "observe", "ts": 1, "signature": None})
    app = FastAPI()
    warhacker.register(app)
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", "").endswith("/observability/spans")
    )
    response = asyncio.run(endpoint())
    import json
    body = json.loads(response.body)
    assert body["spans"]
    assert all(span["chain_verified"] is False for span in body["spans"])


def test_anatomy_span_fallback_does_not_treat_a_missing_flag_as_verified():
    sys.modules["szl_observability"] = types.ModuleType("szl_observability")

    class _Khipu:
        def get_dag(self, org, ns):
            return _Dag({"action": "op", "digest": "abcdef123456", "seq": 1, "ts": 1})

    anatomy._KHIPU = _Khipu()
    missing = anatomy.spans_recent()
    assert missing["spans"]
    assert all(span["ok"] is False for span in missing["spans"])

    class _Verified:
        def get_dag(self, org, ns):
            return _Dag({
                "action": "op", "digest": "abcdef123456", "seq": 1, "ts": 1,
                "chain_verified": True,
            })

    anatomy._KHIPU = _Verified()
    verified = anatomy.spans_recent()
    assert all(span["ok"] is True for span in verified["spans"])
