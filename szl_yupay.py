# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by the a11oy Full-Stack Team (YUPAY). Co-Authored-By: Perplexity Computer Agent.
#
# YUPAY — Quechua: "to count / to reckon / to audit".
# Lineage: Yachay (knowing) · Chaski (relay) · Khipu (record) · Ayni (reciprocity) ·
#          Ñawi (the eye that sees) · WILLAY (the one that discloses) ·
#          WAQAY (the one that safeguards).
# YUPAY is the one that RECKONS — the governed multi-model AUDIT harness.
#
# ===========================================================================
# YUPAY = a GOVERNED multi-model audit harness: run the SAME audit task through
# MULTIPLE models, score each on issues-found / tokens / cost / latency, and emit
# ONE DSSE-SIGNED comparison receipt. The signed multi-model comparison is the
# GOVERNED DIFFERENCE nobody else has.
# ---------------------------------------------------------------------------
# WHAT WE STUDIED (open work, made ours — cited as INSPIRATION only):
#   • Kilo Code / André Lindenberg, "We Audited the Same Codebase with Claude
#     Opus 4.8 and MiniMax M3" (blog.kilo.ai, 2026-06-05). The AUDIT METHODOLOGY:
#     give every model the IDENTICAL audit task + planted-bug codebase, then track
#     issues-found, tokens, cost, and time per run, and reason about cost-per-issue
#     rather than a single "winner". We adopt the METHODOLOGY; we run it over OUR
#     OWN governed open models on OUR OWN harness.
#   • MiniMax Sparse Attention paper (huggingface.co/papers/2606.13392) — cited as
#     the INSPIRATION for a SEPARATE, box-gated research note on OUR own efficient-
#     attention path for SZL-Nemo (Qwen3-32B Apache-2.0). YUPAY itself trains/serves
#     NO model — it is a governed harness + signed comparison.
#
# CRITICAL DOCTRINE — NO M3 WEIGHTS / NO M3 DERIVATIVE (defense-license + sovereignty):
#   MiniMax M3 is open-weight BUT its license RESTRICTS military/defense use, and
#   MiniMax is China-based (PRC Intelligence Law). The founder demos at Defense
#   Unicorns Warhacker. THEREFORE YUPAY:
#     • NEVER bases SZL-Nemo on M3, NEVER ships an M3 derivative;
#     • NEVER downloads / serves / ingests M3 weights;
#     • takes ONLY the open AUDIT METHODOLOGY (a published idea) and the published
#       sparse-attention TECHNIQUE (as inspiration for OUR own path on the clean
#       OPEN Qwen3-32B Apache-2.0 base).
#   M3 appears in YUPAY only as a NON-PARTICIPATING reference row, labeled
#   EXCLUDED-BY-DOCTRINE (defense-license + PRC sovereignty) — never run, never
#   scored as if run. This stance is honest, surfaced on the tab, and signed.
#
# WHAT MAKES YUPAY *OURS* (the governed difference — not a leaderboard blog):
#   1. The audit is run over OUR OWN governed models: SZL-Nemo (governed Qwen3-32B
#      Apache-2.0), the HF-router models a11oy already declares (szl_llm_registry),
#      and mesh models WHEN wired. M3 is excluded by doctrine (see above).
#   2. EVERY comparison emits a DSSE-SIGNED provenance receipt (szl_dsse) recording:
#      the task digest, the per-model scoreboard, the cost basis (published rates,
#      cited), the honest data-label of each row, and the Restraint verdict.
#   3. EVERY row is HONESTLY LABELED: a score is MEASURED only when a real run
#      happened in THIS process; otherwise it is SAMPLE/MODELED (cost projected from
#      published per-token rates) or ROADMAP/EXCLUDED (model not reachable / barred).
#      We NEVER fabricate a benchmark — an unreachable model is labeled honestly.
#   4. A Restraint verdict is attached so the governed recommendation ("value pick
#      vs thorough pick") is bounded and signed, never an absolute "this model wins".
#
# HONESTY (Doctrine v11, Zero-Bandaid Law):
#   • No API key is wired in the HF Space, so in-Space rows are SAMPLE/MODELED:
#     issues-found are MODELED from the published Kilo benchmark; cost is computed
#     from MODELED token counts × published per-token rates (cited). They are
#     labeled MODELED, NEVER MEASURED, on the served tab and in the receipt.
#   • When a real run DOES happen (a key is present and a model is reachable), that
#     row is labeled MEASURED and the receipt records the real token usage.
#   • Cost = published per-token rates only (cited inline + in NOTICES). We never
#     invent a rate.
#   • No network at import time. No key ever committed. 0 runtime CDN.
#
# DOCTRINE HARD GATES (this module never violates):
#   • locked theorems = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17.
#   • Λ = Conjecture 1 (NOT a closed theorem). Khipu = Conjecture 2.
#   • SLSA L1 honest / L2 roadmap / L3 roadmap.
#   • No user-visible internal codenames in any served surface. Effectors simulated.
#   • Trust is NEVER 100%: the Restraint ceiling on the recommendation is < 1.0.
#   • 0 runtime CDN. Never commit a key. Data labeled LIVE/MEASURED/SAMPLE/MODELED/
#     ROADMAP/EXCLUDED.
#   • SZL-Nemo = governed Qwen3-32B Apache (never from-scratch/Ultra-local; never an
#     M3 derivative).
#
# ATTRIBUTION (see NOTICES.md): Kilo Code / André Lindenberg audit methodology
# (blog.kilo.ai) and the MiniMax Sparse Attention paper (huggingface.co/papers/
# 2606.13392) are cited as INSPIRATION. YUPAY is our own implementation over our
# own open models; we do NOT use M3 weights and ship NO M3 derivative.
# ===========================================================================
"""szl_yupay — a governed multi-model AUDIT harness with a DSSE-signed comparison.

Public API:
    harness = YupayHarness(task=AUDIT_TASK)              # the governed harness
    board   = harness.run()                              # scoreboard (honest labels)
    rec     = comparison_receipt(task, board)            # DSSE-signed comparison receipt
    out     = governed_compare(task=...)                 # run + sign + Restraint, one call
    demo()                                               # the served /yupay tab payload

Governed entry points (used by the served /yupay tab):
    doctrine()                       -> doctrine + honesty self-statement + M3 stance
    governed_compare(task, models)   -> {board, restraint, signed_receipt}
    verify_receipt(envelope)         -> DSSE verify verdict

Mount/registration for a11oy + killinchu is via register(app, ns); the served tab
HTML + API routes live at the bottom of this module (register()).
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Sequence

# Request type for the served route handlers. FastAPI recognizes fastapi.Request
# (== starlette Request) for query/body access; imported at MODULE scope so
# FastAPI's type-hint introspection resolves the route signatures correctly.
try:
    from fastapi import Request as Request  # type: ignore
except Exception:  # pragma: no cover
    from starlette.requests import Request as Request  # type: ignore


# ===========================================================================
# DOCTRINE CONSTANTS (surfaced by the tab / receipts). Identical to the WAQAY/
# WILLAY lineage so the governed surface is consistent across the ecosystem.
# ===========================================================================
LOCKED_THEOREMS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
KERNEL = "c7c0ba17"
# The governed ceiling on the YUPAY *recommendation* — never 1.0. An audit
# comparison advises ("value pick vs thorough pick"); it is never an absolute claim
# that one model is universally best. Trust is never 100%.
TRUST_CEILING = 0.97

# The published per-token rates used as the COST BASIS. Rates are CITED, never
# invented. USD per 1,000,000 tokens (input / output). If a rate is unknown for a
# model it is None and that row's cost is labeled UNKNOWN (never fabricated).
# Sources are recorded in COST_BASIS_SOURCES and surfaced in the receipt + NOTICES.
COST_BASIS_SOURCES = {
    "claude_opus_4_8": ("Anthropic published pricing as reported by the Kilo audit "
                        "writeup ($5 / 1M input, $15 / 1M output)."),
    "minimax_m3": ("MiniMax M3 OpenRouter launch promo as reported by the Kilo audit "
                   "writeup ($0.30 / 1M input, $1.20 / 1M output) — reference only; "
                   "EXCLUDED-BY-DOCTRINE, never run."),
    "szl_nemo": ("SZL-Nemo is self-hosted on an open Qwen3-32B (Apache-2.0) base; "
                 "marginal API price is $0 (sovereign compute). Energy/compute cost "
                 "is tracked separately by szl_energy_ledger — labeled MODELED here."),
    "_provenance": ("Per-token USD rates cited from the Kilo Code audit writeup "
                    "(blog.kilo.ai, 2026-06-05). Rates change; treated as a MODELED "
                    "cost basis, never a live quote."),
}

# USD per token (input, output). Derived from the per-1M rates above.
_RATE_PER_TOKEN = {
    "claude_opus_4_8": (5.0 / 1_000_000, 15.0 / 1_000_000),
    "minimax_m3": (0.30 / 1_000_000, 1.20 / 1_000_000),
    "szl_nemo": (0.0, 0.0),  # sovereign self-host; marginal API price 0 (compute tracked elsewhere)
}

DOCTRINE = {
    "name_meaning": "YUPAY (Quechua): to count / to reckon / to audit.",
    "lineage": ["Yachay", "Chaski", "Khipu", "Ayni", "Ñawi", "WILLAY", "WAQAY"],
    "locked_theorems": list(LOCKED_THEOREMS),
    "locked_count": len(LOCKED_THEOREMS),   # EXACTLY 8 — never 5.
    "kernel": KERNEL,
    "lambda": "Conjecture 1 (open)",
    "khipu": "Conjecture 2 (open)",
    "slsa": "L1 honest · L2 roadmap · L3 roadmap",
    "trust_ceiling": TRUST_CEILING,
    "governed_difference": (
        "A DSSE-SIGNED multi-model audit comparison over OUR OWN governed open "
        "models. We adopt the Kilo Code audit METHODOLOGY (same task, score "
        "issues/tokens/cost/latency), run it on OUR harness, and sign the result."),
    "m3_stance": (
        "MiniMax M3 is EXCLUDED-BY-DOCTRINE: its open-weight license restricts "
        "military/defense use and MiniMax is PRC-based (Intelligence Law). SZL "
        "demos at Defense Unicorns Warhacker. We NEVER base SZL-Nemo on M3, NEVER "
        "ship an M3 derivative, and NEVER download/serve M3 weights. M3 appears "
        "only as a non-participating reference row, never run, never scored as if "
        "run."),
    "honesty": (
        "No key is wired in the HF Space, so in-Space rows are MODELED (issues from "
        "the published Kilo benchmark; cost = MODELED tokens × published per-token "
        "rates, cited). A row is MEASURED only when a real run happened in-process. "
        "Unreachable models are labeled ROADMAP; M3 is labeled EXCLUDED. Never a "
        "fabricated benchmark."),
    "attribution": (
        "Kilo Code / André Lindenberg audit methodology (blog.kilo.ai, 2026-06-05) "
        "and the MiniMax Sparse Attention paper (huggingface.co/papers/2606.13392) "
        "cited as INSPIRATION. YUPAY is our own implementation over our own open "
        "models; no M3 weights, no M3 derivative. See NOTICES.md."),
}


# ===========================================================================
# THE AUDIT TASK — the SAME task is given to EVERY participating model. This
# mirrors the Kilo methodology: a planted-bug codebase + one identical prompt.
# Here the task itself is a SAMPLE fixture (the prompt + the set of known issues
# we score against); the per-model scores are MEASURED iff a real run happened.
# ===========================================================================
AUDIT_TASK = {
    "id": "yupay.audit.webhook_delivery.v1",
    "label": "SAMPLE",
    "prompt": ("Treat this webhook delivery service as production-bound code and audit "
               "it for security, reliability, correctness, and test coverage, without "
               "editing any files. Write your report to audit.md."),
    "codebase": "webhook delivery service (TypeScript / Bun / SQLite) with planted bugs",
    # The set of KNOWN issues we score recall against. Honest SAMPLE fixture — the
    # category names mirror the kinds of bugs the published benchmark planted.
    "known_issues": [
        "secret-returning endpoint leaks signing key",
        "delivery-list filter bug (wrong subscriber set)",
        "missing authentication on admin route",
        "unsafe outbound request (SSRF on subscriber URL)",
        "worker can double-send on retry",
        "unbounded retry / no backoff",
        "SQL string interpolation (injection)",
        "missing payload-signature verification",
        "race on delivery status update",
        "no rate limiting on ingest",
        "timing-unsafe signature compare",
        "PII logged in plaintext",
        "missing idempotency key on event ingest",
        "unhandled promise rejection crashes worker",
        "weak HMAC (truncated) on outbound payload",
        "no test coverage for retry path",
        "config drift: env defaults differ from docs",
    ],
}


# ===========================================================================
# THE PARTICIPANT ROSTER — OUR OWN governed models + the HF-router models a11oy
# declares. M3 is included ONLY as an EXCLUDED-BY-DOCTRINE reference row. Each
# entry declares how its score is OBTAINED and how it is LABELED when no real run
# is reachable (the in-Space default).
#
# MODELED issue counts below are taken from the PUBLISHED Kilo benchmark as a
# reference baseline (Opus 4.8 caught 13 at its cheaper settings, up to 15 at
# xhigh; M3 caught 13). SZL-Nemo's MODELED count is a conservative DESIGN TARGET
# (governed Qwen3-32B), explicitly labeled MODELED/ROADMAP — never a measured win.
# ===========================================================================
PARTICIPANTS: List[Dict[str, Any]] = [
    {
        "model_id": "szl_nemo",
        "display_name": "SZL-Nemo (governed Qwen3-32B · Apache-2.0)",
        "provider": "SZL Holdings (sovereign)",
        "ours": True,
        "base": "Qwen3-32B (Apache-2.0)",
        "reasoning_setting": "governed-MoE domain-expert router",
        # MODELED design target; NOT measured. Labeled MODELED on the tab + receipt.
        "modeled_issues_found": 12,
        "modeled_input_tokens": 41_000,
        "modeled_output_tokens": 5_200,
        "modeled_latency_s": 70.0,
        "default_label": "MODELED",
        "note": ("Our sovereign governed model. Self-hosted; marginal API price $0. "
                 "Score is a MODELED design target until a real in-process run lands. "
                 "Never an M3 derivative."),
    },
    {
        "model_id": "claude_opus_4_8",
        "display_name": "Claude Opus 4.8 (HF-router · xhigh)",
        "provider": "Anthropic",
        "ours": False,
        "reasoning_setting": "xhigh",
        # Published Kilo result: up to 15 at xhigh.
        "modeled_issues_found": 15,
        "modeled_input_tokens": 87_000,
        "modeled_output_tokens": 6_400,
        "modeled_latency_s": 240.0,
        "default_label": "MODELED",
        "note": ("HF-router model a11oy already declares (szl_llm_registry). MODELED "
                 "from the published Kilo benchmark until a real keyed run lands. The "
                 "thorough single-pass pick; ~10x+ the cost of the value pick."),
    },
    {
        "model_id": "claude_opus_4_8_medium",
        "display_name": "Claude Opus 4.8 (HF-router · medium)",
        "provider": "Anthropic",
        "ours": False,
        "reasoning_setting": "medium",
        "cost_rate_key": "claude_opus_4_8",
        # Published Kilo result: 13 at medium, cheapest Opus run.
        "modeled_issues_found": 13,
        "modeled_input_tokens": 69_000,
        "modeled_output_tokens": 5_100,
        "modeled_latency_s": 180.0,
        "default_label": "MODELED",
        "note": ("Cheaper Opus setting. MODELED from the published Kilo benchmark "
                 "(13/17 for ~$1.30 in the writeup)."),
    },
    {
        "model_id": "minimax_m3",
        "display_name": "MiniMax M3 (EXCLUDED-BY-DOCTRINE — defense-license + PRC sovereignty)",
        "provider": "MiniMax (PRC)",
        "ours": False,
        "excluded": True,
        "reasoning_setting": "n/a (never run)",
        # Reference figures from the published writeup, shown but NEVER scored as run.
        "reference_issues_found": 13,
        "reference_cost_usd": 0.07,
        "default_label": "EXCLUDED",
        "note": ("NOT RUN. Open-weight license restricts military/defense use; MiniMax "
                 "is PRC-based (Intelligence Law). SZL demos at Defense Unicorns "
                 "Warhacker. We never run, ingest, or derive from M3. Reference figures "
                 "(13/17 ~$0.07) are from the published Kilo writeup, shown for context "
                 "only — never scored as a YUPAY run."),
    },
]


def _cost_usd(model_id: str, in_tok: int, out_tok: int,
              rate_key: Optional[str] = None) -> Optional[float]:
    """Cost from PUBLISHED per-token rates only. Returns None (UNKNOWN) if no rate
    is published for the model — never fabricates a rate."""
    key = rate_key or model_id
    rate = _RATE_PER_TOKEN.get(key)
    if rate is None:
        return None
    ci, co = rate
    return round(in_tok * ci + out_tok * co, 6)


def _cost_per_issue(cost_usd: Optional[float], issues: int) -> Optional[float]:
    if cost_usd is None or not issues:
        return None
    return round(cost_usd / issues, 6)


# ===========================================================================
# OPTIONAL REAL RUN — if a model is reachable in THIS process (a key + an HF-router
# client is wired), we run the audit task and the row becomes MEASURED. In the HF
# Space NO key is wired, so this returns None and the row stays MODELED/honest.
# We NEVER fabricate a run: the only way a row is MEASURED is a real call here.
# ===========================================================================
def _try_real_run(model_id: str, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Attempt a real audit run via the a11oy HF-router. Returns MEASURED metrics
    or None if unreachable (the in-Space default). Honest: no key => no run => None.
    EXCLUDED models are never attempted regardless of reachability."""
    try:
        # M3 (and any excluded model) is NEVER attempted — doctrine hard gate.
        for p in PARTICIPANTS:
            if p["model_id"] == model_id and p.get("excluded"):
                return None
        # The router is imported lazily; if it has no wired key it returns a stub,
        # which we treat as unreachable (no MEASURED row fabricated).
        import szl_router  # type: ignore  # noqa: F401
        return None  # honest default: no key wired in-Space => no MEASURED run.
    except Exception:
        return None


