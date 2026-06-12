# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Co-Authored-By: Perplexity Computer Agent
"""
szl_sovereign_compute.py — ADDITIVE single-pane readiness for the SOVEREIGN
COMPUTE stack (a11oy). One honest endpoint + mobile panel that answers the
Warhacker-outbrief question: "is the agent running on our own GPU yet, and what
is real vs roadmap right now?"

It does NOT invent status. Every line is read live from surfaces already shipped:
  * brain      — GET /api/a11oy/v1/code/health      (inference: self-hosted-gpu |
                 hf-router | NO-CREDENTIAL; primary_model; #319)
  * embeddings — GET /api/a11oy/v1/alloy-embed-fabric/health (backend.kind:
                 self-hosted-gpu | hf-router | catalog-only; #320)
  * doctrine   — the LOCKED anchor (8 / 749-14-163 / c7c0ba17 / Λ=Conjecture 1),
                 surfaced verbatim, never recomputed here.

Each capability gets an honest tier:
  LIVE-SOVEREIGN  — running on our own GPU (self-hosted-gpu, reachable)
  LIVE-MANAGED    — live, but via a managed router (hf-router)
  HONEST-STUB     — up in a deterministic/catalog state, no live model (never faked)
  ROADMAP         — declared, not yet wired (e.g. PQC, Iron Bank) — label only

    from szl_sovereign_compute import register as register_sovereign_compute
    register_sovereign_compute(app, ns="a11oy")

Routes (NEW; never collide):
  GET /api/{ns}/v1/sovereign-compute        — JSON posture (machine-readable)
  GET /sovereign-compute                     — mobile-first HTML panel

Doctrine v11 LOCKED. SLSA L1 honest. Defensive: can never take down a route.
"""
from __future__ import annotations

import json as _json
import os as _os
import urllib.request as _ureq

DOCTRINE = {
    "version": "v11",
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_count": 8,
    "corpus": "749/14/163",
    "kernel_commit": "c7c0ba17",
    "lambda": "Conjecture 1 (advisory floor; unconditional uniqueness machine-checked FALSE; NOT a theorem)",
    "khipu_bft": "Conjecture 2",
    "slsa": "L1 honest (L2 .att emitted not independently verified; L3/FedRAMP/IronBank/CMMC = roadmap)",
}

# ROADMAP capabilities — declared, honestly NOT live until their dep/feed is wired.
ROADMAP = [
    {"id": "pqc", "name": "Post-quantum hybrid signing (ML-DSA/ML-KEM/SLH-DSA)",
     "tier": "ROADMAP", "note": "Wires LIVE when liboqs/oqs-python is in the image. Never fabricates a PQC sig today."},
    {"id": "ironbank", "name": "Iron Bank hardened base images",
     "tier": "ROADMAP", "note": "registry1.dso.mil base — unblocks FedRAMP/CMMC/IL-5/6 prework."},
    {"id": "wire_d_mesh", "name": "Wire D cross-mesh traceparent propagation",
     "tier": "ROADMAP", "note": "traceparent is in-process today; cross-organ needs >=2 organs live (mesh)."},
]


def _get_json(url: str, timeout: float = 6.0):
    try:
        req = _ureq.Request(url, headers={"User-Agent": "szl-sovereign-compute"})
        with _ureq.urlopen(req, timeout=timeout) as r:  # noqa: S310
            if r.status != 200:
                return None, r.status
            return _json.loads(r.read().decode()), 200
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def _self_base(ns: str) -> str:
    # Probe THIS process via loopback so the posture reflects the running app,
    # not a cached external view. Port honored from the app's own env.
    port = _os.environ.get("A11OY_PORT") or _os.environ.get("PORT") or "7860"
    return f"http://127.0.0.1:{port}"


