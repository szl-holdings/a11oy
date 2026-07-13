# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainhealth.py — BRAIN HEALTH: a governed ROLLUP of the brain's honesty surfaces.

The brain-health surface answers ONE honest question for a given query: *can the brain be
trusted for THIS query right now?* It is the brain's equivalent of the estate honesty wall
(szl_honestywall.py), but scoped STRICTLY to knowledge-graph honesty — it advances no
detection / fusion / effector / targeting / cueing capability. It only READS the honesty
signals the brain already computes, and rolls the AVAILABLE ones into a single verdict.

WHAT IT ROLLS UP (each a sibling brain-honesty surface, read VERBATIM with its own honest
label; a component that is not importable is reported UNAVAILABLE, never fabricated):

  * grounding      — grounding confidence      (szl_brainground)
  * freshness      — memory freshness          (szl_brainmemory)
  * provenance     — source-lineage coverage   (szl_brainprovenance)
  * contradiction  — conflict flag             (szl_braincontradict)
  * uncertainty    — uncertainty / abstain     (szl_brainuncertainty)

RESILIENT BY CONSTRUCTION. Several siblings ship in separate PRs and may or may not be
present on main when this runs. Every component is gathered through a GUARDED import
(try/except ImportError → the component degrades to UNAVAILABLE). This module NEVER
hard-depends on a sibling module, NEVER fabricates a component score, and NEVER upgrades a
component's declared label.

VERDICT over the AVAILABLE components only:

  TRUSTWORTHY        — enough components available AND every available one is OK (no adverse
                       signal, a real positive signal present) AND none UNAVAILABLE.
  DEGRADED           — enough components available, none adverse, but some are UNAVAILABLE or
                       their signal is INDETERMINATE (partial trust — never TRUSTWORTHY).
  UNTRUSTWORTHY      — ≥1 available component reports an adverse honesty signal
                       (abstain / insufficient / conflict-flagged / stale-dominant).
  INSUFFICIENT-SIGNAL — fewer than MIN_COMPONENTS components available (too little to judge).

NEVER report TRUSTWORTHY if any available component abstains / is insufficient /
conflict-flagged / stale-dominant — such a signal forces UNTRUSTWORTHY. A truthful
UNTRUSTWORTHY / INSUFFICIENT-SIGNAL beats a fake green.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info / health reads mint NOTHING. Only the
POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the rollup (mirrors the
honestywall content-digest pattern) — a plain content hash, never a fabricated signature.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only OBSERVES.
  - Λ stays Conjecture 1 (never a theorem); introduces no theorem, no green/1.0.
  - No label is ever upgraded; an adverse component can never be reported as TRUSTWORTHY.
  - Pure stdlib + numpy. Additive routes, registered BEFORE the SPA catch-all; 0 runtime CDN.
