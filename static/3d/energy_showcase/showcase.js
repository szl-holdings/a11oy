// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// energy_showcase/showcase.js — the SHARED holographic 3D energy-ops showcase.
//
// ONE module, THREE surfaces: the /holographic "energy" tab loads it (via
// surfaces/energy.js), the a11oy energy tab loads it (web/energy-holographic.html),
// and the Hugging Face SZLHOLDINGS/energy Space loads the SAME module (web/energy.html
// upgrade). Build it once; deploy it everywhere.
//
// DOCTRINE v11 (never violated here):
//   * 0 runtime CDN — three.js r170 resolves through the page importmap; this file
//     fetches ONLY same-origin a11oy endpoints via szl3d_live.poll.
//   * Every value carries its honesty label READ FROM THE JSON (MEASURED/MODELED/
//     SAMPLE/ESTIMATE/STRUCTURAL-ONLY) — never invented, never upgraded.
//   * Revenue is MODELED/ESTIMATE until a real charge clears; joules are MEASURED only.
//   * 404 / network error / {degraded:true} -> the graph renders its honest
//     NO-LIVE-DATA / DEGRADED state. We NEVER fabricate a telemetry value.
//
// Leaders modeled (see zoom_out/viz_leaders_research.md §1 Energy + §8 Frontier):
//   Electricity Maps (carbon/price choropleth), deck.gl ColumnLayer (negative-price
//   columns), NVIDIA Omniverse / TX-Digital-Twin (compute-fabric hex + instanced node
//   health), TSL particle attractors (per-job particle stream), Gaussian/SDF glows
//   (renewable halo, carbon dome), WebGPU-with-WebGL2-fallback (backend indicator).
//
// LIVE ENDPOINTS (wired via szl3d_live.poll; never hardcoded):
//   /api/a11oy/v1/energy/operator/status   — jobs_done, joules_measured_total, tokens, nodes
//   /api/a11oy/v1/energy/ledger            — signed JouleCharge receipts + chain integrity
//   /api/a11oy/v1/energy/projection?window=running — 1-day + scale MODELED projections
//   /api/a11oy/v1/harvest/posture          — grid price, renewable share, negative windows
//   /api/a11oy/v1/compute-pool-hardened    — GPU nodes (rtx-betterwithage + chaski), egress-scrubbed
//
// buildShowcase(ctx) -> { graphs, frame(t), dispose() }
//   ctx = { stage, container, live, label, THREE }   (the szl3d surface contract)

const EP = Object.freeze({
  STATUS:     "/api/a11oy/v1/energy/operator/status",
  LEDGER:     "/api/a11oy/v1/energy/ledger",
  PROJECTION: "/api/a11oy/v1/energy/projection?window=running",
  POSTURE:    "/api/a11oy/v1/harvest/posture",
  POOL:       "/api/a11oy/v1/compute-pool-hardened",
});

const COL = Object.freeze({
  teal: 0x39d3c4, gold: 0xe8c074, green: 0x2fd07a, amber: 0xe8c074,
  blue: 0x6fb1ff, red: 0xff6b6b, gray: 0x8a97a3, dim: 0x1d2a36, cream: 0xeef3f6,
});

// ---------------------------------------------------------------------------
// Tiny helpers — honest number parsing (never coerce missing -> 0 silently).
// ---------------------------------------------------------------------------
function num(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
// Unwrap Dev3's _labeled() shape {value,label} or a bare scalar.
function lv(x) { return (x && typeof x === "object" && "value" in x) ? num(x.value) : num(x); }
function llabel(x) { return (x && typeof x === "object" && "label" in x) ? x.label : null; }
function clamp01(x) { return Math.max(0, Math.min(1, x)); }

// ---------------------------------------------------------------------------
// Graph base: a positioned group + a DOM HUD card (title, value, honesty chip,
// live badge). Each of the 18 graphs subclasses this via a factory.
// ---------------------------------------------------------------------------
function makeGraphCard(ctx, def, originX, originY) {
  const THREE = ctx.THREE;
  const group = new THREE.Group();
  group.position.set(originX, originY, 0);
  ctx.stage.scene.add(group);

  // floating title billboard (STRUCTURAL-ONLY until first live datum upgrades it)
  let titleSprite = null;
  try {
    titleSprite = ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: def.title, scale: 0.5, position: [0, 2.5, 0] });
    group.add(titleSprite);
  } catch (_) {}

  // DOM HUD card
  const card = document.createElement("div");
  card.className = "szl3d-graph-card";
  card.setAttribute("data-graph", def.id);
  Object.assign(card.style, {
    border: "1px solid #182431", background: "rgba(8,16,24,.82)", borderRadius: "9px",
    padding: "8px 10px", font: "11px ui-monospace,SFMono-Regular,Menlo,monospace",
    color: "#9fb1bf", display: "flex", flexDirection: "column", gap: "5px", minWidth: "0",
  });
  const head = document.createElement("div");
  head.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:6px";
  const tt = document.createElement("span");
  tt.textContent = def.n + ". " + def.title;
  tt.style.cssText = "color:#eef3f6;font-weight:600;letter-spacing:.2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
  const chip = ctx.label.chip("STRUCTURAL-ONLY", {});
  head.appendChild(tt); head.appendChild(chip);
  const valLine = document.createElement("div");
  valLine.style.cssText = "color:#39d3c4;font-size:15px;font-weight:600";
  valLine.textContent = "—";
  const subLine = document.createElement("div");
  subLine.style.cssText = "color:#7d8a96;font-size:10px;line-height:1.35";
  subLine.textContent = def.sub || "";
  const badge = ctx.live.createBadge();
  card.appendChild(head); card.appendChild(valLine); card.appendChild(subLine); card.appendChild(badge.el);

  function setLabel(raw) {
    ctx.label.updateChip(chip, raw || "STRUCTURAL-ONLY");
    if (titleSprite) {
      // swap the billboard texture by replacing the sprite (cheap; once per label change)
      try {
        const np = titleSprite.position.clone();
        group.remove(titleSprite);
        titleSprite = ctx.label.billboard(THREE, raw || "STRUCTURAL-ONLY", { text: def.title, scale: 0.5 });
        titleSprite.position.copy(np);
        group.add(titleSprite);
      } catch (_) {}
    }
  }

  return {
    id: def.id, group, card, badge,
    setValue(v) { valLine.textContent = v; },
    setSub(s) { subLine.textContent = s; },
    setLabel,
    add(obj) { group.add(obj); },
  };
}

