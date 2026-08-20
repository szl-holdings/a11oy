#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
szl_organ_health.py — SAME-ORIGIN organ-health proxy (G5 codename gate root-fix).
==================================================================================
WHY THIS EXISTS (no bandaid, root cause):
  /status (pages/status.html) used to run the health probe CLIENT-SIDE with the
  REAL backend hosts baked into the served HTML, e.g.
      https://szlholdings-amaru.hf.space/api/amaru/healthz
  That leaked the internal codenames (amaru/sentra/rosie) into served source —
  a Doctrine G5 violation ("0 user-visible codenames in served HTML/prose/URLs").

  Hiding the codename in the visible label was NOT enough: the *URL* the browser
  fetched still carried it. The only honest fix is to never let the browser see
  a codename subdomain at all. This module adds a SAME-ORIGIN proxy:

      GET /api/a11oy/v1/organ-health/<role>     role ∈ {reasoning,sentinel,operator,
                                                        memory,immune,companion,…}

  The browser asks the a11oy origin for an HONEST role slug. a11oy resolves the
  role → real backend healthz SERVER-SIDE, performs a GENUINE upstream check,
  and returns honest JSON:

      {"role": "reasoning", "label": "Reasoning tier (Memory)",
       "up": false, "status_code": 404, "latency_ms": 812,
       "checked_at": "...", "note": "..."}

  NO amaru/sentra/rosie ever appears in the request URL, the response body, or
  any served label. On any upstream failure (timeout, 5xx, 4xx, retired Space)
  we return up:false HONESTLY — we NEVER fabricate UP.

ROLE → BACKEND RESOLUTION (reuse existing org mapping, do NOT duplicate hosts):
  * codename → healthz URL : reused from the SHIPPED organ registry
                             szl_v4_fleet.PEER_HEALTH_URLS  (single source of
                             host truth that is actually present in the image).
  * codename → public label: reused from the SHARED G5 module
                             szl_codename_gate.MAP  (+ honest tier labels).
  This module owns ONLY the honest role-slug → codename indirection (no such
  slug map exists elsewhere); it imports the real hosts/labels, never re-hardcodes
  them. If neither registry imports at runtime, an unknown role returns an honest
  404 and a known role with no resolvable host returns up:false (never faked).

Doctrine: v11/v12 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (advisory, <1.0)
          · SLSA L1 honest / L2 roadmap · trust<100% · 0 runtime CDN · no key committed
          · G5: 0 user-visible codenames. ADDITIVE only.
DCO: Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Honest role-slug → internal codename indirection.
# The KEYS here are the ONLY identifiers a browser ever sends/sees. The VALUES
# (codenames) stay strictly server-side, used purely to look the backend host up
# in the existing organ registry. Multiple honest aliases map to one codename so
# the surface reads naturally (reasoning/memory → the reasoning organ, etc.).
# ---------------------------------------------------------------------------
_ROLE_TO_CODENAME: Dict[str, str] = {
    "reasoning": "amaru",
    "memory": "amaru",
    "brain": "amaru",
    "sentinel": "sentra",
    "immune": "sentra",
    "policy": "sentra",
    "operator": "rosie",
    "companion": "rosie",
    "care": "rosie",
    # honest direct surfaces (no codename) — resolved straight from the registry
    "orchestrator": "a11oy",
    "vessels": "killinchu",
    "drones": "killinchu",
}

# Honest, user-facing labels per role slug. These MUST NOT contain a codename.
# They mirror the already-honest labels shipped in pages/status.html and the
# Khipu constellation viz, and the public roles in szl_codename_gate.MAP.
_ROLE_LABEL: Dict[str, str] = {
    "reasoning": "Reasoning tier (Memory)",
    "memory": "Reasoning tier (Memory)",
    "brain": "Reasoning tier (Memory)",
    "sentinel": "Sentinel (Immune)",
    "immune": "Sentinel (Immune)",
    "policy": "Sentinel (Immune)",
    "operator": "Operator (Companion)",
    "companion": "Operator (Companion)",
    "care": "Operator (Companion)",
    "orchestrator": "a11oy",
    "vessels": "vessels (killinchu surface)",
    "drones": "vessels (killinchu surface)",
}

_TIMEOUT = 8.0  # seconds — server-side probe budget per upstream


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_health_url(codename: str) -> Optional[str]:
    """codename → real healthz URL, reusing the shipped organ registry
    (szl_v4_fleet.PEER_HEALTH_URLS). Returns None if unresolvable — we NEVER
    re-hardcode a second copy of the host map here."""
    try:
        import szl_v4_fleet  # shipped in the a11oy image (Dockerfile line ~150)

        url = getattr(szl_v4_fleet, "PEER_HEALTH_URLS", {}).get(codename)
        if url:
            return url
    except Exception:  # pragma: no cover — registry import best-effort
        pass
    return None


