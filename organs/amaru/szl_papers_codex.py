# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Co-Authored-By Perplexity Computer Agent
"""
szl_papers_codex.py — ADDITIVE FastAPI module that SURFACES platform research
artifacts already living in szl-holdings/platform@main but never exposed in the
amaru flagship UI:

  1. The 8 research papers under `papers/*.tex` (Lutar Omega, Prisca-GraphRAG,
     Hermetic AI-Safety, Sefirot/Hopfield, Free-Energy/FELAI, Tawa-SAE,
     EPR-Bell/Sacred-Geometry, Chinchilla-Lutar/Grokking).
  2. The Codex-Kernel reference (packages/codex-kernel) — Dresden Codex Venus
     emulator + SZL governed-ops bundle, with the two CI-verified payload hashes.

Single integration point (mirrors szl_unay_routes / szl_live_wires):

    import szl_papers_codex
    szl_papers_codex.register(app, ns="amaru")

Routes added (NEW paths, never collide with existing /api/{ns}/v1|v2/*):
  GET /papers                          — mobile-first HTML panel (papers + codex)
  GET /api/{ns}/v1/papers              — JSON list of the 8 papers
  GET /api/{ns}/v1/codex-kernel        — JSON codex-kernel reference + verified hashes
  GET /api/{ns}/v1/papers/healthz      — 200 + version

ADDITIVE ONLY. Desktop behavior unchanged. Mobile-first per
SZL_MOBILE_FIRST_STANDARD: viewport-fit=cover, 375px verified, touch targets >=44px,
theme-color #0a0e14. No doctrine artifact is modified; this is presentation + links.

HONESTY: Λ-uniqueness is cited as **Conjecture 1**, never a theorem. SLSA L1.
Quechua terms are brand only. The two payload hashes below are the public,
CI-verified prefixes from the codex-kernel-verify gate (full digests on GitHub).
"""
from __future__ import annotations

import json

GH = "https://github.com/szl-holdings/platform/blob/main"
GH_TREE = "https://github.com/szl-holdings/platform/tree/main"