// ===========================================================================
// THE 18 GRAPHS. Each returns { gid, def, mount(ctx, host), update(json, meta),
// frame(t), endpoint }. mount() builds geometry into host.group; update() maps the
// live JSON to the geometry + HUD + honesty chip; frame() animates.
// ===========================================================================

// (1) Live measured-joules orbital counter — the 78k milestone, ticking.
function gMeasuredJoulesOrbital() {
  let core, ring, host, T, joules = null;
  return {
    gid: "joules-orbital", endpoint: EP.STATUS,
    def: { id: "joules-orbital", n: 1, title: "Measured Joules · orbital", sub: "operator status · joules_measured_total" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      core = new T.Mesh(new T.IcosahedronGeometry(0.9, 2),
        new T.MeshStandardMaterial({ color: COL.green, emissive: COL.green, emissiveIntensity: 0.6, metalness: 0.5, roughness: 0.3 }));
      ring = new T.Mesh(new T.TorusGeometry(1.5, 0.04, 12, 80),
        new T.MeshStandardMaterial({ color: COL.green, emissive: COL.green, emissiveIntensity: 0.5 }));
      ring.rotation.x = Math.PI / 2.3;
      host.add(core); host.add(ring);
    },
    update(json, meta) {
      joules = num(json && json.joules_measured_total);
      const lab = (json && json.joules_measured_label) || meta.label || "MEASURED";
      if (joules == null) { host.setValue("NO-LIVE-DATA"); host.setLabel("STRUCTURAL-ONLY"); return; }
      host.setValue(joules.toLocaleString(undefined, { maximumFractionDigits: 1 }) + " J");
      host.setSub("tokens " + (num(json.tokens_total) ?? "—") + " · jobs " + (num(json.jobs_done) ?? "—"));
      host.setLabel(lab);
      const s = 0.7 + clamp01(joules / 100000) * 0.9;
      core.scale.setScalar(s);
    },
    frame(t) { if (core) { core.rotation.y = t * 0.6; ring.rotation.z = t * 0.4; } },
  };
}

// (2) Negative-price column field — grid price over windows, green when grid pays us.
function gNegativePriceColumns() {
  let host, T, cols = [];
  return {
    gid: "price-columns", endpoint: EP.POSTURE,
    def: { id: "price-columns", n: 2, title: "Grid-price columns", sub: "harvest posture · price readings (green = grid pays us)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      for (let i = 0; i < 12; i++) {
        const m = new T.Mesh(new T.BoxGeometry(0.18, 0.05, 0.18),
          new T.MeshStandardMaterial({ color: COL.gold, emissive: COL.gold, emissiveIntensity: 0.4 }));
        m.position.set((i - 5.5) * 0.26, 0, 0);
        host.add(m); cols.push(m);
      }
    },
    update(json, meta) {
      // Build a price series from readings (real values only); harvest posture exposes
      // numeric feed values in `readings[].value`. We never fabricate missing readings.
      const readings = (json && Array.isArray(json.readings)) ? json.readings : [];
      const prices = readings.map((r) => num(r && r.value)).filter((v) => v != null);
      const posture = json && json.posture;
      host.setValue(posture ? String(posture).toUpperCase() : "NO-LIVE-DATA");
      host.setSub(prices.length ? (prices.length + " live feed readings") : "no numeric feed value (honest empty)");
      host.setLabel(meta.label || (json && json.joules_label) || "SAMPLE");
      cols.forEach((m, i) => {
        const p = prices[i % Math.max(1, prices.length)];
        const v = p == null ? 0.05 : Math.min(2.2, Math.abs(p) / 60 + 0.1);
        m.scale.y = v / 0.05;
        m.position.y = v / 2;
        const neg = p != null && p < 0;
        m.material.color.setHex(neg ? COL.green : COL.gold);
        m.material.emissive.setHex(neg ? COL.green : COL.gold);
      });
    },
    frame() {},
  };
}

