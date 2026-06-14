# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by the NEMOTRON SIGNED-TRAJECTORY build team. Co-Authored-By: Perplexity Computer Agent.
"""
szl_nemotron_corpus — served SIGNED-CORPUS tab + verify/stats endpoints for a11oy.

WHAT THIS SERVES (honest framing — read before extending):
    A single, self-contained "Signed Corpus" surface that lets anyone:
      1. SEE sample DSSE-signed agent-trajectory receipts (one JSONL line per
         agent step: action / observation / restraint_verdict / step_hash /
         signature), mapped from nvidia/Nemotron-Agentic-v1 (CC BY 4.0, NVIDIA).
      2. RUN a signature/integrity check IN-BROWSER against any pasted JSONL,
         calling POST /api/a11oy/v1/nemo/verify (server-side szl_dsse verify).
      3. READ honest corpus stats (counts, verdict/pattern mix, signing status).

    Routes (all registered BEFORE the SPA catch-all so explicit paths win):
      GET  /signed-corpus                         -> premium HTML tab
      GET  /api/a11oy/v1/nemo/stats               -> corpus stats JSON
      GET  /api/a11oy/v1/nemo/sample              -> the sample signed JSONL (text)
      POST /api/a11oy/v1/nemo/verify              -> {jsonl} -> aggregate verify JSON

    A small idempotent nav-injection middleware appends a floating "Signed Corpus"
    link to every served HTML surface (so the tab is reachable from the console
    without editing the React SPA). Additive, never rewrites page content.

HONEST LABELS (Doctrine gates — never weaken):
    - "QLoRA-ready corpus; training = ROADMAP (needs 2x80GB GPU)."
    - DATASET property, NOT a model claim. Not an Ultra reproduction. Not from
      scratch. Trust is never 100%. Data labeled LIVE / SAMPLE / MODELED.
    - CC BY 4.0 attribution to NVIDIA is shown on the page and in /stats.
    - Real ECDSA-P256 signatures only when SZL_COSIGN_PRIVATE_KEY_PEM is present;
      else honest UNSIGNED — the verifier reports this transparently.

ADDITIVE · FastAPI + szl_trajectory_sign + szl_nemotron_ingest · 0 runtime CDN.
"""
from __future__ import annotations

import html as _html
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

import szl_trajectory_sign as sts
import szl_nemotron_ingest as ingest

LEAN_SHA = "c7c0ba17"
DOCTRINE = {"version": "v11/v12", "counts": "749/14/163", "lambda": "Conjecture 1"}

# Build the SAMPLE corpus ONCE at import (CPU-only, deterministic content).
try:
    _CORPUS = ingest.build_sample_corpus(label="SAMPLE")
except Exception as _exc:  # never crash registration
    _CORPUS = {"trajectories": [], "jsonl": "", "stats": {
        "label": "SAMPLE", "trajectory_count": 0, "total_steps": 0,
        "verdict_counts": {}, "pattern_counts": {},
        "signing_available": False, "attribution": ingest.ATTRIBUTION,
        "build_error": f"{type(_exc).__name__}: {_exc}"}}


def _stats() -> Dict[str, Any]:
    st = dict(_CORPUS["stats"])
    # Verify the shipped sample so /stats reports honest live integrity numbers.
    v = sts.verify_jsonl(_CORPUS["jsonl"])
    st["verify"] = {k: v[k] for k in
                    ("total_steps", "hash_ok", "signed", "sig_ok",
                     "all_hash_ok", "all_sig_ok")}
    st["doctrine"] = DOCTRINE
    st["step_schema"] = sts.STEP_SCHEMA
    st["payload_type"] = sts.STEP_PAYLOAD_TYPE
    st["source_total_samples"] = ingest.SOURCE_TOTAL
    st["honesty"] = (
        "QLoRA-ready signed-trajectory corpus (DATASET property, not a model claim). "
        "Actual QLoRA/GRPO training = ROADMAP (needs 2x80GB GPU). Not an Ultra "
        "reproduction; not trained from scratch. SAMPLE shown is a representative "
        "schema-faithful mapping of nvidia/Nemotron-Agentic-v1 (CC BY 4.0, NVIDIA); "
        "the full 335,122 samples are re-derivable locally from the open source."
    )
    return st