def _honest_label(role: str, codename: str) -> str:
    """Honest public label for a role slug. Prefer our role→label table; fall
    back to the shared szl_codename_gate.MAP public role for the codename so the
    label is ALWAYS the honest public role, never the codename."""
    lbl = _ROLE_LABEL.get(role)
    if lbl:
        return lbl
    try:
        import szl_codename_gate

        return szl_codename_gate.MAP.get(codename, role)
    except Exception:  # pragma: no cover
        return role


def probe_role(role: str) -> Tuple[int, dict]:
    """Server-side health probe for an honest role slug.

    Returns (http_status_for_proxy, payload). The proxy itself answers 200 with
    an honest body whenever the role is known (even if the upstream is down →
    up:false); it answers 404 only for an UNKNOWN role slug. We never fabricate
    UP and never leak a codename into the payload."""
    role_key = (role or "").strip().lower()
    codename = _ROLE_TO_CODENAME.get(role_key)
    if not codename:
        return 404, {
            "ok": False,
            "role": role_key,
            "error": "unknown role",
            "known_roles": sorted(_ROLE_TO_CODENAME.keys()),
            "checked_at": _now(),
        }

    label = _honest_label(role_key, codename)
    url = _resolve_health_url(codename)
    payload: dict = {
        "ok": True,
        "role": role_key,
        "label": label,
        "up": False,
        "status_code": None,
        "latency_ms": None,
        "checked_at": _now(),
        "source": "a11oy same-origin organ-health proxy (real upstream check)",
    }

    if not url:
        payload["note"] = "backend host not resolvable from organ registry — reported down honestly"
        return 200, payload

    t0 = time.monotonic()
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "a11oy-organ-health-proxy/1.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310 (trusted internal estate)
            code = int(getattr(r, "status", r.getcode()))
            body = r.read(65536)
        payload["latency_ms"] = int(round((time.monotonic() - t0) * 1000))
        payload["status_code"] = code
        payload["up"] = code == 200
        if code != 200:
            payload["note"] = "upstream reachable but not healthy (HTTP %d)" % code
        else:
            # surface a couple of honest upstream fields if present (never invented)
            try:
                j = json.loads(body.decode("utf-8", "replace"))
                if isinstance(j, dict):
                    for k in ("doctrine", "declarations", "version", "axioms"):
                        if k in j:
                            payload[k] = j[k]
            except Exception:
                pass
    except urllib.error.HTTPError as e:
        payload["latency_ms"] = int(round((time.monotonic() - t0) * 1000))
        payload["status_code"] = int(e.code)
        payload["up"] = False
        payload["note"] = "upstream HTTP error %d — reported down honestly" % int(e.code)
    except Exception as e:
        payload["latency_ms"] = int(round((time.monotonic() - t0) * 1000))
        payload["up"] = False
        payload["note"] = "upstream unreachable (%s) — reported down honestly" % type(e).__name__

    return 200, payload


# ---------------------------------------------------------------------------
# FastAPI registration (mirrors the additive register() pattern used across the
# a11oy surface: append @app.get routes, then MOVE them to the front so they win
# over the /api/a11oy/{path:path} Node proxy + the SPA /{full_path:path} catch-all).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    b = f"/api/{ns}/v1/organ-health"
    _n_before = len(app.router.routes)

    @app.get(b + "/{role}")
    @app.get("/v1/organ-health/{role}")
    async def _organ_health(role: str):  # type: ignore
        status, payload = probe_role(role)
        return JSONResponse(payload, status_code=status)

    @app.get(b)
    @app.get("/v1/organ-health")
    async def _organ_health_index():  # type: ignore
        return JSONResponse({
            "ok": True,
            "roles": sorted(_ROLE_TO_CODENAME.keys()),
            "labels": {r: _ROLE_LABEL.get(r) for r in sorted(_ROLE_LABEL.keys())},
            "usage": b + "/<role>",
            "honesty": ("Same-origin proxy: a11oy resolves an honest role slug to "
                        "the real backend healthz server-side and returns honest "
                        "up/down. No internal codename appears in any served URL, "
                        "label, or response body. Down upstreams report up:false; "
                        "health is never fabricated."),
            "checked_at": _now(),
        })

    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        _moved = len(_new)
    except Exception as _e:  # never fatal
        _moved = -1
        print(f"[a11oy] organ-health route reorder failed (non-fatal): {_e!r}", file=sys.stderr)

    print(f"[a11oy] organ-health proxy registered: {b}/<role> [moved {_moved} routes to front]",
          file=sys.stderr)
    return "organ-health-ok moved=%s roles=%d" % (_moved, len(_ROLE_TO_CODENAME))


# CLI: `python szl_organ_health.py reasoning sentinel operator` for a quick honest probe.
if __name__ == "__main__":
    args = sys.argv[1:] or ["reasoning", "sentinel", "operator"]
    rc = 0
    for a in args:
        st, p = probe_role(a)
        print(json.dumps(p, indent=2))
        if st == 404:
            rc = 2
    sys.exit(rc)