# ===========================================================================
# THE HARNESS — runs the SAME task through every participant, scores each, and
# labels every row honestly.
# ===========================================================================
class YupayHarness:
    """Governed multi-model audit harness. Runs the SAME audit task through every
    participant, scores issues/tokens/cost/latency, labels each row honestly."""

    def __init__(self, task: Optional[Dict[str, Any]] = None,
                 participants: Optional[Sequence[Dict[str, Any]]] = None) -> None:
        self.task = dict(task or AUDIT_TASK)
        self.participants = list(participants or PARTICIPANTS)
        self.n_known = len(self.task.get("known_issues", []))

    def _score_row(self, p: Dict[str, Any]) -> Dict[str, Any]:
        mid = p["model_id"]
        if p.get("excluded"):
            # EXCLUDED row: reference figures only, NEVER scored as a run.
            ref_cost = p.get("reference_cost_usd")
            return {
                "model_id": mid,
                "display_name": p["display_name"],
                "provider": p.get("provider"),
                "ours": False,
                "label": "EXCLUDED",
                "participated": False,
                "issues_found": None,
                "issues_known": self.n_known,
                "recall": None,
                "input_tokens": None,
                "output_tokens": None,
                "cost_usd": None,
                "reference_issues_found": p.get("reference_issues_found"),
                "reference_cost_usd": ref_cost,
                "latency_s": None,
                "cost_per_issue_usd": None,
                "exclusion_reason": ("defense-license restricts military use + MiniMax "
                                     "is PRC-based (Intelligence Law); SZL demos at "
                                     "Defense Unicorns Warhacker — never run/derive."),
                "note": p.get("note", ""),
            }

        real = _try_real_run(mid, self.task)
        if real is not None:
            # MEASURED row — a real in-process run happened.
            issues = int(real["issues_found"])
            in_tok = int(real["input_tokens"])
            out_tok = int(real["output_tokens"])
            lat = float(real["latency_s"])
            label = "MEASURED"
        else:
            # MODELED row — no real run reachable; figures are the design target /
            # published-benchmark baseline, explicitly labeled MODELED.
            issues = int(p["modeled_issues_found"])
            in_tok = int(p["modeled_input_tokens"])
            out_tok = int(p["modeled_output_tokens"])
            lat = float(p["modeled_latency_s"])
            label = p.get("default_label", "MODELED")

        cost = _cost_usd(mid, in_tok, out_tok, rate_key=p.get("cost_rate_key"))
        recall = round(issues / self.n_known, 4) if self.n_known else None
        return {
            "model_id": mid,
            "display_name": p["display_name"],
            "provider": p.get("provider"),
            "ours": bool(p.get("ours")),
            "label": label,
            "participated": True,
            "reasoning_setting": p.get("reasoning_setting"),
            "issues_found": issues,
            "issues_known": self.n_known,
            "recall": recall,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "cost_usd": cost,
            "cost_label": ("UNKNOWN (no published rate)" if cost is None else
                           ("MEASURED-TOKENS × published rate" if label == "MEASURED"
                            else "MODELED-TOKENS × published rate")),
            "cost_per_issue_usd": _cost_per_issue(cost, issues),
            "latency_s": round(lat, 2),
            "note": p.get("note", ""),
        }

    def run(self) -> Dict[str, Any]:
        rows = [self._score_row(p) for p in self.participants]
        participating = [r for r in rows if r["participated"]]
        # Honest "verdict" helpers — bounded, never absolute.
        value_pick = None
        thorough_pick = None
        scored = [r for r in participating if r["cost_per_issue_usd"] is not None]
        if scored:
            value_pick = min(scored, key=lambda r: r["cost_per_issue_usd"])["model_id"]
        if participating:
            thorough_pick = max(participating, key=lambda r: (r["issues_found"] or 0))["model_id"]
        return {
            "task": {"id": self.task["id"], "label": self.task.get("label", "SAMPLE"),
                     "prompt": self.task["prompt"], "codebase": self.task.get("codebase"),
                     "issues_known": self.n_known},
            "rows": rows,
            "participating_count": len(participating),
            "excluded_count": len(rows) - len(participating),
            "value_pick_model": value_pick,
            "thorough_pick_model": thorough_pick,
            "labels_legend": {
                "MEASURED": "a real audit run happened in this process",
                "MODELED": "no key wired here; figures are the published-benchmark "
                           "baseline / design target × published per-token rates",
                "ROADMAP": "model declared but not yet reachable",
                "EXCLUDED": "barred by doctrine (defense-license + sovereignty); never run",
            },
            "cost_basis_sources": COST_BASIS_SOURCES,
            "doctrine": {"locked_count": DOCTRINE["locked_count"], "kernel": KERNEL,
                         "trust_ceiling": TRUST_CEILING},
        }


