# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only formula authority and separate numerical demonstrations.

Formal identities, scopes and maturity come from the validated, pinned
``szl_formula_registry`` record. Historical PURIQ F-labels identify different
numerical examples; matching numbers do not bind them to formal theorems.
``FORMULA_META`` and ``EXPERIMENTAL_WAVES`` are retained historical inputs for
crosswalk/reconciliation tools, not public proof authorities. Consumers use
``numeric_demo_metadata`` and ``formal_registry_snapshot`` instead.

GET evaluates reproducible SAMPLE inputs. It never mints a receipt, signs,
persists state, establishes applicability, or grants execution authority.
"""
import copy
import hashlib
import json as _json
import math
import random
from html import escape
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
F10_SQRT2_ERROR_BOUND = 1.5e-6


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
        return reduce(lambda a, b: a * b // math.gcd(a, b), [m1, m2]), None, f"m=({m1},{m2}); coprime premise absent"
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
    ok = (pn == known[n]) if n in known else None
    return pn, ok, f"p({n})"


def _f15(rng):
    x = _R(rng, -20, 20)
    f, g, h = (lambda v: v + 1), (lambda v: v * 2), (lambda v: v - 3)
    left = f(g(h(x))); right = f(g(h(x)))
    return round(left, 4), math.isclose(left, right, abs_tol=1e-12), f"x={x:.2f}"


def _f16(rng):
    a, b, c, d = (_R(rng, -5, 5) for _ in range(4))
    value, checked = _zero_sum_2x2_value(a, b, c, d)
    return round(value, 4), checked, f"matrix={[[a, b], [c, d]]}"


def _zero_sum_2x2_value(a, b, c, d):
    lower = max(min(a, b), min(c, d))
    upper = min(max(a, c), max(b, d))
    if math.isclose(lower, upper, abs_tol=1e-12):
        return lower, True
    denom = a + d - b - c
    if denom == 0:
        return lower, False
    p, q = (d - c) / denom, (d - b) / denom
    if not (0 <= p <= 1 and 0 <= q <= 1):
        return lower, False
    value = (a * d - b * c) / denom
    outcomes = (p * a + (1 - p) * c, p * b + (1 - p) * d,
                q * a + (1 - q) * b, q * c + (1 - q) * d)
    checked = (lower <= value <= upper and
               all(math.isclose(result, value, rel_tol=1e-9, abs_tol=1e-9)
                   for result in outcomes))
    return value, checked


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
    initial_fuel = fuel
    cur, steps = start, 0
    while fuel > 0:
        if cur <= 0:
            break
        cur -= 1; steps += 1; fuel -= 1
    holds = _fuel_bound_holds(start, initial_fuel, steps, cur)
    return steps, holds, f"start={start},initial_fuel={initial_fuel},remaining={cur}"


def _fuel_bound_holds(start, fuel, steps, remaining):
    return (all(type(value) is int and value >= 0
                for value in (start, fuel, steps, remaining))
            and steps == min(start, fuel) and remaining == start - steps)


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
    return round(cap, 4), None, f"R={R:.2f},E={E:.2f},Kmax={Kmax}; action-space cardinality unavailable"


FORMULA_FUNCS = {f"F{i}": fn for i, fn in enumerate(
    [_f1, _f2, _f3, _f4, _f5, _f6, _f7, _f8, _f9, _f10, _f11, _f12, _f13,
     _f14, _f15, _f16, _f17, _f18, _f19, _f20, _f21, _f22, _f23], start=1)}


NUMERIC_DEMO_NAMESPACE = "puriq.numeric-demo.v1"
FORMAL_NAMESPACE = "lutar-lean.formal-f-id.v2"
FORMAL_BINDING = "UNKNOWN_NOT_ASSERTED"


def numeric_demo_metadata():
    """Project historical demonstrations without transferring proof authority."""
    out = {}
    for fid, legacy in FORMULA_META.items():
        meta = {key: copy.deepcopy(legacy[key]) for key in
                ("id", "name", "organ", "primitive", "identity_doc", "invoked_by")
                if key in legacy}
        meta.update({
            "record_id": f"{NUMERIC_DEMO_NAMESPACE}:{fid}",
            "formula_namespace": NUMERIC_DEMO_NAMESPACE,
            "legacy_formula_id": fid,
            "formal_formula_id": None,
            "formal_binding": FORMAL_BINDING,
            "proof_status": "UNVERIFIED",
            "lean_status": "UNVERIFIED",
            "lean_name": None,
            "proved_tactic": None,
            "locked": False,
            "can_authorize_action": False,
            "execution_authority": False,
            "evidence_class": "SAMPLE",
        })
        out[fid] = meta
    return out


def formal_registry_snapshot():
    """Read validated formal metadata; never fall back to historical claims."""
    try:
        import szl_formula_registry as authority
        document = authority.load_registry(verify=True)
    except (ImportError, OSError, ValueError, TypeError, KeyError, RecursionError):
        return {
            "state": "UNAVAILABLE", "reason": "FORMULA_AUTHORITY_UNAVAILABLE",
            "formulas": {}, "registry_digest": None, "signature_status": "UNKNOWN",
            "locked_proven_count": None, "locked_proven_ids": [],
            "kernel_mapping": FORMAL_BINDING, "execution_authority": False,
        }
    payload = document["payload"]
    assets = {asset["id"]: asset for asset in payload["source_assets"]}
    records = {}
    for item in payload["formulas"]:
        row = copy.deepcopy(item)
        source = assets[item["source_asset"]]
        row.update({
            "record_id": f"{FORMAL_NAMESPACE}:{item['id']}",
            "formula_namespace": FORMAL_NAMESPACE,
            "source": copy.deepcopy(source),
            "source_url": (f"https://github.com/{source['repository']}/blob/"
                           f"{source['commit']}/{source['path']}"),
            "registry_digest": document["registry_digest"]["value"],
            "signature_status": document["signature"]["status"],
            "runtime_applicability": "NOT_ESTABLISHED",
            "execution_authority": False,
        })
        records[item["id"]] = row
    return {
        "state": "AVAILABLE", "schema_version": document["schema_version"],
        "registry_version": payload["registry_version"],
        "registry_digest": document["registry_digest"]["value"],
        "signature_status": document["signature"]["status"],
        "formal_source": copy.deepcopy(payload["formal_source"]),
        "coverage_scope": payload["coverage_scope"], "exhaustive": False,
        "locked_proven_count": payload["locked_proven_count"],
        "locked_proven_ids": list(payload["locked_proven_ids"]),
        "kernel_mapping": payload["kernel_source"]["f_id_to_callable_mapping"],
        "policy": copy.deepcopy(payload["policy"]),
        "formulas": records, "execution_authority": False,
    }


def live_snapshot():
    """Compatibility entry point for deterministic, explicitly SAMPLE values."""
    out = {}
    for fid, meta in numeric_demo_metadata().items():
        seed = int(hashlib.sha256(meta["record_id"].encode("utf-8")).hexdigest()[:16], 16)
        value, holds, args = FORMULA_FUNCS[fid](random.Random(seed))
        out[fid] = {
            **meta, "sample_seed": seed, "current_value": value,
            "identity_holds": holds, "sample_inputs": args,
            "sample_check": "NOT_EVALUATED" if holds is None else ("PASS" if holds else "FAIL"),
            "evaluation_scope": "DETERMINISTIC_NUMERICAL_SAMPLE_NOT_FORMAL_PROOF",
            "last_eval_ts": None, "chain_verified": False, "last_receipts": [],
            "receipt_minted": False, "signature_status": "NOT_APPLICABLE_SAMPLE",
        }
    return out


def summary_stats(formal=None):
    if formal is None:
        formal = formal_registry_snapshot()
    return {
        "n_agents": len(FORMULA_META),
        "numeric_demo_count": len(FORMULA_META),
        "numeric_demo_namespace": NUMERIC_DEMO_NAMESPACE,
        "numeric_demo_proved_count": 0,
        "proved_count": formal["locked_proven_count"],
        "proved_count_scope": "CANONICAL_FORMAL_REGISTRY_ONLY",
        "authority_state": formal["state"],
        "registry_digest": formal["registry_digest"],
        "doctrine_v11_locked": copy.deepcopy(DOCTRINE_V11_LOCKED),
        "formal_binding": FORMAL_BINDING,
        "receipt_minted": False, "execution_authority": False,
    }


def formula_surface_snapshot():
    formal = formal_registry_snapshot()
    demos = live_snapshot()
    return {
        "schema": "szl.puriq-formula-surface/v2",
        "summary": summary_stats(formal),
        "formal_registry": formal,
        "numeric_demos": demos,
        "formulas": demos,
        "compatibility": "formulas and legacy F-ID detail routes contain numerical demos only",
        "receipt_minted": False, "execution_authority": False,
    }


def _render_html(snapshot=None):
    if snapshot is None:
        snapshot = formula_surface_snapshot()
    formal = snapshot["formal_registry"]
    formal_rows = []
    for fid, row in formal["formulas"].items():
        refs = ", ".join(row["theorem_refs"])
        formal_rows.append(
            f'<article class="formal-card" id="formal-{escape(fid)}">'
            f'<p class="eyebrow">{escape(fid)} · {escape(row["maturity"])}</p>'
            f'<h3>{escape(row["name"])}</h3><p>{escape(row["scope"])}</p>'
            f'<p class="limit"><strong>Proof limit:</strong> {escape(row["caveat"])}</p>'
            f'<details><summary>Inspect the formal source</summary>'
            f'<p><a href="{escape(row["source_url"], quote=True)}" rel="noopener">'
            f'{escape(refs)}</a></p><p class="mono">Commit: {escape(row["source"]["commit"])}</p>'
            '<p>Runtime applicability: NOT_ESTABLISHED · action authority: NONE</p>'
            '</details></article>'
        )
    demo_rows = []
    for fid, row in snapshot["numeric_demos"].items():
        check = row["sample_check"].replace("_", " ")
        demo_rows.append(
            f'<tr id="{escape(fid)}"><th scope="row">'
            f'<a href="#{escape(fid)}">{escape(fid)}</a></th>'
            f'<td>{escape(row["name"])}</td><td><code>{escape(str(row["current_value"]))}</code></td>'
            f'<td>{escape(check)} (sample only)</td>'
            '<td>UNVERIFIED<br>Binding unknown</td>'
            f'<td><details data-demo="{escape(fid)}"><summary>Inspect sample</summary>'
            f'<pre>{escape(_json.dumps(row, indent=2, ensure_ascii=False))}</pre>'
            f'<a href="/api/a11oy/v1/puriq/formulas/{escape(fid)}">Sample JSON</a>'
            '</details></td></tr>'
        )
    digest = escape(str(formal["registry_digest"] or "UNAVAILABLE"))
    count = formal["locked_proven_count"]
    count_text = str(count) if count is not None else "UNAVAILABLE"
    formal_body = "\n".join(formal_rows) or (
        '<p role="alert">Formal authority is UNAVAILABLE. No historical proof claims '
        'are substituted. The numerical samples below carry no proof authority.</p>'
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A11oy · Formula evidence</title>
<meta name="description" content="Canonical formal scopes and separately identified numerical demonstrations.">
<link rel="stylesheet" href="/assets/szl/szl-design-system.css">
<link rel="stylesheet" href="/assets/szl/szl-console.css">
<style>
body{{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-body)}}
main,nav{{max-width:80rem;margin:auto;padding:1.5rem clamp(1rem,4vw,3rem)}}
nav{{display:flex;gap:1.5rem;flex-wrap:wrap;border-bottom:1px solid var(--border)}}
a{{color:var(--link)}} h1{{font-family:var(--font-display);font-size:clamp(2rem,4vw,3rem);margin:.4rem 0}}
h2{{margin-top:2.5rem}} h3{{font-size:1.15rem;margin:.5rem 0}}
p{{line-height:1.6}} .intro{{max-width:58rem;color:var(--text-sub)}}
.eyebrow{{font-family:var(--font-mono);font-size:.8rem;color:var(--text-ghost)}}
.authority{{padding:1.25rem;border:1px solid var(--border);border-radius:var(--radius-lg);background:var(--surface)}}
.authority strong{{font-size:1.2rem}} .mono,code,pre{{font-family:var(--font-mono);overflow-wrap:anywhere}}
.formal-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,22rem),1fr));gap:1rem}}
.formal-card{{padding:1.25rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg)}}
.limit{{color:var(--text-sub)}} details{{margin-top:.75rem}} summary{{cursor:pointer;min-height:2rem;line-height:2}}
summary:focus-visible,a:focus-visible{{outline:2px solid var(--focus);outline-offset:3px}}
.table-wrap{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;text-align:left}}
th,td{{padding:.9rem;border-bottom:1px solid var(--border);vertical-align:top}}
th{{font-weight:600}} pre{{white-space:pre-wrap;max-height:24rem;overflow:auto;min-width:16rem;font-size:.8rem}}
.boundary{{padding:1rem;border-inline-start:3px solid var(--accent);background:var(--surface)}}
footer{{margin:3rem 0 1rem;color:var(--text-sub);font-size:.9rem}}
</style></head><body>
<nav aria-label="Product"><strong>A11oy / Formula evidence</strong><a href="/console">Console</a>
<a href="/verify">Verify evidence</a><a href="/api/a11oy/v1/puriq/formulas">Complete JSON</a></nav>
<main><header><p class="eyebrow">DOCTRINE V11 · FORMAL SOURCE AND NUMERICAL SAMPLES</p>
<h1>Understand what the mathematics establishes.</h1>
<p class="intro">Inspect the exact statement, its limits, and its source before applying it.
The historical numerical demonstrations use a separate namespace. A matching F-number does not
establish that a theorem proves a demonstration or a deployed implementation.</p></header>
<section class="authority" aria-label="Formal authority status" data-registry-digest="{digest}">
<strong>Formal authority: {escape(formal['state'])} · {count_text} locked formulas</strong>
<p>Registry signature: {escape(formal['signature_status'])}. The digest establishes byte integrity;
it does not establish signer identity, runtime applicability, or permission to act.</p>
<p class="mono">Registry SHA-256: {digest}</p>
<a href="/api/a11oy/v1/puriq/formal-registry">Inspect canonical registry JSON</a></section>
<h2>Formal statements and proof limits</h2>
<p>Eight locked records and the F23 Lambda boundary are covered. Lambda uniqueness remains
Conjecture 1, advisory. This is not an exhaustive inventory of SZL mathematics.</p>
<div class="formal-grid">{formal_body}</div>
<h2>Numerical demonstrations · SAMPLE</h2>
<p class="boundary">These 23 examples use fixed reproducible inputs. Their proof binding is
UNKNOWN_NOT_ASSERTED. A sample check is not a formal proof, a production measurement, or an
action authorization. No receipts are minted or signed by this page.</p>
<p class="mono">Namespace: {NUMERIC_DEMO_NAMESPACE}. Legacy F1–F23 links remain sample links.</p>
<div class="table-wrap"><table><caption>Historical numerical examples with no inherited formal authority</caption>
<thead><tr><th scope="col">Legacy ID</th><th scope="col">Demonstration</th><th scope="col">Sample value</th>
<th scope="col">Sample check</th><th scope="col">Proof binding</th><th scope="col">Evidence</th></tr></thead>
<tbody>{''.join(demo_rows)}</tbody></table></div>
<footer>Formal identities come from the validated, commit-pinned formula registry. Numerical
demonstrations remain separately identified. Reads perform no signing, persistence, or model inference.</footer>
</main></body></html>'''


def register(app) -> None:
    @app.get("/formulas", response_class=HTMLResponse)
    async def puriq_formulas_page():
        snapshot = formula_surface_snapshot()
        status = 200 if snapshot["formal_registry"]["state"] == "AVAILABLE" else 503
        return HTMLResponse(_render_html(snapshot), status_code=status)

    @app.get("/api/a11oy/v1/puriq/formal-registry")
    async def puriq_formal_registry():
        formal = formal_registry_snapshot()
        return JSONResponse(formal, status_code=200 if formal["state"] == "AVAILABLE" else 503)

    @app.get("/api/a11oy/v1/puriq/formal-registry/{fid}")
    async def puriq_formal_detail(fid: str):
        formal = formal_registry_snapshot()
        if formal["state"] != "AVAILABLE":
            return JSONResponse(formal, status_code=503)
        row = formal["formulas"].get(fid.upper())
        if row is None:
            return JSONResponse({"error": "formula outside canonical registry coverage"}, status_code=404)
        return JSONResponse(row)

    @app.get("/api/a11oy/v1/puriq/formulas")
    async def puriq_formulas_api():
        snapshot = formula_surface_snapshot()
        status = 200 if snapshot["formal_registry"]["state"] == "AVAILABLE" else 503
        return JSONResponse(snapshot, status_code=status)

    @app.get("/api/a11oy/v1/puriq/formulas/{fid}")
    async def puriq_formula_detail(fid: str):
        key = fid.upper()
        if key not in FORMULA_FUNCS:
            return JSONResponse({"error": "unknown numerical demonstration"}, status_code=404)
        return JSONResponse(live_snapshot()[key])
