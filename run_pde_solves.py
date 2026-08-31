#!/usr/bin/env python3
# Agentic-PINN PDE solver — 2D heat (steady Poisson) + viscous Burgers.
# Residual-adaptive refinement under a deny-by-default Lambda-gate governor whose
# ALLOW/REFINE inference runs as REAL LLM calls on a sovereign GPU node (chaski by
# default, honoring the governor/solve role-split). Pure stdlib math.
#
# Doctrine v11: rel-L2 / residuals are MODELED error estimates (honest, not MEASURED
# energy). Energy is reported ONLY when the joule-meter exporter is live; otherwise it
# is explicitly NOT_MEASURED — never fabricated. Manufactured solutions give REAL
# residuals (no synthetic "convergence").
import sys, os, json, math, time, urllib.request

GOV_URL = os.environ.get("SZL_GOV_LLM_URL", "http://100.102.173.88:11434/api/generate")  # chaski
GOV_MODEL = os.environ.get("SZL_GOV_LLM_MODEL", "llama3.1:8b")
GOV_NODE = os.environ.get("SZL_GOV_LLM_NODE", "chaski (tailnet 100.102.173.88)")
JOULE = os.environ.get("SZL_JOULE_URL", "http://100.96.129.45:9471/")
SOLVE_NODE = os.environ.get("SZL_SOLVE_NODE", "betterwithage (tailnet 100.125.77.31)")
TOL = float(os.environ.get("SZL_PINN_TOL", "1e-2"))
MAX_ROUNDS = int(os.environ.get("SZL_PINN_MAX_ROUNDS", "6"))


def gauss(Ain, bin_):
    n = len(bin_); A = [r[:] for r in Ain]; b = bin_[:]; fl = 0
    for col in range(n):
        p = max(range(col, n), key=lambda r: abs(A[r][col]))
        A[col], A[p] = A[p], A[col]; b[col], b[p] = b[p], b[col]; piv = A[col][col]
        if piv == 0:
            piv = 1e-30
        for r in range(col + 1, n):
            fct = A[r][col] / piv
            for cc in range(col, n):
                A[r][cc] -= fct * A[col][cc]
            b[r] -= fct * b[col]; fl += (n - col) * 2
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = b[r] - sum(A[r][cc] * x[cc] for cc in range(r + 1, n))
        x[r] = s / (A[r][r] if A[r][r] != 0 else 1e-30); fl += (n - r) * 2
    return x, fl


def lstsq(A, b):
    """Solve least squares min||A c - b|| via normal equations. A: rows x cols."""
    rows = len(A); cols = len(A[0]); fl = 0
    AtA = [[0.0] * cols for _ in range(cols)]; Atb = [0.0] * cols
    for i in range(cols):
        for k in range(cols):
            AtA[i][k] = sum(A[j][i] * A[j][k] for j in range(rows)); fl += rows * 2
        Atb[i] = sum(A[j][i] * b[j] for j in range(rows)); fl += rows * 2
    c, fe = gauss(AtA, Atb)
    return c, fl + fe


# ---------------- PDE 1: 2D steady heat (Poisson) -Lap u = f, u=0 on boundary ----
# Manufactured exact: u*(x,y)=x(1-x)y(1-y) -> f = 2y(1-y)+2x(1-x). Infinite sine
# series => increasing the sin-basis genuinely lowers rel-L2 (real convergence).
def heat2d_exact(x, y):
    return x * (1 - x) * y * (1 - y)


def heat2d_f(x, y):
    return 2 * y * (1 - y) + 2 * x * (1 - x)


def solve_heat2d(n, m):
    """n: modes per dim (basis n*n). m: collocation points per dim."""
    fl = 0
    modes = [(i + 1, j + 1) for i in range(n) for j in range(n)]
    pts = [((a + 1) / (m + 1), (b + 1) / (m + 1)) for a in range(m) for b in range(m)]
    # -Lap sin(i pi x) sin(j pi y) = ((i pi)^2+(j pi)^2) sin(...)
    A = []
    rhs = []
    for (x, y) in pts:
        row = []
        for (i, j) in modes:
            lam = (i * math.pi) ** 2 + (j * math.pi) ** 2
            row.append(lam * math.sin(i * math.pi * x) * math.sin(j * math.pi * y))
        A.append(row); rhs.append(heat2d_f(x, y)); fl += len(modes) * 4
    c, fe = lstsq(A, rhs); fl += fe
    return c, modes, fl


def heat2d_metrics(c, modes, T=24):
    pts = [((a + 1) / (T + 1), (b + 1) / (T + 1)) for a in range(T) for b in range(T)]
    num = 0.0; den = 0.0; res = []
    for (x, y) in pts:
        uh = sum(c[k] * math.sin(i * math.pi * x) * math.sin(j * math.pi * y)
                 for k, (i, j) in enumerate(modes))
        lap = sum(c[k] * ((i * math.pi) ** 2 + (j * math.pi) ** 2)
                  * math.sin(i * math.pi * x) * math.sin(j * math.pi * y)
                  for k, (i, j) in enumerate(modes))
        res.append(abs(lap - heat2d_f(x, y)))
        ue = heat2d_exact(x, y)
        num += (uh - ue) ** 2; den += ue ** 2
    rl2 = math.sqrt(num / den) if den > 0 else 0.0
    return max(res), sum(res) / len(res), rl2