def _brain_capability(base: str, ns: str) -> dict:
    data, code = _get_json(f"{base}/api/{ns}/v1/code/health")
    if not data:
        return {"id": "brain", "name": "Agent brain (code/chat completion)",
                "tier": "UNREACHABLE", "probe_http": code,
                "note": "code/health did not return 200 from loopback."}
    inf = data.get("inference", "")
    model = data.get("primary_model")
    if inf == "self-hosted-gpu":
        tier = "LIVE-SOVEREIGN"
    elif inf == "hf-router":
        tier = "LIVE-MANAGED"
    else:
        tier = "HONEST-STUB"
    return {"id": "brain", "name": "Agent brain (code/chat completion)", "tier": tier,
            "inference": inf, "mode": data.get("mode"), "primary_model": model,
            "router_base": data.get("router_base"), "token_source": data.get("token_source"),
            "note": ("Running on our own GPU." if tier == "LIVE-SOVEREIGN"
                     else "Live via managed HF Router." if tier == "LIVE-MANAGED"
                     else "Up in honest deterministic stub (no live model credential).")}


def _embed_capability(base: str, ns: str) -> dict:
    data, code = _get_json(f"{base}/api/{ns}/v1/alloy-embed-fabric/health")
    if not data:
        return {"id": "embeddings", "name": "Vertical retrieval embeddings",
                "tier": "UNREACHABLE", "probe_http": code,
                "note": "embed-fabric health did not return 200 from loopback."}
    b = data.get("backend", {})
    kind = b.get("kind", "")
    if kind == "self-hosted-gpu" and b.get("reachable"):
        tier = "LIVE-SOVEREIGN"
    elif kind == "self-hosted-gpu":
        tier = "WIRED-UNREACHABLE"
    elif kind == "hf-router":
        tier = "LIVE-MANAGED"
    else:
        tier = "HONEST-STUB"   # catalog-only
    return {"id": "embeddings", "name": "Vertical retrieval embeddings", "tier": tier,
            "kind": kind, "model": b.get("model"), "reachable": b.get("reachable"),
            "note": ("Live embedder on our own GPU." if tier == "LIVE-SOVEREIGN"
                     else "GPU endpoint configured but not reachable (check network/box)." if tier == "WIRED-UNREACHABLE"
                     else "Catalog-only: no live embedder wired (keyword retrieval still honest).")}


def _posture(ns: str) -> dict:
    base = _self_base(ns)
    caps = [_brain_capability(base, ns), _embed_capability(base, ns)]
    sovereign = any(c["tier"] == "LIVE-SOVEREIGN" for c in caps)
    summary = ("SOVEREIGN-GPU LIVE" if all(c["tier"] == "LIVE-SOVEREIGN" for c in caps)
               else "PARTIAL SOVEREIGN (some on own GPU)" if sovereign
               else "MANAGED/STUB — not yet on our GPU")
    return {
        "service": "sovereign-compute", "doctrine": DOCTRINE["version"],
        "summary": summary, "sovereign_any": sovereign,
        "capabilities": caps, "roadmap": ROADMAP, "doctrine_lock": DOCTRINE,
        "honesty": ("Every capability tier is derived from a live loopback probe of an "
                    "already-shipped health endpoint — never asserted. LIVE-SOVEREIGN means a "
                    "real self-hosted GPU endpoint answered; ROADMAP items are labelled, not faked."),
    }


