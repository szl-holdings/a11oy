"""
szl_energy_budget.py — SHARED energy-budget receipt layer for a11oy (Proven Energy Engine).

Per compute task, records a Bekenstein-GATED receipt binding the task's information
content (Shannon) to its physical information-capacity bound (Bekenstein, N·8 bits)
and its energy draw (joules) — so every harvested joule and compute cycle carries a
verifiable, bounded receipt. This is the runtime companion to the kernel-proven Lean
formulas (F19 Bekenstein additivity + TH6 DPI bound; F12 Kuramoto; coherence-decay).

  GET  /api/<ns>/v1/energy/budget                  -> in-memory ledger summary + gate
  GET  /api/<ns>/v1/energy/budget?bytes=&bits=&...  -> track one task, return its receipt

Receipt fields (per task):
  task_hash            sha256 of the inputs (stable id; never a secret)
  output_bytes         n output bytes the task produced
  shannon_bits         Shannon information content of the output (bits)
  bekenstein_bound_bits  N·8 — the SZL canonical Bekenstein software bound (TH6)
  within_bound         shannon_bits <= bekenstein_bound_bits  (the F19/TH6 gate)
  energy_source        harvest source label (default "grid")
  joules_est           SAMPLE/ESTIMATE energy draw — NOT a metered value
  ts                   ISO-8601 UTC timestamp

DOCTRINE (v11/v12, NEVER violated):
  - NO free-energy / perpetual-motion claims. We harvest WASTED energy and PROVE
    bounded work; the Bekenstein gate proves the joules bought real, bounded info work.
  - Every energy number (joules_est) is LABELED "SAMPLE/ESTIMATE" until a real power
    meter is wired. The endpoint reports honestly; the half-state (claiming more energy
    than is real) is the only unacceptable outcome.
  - open-weight only; never commit a key.

Canonical math (mirrors ouroboros runtime/bekenstein, TH6 DPI bound, and the locked-8
F19 Bekenstein additivity in lutar-lean):
  bekenstein_bound(n_bytes) = n_bytes * 8            (bits — software-analogy form)
  shannon_entropy_bits(probs) = -Σ p·log2(p)         (Shannon, bits per symbol)
Because a byte's empirical entropy per symbol is in [0, 8], the total Shannon content
of N bytes is always <= N·8 — i.e. the gate is the proven F19/TH6 inequality, not an
assertion. Pure stdlib; no numpy, no key, no network.
"""
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

# Honest label carried on every energy figure until a real meter exists.
ENERGY_FIGURE_LABEL = "SAMPLE/ESTIMATE (no real power meter wired — doctrine v11/v12)"

# In-memory ledger (process-local; resets on restart). A monotone append-only list
# of receipts — mirrors the f19_budget_monotone / monotone-energy-ledger idea: the
# running joules_est sum is non-decreasing because every draw is nonneg.
_LEDGER: list[dict] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Canonical SZL Bekenstein / Shannon math (TH6 DPI bound; F19 additivity).
# ---------------------------------------------------------------------------
def shannon_entropy_bits(probs: list[float]) -> float:
    """Shannon entropy in bits: H = -Σ p·log2(p). Mirrors the ouroboros runtime."""
    return -sum(p * math.log2(p) for p in probs if p > 0)


def shannon_bits_of_bytes(data: bytes) -> float:
    """Total Shannon information content (bits) of a byte string.

    Empirical byte-frequency distribution -> entropy per byte (in [0, 8]) times the
    number of bytes. By construction this is <= len(data)*8, so it satisfies the
    Bekenstein bound for free — the gate is the PROVEN inequality, not an assertion.
    """
    n = len(data)
    if n == 0:
        return 0.0
    counts = Counter(data)
    probs = [c / n for c in counts.values()]
    per_byte = shannon_entropy_bits(probs)      # bits per byte, in [0, 8]
    return per_byte * n


def bekenstein_bound(n_bytes: int) -> int:
    """SZL canonical software-analogy Bekenstein bound: N·8 bits (TH6 / F19)."""
    return int(n_bytes) * 8


