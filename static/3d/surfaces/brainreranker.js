// SPDX-License-Identifier: Apache-2.0
// Anatomy v6 — measured-state Brain evidence inventory and reranker readiness.
// No mock nodes: geometry is created only from /brain/reranker/inventory records.
// Receipt-linked edges/pulses appear only after a real local feed receipt exists.

import { createShowcase } from "./_showcase.js";

const ID = "brainreranker";
const TITLE = "Anatomy v6 · Brain evidence and reranker readiness";
const STATUS_EP = "/api/a11oy/v1/brain/reranker/status";
const INVENTORY_EP = "/api/a11oy/v1/brain/reranker/inventory?offset=0&limit=220";
const REFRESH_EP = "/api/a11oy/v1/brain/reranker/feed/refresh";

let stage, THREE, group, show, badge, frameRegistered = false, t = 0;
let nodeMeshes = [], edgeLines = [], pulses = [], overlay;
const state = { status: null, inventory: null, mode: "loading", error: null };

function colorFor(row) {
  if (row.admission_decision === "ADMITTED_TO_CANONICAL_MAP") return 0x3af4c8;
  if ((row.reason_codes || []).includes("DUPLICATE_CANONICAL_KEY")) return 0x5b8dee;
  if (row.freshness_basis === "UNVERIFIED") return 0xd2a847;
  return 0x8494a1;
}

function sourceRegions(rows) {
  const names = [...new Set(rows.map(r => r.source_family || "UNKNOWN"))].sort();
  const out = new Map();
  names.forEach((name, i) => {
    const a = (i / Math.max(1, names.length)) * Math.PI * 2;
    const ring = 4.4 + (i % 3) * 1.7;
    out.set(name, new THREE.Vector3(Math.cos(a) * ring, Math.sin(a) * ring * 0.62,
                                    ((i % 5) - 2) * 0.9));
  });
  return out;
}

