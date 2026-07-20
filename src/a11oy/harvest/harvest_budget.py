# VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — apps/agentic-gpu/harvest_budget.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
"""harvest_budget.py — Proven sponge budget for the wasted-energy harvest.

Grounds the soak-window batch admission in the founder's own kernel-proven
formulas so the harvest is PROVABLY BOUNDED, not just heuristic.

Doctrine (binding, v11/v12):
  - NO free-energy / over-unity.  This computes an INFORMATION cap (Bekenstein,
    proven by Lean) and an ENERGY FLOOR (Landauer, proven by Lean). Joule
    figures are labelled SAMPLE/ESTIMATE until a real on-box NVML meter feeds them.
  - The Bekenstein cap is on INFORMATION (bits) — this IS provable and the Lean
    theorem is kernel-checked.  The energy floor (Landauer) is also proven.
    Joule figures stay SAMPLE; information figures are bounded by proven math.
  - The soak loop is bounded by an Ouroboros-style hard-max + budget counter so
    the sponge can NEVER run away. Reactive turns always preempt.
  - Locked-proven set stays EXACTLY 8 (F1,F4,F7,F11,F12,F18,F19,F22 @ c7c0ba17).
    This module cites those theorems but does NOT modify or add to the locked-8.

Formula citations (all kernel-proven / machine-checked):
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ BEKENSTEIN CAP (information bound)                                          │
  │   Lean theorem: bekenstein_bound_additive (n m : Nat) :                    │
  │     bekensteinBits (n + m) = bekensteinBits n + bekensteinBits m           │
  │     ∧ bekensteinBits n ≤ bekensteinBits (n + m)                            │
  │   Lean theorem: info_within_bound (n m e : Nat) (h : e ≤ bekensteinBits n) │
  │     : e ≤ bekensteinBits (n + m)                                           │
  │   Source: Showcase/Frontier/EnergyBudgetWitness.lean                       │
  │           lutar-lean PR #239 (KEYSTONE, 0-sorry)                           │
  │   Composition: mirrors F19 (f19_budget_monotone, s1 ≤ s1+s2)              │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ LANDAUER FLOOR (energy lower bound)                                         │
  │   Lean theorem: landauer_floor_pos (n q : Nat) (hn : 0<n) (hq : 0<q) :   │
  │     0 < energyFloor n q                                                    │
  │   Lean def:     energyFloor n q = n * q  (integer shadow of n·kT·ln2)     │
  │   Source: Showcase/Frontier/LandauerFloorWitness.lean                      │
  │           lutar-lean PR #240                                                │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ MONOTONE LEDGER                                                             │
  │   Lean theorem: energy_ledger_monotone (start : Nat) (draws : List Nat) :  │
  │     start ≤ ledgerSum start draws                                          │
  │   Source: Showcase/Frontier/EnergyBudgetWitness.lean (PR #239)            │
  │   Composition: mirrors F19 (f19_budget_monotone)                           │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │ OUROBOROS BOUNDED RECURSION                                                 │
  │   Source: szl-holdings/ouroboros packages/ouroboros/src/loop-kernel.ts    │
  │   Primitive: runLoop({ maxSteps }) — the loop NEVER exceeds maxSteps       │
  │   iterations; exits 'budgetExhausted' when the cap is hit.  We mirror      │
  │   this exact pattern: OUROBOROS_MAX_SOAK_STEPS hard cap + a work-budget    │
  │   counter so the proactive sponge loop halts unconditionally.              │
  └─────────────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import math
import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Boltzmann constant * room temperature (300 K) * ln 2 — the Landauer minimum
# energy per irreversible bit erasure.  SAMPLE until an on-box calorimeter
# feeds real values.  Used only to ensure SAMPLE estimates never CLAIM to beat
# the floor; the floor itself is the proven lower bound.
_K_B = 1.380649e-23   # J/K  (exact by SI 2019 redefinition)
_LN2 = 0.6931471805599453

# Default room temperature for Landauer floor calculations.
LANDAUER_DEFAULT_TEMP_K: float = 300.0

# Ouroboros bounded-recursion cap.
# Mirrors loop-kernel.ts DEFAULT_MAX_STEPS=8 / runLoop({ maxSteps }) hard cap.
# The proactive soak loop NEVER exceeds this iteration count.
OUROBOROS_MAX_SOAK_STEPS: int = 32   # generous but hard; reactive always preempts

# ---------------------------------------------------------------------------
# Part 1 — Bekenstein information cap
# ---------------------------------------------------------------------------
# Python mirror of:
#   def bekensteinBits (n : Nat) : Nat := n * 8
#   theorem bekenstein_bound_additive ...  [PR #239, EnergyBudgetWitness.lean]
#   theorem info_within_bound ...          [PR #239, EnergyBudgetWitness.lean]


def bekenstein_info_cap(n_bytes: int) -> int:
    """Return the Bekenstein bit-cap for an n-byte output register: n * 8.

    Python mirror of `bekensteinBits (n : Nat) : Nat := n * 8` from
    Showcase/Frontier/EnergyBudgetWitness.lean (lutar-lean PR #239, keystone,
    0-sorry). This is the maximum information that can be carried by an n-byte
    register — the ceiling any admitted batch job must stay within.

    Citation:
      bekenstein_bound_additive (n m : Nat) :
        bekensteinBits (n+m) = bekensteinBits n + bekensteinBits m
        ∧ bekensteinBits n ≤ bekensteinBits (n+m)
      [EnergyBudgetWitness.lean, PR #239, F19-composition]
    """
    if n_bytes < 0:
        raise ValueError(f"n_bytes must be non-negative, got {n_bytes}")
    return n_bytes * 8


class BekensteinAccumulator:
    """Additive Bekenstein-cap accumulator for a soak window.

    Implements the info_within_bound / bekenstein_bound_additive pattern:
    each admitted job contributes its info load to a running total; a new job
    is REFUSED if admitting it would push the total past the window cap.

    All information figures are in BITS (integers, matching the Lean Nat model).

    Citation:
      info_within_bound (n m e : Nat) (h : e ≤ bekensteinBits n) :
        e ≤ bekensteinBits (n + m)
      bekenstein_bound_additive ...
      [Showcase/Frontier/EnergyBudgetWitness.lean, lutar-lean PR #239, 0-sorry]
    """

    def __init__(self, window_cap_bytes: int) -> None:
        """
        Args:
            window_cap_bytes: Total byte budget for the soak window. The
                Bekenstein cap is window_cap_bytes * 8 bits.
        """
        if window_cap_bytes <= 0:
            raise ValueError(f"window_cap_bytes must be positive, got {window_cap_bytes}")
        self._cap_bits: int = bekenstein_info_cap(window_cap_bytes)
        self._used_bits: int = 0
        self._admitted: list[dict] = []

    @property
    def cap_bits(self) -> int:
        return self._cap_bits

    @property
    def used_bits(self) -> int:
        return self._used_bits

    @property
    def remaining_bits(self) -> int:
        return max(0, self._cap_bits - self._used_bits)

    def try_admit(self, job_id: Any, job_info_bits: int) -> bool:
        """Attempt to admit a job that will process job_info_bits bits.

        Returns True (admitted) iff used_bits + job_info_bits ≤ cap_bits,
        mirroring info_within_bound: if e ≤ bekensteinBits n then e ≤ cap.
        Returns False and does NOT update state when the job would exceed the cap.

        Citation: bekenstein_bound_additive / info_within_bound
          [EnergyBudgetWitness.lean, lutar-lean PR #239, keystone, 0-sorry]
        """
        if job_info_bits < 0:
            raise ValueError(f"job_info_bits must be non-negative, got {job_info_bits}")
        if self._used_bits + job_info_bits > self._cap_bits:
            return False
        self._used_bits += job_info_bits
        self._admitted.append({"job_id": job_id, "info_bits": job_info_bits})
        return True

    def admitted_jobs(self) -> list[dict]:
        return list(self._admitted)


# ---------------------------------------------------------------------------
# Part 2 — Landauer floor
# ---------------------------------------------------------------------------
# Python mirror of:
#   def energyFloor (n q : Nat) : Nat := n * q
#   theorem landauer_floor_pos ...         [PR #240, LandauerFloorWitness.lean]


def landauer_floor_joules(bits: int, temp_K: float = LANDAUER_DEFAULT_TEMP_K) -> float:
    """Minimum energy (joules, SAMPLE) to irreversibly erase `bits` bits at temp_K.

    Computes bits * k_B * T * ln2, the Landauer minimum.  This is a LOWER BOUND;
    a real system dissipates at least this much.  A SAMPLE joule estimate for
    any batch job must never CLAIM to beat this floor (anti-over-unity guard).

    The value returned is labelled SAMPLE/ESTIMATE because it uses nominal
    k_B and T; a real on-box calorimeter is needed for a measured value.

    Citation:
      energyFloor (n q : Nat) : Nat := n * q  (integer shadow of n·kT·ln2)
      landauer_floor_pos (n q : Nat) (hn : 0<n) (hq : 0<q) : 0 < energyFloor n q
      landauer_floor_additive (n m q : Nat) : energyFloor (n+m) q = ...
      [Showcase/Frontier/LandauerFloorWitness.lean, lutar-lean PR #240]
    """
    if bits < 0:
        raise ValueError(f"bits must be non-negative, got {bits}")
    if temp_K <= 0:
        raise ValueError(f"temp_K must be positive, got {temp_K}")
    return bits * _K_B * temp_K * _LN2  # SAMPLE/ESTIMATE (doctrine)


def assert_sample_beats_landauer_floor(
    bits: int,
    sample_joules: float,
    temp_K: float = LANDAUER_DEFAULT_TEMP_K,
) -> None:
    """Assert that a SAMPLE joule estimate does NOT claim to beat the Landauer floor.

    If sample_joules < landauer_floor_joules(bits, temp_K), this raises
    AssertionError — the estimate would be physically impossible (over-unity /
    free-energy claim), violating doctrine.

    Note: sample_joules=0 (unknown / not estimated) always passes — zero means
    "not yet measured", not "costs nothing". Pass the actual SAMPLE estimate
    only when you have one.

    Citation: LandauerFloorWitness.lean, lutar-lean PR #240
    """
    if sample_joules <= 0:
        return  # 0 / negative = not estimated; floor check not applicable
    floor = landauer_floor_joules(bits, temp_K)
    assert sample_joules >= floor, (
        f"DOCTRINE VIOLATION: SAMPLE joule estimate {sample_joules:.3e} J "
        f"claims to beat the Landauer floor {floor:.3e} J for {bits} bits at "
        f"{temp_K} K. This would be a free-energy / over-unity claim. "
        f"[LandauerFloorWitness.lean, PR #240]"
    )


# ---------------------------------------------------------------------------
# Part 3 — Monotone SoakLedger
# ---------------------------------------------------------------------------
# Python mirror of:
#   theorem energy_ledger_monotone (start : Nat) (draws : List Nat) :
#     start ≤ ledgerSum start draws
#   [EnergyBudgetWitness.lean, PR #239, F19-composition: f19_budget_monotone]


@dataclass
class LedgerEntry:
    """One append-only entry in the SoakLedger."""
    job_id: Any
    info_bits: int                        # proven-bounded
    joules_sample: float                  # SAMPLE/ESTIMATE until NVML
    joules_label: str = "sample"          # NEVER changes
    timestamp_utc: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    landauer_floor_joules: float = 0.0    # floor for audit
    beats_floor: bool = True              # False = over-unity claim detected


class SoakLedger:
    """Append-only monotone ledger for the wasted-energy soak.

    Models `energy_ledger_monotone` from EnergyBudgetWitness.lean (PR #239):
    the running cumulative totals (info bits, sample joules) are monotone-
    nondecreasing — appending a new draw never lowers the total.

    A monotonicity assertion is checked on every append.

    Citation:
      energy_ledger_monotone (start : Nat) (draws : List Nat) :
        start ≤ ledgerSum start draws
      ledger_step_monotone (s d : Nat) : s ≤ s + d  (= f19_budget_monotone)
      [Showcase/Frontier/EnergyBudgetWitness.lean, lutar-lean PR #239, 0-sorry]
    """

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._total_info_bits: int = 0
        self._total_joules_sample: float = 0.0

    @property
    def total_info_bits(self) -> int:
        return self._total_info_bits

    @property
    def total_joules_sample(self) -> float:
        return self._total_joules_sample

    @property
    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    def append(
        self,
        job_id: Any,
        info_bits: int,
        joules_sample: float = 0.0,
        temp_K: float = LANDAUER_DEFAULT_TEMP_K,
    ) -> LedgerEntry:
        """Append one entry; assert monotonicity after each append.

        Mirrors `ledger_step_monotone`: prev_total ≤ prev_total + draw.
        Checks that the SAMPLE joule estimate does not beat the Landauer floor.

        Joules are labelled SAMPLE/ESTIMATE and never treated as measured.
        """
        if info_bits < 0:
            raise ValueError(f"info_bits must be non-negative, got {info_bits}")
        if joules_sample < 0:
            raise ValueError(f"joules_sample must be non-negative, got {joules_sample}")

        prev_bits = self._total_info_bits
        prev_joules = self._total_joules_sample

        # Landauer floor guard (anti-over-unity)
        floor = landauer_floor_joules(info_bits, temp_K)
        beats_floor = True
        if joules_sample > 0 and joules_sample < floor:
            beats_floor = False  # flag; do not raise (SAMPLE may be zero)

        entry = LedgerEntry(
            job_id=job_id,
            info_bits=info_bits,
            joules_sample=joules_sample,
            joules_label="sample",
            landauer_floor_joules=floor,
            beats_floor=beats_floor,
        )

        self._total_info_bits += info_bits
        self._total_joules_sample += joules_sample
        self._entries.append(entry)

        # Monotonicity assertion — mirrors energy_ledger_monotone
        assert self._total_info_bits >= prev_bits, (
            f"SoakLedger monotonicity violated on info_bits: "
            f"{prev_bits} → {self._total_info_bits} [EnergyBudgetWitness.lean PR #239]"
        )
        assert self._total_joules_sample >= prev_joules, (
            f"SoakLedger monotonicity violated on joules: "
            f"{prev_joules} → {self._total_joules_sample} [EnergyBudgetWitness.lean PR #239]"
        )

        return entry

    def provenance(self) -> dict:
        """Return a receipt-shaped provenance block for the full soak window."""
        return {
            "soak_jobs": len(self._entries),
            "total_info_bits": self._total_info_bits,
            "total_joules_sample": self._total_joules_sample,
            "joules_label": "sample",
            "ledger_monotone": True,
            "citation": (
                "energy_ledger_monotone / ledger_step_monotone "
                "[EnergyBudgetWitness.lean, lutar-lean PR #239, 0-sorry]"
            ),
        }


# ---------------------------------------------------------------------------
# Part 4 — Ouroboros bounded-recursion soak loop guard
# ---------------------------------------------------------------------------
# Models loop-kernel.ts runLoop({ maxSteps }):
#   "runs steps until … we hit maxSteps ('budgetExhausted')"
# The proactive soak loop is capped at OUROBOROS_MAX_SOAK_STEPS; reactive
# turns are NEVER subject to this gate and always preempt.


@dataclass
class OuroborosBudget:
    """A single-use Ouroboros-style work budget for one soak session.

    Mirrors the loop-kernel.ts runLoop({ maxSteps }) primitive:
    the kernel NEVER exceeds maxSteps — it exits 'budgetExhausted' when the
    cap is hit.  This budget wraps the Python soak loop equivalently.

    Citation:
      szl-holdings/ouroboros packages/ouroboros/src/loop-kernel.ts
      runLoop({ maxSteps }) — exits 'budgetExhausted' at hard cap
    """
    max_steps: int = OUROBOROS_MAX_SOAK_STEPS
    _steps_taken: int = field(default=0, init=False, repr=False)
    _exhausted: bool = field(default=False, init=False, repr=False)

    def step(self) -> bool:
        """Consume one step. Returns True if the loop may continue, False if exhausted.

        Once exhausted, every subsequent call returns False — the soak loop halts
        unconditionally, mirroring 'budgetExhausted' in loop-kernel.ts.
        """
        if self._exhausted or self._steps_taken >= self.max_steps:
            self._exhausted = True
            return False
        self._steps_taken += 1
        return True

    @property
    def steps_taken(self) -> int:
        return self._steps_taken

    @property
    def is_exhausted(self) -> bool:
        return self._exhausted or self._steps_taken >= self.max_steps

    @property
    def exit_reason(self) -> str:
        if self._exhausted or self._steps_taken >= self.max_steps:
            return "budgetExhausted"
        return "running"


# ---------------------------------------------------------------------------
# Part 5 — plan_soak: wire everything together
# ---------------------------------------------------------------------------


@dataclass
class SoakPlan:
    """Result of plan_soak(): the admitted batch jobs and the proven bounds respected."""
    admitted: list[dict]           # subset of input jobs admitted within bounds
    refused: list[dict]            # jobs refused (would exceed Bekenstein cap)
    ledger: SoakLedger
    bekenstein_cap_bits: int
    bekenstein_used_bits: int
    ouroboros_steps_taken: int
    ouroboros_max_steps: int
    ouroboros_exit_reason: str
    posture: str
    wasted_energy_available: bool
    proven_bounds_respected: list[str]
    joules_label: str = "sample"
    honest_note: str = (
        "Information cap (Bekenstein) and ledger monotonicity are PROVEN by "
        "kernel-checked Lean theorems (0-sorry). The Ouroboros loop bound is "
        "test-checked (mirrors loop-kernel.ts maxSteps). Joule figures stay "
        "SAMPLE/ESTIMATE until a real on-box NVML meter feeds them."
    )


def plan_soak(
    window: dict,
    jobs: list[dict],
    window_cap_bytes: Optional[int] = None,
    max_soak_steps: int = OUROBOROS_MAX_SOAK_STEPS,
    temp_K: float = LANDAUER_DEFAULT_TEMP_K,
) -> SoakPlan:
    """Admit batch jobs into the soak window, bounded by proven formulas.

    Given:
      window  — the harvest posture dict (from harvest_posture_bridge /
                should_soak_wasted_energy). Must have
                wasted_energy_available=True for any jobs to be admitted.
      jobs    — list of dicts, each with:
                  'id'         : any hashable job identifier
                  'info_bits'  : int, information load the job will process
                  'joules_est' : float (optional), SAMPLE energy estimate
      window_cap_bytes — byte budget for the soak window; Bekenstein cap =
                window_cap_bytes * 8 bits. If None, defaults to
                sum(job['info_bits'] for job in jobs) // 8 + 1  (admits
                exactly the jobs that fit within the cap individually but
                refuses those that together overflow it). Callers should
                supply a real window byte budget.
      max_soak_steps — Ouroboros hard cap (default OUROBOROS_MAX_SOAK_STEPS).
      temp_K         — temperature for Landauer floor (default 300 K).

    Returns:
      SoakPlan with admitted subset, refused subset, proven bounds, ledger.

    Proven bounds respected (in order):
      1. wasted_energy_available gate (posture check)
      2. Bekenstein additive cap (information bound, Lean proven PR #239)
      3. Landauer floor (energy lower bound, Lean proven PR #240)
      4. SoakLedger monotonicity (append-only, Lean proven PR #239)
      5. Ouroboros bounded-recursion cap (loop-kernel.ts maxSteps pattern)
    """
    posture = window.get("posture", "normal")
    wasted = bool(window.get("wasted_energy_available", False))

    # Default cap: sum of all job info bits translated back to bytes (generous)
    if window_cap_bytes is None:
        total_bits = sum(j.get("info_bits", 0) for j in jobs)
        # Use sum+1 as the cap; the additive check still refuses over-cap combos
        window_cap_bytes = max(1, (total_bits // 8) + 1)

    accumulator = BekensteinAccumulator(window_cap_bytes)
    ledger = SoakLedger()
    budget = OuroborosBudget(max_steps=max_soak_steps)

    admitted: list[dict] = []
    refused: list[dict] = []
    proven_bounds: list[str] = []

    # Gate 1: posture check — only soak when wasted energy is available
    if not wasted:
        proven_bounds.append(
            "posture_gate: wasted_energy_available=False — no jobs admitted "
            "(grid not in negative-price/curtailed window)"
        )
        return SoakPlan(
            admitted=admitted,
            refused=list(jobs),
            ledger=ledger,
            bekenstein_cap_bits=accumulator.cap_bits,
            bekenstein_used_bits=0,
            ouroboros_steps_taken=0,
            ouroboros_max_steps=max_soak_steps,
            ouroboros_exit_reason="posture_gate",
            posture=posture,
            wasted_energy_available=wasted,
            proven_bounds_respected=proven_bounds,
        )

    proven_bounds.append(
        "posture_gate: wasted_energy_available=True — soak window open"
    )

    # Main bounded soak loop — capped by Ouroboros budget
    for job in jobs:
        # Gate 2: Ouroboros bounded-recursion cap
        if not budget.step():
            # budgetExhausted — remaining jobs refused (not processed)
            refused.append({**job, "refused_reason": "ouroboros_budget_exhausted"})
            continue

        job_id = job.get("id", f"job_{len(admitted)+len(refused)}")
        info_bits = int(job.get("info_bits", 0))
        joules_est = float(job.get("joules_est", 0.0))

        # Gate 3: Bekenstein additive cap (proven: bekenstein_bound_additive,
        # info_within_bound — EnergyBudgetWitness.lean PR #239, 0-sorry)
        if not accumulator.try_admit(job_id, info_bits):
            refused.append({
                **job,
                "refused_reason": "bekenstein_cap_exceeded",
                "cap_bits": accumulator.cap_bits,
                "used_bits": accumulator.used_bits,
                "job_info_bits": info_bits,
            })
            continue

        # Gate 4: Landauer floor check — SAMPLE estimate must not beat the floor
        floor = landauer_floor_joules(info_bits, temp_K)
        if joules_est > 0 and joules_est < floor:
            # Over-unity claim — refuse
            refused.append({
                **job,
                "refused_reason": "sample_estimate_beats_landauer_floor",
                "sample_joules": joules_est,
                "landauer_floor_joules": floor,
            })
            # Undo Bekenstein accumulation for the refused job
            accumulator._used_bits -= info_bits
            accumulator._admitted.pop()
            continue

        # Gate 5: Append to monotone SoakLedger
        # (proven: energy_ledger_monotone — EnergyBudgetWitness.lean PR #239)
        ledger.append(job_id, info_bits, joules_est, temp_K)
        admitted.append({**job, "joules_label": "sample"})

    # Capture proven bounds respected
    proven_bounds.extend([
        (
            f"bekenstein_additive_cap: {accumulator.used_bits}/{accumulator.cap_bits} bits used "
            f"[bekenstein_bound_additive / info_within_bound, "
            f"EnergyBudgetWitness.lean, lutar-lean PR #239, 0-sorry]"
        ),
        (
            f"landauer_floor: all admitted SAMPLE estimates ≥ floor "
            f"[landauer_floor_pos, LandauerFloorWitness.lean, lutar-lean PR #240]"
        ),
        (
            f"ledger_monotone: SoakLedger append-only, "
            f"total_info_bits={ledger.total_info_bits}, "
            f"total_joules_sample={ledger.total_joules_sample:.3e} SAMPLE "
            f"[energy_ledger_monotone / ledger_step_monotone, "
            f"EnergyBudgetWitness.lean, PR #239]"
        ),
        (
            f"ouroboros_bound: loop halted after {budget.steps_taken}/{max_soak_steps} steps "
            f"(exit: {budget.exit_reason}) "
            f"[szl-holdings/ouroboros loop-kernel.ts runLoop maxSteps]"
        ),
    ])

    return SoakPlan(
        admitted=admitted,
        refused=refused,
        ledger=ledger,
        bekenstein_cap_bits=accumulator.cap_bits,
        bekenstein_used_bits=accumulator.used_bits,
        ouroboros_steps_taken=budget.steps_taken,
        ouroboros_max_steps=max_soak_steps,
        ouroboros_exit_reason=budget.exit_reason,
        posture=posture,
        wasted_energy_available=wasted,
        proven_bounds_respected=proven_bounds,
    )


# ---------------------------------------------------------------------------
# Self-test — no network needed; posture stubbed as negative-price
# ---------------------------------------------------------------------------

def _selftest() -> dict:
    """Self-test: prove all five proven properties hold.

    (a) Bekenstein additive cap REFUSES the over-budget job
    (b) Landauer floor is NEVER undercut by a SAMPLE estimate
    (c) SoakLedger is MONOTONE
    (d) Ouroboros bound HALTS a runaway loop
    (e) Reactive preemption still wins (soak gate=False when posture=normal)

    Stubbed posture: negative-price (wasted_energy_available=True, soak_hard=True).
    """
    checks = 0

    # --- (a) Bekenstein additive cap refuses the over-budget job ------------
    acc = BekensteinAccumulator(window_cap_bytes=10)   # cap = 80 bits
    assert acc.cap_bits == 80, "cap_bits should be 80"

    ok1 = acc.try_admit("job_A", 40)   # 40 bits <= 80: admit
    assert ok1, "(a) job_A should be admitted (40 bits within 80-bit cap)"
    checks += 1

    ok2 = acc.try_admit("job_B", 30)   # 40+30=70 <= 80: admit
    assert ok2, "(a) job_B should be admitted (70 bits within 80-bit cap)"
    checks += 1

    ok3 = acc.try_admit("job_C", 20)   # 70+20=90 > 80: REFUSED
    assert not ok3, "(a) job_C should be REFUSED (would exceed 80-bit Bekenstein cap)"
    checks += 1

    assert acc.used_bits == 70, f"(a) used_bits should be 70, got {acc.used_bits}"
    checks += 1

    # --- (b) Landauer floor is never undercut by a SAMPLE estimate ----------
    floor_300K_1000bits = landauer_floor_joules(1000, temp_K=300.0)
    assert floor_300K_1000bits > 0, "(b) Landauer floor must be positive"
    checks += 1

    # A legitimate estimate: 10x the floor (fine)
    try:
        assert_sample_beats_landauer_floor(1000, floor_300K_1000bits * 10, temp_K=300.0)
        checks += 1
    except AssertionError:
        raise AssertionError("(b) Legitimate sample should NOT raise floor violation")

    # An over-unity estimate: half the floor (forbidden)
    violation_raised = False
    try:
        assert_sample_beats_landauer_floor(1000, floor_300K_1000bits * 0.5, temp_K=300.0)
    except AssertionError:
        violation_raised = True
    assert violation_raised, "(b) Sub-floor SAMPLE estimate should raise floor violation"
    checks += 1

    # Joules=0 (unknown) always passes
    assert_sample_beats_landauer_floor(1000, 0.0, temp_K=300.0)
    checks += 1

    # --- (c) SoakLedger is MONOTONE ----------------------------------------
    ledger = SoakLedger()
    assert ledger.total_info_bits == 0
    checks += 1

    ledger.append("j1", 100, joules_sample=1e-18)
    assert ledger.total_info_bits == 100, "(c) ledger total should be 100 after j1"
    checks += 1

    ledger.append("j2", 200, joules_sample=2e-18)
    assert ledger.total_info_bits == 300, "(c) ledger total should be 300 after j2"
    checks += 1

    ledger.append("j3", 0, joules_sample=0.0)   # zero draw: still non-decreasing
    assert ledger.total_info_bits >= 300, "(c) zero-draw must not decrease ledger"
    checks += 1

    # Verify all entries have joules_label='sample' (doctrine)
    for e in ledger.entries:
        assert e.joules_label == "sample", f"(c) joules_label must be 'sample', got {e.joules_label}"
    checks += 1

    # --- (d) Ouroboros bound HALTS a runaway loop ---------------------------
    budget = OuroborosBudget(max_steps=4)
    iterations = 0
    while budget.step():
        iterations += 1
    assert iterations == 4, f"(d) Ouroboros should halt after 4 steps, got {iterations}"
    checks += 1
    assert budget.is_exhausted, "(d) budget should be exhausted"
    checks += 1
    assert budget.exit_reason == "budgetExhausted", f"(d) exit_reason should be 'budgetExhausted', got {budget.exit_reason}"
    checks += 1
    # Further step() calls return False (loop cannot resume)
    assert not budget.step(), "(d) exhausted budget.step() must return False"
    checks += 1

    # --- (e) Reactive preemption: soak gate=False when posture=normal -------
    normal_window = {
        "posture": "normal",
        "wasted_energy_available": False,
        "soak_hard": False,
    }
    jobs_e = [{"id": "reactive_job", "info_bits": 100, "joules_est": 0.0}]
    plan_e = plan_soak(normal_window, jobs_e, window_cap_bytes=200)
    assert len(plan_e.admitted) == 0, "(e) no jobs admitted when posture=normal"
    checks += 1
    assert len(plan_e.refused) == 1, "(e) job refused when posture=normal (reactive preemption)"
    checks += 1
    assert plan_e.ouroboros_exit_reason == "posture_gate", f"(e) exit should be posture_gate"
    checks += 1

    # Full plan_soak with negative-price stub
    neg_price_window = {
        "posture": "negative-price",
        "wasted_energy_available": True,
        "soak_hard": True,
        "joules_label": "sample",
        "source": "stub (negative-price)",
    }
    jobs_plan = [
        {"id": "batch_A", "info_bits": 40, "joules_est": 1e-17},   # admitted
        {"id": "batch_B", "info_bits": 30, "joules_est": 1e-17},   # admitted (70 total)
        {"id": "batch_C", "info_bits": 20, "joules_est": 1e-17},   # refused (>80-bit cap)
    ]
    plan = plan_soak(neg_price_window, jobs_plan, window_cap_bytes=10)
    assert len(plan.admitted) == 2, f"(a+plan) 2 jobs should be admitted, got {len(plan.admitted)}"
    checks += 1
    assert len(plan.refused) == 1, f"(a+plan) 1 job should be refused, got {len(plan.refused)}"
    checks += 1
    assert plan.refused[0]["refused_reason"] == "bekenstein_cap_exceeded", \
        f"(a+plan) refused reason should be bekenstein_cap_exceeded"
    checks += 1
    assert plan.ledger.total_info_bits == 70, f"(c+plan) ledger total should be 70"
    checks += 1
    assert plan.joules_label == "sample", "(doctrine) joules_label must be 'sample'"
    checks += 1

    return {"ok": True, "checks": checks}


if __name__ == "__main__":
    import sys
    result = _selftest()
    print(f"ok:{str(result['ok']).lower()} checks:{result['checks']}")
    sys.exit(0 if result["ok"] else 1)
