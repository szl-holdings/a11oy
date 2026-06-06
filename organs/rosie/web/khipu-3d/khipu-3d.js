/* ===========================================================================
 * khipu-3d.js — Beat 3 of the Greene demo. A force-directed 3D graph of the
 * LIVE Khipu receipt DAG across all 5 organs, built on three.js + 3d-force-graph.
 *
 *   Node color  = Λ verdict (green ≥0.8, amber 0.5–0.8, red <0.5)
 *   Node size   = Welford online variance of the Λ stream (data-adapter.js)
 *   Edge color  = Wire (B,C,D,E,F,G)  [theme.css palette]
 *   Edge        = DSSE Merkle parent chain (Wire F) + W3C traceparent (Wire D)
 *   Label       = organ · trace…(last 8) · λ · timestamp
 *   Pulse       = a particle fired along edges every time a NEW receipt arrives
 *
 * Polls /api/rosie/v1/khipu/aggregate every 3s; falls back to direct organ
 * fan-out, then to localStorage cache; honest "Mesh quiescent" if all empty.
 *
 * Signed-off-by: Yachay <yachay@szlholdings.ai>
 * Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
 * =========================================================================== */
(function () {
  "use strict";

  const WIRE_COLOR = {
    B: "#5cc4bf", C: "#d7b96b", D: "#9b8cff", E: "#e58e54", F: "#c0392b", G: "#5c8fd1"
  };
  const VERDICT_COLOR = { green: "#4fd18b", amber: "#d7b96b", red: "#c0392b" };
  const POLL_MS = 3000;

  let Graph = null;
  let knownNodeIds = new Set();
  let firstPaint = true;

  function el(id) { return document.getElementById(id); }

  function colorForNode(n) { return VERDICT_COLOR[n.verdict] || "#9aa4b2"; }
  // Node size from Welford variance: low variance → small/stable, high → large.
  function sizeForNode(n) {
    const base = 3.2;
    const v = (typeof n.var === "number") ? n.var : 0;
    return base + Math.sqrt(Math.max(0, v)) * 26 + (n.cosigners > 1 ? n.cosigners * 0.8 : 0);
  }

  function initGraph() {
    const ForceGraph3D = window.ForceGraph3D;
    if (!ForceGraph3D) { showQuiescent("3D engine failed to load", "three.js / 3d-force-graph CDN unreachable. Use the standalone artifact."); return; }
    Graph = ForceGraph3D({ controlType: "orbit" })(el("graph"))
      .backgroundColor("rgba(0,0,0,0)")
      .showNavInfo(false)
      .nodeRelSize(1)
      .nodeVal(sizeForNode)
      .nodeColor(colorForNode)
      .nodeOpacity(0.92)
      .nodeLabel(nodeTooltipHTML)
      .linkColor((l) => WIRE_COLOR[l.wire] || "#5c6b82")
      .linkWidth((l) => (l.wire === "D" ? 1.6 : 1.0))
      .linkOpacity(0.55)
      .linkDirectionalParticles(0)
      .linkDirectionalParticleWidth(2.4)
      .linkDirectionalParticleColor((l) => WIRE_COLOR[l.wire] || "#fff")
      .onNodeHover(onHover)
      .onNodeClick(onClick)
      .nodeThreeObjectExtend(true)
      .nodeThreeObject(makeLabelSprite);

    // Gentle auto-orbit for the demo "cinematic" feel; stops on user interaction.
    Graph.cameraPosition({ z: 220 });
    let userInteracted = false;
    Graph.controls().addEventListener("start", () => { userInteracted = true; });
    let angle = 0;
    (function orbit() {
      if (!userInteracted && Graph) {
        angle += Math.PI / 1400;
        const r = 240;
        Graph.cameraPosition({ x: r * Math.sin(angle), z: r * Math.cos(angle) }, undefined, 0);
      }
      requestAnimationFrame(orbit);
    })();

    window.addEventListener("resize", () => { Graph.width(window.innerWidth); Graph.height(window.innerHeight); });
    Graph.width(window.innerWidth); Graph.height(window.innerHeight);
  }

  // Floating label sprite: organ · trace8 · λ · ts (short)
  function makeLabelSprite(node) {
    const THREE = window.THREE;
    const SpriteText = window.SpriteText;
    if (!THREE || !SpriteText) return undefined;
    const ts = node.ts_utc ? String(node.ts_utc).slice(11, 19) : "--:--:--";
    const txt = `${node.organ}·…${node.trace8 || "????"}\nλ=${(node.lambda || 0).toFixed(2)}·${ts}`;
    const s = new SpriteText(txt);
    s.color = "#f3ecdc";
    s.backgroundColor = "rgba(11,10,31,0.55)";
    s.padding = 1.4;
    s.borderRadius = 2;
    s.fontFace = "JetBrains Mono, monospace";
    s.textHeight = 2.4;
    s.position.y = sizeForNode(node) + 4;
    return s;
  }

  function nodeTooltipHTML(n) {
    return `<div style="font-family:JetBrains Mono,monospace;font-size:11px;color:#f3ecdc">
      <b style="color:#d7b96b">${n.organ}</b> · Wire ${n.wire} · idx ${n.index}<br/>
      trace …${n.trace8} · λ=${(n.lambda||0).toFixed(3)} · <b style="color:${VERDICT_COLOR[n.verdict]}">${(n.verdict||"").toUpperCase()}</b><br/>
      signed=${n.signed} · cosigners=${n.cosigners} · SLSA ${n.slsa||"?"}<br/>
      ${n.ts_utc||""}</div>`;
  }

  // --- Formula card on hover (the math beat) ---------------------------------
  function onHover(node) {
    const card = el("formula-card");
    if (!node || !window.KhipuFormulas) { card.classList.remove("show"); return; }
    const fs = window.KhipuFormulas.forNode(node);
    card.innerHTML = fs.map((f) => `
      <div class="fname">${f.name}</div>
      <code class="fmath">${escapeHTML(f.math)}</code>
      <div class="fval">${escapeHTML(f.value || "")}</div>
      <div class="fcite">${escapeHTML(f.cite)}</div>
    `).join('<hr style="border:0;border-top:1px solid rgba(215,185,107,0.2);margin:10px 0"/>');
    card.classList.add("show");
    document.body.style.cursor = "pointer";
    positionCard();
  }
  function onClick(node) {
    if (!node || !Graph) return;
    // Cinematic focus: fly the camera to the clicked node (used for the BLS beat).
    const dist = 70;
    const ratio = 1 + dist / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
    Graph.cameraPosition({ x: (node.x||0)*ratio, y: (node.y||0)*ratio, z: (node.z||0)*ratio }, node, 1200);
  }
  document.addEventListener("mousemove", (e) => { _mx = e.clientX; _my = e.clientY; positionCard(); });
  let _mx = 0, _my = 0;
  function positionCard() {
    const card = el("formula-card"); if (!card.classList.contains("show")) return;
    const w = card.offsetWidth, h = card.offsetHeight;
    let x = _mx + 18, y = _my + 18;
    if (x + w > window.innerWidth) x = _mx - w - 18;
    if (y + h > window.innerHeight) y = window.innerHeight - h - 12;
    card.style.left = x + "px"; card.style.top = y + "px";
  }
  function escapeHTML(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c])); }

  // --- Apply a snapshot; fire pulses for any NEW receipts --------------------
  function applySnapshot(snap) {
    if (!snap || !snap.nodes || !snap.nodes.length) { showQuiescent(); return; }
    hideQuiescent();
    updateHUD(snap);

    const newIds = [];
    snap.nodes.forEach((n) => { if (!knownNodeIds.has(n.id)) newIds.push(n.id); });

    Graph.graphData({
      nodes: snap.nodes,
      links: (snap.edges || []).map((e) => ({ source: e.source, target: e.target, wire: e.wire, kind: e.kind }))
    });

    // Pulse: shoot particles along edges touching newly-arrived receipts.
    if (!firstPaint && newIds.length) firePulse(newIds);
    if (firstPaint && snap.nodes.length) { setTimeout(() => Graph.zoomToFit(800, 60), 400); firstPaint = false; }

    snap.nodes.forEach((n) => knownNodeIds.add(n.id));
  }

  function firePulse(newIds) {
    const idset = new Set(newIds);
    Graph.linkDirectionalParticles((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      return (idset.has(s) || idset.has(t)) ? 4 : 0;
    });
    Graph.linkDirectionalParticleSpeed(0.012);
    // decay back to 0 so the pulse is a transient "heartbeat"
    setTimeout(() => Graph.linkDirectionalParticles(0), 2600);
  }

  // --- HUD: organ status strip (HONEST) --------------------------------------
  function updateHUD(snap) {
    const box = el("organ-status"); if (!box) return;
    const organs = snap.organs && snap.organs.length ? snap.organs : inferOrgans(snap);
    box.innerHTML = organs.map((o) => {
      const live = (o.status === "LIVE");
      const cls = live ? "live" : "down";
      const meta = live ? (o.count + " rcpt") : (o.status || "DOWN");
      return `<div class="organ-row"><span class="dot ${cls}"></span>
        <span class="name">${o.organ}</span><span class="meta">${meta}</span></div>`;
    }).join("");
    const src = el("data-source");
    if (src) src.textContent = (snap.fromCache ? "cache · " : "") + (snap.source || "live") +
      " · " + (snap.fetched_utc ? snap.fetched_utc.slice(11,19)+"Z" : "now");
  }
  function inferOrgans(snap) {
    const seen = {};
    (snap.nodes||[]).forEach((n) => { seen[n.organ] = (seen[n.organ]||0)+1; });
    return window.KhipuData.ORGANS.map((o) => ({ organ: o, status: seen[o] ? "LIVE" : "BUILD_ERROR", count: seen[o]||0 }));
  }

  function showQuiescent(title, sub) {
    const q = el("quiescent"); if (!q) return;
    if (title) q.querySelector(".q-title").textContent = title;
    if (sub) q.querySelector(".q-sub").textContent = sub;
    q.classList.add("show");
  }
  function hideQuiescent() { const q = el("quiescent"); if (q) q.classList.remove("show"); }

  // --- Poll loop -------------------------------------------------------------
  async function tick() {
    try {
      const snap = await window.KhipuData.fetchSnapshot({ timeoutMs: 8000 });
      applySnapshot(snap);
    } catch (e) {
      // honest failsafe: try cached, else quiescent
      const snap = await window.KhipuData.fetchSnapshot({ timeoutMs: 1 }).catch(() => null);
      if (snap) applySnapshot(snap); else showQuiescent();
    }
  }

  function boot() {
    initGraph();
    el("plaque-line").textContent = window.KhipuData.DOCTRINE.plaque;
    const reload = el("q-reload"); if (reload) reload.addEventListener("click", () => { firstPaint = true; tick(); });
    tick();
    setInterval(tick, POLL_MS);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
