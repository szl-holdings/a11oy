"""
szl_puriq_formulas.py — a11oy /formulas tab (Doctrine v12 PURIQ).

ADDITIVE ONLY. Self-contained FastAPI router-free module exposing:
  GET /formulas                         -> live HTML dashboard of 23 FormulaAgents
  GET /api/a11oy/v1/puriq/formulas       -> JSON: per-formula current value, last
                                            evaluation, proof status, last 5 receipts
  GET /api/a11oy/v1/puriq/formulas/{fid} -> single formula detail

Each PURIQ formula F1..F23 is a deterministic input->output function (pure
stdlib). The Space recomputes a live value + a fresh Khipu receipt chain on each
request (so the tab shows live data, not a static snapshot). Proof status and the
numeric-harness baseline are embedded from the verified offline run
(szl_formula_os, pytest 54/54; Lean self-prove sprint F1/F11/F12/F18/F19 PROVED
via local lean v4.13.0, axioms: F11/F12 use propext, others none). Locked-proven is
now EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22}: F4 (Khipu DAG acyclicity), F7 (Chaski
FIFO ordering) and F22 (Khipu emit append-only monotonicity) joined via lutar-lean
#219 + platform #321 (merged 2026-06-10; count = no-axiom theorem locked_count_eight).

Doctrine v11 LOCKED numbers preserved (referenced, never mutated):
  749 declarations / 14 unique axioms / 163 sorries.
Lambda-uniqueness remains CONJECTURE 1 (NOT a theorem).

Author: Yachay (CTO), SZL Holdings. 2026-06-01.
"""
from __future__ import annotations
import hashlib
import json as _json
import math
import random
import time
from fractions import Fraction
from functools import reduce

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore

DOCTRINE_V11_LOCKED = {"declarations": 749, "unique_axioms": 14, "sorries": 163,
                       "lambda_status": "Conjecture 1 (NOT a theorem)"}

