// SPDX-License-Identifier: Apache-2.0
// A11oy Numerics Dataset — preregistered cases and append-only run evidence.
// Read-only UI: it never executes an engine or writes a result.

import { createShowcase } from "./_showcase.js";

const ID = "numericsdataset";
const TITLE = "Numerics Dataset · frozen inputs vs run evidence";
const STATUS_EP = "/api/a11oy/v1/numerics/dataset/status";
const CASES_EP = "/api/a11oy/v1/numerics/dataset/cases?limit=100";
const RESULTS_EP = "/api/a11oy/v1/numerics/dataset/results?limit=100";
const CURRICULUM_EP = "/api/a11oy/v1/numerics/dataset/curriculum/formulas";
const COLORS = {
  frozen: 0x5b8dee,
  match: 0x3af4c8,
  conflict: 0xe8c074,
  unavailable: 0x42505d,
  frame: 0x1b3a44,
};

let stage = null;
let THREE = null;
let group = null;
let showcase = null;
let badge = null;
let polls = [];
let meshes = [];
let elements = {};
let frameRegistered = false;
let cases = [];
let results = [];
let status = null;
let curriculum = null;
let liveState = "init";

function stateColor(token) {
  if (token === "MATCH") return COLORS.match;
  if (token === "CONFLICT" || token === "REFUSED") return COLORS.conflict;
  if (token === "UNAVAILABLE") return COLORS.unavailable;
  return COLORS.frozen;
}

function clearMeshes() {
  meshes.forEach((mesh) => {
    try {
      group.remove(mesh);
      if (mesh.geometry) mesh.geometry.dispose();
      if (mesh.material) mesh.material.dispose();
    } catch (_) {}
  });
  meshes = [];
}

function rebuildScene() {
  if (!group || !THREE) return;
  clearMeshes();
  const families = [...new Set(cases.map((item) => item.matrix_family))];
  families.forEach((family, index) => {
    const familyCases = cases.filter((item) => item.matrix_family === family);
    const measuredRows = results.filter((row) => {
      const linked = cases.find((item) => item.case_id === row.case_id);
      return linked && linked.matrix_family === family && row.row_state === "RESULT";
    });
    const conflictRows = results.filter((row) => {
      const linked = cases.find((item) => item.case_id === row.case_id);
      return linked && linked.matrix_family === family && row.comparison_state === "CONFLICT";
    });
    const x = (index - (families.length - 1) / 2) * 2.4;
    const frozenHeight = Math.max(0.6, Math.min(5.5, familyCases.length / 24));
    const frozen = new THREE.Mesh(
      new THREE.BoxGeometry(1.25, frozenHeight, 1.25),
      new THREE.MeshStandardMaterial({
        color: COLORS.frozen,
        emissive: COLORS.frozen,
        emissiveIntensity: 0.18,
        transparent: true,
        opacity: 0.74,
      }),
    );
    frozen.position.set(x, frozenHeight / 2, 0);
    group.add(frozen);
    meshes.push(frozen);

    const evidenceHeight = measuredRows.length ? Math.max(0.35, Math.min(4.5, measuredRows.length / 3)) : 0.18;
    const evidenceColor = conflictRows.length ? COLORS.conflict : (measuredRows.length ? COLORS.match : COLORS.unavailable);
    const evidence = new THREE.Mesh(
      new THREE.BoxGeometry(0.55, evidenceHeight, 0.55),
      new THREE.MeshStandardMaterial({
        color: evidenceColor,
        emissive: evidenceColor,
        emissiveIntensity: measuredRows.length ? 0.42 : 0.08,
        transparent: true,
        opacity: measuredRows.length ? 0.92 : 0.38,
      }),
    );
    evidence.position.set(x, evidenceHeight / 2, 1.15);
    group.add(evidence);
    meshes.push(evidence);
  });
}

function setText(id, value) {
  if (elements[id]) elements[id].textContent = value == null ? "—" : String(value);
}

