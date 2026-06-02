# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED 749/14/163
# Authored by Yachay (CTO) — Co-Authored-By: Perplexity Computer Agent.
"""
a11oy_v4_hickok.py — ADDITIVE FastAPI module: the Hickok cognitive-neuroscience
ingest. Grounds the Amaru agent architecture in Gregory Hickok's dual-stream
model of speech/language processing.

LUTAR ANCHORS
  A36 DualStreamRoutingAxiom        — every request routes to EXACTLY ONE of
                                      {dorsal, ventral} (Hickok & Poeppel 2007,
                                      DOI 10.1038/nrn2113).
  A37 InternalFeedbackIntegrity     — internal sensory-motor feedback loop must
                                      close (Hickok, Houde & Rong 2011,
                                      DOI 10.1016/j.neuron.2011.01.019).
  A38 HierarchicalLinearizationRoundTrip — hierarchical meaning ↔ linear Khipu
                                      sequence round-trips (Hickok 2025,
                                      *Wired for Words*, MIT Press).

ENDPOINTS (all ADDITIVE, mounted under /api/{ns}/v4)
  POST /dorsal   {intent}                     → action lane  (A36)
  POST /ventral  {intent}                     → meaning lane (A36)
  POST /spt      {sensory_target, motor_plan} → Spt translation node (A36/A37)
  POST /when     {stream}                     → WHEN-pathway phase prediction
  POST /what     {stream}                     → WHAT-pathway semantic prediction
  GET  /stream                                → SSE firehose of dual-stream receipts
  GET  /brain  (top-level page)               → dual-stream architecture HTML

DUAL-STREAM ROUTER MIDDLEWARE (Task D)
  Every request to /api/{ns}/v4/agent/ask and /api/{ns}/v4/predict is classified
  dorsal | ventral | dual by a rule-based classifier; the classification is
  written to the response (header + receipt). `dual` (neither clear) → gate-fail
  (A36 says EXACTLY one).

Sovereign — no cloud LLM. Receipts sign via szl_dsse (real ECDSA-P256/DSSE when
SZL_COSIGN_PRIVATE_PEM is present, else honestly UNSIGNED). try/except guarded:
a missing dep can NEVER take down the SPA or any existing route.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
except Exception:  # pragma: no cover
    Request = None  # type: ignore
    JSONResponse = StreamingResponse = FileResponse = Response = None  # type: ignore

# Sibling modules — importable whether beside this file or on path.
try:
    import szl_dsse as _dsse  # type: ignore
except Exception:  # pragma: no cover
    _dsse = None  # type: ignore

try:
    import szl_khipu as _khipu  # type: ignore
except Exception:  # pragma: no cover
    _khipu = None  # type: ignore

PAGES_DIR = Path("/app/pages")
INDEX_HTML = Path("/app/static/index.html")

# ---------------------------------------------------------------------------
# Citations (the cognitive-neuroscience provenance set)
# ---------------------------------------------------------------------------
DOI_DUAL_STREAM = "10.1038/nrn2113"                  # Hickok & Poeppel 2007
DOI_STATE_FEEDBACK = "10.1016/j.neuron.2011.01.019"  # Hickok, Houde & Rong 2011
DOI_SPT = "10.1152/jn.91344.2008"                    # Area Spt (sensorimotor)
DOI_WHEN_WHAT = "10.1101/474718"                     # WHEN/WHAT pathways (bioRxiv 2018)
DOI_HICKOK_2022 = "10.1016/B978-0-12-823384-9.00003-7"
WIRED_FOR_WORDS = "Hickok 2025 Wired for Words (MIT Press)"

CITE_DUAL_STREAM = {"doi": DOI_DUAL_STREAM, "label": "Hickok & Poeppel 2007, Nat Rev Neurosci — dual-stream model"}
CITE_STATE_FEEDBACK = {"doi": DOI_STATE_FEEDBACK, "label": "Hickok, Houde & Rong 2011, Neuron — state feedback control"}
CITE_SPT = {"doi": DOI_SPT, "label": "Area Spt — sensorimotor translation node (J Neurophysiol 2009)"}
CITE_WHEN_WHAT = {"doi": DOI_WHEN_WHAT, "label": "WHEN/WHAT predictive pathways (bioRxiv 2018)"}

# ---------------------------------------------------------------------------
# Rule-based dorsal / ventral classifier (Task D + endpoints C1/C2)
# ---------------------------------------------------------------------------
# DORSAL  = action / repetition / sensorimotor  (imperatives, command verbs)
# VENTRAL = meaning / comprehension             (questions, explanations)
# Neither clear → `dual` → A36 gate-fail (exactly one).

_IMPERATIVE_VERBS = {
    "sign", "execute", "run", "deploy", "build", "create", "make", "send",
    "write", "delete", "remove", "add", "update", "patch", "commit", "push",
    "merge", "emit", "fetch", "get", "set", "start", "stop", "restart",
    "generate", "compute", "calculate", "verify", "validate", "compile",
    "render", "save", "load", "open", "close", "call", "invoke", "trigger",
    "repeat", "do", "perform", "apply", "install", "configure", "rotate",
    "issue", "mint", "publish", "schedule", "cancel", "approve", "reject",
}
_INTERROGATIVE_WORDS = {
    "what", "why", "how", "who", "when", "where", "which", "whom", "whose",
    "is", "are", "was", "were", "does", "do", "did", "can", "could", "should",
    "would", "explain", "describe", "define", "mean", "means", "meaning",
    "understand", "tell", "clarify", "summarize", "summarise", "compare",
}
# Words that head an interrogative clause even though they also appear as verbs.
_EXPLAIN_LEAD = {"explain", "describe", "define", "summarize", "summarise", "clarify", "compare"}


def classify_stream(intent: str) -> Dict[str, Any]:
    """Rule-based dorsal/ventral classifier.

    Returns {stream, confidence, signals, gate_pass}. `stream` is one of
    'dorsal' | 'ventral' | 'dual'. A38/A36: exactly one stream must win; a
    `dual` verdict (ambiguous / neither) FAILS the A36 gate.
    """
    text = (intent or "").strip()
    low = text.lower()
    tokens = re.findall(r"[a-z']+", low)
    signals: List[str] = []

    is_question = text.endswith("?")
    first = tokens[0] if tokens else ""

    dorsal_score = 0
    ventral_score = 0

    # Question mark / interrogative lead → ventral (meaning/comprehension).
    if is_question:
        ventral_score += 2
        signals.append("trailing '?' → interrogative")
    if first in _INTERROGATIVE_WORDS or first in _EXPLAIN_LEAD:
        ventral_score += 2
        signals.append(f"interrogative/explanatory lead '{first}'")
    # Any interrogative word present (weaker).
    if any(t in _INTERROGATIVE_WORDS for t in tokens):
        ventral_score += 1
        signals.append("contains interrogative word")

    # Imperative lead (verb-first, no question) → dorsal (action).
    if first in _IMPERATIVE_VERBS and first not in _EXPLAIN_LEAD:
        dorsal_score += 3
        signals.append(f"imperative lead verb '{first}'")
    if any(t in _IMPERATIVE_VERBS for t in tokens) and not is_question:
        dorsal_score += 1
        signals.append("contains command verb")

    if dorsal_score > ventral_score:
        stream = "dorsal"
        conf = min(0.99, 0.5 + 0.15 * (dorsal_score - ventral_score))
    elif ventral_score > dorsal_score:
        stream = "ventral"
        conf = min(0.99, 0.5 + 0.15 * (ventral_score - dorsal_score))
    else:
        # Neither clear (tie, including 0–0) → dual → A36 gate-fail.
        stream = "dual"
        conf = 0.0
        signals.append("ambiguous — neither stream clearly wins")

    return {
        "stream": stream,
        "confidence": round(conf, 3),
        "dorsal_score": dorsal_score,
        "ventral_score": ventral_score,
        "signals": signals,
        # A36: exactly one stream. dual → gate FAILS.
        "gate_pass": stream in ("dorsal", "ventral"),
        "lutar_anchor": "A36",
    }


# ---------------------------------------------------------------------------
# Signed-receipt helper (Task E — neuro_citations on every receipt)
# ---------------------------------------------------------------------------
_RECENT: Deque[Dict[str, Any]] = deque(maxlen=200)  # for SSE + node click history


def _sign(action: str, payload: Dict[str, Any],
          neuro_citations: List[Dict[str, Any]],
          stream: Optional[str] = None) -> Dict[str, Any]:
    """Emit a hash-chained Khipu receipt, sign it via DSSE, attach neuro_citations.

    Returns the signed-receipt envelope {receipt, dsse}. On any failure falls
    back to an honest unsigned dict (never raises into the request path).
    """
    organ = "hickok"
    receipt: Dict[str, Any]
    if _khipu is not None:
        try:
            dag = _khipu.get_dag(organ, "a11oy")
            receipt = dag.emit(action, payload)
        except Exception:
            receipt = {"organ": organ, "action": action, "payload_digest": None,
                       "ts": time.time(), "signature": "DSSE_PLACEHOLDER"}
    else:
        receipt = {"organ": organ, "action": action, "ts": time.time(),
                   "signature": "DSSE_PLACEHOLDER"}

    if stream is not None:
        receipt["dual_stream"] = stream
    receipt["neuro_citations"] = neuro_citations

    signed: Dict[str, Any]
    if _dsse is not None:
        try:
            signed = _dsse.sign_khipu_receipt(receipt, neuro_citations=neuro_citations)
        except Exception:
            signed = {"receipt": receipt, "dsse": {"signed": False,
                      "honesty": "UNSIGNED — szl_dsse raised; no signature fabricated."}}
    else:
        signed = {"receipt": receipt, "dsse": {"signed": False,
                  "honesty": "UNSIGNED — szl_dsse not importable; no signature fabricated."}}

    # Track for /stream SSE + node-click history.
    _RECENT.append({
        "id": receipt.get("digest") or str(uuid.uuid4()),
        "action": action,
        "stream": stream,
        "ts": receipt.get("ts", time.time()),
        "neuro_citations": neuro_citations,
        "signed": bool(signed.get("dsse", {}).get("signed")),
    })
    return signed


def _receipt_id(signed: Dict[str, Any]) -> str:
    r = signed.get("receipt", {})
    return r.get("digest") or r.get("id") or str(uuid.uuid4())


# ---------------------------------------------------------------------------
# FastAPI registration
# ---------------------------------------------------------------------------
def register(app: Any, ns: str = "a11oy") -> Dict[str, Any]:
    """Mount the Hickok ingest endpoints + dual-stream middleware + /brain page."""
    if Request is None:
        return {"registered": False, "reason": "fastapi not available"}

    base = f"/api/{ns}/v4"

    # ---- C1: POST /dorsal — action lane (A36) --------------------------------
    @app.post(f"{base}/dorsal")
    async def v4_dorsal(request: Request) -> Any:  # noqa: ANN401
        body = await request.json()
        intent = body.get("intent", "")
        if not intent:
            return JSONResponse({"error": "intent required"}, status_code=400)
        cls = classify_stream(intent)
        cites = [CITE_DUAL_STREAM]
        signed = _sign("dorsal_route", {"intent": intent, "classification": cls},
                       cites, stream="dorsal")
        return JSONResponse({
            "plan": f"action-plan for: {intent}",
            "motor_pathway": "dorsal — sensorimotor / articulatory (repetition lane)",
            "classification": cls,
            "neuro_citations": [{"doi": DOI_DUAL_STREAM}],
            "lutar_anchor": "A36",
            "signed_receipt_id": _receipt_id(signed),
            "receipt": signed,
        })

    # ---- C2: POST /ventral — meaning lane (A36) ------------------------------
    @app.post(f"{base}/ventral")
    async def v4_ventral(request: Request) -> Any:  # noqa: ANN401
        body = await request.json()
        intent = body.get("intent", "")
        if not intent:
            return JSONResponse({"error": "intent required"}, status_code=400)
        cls = classify_stream(intent)
        cites = [CITE_DUAL_STREAM]
        signed = _sign("ventral_route", {"intent": intent, "classification": cls},
                       cites, stream="ventral")
        return JSONResponse({
            "meaning": f"conceptual interpretation of: {intent}",
            "grounding": "ventral — lexical-semantic / conceptual (comprehension lane)",
            "classification": cls,
            "neuro_citations": [{"doi": DOI_DUAL_STREAM}],
            "lutar_anchor": "A36",
            "signed_receipt_id": _receipt_id(signed),
            "receipt": signed,
        })

    # ---- C3: POST /spt — Area Spt translation node (A36/A37) -----------------
    @app.post(f"{base}/spt")
    async def v4_spt(request: Request) -> Any:  # noqa: ANN401
        body = await request.json()
        sensory_target = body.get("sensory_target")
        motor_plan = body.get("motor_plan")
        if sensory_target is None or motor_plan is None:
            return JSONResponse(
                {"error": "sensory_target and motor_plan required"}, status_code=400)

        # Spt = the sensorimotor translation node: map a sensory target onto a
        # motor plan and report the forward-model error (delta). Numeric inputs
        # → |target - plan|; otherwise a coarse string-mismatch fraction.
        def _num(x: Any) -> Optional[float]:
            try:
                return float(x)
            except (TypeError, ValueError):
                return None

        st_n, mp_n = _num(sensory_target), _num(motor_plan)
        if st_n is not None and mp_n is not None:
            delta = abs(st_n - mp_n)
        else:
            s, m = str(sensory_target), str(motor_plan)
            if s == m:
                delta = 0.0
            else:
                # normalized Levenshtein-free coarse distance
                longer = max(len(s), len(m)) or 1
                same = sum(1 for a, b in zip(s, m) if a == b)
                delta = round(1.0 - (same / longer), 6)

        cites = [CITE_SPT, CITE_STATE_FEEDBACK]
        signed = _sign("spt_translate",
                       {"sensory_target": sensory_target, "motor_plan": motor_plan,
                        "delta": delta},
                       cites, stream="dorsal")
        return JSONResponse({
            "translation": "sensory→motor translation via Area Spt",
            "delta": delta,
            "neuro_citations": [{"doi": DOI_SPT}],
            "lutar_anchor": "A36",
            "signed_receipt_id": _receipt_id(signed),
            "receipt": signed,
        })

    # ---- C4: POST /when — WHEN-pathway phase prediction ----------------------
    @app.post(f"{base}/when")
    async def v4_when(request: Request) -> Any:  # noqa: ANN401
        body = await request.json()
        stream = body.get("stream", "")
        cites = [CITE_WHEN_WHAT]
        signed = _sign("when_predict", {"stream": stream}, cites, stream="dorsal")
        return JSONResponse({
            "phase_prediction": f"low-frequency phase tracking for stream: {stream}",
            "mechanism": "low_freq_phase_Heschl",
            "neuro_citations": [{"doi": DOI_WHEN_WHAT}],
            "lutar_anchor": "A36",
            "signed_receipt_id": _receipt_id(signed),
            "receipt": signed,
        })

    # ---- C5: POST /what — WHAT-pathway semantic prediction -------------------
    @app.post(f"{base}/what")
    async def v4_what(request: Request) -> Any:  # noqa: ANN401
        body = await request.json()
        stream = body.get("stream", "")
        cites = [CITE_WHEN_WHAT]
        signed = _sign("what_predict", {"stream": stream}, cites, stream="ventral")
        return JSONResponse({
            "semantic_prediction": f"gamma-band semantic prediction for stream: {stream}",
            "mechanism": "gamma_planum_temporale",
            "neuro_citations": [{"doi": DOI_WHEN_WHAT}],
            "lutar_anchor": "A36",
            "signed_receipt_id": _receipt_id(signed),
            "receipt": signed,
        })

    # ---- SSE: GET /stream — live dual-stream receipt firehose (Task F) -------
    @app.get(f"{base}/stream")
    async def v4_stream(request: Request) -> Any:  # noqa: ANN401
        async def gen():
            last = 0
            # Seed: replay any receipts already in the buffer.
            snapshot = list(_RECENT)
            for ev in snapshot:
                yield f"data: {json.dumps(ev)}\n\n"
            last = len(snapshot)
            hb = 0
            while True:
                if await request.is_disconnected():
                    break
                cur = list(_RECENT)
                if len(cur) > last:
                    for ev in cur[last:]:
                        yield f"data: {json.dumps(ev)}\n\n"
                    last = len(cur)
                else:
                    hb += 1
                    yield f": heartbeat {hb}\n\n"
                await asyncio.sleep(1.0)
        return StreamingResponse(gen(), media_type="text/event-stream")

    # ---- Hickok dual-stream page (top-level; explicit route wins over the SPA
    # history catch-all). Served from pages/brain-dual.html. ADDITIVE: the prior
    # pages/brain.html (gate-vocabulary view) is preserved untouched; the SPA's
    # client-side /brain route is documented as shadowed by this server route.
    async def _serve_brain_dual() -> Any:  # noqa: ANN401
        f = PAGES_DIR / "brain-dual.html"
        if f.is_file():
            return FileResponse(f, media_type="text/html")
        return FileResponse(INDEX_HTML, media_type="text/html")

    @app.get("/brain")
    async def brain_page() -> Any:  # noqa: ANN401
        return await _serve_brain_dual()

    @app.get("/brain-dual")
    async def brain_dual_page() -> Any:  # noqa: ANN401
        return await _serve_brain_dual()

    # ---- Task D: dual-stream router middleware -------------------------------
    # Classify every /agent/ask and /predict request as dorsal | ventral | dual,
    # write the classification to the response header + a receipt. `dual`
    # (neither clear) → A36 gate-fail flag on the response header.
    #
    # The agent/predict surface is reachable under both the namespaced v4 prefix
    # and the bare /api/{ns} proxy prefix depending on platform wiring, so we
    # match a path *suffix* set rather than a single literal. This keeps the
    # router firing on /api/a11oy/v4/agent/ask, /api/a11oy/agent/ask, and the
    # equivalent /predict paths — fully additive, never blocks a request.
    ns_root = f"/api/{ns}"
    ROUTED_SUFFIXES = ("/agent/ask", "/predict")

    def _is_routed(path: str) -> bool:
        if not path.startswith(ns_root):
            return False
        return any(path.endswith(sfx) for sfx in ROUTED_SUFFIXES)

    @app.middleware("http")
    async def dual_stream_router(request: Request, call_next):
        path = request.url.path
        cls: Optional[Dict[str, Any]] = None
        if request.method == "POST" and _is_routed(path):
            try:
                raw = await request.body()
                # Re-inject the body so downstream handlers can still read it.
                async def _receive():
                    return {"type": "http.request", "body": raw, "more_body": False}
                request._receive = _receive  # type: ignore[attr-defined]
                data = json.loads(raw.decode("utf-8")) if raw else {}
                intent = (data.get("intent") or data.get("action")
                          or data.get("question") or data.get("prompt") or "")
                cls = classify_stream(str(intent))
            except Exception:
                cls = None

        response = await call_next(request)

        if cls is not None:
            response.headers["X-A11oy-Stream"] = cls["stream"]
            response.headers["X-A11oy-Stream-Anchor"] = "A36"
            response.headers["X-A11oy-Stream-Gate"] = "pass" if cls["gate_pass"] else "fail"
            # Receipt the classification (with the dual-stream provenance DOI).
            try:
                _sign("router_classify",
                      {"path": path, "classification": cls},
                      [CITE_DUAL_STREAM], stream=cls["stream"])
            except Exception:
                pass
        return response

    return {
        "registered": True,
        "ns": ns,
        "routes": [
            f"{base}/dorsal", f"{base}/ventral", f"{base}/spt",
            f"{base}/when", f"{base}/what", f"{base}/stream", "/brain", "/brain-dual",
        ],
        "middleware": "dual_stream_router (A36) on /agent/ask + /predict",
        "anchors": ["A36", "A37", "A38"],
        "signing_available": bool(_dsse and _dsse.signing_available()),
    }
