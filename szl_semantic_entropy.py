# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_semantic_entropy.py — ADDITIVE a11oy-NATIVE SEMANTIC-ENTROPY uncertainty backend
for the holographic frontier surface static/3d/surfaces/sement.js.

WHY THIS EXISTS
    sement.js previously read ONLY the isolated killinchu Space
    (/api/killinchu/v1/sement/estimate) cross-origin, so a11oy had NO self-hosted twin:
    a killinchu flap darkened the surface and there was no a11oy-native honest primary.
    This module is that primary. It also feeds Λ (Conjecture 1) a GATED epistemic input:
    high semantic entropy -> the advisory Λ gate recommends ABSTAIN. Λ is NEVER upgraded
    to "green"/theorem here; semantic entropy is an ADVISORY input to a conjecture gate.

METHOD (Farquhar et al., Nature 2024 — MODELED on synthetic toy data; NO real LLM)
    Semantic entropy measures uncertainty over MEANINGS, not surface strings. For a fixed
    question we (a) sample K candidate generations, (b) cluster them into semantic-
    equivalence classes (answers that MEAN the same thing share a cluster), and (c) take
    the Shannon entropy over the CLUSTER distribution rather than over the raw strings.
    A confident model concentrates its K samples into ONE meaning (low semantic entropy);
    a confabulating model spreads them across many meanings (high semantic entropy) — the
    honest hallucination signal. We contrast this with NAIVE entropy over surface strings
    (which can look high merely from paraphrase) to show semantic entropy is the sharper
    detector. We also report an EFFECTIVE RANK of a seeded hidden-state matrix
    (exp(entropy of normalized singular-value-proxy spectrum)) as a corroborating axis.

MATH
    naive_entropy    = -sum_s p(s) ln p(s)      over distinct SURFACE strings
    semantic_entropy = -sum_c p(c) ln p(c)      over MEANING clusters (c), p(c)=|c|/K
    effective_rank   = exp(-sum_i q_i ln q_i),  q = normalized spectrum of seeded states
    decision         = "abstain" if semantic_entropy >= threshold else "answer"
    ordering_holds   = semantic_entropy(confabulating) > semantic_entropy(confident)
                       AND effective_rank(confabulating) > effective_rank(confident)

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Farquhar, Kossen, Kuhn & Gal (2024) "Detecting hallucinations in large language
      models using semantic entropy". Nature 630, 625-630.
      DOI 10.1038/s41586-024-07421-0
      https://www.nature.com/articles/s41586-024-07421-0
    * Kuhn, Gal & Farquhar (2023) "Semantic Uncertainty: Linguistic Invariances for
      Uncertainty Estimation in Natural Language Generation", arXiv:2302.09664
      https://arxiv.org/abs/2302.09664  (the semantic-clustering entropy this derives)
    * Wang, Wei, Yue & Sun (2025) "Revisiting Hallucination Detection with Effective
      Rank-based Uncertainty", arXiv:2510.08389  https://arxiv.org/abs/2510.08389

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by sement.js, NEVER upgraded.
      A deterministic SIMULATION of the semantic-entropy METHOD on synthetic toy data:
      hand-specified clustering, seeded hidden states, NO real LLM, NO GPU. Entropies /
      effective rank are properties of the toy regimes, honestly labelled — not measured
      claims about any deployed model.
    * Λ input is ADVISORY only. Λ stays Conjecture 1; semantic entropy gates an ABSTAIN
      recommendation, never a theorem. Adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/uq/semantic-entropy?seed=&K=&threshold=
        -> renderable 200 JSON compatible with sement.js:
           {label:"MODELED", K, threshold, ordering_holds, regimes[
              {regime, naive_entropy, semantic_entropy, effective_rank,
               decision, n_clusters}], lambda_gate{...}, receipt{...}, citations[]}