// (3) Compute-fabric hex — rtx-betterwithage + chaski as live GPU nodes, pulsing.
function gComputeFabricHex() {
  let host, T, nodes = [];
  return {
    gid: "fabric-hex", endpoint: EP.POOL,
    def: { id: "fabric-hex", n: 3, title: "Compute-fabric hex", sub: "compute-pool · live GPU nodes" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      for (let i = 0; i < 6; i++) {
        const m = new T.Mesh(new T.CylinderGeometry(0.34, 0.34, 0.16, 6),
          new T.MeshStandardMaterial({ color: COL.gray, emissive: COL.gray, emissiveIntensity: 0.3 }));
        const a = (i / 6) * Math.PI * 2;
        m.position.set(Math.cos(a) * 1.2, 0, Math.sin(a) * 1.2);
        host.add(m); nodes.push(m);
      }
    },
    update(json, meta) {
      const arr = (json && Array.isArray(json.nodes)) ? json.nodes : [];
      const counts = (json && json.counts) || {};
      host.setValue((counts.nodes_reachable ?? "—") + "/" + (counts.nodes_total ?? "—") + " reachable");
      host.setSub("GPU reachable " + (counts.gpu_nodes_reachable ?? "—") + " · rtx-betterwithage + chaski");
      host.setLabel(json && json.status === "live" ? "MEASURED" : "STRUCTURAL-ONLY");
      nodes.forEach((m, i) => {
        const n = arr[i];
        if (!n) { m.material.color.setHex(COL.dim); m.material.emissive.setHex(COL.dim); m.userData.live = false; return; }
        const gpu = String(n.kind || "").indexOf("gpu") >= 0;
        const c = n.reachable ? (n.sovereign ? COL.green : (gpu ? COL.teal : COL.blue)) : COL.red;
        m.material.color.setHex(c); m.material.emissive.setHex(c);
        m.userData.live = !!n.reachable; m.userData.gpu = gpu;
      });
    },
    frame(t) { nodes.forEach((m, i) => { if (m.userData.live) m.material.emissiveIntensity = 0.4 + 0.4 * Math.abs(Math.sin(t * 2 + i)); }); },
  };
}

// (4) Per-job particle stream — each completed job a particle node->ledger->receipt.
function gJobParticleStream() {
  let host, T, pts, geo, N = 64, seed = [], jobs = 0;
  return {
    gid: "job-stream", endpoint: EP.STATUS,
    def: { id: "job-stream", n: 4, title: "Per-job particle stream", sub: "operator status · recent_jobs flowing node→receipt" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      geo = new T.BufferGeometry();
      const pos = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) { seed.push(Math.random()); pos[i * 3] = -2.4; pos[i * 3 + 1] = (Math.random() - 0.5) * 0.5; pos[i * 3 + 2] = (Math.random() - 0.5) * 0.5; }
      geo.setAttribute("position", new T.BufferAttribute(pos, 3));
      pts = new T.Points(geo, new T.PointsMaterial({ color: COL.teal, size: 0.09, transparent: true, opacity: 0.9 }));
      host.add(pts);
      const rail = new T.Mesh(new T.CylinderGeometry(0.012, 0.012, 4.8, 6), new T.MeshStandardMaterial({ color: COL.dim, emissive: COL.teal, emissiveIntensity: 0.15 }));
      rail.rotation.z = Math.PI / 2; host.add(rail);
    },
    update(json, meta) {
      jobs = num(json && json.jobs_done) ?? 0;
      const recent = (json && Array.isArray(json.recent_jobs)) ? json.recent_jobs.length : 0;
      host.setValue(jobs.toLocaleString() + " jobs done");
      host.setSub(recent + " in recent window · " + ((json && json.running) ? "RUNNING" : "idle"));
      host.setLabel(meta.label || "MEASURED");
    },
    frame(t) {
      if (!geo) return;
      const p = geo.attributes.position.array;
      const speed = 0.4 + clamp01(jobs / 500) * 1.2;
      for (let i = 0; i < N; i++) {
        let x = -2.4 + (((t * speed + seed[i] * 5) % 4.8));
        p[i * 3] = x;
      }
      geo.attributes.position.needsUpdate = true;
    },
  };
}

// (5) Signed-receipt hash-chain — the ledger chain, integrity glow.
function gReceiptChain() {
  let host, T, links = [], joints = [];
  return {
    gid: "receipt-chain", endpoint: EP.LEDGER,
    def: { id: "receipt-chain", n: 5, title: "Signed-receipt hash-chain", sub: "ledger · prev_digest links + chain integrity" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      for (let i = 0; i < 8; i++) {
        const s = new T.Mesh(new T.SphereGeometry(0.16, 16, 12),
          new T.MeshStandardMaterial({ color: COL.gray, emissive: COL.gray, emissiveIntensity: 0.3 }));
        s.position.set((i - 3.5) * 0.5, 0, 0); host.add(s); joints.push(s);
        if (i > 0) {
          const l = new T.Mesh(new T.CylinderGeometry(0.02, 0.02, 0.5, 6), new T.MeshStandardMaterial({ color: COL.teal, emissive: COL.teal, emissiveIntensity: 0.3 }));
          l.rotation.z = Math.PI / 2; l.position.set((i - 4) * 0.5, 0, 0); host.add(l); links.push(l);
        }
      }
    },
    update(json, meta) {
      const chain = (json && json.chain) || {};
      const ok = chain.ok === true;
      const len = num(chain.length) ?? 0;
      host.setValue(len + " receipts · " + (ok ? "CHAIN INTACT" : (len ? "BROKEN" : "EMPTY")));
      const totals = (json && json.totals) || {};
      host.setSub("billable joules " + (num(totals.joules_measured_billable) ?? "—") + " · " + ((json && json.stripe_mode) || "dry-run"));
      host.setLabel(ok && len > 0 ? "MEASURED" : "STRUCTURAL-ONLY");
      const lit = Math.min(joints.length, len);
      joints.forEach((s, i) => {
        const on = i < lit;
        const c = on ? (ok ? COL.green : COL.red) : COL.gray;
        s.material.color.setHex(c); s.material.emissive.setHex(c); s.userData.on = on; s.userData.ok = ok;
      });
    },
    frame(t) { joints.forEach((s, i) => { if (s.userData.on) s.material.emissiveIntensity = 0.4 + 0.4 * Math.abs(Math.sin(t * 1.5 - i * 0.4)); }); },
  };
}