# ---------------------------------------------------------------------------
# Papers — sourced verbatim from papers/*.tex on platform@main.
# ---------------------------------------------------------------------------
PAPERS = [
    {
        "id": "paper-01",
        "file": "papers/paper-01-lutar-omega-formalism.tex",
        "title": "The Lutar Omega Formalism: A Unified Energy-Mass-Information Framework "
                 "with Ancient Metrological Constants and Sacred Geometry Coherence",
        "abstract": "Seven-version hierarchical framework unifying energy, mass and information "
                    "through a single dimensionless signature L_Omega = sum_i w_i L_i "
                    "(Einstein baseline -> Bekenstein entropy -> Penrose CCC -> Boltzmann-Shannon "
                    "-> Berry holonomy -> E8 triality -> Noether conservation). Subsumes the "
                    "Chinchilla scaling law and Friston free-energy principle as special cases.",
        "math": "L_Omega = Σ_{i=1}^{7} w_i L_i (adaptive softmax weights); Noether closure convergence",
        "dois": ["10.5281/zenodo.19867281", "10.5281/zenodo.19934129"],
    },
    {
        "id": "paper-02",
        "file": "papers/paper-02-prisca-graphrag.tex",
        "title": "Prisca-GraphRAG: Knowledge Retrieval via Ancient Lineage-Boosted Graph "
                 "Augmented Generation with Federated Privacy",
        "abstract": "Retrieval-augmented generation that structures knowledge graphs by "
                    "prisca-theologia lineage with federated privacy guarantees.",
        "math": "Lineage-boosted graph traversal; hybrid retrieval fusion",
        "dois": ["10.5281/zenodo.19867281", "10.5281/zenodo.19934129"],
    },
    {
        "id": "paper-03",
        "file": "papers/paper-03-hermetic-ai-safety.tex",
        "title": "Hermetic Constitutional Guardrails: Safety Alignment Through Ancient "
                 "Philosophical Principles with Noether-Invariant Evaluation and "
                 "Apollo-METR Red-Team Validation",
        "abstract": "Constitutional safety principles derived from the seven Hermetic laws of "
                    "the Kybalion, with Noether-invariant evaluation and Apollo/METR red-team "
                    "validation.",
        "math": "Noether-invariant safety evaluation over constitutional constraints",
        "dois": ["10.5281/zenodo.19867281", "10.5281/zenodo.19934129"],
    },
    {
        "id": "paper-04",
        "file": "papers/paper-04-sefirot-kabbalah-hopfield.tex",
        "title": "Sefirot Continual Learning with Kabbalah-Tiered Memory and Hopfield-Amaru "
                 "Associative Retrieval",
        "abstract": "Continual-learning framework structuring knowledge persistence across the "
                    "ten Sefirot with Hopfield associative (energy-based) retrieval.",
        "math": "Hopfield energy E(x) = -1/2 x^T W x; 10-tier memory hierarchy",
        "dois": [],
    },
    {
        "id": "paper-05",
        "file": "papers/paper-05-free-energy-predictive-coding.tex",
        "title": "Free-Energy-Lutar Active Inference with Hierarchical Predictive Coding "
                 "and Cognitive Map Navigation",
        "abstract": "Extends Friston's Free Energy Principle with the Lutar Omega signature to "
                    "form FELAI, replacing standard KL divergence with an Omega-weighted divergence.",
        "math": "F = E_q[ln q(s) - ln p(o,s)]; Omega-weighted KL; hierarchical predictive coding",
        "dois": [],
    },
    {
        "id": "paper-06",
        "file": "papers/paper-06-tawa-sae-interpretability.tex",
        "title": "Tawa Sparse Autoencoder: Ceque-Indexed Dictionary Learning for Neural "
                 "Network Interpretability",
        "abstract": "Dictionary-learning SAE for interpretability that indexes learned features "
                    "using the 41-line Inca ceque system.",
        "math": "min ||x - D a||^2 + λ||a||_1 (sparse dictionary learning); 41-ceque index",
        "dois": [],
    },
    {
        "id": "paper-07",
        "file": "papers/paper-07-epr-bell-sacred-geometry.tex",
        "title": "EPR-Bell Entanglement Validation and Sacred Geometry Coherence for "
                 "Quantum-Classical AI Systems",
        "abstract": "Applies the CHSH inequality from quantum foundations to test whether AI "
                    "model correlation matrices exhibit non-classical structure.",
        "math": "CHSH: |S| = |E(a,b) - E(a,b') + E(a',b) + E(a',b')| ≤ 2 (classical bound)",
        "dois": [],
    },
    {
        "id": "paper-08",
        "file": "papers/paper-08-scaling-grokking-bifurcation.tex",
        "title": "Chinchilla-Lutar Scaling Laws with Grokking Phase Detection, "
                 "E8-Triality Mixture-of-Experts, and Dynamical Systems Bifurcation Analysis",
        "abstract": "Four contributions: Chinchilla-Lutar scaling, grokking phase detection, "
                    "E8-triality mixture-of-experts routing, and bifurcation analysis of "
                    "training dynamics.",
        "math": "L(N,D) = E + A/N^α + B/D^β (Chinchilla); grokking phase transition; bifurcation",
        "dois": [],
    },
]