function rebuild() {
  while (group && group.children.length) {
    const obj = group.children.pop();
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) obj.material.dispose();
  }
  nodeMeshes = []; edgeLines = []; pulses = [];
  const rows = (state.inventory && state.inventory.decisions) || [];
  if (!rows.length || !group) return;
  const regions = sourceRegions(rows);
  const byId = new Map();
  rows.forEach((row, i) => {
    const center = regions.get(row.source_family || "UNKNOWN");
    const a = i * 2.399963229728653;
    const local = 0.28 + 0.055 * Math.sqrt(i + 1);
    const pos = center.clone().add(new THREE.Vector3(Math.cos(a) * local,
      Math.sin(a) * local * 0.72, Math.sin(a * 0.41) * 0.65));
    const geo = new THREE.SphereGeometry(row.deduplicated ? 0.095 : 0.14, 8, 6);
    const mat = new THREE.MeshStandardMaterial({ color: colorFor(row),
      emissive: colorFor(row), emissiveIntensity: 0.18, roughness: 0.46 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(pos);
    mesh.userData = { row, title: row.brain_node_id + " · " + row.admission_decision };
    group.add(mesh); nodeMeshes.push(mesh); byId.set(row.brain_node_id, mesh);
  });

  // Verified pathways are data-backed dedupe lineage only. No decorative edges.
  rows.forEach((row) => {
    if (!row.deduplicated) return;
    const a = byId.get(row.brain_node_id), b = byId.get(row.canonical_node_id);
    if (!a || !b) return;
    const geo = new THREE.BufferGeometry().setFromPoints([a.position, b.position]);
    const mat = new THREE.LineBasicMaterial({ color: 0x5b8dee, transparent: true, opacity: 0.42 });
    const line = new THREE.Line(geo, mat); group.add(line); edgeLines.push(line);
  });

  // Receipt-linked synapses/pulses exist only when a written feed receipt is present.
  const feed = state.status && state.status.feed;
  const receipt = feed && feed.last_successful_receipt;
  if (receipt && receipt !== "UNKNOWN") {
    edgeLines.slice(0, 64).forEach((line, i) => {
      const pts = line.geometry.attributes.position;
      const p = new THREE.Mesh(new THREE.SphereGeometry(0.055, 6, 5),
        new THREE.MeshBasicMaterial({ color: 0x3af4c8 }));
      p.userData = { edge: line, phase: i / Math.max(1, edgeLines.length), receipt };
      p.position.set(pts.getX(0), pts.getY(0), pts.getZ(0)); group.add(p); pulses.push(p);
    });
  }
}

function value(v) { return v == null ? "UNKNOWN" : String(v); }
function paint() {
  if (!overlay) return;
  const s = state.status || {}, inv = s.inventory || {}, ds = s.dataset || {};
  const feed = s.feed || {}, model = s.model || {}, evaluation = s.evaluation || {};
  overlay.querySelector("[data-v=status]").textContent = value(s.status || state.mode);
  overlay.querySelector("[data-v=raw]").textContent = value(inv.raw_node_count);
  overlay.querySelector("[data-v=rendered]").textContent = value(
    state.inventory && state.inventory.decisions ? state.inventory.decisions.length : 0
  ) + " / " + value(state.inventory && state.inventory.total);
  overlay.querySelector("[data-v=decisions]").textContent = value(inv.decision_count);
  overlay.querySelector("[data-v=canonical]").textContent = value(inv.canonical_node_count);
  overlay.querySelector("[data-v=quarantine]").textContent = value(inv.quarantined_node_count);
  overlay.querySelector("[data-v=dataset]").textContent = value(ds.status) + " · " + value(ds.row_count) + " rows";
  overlay.querySelector("[data-v=model]").textContent = value(model.status);
  overlay.querySelector("[data-v=eval]").textContent = value(evaluation.status);
  overlay.querySelector("[data-v=loop]").textContent = value(feed.status) + " · " + value(feed.checkpoint);
  overlay.querySelector("[data-v=receipt]").textContent = value(feed.last_successful_receipt);
  overlay.querySelector("[data-v=next]").textContent = value(feed.next_refresh_utc);
  overlay.querySelector("[data-v=note]").textContent = state.error ||
    ((ds.reasons || []).join(" | ") || "No readiness claim exceeds the receipts shown here.");
  if (show) {
    show.setChip("state", s.status || "UNAVAILABLE", { text: "dataset" });
    show.setChip("nodes", s.inventory_label || "UNAVAILABLE", {
      text: "raw nodes " + (inv.raw_node_count == null ? "UNKNOWN" : String(inv.raw_node_count))
    });
  }
}

function buildOverlay(ctx) {
  show = createShowcase(ctx, { id: ID, title: TITLE, chips: [
    { name: "state", label: "UNAVAILABLE", text: "dataset" },
    { name: "nodes", label: "UNAVAILABLE", text: "raw nodes" },
  ] });
  overlay = document.createElement("div");
  overlay.style.cssText = "position:absolute;right:16px;top:70px;width:min(420px,44vw);max-height:calc(100vh - 110px);overflow:auto;background:rgba(5,11,17,.94);border:1px solid #263746;border-radius:10px;padding:12px;color:#dbe6ed;font:11px ui-monospace,monospace;z-index:5";
  const fields = [
    ["status","service readiness"],["raw","raw graph nodes"],["rendered","rendered page"],
    ["decisions","node decisions"],
    ["canonical","canonical map"],["quarantine","quarantined"],["dataset","proposal dataset"],
    ["model","model readiness"],["eval","evaluation readiness"],["loop","Ouroboros loop"],
    ["receipt","last written receipt"],["next","next refresh"]
  ];
  const title = document.createElement("div"); title.textContent = "ANATOMY v6 · RECEIPT STATE";
  title.style.cssText = "color:#3af4c8;font-weight:700;margin-bottom:8px"; overlay.appendChild(title);
  fields.forEach(([id,label]) => {
    const row = document.createElement("div"); row.style.cssText = "display:grid;grid-template-columns:150px 1fr;gap:8px;padding:4px 0;border-bottom:1px solid #12202b";
    const k = document.createElement("span"); k.textContent = label; k.style.color = "#8fa3af";
    const v = document.createElement("b"); v.dataset.v = id; v.textContent = "UNKNOWN"; v.style.overflowWrap = "anywhere";
    row.append(k,v); overlay.appendChild(row);
  });
  const note = document.createElement("div"); note.dataset.v = "note";
  note.style.cssText = "margin-top:8px;color:#d2a847;line-height:1.45"; overlay.appendChild(note);
  const button = document.createElement("button"); button.textContent = "run bounded local refresh";
  button.style.cssText = "margin-top:9px;background:#09141c;border:1px solid #5b8dee;border-radius:6px;color:#bcd0ff;padding:6px 9px;font:10px ui-monospace;cursor:pointer";
  button.onclick = async () => {
    button.disabled = true; button.textContent = "refreshing local evidence…";
    try {
      const r = await fetch(REFRESH_EP, { method: "POST", headers: { accept: "application/json" } });
      const j = await r.json(); state.error = j.reason || j.note || (r.ok ? null : "refresh refused honestly");
      await load();
    } catch (_) { state.error = "local refresh unavailable"; paint(); }
    finally { button.disabled = false; button.textContent = "run bounded local refresh"; }
  };
  overlay.appendChild(button);
  ctx.container.appendChild(overlay);
}

async function load() {
  try {
    const [sr, ir] = await Promise.all([fetch(STATUS_EP), fetch(INVENTORY_EP)]);
    state.status = await sr.json(); state.inventory = await ir.json(); state.mode = "live";
    if (badge && badge.set) badge.set("live"); rebuild(); paint();
  } catch (e) {
    state.mode = "error"; state.error = "API unavailable; no visual state fabricated";
    if (badge && badge.set) badge.set("error"); rebuild(); paint();
  }
}

export function mount(ctx) {
  stage = ctx.stage; THREE = ctx.THREE; group = new THREE.Group(); stage.scene.add(group);
  buildOverlay(ctx); if (ctx.live && ctx.live.createBadge) badge = ctx.live.createBadge();
  load();
  if (!frameRegistered && stage.onFrame) { stage.onFrame(animate); frameRegistered = true; }
}

function animate(dt) {
  t += Number(dt || 0.016); if (group) group.rotation.y = Math.sin(t * 0.09) * 0.08;
  pulses.forEach((p) => {
    const a = p.userData.edge.geometry.attributes.position;
    p.userData.phase = (p.userData.phase + 0.007) % 1;
    const q = p.userData.phase;
    p.position.set(a.getX(0) + (a.getX(1)-a.getX(0))*q,
                   a.getY(0) + (a.getY(1)-a.getY(0))*q,
                   a.getZ(0) + (a.getZ(1)-a.getZ(0))*q);
  });
}

export function unmount() {
  try { if (show) show.destroy(); } catch (_) {}
  try { if (overlay) overlay.remove(); } catch (_) {}
  try { if (group && stage) stage.scene.remove(group); } catch (_) {}
  stage = THREE = group = show = badge = overlay = null; nodeMeshes = []; edgeLines = []; pulses = [];
}