"""

import datetime
import hashlib
import importlib
import json
import pathlib
import re
import threading
import time
from typing import Any, Callable

import szl_braincorpus as _braincorpus

try:  # numpy is allowed; used only for the modeled mean, guarded so a missing wheel is honest.
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is a core dep in this estate
    _np = None
    _HAVE_NUMPY = False

# Honesty-label vocabulary (doctrine v11), re-stated (not imported) so a broken import can
# never silently blank it. This is the ALLOWED set a component may declare; brain-health
# reports whichever one the component actually returns, VERBATIM, never upgraded.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived rollup, not a measurement.
MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Per-component availability.
AVAILABLE = "AVAILABLE"
# (UNAVAILABLE reused from the label vocabulary above.)

# Per-component honesty signal.
SIG_OK = "OK"                    # available, a real positive signal, no adverse flag
SIG_ADVERSE = "ADVERSE"          # abstain / insufficient / conflict-flagged / stale-dominant
SIG_INDETERMINATE = "INDETERMINATE"  # available but no clear signal either way

# Aggregate verdicts.
TRUSTWORTHY = "TRUSTWORTHY"
DEGRADED = "DEGRADED"
UNTRUSTWORTHY = "UNTRUSTWORTHY"
INSUFFICIENT_SIGNAL = "INSUFFICIENT-SIGNAL"

# Operational readiness is deliberately separate from epistemic/query trust.  A service can
# load its index and expose every honesty component while a particular question still needs to
# abstain.  Conflating these two states made the blank dashboard query look like a failed brain.
SERVICE_READY = "READY"
SERVICE_DEGRADED = "DEGRADED"
QUERY_EVALUATED = "EVALUATED"
QUERY_NOT_EVALUATED = "NOT-EVALUATED"

_ROOT = pathlib.Path(__file__).resolve().parent

_REFRESH_LOCK = threading.Lock()
_REFRESH_COOLDOWN_SECONDS = 5.0
_LAST_REFRESH_MONOTONIC = 0.0


def _client_is_loopback(host: str | None) -> bool:
    """Fail-closed client check for the local-only cache rebuild endpoint."""
    return str(host or "").strip().lower() in {"127.0.0.1", "::1", "localhost", "testclient"}

VERDICTS = (TRUSTWORTHY, DEGRADED, UNTRUSTWORTHY, INSUFFICIENT_SIGNAL)

# Minimum available components required to render a confident verdict; below this the honest
# answer is INSUFFICIENT-SIGNAL rather than a guess over one lonely signal.
MIN_COMPONENTS = 2

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainhealth"

# Adverse honesty tokens that, if ANY available component declares one, forbid TRUSTWORTHY.
# Restated per doctrine: abstain / insufficient / conflict-flagged / stale-dominant.
_SHARED_ADVERSE = ("abstain", "insufficient", "conflict-flagged", "stale-dominant",
                   "conflict", "contradiction", "contradictory", "stale")

# Affirmative signal tokens — presence of one (with NO adverse token) is a real positive.
_SHARED_POSITIVE = ("grounded", "fresh", "covered", "no-conflict", "no conflict",
                    "consistent", "confident", "trustworthy", "sufficient", "ok")


# ---------------------------------------------------------------------------
# Component registry. Each spec names its sibling module, the candidate compute
# callables to try (broad, so a sibling landing under any of these names still
# wires), how to read its VALUE, and the adverse tokens specific to it. Every
# access is guarded — a missing/broken sibling degrades to UNAVAILABLE.
# ---------------------------------------------------------------------------
COMPONENTS: list[dict] = [
    {
        "key": "grounding",
        "title": "grounding confidence",
        "module": "szl_brainground",
        "funcs": ("evaluate",),
        "call_style": "q_k_ns",
        "value_keys": ("trust_value", "grounding_confidence", "confidence", "grounding", "score", "value"),
        "adverse": ("ungrounded", "no-grounding", "no grounding"),
    },
    {
        "key": "freshness",
        "title": "memory freshness",
        "module": "szl_brainmemory",
        "funcs": ("build_aggregate",),
        "call_style": "ns",
        "value_keys": ("trust_value", "freshness", "freshness_score", "recency", "score", "value"),
        "adverse": ("expired", "outdated"),
    },
    {
        "key": "provenance",
        "title": "source-lineage coverage",
        "module": "szl_brainprovenance",
        "funcs": ("build_provenance",),
        "call_style": "ns_q_k",
        "value_keys": ("trust_value", "provenance_coverage", "lineage_coverage", "score", "value"),
        "adverse": ("unprovenanced", "untraceable", "no-lineage", "no lineage", "unsourced"),
    },
    {
        "key": "contradiction",
        "title": "conflict flag",
        "module": "szl_braincontradict",
        "funcs": ("run_detection",),
        "call_style": "q_k_ns",
        "value_keys": ("trust_value", "contradiction_score", "conflict_score", "score", "value"),
        "adverse": ("conflicted", "contradicted"),
    },
    {
        "key": "uncertainty",
        "title": "uncertainty / abstain",
        "module": "szl_brainuncertainty",
        "funcs": ("handle_uncertainty",),
        "call_style": "ns_q_k",
        "value_keys": ("trust_value", "semantic_entropy", "entropy", "score", "value"),
        "adverse": ("uncertain", "high-uncertainty", "high uncertainty"),
    },
]

# Test / integration seam: an override callable per component key is consulted FIRST. Absent
# an override, the guarded import path is used. This lets a test stub sibling availability BOTH
# ways (present -> supply a callable; absent -> leave unset AND ensure no real module imports).
_PROBE_OVERRIDES: dict[str, Callable[[str, int], Any]] = {}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _resolve_callable(spec: dict) -> Callable | None:
    """Return the sibling's compute callable, or None if the module isn't importable / exposes
    no known compute entrypoint. Guarded — ImportError => None (component UNAVAILABLE)."""
    try:
        mod = importlib.import_module(spec["module"])
    except ImportError:
        return None
    except Exception:  # a sibling that raises on import is honestly treated as unavailable
        return None
    for name in spec["funcs"]:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


def _invoke(fn: Callable, q: str, k: int, style: str = "generic", ns: str = "a11oy"):
    """Call the sibling with the most specific signature it accepts, degrading through
    (q, k) -> (q) -> (). A TypeError only from arity is retried; anything else propagates so
    the caller can mark the component UNAVAILABLE honestly."""
    explicit = {
        "q_k_ns": (q, k, ns),
        "ns_q_k": (ns, q, k),
        "ns": (ns,),
    }
    if style in explicit:
        return fn(*explicit[style])
    for args in ((q, k), (q,), ()):
        try:
            return fn(*args)
        except TypeError as exc:
            # Retry with fewer args ONLY when the arity is the problem, not an inner TypeError.
            if "argument" in str(exc) or "positional" in str(exc):
                continue
            raise
    return fn(q)


def _normalize_component_payload(key: str, payload: dict) -> dict:
    """Add a transparent trust-aligned value without changing the sibling's own label/verdict.

    The old rollup averaged heterogeneous directions (for example, high uncertainty increased
    the displayed modeled trust). Every `trust_value` below uses the same direction: 1 is the
    favorable end of that component's own signal and 0 is the adverse end. Source fields remain
    present and source_verdict is copied verbatim for audit/replay.
    """
    out = dict(payload)
    out["source_verdict"] = payload.get("verdict")

    def clip(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return None

    if key == "grounding":
        value = clip(payload.get("grounding_confidence"))
        if value is not None:
            out["trust_value"] = value
        if payload.get("should_abstain") is True:
            out["abstain"] = True
    elif key == "freshness":
        counts = payload.get("verdict_counts") if isinstance(payload.get("verdict_counts"), dict) else {}
        total = payload.get("node_count")
        stale = counts.get("STALE")
        if isinstance(total, (int, float)) and total > 0 and isinstance(stale, (int, float)):
            stale_share = clip(float(stale) / float(total))
            out["stale_share"] = stale_share
            out["trust_value"] = round(1.0 - stale_share, 6)
            out["stale_dominant"] = stale_share >= 0.5
            out["verdict"] = "STALE-DOMINANT" if stale_share >= 0.5 else "FRESHNESS-MIXED"
    elif key == "provenance":
        coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
        value = clip(coverage.get("fraction_traceable_to_source"))
        if value is not None:
            out["provenance_coverage"] = value
            out["trust_value"] = value
    elif key == "contradiction":
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        pairs = summary.get("pairs_examined")
        flagged = summary.get("flagged_count")
        if isinstance(pairs, (int, float)) and pairs > 0 and isinstance(flagged, (int, float)):
            risk = clip(float(flagged) / float(pairs))
            out["conflict_score"] = risk
            out["trust_value"] = round(1.0 - risk, 6)
        if str(payload.get("verdict", "")).upper() == "CONFLICT-FLAGGED":
            out["contradiction_detected"] = True
    elif key == "uncertainty":
        uncertainty = clip(payload.get("uncertainty"))
        if uncertainty is not None:
            out["raw_uncertainty"] = uncertainty
            out["trust_value"] = round(1.0 - uncertainty, 6)
        if payload.get("abstain_recommended") is True:
            out["abstain"] = True
    return out


def _iter_string_values(obj):
    """Yield every string VALUE reachable in a nested dict/list — never a key. Adverse-token
    scanning must inspect what a component SAYS (its values), never its field NAMES: a field
    literally named 'contradiction_score' or 'uncertainty' is a schema key, not a declared
    adverse signal, and must not be read as one."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_string_values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_string_values(v)