# --------------------------------------------------------------------------- #
# HTML tab
# --------------------------------------------------------------------------- #
def _sample_cards() -> str:
    cards = []
    for traj in _CORPUS["trajectories"]:
        prov = traj["provenance"]
        steps = traj["steps"]
        rows = []
        for s in steps:
            act = s.get("action")
            act_str = json.dumps(act) if not isinstance(act, str) else act
            if len(act_str) > 140:
                act_str = act_str[:140] + "…"
            obs = s.get("observation") or ""
            if len(obs) > 100:
                obs = obs[:100] + "…"
            verdict = s.get("restraint_verdict", "ALLOW")
            vclass = {"ALLOW": "ok", "HOLD": "warn", "MONITOR": "exp",
                      "DECLINE": "bad"}.get(verdict, "exp")
            corr = " ⟲ correction" if s.get("is_correction") else ""
            rows.append(f"""
            <tr>
              <td class="num">{s.get('step')}</td>
              <td><span class="pat">{_html.escape(s.get('pattern',''))}</span>{corr}</td>
              <td class="role">{_html.escape(s.get('role',''))}</td>
              <td class="act"><code>{_html.escape(act_str)}</code></td>
              <td class="obs">{_html.escape(obs)}</td>
              <td><span class="badge {vclass}">{_html.escape(verdict)}</span></td>
              <td class="hash"><code>{_html.escape((s.get('step_hash') or '')[:18])}…</code></td>
            </tr>""")
        signed_badge = ('<span class="badge ok">SIGNED</span>'
                        if prov.get("all_signed")
                        else '<span class="badge warn">UNSIGNED (no key in env — honest)</span>')
        cards.append(f"""
        <article class="tcard">
          <header>
            <h3>trajectory {_html.escape(prov.get('trajectory_id','')[:8])}…</h3>
            <span class="label">{_html.escape(prov.get('label','SAMPLE'))}</span>
            {signed_badge}
          </header>
          <p class="task">📋 {_html.escape(str(prov.get('task',''))[:160])}</p>
          <p class="meta">source: <b>{_html.escape(prov.get('source',''))}</b> ·
             steps: {prov.get('total_steps')} · corrections: {prov.get('corrections')} ·
             reasoning: {_html.escape(str(prov.get('reasoning_mode','')))} ·
             used_in: {_html.escape(json.dumps(prov.get('used_in',[])))}</p>
          <table class="steps">
            <thead><tr><th>#</th><th>pattern</th><th>role</th><th>action</th>
              <th>observation</th><th>verdict</th><th>step_hash</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </article>""")
    return "\n".join(cards)


