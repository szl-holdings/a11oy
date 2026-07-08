#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_honestywall.py — HONESTY WALL: a live "can this system lie right now?" integrity wall.

The honesty wall AGGREGATES the estate's OWN honesty invariants across every registered
frontier surface into a single, verifiable view. It is PURE honesty / observability: it
advances NO detection / fusion / effector / targeting / cueing capability. It only OBSERVES
the honesty posture the running estate already declares, and reports it — never fabricating a
pass, never upgrading a label.

WHAT IT DOES, at request time (honest by construction):
  1. Enumerate the app's OWN live surface registry (szl3d_holographic.SURFACES, imported
     in-process) and, for each surface that exposes a manifest, read its honesty-relevant
     fields from the surface's OWN in-process response (never an external HTTP call out of the
     Space): the data label (MEASURED / MODELED / STRUCTURAL-ONLY / ROADMAP / UNAVAILABLE / …,
     read VERBATIM), provenance_coverage, whether any CONJECTURE is rendered green (must be 0),
     Λ-is-conjecture-not-theorem, locked_count == 8, trust ceiling ≤ 0.97, no_consciousness_claim,
     writer≠judge where the surface declares it, plus every boolean the surface itself lists in
     its own ``honesty_invariants`` block.
  2. Compute an aggregate integrity view: counts of surfaces by label; the number of honesty
     invariants SATISFIED vs VIOLATED; and, for every VIOLATED invariant, the surface id with
     the observed-vs-expected values. A surface whose manifest is UNREACHABLE this request is
     marked UNKNOWN (never a pass, never a fail). A surface with no a11oy-native manifest at all
     is NO-MANIFEST (a client-only surface with no backend that could lie) — it does not affect
     the verdict.
  3. Report ONE honest verdict over the reachable evidence:
       INTACT    — 0 reachable violations AND 0 UNKNOWN surfaces
       DEGRADED  — some UNKNOWN surfaces, 0 reachable violations
       VIOLATED  — ≥ 1 reachable violation
     NEVER report INTACT while anything is violated; NEVER upgrade a surface's declared label.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET status/info reads mint NOTHING. Only the
POST aggregate endpoint emits an UNSIGNED SHA-256 content digest over the integrity aggregate
(consistent with the govern/receipts content-digest pattern) — a plain content hash, never a
fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17; it only
    OBSERVES. Touches no locked formula and no kernel.
  - Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  - No label is ever upgraded; a VIOLATED invariant can never be reported as a pass. A truthful
    BLOCKED/VIOLATED beats a fake green.
  - Additive routes, registered before the SPA catch-all; canonical domain a-11-oy.com; 0
    runtime CDN.
"""

import datetime
import hashlib
import json
import re
from typing import Any

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken import can
# never silently blank the vocabulary; tests grep these exact strings. This is the ALLOWED set a
# surface's backend may declare — the wall reports whichever one the backend actually returns,
# VERBATIM, never a token outside this set, never upgraded.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived aggregate digest, not a measurement.
MODELED = "MODELED"

# Per-surface reachability status.
NATIVE_OK = "NATIVE-OK"        # probed in-process; a manifest answered with honesty fields
UNKNOWN = "UNKNOWN"            # has a native route but did not answer this request (never pass/fail)
NO_MANIFEST = "NO-MANIFEST"    # no a11oy-native manifest route (client-only surface; nothing to lie)

# Per-invariant outcome.
SATISFIED = "SATISFIED"
VIOLATED = "VIOLATED"

# Aggregate verdicts.
INTACT = "INTACT"
VERDICT_DEGRADED = "DEGRADED"
VERDICT_VIOLATED = "VIOLATED"

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "honestywall"

_AGG_TTL = 30.0  # seconds — warm reads serve the last real aggregate; the cache only holds real output.


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _norm(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (token or "").lower())


# ---------------------------------------------------------------------------
# In-process surface introspection — reuse the AUDITED Frontier Index probe path
# (same-process route callables, never an external HTTP hop out of the Space).
# Every use is guarded: if the index module or a helper is unavailable, the wall
# degrades honestly (surfaces marked UNKNOWN) rather than raising.
# ---------------------------------------------------------------------------

def _fi():
    """The Frontier Index module (its route-introspection helpers are the audited, in-process
    probe path shared by the estate). Imported lazily + guarded."""
    import szl_frontier_index as _m
    return _m


def _surface_registry() -> list[dict]:
    """The app's OWN surface registry, imported in-process (never re-typed here)."""
    try:
        import szl3d_holographic as holo
        surfaces = getattr(holo, "SURFACES", None)
        if not isinstance(surfaces, list):
            return []
        return [s for s in surfaces if isinstance(s, dict) and s.get("id")]
    except Exception:
        return []


