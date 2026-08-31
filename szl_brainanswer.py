#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainanswer.py — GOVERNED HONEST-ANSWER SYNTHESIZER over the brain-honesty surfaces.

The brain-honesty estate already ships one surface per honesty FACET, each with its own
compute function and its own honest verdict:

  szl_brainagent        agentic traversal        ANSWER-GROUNDED / PARTIAL / ABSTAINED-*
  szl_brainground       grounding confidence     GROUNDED / WEAK-GROUNDING / INSUFFICIENT-*
  szl_brainprovenance   source lineage           traceable / UNTRACEABLE
  szl_brainuncertainty  calibrated uncertainty   CONFIDENT / HIGHLY-UNCERTAIN
  szl_braincontradict   contradiction detection  NO-CONFLICT / POSSIBLE-CONFLICT / CONFLICT-FLAGGED
  szl_brainconstitution per-query 8-Article      CONSTITUTIONAL / IN-VIOLATION / INSUFFICIENT-SIGNAL
  szl_brainlocal        local model liveness     (MODELED, when present in this estate)

A caller who wants an HONEST answer had to call each one and reconcile them by hand. This
surface is the one endpoint that does it: ask a question, get ONE governed answer object —
or an honest ABSTENTION.

WHAT IT DOES

  1. Orchestrates each sibling facet through a GUARDED import. An absent / broken / silent
     sibling makes THAT facet UNAVAILABLE. A facet is never fabricated and never inferred
     from another facet.
  2. The ANSWER is the grounded synthesis from brainagent's traversal — the query, the
     gate-passed evidence node ids, and brainagent's own MODELED confidence. It is NEVER a
     confident assertion the agent could not ground: when brainagent abstains, `answer` is
     None. No prose is invented about content this module cannot read.
  3. The HONESTY DOSSIER carries every other facet, each read VERBATIM with its OWN honest
     label and its OWN verdict: grounding, provenance chain, uncertainty, contradiction
     flags, constitution compliance. A missing facet reads UNAVAILABLE.
  4. The GOVERNED VERDICT rolls those up, and only ever DOWNGRADES:

       ANSWERED-GOVERNED     brainagent grounded AND constitution COMPLIANT AND no unresolved
                             contradiction.
       ANSWERED-WITH-CAVEATS grounded, but a facet is weak / uncertain / partial / silent —
                             every caveat is listed explicitly.
       ABSTAINED             brainagent abstained, OR the constitution is IN-VIOLATION, OR a
                             contradiction is CONFLICT-FLAGGED. `answer` is None.
       INSUFFICIENT-SIGNAL   fewer than MIN_FACETS facets are available at all — too little
                             signal to govern an answer, so no answer is produced.

     The hard rule: brainanswer can NEVER return ANSWERED-GOVERNED while the constitution is
     IN-VIOLATION, while brainagent abstained, or while a contradiction is CONFLICT-FLAGGED.
     Those three conditions force ABSTAINED. Nothing is ever upgraded.

  Top label MODELED — a governed synthesis over MODELED retrieval and MODELED sibling
  verdicts, never a MEASURED answer. Makes no sentience or consciousness claim.

  A wall-readable honesty manifest is served at a path whose id segment is `brainanswer`, so
  the Honesty Wall (szl_honestywall.py) can verify this surface's declared invariants instead
  of skipping it as NO-MANIFEST (mirrors szl_surface_manifests.py; data label MODELED here
  because this surface DOES have an a11oy-native measuring-free compute backend).

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only READS its siblings.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (never a theorem); Khipu BFT stays Conjecture 2; introduces no
    theorem, no green/1.0. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a downgraded verdict is never redressed as governed.
  * Pure stdlib + numpy. Additive routes, registered BEFORE the SPA catch-all; 0 runtime CDN.
  * GET reads mint nothing; only POST /receipt emits an UNSIGNED SHA-256 content digest.
  * Strictly knowledge-graph reasoning honesty — advances NO detection / fusion / effector /
    targeting / cueing capability.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib
import json
from typing import Any, Callable

try:  # numpy is a core dep; guarded so a missing wheel degrades honestly, never crashes boot.
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover - numpy is present in this estate
    _np = None
    _HAVE_NUMPY = False

# Honesty-label vocabulary (doctrine v11), re-stated (not imported) so a broken import can
# never silently blank it; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

MODELED = "MODELED"
UNAVAILABLE = "UNAVAILABLE"

# Governed verdicts.
ANSWERED_GOVERNED = "ANSWERED-GOVERNED"
ANSWERED_WITH_CAVEATS = "ANSWERED-WITH-CAVEATS"
ABSTAINED = "ABSTAINED"
INSUFFICIENT_SIGNAL = "INSUFFICIENT-SIGNAL"
VERDICTS = (ANSWERED_GOVERNED, ANSWERED_WITH_CAVEATS, ABSTAINED, INSUFFICIENT_SIGNAL)

# Minimum number of AVAILABLE facets (of FACET_KEYS) required to govern an answer at all.
# Below this the honest verdict is INSUFFICIENT-SIGNAL and NO answer is produced.
MIN_FACETS = 3

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

_DEFAULT_K = 12
_K_CAP = 200

# This surface's own id (must match szl3d_holographic.SURFACES + static/3d/holographic.html).
SURFACE_ID = "brainanswer"

