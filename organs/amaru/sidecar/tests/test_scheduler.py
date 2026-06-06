"""Unit tests for the 7-chakra AmaruScheduler.

These exercise the scheduler class directly (not via the FastAPI surface) so
the canonical root->crown ascent, the ouroboros closure, receipt chaining,
tick counting, and upstream-scalar propagation are pinned independently of the
HTTP layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from amaru import CHAKRA_ORDER  # noqa: E402
from amaru.amaru_scheduler import AmaruScheduler, ChakraStep, TickResult  # noqa: E402
from amaru.receipts import GENESIS_PREV_HASH, ReceiptChain  # noqa: E402


_FULL_ENVELOPE = {
    "signals": {
        "grounded": 0.9, "integrity": 0.9,
        "novelty": 0.4, "fluency": 0.7,
        "intent": 0.8, "agency": 0.9, "friction": 0.1,
        "care": 0.8, "harm": 0.2,
        "clarity": 0.9, "truth": 0.9,
        "pattern_strength": 0.7, "uncertainty": 0.2,
    }
}


def _fresh() -> tuple[AmaruScheduler, ReceiptChain]:
    chain = ReceiptChain(operator_id="test-runtime")
    return AmaruScheduler(chain), chain


def test_tick_walks_canonical_root_to_crown_order() -> None:
    sched, _ = _fresh()
    result = sched.tick(_FULL_ENVELOPE)
    assert isinstance(result, TickResult)
    assert [s.chakra for s in result.steps] == list(CHAKRA_ORDER)
    assert result.steps[0].chakra == "root"
    assert result.steps[-1].chakra == "crown"


def test_tick_count_increments_monotonically() -> None:
    sched, _ = _fresh()
    assert sched.tick_count == 0
    first = sched.tick(_FULL_ENVELOPE)
    second = sched.tick(_FULL_ENVELOPE)
    assert first.tick_id == 1
    assert second.tick_id == 2
    assert sched.tick_count == 2


def test_tick_appends_one_receipt_per_chakra() -> None:
    sched, chain = _fresh()
    sched.tick(_FULL_ENVELOPE)
    # 7 chakras -> 7 receipts appended by the scheduler itself.
    assert chain.length() == len(CHAKRA_ORDER)
    receipts = chain.all()
    assert receipts[0].prev_hash == GENESIS_PREV_HASH
    # Sequential, hash-linked chain.
    for prev, cur in zip(receipts, receipts[1:]):
        assert cur.prev_hash == prev.self_hash
        assert cur.seq == prev.seq + 1


def test_receipt_seqs_recorded_on_each_step() -> None:
    sched, _ = _fresh()
    result = sched.tick(_FULL_ENVELOPE)
    seqs = [s.receipt_seq for s in result.steps]
    assert seqs == list(range(1, len(CHAKRA_ORDER) + 1))


def test_all_kernels_real_no_stub_or_error() -> None:
    sched, _ = _fresh()
    result = sched.tick(_FULL_ENVELOPE)
    assert all(s.stubbed is False for s in result.steps)
    assert all(s.error is None for s in result.steps)
    assert all(isinstance(s.output, dict) and "verdict" in s.output for s in result.steps)


def test_crown_produces_bounded_closure_and_ouroboros_handoff() -> None:
    sched, _ = _fresh()
    result = sched.tick(_FULL_ENVELOPE)
    assert result.closure is not None
    assert 0.0 <= result.closure <= 1.0
    assert result.handoff == {"to": "root", "via": "ouroboros"}


def test_empty_envelope_still_completes_full_ascent() -> None:
    # A tick with no signals must still walk all 7 chakras and chain receipts
    # rather than aborting partway.
    sched, chain = _fresh()
    result = sched.tick(None)
    assert [s.chakra for s in result.steps] == list(CHAKRA_ORDER)
    assert chain.length() == len(CHAKRA_ORDER)


def test_upstream_scalars_propagate_into_crown_step() -> None:
    # Numeric kernel outputs from lower chakras must be visible to crown via
    # the rolling upstream dict (this is what feeds the closure computation).
    sched, _ = _fresh()
    result = sched.tick(_FULL_ENVELOPE)
    crown = result.steps[-1]
    assert crown.chakra == "crown"
    assert crown.output is not None
    # Crown reports how many upstream scalars it integrated.
    assert crown.output.get("n_upstream_scalars", 0) >= 1


def test_two_ticks_extend_one_continuous_chain() -> None:
    sched, chain = _fresh()
    sched.tick(_FULL_ENVELOPE)
    sched.tick(_FULL_ENVELOPE)
    assert chain.length() == 2 * len(CHAKRA_ORDER)
    receipts = chain.all()
    for prev, cur in zip(receipts, receipts[1:]):
        assert cur.prev_hash == prev.self_hash


def test_chakra_step_dataclass_shape() -> None:
    step = ChakraStep(chakra="root", output={"verdict": "ground"}, error=None, stubbed=False, receipt_seq=1)
    assert step.chakra == "root"
    assert step.receipt_seq == 1
    assert step.stubbed is False
