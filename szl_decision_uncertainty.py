# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN/CODE ADOPTION (fashion-thinking, NOTICE attribution):
#   prfr — al-jshen/prfr (Probabilistic Random Forest Regression) — MIT License —
#          https://github.com/al-jshen/prfr
#   gaul — al-jshen/gaul (probabilistic sampling: HMC/ADVI/QUAP) — Apache-2.0/MIT —
#          https://github.com/al-jshen/gaul
#   We adopt the PATTERN of (a) bootstrap-aggregated tree ensembles that yield a
#   PREDICTIVE DISTRIBUTION (not a point estimate) and (b) calibrated prediction
#   intervals. We EVOLVE it into a "Reasoning Uncertainty" layer: every governed
#   decision variable comes back with a calibrated confidence band + a risk verdict,
#   so an operator sees not just the number but how much to trust it. Original,
#   dependency-free (stdlib only) clean-room implementation — no prfr/gaul source,
#   no numpy/torch. Trees are real CART regression stumps over bootstrap samples.
"""szl_decision_uncertainty — ADDITIVE risk/uncertainty tab + API for a11oy.

Endpoints (mounted before the SPA catch-all):
  GET  /decision-uncertainty                       — operator tab (HTML, 0 CDN)
  GET  /api/a11oy/v1/uncertainty/demo               — fit on a synthetic, heteroscedastic
                                                      signal and return calibrated bands
  POST /api/a11oy/v1/uncertainty/predict            — {X:[[..]], y:[..], query:[..]} ->
                                                      mean + interval + calibration + risk

HONESTY: this is a real probabilistic random-forest regressor (bootstrap ensemble of
CART trees) with empirical (out-of-bag residual) prediction intervals and a coverage
calibration check on held-out data. No mock numbers. Λ = Conjecture 1.
Doctrine v11 LOCKED 749/14/163.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}


# --------------------------- CART regression tree ---------------------------
class _Node:
    __slots__ = ("feat", "thr", "left", "right", "value")

    def __init__(self):
        self.feat = None; self.thr = None
        self.left = None; self.right = None; self.value = None


def _fit_tree(X: list[list[float]], y: list[float], depth: int, max_depth: int,
              min_leaf: int, rng: random.Random) -> _Node:
    node = _Node()
    n = len(y)
    mean = sum(y) / n
    if depth >= max_depth or n < 2 * min_leaf:
        node.value = mean
        return node
    n_feats = len(X[0])
    # random feature subsampling (forest decorrelation, prfr-style)
    k = max(1, int(math.sqrt(n_feats)))
    feats = rng.sample(range(n_feats), min(k, n_feats))
    best = None  # (sse, feat, thr, left_idx, right_idx)
    for f in feats:
        vals = sorted(set(row[f] for row in X))
        for i in range(1, len(vals)):
            thr = (vals[i - 1] + vals[i]) / 2.0
            li = [j for j in range(n) if X[j][f] <= thr]
            ri = [j for j in range(n) if X[j][f] > thr]
            if len(li) < min_leaf or len(ri) < min_leaf:
                continue
            ml = sum(y[j] for j in li) / len(li)
            mr = sum(y[j] for j in ri) / len(ri)
            sse = sum((y[j] - ml) ** 2 for j in li) + sum((y[j] - mr) ** 2 for j in ri)
            if best is None or sse < best[0]:
                best = (sse, f, thr, li, ri)
    if best is None:
        node.value = mean
        return node
    _, f, thr, li, ri = best
    node.feat = f; node.thr = thr
    node.left = _fit_tree([X[j] for j in li], [y[j] for j in li], depth + 1, max_depth, min_leaf, rng)
    node.right = _fit_tree([X[j] for j in ri], [y[j] for j in ri], depth + 1, max_depth, min_leaf, rng)
    return node


def _pred_tree(node: _Node, x: list[float]) -> float:
    while node.value is None:
        node = node.left if x[node.feat] <= node.thr else node.right
    return node.value


class ProbabilisticForest:
    """Bootstrap ensemble of CART trees -> predictive distribution + calibrated band."""

    def __init__(self, n_trees: int = 60, max_depth: int = 6, min_leaf: int = 3, seed: int = 13):
        self.n_trees = n_trees; self.max_depth = max_depth
        self.min_leaf = min_leaf; self.seed = seed
        self.trees: list[_Node] = []
        # locally-adaptive calibration: keep each OOB residual WITH its X location
        # so prediction intervals widen where the world is genuinely noisier
        # (honest heteroscedastic behaviour, not a global constant band).
        self.oob_resid: list[float] = []
        self._cal_X: list[list[float]] = []
        self._cal_r: list[float] = []

    def fit(self, X: list[list[float]], y: list[float]) -> None:
        rng = random.Random(self.seed)
        n = len(y)
        self.trees = []
        oob_preds: dict[int, list[float]] = {i: [] for i in range(n)}
        for t in range(self.n_trees):
            idx = [rng.randrange(n) for _ in range(n)]            # bootstrap
            inbag = set(idx)
            tree = _fit_tree([X[i] for i in idx], [y[i] for i in idx],
                             0, self.max_depth, self.min_leaf, rng)
            self.trees.append(tree)
            for i in range(n):                                    # out-of-bag preds
                if i not in inbag:
                    oob_preds[i].append(_pred_tree(tree, X[i]))
        # OOB residuals = honest held-out errors (calibration source)
        self.oob_resid = []
        self._cal_X = []; self._cal_r = []
        for i in range(n):
            if oob_preds[i]:
                r = y[i] - (sum(oob_preds[i]) / len(oob_preds[i]))
                self.oob_resid.append(r)
                self._cal_X.append(X[i]); self._cal_r.append(r)
        if not self.oob_resid:
            self.oob_resid = [0.0]; self._cal_X = [[0.0]]; self._cal_r = [0.0]

    def _local_residuals(self, x: list[float], k: int = 40) -> list[float]:
        """k nearest calibration points by feature distance -> local residual set.
        This is what makes the band track LOCAL noise (heteroscedastic)."""
        if not self._cal_X:
            return self.oob_resid
        scored = []
        for xi, ri in zip(self._cal_X, self._cal_r):
            d = sum((a - b) ** 2 for a, b in zip(x, xi))
            scored.append((d, ri))
        scored.sort(key=lambda t: t[0])
        kk = min(k, len(scored))
        return [r for _, r in scored[:kk]]

    def _quantile(self, data: list[float], q: float) -> float:
        s = sorted(data)
        if not s:
            return 0.0
        pos = q * (len(s) - 1)
        lo = int(math.floor(pos)); hi = int(math.ceil(pos))
        if lo == hi:
            return s[lo]
        return s[lo] + (s[hi] - s[lo]) * (pos - lo)

    def predict(self, x: list[float], coverage: float = 0.9) -> dict[str, Any]:
        preds = [_pred_tree(t, x) for t in self.trees]
        mean = sum(preds) / len(preds)
        var_tree = sum((p - mean) ** 2 for p in preds) / max(1, len(preds) - 1)
        alpha = (1.0 - coverage) / 2.0
        # interval = ensemble mean + LOCAL OOB residual quantiles (empirical,
        # calibrated, heteroscedastic — widens where local data is noisier)
        local = self._local_residuals(x)
        lo = mean + self._quantile(local, alpha)
        hi = mean + self._quantile(local, 1.0 - alpha)
        width = hi - lo
        return {"mean": mean, "lower": lo, "upper": hi, "interval_width": width,
                "tree_std": math.sqrt(var_tree), "coverage_target": coverage}

    def calibrate(self, X: list[list[float]], y: list[float], coverage: float = 0.9) -> dict[str, Any]:
        inside = 0
        for xi, yi in zip(X, y):
            p = self.predict(xi, coverage)
            if p["lower"] <= yi <= p["upper"]:
                inside += 1
        empirical = inside / len(y) if y else 0.0
        return {"coverage_target": coverage, "empirical_coverage": round(empirical, 4),
                "n": len(y), "well_calibrated": abs(empirical - coverage) <= 0.1}


def _risk_verdict(width: float, scale: float) -> dict[str, str]:
    """Map relative interval width to an operator-facing risk band."""
    rel = width / scale if scale else float("inf")
    if rel <= 0.15:
        return {"risk": "LOW", "advice": "high confidence — band tight relative to signal"}
    if rel <= 0.40:
        return {"risk": "MODERATE", "advice": "usable — widen review if decision is irreversible"}
    return {"risk": "HIGH", "advice": "do not auto-act — escalate to human / gather more data"}


def _make_demo(seed: int = 21, n: int = 220) -> tuple[list[list[float]], list[float]]:
    rng = random.Random(seed)
    X: list[list[float]] = []; y: list[float] = []
    for _ in range(n):
        x0 = rng.uniform(0, 10); x1 = rng.uniform(-5, 5)
        # heteroscedastic: noise grows with x0 (uncertainty must track it)
        signal = 3.0 * math.sin(x0) + 0.5 * x1 + 0.4 * x0
        noise = rng.gauss(0, 0.3 + 0.25 * x0)
        X.append([x0, x1]); y.append(signal + noise)
    return X, y


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/uncertainty/demo", include_in_schema=False)
    async def _demo(coverage: float = 0.9) -> JSONResponse:
        t0 = time.time()
        X, y = _make_demo()
        cut = int(len(y) * 0.8)
        f = ProbabilisticForest()
        f.fit(X[:cut], y[:cut])
        cov = max(0.5, min(float(coverage), 0.99))
        cal = f.calibrate(X[cut:], y[cut:], cov)
        # sample predictions across the x0 range to show band tracking noise
        samples = []
        yscale = (max(y) - min(y)) or 1.0
        for x0 in [1.0, 3.0, 5.0, 7.0, 9.0]:
            p = f.predict([x0, 0.0], cov)
            samples.append({"x0": x0, **{k: round(v, 4) for k, v in p.items() if isinstance(v, float)},
                            **_risk_verdict(p["interval_width"], yscale)})
        return JSONResponse({"doctrine": DOCTRINE, "n_train": cut, "n_test": len(y) - cut,
                             "trees": f.n_trees, "calibration": cal, "samples": samples,
                             "elapsed_ms": round((time.time() - t0) * 1000, 2),
                             "pattern_source": "al-jshen/prfr (MIT) + gaul (Apache/MIT), evolved to a governed uncertainty layer"})

    @app.post(f"/api/{ns}/v1/uncertainty/predict", include_in_schema=False)
    async def _predict(req: Request) -> JSONResponse:
        try:
            body = await req.json()
        except Exception:
            body = {}
        X = body.get("X"); y = body.get("y"); query = body.get("query")
        cov = max(0.5, min(float(body.get("coverage", 0.9)), 0.99))
        if not (isinstance(X, list) and isinstance(y, list) and isinstance(query, list) and X and y):
            return JSONResponse({"error": "need X:[[..]], y:[..], query:[..]"}, status_code=400)
        try:
            f = ProbabilisticForest(n_trees=int(body.get("n_trees", 60)))
            f.fit(X, y)
            p = f.predict([float(v) for v in query], cov)
            yscale = (max(y) - min(y)) or 1.0
            return JSONResponse({"doctrine": DOCTRINE,
                                 **{k: round(v, 6) for k, v in p.items() if isinstance(v, float)},
                                 **_risk_verdict(p["interval_width"], yscale),
                                 "n_train": len(y)})
        except Exception as e:
            return JSONResponse({"error": f"fit/predict failed: {e}"}, status_code=400)

    @app.get("/decision-uncertainty", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return f"decision-uncertainty mounted: GET /decision-uncertainty + /api/{ns}/v1/uncertainty/(demo|predict)"


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Decision Uncertainty</title>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--amber:#d29922;--red:#f85149;--line:#1e2a36;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:10px 18px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(1.08)}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}th{color:var(--muted)}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.amber{background:rgba(210,153,34,.15);color:var(--amber)}
.red{background:rgba(248,81,73,.15);color:var(--red)}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;
font-size:12.5px;white-space:pre-wrap}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
</style></head>
<body><div class="wrap">
<h1>Decision Uncertainty <span class="pill green">calibrated bands</span></h1>
<p class="sub">A probabilistic random forest gives every governed decision variable a
<b>calibrated confidence band</b> and a <b>risk verdict</b> — so operators see not just the
number but how much to trust it. Pattern from <code>al-jshen/prfr</code> + <code>gaul</code> (MIT/Apache),
evolved into a reasoning-uncertainty layer. Real bootstrap ensemble, OOB-calibrated. 0&nbsp;CDN.</p>

<div class="card">
<div class="row" style="justify-content:space-between">
<h3 style="margin:0">Live demo — heteroscedastic signal</h3>
<button id="run">Fit &amp; calibrate</button>
</div>
<p class="sub" style="margin:8px 0">A synthetic signal whose noise grows with x — a well-calibrated
model must <i>widen its band</i> where the world is noisier. Coverage is checked on held-out data.</p>
<div id="cal" class="pill green">—</div>
<table id="tbl"><thead><tr><th>x</th><th>mean</th><th>lower</th><th>upper</th>
<th>width</th><th>risk</th><th>advice</th></tr></thead><tbody></tbody></table>
<pre id="out" style="margin-top:12px">Click "Fit &amp; calibrate" to run the real ensemble…</pre>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
pattern: al-jshen/prfr (MIT) + gaul (Apache/MIT), evolved · sovereign 0-CDN.</p>
</div>
<script>
const $=s=>document.querySelector(s);
function pill(r){return r==='LOW'?'green':(r==='MODERATE'?'amber':'red');}
$('#run').addEventListener('click',async()=>{
  $('#out').textContent='fitting real ensemble (60 trees)…';$('#tbl').querySelector('tbody').innerHTML='';
  try{const r=await fetch('/api/a11oy/v1/uncertainty/demo?coverage=0.9');const d=await r.json();
    const c=d.calibration;
    $('#cal').className='pill '+(c.well_calibrated?'green':'amber');
    $('#cal').textContent='target '+(c.coverage_target*100)+'% · empirical '+(c.empirical_coverage*100).toFixed(1)
      +'% · '+(c.well_calibrated?'WELL-CALIBRATED':'check')+' · '+d.trees+' trees · '+d.elapsed_ms+'ms';
    const tb=$('#tbl').querySelector('tbody');
    d.samples.forEach(s=>{tb.insertAdjacentHTML('beforeend',
      `<tr><td>${s.x0}</td><td>${s.mean}</td><td>${s.lower}</td><td>${s.upper}</td>
       <td>${s.interval_width}</td><td><span class="pill ${pill(s.risk)}">${s.risk}</span></td>
       <td>${s.advice}</td></tr>`);});
    $('#out').textContent=JSON.stringify(d,null,2);
  }catch(e){$('#out').textContent='error: '+e;}
});
$('#run').click();
</script>
</body></html>"""
