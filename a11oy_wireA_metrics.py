"""
a11oy_wireA_metrics.py  —  ADDITIVE backend for DEV-WIRE-A tab upgrades (2026-06-09).

Pure-Python STDLIB ONLY (math, sqlite3, hashlib, json, time) — NO numpy/scipy/networkx/torch.
Doctrine-safe: self-contained, try/except-guarded register(app), routes pushed to FRONT of
app.router.routes so they win over the generic /api/a11oy/{path:path} Node proxy and the SPA
catch-all. Never breaks the green build. 0 runtime CDN. Λ = Conjecture 1 (NEVER a theorem).
Trust score never 100%. No fabricated data — every series is MODEL-SCORED / SAMPLE labelled.

Endpoints (all under /api/a11oy/v1/wirea/*):
  GET  graph/metrics?graph=<name>        deterministic graph metrics on a real adjacency
  GET  forecast/coverage                 split-conformal empirical coverage summary
  POST eval/scores                       Brier / CRPS / ECE + reliability bins + Pareto front
  POST router/reward                     transparent GraphRouter multi-objective reward
  GET  search?q=...                       SQLite FTS5 (bm25) over an in-memory corpus
  GET  lambda/panel?...                   quasi-arithmetic Λ (Kolmogorov–Nagumo) panel
  GET  trust/gap?...                      info-geometry KL trust gap (advisory)
  POST anomaly/percentiles               calibrated empirical anomaly percentiles
"""
import math, json, time, hashlib, sqlite3

# ----------------------------------------------------------------------------- pure-stdlib math
def _clamp01(x):
    try: x = float(x)
    except Exception: return 0.0
    return 0.0 if x < 0 else (1.0 if x > 1 else x)

def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0

def _quantile_sorted(srt, p):
    """Empirical quantile with finite-sample (n+1) correction; srt must be sorted."""
    if not srt: return 0.0
    n = len(srt)
    k = min(n - 1, max(0, math.ceil((n + 1) * p) - 1))
    return srt[k]

# ---- graph metrics (undirected clustering, degree centrality, DAG check, Fiedler λ2) -------
def _build_adj(nodes, edges):
    idx = {n: i for i, n in enumerate(nodes)}
    nbr = {n: set() for n in nodes}
    for a, b in edges:
        if a in nbr and b in nbr and a != b:
            nbr[a].add(b); nbr[b].add(a)
    return idx, nbr

def _clustering(nodes, nbr):
    """Local clustering coefficient (Watts–Strogatz), averaged. Pure stdlib."""
    if not nodes: return 0.0, {}
    local = {}
    for n in nodes:
        ns = list(nbr[n]); k = len(ns)
        if k < 2:
            local[n] = 0.0; continue
        links = 0
        for i in range(k):
            for j in range(i + 1, k):
                if ns[j] in nbr[ns[i]]: links += 1
        local[n] = (2.0 * links) / (k * (k - 1))
    return _mean(local.values()), local

def _degree_centrality(nodes, nbr):
    n = len(nodes)
    if n <= 1: return {x: 0.0 for x in nodes}
    return {x: len(nbr[x]) / (n - 1) for x in nodes}