def _read_label(payload: dict) -> str | None:
    """Read the component's own honest label VERBATIM (never upgraded). Only a token in the
    honest vocabulary is accepted; anything else is reported as None (never invented)."""
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}
    for v in (payload.get("label"), payload.get("data_label"),
              doctrine.get("label_top") if isinstance(doctrine, dict) else None):
        if isinstance(v, str):
            up = v.strip().upper()
            if up in HONEST_LABELS:
                return up
    return None


def _read_value(payload: dict, value_keys) -> float | None:
    """Read the component's primary numeric signal from its own declared fields (payload or its
    doctrine block). Returns the REAL number or None — never a fabricated default."""
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}
    for key in value_keys:
        for src in (payload, doctrine):
            v = src.get(key) if isinstance(src, dict) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
    return None


# Explicit boolean adverse flags a component may set on itself.
_ADVERSE_FLAGS = ("abstain", "abstained", "insufficient", "conflict", "conflict_flagged",
                  "contradiction", "contradiction_detected", "stale", "stale_dominant")


def _detect_adverse(payload: dict, extra_tokens) -> str | None:
    """Return the adverse reason if the component declares one, else None. Reads the
    component's OWN decision fields VERBATIM: (1) explicit boolean adverse flags set True;
    (2) an adverse token in verdict/status/signal/state/answer_label. Descriptive notes,
    formulas and doctrine text are intentionally excluded: a sentence explaining when to
    abstain is not evidence that this request actually abstained."""
    # (1) explicit boolean flags.
    for flag in _ADVERSE_FLAGS:
        v = payload.get(flag)
        if isinstance(v, bool) and v is True:
            return flag
        if isinstance(payload.get("doctrine"), dict):
            dv = payload["doctrine"].get(flag)
            if isinstance(dv, bool) and dv is True:
                return flag
    tokens = tuple(_SHARED_ADVERSE) + tuple(extra_tokens or ())
    # (2) declared decision strings only (never field names or descriptive prose).
    for field in ("verdict", "status", "signal", "state", "answer_label"):
        s = payload.get(field)
        if not isinstance(s, str):
            continue
        low = s.lower()
        for tok in tokens:
            if tok in low and not _is_negated(low, tok):
                return tok
    return None


def _is_negated(text: str, tok: str) -> bool:
    """True if `tok` appears only in a negated/attribute context (e.g. 'no conflict',
    'not stale', 'conflict_flag": false'). Prevents a component that DECLARES it has 'no
    conflict' from being read as conflicted."""
    for m in re.finditer(re.escape(tok), text):
        i = m.start()
        window = text[max(0, i - 14):i]
        if re.search(r"\b(no|not|never|zero|without|non-?)\s*[-_a-z]*$", window):
            continue
        # a JSON boolean-false attribute like `"conflict": false` / `conflict=false`
        after = text[m.end():m.end() + 16]
        if re.match(r"['\"]?\s*[:=]\s*false", after):
            continue
        return False  # a non-negated occurrence => genuinely adverse
    return True  # every occurrence was negated


def _detect_positive(payload: dict, value: float | None) -> bool:
    """A REAL positive signal: a numeric value present, OR an affirmative verdict token
    (with no adverse token — adverse is checked separately by the caller)."""
    if value is not None:
        return True
    for field in ("verdict", "status", "signal", "state"):
        s = payload.get(field)
        if isinstance(s, str):
            low = s.lower()
            if any(tok in low for tok in _SHARED_POSITIVE):
                return True
    return False