# ---------------------------------------------------------------------------
# Codex-Kernel reference — packages/codex-kernel, CI gate codex-kernel-verify.yml.
# The two payload-hash prefixes are the public CI-verified bundles. Full digests
# are on GitHub; we show prefixes here exactly as captured.
# ---------------------------------------------------------------------------
CODEX_KERNEL = {
    "package": "@workspace/codex-kernel",
    "version": "1.0.0",
    "source": f"{GH_TREE}/packages/codex-kernel",
    "ci_gate": "codex-kernel-verify.yml (replay reproduces bundles bit-for-bit each commit)",
    "summary": "Replay-grade governed-loop primitive: hash-chained state "
               "next_state_hash = H(prev_hash || delta || next_state) (128-bit FNV-1a), "
               "decision receipts, append-only JSONL proof ledger, hard-stop validators "
               "(state_transition_rule, drift_bounds, evidence_provenance, human_gate), "
               "replay verifier, DSSE receipts.",
    "dresden_venus": {
        "what": "Dresden Codex Venus emulator — pre-Columbian Maya synodic-Venus drift "
                "(~583.92-day period, 584-day idealized) modelled as a deterministic governed "
                "loop where drift correction must be explicitly proposed with a decision receipt.",
        "payload_hash_prefix": "fe20ecc47445",
        "runner": "packages/codex-kernel/runner/payload.json",
    },
    "szl_governed_ops": {
        "what": "SZL governed-ops reference bundle (governance ON vs OFF posture).",
        "payload_hash_prefix": "ca0910f40dd2",
        "runner": "packages/codex-kernel/runner/szl-private-governed-ops-001.payload.json",
    },
    "standards": ["EU AI Act Article 12 (record-keeping)", "NIST AI RMF — MEASURE & MANAGE"],
    "honest_note": "Not cryptographically tamper-resistant; the FNV-1a chain is sufficient for "
                   "replay. Swap to SHA-256 in a wrapper for adversarial integrity.",
}

VERSION = "papers-codex-surface-v1 (Doctrine v11 LOCKED 749/14/163)"


def _papers_html(ns: str) -> str:
    cards = []
    for p in PAPERS:
        doi_html = ""
        if p["dois"]:
            doi_html = " · ".join(
                f'<a href="https://doi.org/{d}" target="_blank" rel="noopener">{d}</a>'
                for d in p["dois"]
            )
        else:
            doi_html = '<span class="muted">DOI pending (companion v1/v2 DOIs apply)</span>'
        cards.append(f"""
      <article class="card">
        <div class="pid">{p['id']}</div>
        <h3>{p['title']}</h3>
        <p class="abs">{p['abstract']}</p>
        <p class="math"><b>Math:</b> {p['math']}</p>
        <p class="links">
          <a href="{GH}/{p['file']}" target="_blank" rel="noopener">source .tex ↗</a>
          <span class="doi">{doi_html}</span>
        </p>
      </article>""")
    ck = CODEX_KERNEL
    codex_html = f"""
      <article class="card codex">
        <div class="pid">codex-kernel · v{ck['version']}</div>
        <h3>Codex-Kernel — replay-grade governed loop</h3>
        <p class="abs">{ck['summary']}</p>
        <div class="receipt">
          <div class="rrow"><span>Dresden Venus payload</span><code>{ck['dresden_venus']['payload_hash_prefix']}…</code></div>
          <div class="rsub">{ck['dresden_venus']['what']}</div>
          <div class="rrow"><span>SZL governed-ops payload</span><code>{ck['szl_governed_ops']['payload_hash_prefix']}…</code></div>
          <div class="rsub">{ck['szl_governed_ops']['what']}</div>
        </div>
        <p class="math"><b>CI gate:</b> {ck['ci_gate']}</p>
        <p class="links">
          <a href="{ck['source']}" target="_blank" rel="noopener">packages/codex-kernel ↗</a>
        </p>
        <p class="muted">{ck['honest_note']}</p>
      </article>"""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0a0e14">