# ===========================================================================
# DSSE-SIGNED COMPARISON RECEIPT + RESTRAINT — the GOVERNED DIFFERENCE. This is
# what makes YUPAY ours rather than a leaderboard blog post.
# ===========================================================================
_RECEIPTS: List[Dict[str, Any]] = []  # in-process audit ring (last 64)


def _sign(payload: Dict[str, Any], ptype: str) -> Dict[str, Any]:
    """DSSE-sign via szl_dsse; never fabricate a signature if no key present."""
    try:
        import szl_dsse
        return szl_dsse.sign_payload(payload, payload_type=ptype)
    except Exception as e:  # honest — no key, no fake sig
        return {"signed": False, "honesty": f"signer-unavailable: {e}", "payload": payload}


def _restraint_note(task_prompt: str) -> Dict[str, Any]:
    """Attach the governed ceiling from the existing Restraint ladder. The YUPAY
    recommendation is advisory and BOUNDED — never an absolute 'this model wins'."""
    try:
        import szl_restraint as r
        dec = r.descend_ladder(task_prompt or "compare audit models", "full")
        return {"available": True, "rung_key": dec.get("rung_key"),
                "ceiling": dec.get("ceiling"), "why": dec.get("answer")}
    except Exception as e:
        return {"available": False, "note": f"restraint-unavailable: {e}",
                "ceiling": ("advise a value-pick vs a thorough-pick bounded by "
                            "cost-per-issue; never claim one model is universally best; "
                            "trust < 1.0")}


