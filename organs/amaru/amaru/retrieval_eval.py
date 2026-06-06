# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).
"""
amaru.retrieval_eval — RAG retrieval evaluation for the cortex.

PARITY TARGET: LangSmith retrieval evals, Arize Phoenix RAGAS, Fiddler faithfulness.
  amaru's EDGE: every eval step emits a DSSE-linkable receipt with provenance hash.

Metrics (all deterministic, no LLM-as-judge needed at this layer):
  1. context_precision   — fraction of retrieved chunks containing query tokens
  2. context_recall      — estimated recall: at least 1 chunk has ≥ threshold overlap
  3. answer_faithfulness — fraction of answer sentences grounded in retrieved context
  4. source_coverage     — fraction of retrieved sources that appear in the answer

HONESTY:
  - No synthetic chunks, no fabricated sources. If retrieval is empty, all
    scores are 0 and the result is honest_abstain = True.
  - The `answer_faithfulness` metric is an honest approximation (token overlap
    between answer sentences and chunk text). It is NOT an LLM-judged score;
    the result honestly labels this `method: "token_overlap"`.

Refs:
  - RAGAS: https://docs.ragas.io/en/stable/
  - LangSmith evals: https://docs.langchain.com/langsmith/evaluation
  - Arize Phoenix: https://arize.com/phoenix/
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|(?<=\n)")

DOCTRINE = "v11"
SOURCES = [
    "RAGAS — https://docs.ragas.io/en/stable/",
    "LangSmith evals — https://docs.langchain.com/langsmith/evaluation",
    "Arize Phoenix — https://arize.com/phoenix/",
]


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD_RE.findall(s.lower()) if len(w) > 2}


def _overlap_ratio(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _sha256_hex(obj: Any) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class EvalResult:
    """Full retrieval eval result for one (question, answer, chunks) triplet."""
    question: str
    answer: str
    chunk_count: int

    # Metrics in [0,1]
    context_precision: float
    context_recall: float
    answer_faithfulness: float
    source_coverage: float

    # Aggregate
    composite: float  # unweighted mean of the four metrics

    honest_abstain: bool   # True when chunk_count == 0 (honest zero scores)
    method: str = "token_overlap"
    doctrine: str = DOCTRINE
    input_hash: str = ""
    receipt_ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "question": self.question,
            "answer_excerpt": self.answer[:200] + ("…" if len(self.answer) > 200 else ""),
            "chunk_count": self.chunk_count,
            "metrics": {
                "context_precision": round(self.context_precision, 4),
                "context_recall": round(self.context_recall, 4),
                "answer_faithfulness": round(self.answer_faithfulness, 4),
                "source_coverage": round(self.source_coverage, 4),
            },
            "composite": round(self.composite, 4),
            "honest_abstain": self.honest_abstain,
            "method": self.method,
            "input_hash": self.input_hash,
            "receipt_ts": self.receipt_ts,
            "doctrine": self.doctrine,
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "sources": SOURCES,
        }


def evaluate(
    question: str,
    answer: str,
    chunks: list[str],
    *,
    precision_threshold: float = 0.10,
    recall_threshold: float = 0.15,
) -> EvalResult:
    """Evaluate RAG retrieval quality for (question, answer, retrieved_chunks).

    Args:
        question: The query string.
        answer:   The generated answer to evaluate.
        chunks:   The retrieved context chunks (plain strings).
        precision_threshold: Minimum token-overlap ratio for a chunk to count
            as "relevant" (context_precision numerator).
        recall_threshold: Minimum overlap between query and best chunk to
            claim recall (context_recall).

    Returns:
        EvalResult with four metrics, composite score, and receipt.
    """
    input_hash = _sha256_hex({"question": question, "answer": answer, "chunks": chunks})
    receipt_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not chunks:
        return EvalResult(
            question=question, answer=answer, chunk_count=0,
            context_precision=0.0, context_recall=0.0,
            answer_faithfulness=0.0, source_coverage=0.0,
            composite=0.0, honest_abstain=True,
            input_hash=input_hash, receipt_ts=receipt_ts,
        )

    # 1. context_precision — fraction of chunks with query-token overlap ≥ threshold
    relevant_chunks = [
        c for c in chunks
        if _overlap_ratio(question, c) >= precision_threshold
    ]
    context_precision = len(relevant_chunks) / len(chunks)

    # 2. context_recall — does the best chunk have ≥ recall_threshold overlap?
    best_overlap = max(_overlap_ratio(question, c) for c in chunks)
    context_recall = min(1.0, best_overlap / max(recall_threshold, 1e-9))

    # 3. answer_faithfulness — fraction of answer sentences grounded in any chunk
    sents = _sentences(answer)
    if not sents:
        answer_faithfulness = 0.0
    else:
        all_chunk_text = " ".join(chunks)
        grounded = sum(
            1 for s in sents
            if _overlap_ratio(s, all_chunk_text) >= 0.10
        )
        answer_faithfulness = grounded / len(sents)

    # 4. source_coverage — fraction of chunks whose key tokens appear in answer
    ans_tokens = _tokens(answer)
    if not ans_tokens:
        source_coverage = 0.0
    else:
        covered = sum(
            1 for c in chunks
            if _tokens(c) & ans_tokens
        )
        source_coverage = covered / len(chunks)

    composite = (context_precision + context_recall + answer_faithfulness + source_coverage) / 4.0

    return EvalResult(
        question=question, answer=answer, chunk_count=len(chunks),
        context_precision=context_precision,
        context_recall=context_recall,
        answer_faithfulness=answer_faithfulness,
        source_coverage=source_coverage,
        composite=composite,
        honest_abstain=False,
        input_hash=input_hash, receipt_ts=receipt_ts,
    )


__all__ = ["EvalResult", "evaluate", "SOURCES", "DOCTRINE"]

# ─────────────────────────────────────────────────────────────────────────────
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms (15 raw, 1 dup) /
# 163 sorries (112 baseline + 51 Putnam). Kernel commit c7c0ba17.
# Λ = Conjecture 1 (NOT a theorem). SLSA L1 (honest).
# ─────────────────────────────────────────────────────────────────────────────