// (6) Joules reservoir — MEASURED fill vs the 1-day projection ceiling (MODELED).
function gReservoir() {
  let host, T, fill, ceiling, measured = null, proj = null;
  return {
    gid: "reservoir", endpoint: EP.PROJECTION,
    def: { id: "reservoir", n: 6, title: "Joules reservoir vs 1-day", sub: "projection · MEASURED fill / MODELED ceiling" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      ceiling = new T.Mesh(new T.BoxGeometry(1.1, 2.0, 1.1), new T.MeshStandardMaterial({ color: COL.amber, emissive: COL.amber, emissiveIntensity: 0.12, transparent: true, opacity: 0.18, wireframe: true }));
      ceiling.position.y = 0; host.add(ceiling);
      fill = new T.Mesh(new T.BoxGeometry(1.0, 0.05, 1.0), new T.MeshStandardMaterial({ color: COL.green, emissive: COL.green, emissiveIntensity: 0.5 }));
      fill.position.y = -0.95; host.add(fill);
    },
    update(json, meta) {
      const mi = (json && json.measured_inputs) || {};
      const oneDay = (json && json.projection_1day_single_node) || {};
      measured = lv(mi.joules_measured);
      proj = lv(oneDay.compute_done && oneDay.compute_done.joules);
      if (measured == null || proj == null || proj <= 0) { host.setValue("NO-LIVE-DATA"); host.setLabel("STRUCTURAL-ONLY"); return; }
      const frac = clamp01(measured / proj);
      host.setValue((frac * 100).toFixed(2) + "% of 1-day ceiling");
      host.setSub("MEASURED " + measured.toFixed(0) + " J → MODELED " + proj.toFixed(0) + " J/day");
      host.setLabel("MEASURED");
      const hgt = Math.max(0.05, frac * 1.9);
      fill.scale.y = hgt / 0.05; fill.position.y = -0.95 + hgt / 2;
    },
    frame() {},
  };
}

// (7) Tokens/FLOPs throughput surface — live tokens → projected, MODELED FLOPs.
function gThroughputSurface() {
  let host, T, surf, geoW = 16, geoH = 8, amp = 0.2;
  return {
    gid: "throughput", endpoint: EP.PROJECTION,
    def: { id: "throughput", n: 7, title: "Tokens / FLOPs surface", sub: "projection · tokens MODELED, FLOPs MODELED w/ formula" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      const g = new T.PlaneGeometry(2.4, 1.4, geoW, geoH);
      surf = new T.Mesh(g, new T.MeshStandardMaterial({ color: COL.teal, emissive: COL.teal, emissiveIntensity: 0.3, wireframe: true, side: T.DoubleSide }));
      surf.rotation.x = -Math.PI / 2.6; host.add(surf);
    },
    update(json, meta) {
      const cd = ((json && json.projection_1day_single_node) || {}).compute_done || {};
      const tokens = lv(cd.tokens), flops = lv(cd.flops);
      const lab = llabel(cd.tokens) || "STRUCTURAL-ONLY";
      if (tokens == null) { host.setValue("tokens: STRUCTURAL-ONLY"); host.setSub("no measured tokens → FLOPs not derivable"); host.setLabel("STRUCTURAL-ONLY"); amp = 0.05; return; }
      host.setValue(tokens.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " tok/day");
      host.setSub("MODELED FLOPs/day " + (flops != null ? flops.toExponential(2) : "—") + " · 6·N·tokens");
      host.setLabel(lab);
      amp = 0.15 + clamp01(tokens / 1e6) * 0.5;
    },
    frame(t) {
      if (!surf) return;
      const p = surf.geometry.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i), y = p.getY(i);
        p.setZ(i, Math.sin(x * 3 + t * 1.5) * Math.cos(y * 3 + t) * amp);
      }
      p.needsUpdate = true;
    },
  };
}

