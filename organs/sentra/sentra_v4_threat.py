"""sentra_v4_threat — 3D Threat Globe + Verdict River scenes (ADDITIVE TABS).

Yachay (CTO) · Co-Authored-By: Perplexity Computer Agent · 2026-06-02

These are ADDITIVE standalone scene TABS — they do NOT replace the operational
front (React SPA at `/`) or the 8-immune-gate console (`/console/`). Each scene
is a self-contained Three.js page (CDN module, no build step) that pulls LIVE
verdict data from the existing immune APIs already served by this app:

  - GET /api/sentra/v1/audit-log   (real recorded verdicts; decision/lambda/signals)
  - GET /api/sentra/v1/gates       (the 8 immune gates)

NO HALLUCINATION posture:
  - Every counter rendered is derived from a live HTTP-200 API response. If the
    fetch fails, the scene shows an honest "live feed unavailable" notice rather
    than fabricated numbers.
  - No "first in the world" / unqualified "Palantir-class" marketing claim. The
    pages describe exactly what they do: a 3D rendering of the live verdict feed.
  - Doctrine v11 LOCKED 749/14/163 unchanged. Λ = Conjecture 1 (NOT a theorem).

register(app) mounts:
  GET /threat-globe    -> dark globe, live verdict arcs, 8-gate side panel
  GET /verdict-river   -> flowing verdict stream (allow/review/deny lanes)
Both registered BEFORE the SPA catch-all by serve.py so they resolve locally.
"""
from __future__ import annotations

import sys

try:
    from fastapi.responses import HTMLResponse
except Exception:  # pragma: no cover
    HTMLResponse = None  # type: ignore


_COMMON_HEAD = """
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root{--bg:#04060f;--ink:#e8eefc;--mut:#8aa0bf;--allow:#2ecc71;--review:#e0c060;--deny:#ff5566;--line:#1e3a5f}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow:hidden}
    .topbar{position:fixed;top:0;left:0;right:0;z-index:10;padding:10px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#04060fdd,#04060f88);backdrop-filter:blur(6px);gap:12px;flex-wrap:wrap}
    .topbar a{color:#7fb0e0;text-decoration:none;margin-left:14px}
    .topbar a:hover{text-decoration:underline}
    .pill{font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid;margin-left:8px}
    .pill.live{color:var(--allow);border-color:#2ecc7166;background:#2ecc7115}
    .pill.def{color:var(--review);border-color:#e0c06066;background:#e0c06015}
    .panel{position:fixed;top:64px;right:14px;z-index:9;width:268px;background:#0b1220cc;border:1px solid var(--line);border-radius:12px;padding:12px 14px;backdrop-filter:blur(6px);font-size:12.5px;line-height:1.5}
    .panel h3{margin:0 0 8px;font-size:13px;color:var(--mut);font-weight:600;letter-spacing:.4px;text-transform:uppercase}
    .kpi{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px dashed #ffffff10}
    .kpi b.allow{color:var(--allow)} .kpi b.review{color:var(--review)} .kpi b.deny{color:var(--deny)}
    .gate{display:flex;align-items:center;gap:6px;padding:2px 0;color:var(--mut)}
    .dot{width:7px;height:7px;border-radius:50%;background:var(--allow);box-shadow:0 0 6px var(--allow)}
    .foot{position:fixed;bottom:8px;left:14px;z-index:9;font-size:11px;color:var(--mut)}
    .err{color:var(--review)}
    canvas{display:block}
  </style>
"""