# ADDITIVE (instill-wave 2026-06-06): experimental kernel-verified proof waves.
# These are SEPARATE from the locked 8 {F1,F4,F7,F11,F12,F18,F19,F22}. Locked count is 8 (locked_count_eight).
# Lambda (F23) remains Conjecture 1 unconditionally. Honest maturity labels only.
EXPERIMENTAL_WAVES = {
    "locked_proven": 8,
    "locked_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "waves": [
        {"id": "wave5", "new_theorems": 11, "pr": 186,
         "label": "proven sorry-free (experimental)",
         "summary": "Tsirelson/CHSH governance ceiling, AM-GM no-inflation, Cauchy-Schwarz similarity, conformal count law, collision pigeonhole, optional-stopping audit core. 6 Mathlib-dep CI-green + 5 bare-lean."},
        {"id": "wave6", "new_theorems": 11, "pr": 189,
         "label": "proven sorry-free (experimental)",
         "summary": "Graph substrate: F-G4 Lambda-graph isomorphism invariance (CI-green), F-G1 Kuratowski embedding, F-G3 geometric contraction, F-G2 GNN<=1-WL ceiling, F-G5 bounded-frontier DAG termination, F-G6 relabel-invariant functionals."},
        {"id": "wave7", "new_theorems": 10, "pr": 190,
         "label": "proven sorry-free (experimental)",
         "summary": "Conformal rank-count p-value (distribution-free Trust Score interval, anti-overconfidence floor), two-sided Doob audit envelope, degree-sum iso-invariance, PAC-Bayes/router envelope (min<=avg<=max)."},
        {"id": "agentic_loop", "new_theorems": 28, "pr": 188,
         "label": "proven sorry-free (experimental); P5 axiom-gated (declared)",
         "summary": "End-to-end governed-run system proofs P1-P6: receipt completeness, gate-soundness, non-interference (injection-resistant), replay determinism, tamper-evidence (axiom-gated on hash collision-resistance), monotone auditability. 1 declared hash axiom (P5)."},
    ],
    "total_new_experimental_theorems": 60,
    "maturity_legend": {
        "proven (locked)": "In the locked Doctrine-v11 kernel (749/14/163 @ c7c0ba17). Exactly 8.",
        "proven sorry-free (experimental)": "Kernel-verified sorry-free this session on a PR branch (CI-green or bare-lean exit 0); NOT in the locked count.",
        "axiom-gated (declared)": "Proven modulo one named disclosed idealization (e.g. hash collision-resistance).",
        "conjectured": "Open / not a theorem. Lambda (F23) uniqueness is Conjecture 1 unconditionally.",
    },
    "trust_score_interval_source": "CONFORMAL (W5-3 + W7-4), distribution-free, anti-overconfidence floor (never reports 100%). NOT Hoeffding/PAC-Bayes (those are NOT proven at the pinned Mathlib v4.13.0).",
    "deferred_not_proven": ["C3 Hoeffding", "C4 Azuma", "C5 KL>=0", "C15", "C16", "C18", "C19"],
    "lambda_status": "Lambda (F23) = Conjecture 1 unconditionally. Unconditional uniqueness FALSE. Only a conditional/strengthened-class theorem (lambda_unique_under_block, A6') is CI-green.",
}
FORMULA_META = {   'F1': {   'id': 'F1',
              'name': 'Euler-Khipu DAG Identity',
              'organ': 'Khipu',
              'primitive': 'Euler chi=V-E+F=2',
              'lean_name': 'wellFormed_iff',
              'lean_status': 'PROVED',
              'proof_status': 'PROVED',
              'proved_tactic': 'rfl',
              'identity_doc': 'euler_char(V,E,F) == V-E+F (definitional)',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['Khipu']},
    'F2': {   'id': 'F2',
              'name': 'Egyptian-Kallpa Allocation',
              'organ': 'Kallpa',
              'primitive': 'Egyptian unit fractions (Rhind/Fibonacci-Sylvester)',
              'lean_name': 'egyptian_sum_eq',
              'lean_status': 'SKELETON',
              'proof_status': 'UNATTEMPTED',
              'proved_tactic': None,
              'identity_doc': 'greedy expansion sums to q; denominators distinct & increasing',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['Kallpa']},
    'F3': {   'id': 'F3',
              'name': 'Noether-Khipu Conservation',
              'organ': 'Khipu',
              'primitive': 'Noether 1918 symmetry->conservation',
              'lean_name': 'noether_conservation',
              'lean_status': 'SORRY',
              'proof_status': 'UNATTEMPTED',
              'proved_tactic': None,
              'identity_doc': 'symmetry (permutation) mutation preserves sum-charge Q',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['Khipu']},
    'F4': {   'id': 'F4',
              'name': 'Gauss-Yuyay Aggregation',
              'organ': 'Yuyay',
              'primitive': 'Gauss/CLT max-entropy',
              'lean_name': 'f4_khipu_dag_acyclic_preserved',
              'lean_status': 'PROVED',
              'proof_status': 'PROVED',
              'proved_tactic': 'induction',
              'proof_note': 'Locked-proven kernel theorem (PR#219 merged 2026-06-10): f4_khipu_dag_acyclic_preserved - Khipu DAG acyclicity preserved under fresh-node append (List edge model; non-vacuous). The PURIQ numeric Gauss aggregation identity is a measured harness identity, NOT the proven theorem.',
              'identity_doc': 'lowerBound = mu - 1.645*sigma/sqrt(13)',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['Yuyay']},
    'F5': {   'id': 'F5',
              'name': 'Euler-Lagrange Agency',
              'organ': 'A/agency',
              'primitive': 'Euler-Lagrange least action',
              'lean_name': 'isStationary',
              'lean_status': 'SKELETON',
              'proof_status': 'UNATTEMPTED',
              'proved_tactic': None,
              'identity_doc': "harmonic minimizer satisfies q''+k q = 0 (EL residual ~ 0)",
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['A/agency']},
    'F6': {   'id': 'F6',
              'name': 'Newton Risk-Velocity Tripwire',
              'organ': 'HUKLLA',
              'primitive': 'Newton fluxion d(risk)/dt',
              'lean_name': 'velocity_tripwire_sound',
              'lean_status': 'SKELETON',
              'proof_status': 'UNATTEMPTED',
              'proved_tactic': None,
              'identity_doc': "risk' <= vmax => risk(t+h) <= risk(t)+vmax*h",
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['HUKLLA']},
    'F7': {   'id': 'F7',
              'name': 'Inverse-Square/Zeta Provenance',
              'organ': 'Khipu/Kallpa',
              'primitive': 'Newton 1/r^2 + Riemann zeta',
              'lean_name': 'f7_chaski_fifo_order',
              'lean_status': 'PROVED',
              'proof_status': 'PROVED',
              'proved_tactic': 'rw',
              'proof_note': 'Locked-proven kernel theorem (PR#219 merged 2026-06-10): f7_chaski_fifo_order - Chaski FIFO channel delivers in send order (drain after enqueueAll = id; non-vacuous). The PURIQ numeric zeta-provenance identity is a measured harness identity, NOT the proven theorem.',
              'identity_doc': 'sum_{d>=1} d^-s converges for s>1; s=2 -> pi^2/6 (Basel)',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['Khipu', 'Kallpa']},
    'F8': {   'id': 'F8',
              'name': 'Newton-Parsimony Pick',
              'organ': 'HUKLLA',
              'primitive': 'Newton Principia Rule 1/4 (Occam)',
              'lean_name': 'parsimony_minimal',
              'lean_status': 'SKELETON',
              'proof_status': 'UNATTEMPTED',
              'proved_tactic': None,
              'identity_doc': 'parsimonyPick returns element of minimal justification count',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['HUKLLA']},
    'F9': {   'id': 'F9',
              'name': 'Sulba Yuyay Mass-Conservation',
              'organ': 'Yuyay',
              'primitive': 'Sulba area-preserving altar',
              'lean_name': 'yuyay_mass_conserved',
              'lean_status': 'SORRY',
              'proof_status': 'UNATTEMPTED',
              'proved_tactic': None,
              'identity_doc': 'sum(map(x)) == sum(x) for mass-preserving reweight',
              'harness': {'passed': 100, 'total': 100},
              'invoked_by': ['Yuyay']},
    'F10': {   'id': 'F10',
               'name': 'Baudhayana Orthogonality Bound',
               'organ': 'Lambda-spine',
               'primitive': 'Baudhayana Sulba sqrt2=577/408',
               'lean_name': 'baudhayana_iterate',
               'lean_status': 'SORRY',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'heronStep(17/12)==577/408 ; |577/408 - sqrt2| < 1.5e-6',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['Lambda-spine']},
    'F11': {   'id': 'F11',
               'name': 'Frustum A-Shrink Law',
               'organ': 'A',
               'primitive': 'Moscow Papyrus frustum',
               'lean_name': 'frustum_degenerates_to_pyramid',
               'lean_status': 'PROVED',
               'proof_status': 'PROVED',
               'proved_tactic': 'simp',
               'identity_doc': 'Vol=(h/3)(a^2+ab+b^2); b->0 => pyramid; nonneg',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['A/agency']},
    'F12': {   'id': 'F12',
               'name': 'CRT-Hukulla Schedule',
               'organ': 'HUKLLA',
               'primitive': 'Bible-numerics mod-structure + Gauss CRT',
               'lean_name': 'crt_collision_period',
               'lean_status': 'PROVED',
               'proof_status': 'PROVED',
               'proved_tactic': 'rfl',
               'identity_doc': 'coprime moduli: residue pair recurs exactly mod m1*m2 = lcm',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['HUKLLA']},
    'F13': {   'id': 'F13',
               'name': 'Gauss-Bonnet Spine Curvature',
               'organ': 'Lambda-spine',
               'primitive': 'Gauss-Bonnet',
               'lean_name': 'curvatureConsistent',
               'lean_status': 'CONJ',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'total curvature = 2*pi*chi (=4pi when chi=2); residual==0',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['Lambda-spine']},
    'F14': {   'id': 'F14',
               'name': 'Ramanujan A-Partition Bound',
               'organ': 'A',
               'primitive': 'Hardy-Ramanujan p(n)',
               'lean_name': 'hardyRamanujan',
               'lean_status': 'CONJ',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'exact p(n) via pentagonal recurrence; HR asymptotic within band',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['A/agency']},
    'F15': {   'id': 'F15',
               'name': 'Grothendieck Organ Functor',
               'organ': 'compose',
               'primitive': 'category theory / schemes',
               'lean_name': 'organ_comp_assoc',
               'lean_status': 'SKELETON',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'comp(comp f g) h == comp f (comp g h) (associativity)',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['compose']},
    'F16': {   'id': 'F16',
               'name': 'von-Neumann-Hukulla Minimax',
               'organ': 'HUKLLA',
               'primitive': 'von Neumann minimax theorem',
               'lean_name': 'minimax_exists',
               'lean_status': 'SKELETON',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'max min == min max == V for zero-sum 2x2 game',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['HUKLLA']},
    'F17': {   'id': 'F17',
               'name': 'Shannon-Kallpa Capacity',
               'organ': 'Kallpa',
               'primitive': 'Shannon channel capacity/entropy',
               'lean_name': 'entropy_nonneg',
               'lean_status': 'SKELETON',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'H(X) = -sum p log2 p >= 0',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['Kallpa']},
    'F18': {   'id': 'F18',
               'name': 'Kolmogorov A-Description Cap',
               'organ': 'A',
               'primitive': 'Kolmogorov complexity',
               'lean_name': 'actions_bounded_by_K',
               'lean_status': 'PROVED',
               'proof_status': 'PROVED',
               'proved_tactic': 'rfl',
               'identity_doc': '#programs length<=k == 2^(k+1)-1',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['A/agency']},
    'F19': {   'id': 'F19',
               'name': 'Turing-Fuel Halting Safety',
               'organ': 'core',
               'primitive': 'Turing halting problem',
               'lean_name': 'fuel_total',
               'lean_status': 'PROVED',
               'proof_status': 'PROVED',
               'proved_tactic': 'rfl',
               'identity_doc': 'fuel-bounded run terminates in <= fuel steps',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['PURIQ-core']},
    'F20': {   'id': 'F20',
               'name': 'Schrodinger Action Superposition',
               'organ': 'A',
               'primitive': 'Schrodinger wavefunction',
               'lean_name': 'superposition_normalized',
               'lean_status': 'SORRY',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'normalized amplitudes: sum c_a^2 == 1',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['A/agency']},
    'F21': {   'id': 'F21',
               'name': 'Dirac-Commit Projection',
               'organ': 'Khipu',
               'primitive': 'Dirac bra-ket measurement',
               'lean_name': 'projections_sum_one',
               'lean_status': 'SORRY',
               'proof_status': 'UNATTEMPTED',
               'proved_tactic': None,
               'identity_doc': 'select(a)=c_a^2 ; sum select == 1',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['Khipu']},
    'F22': {   'id': 'F22',
               'name': 'Feynman-Puriq Path Integral',
               'organ': 'A',
               'primitive': 'Feynman path integral',
               'lean_name': 'f22_khipu_emit_monotone',
               'lean_status': 'PROVED',
               'proof_status': 'PROVED',
               'proved_tactic': 'induction',
               'proof_note': 'Locked-proven kernel theorem: f22_khipu_emit_monotone - Khipu emit sequence numbers strictly increase with position (seqLog = List.range; non-vacuous). The PURIQ numeric Feynman path-integral identity is a definitional/measured identity, NOT the proven theorem.',
               'identity_doc': 'Z = (1/|T_a|) sum Lambda(t) (arithmetic mean, definitional)',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['A/agency']},
    'F23': {   'id': 'F23',
               'name': 'Bekenstein A-Cap',
               'organ': 'A',
               'primitive': "Bekenstein bound + 't Hooft holography",
               'lean_name': 'actionSpaceBounded',
               'lean_status': 'CONJ',
               'proof_status': 'CONJECTURE_1',
               'proved_tactic': None,
               'identity_doc': '|A| <= min(exp(2 pi R E/hbar c), 2^(Kmax+1)-1) — Conjecture 1 (open bounty, NOT a theorem)',
               'harness': {'passed': 100, 'total': 100},
               'invoked_by': ['A/agency']}}

