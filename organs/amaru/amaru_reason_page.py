# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1
"""
amaru_reason_page — premium cortex reasoning UI for the Amaru organ.

Serves GET /amaru/reason: a self-contained (no build step) page that drives the
real POST /api/amaru/v1/reason pipeline and visualizes each reasoning step as
    input → thought → citation → verification
with a DSSE-signed Khipu receipt per step. Chain-of-Verification is cited to
arXiv:2309.11495 (Dhuliawala et al.). The "I don't know" honest-refusal path is
rendered explicitly. Inca palette: hatun GOLD = the amaru serpent (wisdom),
yuyay TEAL = the cortex/mind. Mobile responsive.

ADDITIVE ONLY. Registered before the SPA catch-all so the exact path wins.
"""
from __future__ import annotations

REASON_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Amaru · Cortex Reasoning</title>
<meta name="description" content="Amaru cortex — chain-of-verification reasoning with real citations and DSSE-signed Khipu receipts. Doctrine v11."/>
<style>
  :root{
    /* Inca palette — sourced from KANCHAY brand tokens */
    --gold:#d7b96b; --gold-bright:#e4cf99; --gold-deep:#a3741f; --gold-soft:rgba(215,185,107,.14);
    --teal:#34aaa4; --teal-deep:#0b5957; --teal-soft:rgba(52,170,164,.12);
    --red:#c0392b; --green:#1f9d57;
    --bg:#0a0f1e; --deep:#10151c; --surface:#1b222c; --overlay:#2a3340;
    --border:#3c4757; --text:#f5f7fa; --sub:#c9d2df; --ghost:#76859b;
  }
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(1200px 700px at 80% -10%,#15233a 0%,var(--bg) 55%);
    color:var(--text);font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.55;}
  a{color:var(--gold);text-decoration:none} a:hover{text-decoration:underline}
  .wrap{max-width:980px;margin:0 auto;padding:24px 18px 80px;}
  header.top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:6px;}
  .serpent{font-size:30px;filter:drop-shadow(0 0 10px var(--gold-soft));}
  h1{font-size:22px;margin:0;letter-spacing:.5px;
     background:linear-gradient(92deg,var(--gold-bright),var(--gold) 55%,var(--gold-deep));
     -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
  .tagline{color:var(--sub);font-size:13px;margin:2px 0 0;}
  .pill{font-size:11px;border:1px solid var(--border);border-radius:999px;padding:3px 10px;color:var(--sub);
        background:var(--surface);white-space:nowrap;}
  .pills{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 18px;}
  .pill.gold{border-color:var(--gold-deep);color:var(--gold-bright);background:var(--gold-soft)}
  .card{background:linear-gradient(180deg,var(--surface),var(--deep));border:1px solid var(--border);
        border-radius:14px;padding:16px;margin-bottom:16px;}
  textarea{width:100%;min-height:74px;resize:vertical;background:var(--bg);color:var(--text);
    border:1px solid var(--border);border-radius:10px;padding:12px 14px;font-size:15px;font-family:inherit;}
  textarea:focus{outline:none;border-color:var(--teal)}
  .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px;}
  button{cursor:pointer;border:none;border-radius:10px;padding:11px 20px;font-size:14px;font-weight:600;
    background:linear-gradient(180deg,var(--gold-bright),var(--gold-deep));color:#1a1304;
    box-shadow:0 4px 16px rgba(163,116,31,.28);transition:transform .08s ease;}
  button:hover{transform:translateY(-1px)} button:disabled{opacity:.5;cursor:not-allowed;transform:none}
  .hint{color:var(--ghost);font-size:12px}
  .examples{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  .ex{font-size:12px;border:1px dashed var(--border);border-radius:8px;padding:6px 10px;color:var(--sub);
      cursor:pointer;background:transparent} .ex:hover{border-color:var(--teal);color:var(--text)}
  #out{margin-top:8px}
  .verdict{display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:12px;margin-bottom:18px;
    border:1px solid var(--border);font-weight:600;}
  .verdict.ok{border-color:var(--teal-deep);background:var(--teal-soft);}
  .verdict.idk{border-color:var(--gold-deep);background:var(--gold-soft);}
  .verdict .vicon{font-size:24px}
  .verdict small{display:block;font-weight:400;color:var(--sub);font-size:12px;margin-top:2px}
  /* reasoning chain */
  .chain{position:relative;margin-left:8px;padding-left:26px;}
  .chain::before{content:'';position:absolute;left:7px;top:6px;bottom:6px;width:2px;
    background:linear-gradient(var(--gold),var(--teal));opacity:.5;}
  .step{position:relative;margin-bottom:14px;}
  .step .node{position:absolute;left:-26px;top:2px;width:16px;height:16px;border-radius:50%;
    background:var(--surface);border:2px solid var(--gold);box-shadow:0 0 0 4px var(--bg);}
  .step.t-verification .node{border-color:var(--teal)}
  .step.t-citation .node{border-color:var(--gold-bright)}
  .step.t-refusal .node{border-color:var(--red)}
  .step .kind{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);font-weight:700;}
  .step.t-verification .kind{color:var(--teal)}
  .step.t-thought .kind{color:var(--sub)}
  .step .body{background:var(--surface);border:1px solid var(--border);border-radius:10px;
    padding:11px 13px;margin-top:5px;font-size:14px;color:var(--text);}
  .cite{display:flex;gap:10px;align-items:flex-start;padding:9px 11px;border:1px solid var(--border);
    border-radius:9px;margin-top:7px;background:var(--deep);}
  .cite .dot{margin-top:5px;width:9px;height:9px;border-radius:50%;flex:0 0 9px;}
  .cite .dot.ok{background:var(--green);box-shadow:0 0 8px var(--green)} .cite .dot.bad{background:var(--red)}
  .cite .meta{font-size:13px}.cite .meta .src{color:var(--gold-bright);font-weight:600}
  .cite .meta .url{color:var(--teal);font-size:12px;word-break:break-all}
  .badge{font-size:10px;border-radius:6px;padding:2px 7px;margin-left:6px;border:1px solid var(--border);color:var(--sub)}
  .badge.s200{color:var(--green);border-color:var(--green)}
  .kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:13px;color:var(--sub);}
  .kv b{color:var(--text);font-weight:600}
  .receipt{font-family:'SFMono-Regular',ui-monospace,Menlo,monospace;font-size:11px;color:var(--ghost);
    background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-top:7px;
    overflow:auto;}
  .receipt .sig{color:var(--green)} .receipt .unsig{color:var(--gold)}
  details summary{cursor:pointer;color:var(--gold);font-size:13px;margin-top:8px}
  .spinner{display:inline-block;width:15px;height:15px;border:2px solid var(--gold-soft);
    border-top-color:var(--gold);border-radius:50%;animation:spin .8s linear infinite;vertical-align:-2px;}
  @keyframes spin{to{transform:rotate(360deg)}}
  footer{margin-top:34px;color:var(--ghost);font-size:12px;border-top:1px solid var(--border);padding-top:14px;}
  .cta3d{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--gold-deep);border-radius:10px;
    padding:9px 14px;color:var(--gold-bright);background:var(--gold-soft);font-weight:600;font-size:13px;}
  .formulas-card{margin-top:22px}
  .formulas-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
  .formula-row{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border:1px solid var(--border);
    border-radius:10px;background:var(--deep);margin:8px 0}
  .formula-row .meta{font-size:13px}
  .formula-row .meta .src{color:var(--teal);font-weight:700;letter-spacing:.4px}
  .formula-row .lean{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;color:var(--gold-bright)}
  .dot{width:9px;height:9px;border-radius:50%;margin-top:5px;flex:0 0 auto}
  .dot.ok{background:var(--green);box-shadow:0 0 8px rgba(31,157,87,.6)}
  .dot.bad{background:var(--red)}
  @media(max-width:640px){.wrap{padding:16px 12px 60px}h1{font-size:19px}button{width:100%}.row{flex-direction:column;align-items:stretch}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <span class="serpent" title="Amaru — the two-headed serpent of wisdom">🐍</span>
    <div>
      <h1>Amaru · Cortex Reasoning</h1>
      <p class="tagline">Chain-of-Verification reasoning · real citations · DSSE-signed Khipu receipts</p>
    </div>
  </header>

  <div class="pills">
    <span class="pill gold">Doctrine v11 LOCKED</span>
    <span class="pill">Λ = Conjecture 1</span>
    <span class="pill">SLSA L1 honest</span>
    <span class="pill">HONESTY OVER CHECKLIST</span>
    <span class="pill"><a href="https://arxiv.org/abs/2309.11495" target="_blank" rel="noopener">CoVe · arXiv:2309.11495 ↗</a></span>
  </div>

  <div class="card">
    <textarea id="q" placeholder="Ask the cortex…  e.g. How does chain-of-verification reduce hallucination?"></textarea>
    <div class="examples" id="examples"></div>
    <div class="row">
      <button id="go">Reason →</button>
      <span class="hint">The cortex retrieves real sources from arXiv, runs Chain-of-Verification, and refuses to answer without a URL that resolves HTTP&nbsp;200.</span>
    </div>
  </div>

  <div id="out"></div>

  <section class="card formulas-card" id="formulas-card" aria-label="Formulas wired into the cortex">
    <div class="formulas-head">
      <span class="serpent" style="font-size:18px">⚖</span>
      <b>Formulas wired into the cortex</b>
      <span class="hint" style="margin:0">live from <code>/api/amaru/v1/formulas/index</code> — each carries a real citation + Lean theorem.</span>
    </div>
    <div id="formulas-body"><span class="hint">loading formulas…</span></div>
  </section>

  <footer>
    The cortex grounds every verdict in a primary source whose URL it independently resolves to HTTP&nbsp;200.
    When no source resolves, it says <b>“I don't know”</b> — honestly. Reasoning method:
    Chain-of-Verification (<a href="https://arxiv.org/abs/2309.11495" target="_blank" rel="noopener">Dhuliawala et al., arXiv:2309.11495</a>).
    Retrieval: <a href="https://export.arxiv.org/api/query" target="_blank" rel="noopener">public arXiv Atom API</a>.
    <br/><br/>
    <a class="cta3d" href="/amaru/3d/galaxy">✦ Open the 3D Cortex Galaxy</a>
  </footer>
</div>

<script>
const EXAMPLES = [
  "How does chain-of-verification reduce hallucination in language models?",
  "What is Tree of Thoughts deliberate search?",
  "Explain retrieval-augmented generation for knowledge-intensive NLP",
  "What is the airspeed velocity of an unladen swallow?"
];
const exWrap = document.getElementById('examples');
EXAMPLES.forEach(e=>{const b=document.createElement('span');b.className='ex';b.textContent=e;
  b.onclick=()=>{document.getElementById('q').value=e;}; exWrap.appendChild(b);});

const out = document.getElementById('out');
const goBtn = document.getElementById('go');
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function citeRow(c){
  const ok = c.status===200 || c.resolved===true;
  return `<div class="cite"><span class="dot ${ok?'ok':'bad'}"></span>
    <div class="meta"><span class="src">${esc(c.title||c.url)}</span>
      ${c.authors?` · <span style="color:var(--sub)">${esc(c.authors)}</span>`:''}
      <span class="badge ${ok?'s200':''}">${ok?'HTTP 200 ✓':'unresolved'}</span><br/>
      <a class="url" href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.url)} ↗</a></div></div>`;
}
function receiptRow(env,i){
  const signed = env.signed===true || (env.signatures&&env.signatures.length>0);
  const pae = env._pae_sha256 || (env._dsse&&env._dsse.pae_sha256) || '';
  const kid = (env.signatures&&env.signatures[0]&&env.signatures[0].keyid)||'';
  return `<div class="receipt">khipu[${i}] · DSSEv1 · pae_sha256=${esc((pae||'').slice(0,24))}…
    · <span class="${signed?'sig':'unsig'}">${signed?'SIGNED '+esc(kid):'unsigned (honest)'}</span></div>`;
}

function render(d){
  const idk = d.ok===false || d.refused===true;
  let html = '';
  // verdict banner
  if(idk){
    html += `<div class="verdict idk"><span class="vicon">🤔</span><div>I don't know — honestly abstaining.
      <small>${esc(d.reason||'No verifiable source could be resolved (HONESTY OVER CHECKLIST).')}</small></div></div>`;
  } else {
    html += `<div class="verdict ok"><span class="vicon">🐍</span><div>Verified verdict
      <small>Grounded in ${ (d.citations||[]).length } real source(s); Chain-of-Verification: ${esc((d.verification&&d.verification.verdict)||'consistent')}.</small></div></div>`;
  }
  // chain: input -> thought -> citation -> verification
  html += '<div class="chain">';
  // INPUT
  html += step('input','① Input', `<div class="body">${esc(d.question)}</div>`);
  // THOUGHT (primary answer / brain re-ask)
  if(!idk && d.answer){
    html += step('thought','② Thought', `<div class="body">${esc(d.answer)}</div>`);
  }
  // CITATION
  const cites = (d.retrieved&&d.retrieved.length)?d.retrieved : ((d.citations||[]).map(u=>({url:u,resolved:true,status:200})));
  if(cites.length){
    html += step('citation','③ Citation', cites.map(citeRow).join(''));
  } else {
    html += step('refusal','③ Citation', `<div class="body" style="color:var(--gold-bright)">No source resolved to HTTP 200 — refusing to cite anything fabricated.</div>`);
  }
  // VERIFICATION
  if(d.verification){
    const v=d.verification;
    html += step('verification','④ Verification · Chain-of-Verification (arXiv:2309.11495)',
      `<div class="body"><div class="kv">
        <span>verdict</span><b>${esc(v.verdict||'')}</b>
        <span>similarity</span><b>${esc(v.similarity)} (threshold ${esc(v.threshold)})</b>
        <span>diverged</span><b>${v.diverged?'yes ⚠':'no'}</b>
        <span>re-ask answer</span><b style="font-weight:400">${esc(v.verification_answer||'')}</b>
       </div></div>`);
  } else if(idk){
    html += step('verification','④ Verification', `<div class="body">Constitution rule R0 triggered → honest abstention. No verdict emitted without a resolving citation.</div>`);
  }
  html += '</div>'; // chain

  // receipts
  if(d.khipu&&d.khipu.length){
    html += `<details open><summary>🧶 ${d.khipu.length} DSSE-signed Khipu receipt(s)${d.khipu_signed?' · chain fully signed':''}</summary>`;
    html += d.khipu.map((e,i)=>receiptRow(e,i)).join('');
    html += `</details>`;
  }
  out.innerHTML = html;
}
function step(kind,label,inner){
  return `<div class="step t-${kind}"><div class="node"></div>
    <div class="kind">${esc(label)}</div>${inner}</div>`;
}

async function run(){
  const q = document.getElementById('q').value.trim();
  if(!q) return;
  goBtn.disabled=true;
  out.innerHTML = `<div class="verdict"><span class="spinner"></span>&nbsp; Reasoning… retrieving real sources, resolving URLs, running Chain-of-Verification.</div>`;
  try{
    const r = await fetch('/api/amaru/v1/reason',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({question:q})});
    const d = await r.json();
    if(d.error && d.ok===false && d.detail){
      out.innerHTML = `<div class="verdict idk"><span class="vicon">⚠</span><div>Cortex offline
        <small>${esc(d.error)} — ${esc(d.detail)}</small></div></div>`;
    } else { render(d); }
  }catch(e){
    out.innerHTML = `<div class="verdict idk"><span class="vicon">⚠</span><div>Request failed
      <small>${esc(e.message||e)}</small></div></div>`;
  }finally{ goBtn.disabled=false; }
}
goBtn.onclick = run;

