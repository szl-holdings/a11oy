# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_brain_command.py — WAVE O / DEV 5: the founder's "Brain powering the ecosystem"
COMMAND view.

This is the read-only command/dashboard layer over the Brain nervous-system hub.
It answers, in ONE honest signed rollup: what has the Brain HARVESTED (knowledge),
what has it HARNESSED (energy), how many organs/surfaces are LIT, what is the Λ
advisory, and — for any surface — what energy/knowledge budget is the Brain feeding
it right now. Each command snapshot is DSSE-signed (REAL in-Space, honest
UNSIGNED-LOCAL locally).

DESIGN — READS the Brain, never re-computes it, never fabricates:
  * Preferred source is Dev-1's central hub `szl_brain_hub` (GET /brain/pulse) and,
    for the subscribe/budget view, `szl_brain_hub.subscribe(surface_id)`. We call it
    IN-PROCESS via a guarded import so we don't depend on the HTTP hop or on merge
    ordering.
  * GUARDED FALLBACK: if #brain-hub is not merged yet (module absent), we compose an
    HONEST pulse locally from the already-shipped organs:
        - knowledge  ← a11oy_brain_graph (distinct_artifacts / node_count, the honest
                        headline the graph itself publishes; MODELED label)
        - energy     ← szl_energy_ledger totals (MEASURED joules if the ledger has
                        real NVML-attested entries, else honest MODELED/UNAVAILABLE)
        - surfaces   ← szl3d_holographic.SURFACES count (the lit living body)
    and we tag the pulse `source:"local-fallback"` + `pulse_ok:false` so a consumer
    knows the hub is not yet the source of truth. NEVER a fabricated joule; UNAVAILABLE
    when telemetry is absent.

HONESTY (Doctrine v11, verbatim — never upgraded):
  * Λ = Conjecture 1 — advisory, NEVER "green"/"theorem"/"proven".
  * locked-proven == 8; the Brain harvest adds NOTHING to it.
  * Honest labels only: LIVE / SAMPLE / SIMULATED / MODELED / CACHED / PROVEN /
    CONJECTURE / UNAVAILABLE. Trust ceiling 0.97 (never 1.0).
  * Real DSSE signature in-Space (szl_dsse); honest UNSIGNED-LOCAL otherwise — no
    fabricated signature.

Endpoints (additive, registered BEFORE the SPA catch-all, pure reads):
  GET /api/<ns>/v1/brain/command
      → the founder dashboard rollup: {knowledge, energy, surfaces_lit, lambda,
        pulse_ok, source, labels, receipt}
  GET /api/<ns>/v1/brain/command/subscribe/{surface_id}
      → what energy/knowledge budget the Brain allocates to that surface right now
        (delegates to the hub's subscribe when present; honest local allocation
        otherwise), each signed.

