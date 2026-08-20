# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings — ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED (749/14/163). Λ = Conjecture 1 (advisory, NEVER "green").
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
"""
szl_agentloop_brain — the Brain feed for the governed agent-loop (Wave P, Dev 4).

Two thin, GUARDED read helpers that let szl_agent_loop_governed.run_loop become a
genuinely Brain-POWERED governed run instead of a self-contained one:

  consult_brain(ns, task, top_k)  → pull ADVISORY context from the Brain vault
                                     (corpus="brain") relevant to the task.
  allocate_energy(ns, run_id, ..) → request an honest per-loop ENERGY allocation
                                     from the Brain's harnessed power (/brain/energy).

WHY (Wave O #814 fed the Brain into the loop as consulted context; Wave P #811 made
the Brain a power source at /brain/energy). This module chains BOTH into the ONE
composite governed-loop receipt: brain-context + profile + steps + eval + energy.

READ PATHS (code against the unmerged Brain PRs; GUARDED fallback to what is on main):
  * BRAIN VAULT  — PREFERRED szl_brain_corpus.brain_pulse(ns, query, top_k) (PR #814,
    feat/brain-feeds-flywheel). FALLBACK szl_brain_api.get_index(ns).search(task, k)
    (on main) → an honest local pulse built from REAL harvested graph nodes. Else
    UNAVAILABLE. No pulse, node, or citation is ever fabricated.
  * BRAIN ENERGY — PREFERRED szl_brain_energy.brain_energy_summary(ns) (PR #811,
    feat/brain-energy, GET /api/<ns>/v1/brain/energy). FALLBACK szl_energy_budget
    (on main) → an honest SAMPLE/ESTIMATE per-loop draw. Else UNAVAILABLE. Joules are
    MEASURED only from a live meter, SAMPLE from the budget fallback, else null.

HONESTY (absolute): every passage is a REAL brain node with its own id + provenance;
every joule figure carries its true label (MEASURED / MODELED / SAMPLE / UNAVAILABLE);
the allocation SPLIT is a deterministic MODELED share of a real harnessed total, never
a fabricated meter reading. Λ is Conjecture 1 (advisory). Nothing touches the locked-8.
This module NEVER raises into its caller and NEVER changes a gate/decision — the context
and the energy budget are advisory inputs recorded in the receipt.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

CORPUS_ID = "brain"
DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
TRUST_CEILING = 0.97
_CONJECTURE_NOTE = ("Λ is Conjecture 1 — advisory only, NEVER 'green'/proven/a gate; "
                    "trust ceiling 0.97; nothing here touches the locked-8.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ── availability probes (single source of truth for what the loop can advertise) ──
def _corpus_mod():
    import szl_brain_corpus as _c  # PR #814 (feat/brain-feeds-flywheel), guarded
    return _c


def _brain_api_mod():
    import szl_brain_api as _a  # on main — the queryable brain graph index
    return _a


def _energy_mod():
    import szl_brain_energy as _e  # PR #811 (feat/brain-energy), guarded
    return _e


def _budget_mod():
    import szl_energy_budget as _b  # on main — Bekenstein-gated SAMPLE budget
    return _b


def brain_context_available(ns: str = "a11oy") -> bool:
    """True when SOME real brain read path is importable (corpus PR or the on-main index)."""
    try:
        return bool(_corpus_mod().available(ns))
    except Exception:
        pass
    try:
        return bool(_brain_api_mod().get_index(ns).nodes)
    except Exception:
        return False


def brain_energy_available(ns: str = "a11oy") -> bool:
    """True when SOME real energy read path is importable (brain-energy PR or the budget)."""
    try:
        _energy_mod()
        return True
    except Exception:
        pass
    try:
        _budget_mod()
        return True
    except Exception:
        return False


# ===========================================================================
# (a) BRAIN VAULT CONTEXT — advisory context pulled from corpus="brain".
# ===========================================================================
def consult_brain(ns: str, task: str, top_k: int = 5) -> dict:
    """Pull an ADVISORY Brain-vault pulse (corpus="brain") relevant to `task`.

    PREFERRED: szl_brain_corpus.brain_pulse (PR #814). GUARDED FALLBACK: an honest
    local pulse built from REAL nodes via szl_brain_api (on main). Else UNAVAILABLE.
    Returns a receipt-embeddable dict; NEVER raises, NEVER fabricates a node."""
    task = (task or "").strip()

    # PREFERRED read path — Dev-4 #814 brain vault pulse (hub-preferred inside it).
    try:
        p = _corpus_mod().brain_pulse(ns, query=task, top_k=top_k)
        if isinstance(p, dict):
            p.setdefault("corpus_id", CORPUS_ID)
            p.setdefault("conjecture_note", _CONJECTURE_NOTE)
            p["read_path"] = "szl_brain_corpus.brain_pulse (PR #814)"
            return p
    except Exception:
        pass  # module absent/errored → guarded fallback below (never fabricate)

    # GUARDED FALLBACK — real harvested nodes via the on-main brain index.
    try:
        idx = _brain_api_mod().get_index(ns)
        hits = idx.search(task, k=max(1, top_k)) if task else idx.salience(top=top_k)
        relevant = [{"id": h.get("id"),
                     "text": str(h.get("title") or h.get("id"))[:240],
                     "source": h.get("node_label") or h.get("kind") or "brain-graph",
                     "score": h.get("score", h.get("salience"))}
                    for h in (hits or [])]
        st = idx.index_status()
        available = bool(idx.nodes)
        return {
            "corpus_id": CORPUS_ID,
            "available": available,
            "label": ("MODELED (local brain-graph pulse via szl_brain_api; "
                      "szl_brain_corpus #814 not merged in this runtime — see dependency)"
                      if available else
                      "UNAVAILABLE — Brain vault empty/down; no context fabricated"),
            "read_path": "szl_brain_api.get_index(ns).search (guarded on-main fallback)",
            "brain_hub_available": False,
            "knowledge": {
                "node_count": st.get("node_count", 0),
                "community_count": st.get("community_count", 0),
                "vector_backend": st.get("vector_backend"),
                "embed_tier": st.get("embed_tier"),
            },
            "relevant": relevant,
            "relevant_note": ("Top brain passages relevant to the task (REAL harvested "
                              "nodes; cite by id/source). Empty when nothing matches — "
                              "never padded."),
            "dependency": ("szl_brain_corpus (PR #814 feat/brain-feeds-flywheel) not "
                           "merged in this runtime; consulted szl_brain_api directly as a "
                           "guarded fallback. Code targets brain_pulse() when it lands."),
            "conjecture_note": _CONJECTURE_NOTE,
        }
    except Exception as e:
        return {
            "corpus_id": CORPUS_ID,
            "available": False,
            "label": "UNAVAILABLE — no Brain read path importable; no context fabricated.",
            "read_path": "none",
            "relevant": [],
            "error": repr(e),
            "conjecture_note": _CONJECTURE_NOTE,
        }


def context_block(brain: dict) -> dict:
    """Compact, receipt-embeddable summary of a consult_brain() result."""
    b = brain or {}
    rel = b.get("relevant") or []
    return {
        "corpus_id": b.get("corpus_id", CORPUS_ID),
        "available": bool(b.get("available")),
        "label": b.get("label"),
        "read_path": b.get("read_path"),
        "brain_hub_available": b.get("brain_hub_available"),
        "n_passages": len(rel),
        "cited_node_ids": [r.get("id") for r in rel if r.get("id")],
        "knowledge": b.get("knowledge"),
        "advisory": ("Consulted Brain-vault context (corpus='brain'). ADVISORY only — "
                     "recorded in the composite receipt; NEVER changes a gate/decision "
                     "and never fabricates a citation."),
    }


def grounding_preamble(brain: dict, max_chars: int = 700) -> str:
    """A short, clearly-labelled advisory context preamble built from REAL brain
    passages, to be threaded into a step through the engine's GOVERNED untrusted
    channel. Empty when no real passages — never padded."""
    rel = (brain or {}).get("relevant") or []
    if not rel:
        return ""
    lines = ["[BRAIN-VAULT ADVISORY CONTEXT — corpus='brain'; real harvested nodes; "
             "advisory only, verify before relying]"]
    for r in rel:
        rid = r.get("id") or "?"
        txt = str(r.get("text") or "").strip()
        src = r.get("source") or "brain-graph"
        if txt:
            lines.append(f"- ({rid} · {src}) {txt}")
    out = "\n".join(lines)
    return out[:max_chars]


# ===========================================================================
# (e) BRAIN ENERGY ALLOCATION — request a per-loop budget from /brain/energy.
# ===========================================================================
def allocate_energy(ns: str, run_id: str, n_steps: int, task: str = "") -> dict:
    """Request an honest per-loop ENERGY allocation from the Brain's harnessed power.

    PREFERRED: szl_brain_energy.brain_energy_summary (PR #811, GET /brain/energy) — a
    real harnessed-joules total + per-organ split + signed energy receipt. We compute
    the loop's MODELED share (deterministic split of a REAL total; null when the
    harnessed total is UNAVAILABLE — never fabricated). GUARDED FALLBACK: an honest
    SAMPLE/ESTIMATE per-loop draw via szl_energy_budget (on main). Else UNAVAILABLE.
    NEVER raises, NEVER fabricates joules."""
    n_steps = max(1, int(n_steps or 1))

    # PREFERRED read path — the Brain as the ecosystem power source (#811).
    try:
        summ = _energy_mod().brain_energy_summary(ns)
        total = summ.get("total_harnessed_joules")
        j_label = summ.get("harnessed_label") or summ.get("label")
        tpj = summ.get("tokens_per_joule")
        per_organ = summ.get("per_organ") or []
        receipt = summ.get("energy_receipt") or {}
        # Deterministic MODELED share for the agent-loop organ: even split across the
        # brain's organs + our n_steps, applied to the REAL harnessed total. When the
        # total is UNAVAILABLE (null) the allocation joules are null too — never faked.
        denom = max(1, (len(per_organ) or 1)) * n_steps
        alloc_j = round(float(total) / denom, 6) if isinstance(total, (int, float)) else None
        return {
            "available": True,
            "read_path": "szl_brain_energy.brain_energy_summary (PR #811, /brain/energy)",
            "source": "brain-harnessed",
            "total_harnessed_joules": total,
            "harnessed_label": j_label,
            "tokens_per_joule": tpj,
            "gco2_per_token": summ.get("gco2_per_token"),
            "per_organ_count": len(per_organ),
            "loop_allocation_joules": alloc_j,
            "loop_allocation_joules_label": j_label,
            "n_steps": n_steps,
            "allocation_method": ("MODELED even split of the Brain's REAL harnessed total "
                                  "across organs × loop steps; joules label inherited from "
                                  "the harnessed total (null when UNAVAILABLE — never faked)."),
            "energy_receipt": {"payload_sha256": receipt.get("payload_sha256"),
                               "signed": bool(receipt.get("signed"))},
            "label": ("LIVE brain-energy allocation — the Brain harnessed the joules and "
                      "distributed a per-loop budget; joules label is the meter's own."),
            "conjecture_note": _CONJECTURE_NOTE,
        }
    except Exception:
        pass  # brain-energy module absent → guarded on-main fallback

    # GUARDED FALLBACK — honest SAMPLE/ESTIMATE draw via the Bekenstein budget (on main).
    try:
        budget = _budget_mod()
        # A tiny, honest per-step SAMPLE draw keyed to the run — labeled SAMPLE, never MEASURED.
        sample_j = 0.5 * n_steps
        rec = budget.track_task(
            output=("agentloop:%s:%d" % (run_id, n_steps)).encode("utf-8"),
            energy_source="agentloop-fallback",
            joules_est=sample_j,
            extra={"run_id": run_id, "n_steps": n_steps, "surface": "szl_agent_loop_governed"})
        summary = budget.budget_summary()
        return {
            "available": True,
            "read_path": "szl_energy_budget.track_task (guarded on-main SAMPLE fallback)",
            "source": "energy-budget-fallback",
            "total_harnessed_joules": summary.get("total_joules_est"),
            "harnessed_label": rec.get("joules_est_label"),
            "loop_allocation_joules": rec.get("joules_est"),
            "loop_allocation_joules_label": rec.get("joules_est_label"),
            "joules_label": rec.get("joules_label"),
            "bekenstein_within_bound": rec.get("within_bound"),
            "n_steps": n_steps,
            "allocation_method": ("SAMPLE/ESTIMATE per-loop draw via the Bekenstein-gated "
                                  "energy budget (no live meter here); labeled SAMPLE."),
            "energy_receipt": {"task_hash": rec.get("task_hash"), "signed": False},
            "label": ("MODELED-SAMPLE energy allocation — szl_brain_energy (#811) not "
                      "merged in this runtime; honest SAMPLE draw via the energy budget. "
                      "Joules are SAMPLE/ESTIMATE, never a live meter reading."),
            "dependency": ("szl_brain_energy (PR #811 feat/brain-energy, /brain/energy) not "
                           "merged; used szl_energy_budget as a guarded fallback. Code "
                           "targets brain_energy_summary() when it lands."),
            "conjecture_note": _CONJECTURE_NOTE,
        }
    except Exception as e:
        return {
            "available": False,
            "read_path": "none",
            "source": "none",
            "loop_allocation_joules": None,
            "loop_allocation_joules_label": "UNAVAILABLE",
            "label": "UNAVAILABLE — no energy read path importable; no joules fabricated.",
            "error": repr(e),
            "conjecture_note": _CONJECTURE_NOTE,
        }


def energy_block(energy: dict) -> dict:
    """Compact, receipt-embeddable summary of an allocate_energy() result."""
    e = energy or {}
    return {
        "available": bool(e.get("available")),
        "source": e.get("source"),
        "read_path": e.get("read_path"),
        "loop_allocation_joules": e.get("loop_allocation_joules"),
        "loop_allocation_joules_label": e.get("loop_allocation_joules_label"),
        "total_harnessed_joules": e.get("total_harnessed_joules"),
        "harnessed_label": e.get("harnessed_label"),
        "energy_receipt": e.get("energy_receipt"),
        "label": e.get("label"),
    }


def _selftest() -> None:  # pragma: no cover — `python3 szl_agentloop_brain.py`
    ns = "a11oy"
    # consult_brain never raises; returns a labelled dict with a real read_path.
    b = consult_brain(ns, "explain the Euler Khipu DAG identity F1 and its energy budget")
    assert isinstance(b, dict) and "available" in b and "label" in b, b
    assert b.get("read_path"), "consult_brain must record which read path it used"
    if b.get("available"):
        assert isinstance(b.get("relevant"), list), "relevant passages present when available"
    cb = context_block(b)
    assert cb["corpus_id"] == CORPUS_ID and "advisory" in cb
    # a preamble is either empty or clearly labelled advisory (never fabricated).
    pre = grounding_preamble(b)
    assert pre == "" or "BRAIN-VAULT ADVISORY CONTEXT" in pre

    # allocate_energy never raises; joules are labelled, never fabricated.
    e = allocate_energy(ns, run_id="aloop-selftest", n_steps=3, task="demo")
    assert isinstance(e, dict) and "available" in e and "label" in e, e
    assert e.get("read_path"), "allocate_energy must record which read path it used"
    lbl = str(e.get("loop_allocation_joules_label") or "")
    j = e.get("loop_allocation_joules")
    # MEASURED must never be claimed by the fallback; joules None or a real SAMPLE number.
    assert "MEASURED" not in (e.get("label") or "") or e.get("source") == "brain-harnessed"
    eb = energy_block(e)
    assert "loop_allocation_joules" in eb

    print("szl_agentloop_brain: ALL OK — consult_brain read_path=%r available=%s "
          "n_passages=%d ; allocate_energy read_path=%r available=%s joules=%r label=%r. "
          "Λ=Conjecture 1; locked-8 untouched."
          % (b.get("read_path"), b.get("available"), len(b.get("relevant") or []),
             e.get("read_path"), e.get("available"), j, lbl))


if __name__ == "__main__":  # pragma: no cover
    _selftest()
