#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings — Doctrine v11
"""Reproducibility guard for the a11oy PINN benchmark — the CLASSICAL (SZL) arm.

honesty_guard.py proves the artifact's LABELS are internally consistent. This
guard goes one step further and makes "measured, not asserted" enforceable: it
RE-DERIVES the SZL governed classical-spectral arm from source on this machine and
asserts the freshly computed numbers still match the committed results.json. So if
anyone edits a solver (szl_pinn_nonlinear / szl_governed_ipinn / szl_pinn_inverse)
or run_bench.py without regenerating the artifact, the build fails.

Only the SZL arm is reproduced here: it is NumPy-only, deterministic, and fast
(<1s). The DeepXDE and NVIDIA PhysicsNeMo/Modulus neural arms require a CUDA GPU +
PyTorch and are far too expensive for CI; results.json labels them MEASURED-on-GPU
and the /benchmark page discloses that they are not re-run in CI.

Tolerances are NOT bit-exact by design. GitHub-hosted runners have heterogeneous
CPU microarchitectures, so LAPACK/OpenBLAS last-bit results can drift and that
drift is amplified through the Newton / gradient iterations. We verify the CLAIM,
not the bits:
  * Poisson  rel_l2 : absolute < 1e-12   (the claim is "~machine precision, in-basis")
  * Burgers  rel_l2 : relative within 1e-6 of committed, AND newton_iterations exact
  * Duffing  abs_err: relative within 1e-6 of committed
Wall-clock time is never compared.

Usage:
    python benchmarks/pinn/reproduce_szl_guard.py                 # default artifact
    python benchmarks/pinn/reproduce_szl_guard.py path/to/x.json  # explicit
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# run_bench only DEFINES functions at import time (numpy + szl_* are imported lazily
# inside run_szl); importing it also puts the repo root on sys.path for the solvers.
import run_bench  # noqa: E402

POISSON_ATOL = 1e-12
RTOL = 1e-6


def _szl_arm(results: dict, id_prefix: str) -> dict:
    for prob in results.get("problems", []):
        if str(prob.get("id", "")).startswith(id_prefix):
            for arm in prob.get("arms", []):
                if arm.get("framework") == "szl":
                    return arm
    raise SystemExit(
        f"[reproduce-szl] committed results.json has no szl arm for '{id_prefix}'")


def _rel_close(got: float, want: float, rtol: float) -> bool:
    return math.isclose(got, want, rel_tol=rtol, abs_tol=0.0)


def main(argv: list[str]) -> int:
    results_path = Path(argv[0]) if argv else (HERE / "results.json")
    if not results_path.exists():
        print(f"[reproduce-szl] MISSING committed artifact: {results_path}", file=sys.stderr)
        return 2
    committed = json.loads(results_path.read_text())

    print("[reproduce-szl] re-deriving the SZL classical-spectral arm from source ...")
    fresh = run_bench.run_szl()

    checks: list[tuple[str, bool, str]] = []

    # Poisson — verify the ~machine-precision, in-basis claim (absolute threshold;
    # do NOT pin to the exact near-eps value, which can wobble across BLAS kernels).
    p_fresh = fresh["poisson"]["rel_l2_vs_exact"]
    checks.append(("poisson rel_l2 < %g (in-basis, ~machine precision)" % POISSON_ATOL,
                   p_fresh < POISSON_ATOL, "recomputed=%.3e" % p_fresh))

    # Burgers — match committed rel_l2 within rtol AND newton iterations exactly.
    b_fresh = fresh["burgers"]["rel_l2_vs_exact"]
    b_arm = _szl_arm(committed, "steady_burgers")
    b_want = b_arm["rel_l2_vs_exact"]
    checks.append(("burgers rel_l2 within rtol %g of committed" % RTOL,
                   _rel_close(b_fresh, b_want, RTOL),
                   "recomputed=%.6e committed=%.6e" % (b_fresh, b_want)))
    n_fresh = fresh["burgers"]["newton_iterations"]
    n_want = b_arm.get("newton_iterations")
    checks.append(("burgers newton_iterations exact", n_fresh == n_want,
                   "recomputed=%s committed=%s" % (n_fresh, n_want)))

    # Duffing — match committed abs_err within rtol.
    d_fresh = fresh["duffing"]["abs_err"]
    d_want = _szl_arm(committed, "inverse_duffing")["abs_err"]
    checks.append(("duffing abs_err within rtol %g of committed" % RTOL,
                   _rel_close(d_fresh, d_want, RTOL),
                   "recomputed=%.6e committed=%.6e" % (d_fresh, d_want)))

    ok = True
    for name, passed, detail in checks:
        print("  [%s] %s  (%s)" % ("PASS" if passed else "FAIL", name, detail))
        ok = ok and passed

    if not ok:
        print("[reproduce-szl] FAILED — committed SZL numbers do NOT reproduce from source.")
        print("                Regenerate: python benchmarks/pinn/run_bench.py --arm szl && "
              "python benchmarks/pinn/run_bench.py --assemble "
              "--out benchmarks/pinn/results.json")
        return 1
    print("[reproduce-szl] OK — committed SZL classical arm reproduces from source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