Stdlib + already-shipped repo modules only. 0 CDN, 0 Node, 0 new dependency.
"""
from __future__ import annotations

import datetime
from typing import Any, Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover — FastAPI always present in the Space
    FastAPI = Any  # type: ignore
    JSONResponse = None  # type: ignore

# ---- honest label vocabulary (Doctrine v11) -------------------------------- #
LBL_LIVE = "LIVE"
LBL_MEASURED = "MEASURED"
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"
LAMBDA_ADVISORY = "Λ = Conjecture 1 — advisory only; NEVER green/theorem/proven."
TRUST_CEILING = 0.97
LOCKED_PROVEN = 8  # harvest adds nothing to it

_RECEIPT_TYPE = "application/vnd.szl.brain.command+json"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Signed receipt — REAL DSSE in-Space, honest UNSIGNED-LOCAL otherwise.
# --------------------------------------------------------------------------- #
def _sign(payload: dict) -> dict:
    try:
        import szl_dsse
        env = szl_dsse.sign_payload(payload, payload_type=_RECEIPT_TYPE)
        return env
    except Exception as e:  # pragma: no cover — never fail the read on signer absence
        return {
            "payloadType": _RECEIPT_TYPE,
            "signed": False,
            "signatures": [],
            "honesty": f"UNSIGNED-LOCAL — signer unavailable ({type(e).__name__}); no signature fabricated.",
            "_signed_at": _now(),
        }


# --------------------------------------------------------------------------- #
# Knowledge summary — reuse a11oy_brain_graph's OWN honest headline. Never restate.
# --------------------------------------------------------------------------- #
def _knowledge_summary(ns: str = "a11oy") -> dict:
    try:
        import a11oy_brain_graph as _bg
        g = _bg.get_brain_graph(ns)
        return {
            "label": LBL_MODELED,
            "distinct_artifacts": g.get("distinct_artifacts"),
            "node_count": g.get("node_count"),
            "link_count": g.get("link_count"),
            "person_node_count": g.get("person_node_count"),
            "artifact_note": g.get("artifact_note"),
            "source": "a11oy_brain_graph",
            "note": ("distinct_artifacts is the honest headline (excludes arXiv "
                     "co-author person nodes); never present the raw node_count as "
                     "all distinct work."),
        }
    except Exception as e:
        return {
            "label": LBL_UNAVAILABLE,
            "distinct_artifacts": None,
            "node_count": None,
            "source": "a11oy_brain_graph",
            "note": f"brain graph unavailable ({type(e).__name__}); no count fabricated.",
        }


# --------------------------------------------------------------------------- #
# Energy summary — MEASURED joules only from the real ledger; MODELED for dry-run
# projections; UNAVAILABLE when the ledger/telemetry is absent. NEVER fabricate.
# --------------------------------------------------------------------------- #
def _energy_summary() -> dict:
    try:
        import szl_energy_ledger as _el
        ledger = _el.get_ledger()
        t = ledger.totals()
        joules_measured = t.get("joules_measured_billable", 0.0) or 0.0
        jobs = t.get("jobs", 0) or 0
        # Honest label selection: MEASURED only when the ledger carries real
        # NVML-attested billable joules; else MODELED (dry-run projection) if there
        # are jobs at all; else UNAVAILABLE (nothing harnessed yet — never faked).
        if joules_measured > 0.0:
            label = LBL_MEASURED
        elif jobs > 0:
            label = LBL_MODELED
        else:
            label = LBL_UNAVAILABLE
        return {
            "label": label,
            "joules_measured_billable": round(float(joules_measured), 6),
            "kwh_total": t.get("kwh_total"),
            "tokens_total": t.get("tokens_total"),
            "jobs": jobs,
            "would_charge_cents": t.get("would_charge_cents"),  # MODELED dry-run
            "charged_cents": t.get("charged_cents"),            # MEASURED cleared
            "source": "szl_energy_ledger",
            "note": ("MEASURED = real NVML-attested billable joules in the chain; "
                     "MODELED = dry-run projection; UNAVAILABLE = no telemetry. "
                     "Joules are never fabricated."),
        }
    except Exception as e:
        return {
            "label": LBL_UNAVAILABLE,
            "joules_measured_billable": None,
            "source": "szl_energy_ledger",
            "note": f"energy ledger unavailable ({type(e).__name__}); no joule fabricated.",
        }


# --------------------------------------------------------------------------- #
# Surfaces lit — the living-body organ/surface count (the estate the Brain powers).
# --------------------------------------------------------------------------- #
def _surfaces_lit() -> dict:
    try:
        import szl3d_holographic as _holo
        n = len(getattr(_holo, "SURFACES", []) or [])
        return {"label": LBL_LIVE if n > 0 else LBL_UNAVAILABLE, "count": n,
                "source": "szl3d_holographic.SURFACES"}
    except Exception as e:
        return {"label": LBL_UNAVAILABLE, "count": None,
                "source": "szl3d_holographic.SURFACES",
                "note": f"surface registry unavailable ({type(e).__name__})."}


# --------------------------------------------------------------------------- #
# The ecosystem pulse — Dev-1 hub first (in-process, guarded), local fallback else.
# --------------------------------------------------------------------------- #
def _hub_pulse(ns: str = "a11oy") -> Optional[dict]:
    """Try to read Dev-1's central hub pulse in-process. Returns None if the hub
    module (szl_brain_hub) is not merged / not importable — NEVER raises."""
    try:
        import szl_brain_hub as _hub  # Dev-1 (feat/brain-hub) — may not be merged yet
    except Exception:
        return None
    # Tolerate a few plausible function names the hub may expose; never invent data.
    for fn_name in ("build_pulse", "pulse", "get_pulse", "current_pulse"):
        fn = getattr(_hub, fn_name, None)
        if callable(fn):
            try:
                p = fn(ns) if _fn_takes_arg(fn) else fn()
                if isinstance(p, dict):
                    return p
            except Exception:
                return None
    return None


def _fn_takes_arg(fn) -> bool:
    try:
        import inspect
        return len(inspect.signature(fn).parameters) >= 1
    except Exception:
        return False


def build_command(ns: str = "a11oy") -> dict:
    """The founder dashboard rollup. Prefers Dev-1's live hub pulse; falls back to
    an HONEST locally-composed pulse (pulse_ok:false) when the hub isn't merged."""
    hub = _hub_pulse(ns)
    if hub is not None:
        knowledge = hub.get("knowledge") or _knowledge_summary(ns)
        energy = hub.get("energy") or _energy_summary()
        surfaces = hub.get("surfaces_lit")
        if not isinstance(surfaces, dict):
            _s = _surfaces_lit()
            surfaces = {"count": (surfaces if isinstance(surfaces, int) else _s["count"]),
                        "label": _s["label"], "source": _s["source"]}
        source = "brain-hub"
        pulse_ok = True
    else:
        knowledge = _knowledge_summary(ns)
        energy = _energy_summary()
        surfaces = _surfaces_lit()
        source = "local-fallback"
        pulse_ok = False

    payload = {
        "view": "brain-command",
        "ns": ns,
        "source": source,          # brain-hub | local-fallback
        "pulse_ok": pulse_ok,      # true only when Dev-1's hub is the source of truth
        "knowledge": knowledge,    # what the Brain has HARVESTED
        "energy": energy,          # what the Brain has HARNESSED
        "surfaces_lit": surfaces,  # the living body it powers
        "lambda": {"label": "CONJECTURE", "value": "Conjecture 1", "advisory": LAMBDA_ADVISORY},
        "locked_proven": LOCKED_PROVEN,
        "trust_ceiling": TRUST_CEILING,
        "labels": [LBL_LIVE, LBL_MEASURED, LBL_MODELED, LBL_UNAVAILABLE, "CONJECTURE"],
        "note": ("Read-only command view over the Brain nervous-system hub. When "
                 "source=local-fallback the central hub (Dev-1 /brain/pulse) is not "
                 "yet merged and this rollup is composed honestly from the shipped "
                 "organs — pulse_ok is false. Λ = Conjecture 1; nothing here touches "
                 "the locked-8."),
        "generated_at": _now(),
    }
    payload["receipt"] = _sign(payload_snapshot(payload))
    return payload