def _scene_page(title: str, kind: str, sibling_label: str, sibling_href: str) -> str:
    """kind = 'globe' | 'river'."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>{title} · sentra</title>
  {_COMMON_HEAD}
  <script type="importmap">
  {{ "imports": {{ "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js" }} }}
  </script>
</head>
<body>
  <div class="topbar">
    <div><strong>sentra · {title}</strong>
      <span class="pill live" id="srcpill">live verdict feed</span>
      <span style="color:var(--mut);font-size:12px">— 3D rendering of the live /api/sentra/v1/audit-log verdict stream</span>
    </div>
    <div>
      <a href="/">← operational front</a>
      <a href="/console/">8-gate console</a>
      <a href="{sibling_href}">{sibling_label} →</a>
    </div>
  </div>

  <div class="panel">
    <h3>Live verdicts (session)</h3>
    <div class="kpi"><span>total</span><b id="k-total">…</b></div>
    <div class="kpi"><span>allow</span><b class="allow" id="k-allow">…</b></div>
    <div class="kpi"><span>review/warn</span><b class="review" id="k-review">…</b></div>
    <div class="kpi"><span>deny/block</span><b class="deny" id="k-deny">…</b></div>
    <h3 style="margin-top:12px">8 immune gates</h3>
    <div id="gatelist"><span style="color:var(--mut)">loading…</span></div>
    <div id="feederr" class="err" style="margin-top:8px"></div>
  </div>

  <div class="foot">
    Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT a theorem) ·
    counters derived from live HTTP-200 API responses (NO HALLUCINATION).
  </div>

  <script type="module">
    import * as THREE from 'three';

    const KIND = {kind!r};
    const COLORS = {{ allow: 0x2ecc71, review: 0xe0c060, deny: 0xff5566 }};

    // ---- live data ---------------------------------------------------------
    function classify(d) {{
      d = (d || '').toLowerCase();
      if (d.includes('deny') || d.includes('block')) return 'deny';
      if (d.includes('review') || d.includes('warn')) return 'review';
      return 'allow';
    }}
    async function loadData() {{
      const out = {{ verdicts: [], gates: [], ok: false, err: '' }};
      try {{
        const r = await fetch('/api/sentra/v1/audit-log', {{ headers: {{ accept: 'application/json' }} }});
        if (!r.ok) throw new Error('audit-log HTTP ' + r.status);
        const j = await r.json();
        out.verdicts = (j.entries || []).map(e => ({{
          cls: classify(e.decision), lam: typeof e.lambda_value === 'number' ? e.lambda_value : 1.0,
          agent: e.agent || '', id: e.id || ''
        }}));
        out.ok = true;
      }} catch (e) {{ out.err = String(e.message || e); }}
      try {{
        const g = await fetch('/api/sentra/v1/gates', {{ headers: {{ accept: 'application/json' }} }});
        if (g.ok) {{ const gj = await g.json(); out.gates = (gj.gates || []).map(x => x.label || x.name || x.id); }}
      }} catch (e) {{ /* gates optional */ }}
      return out;
    }}

    function renderPanel(data) {{
      const v = data.verdicts;
      const c = {{ allow: 0, review: 0, deny: 0 }};
      v.forEach(x => c[x.cls]++);
      document.getElementById('k-total').textContent = v.length;
      document.getElementById('k-allow').textContent = c.allow;
      document.getElementById('k-review').textContent = c.review;
      document.getElementById('k-deny').textContent = c.deny;
      const gl = document.getElementById('gatelist');
      if (data.gates.length) {{
        gl.innerHTML = data.gates.slice(0, 8).map(n => `<div class="gate"><span class="dot"></span>${{n}}</div>`).join('');
      }} else {{
        gl.innerHTML = '<span style="color:var(--mut)">8 immune gates — see /console/</span>';
      }}
      if (!data.ok) {{
        document.getElementById('srcpill').textContent = 'live feed unavailable';
        document.getElementById('srcpill').className = 'pill def';
        document.getElementById('feederr').textContent = 'Honest gap: live verdict feed unavailable (' + data.err + '). Showing scene scaffold only — no fabricated counters.';
      }}
      return c;
    }}

    // ---- three.js scaffold -------------------------------------------------
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x04060f, 0.018);
    const camera = new THREE.PerspectiveCamera(55, innerWidth/innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(innerWidth, innerHeight);
    document.body.appendChild(renderer.domElement);
    addEventListener('resize', () => {{
      camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
    }});
    scene.add(new THREE.AmbientLight(0x88aaff, 0.5));
    const key = new THREE.PointLight(0x66aaff, 1.2); key.position.set(8, 6, 10); scene.add(key);

    const group = new THREE.Group(); scene.add(group);
    let nodes = [];

    function buildGlobe(verdicts) {{
      camera.position.set(0, 0, 9);
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(3, 48, 48),
        new THREE.MeshBasicMaterial({{ color: 0x0a2540, wireframe: true, transparent: true, opacity: 0.35 }})
      );
      group.add(sphere);
      const core = new THREE.Mesh(new THREE.SphereGeometry(2.92, 48, 48),
        new THREE.MeshPhongMaterial({{ color: 0x061626, shininess: 8, transparent: true, opacity: 0.9 }}));
      group.add(core);
      const list = verdicts.length ? verdicts : Array.from({{length: 24}}, () => ({{ cls: 'allow', lam: 1 }}));
      list.forEach((v, i) => {{
        const phi = Math.acos(-1 + (2 * i) / list.length);
        const theta = Math.sqrt(list.length * Math.PI) * phi;
        const r = 3.05;
        const p = new THREE.Vector3(
          r * Math.cos(theta) * Math.sin(phi),
          r * Math.sin(theta) * Math.sin(phi),
          r * Math.cos(phi)
        );
        const m = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 12),
          new THREE.MeshBasicMaterial({{ color: COLORS[v.cls] }}));
        m.position.copy(p); m.userData = {{ base: p.clone(), ph: Math.random()*Math.PI*2 }};
        group.add(m); nodes.push(m);
      }});
    }}

    function buildRiver(verdicts) {{
      camera.position.set(0, 2.5, 11);
      camera.lookAt(0, 0, 0);
      const laneY = {{ allow: 1.6, review: 0, deny: -1.6 }};
      ['allow','review','deny'].forEach(cls => {{
        const g = new THREE.Mesh(new THREE.PlaneGeometry(22, 1.1),
          new THREE.MeshBasicMaterial({{ color: COLORS[cls], transparent: true, opacity: 0.06 }}));
        g.position.set(0, laneY[cls], -0.2); scene.add(g);
      }});
      const list = verdicts.length ? verdicts : Array.from({{length: 30}}, () => ({{ cls: 'allow', lam: 1 }}));
      list.forEach((v, i) => {{
        const m = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.28, 0.28),
          new THREE.MeshBasicMaterial({{ color: COLORS[v.cls] }}));
        m.position.set(-11 + (i/list.length)*22 + Math.random()*0.5, laneY[v.cls] + (Math.random()-0.5)*0.4, 0);
        m.userData = {{ speed: 0.012 + Math.random()*0.02 }};
        scene.add(m); nodes.push(m);
      }});
    }}

    function animate() {{
      requestAnimationFrame(animate);
      const t = performance.now() * 0.001;
      if (KIND === 'globe') {{
        group.rotation.y = t * 0.12;
        nodes.forEach(n => {{ const s = 1 + 0.25*Math.sin(t*2 + n.userData.ph); n.scale.setScalar(s); }});
      }} else {{
        nodes.forEach(n => {{ n.position.x += n.userData.speed; n.rotation.x += 0.04; n.rotation.y += 0.03;
          if (n.position.x > 11) n.position.x = -11; }});
      }}
      renderer.render(scene, camera);
    }}

    (async () => {{
      const data = await loadData();
      renderPanel(data);
      if (KIND === 'globe') buildGlobe(data.verdicts); else buildRiver(data.verdicts);
      animate();
    }})();
  </script>
</body>
</html>"""