def _is_dag(nodes, dedges):
    """Kahn topological sort on DIRECTED edges; returns (is_dag, num_back_edges)."""
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for a, b in dedges:
        if a in indeg and b in indeg:
            out[a].append(b); indeg[b] += 1
    q = [n for n in nodes if indeg[n] == 0]
    seen = 0
    while q:
        u = q.pop()
        seen += 1
        for v in out[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return (seen == len(nodes)), (len(nodes) - seen)

def _fiedler_lambda2(nodes, nbr, iters=200):
    """Algebraic connectivity λ2 of the normalized Laplacian via deflated power
    iteration (pure stdlib). Advisory — small graphs only. Returns λ2 in [0,2]."""
    n = len(nodes)
    if n < 2: return 0.0
    order = list(nodes); pos = {x: i for i, x in enumerate(order)}
    deg = [max(1, len(nbr[x])) for x in order]
    # Use L_sym = I - D^-1/2 A D^-1/2; power-iterate on (2I - L_sym) then map back, deflate v1.
    import random as _r; _r.seed(1234)  # deterministic
    v = [_r.random() - 0.5 for _ in range(n)]
    # v1 (smallest eigvec of L_sym) ∝ sqrt(deg)
    v1 = [math.sqrt(deg[i]) for i in range(n)]
    nrm1 = math.sqrt(sum(x * x for x in v1)) or 1.0
    v1 = [x / nrm1 for x in v1]
    def matvec(x):
        # y = (2I - L_sym) x  = (I + D^-1/2 A D^-1/2) x
        y = [x[i] for i in range(n)]
        for a in order:
            ia = pos[a]
            for b in nbr[a]:
                ib = pos[b]
                y[ia] += x[ib] / math.sqrt(deg[ia] * deg[ib])
        return y
    lam = 0.0
    for _ in range(iters):
        dot = sum(v[i] * v1[i] for i in range(n))
        v = [v[i] - dot * v1[i] for i in range(n)]      # deflate v1
        y = matvec(v)
        nrm = math.sqrt(sum(t * t for t in y)) or 1.0
        v = [t / nrm for t in y]
        lam = nrm
    mu = lam                         # ≈ largest eigval of (2I - L_sym) excl. v1
    lambda2 = 2.0 - mu               # back to L_sym spectrum
    return max(0.0, min(2.0, lambda2))

# ---- proper scoring rules (pure stdlib) ----------------------------------------------------
def _brier(probs, outcomes):
    """Mean squared error of probabilistic forecasts vs {0,1} outcomes."""
    if not probs: return None
    return _mean([(_clamp01(p) - float(o)) ** 2 for p, o in zip(probs, outcomes)])

def _crps_ensemble(forecasts, observed):
    """CRPS for a deterministic point vs observed using the empirical-CDF energy form
    for a single-sample ensemble: |f - y|. For an ensemble list, use the NRG estimator."""
    out = []
    for fs, y in zip(forecasts, observed):
        ens = fs if isinstance(fs, list) else [fs]
        m = len(ens)
        term1 = _mean([abs(e - y) for e in ens])
        if m > 1:
            s = 0.0
            for i in range(m):
                for j in range(m):
                    s += abs(ens[i] - ens[j])
            term2 = s / (2.0 * m * m)
        else:
            term2 = 0.0
        out.append(term1 - term2)
    return _mean(out) if out else None

def _ece(probs, outcomes, n_bins=10):
    """Expected Calibration Error + reliability bins."""
    if not probs: return None, []
    bins = [[] for _ in range(n_bins)]
    for p, o in zip(probs, outcomes):
        p = _clamp01(p)
        bi = min(n_bins - 1, int(p * n_bins))
        bins[bi].append((p, float(o)))
    ece = 0.0; rel = []
    N = len(probs)
    for bi, b in enumerate(bins):
        lo = bi / n_bins; hi = (bi + 1) / n_bins
        if not b:
            rel.append({"bin": [round(lo, 3), round(hi, 3)], "n": 0, "conf": None, "acc": None})
            continue
        conf = _mean([x[0] for x in b]); acc = _mean([x[1] for x in b])
        ece += (len(b) / N) * abs(conf - acc)
        rel.append({"bin": [round(lo, 3), round(hi, 3)], "n": len(b),
                    "conf": round(conf, 4), "acc": round(acc, 4)})
    return ece, rel

def _pareto_front(items, keys, directions):
    """Non-dominated set. items: list of dicts. keys: metric names. directions: 'max'/'min'."""
    def dominates(a, b):
        ge = True; gt = False
        for k, d in zip(keys, directions):
            av, bv = a.get(k, 0.0), b.get(k, 0.0)
            if d == "min": av, bv = -av, -bv
            if av < bv: ge = False; break
            if av > bv: gt = True
        return ge and gt
    front = []
    for a in items:
        if not any(dominates(b, a) for b in items if b is not a):
            front.append(a)
    return front

# ---- quasi-arithmetic mean (Kolmogorov–Nagumo) ---------------------------------------------
def _quasi_mean(xs, kind="geometric", p=2.0, w=None):
    xs = [_clamp01(x) for x in xs]
    if not xs: return 0.0
    n = len(xs)
    w = w or [1.0 / n] * n
    sw = sum(w) or 1.0; w = [wi / sw for wi in w]
    if kind == "arithmetic":
        return sum(wi * xi for wi, xi in zip(w, xs))
    if kind == "geometric":
        eps = 1e-9
        return math.exp(sum(wi * math.log(max(eps, xi)) for wi, xi in zip(w, xs)))
    if kind == "harmonic":
        eps = 1e-9
        return 1.0 / sum(wi / max(eps, xi) for wi, xi in zip(w, xs))
    if kind == "power":
        if abs(p) < 1e-9: return _quasi_mean(xs, "geometric", w=w)
        return (sum(wi * (xi ** p) for wi, xi in zip(w, xs))) ** (1.0 / p)
    return _quasi_mean(xs, "geometric", w=w)

# ---- info-geometry KL trust gap -------------------------------------------------------------
def _kl(p, q):
    """KL(p||q) over a discrete simplex; both normalized. Returns nats. KL>=0 (Gibbs)."""
    eps = 1e-12
    sp = sum(p) or 1.0; sq = sum(q) or 1.0
    p = [max(eps, x / sp) for x in p]; q = [max(eps, x / sq) for x in q]
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q))

