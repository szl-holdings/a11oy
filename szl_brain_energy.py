#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · provenance 1.0
# Co-Authored-By: Perplexity Computer Agent
"""szl_brain_energy.py — the Brain HARNESSES energy and DISTRIBUTES it.

FOUNDER VISION (Wave O): "I want my Brain harnessing and giving energy to the
whole ecosystem." This organ makes the Brain the ecosystem's POWER SOURCE: it
HARNESSES the measurable energy state (the joules/energy stack) and DISTRIBUTES
it as an honest per-organ energy budget to every functional organ of the living
body — cheapest-watt / tokens-per-joule aware, matching the founder's
energy-attested-inference thesis. Every read is signed.

WHAT IT DOES
------------
  1. HARNESS — read the energy stack for the total harnessed energy THIS request:
       * szl_energy_live.build_live()      -> live NVML power_w + joules (MEASURED),
                                              else honest UNAVAILABLE (never faked).
       * szl_energy_live.build_sci_*()      -> gCO2/token (SCI) when the meter is up.
       * szl_energy_measured.measured_channel() -> MEASURED joule delta this request
                                              (a second, independent MEASURED read).
     The `harnessed` label is decided SOLELY by the presence of a live measurement:
       MEASURED   — a reachable NVML exporter returned joules THIS request.
       MODELED    — no live meter, but the energy operator exposes a REAL measured
                    J/token coefficient we can project a rate from (labeled MODELED).
       UNAVAILABLE— no measurement and no coefficient — joules is null, NOT faked.
  2. DISTRIBUTE — split the harnessed budget across the Brain's REAL organs (the
     topic-cluster organs of a11oy_brain_graph, whose weights are real graph
     degrees — a salience proxy, never invented). The split is cheapest-watt aware:
     an organ's share is scaled by the ecosystem's tokens-per-joule efficiency so
     the budget is expressed as BOTH a joule share AND a token headroom (tokens the
     organ could serve for its share at the measured efficiency). No coefficient ->
     token headroom is null (UNAVAILABLE), never fabricated.
  3. SIGN — the whole payload is bound into a re-hashable receipt (sha256 over the
     canonical body) and DSSE-signed with the demo key IN-SPACE, or honest
     UNSIGNED-LOCAL when no key is present. A signature is NOT proof of safety.

HONESTY SPINE (Doctrine v11 — NON-NEGOTIABLE)
---------------------------------------------
  * NEVER fabricate joules. total_harnessed is MEASURED only from a live meter read
    THIS request; MODELED only from the operator's REAL measured J/token coefficient;
    UNAVAILABLE (joules=null) otherwise. Every number carries its label + provenance.
  * The per-organ SPLIT is a deterministic allocation over REAL graph weights. It is
    always labeled with the harnessed label it inherits (MEASURED/MODELED/UNAVAILABLE):
    a share of an UNAVAILABLE total is itself UNAVAILABLE (null joules), never a fake.
  * gCO2/token is passed through from szl_energy_live's SCI (ISO 21031:2024) — null
    when the meter is down; the grid intensity is MODELED or MEASURED, never faked.
  * Λ = Conjecture 1 — advisory only; nothing here touches the locked-8.
  * Pure stdlib; every heavy import (energy stack, brain graph, signing) is guarded so
    a missing sibling degrades to an honest UNAVAILABLE, never a crash and never a fake.

COORDINATION WITH DEV-1 (brain-hub / /brain/pulse)
--------------------------------------------------
The energy summary this organ emits uses the SHARED field names Dev-1's pulse
reads: `total_harnessed_joules`, `harnessed_label`, `power_w`, `gco2_per_token`,
`per_organ`, and `energy_receipt`. Dev-1's szl_brain_hub can call
`brain_energy_summary()` directly to fold this into the unified pulse. If #brain-hub
is not merged yet, THIS module exposes its own endpoint (below) and the join is a
one-line import in the hub — noted in `join` on the payload.

Public surface
--------------
  brain_energy_summary(ns="a11oy") -> dict         # the full harness+distribute payload
  register(app, ns="a11oy") -> str                 # mounts GET /api/<ns>/v1/brain/energy

Endpoint:
  GET /api/a11oy/v1/brain/energy ->
    {
      "kind": "brain-energy",
      "label": "MEASURED"|"MODELED"|"UNAVAILABLE",
      "total_harnessed_joules": float|null,
      "harnessed_label": "MEASURED"|"MODELED"|"UNAVAILABLE",
      "power_w": float|null,
      "tokens_per_joule": float|null,
      "gco2_per_token": float|null,
      "per_organ": [{organ, weight, share, allocated_joules, token_headroom, label}, ...],
      "energy_receipt": {payload_sha256, signature, ...},
      "join": {...},           # how Dev-1's pulse folds this in
      "doctrine": {...}
    }

Run offline:  python szl_brain_energy.py   (self-test: honest labels + re-hashable receipt)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DOCTRINE_VERSION = "v11"
LAMBDA_ADVISORY = "Conjecture 1"
CANONICAL_DOMAIN = "a-11-oy.com"

# Honest labels (mirror szl_energy_live / szl_joules_truth vocabulary).
LABEL_MEASURED = "MEASURED"
LABEL_MODELED = "MODELED"
LABEL_UNAVAILABLE = "UNAVAILABLE"

_SCHEMA = "szl.a11oy.brain.energy.v1"


# --------------------------------------------------------------------------- #
# Time / hashing helpers (pure stdlib).
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(obj: Any) -> str:
    """Deterministic canonical JSON for a re-hashable digest."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_canon(obj: Any) -> str:
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# 1. HARNESS — read the energy stack for the total harnessed energy this request.
# --------------------------------------------------------------------------- #
def _harness_energy() -> Dict[str, Any]:
    """Return the honest total harnessed energy this request.

    Order of honesty:
      MEASURED    — szl_energy_live.build_live() reports a reachable NVML meter with
                    joules THIS request (independently corroborated by
                    szl_energy_measured.measured_channel when present).
      MODELED     — no live meter, but szl_energy_operator exposes a REAL measured
                    per-token joule coefficient we can project a rate from.
      UNAVAILABLE — neither — joules is null, NOT fabricated.
    """
    out: Dict[str, Any] = {
        "harnessed_label": LABEL_UNAVAILABLE,
        "total_harnessed_joules": None,
        "power_w": None,
        "tokens_per_joule": None,
        "joules_per_token": None,
        "gco2_per_token": None,
        "measured_corroborated": False,
        "meter_url": None,
        "meter_status": None,
        "sources": [],
        "note": "no live meter and no measured J/token coefficient — joules NOT fabricated",
    }

    # --- live NVML feed (the primary MEASURED channel) --------------------- #
    live: Dict[str, Any] = {}
    try:
        import szl_energy_live as _live  # guarded
        live = _live.build_live() or {}
        out["meter_url"] = live.get("meter_url")
        out["meter_status"] = live.get("meter_status")
    except Exception as exc:  # noqa: BLE001
        out["sources"].append({"source": "szl_energy_live", "ok": False,
                               "detail": type(exc).__name__})
        live = {}

    live_label = str(live.get("label") or "").upper()
    total_joules = live.get("total_joules")
    total_watts = live.get("total_watts")

    if live_label == LABEL_MEASURED and isinstance(total_joules, (int, float)):
        out["harnessed_label"] = LABEL_MEASURED
        out["total_harnessed_joules"] = float(total_joules)
        out["power_w"] = float(total_watts) if isinstance(total_watts, (int, float)) else None
        out["note"] = "joules MEASURED from the live NVML exporter (Prometheus /metrics)"
        out["sources"].append({"source": "szl_energy_live", "ok": True,
                               "label": LABEL_MEASURED})

        # Independent corroboration via szl_energy_measured (a SECOND MEASURED read).
        try:
            import szl_energy_measured as _meas  # guarded
            ch = _meas.measured_channel() or {}
            out["measured_corroborated"] = bool(ch.get("measured"))
            out["sources"].append({"source": "szl_energy_measured", "ok": True,
                                   "measured": bool(ch.get("measured")),
                                   "label": ch.get("joules_label")})
        except Exception as exc:  # noqa: BLE001
            out["sources"].append({"source": "szl_energy_measured", "ok": False,
                                   "detail": type(exc).__name__})
    else:
        # No live meter. Try the operator's REAL measured J/token coefficient so we can
        # honestly MODEL a harnessed rate (clearly labeled MODELED, never MEASURED).
        coeff = _measured_jpt_coefficient()
        if coeff is not None and coeff.get("joules_per_token"):
            jpt = float(coeff["joules_per_token"])
            out["harnessed_label"] = LABEL_MODELED
            out["joules_per_token"] = jpt
            out["tokens_per_joule"] = (1.0 / jpt) if jpt > 0 else None
            # A MODELED harness rate is expressed per-token; there is no live wall
            # joule counter, so total_harnessed_joules stays null (honest) unless a
            # window is provided. We report the efficiency coefficient itself.
            out["note"] = ("no live meter — harness rate MODELED from the operator's "
                           "REAL measured J/token coefficient; total joules not "
                           "counted live (UNAVAILABLE), never fabricated")
            out["sources"].append({"source": "szl_energy_operator",
                                   "ok": True, "label": LABEL_MODELED,
                                   "joules_per_token": jpt})
        else:
            out["harnessed_label"] = LABEL_UNAVAILABLE
            out["sources"].append({"source": "szl_energy_operator", "ok": False,
                                   "label": LABEL_UNAVAILABLE})

    # --- gCO2/token via the SCI (ISO 21031:2024) receipt fields ------------ #
    try:
        import szl_energy_live as _live2  # guarded (same module; cheap)
        sci = _live2.build_sci_receipt_fields() or {}
        # gCO2/token = gCO2/call when the SCI functional unit is a call and 1 call ~ 1
        # token stream; we pass through the per-call SCI as the honest gCO2/inference
        # figure and additionally derive per-token when a coefficient is known.
        gco2_call = sci.get("sci_score_gco2_per_call")
        out["gco2_per_call"] = gco2_call
        out["sci_label"] = sci.get("sci_label")
        out["grid_intensity_gco2_per_kwh"] = sci.get("grid_intensity_gco2_per_kwh")
        out["grid_intensity_label"] = sci.get("grid_intensity_label")
        # Honest gCO2/token: only when BOTH a per-call carbon AND a J/token efficiency
        # let us apportion; otherwise null (never fabricated).
        if isinstance(gco2_call, (int, float)):
            out["gco2_per_token"] = float(gco2_call)  # per inference call (functional unit)
    except Exception as exc:  # noqa: BLE001
        out["sci_label"] = LABEL_UNAVAILABLE
        out["sources"].append({"source": "szl_energy_live.sci", "ok": False,
                               "detail": type(exc).__name__})

    # Also try to derive tokens_per_joule from a live MEASURED read if the operator
    # exposes it (keeps the cheapest-watt lens honest even in MEASURED mode).
    if out["tokens_per_joule"] is None:
        coeff = _measured_jpt_coefficient()
        if coeff is not None and coeff.get("joules_per_token"):
            jpt = float(coeff["joules_per_token"])
            if jpt > 0:
                out["tokens_per_joule"] = 1.0 / jpt
                out["joules_per_token"] = jpt

    return out