function paintOverlay() {
  const prereg = status && status.preregistration;
  const ledger = status && status.result_ledger;
  const runtime = status && status.local_runtime;
  const curriculumCounts = curriculum && curriculum.counts;
  const counts = (ledger && ledger.classification_counts) || {};
  const token = liveState === "live" ? null : (liveState === "missing" ? "NO-LIVE-DATA" : "UNAVAILABLE");
  if (showcase) {
    showcase.setChip("design", token || (prereg && prereg.inputs_frozen ? "FROZEN" : "UNAVAILABLE"), { text: "input design" });
    showcase.setChip("evidence", token || ((ledger && ledger.row_count) ? "INGESTED" : "NO RESULTS"), { text: "run ledger" });
  }
  setText("nd-service", token || (status && status.service_state));
  setText("nd-cases", token || (prereg && prereg.case_count));
  setText("nd-confirm", token || (prereg && prereg.confirmatory_case_count));
  setText("nd-explore", token || (prereg && prereg.exploratory_case_count));
  setText("nd-rows", token || (ledger && ledger.row_count));
  setText("nd-match", token || (counts.MATCH || 0));
  setText("nd-conflict", token || (counts.CONFLICT || 0));
  setText("nd-unavailable", token || (counts.UNAVAILABLE || 0));
  setText("nd-ingest", token || (ledger && ledger.ingest_gate));
  setText("nd-octave", token || (runtime && runtime.octave));
  setText("nd-matlab", token || (runtime && runtime.matlab));
  setText("nd-network", token || (runtime && runtime.network_denial_evidence));
  setText("nd-formulas", token || (curriculumCounts && curriculumCounts.eligible));
  setText("nd-quarantine", token || (curriculumCounts && curriculumCounts.quarantined));
  setText("nd-families", token || (curriculumCounts && curriculumCounts.source_families));
  if (elements["nd-results"]) {
    elements["nd-results"].innerHTML = "";
    if (!results.length) {
      const empty = document.createElement("div");
      empty.style.color = "#8494a1";
      empty.textContent = "No run rows. Frozen cases are not measurements and are not displayed as successes.";
      elements["nd-results"].appendChild(empty);
    } else {
      results.slice(0, 12).forEach((row) => {
        const line = document.createElement("div");
        line.style.cssText = "display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid #14222d";
        const left = document.createElement("span");
        left.style.cssText = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:66%;color:#c9d6df";
        left.textContent = `${row.engine || "?"} · ${row.case_id || "?"}`;
        const right = document.createElement("b");
        const color = `#${stateColor(row.comparison_state).toString(16).padStart(6, "0")}`;
        right.style.color = color;
        right.textContent = row.comparison_state || row.row_state || "UNKNOWN";
        line.append(left, right);
        elements["nd-results"].appendChild(line);
      });
    }
  }
}