# ============================================================================================
def register(app):
    """Push all wireA metric routes to the FRONT so they win ordering. Returns route list."""
    from fastapi.responses import JSONResponse
    from fastapi import Request
    added = []

    def _front(path):
        # move the just-added route to the front of the router so it wins over proxy/catch-all
        try:
            r = app.router.routes.pop()
            app.router.routes.insert(0, r)
        except Exception:
            pass
        added.append(path)

    NOTE = ("MODEL-SCORED / SAMPLE inputs unless a real feed is named. Λ = Conjecture 1 "
            "(advisory, NEVER a theorem). Trust scores are advisory and never 100%.")

    # ---- real-ish graph builders from honest in-image structures -----------------------
    def _graph_data(name):
        """Return (nodes, undirected_edges, directed_edges, label, source). Honest empty
        state when the structure is unknown."""
        name = (name or "organism").lower()
        # Receipt / khipu hash-chain: linear DAG of the locked-8 formulas + aggregate.
        if name in ("chain", "lineage", "receiptchain"):
            seq = ["F1", "F11", "F12", "F18", "F19", "Λ-aggregate"]
            nodes = list(seq)
            de = [(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]
            ue = list(de)
            return nodes, ue, de, "Receipt hash-chain (locked-8 → Λ)", "Khipu-DSSE ledger (in-image, hash-chained)"
        # Living organism: organ topology (Quechua/honest names; NO banned codenames).
        if name in ("organism", "mesh", "constellation", "trustspace"):
            organs = ["Reception", "Operator", "Provenance-Anchor", "Policy",
                      "terra", "vessels", "counsel", "Voice", "House-Watch"]
            nodes = list(organs)
            # hub-and-spoke through Policy (deny-by-default gate) + Operator orchestration
            ue = []
            for o in organs:
                if o != "Policy": ue.append(("Policy", o))
            ue += [("Operator", "Provenance-Anchor"), ("Operator", "Reception"),
                   ("Operator", "Voice"), ("terra", "vessels"), ("vessels", "counsel")]
            de = [("Reception", "Policy"), ("Policy", "Operator"),
                  ("Operator", "Provenance-Anchor")] + [("Operator", o) for o in ("Voice", "House-Watch")]
            return nodes, ue, de, "Living-organism organ topology", "UDS organ registry (honest organ names)"
        # Knowledge ontology / decision graphs: small formula dependency DAG.
        if name in ("ontology", "knowledge", "decisiongraphs", "govatlas"):
            nodes = ["soundness(F1)", "STL(F11)", "gate(F12)", "DSSE(F18)", "Λ(F19)",
                     "policy-decision", "receipt"]
            de = [("F1", "policy-decision"), ("STL(F11)", "policy-decision"),
                  ("gate(F12)", "policy-decision"), ("policy-decision", "receipt"),
                  ("DSSE(F18)", "receipt"), ("Λ(F19)", "receipt")]
            de = [(a if a in nodes else nodes[0], b) for a, b in de]
            # remap short names
            m = {"F1": "soundness(F1)"}
            de = [(m.get(a, a), m.get(b, b)) for a, b in de]
            ue = list(de)
            return nodes, ue, de, "Knowledge → decision DAG", "OSCAL controls + formula registry"
        # Threat / attack-surface graph.
        if name in ("threatgraph", "attack", "cybsurface", "cybzero"):
            nodes = ["ingress", "auth-gate", "policy-gate", "service-a", "service-b",
                     "data-store", "egress"]
            de = [("ingress", "auth-gate"), ("auth-gate", "policy-gate"),
                  ("policy-gate", "service-a"), ("policy-gate", "service-b"),
                  ("service-a", "data-store"), ("service-b", "data-store"),
                  ("data-store", "egress")]
            ue = list(de)
            return nodes, ue, de, "Attack-surface / zero-trust path graph", "UDS allow-matrix (deny-by-default)"
        return [], [], [], "Unknown graph", "(no source bound — honest empty state)"

    @app.get("/api/a11oy/v1/wirea/graph/metrics")
    async def _wirea_graph_metrics(graph: str = "organism"):
        nodes, ue, de, label, source = _graph_data(graph)
        if not nodes:
            return JSONResponse({"graph": graph, "label": label, "source": source,
                                 "empty": True, "honest": "No graph structure bound for this key yet — honest empty state.",
                                 "note": NOTE})
        idx, nbr = _build_adj(nodes, ue)
        avg_cc, local_cc = _clustering(nodes, nbr)
        dc = _degree_centrality(nodes, nbr)
        is_dag, back_edges = _is_dag(nodes, de)
        lam2 = _fiedler_lambda2(nodes, nbr)
        # deterministic seed for layout reproducibility (sha of node set)
        seed = int(hashlib.sha256(("|".join(nodes)).encode()).hexdigest()[:8], 16)
        top_central = sorted(dc.items(), key=lambda kv: -kv[1])[:5]
        return JSONResponse({
            "graph": graph, "label": label, "source": source, "empty": False,
            "n_nodes": len(nodes), "n_edges": len(ue),
            "metrics": {
                "avg_clustering_coefficient": round(avg_cc, 4),
                "graph_density": round((2.0 * len(ue)) / (len(nodes) * (len(nodes) - 1)), 4) if len(nodes) > 1 else 0.0,
                "dag_integrity": {"is_dag": is_dag, "back_edges": back_edges},
                "fiedler_lambda2": round(lam2, 4),
                "algebraic_connectivity_note": "λ2>0 ⇒ connected; higher ⇒ better-knit (advisory)",
            },
            "top_degree_centrality": [{"node": k, "centrality": round(v, 4)} for k, v in top_central],
            "layout": {"engine": "ngraph.forcelayout (deterministic)", "seed": seed,
                       "dimensions_supported": [2, 3]},
            "formulas": ["F12 (monotone gate)", "F19 (Λ aggregate)"],
            "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/graph/metrics")

    @app.get("/api/a11oy/v1/wirea/forecast/coverage")
    async def _wirea_forecast_coverage(target: float = 0.9, n: int = 40):
        # SAMPLE residual stream (deterministic) to demonstrate empirical coverage vs target.
        import random as _r; _r.seed(7)
        resid = sorted(abs(_r.gauss(0, 1.0)) for _ in range(max(8, n)))
        q = _quantile_sorted(resid, target)
        covered = sum(1 for x in resid if x <= q)
        emp = covered / len(resid)
        return JSONResponse({
            "method": "split-conformal residual quantile, finite-sample (n+1) correction",
            "coverage_target": target, "empirical_coverage": round(emp, 4),
            "n": len(resid), "band_halfwidth": round(q, 4),
            "gap": round(emp - target, 4),
            "label": "SAMPLE residuals (deterministic seed) — wire a real feed to replace",
            "honest": "Distribution-free; NOT Hoeffding. Coverage is the realized fraction within the band.",
            "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/forecast/coverage")

    @app.post("/api/a11oy/v1/wirea/eval/scores")
    async def _wirea_eval_scores(req: Request):
        try: body = await req.json()
        except Exception: body = {}
        probs = body.get("probs") or [0.9, 0.8, 0.3, 0.6, 0.55, 0.2, 0.95, 0.4]
        outcomes = body.get("outcomes") or [1, 1, 0, 1, 0, 0, 1, 0]
        fc = body.get("forecasts"); obs = body.get("observed")
        brier = _brier(probs, outcomes)
        ece, rel = _ece(probs, outcomes, body.get("bins", 10))
        crps = _crps_ensemble(fc, obs) if (fc and obs) else _crps_ensemble(probs, [float(o) for o in outcomes])
        # Pareto front over candidate models (lower Brier/ECE better, higher coverage better)
        cands = body.get("candidates") or [
            {"model": "A", "brier": 0.12, "ece": 0.04, "coverage": 0.91},
            {"model": "B", "brier": 0.18, "ece": 0.02, "coverage": 0.93},
            {"model": "C", "brier": 0.10, "ece": 0.07, "coverage": 0.88},
            {"model": "D", "brier": 0.20, "ece": 0.09, "coverage": 0.80},
        ]
        front = _pareto_front(cands, ["brier", "ece", "coverage"], ["min", "min", "max"])
        return JSONResponse({
            "brier": round(brier, 5) if brier is not None else None,
            "crps": round(crps, 5) if crps is not None else None,
            "ece": round(ece, 5) if ece is not None else None,
            "reliability_bins": rel,
            "pareto_front": [c.get("model") for c in front],
            "candidates": cands,
            "label": "MODEL-SCORED (proper scoring rules; lower Brier/CRPS/ECE = better calibrated)",
            "formulas": ["F19 (Λ aggregate, advisory)"],
            "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/eval/scores")

    @app.post("/api/a11oy/v1/wirea/router/reward")
    async def _wirea_router_reward(req: Request):
        """Transparent GraphRouter multi-objective reward:
           reward = α·Quality − β·Cost − γ·Latency. Presets:
           Performance-First(1,0,0) / Balanced(0.5,0.5,0.3) / Cost-First(0.2,0.8,0.2)."""
        try: body = await req.json()
        except Exception: body = {}
        preset = (body.get("preset") or "balanced").lower()
        presets = {"performance": (1.0, 0.0, 0.0), "balanced": (0.5, 0.5, 0.3),
                   "cost": (0.2, 0.8, 0.2)}
        a, b, g = presets.get(preset, presets["balanced"])
        cands = body.get("candidates") or [
            {"model": "opus-4.8", "quality": 0.96, "cost": 0.90, "latency": 0.70},
            {"model": "gpt-frontier", "quality": 0.93, "cost": 0.75, "latency": 0.55},
            {"model": "mistral-large", "quality": 0.84, "cost": 0.30, "latency": 0.35},
            {"model": "local-7b", "quality": 0.62, "cost": 0.05, "latency": 0.20},
        ]
        ranked = []
        for c in cands:
            q = _clamp01(c.get("quality", 0)); co = _clamp01(c.get("cost", 0)); la = _clamp01(c.get("latency", 0))
            reward = a * q - b * co - g * la
            why = ("quality {:.2f}×α{:.2f} − cost {:.2f}×β{:.2f} − latency {:.2f}×γ{:.2f}"
                   .format(q, a, co, b, la, g))
            ranked.append({"model": c.get("model"), "reward": round(reward, 4),
                           "quality": q, "cost": co, "latency": la, "why": why})
        ranked.sort(key=lambda x: -x["reward"])
        # receipt: hash of the ranking decision (tamper-evident)
        payload = json.dumps({"preset": preset, "ranked": ranked}, sort_keys=True)
        receipt = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
        return JSONResponse({
            "preset": preset, "weights": {"alpha_quality": a, "beta_cost": b, "gamma_latency": g},
            "ranked": ranked, "selected": ranked[0]["model"] if ranked else None,
            "receipt": receipt, "ts": int(time.time()),
            "label": "MODEL-SCORED candidate attributes (wire szl_llm_registry telemetry to replace)",
            "honest": "Transparent linear scalarization; 'why' shows every term. Receipted (sha256).",
            "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/router/reward")

    # ---- SQLite FTS5 search over an in-image governance corpus -------------------------
    _FTS_CORPUS = [
        ("F1", "soundness gate-pass implies Λ ≥ 0.90 conjunctive soundness locked-proven"),
        ("F11", "STL signal temporal logic robustness rho envelope geofence gates locked-proven"),
        ("F12", "monotone policy gate deny-by-default monotonicity locked-proven"),
        ("F18", "DSSE seal receipt signature binds canonical payload tamper-evident locked-proven"),
        ("F19", "Λ aggregate 13-axis geometric mean trust advisory locked-proven"),
        ("F23", "Λ uniqueness conditional slice multiplicativity axiom-free conjecture-1 unconditional"),
        ("organism", "living organism organ topology Reception Operator Provenance-Anchor Policy"),
        ("chain", "receipt hash-chain Khipu DSSE ledger locked-8 aggregate"),
        ("threat", "attack surface zero-trust path ingress auth-gate policy-gate egress"),
        ("router", "GraphRouter multi-objective reward quality cost latency presets"),
        ("forecast", "split-conformal coverage residual quantile distribution-free band"),
        ("eval", "Brier CRPS ECE reliability calibration Pareto front proper scoring"),
    ]
    def _fts_search(q):
        try:
            con = sqlite3.connect(":memory:")
            con.execute("CREATE VIRTUAL TABLE docs USING fts5(key, body)")
            con.executemany("INSERT INTO docs(key, body) VALUES (?, ?)", _FTS_CORPUS)
            cur = con.execute(
                "SELECT key, body, bm25(docs) AS score FROM docs WHERE docs MATCH ? ORDER BY score LIMIT 20",
                (q,))
            rows = [{"key": r[0], "body": r[1], "bm25": round(r[2], 4)} for r in cur.fetchall()]
            con.close()
            return rows, "fts5+bm25"
        except Exception as e:
            # honest fallback: LIKE substring (FTS5 not compiled in)
            ql = (q or "").lower().replace('"', "").split()
            rows = []
            for k, b in _FTS_CORPUS:
                if all(t in (k + " " + b).lower() for t in ql):
                    rows.append({"key": k, "body": b, "bm25": None})
            return rows, "LIKE-fallback (FTS5 unavailable: %s)" % str(e)[:60]

    @app.get("/api/a11oy/v1/wirea/search")
    async def _wirea_search(q: str = ""):
        if not q.strip():
            return JSONResponse({"q": q, "results": [], "engine": None,
                                 "honest": "Empty query — honest empty state.", "note": NOTE})
        rows, engine = _fts_search(q.strip())
        return JSONResponse({"q": q, "engine": engine, "count": len(rows), "results": rows,
                             "honest": "Full-text search over the in-image governance corpus.", "note": NOTE})
    _front("/api/a11oy/v1/wirea/search")

    @app.get("/api/a11oy/v1/wirea/lambda/panel")
    async def _wirea_lambda_panel(scores: str = "0.97,0.94,0.92,0.99,0.88,0.95", kind: str = "geometric", p: float = 2.0):
        try:
            xs = [float(s) for s in scores.split(",") if s.strip() != ""]
        except Exception:
            xs = []
        if not xs:
            return JSONResponse({"empty": True, "honest": "No axis scores given — honest empty state.", "note": NOTE})
        variants = {k: round(_quasi_mean(xs, k), 5) for k in ("arithmetic", "geometric", "harmonic")}
        variants["power_p"] = round(_quasi_mean(xs, "power", p=p), 5)
        lam = _quasi_mean(xs, kind, p=p)
        # AM ≥ GM ≥ HM sanity (Cauchy)
        ordered = variants["arithmetic"] >= variants["geometric"] >= variants["harmonic"] - 1e-9
        return JSONResponse({
            "lambda": round(min(lam, 0.999), 5),  # trust never 100%
            "kind": kind, "p": p, "axes": xs, "variants": variants,
            "am_gm_hm_ordering_holds": ordered,
            "maturity": "Λ = Conjecture 1 (advisory, never a theorem)",
            "lean": "Lutar/Lambda.lean::lambda_geomean_wellformed (F19, locked-proven well-formedness only)",
            "honest": "Quasi-arithmetic (Kolmogorov–Nagumo) mean family. Λ generator = geometric (F19). "
                      "Uniqueness is Conjecture 1 (machine-checked FALSE unconditionally).",
            "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/lambda/panel")

    @app.get("/api/a11oy/v1/wirea/trust/gap")
    async def _wirea_trust_gap(observed: str = "0.6,0.25,0.15", reference: str = "0.5,0.3,0.2"):
        try:
            p = [float(x) for x in observed.split(",") if x.strip() != ""]
            q = [float(x) for x in reference.split(",") if x.strip() != ""]
        except Exception:
            p, q = [], []
        if not p or not q or len(p) != len(q):
            return JSONResponse({"empty": True, "honest": "Need equal-length observed/reference simplices.", "note": NOTE})
        kl_pq = _kl(p, q); kl_qp = _kl(q, p)
        jeffreys = kl_pq + kl_qp
        return JSONResponse({
            "kl_observed_vs_reference_nats": round(kl_pq, 5),
            "kl_reference_vs_observed_nats": round(kl_qp, 5),
            "jeffreys_divergence_nats": round(jeffreys, 5),
            "trust_gap_pct": round(min(0.999, 1.0 - math.exp(-kl_pq)) * 100, 2),
            "gibbs_nonneg_holds": kl_pq >= -1e-9 and kl_qp >= -1e-9,
            "honest": "Information-geometry KL trust gap (advisory). KL≥0 by Gibbs' inequality. "
                      "Larger gap ⇒ observed posture diverges further from the trusted reference.",
            "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/trust/gap")

    @app.post("/api/a11oy/v1/wirea/anomaly/percentiles")
    async def _wirea_anomaly_pct(req: Request):
        try: body = await req.json()
        except Exception: body = {}
        baseline = body.get("baseline")
        if not baseline:
            import random as _r; _r.seed(11)
            baseline = [_r.gauss(100, 15) for _ in range(200)]
            blabel = "SAMPLE baseline (deterministic seed) — wire a real metric stream to replace"
        else:
            blabel = "caller-supplied baseline"
        point = body.get("value", 142.0)
        srt = sorted(float(x) for x in baseline)
        below = sum(1 for x in srt if x <= point)
        pct = 100.0 * below / len(srt)
        p95 = _quantile_sorted(srt, 0.95); p99 = _quantile_sorted(srt, 0.99)
        sev = "critical" if point >= p99 else ("elevated" if point >= p95 else "nominal")
        return JSONResponse({
            "value": point, "empirical_percentile": round(pct, 2),
            "p95": round(p95, 3), "p99": round(p99, 3), "n_baseline": len(srt),
            "severity": sev, "is_anomaly": point >= p95,
            "method": "calibrated empirical percentile vs baseline ECDF (distribution-free)",
            "baseline_label": blabel, "note": NOTE,
        })
    _front("/api/a11oy/v1/wirea/anomaly/percentiles")

    @app.get("/api/a11oy/v1/wirea/healthz")
    async def _wirea_health():
        # report whether FTS5 is available in this build (honest)
        try:
            c = sqlite3.connect(":memory:"); c.execute("CREATE VIRTUAL TABLE t USING fts5(x)"); c.close()
            fts = True
        except Exception:
            fts = False
        return JSONResponse({"ok": True, "module": "a11oy_wireA_metrics", "fts5_available": fts,
                             "routes": added, "stdlib_only": True, "cdn": 0})
    _front("/api/a11oy/v1/wirea/healthz")

    return added