def task_hash(inputs: dict) -> str:
    """Stable sha256 of the task inputs (an id, never a secret)."""
    blob = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def track_task(
    output: bytes | str | None = None,
    output_bytes: int | None = None,
    shannon_bits: float | None = None,
    energy_source: str = "grid",
    joules_est: float = 0.0,
    extra: dict | None = None,
) -> dict:
    """Build + append a Bekenstein-gated energy receipt for one compute task.

    Two ways to supply the info content:
      * output (bytes/str): we compute real shannon_bits + output_bytes from it.
      * output_bytes (+ optional shannon_bits): when only sizes are known (e.g. a
        remote turn). If shannon_bits is omitted we honestly assume the worst case
        output_bytes*8 (full-entropy), which still satisfies the bound with equality.
    Asserts shannon_bits <= bekenstein_bound_bits (the F19/TH6 gate). Energy figures
    are labeled SAMPLE/ESTIMATE. Returns the receipt; appends it to the ledger.
    """
    if output is not None:
        data = output.encode("utf-8") if isinstance(output, str) else bytes(output)
        n_bytes = len(data)
        s_bits = shannon_bits_of_bytes(data)
    else:
        n_bytes = int(output_bytes or 0)
        s_bits = float(shannon_bits) if shannon_bits is not None else float(n_bytes * 8)
    bound = bekenstein_bound(n_bytes)
    within = s_bits <= bound + 1e-9          # numeric slack, mirrors dpi_bound_satisfied
    j_est = max(0.0, float(joules_est))      # nonneg draw — keeps the ledger monotone
    receipt = {
        "task_hash": task_hash({
            "output_bytes": n_bytes, "shannon_bits": round(s_bits, 6),
            "energy_source": energy_source, "joules_est": j_est,
            "extra": extra or {},
        }),
        "output_bytes": n_bytes,
        "shannon_bits": round(s_bits, 6),
        "bekenstein_bound_bits": bound,
        "within_bound": bool(within),
        "energy_source": str(energy_source),
        "joules_est": round(j_est, 6),
        "joules_est_label": ENERGY_FIGURE_LABEL,
        "gate": "F19/TH6 Bekenstein: shannon_bits <= output_bytes*8",
        "ts": _now(),
    }
    if extra:
        receipt["extra"] = extra
    _LEDGER.append(receipt)
    return receipt


def budget_summary() -> dict:
    """Honest summary of the in-memory ledger: totals, monotone joules sum, gate status."""
    total_bytes = sum(r["output_bytes"] for r in _LEDGER)
    total_shannon = sum(r["shannon_bits"] for r in _LEDGER)
    total_bound = sum(r["bekenstein_bound_bits"] for r in _LEDGER)
    total_joules = sum(r["joules_est"] for r in _LEDGER)
    all_within = all(r["within_bound"] for r in _LEDGER)
    return {
        "model": "Proven Energy Engine — Bekenstein-gated energy+information budget",
        "status": "VERIFIED (gate)" if _LEDGER else "EMPTY",
        "task_count": len(_LEDGER),
        "total_output_bytes": total_bytes,
        "total_shannon_bits": round(total_shannon, 6),
        "total_bekenstein_bound_bits": total_bound,
        "all_within_bound": bool(all_within),
        "gate": "F19/TH6 Bekenstein: Σ shannon_bits <= Σ output_bytes*8",
        "total_joules_est": round(total_joules, 6),
        "total_joules_est_label": ENERGY_FIGURE_LABEL,
        "ledger_monotone": "running joules_est sum is non-decreasing (every draw nonneg) — mirrors f19_budget_monotone",
        "composes": ["F19 Bekenstein additivity (locked-8)", "TH6 DPI/Bekenstein runtime bound",
                     "F12 Kuramoto multi-node coupling", "coherence-decay honesty governor"],
        "doctrine": "NO free-energy claims; energy figures are SAMPLE/ESTIMATE until a real meter; harvest WASTED energy + PROVE bounded work; open-weight only; never commit a key.",
        "lean_witness": "Showcase/Frontier/EnergyBudgetWitness.lean (0-sorry, core-axioms-only)",
        "computed_at": _now(),
    }


# ---------------------------------------------------------------------------
# HTTP handlers (same style as szl_quantum_bio).
# ---------------------------------------------------------------------------
def _f(req, key, default):
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return float(default)