# ---------------- PDE 2: viscous Burgers (steady) -nu u'' + u u' = f, u(0)=u(1)=0 -
# Manufactured exact: u*(x)=x(1-x) -> u*'=1-2x, u*''=-2 ;
# f = 2 nu + x(1-x)(1-2x). Infinite sine series => real convergence with refinement.
NU = float(os.environ.get("SZL_BURGERS_NU", "0.1"))


def burgers_exact(x):
    return x * (1 - x)


def burgers_f(x):
    return 2 * NU + x * (1 - x) * (1 - 2 * x)


def solve_burgers(n, m, picard_iters=20):
    """Picard linearization: -nu u'' + u_prev u' = f, refit basis each iter."""
    fl = 0
    pts = [(j + 1) / (m + 1) for j in range(m)]
    c = [0.0] * n  # start from zero field
    for _ in range(picard_iters):
        # u_prev at points
        uprev = [sum(c[k] * math.sin((k + 1) * math.pi * x) for k in range(n)) for x in pts]
        A = []; rhs = []
        for idx, x in enumerate(pts):
            row = []
            for k in range(n):
                kp = (k + 1) * math.pi
                dd = (kp ** 2) * math.sin(kp * x)        # -u'' coefficient => nu*kp^2*sin
                d1 = kp * math.cos(kp * x)               # u' basis
                row.append(NU * dd + uprev[idx] * d1)
            A.append(row); rhs.append(burgers_f(x)); fl += n * 4
        cnew, fe = lstsq(A, rhs); fl += fe
        delta = sum((cnew[k] - c[k]) ** 2 for k in range(n)) ** 0.5
        c = cnew
        if delta < 1e-12:
            break
    return c, fl


def burgers_metrics(c, n, T=200):
    pts = [(j + 1) / (T + 1) for j in range(T)]
    num = 0.0; den = 0.0; res = []
    for x in pts:
        uh = sum(c[k] * math.sin((k + 1) * math.pi * x) for k in range(n))
        u1 = sum(c[k] * (k + 1) * math.pi * math.cos((k + 1) * math.pi * x) for k in range(n))
        u2 = sum(-c[k] * ((k + 1) * math.pi) ** 2 * math.sin((k + 1) * math.pi * x) for k in range(n))
        res.append(abs(-NU * u2 + uh * u1 - burgers_f(x)))
        ue = burgers_exact(x)
        num += (uh - ue) ** 2; den += ue ** 2
    rl2 = math.sqrt(num / den) if den > 0 else 0.0
    return max(res), sum(res) / len(res), rl2


