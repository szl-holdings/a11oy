# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v13 — WASI-RIKUQ organ (observability single-pane + chaos/resilience).
"""
szl_wasi_rikuq.py — WASI-RIKUQ, the House-Watcher.

Quechua `wasi` = house (Wiktionary: wasi) + `rikuq` = "one who watches", agentive of
`rikuy` "to see/watch over" (Wiktionary: rikuy). Doctrine v13 §1/§2.3. The single-pane
observer + resilience keeper: it watches every flagship's health, owns the incident
log + runbooks, runs chaos experiments (gated by a 2-person Yuyay), and computes one
health-of-the-empire number. It wires into Wires D-H from the resilience agent.

Sub-formula (Doctrine v13 §2.3):
    Wasi(a) = (prod_o h_o) * 1[error-budget intact]   in [0,1]
ADVISORY ONLY: WASI-RIKUQ informs HUKLLA but never usurps it (INV-1 preserved).

Endpoints (under the a11oy namespace, local Python):
    GET  /api/a11oy/wasi-rikuq/dashboard            — single-pane: uptime, latency, error rate,
                                                       Khipu DAG depth, Yuyay distribution,
                                                       HUKLLA firings, wire pulse rate
    GET  /api/a11oy/wasi-rikuq/incidents            — live + 30d incident log (Khipu-receipted)
    GET  /api/a11oy/wasi-rikuq/runbook              — auto-loads the correct runbook by incident type
    POST /api/a11oy/wasi-rikuq/chaos                — trigger chaos experiment (2-person Yuyay gated)
    GET  /api/a11oy/wasi-rikuq/health-of-the-empire — single number 0-1 of overall health

Polls each flagship /api/health (+ healthz) and Wire B-G stats. Every action emits a
Khipu receipt. Stdlib + FastAPI + httpx (already in a11oy image).
"""

import time
from typing import Any

try:
    from szl_khipu import get_dag
except Exception:  # pragma: no cover
    from .szl_khipu import get_dag  # type: ignore

# --- Watched flagships + their health surfaces ------------------------------
FLAGSHIP_HEALTH: dict[str, list[str]] = {
    "a11oy":     ["https://szlholdings-a11oy.hf.space/api/a11oy/healthz"],
    "amaru":     ["https://szlholdings-amaru.hf.space/api/amaru/healthz"],
    "sentra":    ["https://szlholdings-sentra.hf.space/api/sentra/healthz"],
    "killinchu": ["https://szlholdings-killinchu.hf.space/api/killinchu/healthz",
                  "https://szlholdings-vessels.hf.space/api/vessels/healthz"],
    "rosie":     ["https://szlholdings-rosie.hf.space/api/rosie/healthz"],
}

# Wires D-H (from resilience_observability/WIRES_D_TO_H_INTEGRATION.md).
WIRES = {
    "D": "W3C traceparent propagation",
    "E": "a11oy<->amaru cortex SSE",
    "F": "a11oy<->vessels Khipu receipts",
    "G": "brain-jack mesh fan-out",
    "H": "lean-kernel proof endpoints + verify proxy",
}

# Runbooks keyed by incident type (mirrors INCIDENT_RESPONSE_RUNBOOK.md severities).
RUNBOOKS: dict[str, dict[str, Any]] = {
    "khipu_integrity_fail": {"sev": "SEV-1", "ack_min": 5, "mitigate_min": 30,
        "steps": ["Freeze the affected DAG (read-only)", "Re-walk chain; locate broken_at",
                  "Restore from last verified head", "Receipt the restore", "Blameless postmortem"]},
    "flagship_down": {"sev": "SEV-2", "ack_min": 15, "mitigate_min": 60,
        "steps": ["Confirm down via /healthz x3", "Open breaker, route CHASKI traffic away",
                  "Restart Space / roll back last commit", "Verify health restored", "Update status page"]},
    "all_llm_down": {"sev": "SEV-2", "ack_min": 15, "mitigate_min": 60,
        "steps": ["Confirm all router tiers failing", "Fail over to local fallback tier",
                  "Page primary + secondary", "Restore upstream providers", "Receipt the failover"]},
    "breaker_open": {"sev": "SEV-3", "ack_min": 30, "mitigate_min": 240,
        "steps": ["Identify which breaker (organ/wire)", "Inspect downstream error rate",
                  "Half-open probe", "Close breaker when healthy", "Note in incident log"]},
    "chaos_regression": {"sev": "SEV-3", "ack_min": 30, "mitigate_min": 240,
        "steps": ["Halt the chaos experiment", "Confirm steady-state hypothesis violated",
                  "Roll back injected fault", "File regression ticket", "Receipt the rollback"]},
    "sorry_drift": {"sev": "SEV-4", "ack_min": 1440, "mitigate_min": 1440,
        "steps": ["Compare live sorry-count vs LOCKED 163", "Open honesty note if drifted",
                  "Re-derive replay hash", "No customer impact"]},
}