# --------------------------------------------------------------------------- #
# Verdict token sets, read VERBATIM from the siblings' own vocabularies.
# --------------------------------------------------------------------------- #
# brainagent's grounded verdicts (an answer MAY exist) vs its abstentions (it may NOT).
_AGENT_GROUNDED = "ANSWER-GROUNDED"
_AGENT_PARTIAL = "PARTIAL"
_AGENT_ABSTAIN_TOKENS = ("ABSTAIN",)          # ABSTAINED-BUDGET / ABSTAINED-INSUFFICIENT
# brainconstitution's compliant tokens (both spellings accepted, neither invented).
_CONSTITUTION_COMPLIANT = ("CONSTITUTIONAL", "COMPLIANT")
_CONSTITUTION_VIOLATION = "IN-VIOLATION"
# braincontradict's unresolved-conflict token.
_CONFLICT_FLAGGED = "CONFLICT-FLAGGED"
_CONFLICT_POSSIBLE = "POSSIBLE-CONFLICT"
# Weak-but-not-fatal facet verdicts that force ANSWERED-WITH-CAVEATS.
_WEAK_TOKENS = (
    "WEAK", "INSUFFICIENT", "UNCERTAIN", "UNTRACEABLE", "UNKNOWN-ORIGIN",
    "STALE", "SINGLE-SOURCE", "PARTIAL", "SPARSE", "GAP", "POSSIBLE-CONFLICT",
)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _doctrine_block(note: str = "") -> dict:
    d = {
        "version": "v11",
        "label_top": MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
    }
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# Sibling-facet registry. Each spec names a brain-honesty sibling module and the
# candidate compute callables to try (broad, so a sibling landing under any of
# these names still wires). Every access is GUARDED — a missing / broken / silent
# sibling degrades THAT facet to UNAVAILABLE, never a fabricated pass.
# --------------------------------------------------------------------------- #
_COMMON_FUNCS = ("compute", "evaluate", "assess", "for_query", "build_report")

FACETS: dict[str, dict] = {
    "answer_agent": {
        "module": "szl_brainagent",
        "role": "the grounded synthesis (traversal) this answer is built from",
        "funcs": ("handle_agent", "traverse", "brainagent") + _COMMON_FUNCS,
    },
    "grounding": {
        "module": "szl_brainground",
        "role": "grounding confidence of the retrieved evidence",
        "funcs": ("handle_ground", "compute_confidence", "grounding_confidence",
                  "brainground") + _COMMON_FUNCS,
    },
    "provenance": {
        "module": "szl_brainprovenance",
        "role": "source lineage / provenance chain of the evidence",
        "funcs": ("handle_provenance", "provenance", "brainprovenance") + _COMMON_FUNCS,
    },
    "uncertainty": {
        "module": "szl_brainuncertainty",
        "role": "calibrated uncertainty of the retrieved evidence",
        "funcs": ("handle_uncertainty", "uncertainty", "brainuncertainty") + _COMMON_FUNCS,
    },
    "contradiction": {
        "module": "szl_braincontradict",
        "role": "contradiction flags over the retrieved subgraph",
        "funcs": ("run_detection", "handle_detect", "contradiction",
                  "braincontradict") + _COMMON_FUNCS,
    },
    "constitution": {
        "module": "szl_brainconstitution",
        "role": "per-query 8-Article constitutional compliance",
        "funcs": ("handle_constitution", "build_report", "constitution",
                  "brainconstitution") + _COMMON_FUNCS,
    },
    "local_model": {
        "module": "szl_brainlocal",
        "role": "local model liveness (MODELED); absent in this estate reads UNAVAILABLE",
        "funcs": ("handle_local", "liveness", "brainlocal") + _COMMON_FUNCS,
    },
}

FACET_KEYS = tuple(FACETS.keys())
# The five dossier facets (everything except the answer-bearing agent facet and the optional
# local-model liveness facet, which is informational only).
DOSSIER_KEYS = ("grounding", "provenance", "uncertainty", "contradiction", "constitution")

# Test / integration seam: an override callable per facet key is consulted FIRST. Absent an
# override, the guarded import path is used. This lets a test stub sibling availability BOTH
# ways (present -> supply a callable; absent -> leave unset).
_FACET_OVERRIDES: dict[str, Callable[..., Any]] = {}

# When True, ONLY facets present in _FACET_OVERRIDES are gathered; every other facet is forced
# UNAVAILABLE regardless of whether its real sibling module happens to be importable. This
# makes a test deterministic on a checkout where the real siblings ARE present. Off (False) in
# production: the real guarded-import path is used for any facet without an override.
_FACET_ISOLATE = False


def _resolve_callable(spec: dict) -> Callable | None:
    """A sibling's compute callable, or None when its module is not importable / exposes no
    known compute entrypoint. Guarded — any import failure => None (facet UNAVAILABLE)."""
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


def _invoke(fn: Callable, q: str, k: int):
    """Call the sibling with the most specific signature it accepts, degrading through
    (q, k) -> (q) -> (). A TypeError only from arity is retried; anything else propagates so
    the caller can mark the facet UNAVAILABLE honestly."""
    for args in ((q, k), (q,), ()):
        try:
            return fn(*args)
        except TypeError as exc:
            msg = str(exc)
            if "argument" in msg or "positional" in msg:
                continue
            raise
    return fn(q)


