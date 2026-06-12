# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Co-Authored-By Perplexity Computer Agent
"""
szl_alloy_embed_fabric.py — ADDITIVE FastAPI module surfacing the Alloy Embedding
Fabric (AEF) in the a11oy flagship.

The real embedder + pgvector hybrid search + governance lives at
`apps/alloy-embedding-api` and the `aef-*` packages on szl-holdings/platform@main,
but a11oy had NO surface for it. This adds a linkable panel with the actual
retrieval math (reciprocal-rank fusion, recall@k / nDCG / MRR) — additive-only.

    import szl_alloy_embed_fabric
    szl_alloy_embed_fabric.register(app, ns="a11oy")

Routes (NEW; never collide):
  GET /alloy-embed-fabric              — mobile-first HTML panel
  GET /api/{ns}/v1/alloy-embed-fabric  — JSON catalog

Doctrine v11 LOCKED. SLSA L1 honest. Quechua = brand only.
"""
from __future__ import annotations

GH = "https://github.com/szl-holdings/platform/tree/main"

COMPONENTS = [
    {
        "pkg": "apps/alloy-embedding-api",
        "name": "Alloy Embedding Fabric — REST gateway",
        "what": "Real embedder + pgvector hybrid search + reranking + ingestion + evals. "
                "Default port 8766, BASE_PATH /alloy-embedding-api, bearer-token auth.",
        "url": f"{GH}/apps/alloy-embedding-api",
    },
    {
        "pkg": "aef-retrieval-core",
        "name": "Retrieval core — reciprocal-rank fusion",
        "what": "Pure retrieval functions. reciprocalRankFusion fuses dense + keyword rankings: "
                "fusedScore = Σ over lists of weight / (k + rank), default k=60, "
                "denseWeight=0.6, keywordWeight=0.4. Plus query normalization, boost, citations, filter.",
        "url": f"{GH}/packages/aef-retrieval-core",
    },
    {
        "pkg": "aef-evals",
        "name": "Retrieval evals — recall@k / nDCG / MRR",
        "what": "Retrieval evaluation harness computing recall@k, nDCG, MRR, exact-match against "
                "labelled query sets.",
        "url": f"{GH}/packages/aef-evals",
    },
    {
        "pkg": "aef-policy-guard",
        "name": "Policy guard — tenant boundaries",
        "what": "Policy rule evaluation, tenant boundary enforcement, retention controls over "
                "every retrieval request.",
        "url": f"{GH}/packages/aef-policy-guard",
    },
    {
        "pkg": "aef-evidence-ledger",
        "name": "Evidence ledger — append-only",
        "what": "Append-only ledger recording request, chunk, source, score for every retrieval — "
                "the provenance spine of the fabric.",
        "url": f"{GH}/packages/aef-evidence-ledger",
    },
    {
        "pkg": "aef-storage-adapters",
        "name": "Storage adapters — pgvector + local",
        "what": "Unified storage adapter interface with working local-filesystem and pgvector "
                "(approximate-nearest-neighbour) backends.",
        "url": f"{GH}/packages/aef-storage-adapters",
    },
]

VERSION = "alloy-embed-fabric-surface-v1 (Doctrine v11 LOCKED 749/14/163)"


def _embed_backend() -> dict:
    """Honest status of the embedding backend. When A11OY_EMBED_BASE_URL is set
    (e.g. a self-hosted TEI / vLLM embeddings server on the RTX 5000 Hetzner GPU
    node, OpenAI-compatible /embeddings), report 'self-hosted-gpu' and probe it.
    With no endpoint configured, report the honest 'catalog-only' state — the
    fabric is documented + runnable on platform, but no live embedder is wired to
    THIS surface. Never claims a live embedder that isn't there.
    """
    import os
    base = (os.environ.get("A11OY_EMBED_BASE_URL")
            or os.environ.get("EMBED_BASE_URL") or "").rstrip("/")
    model = os.environ.get("A11OY_EMBED_MODEL") or "BAAI/bge-large-en-v1.5"
    if not base:
        return {"wired": False, "kind": "catalog-only", "base": None, "model": None,
                "note": ("No A11OY_EMBED_BASE_URL configured. This surface catalogs the "
                         "Alloy Embedding Fabric (real embedder lives in "
                         "apps/alloy-embedding-api on platform); set A11OY_EMBED_BASE_URL "
                         "to a self-hosted TEI/vLLM /embeddings endpoint to wire a live "
                         "GPU embedder here. Honest: not live until then.")}
    kind = "self-hosted-gpu" if ("huggingface.co" not in base.lower()) else "hf-router"
    reachable, http = False, None
    try:
        import urllib.request as _u, json as _j
        token = (os.environ.get("A11OY_EMBED_TOKEN") or os.environ.get("A11OY_GPU_TOKEN")
                 or os.environ.get("VLLM_API_KEY") or "").strip()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        body = _j.dumps({"model": model, "input": "healthz"}).encode()
        req = _u.Request(base + "/embeddings", data=body, headers=headers, method="POST")
        with _u.urlopen(req, timeout=8) as r:  # noqa: S310
            http = r.status
            reachable = (r.status == 200)
    except Exception as e:  # noqa: BLE001
        http = type(e).__name__
    return {"wired": True, "kind": kind, "base": base, "model": model,
            "reachable": reachable, "probe_http": http,
            "note": ("Live embedder wired. 'reachable' reflects a real /embeddings probe — "
                     "never claims live unless the probe returned 200.")}