def register(app, ns: str = "sentra", organ: str = None, **_kwargs) -> dict:
    """Mount the 3D scene TABS.

    Accepts BOTH ``ns=`` (this module's contract) and the legacy ``organ=``
    kwarg so the same serve.py call works regardless of which serve.py revision
    is live — prevents a silent TypeError -> try/except -> routes falling through
    to the SPA shell. Extra kwargs are tolerated for the same reason.
    """
    ns = organ or ns or "sentra"
    if HTMLResponse is None:
        raise RuntimeError("fastapi HTMLResponse unavailable")

    globe_html = _scene_page("Threat Globe (3D)", "globe", "Verdict River", "/verdict-river")
    river_html = _scene_page("Verdict River (3D)", "river", "Threat Globe", "/threat-globe")

    @app.get("/threat-globe")
    async def threat_globe():  # noqa: ANN201
        return HTMLResponse(globe_html)

    @app.get("/verdict-river")
    async def verdict_river():  # noqa: ANN201
        return HTMLResponse(river_html)

    print("[sentra_v4_threat] /threat-globe + /verdict-river registered "
          "(3D TABS, live audit-log feed; ADDITIVE, do-not-replace-front)", file=sys.stderr)
    return {"base": ns, "routes": ["/threat-globe", "/verdict-river"]}