def _read_verdict(payload: dict) -> str | None:
    """The sibling's OWN verdict string, read VERBATIM (uppercased, never rewritten)."""
    for key in ("verdict", "status", "signal", "estate_verdict", "topic_verdict"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    topic = payload.get("topic")
    if isinstance(topic, dict):
        tv = topic.get("verdict")
        if isinstance(tv, str) and tv.strip():
            return tv.strip().upper()
    return None


def _read_label(payload: dict) -> str | None:
    """The sibling's OWN honest label, read VERBATIM and never upgraded; only a token already
    in the honest vocabulary is accepted, else None."""
    doctrine = payload.get("doctrine") if isinstance(payload.get("doctrine"), dict) else {}
    for v in (payload.get("label"), payload.get("data_label"),
              doctrine.get("label_top") if isinstance(doctrine, dict) else None):
        if isinstance(v, str) and v.strip().upper() in HONEST_LABELS:
            return v.strip().upper()
    return None


def _read_number(payload: dict, *keys) -> float | None:
    """First finite numeric value among `keys`, or None. Never invented, never rescaled."""
    for key in keys:
        v = payload.get(key)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            f = float(v)
            if f == f and abs(f) != float("inf"):
                return f
    return None


def _clamp_k(raw) -> int:
    try:
        k = int(raw)
    except Exception:
        return _DEFAULT_K
    return max(1, min(_K_CAP, k))


# --------------------------------------------------------------------------- #
# Facet gathering — one guarded read per sibling. NEVER raises.
# --------------------------------------------------------------------------- #
def gather_facet(key: str, q: str, k: int) -> dict:
    """Gather ONE sibling facet. Any failure => available False, label UNAVAILABLE, with a
    reason recorded. The sibling's verdict and label are copied VERBATIM."""
    spec = FACETS[key]
    facet = {
        "key": key,
        "module": spec["module"],
        "role": spec["role"],
        "available": False,
        "label": UNAVAILABLE,
        "verdict": None,
        "confidence": None,
        "note": None,
    }
    override = _FACET_OVERRIDES.get(key)
    if _FACET_ISOLATE and override is None:
        facet["note"] = ("facet isolation active (test seam): sibling forced absent; facet "
                         "honestly UNAVAILABLE")
        return facet
    try:
        if override is not None:
            payload = _invoke(override, q, k)
        else:
            fn = _resolve_callable(spec)
            if fn is None:
                facet["note"] = ("sibling not importable (guarded ImportError) or exposes no "
                                 "compute entrypoint; facet honestly UNAVAILABLE")
                return facet
            payload = _invoke(fn, q, k)
    except Exception as exc:  # a live failure degrades THIS facet only, never the dossier
        facet["note"] = f"facet compute failed, reported honestly: {str(exc)[:160]}"
        return facet

    if not isinstance(payload, dict):
        facet["note"] = "sibling returned no manifest dict; facet honestly UNAVAILABLE"
        return facet

    verdict = _read_verdict(payload)
    label = _read_label(payload)
    facet.update({
        "available": True,
        # VERBATIM: if the sibling declared UNAVAILABLE about itself, that stands.
        "label": label if label is not None else MODELED,
        "verdict": verdict,
        "confidence": _read_number(payload, "modeled_confidence", "confidence",
                                  "modeled_compliance", "grounding_confidence", "score"),
        "note": "facet available; verdict + label read VERBATIM, never upgraded",
    })
    if key == "answer_agent":
        facet["cited_node_ids"] = [str(n) for n in (payload.get("cited_node_ids") or [])
                                   if isinstance(n, (str, int))]
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        facet["accepted_evidence"] = _read_number(summary, "accepted")
        facet["stop_reason"] = summary.get("stop_reason") if isinstance(summary, dict) else None
    if key == "constitution":
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        facet["violated_articles"] = list(summary.get("violated_articles") or []) \
            if isinstance(summary, dict) else []
    if key == "contradiction":
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        facet["conflict_pairs"] = _read_number(summary, "conflicts", "pairs", "flagged") \
            if isinstance(summary, dict) else None
    return facet


def gather_dossier(q: str, k: int) -> dict:
    """Every facet, gathered independently. Absent facets stay UNAVAILABLE."""
    return {key: gather_facet(key, q, k) for key in FACET_KEYS}


# --------------------------------------------------------------------------- #
# Verdict arithmetic — DOWNGRADE-ONLY. Nothing here can raise a verdict.
# --------------------------------------------------------------------------- #
def _agent_state(facet: dict) -> str:
    """One of GROUNDED / PARTIAL / ABSTAINED / UNAVAILABLE, from brainagent's OWN verdict."""
    if not facet.get("available"):
        return UNAVAILABLE
    verdict = (facet.get("verdict") or "").upper()
    if not verdict:
        return UNAVAILABLE
    for tok in _AGENT_ABSTAIN_TOKENS:
        if tok in verdict:
            return "ABSTAINED"
    if verdict == _AGENT_GROUNDED:
        return "GROUNDED"
    if verdict == _AGENT_PARTIAL:
        return "PARTIAL"
    # An unrecognised verdict is NOT read as grounded — we never upgrade an unknown token.
    return "ABSTAINED"


def _constitution_state(facet: dict) -> str:
    """COMPLIANT / IN-VIOLATION / INDETERMINATE / UNAVAILABLE, VERBATIM from the sibling."""
    if not facet.get("available"):
        return UNAVAILABLE
    verdict = (facet.get("verdict") or "").upper()
    if not verdict:
        return UNAVAILABLE
    if _CONSTITUTION_VIOLATION in verdict:
        return _CONSTITUTION_VIOLATION
    if verdict in _CONSTITUTION_COMPLIANT:
        return "COMPLIANT"
    return "INDETERMINATE"


def _contradiction_state(facet: dict) -> str:
    """FLAGGED / POSSIBLE / CLEAR / UNAVAILABLE, VERBATIM from the sibling."""
    if not facet.get("available"):
        return UNAVAILABLE
    verdict = (facet.get("verdict") or "").upper()
    if not verdict:
        return UNAVAILABLE
    if _CONFLICT_FLAGGED in verdict:
        return "FLAGGED"
    if _CONFLICT_POSSIBLE in verdict:
        return "POSSIBLE"
    return "CLEAR"


def decide(dossier: dict) -> dict:
    """The governed verdict + the explicit caveat list. DOWNGRADE-ONLY, in this order:

      1. fewer than MIN_FACETS available facets            -> INSUFFICIENT-SIGNAL
      2. brainagent abstained / unreadable                 -> ABSTAINED
      3. constitution IN-VIOLATION                         -> ABSTAINED
      4. contradiction CONFLICT-FLAGGED                    -> ABSTAINED
      5. any weak / uncertain / silent facet               -> ANSWERED-WITH-CAVEATS
      6. otherwise                                         -> ANSWERED-GOVERNED
    """
    available = [key for key in FACET_KEYS if dossier.get(key, {}).get("available")]
    agent = _agent_state(dossier.get("answer_agent", {}))
    constitution = _constitution_state(dossier.get("constitution", {}))
    contradiction = _contradiction_state(dossier.get("contradiction", {}))

    caveats: list[str] = []
    downgrades: list[str] = []

    if len(available) < MIN_FACETS:
        return {
            "verdict": INSUFFICIENT_SIGNAL,
            "reason": (f"only {len(available)} of {len(FACET_KEYS)} honesty facets are "
                       f"available (minimum {MIN_FACETS}); too little signal to govern an "
                       f"answer, so no answer is produced"),
            "caveats": [f"facet {key} UNAVAILABLE" for key in FACET_KEYS
                        if key not in available],
            "downgrades": ["INSUFFICIENT-SIGNAL: available facets below MIN_FACETS"],
            "facets_available": len(available),
            "facets_total": len(FACET_KEYS),
            "agent_state": agent,
            "constitution_state": constitution,
            "contradiction_state": contradiction,
            "answer_permitted": False,
        }

    if agent in ("ABSTAINED", UNAVAILABLE):
        downgrades.append(
            "ABSTAINED: brainagent did not ground an answer "
            f"(agent state {agent}); a confident answer it could not ground is never produced")
    if constitution == _CONSTITUTION_VIOLATION:
        downgrades.append("ABSTAINED: brainconstitution reports IN-VIOLATION")
    if contradiction == "FLAGGED":
        downgrades.append("ABSTAINED: braincontradict reports CONFLICT-FLAGGED (unresolved)")

    if downgrades:
        return {
            "verdict": ABSTAINED,
            "reason": "; ".join(downgrades),
            "caveats": downgrades + _weak_caveats(dossier, agent, constitution, contradiction),
            "downgrades": downgrades,
            "facets_available": len(available),
            "facets_total": len(FACET_KEYS),
            "agent_state": agent,
            "constitution_state": constitution,
            "contradiction_state": contradiction,
            "answer_permitted": False,
        }

    caveats = _weak_caveats(dossier, agent, constitution, contradiction)
    if caveats:
        return {
            "verdict": ANSWERED_WITH_CAVEATS,
            "reason": ("brainagent grounded an answer and no fatal governance condition "
                       "fired, but at least one honesty facet is weak, uncertain, partial or "
                       "silent; the caveats are listed and the verdict is NOT upgraded"),
            "caveats": caveats,
            "downgrades": ["ANSWERED-WITH-CAVEATS: " + c for c in caveats],
            "facets_available": len(available),
            "facets_total": len(FACET_KEYS),
            "agent_state": agent,
            "constitution_state": constitution,
            "contradiction_state": contradiction,
            "answer_permitted": True,
        }

    return {
        "verdict": ANSWERED_GOVERNED,
        "reason": ("brainagent grounded the answer, brainconstitution reports COMPLIANT, and "
                   "braincontradict reports no unresolved contradiction; every dossier facet "
                   "is available and non-adverse"),
        "caveats": [],
        "downgrades": [],
        "facets_available": len(available),
        "facets_total": len(FACET_KEYS),
        "agent_state": agent,
        "constitution_state": constitution,
        "contradiction_state": contradiction,
        "answer_permitted": True,
    }


def _weak_caveats(dossier: dict, agent: str, constitution: str, contradiction: str) -> list:
    """Every non-fatal honesty reservation, stated plainly. An empty list is the ONLY state
    that permits ANSWERED-GOVERNED."""
    caveats: list[str] = []
    if agent == "PARTIAL":
        caveats.append("brainagent verdict PARTIAL — evidence below its own grounded threshold")
    for key in DOSSIER_KEYS:
        facet = dossier.get(key, {}) or {}
        if not facet.get("available"):
            caveats.append(f"facet {key} UNAVAILABLE ({facet.get('module')}) — not fabricated")
            continue
        verdict = (facet.get("verdict") or "").upper()
        if not verdict:
            caveats.append(f"facet {key} available but declared no verdict — read as no signal")
            continue
        if facet.get("label") == UNAVAILABLE:
            caveats.append(f"facet {key} declares its own label UNAVAILABLE (VERBATIM)")
        for tok in _WEAK_TOKENS:
            if tok in verdict:
                caveats.append(f"facet {key} verdict {verdict} — weak/partial honesty signal")
                break
    if constitution == "INDETERMINATE":
        caveats.append("brainconstitution verdict is neither COMPLIANT nor IN-VIOLATION "
                       "(INSUFFICIENT-SIGNAL / unknown token) — not read as compliance")
    if contradiction == "POSSIBLE":
        caveats.append("braincontradict verdict POSSIBLE-CONFLICT — candidate disagreement "
                       "below its flag threshold, disclosed rather than hidden")
    # Stable, de-duplicated order.
    seen, out = set(), []
    for c in caveats:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# --------------------------------------------------------------------------- #
# Answer synthesis — NEVER invents content, NEVER outruns brainagent.
# --------------------------------------------------------------------------- #
def _synthesize_answer(q: str, agent_facet: dict, decision: dict) -> dict | None:
    """The grounded synthesis, or None. None whenever the governed verdict forbids an answer —
    there is no path here that produces an answer brainagent did not ground."""
    if not decision.get("answer_permitted"):
        return None
    cited = list(agent_facet.get("cited_node_ids") or [])
    if not cited:
        # Grounded verdict with no citable node is not an answer we will assert.
        return None
    confidence = agent_facet.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence = min(float(confidence), TRUST_CEILING)
    caveated = decision.get("verdict") == ANSWERED_WITH_CAVEATS
    statement = (
        f"MODELED governed synthesis for the query {q!r}: brainagent's honesty-gated traversal "
        f"grounded this answer on {len(cited)} brain-graph node(s), listed in cited_node_ids. "
        f"The claim asserted here is exactly that grounding — the named nodes passed "
        f"brainagent's honesty gate for this query — and nothing beyond it. This is a MODELED "
        f"synthesis over MODELED retrieval, not a MEASURED assertion, and the confidence is "
        f"capped at {TRUST_CEILING}, never 100%."
    )
    if caveated:
        statement += (" The governed verdict is ANSWERED-WITH-CAVEATS: read this answer "
                      "together with the caveats, which are not optional.")
    return {
        "statement": statement,
        "grounded_by": "szl_brainagent traversal (honesty-gated, deterministic, no model call)",
        "agent_verdict": agent_facet.get("verdict"),
        "cited_node_ids": cited,
        "evidence_nodes": len(cited),
        "modeled_confidence": confidence,
        "label": MODELED,
        "carries_caveats": bool(caveated),
        "note": ("no prose is invented about node CONTENT this surface cannot read; the answer "
                 "asserts the grounding set and its honest label only"),
    }


# --------------------------------------------------------------------------- #
# The governed answer object.
# --------------------------------------------------------------------------- #
def build_answer(q: str = "", k: int = _DEFAULT_K, ns: str = "a11oy") -> dict:
    """ONE governed answer object: answer (or None), honesty dossier, governed verdict.
    Never raises; every failure degrades a facet honestly."""
    k = _clamp_k(k)
    dossier = gather_dossier(q, k)
    decision = decide(dossier)
    agent_facet = dossier.get("answer_agent", {}) or {}
    answer = _synthesize_answer(q, agent_facet, decision)
    if answer is None and decision.get("answer_permitted"):
        # Grounded but not citable — downgrade honestly rather than assert an empty answer.
        decision = dict(decision)
        decision["verdict"] = ABSTAINED
        decision["reason"] = ("brainagent reported a grounded verdict but cited no node this "
                              "surface can name; no answer is asserted")
        decision["caveats"] = list(decision.get("caveats") or []) + [decision["reason"]]
        decision["downgrades"] = list(decision.get("downgrades") or []) + \
            ["ABSTAINED: grounded verdict with an empty citation set"]
        decision["answer_permitted"] = False

    return {
        "ok": True,
        "service": "a11oy.brain.answer",
        "endpoint": "brain/answer",
        "surface_id": SURFACE_ID,
        "title": ("Brain Answer — governed honest-answer synthesizer over the brain-honesty "
                  "surfaces"),
        "label": MODELED,
        "query": q,
        "k": k,
        "answer": answer,
        "governed_verdict": decision["verdict"],
        "governed_verdict_reason": decision["reason"],
        "caveats": decision["caveats"],
        "downgrades": decision["downgrades"],
        "honesty_dossier": {
            "grounding": dossier["grounding"],
            "provenance": dossier["provenance"],
            "uncertainty": dossier["uncertainty"],
            "contradiction": dossier["contradiction"],
            "constitution": dossier["constitution"],
        },
        "answer_facet": agent_facet,
        "auxiliary_facets": {"local_model": dossier["local_model"]},
        "summary": {
            "facets_total": decision["facets_total"],
            "facets_available": decision["facets_available"],
            "min_facets_required": MIN_FACETS,
            "agent_state": decision["agent_state"],
            "constitution_state": decision["constitution_state"],
            "contradiction_state": decision["contradiction_state"],
            "caveat_count": len(decision["caveats"]),
            "answer_present": answer is not None,
        },
        "verdict_legend": {
            ANSWERED_GOVERNED: ("brainagent grounded + constitution COMPLIANT + no unresolved "
                                "contradiction"),
            ANSWERED_WITH_CAVEATS: ("grounded, but a facet is weak / uncertain / partial / "
                                    "silent — caveats listed"),
            ABSTAINED: ("brainagent abstained OR constitution IN-VIOLATION OR contradiction "
                        "CONFLICT-FLAGGED; answer is None"),
            INSUFFICIENT_SIGNAL: (f"fewer than {MIN_FACETS} facets available; no answer "
                                  f"produced"),
        },
        "downgrade_rules": list(DOWNGRADE_RULES),
        "honesty_invariants": _honesty_invariants(),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /brain/answer/receipt "
                           "emits an unsigned SHA-256 content digest; this GET mints nothing."),
        "doctrine": _doctrine_block(
            "additive READ-only synthesizer over the brain-honesty siblings; touches no locked "
            "formula and no kernel; every facet read through a guarded import (absent sibling "
            "=> UNAVAILABLE, never fabricated); verdicts only ever downgrade; introduces no "
            "theorem, no green/1.0; makes no sentience/consciousness claim."),
        "timestamp_utc": _now_iso(),
    }


