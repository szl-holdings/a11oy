#!/usr/bin/env python3
"""Generate tabs.json — the Tab Contract Matrix for the a11oy console.

This is the single source of truth that proves "every tab is real". It maps every
console tab -> route -> backing endpoints -> response schema -> freshness SLA ->
citations-required -> degraded rules. The harness (Playwright sweeper, API probe
runner, link-check, stress suite) all consume this file.

Design:
- The TAB list is extracted from the live console source (pages/console.html) so it
  can never silently drift away from what actually ships.
- The ENDPOINT contract registry (schemas, freshness SLAs, citation + degraded
  rules) is curated here and grounded in the real /api/a11oy/v1/* surface. This is
  the part a human reviews; it encodes the doctrine-v11 honesty contract.
- Tabs are attached to endpoints by an explicit per-tab map (preferred) falling back
  to a family-prefix heuristic, so a new tab is never left un-contracted.

Run:  python3 tools/readiness-harness/gen_tabs_matrix.py
      python3 tools/readiness-harness/gen_tabs_matrix.py --check   # CI: fail on drift
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CONSOLE = os.path.join(REPO, "pages", "console.html")
OUT = os.path.join(HERE, "tabs.json")

ORGAN = "a11oy"
CONSOLE_ROUTE = "/console"

# ── Endpoint contract registry ─────────────────────────────────────────────
# freshnessSLA: max acceptable age (seconds) of the data the endpoint returns;
#   null  -> static/derived, no freshness obligation.
# citationsRequired: the response MUST carry at least one citation/source when it
#   claims live external data (doctrine v11: "no mock theater").
# degraded: which honest states the harness tolerates without failing the build.
#   allowStatuses are the only HTTP codes that count as "up"; anything else
#   (4xx/5xx) is an undeclared breakage and fails. allowLabels are the honest
#   data_kind/status labels a tab may carry (live, cached, degraded, sample…).
# liesIf: response shapes that count as a "lie" (stale/mock/uncited) -> fail.
def ep(method="GET", schema=None, sla=None, citations=False,
       allow_statuses=(200,), allow_labels=("live", "cached"),
       lies_if=("mock", "fabricated", "placeholder"), note=""):
    return {
        "method": method,
        "schema": schema,
        "freshnessSLA": sla,
        "citationsRequired": citations,
        "degradedRules": {
            "allowStatuses": list(allow_statuses),
            "allowLabels": list(allow_labels),
            "liesIf": list(lies_if),
        },
        "note": note,
    }


DAY = 86400
HOUR = 3600
MIN = 60

ENDPOINTS = {
    # ── Core honesty / governance spine ──
    "/api/a11oy/v1/lambda": ep(schema="lambda", sla=None,
        note="Λ governance score — derived/deterministic, Conjecture-1 honest."),
    "/api/a11oy/v1/gates": ep(schema="gates", sla=None),
    "/api/a11oy/v1/formulas/selftest": ep(schema="selftest", sla=None,
        note="Kernel-gated proven-formula self-test."),
    "/api/a11oy/v1/mcp/tools": ep(schema="mcp_tools", sla=None,
        note="Returns the 4 real flagship tools; never the fabricated 12."),
    "/api/a11oy/v1/llm/registry": ep(schema="llm_registry", sla=None),
    "/api/a11oy/v1/reason/tiers": ep(schema="generic_obj", sla=None),
    "/api/a11oy/v1/reason/readiness": ep(schema="generic_obj", sla=None),

    # ── Governed decision endpoints (POST; empty body legitimately 400/422) ──
    "/api/a11oy/v1/policy/decide": ep(method="POST", schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422), note="Governed decision; empty body validates."),
    "/api/a11oy/v1/operator/ask": ep(method="POST", schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422), note="Operator ask; empty body validates."),

    # ── Provenance / receipts ──
    # NOTE: the console calls /api/a11oy/provenance (NO /v1/). /v1/provenance is 404.
    "/api/a11oy/provenance": ep(schema="provenance", sla=DAY, citations=True,
        note="Combined provenance board (note: /provenance, NOT /v1/provenance)."),
    "/api/a11oy/v1/ledger": ep(schema="ledger", sla=DAY),
    "/api/a11oy/v1/receipt/export": ep(schema="generic_obj", sla=None),
    "/api/a11oy/cosign.pub": ep(schema="text", sla=None,
        note="Public signing key for offline receipt verification."),

    # ── Eval arena ──
    "/api/a11oy/v1/eval-arena/history": ep(schema="arena_history", sla=DAY),

    # ── Observability ──
    "/api/a11oy/v1/observability/summary": ep(schema="generic_obj", sla=HOUR),
    "/api/a11oy/v1/observability/business": ep(schema="generic_obj", sla=HOUR),

    # ── Mesh / capabilities ──
    "/api/a11oy/v1/mesh/state": ep(schema="mesh", sla=5 * MIN),
    "/api/a11oy/v1/capabilities/mesh": ep(schema="mesh", sla=5 * MIN),

    # ── Operator (rosie) ──
    "/api/a11oy/v1/operator/ledger": ep(schema="generic_obj", sla=HOUR),
    "/api/a11oy/v1/operator/recommend": ep(method="POST", schema="generic_obj", sla=None),
    "/api/a11oy/v2/operator/command-log": ep(schema="generic_obj", sla=None,
        note="Append-only command log; quiet != stale, so no freshness SLA."),

    # ── Policy (sentra) ──
    "/api/a11oy/v1/policy/compliance": ep(schema="generic_obj", sla=HOUR),
    "/api/a11oy/v1/policy/gates": ep(schema="generic_obj", sla=None),
    "/api/a11oy/v1/policy/threats": ep(schema="generic_obj", sla=None, citations=True,
        note="Curated, citation-gated policy threat catalog (not a live feed); judged on citations, not freshness."),
    "/api/a11oy/v1/policy/decisions/feed": ep(schema="generic_obj", sla=HOUR),

    # ── Security feeds (live external OSINT) ──
    "/api/a11oy/v1/sec/cve": ep(schema="generic_list", sla=DAY, citations=True,
        note="Live CVE feed (NVD)."),
    "/api/a11oy/v1/sec/kev": ep(schema="generic_list", sla=DAY, citations=True,
        note="Live CISA KEV catalog."),
    "/api/a11oy/v1/sec/attack": ep(schema="generic_obj", sla=DAY, citations=True),
    "/api/a11oy/v1/sec/threats": ep(schema="generic_obj", sla=HOUR, citations=True),
    "/api/a11oy/v1/sec/threatgraph": ep(schema="generic_obj", sla=HOUR, citations=True),

    # ── Vertical packs / deva (finance, live external) ──
    "/api/a11oy/v1/vertical-packs": ep(schema="generic_obj", sla=None),
    "/api/a11oy/v1/vert/finance/feed": ep(schema="generic_obj", sla=HOUR, citations=True,
        note="Live Yahoo/macro finance feed; cold-burst 404 tolerated, re-probe."),
    "/api/a11oy/v1/deva/healthz": ep(schema="deva_health", sla=5 * MIN,
        note="deva feed health — lists the live tabs[]; warm before judging deep tabs."),

    # ── devb (legal + enterprise, live external) ──
    "/api/a11oy/v1/devb/healthz": ep(schema="generic_obj", sla=5 * MIN),

    # ── seismic ──
    "/api/a11oy/v1/seismic/forecast": ep(schema="generic_obj", sla=HOUR, citations=True),

    # ── warhacker ──
    "/api/a11oy/v1/warhacker/index": ep(schema="generic_obj", sla=None),

    # ── New live tabs (2026-06-10 agent/Chaski/router build) ──
    # feedpulse: real-time server-side liveness probe of every upstream evidence
    #   feed (kev/osv/rekor/iss/celestrak/prometheus/fhir). Each item carries a
    #   source + source_url, so citations are required; data must be fresh.
    "/api/a11oy/v1/feeds/pulse": ep(schema="feeds_pulse", sla=5 * MIN, citations=True,
        note="Live data-feed liveness/provenance heartbeat; each item cites source_url."),
    # kevgate: live CISA KEV CVEs mapped through the REAL governed policy engine.
    "/api/a11oy/v1/sec/kevgate": ep(schema="kevgate", sla=DAY, citations=True,
        note="Live CISA KEV -> deny-by-default gate impact; gates_fired is the real engine result."),
    # router/stats: live per-tier router stats derived from the real szl_brain.TIERS
    #   catalog. Throughput is an honest in-memory counter (resets on rebuild), so
    #   it is deterministic/derived -> no freshness SLA and no external citation.
    "/api/a11oy/v1/router/stats": ep(schema="router_stats", sla=None,
        note="Live LLM-router per-tier stats from szl_brain.TIERS; throughput is an honest in-memory counter."),

    # ── Metabolic scaling (szl_scaling.py — DETERMINISTIC, reproduces documented numerics) ──
    # These are pure closed-form computations of published allometric/scaling laws,
    # NOT a live external feed: same inputs -> same output every call, so there is no
    # freshness obligation (sla=None/static). Each response already carries the author
    # attributions (Kleiber 1932, West-Brown-Enquist 1997, Banavar-Maritan-Rinaldo 1999,
    # Brown et al. 2004 MTE, Demetrius-Tuszynski 2010, Kaplan et al. 2020) in its body —
    # see /scaling/summary.sources. Honest labels: the reproduced classical numerics are
    # VERIFIED-deterministic; the SZL unified Φ (and compute-allometry analogy) are
    # explicitly PROPOSED — Φ is an engineering construct, NOT in the locked 8 and NOT
    # the formal Λ (Λ stays Conjecture 1). citationsRequired stays False because these
    # are derived computations (like /v1/lambda), not a live-data "no-mock-theater" feed;
    # the citations ride along as documentation, not as a freshness/liveness obligation.
    #
    # 200-on-bare-GET family: summary/exponents/compute take no required params.
    "/api/a11oy/v1/scaling/summary": ep(schema="scaling", sla=None,
        note="Deterministic scaling overview: status legend + author sources (Kleiber 1932 / WBE 1997 / Banavar 1999 / Brown 2004 / Demetrius-Tuszynski 2010 / Kaplan 2020) + worked examples. VERIFIED reproductions; SZL-Φ PROPOSED, NOT formal Λ."),
    "/api/a11oy/v1/scaling/exponents": ep(schema="scaling", sla=None,
        note="Deterministic catalog of universal scaling exponents, each row attributed (cite=). VERIFIED documented values."),
    "/api/a11oy/v1/scaling/compute": ep(schema="scaling", sla=None,
        note="Compute-capability-as-allometry mapping (Kaplan et al. 2020 neural scaling); status=PROPOSED analogy, NOT formal Λ."),
    # M-required family: kleiber/mte/heart/unified require ?M=<mass_kg>; calling without
    # the required query param legitimately validates (400/422) — that is honest input
    # validation (same pattern as the governed POST endpoints), NOT an undeclared break.
    # schema=generic_obj (not the strict scaling schema) because the probe runner hits
    # these bare (no ?M=) and validates the body of whatever status it allows; the
    # 200 result AND the honest 400/422 validation body are both JSON objects (same
    # pattern as the governed POST endpoints), so generic_obj passes both without
    # branding legitimate input-validation a schema lie.
    "/api/a11oy/v1/scaling/kleiber": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Kleiber 1932 B=B0·M^(3/4) basal metabolic rate; requires ?M=<kg>. Empty M validates (400/422). VERIFIED deterministic (70kg -> 1694.03 kcal/day)."),
    "/api/a11oy/v1/scaling/mte": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Brown et al. 2004 MTE Boltzmann-factor metabolic rate; requires ?M=<kg>. Empty M validates (400/422). VERIFIED deterministic."),
    "/api/a11oy/v1/scaling/heart": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="MTE-derived heart-rate/lifespan allometry; requires ?M=<kg>. Empty M validates (400/422). VERIFIED deterministic (70kg -> 83.32 bpm)."),
    "/api/a11oy/v1/scaling/unified": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="SZL unified Φ (WBE network × MTE/PMF activation × coherence); requires ?M=<kg>. status=PROPOSED, note carries 'Λ=Conjecture 1'. PROPOSED engineering construct, NOT the formal Λ, NOT in the locked 8."),

    # ── Allodial AI sovereignty (szl_allodial.py — DETERMINISTIC; PROPOSED engineering
    # gate, NOT the formal Λ; Λ stays Conjecture 1; adds NOTHING to the locked 8). Every
    # formula derived from cited prior art (Denning 1976 lattice / Goguen-Meseguer 1982
    # non-interference / EU-CSF SEAL+SovScore / HHI). SZL claims none as its own. ──
    "/api/a11oy/v1/allodial/summary": ep(schema="generic_obj", sla=None,
        note="Allodial doctrine summary: thesis, 3 layers (land/deed/allodium), SEAL scale, doctrine gates (tier=EXPERIMENTAL/PROPOSED, lambda=Conjecture 1, allodial_is_formal_lambda=False, trust_never_100=True), cites. PROPOSED, NOT the formal Λ."),
    "/api/a11oy/v1/allodial/score": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Allodial Sovereignty Score A=[Σ w_k·SEAL_k/4]×(1−DCI)×100 from ?seals=&weights=&dep=. EU-CSF weighted SEAL + HHI lock-in penalty (both cited). tier=PROPOSED (weights need calibration), NOT the formal Λ."),
    "/api/a11oy/v1/allodial/lattice": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Denning-1976 access-control lattice (DOI:10.1145/360051.360056) rendered as a 3D DAG: ⊤=SEAL-4 allodial top, feudal chains strictly lower. Deterministic; PROPOSED engineering view, NOT the formal Λ."),
    "/api/a11oy/v1/allodial/noninterference": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Goguen-Meseguer 1982 non-interference witness (IEEE S&P): purged-op equivalence over the lattice. Deterministic; cited prior art; PROPOSED, NOT the formal Λ."),

    # ── szl_entanglement.py: 2-qubit entanglement measures + the PROPOSED coherence→
    # entanglement-capacity bridge E_max(t) ≤ C0·exp(−γt). PURE STDLIB, deterministic,
    # byte-identical a11oy↔killinchu. EXPERIMENTAL tier; adds NOTHING to the locked 8;
    # Λ stays Conjecture 1; the capacity bound is a PROPOSED engineering gate, NOT the
    # formal Λ; trust never 100%. Every borrowed formula cited to its real author. ──
    "/api/a11oy/v1/entangle/summary": ep(schema="generic_obj", sla=None,
        note="Entanglement module summary: honest verdict + tiers (RIGOROUS bridge / monogamy STRUCTURAL / QBA NARRATIVE / avian ACTIVE / FMO CONTESTED / Orch-OR SPECULATIVE), measures, doctrine (locked_count_unchanged, lambda=Conjecture 1, trust_never_100, tier=EXPERIMENTAL/PROPOSED), cites. PROPOSED, NOT the formal Λ."),
    "/api/a11oy/v1/entangle/capacity_bound": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="HERO bridge: E_max(t) ≤ C0·exp(−γt) tying SZL Λ-v5 coherence decay to entanglement-generating CAPACITY (Streltsov 2015, RMP 89:041003) composed with the merged-Lean coherence curve. Deterministic; PROPOSED engineering gate, NOT the formal Λ; Λ stays Conjecture 1."),
    "/api/a11oy/v1/entangle/entropy": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="von Neumann entanglement entropy (bits) for state=bell|product. Bell=1 bit, product=0. Cited (von Neumann). Deterministic."),
    "/api/a11oy/v1/entangle/concurrence": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Wootters 1998 concurrence + entanglement of formation for state=bell|product. Bell concurrence=1, product=0. Cited (Wootters, PRL 80:2245). Deterministic."),
    "/api/a11oy/v1/entangle/negativity": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Vidal-Werner 2002 negativity + logarithmic negativity for state=bell|product. Bell negativity=0.5, product=0. Cited (Vidal-Werner, PRA 65:032314). Deterministic."),
    "/api/a11oy/v1/entangle/chsh": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="CHSH 1969 S value vs classical bound 2 vs Tsirelson 1980 bound 2√2 from ?corr=c1,c2,c3,c4; flags local-realism violation. Cited (CHSH PRL 23:880 / Tsirelson). Deterministic."),
    "/api/a11oy/v1/entangle/monogamy": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="CKW 2000 monogamy Σ τ_pairwise ≤ τ_global from ?pairwise=&total= — the STRUCTURAL no-leak / trust<100% primitive tying to Khipu. Cited (Coffman-Kundu-Wootters, PRA 61:052306). Deterministic."),

    # ── szl_neuroplasticity.py: cited learning-rule math grounding the agent loop.
    # PURE STDLIB, deterministic, byte-identical a11oy↔killinchu. EXPERIMENTAL tier; adds
    # NOTHING to the locked 8; Λ stays Conjecture 1; trust never 100%. RIGOROUS (cited):
    # Hebb 1949 / Oja 1982 / BCM 1982 / Bi-Poo 1998 / Hubel-Wiesel 1981 / Dohare-Sutton
    # Nature 2024 / Sokar ReDo 2023 / Kirkpatrick EWC 2017. The predictive-coding↔Hebbian
    # unifier (Millidge 2022) is a PROPOSED lens, NOT a Λ theorem. Every rule cited. ──
    "/api/a11oy/v1/neuro/summary": ep(schema="generic_obj", sla=None,
        note="Neuroplasticity module summary: honest_frame + tiers (Hebb/Oja/BCM/STDP/scaling=RIGOROUS; loss-of-plasticity/ReDo/EWC=RIGOROUS recent; predictive-coding↔Hebbian unifier=PROPOSED lens), doctrine (locked_count_unchanged, lambda=Conjecture 1, trust_never_100, tier=EXPERIMENTAL/PROPOSED), cites. PROPOSED, NOT the formal Λ."),
    "/api/a11oy/v1/neuro/hebb": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Hebb 1949 update Δw=η·x·y (unstable alone, grows unbounded). Cited (Hebb, The Organization of Behavior 1949). Deterministic."),
    "/api/a11oy/v1/neuro/oja": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Oja 1982 rule fitted over ?data= — returns the learned principal_direction + eigenvalue_estimate (provably converges to the top principal eigenvector). Cited (Oja, J. Math. Biol. 15:267-273). Deterministic."),
    "/api/a11oy/v1/neuro/bcm": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="BCM 1982 sliding modification threshold θ_M=E[y²] from ?y=history; reports potentiate/depress sign. Cited (Bienenstock-Cooper-Munro, J. Neurosci. 2(1):32-48). Deterministic."),
    "/api/a11oy/v1/neuro/stdp": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Bi-Poo 1998 STDP window Δw(Δt) from ?dt= ms: Δt>0 LTP, Δt<0 LTD (asymmetric exponential). Cited (Bi & Poo, J. Neurosci. 18(24):10464). Deterministic."),
    "/api/a11oy/v1/neuro/plasticity": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="HERO loss-of-plasticity diagnostic from ?act=activations: dormant-unit fraction + plasticity score + re-init recommendation (continual backprop / ReDo) — the honest frontier tie-in for long-running agents. Cited (Dohare-Sutton Nature 2024 DOI:10.1038/s41586-024-07711-7; Sokar ReDo 2023 arXiv:2302.12902). Deterministic."),
    "/api/a11oy/v1/neuro/ewc": ep(schema="generic_obj", sla=None,
        allow_statuses=(200, 400, 422),
        note="Kirkpatrick 2017 EWC penalty L=(λ/2)Σ Fᵢ(θᵢ−θ*ᵢ)² from ?theta=&star=&fisher= — mitigates catastrophic forgetting in continual learning. Cited (Kirkpatrick et al. PNAS DOI:10.1073/pnas.1611835114). Deterministic."),

    # ── szl_unified_formulas.py + szl_cuas_formulas.py module-level /summary cards.
    # These two module summaries back the Formula Atlas index tab. Bare-GET 200,
    # deterministic, each carries its own author citations + doctrine block in-body
    # (sources cited to origin; locked_proven=8; lambda=Conjecture 1; trust never 100%;
    # cuas effector=SIMULATED). PROPOSED/ANALOGY engineering constructs, NOT the formal
    # Λ; Λ stays Conjecture 1. No live-feed freshness obligation (sla=None). ──
    "/api/a11oy/v1/unified/summary": ep(schema="generic_obj", sla=None,
        note="Unified-formulas (thesis v6) summary: borrowed structure cited to origin (Sherman-Morgan/NASA/Tsiolkovsky, LS12/Cuk-Stewart/Lock-Stewart, Lindblad 1976, Baumgratz-Cramer-Plenio 2014), status_legend VERIFIED/PROPOSED/ANALOGY, doctrine (locked_proven=8, lambda=Conjecture 1, lambda_v5=PROPOSED engineering gate, trust never 100%). PROPOSED/ANALOGY, NOT the formal Λ."),
    "/api/a11oy/v1/cuas/summary": ep(schema="generic_obj", sla=None,
        note="Counter-UAS C2 summary: SZL constructs with classical inspirations cited (Zarchan/Palumbo PN, Joerger GNSS χ², Julier-Uhlmann CI, Bar-Shalom, Olfati-Saber/Zelazo consensus, Manne WTA, NIST PQC FIPS 203/204/205), status_legend SIMULATED/VERIFIED/EXPERIMENTAL, doctrine (locked_proven=8, lambda=Conjecture 1, effector=SIMULATED, trust never 100%). EXPERIMENTAL; effector SIMULATED, never actuates."),

    # ── readiness (self) ──
    "/api/a11oy/v1/readiness": ep(schema="readiness", sla=5 * MIN),
    "/api/a11oy/v1/readiness/tab-matrix": ep(schema="tab_matrix", sla=None,
        note="This contract, served live — the harness verifies served == repo."),
}

# JSON-schema-lite shapes the probe runner validates against. Intentionally
# permissive on extra keys, strict on the keys that prove the response is real.
SCHEMAS = {
    "text": {"type": "string"},
    "generic_obj": {"type": "object"},
    "generic_list": {"anyOf": [{"type": "array"}, {"type": "object"}]},
    "lambda": {"type": "object", "anyKey": ["lambda", "value", "score", "Λ", "conjecture", "floor"]},
    "gates": {"type": "object", "anyKey": ["gates", "manifest", "passed", "results"]},
    "selftest": {"type": "object",
                 "anyKey": ["invariants", "invariants_all_hold", "reasoning",
                            "policy", "operator", "unifying", "passed", "results"]},
    "mcp_tools": {"type": "object", "anyKey": ["tools", "count", "items"]},
    "llm_registry": {"type": "object", "anyKey": ["models", "registry", "tiers", "providers"]},
    "provenance": {"type": "object",
                   "anyKey": ["receipts", "chain", "anchor", "entries", "items",
                              "slsa", "doctrine", "khipu_dsse", "self_attesting", "space"]},
    "ledger": {"type": "object", "anyKey": ["entries", "ledger", "items", "rows", "receipts", "count"]},
    "arena_history": {"type": "object", "anyKey": ["runs", "history", "items"]},
    "mesh": {"type": "object",
             "anyKey": ["nodes", "state", "quorum", "health", "mesh_organs", "wires", "khipu_nodes"]},
    "deva_health": {"type": "object", "required": ["tabs"]},
    "feeds_pulse": {"type": "object", "anyKey": ["items", "feed_count", "live_count"]},
    "kevgate": {"type": "object", "anyKey": ["items", "gate_catalog", "count"]},
    "router_stats": {"type": "object", "anyKey": ["routes", "servedThisWindow", "tiers"]},
    # scaling: deterministic metabolic/allometric/compute-scaling computations. Strict
    # on at least one distinctive real key across the family, permissive on extras.
    "scaling": {"type": "object",
                "anyKey": ["sources", "examples", "universal_exponents", "exponents",
                           "B_kcal_day", "bpm", "phi", "predicted_loss", "status_legend"]},
    "readiness": {"type": "object", "required": ["sections"]},
    "tab_matrix": {"type": "object", "required": ["tabs", "endpoints"]},
}

# Explicit per-tab endpoint attachment (authoritative where present). Keys missing
# here fall back to the family heuristic below.
TAB_ENDPOINTS = {
    "warboard": ["/api/a11oy/v1/lambda", "/api/a11oy/v1/gates", "/api/a11oy/provenance"],
    "lambda": ["/api/a11oy/v1/lambda"],
    "gates": ["/api/a11oy/v1/gates"],
    "mcp": ["/api/a11oy/v1/mcp/tools"],
    "llm": ["/api/a11oy/v1/llm/registry"],
    "modelatlas": ["/api/a11oy/v1/llm/registry"],
    "arena": ["/api/a11oy/v1/eval-arena/history"],
    "replay": ["/api/a11oy/v1/eval-arena/history"],
    "mesh": ["/api/a11oy/v1/mesh/state", "/api/a11oy/v1/capabilities/mesh"],
    "trustspace": ["/api/a11oy/v1/mesh/state"],
    "ledger3d": ["/api/a11oy/v1/ledger"],
    "receipts": ["/api/a11oy/provenance", "/api/a11oy/v1/receipt/export", "/api/a11oy/cosign.pub"],
    "chain": ["/api/a11oy/provenance"],
    "lineage": ["/api/a11oy/provenance"],
    "reciprocity": ["/api/a11oy/v1/ledger"],
    "govern": ["/api/a11oy/v1/policy/decide", "/api/a11oy/v1/gates"],
    "govatlas": ["/api/a11oy/v1/policy/gates"],
    "policies": ["/api/a11oy/v1/policy/compliance", "/api/a11oy/v1/policy/gates"],
    "decision": ["/api/a11oy/v1/policy/decisions/feed"],
    "threats": ["/api/a11oy/v1/sec/threats"],
    "threatgraph": ["/api/a11oy/v1/sec/threatgraph"],
    "attack": ["/api/a11oy/v1/sec/attack"],
    "cve": ["/api/a11oy/v1/sec/cve"],
    "kev": ["/api/a11oy/v1/sec/kev"],
    "fleet": ["/api/a11oy/v1/mesh/state", "/api/a11oy/v1/operator/ledger"],
    "ask": ["/api/a11oy/v1/operator/ask"],
    "command": ["/api/a11oy/v2/operator/command-log"],
    "mission": ["/api/a11oy/v1/operator/ledger"],
    "pulse": ["/api/a11oy/v1/observability/summary"],
    "business": ["/api/a11oy/v1/observability/business"],
    "forecast": ["/api/a11oy/v1/seismic/forecast"],
    "feed": ["/api/a11oy/v1/policy/decisions/feed"],
    "verticals": ["/api/a11oy/v1/vertical-packs"],
    "knowledge": ["/api/a11oy/v1/formulas/selftest"],
    "readiness": ["/api/a11oy/v1/readiness", "/api/a11oy/v1/readiness/tab-matrix"],
    # Vertical command + deep tabs
    "vfinance": ["/api/a11oy/v1/vert/finance/feed", "/api/a11oy/v1/deva/healthz"],
    "finq": ["/api/a11oy/v1/vert/finance/feed", "/api/a11oy/v1/deva/healthz"],
    "finc": ["/api/a11oy/v1/deva/healthz"],
    "finm": ["/api/a11oy/v1/deva/healthz"],
    "finp": ["/api/a11oy/v1/deva/healthz"],
    "finr": ["/api/a11oy/v1/deva/healthz"],
    "vrealestate": ["/api/a11oy/v1/deva/healthz"],
    "rem": ["/api/a11oy/v1/deva/healthz"],
    "red": ["/api/a11oy/v1/deva/healthz"],
    "reo": ["/api/a11oy/v1/deva/healthz"],
    "redeal": ["/api/a11oy/v1/deva/healthz"],
    "rebe": ["/api/a11oy/v1/deva/healthz"],
    "vlegal": ["/api/a11oy/v1/devb/healthz"],
    "legMatter": ["/api/a11oy/v1/devb/healthz"],
    "legDefense": ["/api/a11oy/v1/devb/healthz"],
    "legReg": ["/api/a11oy/v1/devb/healthz"],
    "legInsure": ["/api/a11oy/v1/devb/healthz"],
    "legExposure": ["/api/a11oy/v1/devb/healthz"],
    "entCockpit": ["/api/a11oy/v1/devb/healthz", "/api/a11oy/v1/observability/summary"],
    "entComms": ["/api/a11oy/v1/devb/healthz"],
    "entRevenue": ["/api/a11oy/v1/devb/healthz"],
    "entIncident": ["/api/a11oy/v1/devb/healthz"],
    "entForecast": ["/api/a11oy/v1/devb/healthz"],
    "vcyber": ["/api/a11oy/v1/sec/threats", "/api/a11oy/v1/sec/threatgraph"],
    "cybThreat": ["/api/a11oy/v1/sec/threats", "/api/a11oy/v1/sec/cve"],
    "cybSurface": ["/api/a11oy/v1/sec/threatgraph", "/api/a11oy/v1/sec/attack"],
    "cybZero": ["/api/a11oy/v1/mesh/state"],
    "cybPosture": ["/api/a11oy/v1/policy/compliance"],
    "cybIncident": ["/api/a11oy/provenance"],
    "vdefense": ["/api/a11oy/v1/mesh/state"],
    "fltTopo": ["/api/a11oy/v1/mesh/state"],
    "fltObs": ["/api/a11oy/v1/observability/summary"],
    "fltOrch": ["/api/a11oy/v1/llm/registry"],
    "fltReceipts": ["/api/a11oy/provenance"],
    "fltGov": ["/api/a11oy/v1/policy/gates"],
    "pvaAnchor": ["/api/a11oy/provenance"],
    "pvaGraph": ["/api/a11oy/provenance"],
    "pvaHealth": ["/api/a11oy/provenance"],
    "pvaPqc": ["/api/a11oy/cosign.pub"],
    "pvaVerify": ["/api/a11oy/v1/receipt/export", "/api/a11oy/cosign.pub"],
    "whHero": ["/api/a11oy/v1/warhacker/index"],
    # New live tabs (2026-06-10): contract them to their real backing endpoints so
    # the probe judges them honestly instead of treating live tabs as static.
    "feedpulse": ["/api/a11oy/v1/feeds/pulse"],
    "kevgate": ["/api/a11oy/v1/sec/kevgate"],
    "routerarena": ["/api/a11oy/v1/router/stats", "/api/a11oy/v1/llm/registry"],
    "udsMesh": ["/api/a11oy/v1/mesh/state"],
    # New living-3D tab (Metabolic Scaling): explicitly contract it to the real
    # deterministic szl_scaling.py family so it is judged as a genuine declared tab
    # (NOT silently bucketed static). VERIFIED reproductions + PROPOSED SZL-Φ.
    "scaling": ["/api/a11oy/v1/scaling/summary", "/api/a11oy/v1/scaling/exponents",
                "/api/a11oy/v1/scaling/compute", "/api/a11oy/v1/scaling/kleiber",
                "/api/a11oy/v1/scaling/mte", "/api/a11oy/v1/scaling/heart",
                "/api/a11oy/v1/scaling/unified"],
    # Allodial AI doctrine + interactive sovereignty-score tab: contract it to the real
    # szl_allodial.py endpoints so it is judged as a genuine declared (non-static) tab.
    # PROPOSED engineering gate; Λ stays Conjecture 1; deterministic, prior-art-cited.
    "allodialai": ["/api/a11oy/v1/allodial/summary", "/api/a11oy/v1/allodial/score"],
    # Living-3D sovereignty/allodial-lattice visualization tab (Dev 2). Distinct from
    # allodialai; same szl_allodial.py endpoints — lattice + non-interference witness +
    # summary + interactive score. PROPOSED engineering view; Λ stays Conjecture 1.
    "sovereignty": ["/api/a11oy/v1/allodial/summary", "/api/a11oy/v1/allodial/score",
                    "/api/a11oy/v1/allodial/lattice", "/api/a11oy/v1/allodial/noninterference"],
    # Living-3D "Entanglement" tab (EXPERIMENTAL): contract it to the real deterministic
    # szl_entanglement.py family so the probe judges it as a genuine declared tab (NOT
    # silently bucketed static). HERO = the PROPOSED capacity bound E_max(t) ≤ C0·exp(−γt)
    # (Streltsov 2015 ∘ SZL Λ-v5); Bell-vs-product comparator; CHSH meter; CKW monogamy →
    # Khipu; honest-tiering panel. PROPOSED engineering gate; Λ stays Conjecture 1.
    "entangle": ["/api/a11oy/v1/entangle/summary", "/api/a11oy/v1/entangle/capacity_bound",
                 "/api/a11oy/v1/entangle/concurrence", "/api/a11oy/v1/entangle/negativity",
                 "/api/a11oy/v1/entangle/entropy", "/api/a11oy/v1/entangle/chsh",
                 "/api/a11oy/v1/entangle/monogamy"],
    # Living "Neuroplasticity" tab (EXPERIMENTAL): contract it to the real deterministic
    # szl_neuroplasticity.py family so the probe judges it as a genuine declared tab (NOT
    # silently bucketed static). HERO = the loss-of-plasticity diagnostic (Dohare-Sutton
    # Nature 2024 / Sokar ReDo 2023) grounding the agent loop; Hubel-Wiesel critical period;
    # Hebb vs Oja; BCM sliding threshold; STDP window; honest-tiering panel. RIGOROUS (cited)
    # for the rules; predictive-coding↔Hebbian unifier is a PROPOSED lens; Λ stays Conjecture 1.
    "neuro": ["/api/a11oy/v1/neuro/summary", "/api/a11oy/v1/neuro/hebb",
              "/api/a11oy/v1/neuro/oja", "/api/a11oy/v1/neuro/bcm",
              "/api/a11oy/v1/neuro/stdp", "/api/a11oy/v1/neuro/plasticity",
              "/api/a11oy/v1/neuro/ewc"],
    # Formula Atlas — the unified investor-readable INDEX of all 5 live formula
    # modules. Contract it to each module's live /summary so it is judged as a
    # genuine declared (non-static) tab, NOT silently bucketed static. Pure index
    # view: reads every /summary live for tier + citations (never upgraded), with
    # clickable live routes. Additive; Λ stays Conjecture 1; locked-proven stays 8.
    "atlas": ["/api/a11oy/v1/scaling/summary", "/api/a11oy/v1/allodial/summary",
              "/api/a11oy/v1/entangle/summary", "/api/a11oy/v1/unified/summary",
              "/api/a11oy/v1/cuas/summary"],
    "whTamper": ["/api/a11oy/v1/warhacker/index"],
    "whCannonico": ["/api/a11oy/v1/warhacker/index"],
}

# Tabs that present clearly-labelled SAMPLE/MODELED/CONNECT-READY content by design
# (doctrine-compliant when labelled). The sweeper still requires the explicit label.
SAMPLE_OK_TABS = {
    "entComms", "entRevenue", "entForecast", "replay", "demo", "wowdrop",
    "wowledger", "wowroi", "wowtoggle", "melt", "brain2",
}

# Tabs that legitimately render without a network call (pure explainer / static UI).
STATIC_TABS = {
    "demo", "knowledge", "ontology", "honest", "kbformulas", "codetab",
    "docs", "sdk", "deploy", "organism", "organheart", "organnervous",
    "organskeleton", "organyawar", "wowtoggle", "oversight",
}


def _decode(s: str) -> str:
    """Decode \\uXXXX escapes that appear in the JS source string literals."""
    try:
        return s.encode("utf-8").decode("unicode_escape")
    except Exception:
        return s


def extract_tabs(html: str):
    """Extract ONLY genuine console tabs. A tab is real iff it is one of:
      (a) a top-level nav target  data-view="key"
      (b) a registered view       reg('key','Title', ...)
      (c) a direct view override  V.key = ...  (legacy/core tabs)
      (d) a deep vertical def      ['key','Title','badge','desc', R.renderXxx]
      (e) a vertical-command def   ['key','\\uXXXX','Label']   (icon = unicode glyph)
    The narrow patterns avoid pulling in proof/formula/ticker data arrays
    (F1, P1, SPY, …) that merely look like ['x','y',...] elsewhere in the page.
    """
    tabs = {}  # key -> {title, group}

    def put(k, title=None, override=False):
        if k not in tabs:
            tabs[k] = {"title": title or k, "group": "Console"}
        elif override and title:
            tabs[k]["title"] = title

    # (a) data-view nav targets
    for k in sorted(set(re.findall(r'data-view="([a-zA-Z0-9_]+)"', html))):
        put(k)

    # (b) reg('key','Title', ...)
    for k, t in re.findall(r"reg\('([a-zA-Z0-9_-]+)','([^']*)'", html):
        put(k, _decode(t), override=True)

    # (c) V.key = ...  (then V.key = mk('Title' for the title)
    for k in sorted(set(re.findall(r"\bV\.([a-zA-Z0-9_]+)\s*=", html))):
        put(k)
    for k, t in re.findall(r"\bV\.([a-zA-Z0-9_]+)\s*=\s*mk\('([^']*)'", html):
        put(k, _decode(t), override=True)

    # (d) deep vertical defs: 5-element entry terminating in R.renderXxx
    for k, t in re.findall(
        r"\['([a-zA-Z0-9_-]+)',\s*'([^']*)',\s*'[^']*',\s*'[^']*',\s*R\.render",
        html,
    ):
        put(k, _decode(t), override=True)

    # (e) vertical-command defs: ['key','\uXXXX','Label']
    for k, t in re.findall(r"\['([a-zA-Z0-9_-]+)',\s*'\\u[0-9a-fA-F]{4}',\s*'([^']*)'\]", html):
        put(k, _decode(t), override=True)

    return tabs


FAMILY_PREFIX = [
    ("fin", ["/api/a11oy/v1/deva/healthz"]),
    ("re", ["/api/a11oy/v1/deva/healthz"]),
    ("leg", ["/api/a11oy/v1/devb/healthz"]),
    ("ent", ["/api/a11oy/v1/devb/healthz"]),
    ("cyb", ["/api/a11oy/v1/sec/threats"]),
    ("flt", ["/api/a11oy/v1/mesh/state"]),
    ("pva", ["/api/a11oy/provenance"]),
    ("wh", ["/api/a11oy/v1/warhacker/index"]),
    ("uds", ["/api/a11oy/v1/mesh/state"]),
    ("org", []),
    ("wow", []),
]


def endpoints_for(key: str):
    if key in TAB_ENDPOINTS:
        return TAB_ENDPOINTS[key]
    for pref, eps in FAMILY_PREFIX:
        if key.startswith(pref):
            return eps
    return []


def build():
    if not os.path.exists(CONSOLE):
        print("FATAL: console.html not found at %s" % CONSOLE, file=sys.stderr)
        sys.exit(2)
    with open(CONSOLE, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    raw = extract_tabs(html)
    tabs = []
    for key in sorted(raw):
        info = raw[key]
        eps = endpoints_for(key)
        is_static = key in STATIC_TABS or (not eps)
        sample_ok = key in SAMPLE_OK_TABS
        # citationsRequired for the tab = any backing endpoint requires citations
        cit = any(ENDPOINTS.get(e, {}).get("citationsRequired") for e in eps)
        tabs.append({
            "key": key,
            "title": info["title"],
            "group": info["group"],
            "route": "%s#%s" % (CONSOLE_ROUTE, key),
            "endpoints": eps,
            "citationsRequired": bool(cit),
            "sampleLabelAllowed": sample_ok,
            "static": is_static,
            # degradedRules at tab level: tolerate honest cached/degraded but never
            # unlabeled placeholder data or undeclared 5xx.
            "degradedRules": {
                "allowSampleLabel": sample_ok,
                "failOnUnlabeledPlaceholder": True,
                "failOnMissingCitation": bool(cit),
            },
        })

    matrix = {
        "version": "1",
        "doctrine": "v11",
        "organ": ORGAN,
        "consoleRoute": CONSOLE_ROUTE,
        "generatedAt": os.environ.get("SOURCE_DATE_EPOCH_ISO")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z"),
        "generator": "tools/readiness-harness/gen_tabs_matrix.py",
        "summary": {
            "tabs": len(tabs),
            "endpoints": len(ENDPOINTS),
            "tabsWithCitations": sum(1 for t in tabs if t["citationsRequired"]),
            "staticTabs": sum(1 for t in tabs if t["static"]),
        },
        "endpoints": ENDPOINTS,
        "schemas": SCHEMAS,
        "tabs": tabs,
    }
    return matrix


def main():
    matrix = build()
    text = json.dumps(matrix, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    if "--check" in sys.argv:
        if not os.path.exists(OUT):
            print("DRIFT: tabs.json missing — run the generator.", file=sys.stderr)
            sys.exit(1)
        with open(OUT, "r", encoding="utf-8") as f:
            cur = f.read()
        # compare modulo the generatedAt line (date is informational, not drift)
        def strip_date(s):
            return re.sub(r'"generatedAt":\s*"[^"]*"', '"generatedAt":""', s)
        if strip_date(cur) != strip_date(text):
            print("DRIFT: tabs.json is stale vs the console — regenerate.", file=sys.stderr)
            sys.exit(1)
        print("OK: tabs.json matches the console (%d tabs)." % matrix["summary"]["tabs"])
        return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    # Emit a GET-only target list for the k6 stress suite (warhacker.js reads it).
    stress_targets = sorted(
        p for p, spec in ENDPOINTS.items() if (spec.get("method") or "GET") == "GET"
    )
    stress_path = os.path.join(os.path.dirname(OUT), "stress", "stress-targets.json")
    os.makedirs(os.path.dirname(stress_path), exist_ok=True)
    with open(stress_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(stress_targets, indent=2) + "\n")
    print("wrote %s (%d tabs, %d endpoints, %d stress targets)" %
          (OUT, matrix["summary"]["tabs"], matrix["summary"]["endpoints"], len(stress_targets)))


if __name__ == "__main__":
    main()