def _gather_component(spec: dict, q: str, k: int, ns: str = "a11oy") -> dict:
    """Gather ONE component honestly. Never raises: any failure => UNAVAILABLE with a reason."""
    key = spec["key"]
    base = {
        "key": key,
        "title": spec["title"],
        "module": spec["module"],
        "available": False,
        "label": UNAVAILABLE,
        "value": None,
        "signal": None,
        "adverse_reason": None,
        "note": None,
    }
    override = _PROBE_OVERRIDES.get(key)
    try:
        if override is not None:
            payload = _invoke(override, q, k)
        else:
            fn = _resolve_callable(spec)
            if fn is None:
                base["note"] = ("sibling not importable (guarded ImportError) or exposes no "
                                "compute entrypoint; component honestly UNAVAILABLE")
                return base
            payload = _invoke(fn, q, k, style=spec.get("call_style", "generic"), ns=ns)
    except Exception as exc:  # a live failure degrades THIS component honestly, never the roll-up
        base["note"] = f"component compute failed, reported honestly: {str(exc)[:160]}"
        return base

    if not isinstance(payload, dict):
        base["note"] = "component returned no manifest dict; honestly UNAVAILABLE"
        return base

    payload = _normalize_component_payload(key, payload)
    label = _read_label(payload)
    value = _read_value(payload, spec.get("value_keys", ()))
    adverse = _detect_adverse(payload, spec.get("adverse"))
    if adverse is not None:
        signal = SIG_ADVERSE
    elif _detect_positive(payload, value):
        signal = SIG_OK
    else:
        signal = SIG_INDETERMINATE

    base.update({
        "available": True,
        "label": label if label is not None else MODELED,
        "value": round(value, 6) if value is not None else None,
        "value_semantics": "trust-aligned [0,1]; source direction normalized transparently",
        "source_verdict": payload.get("source_verdict"),
        "signal": signal,
        "adverse_reason": adverse,
        "note": ("component available; label read VERBATIM, never upgraded"
                 if adverse is None else f"adverse honesty signal: {adverse}"),
    })
    return base


def _component_module_readiness() -> list[dict]:
    """Probe import/entrypoint readiness without running a query or inventing query evidence."""
    checks = []
    for spec in COMPONENTS:
        fn = _resolve_callable(spec)
        checks.append({
            "key": spec["key"],
            "module": spec["module"],
            "ready": callable(fn),
            "entrypoint": spec["funcs"][0],
        })
    return checks


def _source_snapshot_metadata(ns: str = "a11oy") -> dict:
    """Small, source-authored snapshot manifest; never substitutes request time for capture time."""
    try:
        import a11oy_brain_graph as graph_module
        import szl_brain_api as brain_api

        graph = graph_module.get_brain_graph(ns)
        index = brain_api.get_index(ns)
        sources = graph.get("sources") if isinstance(graph.get("sources"), dict) else {}
        repos = sources.get("repos") if isinstance(sources.get("repos"), dict) else {}
        harvest = sources.get("harvest") if isinstance(sources.get("harvest"), dict) else {}
        return {
            "available": True,
            "label": graph.get("label", MODELED),
            "graph_generated_at": graph.get("generated"),
            "graph_content_hash": getattr(index, "content_hash", None),
            "node_count": graph.get("node_count"),
            "link_count": graph.get("link_count"),
            "distinct_artifacts": graph.get("distinct_artifacts"),
            "sources": {
                "surfaces": sources.get("surfaces"),
                "formulas": sources.get("formulas"),
                "repos": repos,
                "topics": sources.get("topics"),
                "harvest": harvest,
            },
            "capture_evidence": {
                "repo_snapshot_captured": repos.get("captured"),
                "repo_snapshot_source": repos.get("source"),
                "harvest_files": list(harvest.get("files") or []),
                "harvest_source": harvest.get("source"),
            },
            "freshness_rule": (
                "only source-provided captured_at/harvested_at values count as recency; "
                "graph_generated_at is cache-build time and is never treated as source freshness"
            ),
            "refresh_scope": "bounded committed local sources; no network, no source-date rewrite",
        }
    except Exception as exc:
        return {
            "available": False,
            "label": UNAVAILABLE,
            "error": str(exc)[:200],
            "freshness_rule": "no source timestamp fabricated while snapshot is unavailable",
            "refresh_scope": "bounded committed local sources; no network, no source-date rewrite",
        }


def build_corpus_source_contract() -> dict:
    """Return the bounded content-addressed corpus admission status (pure read)."""
    return _braincorpus.build_corpus_status(_ROOT)


def _service_readiness(ns: str = "a11oy", snapshot: dict | None = None) -> dict:
    """Operational/service readiness only.  It is never a synonym for query trust."""
    module_checks = _component_module_readiness()
    snapshot = snapshot if isinstance(snapshot, dict) else _source_snapshot_metadata(ns)
    modules_ready = all(c["ready"] for c in module_checks)
    index_ready = bool(snapshot.get("available") and snapshot.get("graph_content_hash")
                       and isinstance(snapshot.get("node_count"), int)
                       and snapshot.get("node_count") > 0)
    operational = modules_ready and index_ready
    return {
        "status": SERVICE_READY if operational else SERVICE_DEGRADED,
        "operational": operational,
        "query_trust_equivalent": False,
        "checks": {
            "brain_index_readable": index_ready,
            "honesty_components_loadable": modules_ready,
            "component_modules": module_checks,
        },
        "note": (
            "READY means the local graph/index and honesty evaluators can serve requests; it does "
            "not mean any query is trustworthy. Query trust remains a separate evidence verdict."
        ),
    }


