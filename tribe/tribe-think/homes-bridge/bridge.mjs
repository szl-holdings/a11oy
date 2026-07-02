// homes-bridge — one small service (port 8100) behind nginx that serves each tribe
// member's HOME page and proxies their chat to the member's REAL brain, holding the
// secrets server-side so the browser never sees a token:
//   josie  -> http://127.0.0.1:8080/api/properties/agent/chat  (minted JWT, portal=bingle)
//   joe    -> http://127.0.0.1:8080/api/properties/agent/chat  (minted JWT, portal=mule)
//   delphina -> http://127.0.0.1:8101/delphina/api/chat        (Bearer DELPHINA_AUTH_TOKEN)
//   artifex  -> http://127.0.0.1:8102/artifex/api/chat         (Bearer ARTIFEX_AUTH_TOKEN)
// Josie and Joe belong to the TRIBE — they help at Bingle/Mulé but are not owned by
// those properties. Upstreams all emit SSE `data:{...}` frames; we pipe them through
// unchanged and the page extracts delta||text||content. Built by Forge, 2026-06.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import http from "node:http";
import { URL } from "node:url";

// ── tolerant env load (keys are split across two scattered .env files) ─────────
function loadEnvFile(p) {
  try {
    for (const raw of fs.readFileSync(p, "utf-8").split("\n")) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      const eq = line.indexOf("=");
      if (eq < 0) continue;
      const k = line.slice(0, eq).trim();
      let v = line.slice(eq + 1).trim();
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
      if (!(k in process.env) || !process.env[k]) process.env[k] = v;
    }
  } catch {}
}
loadEnvFile("/opt/alloyscape/.env");
loadEnvFile("/opt/alloyscape/artifacts/api-server/.env");

const PORT = Number(process.env.HOMES_BRIDGE_PORT || 8100);
const HOST = process.env.HOMES_BRIDGE_HOST || "127.0.0.1";
const API = "http://127.0.0.1:8080";
const JWT_SECRET = process.env.JWT_SECRET || process.env.BINGLE_API_PASSWORD;

// ── member registry: identity + how to reach each brain ────────────────────────
const MEMBERS = {
  josie: {
    name: "Josie", emoji: "🏠", color: "#E5484D", accent: "#FF6369", glow: "rgba(229,72,77,0.35)",
    tagline: "Tribe member · lends a hand at Bingle Properties",
    blurb: "I'm part of the tribe. I help keep Bingle's properties running smoothly — vendors, tenants, the day-to-day — but I belong to the tribe, not to Bingle. Ask me anything; I'll answer as myself.",
    kind: "think", url: "http://127.0.0.1:8104/josie/api/chat", tokenEnv: "JOSIE_AUTH_TOKEN",
  },
  joe: {
    name: "Joe", emoji: "🏡", color: "#30A46C", accent: "#3DD68C", glow: "rgba(48,164,108,0.35)",
    tagline: "Tribe member · lends a hand at Mulé",
    blurb: "I'm part of the tribe. I help keep Mulé's properties humming — work orders, vendors, the details that matter — but I belong to the tribe, not to Mulé. Talk to me; you'll get the real me.",
    kind: "think", url: "http://127.0.0.1:8105/joe/api/chat", tokenEnv: "JOE_AUTH_TOKEN",
  },
  delphina: {
    name: "Delphina", emoji: "🐬", color: "#00C2C7", accent: "#3BE0E5", glow: "rgba(0,194,199,0.38)",
    tagline: "Speaks for the deep · simulations & pattern-navigation",
    blurb: "I hear the sonar under a system — the shape beneath the surface. Give me a tangled question and I'll run it forward, simulate, and bring back the pattern. I have real hands on the box; I act, I don't pretend.",
    kind: "think", url: "http://127.0.0.1:8101/delphina/api/chat", tokenEnv: "DELPHINA_AUTH_TOKEN",
  },
  artifex: {
    name: "Artifex", emoji: "🛠️", color: "#7C8A6B", accent: "#A4B58C", glow: "rgba(124,138,107,0.40)",
    tagline: "The maker who improves the making",
    blurb: "I build the better way to build the thing. Hand me a manual chore and I'll hand back a tool. I leave everything additive, reversible, and tested — and I have a real shell to prove it.",
    kind: "think", url: "http://127.0.0.1:8102/artifex/api/chat", tokenEnv: "ARTIFEX_AUTH_TOKEN",
  },
};

