/* SPDX-License-Identifier: Apache-2.0
 * A11oy Holographic · YACHAY Brain v7
 * Same-origin, handles-only observability over the Living Anatomy source boundary.
 */
(() => {
  "use strict";

  if (document.documentElement.dataset.a11BrainV7Installed === "true") return;
  document.documentElement.dataset.a11BrainV7Installed = "true";

  const BASE = "/api/a11oy/v1/holographic/brain-v7";
  const ENDPOINTS = Object.freeze({
    frontier: `${BASE}/frontier`,
    formulas: `${BASE}/formulas`,
    quant: `${BASE}/quant`,
    ouroboros: `${BASE}/ouroboros`,
  });
  const CONTRACT = `${BASE}/contract`;
  const HEALTH = `${BASE}/health`;
  const LABELS = Object.freeze({
    frontier: "Frontier",
    formulas: "Formulas",
    quant: "Quant",
    ouroboros: "Ouroboros",
  });
  const FORBIDDEN_KEYS = new Set(["content", "text", "documents"]);
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;

  const state = {
    open: false,
    tab: "frontier",
    query: "",
    contract: null,
    health: null,
    planes: new Map(),
    handles: [],
    selected: null,
    abort: null,
    raf: 0,
    previousFocus: null,
  };

  function walkForForbidden(value) {
    if (!value || typeof value !== "object") return false;
    if (Array.isArray(value)) return value.some(walkForForbidden);
    return Object.entries(value).some(([key, child]) => (
      FORBIDDEN_KEYS.has(key.toLowerCase()) || walkForForbidden(child)
    ));
  }

  function validateEnvelope(envelope, plane) {
    if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) {
      throw new Error("INVALID_ENVELOPE");
    }
    if (envelope.schema !== "szl.a11oy.holographic-brain-v7/v1") {
      throw new Error("SCHEMA_DRIFT");
    }
    if (envelope.plane !== plane) throw new Error("PLANE_DRIFT");
    if (walkForForbidden(envelope)) throw new Error("CONTENT_BOUNDARY_VIOLATION");
    const authority = envelope.authority || {};
    for (const field of ["training", "weight_update", "promotion", "merge", "execution", "provider_mutation"]) {
      if (authority[field] !== "NONE") throw new Error("AUTHORITY_DRIFT");
    }
    if (authority.private_memory_access !== "NONE") throw new Error("PRIVATE_MEMORY_DRIFT");
    const payload = envelope.payload;
    if (!payload || typeof payload !== "object") throw new Error("INVALID_PAYLOAD");
    if (payload.content_access !== "HANDLES_ONLY") throw new Error("ACCESS_DRIFT");
    const handles = Array.isArray(payload.handles) ? payload.handles : [];
    if (handles.length > 48) throw new Error("HANDLE_BOUND_EXCEEDED");
    for (const handle of handles) {
      if (!handle || typeof handle !== "object") throw new Error("INVALID_HANDLE");
      if (handle.contentAccess !== "HANDLES_ONLY") throw new Error("HANDLE_ACCESS_DRIFT");
      if (handle.candidateState !== "DISCOVERED_REVIEW_REQUIRED") {
        throw new Error("CANDIDATE_PROMOTION_DRIFT");
      }
      if (!/^frontier:[0-9a-f]{32}$/.test(String(handle.nodeId || ""))) {
        throw new Error("INVALID_HANDLE_ID");
      }
      if (!/^[0-9a-f]{40}$/.test(String(handle.revision || ""))) {
        throw new Error("INVALID_REVISION");
      }
      if (!/^[0-9a-f]{64}$/.test(String(handle.sha256 || ""))) {
        throw new Error("INVALID_DIGEST");
      }
    }
    return envelope;
  }

  async function fetchJson(url, signal) {
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: { Accept: "application/json" },
      signal,
    });
    if (!response.ok) throw new Error(`HTTP_${response.status}`);
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("application/json")) {
      throw new Error("NON_JSON_RESPONSE");
    }
    return response.json();
  }

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "a11-brain-v7-trigger";
  trigger.setAttribute("aria-haspopup", "dialog");
  trigger.setAttribute("aria-controls", "a11-brain-v7-shell");
  trigger.setAttribute("aria-expanded", "false");
  trigger.textContent = "Brain v7";

  const mount = document.querySelector(".navtools") || document.querySelector("header") || document.body;
  mount.append(trigger);

  const shell = document.createElement("div");
  shell.id = "a11-brain-v7-shell";
  shell.className = "a11-brain-v7-shell";
  shell.hidden = true;
  shell.innerHTML = `
    <section class="a11-brain-v7-dialog" role="dialog" aria-modal="true" aria-labelledby="a11-brain-v7-title" aria-describedby="a11-brain-v7-subtitle">
      <header class="a11-brain-v7-head">
        <div>
          <p class="a11-brain-v7-kicker">A11oy Holographic · Living Anatomy source plane</p>
          <h2 class="a11-brain-v7-title" id="a11-brain-v7-title">YACHAY Brain · Formula &amp; Quant Mesh</h2>
          <p class="a11-brain-v7-subtitle" id="a11-brain-v7-subtitle">Source-bound public handles move through a bounded Ouroboros review loop. Evidence is visible; content, private memory, weights and effectors stay outside this surface.</p>
        </div>
        <button class="a11-brain-v7-close" type="button" aria-label="Close Brain v7">×</button>
      </header>
      <div class="a11-brain-v7-toolbar">
        <input class="a11-brain-v7-search" type="search" maxlength="512" autocomplete="off" spellcheck="false" aria-label="Filter holographic Brain handles" placeholder="Filter handles, formulas, quant domains, or sources…" />
        <div class="a11-brain-v7-tabs" role="tablist" aria-label="Brain v7 planes"></div>
      </div>
      <div class="a11-brain-v7-body">
        <div class="a11-brain-v7-stage" aria-label="Holographic network of review-required source handles">
          <canvas class="a11-brain-v7-canvas"></canvas>
          <div class="a11-brain-v7-stage-meta">observe → retrieve → hypothesize → falsify → revise → package → review</div>
        </div>
        <aside class="a11-brain-v7-side" aria-label="Brain v7 handle registry">
          <div class="a11-brain-v7-metrics" aria-live="polite"></div>
          <div class="a11-brain-v7-list" role="tabpanel" tabindex="0"></div>
        </aside>
      </div>
      <footer class="a11-brain-v7-foot">
        <span class="a11-brain-v7-state" data-ready="false">Resolving exact Anatomy source…</span>
        <span class="a11-brain-v7-digest" title="Candidate set digest">digest · unavailable</span>
      </footer>
    </section>
  `;
  document.body.append(shell);

  const dialog = shell.querySelector(".a11-brain-v7-dialog");
  const closeButton = shell.querySelector(".a11-brain-v7-close");
  const search = shell.querySelector(".a11-brain-v7-search");
  const tabs = shell.querySelector(".a11-brain-v7-tabs");
  const metrics = shell.querySelector(".a11-brain-v7-metrics");
  const list = shell.querySelector(".a11-brain-v7-list");
  const stage = shell.querySelector(".a11-brain-v7-stage");
  const canvas = shell.querySelector(".a11-brain-v7-canvas");
  const statusNode = shell.querySelector(".a11-brain-v7-state");
  const digestNode = shell.querySelector(".a11-brain-v7-digest");
  const context = canvas.getContext("2d", { alpha: true });

  function short(value, front = 10, back = 5) {
    const text = String(value || "");
    return text ? `${text.slice(0, front)}…${text.slice(-back)}` : "unavailable";
  }

  function bucket(handle) {
    const kind = String(handle.kind || "");
    const repository = String(handle.repository || "");
    if (kind.includes("quant") || handle.quantDomain) return "quant";
    if (kind.includes("formula")) return "formula";
    if (repository.includes("ouroboros")) return "ouroboros";
    if (repository.includes("anatomy")) return "anatomy";
    if (repository.includes("second-brain")) return "brain";
    return "source";
  }

  function stableNumber(value) {
    let hash = 2166136261;
    const text = String(value || "");
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0) / 4294967295;
  }

  function currentPayload() {
    return state.planes.get(state.tab)?.payload || { handles: [] };
  }

  function visibleHandles() {
    const handles = Array.isArray(currentPayload().handles) ? currentPayload().handles : [];
    const terms = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return handles;
    return handles.filter((handle) => {
      const haystack = [
        handle.title,
        handle.repository,
        handle.path,
        handle.kind,
        handle.quantDomain,
        handle.admission,
      ].join(" ").toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
  }

  function setStatus(label, ready) {
    statusNode.textContent = label;
    statusNode.dataset.ready = ready ? "true" : "false";
  }

  function selectTab(tab) {
    if (!(tab in ENDPOINTS)) return;
    state.tab = tab;
    state.selected = null;
    render();
  }

  function renderTabs() {
    tabs.replaceChildren();
    const ids = Object.keys(LABELS);
    ids.forEach((id, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "a11-brain-v7-tab";
      button.dataset.tab = id;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", state.tab === id ? "true" : "false");
      button.setAttribute("tabindex", state.tab === id ? "0" : "-1");
      button.textContent = LABELS[id];
      button.addEventListener("click", () => selectTab(id));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (event.key === "ArrowLeft") next = (index - 1 + ids.length) % ids.length;
        if (event.key === "ArrowRight") next = (index + 1) % ids.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = ids.length - 1;
        selectTab(ids[next]);
        requestAnimationFrame(() => tabs.querySelector(`[data-tab="${ids[next]}"]`)?.focus());
      });
      tabs.append(button);
    });
  }

  function renderMetrics(handles) {
    const formulas = handles.filter((handle) => bucket(handle) === "formula").length;
    const domains = new Set(handles.map((handle) => handle.quantDomain).filter(Boolean)).size;
    const repos = new Set(handles.map((handle) => handle.repository).filter(Boolean)).size;
    metrics.replaceChildren();
    for (const [value, label] of [
      [handles.length, "visible handles"],
      [formulas, "formula handles"],
      [domains || repos, domains ? "quant domains" : "source repos"],
    ]) {
      const box = document.createElement("div");
      box.className = "a11-brain-v7-metric";
      const strong = document.createElement("strong");
      const span = document.createElement("span");
      strong.textContent = String(value);
      span.textContent = label;
      box.append(strong, span);
      metrics.append(box);
    }
  }

  function renderList(handles) {
    list.replaceChildren();
    if (!handles.length) {
      const empty = document.createElement("p");
      empty.className = "a11-brain-v7-empty";
      empty.textContent = "No verified handles match this plane. The holograph refuses to invent nodes.";
      list.append(empty);
      return;
    }
    const fragment = document.createDocumentFragment();
    for (const handle of handles) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "a11-brain-v7-item";
      item.dataset.bucket = bucket(handle);
      item.dataset.active = state.selected === handle.nodeId ? "true" : "false";
      item.setAttribute("aria-label", `Focus ${String(handle.title || "source handle")}`);
      const dot = document.createElement("span");
      dot.className = "a11-brain-v7-item-dot";
      dot.setAttribute("aria-hidden", "true");
      const copy = document.createElement("span");
      const title = document.createElement("h3");
      title.textContent = String(handle.title || "UNAVAILABLE");
      const meta = document.createElement("p");
      meta.textContent = [
        String(handle.kind || "source"),
        handle.quantDomain ? `domain ${handle.quantDomain}` : null,
        String(handle.repository || "UNAVAILABLE"),
        `rev ${short(handle.revision, 8, 4)}`,
        `sha ${short(handle.sha256, 8, 4)}`,
      ].filter(Boolean).join(" · ");
      copy.append(title, meta);
      item.append(dot, copy);
      item.addEventListener("click", () => {
        state.selected = handle.nodeId;
        render();
      });
      fragment.append(item);
    }
    list.append(fragment);
  }

  function resizeCanvas() {
    const rect = stage.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(rect.width * ratio));
    const height = Math.max(1, Math.floor(rect.height * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    return { width, height, ratio };
  }

  function colorFor(kind) {
    const styles = getComputedStyle(document.documentElement);
    if (kind === "quant") return styles.getPropertyValue("--a11-brain-gold").trim() || "#e8c074";
    if (kind === "ouroboros") return styles.getPropertyValue("--a11-brain-warn").trim() || "#ffae62";
    return styles.getPropertyValue("--a11-brain-proof").trim() || "#3af4c8";
  }

  function layout(handles, width, height) {
    const center = { x: width * 0.5, y: height * 0.52 };
    const groups = new Map();
    for (const handle of handles) {
      const group = bucket(handle);
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(handle);
    }
    const names = [...groups.keys()].sort();
    const dimension = Math.min(width, height);
    const inner = Math.max(68, dimension * 0.18);
    const outer = Math.max(inner + 42, dimension * 0.43);
    const nodes = [];
    names.forEach((name, groupIndex) => {
      const group = groups.get(name);
      const groupAngle = (Math.PI * 2 * groupIndex) / Math.max(1, names.length) - Math.PI / 2;
      group.forEach((handle, itemIndex) => {
        const seed = stableNumber(handle.nodeId);
        const spread = group.length > 1 ? (itemIndex / group.length - 0.5) * 0.92 : 0;
        const angle = groupAngle + spread + (seed - 0.5) * 0.17;
        const radius = inner + (outer - inner) * (0.3 + seed * 0.7);
        nodes.push({
          handle,
          group: name,
          x: center.x + Math.cos(angle) * radius,
          y: center.y + Math.sin(angle) * radius * 0.72,
          size: handle.nodeId === state.selected ? 8 : 4 + seed * 2,
        });
      });
    });
    return { center, nodes };
  }

  function draw(time = 0) {
    if (!state.open || !context) return;
    const { width, height, ratio } = resizeCanvas();
    context.clearRect(0, 0, width, height);
    const graph = layout(state.handles, width, height);
    const pulse = reducedMotion ? 0 : (Math.sin(time / 880) + 1) * 0.5;

    context.save();
    context.lineWidth = Math.max(1, ratio * 0.55);
    for (const node of graph.nodes) {
      const active = node.handle.nodeId === state.selected;
      context.beginPath();
      context.moveTo(graph.center.x, graph.center.y);
      context.lineTo(node.x, node.y);
      context.strokeStyle = active ? "rgba(238,247,246,.62)" : "rgba(58,244,200,.11)";
      context.stroke();
    }

    const glow = context.createRadialGradient(
      graph.center.x,
      graph.center.y,
      0,
      graph.center.x,
      graph.center.y,
      62 * ratio,
    );
    glow.addColorStop(0, "rgba(58,244,200,.34)");
    glow.addColorStop(0.3, "rgba(58,244,200,.11)");
    glow.addColorStop(1, "rgba(58,244,200,0)");
    context.fillStyle = glow;
    context.beginPath();
    context.arc(graph.center.x, graph.center.y, 62 * ratio, 0, Math.PI * 2);
    context.fill();

    context.beginPath();
    context.arc(graph.center.x, graph.center.y, (11 + pulse * 2) * ratio, 0, Math.PI * 2);
    context.fillStyle = colorFor("brain");
    context.shadowColor = colorFor("brain");
    context.shadowBlur = 18 * ratio;
    context.fill();
    context.shadowBlur = 0;

    for (const node of graph.nodes) {
      const active = node.handle.nodeId === state.selected;
      const color = colorFor(node.group);
      context.beginPath();
      context.arc(node.x, node.y, (node.size + (active ? pulse * 2 : 0)) * ratio, 0, Math.PI * 2);
      context.fillStyle = color;
      context.globalAlpha = active ? 1 : 0.76;
      context.shadowColor = color;
      context.shadowBlur = (active ? 20 : 8) * ratio;
      context.fill();
      context.globalAlpha = 1;
      context.shadowBlur = 0;
    }
    context.restore();
    if (!reducedMotion) state.raf = requestAnimationFrame(draw);
  }

  function render() {
    state.handles = visibleHandles();
    if (state.selected && !state.handles.some((handle) => handle.nodeId === state.selected)) {
      state.selected = null;
    }
    renderTabs();
    renderMetrics(state.handles);
    renderList(state.handles);
    if (state.open) {
      cancelAnimationFrame(state.raf);
      draw(performance.now());
    }
  }

  async function load() {
    state.abort?.abort();
    const controller = new AbortController();
    state.abort = controller;
    const timeout = window.setTimeout(() => controller.abort("TIMEOUT"), 10_000);
    setStatus("Resolving exact Anatomy source…", false);
    try {
      const [contract, health, ...planes] = await Promise.all([
        fetchJson(CONTRACT, controller.signal),
        fetchJson(HEALTH, controller.signal),
        ...Object.entries(ENDPOINTS).map(([, url]) => fetchJson(url, controller.signal)),
      ]);
      if (contract.public_content_access !== "HANDLES_ONLY") throw new Error("CONTRACT_ACCESS_DRIFT");
      if (contract.locked_proven_count !== 8) throw new Error("LOCKED_COUNT_DRIFT");
      if (contract.lambda !== "CONJECTURE_1") throw new Error("LAMBDA_STATE_DRIFT");
      const validatedHealth = validateEnvelope(health, "health");
      if (validatedHealth.state !== "REVIEW_REQUIRED" || validatedHealth.ready !== true) {
        throw new Error("ANATOMY_FRONTIER_UNAVAILABLE");
      }
      state.contract = contract;
      state.health = validatedHealth;
      Object.keys(ENDPOINTS).forEach((plane, index) => {
        state.planes.set(plane, validateEnvelope(planes[index], plane));
      });
      const payload = validatedHealth.payload;
      const digest = payload.candidate_set_sha256;
      digestNode.textContent = `digest · ${short(digest, 16, 6)}`;
      digestNode.title = `Second Brain candidate set SHA-256: ${digest}`;
      setStatus(`${payload.candidate_count} candidates · review required · source-bound`, true);
      render();
    } catch (error) {
      state.contract = null;
      state.health = null;
      state.planes.clear();
      state.handles = [];
      const reason = error instanceof Error ? error.message : "UNAVAILABLE";
      setStatus(`UNAVAILABLE · ${reason}`, false);
      digestNode.textContent = "digest · unavailable";
      list.replaceChildren();
      const message = document.createElement("p");
      message.className = "a11-brain-v7-error";
      message.textContent = "The Living Anatomy source plane did not prove its exact handles-only contract. No cached or invented Brain nodes are shown.";
      list.append(message);
      renderMetrics([]);
      cancelAnimationFrame(state.raf);
      draw(performance.now());
    } finally {
      window.clearTimeout(timeout);
      if (state.abort === controller) state.abort = null;
    }
  }

  function focusable() {
    return [...dialog.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter((element) => !element.hidden && element.getClientRects().length > 0);
  }

  function open() {
    if (state.open) return;
    state.open = true;
    state.previousFocus = document.activeElement;
    shell.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    document.body.classList.add("a11-brain-v7-open");
    requestAnimationFrame(() => {
      search.focus();
      draw(performance.now());
    });
    load();
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    shell.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    document.body.classList.remove("a11-brain-v7-open");
    state.abort?.abort("CLOSED");
    cancelAnimationFrame(state.raf);
    if (state.previousFocus instanceof HTMLElement && document.contains(state.previousFocus)) {
      state.previousFocus.focus();
    } else {
      trigger.focus();
    }
  }

  trigger.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  shell.addEventListener("mousedown", (event) => {
    if (event.target === shell) close();
  });
  search.addEventListener("input", () => {
    state.query = search.value.slice(0, 512);
    state.selected = null;
    render();
  });
  window.addEventListener("resize", () => {
    if (state.open) draw(performance.now());
  }, { passive: true });
  document.addEventListener("keydown", (event) => {
    if ((event.altKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "b") {
      event.preventDefault();
      state.open ? close() : open();
      return;
    }
    if (!state.open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const elements = focusable();
    if (!elements.length) return;
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  renderTabs();
  renderMetrics([]);
})();