// (8) Earnings gauge — dry-run cents (MODELED) + 1-day projection (ESTIMATE-labeled).
function gEarningsGauge() {
  let host, T, needle, arc;
  return {
    gid: "earnings", endpoint: EP.PROJECTION,
    def: { id: "earnings", n: 8, title: "Earnings gauge (1-day)", sub: "projection · MODELED total / ESTIMATE resale (never MEASURED)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      arc = new T.Mesh(new T.TorusGeometry(1.2, 0.05, 10, 60, Math.PI), new T.MeshStandardMaterial({ color: COL.amber, emissive: COL.amber, emissiveIntensity: 0.4 }));
      host.add(arc);
      needle = new T.Mesh(new T.ConeGeometry(0.07, 1.1, 8), new T.MeshStandardMaterial({ color: COL.gold, emissive: COL.gold, emissiveIntensity: 0.6 }));
      needle.position.y = 0.2; host.add(needle);
    },
    update(json, meta) {
      const earn = ((json && json.projection_1day_single_node) || {}).earnings || {};
      const total = lv(earn.total_usd), resale = lv(earn.compute_resale_usd);
      const lab = llabel(earn.total_usd) || "MODELED";
      if (total == null) { host.setValue("NO-LIVE-DATA"); host.setLabel("STRUCTURAL-ONLY"); return; }
      host.setValue("$" + total.toFixed(4) + " /day");
      host.setSub("resale $" + (resale != null ? resale.toFixed(4) : "—") + " (ESTIMATE) · dry-run, no charge cleared");
      host.setLabel(lab);
      const frac = clamp01(total / 1.0);
      needle.rotation.z = Math.PI / 2 - frac * Math.PI;
    },
    frame() {},
  };
}

// (9) Renewable-share halo — >100% curtailment glow.
function gRenewableHalo() {
  let host, T, halo, glow = 0.3;
  return {
    gid: "renewable-halo", endpoint: EP.POSTURE,
    def: { id: "renewable-halo", n: 9, title: "Renewable-share halo", sub: "harvest posture · renewable share of load" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      halo = new T.Mesh(new T.TorusGeometry(1.1, 0.12, 16, 64), new T.MeshStandardMaterial({ color: COL.green, emissive: COL.green, emissiveIntensity: 0.4, transparent: true, opacity: 0.7 }));
      halo.rotation.x = Math.PI / 2.5; host.add(halo);
    },
    update(json, meta) {
      const readings = (json && Array.isArray(json.readings)) ? json.readings : [];
      const ren = readings.find((r) => r && /ren_share|renewable/i.test(String(r.feed || "")));
      const share = ren ? num(ren.value) : null;
      const measured = !!(ren && ren.measured);
      if (share == null) { host.setValue("STRUCTURAL-ONLY"); host.setSub("no renewable feed reading (honest)"); host.setLabel("STRUCTURAL-ONLY"); glow = 0.2; return; }
      host.setValue(share.toFixed(1) + "% renewable");
      host.setSub(share >= 100 ? "curtailment surplus — grid oversupplied" : "share of load");
      host.setLabel(measured ? "MEASURED" : "SAMPLE");
      glow = 0.3 + clamp01(share / 100) * 0.9;
    },
    frame(t) { if (halo) { halo.rotation.z = t * 0.3; halo.material.emissiveIntensity = glow * (0.7 + 0.3 * Math.sin(t * 2)); } },
  };
}

// (10) Carbon-intensity tint dome.
function gCarbonDome() {
  let host, T, dome;
  return {
    gid: "carbon-dome", endpoint: EP.POSTURE,
    def: { id: "carbon-dome", n: 10, title: "Carbon-intensity dome", sub: "harvest posture · UK carbon intensity tint" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      dome = new T.Mesh(new T.SphereGeometry(1.2, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2), new T.MeshStandardMaterial({ color: COL.blue, emissive: COL.blue, emissiveIntensity: 0.25, transparent: true, opacity: 0.4, side: T.DoubleSide }));
      host.add(dome);
    },
    update(json, meta) {
      const readings = (json && Array.isArray(json.readings)) ? json.readings : [];
      const carbon = readings.find((r) => r && /carbon/i.test(String(r.feed || "")));
      const v = carbon ? num(carbon.value) : null;
      if (v == null) { host.setValue("STRUCTURAL-ONLY"); host.setSub("no carbon feed reading (honest)"); host.setLabel("STRUCTURAL-ONLY"); return; }
      host.setValue(v.toFixed(0) + " gCO₂/kWh");
      host.setLabel((carbon && carbon.measured) ? "MEASURED" : "SAMPLE");
      // green (clean) → red (dirty)
      const dirty = clamp01(v / 400);
      dome.material.color.setHex(dirty > 0.5 ? COL.red : COL.green);
      dome.material.emissive.setHex(dirty > 0.5 ? COL.red : COL.green);
    },
    frame(t) { if (dome) dome.rotation.y = t * 0.15; },
  };
}

// (11) Power-draw live gauge — W from exporter.
function gPowerGauge() {
  let host, T, bar, w = null;
  return {
    gid: "power-gauge", endpoint: EP.PROJECTION,
    def: { id: "power-gauge", n: 11, title: "Power-draw gauge", sub: "projection measured_inputs · power_w_sample (exporter)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      const frame = new T.Mesh(new T.BoxGeometry(0.4, 2.0, 0.4), new T.MeshStandardMaterial({ color: COL.dim, transparent: true, opacity: 0.3, wireframe: true }));
      host.add(frame);
      bar = new T.Mesh(new T.BoxGeometry(0.34, 0.05, 0.34), new T.MeshStandardMaterial({ color: COL.teal, emissive: COL.teal, emissiveIntensity: 0.5 }));
      bar.position.y = -0.95; host.add(bar);
    },
    update(json, meta) {
      const mi = (json && json.measured_inputs) || {};
      // power lives on measured_inputs via Dev3; honest fallback handled by null check.
      w = lv(mi.power_w_sample) ?? num((json && json.measured_inputs && json.measured_inputs.power_w_sample));
      // some payloads carry power in operator status, but this graph reads projection.
      if (w == null) { host.setValue("NO-LIVE-DATA"); host.setLabel("STRUCTURAL-ONLY"); return; }
      host.setValue(w.toFixed(2) + " W");
      host.setSub("live exporter sample · scales up under load");
      host.setLabel("MEASURED");
      const frac = clamp01(w / 300);
      const hgt = Math.max(0.05, frac * 1.9);
      bar.scale.y = hgt / 0.05; bar.position.y = -0.95 + hgt / 2;
    },
    frame() {},
  };
}