def _html(p: dict) -> str:
    def chip(t: str) -> str:
        col = {"LIVE-SOVEREIGN": "#42d392", "LIVE-MANAGED": "#5fb8ff",
               "HONEST-STUB": "#e0b34a", "WIRED-UNREACHABLE": "#ff7b72",
               "UNREACHABLE": "#ff7b72", "ROADMAP": "#9aa7b4"}.get(t, "#9aa7b4")
        return f'<span class="tier" style="color:{col};border-color:{col}">{t}</span>'
    caps = "".join(f"""
      <article class="card">
        <div class="row"><h3>{c['name']}</h3>{chip(c['tier'])}</div>
        <p class="what">{c.get('note','')}</p>
        <p class="meta">{c.get('inference') or c.get('kind') or ''} {('· '+str(c.get('primary_model') or c.get('model') or '')) if (c.get('primary_model') or c.get('model')) else ''}</p>
      </article>""" for c in p["capabilities"])
    road = "".join(f"""
      <article class="card road">
        <div class="row"><h3>{r['name']}</h3>{chip(r['tier'])}</div>
        <p class="what">{r['note']}</p>
      </article>""" for r in p["roadmap"])
    d = p["doctrine_lock"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#0a0e14"><title>Sovereign Compute — a11oy</title>
<style>
 :root{{color-scheme:dark}} *{{box-sizing:border-box}}
 body{{margin:0;background:#0a0e14;color:#e6edf3;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
   padding:max(16px,env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom))}}
 header{{max-width:880px;margin:0 auto 18px}}
 h1{{font-size:clamp(1.4rem,5vw,2rem);margin:0 0 6px}}
 .summary{{font-weight:700;font-size:1.05rem;color:#42d392;margin:0 0 4px}}
 .sub{{color:#9aa7b4;font-size:.85rem}}
 .grid{{max-width:880px;margin:0 auto;display:grid;gap:14px;grid-template-columns:1fr}}
 @media(min-width:720px){{.grid{{grid-template-columns:1fr 1fr}}}}
 .card{{background:#111722;border:1px solid #1e2a3a;border-radius:14px;padding:15px}}
 .card.road{{opacity:.78}}
 .row{{display:flex;align-items:center;justify-content:space-between;gap:10px}}
 h3{{font-size:1rem;margin:0}}
 .tier{{font:600 .68rem/1 ui-monospace,monospace;letter-spacing:.05em;border:1px solid;border-radius:999px;padding:4px 9px;white-space:nowrap}}
 .what{{color:#c4cdd6;font-size:.88rem;margin:9px 0 4px}}
 .meta{{color:#6b7785;font-size:.76rem;font-family:ui-monospace,monospace;margin:0;word-break:break-word}}
 footer{{max-width:880px;margin:22px auto 0;color:#6b7785;font-size:.76rem}}
 .lock{{font-family:ui-monospace,monospace;color:#9aa7b4}}
</style></head><body>
<header>
  <h1>Sovereign Compute</h1>
  <p class="summary">{p['summary']}</p>
  <p class="sub">Live loopback probe of the running app. Each tier is read, never asserted.</p>
</header>
<main class="grid">{caps}{road}</main>
<footer>
  <p class="lock">Doctrine {d['version']} LOCKED · locked-proven={d['locked_count']} {{{', '.join(d['locked_proven'])}}} ·
  {d['corpus']} @ {d['kernel_commit']} · Λ = {d['lambda'].split('(')[0].strip()} (NOT a theorem) · {d['slsa'].split('(')[0].strip()}</p>
  <p>LIVE-SOVEREIGN = our own GPU answered · LIVE-MANAGED = managed router · HONEST-STUB = up, no live model · ROADMAP = declared, not faked.</p>
</footer></body></html>"""


def register(app, ns: str = "a11oy") -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get(f"/api/{ns}/v1/sovereign-compute")
    async def _sc_json():  # noqa: ANN202
        return JSONResponse(_posture(ns))

    @app.get("/sovereign-compute", response_class=HTMLResponse)
    async def _sc_panel():  # noqa: ANN202
        return HTMLResponse(_html(_posture(ns)))

    return {"ok": True, "ns": ns,
            "routes": [f"/api/{ns}/v1/sovereign-compute", "/sovereign-compute"]}


if __name__ == "__main__":
    import sys
    p = _posture("a11oy")
    print(f"[sovereign-compute] summary={p['summary']} caps={[c['tier'] for c in p['capabilities']]} "
          f"html_bytes={len(_html(p))}", file=sys.stderr)