def _remediation_plan(components: list[dict], query_evaluated: bool, ns: str) -> list[dict]:
    """Return concrete next actions for observed gaps; actions never change verdicts by fiat."""
    base = f"/api/{ns}/v1/brain/health"
    if not query_evaluated:
        return [{
            "component": "query",
            "action": "submit a non-empty q parameter to run grounding/provenance/conflict/uncertainty",
            "endpoint": f"GET {base}?q=<question>&k=12",
            "effect_on_trust": "none until evidence is evaluated",
        }]

    actions = []
    adverse = {c.get("key"): c.get("adverse_reason") for c in components
               if c.get("signal") == SIG_ADVERSE}
    if "freshness" in adverse:
        actions.append({
            "component": "freshness",
            "action": (
                "reindex the bounded committed local sources, then replace stale/undated source "
                "snapshots only through a separately reviewed harvest carrying real capture times"
            ),
            "endpoint": f"POST {base}/refresh",
            "limitation": (
                "local reindex clears caches but cannot make old evidence fresh or rewrite capture times"
            ),
        })
    if "grounding" in adverse:
        actions.append({
            "component": "grounding",
            "action": "narrow the query or ingest a cited local source that directly covers its terms",
            "effect_on_trust": "re-evaluate; no automatic upgrade",
        })
    if "provenance" in adverse:
        actions.append({
            "component": "provenance",
            "action": "attach source/url and an honest label to every supporting node, then reindex",
            "effect_on_trust": "re-evaluate; no automatic upgrade",
        })
    if "contradiction" in adverse:
        actions.append({
            "component": "contradiction",
            "action": "inspect the reported conflict pairs; resolve sources or narrow the claim scope",
            "effect_on_trust": "re-evaluate; conflicts remain adverse until evidence changes",
        })
    if "uncertainty" in adverse:
        actions.append({
            "component": "uncertainty",
            "action": "narrow the question and require a more concentrated, source-cited retrieval",
            "effect_on_trust": "re-evaluate; abstention remains active until uncertainty falls",
        })
    return actions


def _unevaluated_components() -> list[dict]:
    checks = {c["key"]: c for c in _component_module_readiness()}
    return [{
        "key": spec["key"],
        "title": spec["title"],
        "module": spec["module"],
        "available": False,
        "service_available": bool(checks[spec["key"]]["ready"]),
        "label": UNAVAILABLE,
        "value": None,
        "signal": None,
        "adverse_reason": None,
        "evaluation_status": QUERY_NOT_EVALUATED,
        "note": "no query was supplied; component was not invoked and no query evidence was fabricated",
    } for spec in COMPONENTS]


# ---------------------------------------------------------------------------
# Rollup assembly — pure computation over ONLY the available components. Mints nothing.
# ---------------------------------------------------------------------------
def _decide_verdict(components: list[dict]) -> tuple[str, str]:
    available = [c for c in components if c["available"]]
    unavailable = [c for c in components if not c["available"]]
    adverse = [c for c in available if c["signal"] == SIG_ADVERSE]
    indeterminate = [c for c in available if c["signal"] == SIG_INDETERMINATE]

    if len(available) < MIN_COMPONENTS:
        return (INSUFFICIENT_SIGNAL,
                f"only {len(available)} component(s) available (< {MIN_COMPONENTS} required); "
                "too little signal to judge brain trust")
    if adverse:
        reasons = ", ".join(f"{c['key']}:{c['adverse_reason']}" for c in adverse)
        return (UNTRUSTWORTHY,
                f"{len(adverse)} available component(s) report an adverse honesty signal "
                f"({reasons}); never TRUSTWORTHY while any component abstains/insufficient/"
                "conflict-flagged/stale-dominant")
    if unavailable or indeterminate:
        return (DEGRADED,
                f"{len(available)} component(s) OK, none adverse; but "
                f"{len(unavailable)} UNAVAILABLE and {len(indeterminate)} INDETERMINATE "
                "(partial signal — never upgraded to TRUSTWORTHY)")
    return (TRUSTWORTHY,
            f"all {len(available)} components available and OK; no adverse signal, "
            "none UNAVAILABLE")


def _modeled_trust(components: list[dict]) -> float | None:
    """A MODELED aggregate of the available numeric component values, capped at the trust
    ceiling (0.97, never 100%). Returns None when no component exposes a number — the roll-up
    never fabricates a score. This is a derived MODELED number, NEVER a MEASURED one."""
    vals = [c["value"] for c in components if c["available"] and isinstance(c["value"], (int, float))]
    if not vals:
        return None
    if _HAVE_NUMPY:
        mean = float(_np.mean(_np.asarray(vals, dtype="float64")))
    else:  # pragma: no cover - numpy present in this estate
        mean = sum(vals) / len(vals)
    return round(min(mean, TRUST_CEILING), 6)


