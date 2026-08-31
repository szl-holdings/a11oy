# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
# Doctrine v11 LOCKED 749/14/163 · Λ Conjecture 1 · SLSA L1 honest · ADDITIVE only
"""
conduction_aphasia.py — Conduction-Aphasia Detector for a11oy.

Hickok state feedback control architecture (Neuron 2011):
  DOI 10.1016/j.neuron.2011.01.019
  Hickok, Houde, Rong — Sensorimotor integration in speech processing:
    Computational basis and neural organization. Neuron 69, 407-422.

Mechanism:
  1. Before any agent action, the PAC-Bayes Governance Head at /api/a11oy/v4/predict
     produces a predicted sensory consequence (the forward model).
  2. After the action runs, we capture the actual sensory consequence (what happened).
  3. Compute delta = ||predicted − actual|| in a defined metric space.
  4. Sign delta into the Khipu receipt.
  5. If delta exceeds τ across N consecutive ticks → fire a CONDUCTION_ALERT receipt.
     This is the analog of conduction aphasia: motor plans intact, outputs may look fine,
     but the internal-loop check is broken.

Lutar anchor: A37 InternalFeedbackIntegrity

ADDITIVE: call register(app, ns="a11oy") from serve.py BEFORE the SPA catch-all.
Never modifies existing routes. try/except-guarded from the caller side.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

try:
    from fastapi import FastAPI, Query, Request
    from fastapi.responses import HTMLResponse, JSONResponse
except Exception:
    FastAPI = Query = Request = HTMLResponse = JSONResponse = None  # type: ignore

try:
    import szl_dsse as _dsse
except Exception:
    _dsse = None  # type: ignore

# ---------------------------------------------------------------------------
# Constants — Doctrine v11 LOCKED
# ---------------------------------------------------------------------------
DOCTRINE_V = "11"
LUTAR_ANCHOR = "A37_InternalFeedbackIntegrity"
NEURO_CITATION = {
    "doi": "10.1016/j.neuron.2011.01.019",
    "label": "Hickok, Houde, Rong 2011 — Sensorimotor integration: state feedback control",
    "full": (
        "Hickok, G., Houde, J., & Rong, F. (2011). Sensorimotor integration in speech "
        "processing: Computational basis and neural organization. Neuron, 69(3), 407–422."
    ),
}
DUAL_STREAM_CITATION = {
    "doi": "10.1038/nrn2113",
    "label": "Hickok & Poeppel 2007 — The cortical organization of speech processing",
}

DEFAULT_THRESHOLD_TAU = 0.30
DEFAULT_WINDOW_N = 3          # consecutive breaches to fire CONDUCTION_ALERT
RECEIPT_RING_SIZE = 200       # in-memory ring buffer

ALERT_NORMAL = "normal"
ALERT_WATCHING = "watching"
ALERT_CONDUCTION = "conduction_alert"


# ---------------------------------------------------------------------------
# In-process state
# ---------------------------------------------------------------------------

class _ConductionState:
    def __init__(self, tau: float = DEFAULT_THRESHOLD_TAU, window: int = DEFAULT_WINDOW_N) -> None:
        self.threshold_tau: float = float(tau)
        self.window_size: int = int(window)
        self._breach_streak: int = 0
        self._current_alert: str = ALERT_NORMAL
        self._last_alert_at: Optional[str] = None
        self._receipts: Deque[Dict[str, Any]] = deque(maxlen=RECEIPT_RING_SIZE)
        self._breach_count_24h: int = 0
        self._24h_window_start: float = time.time()

    def observe(self, tick_id: str, predicted_sensory: Any, actual_sensory: Any,
                metric: str = "cosine") -> Dict[str, Any]:
        delta = _compute_delta(predicted_sensory, actual_sensory, metric)
        breach = delta > self.threshold_tau
        if breach:
            self._breach_streak += 1
            self._update_24h_breach_count()
        else:
            self._breach_streak = 0

        if self._breach_streak >= self.window_size:
            alert_level = ALERT_CONDUCTION
            self._current_alert = ALERT_CONDUCTION
            self._last_alert_at = _iso()
        elif self._breach_streak >= 1:
            alert_level = ALERT_WATCHING
            self._current_alert = ALERT_WATCHING
        else:
            alert_level = ALERT_NORMAL
            self._current_alert = ALERT_NORMAL

        receipt = _build_receipt(
            tick_id=tick_id, predicted_sensory=predicted_sensory,
            actual_sensory=actual_sensory, delta=float(delta), metric=metric,
            threshold_tau=self.threshold_tau, breach=breach, alert_level=alert_level,
            consecutive_breaches=self._breach_streak,
        )
        self._receipts.appendleft(receipt)
        return receipt

    def status(self) -> Dict[str, Any]:
        return {
            "window_size": self.window_size,
            "threshold_tau": self.threshold_tau,
            "recent_breaches": [r for r in list(self._receipts)[:10] if r.get("breach")],
            "current_alert_level": self._current_alert,
            "last_alert_at": self._last_alert_at,
            "consecutive_breaches": self._breach_streak,
            "breaches_24h": self._get_24h_breach_count(),
            "doctrine_v": DOCTRINE_V,
            "lutar_anchor": LUTAR_ANCHOR,
            "neuro_citation": NEURO_CITATION,
        }

    def receipts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(self._receipts)[:limit]

    def _update_24h_breach_count(self) -> None:
        now = time.time()
        if now - self._24h_window_start > 86400:
            self._breach_count_24h = 1
            self._24h_window_start = now
        else:
            self._breach_count_24h += 1

    def _get_24h_breach_count(self) -> int:
        if time.time() - self._24h_window_start > 86400:
            return 0
        return self._breach_count_24h


_STATE = _ConductionState()


def get_state() -> _ConductionState:
    return _STATE


def reset_state(tau: float = DEFAULT_THRESHOLD_TAU, window: int = DEFAULT_WINDOW_N) -> None:
    global _STATE
    _STATE = _ConductionState(tau=tau, window=window)


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------

def _to_vec(x: Any) -> List[float]:
    if isinstance(x, list) and all(isinstance(v, (int, float)) for v in x):
        return [float(v) for v in x]
    if isinstance(x, dict):
        return [float(v) for v in sorted(x.values()) if isinstance(v, (int, float))]
    if isinstance(x, (int, float)):
        return [float(x)]
    if isinstance(x, str):
        h = int(hashlib.sha256(x.encode()).hexdigest(), 16)
        return [float((h >> (i * 8)) & 0xFF) / 255.0 for i in range(8)]
    raw = json.dumps(x, sort_keys=True, default=str).encode()
    h = int(hashlib.sha256(raw).hexdigest(), 16)
    return [float((h >> (i * 8)) & 0xFF) / 255.0 for i in range(8)]


def _l2_delta(a: List[float], b: List[float]) -> float:
    n = max(len(a), len(b))
    a = (a + [0.0] * n)[:n]
    b = (b + [0.0] * n)[:n]
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _cosine_delta(a: List[float], b: List[float]) -> float:
    n = max(len(a), len(b))
    a = (a + [0.0] * n)[:n]
    b = (b + [0.0] * n)[:n]
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0 if mag_a == mag_b == 0 else 1.0
    return 1.0 - dot / (mag_a * mag_b)


def _hash_hamming_delta(predicted: Any, actual: Any) -> float:
    def _sha_bits(x: Any) -> str:
        raw = json.dumps(x, sort_keys=True, default=str).encode()
        h = hashlib.sha256(raw).hexdigest()
        return bin(int(h, 16))[2:].zfill(256)
    bits_p = _sha_bits(predicted)
    bits_a = _sha_bits(actual)
    return sum(p != a for p, a in zip(bits_p, bits_a)) / 256.0


def _compute_delta(predicted: Any, actual: Any, metric: str) -> float:
    metric = metric.lower()
    if metric == "hash_hamming":
        return _hash_hamming_delta(predicted, actual)
    vec_p = _to_vec(predicted)
    vec_a = _to_vec(actual)
    if metric == "l2":
        return _l2_delta(vec_p, vec_a)
    return _cosine_delta(vec_p, vec_a)


# ---------------------------------------------------------------------------
# Receipt construction + signing
# ---------------------------------------------------------------------------

def _sha256_repr(x: Any) -> str:
    raw = json.dumps(x, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_id(tick_id: str, ts: str) -> str:
    raw = f"conduction:{tick_id}:{ts}".encode()
    return "cr_" + hashlib.sha256(raw).hexdigest()[:24]


def _build_receipt(tick_id, predicted_sensory, actual_sensory, delta, metric,
                   threshold_tau, breach, alert_level, consecutive_breaches):
    ts = _iso()
    rid = _receipt_id(tick_id, ts)
    receipt: Dict[str, Any] = {
        "receipt_id": rid,
        "kind": "conduction_observation",
        "tick_id": tick_id,
        "predicted_hash": _sha256_repr(predicted_sensory),
        "actual_hash": _sha256_repr(actual_sensory),
        "delta": delta,
        "metric": metric,
        "threshold_tau": threshold_tau,
        "breach": breach,
        "alert_level": alert_level,
        "consecutive_breaches": consecutive_breaches,
        "doctrine_v": DOCTRINE_V,
        "neuro_citation": NEURO_CITATION,
        "lutar_anchor": LUTAR_ANCHOR,
        "signed_by": "yachay",
        "sig": "UNSIGNED",
        "ts": ts,
    }
    if _dsse is not None:
        try:
            env = _dsse.sign_payload(receipt)
            receipt["sig"] = env.get("signatures", [{}])[0].get("sig", "UNSIGNED")
            receipt["dsse_envelope"] = env
            receipt["_signing"] = "REAL" if env.get("signed") else "UNSIGNED"
        except Exception as e:
            receipt["sig"] = f"UNSIGNED: {e}"
            receipt["_signing"] = "UNSIGNED"
    else:
        receipt["sig"] = "UNSIGNED — szl_dsse not available"
        receipt["_signing"] = "UNSIGNED"
    return receipt


# ---------------------------------------------------------------------------
# FastAPI router registration
# ---------------------------------------------------------------------------

def register(app: Any, ns: str = "a11oy") -> Dict[str, Any]:
    """Mount Conduction-Aphasia Detector endpoints. ADDITIVE only."""
    base = f"/api/{ns}/v4/conduction"

    @app.post(f"{base}/observe", tags=["conduction"])
    async def conduction_observe(request: Request) -> JSONResponse:
        """Record one predicted→actual observation. Body: {tick_id, predicted_sensory,
        actual_sensory, metric: l2|cosine|hash_hamming}"""
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse({"error": f"Invalid JSON: {e}"}, status_code=422)
        tick_id = str(body.get("tick_id") or f"tick_{int(time.time()*1000)}")
        predicted = body.get("predicted_sensory", {})
        actual = body.get("actual_sensory", {})
        metric = str(body.get("metric", "cosine")).lower()
        if metric not in ("l2", "cosine", "hash_hamming"):
            metric = "cosine"
        receipt = _STATE.observe(tick_id, predicted, actual, metric)
        return JSONResponse({
            "delta": receipt["delta"],
            "threshold": receipt["threshold_tau"],
            "breach": receipt["breach"],
            "alert_level": receipt["alert_level"],
            "receipt_id": receipt["receipt_id"],
            "consecutive_breaches": receipt["consecutive_breaches"],
            "doctrine_v": DOCTRINE_V,
            "lutar_anchor": LUTAR_ANCHOR,
        })

    @app.get(f"{base}/status", tags=["conduction"])
    async def conduction_status() -> JSONResponse:
        """Return current Conduction gate state."""
        return JSONResponse(_STATE.status())

    @app.get(f"{base}/receipts", tags=["conduction"])
    async def conduction_receipts(limit: int = Query(default=20, le=200)) -> JSONResponse:
        """Return last N conduction receipts (signed, Khipu-compatible)."""
        recs = _STATE.receipts(limit)
        return JSONResponse({"receipts": recs, "count": len(recs),
                             "lutar_anchor": LUTAR_ANCHOR, "doctrine_v": DOCTRINE_V})

    @app.post(f"{base}/demo", tags=["conduction"])
    async def conduction_demo() -> JSONResponse:
        """Inject a synthetic high-delta observation (DEMO ONLY)."""
        predicted = [1.0, 0.0, 0.0, 0.5]
        actual = [0.0, 1.0, 1.0, 0.0]
        receipt = _STATE.observe("demo_tick_synthetic", predicted, actual, "cosine")
        return JSONResponse({
            "demo": True,
            "note": "DEMO — synthetic predicted/actual pair injected. Not a real agent tick.",
            "delta": receipt["delta"],
            "breach": receipt["breach"],
            "alert_level": receipt["alert_level"],
            "receipt_id": receipt["receipt_id"],
            "doctrine_v": DOCTRINE_V,
        })

    @app.get("/conduction", tags=["conduction"], response_class=HTMLResponse)
    async def conduction_html() -> HTMLResponse:
        return HTMLResponse(_CONDUCTION_HTML.replace("__NS__", ns))

    return {
        "observe": f"POST {base}/observe",
        "status": f"GET {base}/status",
        "receipts": f"GET {base}/receipts",
        "demo": f"POST {base}/demo",
        "ui": "/conduction",
        "lutar_anchor": LUTAR_ANCHOR,
        "doctrine_v": DOCTRINE_V,
    }


# ---------------------------------------------------------------------------
# /conduction HTML
# ---------------------------------------------------------------------------

_CONDUCTION_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conduction-Aphasia Detector · a11oy</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0a0a0a;--card:#111;--border:#222;--accent:#00ff88;--warn:#ffaa00;
    --danger:#ff3333;--dim:#666;--text:#e0e0e0;--mono:'JetBrains Mono','Fira Code','Courier New',monospace;
  }
  body{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;min-height:100vh;padding:20px}
  h1{color:var(--accent);font-size:20px;letter-spacing:2px;margin-bottom:4px}
  .subtitle{color:var(--dim);font-size:11px;margin-bottom:24px}
  .big3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}
  .big-card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:16px;text-align:center}
  .big-label{color:var(--dim);font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}
  .big-value{font-size:36px;font-weight:700;letter-spacing:1px}
  .big-value.normal{color:var(--accent)}
  .big-value.watching{color:var(--warn)}
  .big-value.conduction_alert{color:var(--danger);animation:pulse 1s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
  .panel{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:16px}
  .panel-title{color:var(--accent);font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;border-bottom:1px solid var(--border);padding-bottom:8px}
  .diagram-wrap{overflow:auto;padding:8px}
  svg text{font-family:var(--mono);font-size:10px}
  .receipt-table{width:100%;border-collapse:collapse;font-size:11px}
  .receipt-table th{color:var(--dim);text-align:left;padding:4px 6px;border-bottom:1px solid var(--border);font-weight:normal;letter-spacing:1px}
  .receipt-table td{padding:4px 6px;border-bottom:1px solid #1a1a1a;white-space:nowrap}
  .breach-yes{color:var(--danger)}
  .breach-no{color:var(--accent)}
  .al-normal{color:var(--accent)}
  .al-watching{color:var(--warn)}
  .al-conduction_alert{color:var(--danger)}
  .demo-btn{background:transparent;border:1px solid var(--warn);color:var(--warn);
    font-family:var(--mono);font-size:12px;padding:8px 20px;border-radius:3px;
    cursor:pointer;letter-spacing:1px;transition:.2s}
  .demo-btn:hover{background:var(--warn);color:#000}
  .demo-note{color:var(--dim);font-size:10px;margin-top:6px}
  .footer{border-top:1px solid var(--border);margin-top:24px;padding-top:12px;
    color:var(--dim);font-size:10px;line-height:1.8}
  .footer a{color:var(--dim);text-decoration:none}
  .footer a:hover{color:var(--accent)}
</style>
</head>
<body>
<h1>&#9711; CONDUCTION-APHASIA DETECTOR</h1>
<div class="subtitle">a11oy &middot; A37 InternalFeedbackIntegrity &middot; Hickok state feedback control architecture &middot; Doctrine v11</div>

<div class="big3">
  <div class="big-card">
    <div class="big-label">Current Alert Level</div>
    <div class="big-value normal" id="b-alert">&mdash;</div>
  </div>
  <div class="big-card">
    <div class="big-label">Consecutive Breaches</div>
    <div class="big-value normal" id="b-streak">&mdash;</div>
  </div>
  <div class="big-card">
    <div class="big-label">Breaches (24h)</div>
    <div class="big-value normal" id="b-24h">&mdash;</div>
  </div>
</div>

<div class="row2">
  <div class="panel">
    <div class="panel-title">Hickok Dual-Stream + Internal Feedback Loop</div>
    <div class="diagram-wrap">
      <svg width="460" height="340" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#666"/>
          </marker>
          <marker id="arr-hl" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#00ff88"/>
          </marker>
          <marker id="arr-red" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#ff3333"/>
          </marker>
        </defs>
        <rect x="110" y="10" width="240" height="32" rx="3" fill="#111" stroke="#444"/>
        <text x="230" y="31" fill="#888" text-anchor="middle">SPECTROTEMPORAL INPUT</text>
        <rect x="110" y="66" width="240" height="32" rx="3" fill="#111" stroke="#444"/>
        <text x="230" y="87" fill="#888" text-anchor="middle">PHONOLOGICAL NETWORK</text>
        <line x1="230" y1="42" x2="230" y2="66" stroke="#444" stroke-width="1.5" marker-end="url(#arr)"/>
        <line x1="170" y1="98" x2="130" y2="118" stroke="#444" stroke-width="1.5" marker-end="url(#arr)"/>
        <line x1="290" y1="98" x2="330" y2="118" stroke="#444" stroke-width="1.5" marker-end="url(#arr)"/>
        <rect x="10" y="118" width="170" height="70" rx="3" fill="#0d1a12" stroke="#2a5a3a"/>
        <text x="95" y="137" fill="#2a8a4a" text-anchor="middle" font-size="9">DORSAL STREAM</text>
        <text x="95" y="152" fill="#666" text-anchor="middle">Sensorimotor Interface</text>
        <text x="95" y="167" fill="#666" text-anchor="middle">Area Spt (PAC-Bayes)</text>
        <text x="95" y="180" fill="#666" text-anchor="middle">/api/a11oy/v4/predict</text>
        <rect x="280" y="118" width="170" height="70" rx="3" fill="#0d0d1a" stroke="#2a2a5a"/>
        <text x="365" y="137" fill="#2a2a8a" text-anchor="middle" font-size="9">VENTRAL STREAM</text>
        <text x="365" y="152" fill="#666" text-anchor="middle">Lexical Interface</text>
        <text x="365" y="167" fill="#666" text-anchor="middle">pMTG / pITS</text>
        <text x="365" y="180" fill="#666" text-anchor="middle">meaning / comprehension</text>
        <rect x="110" y="210" width="240" height="38" rx="3" fill="#001a0a" stroke="#00ff88" stroke-width="2"/>
        <text x="230" y="226" fill="#00ff88" text-anchor="middle" font-size="10">FORWARD MODEL (predicted sensory)</text>
        <text x="230" y="241" fill="#00aa55" text-anchor="middle" font-size="9">Lambda predicted consequence before action</text>
        <line x1="95" y1="188" x2="170" y2="210" stroke="#2a5a3a" stroke-width="1.5" marker-end="url(#arr)"/>
        <rect x="110" y="268" width="240" height="38" rx="3" fill="#1a0000" stroke="#ff3333" stroke-width="2"/>
        <text x="230" y="284" fill="#ff3333" text-anchor="middle" font-size="10">CONDUCTION GATE (A37)</text>
        <text x="230" y="299" fill="#aa2222" text-anchor="middle" font-size="9">||predicted - actual|| &gt; tau  ALERT</text>
        <path d="M 230 248 L 230 268" stroke="#00ff88" stroke-width="2" marker-end="url(#arr-hl)"/>
        <path d="M 450 283 L 350 283" stroke="#ff3333" stroke-width="2" stroke-dasharray="4,3" marker-end="url(#arr-red)"/>
        <text x="452" y="280" fill="#ff3333" font-size="9">actual</text>
        <text x="452" y="290" fill="#ff3333" font-size="9">sensory</text>
        <text x="14" y="260" fill="#00ff88" font-size="9">internal</text>
        <text x="14" y="272" fill="#00ff88" font-size="9">feedback</text>
        <text x="14" y="284" fill="#00ff88" font-size="9">loop</text>
        <path d="M 55 270 L 110 283" stroke="#00ff88" stroke-width="1" stroke-dasharray="3,2" marker-end="url(#arr-hl)"/>
      </svg>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">Demo Divergence Injector</div>
    <p style="color:#666;margin-bottom:12px;font-size:11px">
      Inject a synthetic predicted&rarr;actual mismatch to demonstrate the Conduction Alert.
      Predicted: [1.0, 0.0, 0.0, 0.5] &middot; Actual: [0.0, 1.0, 1.0, 0.0]
    </p>
    <button class="demo-btn" onclick="injectDemo()">&#9654; Trigger Demo Divergence</button>
    <div class="demo-note">&#9888; DEMO ONLY &mdash; clearly labelled synthetic pair, not a real agent tick.</div>
    <div id="demo-result" style="margin-top:12px;font-size:11px;color:#666"></div>

    <div style="margin-top:20px">
      <div class="panel-title" style="margin-top:0">Gate Parameters</div>
      <table style="font-size:11px;width:100%">
        <tr><td style="color:#666;padding:3px 0">Threshold &tau;</td><td id="p-tau" style="color:#e0e0e0">&mdash;</td></tr>
        <tr><td style="color:#666;padding:3px 0">Window N</td><td id="p-window" style="color:#e0e0e0">&mdash;</td></tr>
        <tr><td style="color:#666;padding:3px 0">Last Alert</td><td id="p-last-alert" style="color:#e0e0e0">&mdash;</td></tr>
        <tr><td style="color:#666;padding:3px 0">Lutar anchor</td><td style="color:#00ff88">A37 InternalFeedbackIntegrity</td></tr>
        <tr><td style="color:#666;padding:3px 0">Doctrine</td><td style="color:#888">v11 LOCKED 749/14/163</td></tr>
      </table>
    </div>
  </div>
</div>

<div class="panel" style="margin-bottom:16px">
  <div class="panel-title">Live Receipt Tail (last 20 &middot; auto-refresh 5s)
    <span id="status-ts" style="float:right;font-size:10px;color:#444">refreshing&hellip;</span>
  </div>
  <table class="receipt-table">
    <thead>
      <tr>
        <th>receipt_id</th><th>tick_id</th><th>delta</th><th>metric</th>
        <th>breach</th><th>alert_level</th><th>consecutive</th><th>ts</th>
      </tr>
    </thead>
    <tbody id="receipt-tbody">
      <tr><td colspan="8" style="color:#444;text-align:center;padding:12px">No receipts yet &mdash; waiting for observations&hellip;</td></tr>
    </tbody>
  </table>
</div>

<div class="footer">
  <div>A37 InternalFeedbackIntegrity &middot; Citation: Hickok, Houde, Rong 2011, Neuron 69:407&ndash;422 &middot; <a href="https://doi.org/10.1016/j.neuron.2011.01.019">DOI 10.1016/j.neuron.2011.01.019</a></div>
  <div>Dual-stream: Hickok &amp; Poeppel 2007, Nat Rev Neurosci 8:393&ndash;402 &middot; <a href="https://doi.org/10.1038/nrn2113">DOI 10.1038/nrn2113</a></div>
  <div>Doctrine v11 LOCKED &middot; 749 declarations / 14 axioms / 163 sorries &middot; &Lambda; = Conjecture 1 (NOT a theorem) &middot; SLSA L1 honest &middot; Sovereign-default</div>
  <div style="margin-top:4px">&copy; 2026 SZL Holdings &middot; Authored by Yachay (CTO) &middot; Co-Authored-By: Perplexity Computer Agent</div>
</div>

<script>
const BASE = '/api/__NS__/v4/conduction';
function alertClass(l){return l==='conduction_alert'?'conduction_alert':l==='watching'?'watching':'normal'}
function alLabel(l){return l==='conduction_alert'?'CONDUCTION_ALERT':l==='watching'?'WATCHING':'normal'}
async function fetchStatus(){
  try{
    const d=await(await fetch(BASE+'/status')).json();
    const al=d.current_alert_level||'normal';
    const el=document.getElementById('b-alert');
    el.textContent=alLabel(al); el.className='big-value '+alertClass(al);
    document.getElementById('b-streak').textContent=d.consecutive_breaches??0;
    document.getElementById('b-24h').textContent=d.breaches_24h??0;
    document.getElementById('p-tau').textContent=d.threshold_tau??'--';
    document.getElementById('p-window').textContent=d.window_size??'--';
    document.getElementById('p-last-alert').textContent=d.last_alert_at||'none';
    document.getElementById('status-ts').textContent='updated '+new Date().toLocaleTimeString();
  }catch(e){console.error(e)}
}
async function fetchReceipts(){
  try{
    const d=await(await fetch(BASE+'/receipts?limit=20')).json();
    const rows=d.receipts||[];
    const tb=document.getElementById('receipt-tbody');
    if(!rows.length){tb.innerHTML='<tr><td colspan="8" style="color:#444;text-align:center;padding:12px">No receipts yet</td></tr>';return}
    function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
    tb.innerHTML=rows.map(r=>`<tr>
      <td style="color:#555">${esc((r.receipt_id||'').slice(0,18))}...</td>
      <td>${esc(r.tick_id||'')}</td>
      <td>${typeof r.delta==='number'?r.delta.toFixed(4):'--'}</td>
      <td>${esc(r.metric||'')}</td>
      <td class="${r.breach?'breach-yes':'breach-no'}">${r.breach?'YES':'no'}</td>
      <td class="al-${esc(r.alert_level||'normal')}">${esc(r.alert_level||'')}</td>
      <td>${r.consecutive_breaches??0}</td>
      <td style="color:#555">${(r.ts||'').slice(11,19)}</td>
    </tr>`).join('');
  }catch(e){console.error(e)}
}
async function injectDemo(){
  const btn=document.querySelector('.demo-btn');
  btn.disabled=true; btn.textContent='... injecting ...';
  try{
    const d=await(await fetch(BASE+'/demo',{method:'POST'})).json();
    document.getElementById('demo-result').innerHTML=
      `<span style="color:#ffaa00">DEMO injected</span> delta=${d.delta?.toFixed(4)} breach=${d.breach} alert=${d.alert_level} id=${d.receipt_id}`;
    await fetchStatus(); await fetchReceipts();
  }catch(e){document.getElementById('demo-result').textContent='Error: '+e}
  finally{btn.disabled=false;btn.textContent='Trigger Demo Divergence'}
}
function refresh(){fetchStatus();fetchReceipts()}
refresh(); setInterval(refresh,5000);
</script>
</body>
</html>"""