def _html() -> str:
    cards = "".join(f"""
      <article class="card">
        <div class="pid">{c['pkg']}</div>
        <h3>{c['name']}</h3>
        <p class="what">{c['what']}</p>
        <p class="links"><a href="{c['url']}" target="_blank" rel="noopener">source ↗</a></p>
      </article>""" for c in COMPONENTS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0a0e14">
<title>Alloy Embedding Fabric — a11oy</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0a0e14; color:#e6edf3;
          font:16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          padding:max(16px, env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom)); }}
  header {{ max-width:880px; margin:0 auto 20px; }}
  h1 {{ font-size:clamp(1.4rem,5vw,2rem); margin:0 0 6px; }}
  .sub {{ color:#9aa7b4; font-size:.9rem; }} .sub a {{ color:#5fb8ff; }}
  .grid {{ max-width:880px; margin:0 auto; display:grid; gap:16px; grid-template-columns:1fr; }}
  @media (min-width:720px) {{ .grid {{ grid-template-columns:1fr 1fr; }} }}
  .card {{ background:#111722; border:1px solid #1e2a3a; border-radius:14px; padding:16px; }}
  .pid {{ font:600 .72rem/1 ui-monospace, monospace; letter-spacing:.06em; text-transform:uppercase;
          color:#5fe0c0; margin-bottom:8px; }}
  h3 {{ font-size:1.02rem; margin:0 0 8px; }}
  .what {{ color:#c4cdd6; font-size:.9rem; margin:0 0 10px; word-break:break-word; }}
  .links a {{ color:#5fb8ff; text-decoration:none; display:inline-block; min-height:44px; line-height:44px; }}
  .links a:active {{ opacity:.6; }}
  footer {{ max-width:880px; margin:24px auto 0; color:#6b7785; font-size:.78rem; }} footer a {{ color:#5fb8ff; }}
</style>
</head>
<body>
<header>
  <h1>Alloy Embedding Fabric</h1>
  <p class="sub">Real embedder + pgvector hybrid search + governance, surfaced from
  <a href="https://github.com/szl-holdings/platform/tree/main" target="_blank" rel="noopener">szl-holdings/platform@main</a>.
  Doctrine v11 LOCKED · 749/14/163 · SLSA L1.</p>
</header>
<main class="grid">{cards}</main>
<footer>
  Hybrid retrieval = dense (pgvector ANN) ⊕ keyword, fused by reciprocal-rank fusion
  (k=60, dense 0.6 / keyword 0.4), evaluated by recall@k · nDCG · MRR.
  Surfaced additively by Yachay. Quechua terms are brand only; no fabrication.
</footer>
</body>
</html>"""


def register(app, ns: str = "a11oy") -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get("/alloy-embed-fabric", response_class=HTMLResponse)
    async def _aef_panel():  # noqa: ANN202
        return HTMLResponse(_html())

    @app.get(f"/api/{ns}/v1/alloy-embed-fabric")
    async def _aef_json():  # noqa: ANN202
        return JSONResponse({"version": VERSION, "count": len(COMPONENTS),
                             "components": COMPONENTS, "backend": _embed_backend()})

    @app.get(f"/api/{ns}/v1/alloy-embed-fabric/health")
    async def _aef_health():  # noqa: ANN202
        # Honest live status of the embedding backend (catalog-only vs
        # self-hosted-gpu vs hf-router), with a real /embeddings probe.
        return JSONResponse({"service": "alloy-embed-fabric", "doctrine": "v11",
                             "backend": _embed_backend()})

    return {"ok": True, "version": VERSION, "components": len(COMPONENTS),
            "routes": ["/alloy-embed-fabric", f"/api/{ns}/v1/alloy-embed-fabric",
                       f"/api/{ns}/v1/alloy-embed-fabric/health"]}


if __name__ == "__main__":
    html = _html()
    print(f"[alloy-embed-fabric] {VERSION} components={len(COMPONENTS)} html_bytes={len(html)}")