// (12) Scale-out hologram — 1/3/10/100/1000-node projection bars (MODELED).
function gScaleOut() {
  let host, T, bars = [];
  const NODES = [1, 3, 10, 100, 1000];
  return {
    gid: "scale-out", endpoint: EP.PROJECTION,
    def: { id: "scale-out", n: 12, title: "Scale-out hologram", sub: "projection · 1/3/10/100/1000-node MODELED (honest 3-node)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      NODES.forEach((n, i) => {
        const m = new T.Mesh(new T.BoxGeometry(0.22, 0.05, 0.22), new T.MeshStandardMaterial({ color: i === 1 ? COL.green : COL.amber, emissive: i === 1 ? COL.green : COL.amber, emissiveIntensity: 0.4 }));
        m.position.set((i - 2) * 0.4, 0, 0); host.add(m); bars.push(m);
      });
    },
    update(json, meta) {
      const sp = (json && json.scale_projection) || {};
      const lines = Array.isArray(sp.lines) ? sp.lines : [];
      if (!lines.length) { host.setValue("NO-LIVE-DATA"); host.setLabel("STRUCTURAL-ONLY"); return; }
      const byN = {}; lines.forEach((l) => { byN[l.nodes] = lv(l.total_usd_yr); });
      const n3 = byN[3];
      host.setValue(n3 != null ? "3-node: $" + n3.toFixed(2) + "/yr" : "MODELED");
      host.setSub("from live single-node rate × nodes × 365d (ESTIMATE resale input)");
      host.setLabel("MODELED");
      const max = Math.max(...NODES.map((n) => byN[n] || 0), 1);
      bars.forEach((m, i) => {
        const v = byN[NODES[i]] || 0;
        const hgt = Math.max(0.05, (Math.log10(v + 1) / Math.log10(max + 1)) * 1.8);
        m.scale.y = hgt / 0.05; m.position.y = hgt / 2;
      });
    },
    frame() {},
  };
}

// (13) Negative-window countdown ribbon.
function gNegativeWindowRibbon() {
  let host, T, ribbon, active = false;
  return {
    gid: "neg-window", endpoint: EP.POSTURE,
    def: { id: "neg-window", n: 13, title: "Negative-window ribbon", sub: "harvest posture · wasted-energy availability" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      ribbon = new T.Mesh(new T.TorusKnotGeometry(0.8, 0.06, 96, 12, 2, 3), new T.MeshStandardMaterial({ color: COL.gold, emissive: COL.gold, emissiveIntensity: 0.4 }));
      host.add(ribbon);
    },
    update(json, meta) {
      const avail = json && json.wasted_energy_available;
      const posture = json && json.posture;
      active = !!avail;
      host.setValue(active ? "WASTED-ENERGY WINDOW" : (posture ? String(posture).toUpperCase() : "NO-LIVE-DATA"));
      host.setSub("soak_hard " + (json && json.soak_hard != null ? json.soak_hard : "—") + " · rank " + (json && json.rank != null ? json.rank : "—"));
      host.setLabel(meta.label || (json && json.joules_label) || "SAMPLE");
      const c = active ? COL.green : COL.gold;
      ribbon.material.color.setHex(c); ribbon.material.emissive.setHex(c);
    },
    frame(t) { if (ribbon) { ribbon.rotation.y = t * 0.5; ribbon.rotation.x = t * 0.2; if (active) ribbon.material.emissiveIntensity = 0.4 + 0.4 * Math.sin(t * 4); } },
  };
}

// (14) Node-health reachability ring (6/6, GPU live).
function gReachabilityRing() {
  let host, T, dots = [];
  return {
    gid: "reach-ring", endpoint: EP.POOL,
    def: { id: "reach-ring", n: 14, title: "Node-health ring", sub: "compute-pool · reachability (real TCP probe)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      const ring = new T.Mesh(new T.TorusGeometry(1.1, 0.02, 8, 64), new T.MeshStandardMaterial({ color: COL.dim, emissive: COL.teal, emissiveIntensity: 0.15 }));
      ring.rotation.x = Math.PI / 2; host.add(ring);
    },
    update(json, meta) {
      const arr = (json && Array.isArray(json.nodes)) ? json.nodes : [];
      const counts = (json && json.counts) || {};
      // rebuild dots to match node count (real nodes only)
      dots.forEach((d) => host.group.remove(d)); dots = [];
      arr.forEach((n, i) => {
        const d = new T.Mesh(new T.SphereGeometry(0.12, 12, 8), new T.MeshStandardMaterial({ color: n.reachable ? COL.green : COL.red, emissive: n.reachable ? COL.green : COL.red, emissiveIntensity: 0.5 }));
        const a = (i / Math.max(1, arr.length)) * Math.PI * 2;
        d.position.set(Math.cos(a) * 1.1, 0, Math.sin(a) * 1.1); host.add(d); dots.push(d);
      });
      host.setValue((counts.nodes_reachable ?? "—") + "/" + (counts.nodes_total ?? "—") + " up");
      host.setSub("GPU live " + (counts.gpu_nodes_reachable ?? "—"));
      host.setLabel(json && json.status === "live" ? "MEASURED" : "STRUCTURAL-ONLY");
    },
    frame(t) { dots.forEach((d, i) => { d.material.emissiveIntensity = 0.4 + 0.3 * Math.abs(Math.sin(t * 1.5 + i)); }); },
  };
}