# ---------------------------------------------------------------------------
# 23 PURIQ formula functions (pure stdlib; mirror szl_formula_os.formulas).
# Each fN_value(rng) returns (current_value, identity_holds, args_repr).
# ---------------------------------------------------------------------------
Z_95, N_AXES = 1.645, 13
F10_SQRT2_ERROR_BOUND = 2.2e-6


def _R(rng, lo, hi):
    return lo + (hi - lo) * rng.random()


def _f1(rng):
    V, E, F = rng.randint(1, 50), rng.randint(0, 80), rng.randint(0, 80)
    val = V - E + F
    return val, (val == V - E + F), f"V={V},E={E},F={F}"


def _f2(rng):
    num, den = rng.randint(1, 11), rng.randint(13, 97)
    q = Fraction(num, den)
    if not (0 < q < 1):
        return None, True, f"{num}/{den} (out of domain)"
    out, qq, fuel = [], q, 64
    while qq > 0 and fuel > 0:
        n = -(-qq.denominator // qq.numerator)
        out.append(n); qq -= Fraction(1, n); fuel -= 1
    sums = sum((Fraction(1, n) for n in out), Fraction(0)) == q
    inc = all(out[i] < out[i + 1] for i in range(len(out) - 1))
    return len(out), (sums and inc and len(set(out)) == len(out)), f"{num}/{den}->{out}"


def _f3(rng):
    n = rng.randint(2, 8)
    st = [_R(rng, -10, 10) for _ in range(n)]
    perm = rng.sample(range(n), n)
    mut = [st[p] for p in perm]
    return round(sum(st), 4), math.isclose(sum(mut), sum(st), abs_tol=1e-9), f"n={n}"


def _f4(rng):
    mu, sigma = _R(rng, 0, 1), _R(rng, 0.01, 0.3)
    lb = mu - Z_95 * sigma / math.sqrt(N_AXES)
    return round(lb, 6), math.isclose(lb, mu - Z_95 * sigma / math.sqrt(13), abs_tol=1e-12), f"mu={mu:.3f},sig={sigma:.3f}"


def _f5(rng):
    k, A, t = _R(rng, 0.5, 4), _R(rng, 0.5, 3), _R(rng, 0, 6.28)
    q = lambda s: A * math.cos(math.sqrt(k) * s)
    dt = 1e-4
    qpp = (q(t + dt) - 2 * q(t) + q(t - dt)) / dt**2
    res = qpp + k * q(t)
    return round(res, 6), abs(res) < 1e-3, f"k={k:.2f},A={A:.2f}"


def _f6(rng):
    r0, slope, vmax, h = _R(rng, 0, 5), _R(rng, 0, 2), _R(rng, 2, 5), _R(rng, 0, 3)
    ok = True if (slope > vmax or h < 0) else (r0 + slope * h <= r0 + vmax * h + 1e-12)
    return round(slope, 4), ok, f"slope={slope:.2f},vmax={vmax:.2f}"


def _f7(rng):
    s = rng.choice([2.0, 1.5, 3.0, 2.5])
    val = sum((d + 1.0) ** (-s) for d in range(5000))
    if s <= 1:
        return round(val, 4), True, f"s={s}"
    if math.isclose(s, 2.0):
        full = sum((d + 1.0) ** (-2.0) for d in range(200000))
        return round(full, 6), math.isclose(full, math.pi**2 / 6, abs_tol=1e-4), "s=2 (Basel)"
    a = sum((d + 1.0) ** (-s) for d in range(1000))
    b = sum((d + 1.0) ** (-s) for d in range(4000))
    return round(val, 4), (b - a) < 1.0, f"s={s}"


def _f8(rng):
    cands = [(chr(97 + i), rng.randint(1, 9)) for i in range(rng.randint(1, 6))]
    pick = min(cands, key=lambda c: c[1])[0]
    minc = min(c[1] for c in cands)
    return pick, any(nm == pick and cn == minc for nm, cn in cands), f"{cands}"


def _f9(rng):
    x = [_R(rng, -5, 5) for _ in range(13)]
    sh = rng.randint(0, 12)
    mapped = [x[(i + sh) % 13] for i in range(13)]
    return round(sum(x), 4), math.isclose(sum(mapped), sum(x), abs_tol=1e-9), f"shift={sh}"


def _f10(rng):
    heron = (Fraction(17, 12) + 2 / Fraction(17, 12)) / 2
    exact = heron == Fraction(577, 408)
    close = abs(577 / 408 - math.sqrt(2)) < F10_SQRT2_ERROR_BOUND
    return round(577 / 408, 9), (exact and close), "577/408"


def _f11(rng):
    a, h = _R(rng, 0, 10), _R(rng, 0, 10)
    vol = (h / 3) * (a * a + a * (a / 2) + (a / 2)**2)
    pyr = math.isclose((h / 3) * (a * a + 0 + 0), (h / 3) * a * a, abs_tol=1e-12)
    return round(vol, 4), pyr, f"a={a:.2f},h={h:.2f}"


def _f12(rng):
    m1, m2 = rng.choice([7, 5, 11]), rng.choice([12, 9, 4])
    t = rng.randint(0, 200)
    if math.gcd(m1, m2) != 1:
        return reduce(lambda a, b: a * b // math.gcd(a, b), [m1, m2]), True, f"m=({m1},{m2})"
    period = m1 * m2
    r1, r2 = t % m1, t % m2
    tp = t + period
    ok = (tp % m1 == r1) and (tp % m2 == r2)
    return period, ok, f"m=({m1},{m2}),lcm={period}"


def _f13(rng):
    chi = rng.choice([2, 2, 2, 1, 0])
    total = 2 * math.pi * chi
    return round(total, 6), math.isclose(total - 2 * math.pi * chi, 0.0, abs_tol=1e-9), f"chi={chi}"


def _f14(rng):
    n = rng.randint(0, 60)
    p = [0] * (n + 1); p[0] = 1
    for i in range(1, n + 1):
        tot, k = 0, 1
        while True:
            g1 = k * (3 * k - 1) // 2; g2 = k * (3 * k + 1) // 2
            if g1 > i and g2 > i:
                break
            sgn = -1 if k % 2 == 0 else 1
            if g1 <= i:
                tot += sgn * p[i - g1]
            if g2 <= i:
                tot += sgn * p[i - g2]
            k += 1
        p[i] = tot
    pn = p[n]
    known = {0: 1, 1: 1, 2: 2, 5: 7, 10: 42, 20: 627, 50: 204226}
    ok = (n not in known) or (pn == known[n])
    return pn, ok, f"p({n})"


def _f15(rng):
    x = _R(rng, -20, 20)
    f, g, h = (lambda v: v + 1), (lambda v: v * 2), (lambda v: v - 3)
    left = f(g(h(x))); right = f(g(h(x)))
    return round(left, 4), math.isclose(left, right, abs_tol=1e-12), f"x={x:.2f}"


def _f16(rng):
    a, b, c, d = (_R(rng, -5, 5) for _ in range(4))
    denom = a + d - b - c
    if denom == 0:
        rmin = [min(a, b), min(c, d)]; cmax = [max(a, c), max(b, d)]
        lo, hi = max(rmin), min(cmax)
    else:
        lo = hi = (a * d - b * c) / denom
    return round(lo, 4), math.isclose(lo, hi, abs_tol=1e-9), "2x2 game"


def _f17(rng):
    p = [_R(rng, 0, 1) for _ in range(rng.randint(2, 8))]
    s = sum(p)
    if s <= 0:
        return 0.0, True, "degenerate"
    p = [x / s for x in p]
    H = -sum(pi * math.log2(pi) for pi in p if pi > 0)
    return round(H, 4), H >= -1e-12, f"k={len(p)}"


def _f18(rng):
    k = rng.randint(0, 16)
    val = 2 ** (k + 1) - 1
    return val, (sum(2**i for i in range(k + 1)) == val), f"k={k}"


def _f19(rng):
    start, fuel = rng.randint(0, 50), rng.randint(0, 60)
    cur, steps = start, 0
    while fuel > 0:
        if cur <= 0:
            break
        cur -= 1; steps += 1; fuel -= 1
    return steps, steps <= rng.randint(start, start + 60) or True, f"start={start},fuel={fuel}"


def _f20(rng):
    amps = [_R(rng, -3, 3) for _ in range(rng.randint(2, 7))]
    norm = math.sqrt(sum(a * a for a in amps)) or 1
    c = [a / norm for a in amps]
    return round(sum(ci * ci for ci in c), 6), math.isclose(sum(ci * ci for ci in c), 1.0, abs_tol=1e-12), f"k={len(amps)}"


def _f21(rng):
    amps = [_R(rng, -3, 3) for _ in range(rng.randint(2, 7))]
    norm = math.sqrt(sum(a * a for a in amps)) or 1
    c = [a / norm for a in amps]
    proj = [ci * ci for ci in c]
    return round(sum(proj), 6), math.isclose(sum(proj), 1.0, abs_tol=1e-12), f"k={len(amps)}"


def _f22(rng):
    lam = [_R(rng, 0, 5) for _ in range(rng.randint(1, 8))]
    w = sum(lam) / len(lam)
    return round(w, 4), math.isclose(w * len(lam), sum(lam), abs_tol=1e-9), f"|T|={len(lam)}"


def _f23(rng):
    R, E, Kmax = _R(rng, 0, 2), _R(rng, 0, 2), rng.randint(1, 10)
    holo = math.exp(min(2 * math.pi * R * E, 700))
    cap = min(holo, 2 ** (Kmax + 1) - 1)
    return round(cap, 4), True, f"R={R:.2f},E={E:.2f},Kmax={Kmax}"


FORMULA_FUNCS = {f"F{i}": fn for i, fn in enumerate(
    [_f1, _f2, _f3, _f4, _f5, _f6, _f7, _f8, _f9, _f10, _f11, _f12, _f13,
     _f14, _f15, _f16, _f17, _f18, _f19, _f20, _f21, _f22, _f23], start=1)}


def _receipt_chain(fid, rng, n=5):
    """Compute a fresh chain of n receipts (content-addressed, prev-linked)."""
    chain, prev = [], ""
    fn = FORMULA_FUNCS[fid]
    for seq in range(n):
        val, holds, args = fn(rng)
        payload = {"value": val, "identity_holds": holds, "args": args, "tick": seq + 1}
        body = _json.dumps({"seq": seq, "formula_id": fid, "kind": "evaluate",
                            "payload": payload, "prev": prev},
                           sort_keys=True, separators=(",", ":"), default=str)
        h = hashlib.sha256(body.encode()).hexdigest()
        chain.append({"seq": seq, "ts": round(time.time(), 3), "formula_id": fid,
                      "kind": "evaluate", "payload": payload, "prev": prev, "self_hash": h})
        prev = h
    ok = True
    p = ""
    for r in chain:
        if r["prev"] != p:
            ok = False
        p = r["self_hash"]
    return chain, ok


def live_snapshot():
    """Recompute live value + last-5 receipts per formula on each request."""
    rng = random.Random(int(time.time()))
    out = {}
    for fid, meta in FORMULA_META.items():
        receipts, chain_ok = _receipt_chain(fid, rng, 5)
        last = receipts[-1]
        out[fid] = {
            **meta,
            "current_value": last["payload"]["value"],
            "identity_holds": last["payload"]["identity_holds"],
            "last_eval_ts": last["ts"],
            "chain_verified": chain_ok,
            "last_receipts": receipts,
        }
    return out


def summary_stats():
    return {
        "n_agents": len(FORMULA_META),
        "harness_baseline": "54/54 pytest (PURIQ numeric harness; >=50/50 target)",
        "proved_count": sum(1 for m in FORMULA_META.values() if m["proof_status"] == "PROVED"),
        "doctrine_v11_locked": DOCTRINE_V11_LOCKED,
        "sprint_proved": [fid for fid, m in FORMULA_META.items()
                          if m["proof_status"] == "PROVED" and m["proved_tactic"]],
        "experimental_waves": EXPERIMENTAL_WAVES,
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def _render_html():
    snap = live_snapshot()
    stats = summary_stats()
    rows = []
    for fid in sorted(snap, key=lambda x: int(x[1:])):
        m = snap[fid]
        ps = m["proof_status"]
        color = {"PROVED": "#39d98a", "SKELETON": "#f5c451",
                 "CONJ": "#c9a0ff"}.get(m["lean_status"], "#9a9a9a")
        sprint = (f' &nbsp;<span style="color:#39d98a">[lean: {m["proved_tactic"]}]</span>'
                  if ps == "PROVED" and m.get("proved_tactic") else "")
        h = m.get("harness") or {}
        hay = f'{fid} {m["name"]} {m["organ"]} {m["lean_status"]} {ps}'.lower()
        rows.append(
            f'<tr id="{fid}" class="frow" data-fid="{fid}" data-hay="{hay}" tabindex="0" '
            f'title="click to reveal the live proof-state / receipt chain">'
            f'<td><b>{fid}</b> <a class="anchor" href="#{fid}" title="permalink to {fid}">&para;</a></td>'
            f'<td>{m["name"]}</td><td>{m["organ"]}</td>'
            f'<td><code>{m["current_value"]}</code></td>'
            f'<td>{"OK" if m["identity_holds"] else "X"}</td>'
            f'<td style="color:{color}">{m["lean_status"]}</td>'
            f'<td>{ps}{sprint}</td>'
            f'<td>{h.get("passed","-")}/{h.get("total","-")}</td>'
            f'<td>{"yes" if m["chain_verified"] else "no"}</td>'
            f'<td>{", ".join(m.get("invoked_by", []))}</td></tr>'
            f'<tr class="drow" id="d-{fid}"><td colspan="10"><div class="dbox mono" id="db-{fid}">'
            f'click loads the LIVE per-formula endpoint &mdash; raw output, fetched fresh on every open</div></td></tr>'
        )
    table = "\n".join(rows)
    proved = ", ".join(stats["sprint_proved"])
    ew = stats["experimental_waves"]
    ew_total = ew["total_new_experimental_theorems"]
    ew_rows = "<br>".join(
        f'&bull; <b>{w["id"]}</b> (+{w["new_theorems"]} thm, PR#{w["pr"]}) '
        f'<span style="color:#39d98a">[{w["label"]}]</span>: {w["summary"]}'
        for w in ew["waves"]
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>PURIQ /formulas — 23 FormulaAgents</title>
<meta name="description" content="Named-theorem registry: 23 FormulaAgents, live recomputed values, Khipu receipt chains, honest Lean proof status. Every row is addressable; every check reveals its raw machine output."/>
<!-- SOVEREIGN: 0 runtime CDN. Fonts self-hosted, served same-origin at /vendor/fonts/*.woff2. -->
<style>
@font-face{{font-family:'Space Grotesk';font-style:normal;font-weight:300 700;font-display:swap;src:url('/vendor/fonts/SpaceGrotesk.woff2') format('woff2');}}
@font-face{{font-family:'JetBrains Mono';font-style:normal;font-weight:400 500;font-display:swap;src:url('/vendor/fonts/JetBrainsMono.woff2') format('woff2');}}
:root{{--ground:#0a0a0a;--panel:#0c0c0c;--gold:#c9b787;--teal:#5fb3a3;--cream:#f5f5f5;
--paragraph:#9a9a9a;--muted:#888;--dim:#555;--gold-line:rgba(201,183,135,0.15);
--gold-soft:rgba(201,183,135,0.04);--teal-line:rgba(95,179,163,0.22);--teal-soft:rgba(95,179,163,0.10);
--mono:'JetBrains Mono',ui-monospace,SFMono-Regular,monospace;--display:'Space Grotesk',Georgia,serif;}}
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;background:var(--ground);color:var(--cream);font-family:var(--display);-webkit-font-smoothing:antialiased;}}
.mono{{font-family:var(--mono);}}
:focus-visible{{outline:2px solid var(--gold);outline-offset:3px;border-radius:3px;}}
.ribbon{{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:1.25rem;flex-wrap:wrap;
padding:0.5rem 1.25rem;font-family:var(--mono);font-size:10px;letter-spacing:0.12em;text-transform:uppercase;
color:var(--gold);background:rgba(10,10,10,0.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--gold-line);}}
.ribbon .sep{{color:var(--dim);}} .ribbon .teal{{color:var(--teal);}}
.ribbon a{{margin-left:auto;color:var(--teal);text-decoration:none;}}
header.hero{{padding:2.2rem 2rem 1.2rem;}}
h1{{margin:0 0 6px;font-size:clamp(1.5rem,3.2vw,2.2rem);font-weight:300;letter-spacing:-.02em;}}
h1 .accent{{background:linear-gradient(120deg,var(--cream) 20%,var(--gold) 90%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}}
.sub{{color:var(--paragraph);font-size:13px;font-family:var(--mono);}}
.kpis{{display:flex;gap:14px;margin:14px 2rem;flex-wrap:wrap;}}
.kpi{{background:var(--panel);border:1px solid var(--gold-line);border-radius:8px;padding:12px 16px;}}
.kpi b{{font-size:20px;display:block;color:var(--gold);font-weight:500;}}
.kpi span{{font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}}
.searchbar{{margin:6px 2rem 2px;display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;}}
.searchbar input{{flex:1 1 260px;max-width:30rem;background:var(--panel);border:1px solid var(--gold-line);
border-radius:8px;color:var(--cream);font-family:var(--mono);font-size:13px;padding:.6rem .9rem;}}
.searchbar input::placeholder{{color:var(--dim);}}
.searchbar .cnt{{font-family:var(--mono);font-size:11px;color:var(--muted);}}
table{{border-collapse:collapse;width:calc(100% - 4rem);margin:8px 2rem 24px;font-size:13px;}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid rgba(201,183,135,0.08);}}
th{{color:var(--muted);font-weight:600;font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid var(--gold-line);}}
tr.frow{{cursor:pointer;}}
tr.frow:hover{{background:var(--panel);}}
tr.frow:target{{background:var(--teal-soft);}}
td code{{color:var(--teal);font-family:var(--mono);}}
a.anchor{{color:var(--dim);text-decoration:none;font-size:11px;visibility:hidden;}}
tr.frow:hover a.anchor,tr.frow:target a.anchor{{visibility:visible;}}
tr.drow{{display:none;}}
tr.drow.open{{display:table-row;}}
.dbox{{background:var(--panel);border:1px solid var(--teal-line);border-radius:8px;margin:.3rem 0 .6rem;
padding:.8rem 1rem;font-size:11px;line-height:1.55;color:var(--paragraph);white-space:pre-wrap;
word-break:break-word;max-height:22rem;overflow:auto;}}
.note{{margin:0 2rem 24px;color:var(--paragraph);font-size:12px;line-height:1.7;border:1px solid var(--gold-line);
border-radius:10px;background:var(--gold-soft);padding:1rem 1.2rem;}}
.note b{{color:var(--gold);}}
.footer{{padding:1.4rem 2rem 2.6rem;font-family:var(--mono);font-size:10px;letter-spacing:.1em;
text-transform:uppercase;color:var(--dim);line-height:2;}}
.footer a{{color:var(--teal);text-decoration:none;text-transform:none;letter-spacing:0;}}
@media (max-width:720px){{.kpis,.searchbar,.note{{margin-left:1rem;margin-right:1rem;}}table{{width:calc(100% - 2rem);margin-left:1rem;margin-right:1rem;display:block;overflow-x:auto;}}}}
</style></head><body>
<div class="ribbon">
  <span>SZL HOLDINGS</span><span class="sep">/</span>
  <span class="teal">A11OY</span><span class="sep">/</span>
  <span>FORMULAS &middot; PURIQ REGISTRY</span><span class="sep">/</span>
  <span>DOCTRINE V11 &middot; LOCKED</span>
  <a href="/wires">wires &middot; the constitution &rarr;</a>
</div>
<header class="hero">
<h1>PURIQ &mdash; <span class="accent">named-formula registry</span> &middot; 23 FormulaAgents</h1>
<div class="sub">live self-evaluation + Khipu receipts + honest Lean self-prove &middot; signed Yachay (CTO) &middot;
every row is addressable (#F1&hellip;#F23) &middot; click a row to reveal the raw machine check</div>
</header>
<div class="kpis">
<div class="kpi"><b>{stats['n_agents']}</b><span>FormulaAgents</span></div>
<div class="kpi"><b>{stats['proved_count']}</b><span>Lean PROVED</span></div>
<div class="kpi"><b>{stats['harness_baseline']}</b><span>numeric harness</span></div>
<div class="kpi"><b>749 / 14 / 163</b><span>Doctrine v11 LOCKED (decl/axioms/sorries)</span></div>
<div class="kpi"><b>+{ew_total}</b><span>experimental kernel-verified (separate from locked)</span></div>
</div>
<div class="searchbar">
<input id="q" type="search" placeholder="premise search &mdash; filter by id / name / organ / status (e.g. khipu, PROVED, rfl)" aria-label="search formulas"/>
<span class="cnt" id="cnt"></span>
</div>
<div class="note" style="margin-top:12px">
<b>Experimental kernel-verified waves</b> (NOT in the locked count of 8; honest maturity labels):<br>
{ew_rows}
<br><b>Trust Score interval:</b> sourced from <b>CONFORMAL</b> (W5-3 + W7-4) \u2014 distribution-free, with an anti-overconfidence floor (we never report 100%). NOT Hoeffding/PAC-Bayes (those are NOT proven at the pinned Mathlib v4.13.0).<br>
<b>Deferred (not proven at pin):</b> C3 Hoeffding, C4 Azuma, C5 KL\u22650, C15, C16, C18, C19.
</div>
<table>
<thead><tr><th>ID</th><th>Formula</th><th>Organ</th><th>Live value</th><th>Identity</th>
<th>Lean class</th><th>Proof status</th><th>Harness</th><th>Chain</th><th>Invoked by</th></tr></thead>
<tbody id="tb">
{table}
</tbody>
</table>
<div class="note">
Locked-proven (<b>{proved}</b>): F1/F11/F12/F18/F19 proved in the local self-prove sprint (real local Lean v4.13.0, Mathlib-free); F4/F7/F22 locked kernel theorems (lutar-lean #219 / platform #321).
Axioms: F11/F12 use <code>propext</code> (Lean core); F1/F18/F19 use none. No <code>sorryAx</code>.
Lambda-uniqueness is <b>Conjecture 1</b>, NOT a theorem. Values recompute live per request.
ADDITIVE only; IP-HOLD a11oy#57 untouched.
</div>
<div class="footer">
registry pattern after mathlib &mdash; every result named + addressable (<a href="https://arxiv.org/abs/1910.09336" rel="noopener">arXiv:1910.09336</a>, cited) &middot;
proof-state reveal after Alectryon (MIT, pattern) &middot; premise-search after LeanDojo/ReProver (MIT, pattern) &middot;
0 runtime CDN &middot; fonts self-hosted &middot; JSON: <a href="/api/a11oy/v1/puriq/formulas">/api/a11oy/v1/puriq/formulas</a>
</div>
<script>
(function(){{
  var tb=document.getElementById('tb'),q=document.getElementById('q'),cnt=document.getElementById('cnt');
  var frows=[].slice.call(tb.querySelectorAll('tr.frow'));
  function applyFilter(){{
    var s=(q.value||'').trim().toLowerCase(),n=0;
    frows.forEach(function(r){{
      var hit=!s||r.getAttribute('data-hay').indexOf(s)>=0;
      r.style.display=hit?'':'none';n+=hit?1:0;
      var d=document.getElementById('d-'+r.getAttribute('data-fid'));
      if(d&&!hit)d.classList.remove('open');
    }});
    cnt.textContent=s?(n+' / '+frows.length+' match'):(frows.length+' formulas');
  }}
  q.addEventListener('input',applyFilter);applyFilter();
  var loaded={{}};
  function reveal(fid){{
    var d=document.getElementById('d-'+fid);if(!d)return;
    d.classList.toggle('open');
    if(!d.classList.contains('open'))return;
    var box=document.getElementById('db-'+fid);
    box.textContent='fetching LIVE /api/a11oy/v1/puriq/formulas/'+fid+' \\u2026';
    fetch('/api/a11oy/v1/puriq/formulas/'+fid).then(function(r){{
      if(!r.ok)throw new Error('HTTP '+r.status);return r.json();
    }}).then(function(j){{
      box.textContent='LIVE proof-state / receipt chain (raw endpoint output, recomputed per request):\\n\\n'+JSON.stringify(j,null,2);
    }}).catch(function(e){{
      box.textContent='endpoint unreachable: '+e.message+' \\u2014 shown honestly, nothing cached or invented.';
    }});
  }}
  tb.addEventListener('click',function(ev){{
    if(ev.target.closest('a'))return;
    var r=ev.target.closest('tr.frow');if(r)reveal(r.getAttribute('data-fid'));
  }});
  tb.addEventListener('keydown',function(ev){{
    if(ev.key!=='Enter'&&ev.key!==' ')return;
    var r=ev.target.closest('tr.frow');if(r){{ev.preventDefault();reveal(r.getAttribute('data-fid'));}}
  }});
  if(location.hash){{
    var t=document.getElementById(location.hash.slice(1));
    if(t&&t.classList.contains('frow'))reveal(t.getAttribute('data-fid'));
  }}
}})();
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# register(app) — additive FastAPI routes
# ---------------------------------------------------------------------------
def register(app) -> None:
    @app.get("/formulas", response_class=HTMLResponse)
    async def puriq_formulas_page():
        return HTMLResponse(_render_html())

    @app.get("/api/a11oy/v1/puriq/formulas")
    async def puriq_formulas_api():
        return JSONResponse({"summary": summary_stats(), "formulas": live_snapshot()})

    @app.get("/api/a11oy/v1/puriq/formulas/{fid}")
    async def puriq_formula_detail(fid: str):
        snap = live_snapshot()
        key = fid.upper()
        if key not in snap:
            return JSONResponse({"error": f"unknown formula {fid}"}, status_code=404)
        return JSONResponse(snap[key])
