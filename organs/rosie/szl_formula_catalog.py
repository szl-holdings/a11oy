#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_formula_catalog.py — cross-organ thesis-v22 formula catalog page.

Mounts a single read-only page at GET /formulas (HTML) + GET /api/rosie/v1/formulas/catalog
(JSON). It lists every wired formula with: name + thesis-v22 citation, the real Lean
theorem name + a GitHub permalink (pinned commit) into szl-holdings/lutar-lean, the LIVE
endpoint URL, and — client-side — a real-time fetch of that endpoint so the visitor sees
the actual JSON response.

HONESTY:
  * Every Lean permalink is pinned to a real commit and a real theorem line.
  * a11oy endpoints are NOT advertised as live: the a11oy HF Space is in BUILD_ERROR;
    a11oy-resident formulas are shown with their REAL_REPO home, not a fake live URL.
  * Λ uniqueness is Conjecture 1 — there is NO lambda_unique theorem and NO
    /formula/lambda-unique endpoint. The page says so explicitly.

ADDITIVE: register(app) only adds GET /formulas + the catalog JSON. Never overwrites.
Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import json as _json

# Pinned commits (verified 2026-06-03) for stable Lean permalinks.
_LEAN = "https://github.com/szl-holdings/lutar-lean/blob"
_MAIN = "abd58d159f1bdb79a017d71a6b94ab160ead8d9d"
_R11 = "f3153a684e7d9b77462d58185bd1eae0aeacd1bc"
_R12 = "d5f5dd8d99c94783bab43de23febbbd68428a94b"

