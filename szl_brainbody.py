#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""szl_brainbody.py — Brain-Body panel (Wave O, Dev 3).

GET /api/a11oy/v1/frontier/brainbody returns the state that lights the LIVING BODY
3D surface (``static/3d/surfaces/brainbody.js``): each organ's brightness/activity is
driven by the **Brain pulse** (Dev-1's ``GET /api/a11oy/v1/brain/pulse``) and its
**energy allocation** (Dev-2's ``GET /api/a11oy/v1/brain/energy``). This backend is a
THIN, honest COMPOSER: it reads the Brain pulse + energy state SERVER-SIDE, maps them
onto a canonical organ set, and returns per-organ lighting each carrying its VERBATIM
honesty label (LIVE / MODELED / UNAVAILABLE) plus a signed receipt of the read.

WHY A BACKEND AT ALL: the surface *could* fetch the Brain endpoints directly, but the
Brain PRs (Dev-1 ``feat/brain-hub``, Dev-2 ``feat/brain-energy``) may not be merged in
this runtime. Composing server-side gives the surface ONE deterministic endpoint, lets
us join pulse+energy into per-organ lighting once, and lets us sign a receipt of the
read. If the Brain endpoints are absent, this degrades to an HONEST UNAVAILABLE for the
missing source — it NEVER fabricates a pulse, a joule, or a lit organ.

HONESTY (doctrine v11 · Zero-Bandaid Law):
  - Each organ's ``label`` is LIVE only when a real pulse/energy value backed it THIS
    request; MODELED when the source labeled its own value modeled/derived; UNAVAILABLE
    when the source was absent or returned no value. No label is ever upgraded.
  - ``brightness`` in [0,1] is a deterministic function of the (labeled) pulse activity
    and energy allocation; an UNAVAILABLE organ is DIM (never shown alive).
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17.
  - Λ stays Conjecture 1 (advisory, never "green"/theorem). Trust ceiling 0.97.
  - Additive route, registered BEFORE the SPA catch-all; 0 runtime CDN.

SOURCES / JOINS:
  - Dev-1 Brain pulse   — GET /api/a11oy/v1/brain/pulse        (feat/brain-hub)
  - Dev-2 Brain energy  — GET /api/a11oy/v1/brain/energy       (feat/brain-energy)
  - Prefer the in-process module (szl_brain_hub / szl_brain_energy) when present so we
    agree with the routed endpoints by construction; else an internal HTTP read of the
    same-origin routes; else honest UNAVAILABLE with the dependency recorded.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any

# Honesty-label vocabulary (doctrine v11) — tests grep these exact strings.
LIVE = "LIVE"
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Trust ceiling — advisory, never 100% (doctrine v11).
TRUST_CEILING = 0.97

# The Brain read routes we compose (Dev-1 pulse, Dev-2 energy).
DEV1_PULSE_ROUTE = "/api/a11oy/v1/brain/pulse"
DEV2_ENERGY_ROUTE = "/api/a11oy/v1/brain/energy"

# Canonical organ set the Brain (central nervous system + power source) feeds. Each maps
# a body organ to the ecosystem function it powers. This is the DISPLAY skeleton; the
# LIVE activity/energy that lights each organ comes ONLY from the Brain pulse/energy.
ORGANS: list[dict[str, str]] = [
    {"id": "brain",     "organ": "Brain",              "role": "central nervous system + power source (the pulse origin)"},
    {"id": "heart",     "organ": "Heart",              "role": "circulation — signed-receipt / khipu heartbeat"},
    {"id": "lungs",     "organ": "Lungs",              "role": "energy intake — GPU joules / grid posture"},
    {"id": "vault",     "organ": "Memory (hippocampus)", "role": "knowledge vault — self-writing harvest"},
    {"id": "flywheel",  "organ": "Muscles",            "role": "governed flywheel — harness / eval / RAG / agent-loop"},
    {"id": "liver",     "organ": "Liver",              "role": "governance / detox — Λ gates + restraint"},
    {"id": "eyes",      "organ": "Eyes",               "role": "observability — telemetry / attestation"},
    {"id": "surfaces",  "organ": "Skin (sensorium)",   "role": "frontier surfaces — the 84 lit organs"},
]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_hex(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


def _clamp01(x: Any) -> float:
    try:
        v = float(x)
    except Exception:  # noqa: BLE001
        return 0.0
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def _upper_label(v: Any, default: str = UNAVAILABLE) -> str:
    s = str(v if v is not None else default).upper()
    # Normalize a few common synonyms into our 3-word vocabulary; never upgrade.
    if s in ("LIVE", "MEASURED", "LIVE-SOVEREIGN", "OK", "HEALTHY"):
        return LIVE
    if s in ("MODELED", "SIMULATED", "SAMPLE", "DERIVED", "ESTIMATED", "CACHED"):
        return MODELED
    return UNAVAILABLE


# ---------------------------------------------------------------------------
# 1. Read the Brain pulse (Dev-1). Prefer in-process module; else HTTP; else UNAVAILABLE.
# ---------------------------------------------------------------------------

def _read_pulse() -> dict[str, Any]:
    """Return {ok, source, label, pulse, dependency, note}. NEVER fabricates a pulse."""
    out: dict[str, Any] = {"ok": False, "source": None, "label": UNAVAILABLE,
                           "pulse": None, "dependency": None, "note": ""}
    # Preferred: in-process module (agrees with the routed endpoint by construction).
    try:
        import szl_brain_hub as _hub  # local import (in Dockerfile COPY set when merged)
        if hasattr(_hub, "pulse_payload"):
            p = _hub.pulse_payload()
        elif hasattr(_hub, "build_pulse"):
            p = _hub.build_pulse()
        else:
            p = _hub.handle() if hasattr(_hub, "handle") else None
        if isinstance(p, dict):
            out.update(ok=True, source="szl_brain_hub (in-process)", pulse=p,
                       label=_upper_label(p.get("label"), LIVE),
                       dependency="resolved: szl_brain_hub present in this runtime")
            return out
    except Exception as exc:  # noqa: BLE001 — Dev-1 module absent → honest note, try HTTP
        out["dependency"] = ("PENDING: szl_brain_hub unavailable (%s); Dev-1 %s not merged "
                             "in this runtime — trying same-origin HTTP read." %
                             (type(exc).__name__, DEV1_PULSE_ROUTE))
    # Fallback: same-origin HTTP read of the routed endpoint (pure stdlib, short timeout).
    p = _http_get_local(DEV1_PULSE_ROUTE)
    if isinstance(p, dict):
        out.update(ok=True, source="HTTP %s" % DEV1_PULSE_ROUTE, pulse=p,
                   label=_upper_label(p.get("label"), LIVE),
                   dependency=(out.get("dependency") or "") + " HTTP read succeeded.")
        return out
    out["note"] = ("Brain pulse UNAVAILABLE — neither szl_brain_hub (in-process) nor %s "
                   "(HTTP) responded; no pulse fabricated (Zero-Bandaid Law)." % DEV1_PULSE_ROUTE)
    return out


# ---------------------------------------------------------------------------
# 2. Read the Brain energy allocation (Dev-2). Same guarded pattern.
# ---------------------------------------------------------------------------

def _read_energy() -> dict[str, Any]:
    """Return {ok, source, label, energy, dependency, note}. NEVER fabricates joules."""
    out: dict[str, Any] = {"ok": False, "source": None, "label": UNAVAILABLE,
                           "energy": None, "dependency": None, "note": ""}
    try:
        import szl_brain_energy as _be  # local import (in Dockerfile COPY set when merged)
        if hasattr(_be, "energy_payload"):
            e = _be.energy_payload()
        elif hasattr(_be, "build_energy"):
            e = _be.build_energy()
        else:
            e = _be.handle() if hasattr(_be, "handle") else None
        if isinstance(e, dict):
            out.update(ok=True, source="szl_brain_energy (in-process)", energy=e,
                       label=_upper_label(e.get("label"), MODELED),
                       dependency="resolved: szl_brain_energy present in this runtime")
            return out
    except Exception as exc:  # noqa: BLE001 — Dev-2 module absent → honest note, try HTTP
        out["dependency"] = ("PENDING: szl_brain_energy unavailable (%s); Dev-2 %s not merged "
                             "in this runtime — trying same-origin HTTP read." %
                             (type(exc).__name__, DEV2_ENERGY_ROUTE))
    e = _http_get_local(DEV2_ENERGY_ROUTE)
    if isinstance(e, dict):
        out.update(ok=True, source="HTTP %s" % DEV2_ENERGY_ROUTE, energy=e,
                   label=_upper_label(e.get("label"), MODELED),
                   dependency=(out.get("dependency") or "") + " HTTP read succeeded.")
        return out
    out["note"] = ("Brain energy UNAVAILABLE — neither szl_brain_energy (in-process) nor %s "
                   "(HTTP) responded; no joules fabricated (Zero-Bandaid Law)." % DEV2_ENERGY_ROUTE)
    return out


def _http_get_local(path: str) -> Any:
    """Same-origin GET of a local route (stdlib, short timeout, never raises)."""
    import os as _os
    import urllib.request as _rq

    port = (_os.environ.get("PORT", "7860") or "7860").strip()
    url = "http://127.0.0.1:%s%s" % (port, path)
    try:
        req = _rq.Request(url, headers={"Accept": "application/json"})
        with _rq.urlopen(req, timeout=1.5) as resp:  # noqa: S310 — fixed localhost
            if 200 <= resp.status < 300:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — honest miss, never fabricate
        return None
    return None


# ---------------------------------------------------------------------------
# 3. Join pulse + energy into per-organ lighting — deterministic + honest.
# ---------------------------------------------------------------------------

def _extract_organ_map(blob: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    """Pull a per-organ dict out of a pulse/energy blob under any of `keys`.
    Accepts {organ_id: value} or a list[{id/organ, value/activity/brightness/joules}]."""
    if not isinstance(blob, dict):
        return {}
    for k in keys:
        v = blob.get(k)
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            m: dict[str, Any] = {}
            for it in v:
                if isinstance(it, dict):
                    oid = it.get("id") or it.get("organ") or it.get("surface") or it.get("name")
                    if oid is not None:
                        m[str(oid)] = it
            if m:
                return m
    return {}


def _num(d: Any, *names: str) -> Any:
    if isinstance(d, dict):
        for n in names:
            if d.get(n) is not None:
                return d.get(n)
    return d if isinstance(d, (int, float)) else None


def _light_organs(pulse_rd: dict[str, Any], energy_rd: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the per-organ lighting list. Each item is honestly labeled; an organ with
    no live pulse/energy value is UNAVAILABLE + dim (never shown alive)."""
    pulse = pulse_rd.get("pulse") if pulse_rd.get("ok") else None
    energy = energy_rd.get("energy") if energy_rd.get("ok") else None

    p_map = _extract_organ_map(pulse, ("organs", "per_organ", "organ_activity", "lit"))
    e_map = _extract_organ_map(energy, ("per_organ", "per_organ_allocation", "allocation", "organs"))

    # A global pulse activity (used to gently animate the whole body when live but no
    # per-organ breakdown is exposed yet). Purely a display heartbeat; still labeled.
    global_act = None
    if isinstance(pulse, dict):
        global_act = _num(pulse, "activity", "pulse_activity", "beat", "load")

    out: list[dict[str, Any]] = []
    for spec in ORGANS:
        oid = spec["id"]
        pv = p_map.get(oid)
        ev = e_map.get(oid)

        activity = _num(pv, "activity", "brightness", "value", "beat")
        alloc = _num(ev, "allocation", "share", "budget", "joules", "value")

        # Determine the honest label for THIS organ:
        #  LIVE        — a real per-organ pulse value backed it this request
        #  MODELED     — only a modeled/global signal (energy allocation or global pulse)
        #  UNAVAILABLE — no signal at all
        has_live = activity is not None and pulse_rd.get("label") == LIVE
        has_modeled = (alloc is not None) or (global_act is not None) or (activity is not None)
        if has_live:
            label = LIVE
            base = _clamp01(activity)
        elif has_modeled:
            label = MODELED
            # blend whatever we have; if only global pulse, use it dimly
            parts = [x for x in (_clamp01(activity) if activity is not None else None,
                                 _clamp01(alloc) if alloc is not None else None,
                                 _clamp01(global_act) if global_act is not None else None)
                     if x is not None]
            base = (sum(parts) / len(parts)) if parts else 0.0
        else:
            label = UNAVAILABLE
            base = 0.0

        # Brightness: LIVE organs glow, MODELED organs glow dimmer, UNAVAILABLE stay dark.
        if label == LIVE:
            brightness = 0.45 + 0.55 * base
        elif label == MODELED:
            brightness = 0.20 + 0.35 * base
        else:
            brightness = 0.06  # dim, never alive

        out.append({
            "id": oid,
            "organ": spec["organ"],
            "role": spec["role"],
            "label": label,
            "brightness": round(_clamp01(brightness), 4),
            "activity": (round(_clamp01(activity), 4) if activity is not None else None),
            "energy_alloc": (round(_clamp01(alloc), 4) if alloc is not None else None),
            "lit_by_brain": label in (LIVE, MODELED),
        })
    return out


# ---------------------------------------------------------------------------
# 4. Signed receipt of the read — REAL DSSE in-Space, honest UNSIGNED-LOCAL else.
# ---------------------------------------------------------------------------

def _sign_receipt(snapshot: dict[str, Any]) -> dict[str, Any]:
    receipt_body = {
        "kind": "brainbody_read",
        "top_label": snapshot.get("label"),
        "pulse_source": snapshot.get("pulse", {}).get("source"),
        "energy_source": snapshot.get("energy", {}).get("source"),
        "organs_lit": snapshot.get("summary", {}).get("organs_lit"),
        "organs_total": snapshot.get("summary", {}).get("organs_total"),
        "checked_at": snapshot.get("timestamp_utc"),
    }
    try:
        import szl_dsse as _dsse  # local import (in Dockerfile COPY set)
        env = _dsse.sign_payload(receipt_body, payload_type="application/vnd.szl.brainbody-read+json")
        signed = bool(env.get("signed"))
        return {
            "receipt": receipt_body,
            "dsse": env,
            "signed": signed,
            "sign_mode": "DSSE-LIVE" if signed else "UNSIGNED-LOCAL",
            "signer_fingerprint": (_dsse.public_key_fingerprint()
                                   if hasattr(_dsse, "public_key_fingerprint") else None),
            "note": ("REAL ECDSA-P256 DSSE over the brain-body read snapshot."
                     if signed else
                     "UNSIGNED-LOCAL — no cosign private key in this runtime; receipt "
                     "explicitly unsigned (never fabricated)."),
        }
    except Exception as exc:  # noqa: BLE001 — signer absent → honest self-hash, never faked sig
        return {
            "receipt": receipt_body,
            "dsse": None,
            "signed": False,
            "sign_mode": "UNSIGNED-LOCAL",
            "content_sha256": _sha256_hex(repr(sorted(receipt_body.items())).encode("utf-8")),
            "note": ("DSSE signer unavailable (%s) — receipt is UNSIGNED-LOCAL with a plain "
                     "content hash; no signature fabricated." % type(exc).__name__),
        }


def _doctrine_block() -> dict[str, Any]:
    return {
        "locked_proven": 8,
        "locked_set": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "kernel_commit": "c7c0ba17",
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
    }


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------

def build_payload() -> dict[str, Any]:
    pulse_rd = _read_pulse()
    energy_rd = _read_energy()
    organs = _light_organs(pulse_rd, energy_rd)

    lit = [o for o in organs if o["lit_by_brain"]]
    live_ct = sum(1 for o in organs if o["label"] == LIVE)
    modeled_ct = sum(1 for o in organs if o["label"] == MODELED)
    unavail_ct = sum(1 for o in organs if o["label"] == UNAVAILABLE)

    # Top label: LIVE only if the pulse was LIVE and at least one organ is LIVE;
    # MODELED if we have *some* modeled signal; else UNAVAILABLE. Never upgraded.
    if pulse_rd.get("label") == LIVE and live_ct > 0:
        top = LIVE
    elif (pulse_rd.get("ok") or energy_rd.get("ok")) and (modeled_ct + live_ct) > 0:
        top = MODELED
    else:
        top = UNAVAILABLE

    payload: dict[str, Any] = {
        "ok": True,
        "surface": "brainbody",
        "title": "Anatomy · Body lit by the Brain",
        "label": top,
        "claim": top,
        "timestamp_utc": _now_iso(),
        "pulse": {
            "ok": pulse_rd["ok"], "label": pulse_rd["label"], "source": pulse_rd["source"],
            "dependency": pulse_rd["dependency"], "note": pulse_rd["note"],
            "route": DEV1_PULSE_ROUTE, "owner": "Dev-1 (feat/brain-hub)",
        },
        "energy": {
            "ok": energy_rd["ok"], "label": energy_rd["label"], "source": energy_rd["source"],
            "dependency": energy_rd["dependency"], "note": energy_rd["note"],
            "route": DEV2_ENERGY_ROUTE, "owner": "Dev-2 (feat/brain-energy)",
        },
        "organs": organs,
        "summary": {
            "organs_total": len(organs),
            "organs_lit": len(lit),
            "live": live_ct, "modeled": modeled_ct, "unavailable": unavail_ct,
        },
        "how_lit": ("Each organ's brightness is a deterministic function of the Brain pulse "
                    "(Dev-1 /brain/pulse) activity and its energy allocation (Dev-2 "
                    "/brain/energy). LIVE organs glow, MODELED organs glow dimmer, "
                    "UNAVAILABLE organs stay dark — never shown alive."),
        "doctrine": _doctrine_block(),
        "sources": [
            {"name": "Brain pulse (Dev-1)", "route": DEV1_PULSE_ROUTE, "branch": "feat/brain-hub"},
            {"name": "Brain energy (Dev-2)", "route": DEV2_ENERGY_ROUTE, "branch": "feat/brain-energy"},
            {"name": "Λ = Conjecture 1 (lutar-lean)", "route": None, "branch": None},
        ],
    }
    payload["signed_receipt"] = _sign_receipt(payload)
    return payload


def handle() -> dict[str, Any]:
    try:
        return build_payload()
    except Exception as exc:  # noqa: BLE001 — never 500; honest UNAVAILABLE envelope
        return {
            "ok": True, "surface": "brainbody", "label": UNAVAILABLE, "claim": UNAVAILABLE,
            "timestamp_utc": _now_iso(),
            "error_class": type(exc).__name__,
            "note": "brain-body composer errored — degraded to honest UNAVAILABLE (no fabrication).",
            "organs": [], "summary": {"organs_total": 0, "organs_lit": 0,
                                      "live": 0, "modeled": 0, "unavailable": 0},
            "doctrine": _doctrine_block(),
        }


def rollup_signal() -> dict[str, Any]:
    """Compact signal for a healthz rollup: {label, organs_lit, organs_total}."""
    p = build_payload()
    s = p.get("summary", {})
    return {"label": p.get("label"), "organs_lit": s.get("organs_lit"),
            "organs_total": s.get("organs_total")}


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the brain-body panel endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/brainbody")
    async def _frontier_brainbody():  # noqa: ANN202
        """Per-organ lighting for the living body, driven by the Brain pulse + energy."""
        return JSONResponse(handle())

    return f"{base}/brainbody"


# ---------------------------------------------------------------------------
# Self-test — honest labels, no upgrade, degrades to UNAVAILABLE, sources cited.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainbody — self-test (organs lit by the Brain; UNAVAILABLE when Brain down)")
    print("=" * 72)

    p = build_payload()

    # 1) shape + honest top label (one of the 3-word vocabulary; consistent with claim).
    assert p["ok"] is True
    assert p["label"] in (LIVE, MODELED, UNAVAILABLE)
    assert p["label"] == p["claim"]
    assert p["surface"] == "brainbody"
    print(f"[1] top label={p['label']} (== claim; honest 3-word vocabulary)  OK")

    # 2) every organ carries an honest label + brightness in [0,1]; UNAVAILABLE organs dim.
    organs = p["organs"]
    assert len(organs) == len(ORGANS)
    for o in organs:
        assert o["label"] in (LIVE, MODELED, UNAVAILABLE)
        assert 0.0 <= o["brightness"] <= 1.0
        if o["label"] == UNAVAILABLE:
            assert o["brightness"] <= 0.1 and o["lit_by_brain"] is False
        if o["label"] == LIVE:
            assert o["lit_by_brain"] is True
    print(f"[2] {len(organs)} organs each honestly labeled; UNAVAILABLE organs dim (never alive)  OK")

    # 3) with the Brain PRs not merged in CI, pulse+energy MUST be honest UNAVAILABLE and
    #    the top label MUST NOT be fabricated LIVE.
    if not p["pulse"]["ok"] and not p["energy"]["ok"]:
        assert p["label"] == UNAVAILABLE
        assert all(o["label"] == UNAVAILABLE for o in organs)
        assert p["summary"]["organs_lit"] == 0
    print(f"[3] pulse.ok={p['pulse']['ok']} energy.ok={p['energy']['ok']} — no fabricated LIVE when Brain absent  OK")

    # 4) summary counts are consistent with the organ labels.
    s = p["summary"]
    assert s["organs_total"] == len(organs)
    assert s["live"] == sum(1 for o in organs if o["label"] == LIVE)
    assert s["modeled"] == sum(1 for o in organs if o["label"] == MODELED)
    assert s["unavailable"] == sum(1 for o in organs if o["label"] == UNAVAILABLE)
    assert s["organs_lit"] == s["live"] + s["modeled"]
    print(f"[4] summary consistent: lit={s['organs_lit']}/{s['organs_total']} "
          f"(live={s['live']} modeled={s['modeled']} unavailable={s['unavailable']})  OK")

    # 5) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = p["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    # 6) signed receipt of the read present + honest sign mode (never a faked signature).
    sr = p["signed_receipt"]
    assert sr["sign_mode"] in ("DSSE-LIVE", "UNSIGNED-LOCAL")
    assert isinstance(sr["receipt"], dict) and sr["receipt"]["kind"] == "brainbody_read"
    if sr["sign_mode"] == "UNSIGNED-LOCAL":
        env = sr.get("dsse") or {}
        assert not env.get("signatures")
    print(f"[6] signed receipt present; sign_mode={sr['sign_mode']} (no fabricated signature)  OK")

    # 7) no VERIFIED/green-1.0 top state; trust never 100%.
    assert "VERIFIED" not in {p["label"], p["claim"]}
    assert d["trust_ceiling"] < 1.0
    print("[7] no VERIFIED/green-1.0 top state; trust never 100%  OK")

    # 8) rollup signal shape.
    r = rollup_signal()
    assert set(("label", "organs_lit", "organs_total")) <= set(r)
    print(f"[8] rollup signal {{'label':'{r['label']}', 'organs_lit':{r['organs_lit']}/{r['organs_total']}}}  OK")

    print("\nok:true checks:8")
    _sys.exit(0)