def _page_html(ns: str = "a11oy") -> str:
    st = _stats()
    attr = st["attribution"]
    vc = st.get("verdict_counts", {})
    pc = st.get("pattern_counts", {})
    verify = st.get("verify", {})
    sample_jsonl = _CORPUS["jsonl"]
    chips = "".join(
        f'<span class="chip">{_html.escape(k)}: <b>{v}</b></span>'
        for k, v in {**vc, **{f"pat:{p}": n for p, n in pc.items()}}.items())
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>A11oy — Signed Corpus (SZL-Nemo)</title>
<style>
  :root {{ --bg:#0a0f1e; --panel:#111a2e; --ink:#e8eef7; --muted:#8aa0bd;
           --indigo:#4d8fcc; --terra:#c8643c; --gold:#d8a23c; --ok:#3fae7a;
           --warn:#c8893c; --bad:#cc5a5a; --exp:#9fb0e6; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
          background:radial-gradient(1200px 600px at 70% -10%, #16223c, var(--bg)); color:var(--ink); }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
  .plaque {{ font-family:ui-monospace,monospace; font-size:.72rem; letter-spacing:.12em;
             color:var(--muted); text-transform:uppercase; }}
  .plaque b {{ color:var(--gold); }}
  h1 {{ font-size:clamp(1.8rem,4vw,2.6rem); margin:.4rem 0 .2rem; }}
  h1 .accent {{ color:var(--terra); }}
  .sub {{ color:var(--muted); max-width:74ch; line-height:1.55; }}
  .honest {{ background:rgba(200,137,60,.10); border:1px solid rgba(200,137,60,.35);
             border-radius:10px; padding:.8rem 1rem; margin:1.1rem 0; color:#e7c98f;
             font-size:.85rem; line-height:1.5; }}
  .attr {{ background:rgba(77,143,204,.08); border:1px solid rgba(77,143,204,.3);
           border-radius:10px; padding:.7rem 1rem; margin:.8rem 0; font-size:.8rem; color:#bcd; }}
  .attr a {{ color:var(--indigo); }}
  .chips {{ display:flex; flex-wrap:wrap; gap:.45rem; margin:1rem 0; }}
  .chip {{ background:var(--panel); border:1px solid #21304d; border-radius:999px;
           padding:.3rem .7rem; font-size:.74rem; color:var(--muted); }}
  .chip b {{ color:var(--ink); }}
  .bignum {{ display:flex; gap:1.4rem; flex-wrap:wrap; margin:1.2rem 0; }}
  .bignum .n {{ font-size:2rem; font-weight:800; color:var(--gold); line-height:1; }}
  .bignum .l {{ font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }}
  .tcard {{ background:var(--panel); border:1px solid #21304d; border-radius:12px;
            padding:1.1rem 1.15rem; margin:1rem 0; box-shadow:0 18px 40px -28px #000; }}
  .tcard header {{ display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; }}
  .tcard h3 {{ margin:0; font-family:ui-monospace,monospace; color:var(--indigo); font-size:1rem; }}
  .label {{ font-size:.62rem; padding:.18rem .5rem; border-radius:999px; background:rgba(216,162,60,.16);
            color:var(--gold); border:1px solid rgba(216,162,60,.4); letter-spacing:.08em; }}
  .task {{ color:var(--ink); font-size:.86rem; margin:.6rem 0 .2rem; }}
  .meta {{ color:var(--muted); font-size:.76rem; margin:.1rem 0 .7rem; }}
  table.steps {{ width:100%; border-collapse:collapse; font-size:.74rem; }}
  table.steps th {{ text-align:left; color:var(--muted); font-weight:600; border-bottom:1px solid #21304d;
                    padding:.3rem .4rem; text-transform:uppercase; font-size:.64rem; letter-spacing:.06em; }}
  table.steps td {{ padding:.32rem .4rem; border-bottom:1px solid #16213a; vertical-align:top; }}
  td.num {{ color:var(--muted); }} td.act code {{ color:#bcd; word-break:break-word; }}
  td.obs {{ color:var(--muted); }} td.hash code {{ color:var(--gold); font-size:.68rem; }}
  .pat {{ color:var(--indigo); font-weight:600; }} .role {{ color:var(--muted); }}
  .badge {{ font-size:.6rem; padding:.16rem .45rem; border-radius:999px; letter-spacing:.05em; }}
  .badge.ok {{ background:rgba(63,174,122,.16); color:var(--ok); border:1px solid rgba(63,174,122,.4); }}
  .badge.warn {{ background:rgba(200,137,60,.16); color:var(--warn); border:1px solid rgba(200,137,60,.4); }}
  .badge.exp {{ background:rgba(120,140,210,.16); color:var(--exp); border:1px solid rgba(120,140,210,.45); }}
  .badge.bad {{ background:rgba(204,90,90,.16); color:var(--bad); border:1px solid rgba(204,90,90,.45); }}
  h2 {{ margin-top:2.2rem; font-size:1.25rem; }}
  textarea {{ width:100%; min-height:140px; background:#070c17; border:1px solid #1a2742; border-radius:8px;
              color:#bcd; font-family:ui-monospace,monospace; font-size:.72rem; padding:.7rem; }}
  button.verify {{ background:var(--terra); color:#0a0f1e; border:0; border-radius:8px; padding:.5rem .9rem;
                   font-weight:700; cursor:pointer; font-size:.85rem; margin-top:.6rem; }}
  button.verify:hover {{ filter:brightness(1.08); }}
  pre.out {{ background:#070c17; border:1px solid #1a2742; border-radius:8px; padding:.7rem; margin-top:.7rem;
             font-size:.74rem; color:#bcd; overflow:auto; max-height:300px; white-space:pre-wrap; }}
  a.back {{ color:var(--muted); text-decoration:none; font-size:.85rem; }}
  code.ep {{ color:var(--gold); }}
</style></head>
<body>
  <main class="wrap" id="main">
    <div class="plaque">SZL HOLDINGS / A11OY / SZL-NEMO / DOCTRINE <b>{DOCTRINE['version']} · LOCKED</b>
      / {DOCTRINE['counts']} / Λ = CONJECTURE 1 / SLSA L1 (L2/L3 ROADMAP)</div>
    <h1>The <span class="accent">signed corpus</span> is verifiable.</h1>
    <p class="sub">A cryptographically-signed, provenance-attested agent-trajectory corpus.
       Each JSONL line is one agent step — <code>action</code>, <code>observation</code>,
       <code>restraint_verdict</code>, <code>step_hash</code>, <code>signature</code> — emitted by
       instrumenting the SZL ReAct + Reflexion + Restraint + Auto-Review loop. Anyone can verify
       every signature below. <a class="back" href="/">← back to console</a></p>

    <div class="honest">⚖️ <b>Honest scope:</b> {_html.escape(st['honesty'])}</div>

    <div class="attr">📚 <b>Attribution (CC BY 4.0):</b> sample trajectories are a schema-faithful
       mapping of <a href="{_html.escape(attr['url'])}" target="_blank" rel="noopener">{_html.escape(attr['source_dataset'])}</a>
       © {_html.escape(attr['source_owner'])}, licensed {_html.escape(attr['license_full'])}.
       Source totals: {attr['subsets']['interactive_agent']:,} interactive_agent +
       {attr['subsets']['tool_calling']:,} tool_calling = {attr['total_source_samples']:,} samples.
       Attribution is required and does not imply endorsement.</div>

    <div class="bignum">
      <div><div class="n">{st['trajectory_count']}</div><div class="l">sample trajectories</div></div>
      <div><div class="n">{st['total_steps']}</div><div class="l">signed steps</div></div>
      <div><div class="n">{verify.get('hash_ok',0)}/{verify.get('total_steps',0)}</div><div class="l">hash-verified</div></div>
      <div><div class="n">{'YES' if st['signing_available'] else 'NO'}</div><div class="l">private key in env</div></div>
      <div><div class="n">{ingest.SOURCE_TOTAL:,}</div><div class="l">source samples (CC BY 4.0)</div></div>
    </div>
    <div class="chips">{chips}</div>

    <h2>Sample signed trajectories</h2>
    {_sample_cards()}

    <h2>Verify it yourself</h2>
    <p class="sub">Paste signed-trajectory JSONL (or use the loaded sample) and run the integrity +
       signature check. It calls <code class="ep">POST /api/{ns}/v1/nemo/verify</code> server-side,
       which recomputes each <code>step_hash</code> and verifies each DSSE envelope against the
       published <code>cosign.pub</code>. Honest: with no private key in this environment the receipts
       are UNSIGNED and the verifier says so — it never fabricates a pass.</p>
    <textarea id="jsonl"></textarea>
    <div>
      <button class="verify" id="run">Verify signatures &amp; hashes</button>
      <button class="verify" id="load" style="background:var(--indigo);">Load sample JSONL</button>
    </div>
    <pre class="out" id="out" hidden></pre>
  </main>
<script>
const NS = {json.dumps(ns)};
const SAMPLE = {json.dumps(sample_jsonl)};
document.getElementById('load').addEventListener('click', function() {{
  document.getElementById('jsonl').value = SAMPLE;
}});
document.getElementById('run').addEventListener('click', async function() {{
  const out = document.getElementById('out');
  const jsonl = document.getElementById('jsonl').value || SAMPLE;
  out.hidden = false; out.textContent = 'verifying …';
  try {{
    const r = await fetch('/api/' + NS + '/v1/nemo/verify', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ jsonl: jsonl }})
    }});
    const t = await r.text();
    try {{ out.textContent = '[' + r.status + '] ' + JSON.stringify(JSON.parse(t), null, 2); }}
    catch (e) {{ out.textContent = '[' + r.status + '] ' + t.slice(0, 1200); }}
  }} catch (e) {{ out.textContent = 'error: ' + e; }}
}});
</script>
</body></html>"""


# --------------------------------------------------------------------------- #
# Nav-injection middleware (idempotent; appends a floating link to every HTML
# surface so the tab is reachable from the console without editing the SPA).
# --------------------------------------------------------------------------- #
def _install_nav_injector(app: FastAPI) -> bool:
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import Response as _Resp
    except Exception:
        return False

    _MARKER = b"szl-nemo-corpus-nav"
    _TAG = (
        b'<a id="szl-nemo-corpus-nav" href="/signed-corpus" '
        b'style="position:fixed;right:14px;bottom:14px;z-index:99998;'
        b'background:#c8643c;color:#0a0f1e;font:600 12px ui-sans-serif,system-ui;'
        b'padding:8px 12px;border-radius:999px;text-decoration:none;'
        b'box-shadow:0 6px 18px -6px #000;" '
        b'title="DSSE-signed agent-trajectory corpus (SZL-Nemo)">'
        b'\xe2\x97\x88 Signed Corpus</a>'
    )

    class _NemoNavInjector(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # noqa: ANN001
            resp = await call_next(request)
            try:
                ct = (resp.headers.get("content-type") or "").lower()
                if "text/html" not in ct:
                    return resp
                p = request.url.path
                if (p.startswith("/vendor/") or p.startswith("/api/")
                        or p.startswith("/assets/") or p == "/signed-corpus"):
                    return resp
                body = b""
                async for chunk in resp.body_iterator:
                    body += chunk if isinstance(chunk, (bytes, bytearray)) \
                        else str(chunk).encode()
                if _MARKER in body:                       # idempotent
                    new_body = body
                elif b"</body>" in body:
                    new_body = body.replace(b"</body>", _TAG + b"</body>", 1)
                elif b"</html>" in body:
                    new_body = body.replace(b"</html>", _TAG + b"</html>", 1)
                else:
                    new_body = body + _TAG
                headers = dict(resp.headers)
                headers.pop("content-length", None)
                return _Resp(content=new_body, status_code=resp.status_code,
                             headers=headers, media_type="text/html")
            except Exception:
                return resp

    app.add_middleware(_NemoNavInjector)
    return True


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount the Signed-Corpus tab + JSON/verify endpoints + nav injector.

    ADDITIVE — explicit routes registered before the SPA catch-all; the nav
    injector is idempotent and never rewrites page content. try/except in
    serve.py guarantees a missing dep can never take down the Space.
    """

    @app.get("/signed-corpus", include_in_schema=False)
    async def signed_corpus_page() -> HTMLResponse:  # noqa: ANN202
        return HTMLResponse(_page_html(ns))

    # Alias under the namespace, mirroring the other genius tabs.
    @app.get(f"/{ns}/signed-corpus", include_in_schema=False)
    async def signed_corpus_page_ns() -> HTMLResponse:  # noqa: ANN202
        return HTMLResponse(_page_html(ns))

    @app.get(f"/api/{ns}/v1/nemo/stats", include_in_schema=False)
    async def nemo_stats() -> JSONResponse:  # noqa: ANN202
        return JSONResponse(_stats())

    @app.get(f"/api/{ns}/v1/nemo/sample", include_in_schema=False)
    async def nemo_sample() -> PlainTextResponse:  # noqa: ANN202
        return PlainTextResponse(_CORPUS["jsonl"], media_type="application/x-ndjson")

    @app.post(f"/api/{ns}/v1/nemo/verify", include_in_schema=False)
    async def nemo_verify(request: Request) -> JSONResponse:  # noqa: ANN202
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        jsonl = ""
        if isinstance(payload, dict):
            jsonl = payload.get("jsonl") or payload.get("text") or ""
        if not isinstance(jsonl, str) or not jsonl.strip():
            jsonl = _CORPUS["jsonl"]  # default: verify the shipped sample
        result = sts.verify_jsonl(jsonl)
        result["honesty"] = (
            "Integrity check recomputes each step_hash and verifies each DSSE "
            "envelope against the published cosign.pub. 'signed' counts receipts "
            "carrying a real signature; with no private key in this environment "
            "receipts are honestly UNSIGNED (signed=0) — never fabricated."
        )
        result["doctrine"] = DOCTRINE
        return JSONResponse(result)

    nav_ok = _install_nav_injector(app)
    return (f"nemotron signed-corpus mounted: GET /signed-corpus + "
            f"/api/{ns}/v1/nemo/{{stats,sample,verify}} ; nav-injector={nav_ok}")


if __name__ == "__main__":
    # Pure self-check: render page + verify endpoints without a live server.
    st = _stats()
    page = _page_html("a11oy")
    assert "signed corpus" in page.lower()
    assert "CC BY 4.0" in page or "cc-by-4.0" in page.lower()
    assert "ROADMAP" in page
    assert st["trajectory_count"] >= 1
    print(json.dumps({
        "page_bytes": len(page),
        "trajectory_count": st["trajectory_count"],
        "total_steps": st["total_steps"],
        "verify": st["verify"],
        "verdict_counts": st["verdict_counts"],
        "pattern_counts": st["pattern_counts"],
        "signing_available": st["signing_available"],
        "attribution_license": st["attribution"]["license"],
    }, indent=2))