function buildOverlay(ctx) {
  showcase = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    accent: "#5b8dee",
    badge,
    chips: [
      { label: "FROZEN", text: "input design", name: "design" },
      { label: "NO RESULTS", text: "run ledger", name: "evidence" },
    ],
    legend: ["FROZEN INPUT", "MEASURED", "CONFLICT", "UNAVAILABLE"],
  });
  const intro = document.createElement("div");
  intro.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  intro.innerHTML =
    "The blue towers are <b>preregistered inputs</b>: fixed families, dimensions, condition strata, seeds, and operations. " +
    "They are not engine results. The narrow towers are append-only run evidence and remain grey until an authenticated, " +
    "network-denied run receipt is ingested. MATLAB and Octave stay UNAVAILABLE when their real runtime evidence is absent. " +
    "MATCH means bounded agreement for one case only; proof/trust uplift is always zero.";
  const curriculumNote = document.createElement("div");
  curriculumNote.style.cssText = "color:#8195a5;font-size:10px;line-height:1.45;border-left:2px solid #5b8dee;padding-left:8px";
  curriculumNote.textContent =
    "The Brain curriculum bridge carries all F1-F23 formula IDs, honest statuses, source-family splits, and content hashes. " +
    "Missing per-formula proof/refutation receipts stay null; unsupported or unresolved records are quarantined.";
  showcase.body.appendChild(curriculumNote);
  showcase.body.appendChild(intro);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:grid;grid-template-columns:1fr;gap:4px";
  const rows = [
    ["nd-service", "dataset service"],
    ["nd-cases", "preregistered cases"],
    ["nd-confirm", "confirmatory inputs"],
    ["nd-explore", "exploratory inputs"],
    ["nd-rows", "append-only run rows"],
    ["nd-match", "MATCH rows"],
    ["nd-conflict", "CONFLICT rows"],
    ["nd-unavailable", "UNAVAILABLE rows"],
    ["nd-ingest", "authenticated ingest gate"],
    ["nd-octave", "local Octave"],
    ["nd-matlab", "local MATLAB"],
    ["nd-network", "network denial evidence"],
    ["nd-formulas", "eligible formula records"],
    ["nd-quarantine", "quarantined formula records"],
    ["nd-families", "source families"],
  ];
  rows.forEach(([id, label]) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:10.5px";
    const key = document.createElement("span");
    key.style.color = "#9fb1bf";
    key.textContent = label;
    const value = document.createElement("b");
    value.style.cssText = "color:#eef3f6;text-align:right;max-width:58%;overflow-wrap:anywhere";
    value.textContent = "—";
    elements[id] = value;
    row.append(key, value);
    card.appendChild(row);
  });
  showcase.body.appendChild(card);

  const heading = document.createElement("div");
  heading.style.cssText = "font:10px ui-monospace,monospace;color:#5b8dee;letter-spacing:.6px;text-transform:uppercase";
  heading.textContent = "Latest append-only run evidence";
  showcase.body.appendChild(heading);
  const resultList = document.createElement("div");
  resultList.style.cssText = "font-size:10px;max-height:170px;overflow:auto;border:1px solid #1d2a36;border-radius:7px;padding:6px 8px";
  elements["nd-results"] = resultList;
  showcase.body.appendChild(resultList);
  paintOverlay();
}

function onStatus(value) {
  status = value || null;
  paintOverlay();
}

function onCases(value) {
  cases = Array.isArray(value && value.items) ? value.items : [];
  rebuildScene();
  paintOverlay();
}

function onResults(value) {
  results = Array.isArray(value && value.items) ? value.items : [];
  rebuildScene();
  paintOverlay();
}

function onCurriculum(value) {
  curriculum = value || null;
  paintOverlay();
}

function onFrame() {
  if (group) group.rotation.y = Math.sin(performance.now() * 0.00008) * 0.08;
}

export function mount(ctx) {
  stage = ctx.stage;
  THREE = ctx.THREE;
  group = new THREE.Group();
  stage.scene.add(group);
  stage.camera.position.set(0, 6.5, 18);
  try {
    stage.controls.target.set(0, 2.2, 0);
    stage.controls.update();
    stage.setBloom(true);
  } catch (_) {}
  const grid = new THREE.GridHelper(36, 36, COLORS.frame, 0x0f2027);
  grid.material.opacity = 0.18;
  grid.material.transparent = true;
  group.add(grid);
  meshes.push(grid);
  if (!frameRegistered) {
    stage.onFrame(onFrame);
    frameRegistered = true;
  }
  badge = ctx.live.createBadge();
  polls.push(ctx.live.poll(STATUS_EP, 8000, onStatus, {
    badge,
    onState: (meta) => {
      liveState = meta.state;
      paintOverlay();
    },
  }));
  polls.push(ctx.live.poll(CASES_EP, 30000, onCases));
  polls.push(ctx.live.poll(RESULTS_EP, 10000, onResults));
  polls.push(ctx.live.poll(CURRICULUM_EP, 30000, onCurriculum));
  buildOverlay(ctx);
  return { id: ID, started: true };
}

export function unmount() {
  polls.forEach((poll) => { try { poll.stop(); } catch (_) {} });
  polls = [];
  try { if (showcase) showcase.destroy(); } catch (_) {}
  clearMeshes();
  try { if (group && stage) stage.scene.remove(group); } catch (_) {}
  stage = THREE = group = showcase = badge = null;
  elements = {};
  cases = [];
  results = [];
  status = null;
  curriculum = null;
  liveState = "init";
  frameRegistered = false;
}

export default { id: ID, title: TITLE, endpoints: [STATUS_EP, CASES_EP, RESULTS_EP, CURRICULUM_EP], mount, unmount };