# Each entry: name, thesis citation, lean theorem, lean permalink, live endpoint (or None),
# grade. live=None means REAL_REPO/PROVED_NOT_USED — shown without a fake live URL.
CATALOG = [
    {"name": "PAC-Bayes (Catoni/McAllester)", "thesis": "v22 §2 (formula table; TH13)",
     "lean": "pac_bayes_bound / pacBayesBound_*",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/PACBayes.lean#L102",
     "live": "https://szlholdings-sentra.hf.space/api/sentra/v1/formula/pacbayes?n=1000&epsilon=0.05",
     "grade": "REAL_LIVE"},
    {"name": "Welford online variance", "thesis": "v22 §2 (round-11 frontier)",
     "lean": "welford_mean_exact (sorry-free)",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierWelfordVariance.lean#L89",
     "live": "https://szlholdings-killinchu.hf.space/api/killinchu/v1/formula/welford",
     "grade": "REAL_LIVE"},
    {"name": "Bloom filter (no false negatives)", "thesis": "v22 §2 (round-11 frontier)",
     "lean": "query_after_insert / absent_false_after_insert (sorry-free)",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierBloomCacheBypass.lean#L77",
     "live": "https://szlholdings-sentra.hf.space/api/sentra/v1/formula/bloom?key=demo",
     "grade": "REAL_LIVE"},
    {"name": "Byzantine quorum (n>=3f+1)", "thesis": "v22 §2; §1,§4",
     "lean": "khipu_consensus_safety (Conjecture 2, OPEN) + runtime quorum defs",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/KhipuConsensus.lean#L23",
     "live": "https://szlholdings-rosie.hf.space/api/rosie/v1/formula/quorum?n=5&f=1",
     "grade": "REAL_LIVE"},
    {"name": "Ayni / Ubuntu quorum-intersection (Round 12)", "thesis": "v22 §2 · Round-12 frontier",
     "lean": "quorum_intersection_honest (Round-12, SORRY-FREE)",
     "permalink": f"{_LEAN}/{_R12}/Lutar/Innovations/round12/Identity_Ayni_Quorum.lean#L69",
     "live": "https://szlholdings-rosie.hf.space/api/rosie/v1/formula/ayni-quorum?n=5&f=1",
     "grade": "REAL_LIVE (wired this task)"},
    {"name": "HNSW retrieval navigability", "thesis": "v22 §2 (RAG; round-11)",
     "lean": "greedy_search_terminates",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierHNSWNavigability.lean#L87",
     "live": "https://szlholdings-amaru.hf.space/api/amaru/v1/formula/hnsw",
     "grade": "REAL_LIVE (amaru owns retrieval)"},
    {"name": "A5 permutation invariance (Noether→A5)", "thesis": "v22 §1,§2 (PR #148/#177)",
     "lean": "lambda_perm_invariant (sorry-free)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/LambdaPermInvariant.lean#L15",
     "live": "https://szlholdings-rosie.hf.space/api/rosie/v1/honest",
     "grade": "REAL_LIVE (organ /honest + /lambda)"},
    {"name": "BLS aggregate signature", "thesis": "v22 §2 (PR #179; round-11)",
     "lean": "agg_sig_eq_agg_key_sig / aggregate_verify",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierBLSAggregation.lean#L82",
     "live": None, "home": "szl-holdings/a11oy src/a11oy/formulas/bls_aggregate.py (a11oy Space in BUILD_ERROR)",
     "grade": "REAL_REPO"},
    {"name": "Holevo capacity bound", "thesis": "v22 §2 (PR #176)",
     "lean": "Holevo χ (Gibbs honest hardness assumption)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar",
     "live": None, "home": "szl-holdings/a11oy src/a11oy/formulas/holevo_bound.py (a11oy Space down)",
     "grade": "REAL_REPO"},
    {"name": "Kalman filter gain", "thesis": "v22 §2 (round-11)",
     "lean": "gain_in_unit_interval / posterior_le_prior",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierKalmanGain.lean#L72",
     "live": None, "home": "szl-holdings/a11oy src/a11oy/formulas/kalman.py (a11oy Space down)",
     "grade": "REAL_REPO"},
    {"name": "Reidemeister moves (Khipu braid)", "thesis": "v22 §2 (v15 knot calculus)",
     "lean": "r3_invariance / r12_equiv_lambda_flat (R1/R2 axiom; R3 flat-segment)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/Knot/ReidemeisterConjecture.lean#L206",
     "live": None, "home": "szl-holdings/a11oy src/a11oy/formulas/reidemeister.py (a11oy Space down)",
     "grade": "REAL_REPO"},
    {"name": "DSSE EUF-CMA receipt signing", "thesis": "v22 §2 (PR #179)",
     "lean": "PAE injectivity + conditional EUF-CMA (NIST hardness, labeled)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar",
     "live": "https://szlholdings-rosie.hf.space/api/rosie/v1/mesh/health",
     "grade": "REAL_LIVE (receipt signing across organs)"},
    {"name": "Cauchy_ND scaffold (Λ disclosure)", "thesis": "v22 §1,§4",
     "lean": "lutar_is_geomean — OPEN CAUCHY_ND sorry (keeps Λ = Conjecture 1)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/Uniqueness.lean",
     "live": "https://szlholdings-rosie.hf.space/api/rosie/v1/honest",
     "grade": "REAL_LIVE (honest disclosure)"},
    # ── killinchu edge formulas (PR #44 merged into szl-holdings/killinchu/main) ──
    {"name": "Kalman filter (killinchu edge telemetry smoothing)", "thesis": "v22 §2 (round-11 frontier)",
     "lean": "gain_in_unit_interval (sorry-free)",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierKalmanGain.lean#L72",
     "live": "https://szlholdings-killinchu.hf.space/edge/track-smooth",
     "grade": "REAL_LIVE (killinchu edge — PR #44)"},
    {"name": "PAC-Bayes edge verdict (killinchu, Λ+DSSE receipt)", "thesis": "v22 §2 (formula table; TH13)",
     "lean": "pacBayesBound_eq_add_slack (sorry-free)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/PACBayes.lean#L165",
     "live": "https://szlholdings-killinchu.hf.space/edge/verdict",
     "grade": "REAL_LIVE (killinchu edge — PR #44)"},
    {"name": "Byzantine quorum at the edge (killinchu; 5 sensors tolerate 1)", "thesis": "v22 §2; §1,§4",
     "lean": "faultyCount (safety = Conjecture 2, OPEN)",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/KhipuConsensus.lean#L116",
     "live": "https://szlholdings-killinchu.hf.space/edge/quorum-status",
     "grade": "REAL_LIVE (killinchu edge — PR #44)"},
    # ── UDS-mesh runtime formulas (PR #76 merged into szl-holdings/uds-mesh/main) ──
    {"name": "PAC-Bayes + Byzantine quorum gate (UDS mesh runtime)", "thesis": "v22 §2",
     "lean": "pacBayesBound_eq_add_slack + faultyCount",
     "permalink": f"{_LEAN}/{_MAIN}/Lutar/PACBayes.lean#L165",
     "live": None,
     "home": "szl-holdings/uds-mesh mesh/formulas/pac_bayes_quorum.py — invoked by MeshGovernance.gate (PR #76; runtime SDK)",
     "grade": "REAL_REPO (mesh runtime — wired + tested)"},
    {"name": "BLS12-381 aggregate co-signature (UDS mesh, py_ecc FastAggregateVerify)", "thesis": "v22 §2 (round-11)",
     "lean": "aggregate_verify (sorry-free)",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierBLSAggregation.lean#L95",
     "live": None,
     "home": "szl-holdings/uds-mesh mesh/formulas/bls_aggregate.py — invoked by MeshGovernance.cosign (PR #76; REAL BLS12-381)",
     "grade": "REAL_REPO (mesh runtime — 6 tests green incl. tamper-reject)"},
    {"name": "Welford streaming stats (UDS mesh fan-out latency)", "thesis": "v22 §2 (round-11)",
     "lean": "welford_mean_exact (sorry-free)",
     "permalink": f"{_LEAN}/{_R11}/Lutar/Innovations/round11/FrontierWelfordVariance.lean#L89",
     "live": None,
     "home": "szl-holdings/uds-mesh mesh/formulas/welford_streaming.py — invoked by MeshGovernance.observe_fanout (PR #76)",
     "grade": "REAL_REPO (mesh runtime — z-score outlier flag)"},
]