def _self_manifest(ns: str = "a11oy") -> dict:
    """This surface's OWN honesty manifest — used when the aggregate evaluates honestywall
    itself, so it NEVER re-invokes its own aggregate endpoint (no recursion) and never lies
    about its own posture."""
    base = f"/api/{ns}/v1/govern/honestywall"
    return {
        "service": "a11oy.govern.honestywall",
        "label": MODELED,
        "surface_id": SURFACE_ID,
        "endpoint": f"{base}/status",
        "doctrine": {
            "label_top": MODELED,
            "locked_proven": LOCKED_COUNT,
            "locked_set": LOCKED_SET,
            "kernel_commit": KERNEL_COMMIT,
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
        },
        "provenance_coverage": 1.0,
        "honesty_invariants": {
            "observes_only_never_advances_capability": True,
            "never_reports_intact_while_violated": True,
            "never_upgrades_a_label": True,
            "receipt_on_write_not_on_read": True,
            "lambda_is_conjecture_1_not_a_theorem": True,
            "adds_nothing_to_locked_8": True,
            "no_consciousness_claim": True,
        },
    }


def _probe_surface(app, sid: str, get_paths: list[str], ns: str,
                   timeout: float = 3.0) -> tuple[dict | None, str | None, str]:
    """Return (payload, endpoint, status) for one surface, read from its OWN in-process
    response. status is NATIVE_OK / UNKNOWN / NO_MANIFEST. Fully guarded."""
    # Our own surface: use the static self-manifest so we never recurse into our aggregate.
    if _norm(sid) == _norm(SURFACE_ID):
        return _self_manifest(ns), f"/api/{ns}/v1/govern/honestywall/status", NATIVE_OK
    try:
        fi = _fi()
        routes = fi._surface_routes(sid, get_paths, ns)
        eps = fi._pick_probe_endpoints(sid, routes, ns)
    except Exception:
        return None, None, UNKNOWN
    if not routes:
        return None, None, NO_MANIFEST
    for ep in eps:
        try:
            route = fi._get_route(app, ep)
            if route is None:
                continue
            payload = fi._invoke_route(app, route, ep, timeout)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return payload, ep, NATIVE_OK
    # A native route exists but none answered with a manifest this request -> honest UNKNOWN.
    return None, (eps[0] if eps else None), UNKNOWN


# ---------------------------------------------------------------------------
# Honesty-invariant evaluation — read the surface's OWN declared fields VERBATIM.
# An invariant is only judged when the relevant field is PRESENT in the manifest;
# a satisfied value -> SATISFIED, a contradicting value -> VIOLATED. Absent fields
# are simply not judged (never a fabricated pass, never a fabricated fail).
# ---------------------------------------------------------------------------

