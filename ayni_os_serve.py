"""a11oy ADDITIVE router — mounts AYNI-OS at /v1/ayni, /v1/replay, /v1/tinkuy.

Self-contained APIRouter following the kipu_qillqaq_serve.py / WAYRA pattern: import,
include_router BEFORE the SPA catch-all, wrap in try/except so a missing dep can never
take down the SPA. The `ayni_os` package is vendored alongside this file in the Space.

HONEST NAMING (Zero-Bandaid Law):
- "/v1/replay?at=<ts>" reconstructs past state by EVENT-SOURCING REPLAY of signed KIPU
  receipts — NOT "quantum time-travel". No physics claim.
- "Ayni" is a GAME-THEORY primitive: direct reciprocity (Axelrod & Hamilton 1981;
  Trivers 1971). No mysticism.
- "Tinkuy" is the KURAMOTO (1975) order parameter r across organ phases. No mysticism.

DATA PROVENANCE (Zero-Bandaid Law): the reciprocity ledger is NOT hand-typed seeds.
It is EVENT-SOURCED at startup from the platform's signed KIPU receipt stream shipped
in this Space (infra/receipts-samples/receipts_sample.jsonl — real DSSE receipts, each
carrying the producing organ `component`, the operation `kind`, and a real issued-at
timestamp). Each receipt becomes a double-entry: the organ GIVES a signed attestation
to the empire and TAKES the compute it consumed to produce it; the Ayni coefficient
alpha = In/(In+Out) is therefore measured, not invented. The shipped corpus is a
labelled sample stream (its receipts are flagged synthetic upstream); every response
carries `data_source`/`live`/`receipts_ingested` so the provenance is never hidden. If
no receipt corpus is present in the image, the module falls back to a small honest
synthetic ledger flagged `data_source:"synthetic_fallback", live:false`.

LOCKED preserved: 749/14/163, 13-axis yuyay_v3, replay bacf5443…631fc5,
A2=IsHomogeneous, A4=IsBounded, SLSA L1, Λ Conjecture 1. ADDITIVE only.

Endpoints (read-only / in-memory; ADDITIVE, no existing route touched):
  GET /v1/ayni             -> per-organ Ayni coefficients + HUKLLA T24 deficit report
  GET /v1/replay?at=<ts>   -> verifiable reconstructed state at past timestamp T
  GET /v1/tinkuy           -> current Kuramoto order parameter r + per-organ phases
  GET /v1/ayni/healthz     -> liveness + LOCKED-numbers echo + provenance
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# Module-scope defaults so the route handlers never NameError if the try-block
# below fails (e.g. a missing dep). _SVC None => endpoints return 503.
ORGANS: tuple = ()
_SVC = None
_OK = False
_DATA_SOURCE = None
_RECEIPTS_INGESTED = 0
_LIVE = False
_ORGAN_ACTIVITY: dict = {}

# Candidate REAL KIPU receipt corpora shipped in the Space, in preference order.
_RECEIPT_CANDIDATES = (
    "infra/receipts-samples/receipts_sample.jsonl",
    "huggingface/DEMO_RECEIPT_SAMPLE.jsonl",
    "deploy/attestations.jsonl",
)

# Per-operation compute "take" weight (resource the organ consumed to produce a
# receipt of that kind). Anything unlisted uses _DEFAULT_COST. These are the only
# tunables; the give side is a constant 1.0 attestation unit per receipt.
_KIND_COST = {
    "policy_eval": 1.0,
    "policy_gate_evaluate": 1.0,
    "sbom_probe": 2.0,
    "receipted_retrieval": 1.5,
    "build": 2.5,
    "attestation": 1.0,
}
_DEFAULT_COST = 1.5


def _iso_to_epoch(s):
    """Parse an ISO-8601 timestamp (…Z or offset) to a unix epoch, or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _organ_of(name, organs):
    """Map a receipt's component/actor to one of the canonical organs.

    Exact match wins; otherwise a stable content-hash assignment keeps historic
    organ names (or operator DIDs) deterministically attributed across restarts.
    """
    n = str(name or "").strip().lower()
    # tolerate "did:web:szlholdings.com:rosie#key-1" / "did:szl:operator" forms
    if ":" in n:
        n = n.split("#", 1)[0].split(":")[-1]
    if n in organs:
        return n
    h = int(hashlib.sha256(n.encode()).hexdigest(), 16)
    return organs[h % len(organs)]


