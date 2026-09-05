// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Stephen P. Lutar Jr. and SZL Holdings
//
// Thin event-driven renderer adapter for the A11oy public experience.
//
// This module owns pixels only. It performs no fetch, polling, session control,
// approval, verification, or truth inference. The semantic controller passes
// ordered API state to update(), and this adapter renders that exact projection.
import { boot } from "/static/3d/szl3d/szl3d_boot.js";

const LIFECYCLE = Object.freeze([
  "PROPOSE",
  "EVIDENCE",
  "POLICY",
  "APPROVAL",
  "EXECUTE",
  "VERIFY",
  "RECEIPT",
]);

const STAGE_TO_STEP = Object.freeze({
  CREATED: "PROPOSE",
  PROPOSED: "PROPOSE",
  EVIDENCE_BOUND: "EVIDENCE",
  QUALIFIED: "EVIDENCE",
  POLICY_EVALUATED: "POLICY",
  POLICY_DENIED: "POLICY",
  BLOCKED: "POLICY",
  APPROVAL_REQUIRED: "APPROVAL",
  APPROVED: "APPROVAL",
  EXECUTING: "EXECUTE",
  VERIFIED: "VERIFY",
  VERIFICATION_FAILED: "VERIFY",
  RECOVERY_REQUIRED: "VERIFY",
  UNAVAILABLE: "VERIFY",
  RECEIPTED: "RECEIPT",
});

const FAILURE_STAGES = new Set([
  "POLICY_DENIED",
  "BLOCKED",
  "VERIFICATION_FAILED",
  "RECOVERY_REQUIRED",
]);

const COLORS = Object.freeze({
  void: 0x080c14,
  proof: 0x5fb3a3,
  lattice: 0xc9b787,
  advisory: 0xc9b787,
  denied: 0xf06464,
  unavailable: 0x85909a,
  snapshot: 0xd7e4e7,
  dormant: 0x263448,
});

const mountedCanvases = new WeakMap();
const mountAttempts = new WeakMap();

function nowMs() {
  return typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();
}

function stepIndex(stage) {
  const step = STAGE_TO_STEP[String(stage || "").toUpperCase()] || "PROPOSE";
  return Math.max(0, LIFECYCLE.indexOf(step));
}

function stateColor(THREE, dataState) {
  const value = String(dataState || "").toUpperCase();
  if (value === "LIVE" || value === "MEASURED") return new THREE.Color(COLORS.proof);
  if (value === "SIMULATION") return new THREE.Color(COLORS.lattice);
  if (value === "SNAPSHOT") return new THREE.Color(COLORS.snapshot);
  if (value === "MODELED") return new THREE.Color(COLORS.advisory);
  return new THREE.Color(COLORS.unavailable);
}

function stageColor(THREE, stage, dataState) {
  const value = String(stage || "").toUpperCase();
  if (FAILURE_STAGES.has(value)) return new THREE.Color(COLORS.denied);
  if (value === "APPROVAL_REQUIRED") return new THREE.Color(COLORS.advisory);
  if (value === "UNAVAILABLE") return new THREE.Color(COLORS.unavailable);
  return stateColor(THREE, dataState);
}

function deterministicAngle(value) {
  const text = String(value || "");
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 4294967295) * Math.PI * 2;
}

function disposeObject(object) {
  if (!object) return;
  object.traverse((child) => {
    if (child.geometry && typeof child.geometry.dispose === "function") {
      child.geometry.dispose();
    }
    if (Array.isArray(child.material)) {
      child.material.forEach((material) => {
        if (material && typeof material.dispose === "function") material.dispose();
      });
    } else if (child.material && typeof child.material.dispose === "function") {
      child.material.dispose();
    }
  });
}