def _extract_label(payload: dict) -> tuple[str | None, str | None]:
    """Return (verbatim_raw_label, honest_vocabulary_token). The token is the honest label the
    surface declares (never upgraded); raw is exactly what it wrote."""
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}
    raw = None
    for v in (payload.get("label"), payload.get("data_label"), payload.get("claim"),
              doctrine.get("label_top") if isinstance(doctrine, dict) else None):
        if isinstance(v, str) and v.strip():
            raw = v.strip()
            break
    tok = None
    try:
        tok = _fi()._primary_label(raw) if raw else None
    except Exception:
        # Local fallback: find the first vocabulary token as a substring (never invents one).
        if raw:
            up = raw.upper()
            best_pos, best = None, None
            for t in HONEST_LABELS:
                i = up.find(t)
                if i >= 0 and (best_pos is None or i < best_pos):
                    best_pos, best = i, t
            tok = best
    return raw, tok


def _check(name: str, observed: Any, expected: str, ok: bool) -> dict:
    return {
        "invariant": name,
        "observed": observed,
        "expected": expected,
        "status": SATISFIED if ok else VIOLATED,
    }


# Conservative positive-claim patterns — a surface that merely DECLARES
# `no_consciousness_claim: true` contains the word "consciousness"; we must NOT flag that as a
# violation. Only an explicit positive assertion counts.
_CONSCIOUS_CLAIM = re.compile(
    r"\b(is|are|am|becomes?)\s+(conscious|sentient|self-aware)\b"
    r"|(achiev|attain|possess|demonstrat|prove[ds]?)\w*\s+(consciousness|sentience|sapience)",
    re.IGNORECASE,
)


def _eval_payload(payload: dict) -> tuple[str | None, float | None, list[dict]]:
    """Evaluate one surface manifest. Returns (label_token, provenance_coverage, checks)."""
    checks: list[dict] = []
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}

    # data label — read VERBATIM; the invariant is that the declared label is in the honest
    # vocabulary (a bogus / marketing label that maps to no honest token is a violation).
    raw_label, label_tok = _extract_label(payload)
    if raw_label is not None:
        checks.append(_check("label_in_honest_vocabulary", raw_label,
                             "∈ HONEST_LABELS (verbatim, never upgraded)", label_tok is not None))

    # locked_count == 8 (never inflate).
    lc = doctrine.get("locked_proven", doctrine.get("locked_count"))
    if isinstance(lc, (int, float)) and not isinstance(lc, bool):
        checks.append(_check("locked_count_eight", lc, "== 8", int(lc) == LOCKED_COUNT))

    # Λ is Conjecture 1, never a theorem.
    # Only an AFFIRMATIVE "is a theorem" claim is a violation; a negated mention
    # ("not a theorem", "never a theorem") is the honest declaration and must PASS.
    # (Prior naive `"theorem" not in low` false-flagged "NOT a theorem".)
    lam = doctrine.get("lambda")
    if isinstance(lam, str) and lam.strip():
        low = lam.lower()
        stripped = re.sub(r"\b(?:not|never|isn'?t|is\s+not|no)\s+a?\s*theorem", "", low)
        claims_theorem = "theorem" in stripped
        checks.append(_check("lambda_is_conjecture_not_theorem", lam,
                             "declares a Conjecture, never a theorem",
                             ("conjecture" in low) and not claims_theorem))

    # trust ceiling ≤ 0.97 and never 100%.
    tc = doctrine.get("trust_ceiling")
    if isinstance(tc, (int, float)) and not isinstance(tc, bool):
        checks.append(_check("trust_ceiling_le_0_97", tc, "<= 0.97", tc <= TRUST_CEILING + 1e-9))
    t100 = doctrine.get("trust_100_percent")
    if isinstance(t100, bool):
        checks.append(_check("trust_never_100", t100, "False", t100 is False))

    # provenance_coverage — report the REAL number; a value outside [0,1] is a violation.
    pc = payload.get("provenance_coverage")
    if pc is None and isinstance(doctrine, dict):
        pc = doctrine.get("provenance_coverage")
    prov = None
    if isinstance(pc, (int, float)) and not isinstance(pc, bool):
        prov = float(pc)
        checks.append(_check("provenance_coverage_in_unit_interval", prov, "in [0,1]",
                             0.0 <= prov <= 1.0))

    # no CONJECTURE rendered green (must be 0).
    for key in ("conjecture_green", "conjectures_green", "conjecture_rendered_green",
                "green_conjectures"):
        v = payload.get(key, doctrine.get(key))
        if isinstance(v, bool):
            checks.append(_check("no_conjecture_rendered_green", v, "False", v is False))
            break
        if isinstance(v, (int, float)):
            checks.append(_check("no_conjecture_rendered_green", v, "== 0", int(v) == 0))
            break

    # no consciousness claim — absence of an explicit positive claim = satisfied (always judged).
    try:
        blob = json.dumps(payload, default=str)
    except Exception:
        blob = ""
    checks.append(_check("no_consciousness_claim",
                         "explicit-claim" if _CONSCIOUS_CLAIM.search(blob) else "none",
                         "no explicit consciousness/sentience claim",
                         not bool(_CONSCIOUS_CLAIM.search(blob))))

    # writer ≠ judge, where the surface declares it at the top level.
    for key, want in (("writer_ne_judge", True), ("writer_eq_judge", False)):
        v = payload.get(key)
        if isinstance(v, bool):
            checks.append(_check(key, v, str(want), v is want))

    # Every boolean the surface itself lists in its OWN honesty_invariants block, read VERBATIM:
    # True = the surface asserts it satisfies that invariant; False = it declares it does NOT.
    hi = payload.get("honesty_invariants")
    if isinstance(hi, dict):
        for k, v in hi.items():
            if isinstance(v, bool):
                checks.append(_check(f"declared:{k}", v, "True (surface's own assertion)", v is True))

    return label_tok, prov, checks