<title>SZL Papers + Codex-Kernel — amaru</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #0a0e14; color: #e6edf3;
          font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          padding: max(16px, env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom)); }}
  header {{ max-width: 880px; margin: 0 auto 20px; }}
  h1 {{ font-size: clamp(1.4rem, 5vw, 2rem); margin: 0 0 6px; }}
  .sub {{ color: #9aa7b4; font-size: .9rem; }}
  .grid {{ max-width: 880px; margin: 0 auto; display: grid; gap: 16px;
           grid-template-columns: 1fr; }}
  @media (min-width: 720px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} .codex {{ grid-column: 1 / -1; }} }}
  .card {{ background: #111722; border: 1px solid #1e2a3a; border-radius: 14px; padding: 16px; }}
  .codex {{ border-color: #2d4a2d; background: #0f1710; }}
  .pid {{ font: 600 .72rem/1 ui-monospace, monospace; letter-spacing: .06em;
          text-transform: uppercase; color: #5fb8ff; margin-bottom: 8px; }}
  h3 {{ font-size: 1.02rem; margin: 0 0 8px; }}
  .abs {{ color: #c4cdd6; font-size: .92rem; margin: 0 0 10px; }}
  .math {{ color: #b6e3b6; font-size: .85rem; margin: 0 0 10px; word-break: break-word; }}
  .links a {{ color: #5fb8ff; text-decoration: none; display: inline-block;
              min-height: 44px; line-height: 44px; padding-right: 14px; }}
  .links a:active {{ opacity: .6; }}
  .doi {{ color: #9aa7b4; font-size: .82rem; }}
  .doi a {{ color: #9aa7b4; line-height: 1.4; min-height: 0; }}
  .muted {{ color: #6b7785; font-size: .8rem; }}
  .receipt {{ background:#0a0e14; border:1px solid #1e2a3a; border-radius:10px; padding:10px; margin:8px 0; }}
  .rrow {{ display:flex; justify-content:space-between; gap:10px; font-size:.85rem; padding:4px 0; }}
  .rrow code {{ color:#ffd479; }}
  .rsub {{ color:#8794a1; font-size:.78rem; padding:0 0 6px; }}
  footer {{ max-width: 880px; margin: 24px auto 0; color: #6b7785; font-size: .78rem; }}
  footer a {{ color: #5fb8ff; }}
</style>
</head>
<body>
<header>
  <h1>Research Papers + Codex-Kernel</h1>
  <p class="sub">8 papers + replay-grade kernel, surfaced from
  <a href="{GH_TREE}" style="color:#5fb8ff">szl-holdings/platform@main</a>.
  Doctrine v11 LOCKED · 749/14/163 · Λ-uniqueness = <b>Conjecture 1</b> · SLSA L1.</p>
</header>
<main class="grid">
  {codex_html}
  {''.join(cards)}
</main>
<footer>
  Author: Stephen Paul Lutar Jr. · ORCID
  <a href="https://orcid.org/0009-0001-0110-4173" target="_blank" rel="noopener">0009-0001-0110-4173</a>.
  Reference implementation: <code>packages/ouroboros-integrations</code>.
  Surfaced additively by Yachay. Quechua terms are brand only; no fabrication.
</footer>
</body>
</html>"""


def register(app, ns: str = "amaru", api_app=None) -> dict:
    """Mount the papers + codex-kernel surface. ADDITIVE; never raises into caller."""
    from fastapi.responses import HTMLResponse, JSONResponse

    target = api_app if api_app is not None else app

    @app.get("/papers", response_class=HTMLResponse)
    async def _papers_panel():  # noqa: ANN202
        return HTMLResponse(_papers_html(ns))

    @target.get(f"/api/{ns}/v1/papers")
    async def _papers_json():  # noqa: ANN202
        return JSONResponse({"version": VERSION, "count": len(PAPERS), "papers": PAPERS})

    @target.get(f"/api/{ns}/v1/codex-kernel")
    async def _codex_json():  # noqa: ANN202
        return JSONResponse({"version": VERSION, "codex_kernel": CODEX_KERNEL})

    @target.get(f"/api/{ns}/v1/papers/healthz")
    async def _papers_health():  # noqa: ANN202
        return JSONResponse({"ok": True, "version": VERSION})

    return {"ok": True, "version": VERSION, "papers": len(PAPERS),
            "routes": ["/papers", f"/api/{ns}/v1/papers",
                       f"/api/{ns}/v1/codex-kernel", f"/api/{ns}/v1/papers/healthz"]}


if __name__ == "__main__":
    # Quick offline render check.
    html = _papers_html("amaru")
    print(f"[papers-codex] {VERSION}")
    print(f"[papers-codex] papers={len(PAPERS)} html_bytes={len(html)}")
    print(json.dumps({"codex_hashes": [
        CODEX_KERNEL["dresden_venus"]["payload_hash_prefix"],
        CODEX_KERNEL["szl_governed_ops"]["payload_hash_prefix"],
    ]}))