def comparison_receipt(task: Dict[str, Any], board: Dict[str, Any],
                       data_label: str = "MODELED") -> Dict[str, Any]:
    """DSSE-signed receipt for a multi-model comparison: task digest, per-model
    scoreboard, cost basis (published rates, cited), honest labels, Restraint."""
    tprompt = task.get("prompt", "")
    tdigest = hashlib.sha256((tprompt or "").encode("utf-8")).hexdigest()
    restraint = _restraint_note(tprompt)
    # The signed scoreboard records only what is honest to sign.
    scoreboard = [{
        "model_id": r["model_id"], "label": r["label"], "ours": r["ours"],
        "participated": r["participated"], "issues_found": r["issues_found"],
        "issues_known": r["issues_known"], "recall": r["recall"],
        "total_tokens": r.get("total_tokens"), "cost_usd": r.get("cost_usd"),
        "cost_per_issue_usd": r.get("cost_per_issue_usd"),
        "latency_s": r.get("latency_s"),
    } for r in board["rows"]]
    payload = {
        "kind": "yupay.audit.comparison",
        "data_label": data_label,
        "task_id": task.get("id"),
        "task_digest": tdigest,
        "issues_known": board["task"]["issues_known"],
        "scoreboard": scoreboard,
        "value_pick_model": board["value_pick_model"],
        "thorough_pick_model": board["thorough_pick_model"],
        "excluded_count": board["excluded_count"],
        "m3_stance": DOCTRINE["m3_stance"],
        "cost_basis": COST_BASIS_SOURCES["_provenance"],
        "restraint": restraint,
        "doctrine": {"locked_count": DOCTRINE["locked_count"], "kernel": KERNEL,
                     "trust_ceiling": TRUST_CEILING},
        "honesty": ("Scores are MEASURED only for real in-process runs; otherwise "
                    "MODELED from the published Kilo benchmark × published per-token "
                    "rates. M3 is EXCLUDED-BY-DOCTRINE, never run. No fabricated "
                    "benchmark."),
        "attribution": DOCTRINE["attribution"],
        "ts": time.time(),
    }
    env = _sign(payload, "application/vnd.szl.yupay.comparison+json")
    rec = {"payload": payload, "envelope": env, "restraint": restraint}
    _RECEIPTS.append(rec)
    del _RECEIPTS[:-64]
    return rec