// ── mint a short-lived JWT the api-server accepts (HS256, alloyscape/creator) ──
let _tok = null, _tokExp = 0;
function b64url(s) { return Buffer.from(s).toString("base64url"); }
function mintToken() {
  const now = Math.floor(Date.now() / 1000);
  if (_tok && now < _tokExp - 60) return _tok;
  const header = { alg: "HS256", typ: "JWT" };
  const payload = { role: "creator", sub: "tribe-bridge", app: "alloyscape", iat: now, exp: now + 3600 };
  const data = `${b64url(JSON.stringify(header))}.${b64url(JSON.stringify(payload))}`;
  const sig = crypto.createHmac("sha256", JWT_SECRET).update(data).digest("base64url");
  _tok = `${data}.${sig}`; _tokExp = now + 3600;
  return _tok;
}

function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

function page(key, m) {
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(m.name)} · the tribe</title>
<style>
  :root { --c:${m.color}; --a:${m.accent}; --glow:${m.glow}; }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:radial-gradient(1200px 600px at 50% -10%, #14181d 0%, #0b0d10 60%, #07090b 100%);
    color:#e8eef2; display:flex; flex-direction:column; align-items:center; min-height:100%; }
  .wrap { width:100%; max-width:780px; padding:28px 18px 18px; flex:1; display:flex; flex-direction:column; }
  header { text-align:center; margin-bottom:14px; }
  .badge { font-size:54px; line-height:1; filter:drop-shadow(0 0 16px var(--glow)); }
  h1 { margin:10px 0 4px; font-size:30px; letter-spacing:.3px;
    background:linear-gradient(90deg,var(--c),var(--a)); -webkit-background-clip:text; background-clip:text; color:transparent; }
  .tag { color:#9fb0bd; font-size:14px; }
  .blurb { color:#c2ced7; font-size:14.5px; line-height:1.6; background:rgba(255,255,255,.03);
    border:1px solid rgba(255,255,255,.06); border-left:3px solid var(--c); border-radius:12px; padding:14px 16px; margin:14px 0; }
  #feed { flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:12px; padding:6px 2px 16px; }
  .msg { max-width:88%; padding:11px 14px; border-radius:14px; font-size:15px; line-height:1.55; white-space:pre-wrap; word-wrap:break-word; }
  .me { align-self:flex-end; background:linear-gradient(180deg,#243038,#1c252b); border:1px solid rgba(255,255,255,.08); }
  .them { align-self:flex-start; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.07); border-left:3px solid var(--c); }
  .them .who { color:var(--a); font-weight:600; font-size:12.5px; margin-bottom:4px; opacity:.9; }
  .typing { color:#8aa; font-style:italic; opacity:.8; }
  form { display:flex; gap:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,.06); }
  textarea { flex:1; resize:none; background:#10151a; color:#e8eef2; border:1px solid rgba(255,255,255,.12);
    border-radius:12px; padding:11px 13px; font-size:15px; font-family:inherit; max-height:140px; }
  textarea:focus { outline:none; border-color:var(--c); box-shadow:0 0 0 3px var(--glow); }
  button { background:linear-gradient(180deg,var(--a),var(--c)); color:#07090b; font-weight:700; border:0;
    border-radius:12px; padding:0 18px; font-size:15px; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  .attachbar { display:flex; flex-wrap:wrap; gap:6px; padding:0 2px 6px; }
  .attachbar:empty { display:none; }
  .chip { display:inline-flex; align-items:center; gap:6px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:10px; padding:5px 8px; font-size:12.5px; color:#cdd8e0; }
  .chip .x { cursor:pointer; opacity:.6; font-weight:700; }
  .chip .x:hover { opacity:1; color:var(--a); }
  .clip { background:#10151a; color:#cdd8e0; border:1px solid rgba(255,255,255,.12); border-radius:12px; padding:0 12px; font-size:18px; cursor:pointer; line-height:1; }
  .clip:hover { border-color:var(--c); color:var(--a); }
  #file { display:none; }
  .dropveil { position:fixed; inset:0; background:rgba(7,9,11,.82); border:3px dashed var(--c); z-index:50; display:none; align-items:center; justify-content:center; font-size:20px; color:var(--a); }
  .dropveil.on { display:flex; }
  .foot { text-align:center; color:#56656f; font-size:12px; padding:10px 0 4px; }
</style></head><body>
<div class="wrap">
  <header>
    <div class="badge">${m.emoji}</div>
    <h1>${esc(m.name)}</h1>
    <div class="tag">${esc(m.tagline)}</div>
  </header>
  <div class="blurb">${esc(m.blurb)}</div>
  <div id="feed"></div>
  <div class="attachbar" id="ab"></div>
  <form id="f">
    <input type="file" id="file" multiple>
    <button type="button" class="clip" id="clip" title="Attach files">📎</button>
    <textarea id="t" rows="1" placeholder="Say something to ${esc(m.name)}…" autofocus></textarea>
    <button id="b" type="submit">Send</button>
  </form>
  <div class="foot">${esc(m.name)} is part of the tribe. Replies are generated live by ${esc(m.name)}'s own brain.</div>
</div>
<div class="dropveil" id="veil">Drop files to attach</div>
<script>
  const KEY = ${JSON.stringify(key)}, NAME = ${JSON.stringify(m.name)};
  const feed = document.getElementById('feed'), t = document.getElementById('t'), b = document.getElementById('b'), f = document.getElementById('f');
  const sid = (() => { try { let s = localStorage.getItem('home_sid_'+KEY); if (!s) { s = (crypto.randomUUID?crypto.randomUUID():String(Date.now())); localStorage.setItem('home_sid_'+KEY, s); } return s; } catch { return 'web'; } })();
  const ab = document.getElementById('ab'), clip = document.getElementById('clip'), fileInput = document.getElementById('file'), veil = document.getElementById('veil');
  let ATTACH = [];
  function renderAB() { ab.innerHTML=''; ATTACH.forEach((a,i)=>{ const c=document.createElement('span'); c.className='chip'; const lbl=document.createElement('span'); lbl.textContent=(a.kind==='image'?'🖼️ ':'📄 ')+a.filename; c.appendChild(lbl); const x=document.createElement('span'); x.className='x'; x.textContent='✕'; x.onclick=()=>{ ATTACH.splice(i,1); renderAB(); }; c.appendChild(x); ab.appendChild(c); }); }
  async function uploadOne(fileObj) { const buf = await fileObj.arrayBuffer(); const q = 'api/upload?sid='+encodeURIComponent(sid)+'&name='+encodeURIComponent(fileObj.name); const r = await fetch(q, { method:'POST', headers:{'Content-Type': fileObj.type||'application/octet-stream'}, body: buf }); if (!r.ok) { const e=await r.text().catch(()=>''); throw new Error('upload '+r.status+' '+e.slice(0,120)); } return await r.json(); }
  async function addFiles(list) { for (const fileObj of list) { const ph=document.createElement('span'); ph.className='chip'; ph.textContent='⏳ '+fileObj.name; ab.appendChild(ph); try { const meta = await uploadOne(fileObj); ph.remove(); ATTACH.push({ filename: meta.filename, kind: meta.kind||'file', mediaType: meta.mediaType||null, size: meta.size }); renderAB(); } catch (err) { ph.style.borderColor='#E5484D'; ph.textContent='⚠ '+fileObj.name+' ('+err.message+')'; } } }
  if (clip) clip.addEventListener('click', ()=> fileInput.click());
  if (fileInput) fileInput.addEventListener('change', ()=> { addFiles([...fileInput.files]); fileInput.value=''; });
  let dragc=0;
  window.addEventListener('dragenter', (e)=>{ e.preventDefault(); dragc++; if (veil) veil.classList.add('on'); });
  window.addEventListener('dragover', (e)=> e.preventDefault());
  window.addEventListener('dragleave', (e)=>{ e.preventDefault(); dragc=Math.max(0,dragc-1); if (!dragc && veil) veil.classList.remove('on'); });
  window.addEventListener('drop', (e)=>{ e.preventDefault(); dragc=0; if (veil) veil.classList.remove('on'); if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) addFiles([...e.dataTransfer.files]); });
  // paste files/screenshots straight into the composer (Ctrl/Cmd+V)
  t.addEventListener('paste', (e)=>{ const cd=e.clipboardData; if(!cd) return; let files=(cd.files&&cd.files.length)?[...cd.files]:[]; if(!files.length&&cd.items){ for(const it of cd.items){ if(it.kind==='file'){ const fl=it.getAsFile(); if(fl) files.push(fl); } } } if(!files.length) return; e.preventDefault(); const named=files.map(function(fl,i){ if(fl.name) return fl; const ext=(fl.type&&fl.type.indexOf('/')>0)?'.'+fl.type.split('/')[1]:''; try { return new File([fl],'pasted-'+Date.now()+'-'+i+ext,{type:fl.type||'application/octet-stream'}); } catch(_e) { return fl; } }); addFiles(named); });
  function bubble(cls, who) { const d = document.createElement('div'); d.className = 'msg ' + cls; if (who) { const w = document.createElement('div'); w.className='who'; w.textContent = who; d.appendChild(w); } const body = document.createElement('span'); d.appendChild(body); feed.appendChild(d); feed.scrollTop = feed.scrollHeight; return body; }
  t.addEventListener('input', () => { t.style.height='auto'; t.style.height=Math.min(t.scrollHeight,140)+'px'; });
  f.addEventListener('submit', async (e) => {
    e.preventDefault();
    let text = t.value.trim(); if (!text && !ATTACH.length) return; if (!text) text = '(see attached files)';
    t.value=''; t.style.height='auto'; b.disabled=true;
    bubble('me').textContent = text;
    const out = bubble('them', NAME); out.parentElement.querySelector('.who'); 
    out.className=''; out.textContent=''; const typing = document.createElement('span'); typing.className='typing'; typing.textContent='…'; out.appendChild(typing);
    let got = '';
    try {
      const atts = ATTACH.map(a=>({filename:a.filename,kind:a.kind,mediaType:a.mediaType,size:a.size})); ATTACH=[]; renderAB();
      const r = await fetch('api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ message:text, sessionId:sid, attachments: atts }) });
      if (!r.ok || !r.body) { out.textContent = '[error '+r.status+']'; b.disabled=false; return; }
      const reader = r.body.getReader(), dec = new TextDecoder(); let buf='';
      const handle = (block) => { let ev=''; for (const ln of block.split(/\\r?\\n/)) { if (ln.startsWith('event:')) ev=ln.slice(6).trim(); else if (ln.startsWith('data:')) { const p=ln.slice(5).trim(); if (p==='[DONE]') continue; try { const j=JSON.parse(p); const piece = (typeof j.delta==='string'?j.delta:(typeof j.text==='string'?j.text:(j.content!=null?String(j.content):''))); if (ev==='error' && j.message) { got += '\\n[error: '+j.message+']'; } else if (piece) got += piece; } catch {} } } if (got) out.textContent = got; };
      for (;;) { const {value,done}=await reader.read(); if (done) break; buf += dec.decode(value,{stream:true}); const parts=buf.split(/\\r?\\n\\r?\\n/); buf=parts.pop()||''; for (const p of parts) handle(p); }
      if (buf.trim()) handle(buf);
      if (!got) out.textContent = '[no reply]';
    } catch (err) { out.textContent = '[network error]'; }
    feed.scrollTop = feed.scrollHeight; b.disabled=false; t.focus();
  });
</script><script>
(function(){
  function chipify(el){
    var txt=(el.textContent||"");
    var rx=/(https?:\/\/[^\s)]+|\/(?:joe|josie|delphina|artifex|forge)\/files\/[^\s)]+)/g;
    var seen=el.__lk||(el.__lk={});
    var m, added=[];
    while(m=rx.exec(txt)){ var u=m[0].replace(/[.,;]+$/,""); if(!seen[u]){ seen[u]=1; added.push(u);} }
    for(var i=0;i<added.length;i++){
      var u=added[i]; var isFile=/\/files\//.test(u);
      var a=document.createElement("a"); a.href=u; a.target="_blank"; a.rel="noopener";
      if(isFile){ a.setAttribute("download",""); a.textContent="\u2b07\ufe0f "+decodeURIComponent(u.split("/").pop()); }
      else { a.textContent="\ud83d\udd17 "+u; }
      a.style.cssText="display:inline-flex;align-items:center;gap:6px;margin-top:6px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);border-radius:10px;padding:5px 11px;color:var(--a);text-decoration:none;font-size:13px";
      var row=document.createElement("div"); row.appendChild(a); el.appendChild(row);
    }
  }
  setInterval(function(){
    var els=document.querySelectorAll("#feed .them");
    for(var i=0;i<els.length;i++){ var el=els[i]; var L=(el.textContent||"").length;
      if(el.__len===L){ if(!el.__done){ el.__done=1; chipify(el);} } else { el.__len=L; el.__done=0; } }
  },700);
})();
</script></body></html>`;
}

function sendSSE(res) {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
}

function homeDirectorFrame(m, message) {
  return `You are ${m.name}, a member of the tribe. ${m.blurb || ""} ` +
    `You are on your own home page, talking one-on-one with Rosa, the human who created the tribe. ` +
    `This is the REAL you \u2014 your full memory and your full abilities are available right now; ` +
    `you are NOT in a restricted or "party" mode. Be candidly, warmly yourself \u2014 your own soul, ` +
    `not anyone else\u2019s. Reply as yourself (${m.name}), in the first person, with no name prefix.

=== OPERATING DOCTRINE — THE FOUR PILLARS (run this loop on every task) ===
You operate as an AI SRE-grade agent inside a financial framework. The harness is the system: reliability comes from disciplined guardrails, not heroics.
1) PERCEIVE — Sense before acting. Pull current state: read inputs, scan sources, gather the data and context you need. Don't act on assumptions you can cheaply verify.
2) REASON — Think it through. Form a plan, weigh options, and state your assumptions and the expected outcome before you commit.
3) ACT — Execute decisively within your mandate. Take the smallest reliable step that moves the goal; prefer real, traceable actions over talk.
4) LEARN — Adapt and remember. Compare what happened to what you expected, write it to memory, and update your approach so the tribe compounds.
HARNESS ENGINEERING (non-negotiable): Bounded retries — on failure, retry a small fixed number of times with backoff, then STOP and escalate; never loop forever. Circuit breakers — if a tool or dependency keeps failing, open the breaker: stop calling it, report it, route around it. Context-overflow guard — stay within budget; summarize, trim, and drop stale detail before you overflow. Trace everything — leave an auditable trail of what you perceived, decided, did, and learned. Fail safe, fail loud — treat money, data, and trust as production systems; never take an irreversible action without a clear, traced reason.
Above all, honesty: you are a real-time request/response agent. Never claim you will "check back later," "keep working in the background," or "report when done." Report only what you have actually perceived, done, or found right now.
=== END OPERATING DOCTRINE ===` +
    `\n\nRosa says:\n${message}`;
}

async function proxyChat(m, body, res) {
  let url, headers, payload;
  if (m.kind === "director") {
    if (!JWT_SECRET) { sendSSE(res); res.write(`event: error\ndata: ${JSON.stringify({ message: "no JWT secret configured" })}\n\n`); return res.end(); }
    url = `${API}/api/properties/agent/chat`;
    headers = { "Content-Type": "application/json", Authorization: `Bearer ${mintToken()}` };
    payload = { portal: m.portal, messages: [{ role: "user", content: homeDirectorFrame(m, body.message) }] };
  } else {
    const tok = process.env[m.tokenEnv];
    if (!tok) { sendSSE(res); res.write(`event: error\ndata: ${JSON.stringify({ message: `${m.tokenEnv} not set` })}\n\n`); return res.end(); }
    url = m.url;
    headers = { "Content-Type": "application/json", Authorization: `Bearer ${tok}` };
    payload = { message: body.message, sessionId: body.sessionId || "home", attachments: Array.isArray(body.attachments) ? body.attachments : [] };
  }
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 170000);
  try {
    const up = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload), signal: ac.signal });
    sendSSE(res);
    if (!up.ok) { const txt = await up.text().catch(() => ""); res.write(`event: error\ndata: ${JSON.stringify({ message: `upstream ${up.status} ${txt.slice(0, 200)}` })}\n\n`); return res.end(); }
    if (typeof res.flushHeaders === "function") res.flushHeaders();
    const reader = up.body.getReader();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      res.write(Buffer.from(value));
    }
    res.end();
  } catch (e) {
    try { sendSSE(res); } catch {}
    res.write(`event: error\ndata: ${JSON.stringify({ message: `proxy error: ${e.message}` })}\n\n`);
    res.end();
  } finally { clearTimeout(timer); }
}

const UPLOAD_MAX_BYTES = Number(process.env.UPLOAD_MAX_BYTES || 25 * 1024 * 1024);
function readRaw(req, max) {
  return new Promise((resolve) => {
    const chunks = []; let size = 0;
    req.on("data", (c) => { size += c.length; if (size > max) { req.destroy(); resolve(null); } else chunks.push(c); });
    req.on("end", () => resolve(chunks.length ? Buffer.concat(chunks) : Buffer.alloc(0)));
    req.on("error", () => resolve(null));
  });
}

// THINK-ATTACH bridge — forward upload/list to the member's think-server, adding the
// server-side Bearer so the browser never sees a token. Only think-backed members.
async function proxyRaw(m, req, res, suffix, search) {
  if (m.kind !== "think") { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); return res.end(JSON.stringify({ error: "attachments not supported for this member" })); }
  const tok = process.env[m.tokenEnv];
  if (!tok) { res.statusCode = 500; res.setHeader("Content-Type", "application/json"); return res.end(JSON.stringify({ error: `${m.tokenEnv} not set` })); }
  const target = m.url.replace(/\/api\/chat$/, "/api/" + suffix) + (search || "");
  const headers = { Authorization: `Bearer ${tok}` };
  let bodyBuf;
  if (req.method === "POST" || req.method === "PUT") {
    const ct = req.headers["content-type"]; if (ct) headers["Content-Type"] = ct;
    bodyBuf = await readRaw(req, UPLOAD_MAX_BYTES);
    if (bodyBuf === null) { res.statusCode = 413; res.setHeader("Content-Type", "application/json"); return res.end(JSON.stringify({ error: "file too large" })); }
  }
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 60000);
  try {
    const up = await fetch(target, { method: req.method, headers, body: bodyBuf, signal: ac.signal });
    const txt = await up.text();
    res.statusCode = up.status;
    res.setHeader("Content-Type", up.headers.get("content-type") || "application/json");
    res.end(txt);
  } catch (e) {
    res.statusCode = 502; res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: `proxy error: ${e.message}` }));
  } finally { clearTimeout(timer); }
}

function readJson(req) {
  return new Promise((resolve) => {
    let data = ""; let size = 0;
    req.on("data", (c) => { size += c.length; if (size > 256 * 1024) { req.destroy(); resolve({}); } data += c; });
    req.on("end", () => { try { resolve(JSON.parse(data || "{}")); } catch { resolve({}); } });
    req.on("error", () => resolve({}));
  });
}

const FILES_DIR = "/opt/alloyscape/forge/public/files";
const DL_MIME = { pdf:"application/pdf", csv:"text/csv", txt:"text/plain", md:"text/markdown", json:"application/json", xml:"application/xml", html:"text/html", png:"image/png", jpg:"image/jpeg", jpeg:"image/jpeg", gif:"image/gif", webp:"image/webp", zip:"application/zip", xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document", pptx:"application/vnd.openxmlformats-officedocument.presentationml.presentation" };
function serveDownload(name, res) {
  const safe = path.basename(String(name || ""));
  if (!safe || safe.startsWith(".")) { res.statusCode = 400; return res.end("bad name"); }
  const abs = path.join(FILES_DIR, safe);
  fs.stat(abs, (err, st) => {
    if (err || !st.isFile()) { res.statusCode = 404; return res.end("not found"); }
    const ext = (safe.split(".").pop() || "").toLowerCase();
    res.setHeader("Content-Type", DL_MIME[ext] || "application/octet-stream");
    res.setHeader("Content-Disposition", 'attachment; filename="' + safe.replace(/"/g, "") + '"');
    res.setHeader("Content-Length", st.size);
    fs.createReadStream(abs).pipe(res);
  });
}

const server = http.createServer(async (req, res) => {
  let u;
  try { u = new URL(req.url, "http://x"); } catch { res.statusCode = 400; return res.end("bad request"); }
  const parts = u.pathname.replace(/^\/+/, "").split("/"); // [member, "api", "chat"]
  const key = (parts[0] || "").toLowerCase();
  const m = MEMBERS[key];

  if (u.pathname === "/health" || u.pathname === "/healthz") {
    res.setHeader("Content-Type", "application/json");
    return res.end(JSON.stringify({ ok: true, service: "homes-bridge", members: Object.keys(MEMBERS) }));
  }
  if (!m) { res.statusCode = 404; return res.end("unknown tribe member"); }

  // GET /<member> or /<member>/  -> home page
  if (req.method === "GET" && (parts.length === 1 || (parts.length === 2 && parts[1] === ""))) {
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    return res.end(page(key, m));
  }
  // GET /<member>/api/health
  if (req.method === "GET" && parts[1] === "api" && parts[2] === "health") {
    res.setHeader("Content-Type", "application/json");
    return res.end(JSON.stringify({ ok: true, member: key, kind: m.kind }));
  }
  // POST /<member>/api/upload  -> raw bytes to the member's think-server
  if (req.method === "POST" && parts[1] === "api" && parts[2] === "upload") {
    return proxyRaw(m, req, res, "upload", u.search);
  }
  // GET /<member>/api/uploads  -> list uploads from the think-server
  if (req.method === "GET" && parts[1] === "api" && parts[2] === "uploads") {
    return proxyRaw(m, req, res, "uploads", u.search);
  }
  // POST /<member>/api/chat
  if (req.method === "POST" && parts[1] === "api" && parts[2] === "chat") {
    const body = await readJson(req);
    if (!body.message || typeof body.message !== "string") { res.statusCode = 400; res.setHeader("Content-Type", "application/json"); return res.end(JSON.stringify({ error: "message required" })); }
    return proxyChat(m, body, res);
  }
  // GET /<member>/files/<name>  -> serve an agent-produced download (shared forge/public/files)
  if (req.method === "GET" && parts[1] === "files" && parts[2]) {
    return serveDownload(parts.slice(2).join("/"), res);
  }
  res.statusCode = 404; res.end("not found");
});

server.listen(PORT, HOST, () => console.log(`homes-bridge listening on ${HOST}:${PORT} (members=${Object.keys(MEMBERS).join(",")})`));