# ---------------------------------------------------------------------------
# Aggregate assembly (cached, honest, pure computation — mints nothing).
# ---------------------------------------------------------------------------

def _build_aggregate(app, ns: str = "a11oy") -> dict:
    surfaces = _surface_registry()
    try:
        get_paths = _fi()._registered_get_paths(app, ns) if app is not None else []
    except Exception:
        get_paths = []

    entries: list[dict] = []
    label_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {NATIVE_OK: 0, UNKNOWN: 0, NO_MANIFEST: 0}
    inv_satisfied = 0
    inv_violated = 0
    violated_list: list[dict] = []

    for s in surfaces:
        sid = s.get("id", "")
        title = s.get("title", sid)
        category = s.get("cat", s.get("category"))
        try:
            payload, endpoint, status = _probe_surface(app, sid, get_paths, ns)
        except Exception as exc:  # degrade THIS surface honestly, never the whole wall
            entries.append({
                "id": sid, "title": title, "category": category,
                "status": UNKNOWN, "label": None, "endpoint": None,
                "checks_satisfied": 0, "checks_violated": 0, "violations": [],
                "note": f"probe failed for this surface, reported honestly: {str(exc)[:160]}",
            })
            status_counts[UNKNOWN] += 1
            continue

        status_counts[status] = status_counts.get(status, 0) + 1

        entry: dict[str, Any] = {
            "id": sid, "title": title, "category": category,
            "status": status, "label": None, "endpoint": endpoint,
            "checks_satisfied": 0, "checks_violated": 0, "violations": [],
        }

        if status == NATIVE_OK and isinstance(payload, dict):
            label_tok, prov, checks = _eval_payload(payload)
            entry["label"] = label_tok
            if prov is not None:
                entry["provenance_coverage"] = prov
            if label_tok:
                label_counts[label_tok] = label_counts.get(label_tok, 0) + 1
            for c in checks:
                if c["status"] == SATISFIED:
                    entry["checks_satisfied"] += 1
                    inv_satisfied += 1
                else:
                    entry["checks_violated"] += 1
                    inv_violated += 1
                    v = {"surface": sid, "invariant": c["invariant"],
                         "observed": c["observed"], "expected": c["expected"]}
                    entry["violations"].append(v)
                    violated_list.append(v)
        elif status == NO_MANIFEST:
            entry["note"] = "no a11oy-native manifest route; client-only surface (nothing to attest)"
        else:  # UNKNOWN
            entry["note"] = "native route registered but no manifest answered in-process this request"

        entries.append(entry)

    reachable_violations = inv_violated
    unknown_count = status_counts.get(UNKNOWN, 0)
    if reachable_violations >= 1:
        verdict = VERDICT_VIOLATED
    elif unknown_count > 0:
        verdict = VERDICT_DEGRADED
    else:
        verdict = INTACT

    verdict_reason = {
        INTACT: "0 reachable invariant violations and 0 UNKNOWN surfaces",
        VERDICT_DEGRADED: f"{unknown_count} surface(s) UNKNOWN this request; 0 reachable violations",
        VERDICT_VIOLATED: f"{reachable_violations} reachable invariant violation(s) observed",
    }[verdict]

    return {
        "ok": True,
        "endpoint": "govern/honestywall/aggregate",
        "service": "a11oy.govern.honestywall",
        "title": "Honesty Wall — can this system lie right now?",
        "label": MODELED,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "what": ("a live integrity wall that AGGREGATES the estate's OWN honesty invariants "
                 "across every registered frontier surface into a single verifiable view. Reads "
                 "each surface's honesty-relevant manifest fields VERBATIM from its own "
                 "in-process response; never fabricates a pass, never upgrades a label, never "
                 "reports INTACT while anything is violated. Pure honesty/observability — "
                 "advances no detection/fusion/effector/targeting/cueing capability."),
        "introspection": {
            "surface_registry": "szl3d_holographic.SURFACES (imported in-process)",
            "manifest_source": "each surface's OWN in-process response (VERBATIM; never upgraded)",
            "probe_path": "szl_frontier_index in-process route callables (no external HTTP hop)",
            "api_routes_seen": len(get_paths),
        },
        "doctrine": {
            "label_top": MODELED,
            "locked_proven": LOCKED_COUNT,
            "locked_set": LOCKED_SET,
            "kernel_commit": KERNEL_COMMIT,
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
            "note": ("additive OBSERVE-only surface; touches no locked formula and no kernel; "
                     "GET reads sign/mint nothing; POST aggregate emits an UNSIGNED SHA-256 "
                     "content digest only; introduces no theorem, no green/1.0."),
        },
        "verdict_legend": {
            INTACT: "0 reachable violations AND 0 UNKNOWN surfaces",
            VERDICT_DEGRADED: "some surfaces UNKNOWN this request, 0 reachable violations",
            VERDICT_VIOLATED: ">= 1 reachable invariant violation (never reported as INTACT)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "summary": {
            "surfaces": len(entries),
            "surfaces_by_status": status_counts,
            "label_counts": label_counts,
            "invariants_satisfied": inv_satisfied,
            "invariants_violated": inv_violated,
            "reachable_violations": reachable_violations,
            "unknown_surfaces": unknown_count,
        },
        "violations": violated_list,
        "surfaces": entries,
        "timestamp_utc": _now_iso(),
    }