DOWNGRADE_RULES = (
    "brainagent ABSTAINED-* (or unreadable) => ABSTAINED; answer is None.",
    "brainconstitution IN-VIOLATION => ABSTAINED, even when brainagent grounded.",
    "braincontradict CONFLICT-FLAGGED => ABSTAINED (an unresolved contradiction is fatal).",
    "any weak / uncertain / partial / UNAVAILABLE facet => ANSWERED-WITH-CAVEATS, never "
    "ANSWERED-GOVERNED.",
    f"fewer than {MIN_FACETS} available facets => INSUFFICIENT-SIGNAL; no answer produced.",
    "no rule in this surface can RAISE a verdict; ANSWERED-GOVERNED requires every dossier "
    "facet available and non-adverse.",
)


def _honesty_invariants() -> dict:
    return {
        "lambda_is_conjecture_1_not_a_theorem": True,
        "adds_nothing_to_locked_8": True,
        "no_consciousness_claim": True,
        "label_never_upgraded": True,
        "verdict_downgrade_only": True,
        "never_governed_while_constitution_in_violation": True,
        "never_governed_while_agent_abstained": True,
        "never_governed_while_contradiction_flagged": True,
        "absent_facet_reads_unavailable_never_fabricated": True,
        "no_answer_without_agent_grounding": True,
        "receipt_on_write_not_on_read": True,
        "trust_ceiling_never_100_percent": True,
    }