def payload_snapshot(payload: dict) -> dict:
    """The deterministic subset that gets signed (excludes volatile timestamp + the
    receipt itself so the DSSE PAE is stable for the same underlying pulse)."""
    return {
        "view": payload["view"],
        "ns": payload["ns"],
        "source": payload["source"],
        "pulse_ok": payload["pulse_ok"],
        "knowledge_distinct_artifacts": (payload["knowledge"] or {}).get("distinct_artifacts"),
        "energy_label": (payload["energy"] or {}).get("label"),
        "energy_joules_measured": (payload["energy"] or {}).get("joules_measured_billable"),
        "surfaces_lit": (payload["surfaces_lit"] or {}).get("count"),
        "lambda": "Conjecture 1",
        "locked_proven": LOCKED_PROVEN,
    }


# --------------------------------------------------------------------------- #
# Subscribe / budget — "what is the Brain feeding this surface right now?"
# Delegates to the hub's subscribe when present; honest local allocation else.
# --------------------------------------------------------------------------- #
def build_subscribe(surface_id: str, ns: str = "a11oy") -> dict:
    surface_id = (surface_id or "").strip()
    # Prefer Dev-1's hub allocation if merged (in-process, guarded).
    try:
        import szl_brain_hub as _hub
        for fn_name in ("subscribe", "budget_for", "allocation"):
            fn = getattr(_hub, fn_name, None)
            if callable(fn):
                try:
                    alloc = fn(surface_id, ns) if _fn_takes_two(fn) else fn(surface_id)
                    if isinstance(alloc, dict):
                        alloc.setdefault("source", "brain-hub")
                        alloc.setdefault("surface_id", surface_id)
                        out = {"view": "brain-subscribe", "ns": ns, "surface_id": surface_id,
                               "allocation": alloc, "source": "brain-hub",
                               "lambda": {"label": "CONJECTURE", "value": "Conjecture 1",
                                          "advisory": LAMBDA_ADVISORY},
                               "generated_at": _now()}
                        out["receipt"] = _sign({"view": "brain-subscribe", "surface_id": surface_id,
                                                "source": "brain-hub"})
                        return out
                except Exception:
                    pass
    except Exception:
        pass

    # HONEST local allocation: a simple, transparent share of the current pulse.
    # This is a MODELED allocation function (equal per-surface floor) — NOT a live
    # per-organ energy meter. Labeled MODELED so no one reads it as measured.
    cmd = build_command(ns)
    n = (cmd["surfaces_lit"] or {}).get("count") or 0
    energy = cmd["energy"] or {}
    joules_total = energy.get("joules_measured_billable")
    known = _surface_known(surface_id)
    if n and isinstance(joules_total, (int, float)) and joules_total:
        joule_share = round(float(joules_total) / float(n), 6)
        energy_label = energy.get("label", LBL_MODELED)
    else:
        joule_share = None
        energy_label = LBL_UNAVAILABLE
    knowledge = cmd["knowledge"] or {}
    alloc = {
        "surface_id": surface_id,
        "known_surface": known,
        "source": "local-fallback",
        "energy": {
            "label": (energy_label if energy_label == LBL_UNAVAILABLE else LBL_MODELED),
            "joules_share_modeled": joule_share,
            "policy": "equal-share floor over lit surfaces",
            "note": ("MODELED equal-share allocation over the currently lit surfaces "
                     "from the harnessed-energy pool; not a live per-organ meter. "
                     "UNAVAILABLE when no measured joules are in the ledger."),
        },
        "knowledge": {
            "label": (LBL_MODELED if knowledge.get("distinct_artifacts") is not None else LBL_UNAVAILABLE),
            "corpus": "brain",
            "distinct_artifacts_available": knowledge.get("distinct_artifacts"),
            "note": ("The full harvested Brain vault is available to every surface as "
                     "a first-class corpus; this counts what is harvestable, not a "
                     "per-surface reservation."),
        },
    }
    out = {"view": "brain-subscribe", "ns": ns, "surface_id": surface_id,
           "allocation": alloc, "source": "local-fallback", "pulse_ok": cmd["pulse_ok"],
           "lambda": {"label": "CONJECTURE", "value": "Conjecture 1", "advisory": LAMBDA_ADVISORY},
           "note": ("Local honest allocation because the central hub (Dev-1) is not "
                    "merged yet; delegates to szl_brain_hub.subscribe when present."),
           "generated_at": _now()}
    out["receipt"] = _sign({"view": "brain-subscribe", "surface_id": surface_id,
                            "source": "local-fallback", "joules_share_modeled": joule_share})
    return out


