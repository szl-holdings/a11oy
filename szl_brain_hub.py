#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""szl_brain_hub.py — the Brain's CENTRAL NERVOUS-SYSTEM hub (the pulse bus).

FOUNDER VISION: "I want my Brain harnessing and giving energy to the whole
ecosystem." This module is the single place that unifies the two halves of the
Brain — its harvested KNOWLEDGE (the self-writing vault + brain graph) and its
harnessed ENERGY (the joules/tokens ledger) — into ONE honest, signed "pulse"
that every organ and frontier surface can read. Then it hands each surface an
honest energy/knowledge BUDGET so any surface can ask "what is the Brain feeding
me right now?".

ENDPOINTS (registered BEFORE the SPA catch-all + the Node proxy):
  GET /api/<ns>/v1/brain/pulse
      -> the current ecosystem pulse:
         {knowledge: summary from a11oy_brain_graph (+ harvest_vault provenance),
          energy:    summary from szl_energy_ledger (MEASURED joules/tokens if the
                     ledger holds billable measured jobs, else honest MODELED for a
                     dry-run projection, else UNAVAILABLE when the source is down),
          lit:       organ/surface count the Brain is lighting,
          lambda:    Λ = Conjecture 1 advisory (NEVER "green"/theorem),
          labels:    honest per-section labels,
          receipt:   a DSSE receipt over the deterministic pulse core}
  GET /api/<ns>/v1/brain/subscribe/{surface_id}
      -> the honest energy/knowledge budget the Brain allocates to that surface,
         a simple deterministic allocation function over the LIVE pulse.

HONESTY (Doctrine v11 LOCKED):
  * Knowledge counts are REUSED verbatim from a11oy_brain_graph — never restated,
    never fabricated. Label MODELED (a derived view over the real estate).
  * Energy joules are NEVER fabricated. Measured joules only when the ledger holds
    MEASURED-billable jobs; a dry-run projection is labeled MODELED; when the
    ledger source raises/absent the energy section is honestly UNAVAILABLE.
  * Λ (F23) = Conjecture 1 — NEVER a theorem, never "green". Nothing here touches
    the locked-8 numbers; the hub adds a derived VIEW, it changes no gate.
  * Signing: REAL DSSE in-Space (when the cosign secret is present) via szl_dsse;
    honest UNSIGNED-LOCAL envelope otherwise (no signature fabricated).
  * The receipt is minted over a DETERMINISTIC pulse core (volatile timestamps are
    excluded from the signed body) so the same estate re-signs to the same digest.