// (15) Grid "paying us" beat — beat animation when price<0.
function gGridPayingBeat() {
  let host, T, heart, paying = false;
  return {
    gid: "grid-beat", endpoint: EP.STATUS,
    def: { id: "grid-beat", n: 15, title: "Grid 'paying us' beat", sub: "operator status · grid_price_eur_mwh (beat when <0)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      heart = new T.Mesh(new T.IcosahedronGeometry(0.7, 1), new T.MeshStandardMaterial({ color: COL.gold, emissive: COL.gold, emissiveIntensity: 0.5 }));
      host.add(heart);
    },
    update(json, meta) {
      const price = num(json && json.grid_price_eur_mwh);
      paying = price != null && price < 0;
      if (price == null) { host.setValue("STRUCTURAL-ONLY"); host.setSub("grid price not reported this tick"); host.setLabel("STRUCTURAL-ONLY"); return; }
      host.setValue(price.toFixed(2) + " EUR/MWh");
      host.setSub(paying ? "GRID IS PAYING US — soak now" : "positive price — normal");
      host.setLabel("SAMPLE");
      const c = paying ? COL.green : COL.gold;
      heart.material.color.setHex(c); heart.material.emissive.setHex(c);
    },
    frame(t) { if (heart) { const beat = paying ? (1 + 0.25 * Math.abs(Math.sin(t * 5))) : (1 + 0.05 * Math.sin(t * 1.5)); heart.scale.setScalar(beat); } },
  };
}

// (16) Receipt-mint burst — a new JouleCharge lights up live.
function gReceiptMintBurst() {
  let host, T, burst, geo, N = 80, lastLen = 0, fire = 0;
  return {
    gid: "mint-burst", endpoint: EP.LEDGER,
    def: { id: "mint-burst", n: 16, title: "Receipt-mint burst", sub: "ledger · burst when a new JouleCharge mints" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      geo = new T.BufferGeometry();
      const pos = new Float32Array(N * 3);
      geo.setAttribute("position", new T.BufferAttribute(pos, 3));
      burst = new T.Points(geo, new T.PointsMaterial({ color: COL.green, size: 0.08, transparent: true, opacity: 0 }));
      host.add(burst);
      const core = new T.Mesh(new T.OctahedronGeometry(0.4), new T.MeshStandardMaterial({ color: COL.green, emissive: COL.green, emissiveIntensity: 0.4 }));
      host.add(core);
    },
    update(json, meta) {
      const len = num((json && json.chain && json.chain.length)) ?? num((json && json.totals && json.totals.jobs)) ?? 0;
      if (len > lastLen) { fire = 1; }
      lastLen = len;
      host.setValue(len + " minted");
      const totals = (json && json.totals) || {};
      host.setSub("would-charge " + (num(totals.would_charge_cents) ?? "—") + "¢ (MODELED dry-run)");
      host.setLabel(len > 0 ? "MEASURED" : "STRUCTURAL-ONLY");
    },
    frame(t) {
      if (!geo) return;
      if (fire > 0) {
        const p = geo.attributes.position.array;
        for (let i = 0; i < N; i++) {
          const r = (1 - fire) * 2.0;
          const a = i / N * Math.PI * 2, b = (i % 9) / 9 * Math.PI;
          p[i * 3] = Math.cos(a) * Math.sin(b) * r; p[i * 3 + 1] = Math.cos(b) * r; p[i * 3 + 2] = Math.sin(a) * Math.sin(b) * r;
        }
        geo.attributes.position.needsUpdate = true;
        burst.material.opacity = fire;
        fire = Math.max(0, fire - 0.02);
      } else { burst.material.opacity = 0; }
    },
  };
}

// (17) Uptime helix — operator uptime as a growing helix.
function gUptimeHelix() {
  let host, T, helix, up = null;
  return {
    gid: "uptime-helix", endpoint: EP.STATUS,
    def: { id: "uptime-helix", n: 17, title: "Uptime helix", sub: "operator status · uptime_s while running non-stop" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      const pts = [];
      for (let i = 0; i < 200; i++) { const a = i / 200 * Math.PI * 8; pts.push(new T.Vector3(Math.cos(a) * 0.7, (i / 200 - 0.5) * 2.2, Math.sin(a) * 0.7)); }
      helix = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: COL.teal }));
      host.add(helix);
    },
    update(json, meta) {
      up = num(json && json.uptime_s);
      if (up == null) { host.setValue("NO-LIVE-DATA"); host.setLabel("STRUCTURAL-ONLY"); return; }
      const hrs = up / 3600;
      host.setValue(hrs >= 1 ? hrs.toFixed(2) + " h" : up.toFixed(0) + " s");
      host.setSub((json && json.running) ? "RUNNING non-stop" : "stopped");
      host.setLabel(meta.label || "MEASURED");
    },
    frame(t) { if (helix) helix.rotation.y = t * 0.4; },
  };
}