def _fn_takes_two(fn) -> bool:
    try:
        import inspect
        return len(inspect.signature(fn).parameters) >= 2
    except Exception:
        return False


def _surface_known(surface_id: str) -> bool:
    try:
        import szl3d_holographic as _holo
        return any((s.get("id") == surface_id) for s in getattr(_holo, "SURFACES", []) or [])
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# healthz rollup helper — the compact {knowledge_nodes, energy_label,
# surfaces_lit, pulse_ok} field consumed by GET /api/a11oy/healthz. Never raises.
# --------------------------------------------------------------------------- #
def healthz_brain(ns: str = "a11oy") -> dict:
    try:
        k = _knowledge_summary(ns)
        e = _energy_summary()
        s = _surfaces_lit()
        pulse_ok = _hub_pulse(ns) is not None
        return {
            "knowledge_nodes": k.get("distinct_artifacts", k.get("node_count")),
            "energy_label": e.get("label", LBL_UNAVAILABLE),
            "surfaces_lit": s.get("count"),
            "pulse_ok": bool(pulse_ok),
            "lambda": "Conjecture 1",
            "source": ("brain-hub" if pulse_ok else "local-fallback"),
            "note": ("Compact Brain rollup. pulse_ok=false means Dev-1's central hub "
                     "(/brain/pulse) is not yet merged; counts are composed honestly "
                     "from the shipped organs. Λ = Conjecture 1."),
        }
    except Exception as e:  # pragma: no cover — healthz must never 500 on this
        return {
            "knowledge_nodes": None,
            "energy_label": LBL_UNAVAILABLE,
            "surfaces_lit": None,
            "pulse_ok": False,
            "error": f"{type(e).__name__}",
            "note": "Brain rollup unavailable; nothing fabricated.",
        }