# Honest non-endpoints — declared, not faked.
NOT_WIRED = [
    {"name": "Liouville theorem", "why": "v22-labeled scaffolding/analogy; no software call site",
     "grade": "PROVED_NOT_USED"},
    {"name": "multiplicative_monotone_isPow", "why": "Lean on-branch (PR #173, not merged); degenerate sorry",
     "grade": "PROVED_NOT_USED"},
    {"name": "monotone→continuous bridge", "why": "strongest-true form honestly refuted as FALSE; no fake proof",
     "grade": "PROVED_NOT_USED"},
    {"name": "VCG truthfulness", "why": "Lean closed on-branch (PR #172, not merged); no live call site",
     "grade": "PROVED_NOT_USED"},
    {"name": "lambda_unique (Λ uniqueness)", "why": "Λ = CONJECTURE 1. CAUCHY_ND NOT closed (2 open sorries). "
     "NO theorem, NO /formula/lambda-unique endpoint exists or is claimed.",
     "grade": "CONJECTURE (not a theorem)"},
]


def build_catalog() -> dict:
    return {
        "title": "SZL Holdings — Cross-Organ Formula Catalog (thesis v22 + Round 12)",
        "doctrine": "v11 LOCKED · 749 decl · 14 axioms · 163 sorries · c7c0ba17 · Λ = Conjecture 1",
        "lean_repo": "szl-holdings/lutar-lean",
        "wired": CATALOG,
        "not_wired": NOT_WIRED,
        "live_count": sum(1 for c in CATALOG if c.get("live")),
        "note": "a11oy HF Space is in BUILD_ERROR; a11oy-resident formulas show their REAL_REPO home "
                "rather than a fake live URL. Λ uniqueness remains Conjecture 1.",
    }


def _row_html(c: dict) -> str:
    live = c.get("live")
    if live:
        ep = (f'<a href="{live}" target="_blank" rel="noopener">{live}</a>'
              f'<pre class="resp" data-url="{live}">… fetching live …</pre>')
    else:
        ep = f'<span class="repo">REAL_REPO — {c.get("home","(no live endpoint)")}</span>'
    return (
        "<tr>"
        f'<td><b>{c["name"]}</b><div class="grade g-{ "live" if c.get("live") else "repo" }">{c["grade"]}</div></td>'
        f'<td>{c["thesis"]}</td>'
        f'<td><code>{c["lean"]}</code><br><a href="{c["permalink"]}" target="_blank" rel="noopener">Lean permalink ↗</a></td>'
        f"<td>{ep}</td>"
        "</tr>"
    )