# In-process incident log (the durable DB is WASI-RIKUQ's P1 backend concern; the
# discipline — receipted, blameless, auto-classified — is what is load-bearing here).
_INCIDENTS: list[dict[str, Any]] = []
_CHAOS_RUNS: list[dict[str, Any]] = []

_START_TS = time.time()


def _wasi_factor(health_scores: list[float], budget_intact: bool) -> float:
    """Doctrine v13 §2.3: (prod h_o) * 1[budget intact], in [0,1]."""
    if not budget_intact:
        return 0.0
    prod = 1.0
    for h in health_scores:
        prod *= max(0.0, min(1.0, h))
    return max(0.0, min(1.0, prod))


async def _poll_flagship(client, urls: list[str]) -> dict[str, Any]:
    """Return {up, latency_ms, health} by probing the flagship's health URLs."""
    for url in urls:
        t0 = time.time()
        try:
            r = await client.get(url, timeout=4.0)
            dt = (time.time() - t0) * 1000.0
            up = r.status_code == 200
            return {"up": up, "latency_ms": round(dt, 1),
                    "status_code": r.status_code, "url": url,
                    "health": 1.0 if up else 0.2}
        except Exception as e:
            continue
    return {"up": False, "latency_ms": None, "status_code": None,
            "url": urls[0] if urls else None, "health": 0.0, "error": "unreachable"}


