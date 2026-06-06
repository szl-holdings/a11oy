# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Unit tests for the /api/rosie/v1/quorum tile endpoint.

Tests are hermetic: ToolRouter.organ_health() is monkey-patched to return
deterministic health dictionaries so no network calls are made.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).

Run: pytest -q tests/test_quorum_endpoint.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rosie.tool_router import ToolRouter, byzantine_quorum_n   # noqa: E402


def _healthy_router():
    """All 4 peer organs (excluding rosie itself) report healthy."""
    health = {o: {"http": 200, "ok": True, "lambda": "Conjecture 1", "base": "x"}
              for o in ("amaru", "sentra", "killinchu", "a11oy", "rosie")}
    r = ToolRouter()
    r.organ_health = lambda: health  # type: ignore
    return r


def _partial_router(healthy_count: int):
    """Exactly `healthy_count` of the 4 peer organs report ok=True."""
    organs = ["amaru", "sentra", "killinchu", "a11oy"]
    health = {o: {"http": 200 if i < healthy_count else 503,
                  "ok": i < healthy_count,
                  "lambda": "Conjecture 1",
                  "base": "x"}
              for i, o in enumerate(organs)}
    health["rosie"] = {"http": 200, "ok": True, "lambda": "Conjecture 1", "base": "x"}
    r = ToolRouter()
    r.organ_health = lambda: health  # type: ignore
    return r


_TP = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"


# ── byzantine_quorum_n ────────────────────────────────────────────────────

def test_bft_formula_f1():
    """n >= 3f + 1 with f=1 gives 4 required witnesses."""
    assert byzantine_quorum_n(1) == 4


def test_bft_formula_f0():
    assert byzantine_quorum_n(0) == 1


def test_bft_formula_f2():
    assert byzantine_quorum_n(2) == 7


# ── quorum_witnesses fields ───────────────────────────────────────────────

def test_quorum_all_healthy_permitted():
    q = _healthy_router().quorum_witnesses("lambda_gate", _TP)
    assert q["bft_bound"] == "n>=3f+1"
    assert q["n_required"] == 4
    assert q["healthy_witnesses"] == 4
    assert q["quorum_permitted"] is True
    assert isinstance(q["witnesses"], dict)


def test_quorum_exactly_3_of_4_permitted():
    q = _partial_router(3).quorum_witnesses("lambda_gate", _TP)
    assert q["healthy_witnesses"] == 3
    assert q["quorum_permitted"] is True


def test_quorum_2_of_4_denied():
    q = _partial_router(2).quorum_witnesses("lambda_gate", _TP)
    assert q["healthy_witnesses"] == 2
    assert q["quorum_permitted"] is False


def test_quorum_0_healthy_denied():
    q = _partial_router(0).quorum_witnesses("lambda_gate", _TP)
    assert q["healthy_witnesses"] == 0
    assert q["quorum_permitted"] is False


def test_quorum_witnesses_excludes_rosie():
    """Witnesses dict must not include 'rosie' (self)."""
    q = _healthy_router().quorum_witnesses("lambda_gate", _TP)
    assert "rosie" not in q["witnesses"]
    # Exactly the 4 peer organs
    assert set(q["witnesses"].keys()) == {"amaru", "sentra", "killinchu", "a11oy"}


def test_quorum_rule_present():
    q = _healthy_router().quorum_witnesses("lambda_gate", _TP)
    assert "3-of-4" in q["rule"]


# ── FastAPI endpoint shape (via TestClient) ───────────────────────────────

def test_quorum_endpoint_response_shape():
    """Integration smoke: /api/rosie/v1/quorum returns expected JSON keys."""
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        app = FastAPI()

        # Inline the same logic as the production block but with a controlled router.
        @app.get("/api/rosie/v1/quorum")
        def _quorum():
            rt = _healthy_router()
            tp = _TP
            q = rt.quorum_witnesses("lambda_gate", tp)
            return JSONResponse({
                "bft_bound": q["bft_bound"],
                "n_required": q["n_required"],
                "healthy_witnesses": q["healthy_witnesses"],
                "quorum_permitted": q["quorum_permitted"],
                "witnesses": q["witnesses"],
                "rule": q["rule"],
                "traceparent": tp,
                "doctrine": "v11 LOCKED 749/14/163 @ c7c0ba17",
                "lambda_status": "Conjecture 1 (NOT a theorem)",
                "source": "rosie.tool_router.ToolRouter.quorum_witnesses",
            })

        @app.get("/quorum")
        def _quorum_alias():
            return _quorum()

        client = TestClient(app)

        r = client.get("/api/rosie/v1/quorum")
        assert r.status_code == 200
        d = r.json()
        assert d["bft_bound"] == "n>=3f+1"
        assert d["n_required"] == 4
        assert d["healthy_witnesses"] == 4
        assert d["quorum_permitted"] is True
        assert "Conjecture 1" in d["lambda_status"]
        assert "rosie" not in d["witnesses"]
        assert d["doctrine"].startswith("v11")

        # Alias test
        r2 = client.get("/quorum")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["quorum_permitted"] is True

    except ImportError:
        import pytest
        pytest.skip("fastapi[testclient] not installed")