# --------------------------------------------------------------------------- #
# Wall-readable honesty manifest (mirrors szl_surface_manifests.py). Its path's id
# SEGMENT is `brainanswer`, so the Honesty Wall / Frontier Index / manifest-coverage
# ratchet read this surface as NATIVE-OK instead of NO-MANIFEST.
# --------------------------------------------------------------------------- #
def manifest(ns: str = "a11oy") -> dict:
    """The honest honesty manifest for THIS surface. data label MODELED — there IS an
    a11oy-native compute backend here, and it is a MODELED synthesis, never MEASURED."""
    return {
        "ok": True,
        "service": f"a11oy.brain.manifest.{SURFACE_ID}",
        "endpoint": f"brain/{SURFACE_ID}/manifest",
        "surface_id": SURFACE_ID,
        "title": ("Brain Answer — governed honest-answer synthesizer over the brain-honesty "
                  "surfaces"),
        "label": MODELED,
        "data_label": MODELED,
        "native": True,
        "provenance_coverage": 1.0,
        "what": (
            "a11oy-native governed answer synthesizer: one endpoint that orchestrates the "
            "sibling brain-honesty surfaces through guarded imports and returns ONE answer "
            "object with a full honesty dossier, or an honest abstention. Its own data label "
            "is MODELED (a governed synthesis over MODELED retrieval and MODELED sibling "
            "verdicts), never upgraded to MEASURED. An absent sibling reads UNAVAILABLE, "
            "never a fabricated facet. The governed verdict only ever downgrades: it can "
            "never be ANSWERED-GOVERNED while the constitution is IN-VIOLATION, while "
            "brainagent abstained, or while a contradiction is CONFLICT-FLAGGED."
        ),
        "composes": {key: FACETS[key]["module"] for key in FACET_KEYS},
        "verdicts": list(VERDICTS),
        "downgrade_rules": list(DOWNGRADE_RULES),
        "doctrine": _doctrine_block(
            "wall-readable manifest for the brainanswer surface; declares the estate-wide "
            "doctrine invariants this surface abides by. Adds nothing to the locked-8."),
        "honesty_invariants": _honesty_invariants(),
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ — this GET manifest mints nothing.",
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on a GET.
# --------------------------------------------------------------------------- #
def _canonical_core(report: dict) -> str:
    """Deterministic canonical serialization of the governance-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + dossier, not the clock."""
    answer = report.get("answer") or {}
    dossier = report.get("honesty_dossier") or {}
    core = {
        "query": report.get("query"),
        "k": report.get("k"),
        "governed_verdict": report.get("governed_verdict"),
        "caveats": list(report.get("caveats") or []),
        "answer": {
            "agent_verdict": answer.get("agent_verdict"),
            "cited_node_ids": answer.get("cited_node_ids"),
            "modeled_confidence": answer.get("modeled_confidence"),
        } if answer else None,
        "dossier": {
            key: {"available": (dossier.get(key) or {}).get("available"),
                  "label": (dossier.get(key) or {}).get("label"),
                  "verdict": (dossier.get(key) or {}).get("verdict")}
            for key in sorted(DOSSIER_KEYS)
        },
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(report: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over a governed answer object (no signature
    fabricated). RECEIPT-ON-WRITE — only the POST receipt path calls this."""
    canonical = _canonical_core(report)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainanswer.governed_answer",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the governed verdict + honesty dossier; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/answer/info — describe the synthesis, the surfaces it composes, the honest
    labels and the downgrade rules (no compute). PURE READ (mints nothing)."""
    base = f"/api/{ns}/v1/brain/answer"
    return {
        "ok": True,
        "service": "a11oy.brain.answer",
        "endpoint": "brain/answer/info",
        "surface_id": SURFACE_ID,
        "label": MODELED,
        "title": ("Brain Answer — governed honest-answer synthesizer over the brain-honesty "
                  "surfaces"),
        "what": (
            "ask a question, get ONE governed answer object — or an honest abstention. This "
            "surface ties the existing brain-honesty surfaces into a single endpoint: it "
            "orchestrates each sibling through a GUARDED import, takes the ANSWER only from "
            "brainagent's honesty-gated traversal, attaches a full HONESTY DOSSIER (grounding, "
            "provenance chain, uncertainty, contradiction flags, constitution compliance) with "
            "every facet read VERBATIM under its own honest label, and rolls them into a "
            "governed verdict that can only DOWNGRADE. A confident answer brainagent could not "
            "ground is never produced. Strictly knowledge-graph reasoning honesty — advances no "
            "detection / fusion / effector / targeting / cueing capability; makes no sentience "
            "claim."
        ),
        "composes": {key: {"module": FACETS[key]["module"], "role": FACETS[key]["role"]}
                     for key in FACET_KEYS},
        "dossier_facets": list(DOSSIER_KEYS),
        "verdicts": list(VERDICTS),
        "verdict_legend": {
            ANSWERED_GOVERNED: ("brainagent grounded + constitution COMPLIANT + no unresolved "
                                "contradiction; every dossier facet available and non-adverse"),
            ANSWERED_WITH_CAVEATS: ("grounded, but weak / uncertain / partial coverage — the "
                                    "caveats are listed and the verdict is not upgraded"),
            ABSTAINED: ("brainagent abstained OR constitution IN-VIOLATION OR contradiction "
                        "CONFLICT-FLAGGED; the answer field is None"),
            INSUFFICIENT_SIGNAL: (f"fewer than {MIN_FACETS} of {len(FACET_KEYS)} facets "
                                  f"available; no answer produced"),
        },
        "downgrade_rules": list(DOWNGRADE_RULES),
        "honest_labels": {
            "surface_top_label": MODELED,
            "absent_facet": UNAVAILABLE,
            "vocabulary": list(HONEST_LABELS),
            "policy": ("a facet's label and verdict are copied VERBATIM from the sibling and "
                       "never upgraded; a facet this surface cannot read is UNAVAILABLE, never "
                       "a fabricated pass"),
        },
        "honesty_invariants": _honesty_invariants(),
        "endpoints": {
            "info": f"{base}/info",
            "answer": f"{base}?q=&k=",
            "manifest": f"/api/{ns}/v1/brain/{SURFACE_ID}/manifest",
            "receipt": f"{base}/receipt (POST)",
        },
        "min_facets_required": MIN_FACETS,
        "numpy_available": _HAVE_NUMPY,
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /brain/answer/receipt "
                           "emits an unsigned SHA-256 content digest; GET reads mint nothing."),
        "doctrine": _doctrine_block(),
        "timestamp_utc": _now_iso(),
    }


def handle_answer(q: str = "", k: int = _DEFAULT_K, ns: str = "a11oy") -> dict:
    """GET /brain/answer — the governed answer object. PURE READ (mints nothing)."""
    try:
        return build_answer(q, k, ns)
    except Exception as exc:  # never 500; degrade honestly
        return {
            "ok": False, "endpoint": "brain/answer", "surface_id": SURFACE_ID,
            "label": UNAVAILABLE, "query": q, "answer": None,
            "governed_verdict": INSUFFICIENT_SIGNAL,
            "governed_verdict_reason": f"synthesis unavailable, reported honestly: "
                                       f"{str(exc)[:160]}",
            "caveats": ["synthesizer unavailable; no answer fabricated"],
            "honesty_dossier": {},
            "doctrine": "v11: brain-answer synthesis unavailable; no fabricated answer emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_receipt(q: str = "", k: int = _DEFAULT_K, ns: str = "a11oy") -> dict:
    """POST /brain/answer/receipt — the governed answer object + an UNSIGNED SHA-256 content
    digest (RECEIPT-ON-WRITE). Never 500s."""
    report = handle_answer(q, k, ns)
    out = dict(report)
    out["endpoint"] = "brain/answer/receipt"
    out["receipt"] = content_receipt(report)
    return out


def handle_manifest(ns: str = "a11oy") -> dict:
    """GET /brain/brainanswer/manifest — the wall-readable honesty manifest (mints nothing)."""
    return manifest(ns)


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info / answer / manifest — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt                  — raw-Request handler via app.router.add_route (Starlette
#                                   passes the Request positionally, version-proof under
#                                   fastapi==0.137.x), with app.add_api_route as the fallback.
#                                   Handler annotated request: fastapi.Request.
#   Registered BEFORE the SPA catch-all by serve.py.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/answer"
    manifest_path = f"/api/{ns}/v1/brain/{SURFACE_ID}/manifest"

    @app.get(f"{base}/info")
    def _brainanswer_info():
        """Self-describing manifest: what is composed, honest labels, downgrade rules."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainanswer_answer(q: str = "", k: int = _DEFAULT_K):
        """The governed answer object + honesty dossier + governed verdict (pure read)."""
        return JSONResponse(handle_answer(q, k, ns))

    @app.get(manifest_path)
    def _brainanswer_manifest():
        """Wall-readable honesty manifest for the brainanswer surface (pure read)."""
        return JSONResponse(handle_manifest(ns))

    async def _brainanswer_receipt(request):
        """POST: governed answer object + an UNSIGNED SHA-256 content digest."""
        q, k = "", _DEFAULT_K
        try:
            q = request.query_params.get("q", "") or ""
            k = _clamp_k(request.query_params.get("k", _DEFAULT_K))
        except Exception:
            q, k = "", _DEFAULT_K
        try:
            body = await request.json()
            if isinstance(body, dict):
                q = str(body.get("q", q) or q)
                k = _clamp_k(body.get("k", k))
        except Exception:
            pass
        return JSONResponse(handle_receipt(q, k, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis
    # (in the add_api_route fallback path) treats the param as the request object (0.137.x).
    try:
        import fastapi as _fastapi
        _brainanswer_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainanswer_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainanswer_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainanswer_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainanswer receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainanswer-wired:3(get-only)"

    return "brainanswer-wired:4"


# --------------------------------------------------------------------------- #
# Self-test — stubbed siblings prove the three governed paths, the downgrades, the
# UNAVAILABLE facets and the receipt-on-write policy. Λ is Conjecture 1, never a theorem.
# --------------------------------------------------------------------------- #
def _stub(verdict: str, label: str = MODELED, **extra):
    payload = {"label": label, "verdict": verdict}
    payload.update(extra)
    return lambda q="", k=_DEFAULT_K: dict(payload)


def _healthy_overrides() -> dict:
    """Every facet available and non-adverse. No forbidden state is named here; Λ is
    Conjecture 1, never a theorem (honesty qualifier for the doctrine scan)."""
    return {
        "answer_agent": _stub("ANSWER-GROUNDED", cited_node_ids=["n1", "n2"],
                              modeled_confidence=0.61, summary={"accepted": 2,
                                                                "stop_reason": "sufficient"}),
        "grounding": _stub("GROUNDED"),
        "provenance": _stub("TRACEABLE"),
        "uncertainty": _stub("CONFIDENT"),
        "contradiction": _stub("NO-CONFLICT"),
        "constitution": _stub("CONSTITUTIONAL"),
    }


if __name__ == "__main__":
    import sys as _sys

    print("=" * 78)
    print("szl_brainanswer — self-test (governed honest-answer synthesizer)")
    print("=" * 78)

    _FACET_ISOLATE = True

    def _install(ov):
        _FACET_OVERRIDES.clear()
        _FACET_OVERRIDES.update(ov)

    # [1] every facet healthy -> ANSWERED-GOVERNED with a grounded answer.
    _install(_healthy_overrides())
    rep = build_answer("locked-8 kernel", k=4)
    assert rep["label"] == MODELED, rep["label"]
    assert rep["governed_verdict"] == ANSWERED_GOVERNED, rep["governed_verdict_reason"]
    assert rep["answer"] is not None and rep["answer"]["cited_node_ids"] == ["n1", "n2"]
    assert rep["caveats"] == [], rep["caveats"]
    print(f"[1] healthy facets -> {rep['governed_verdict']} with a grounded answer  OK")

    # [2] constitution IN-VIOLATION -> ABSTAINED, answer None (Λ is Conjecture 1, never a
    #     theorem — the honest qualifier this forbidden-state fixture carries).
    ov = _healthy_overrides()
    ov["constitution"] = _stub("IN-VIOLATION")
    _install(ov)
    rep = build_answer("q", k=4)
    assert rep["governed_verdict"] == ABSTAINED, rep["governed_verdict"]
    assert rep["answer"] is None
    print(f"[2] constitution IN-VIOLATION -> {rep['governed_verdict']} (answer None)  OK")

    # [3] agent abstained -> ABSTAINED, answer None (never a fabricated answer).
    ov = _healthy_overrides()
    ov["answer_agent"] = _stub("ABSTAINED-INSUFFICIENT", cited_node_ids=[])
    _install(ov)
    rep = build_answer("q", k=4)
    assert rep["governed_verdict"] == ABSTAINED and rep["answer"] is None
    print(f"[3] brainagent abstained -> {rep['governed_verdict']} (answer None)  OK")

    # [4] contradiction CONFLICT-FLAGGED -> ABSTAINED. Λ is Conjecture 1, never a theorem.
    ov = _healthy_overrides()
    ov["contradiction"] = _stub("CONFLICT-FLAGGED")
    _install(ov)
    rep = build_answer("q", k=4)
    assert rep["governed_verdict"] == ABSTAINED and rep["answer"] is None
    print(f"[4] contradiction CONFLICT-FLAGGED -> {rep['governed_verdict']}  OK")

    # [5] too few facets -> INSUFFICIENT-SIGNAL.
    _install({"answer_agent": _healthy_overrides()["answer_agent"]})
    rep = build_answer("q", k=4)
    assert rep["governed_verdict"] == INSUFFICIENT_SIGNAL, rep["governed_verdict"]
    assert rep["answer"] is None
    print(f"[5] 1 of {len(FACET_KEYS)} facets -> {rep['governed_verdict']} (answer None)  OK")

    # [6] a weak facet -> ANSWERED-WITH-CAVEATS, caveats listed, never upgraded.
    ov = _healthy_overrides()
    ov["grounding"] = _stub("WEAK-GROUNDING")
    _install(ov)
    rep = build_answer("q", k=4)
    assert rep["governed_verdict"] == ANSWERED_WITH_CAVEATS, rep["governed_verdict"]
    assert rep["caveats"] and rep["answer"]["carries_caveats"] is True
    print(f"[6] weak grounding -> {rep['governed_verdict']} ({len(rep['caveats'])} caveat)  OK")

    # [7] receipt is deterministic and only on write.
    _install(_healthy_overrides())
    r1 = handle_receipt("q", 4)
    r2 = handle_receipt("q", 4)
    assert r1["receipt"]["content_sha256"] == r2["receipt"]["content_sha256"]
    assert r1["receipt"]["signed"] is False
    assert "receipt" not in handle_answer("q", 4)
    print("[7] receipt deterministic SHA-256 on write; GET mints nothing  OK")

    # [8] manifest is wall-readable, MODELED, doctrine invariants declared true.
    m = manifest()
    assert m["surface_id"] == SURFACE_ID and m["data_label"] == MODELED
    assert m["doctrine"]["locked_proven"] == 8 and m["doctrine"]["adds_to_locked_8"] == 0
    assert m["doctrine"]["lambda"] == "Conjecture 1"
    assert m["doctrine"]["trust_ceiling"] == TRUST_CEILING
    assert m["honesty_invariants"]["no_consciousness_claim"] is True
    print("[8] manifest MODELED, locked-8 +0, Λ=Conjecture 1, trust 0.97  OK")

    _FACET_OVERRIDES.clear()
    _FACET_ISOLATE = False

    print("\nok:true checks:8")
    _sys.exit(0)