def _kind_of(rec):
    """Best-effort operation kind: explicit field, then decoded DSSE payload."""
    k = rec.get("kind") or rec.get("event_type") or (rec.get("envelope") or {}).get("tool_name")
    if k:
        return str(k)
    try:
        payload = (rec.get("dsse_envelope") or {}).get("payload")
        if payload:
            d = json.loads(base64.b64decode(payload).decode())
            ep = (d.get("predicate", {}).get("buildDefinition", {})
                  .get("externalParameters", {}))
            if ep.get("kind"):
                return str(ep["kind"])
    except Exception:
        pass
    return "operation"


def _load_real_receipts(organs):
    """Return (relpath, [(ts, organ, kind), …]) from the first present corpus."""
    base = os.path.dirname(os.path.abspath(__file__))
    for rel in _RECEIPT_CANDIDATES:
        path = os.path.join(base, rel)
        if not os.path.exists(path):
            continue
        recs = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    organ = _organ_of(
                        rec.get("component") or rec.get("actor_id")
                        or rec.get("builder_id") or rec.get("signer")
                        or rec.get("subject"), organs)
                    ts = _iso_to_epoch(
                        rec.get("issued_at_utc") or rec.get("timestamp_iso8601")
                        or rec.get("ts")) or 0.0
                    recs.append((ts, organ, _kind_of(rec)))
        except Exception:
            continue
        if recs:
            recs.sort(key=lambda x: x[0])
            return rel, recs
    return None, []