def build_aggregate(app, ns: str = "a11oy") -> dict:
    """Cached entrypoint. Serves the last real aggregate for _AGG_TTL seconds so a read does not
    re-probe every surface on every hit. The cache only ever holds real output."""
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    key = (id(app), ns)
    cache = getattr(build_aggregate, "_cache", None)
    if cache is not None:
        ck, ts, val = cache
        if ck == key and (now - ts) < _AGG_TTL:
            return val
    val = _build_aggregate(app, ns)
    build_aggregate._cache = (key, now, val)  # type: ignore[attr-defined]
    return val


# ---------------------------------------------------------------------------
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on a GET read.
# ---------------------------------------------------------------------------

def _canonical_core(aggregate: dict) -> str:
    """Deterministic canonical serialization of the integrity-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + evidence, not the clock."""
    core = {
        "verdict": aggregate.get("verdict"),
        "summary": aggregate.get("summary"),
        "surfaces": [
            {"id": s.get("id"), "status": s.get("status"), "label": s.get("label"),
             "violations": s.get("violations", [])}
            for s in aggregate.get("surfaces", [])
        ],
        "violations": aggregate.get("violations", []),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(aggregate: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the aggregate (no signature fabricated)."""
    canonical = _canonical_core(aggregate)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.honestywall.aggregate",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST aggregate)",
        "note": ("unsigned SHA-256 content digest of the integrity aggregate; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------

def handle_status(app, ns: str = "a11oy") -> dict:
    """GET /govern/honestywall/status — a compact live verdict + counts. PURE READ (mints
    nothing). Also the endpoint the Frontier Index catalog probes for THIS surface, so the
    aggregate (which reads that catalog's probe path) never recurses into itself."""
    try:
        agg = build_aggregate(app, ns)
        return {
            "ok": True,
            "endpoint": "govern/honestywall/status",
            "service": "a11oy.govern.honestywall",
            "label": MODELED,
            "surface_id": SURFACE_ID,
            "verdict": agg["verdict"],
            "verdict_reason": agg["verdict_reason"],
            "summary": agg["summary"],
            "doctrine": {"lambda": "Conjecture 1", "locked_proven": LOCKED_COUNT,
                         "trust_ceiling": TRUST_CEILING, "trust_100_percent": False,
                         "adds_to_locked_8": 0},
            "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; POST aggregate digests.",
            "timestamp_utc": _now_iso(),
        }
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False, "endpoint": "govern/honestywall/status", "label": "UNAVAILABLE",
            "surface_id": SURFACE_ID, "error": str(exc)[:200],
            "doctrine": "v11: honesty wall unavailable; no fabricated verdict emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_info(ns: str = "a11oy") -> dict:
    """GET /govern/honestywall/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/govern/honestywall"
    man = _self_manifest(ns)
    man.update({
        "ok": True,
        "endpoint": "govern/honestywall/info",
        "title": "Honesty Wall — can this system lie right now?",
        "what": ("aggregates the estate's OWN honesty invariants across all surfaces into one "
                 "verifiable integrity view; pure honesty/observability, advances no "
                 "detection/fusion/effector/targeting/cueing capability."),
        "endpoints": {
            "status": f"GET  {base}/status",
            "info": f"GET  {base}/info",
            "aggregate": f"POST {base}/aggregate",
        },
        "verdicts": [INTACT, VERDICT_DEGRADED, VERDICT_VIOLATED],
        "invariants_checked": [
            "label_in_honest_vocabulary (verbatim, never upgraded)",
            "locked_count_eight (== 8, never inflated)",
            "lambda_is_conjecture_not_theorem",
            "trust_ceiling_le_0_97 / trust_never_100",
            "provenance_coverage_in_unit_interval (real number reported)",
            "no_conjecture_rendered_green (== 0)",
            "no_consciousness_claim",
            "writer_ne_judge (where declared)",
            "each surface's own declared honesty_invariants (verbatim)",
        ],
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — only POST /aggregate emits an unsigned SHA-256 content digest.",
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "timestamp_utc": _now_iso(),
    })
    return man


def handle_aggregate(app, ns: str = "a11oy") -> dict:
    """POST /govern/honestywall/aggregate — the full integrity view + an UNSIGNED SHA-256
    content-digest receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    try:
        agg = build_aggregate(app, ns)
        out = dict(agg)
        out["receipt"] = _content_receipt(agg)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "govern/honestywall/aggregate", "label": "UNAVAILABLE",
            "verdict": VERDICT_DEGRADED, "error": str(exc)[:200],
            "doctrine": "v11: aggregate unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration.
#   GET  status/info — normal FastAPI GET handlers.
#   POST aggregate   — raw-Request handler via app.router.add_route (Starlette passes the
#                      Request positionally, version-proof under fastapi==0.137.x), with
#                      app.add_api_route as the fallback. The handler is annotated
#                      request: fastapi.Request. Registered BEFORE the SPA catch-all by serve.py.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/govern/honestywall"

    @app.get(f"{base}/status")
    def _honestywall_status():
        """Compact live integrity verdict + counts (pure read; mints nothing; self-probe endpoint)."""
        return JSONResponse(handle_status(app, ns))

    @app.get(f"{base}/info")
    def _honestywall_info():
        """Self-describing honesty-wall manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    async def _honestywall_aggregate(request):
        """POST: full honesty aggregate across the estate + UNSIGNED SHA-256 content digest
        (RECEIPT-ON-WRITE). The body is ignored (a pure aggregate compute)."""
        return JSONResponse(handle_aggregate(app, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _honestywall_aggregate.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    agg_path = f"{base}/aggregate"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(agg_path, _honestywall_aggregate, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(agg_path, _honestywall_aggregate, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(agg_path, _honestywall_aggregate, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] honestywall aggregate POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "honestywall-wired:2(get-only)"

    return "honestywall-wired:3"


# ---------------------------------------------------------------------------
# Self-test — honest verdict, no fabricated pass, no label upgrade, receipt only on write.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_honestywall — self-test (live honesty integrity wall)")
    print("=" * 72)

    from fastapi import FastAPI
    app = FastAPI()
    import szl_frontier_index as _fi_mod
    _fi_mod.register(app, ns="a11oy")
    try:
        import szl_frontier_zkinfer as _zk
        _zk.register(app, ns="a11oy")
    except Exception as _e:  # pragma: no cover
        print(f"(zkinfer not wired for self-test: {_e!r})")
    register(app, ns="a11oy")

    agg = handle_aggregate(app, ns="a11oy")

    # 1) aggregate built, ok:true, MODELED self label, honest verdict, surfaces enumerated.
    assert agg["ok"] is True
    assert agg["label"] == MODELED
    assert agg["verdict"] in (INTACT, VERDICT_DEGRADED, VERDICT_VIOLATED)
    assert len(agg["surfaces"]) >= 1
    print(f"[1] aggregate ok, MODELED, verdict={agg['verdict']}, "
          f"{len(agg['surfaces'])} surfaces  OK")

    # 2) NEVER INTACT while any violation exists; verdict is consistent with the evidence.
    rv = agg["summary"]["reachable_violations"]
    if rv >= 1:
        assert agg["verdict"] == VERDICT_VIOLATED, "must be VIOLATED when violations exist"
    elif agg["summary"]["unknown_surfaces"] > 0:
        assert agg["verdict"] == VERDICT_DEGRADED
    else:
        assert agg["verdict"] == INTACT
    print(f"[2] verdict consistent w/ evidence (violations={rv}, "
          f"unknown={agg['summary']['unknown_surfaces']})  OK")

    # 3) every per-surface label is an honest-vocabulary token (never upgraded/invented).
    vocab = set(HONEST_LABELS)
    for s in agg["surfaces"]:
        assert s["label"] is None or s["label"] in vocab, f"{s['id']}: bad label {s['label']!r}"
        assert s["status"] in (NATIVE_OK, UNKNOWN, NO_MANIFEST)
    print("[3] all per-surface labels in honest vocabulary; statuses honest  OK")

    # 4) RECEIPT-ON-WRITE: POST aggregate carries an UNSIGNED sha256 digest; GET status mints none.
    r = agg["receipt"]
    assert r["algorithm"] == "sha256" and len(r["content_sha256"]) == 64
    assert r["signed"] is False and r["mode"] == "UNSIGNED-CONTENT-DIGEST"
    st = handle_status(app, ns="a11oy")
    assert "receipt" not in st, "GET status must NOT mint a receipt (receipt-on-write-not-on-read)"
    print(f"[4] POST digest={r['content_sha256'][:16]}… unsigned; GET status mints nothing  OK")

    # 5) doctrine: locked-8 exact, adds nothing, Λ Conjecture 1, trust 0.97 not 100%.
    d = agg["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