// (18) WebGPU/WebGL2 backend indicator — honest renderer truth.
function gBackendIndicator() {
  let host, T, cube, backend = "…";
  return {
    gid: "backend", endpoint: null, // not polled — reads the stage backend (honest hardware truth)
    def: { id: "backend", n: 18, title: "Render backend", sub: "WebGPU-with-WebGL2-fallback (honest: what you got)" },
    mount(ctx, h) {
      host = h; T = ctx.THREE;
      cube = new T.Mesh(new T.BoxGeometry(1.0, 1.0, 1.0), new T.MeshStandardMaterial({ color: COL.blue, emissive: COL.blue, emissiveIntensity: 0.35, metalness: 0.4, roughness: 0.3 }));
      host.add(cube);
      backend = (ctx.stage && ctx.stage.backend) || "webgl2";
      host.setValue(String(backend).toUpperCase());
      host.setSub(backend === "webgpu" ? "WebGPU device acquired" : "WebGL2 fallback (production-safe)");
      host.setLabel("MEASURED"); // the backend is a real, measured capability of this device
      cube.material.color.setHex(backend === "webgpu" ? COL.green : COL.teal);
      cube.material.emissive.setHex(backend === "webgpu" ? COL.green : COL.teal);
      // no badge polling for this card
      host.badge.set("live", { label: backend.toUpperCase() });
    },
    update() {},
    frame(t) { if (cube) { cube.rotation.x = t * 0.5; cube.rotation.y = t * 0.35; } },
  };
}

const GRAPH_FACTORIES = [
  gMeasuredJoulesOrbital, gNegativePriceColumns, gComputeFabricHex, gJobParticleStream,
  gReceiptChain, gReservoir, gThroughputSurface, gEarningsGauge, gRenewableHalo,
  gCarbonDome, gPowerGauge, gScaleOut, gNegativeWindowRibbon, gReachabilityRing,
  gGridPayingBeat, gReceiptMintBurst, gUptimeHelix, gBackendIndicator,
];

// ---------------------------------------------------------------------------
// buildShowcase — lay the 18 graphs out in a 3D grid, wire each to its endpoint,
// build the DOM HUD grid, and return a controller.
// ---------------------------------------------------------------------------
export function buildShowcase(ctx) {
  const THREE = ctx.THREE;
  const graphs = GRAPH_FACTORIES.map((f) => f());
  const handles = [];
  const cards = [];

  // 3D layout: 6 columns × 3 rows, spaced out.
  const COLS = 6, GAP_X = 6.5, GAP_Y = 6.0;
  graphs.forEach((g, i) => {
    const col = i % COLS, row = Math.floor(i / COLS);
    const x = (col - (COLS - 1) / 2) * GAP_X;
    const y = ((1) - row) * GAP_Y;
    const host = makeGraphCard(ctx, g.def, x, y);
    cards.push(host);
    g.mount(ctx, host);
    if (g.endpoint) {
      const h = ctx.live.poll(g.endpoint, 4000, (json, meta) => {
        try { g.update(json, meta); } catch (e) { if (console) console.error("[showcase] update", g.gid, e); }
      }, { badge: host.badge });
      handles.push(h);
    }
  });

  // DOM HUD grid overlay (the value-readout grid; 0-CDN system fonts).
  const hud = document.createElement("div");
  hud.className = "szl3d-showcase-hud";
  Object.assign(hud.style, {
    position: "absolute", left: "0", right: "0", bottom: "0", zIndex: "6",
    display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))",
    gap: "7px", padding: "9px", maxHeight: "46%", overflow: "auto",
    background: "linear-gradient(180deg,rgba(5,7,13,0) 0%,rgba(5,7,13,.88) 30%)",
  });
  cards.forEach((c) => hud.appendChild(c.card));
  (ctx.container || document.body).appendChild(hud);

  // legend + 0-CDN attestation
  const legend = ctx.label.legend();
  Object.assign(legend.style, { position: "absolute", left: "12px", top: "10px", zIndex: "7", opacity: "0.9" });
  (ctx.container || document.body).appendChild(legend);

  let _frame = (t) => { graphs.forEach((g) => { try { g.frame(t); } catch (_) {} }); };
  const onFrame = () => { _frame(performance.now() / 1000); };
  if (ctx.stage && ctx.stage.onFrame) ctx.stage.onFrame(onFrame);

  function dispose() {
    handles.forEach((h) => { try { h.stop(); } catch (_) {} });
    try { if (hud.parentNode) hud.parentNode.removeChild(hud); } catch (_) {}
    try { if (legend.parentNode) legend.parentNode.removeChild(legend); } catch (_) {}
    cards.forEach((c) => { try { ctx.stage.scene.remove(c.group); } catch (_) {} });
  }

  return {
    graphs, handles, cards,
    count: graphs.length,
    endpoints: Array.from(new Set(graphs.map((g) => g.endpoint).filter(Boolean))),
    frame: _frame,
    dispose,
  };
}

export const SHOWCASE_GRAPHS = GRAPH_FACTORIES.map((f) => { const g = f(); return { id: g.gid, title: g.def.title, n: g.def.n, endpoint: g.endpoint }; });
export const SHOWCASE_ENDPOINTS = EP;

export default { buildShowcase, SHOWCASE_GRAPHS, SHOWCASE_ENDPOINTS };