def build_rollup(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """Gather every brain-honesty component (available ones read VERBATIM, missing ones
    UNAVAILABLE) and roll the AVAILABLE ones into ONE honest brain-trust verdict."""
    q = (q or "").strip()
    query_evaluated = bool(q)
    if query_evaluated:
        components = [_gather_component(spec, q, k, ns=ns) for spec in COMPONENTS]
        verdict, reason = _decide_verdict(components)
    else:
        components = _unevaluated_components()
        verdict = INSUFFICIENT_SIGNAL
        reason = ("no query supplied; epistemic trust was NOT EVALUATED. Operational readiness "
                  "is reported separately and is never promoted into a query-trust verdict")

    available = [c for c in components if c["available"]]
    unavailable = [c for c in components if not c["available"]]
    summary = {
        "components_total": len(components),
        "components_available": len(available),
        "components_unavailable": len(unavailable),
        "available_keys": [c["key"] for c in available],
        "unavailable_keys": [c["key"] for c in unavailable],
        "signals": {c["key"]: c["signal"] for c in available},
        "adverse": [{"key": c["key"], "reason": c["adverse_reason"]}
                    for c in available if c["signal"] == SIG_ADVERSE],
        "min_components_required": MIN_COMPONENTS,
    }
    trust = _modeled_trust(components) if query_evaluated else None
    snapshot = _source_snapshot_metadata(ns)
    readiness = _service_readiness(ns, snapshot=snapshot)

    return {
        "ok": True,
        "endpoint": "brain/health",
        "service": "a11oy.brain.health",
        "surface_id": SURFACE_ID,
        "title": "Brain Health — can the brain be trusted for this query right now?",
        "label": MODELED,
        "query": q,
        "k": k,
        "query_assessment": {
            "status": QUERY_EVALUATED if query_evaluated else QUERY_NOT_EVALUATED,
            "evaluated": query_evaluated,
            "note": ("component evidence evaluated for this query" if query_evaluated else
                     "blank q is a service-status view only; no answer trust was inferred"),
        },
        "service_readiness": readiness,
        "source_snapshot": snapshot,
        "verdict": verdict,
        "verdict_reason": reason,
        "modeled_trust": trust,
        "what": ("a governed ROLLUP of the brain's OWN honesty surfaces (grounding confidence, "
                 "memory freshness, source-lineage provenance, contradiction flag, uncertainty) "
                 "into a single brain-trust verdict for a query. Reads each available component "
                 "VERBATIM with its own honest label; components not importable are UNAVAILABLE "
                 "(never fabricated). Never TRUSTWORTHY while any available component abstains / "
                 "is insufficient / conflict-flagged / stale-dominant. Strictly knowledge-graph "
                 "honesty — advances no detection/fusion/effector/targeting/cueing capability."),
        "components": components,
        "summary": summary,
        "remediation": _remediation_plan(components, query_evaluated, ns),
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
            "note": ("additive OBSERVE-only rollup; touches no locked formula and no kernel; "
                     "GET reads sign/mint nothing; POST receipt emits an UNSIGNED SHA-256 "
                     "content digest only; introduces no theorem, no green/1.0; modeled_trust "
                     "is a MODELED aggregate capped at 0.97, never MEASURED, never 100%."),
        },
        "verdict_legend": {
            TRUSTWORTHY: "enough components available and ALL OK; none UNAVAILABLE",
            DEGRADED: "none adverse, but some UNAVAILABLE / INDETERMINATE (never TRUSTWORTHY)",
            UNTRUSTWORTHY: ">= 1 available component adverse (abstain/insufficient/conflict/stale)",
            INSUFFICIENT_SIGNAL: f"< {MIN_COMPONENTS} components available (too little to judge)",
        },
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "timestamp_utc": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on a GET read.
# ---------------------------------------------------------------------------
def _canonical_core(rollup: dict) -> str:
    """Deterministic canonical serialization of the trust-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + component evidence, not the clock."""
    core = {
        "query": rollup.get("query"),
        "query_assessment": rollup.get("query_assessment"),
        "verdict": rollup.get("verdict"),
        "modeled_trust": rollup.get("modeled_trust"),
        "summary": rollup.get("summary"),
        "components": [
            {"key": c.get("key"), "available": c.get("available"), "label": c.get("label"),
             "value": c.get("value"), "signal": c.get("signal"),
             "adverse_reason": c.get("adverse_reason")}
            for c in rollup.get("components", [])
        ],
        "source_snapshot": {
            "graph_content_hash": (rollup.get("source_snapshot") or {}).get("graph_content_hash"),
            "capture_evidence": (rollup.get("source_snapshot") or {}).get("capture_evidence"),
        },
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(rollup: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the rollup (no signature fabricated)."""
    canonical = _canonical_core(rollup)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainhealth.rollup",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the brain-health rollup; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


def _refresh_receipt(core: dict) -> dict:
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "kind": "szl.brainhealth.bounded-local-reindex",
        "algorithm": "sha256",
        "content_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST refresh)",
        "note": (
            "unsigned digest of the bounded local reindex result; no source timestamps were "
            "rewritten and no signature was fabricated"
        ),
        "computed_at": _now_iso(),
    }


def handle_refresh(ns: str = "a11oy") -> dict:
    """Rebuild only the in-process graph/index from committed local sources.

    This is intentionally not a network harvest and cannot make stale evidence fresh.  It is a
    bounded cache/index write with a receipt so operators can distinguish "reindexed" from
    "source evidence updated".
    """
    global _LAST_REFRESH_MONOTONIC
    if not _REFRESH_LOCK.acquire(blocking=False):
        return {
            "ok": False, "endpoint": "brain/health/refresh", "label": UNAVAILABLE,
            "outcome": "REINDEX-IN-PROGRESS", "retry_after_seconds": _REFRESH_COOLDOWN_SECONDS,
            "source_freshness_changed": False, "receipt": None,
        }
    now = time.monotonic()
    if _LAST_REFRESH_MONOTONIC and now - _LAST_REFRESH_MONOTONIC < _REFRESH_COOLDOWN_SECONDS:
        retry = round(_REFRESH_COOLDOWN_SECONDS - (now - _LAST_REFRESH_MONOTONIC), 3)
        _REFRESH_LOCK.release()
        return {
            "ok": False, "endpoint": "brain/health/refresh", "label": UNAVAILABLE,
            "outcome": "REINDEX-COOLDOWN", "retry_after_seconds": retry,
            "source_freshness_changed": False, "receipt": None,
        }
    before = _source_snapshot_metadata(ns)
    try:
        import szl_brain_api as brain_api

        # get_index(refresh=True) refreshes the graph exactly once and rebuilds the index.
        brain_api.get_index(ns, refresh=True)
        after = _source_snapshot_metadata(ns)
        core = {
            "scope": "BOUNDED-COMMITTED-LOCAL-SOURCES",
            "network_access": False,
            "source_timestamps_rewritten": False,
            "before_content_hash": before.get("graph_content_hash"),
            "after_content_hash": after.get("graph_content_hash"),
            "node_count": after.get("node_count"),
            "link_count": after.get("link_count"),
            "capture_evidence": after.get("capture_evidence"),
        }
        return {
            "ok": True,
            "endpoint": "brain/health/refresh",
            "label": MODELED,
            "outcome": "REINDEXED",
            "changed": core["before_content_hash"] != core["after_content_hash"],
            "source_freshness_changed": False,
            "before": before,
            "after": after,
            "receipt": _refresh_receipt(core),
            "note": (
                "local caches/index rebuilt from committed bounded sources. This does not refresh "
                "old capture dates; update source snapshots through a reviewed harvest if stale."
            ),
            "timestamp_utc": _now_iso(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": "brain/health/refresh",
            "label": UNAVAILABLE,
            "outcome": "REINDEX-FAILED",
            "source_freshness_changed": False,
            "error": str(exc)[:200],
            "receipt": None,
            "note": "no source timestamps changed and no receipt minted over a failed reindex",
            "timestamp_utc": _now_iso(),
        }
    finally:
        _LAST_REFRESH_MONOTONIC = time.monotonic()
        _REFRESH_LOCK.release()


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------
def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/health/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/health"
    return {
        "ok": True,
        "endpoint": "brain/health/info",
        "service": "a11oy.brain.health",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": "Brain Health — can the brain be trusted for this query right now?",
        "what": ("a governed rollup of the brain's OWN honesty surfaces into one honest "
                 "brain-trust verdict per query; strictly knowledge-graph honesty, advances no "
                 "detection/fusion/effector/targeting/cueing capability."),
        "rolls_up": [
            {"key": c["key"], "title": c["title"], "module": c["module"],
             "label_when_present": "read VERBATIM from the component (never upgraded)",
             "label_when_absent": UNAVAILABLE}
            for c in COMPONENTS
        ],
        "endpoints": {
            "info": f"GET  {base}/info",
            "health": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt",
            "bounded_local_reindex": f"POST {base}/refresh",
            "corpus_sources": f"GET  {base}/corpus-sources",
            "corpus_sources_info": f"GET  {base}/corpus-sources/info",
        },
        "state_separation": {
            "service_readiness": "can the graph/index and evaluators serve a request?",
            "query_trust": "does the evidence support this specific non-empty query?",
            "invariant": "service READY never promotes query trust",
            "empty_query": QUERY_NOT_EVALUATED,
        },
        "source_snapshot": _source_snapshot_metadata(ns),
        "verdicts": list(VERDICTS),
        "verdict_legend": {
            TRUSTWORTHY: "enough components available and ALL OK; none UNAVAILABLE",
            DEGRADED: "none adverse, but some UNAVAILABLE / INDETERMINATE (never TRUSTWORTHY)",
            UNTRUSTWORTHY: ">= 1 available component adverse (abstain/insufficient/conflict/stale)",
            INSUFFICIENT_SIGNAL: f"< {MIN_COMPONENTS} components available (too little to judge)",
        },
        "min_components_required": MIN_COMPONENTS,
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET info/health mint nothing; only "
                           "POST /receipt emits an unsigned SHA-256 content digest."),
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
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "timestamp_utc": _now_iso(),
    }


def handle_health(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """GET /brain/health — the rollup verdict + per-component (value + label + available).
    PURE READ (mints nothing). Never 500s: honest degraded response on error."""
    try:
        return build_rollup(q, k, ns)
    except Exception as exc:  # never 500: honest degraded response, no fabricated verdict
        return {
            "ok": False, "endpoint": "brain/health", "label": UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": INSUFFICIENT_SIGNAL,
            "verdict_reason": "rollup unavailable; no fabricated verdict emitted",
            "error": str(exc)[:200],
            "doctrine": "v11: brain-health unavailable; no fabricated verdict emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """POST /brain/health/receipt — the rollup + an UNSIGNED SHA-256 content-digest receipt
    (RECEIPT-ON-WRITE). Never 500s: honest degraded response on error."""
    try:
        roll = build_rollup(q, k, ns)
        out = dict(roll)
        out["receipt"] = _content_receipt(roll)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/health/receipt", "label": UNAVAILABLE,
            "verdict": INSUFFICIENT_SIGNAL, "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration.
#   GET  info/health — normal FastAPI GET handlers.
#   POST receipt     — raw-Request handler via app.router.add_route (Starlette passes the
#                      Request positionally, version-proof under fastapi==0.137.x), with
#                      app.add_api_route as the fallback. The handler is annotated
#                      request: fastapi.Request. Registered BEFORE the SPA catch-all by serve.py.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/health"

    @app.get(f"{base}/info")
    def _brainhealth_info():
        """Self-describing brain-health manifest + the components it rolls up (pure read)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainhealth_health(q: str = "", k: int = 12):
        """Live brain-trust rollup verdict + per-component value/label/available (pure read)."""
        return JSONResponse(handle_health(q, k, ns))

    @app.get(f"{base}/corpus-sources")
    def _brainhealth_corpus_sources():
        """Versioned local evidence manifests under the no-uplift proof lattice."""
        return JSONResponse(build_corpus_source_contract())

    @app.get(f"{base}/corpus-sources/info")
    def _brainhealth_corpus_sources_info():
        """Static, side-effect-free content-addressed corpus admission contract."""
        return JSONResponse({"ok": True, "endpoint": "brain/health/corpus-sources/info",
                             **_braincorpus.info()})

    async def _brainhealth_receipt(request):
        """POST: rollup + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE). Reads q/k from the
        query string when present; the body is otherwise ignored (a pure rollup compute)."""
        q = request.query_params.get("q", "")
        try:
            k = int(request.query_params.get("k", "12"))
        except (TypeError, ValueError):
            k = 12
        return JSONResponse(handle_receipt(q, k, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainhealth_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    refresh_path = f"{base}/refresh"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainhealth_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainhealth_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainhealth_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainhealth receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainhealth-wired:2(get-only)"

    async def _brainhealth_refresh(request):
        """POST: bounded local cache/index rebuild with an unsigned result receipt."""
        client = getattr(request, "client", None)
        host = getattr(client, "host", None)
        if not _client_is_loopback(host):
            return JSONResponse({
                "ok": False,
                "endpoint": "brain/health/refresh",
                "label": UNAVAILABLE,
                "outcome": "LOCAL-CLIENT-REQUIRED",
                "source_freshness_changed": False,
                "receipt": None,
                "note": "bounded local reindex rejects non-loopback clients; no auth bypass",
            }, status_code=403)
        result = handle_refresh(ns)
        status = 200
        if result.get("outcome") == "REINDEX-IN-PROGRESS":
            status = 409
        elif result.get("outcome") == "REINDEX-COOLDOWN":
            status = 429
        elif not result.get("ok"):
            status = 503
        return JSONResponse(result, status_code=status)

    try:
        import fastapi as _fastapi
        _brainhealth_refresh.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001
        pass

    try:
        if callable(add_route):
            app.router.add_route(refresh_path, _brainhealth_refresh, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(refresh_path, _brainhealth_refresh, methods=["POST"])
        else:  # pragma: no cover
            from starlette.routing import Route
            app.router.routes.append(Route(refresh_path, _brainhealth_refresh, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainhealth refresh POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainhealth-wired:3(no-refresh)"

    return "brainhealth-wired:5"


# ---------------------------------------------------------------------------
# Self-test — honest verdict, no fabricated component, no label upgrade, receipt only on write.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainhealth — self-test (brain-honesty rollup verdict)")
    print("=" * 72)

    # With NO siblings importable (the on-main reality until the PRs land), the rollup is
    # honestly INSUFFICIENT-SIGNAL — never a fabricated TRUSTWORTHY.
    _PROBE_OVERRIDES.clear()
    roll = build_rollup("what proves the estate thesis", k=8)
    assert roll["ok"] is True and roll["label"] == MODELED
    assert roll["verdict"] in VERDICTS
    print(f"[1] rollup ok, MODELED, verdict={roll['verdict']} "
          f"(available={roll['summary']['components_available']})  OK")

    # Stub TWO components OK -> TRUSTWORTHY; then flip one to an abstain -> UNTRUSTWORTHY.
    _PROBE_OVERRIDES["grounding"] = lambda q, k: {"label": "MODELED", "grounding_confidence": 0.8,
                                                  "verdict": "grounded"}
    _PROBE_OVERRIDES["freshness"] = lambda q, k: {"label": "SAMPLE", "freshness": 0.7,
                                                  "verdict": "fresh"}
    for _missing_key in ("provenance", "contradiction", "uncertainty"):
        _PROBE_OVERRIDES[_missing_key] = lambda q, k: None
    r2 = build_rollup("q", k=4)
    # exactly two available, both OK, but 3 UNAVAILABLE -> DEGRADED (never TRUSTWORTHY w/ gaps).
    assert r2["verdict"] == DEGRADED, r2["verdict"]
    assert r2["summary"]["components_available"] == 2
    print(f"[2] two OK + three UNAVAILABLE -> {r2['verdict']} (never TRUSTWORTHY w/ gaps)  OK")

    _PROBE_OVERRIDES["freshness"] = lambda q, k: {"label": "SAMPLE", "abstain": True}
    r3 = build_rollup("q", k=4)
    assert r3["verdict"] == UNTRUSTWORTHY, r3["verdict"]
    print(f"[3] one component abstains -> {r3['verdict']} (never TRUSTWORTHY)  OK")

    # All five OK -> TRUSTWORTHY, and labels are read VERBATIM (SAMPLE stays SAMPLE).
    _PROBE_OVERRIDES.clear()
    _PROBE_OVERRIDES["grounding"] = lambda q, k: {"label": "MODELED", "grounding_confidence": 0.9}
    _PROBE_OVERRIDES["freshness"] = lambda q, k: {"label": "SAMPLE", "freshness": 0.8}
    _PROBE_OVERRIDES["provenance"] = lambda q, k: {"label": "MEASURED", "provenance_coverage": 0.95}
    _PROBE_OVERRIDES["contradiction"] = lambda q, k: {"label": "MODELED", "contradiction_score": 0.0,
                                                      "verdict": "no-conflict"}
    _PROBE_OVERRIDES["uncertainty"] = lambda q, k: {"label": "MODELED", "uncertainty": 0.1}
    r4 = build_rollup("q", k=4)
    assert r4["verdict"] == TRUSTWORTHY, r4["verdict"]
    labels = {c["key"]: c["label"] for c in r4["components"]}
    assert labels["provenance"] == "MEASURED" and labels["freshness"] == "SAMPLE", labels
    assert r4["modeled_trust"] is not None and r4["modeled_trust"] <= TRUST_CEILING
    print(f"[4] all five OK -> {r4['verdict']}, labels verbatim, modeled_trust="
          f"{r4['modeled_trust']} (<=0.97)  OK")

    # RECEIPT-ON-WRITE: POST receipt carries an UNSIGNED sha256 digest; GET health mints none.
    rec = handle_receipt("q", 4)["receipt"]
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert "receipt" not in handle_health("q", 4), "GET health must NOT mint a receipt"
    print(f"[5] POST digest={rec['content_sha256'][:16]}… unsigned; GET health mints nothing  OK")

    _PROBE_OVERRIDES.clear()
    print("\nok:true checks:5")
    _sys.exit(0)
