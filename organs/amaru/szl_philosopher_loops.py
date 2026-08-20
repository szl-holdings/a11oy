# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Co-Authored-By Perplexity Computer Agent
"""
szl_philosopher_loops.py — ADDITIVE FastAPI module surfacing the named
"philosopher" Ouroboros packages from szl-holdings/platform@main as a single
"Philosopher Loops" panel in the amaru flagship.

These TS packages contain real, source-cited math/logic primitives but had ZERO
flagship exposure. This surfaces them (links + math summaries), additive-only.

    import szl_philosopher_loops
    szl_philosopher_loops.register(app, ns="amaru")

Routes (NEW; never collide):
  GET /philosopher-loops               — mobile-first HTML panel
  GET /api/{ns}/v1/philosopher-loops   — JSON catalog

Doctrine v11 LOCKED. Λ-uniqueness = Conjecture 1, never a theorem.
SLSA L1 honest. Quechua = brand only.
"""
from __future__ import annotations

GH_TREE = "https://github.com/szl-holdings/platform/tree/main/packages"

# Seven named philosopher loops requested by the founder directive, each with a
# verbatim-sourced math/logic summary drawn from the package source headers.
LOOPS = [
    {
        "pkg": "ouroboros-aristotle",
        "name": "Aristotle — syllogistic gates",
        "math": "13 demonstration gates incl. PNC bedrock-axiom guard (Metaphysics Γ.3 1005b19): "
                "blocks attempts to prove the Principle of Non-Contradiction, inferences entailing "
                "(A ∧ ¬A), and treating PNC as a revisable hypothesis. Plus metabasis prohibition, "
                "hoti/dioti classifier, kath-hauto predication filter, qua-realism gate.",
    },
    {
        "pkg": "ouroboros-davinci",
        "name": "da Vinci — divine proportion",
        "math": "φ = (1+√5)/2 (Pacioli & Leonardo, De Divina Proportione 1509). verifyPhi(ratio) "
                "with exact tol 1e-6 / approx tol 0.05; sfumato, vanishing-point, Vitruvian frame.",
    },
    {
        "pkg": "ouroboros-gauss",
        "name": "Gauß — least-squares adjustment",
        "math": "x* = arg min ‖Ax − b‖² via normal equations AᵀA x* = Aᵀb (network adjustment); "
                "residual-fit, conformal projection, class-number primitives.",
    },
    {
        "pkg": "ouroboros-jung",
        "name": "Jung — individuation ledger",
        "math": "Monotone-progress ledger over ordered stages persona → shadow-encounter → "
                "anima-animus → self-recognition → wholeness; every advance carries a witness, "
                "regressions logged honestly. Plus archetype mapping, synchronicity log.",
    },
    {
        "pkg": "ouroboros-newton",
        "name": "Newton — three-laws ledger",
        "math": "ΣF = dp/dt (Principia 1687, Axiomata); transition verdicts OK/LEX2_FAIL/"
                "LEX3_UNPAIRED/DIM_MISMATCH pairing every action with an opposing reaction; "
                "fluxions receipt, prismatic spectrum.",
    },
    {
        "pkg": "ouroboros-oppenheimer",
        "name": "Oppenheimer — dual-use review",
        "math": "Bohr open-world test: artifacts scored on four ledgers benignBenefit, harmPotential, "
                "reproducibility, verifiability ∈ [0,1] (LoC MSS35188 Bohr/Frankfurter 1944–45). "
                "Plus classification ladder, clearance ledger, moral ledger.",
    },
    {
        "pkg": "ouroboros-socrates",
        "name": "Socrates — divided line",
        "math": "Cognitive tiers EIKASIA < PISTIS < DIANOIA < NOESIS with grounding ranks; "
                "PISTIS→DIANOIA requires explicit hypotheses (elenchus, synoptic-witness, "
                "hypothesis ledger).",
    },
]

VERSION = "philosopher-loops-v1 (Doctrine v11 LOCKED 749/14/163)"


def _html() -> str:
    cards = []
    for L in LOOPS:
        cards.append(f"""
      <article class="card">
        <div class="pid">{L['pkg']}</div>
        <h3>{L['name']}</h3>
        <p class="math">{L['math']}</p>
        <p class="links"><a href="{GH_TREE}/{L['pkg']}" target="_blank" rel="noopener">source ↗</a></p>
      </article>""")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0a0e14">
<title>Philosopher Loops — amaru</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0a0e14; color:#e6edf3;
          font:16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          padding:max(16px, env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom)); }}
  header {{ max-width:880px; margin:0 auto 20px; }}
  h1 {{ font-size:clamp(1.4rem,5vw,2rem); margin:0 0 6px; }}
  .sub {{ color:#9aa7b4; font-size:.9rem; }}
  .sub a {{ color:#5fb8ff; }}
  .grid {{ max-width:880px; margin:0 auto; display:grid; gap:16px; grid-template-columns:1fr; }}
  @media (min-width:720px) {{ .grid {{ grid-template-columns:1fr 1fr; }} }}
  .card {{ background:#111722; border:1px solid #1e2a3a; border-radius:14px; padding:16px; }}
  .pid {{ font:600 .72rem/1 ui-monospace, monospace; letter-spacing:.06em; text-transform:uppercase;
          color:#c08bff; margin-bottom:8px; }}
  h3 {{ font-size:1.02rem; margin:0 0 8px; }}
  .math {{ color:#c4cdd6; font-size:.9rem; margin:0 0 10px; word-break:break-word; }}
  .links a {{ color:#5fb8ff; text-decoration:none; display:inline-block; min-height:44px; line-height:44px; }}
  .links a:active {{ opacity:.6; }}
  footer {{ max-width:880px; margin:24px auto 0; color:#6b7785; font-size:.78rem; }}
  footer a {{ color:#5fb8ff; }}
</style>
</head>
<body>
<header>
  <h1>Philosopher Loops</h1>
  <p class="sub">Seven named Ouroboros primitives surfaced from
  <a href="https://github.com/szl-holdings/platform/tree/main" target="_blank" rel="noopener">szl-holdings/platform@main</a>.
  Doctrine v11 LOCKED · 749/14/163 · Λ-uniqueness = <b>Conjecture 1</b> · SLSA L1.</p>
</header>
<main class="grid">
  {''.join(cards)}
</main>
<footer>
  Each loop maps a historical/philosophical principle to a computable governance gate with cited sources.
  Surfaced additively by Yachay. Quechua terms are brand only; no fabrication.
</footer>
</body>
</html>"""


def register(app, ns: str = "amaru", api_app=None) -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse
    target = api_app if api_app is not None else app

    @app.get("/philosopher-loops", response_class=HTMLResponse)
    async def _phil_panel():  # noqa: ANN202
        return HTMLResponse(_html())

    @target.get(f"/api/{ns}/v1/philosopher-loops")
    async def _phil_json():  # noqa: ANN202
        return JSONResponse({"version": VERSION, "count": len(LOOPS), "loops": LOOPS})

    return {"ok": True, "version": VERSION, "loops": len(LOOPS),
            "routes": ["/philosopher-loops", f"/api/{ns}/v1/philosopher-loops"]}


if __name__ == "__main__":
    html = _html()
    print(f"[philosopher-loops] {VERSION} loops={len(LOOPS)} html_bytes={len(html)}")
