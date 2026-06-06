"""
Binding-drift guard — receipt_replay.py (Watunakuy Strike 1)

These tests assert that the @lean_theorem annotation in receipt_replay.py
cites a REAL theorem that exists in Lutar/PRNG/K10v2_ReplayRoot.lean, and
that @lean_status is not falsely GREEN.

PhD-Math finding F4 (HIGH, 2026-05-31): the prior annotation cited
"prng_replay_root_deterministic" which does NOT exist in K10v2_ReplayRoot.lean.
The file uses True-shell obligations (def xxx := True; proved by trivial) —
axiom-free and sorry-free, but logically vacuous. This is the "Prop := True;
proof := trivial" anti-pattern explicitly banned by Watunakuy §The Forbidden Tests.

These tests will FAIL if someone re-introduces the false annotation.

Lean corpus reference: 749 declarations / 14 unique axioms / 163 sorries
@ c7c0ba17 (canonical HEAD 2026-05-31).

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import re
import os
import hashlib
import pytest

# Path to source file under test
SRC_FILE = os.path.join(
    os.path.dirname(__file__), "..", "src", "replay", "receipt_replay.py"
)


# ---------------------------------------------------------------------------
# Helpers: read source annotation
# ---------------------------------------------------------------------------

def _read_src() -> str:
    with open(SRC_FILE, "r") as f:
        return f.read()


def _get_annotation(src: str, tag: str) -> str:
    """Extract the value after a @lean_xxx: annotation tag."""
    pattern = rf"@{tag}:\s+(\S+)"
    m = re.search(pattern, src)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Strike 1 — Binding annotation integrity tests
# ---------------------------------------------------------------------------

class TestLeanBindingAnnotation:
    """PhD-Math F4: receipt_replay.py false-GREEN annotation guard."""

    def test_lean_theorem_must_not_cite_nonexistent_name(self):
        """@lean_theorem must NOT cite 'prng_replay_root_deterministic'.

        This identifier does not exist in K10v2_ReplayRoot.lean at c7c0ba17.
        PhD-Math Pass 1 Binding #14 confirms absence via grep.
        """
        src = _read_src()
        theorem = _get_annotation(src, "lean_theorem")
        assert "prng_replay_root_deterministic" not in theorem, (
            "BINDING DRIFT: 'prng_replay_root_deterministic' does not exist in "
            "Lutar/PRNG/K10v2_ReplayRoot.lean. Restore requires implementing "
            "the theorem in lutar-lean first. PhD-Math F4."
        )

    def test_lean_theorem_must_cite_a_real_identifier(self):
        """@lean_theorem must cite one of the real identifiers in K10v2_ReplayRoot.lean.

        Real identifiers at c7c0ba17 (non-vacuous preferred; vacuous listed for reference):
          - isReplayRoot_correct_obligation_tracked (trivial — vacuous but real)
          - replayRoot_unique_in_list_obligation_tracked (trivial — vacuous)
          - findReplayRoot_sound_obligation_tracked (trivial — vacuous)
          - findReplayRoot_complete_obligation_tracked (trivial — vacuous)
          - xoshiro_period_bound_obligation_tracked (trivial — vacuous)
          - xoshiroOutput_eq_of_state_eq (real proof from h : s = t)
          - generateOutputs_eq_of_eq (real proof from h : s = t)
        Note: all _obligation_tracked theorems are True-shells (Watunakuy §Forbidden).
        They are listed here so the test accepts them while they exist; the @lean_todo
        is to replace them with substantive proofs.
        """
        src = _read_src()
        theorem = _get_annotation(src, "lean_theorem")
        short = theorem.split(".")[-1]
        KNOWN_REAL_IDENTIFIERS = {
            "isReplayRoot_correct_obligation_tracked",
            "replayRoot_unique_in_list_obligation_tracked",
            "findReplayRoot_sound_obligation_tracked",
            "findReplayRoot_complete_obligation_tracked",
            "xoshiro_period_bound_obligation_tracked",
            "xoshiroOutput_eq_of_state_eq",
            "generateOutputs_eq_of_eq",
            # Future: add real prng_replay_root_deterministic once implemented
        }
        assert short in KNOWN_REAL_IDENTIFIERS, (
            f"@lean_theorem '{theorem}' (short: '{short}') is not a known real identifier "
            f"in K10v2_ReplayRoot.lean at c7c0ba17. Valid: {sorted(KNOWN_REAL_IDENTIFIERS)}"
        )

    def test_lean_status_must_not_be_bare_green(self):
        """@lean_status must NOT be 'GREEN' while theorem is vacuous or absent.

        All K10v2_ReplayRoot.lean substantive obligations are True-shells.
        GREEN is a fake-green doctrine violation (§2) until a real proof exists.
        """
        src = _read_src()
        status = _get_annotation(src, "lean_status")
        assert status != "GREEN", (
            "BINDING DRIFT: @lean_status is falsely GREEN. "
            "K10v2_ReplayRoot.lean uses True-shell obligations (Prop := True; trivial). "
            "This is the pattern banned by Watunakuy §The Forbidden Tests. "
            "Status must be UNVERIFIED until a real proof exists. PhD-Math F4."
        )

    def test_receipt_dict_must_not_cite_nonexistent_theorem(self):
        """The lean_theorem field in runtime receipt dicts must not cite the absent name.

        Note: "prng_replay_root_deterministic" is allowed as:
          - A comment / @lean_todo annotation (documentation of the goal)
          - The "formula" label (short name for the receipt formula, not a Lean theorem)
        It must NOT appear as a value of the "lean_theorem" key in runtime code.
        """
        src = _read_src()
        import ast
        # Parse the source and find all string literals assigned to lean_theorem keys.
        # This is more reliable than regex on the raw source.
        # Simpler approach: look for the pattern "lean_theorem": "<value>" in non-comment lines
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("@") or stripped.startswith("*"):
                continue  # skip comments and docstring annotations
            if '"lean_theorem"' in stripped and "prng_replay_root_deterministic" in stripped:
                raise AssertionError(
                    f"BINDING DRIFT: lean_theorem runtime field still cites the "
                    f"non-existent theorem name on line:\n  {line}\n"
                    "This propagates a false provenance claim to all DSSE receipts. "
                    "PhD-Math F4."
                )
            if "'lean_theorem'" in stripped and "prng_replay_root_deterministic" in stripped:
                raise AssertionError(
                    f"BINDING DRIFT (single-quote): lean_theorem runtime field cites "
                    f"absent theorem name on line:\n  {line}"
                )


# ---------------------------------------------------------------------------
# Strike 1 — Behavioral correctness (regression guard)
# The PRNG determinism claim IS behaviorally correct (HMAC-SHA256 is deterministic).
# These tests guard the TS implementation's behavior regardless of Lean status.
# ---------------------------------------------------------------------------

class TestK10v2PrngBehavioral:
    """Behavioral regression for k10v2_prng — PRNG is deterministic in root."""

    def _import_module(self):
        from src.replay.receipt_replay import k10v2_prng, replay_chain, verify_chain
        return k10v2_prng, replay_chain, verify_chain

    def test_happy_path_deterministic_same_root_same_index(self):
        k10v2_prng, _, _ = self._import_module()
        root = "a" * 64
        assert k10v2_prng(root, 0) == k10v2_prng(root, 0)
        assert k10v2_prng(root, 5) == k10v2_prng(root, 5)

    def test_edge_case_index_0_reproducible(self):
        k10v2_prng, _, _ = self._import_module()
        root = "0" * 64
        result = k10v2_prng(root, 0)
        assert len(result) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in result)

    def test_failure_path_bad_root_length(self):
        k10v2_prng, _, _ = self._import_module()
        with pytest.raises(ValueError, match="64-char hex"):
            k10v2_prng("short", 0)


# ---------------------------------------------------------------------------
# Strike 4 — Property tests: PRNG determinism over N=100 random roots
# ---------------------------------------------------------------------------

class TestK10v2PrngPropertyDeterminism:
    """Strike 4: determinism holds across 100 random roots (Watunakuy §Property)."""

    def _import_module(self):
        from src.replay.receipt_replay import k10v2_prng, replay_chain, verify_chain
        return k10v2_prng, replay_chain, verify_chain

    def test_100_random_roots_same_output_on_repeat(self):
        """k10v2_prng(root, i) == k10v2_prng(root, i) for 100 random roots."""
        k10v2_prng, _, _ = self._import_module()
        for _ in range(100):
            root = hashlib.sha256(os.urandom(32)).hexdigest()
            idx = int.from_bytes(os.urandom(2), "little") % 50
            v1 = k10v2_prng(root, idx)
            v2 = k10v2_prng(root, idx)
            assert v1 == v2, f"Non-determinism detected at root={root[:8]}..., index={idx}"

    def test_100_replay_chains_verify_cleanly(self):
        """replay_chain(root, n) verifies against itself for 100 random roots."""
        _, replay_chain, verify_chain = self._import_module()
        for _ in range(100):
            root = hashlib.sha256(os.urandom(32)).hexdigest()
            chain = replay_chain(root, 10)
            refs = [{"value": r.value} for r in chain.receipts]
            result = verify_chain(root, refs)
            assert result.verified, (
                f"Self-verification failed for root={root[:8]}...: "
                f"{result.n_mismatches} mismatches"
            )

    def test_single_bit_flip_detected(self):
        """A 1-bit flip in any receipt value is detected by verify_chain."""
        _, replay_chain, verify_chain = self._import_module()
        root = hashlib.sha256(b"test-root-for-flip").hexdigest()
        chain = replay_chain(root, 5)
        refs = [{"value": r.value} for r in chain.receipts]
        # Flip one bit in receipt at index 2
        original = refs[2]["value"]
        flipped = bytearray(bytes.fromhex(original))
        flipped[0] ^= 0x01
        refs[2]["value"] = flipped.hex()
        result = verify_chain(root, refs)
        assert not result.verified
        assert result.n_mismatches == 1
        assert result.first_mismatch_index == 2