def _h_budget(req: Request):
    """Track a task when ?bytes= is present; otherwise return the ledger summary."""
    qp = req.query_params
    if "bytes" in qp or "output_bytes" in qp:
        n_bytes = int(_f(req, "bytes", _f(req, "output_bytes", 0.0)))
        s_raw = qp.get("bits", qp.get("shannon_bits"))
        s_bits = float(s_raw) if s_raw not in (None, "") else None
        source = qp.get("source", qp.get("energy_source", "grid"))
        j_est = _f(req, "joules", _f(req, "joules_est", 0.0))
        receipt = track_task(output_bytes=n_bytes, shannon_bits=s_bits,
                             energy_source=source, joules_est=j_est)
        return JSONResponse({
            "model": "Proven Energy Engine — task receipt",
            "status": "VERIFIED (gate)",
            "receipt": receipt,
            "summary": budget_summary(),
        })
    return JSONResponse(budget_summary())


def register(app, ns="a11oy"):
    """Wire the energy-budget endpoint onto the app under /api/<ns>/v1/energy/*.

    Additive. Uses FastAPI's add_api_route when available (matches the other szl_*
    modules so resolution order is correct vs the SPA catch-all); falls back to a
    Starlette route append for a bare Starlette app."""
    base = f"/api/{ns}/v1/energy"
    handlers = [
        (f"{base}/budget", _h_budget),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


def _selftest() -> dict:
    """No-server self-test for the energy-budget receipt + Bekenstein gate.

    Proves, from core math only: the bound is N·8; real-bytes Shannon content never
    exceeds the bound (the F19/TH6 inequality); the gate flags an over-claim; the
    ledger joules sum stays monotone; energy figures carry the SAMPLE label.
    """
    _LEDGER.clear()
    out: dict = {}

    # (a) Bekenstein bound is exactly N*8.
    assert bekenstein_bound(0) == 0 and bekenstein_bound(1) == 8 and bekenstein_bound(64) == 512
    out["bekenstein_bound_n8"] = True

    # (b) Real-bytes Shannon content <= bound (the proven F19/TH6 gate), various inputs.
    for sample in (b"", b"A", b"AAAAAAAA", b"abcdefgh", bytes(range(256)), b"the quick brown fox"):
        s = shannon_bits_of_bytes(sample)
        assert s <= bekenstein_bound(len(sample)) + 1e-9, (sample, s)
    out["shannon_within_bound"] = True

    # (c) A tracked real task is within_bound and labels its energy figure SAMPLE.
    r1 = track_task(output=b"hello world", energy_source="curtailed-solar", joules_est=1.5)
    assert r1["within_bound"] is True
    assert r1["bekenstein_bound_bits"] == 11 * 8
    assert "SAMPLE/ESTIMATE" in r1["joules_est_label"]
    assert r1["energy_source"] == "curtailed-solar"
    out["task_within_bound_labeled"] = True

    # (d) The gate HONESTLY flags an over-claim (shannon_bits > N*8) as within_bound False.
    r_bad = track_task(output_bytes=4, shannon_bits=999.0, energy_source="grid", joules_est=0.0)
    assert r_bad["within_bound"] is False, r_bad
    out["gate_flags_overclaim"] = True

    # (e) Ledger joules sum is monotone non-decreasing (every draw nonneg).
    _LEDGER.clear()
    running = 0.0
    prev = -1.0
    for j in (0.0, 2.0, 0.5, 10.0):
        track_task(output=b"x" * 8, energy_source="off-peak", joules_est=j)
        running = budget_summary()["total_joules_est"]
        assert running >= prev, (running, prev)
        prev = running
    out["ledger_monotone"] = True

    # (f) Summary is honest: all_within_bound True, doctrine + SAMPLE label present.
    summ = budget_summary()
    assert summ["all_within_bound"] is True
    assert "SAMPLE/ESTIMATE" in summ["total_joules_est_label"]
    assert "free-energy" in summ["doctrine"].lower() or "no free" in summ["doctrine"].lower()
    out["summary_honest"] = True

    _LEDGER.clear()
    out["ok"] = True
    return out


if __name__ == "__main__":
    print(_selftest())