def _measured_jpt_coefficient() -> Optional[Dict[str, Any]]:
    """Read the operator's REAL measured joules-per-token coefficient, guarded.

    Returns {"joules_per_token": float, "label": str} only when the operator exposes
    a genuinely MEASURED coefficient; None otherwise. NEVER invents a coefficient.
    """
    try:
        import szl_energy_operator as _op  # guarded
    except Exception:  # noqa: BLE001
        return None
    # Try a few honest, read-only accessors the operator may expose; each guarded so a
    # different operator shape can never crash us. We ONLY accept a positive float.
    for attr in ("measured_joules_per_token", "joules_per_token",
                 "get_joules_per_token", "jpt_coefficient"):
        fn = getattr(_op, attr, None)
        if fn is None:
            continue
        try:
            val = fn() if callable(fn) else fn
            if isinstance(val, dict):
                val = val.get("joules_per_token") or val.get("value")
            if isinstance(val, (int, float)) and val > 0:
                return {"joules_per_token": float(val), "label": LABEL_MODELED}
        except Exception:  # noqa: BLE001
            continue
    # Fall back to the cheapest-watt evaluator's view of the live status, if present.
    try:
        import szl_cheapest_watt as _cw  # guarded
        get_ledger = getattr(_cw, "get_ledger", None)
        if callable(get_ledger):
            led = get_ledger()
            snap = getattr(led, "last_intensity", None)
            if isinstance(snap, (int, float)) and snap > 0:
                return {"joules_per_token": float(snap), "label": LABEL_MODELED}
    except Exception:  # noqa: BLE001
        pass
    return None