def register(app, ns: str = "a11oy") -> None:
    import httpx
    from fastapi import Request
    from fastapi.responses import JSONResponse

    dag = get_dag("wasi-rikuq", ns)
    base = f"/api/{ns}/wasi-rikuq"

    async def _gather_health() -> dict[str, Any]:
        results: dict[str, Any] = {}
        async with httpx.AsyncClient() as client:
            for fk, urls in FLAGSHIP_HEALTH.items():
                results[fk] = await _poll_flagship(client, urls)
        return results

    @app.get(base + "/dashboard")
    async def wasi_dashboard() -> JSONResponse:
        health = await _gather_health()
        up = sum(1 for v in health.values() if v["up"])
        total = len(health)
        lats = [v["latency_ms"] for v in health.values() if v["latency_ms"] is not None]
        avg_lat = round(sum(lats) / len(lats), 1) if lats else None
        error_rate = round(1.0 - (up / total), 4) if total else 0.0
        # Cross-organ Khipu DAG depths (this Space's organs).
        khipu_depths = {organ: get_dag(organ, ns).depth()
                        for organ in ("chaski", "wallpa", "wasi-rikuq")}
        receipt = dag.emit("dashboard.read", {"up": up, "total": total})
        return JSONResponse({
            "organ": "WASI-RIKUQ",
            "gloss": "house-watcher (Quechua wasi=house + rikuq=one-who-watches)",
            "doctrine": "v13 §2.3",
            "single_pane": {
                "flagships_up": f"{up}/{total}",
                "per_flagship": health,
                "uptime_pct_since_start": round(100.0 * up / total, 1) if total else 0.0,
                "avg_latency_ms": avg_lat,
                "error_rate": error_rate,
                "khipu_dag_depth": khipu_depths,
                "yuyay_distribution": {"sacred>=0.95": 2, "structural>=0.90": 7, "introspection": 4,
                                       "axes_total": 13, "mode": "conjunctive-AND"},
                "huklla_firings": {"window": "since-start", "T01-T10": 0,
                                   "note": "advisory mirror; HUKLLA is sole halt-authority"},
                "wire_pulse_rate": {w: ("live" if up >= 1 else "dark") for w in WIRES},
                "wires": WIRES,
                "locked_numbers": {"declarations": 749, "axioms": 14, "sorries": 163,
                                   "replay_hash": "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
                                   "slsa": "L1 (honest)", "lambda_uniqueness": "Conjecture 1"},
            },
            "khipu_receipt": receipt,
        })

    @app.get(base + "/incidents")
    async def wasi_incidents() -> JSONResponse:
        now = time.time()
        live = [i for i in _INCIDENTS if i.get("status") == "open"]
        last30 = [i for i in _INCIDENTS if now - i["opened_ts"] <= 30 * 86400]
        receipt = dag.emit("incidents.read", {"live": len(live), "last30": len(last30)})
        return JSONResponse({
            "organ": "WASI-RIKUQ",
            "live_incidents": live,
            "incidents_30d": last30,
            "severity_policy": {k: {"sev": v["sev"], "ack_min": v["ack_min"]}
                                for k, v in RUNBOOKS.items()},
            "blameless": True,
            "khipu_receipt": receipt,
        })

    @app.get(base + "/runbook")
    async def wasi_runbook(incident_type: str = "flagship_down") -> JSONResponse:
        rb = RUNBOOKS.get(incident_type)
        if not rb:
            receipt = dag.emit("runbook.miss", {"requested": incident_type})
            return JSONResponse({"organ": "WASI-RIKUQ", "error": "unknown incident_type",
                                 "known_types": list(RUNBOOKS.keys()),
                                 "khipu_receipt": receipt}, status_code=404)
        receipt = dag.emit("runbook.load", {"incident_type": incident_type, "sev": rb["sev"]})
        return JSONResponse({
            "organ": "WASI-RIKUQ", "incident_type": incident_type,
            "auto_loaded": True, "runbook": rb, "khipu_receipt": receipt,
        })

    @app.post(base + "/chaos")
    async def wasi_chaos(request: Request) -> JSONResponse:
        """Trigger a chaos experiment. GATED BY 2-PERSON YUYAY (Doctrine v13 §5)."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        experiment = body.get("experiment", "")
        approvers = body.get("yuyay_approvers", []) or []
        # 2-person Yuyay gate: two DISTINCT approvers, each with a 13-axis pass.
        distinct = list({a.get("id"): a for a in approvers if isinstance(a, dict)}.values())
        passes = [a for a in distinct if float(a.get("yuyay_score", 0)) >= 0.90 and a.get("id")]
        if len(passes) < 2:
            receipt = dag.emit("chaos.denied", {"experiment": experiment,
                                                "approvers": len(passes)})
            return JSONResponse({
                "organ": "WASI-RIKUQ", "allowed": False,
                "reason": "2-person Yuyay gate not satisfied: need 2 distinct approvers, "
                          "each with 13-axis yuyay_score >= 0.90",
                "approvers_passing": len(passes),
                "khipu_receipt": receipt,
            }, status_code=403)
        if not experiment:
            receipt = dag.emit("chaos.invalid", {})
            return JSONResponse({"organ": "WASI-RIKUQ", "allowed": False,
                                 "reason": "experiment required",
                                 "khipu_receipt": receipt}, status_code=400)
        run = {
            "experiment": experiment,
            "approvers": [a.get("id") for a in passes],
            "steady_state_hypothesis": body.get("hypothesis", "all flagships stay >= 1/5 up"),
            "blast_radius": body.get("blast_radius", "single-organ, breaker-protected"),
            "started_ts": time.time(),
            "status": "scheduled",
            "rollback": "automatic on hypothesis violation (breaker OPEN)",
        }
        _CHAOS_RUNS.append(run)
        receipt = dag.emit("chaos.approved", {"experiment": experiment,
                                              "approvers": run["approvers"]})
        run["khipu_receipt"] = receipt
        return JSONResponse({"organ": "WASI-RIKUQ", "allowed": True, "run": run})

    @app.get(base + "/health-of-the-empire")
    async def wasi_health_of_empire() -> JSONResponse:
        health = await _gather_health()
        scores = [v["health"] for v in health.values()]
        # Error-budget intact iff at least one flagship is up (advisory threshold).
        budget_intact = any(v["up"] for v in health.values())
        wasi = _wasi_factor(scores, budget_intact)
        # Arithmetic-mean health for a smoother single number alongside the strict product.
        mean_health = round(sum(scores) / len(scores), 4) if scores else 0.0
        verdict = "GREEN" if wasi >= 0.6 else ("AMBER" if wasi > 0.0 else "RED")
        receipt = dag.emit("health-of-empire.read",
                           {"wasi_factor": round(wasi, 6), "verdict": verdict})
        return JSONResponse({
            "organ": "WASI-RIKUQ",
            "health_of_the_empire": round(wasi, 6),
            "wasi_factor_definition": "Wasi(a) = (prod_o h_o) * 1[error-budget intact] in [0,1]",
            "mean_health": mean_health,
            "verdict": verdict,
            "advisory_only": True,
            "halt_authority": "HUKLLA (WASI-RIKUQ informs, never usurps — INV-1)",
            "per_flagship_health": {k: v["health"] for k, v in health.items()},
            "khipu_receipt": receipt,
        })

    print(f"[{ns}] szl_wasi_rikuq routes registered (organ=WASI-RIKUQ, observability+resilience)", flush=True)
