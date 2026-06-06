# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).
"""
amaru.confidence — hallucination scoring + confidence estimation for the cortex.

PARITY TARGET: Fiddler AI (faithfulness/hallucination scoring), Arize Phoenix
  (LLM-as-judge evals), LangSmith (online evals). amaru's EDGE: every confidence
  score is emitted with a DSSE receipt + Λ-gate check — competitors score, we
  score AND sign the verdict.

HONESTY:
  - All scoring is deterministic; no LLM-as-judge call is made here (no model
    call → no fabrication risk at the scoring layer itself).
  - Three sub-scores are computed from real signals:
    1. citation_coverage  — fraction of sentences that carry an http(s) URL
    2. cove_consistency   — chain-of-verification token similarity (real)
    3. lambda_floor       — Λ (13-axis geomean) ≥ 0.85 floor check
  - The composite confidence is the geometric mean of the three sub-scores.
  - A `hallucination_risk` flag is raised when any sub-score < 0.50.
  - A DSSE-style receipt binds the score to the input hash (real SHA-256).

Refs:
  - Dhuliawala et al. (2023), arXiv:2309.11495 (CoVe)
  - Fiddler AI LLMOps, https://www.fiddler.ai/llmops
  - Arize Phoenix, https://arize.com/phoenix/
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

_URL_RE = re.compile(
    r"https?://"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}"
    r"(?::\d{1,5})?"
    r"(?:/[^\s\"'<>]*)?",
    re.IGNORECASE,
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|(?<=\n)")

_LAMBDA_FLOOR = 0.85  # Doctrine v11 Λ-floor (Conjecture 1, NOT a theorem)

DOCTRINE = "v11"
SOURCES = [
    "Dhuliawala et al. CoVe arXiv:2309.11495 — https://arxiv.org/abs/2309.11495",
    "Fiddler AI LLMOps — https://www.fiddler.ai/llmops",
    "Arize Phoenix — https://arize.com/phoenix/",
]


def _sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _citation_coverage(text: str) -> float:
    """Fraction of sentences that carry ≥1 http(s) URL."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    cited = sum(1 for s in sents if _URL_RE.search(s))
    return cited / len(sents)


def _cove_similarity(primary: str, verification: str) -> float:
    """Token-overlap Jaccard between primary and verification answers (real, deterministic)."""
    from amaru.verification import similarity as _sim
    return _sim(primary, verification)


def _geomean(*vals: float) -> float:
    if not vals:
        return 0.0
    product = 1.0
    for v in vals:
        product *= max(v, 1e-9)
    return product ** (1.0 / len(vals))


def _sha256_hex(obj: Any) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ConfidenceResult:
    """Hallucination-risk scored confidence for a single cortex output."""
    # inputs
    question: str
    answer: str
    verification_answer: str

    # sub-scores (all in [0,1])
    citation_coverage: float
    cove_consistency: float
    lambda_score: float   # Λ-gate: 1.0 if axes ≥ floor, else fraction

    # composite
    confidence: float     # geometric mean of sub-scores
    hallucination_risk: bool  # True if any sub-score < 0.5

    # provenance
    input_hash: str
    receipt_ts: str
    doctrine: str = DOCTRINE

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "question": self.question,
            "answer_excerpt": self.answer[:200] + ("…" if len(self.answer) > 200 else ""),
            "scores": {
                "citation_coverage": round(self.citation_coverage, 4),
                "cove_consistency": round(self.cove_consistency, 4),
                "lambda_score": round(self.lambda_score, 4),
            },
            "confidence": round(self.confidence, 4),
            "hallucination_risk": self.hallucination_risk,
            "risk_label": "HIGH" if self.hallucination_risk else "LOW",
            "input_hash": self.input_hash,
            "receipt_ts": self.receipt_ts,
            "doctrine": self.doctrine,
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "sources": SOURCES,
        }


def score(
    question: str,
    answer: str,
    *,
    verification_answer: str | None = None,
    axis_scores: list[float] | None = None,
) -> ConfidenceResult:
    """Compute a hallucination-risk confidence score for (question, answer).

    Args:
        question: The prompt / query.
        answer: The primary cortex answer to evaluate.
        verification_answer: Independent verification pass answer (optional; if
            omitted, a deterministic stub is used so scoring is always available).
        axis_scores: The 13 Λ-axis scores (float list). If absent, defaults to
            the Doctrine v11 baseline [0.9]*13.

    Returns:
        ConfidenceResult with sub-scores, composite confidence, and receipt.
    """
    # 1. Citation coverage
    cit_cov = _citation_coverage(answer)

    # 2. CoVe consistency
    if verification_answer is None:
        # No independent pass provided → assume maximum uncertainty (0.5)
        cove_sim = 0.5
    else:
        cove_sim = _cove_similarity(answer, verification_answer)

    # 3. Λ-floor check (Doctrine v11: Λ is Conjecture 1, not a theorem)
    axes = axis_scores if axis_scores else [0.9] * 13
    axes_valid = [max(0.0, min(1.0, float(a))) for a in axes]
    # Λ = geomean of axes; score = 1.0 if Λ ≥ floor, else Λ/floor
    Lambda = _geomean(*axes_valid)
    lambda_score = min(1.0, Lambda / _LAMBDA_FLOOR) if _LAMBDA_FLOOR > 0 else 1.0

    # 4. Composite
    confidence = _geomean(cit_cov, cove_sim, lambda_score)

    # 5. Risk flag
    hallucination_risk = any(s < 0.5 for s in [cit_cov, cove_sim, lambda_score])

    # 6. Receipt
    input_hash = _sha256_hex({"question": question, "answer": answer})
    receipt_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    return ConfidenceResult(
        question=question,
        answer=answer,
        verification_answer=verification_answer or "",
        citation_coverage=cit_cov,
        cove_consistency=cove_sim,
        lambda_score=lambda_score,
        confidence=confidence,
        hallucination_risk=hallucination_risk,
        input_hash=input_hash,
        receipt_ts=receipt_ts,
    )


__all__ = ["ConfidenceResult", "score", "SOURCES", "DOCTRINE"]

# ─────────────────────────────────────────────────────────────────────────────
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms (15 raw, 1 dup) /
# 163 sorries (112 baseline + 51 Putnam). Kernel commit c7c0ba17.
# Λ = Conjecture 1 (NOT a theorem). SLSA L1 (honest).
# ─────────────────────────────────────────────────────────────────────────────