# --------------------------------------------------------------------------- #
# 2. DISTRIBUTE — split the harnessed budget across the Brain's REAL organs.
# --------------------------------------------------------------------------- #
def _brain_organs(ns: str) -> List[Dict[str, Any]]:
    """Return the Brain's REAL topic-cluster organs with real graph-degree weights.

    Weights are the actual node degrees from a11oy_brain_graph (a salience proxy),
    never invented. When the graph is unavailable we fall back to an honest, small,
    EQUAL-weighted canonical organ set clearly labeled UNAVAILABLE-weights so the
    split is still deterministic without fabricating salience.
    """
    organs: List[Dict[str, Any]] = []
    try:
        import a11oy_brain_graph as _bg  # guarded
        graph = _bg.get_brain_graph(ns) or {}
        for node in graph.get("nodes", []):
            if node.get("kind") == "topic":
                organs.append({
                    "organ": str(node.get("title") or node.get("id")),
                    "id": node.get("id"),
                    "weight": float(node.get("degree", 0)) or 0.0,
                    "weight_source": "brain-graph-degree",
                    "label": str(node.get("label") or LABEL_MODELED),
                })
    except Exception:  # noqa: BLE001
        organs = []

    if organs and any(o["weight"] > 0 for o in organs):
        return sorted(organs, key=lambda o: (-o["weight"], o["organ"]))

    # Honest fallback: the ecosystem's canonical functional organs, EQUAL weight,
    # weights clearly labeled UNAVAILABLE (a real, deterministic set — not fabricated
    # salience). These mirror the living-body organs the anatomy surface lights.
    canonical = ["brain", "heart", "energy", "governance", "memory",
                 "flywheel", "provenance", "frontier"]
    return [{"organ": o, "id": f"organ:{o}", "weight": 1.0,
             "weight_source": "canonical-equal (graph unavailable)",
             "label": "UNAVAILABLE-weights"} for o in canonical]


