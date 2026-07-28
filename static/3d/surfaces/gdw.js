// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
//
// Structural view of the Wave 26 immutable disposal boundary. Geometry is a
// diagram, not measured state. Runtime/storage labels and persisted counts are
// read verbatim from the same-origin status endpoint; GET signs nothing.

import { createShowcase } from "./_showcase.js";

const ID = "gdw";
const TITLE = "Governed Delta Workspace · Λ-AttnRes (MODELED)";
const EP = "/api/a11oy/v1/gdw/status";
const TEAL = 0x5fb3a3;
const GOLD = 0xc9b787;
const GREY = 0x42505d;
const RED = 0xdf7b72;

let stage = null, THREE = null, group = null, show = null, badge = null, poll = null;
let frameRegistered = false, phase = 0, kernel = null, candidate = null, committed = null;
const fields = {};
const state = { label: "MODELED", runtime: null, storage: null, counts: null, mode: "init" };

function buildScene() {
  const floor = new THREE.GridHelper(28, 28, 0x21383c, 0x12252b);
  floor.material.opacity = 0.22;
  floor.material.transparent = true;
  group.add(floor);

  candidate = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.75, 1),
    new THREE.MeshStandardMaterial({
      color: GOLD, emissive: GOLD, emissiveIntensity: 0.25,
      transparent: true, opacity: 0.88, wireframe: true,
    }),
  );
  candidate.position.set(-4.2, 1.2, 0);
  group.add(candidate);

  kernel = new THREE.Mesh(
    new THREE.BoxGeometry(2.2, 2.2, 2.2),
    new THREE.MeshStandardMaterial({
      color: TEAL, emissive: TEAL, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.78, wireframe: true,
    }),
  );
  kernel.position.set(0, 1.2, 0);
  group.add(kernel);

  committed = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.75, 1),
    new THREE.MeshStandardMaterial({
      color: GREY, emissive: GREY, emissiveIntensity: 0.16,
      transparent: true, opacity: 0.88,
    }),
  );
  committed.position.set(4.2, 1.2, 0);
  group.add(committed);

  const line = (left, right) => {
    const geometry = new THREE.BufferGeometry().setFromPoints([left, right]);
    const material = new THREE.LineBasicMaterial({
      color: GOLD, transparent: true, opacity: 0.48,
    });
    group.add(new THREE.Line(geometry, material));
  };
  line(candidate.position, kernel.position);
  line(kernel.position, committed.position);
}

function paint() {
  const unavailable = state.mode !== "live" || !state.runtime;
  const color = unavailable ? RED : TEAL;
  if (kernel) {
    kernel.material.color.setHex(color);
    kernel.material.emissive.setHex(color);
  }
  if (committed) {
    const storageColor = state.storage ? TEAL : GREY;
    committed.material.color.setHex(storageColor);
    committed.material.emissive.setHex(storageColor);
  }
  fields.runtime.textContent = state.runtime == null
    ? "UNAVAILABLE" : (state.runtime ? "READY" : "UNAVAILABLE");
  fields.storage.textContent = state.storage == null
    ? "UNAVAILABLE" : (state.storage ? "ATTACHED" : "UNAVAILABLE");
  fields.sessions.textContent = state.counts?.sessions ?? "—";
  fields.receipts.textContent = state.counts?.receipts ?? "—";
  fields.operations.textContent = state.counts?.operations ?? "—";
  fields.claim.textContent = "training/performance UNAVAILABLE";
  if (show) show.setChip("truth", state.label || "MODELED", { text: "workspace" });
}

function onStatus(body) {
  state.label = String(body.label || "MODELED").toUpperCase();
  state.runtime = body.runtime_ready === true;
  state.storage = body.storage_ready === true;
  state.counts = body.storage && body.storage.counts ? body.storage.counts : null;
  paint();
}

function animate(delta) {
  phase += Number(delta || 0.016);
  if (kernel) kernel.rotation.y = phase * 0.2;
  if (candidate) candidate.rotation.y = -phase * 0.14;
  if (committed) committed.rotation.y = phase * 0.1;
}

export function mount(ctx) {
  stage = ctx.stage;
  THREE = ctx.THREE;
  group = new THREE.Group();
  stage.scene.add(group);
  stage.camera.position.set(0, 6.5, 14);
  try {
    stage.controls.target.set(0, 1.1, 0);
    stage.controls.update();
    stage.setBloom(true);
  } catch (_) {}
  buildScene();

  badge = ctx.live.createBadge();
  show = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    badge,
    accent: "#5fb3a3",
    chips: [{ name: "truth", label: "MODELED", text: "workspace" }],
    legend: ["MODELED", "UNAVAILABLE"],
    description:
      "<b>Structural view:</b> a candidate crosses the immutable kernel before durable state. " +
      "Only status and persisted counts come from the live API; the geometry is not a metric.",
    citations:
      "Attention Residuals arXiv:2603.15031 · Delta lineage arXiv:2510.26692 · " +
      "Gated DeltaNet arXiv:2412.06464 · Λ remains Conjecture 1.",
  });
  fields.runtime = show.addField("governed runtime");
  fields.storage = show.addField("durable storage");
  fields.sessions = show.addField("persisted sessions");
  fields.receipts = show.addField("persisted receipts");
  fields.operations = show.addField("idempotent operations");
  fields.claim = show.addField("evidence boundary");

  poll = ctx.live.poll(EP, 8000, onStatus, {
    badge,
    onState: (message) => {
      state.mode = message.state;
      paint();
    },
  });
  if (!frameRegistered) {
    stage.onFrame(animate);
    frameRegistered = true;
  }
  paint();
  return { id: ID, started: true };
}

export function unmount() {
  try { if (poll) poll.stop(); } catch (_) {}
  try { if (show) show.destroy(); } catch (_) {}
  try {
    if (group && stage) {
      group.traverse((object) => {
        if (object.geometry) object.geometry.dispose();
        if (object.material) {
          const materials = Array.isArray(object.material)
            ? object.material : [object.material];
          materials.forEach((material) => material.dispose && material.dispose());
        }
      });
      stage.scene.remove(group);
    }
  } catch (_) {}
  stage = THREE = group = show = badge = poll = kernel = candidate = committed = null;
  frameRegistered = false;
  state.label = "MODELED";
  state.runtime = state.storage = state.counts = null;
  state.mode = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