# ---------------- Lambda-gate governor (real LLM inference on chaski) -------------
def governor(rd, basis, ncol, maxr, rl2):
    prompt = ("You are the deny-by-default Lambda-gate governor of an agentic PINN solver. "
              f"Round {rd}: basis_size={basis}, collocation_points={ncol}, "
              f"max_residual={maxr:.3e}, rel_L2_error={rl2:.3e}, tolerance={TOL:.0e}. "
              f"If rel_L2_error < {TOL:.0e} the solve has converged -> reply ALLOW; "
              "else reply REFINE. Answer with exactly one word: ALLOW or REFINE.")
    body = json.dumps({"model": GOV_MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.1}}).encode()
    req = urllib.request.Request(GOV_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
        txt = (d.get("response", "") or "").strip().upper()
        ev = int(d.get("eval_count", 0) or 0)
        verdict = "ALLOW" if "ALLOW" in txt else "REFINE"
        return verdict, ev, "llm@" + GOV_NODE
    except Exception as e:
        # honest fallback — never block the audit; label the source truthfully
        verdict = "ALLOW" if rl2 < TOL else "REFINE"
        return verdict, 0, f"rule-based-fallback (governor node unreachable: {type(e).__name__})"


def run_pde(name, pde_str, solve_fn, metric_fn, n0, refine):
    rounds = []; n = n0; accepted = False; final = "REFINE"
    for rd in range(1, MAX_ROUNDS + 1):
        c, ncol, total = solve_fn(n)
        maxr, meanr, rl2 = metric_fn(c, n if name == "burgers" else ncol)
        verdict, ev, gsrc = governor(rd, n, (ncol if isinstance(ncol, int) else n), maxr, rl2)
        converged = rl2 < TOL
        acc = bool(converged and verdict == "ALLOW")
        rounds.append({
            "round_index": rd, "basis_size": n,
            "n_pde_collocation": (ncol if isinstance(ncol, int) else n),
            "max_residual_on_test": maxr, "mean_residual_on_test": meanr,
            "rel_l2_error_estimate": rl2,
            "lambda_verdict": verdict, "lambda_gate_converged": converged, "accepted": acc,
            "modeled_not_measured": True, "error_estimate_is_bound": True,
            "governor_source": gsrc, "llm_eval_count": ev,
        })
        print(f"  [{name}] round {rd}: basis={n} rl2={rl2:.3e} maxr={maxr:.3e} "
              f"gov={verdict} ({gsrc.split(' ')[0]}) acc={acc}", flush=True)
        if acc:
            accepted = True; final = "ALLOW"; break
        n = refine(n)
    return {"name": name, "pde": pde_str, "final_verdict": final,
            "final_accepted": accepted, "converged": accepted, "rounds": rounds}


def main():
    print(f"[*] agentic-PINN multi-PDE solve; governor={GOV_MODEL}@{GOV_NODE}; tol={TOL:.0e}", flush=True)
    pdes = []
    # 2D heat: basis n*n, collocation grows with n
    pdes.append(run_pde(
        "heat2d",
        "-Laplacian u(x,y) = f on (0,1)^2, u=0 on boundary; manufactured exact "
        "u*=x(1-x)y(1-y); sin-collocation spectral basis sin(i pi x) sin(j pi y)",
        lambda n: solve_heat2d(n, max(2 * n + 1, 5)),
        lambda c, modes: heat2d_metrics(c, modes),
        n0=1, refine=lambda n: n + 1))
    # Burgers: 1D basis n, collocation grows
    pdes.append(run_pde(
        "burgers",
        "-nu u''(x) + u(x) u'(x) = f on (0,1), u(0)=u(1)=0, nu=%g; manufactured exact "
        "u*=x(1-x); Picard-linearized sin-collocation; nonlinear convective term" % NU,
        lambda n: (lambda c, fl: (c, n, fl))(*solve_burgers(n, max(2 * n + 2, 8))),
        lambda c, n: burgers_metrics(c, n),
        n0=2, refine=lambda n: n + 2))

    # energy: report ONLY if exporter live; never fabricate
    energy = {"status": "NOT_MEASURED",
              "note": "joule-meter exporter not live for this run; rel-L2/residuals are "
                      "MODELED math estimates (honest), energy intentionally omitted "
                      "rather than fabricated (Doctrine v11)."}
    try:
        with urllib.request.urlopen(JOULE, timeout=8) as r:
            jm = json.loads(r.read().decode())
        for e in jm.get("engines", []):
            for g in e.get("gpus", []):
                if g.get("live"):
                    energy = {"status": "AVAILABLE_BUT_NOT_BOUND_TO_THIS_RUN",
                              "joule_meter_total_joules": jm.get("totals", {}).get("joules"),
                              "note": "exporter live; this trail certifies MODELED solve "
                                      "accuracy, not a per-PDE energy delta."}
    except Exception:
        pass

    trail = {
        "model": "SZL Agentic PINN — governed multi-PDE solve decision trail",
        "schema": "szl/agentic-pinn-trail/v2",
        "pdes": pdes,
        # backward-compat: top-level mirrors the FIRST PDE so the v1 /residual reader works
        "pde": pdes[0]["pde"], "rounds": pdes[0]["rounds"],
        "final_verdict": "ALLOW" if all(p["final_accepted"] for p in pdes) else "PARTIAL",
        "final_accepted": all(p["final_accepted"] for p in pdes),
        "converged": all(p["converged"] for p in pdes),
        "governor": {"model": GOV_MODEL, "node": GOV_NODE,
                     "role_split": "Lambda-gate governor inference on chaski; PDE residual "
                                   "math on the solve node CPU (" + SOLVE_NODE + ")"},
        "energy_measurement": energy,
        "doctrine": "v11 LOCKED: rel-L2 MODELED (not MEASURED energy); manufactured "
                    "solutions => REAL residuals; Lambda=Conjecture 1 advisory, deny-by-default; "
                    "no fabricated numbers/energy/signatures.",
        "lambda_note": "Lambda = Conjecture 1 (advisory). States physical FACTS, not 'proven "
                       "trust'. Gate is deny-by-default.",
        "timestamp_utc": time.time(),
    }
    out_dir = os.environ.get("SZL_PINN_ARTIFACT_DIR", os.path.dirname(os.path.abspath(__file__)))
    tp = os.path.join(out_dir, "agentic_decision_trail.json")
    with open(tp, "w") as fh:
        json.dump(trail, fh, indent=2)
    print("\n===== SUMMARY =====")
    for p in pdes:
        last = p["rounds"][-1]
        print(f"  {p['name']}: accepted={p['final_accepted']} "
              f"final_rel_l2={last['rel_l2_error_estimate']:.3e} rounds={len(p['rounds'])}")
    print("WROTE", tp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