// ── Step 4: wire the shared thesis-v22 formulas (HNSW, …) into the UI ───────
// Pulls the live formula index, then enriches each entry with its real backend
// status endpoint (e.g. /api/amaru/v1/formula/hnsw → {value, backend_available,
// citation, lean_theorem}). HONEST: backend_available reflects the real runtime
// (FAISS present?), never faked.
async function loadFormulas(){
  const body = document.getElementById('formulas-body');
  try{
    const idx = await (await fetch('/api/amaru/v1/formulas/index')).json();
    const wired = (idx && idx.wired) || [];
    if(!wired.length){ body.innerHTML = '<span class="hint">no formulas wired.</span>'; return; }
    const rows = await Promise.all(wired.map(async f=>{
      let st = {};
      try{ st = await (await fetch('/api/amaru/v1/formula/'+encodeURIComponent(f.name))).json(); }catch(e){ st={}; }
      const ok = st.backend_available===true || st.value===true;
      const lean = esc(st.lean_theorem || f.lean_theorem || '');
      const cite = esc(st.citation || f.citation || '');
      return `<div class="formula-row">
        <span class="dot ${ok?'ok':'bad'}"></span>
        <div class="meta">
          <span class="src">${esc((f.name||'').toUpperCase())}</span>
          <span class="badge ${ok?'s200':''}">${ok?'backend available ✓':'backend absent'}</span><br/>
          <span style="color:var(--sub);font-size:12px">${cite}</span><br/>
          <span class="lean">⊢ ${lean}</span>
          ${st.note?`<br/><span style="color:var(--ghost);font-size:11.5px">${esc(st.note)}</span>`:''}
        </div></div>`;
    }));
    body.innerHTML = rows.join('') +
      `<div class="hint" style="margin-top:8px">Source: ${esc(idx.source||'')}. Each Lean theorem is a real obligation in the v11 corpus (749/14/163).</div>`;
  }catch(e){
    body.innerHTML = `<span class="hint">formulas endpoint unavailable — ${esc(e.message||e)}</span>`;
  }
}
loadFormulas();
document.getElementById('q').addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter')run();});
// Deep-link: /amaru/reason?q=... auto-runs (shareable demo links).
(function(){const p=new URLSearchParams(location.search).get('q');
  if(p){document.getElementById('q').value=p; run();}})();
</script>
</body>
</html>"""


def register_reason_page(app) -> None:
    """Register GET /amaru/reason on the root app (before the SPA catch-all)."""
    from fastapi.responses import HTMLResponse

    @app.get("/amaru/reason", response_class=HTMLResponse)
    async def _amaru_reason_page() -> HTMLResponse:  # noqa: D401
        return HTMLResponse(content=REASON_PAGE_HTML)