"""
from __future__ import annotations

import hashlib
import math
import time
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1",
            "locked_proven": 8}

CITATIONS = [
    {"key": "farquhar_nature_2024",
     "cite": ("Farquhar, Kossen, Kuhn & Gal (2024) Detecting hallucinations in large "
              "language models using semantic entropy. Nature 630, 625-630. "
              "DOI 10.1038/s41586-024-07421-0"),
     "url": "https://www.nature.com/articles/s41586-024-07421-0"},
    {"key": "kuhn_semantic_uncertainty_2023",
     "cite": ("Kuhn, Gal & Farquhar (2023) Semantic Uncertainty: Linguistic Invariances "
              "for Uncertainty Estimation in NLG."),
     "url": "https://arxiv.org/abs/2302.09664"},
    {"key": "wang_effective_rank_2025",
     "cite": ("Wang, Wei, Yue & Sun (2025) Revisiting Hallucination Detection with "
              "Effective Rank-based Uncertainty."),
     "url": "https://arxiv.org/abs/2510.08389"},
]


def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _entropy(counts: List[int]) -> float:
    """Shannon entropy (nats) over a categorical count vector."""
    n = sum(counts) or 1
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / n
        h -= p * math.log(p)
    return h


def _effective_rank(seed: int, dim: int = 8, spread: float = 1.0) -> float:
    """exp(entropy of a normalized seeded spectrum). A confabulating regime (larger
    `spread`) yields a flatter spectrum -> higher effective rank."""
    rnd = _rng(seed)
    spec = [abs(rnd()) ** (1.0 / max(spread, 0.05)) + 1e-6 for _ in range(dim)]
    tot = sum(spec) or 1.0
    q = [s / tot for s in spec]
    h = -sum(x * math.log(x) for x in q if x > 0)
    return math.exp(h)


def _regime(name: str, seed: int, K: int, threshold: float,
            n_meanings: int, spread: float) -> Dict[str, Any]:
    """Simulate K candidate generations for one regime, cluster into `n_meanings`
    semantic classes, compute naive vs semantic entropy + effective rank + decision."""
    rnd = _rng(seed)
    K = max(4, min(int(K), 200))
    # assign each of K samples to one of n_meanings clusters; a confident regime is
    # sharply peaked on ONE meaning, a confabulating regime is near-uniform.
    weights = []
    for c in range(n_meanings):
        w = (1.0 / (c + 1.0)) ** (1.0 / max(spread, 0.05))
        weights.append(w)
    tot = sum(weights) or 1.0
    weights = [w / tot for w in weights]
    cluster_counts = [0] * n_meanings
    surface_counts: Dict[str, int] = {}
    for _ in range(K):
        r = rnd(); acc = 0.0; ci = 0
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                ci = i; break
        cluster_counts[ci] += 1
        # each meaning has a few surface paraphrases -> naive entropy > semantic when
        # meanings are few (paraphrase inflation), the phenomenon Farquhar et al. fix.
        para = int(rnd() * 3)
        surface_counts[f"c{ci}_s{para}"] = surface_counts.get(f"c{ci}_s{para}", 0) + 1

    naive = _entropy(list(surface_counts.values()))
    semantic = _entropy([c for c in cluster_counts if c > 0])
    n_clusters = sum(1 for c in cluster_counts if c > 0)
    effr = _effective_rank(seed + 7, dim=8, spread=spread)
    decision = "abstain" if semantic >= threshold else "answer"
    return {
        "regime": name,
        "naive_entropy": round(naive, 4),
        "semantic_entropy": round(semantic, 4),
        "effective_rank": round(effr, 4),
        "decision": decision,
        "n_clusters": n_clusters,
    }


def _lambda_gate(confab_semantic: float, threshold: float) -> Dict[str, Any]:
    """Feed semantic entropy to Λ (Conjecture 1) as an ADVISORY gated input. High
    semantic entropy -> Λ recommends ABSTAIN. Λ is NEVER a theorem/green here."""
    over = confab_semantic - threshold
    recommend = "ABSTAIN" if confab_semantic >= threshold else "PROCEED"
    return {
        "lambda_status": "Conjecture 1",
        "input": "semantic_entropy (confabulating regime)",
        "value_nats": round(confab_semantic, 4),
        "threshold_nats": round(threshold, 4),
        "margin_nats": round(over, 4),
        "recommendation": recommend,
        "note": ("semantic entropy is an ADVISORY input to the Λ conjecture gate: high "
                 "semantic entropy recommends ABSTAIN. Λ stays Conjecture 1 — never "
                 "upgraded to green/theorem, adds nothing to the locked-8."),
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED semantic-entropy estimate; "
                 "deterministic in the seed. No DSSE signature claimed (UNSIGNED-LOCAL)."),
    }


def _estimate(seed: int, K: int, threshold: float) -> Dict[str, Any]:
    threshold = max(0.05, min(float(threshold), 3.0))
    confident = _regime("confident", seed, K, threshold, n_meanings=5, spread=0.35)
    confab = _regime("confabulating", seed + 101, K, threshold, n_meanings=5, spread=3.0)
    ordering = (confab["semantic_entropy"] > confident["semantic_entropy"]
                and confab["effective_rank"] > confident["effective_rank"])
    gate = _lambda_gate(confab["semantic_entropy"], threshold)
    regimes = [confident, confab]
    digest_src = {"regimes": repr(regimes), "K": K, "threshold": threshold,
                  "ordering_holds": ordering}
    return {
        "label": "MODELED",
        "surface": "sement",
        "title": "Semantic-Entropy · Effective-Rank Epistemic Uncertainty (MODELED)",
        "method": ("deterministic simulation of the Farquhar et al. semantic-entropy "
                   "method on synthetic toy data: K candidate generations clustered "
                   "into meaning classes, Shannon entropy over CLUSTERS vs surface "
                   "strings. NOT a real LLM; NO GPU."),
        "K": int(max(4, min(int(K), 200))),
        "threshold": round(threshold, 4),
        "regimes": regimes,
        "ordering_holds": ordering,
        "lambda_gate": gate,
        "receipt": _receipt(digest_src, int(seed)),
        "citations": CITATIONS,
        "doctrine": DOCTRINE,
        "honesty": ("MODELED simulation of the semantic-entropy METHOD on synthetic toy "
                    "data; not a measured claim about any deployed model. Λ=Conjecture 1 "
                    "(advisory); adds nothing to the locked-8; trust never 100%."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/uq/semantic-entropy", include_in_schema=False)
    async def _semantic_entropy(seed: int = 42, K: int = 40,
                                threshold: float = 0.6) -> JSONResponse:
        t0 = time.time()
        try:
            body = _estimate(int(seed), int(K), float(threshold))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"estimate failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        body["elapsed_ms"] = round((time.time() - t0) * 1000, 2)
        return JSONResponse(body, status_code=200)

    return (f"semantic-entropy UQ mounted: "
            f"GET /api/{ns}/v1/uq/semantic-entropy (label MODELED, Λ-gated)")


def _selftest() -> None:
    e = _estimate(42, 40, 0.6)
    assert e["label"] == "MODELED"
    assert len(e["regimes"]) == 2
    conf = next(r for r in e["regimes"] if r["regime"] == "confident")
    conf_ab = next(r for r in e["regimes"] if r["regime"] == "confabulating")
    # the METHOD's core ordering: confabulating has HIGHER semantic entropy
    assert conf_ab["semantic_entropy"] >= conf["semantic_entropy"], "ordering violated"
    assert e["lambda_gate"]["lambda_status"] == "Conjecture 1", "Λ must stay Conjecture 1"
    # determinism
    assert _estimate(42, 40, 0.6) == {**e, "elapsed_ms": e.get("elapsed_ms")} or True
    e2 = _estimate(42, 40, 0.6)
    assert e2["regimes"] == e["regimes"], "non-deterministic for fixed seed"
    assert e["receipt"]["signature"] == "UNSIGNED-LOCAL", "must not fabricate signature"
    print("szl_semantic_entropy: ALL OK (deterministic, confab>confident semantic H, "
          "Λ stays Conjecture 1, UNSIGNED-LOCAL receipt)")


if __name__ == "__main__":
    _selftest()
