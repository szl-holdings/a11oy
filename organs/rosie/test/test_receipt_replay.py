"""
Tests for Receipt Replay Module — K10v2 PRNG Determinism
Lean theorem: Lutar.PRNG.K10v2ReplayRoot.prng_replay_root_deterministic (GREEN)

Properties:
  1. Same root replays identically (determinism)
  2. Verification mode detects 1-bit mutations
"""

import hashlib
import json
import random
import pytest

from src.replay.receipt_replay import (
    k10v2_prng,
    replay_chain,
    verify_chain,
    ReplayChain,
    VerifyResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def random_root() -> str:
    """Generate a random 64-char hex SHA-256-like root."""
    return hashlib.sha256(random.randbytes(32)).hexdigest()


def flip_bit_in_hex(hex_str: str, byte_index: int) -> str:
    """Flip one bit in a hex-encoded string at byte_index."""
    b = bytearray(bytes.fromhex(hex_str))
    b[byte_index % len(b)] ^= 0x01
    return b.hex()


# ---------------------------------------------------------------------------
# k10v2_prng unit tests
# ---------------------------------------------------------------------------


class TestK10v2Prng:
    def test_deterministic_same_root_same_index(self):
        root = "a" * 64
        v1 = k10v2_prng(root, 0)
        v2 = k10v2_prng(root, 0)
        assert v1 == v2

    def test_different_index_different_value(self):
        root = "b" * 64
        assert k10v2_prng(root, 0) != k10v2_prng(root, 1)

    def test_different_root_different_value(self):
        root1 = "c" * 64
        root2 = "d" * 64
        assert k10v2_prng(root1, 0) != k10v2_prng(root2, 0)

    def test_output_is_64_char_hex(self):
        root = "e" * 64
        v = k10v2_prng(root, 42)
        assert len(v) == 64
        assert all(c in "0123456789abcdef" for c in v)

    def test_invalid_root_raises(self):
        with pytest.raises(ValueError, match="64-char hex"):
            k10v2_prng("short", 0)

    def test_sequential_indices_all_distinct(self):
        root = random_root()
        values = [k10v2_prng(root, i) for i in range(100)]
        assert len(set(values)) == 100  # all distinct (HMAC-SHA256 collision-resistance)


# ---------------------------------------------------------------------------
# replay_chain tests
# ---------------------------------------------------------------------------


class TestReplayChain:
    def test_replay_deterministic(self):
        root = random_root()
        chain1 = replay_chain(root, 50)
        chain2 = replay_chain(root, 50)
        assert [r.value for r in chain1.receipts] == [r.value for r in chain2.receipts]

    def test_different_roots_different_chains(self):
        root1, root2 = random_root(), random_root()
        c1 = replay_chain(root1, 20)
        c2 = replay_chain(root2, 20)
        assert [r.value for r in c1.receipts] != [r.value for r in c2.receipts]

    def test_receipt_count_matches_length(self):
        root = random_root()
        n = 37
        chain = replay_chain(root, n)
        assert len(chain.receipts) == n

    def test_zero_length(self):
        chain = replay_chain(random_root(), 0)
        assert chain.receipts == []
        assert chain.length == 0

    def test_receipt_contains_lean_theorem(self):
        # Per PhD-Math F4 (rosie #80) — @lean_theorem was downgraded from the
        # nonexistent 'prng_replay_root_deterministic' to the real (but trivial)
        # 'isReplayRoot_correct_obligation_tracked' identifier at c7c0ba17.
        # Status: UNVERIFIED until K10v2 obligations are discharged (lutar-lean #137).
        chain = replay_chain(random_root(), 3)
        for r in chain.receipts:
            assert r.lean_theorem == (
                "Lutar.PRNG.K10v2ReplayRoot.isReplayRoot_correct_obligation_tracked"
            )

    def test_dsse_receipt_fields(self):
        chain = replay_chain(random_root(), 5)
        dsse = chain.dsse_receipt
        assert dsse["formula"] == "prng_replay_root_deterministic"
        assert dsse["lean_file"] == "Lutar/PRNG/K10v2_ReplayRoot.lean"
        assert len(dsse["inputs_hash"]) == 64
        assert "ts" in dsse

    def test_negative_length_raises(self):
        with pytest.raises(ValueError):
            replay_chain(random_root(), -1)


# ---------------------------------------------------------------------------
# verify_chain tests
# ---------------------------------------------------------------------------


class TestVerifyChain:
    def test_correct_chain_verifies(self):
        root = random_root()
        chain = replay_chain(root, 20)
        reference = [{"value": r.value} for r in chain.receipts]
        result = verify_chain(root, reference)
        assert result.verified
        assert result.n_mismatches == 0

    def test_single_bit_mutation_detected(self):
        root = random_root()
        chain = replay_chain(root, 10)
        reference = [{"value": r.value} for r in chain.receipts]
        # Flip 1 bit in entry at index 5
        mutated_value = flip_bit_in_hex(reference[5]["value"], 3)
        reference[5] = {"value": mutated_value}
        result = verify_chain(root, reference)
        assert not result.verified
        assert result.n_mismatches >= 1
        assert result.first_mismatch_index == 5

    def test_all_entries_mutated_detected(self):
        root = random_root()
        chain = replay_chain(root, 5)
        reference = [{"value": flip_bit_in_hex(r.value, 0)} for r in chain.receipts]
        result = verify_chain(root, reference)
        assert not result.verified
        assert result.n_mismatches == 5

    def test_empty_reference(self):
        result = verify_chain(random_root(), [])
        assert result.verified
        assert result.n_checked == 0

    def test_verify_dsse_receipt(self):
        root = random_root()
        chain = replay_chain(root, 3)
        reference = [{"value": r.value} for r in chain.receipts]
        result = verify_chain(root, reference)
        dsse = result.dsse_receipt
        # Per PhD-Math F4 (rosie #80) — see test_receipt_contains_lean_theorem above.
        assert dsse["lean_theorem"] == (
            "Lutar.PRNG.K10v2ReplayRoot.isReplayRoot_correct_obligation_tracked"
        )
        assert dsse["output"]["verified"] is True


# ---------------------------------------------------------------------------
# Fuzz: 1000 random replays
# ---------------------------------------------------------------------------


class TestFuzz:
    def test_1000_replays_deterministic(self):
        """Same root always produces the same chain — theorem fuzz."""
        random.seed(777)
        for _ in range(1000):
            root = random_root()
            n = random.randint(1, 20)
            c1 = replay_chain(root, n)
            c2 = replay_chain(root, n)
            assert [r.value for r in c1.receipts] == [r.value for r in c2.receipts]

    def test_1000_single_mutation_detections(self):
        """1-bit mutations are always detected."""
        random.seed(888)
        detections = 0
        for _ in range(1000):
            root = random_root()
            n = random.randint(2, 10)
            chain = replay_chain(root, n)
            reference = [{"value": r.value} for r in chain.receipts]
            mut_idx = random.randint(0, n - 1)
            reference[mut_idx] = {"value": flip_bit_in_hex(reference[mut_idx]["value"], 0)}
            result = verify_chain(root, reference)
            if not result.verified:
                detections += 1
        assert detections == 1000
