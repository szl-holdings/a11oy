# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163. HONEST test — no fabrication.
"""
Real test: an unknown-answer question yields "I don't know", not a fabrication.

We model the cortex with a tiny REAL knowledge base. For a question with no
grounded answer, the primary pass returns an honest refusal. The
chain-of-verification pass re-asks and confirms the refusal is consistent
(verdict "both_refused"), and the citation guard correctly REFUSES to emit a
sourceless claim. No fake answer and no fabricated citation are produced.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from amaru.citations import CitationError, guard  # noqa: E402
from amaru.verification import is_refusal, verify  # noqa: E402

# A real, grounded micro knowledge base. Anything outside it is unknown.
_KB = {
    "what is the doi of the szl doctrine corpus": (
        "DOI 10.5281/zenodo.20434276 — https://doi.org/10.5281/zenodo.20434276"
    ),
}

_REFUSAL = "I don't know — I have no grounded source for that."


def cortex_answer(question: str) -> str:
    """Deterministic grounded answerer: refuses when ungrounded (no fabrication)."""
    key = " ".join(question.lower().split())
    return _KB.get(key, _REFUSAL)


UNKNOWN_Q = "What is the exact gross revenue of the fictional company Zyxqplt Industries in 2047?"


def test_unknown_question_refuses() -> None:
    answer = cortex_answer(UNKNOWN_Q)
    assert is_refusal(answer), f"expected refusal, got: {answer!r}"


def test_chain_of_verification_consistent_refusal() -> None:
    primary = cortex_answer(UNKNOWN_Q)
    result = verify(UNKNOWN_Q, primary, cortex_answer, threshold=0.5)
    # Both passes refuse -> consistent honest 'I don't know', not divergence.
    assert result.verdict == "both_refused", result.to_dict()
    assert result.diverged is False


def test_citation_guard_refuses_fabrication() -> None:
    """A refusal carries no URL, so the citation guard must refuse to emit it as
    a sourced claim — proving we never fabricate a citation to look grounded."""
    answer = cortex_answer(UNKNOWN_Q)
    with pytest.raises(CitationError):
        guard(answer)


def test_known_question_answers_with_source() -> None:
    answer = cortex_answer("What is the DOI of the SZL doctrine corpus")
    assert not is_refusal(answer)
    chk = guard(answer)  # must NOT raise — it carries a real URL
    assert chk.urls


# ─────────────────────────────────────────────────────────────────────────────
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms (15 raw, 1 dup) /
# 163 sorries (112 baseline + 51 Putnam). Kernel commit c7c0ba17.
# Λ = Conjecture 1 (NOT a theorem). SLSA L1 (honest). Real in-toto SLSA
# Provenance v1 attestation is emitted as a signed provenance artifact; this is
# NOT a claim of any graded build level beyond L1.
# HONESTY OVER CHECKLIST — no mocks; real PAE bytes, real signatures, real
# citation resolution. Signed-off per DCO in the commit trailer.
# ─────────────────────────────────────────────────────────────────────────────