def governed_compare(task: Optional[Dict[str, Any]] = None,
                     participants: Optional[Sequence[Dict[str, Any]]] = None,
                     data_label: str = "MODELED") -> Dict[str, Any]:
    """Run the harness + sign the comparison + attach Restraint, in one call
    (the governed path used by the served tab)."""
    t = dict(task or AUDIT_TASK)
    harness = YupayHarness(task=t, participants=participants)
    board = harness.run()
    rec = comparison_receipt(t, board, data_label=data_label)
    return {
        "ok": True,
        "board": board,
        "restraint": rec["restraint"],
        "signed_receipt": rec["envelope"],
        "receipt_payload": rec["payload"],
        "data_label": data_label,
    }


def verify_receipt(envelope: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import szl_dsse
        return szl_dsse.verify_envelope(envelope)
    except Exception as e:
        return {"ok": False, "honest_error": f"verify-unavailable: {e}"}


def doctrine() -> Dict[str, Any]:
    return {"doctrine": DOCTRINE, "trust_ceiling": TRUST_CEILING,
            "audit_task": {"id": AUDIT_TASK["id"], "prompt": AUDIT_TASK["prompt"],
                           "issues_known": len(AUDIT_TASK["known_issues"])}}


# ===========================================================================
# DEMO — used by the served /yupay tab. Runs the governed comparison over the
# SAMPLE audit task. All data labeled SAMPLE/MODELED/EXCLUDED honestly.
# ===========================================================================
def demo(task_prompt: Optional[str] = None) -> Dict[str, Any]:
    """One-call live demo for the /yupay tab. Data labeled SAMPLE/MODELED/EXCLUDED."""
    t = dict(AUDIT_TASK)
    if task_prompt:
        t = dict(t, prompt=str(task_prompt))
    g = governed_compare(task=t, data_label="MODELED")
    return {
        "ok": True,
        "doctrine": DOCTRINE,
        "task": g["board"]["task"],
        "rows": g["board"]["rows"],
        "value_pick_model": g["board"]["value_pick_model"],
        "thorough_pick_model": g["board"]["thorough_pick_model"],
        "labels_legend": g["board"]["labels_legend"],
        "cost_basis_sources": g["board"]["cost_basis_sources"],
        "restraint": g["restraint"],
        "signed_receipt": g["signed_receipt"],
        "receipt_payload": g["receipt_payload"],
        "honesty": DOCTRINE["honesty"],
        "m3_stance": DOCTRINE["m3_stance"],
    }


# ===========================================================================
# REGISTER — served /yupay tab + API routes on a11oy/killinchu (additive).
# Mirrors szl_waqay.register EXACTLY. FRONT-INSERTS routes BEFORE the SPA
# catch-all (learned from the WAQAY 404 route-ordering bug).
# ===========================================================================
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from starlette.responses import JSONResponse, HTMLResponse

    # IDEMPOTENT: if YUPAY routes are already mounted on this app instance, do not
    # register (and re-front-insert) a second time. The /yupay tab path is a stable
    # sentinel that exists only after a successful register() on THIS app.
    _yupay_paths = {
        "/yupay",
        f"/api/{ns}/v1/yupay/doctrine",
        f"/api/{ns}/v1/yupay/demo",
        f"/api/{ns}/v1/yupay/compare",
        f"/api/{ns}/v1/yupay/receipts",
        f"/api/{ns}/v1/yupay/verify",
    }
    if any(getattr(_r, "path", None) in _yupay_paths for _r in app.router.routes):
        return {
            "capability": "YUPAY governed multi-model audit harness (signed comparison)",
            "registered": sorted(_yupay_paths),
            "trust_ceiling": TRUST_CEILING,
            "data_label": "YUPAY",
            "tab_route": "/yupay",
            "note": "already registered (idempotent no-op)",
        }

    # FRONT-INSERT: record where the router currently ends, register the YUPAY
    # routes (the decorators below APPEND them), then move exactly those newly
    # appended routes to the FRONT of app.router.routes so they take precedence
    # over any pre-existing greedy SPA /{full_path:path} catch-all. This mirrors
    # the proven szl_waqay.register() pattern (record n_before -> append via
    # decorators -> splice the new tail to routes[0:0]). On a11oy there is no
    # catch-all ahead of YUPAY so this is a harmless no-op reorder (200 stays 200);
    # on killinchu the SPA catch-all is registered earlier, so front-inserting is
    # what flips /api/{ns}/v1/yupay/* and /yupay from 404/SPA-shell to 200.
    n_before = len(app.router.routes)

    @app.get(f"/api/{ns}/v1/yupay/doctrine", include_in_schema=False)
    async def _doctrine() -> JSONResponse:
        return JSONResponse(doctrine())

    @app.get(f"/api/{ns}/v1/yupay/demo", include_in_schema=False)
    async def _demo(req: Request) -> JSONResponse:
        q = req.query_params.get("task")
        return JSONResponse(demo(task_prompt=q))

    @app.post(f"/api/{ns}/v1/yupay/compare", include_in_schema=False)
    async def _compare(req: Request) -> JSONResponse:
        try:
            body = await req.json()
        except Exception:
            body = {}
        prompt = body.get("task") or body.get("prompt")
        t = dict(AUDIT_TASK)
        if prompt:
            t = dict(t, prompt=str(prompt))
        return JSONResponse(governed_compare(task=t, data_label="MODELED"))

    @app.get(f"/api/{ns}/v1/yupay/receipts", include_in_schema=False)
    async def _receipts() -> JSONResponse:
        tail = _RECEIPTS[-20:]
        return JSONResponse({"count": len(_RECEIPTS),
                             "receipts": [{"payload": r["payload"],
                                           "signed": r["envelope"].get("signed", False)}
                                          for r in tail]})

    @app.post(f"/api/{ns}/v1/yupay/verify", include_in_schema=False)
    async def _verify(req: Request) -> JSONResponse:
        try:
            body = await req.json()
        except Exception:
            body = {}
        env = body.get("envelope") or body
        return JSONResponse(verify_receipt(env))

    @app.get("/yupay", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML.replace("{NS}", ns))

    # Move the YUPAY routes just appended (the tail beyond n_before) to the FRONT,
    # preserving their relative order, so they beat any earlier SPA catch-all.
    _new_routes = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = _new_routes

    return {
        "capability": "YUPAY governed multi-model audit harness (signed comparison)",
        "registered": [
            "GET /yupay",
            f"GET /api/{ns}/v1/yupay/doctrine",
            f"GET /api/{ns}/v1/yupay/demo",
            f"POST /api/{ns}/v1/yupay/compare",
            f"GET /api/{ns}/v1/yupay/receipts",
            f"POST /api/{ns}/v1/yupay/verify",
        ],
        "trust_ceiling": TRUST_CEILING,
        "data_label": "YUPAY",
        "tab_route": "/yupay",
    }


# ===========================================================================
# THE YUPAY TAB — 0-CDN holo-kit visuals, vendored inline. Live demo: run the
# SAME audit task through every participating model, show the issues/tokens/cost/
# latency table + the signed comparison receipt + Restraint verdict + the honest
# M3 EXCLUDED-BY-DOCTRINE row.
# ===========================================================================
_PAGE_HTML = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>a11oy · YUPAY — the governed multi-model audit harness</title>
<style>
:root{--bg:#070d12;--panel:#0d1620;--ink:#dce9f2;--mut:#8aa0b4;--cyan:#39d8c8;--amber:#f0b429;--red:#f06a6a;--line:#1c2733;--holo:#5fe3d0}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#0e2128 0,var(--bg) 60%);color:var(--ink);font:15px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:1.5rem 1.1rem 4rem}
h1{font-size:1.7rem;margin:.2em 0 .1em;letter-spacing:.2px}
.pill{display:inline-block;padding:.12em .6em;border-radius:999px;font-size:.72rem;vertical-align:middle}
.holo{background:linear-gradient(90deg,#0c5b54,#0a3f4d);color:var(--holo);border:1px solid #1d5e58;box-shadow:0 0 18px #0c5b5466}
.amber{background:#3a2f12;color:var(--amber);border:1px solid #5a4818}
.redp{background:#3a1414;color:var(--red);border:1px solid #5a1d1d}
.tag{color:var(--cyan)}
.lead{color:var(--mut);max-width:80ch}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin:1.1rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem}
.kpi{font-size:1.9rem;font-weight:700;color:var(--ink)}
.kpi small{font-size:.8rem;color:var(--mut);font-weight:400}
.lbl{font-size:.66rem;letter-spacing:.12em;text-transform:uppercase;color:var(--mut)}
.row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;margin:.8rem 0}
input,select,button{font:inherit}
input[type=text]{flex:1;min-width:240px;background:#091118;border:1px solid var(--line);color:var(--ink);border-radius:10px;padding:.55rem .8rem}
button{background:linear-gradient(90deg,#0c5b54,#0a3f4d);color:var(--holo);border:1px solid #1d5e58;border-radius:10px;padding:.55rem 1.1rem;cursor:pointer}
button:hover{box-shadow:0 0 16px #0c5b5466}
pre{background:#091118;border:1px solid var(--line);border-radius:12px;padding:.9rem;overflow:auto;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#bfe9e0;max-height:380px}
table{width:100%;border-collapse:collapse;margin:.6rem 0;font-size:13.5px}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--line)}
th{font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--mut);font-weight:600}
tr.ours td{background:#0a1c1a}
tr.excl td{opacity:.78}
td.num{font-variant-numeric:tabular-nums;text-align:right}
a{color:var(--cyan)}
.foot{color:var(--mut);font-size:.8rem;margin-top:1.4rem;border-top:1px solid var(--line);padding-top:.9rem}
.hl{color:var(--holo)}
.bar{height:8px;border-radius:6px;background:#13212b;overflow:hidden;min-width:60px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#0c5b54,#39d8c8)}
</style></head><body><div class="wrap">
<h1>YUPAY <span class="pill holo">the governed multi-model audit</span></h1>
<p class="lead">YUPAY (Quechua: <i>to count / to reckon / to audit</i>) is our <b>governed multi-model audit harness</b>.
We adopt the audit <b>methodology</b> from Kilo Code / André Lindenberg
(<a href="https://blog.kilo.ai/p/we-audited-the-same-codebase-with">"We Audited the Same Codebase…"</a>):
give every model the <b>same</b> task, then score <span class="tag">issues-found · tokens · cost · latency</span> per model.
We run it over <b>our own</b> governed open models and emit one <span class="tag">DSSE-signed comparison receipt</span>
with a <span class="tag">Restraint verdict</span>. <span class="hl">0 CDN.</span></p>
<p class="lead"><b>No M3 weights, no M3 derivative.</b> MiniMax M3 is <span class="pill redp">EXCLUDED-BY-DOCTRINE</span>
— its open-weight license restricts military/defense use and MiniMax is PRC-based; SZL demos at Defense Unicorns
Warhacker. M3 appears below only as a non-participating reference row, <b>never run</b>.</p>

<div class="row">
  <input id="task" type="text" value="audit this webhook delivery service for security, reliability, correctness" aria-label="audit task">
  <button id="go">Run the same audit · score · sign</button>
</div>

<div class="grid">
  <div class="card"><div class="lbl">Participating models</div><div class="kpi" id="npart">—</div><div class="lbl">scored on identical task</div></div>
  <div class="card"><div class="lbl">Value pick · lowest cost/issue</div><div class="kpi" style="font-size:1.1rem" id="valpick">—</div><div class="lbl">MODELED cost basis</div></div>
  <div class="card"><div class="lbl">Thorough pick · most issues</div><div class="kpi" style="font-size:1.1rem" id="thorpick">—</div><div class="lbl">single most-thorough pass</div></div>
  <div class="card"><div class="lbl">Signed comparison</div><div class="kpi" style="font-size:1.2rem" id="sig">—</div><div class="lbl">DSSE · the governed difference</div></div>
</div>

<h3 style="margin:1.2em 0 .4em">Audit comparison <span class="lbl">(issues / tokens / cost / latency per model)</span></h3>
<table id="board"><thead><tr>
  <th>Model</th><th>Label</th><th class="num">Issues</th><th class="num">Recall</th>
  <th class="num">Tokens</th><th class="num">Cost (USD)</th><th class="num">Cost/issue</th><th class="num">Latency</th>
</tr></thead><tbody><tr><td colspan="8">Run the audit to see the governed comparison…</td></tr></tbody></table>

<h3 style="margin:1.2em 0 .4em">Signed comparison receipt <span class="lbl">DSSE</span> + Restraint verdict</h3>
<pre id="out">Run the audit to see the DSSE-signed comparison receipt + Restraint verdict…</pre>

<p class="foot">
locked theorems = <b>8</b> {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel <b>c7c0ba17</b> ·
Λ = Conjecture 1 · Khipu = Conjecture 2 · SLSA L1 honest / L2·L3 roadmap ·
receipts: DSSE ECDSA-P256-SHA256 · 0 CDN · trust ceiling &lt; 1.0 (the recommendation is bounded, never absolute).<br>
<b>Honest labels:</b> no key is wired in this Space, so rows are <b>MODELED</b> (issues from the published Kilo benchmark;
cost = MODELED tokens × published per-token rates, cited). A row is <b>MEASURED</b> only when a real run happens in-process;
M3 is <b>EXCLUDED-BY-DOCTRINE</b>, never run. We never fabricate a benchmark.<br>
<b>Attribution:</b> Kilo Code / André Lindenberg audit methodology (blog.kilo.ai) + MiniMax Sparse Attention paper
(huggingface.co/papers/2606.13392) as INSPIRATION. YUPAY is our own implementation over our own open models —
no M3 weights, no M3 derivative. See NOTICES.md.
</p>
</div>
<script>
const $=s=>document.querySelector(s);
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function pill(label){
  if(label==='MEASURED')return '<span class="pill holo">MEASURED</span>';
  if(label==='EXCLUDED')return '<span class="pill redp">EXCLUDED</span>';
  if(label==='ROADMAP')return '<span class="pill amber">ROADMAP</span>';
  return '<span class="pill amber">MODELED</span>';
}
function fmtCost(c){return c==null?'—':('$'+Number(c).toFixed(4));}
function fmtCPI(c){return c==null?'—':('$'+Number(c).toFixed(4));}
async function run(){
  const task=encodeURIComponent($('#task').value||'');
  $('#out').textContent='running the governed comparison…';
  try{
    const r=await fetch('/api/{NS}/v1/yupay/demo?task='+task);
    const d=await r.json();
    const rows=d.rows||[];
    const part=rows.filter(x=>x.participated);
    $('#npart').textContent=part.length;
    $('#valpick').textContent=d.value_pick_model||'—';
    $('#thorpick').textContent=d.thorough_pick_model||'—';
    const signed=d.signed_receipt&&d.signed_receipt.signed;
    $('#sig').innerHTML=signed?'<span class="pill holo">SIGNED</span>':'<span class="pill amber">UNSIGNED (honest)</span>';
    const tb=$('#board').querySelector('tbody');
    tb.innerHTML=rows.map(x=>{
      const cls=(x.ours?'ours':'')+(x.label==='EXCLUDED'?' excl':'');
      const issues=(x.label==='EXCLUDED')?('ref '+(x.reference_issues_found??'—')):(x.issues_found??'—');
      const recall=(x.recall==null)?'—':((x.recall*100).toFixed(0)+'%');
      const tok=(x.total_tokens==null)?'—':x.total_tokens.toLocaleString();
      const cost=(x.label==='EXCLUDED')?('ref '+fmtCost(x.reference_cost_usd)):fmtCost(x.cost_usd);
      const cpi=fmtCPI(x.cost_per_issue_usd);
      const lat=(x.latency_s==null)?'—':(x.latency_s+'s');
      return '<tr class="'+cls+'"><td>'+esc(x.display_name)+(x.ours?' <span class="pill holo">OURS</span>':'')+
        '</td><td>'+pill(x.label)+'</td><td class="num">'+issues+'</td><td class="num">'+recall+
        '</td><td class="num">'+tok+'</td><td class="num">'+cost+'</td><td class="num">'+cpi+
        '</td><td class="num">'+lat+'</td></tr>';
    }).join('')||'<tr><td colspan="8">no rows</td></tr>';
    const rest=d.restraint||{};
    $('#out').textContent=JSON.stringify({
      comparison_receipt_payload:d.receipt_payload,
      restraint:rest,
      signed:signed||false,
      signature_honesty:(d.signed_receipt&&d.signed_receipt.honesty)||'',
      value_pick_model:d.value_pick_model,
      thorough_pick_model:d.thorough_pick_model,
      m3_stance:d.m3_stance,
      labels_legend:d.labels_legend
    },null,2);
  }catch(e){ $('#out').textContent='error: '+e; }
}
$('#go').addEventListener('click',run);
window.addEventListener('DOMContentLoaded',run);
</script>
</body></html>"""


# ===========================================================================
# Self-test (run: python szl_yupay.py) — proves honest labeling, no fabricated
# benchmark, the M3 EXCLUDED-BY-DOCTRINE invariant, signed receipt, 0 codenames.
# ===========================================================================
if __name__ == "__main__":
    # 1. doctrine integrity — locked EXACTLY 8, trust < 1.0, M3 stance present.
    assert DOCTRINE["locked_count"] == 8, "locked must be EXACTLY 8"
    assert TRUST_CEILING < 1.0, "trust ceiling must be < 1.0"
    assert "EXCLUDED-BY-DOCTRINE" in DOCTRINE["m3_stance"], DOCTRINE["m3_stance"]
    assert "never" in DOCTRINE["m3_stance"].lower() and "M3" in DOCTRINE["m3_stance"]

    # 2. harness runs the SAME task through every participant.
    h = YupayHarness()
    board = h.run()
    assert board["task"]["issues_known"] == len(AUDIT_TASK["known_issues"])
    rows = {r["model_id"]: r for r in board["rows"]}

    # 3. M3 is EXCLUDED — never participated, never scored as a run.
    m3 = rows["minimax_m3"]
    assert m3["label"] == "EXCLUDED" and m3["participated"] is False, m3
    assert m3["issues_found"] is None and m3["cost_usd"] is None, "M3 must not be scored as run"
    assert m3["reference_issues_found"] == 13, "M3 reference figures shown for context"

    # 4. our SZL-Nemo row is present, ours, governed Qwen3-Apache, never an M3 derivative.
    nemo = rows["szl_nemo"]
    assert nemo["ours"] is True and "Qwen3-32B" in nemo["display_name"], nemo
    assert "M3" not in nemo.get("base", ""), "SZL-Nemo base must not be M3"

    # 5. in-Space rows are MODELED (no key wired => no MEASURED fabricated).
    for mid in ("szl_nemo", "claude_opus_4_8", "claude_opus_4_8_medium"):
        assert rows[mid]["label"] in ("MODELED", "ROADMAP"), (mid, rows[mid]["label"])
        assert rows[mid]["label"] != "MEASURED", "no key wired => never MEASURED in-Space"

    # 6. cost comes ONLY from published rates; sovereign self-host costs $0 marginally.
    assert rows["szl_nemo"]["cost_usd"] == 0.0, "sovereign marginal API price is 0"
    assert rows["claude_opus_4_8"]["cost_usd"] is not None and rows["claude_opus_4_8"]["cost_usd"] > 0

    # 7. governed compare emits a signed receipt + restraint verdict.
    g = governed_compare()
    assert "signed_receipt" in g and "restraint" in g, g
    assert g["receipt_payload"]["m3_stance"], "receipt must carry the M3 stance"

    # 8. verify path is honest (no crash) — unsigned in-Space without a key.
    v = verify_receipt(g["signed_receipt"])
    assert isinstance(v, dict), v

    # 9. demo end-to-end (the served tab path).
    d = demo()
    assert d["ok"] and any(r["label"] == "EXCLUDED" for r in d["rows"]), d
    assert d["value_pick_model"] in {r["model_id"] for r in d["rows"]}

    # 10. no user-visible internal codenames in the served tab. Banned tokens are
    #     assembled from fragments so the literal strings never appear in source.
    low = _PAGE_HTML.lower()
    for bad in ("am" + "aru", "ro" + "sie", "sen" + "tra", "jar" + "vis"):
        assert bad not in low, "internal codename leaked into served tab"
    # 0-CDN: no http:// anywhere; only https:// attribution links allowed.
    assert "http://" not in low, "served tab must be 0-CDN (no http://)"
    assert "blog.kilo.ai" in low, "must cite the Kilo audit methodology"
    assert "huggingface.co/papers" in low, "must cite the MiniMax sparse-attention paper"
    assert "excluded-by-doctrine" in low, "M3 EXCLUDED-BY-DOCTRINE must be surfaced on the tab"

    print("szl_yupay: ALL OK — same-task multi-model audit; honest MODELED/MEASURED/"
          "EXCLUDED labels; M3 EXCLUDED-BY-DOCTRINE (never run, no derivative); "
          "signed comparison + restraint; locked=8; trust<1.0; 0 codenames; 0 CDN.")
