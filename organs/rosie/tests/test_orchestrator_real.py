# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Real chain test for the Amaru → Sentra → Killinchu → A11oy orchestrator.

We inject a deterministic dispatch override into ToolRouter so the test is
hermetic (no network), but it exercises the REAL orchestrator state machine,
the REAL Byzantine-quorum gate, and the REAL OTLP span recorder — asserting the
single-trace-id cross-pod contract and the honest halt behaviour.

Run:  pytest -q tests/test_orchestrator_real.py
Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rosie.orchestrator import Orchestrator, CHAIN          # noqa: E402
from rosie.tool_router import ToolRouter                    # noqa: E402
from rosie.observability import Observability, parse_traceparent  # noqa: E402


def _allow_router():
    """Router whose organs all attest healthy and ALLOW (quorum passes)."""
    health = {o: {"http": 200, "ok": True, "lambda": "Conjecture 1", "base": "x"}
              for o in ("amaru", "sentra", "killinchu", "a11oy", "rosie")}

    def dispatch(tool, args, organ, tp):
        return {"tool": tool, "organ": organ, "success": True, "http": 200,
                "result": {"verdict": "allow", "allowed": True}, "traceparent": tp}

    r = ToolRouter(dispatch_override=dispatch)
    r.organ_health = lambda: health  # type: ignore
    return r


def _deny_at_sentra_router():
    health = {o: {"http": 200, "ok": True, "lambda": "Conjecture 1", "base": "x"}
              for o in ("amaru", "sentra", "killinchu", "a11oy", "rosie")}

    def dispatch(tool, args, organ, tp):
        if organ == "sentra":
            return {"tool": tool, "organ": organ, "success": True, "http": 200,
                    "result": {"verdict": "deny", "allowed": False}, "traceparent": tp}
        return {"tool": tool, "organ": organ, "success": True, "http": 200,
                "result": {"verdict": "allow", "allowed": True}, "traceparent": tp}

    r = ToolRouter(dispatch_override=dispatch)
    r.organ_health = lambda: health  # type: ignore
    return r


def test_chain_order_is_amaru_sentra_killinchu_a11oy():
    assert [n.name for n in CHAIN] == ["amaru", "sentra", "killinchu", "a11oy"]


def test_full_allow_chain_single_trace_id():
    orch = Orchestrator(router=_allow_router(), obs=Observability("rosie"))
    state = orch.run("ship doctrine-v11 receipt")
    summ = orch.summary(state)
    # all 4 organs ran
    assert summ["hops"] == 4
    assert [r["organ"] for r in summ["receipts"]] == \
        ["amaru", "sentra", "killinchu", "a11oy"]
    # ONE trace-id threads every hop (cross-pod tracing contract)
    assert summ["single_trace_id"] is True
    assert len(summ["trace_ids"]) == 1
    # final governance verdict is an honest ALLOW
    assert summ["verdict"].startswith("ALLOW")
    assert "Conjecture 1" in summ["lambda_status"]


def test_quorum_gate_denies_when_witnesses_unhealthy():
    r = _allow_router()
    # only 2 of 4 organ witnesses healthy -> below 3-of-4 majority
    bad = {o: {"http": 503, "ok": False, "lambda": "Conjecture 1", "base": "x"}
           for o in ("amaru", "sentra", "killinchu", "a11oy", "rosie")}
    bad["amaru"]["ok"] = True; bad["amaru"]["http"] = 200
    bad["sentra"]["ok"] = True; bad["sentra"]["http"] = 200
    r.organ_health = lambda: bad  # type: ignore
    q = r.quorum_witnesses("lambda_gate", "00-" + "a" * 32 + "-" + "b" * 16 + "-01")
    assert q["bft_bound"] == "n>=3f+1"
    assert q["n_required"] == 4
    assert q["quorum_permitted"] is False


def test_chain_halts_honestly_on_policy_deny():
    orch = Orchestrator(router=_deny_at_sentra_router(), obs=Observability("rosie"))
    state = orch.run("do something the immune system blocks")
    summ = orch.summary(state)
    assert state.halted is True
    # halted right after sentra; killinchu + a11oy never fabricated
    assert [r["organ"] for r in summ["receipts"]] == ["amaru", "sentra"]
    assert "HALTED" in summ["verdict"]
    assert "sentra" in summ["verdict"]


def test_spans_are_valid_w3c_traceparents():
    orch = Orchestrator(router=_allow_router(), obs=Observability("rosie"))
    orch.run("emit spans")
    assert len(orch.obs.spans) >= 4
    for s in orch.obs.spans:
        assert len(s.trace_id) == 32
        assert len(s.span_id) == 16


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
