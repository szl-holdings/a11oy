# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v13 — CHASKI organ (reception / onboarding / first-touch).
"""
szl_chaski.py — CHASKI, the Messenger. The empire-edge reception organ.

Quechua `chaski` = relay messenger (Wiktionary: chaski; Wikipedia: Chasqui).
Doctrine v13 §1/§2.1. CHASKI owns the first-30-seconds: greet a visitor, explain
"what is this", route them to the right flagship by stated need, and apply edge
backpressure.

Sub-formula (Doctrine v13 §2.1):
    Chaski(a) = exp(-kappa * backpressure(a)) * 1[routable(a)]  in [0,1]

Endpoints (registered under the a11oy namespace, all local Python, no Node):
    GET  /api/a11oy/chaski/welcome        — first-touch greeting + organ map
    GET  /api/a11oy/chaski/onboard/start  — begin an onboarding session
    POST /api/a11oy/chaski/onboard/step   — advance onboarding; routes by need
    GET  /api/a11oy/chaski/quickstart     — quickstart card per flagship
    GET  /api/a11oy/chaski/heatmap        — first-touch UX metrics (aggregate)

Every action emits a Khipu receipt (Doctrine v13 §5). Stdlib + FastAPI only.
"""

import math
import time
import uuid
from typing import Any

try:
    from szl_khipu import get_dag
except Exception:  # pragma: no cover — local dev fallback
    from .szl_khipu import get_dag  # type: ignore

# --- Flagship routing table (stated-need -> flagship) -----------------------
# Each flagship is a known live SZL organ surface. Routing is the heart of CHASKI.
FLAGSHIPS: dict[str, dict[str, Any]] = {
    "amaru":     {"organ": "Cortex / AMARU", "need": ["data sync", "memory", "ingest", "multi-source"],
                  "url": "https://szlholdings-amaru.hf.space", "blurb": "Convergent multi-source data sync — the memory cortex."},
    "sentra":    {"organ": "Immune / HUKLLA-front", "need": ["security", "halt", "tripwire", "policy"],
                  "url": "https://szlholdings-sentra.hf.space", "blurb": "Immune front — tripwires and policy halts."},
    "killinchu": {"organ": "Geofence / KILLINCHU", "need": ["drone", "geofence", "embodied", "edge device"],
                  "url": "https://szlholdings-killinchu.hf.space", "blurb": "Geofence bridge — the embodied/edge lane."},
    "rosie":     {"organ": "Brain-jack mesh / ROSIE", "need": ["agent mesh", "brain", "decision flow", "live mesh"],
                  "url": "https://szlholdings-rosie.hf.space", "blurb": "Brain-jack mesh — live PURIQ decision flow."},
    "a11oy":     {"organ": "Gate / a11oy.code router", "need": ["router", "llm", "governance", "gate", "reason"],
                  "url": "https://szlholdings-a11oy.hf.space", "blurb": "The governed agentic execution fabric + 7-tier router."},
}

WELCOME_TEXT = (
    "Welcome — I am CHASKI, the messenger. In one breath: SZL is a governed "
    "agentic anatomy. Twelve organs decide, halt, record and act under one master "
    "formula P(x,t), 13-axis gated and receipt-chained. Tell me what you need and "
    "I will run you to the right flagship."
)

# In-process onboarding session store and heatmap counters.
_SESSIONS: dict[str, dict[str, Any]] = {}
_HEATMAP: dict[str, int] = {"welcome": 0, "onboard_start": 0, "onboard_step": 0,
                            "quickstart": 0, "routed": 0, "backpressure_shed": 0}
_ROUTE_COUNTS: dict[str, int] = {k: 0 for k in FLAGSHIPS}

ONBOARD_STEPS = [
    {"id": "need", "prompt": "What do you want to do? (e.g. 'sync data', 'secure agents', 'fly a drone', 'route an LLM')"},
    {"id": "depth", "prompt": "Do you want a quickstart or the full deployment path?"},
    {"id": "route", "prompt": "Routing you to your flagship now."},
]


def _chaski_factor(backpressure: float, routable: bool, kappa: float = 0.35) -> float:
    """Doctrine v13 §2.1: exp(-kappa*backpressure) * 1[routable], clamped to [0,1]."""
    if not routable:
        return 0.0
    val = math.exp(-max(0.0, kappa) * max(0.0, backpressure))
    return max(0.0, min(1.0, val))


def _route_for_need(need: str) -> tuple[str | None, float]:
    """Score each flagship by keyword overlap; return (best_flagship, confidence)."""
    need_l = (need or "").lower()
    best, best_score = None, 0
    for fk, fv in FLAGSHIPS.items():
        score = sum(1 for kw in fv["need"] if kw in need_l)
        if fk in need_l:
            score += 2
        if score > best_score:
            best, best_score = fk, score
    conf = min(1.0, best_score / 3.0) if best else 0.0
    return best, conf