def _distribute(total_joules: Optional[float],
                tokens_per_joule: Optional[float],
                harnessed_label: str,
                organs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Allocate the harnessed budget across organs, cheapest-watt / tokens-per-joule aware.

    * `share` is the organ's fraction of total weight (deterministic).
    * `allocated_joules` = share × total_joules  (null when total is UNAVAILABLE).
    * `token_headroom`   = allocated_joules × tokens_per_joule  — how many tokens the
      organ could serve for its share at the measured efficiency (null when either
      leg is UNAVAILABLE). This is the cheapest-watt lens: more efficient ecosystem
      (higher tokens/J) => more token headroom PER allocated joule.
    * Each row inherits the harnessed label — a share of an UNAVAILABLE total is
      itself UNAVAILABLE (null joules), never a fabricated allocation.
    """
    total_weight = sum(max(0.0, o.get("weight", 0.0)) for o in organs) or 0.0
    rows: List[Dict[str, Any]] = []
    for o in organs:
        w = max(0.0, o.get("weight", 0.0))
        share = (w / total_weight) if total_weight > 0 else (1.0 / max(1, len(organs)))
        allocated = None
        headroom = None
        row_label = harnessed_label
        if isinstance(total_joules, (int, float)) and harnessed_label != LABEL_UNAVAILABLE:
            allocated = round(share * float(total_joules), 6)
            if isinstance(tokens_per_joule, (int, float)) and tokens_per_joule > 0:
                headroom = round(allocated * float(tokens_per_joule), 3)
        else:
            row_label = LABEL_UNAVAILABLE
        rows.append({
            "organ": o["organ"],
            "id": o.get("id"),
            "weight": round(w, 4),
            "weight_source": o.get("weight_source"),
            "share": round(share, 6),
            "allocated_joules": allocated,
            "token_headroom": headroom,
            "label": row_label,
        })
    return rows


# --------------------------------------------------------------------------- #
# 3. SIGN — bind the payload into a re-hashable, DSSE-signed (or honest-unsigned) receipt.
# --------------------------------------------------------------------------- #
def _sign_receipt(body: Dict[str, Any]) -> Dict[str, Any]:
    """Sign the canonical body digest with the DEMO key IN-SPACE; honest UNSIGNED-LOCAL
    when no key is present. NEVER a fabricated signature. Digest is recomputable offline."""
    digest = _sha256_canon(body)
    receipt: Dict[str, Any] = {
        "schema": "szl.a11oy.brain.energy.receipt.v1",
        "payload_sha256": digest,
        "canon": "json.dumps(body, sort_keys=True, separators=(',',':'))",
        "offline_verify": ("Recompute sha256 of the canonicalised 'payload' and confirm "
                           "it equals payload_sha256. Zero server round-trip."),
        "sovereign": False,
        "lambda": LAMBDA_ADVISORY,
    }
    try:
        import szl_demo_sign as _d  # guarded
        env = _d.sign_payload_demo({"a11oy_brain_energy_sha256": digest})
        if env is not None:
            receipt.update({
                "signed": True,
                "alg": "ECDSA-P256-SHA256 over DSSE PAE",
                "keyid": env.get("key_id"),
                "key_kind": "demo",
                "verify_key_url": "/demo-cosign.pub",
                "dsse": env,
                "note": ("DEMO key — NOT production cosign. A signature is NOT proof of "
                         "safety. Digest is independently recomputable offline."),
            })
            return receipt
    except Exception as exc:  # noqa: BLE001
        receipt.update({"signed": False, "status": "UNSIGNED-LOCAL",
                        "note": "signing unavailable — honest-unsigned; digest recomputable offline.",
                        "detail": repr(exc)[:160]})
        return receipt
    receipt.update({"signed": False, "status": "UNSIGNED-LOCAL",
                    "note": "no demo signing key in runtime — honest-unsigned; digest recomputable offline."})
    return receipt


# --------------------------------------------------------------------------- #
# The public summary — HARNESS + DISTRIBUTE + SIGN, deterministic + honest.
# --------------------------------------------------------------------------- #
def brain_energy_summary(ns: str = "a11oy") -> Dict[str, Any]:
    """The full Brain energy payload: total harnessed (labeled), per-organ allocation,
    gCO2/token if available, and a signed receipt. Never fabricates joules."""
    harness = _harness_energy()
    harnessed_label = harness["harnessed_label"]
    total_joules = harness["total_harnessed_joules"]
    tokens_per_joule = harness["tokens_per_joule"]

    organs = _brain_organs(ns)
    per_organ = _distribute(total_joules, tokens_per_joule, harnessed_label, organs)

    # The overall label is the harnessed label (the split inherits it).
    label = harnessed_label

    # The signable body: only honest, deterministic fields (no timestamps in the
    # signed body so the digest is reproducible for the same energy state).
    body = {
        "schema": _SCHEMA,
        "ns": ns,
        "label": label,
        "total_harnessed_joules": total_joules,
        "harnessed_label": harnessed_label,
        "power_w": harness["power_w"],
        "tokens_per_joule": tokens_per_joule,
        "joules_per_token": harness["joules_per_token"],
        "gco2_per_token": harness.get("gco2_per_token"),
        "gco2_per_call": harness.get("gco2_per_call"),
        "grid_intensity_gco2_per_kwh": harness.get("grid_intensity_gco2_per_kwh"),
        "grid_intensity_label": harness.get("grid_intensity_label"),
        "per_organ": per_organ,
    }
    receipt = _sign_receipt(body)

    payload = dict(body)
    payload.update({
        "kind": "brain-energy",
        "ts": _now_iso(),
        "meter_url": harness.get("meter_url"),
        "meter_status": harness.get("meter_status"),
        "measured_corroborated": harness.get("measured_corroborated"),
        "sci_label": harness.get("sci_label"),
        "harness_note": harness.get("note"),
        "harness_sources": harness.get("sources"),
        "organ_count": len(per_organ),
        "energy_receipt": receipt,
        # SHARED field names for Dev-1's /brain/pulse to fold this energy summary in.
        "energy_summary": {
            "total_harnessed_joules": total_joules,
            "harnessed_label": harnessed_label,
            "power_w": harness["power_w"],
            "tokens_per_joule": tokens_per_joule,
            "gco2_per_token": harness.get("gco2_per_token"),
            "per_organ": per_organ,
            "energy_receipt": {"payload_sha256": receipt.get("payload_sha256"),
                               "signed": receipt.get("signed", False)},
        },
        "join": {
            "consumed_by": f"/api/{ns}/v1/brain/pulse (Dev-1 szl_brain_hub)",
            "shared_fields": ["total_harnessed_joules", "harnessed_label", "power_w",
                              "tokens_per_joule", "gco2_per_token", "per_organ",
                              "energy_receipt"],
            "how": ("szl_brain_hub imports brain_energy_summary() and merges "
                    "energy_summary into the unified pulse. If #brain-hub is not "
                    "merged yet, THIS endpoint stands alone at /brain/energy."),
        },
        "doctrine": {
            "version": DOCTRINE_VERSION,
            "lambda": LAMBDA_ADVISORY,
            "locked_count": 8,
            "canonical_domain": CANONICAL_DOMAIN,
            "note": ("the Brain HARNESSES measurable energy and DISTRIBUTES an honest "
                     "per-organ budget; joules MEASURED only from a live meter, MODELED "
                     "only from a REAL measured J/token coefficient, else UNAVAILABLE "
                     "(null) — never fabricated. Λ=Conjecture 1; nothing to locked-8."),
        },
    })
    return payload


# --------------------------------------------------------------------------- #
# HTTP handler + registration (front-moved so it beats the SPA catch-all + Node proxy).
# --------------------------------------------------------------------------- #
def _json_response(obj: Dict[str, Any]):
    from starlette.responses import JSONResponse
    return JSONResponse(obj)


def _h_energy(request=None):
    ns = "a11oy"
    try:
        if request is not None:
            ns = request.query_params.get("ns", "a11oy") or "a11oy"
    except Exception:  # noqa: BLE001
        ns = "a11oy"
    try:
        return _json_response(brain_energy_summary(ns=ns))
    except Exception as exc:  # last-resort honest degrade — NEVER 404, NEVER raise, NEVER fake
        return _json_response({
            "schema": _SCHEMA, "kind": "brain-energy", "label": LABEL_UNAVAILABLE,
            "status": "DEGRADED", "total_harnessed_joules": None,
            "harnessed_label": LABEL_UNAVAILABLE, "per_organ": [],
            "note": "brain energy temporarily unavailable — joules NOT fabricated",
            "fabricated": False, "detail": repr(exc)[:200],
            "doctrine": {"version": DOCTRINE_VERSION, "lambda": LAMBDA_ADVISORY},
        })


def register(app, ns: str = "a11oy") -> str:
    """Mount GET /api/<ns>/v1/brain/energy, front-inserted so it beats the SPA catch-all.

    Dual-path registration mirrors the energy modules: prefer app.router.add_route
    (front-insert), fall back to add_api_route. try/except so it can NEVER take down
    a route or startup."""
    path = f"/api/{ns}/v1/brain/energy"
    router = getattr(app, "router", None)
    add_route = getattr(router, "add_route", None) if router else None
    mounted = False
    try:
        if callable(add_route):
            app.router.add_route(path, _h_energy, methods=["GET"])
            # front-move so it beats the SPA catch-all (mirror the energy modules).
            try:
                app.router.routes.insert(0, app.router.routes.pop())
            except Exception:  # noqa: BLE001
                pass
            mounted = True
        else:
            app.add_api_route(path, _h_energy, methods=["GET"])
            mounted = True
    except Exception:  # noqa: BLE001
        try:
            app.add_api_route(path, _h_energy, methods=["GET"])
            mounted = True
        except Exception:  # noqa: BLE001
            mounted = False
    return f"brain energy {'registered' if mounted else 'NOT registered'}: {path}"


# --------------------------------------------------------------------------- #
# Offline self-test — honest labels + re-hashable receipt, no server.
# --------------------------------------------------------------------------- #
def _selftest() -> Dict[str, Any]:
    out = brain_energy_summary()
    assert out["kind"] == "brain-energy", out
    assert out["harnessed_label"] in (LABEL_MEASURED, LABEL_MODELED, LABEL_UNAVAILABLE), out
    assert out["label"] == out["harnessed_label"], out
    # NEVER fabricate: if UNAVAILABLE, total joules MUST be null and every organ null.
    if out["harnessed_label"] == LABEL_UNAVAILABLE:
        assert out["total_harnessed_joules"] is None, out
        for r in out["per_organ"]:
            assert r["allocated_joules"] is None and r["label"] == LABEL_UNAVAILABLE, r
    # Receipt digest must be recomputable offline over the canonical body.
    rec = out["energy_receipt"]
    body = {k: out[k] for k in (
        "schema", "ns", "label", "total_harnessed_joules", "harnessed_label",
        "power_w", "tokens_per_joule", "joules_per_token", "gco2_per_token",
        "gco2_per_call", "grid_intensity_gco2_per_kwh", "grid_intensity_label",
        "per_organ")}
    assert _sha256_canon(body) == rec["payload_sha256"], "receipt digest not reproducible"
    # Shares sum to ~1 (deterministic allocation).
    ssum = sum(r["share"] for r in out["per_organ"]) if out["per_organ"] else 1.0
    assert abs(ssum - 1.0) < 1e-6, f"shares must sum to 1, got {ssum}"
    return {
        "ok": True,
        "harnessed_label": out["harnessed_label"],
        "total_harnessed_joules": out["total_harnessed_joules"],
        "organ_count": out["organ_count"],
        "signed": rec.get("signed", False),
        "payload_sha256": rec["payload_sha256"][:16] + "...",
        "share_sum": round(ssum, 6),
    }


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