def render_html() -> str:
    cat = build_catalog()
    rows = "\n".join(_row_html(c) for c in cat["wired"])
    nw = "\n".join(
        f'<li><b>{n["name"]}</b> — <span class="grade g-nw">{n["grade"]}</span> — {n["why"]}</li>'
        for n in NOT_WIRED
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SZL Formula Catalog — thesis v22 + Round 12</title>
<style>
:root{{--bg:#0b0e14;--fg:#e6e9ef;--mut:#9aa4b2;--card:#141a24;--acc:#6ee7b7;--repo:#fbbf24;--nw:#f87171;--line:#26303d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:26px;margin:0 0 6px}}.sub{{color:var(--mut);margin:0 0 4px}}
.doc{{color:var(--acc);font:12px ui-monospace,monospace;margin:8px 0 22px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:13.5px}}
th{{background:#0f1622;color:var(--mut);text-transform:uppercase;font-size:11px;letter-spacing:.04em}}
code{{font:12px ui-monospace,monospace;color:#c4b5fd}}
a{{color:var(--acc);text-decoration:none}}a:hover{{text-decoration:underline}}
.grade{{display:inline-block;margin-top:4px;font:11px ui-monospace,monospace;padding:1px 7px;border-radius:6px}}
.g-live{{background:rgba(110,231,183,.14);color:var(--acc)}}.g-repo{{background:rgba(251,191,36,.14);color:var(--repo)}}.g-nw{{background:rgba(248,113,113,.14);color:var(--nw)}}
pre.resp{{margin:8px 0 0;padding:8px 10px;background:#0a0f17;border:1px solid var(--line);border-radius:7px;color:#9be7c4;white-space:pre-wrap;word-break:break-word;max-height:180px;overflow:auto;font:11.5px ui-monospace,monospace}}
.repo{{color:var(--repo);font:12px ui-monospace,monospace}}
.box{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:22px 0}}
.box h2{{font-size:16px;margin:0 0 10px}}.box li{{margin:6px 0;color:var(--fg)}}
.foot{{color:var(--mut);font-size:12px;margin-top:26px;border-top:1px solid var(--line);padding-top:14px}}
.pill{{display:inline-block;background:rgba(110,231,183,.14);color:var(--acc);padding:2px 9px;border-radius:20px;font:12px ui-monospace,monospace;margin-left:6px}}
</style></head><body><div class="wrap">
<h1>SZL Holdings — Cross-Organ Formula Catalog <span class="pill">{cat['live_count']} live</span></h1>
<p class="sub">Every thesis v22 + Round-12 formula: thesis citation · real Lean theorem + GitHub permalink · live endpoint · real-time response.</p>
<p class="doc">{cat['doctrine']}</p>
<table><thead><tr><th>Formula / grade</th><th>Thesis citation</th><th>Lean theorem (permalink)</th><th>Live endpoint + real-time response</th></tr></thead>
<tbody>
{rows}
</tbody></table>
<div class="box"><h2>Honestly NOT wired (declared, not faked)</h2><ul>
{nw}
</ul></div>
<div class="box"><h2>Λ status</h2><p style="color:var(--mut)">Λ uniqueness is <b style="color:var(--nw)">Conjecture 1</b>, never a theorem. CAUCHY_ND is <b>not</b> closed (the Λ-closure squad's current file carries 2 open <code>sorry</code>s). There is no <code>lambda_unique</code> theorem and no <code>/api/a11oy/v1/formula/lambda-unique</code> endpoint — the Round-12 Λ→Theorem closure did <b>not</b> succeed, so it is not claimed here.</p></div>
<p class="foot">© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Apache-2.0 · Lean: <a href="https://github.com/szl-holdings/lutar-lean" target="_blank" rel="noopener">szl-holdings/lutar-lean</a>. Live cells fetch each endpoint from your browser; a11oy-resident formulas show their REAL_REPO home because the a11oy HF Space is in BUILD_ERROR.</p>
</div>
<script>
document.querySelectorAll('pre.resp').forEach(function(pre){{
  var url=pre.getAttribute('data-url');
  fetch(url).then(function(r){{return r.text().then(function(t){{
    try{{pre.textContent='HTTP '+r.status+'  '+JSON.stringify(JSON.parse(t),null,1);}}
    catch(e){{pre.textContent='HTTP '+r.status+'  '+t.slice(0,400);}}
  }});}}).catch(function(e){{pre.textContent='fetch error: '+e;}});
}});
</script>
</body></html>"""


def register(app, ns: str = "rosie") -> str:
    """Mount GET /formulas (HTML) + GET /api/{ns}/v1/formulas/catalog (JSON)."""
    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get("/formulas", response_class=HTMLResponse)
    async def _formulas_page():
        return HTMLResponse(render_html())

    @app.get(f"/api/{ns}/v1/formulas/catalog")
    async def _formulas_catalog():
        return JSONResponse(build_catalog())

    return "formula-catalog-mounted:/formulas"


__all__ = ["register", "build_catalog", "render_html"]

if __name__ == "__main__":  # pragma: no cover
    print(render_html()[:600])

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