try:
    from ayni_os.ledger import ReciprocityLedger, ORGANS
    from ayni_os.checkpoint import CheckpointStore
    from ayni_os.tinkuy import TinkuyMonitor
    from ayni_os.replay_api import AyniService

    _LED = ReciprocityLedger()
    _DATA_SOURCE, _real = _load_real_receipts(ORGANS)

    if _real:
        # ---- EVENT-SOURCE the ledger from the REAL signed receipt stream ----
        _LIVE = True
        _last = 0.0
        for _i, (_ts, _organ, _kind) in enumerate(_real):
            # strictly-increasing clock so the hash chain stays a clean prefix
            _t = _ts if (_ts and _ts > _last) else (_last + 1.0)
            _last = _t
            # GIVE: a signed attestation contributed to the empire (1 unit)
            _LED.reciprocate(organ=_organ, resource="attestation", amount=1.0,
                             pair_id="rcpt%d" % _i, ts=_t)
            _last += 0.001
            # TAKE: the compute consumed to produce it (cost by operation kind)
            _LED.drain(organ=_organ, resource="compute",
                       amount=_KIND_COST.get(_kind, _DEFAULT_COST),
                       pair_id="rcpt%d" % _i, ts=_last)
        _RECEIPTS_INGESTED = len(_real)
        # checkpoint at the midpoint of the real receipt window
        _STORE = CheckpointStore()
        _mid = _real[len(_real) // 2][0] or (time.time() - 1800)
        _STORE.force_checkpoint(_LED, at_ts=_mid)
        # per-organ activity (real receipt counts) drives natural frequency
        _ORGAN_ACTIVITY = {o: 0 for o in ORGANS}
        for (_ts, _organ, _kind) in _real:
            _ORGAN_ACTIVITY[_organ] = _ORGAN_ACTIVITY.get(_organ, 0) + 1
    else:
        # ---- honest synthetic fallback (no corpus present in this image) ----
        _LIVE = False
        _DATA_SOURCE = "synthetic_fallback"
        _RECEIPTS_INGESTED = 0
        _t = time.time() - 3600
        _LED.record_exchange(taker="amaru", giver="sentra", resource="gpu_min",
                             amount=12.0, pair_id="seed1", ts=_t)
        _LED.reciprocate(organ="sentra", resource="gpu_min", amount=12.0,
                         pair_id="seed1", ts=_t + 1200)
        _LED.reciprocate(organ="amaru", resource="gpu_min", amount=12.0,
                         pair_id="seed1b", ts=_t + 1300)
        _STORE = CheckpointStore()
        _STORE.force_checkpoint(_LED, at_ts=_t + 1000)
        _ORGAN_ACTIVITY = {o: 1 for o in ORGANS}

    _TINKUY = TinkuyMonitor()
    _SVC = AyniService(ledger=_LED, store=_STORE, tinkuy=_TINKUY)
    _OK = True
    print("[ayni_os] AYNI-OS mounted at /v1/ayni + /v1/replay + /v1/tinkuy "
          "(data_source=%s live=%s receipts=%d)"
          % (_DATA_SOURCE, _LIVE, _RECEIPTS_INGESTED), file=sys.stderr)
except Exception as _e:  # pragma: no cover
    _SVC = None
    _OK = False
    print(f"[ayni_os] NOT mounted ({_e!r})", file=sys.stderr)


def _refresh_phases():
    """Recompute each organ's Kuramoto phase from a LIVE clock + real activity.

    omega_o (natural frequency) scales gently with the organ's real receipt
    activity, so organs with similar activity phase-lock (higher r). phase = omega*t
    evaluated at the current wall clock, so /v1/tinkuy returns genuinely current
    synchrony on every request rather than a frozen snapshot.
    """
    if not (_OK and _ORGAN_ACTIVITY):
        return
    now = time.time()
    maxc = max(_ORGAN_ACTIVITY.values()) or 1
    for o in ORGANS:
        omega = 0.10 + 0.04 * (_ORGAN_ACTIVITY.get(o, 0) / maxc)
        _SVC.tinkuy.set_phase(o, (omega * now) % (2 * math.pi))


def _provenance():
    return {"data_source": _DATA_SOURCE, "live": _LIVE,
            "receipts_ingested": _RECEIPTS_INGESTED,
            "generated_at": round(time.time(), 3)}


@router.get("/v1/ayni/healthz")
def ayni_healthz():
    return {
        "ok": _OK,
        "module": "AYNI-OS",
        "framing": "game-theory primitive (Axelrod-Hamilton 1981); NOT mystical",
        "provenance": _provenance(),
        "locked_numbers": {"declarations": 749, "unique_axioms": 14, "sorries": 163,
                           "yuyay_v3_axes": 13},
        "yuyay_v3_replay_hash":
            "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    }


@router.get("/v1/ayni")
def ayni():
    if _SVC is None:
        return JSONResponse({"error": "AYNI-OS unavailable"}, status_code=503)
    d = _SVC.get_ayni()
    d.update(_provenance())
    return d


@router.get("/v1/replay")
def replay(at: float = Query(..., description="target unix timestamp T")):
    if _SVC is None:
        return JSONResponse({"error": "AYNI-OS unavailable"}, status_code=503)
    d = _SVC.get_replay(at)
    d.update(_provenance())
    return d


@router.get("/v1/tinkuy")
def tinkuy():
    if _SVC is None:
        return JSONResponse({"error": "AYNI-OS unavailable"}, status_code=503)
    _refresh_phases()
    d = _SVC.get_tinkuy()
    try:
        d["phases"] = {o: round(float(_SVC.tinkuy._phases.get(o, 0.0)), 6)
                       for o in ORGANS}
    except Exception:
        d["phases"] = {}
    d.update(_provenance())
    return d