export async function mountExperienceRenderer(canvas, options = {}) {
  if (!canvas) return { ok: false, reason: "canvas-unavailable" };
  if (options.signal && options.signal.aborted) return { ok: false, reason: "cancelled" };
  const previous = mountedCanvases.get(canvas);
  if (previous && typeof previous.destroy === "function") previous.destroy();
  const attempt = {};
  mountAttempts.set(canvas, attempt);

  const reducedMotion = options.reducedMotion === true;
  const stage = await boot(canvas, {
    webgpu: options.forcedColors !== true,
    forceWebGL: options.forceWebGL === true,
    bloom: false,
    background: null,
    cameraFov: 46,
    cameraNear: 0.1,
    cameraFar: 100,
    cameraPos: [0, 0.4, 10.8],
    orbit: false,
    alpha: true,
    antialias: true,
    pixelRatioCap: Math.min(2, options.pixelRatioCap || 2),
  });
  if (mountAttempts.get(canvas) !== attempt || (options.signal && options.signal.aborted)) {
    stage.dispose();
    return { ok: false, reason: "cancelled" };
  }
  const ownerDocument = canvas.ownerDocument;
  const THREE = stage.THREE;
  const sceneRoot = new THREE.Group();
  sceneRoot.name = "a11oy-public-experience-v1";
  stage.scene.add(sceneRoot);

  const coreMaterial = new THREE.MeshBasicMaterial({
    color: COLORS.lattice,
    wireframe: true,
    transparent: true,
    opacity: 0.18,
    depthWrite: false,
  });
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.08, 2),
    coreMaterial
  );
  core.position.set(0, 0.25, -0.8);
  sceneRoot.add(core);

  const cageMaterial = new THREE.LineBasicMaterial({
    color: COLORS.dormant,
    transparent: true,
    opacity: 0.35,
  });
  const cage = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.55, 1)),
    cageMaterial
  );
  cage.position.copy(core.position);
  sceneRoot.add(cage);

  const nodePositions = [];
  const nodes = [];
  const nodeGeometry = new THREE.SphereGeometry(0.115, 18, 12);
  const ringGeometry = new THREE.TorusGeometry(0.22, 0.012, 8, 36);

  LIFECYCLE.forEach((name, index) => {
    const fraction = index / (LIFECYCLE.length - 1);
    const angle = -Math.PI * 0.82 + fraction * Math.PI * 1.64;
    const radius = 3.35;
    const position = new THREE.Vector3(
      Math.cos(angle) * radius,
      Math.sin(angle) * 2.05 + 0.15,
      Math.sin(fraction * Math.PI) * 0.52
    );
    nodePositions.push(position);

    const material = new THREE.MeshBasicMaterial({
      color: COLORS.dormant,
      transparent: true,
      opacity: 0.32,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(nodeGeometry, material);
    mesh.position.copy(position);
    mesh.userData.lifecycleStep = name;
    sceneRoot.add(mesh);

    const ringMaterial = new THREE.MeshBasicMaterial({
      color: COLORS.dormant,
      transparent: true,
      opacity: 0.12,
      depthWrite: false,
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    ring.position.copy(position);
    ring.lookAt(stage.camera.position);
    sceneRoot.add(ring);
    nodes.push({ mesh, ring, material, ringMaterial });
  });

  const edgePositions = [];
  for (let index = 0; index < nodePositions.length - 1; index += 1) {
    edgePositions.push(
      nodePositions[index].x,
      nodePositions[index].y,
      nodePositions[index].z,
      nodePositions[index + 1].x,
      nodePositions[index + 1].y,
      nodePositions[index + 1].z
    );
  }
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(edgePositions, 3)
  );
  const edgeMaterial = new THREE.LineBasicMaterial({
    color: COLORS.lattice,
    transparent: true,
    opacity: 0.18,
  });
  const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial);
  sceneRoot.add(edges);

  const transitionMaterial = new THREE.MeshBasicMaterial({
    color: COLORS.proof,
    transparent: true,
    opacity: 0,
    depthWrite: false,
  });
  const transitionPulse = new THREE.Mesh(
    new THREE.SphereGeometry(0.075, 12, 8),
    transitionMaterial
  );
  sceneRoot.add(transitionPulse);

  const receiptMaterial = new THREE.MeshBasicMaterial({
    color: COLORS.proof,
    transparent: true,
    opacity: 0,
    depthWrite: false,
  });
  const receiptSeal = new THREE.Mesh(
    new THREE.TorusGeometry(0.72, 0.035, 12, 72),
    receiptMaterial
  );
  receiptSeal.position.copy(nodePositions[LIFECYCLE.length - 1]);
  receiptSeal.lookAt(stage.camera.position);
  receiptSeal.visible = false;
  sceneRoot.add(receiptSeal);

  const focusMaterial = new THREE.MeshBasicMaterial({
    color: COLORS.lattice,
    wireframe: true,
    transparent: true,
    opacity: 0,
    depthWrite: false,
  });
  const focusObject = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.42, 1),
    focusMaterial
  );
  focusObject.visible = false;
  sceneRoot.add(focusObject);

  const evidenceGroup = new THREE.Group();
  evidenceGroup.name = "evidence-handles";
  sceneRoot.add(evidenceGroup);

  let destroyed = false;
  let visible = true;
  let manuallyPaused = false;
  let loopRunning = false;
  let transitionStart = 0;
  let transitionEnd = 0;
  let transitionFrom = 0;
  let transitionTo = 0;
  let currentIndex = 0;
  let currentStage = "CREATED";
  let currentDataState = "UNAVAILABLE";
  let lastSequence = -1;
  let pointerX = 0;
  let pointerY = 0;
  let intersectionObserver = null;

  function canRender() {
    return !destroyed && visible && !manuallyPaused &&
      (!ownerDocument || ownerDocument.visibilityState !== "hidden");
  }

  function clearEvidence() {
    while (evidenceGroup.children.length) {
      const child = evidenceGroup.children[evidenceGroup.children.length - 1];
      evidenceGroup.remove(child);
      disposeObject(child);
    }
  }

  function renderEvidence(evidence) {
    clearEvidence();
    const handles = Array.isArray(evidence) ? evidence.slice(0, 10) : [];
    if (!handles.length) return;
    const center = nodePositions[1];
    handles.forEach((handle, index) => {
      const fraction = index / Math.max(1, handles.length);
      const angle = fraction * Math.PI * 2 + deterministicAngle(handle && handle.id) * 0.18;
      const radius = 0.48 + (index % 3) * 0.14;
      const color = stateColor(THREE, handle && (handle.sourceClass || handle.source_class));
      const material = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.62,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.045, 10, 7),
        material
      );
      mesh.position.set(
        center.x + Math.cos(angle) * radius,
        center.y + Math.sin(angle) * radius,
        center.z + Math.sin(angle * 2) * 0.12
      );
      evidenceGroup.add(mesh);
    });
  }

  function paint(view) {
    const activeColor = stageColor(THREE, currentStage, currentDataState);
    const stepStates = view && view.stepStates && typeof view.stepStates === "object"
      ? view.stepStates
      : {};
    nodes.forEach((node, index) => {
      const status = String(stepStates[LIFECYCLE[index]] || "pending");
      if (status === "complete") {
        node.material.color.set(COLORS.proof);
        node.material.opacity = 0.64;
        node.ringMaterial.color.set(COLORS.proof);
        node.ringMaterial.opacity = 0.22;
        node.mesh.scale.setScalar(1);
      } else if (index === currentIndex &&
                 ["active", "blocked", "failed", "unavailable"].includes(status)) {
        node.material.color.copy(activeColor);
        node.material.opacity = 0.96;
        node.ringMaterial.color.copy(activeColor);
        node.ringMaterial.opacity = 0.7;
        node.mesh.scale.setScalar(1.22);
      } else {
        node.material.color.set(COLORS.dormant);
        node.material.opacity = 0.28;
        node.ringMaterial.color.set(COLORS.dormant);
        node.ringMaterial.opacity = 0.1;
        node.mesh.scale.setScalar(0.88);
      }
    });
    edgeMaterial.color.copy(stateColor(THREE, currentDataState));
    edgeMaterial.opacity = currentDataState === "UNAVAILABLE" ? 0.1 : 0.25;
    coreMaterial.color.copy(activeColor);
    coreMaterial.opacity = currentStage === "CREATED" ? 0.16 : 0.3;
    cageMaterial.opacity = currentStage === "BLOCKED" ? 0.7 : 0.3;
    receiptSeal.visible = Boolean(view && view.receiptId);
    receiptMaterial.color.copy(activeColor);
    receiptMaterial.opacity = receiptSeal.visible ? 0.82 : 0;
  }

  function animateFrame() {
    if (!loopRunning) return;
    if (!canRender()) {
      loopRunning = false;
      stage.stop();
      return;
    }
    const now = nowMs();
    const duration = Math.max(1, transitionEnd - transitionStart);
    const progress = Math.max(0, Math.min(1, (now - transitionStart) / duration));
    const eased = 1 - Math.pow(1 - progress, 3);
    const from = nodePositions[transitionFrom] || nodePositions[0];
    const to = nodePositions[transitionTo] || from;
    transitionPulse.position.lerpVectors(from, to, eased);
    transitionMaterial.opacity = Math.sin(progress * Math.PI) * 0.9;
    transitionPulse.scale.setScalar(0.9 + Math.sin(progress * Math.PI) * 0.8);
    const active = nodes[currentIndex];
    if (active) {
      const pulse = 1.18 + Math.sin(progress * Math.PI) * 0.28;
      active.mesh.scale.setScalar(pulse);
      active.ring.rotation.z = progress * Math.PI;
    }
    core.rotation.y = pointerX * 0.18 + eased * 0.08;
    core.rotation.x = pointerY * 0.12;
    cage.rotation.y = -eased * 0.06;
    focusObject.rotation.y = eased * Math.PI * 0.25;
    if (progress >= 1) {
      transitionMaterial.opacity = 0;
      loopRunning = false;
      stage.stop();
    }
  }

  stage.onFrame(animateFrame);

  function beginTransition(fromIndex, toIndex) {
    transitionFrom = Math.max(0, Math.min(LIFECYCLE.length - 1, fromIndex));
    transitionTo = Math.max(0, Math.min(LIFECYCLE.length - 1, toIndex));
    transitionStart = nowMs();
    transitionEnd = transitionStart + 620;
    if (reducedMotion || !canRender()) {
      transitionMaterial.opacity = 0;
      if (canRender()) stage.render();
      return;
    }
    if (!loopRunning) {
      loopRunning = true;
      stage.start();
    }
  }

  function applyFocus(asset, animate) {
    if (!asset || !asset.id) {
      focusObject.visible = false;
      focusMaterial.opacity = 0;
      if (canRender()) stage.render();
      return;
    }
    const angle = deterministicAngle(asset.id);
    focusObject.position.set(
      Math.cos(angle) * 1.9,
      Math.sin(angle) * 1.15 + 0.25,
      0.2
    );
    focusMaterial.color.copy(stateColor(THREE, asset.dataState || asset.data_state));
    focusMaterial.opacity = 0.72;
    focusObject.visible = true;
    if (animate) beginTransition(currentIndex, currentIndex);
    else if (canRender()) stage.render();
  }

  function update(view) {
    if (destroyed || !view || typeof view !== "object") return;
    const nextStage = String(view.stage || "CREATED").toUpperCase();
    const declaredStep = String(view.currentStep || "").toUpperCase();
    const nextIndex = LIFECYCLE.includes(declaredStep)
      ? LIFECYCLE.indexOf(declaredStep)
      : stepIndex(nextStage);
    const nextSequence = Number.isInteger(view.sequence) ? view.sequence : lastSequence;
    const shouldAnimate = nextSequence > lastSequence || nextStage !== currentStage;
    const priorIndex = currentIndex;
    currentIndex = nextIndex;
    currentStage = nextStage;
    currentDataState = String(view.dataState || "UNAVAILABLE").toUpperCase();
    lastSequence = Math.max(lastSequence, nextSequence);
    paint(view);
    renderEvidence(view.evidence);
    applyFocus(view.focus, false);
    if (shouldAnimate) beginTransition(priorIndex, nextIndex);
    else if (canRender()) stage.render();
  }

  function setFocus(asset) {
    if (destroyed) return;
    applyFocus(asset, true);
  }

  function onPointerMove(event) {
    if (!canRender() || reducedMotion) return;
    const rect = canvas.getBoundingClientRect();
    pointerX = rect.width ? ((event.clientX - rect.left) / rect.width - 0.5) : 0;
    pointerY = rect.height ? ((event.clientY - rect.top) / rect.height - 0.5) : 0;
    sceneRoot.rotation.y = pointerX * 0.07;
    sceneRoot.rotation.x = -pointerY * 0.045;
    stage.render();
  }

  function onPointerLeave() {
    if (destroyed) return;
    pointerX = 0;
    pointerY = 0;
    sceneRoot.rotation.set(0, 0, 0);
    if (canRender()) stage.render();
  }

  canvas.addEventListener("pointermove", onPointerMove, { passive: true });
  canvas.addEventListener("pointerleave", onPointerLeave, { passive: true });

  if (typeof IntersectionObserver !== "undefined") {
    intersectionObserver = new IntersectionObserver((entries) => {
      if (destroyed) return;
      entries.forEach((entry) => {
        visible = entry.isIntersecting;
        syncVisibility();
      });
    }, { threshold: 0.01 });
    intersectionObserver.observe(canvas);
  }

  function pause() {
    manuallyPaused = true;
    loopRunning = false;
    stage.stop();
  }

  function resume() {
    if (destroyed) return;
    manuallyPaused = false;
    syncVisibility();
  }

  function syncVisibility() {
    if (destroyed) return;
    if (!canRender()) {
      loopRunning = false;
      stage.stop();
    } else if (!reducedMotion && transitionEnd > nowMs()) {
      if (!loopRunning) {
        loopRunning = true;
        stage.start();
      }
    } else {
      transitionMaterial.opacity = 0;
      stage.render();
    }
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    loopRunning = false;
    if (intersectionObserver) intersectionObserver.disconnect();
    if (ownerDocument) ownerDocument.removeEventListener("visibilitychange", syncVisibility);
    if (options.signal) options.signal.removeEventListener("abort", destroy);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerleave", onPointerLeave);
    stage.stop();
    stage.scene.remove(sceneRoot);
    disposeObject(sceneRoot);
    stage.dispose();
    if (mountedCanvases.get(canvas) === handle) mountedCanvases.delete(canvas);
    if (mountAttempts.get(canvas) === attempt) mountAttempts.delete(canvas);
  }

  const handle = Object.freeze({
    ok: true,
    backend: stage.backend,
    update,
    setFocus,
    pause,
    resume,
    destroy,
  });
  mountedCanvases.set(canvas, handle);
  if (ownerDocument) ownerDocument.addEventListener("visibilitychange", syncVisibility);
  if (options.signal) options.signal.addEventListener("abort", destroy, { once: true });
  paint({ stages: [], receiptId: "" });
  if (canRender()) stage.render();
  return handle;
}

// Compatibility name for the existing landing import. It intentionally has the
// same state-only contract and does not boot data access.
export function mountHero(canvas, options = {}) {
  return mountExperienceRenderer(canvas, options);
}

export default Object.freeze({
  mountExperienceRenderer,
  mountHero,
});