def register(app, ns: str = "a11oy") -> None:
    """Register CHASKI routes on the given FastAPI app under /api/{ns}/chaski/*."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    dag = get_dag("chaski", ns)
    base = f"/api/{ns}/chaski"

    @app.get(base + "/welcome")
    async def chaski_welcome() -> JSONResponse:
        _HEATMAP["welcome"] += 1
        receipt = dag.emit("welcome", {"surface": "first-touch"})
        return JSONResponse({
            "organ": "CHASKI",
            "gloss": "messenger / relay-runner (Quechua chaski; relay-station chaskiwasi)",
            "doctrine": "v13 §2.1",
            "welcome": WELCOME_TEXT,
            "factor": "Chaski(a) = exp(-kappa*backpressure)*1[routable] in [0,1]",
            "flagships": {k: {"organ": v["organ"], "blurb": v["blurb"], "url": v["url"]}
                          for k, v in FLAGSHIPS.items()},
            "khipu_receipt": receipt,
        })

    @app.get(base + "/onboard/start")
    async def chaski_onboard_start() -> JSONResponse:
        _HEATMAP["onboard_start"] += 1
        sid = uuid.uuid4().hex[:12]
        _SESSIONS[sid] = {"step": 0, "started": time.time(), "answers": {}}
        receipt = dag.emit("onboard.start", {"session": sid})
        return JSONResponse({
            "organ": "CHASKI",
            "session_id": sid,
            "step": ONBOARD_STEPS[0],
            "total_steps": len(ONBOARD_STEPS),
            "khipu_receipt": receipt,
        })

    @app.post(base + "/onboard/step")
    async def chaski_onboard_step(request: Request) -> JSONResponse:
        _HEATMAP["onboard_step"] += 1
        try:
            body = await request.json()
        except Exception:
            body = {}
        sid = body.get("session_id")
        answer = body.get("answer", "")
        backpressure = float(body.get("backpressure", 0.0) or 0.0)
        sess = _SESSIONS.get(sid)
        if not sess:
            return JSONResponse({"error": "unknown or expired session_id"}, status_code=404)

        step_idx = sess["step"]
        step = ONBOARD_STEPS[step_idx]
        sess["answers"][step["id"]] = answer

        # Reception admissibility gate (Doctrine v13 §2.1).
        routed_flagship, conf = _route_for_need(
            sess["answers"].get("need", "") + " " + str(answer))
        routable = routed_flagship is not None
        factor = _chaski_factor(backpressure, routable)
        if factor == 0.0 and not routable:
            _HEATMAP["backpressure_shed"] += 0  # routability failure, not backpressure
        if backpressure > 0 and factor < 1.0:
            _HEATMAP["backpressure_shed"] += 1

        sess["step"] = step_idx + 1
        done = sess["step"] >= len(ONBOARD_STEPS)
        result: dict[str, Any] = {
            "organ": "CHASKI",
            "session_id": sid,
            "chaski_factor": round(factor, 6),
            "routable": routable,
        }
        if done and routed_flagship:
            _ROUTE_COUNTS[routed_flagship] += 1
            _HEATMAP["routed"] += 1
            fv = FLAGSHIPS[routed_flagship]
            result.update({
                "complete": True,
                "routed_to": routed_flagship,
                "route_confidence": round(conf, 3),
                "flagship": {"organ": fv["organ"], "url": fv["url"], "blurb": fv["blurb"]},
            })
        else:
            result.update({"complete": False, "next_step": ONBOARD_STEPS[sess["step"]]
                           if not done else None})
        receipt = dag.emit("onboard.step", {"session": sid, "step": step["id"],
                                            "factor": round(factor, 6),
                                            "routed_to": result.get("routed_to")})
        result["khipu_receipt"] = receipt
        return JSONResponse(result)

    @app.get(base + "/quickstart")
    async def chaski_quickstart(flagship: str = "a11oy") -> JSONResponse:
        _HEATMAP["quickstart"] += 1
        fk = flagship if flagship in FLAGSHIPS else "a11oy"
        fv = FLAGSHIPS[fk]
        cards = {
            "a11oy": ["Open /code", "Paste a query + 13-axis score vector", "Watch it route, then re-derive the replay hash"],
            "amaru": ["Open /api/health", "POST a multi-source delta", "Read back the hash-verified receipt"],
            "sentra": ["Trip a tripwire (T01-T10)", "Watch HUKLLA halt", "Inspect the receipt chain"],
            "killinchu": ["Open the geofence map", "Submit a flight plan", "Confirm the geofence factor gates it"],
            "rosie": ["Open the brain-jack mesh", "Trigger a decision", "Watch the PURIQ flow live"],
        }
        receipt = dag.emit("quickstart", {"flagship": fk})
        return JSONResponse({
            "organ": "CHASKI", "flagship": fk, "blurb": fv["blurb"], "url": fv["url"],
            "steps": cards.get(fk, cards["a11oy"]), "khipu_receipt": receipt,
        })

    @app.get(base + "/heatmap")
    async def chaski_heatmap() -> JSONResponse:
        receipt = dag.emit("heatmap.read", {})
        total = max(1, _HEATMAP["welcome"])
        return JSONResponse({
            "organ": "CHASKI",
            "first_touch_events": dict(_HEATMAP),
            "route_distribution": dict(_ROUTE_COUNTS),
            "onboarding_completion_rate": round(_HEATMAP["routed"] / total, 4),
            "khipu_depth": dag.depth(),
            "khipu_head": dag.head(),
            "khipu_receipt": receipt,
        })

    print(f"[{ns}] szl_chaski routes registered (organ=CHASKI, reception)", flush=True)