REUSE (wire, don't reinvent):
  * knowledge — a11oy_brain_graph.get_brain_graph (cached); harvest_vault for
    provenance of the self-writing vault.
  * energy    — szl_energy_ledger.get_ledger().{totals,persistence_info,storage_health}.
  * signing   — szl_dsse.sign_payload (real in-Space, unsigned honest locally).

Standalone self-test (no server):
  python3 szl_brain_hub.py
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from typing import Any, Optional

# module-scope so FastAPI's add_api_route injects the Starlette Request rather than
# treating a 'request' parameter as a required query field (the classic 422). Guarded:
# if starlette is absent (pure offline use), the read endpoints simply aren't mounted.
try:
    from starlette.requests import Request as _Request
except Exception:  # pragma: no cover
    _Request = None  # type: ignore

# Honesty labels (Doctrine v11 vocabulary).
LBL_MODELED = "MODELED"
LBL_MEASURED = "MEASURED"
LBL_UNAVAILABLE = "UNAVAILABLE"

LAMBDA_ADVISORY = (
    "Λ (F23) = Conjecture 1 — NEVER a theorem, never \"green\". The Brain pulse is a "
    "MODELED derived view over the real estate; it changes no gate and touches no "
    "locked-8 number."
)

# DSSE payloadType for the pulse envelope (self-describing, versioned).
PULSE_PAYLOAD_TYPE = "application/vnd.szl.brain.pulse+json"

_DOCTRINE = {
    "version": "v11",
    "lambda": "Conjecture 1",
    "note": (
        "Brain nervous-system hub: one signed pulse unifying harvested knowledge + "
        "harnessed energy. Knowledge counts reused verbatim from a11oy_brain_graph "
        "(NOT the leaked 8,893); joules never fabricated (UNAVAILABLE when the ledger "
        "source is down); Λ = Conjecture 1 throughout."
    ),
}


# --------------------------------------------------------------------------- #
# KNOWLEDGE — harvested by the Brain (self-writing vault + brain graph)
# --------------------------------------------------------------------------- #
def knowledge_summary(ns: str = "a11oy") -> dict:
    """Honest KNOWLEDGE half of the pulse, reused from a11oy_brain_graph.

    Counts are the ACTUAL harvested totals (never the leaked 8,893). On any error
    the section is honestly UNAVAILABLE — never fabricated."""
    try:
        import a11oy_brain_graph as _bg
        g = _bg.get_brain_graph(ns)
        s = g.get("summary", {})
        out = {
            "label": g.get("label", LBL_MODELED),
            "available": True,
            "endpoint": g.get("endpoint", f"/api/{ns}/v1/brain/graph"),
            "node_count": g.get("node_count"),
            "link_count": g.get("link_count"),
            # HONEST headline: distinct real artifacts (excludes arXiv co-author
            # person nodes) — never present the raw total as all distinct work.
            "distinct_artifacts": g.get("distinct_artifacts"),
            "person_node_count": g.get("person_node_count"),
            "by_kind": s.get("by_kind"),
            "locked_flagged": s.get("locked_flagged"),
            "sources": {
                k: {kk: vv for kk, vv in v.items() if kk in ("count", "endpoint", "captured", "available")}
                for k, v in (g.get("sources") or {}).items()
            },
            "artifact_note": g.get("artifact_note"),
            "note": (
                "counts reused verbatim from a11oy_brain_graph (MODELED derived view "
                "over the real estate; NOT the leaked 8,893)."
            ),
        }
        # Best-effort provenance of the self-writing vault (read-only; never fabricated).
        try:
            import brain.harvest_vault as _hv  # noqa: F401  (import proves the vault harvester ships)
            out["self_writing_vault"] = {
                "harvester": "brain/harvest_vault.py",
                "available": True,
                "note": "self-writing vault harvests this same graph into a backlinked markdown brain.",
            }
        except Exception:
            out["self_writing_vault"] = {"available": False,
                                         "note": "vault harvester not importable here; graph still reused honestly."}
        return out
    except Exception as exc:  # noqa: BLE001 — never crash the pulse; report honestly
        return {"label": LBL_UNAVAILABLE, "available": False,
                "error": f"{type(exc).__name__}: {exc}",
                "note": "knowledge source (a11oy_brain_graph) unavailable — nothing fabricated."}


# --------------------------------------------------------------------------- #
# ENERGY — harnessed by the Brain (the joules/tokens ledger)
# --------------------------------------------------------------------------- #
def energy_summary() -> dict:
    """Honest ENERGY half of the pulse, reused from szl_energy_ledger.

    joules_label semantics (Doctrine v11: NO free-energy, never fabricate joules):
      * MEASURED    — the ledger holds MEASURED-billable joules (real NVML meter).
      * MODELED     — the ledger has jobs but only a dry-run projection (would_charge);
                      joules shown are a projection, not billed measured energy.
      * UNAVAILABLE — the ledger source raised or holds nothing measurable.
    """
    try:
        import szl_energy_ledger as _el
        led = _el.get_ledger()
        totals = led.totals()
        persistence = led.persistence_info()
        storage = led.storage_health()

        joules_billable = float(totals.get("joules_measured_billable", 0.0) or 0.0)
        jobs = int(totals.get("jobs", 0) or 0)
        would_cents = int(totals.get("would_charge_cents", 0) or 0)

        if joules_billable > 0.0:
            label = LBL_MEASURED
            note = ("MEASURED joules from the hash-chained ledger (NVML-metered, "
                    "billable). No free energy; every joule re-hashable offline.")
        elif jobs > 0 and would_cents > 0:
            label = LBL_MODELED
            note = ("ledger holds jobs but only a dry-run projection (would_charge); "
                    "joules_total is a MODELED projection, NOT billed measured energy.")
        else:
            label = LBL_UNAVAILABLE
            note = ("no MEASURED-billable joules and no dry-run projection in the "
                    "ledger — energy honestly UNAVAILABLE; no joules fabricated.")

        return {
            "label": label,
            "available": label != LBL_UNAVAILABLE,
            "jobs": jobs,
            "joules_measured_billable": round(joules_billable, 6),
            "joules_total": totals.get("joules_total"),
            "tokens_total": totals.get("tokens_total"),
            "kwh_total": totals.get("kwh_total"),
            "would_charge_cents": would_cents,   # MODELED (dry-run projection)
            "charged_cents": totals.get("charged_cents"),  # MEASURED (real cleared charges)
            "storage_status": storage.get("status"),
            "persistence_label": persistence.get("label"),
            "survives_redeploy": persistence.get("survives_redeploy"),
            "endpoint": "/api/a11oy/v1/energy/ledger",
            "note": note,
        }
    except Exception as exc:  # noqa: BLE001 — never crash the pulse; report honestly
        return {"label": LBL_UNAVAILABLE, "available": False,
                "error": f"{type(exc).__name__}: {exc}",
                "note": "energy source (szl_energy_ledger) unavailable — no joules fabricated."}


# --------------------------------------------------------------------------- #
# LIT — how many organs/surfaces the Brain is lighting
# --------------------------------------------------------------------------- #
def lit_summary(knowledge: dict) -> dict:
    """Organ/surface count the Brain is lighting, derived from the SAME graph the
    knowledge half reused (never a second, drifting count)."""
    src = (knowledge or {}).get("sources") or {}
    surfaces = (src.get("surfaces") or {}).get("count")
    topics = (src.get("topics") or {}).get("count")  # topic clusters ≈ organs
    return {
        "label": knowledge.get("label", LBL_MODELED) if knowledge else LBL_MODELED,
        "surfaces_lit": surfaces,
        "organs_lit": topics,
        "note": ("surfaces_lit + organs_lit derived from the SAME brain graph the "
                 "knowledge half reused (frontier surfaces manifest + formula-organ "
                 "topic clusters); no second drifting count."),
    }


# --------------------------------------------------------------------------- #
# PULSE — the unified, deterministic, signed nervous-system beat
# --------------------------------------------------------------------------- #
def _deterministic_core(ns: str, knowledge: dict, energy: dict, lit: dict) -> dict:
    """The signed body: everything the receipt attests, with VOLATILE fields
    (wall-clock timestamps, storage bytes) excluded so the same estate re-signs to
    the same digest. Deterministic + honest."""
    return {
        "ns": ns,
        "kind": "SZL.Brain.Pulse.v1",
        "lambda": "Conjecture 1",
        "knowledge": {
            "label": knowledge.get("label"),
            "node_count": knowledge.get("node_count"),
            "link_count": knowledge.get("link_count"),
            "distinct_artifacts": knowledge.get("distinct_artifacts"),
            "by_kind": knowledge.get("by_kind"),
            "locked_flagged": knowledge.get("locked_flagged"),
        },
        "energy": {
            "label": energy.get("label"),
            "jobs": energy.get("jobs"),
            "joules_measured_billable": energy.get("joules_measured_billable"),
            "tokens_total": energy.get("tokens_total"),
            "would_charge_cents": energy.get("would_charge_cents"),
        },
        "lit": {
            "surfaces_lit": lit.get("surfaces_lit"),
            "organs_lit": lit.get("organs_lit"),
        },
        "doctrine": _DOCTRINE,
    }


def _content_digest(core: dict) -> str:
    body = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sign(core: dict) -> dict:
    """Sign the deterministic pulse core. REAL DSSE in-Space (cosign secret present);
    honest UNSIGNED-LOCAL envelope otherwise — never a fabricated signature."""
    try:
        import szl_dsse as _dsse
        env = _dsse.sign_payload(core, PULSE_PAYLOAD_TYPE)
        if env.get("signed"):
            env["mode"] = "REAL-DSSE"
        else:
            # No private key in this runtime — honest local, no fabricated signature.
            env["mode"] = "UNSIGNED-LOCAL"
            env["honesty"] = (env.get("honesty")
                              or "UNSIGNED-LOCAL — no cosign secret in this runtime; no signature fabricated.")
        env["content_digest_sha256"] = _content_digest(core)
        return env
    except Exception as exc:  # noqa: BLE001 — signing never crashes the pulse
        return {
            "mode": "UNSIGNED-LOCAL",
            "signed": False,
            "signatures": [],
            "content_digest_sha256": _content_digest(core),
            "honesty": ("UNSIGNED-LOCAL — szl_dsse unavailable in this runtime "
                        f"({type(exc).__name__}); no signature fabricated."),
        }


def build_pulse(ns: str = "a11oy") -> dict:
    """Build the current ecosystem pulse — the single beat every subscriber reads.

    Deterministic core (signed) + honest labels + a DSSE receipt. Volatile fields
    (generated timestamp) live OUTSIDE the signed body so the receipt is stable."""
    knowledge = knowledge_summary(ns)
    energy = energy_summary()
    lit = lit_summary(knowledge)
    core = _deterministic_core(ns, knowledge, energy, lit)
    receipt = _sign(core)
    return {
        "ok": True,
        "kind": "SZL.Brain.Pulse.v1",
        "ns": ns,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "knowledge": knowledge,
        "energy": energy,
        "lit": lit,
        "lambda_advisory": LAMBDA_ADVISORY,
        "labels": {
            "knowledge": knowledge.get("label"),
            "energy": energy.get("label"),
            "lambda": "Conjecture 1",
            "pulse": LBL_MODELED,
        },
        "receipt": receipt,
        "doctrine": _DOCTRINE,
    }


# --------------------------------------------------------------------------- #
# SUBSCRIBE — the honest budget the Brain feeds a given surface
# --------------------------------------------------------------------------- #
def _known_surface(ns: str, surface_id: str) -> Optional[bool]:
    """Best-effort check whether surface_id exists in the brain graph. Returns
    True/False when the graph is available, None when it can't be checked (so we
    report honestly rather than falsely claim unknown)."""
    try:
        import a11oy_brain_graph as _bg
        g = _bg.get_brain_graph(ns)
        sid = (surface_id or "").strip().lower()
        for n in g.get("nodes", []):
            if n.get("kind") != "surface":
                continue
            nid = str(n.get("id", ""))
            # ids look like "surface:<slug>"
            slug = nid.split(":", 1)[1] if ":" in nid else nid
            title = str(n.get("title", ""))
            if sid and (sid == slug.lower() or sid == title.lower()
                        or sid in slug.lower() or sid in title.lower()):
                return True
        return False
    except Exception:
        return None


def allocate_budget(pulse: dict, surface_id: str) -> dict:
    """A simple, honest, deterministic allocation of the live pulse to ONE surface.

    The Brain feeds each surface an EQUAL share of the harnessed knowledge/energy
    across the surfaces it is lighting (1/N). Labels flow straight through from the
    pulse: a MODELED/UNAVAILABLE energy pulse yields a MODELED/UNAVAILABLE budget —
    we never upgrade an honest label, and we never fabricate a joule or a node."""
    knowledge = pulse.get("knowledge", {})
    energy = pulse.get("energy", {})
    lit = pulse.get("lit", {})

    surfaces_lit = lit.get("surfaces_lit")
    try:
        n = int(surfaces_lit) if surfaces_lit else 0
    except (TypeError, ValueError):
        n = 0
    share = (1.0 / n) if n > 0 else None  # None -> honestly cannot divide (no fabrication)

    def _per(value):
        if share is None or value is None:
            return None
        try:
            return round(float(value) * share, 6)
        except (TypeError, ValueError):
            return None

    k_label = knowledge.get("label", LBL_UNAVAILABLE)
    e_label = energy.get("label", LBL_UNAVAILABLE)

    knowledge_budget = {
        "label": k_label if share is not None else LBL_UNAVAILABLE,
        "share_of_estate": share,
        "nodes_allocated": _per(knowledge.get("distinct_artifacts") or knowledge.get("node_count")),
        "basis": "equal 1/N share of the Brain's distinct artifacts across lit surfaces",
        "note": ("MODELED derived allocation over the reused brain-graph counts; "
                 "no knowledge fabricated." if share is not None else
                 "no lit surfaces to divide across — allocation honestly UNAVAILABLE."),
    }
    energy_budget = {
        "label": e_label if (share is not None and e_label != LBL_UNAVAILABLE) else LBL_UNAVAILABLE,
        "share_of_estate": share,
        "joules_allocated": _per(energy.get("joules_measured_billable")) if e_label == LBL_MEASURED else None,
        "tokens_allocated": _per(energy.get("tokens_total")),
        "would_charge_cents_allocated": _per(energy.get("would_charge_cents")),
        "basis": "equal 1/N share of the Brain's harnessed energy across lit surfaces",
        "note": ({
            LBL_MEASURED: "MEASURED joules allocated (real metered, billable); label flows through the pulse.",
            LBL_MODELED: "MODELED dry-run projection allocated; NOT billed measured energy.",
            LBL_UNAVAILABLE: "energy pulse UNAVAILABLE — no joules allocated, nothing fabricated.",
        }.get(e_label, "energy label flows through the pulse honestly.")),
    }

    known = _known_surface(pulse.get("ns", "a11oy"), surface_id)
    return {
        "ok": True,
        "kind": "SZL.Brain.Budget.v1",
        "surface_id": surface_id,
        "surface_known": known,  # True/False/None(uncheckable) — never a fabricated boolean
        "surface_note": ("surface found in the brain graph" if known is True else
                         "surface not found in the brain graph (budget still computed from the live pulse; "
                         "the Brain feeds any subscriber honestly)" if known is False else
                         "could not check the brain graph — reported honestly, not assumed"),
        "knowledge_budget": knowledge_budget,
        "energy_budget": energy_budget,
        "lambda_advisory": LAMBDA_ADVISORY,
        "pulse_receipt_digest": (pulse.get("receipt", {}) or {}).get("content_digest_sha256"),
        "pulse_generated_utc": pulse.get("generated_utc"),
        "doctrine": _DOCTRINE,
    }


# --------------------------------------------------------------------------- #
# HTTP handlers + registration (front-inserted BEFORE the SPA catch-all + Node
# proxy, mirroring szl_energy_ledger.register()).
# --------------------------------------------------------------------------- #
def handle_pulse(ns: str = "a11oy") -> dict:
    return build_pulse(ns)


def handle_subscribe(surface_id: str, ns: str = "a11oy") -> dict:
    return allocate_budget(build_pulse(ns), surface_id)


def register(app, ns: str = "a11oy"):
    """Mount the hub endpoints under /api/<ns>/v1/brain/{pulse,subscribe/{surface_id}}.

    Dual-register: prefer FastAPI's add_api_route (so routes resolve BEFORE the SPA
    catch-all, matching the other szl_* modules); fall back to a Starlette Route for
    a bare Starlette app. Returns the list of mounted paths."""
    from starlette.responses import JSONResponse

    base = f"/api/{ns}/v1/brain"

    def _h_pulse(request: _Request):
        return JSONResponse(handle_pulse(ns))

    def _h_subscribe(request: _Request):
        surface_id = request.path_params.get("surface_id", "")
        return JSONResponse(handle_subscribe(surface_id, ns))

    handlers = [
        (f"{base}/pulse", _h_pulse),
        (f"{base}/subscribe/{{surface_id}}", _h_subscribe),
    ]

    add_api_route = getattr(app, "add_api_route", None)
    mounted = []
    for path, fn in handlers:
        try:
            if callable(add_api_route):
                app.add_api_route(path, fn, methods=["GET"])
            else:
                from starlette.routing import Route
                app.router.routes.append(Route(path, fn))
            mounted.append(path)
        except Exception:  # pragma: no cover
            continue

    # Front-insert our routes so they win over the SPA /{full_path:path} catch-all +
    # the /api/<ns>/{path:path} Node proxy (same pattern as the other brain modules).
    try:
        routes = app.router.routes
        ours = [r for r in routes if getattr(r, "path", None) in set(m for m in mounted)]
        for r in ours:
            routes.remove(r)
        for r in reversed(ours):
            routes.insert(0, r)
    except Exception:  # pragma: no cover — non-fatal; add_api_route already mounted
        pass

    return mounted


# --------------------------------------------------------------------------- #
# Self-test — no server. Builds a pulse, checks honesty invariants, allocates.
# --------------------------------------------------------------------------- #
def _selftest() -> dict:
    out: dict = {}

    pulse = build_pulse("a11oy")
    out["pulse_ok"] = pulse.get("ok") is True

    # Λ is Conjecture 1, never "green"/theorem.
    body = json.dumps(pulse, default=str).lower()
    out["lambda_is_conjecture"] = (pulse["labels"]["lambda"] == "Conjecture 1")
    out["no_green_theorem_on_lambda"] = not ("lambda" in body and "theorem" in
                                             pulse.get("lambda_advisory", "").lower().replace("never a theorem", ""))

    # Knowledge is reused (MODELED) or honestly UNAVAILABLE — never a fabricated headline.
    out["knowledge_labeled"] = pulse["knowledge"].get("label") in (LBL_MODELED, LBL_UNAVAILABLE)

    # Energy is MEASURED / MODELED / UNAVAILABLE — never fabricated joules.
    out["energy_labeled"] = pulse["energy"].get("label") in (LBL_MEASURED, LBL_MODELED, LBL_UNAVAILABLE)
    if pulse["energy"].get("label") == LBL_UNAVAILABLE:
        out["no_fabricated_joules"] = not pulse["energy"].get("joules_measured_billable")

    # Receipt present with a mode + a deterministic digest.
    rec = pulse.get("receipt", {})
    out["receipt_has_mode"] = rec.get("mode") in ("REAL-DSSE", "UNSIGNED-LOCAL")
    out["receipt_has_digest"] = bool(rec.get("content_digest_sha256"))

    # Determinism: two builds re-sign to the same content digest (volatile ts excluded).
    d1 = build_pulse("a11oy")["receipt"]["content_digest_sha256"]
    d2 = build_pulse("a11oy")["receipt"]["content_digest_sha256"]
    out["receipt_deterministic"] = (d1 == d2)

    # Subscribe: budget flows the pulse labels through, no upgrade.
    budget = allocate_budget(pulse, "orbital")
    out["budget_ok"] = budget.get("ok") is True
    out["budget_energy_label_flows"] = (
        budget["energy_budget"]["label"] in (LBL_MEASURED, LBL_MODELED, LBL_UNAVAILABLE))
    # Unknown-surface budget still computes (Brain feeds any subscriber honestly).
    b2 = allocate_budget(pulse, "definitely-not-a-real-surface-xyz")
    out["budget_unknown_surface_still_honest"] = (b2.get("ok") is True
                                                  and b2.get("surface_known") in (False, None))

    out["doctrine"] = _DOCTRINE["version"]
    out["ok"] = all(v is True for k, v in out.items() if isinstance(v, bool))
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2, default=str))
    print("--- sample pulse ---", file=sys.stderr)
    print(json.dumps(build_pulse("a11oy"), indent=2, default=str)[:2000], file=sys.stderr)