# --------------------------------------------------------------------------- #
# FastAPI registration — additive, before the SPA catch-all. Pure reads.
# --------------------------------------------------------------------------- #
def register(app: "FastAPI", ns: str = "a11oy") -> str:
    base = f"/api/{ns}/v1/brain/command"

    @app.get(base)
    async def brain_command():  # noqa: ANN202
        return JSONResponse(build_command(ns))

    @app.get(f"{base}/subscribe/{{surface_id}}")
    async def brain_command_subscribe(surface_id: str):  # noqa: ANN202
        return JSONResponse(build_subscribe(surface_id, ns))

    return f"GET {base} + {base}/subscribe/{{surface_id}}"


# --------------------------------------------------------------------------- #
# Self-test (stdlib, network-free) — proves honest shape + never-500 guarantees.
# --------------------------------------------------------------------------- #
def _selftest() -> dict:
    cmd = build_command("a11oy")
    assert cmd["view"] == "brain-command"
    assert cmd["lambda"]["value"] == "Conjecture 1", "Λ must be Conjecture 1"
    assert cmd["locked_proven"] == 8, "locked-proven must stay 8"
    assert cmd["source"] in ("brain-hub", "local-fallback")
    assert "receipt" in cmd and "payloadType" in cmd["receipt"]
    # honest energy label vocabulary only
    assert (cmd["energy"] or {}).get("label") in (LBL_LIVE, LBL_MEASURED, LBL_MODELED, LBL_UNAVAILABLE)
    sub = build_subscribe("brain", "a11oy")
    assert sub["view"] == "brain-subscribe"
    assert "receipt" in sub
    hz = healthz_brain("a11oy")
    assert set(["knowledge_nodes", "energy_label", "surfaces_lit", "pulse_ok"]).issubset(hz.keys())
    assert isinstance(hz["pulse_ok"], bool)
    return {"ok": True, "source": cmd["source"], "pulse_ok": cmd["pulse_ok"],
            "energy_label": (cmd["energy"] or {}).get("label"),
            "surfaces_lit": (cmd["surfaces_lit"] or {}).get("count")}


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2))
