// SPDX-License-Identifier: Apache-2.0
// A11oy Holographic v7 · source-bound Brain Frontier command instrument.
(() => {
  "use strict";

  const SNAPSHOT_PATH = "/assets/brain-frontier-v7.json";
  const DIALOG_ID = "szl-brain-frontier-v7";
  const LAUNCHER_ID = "szl-brain-frontier-v7-launcher";
  const CANVAS_ID = "szl-brain-frontier-v7-canvas";
  const HANDLE_ID = /^frontier:[0-9a-f]{32}$/;
  const REVISION = /^[0-9a-f]{40}$/;
  const DIGEST = /^[0-9a-f]{64}$/;
  const ALLOWED_REPOSITORIES = new Set([
    "szl-holdings/szl-formulas",
    "szl-holdings/ouroboros",
    "szl-holdings/anatomy",
    "szl-holdings/a11oy",
    "szl-holdings/szl-forge",
    "szl-holdings/szl-nemo",
  ]);
  const REQUIRED_REPOSITORIES = [
    "szl-holdings/anatomy",
    "szl-holdings/ouroboros",
    "szl-holdings/a11oy",
    "szl-holdings/szl-forge",
    "szl-holdings/szl-nemo",
  ];
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
  const state = {
    open: false,
    loading: false,
    payload: null,
    query: "",
    frame: 0,
    observer: null,
    previousFocus: null,
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const short = (value, width = 13) => {
    const text = String(value ?? "");
    if (!DIGEST.test(text) && !REVISION.test(text)) return "UNAVAILABLE";
    return `${text.slice(0, width)}…${text.slice(-6)}`;
  };

  const compactRepo = (value) => {
    const text = String(value ?? "");
    return text.startsWith("szl-holdings/") ? text.slice(13) : text;
  };

  function validateHandle(handle) {
    if (!handle || typeof handle !== "object") return false;
    if (!ALLOWED_REPOSITORIES.has(String(handle.repository ?? ""))) return false;
    if (!HANDLE_ID.test(String(handle.nodeId ?? ""))) return false;
    if (!DIGEST.test(String(handle.sha256 ?? ""))) return false;
    if (!REVISION.test(String(handle.revision ?? ""))) return false;
    if (handle.candidateState !== "DISCOVERED_REVIEW_REQUIRED") return false;
    if (handle.contentAccess !== "HANDLES_ONLY") return false;
    if (handle.authority !== "NONE") return false;
    if (Object.hasOwn(handle, "content") || Object.hasOwn(handle, "text")) return false;
    return true;
  }

  function validatePayload(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return false;
    if (payload.schema !== "szl.a11oy.brain-frontier-holographic-v7/v1") return false;
    if (payload.state !== "SOURCE_BOUND_REVIEW_MEMORY") return false;
    if (payload.surface !== "A11OY_HOLOGRAPHIC_V7_BRAIN_FRONTIER") return false;
    if (!DIGEST.test(String(payload.snapshot_sha256 ?? ""))) return false;
    if (!Array.isArray(payload.handles) || payload.handles.length !== 72) return false;
    if (!payload.handles.every(validateHandle)) return false;
    if (payload.selected_handle_count !== payload.handles.length) return false;
    const presentRepos = new Set(payload.handles.map((handle) => String(handle.repository ?? "")));
    if (!REQUIRED_REPOSITORIES.every((repository) => presentRepos.has(repository))) return false;
    const brain = payload.sources?.second_brain;
    const anatomy = payload.sources?.anatomy;
    const formula = payload.formula_atlas;
    const authority = payload.authority;
    if (!brain || !REVISION.test(String(brain.revision ?? ""))) return false;
    if (!DIGEST.test(String(brain.candidate_set_sha256 ?? ""))) return false;
    if (!anatomy || anatomy.repository !== "szl-holdings/anatomy") return false;
    if (!REVISION.test(String(anatomy.revision ?? ""))) return false;
    if (!formula || formula.attributed_formula_count !== 30) return false;
    if (formula.executable_formula_count !== 21 || formula.quant_domain_count !== 9) return false;
    if (formula.locked_proven_formula_count !== 8) return false;
    if (formula.f_number_to_executable_mapping !== "UNKNOWN_NOT_INFERRED") return false;
    if (formula.lambda !== "CONJECTURE_1") return false;
    if (!authority || authority.public_content_access !== "HANDLES_ONLY") return false;
    if (authority.training !== "NONE" || authority.promotion !== "NONE") return false;
    if (authority.execution !== "NONE" || authority.merge !== "NONE") return false;
    if (authority.provider_mutation !== "NONE" || authority.private_graph_present !== false) return false;
    if (authority.raw_graph_nodes_admitted_to_gradients !== 0) return false;
    if (authority.human_review_required !== true) return false;
    return true;
  }

  async function loadSnapshot() {
    if (state.loading) return;
    state.loading = true;
    renderCards();
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 9000);
    try {
      const url = new URL(SNAPSHOT_PATH, window.location.origin);
      if (url.origin !== window.location.origin) throw new Error("CROSS_ORIGIN_REJECTED");
      const response = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP_${response.status}`);
      const payload = await response.json();
      if (!validatePayload(payload)) throw new Error("SNAPSHOT_CONTRACT_REJECTED");
      state.payload = payload;
    } catch (_error) {
      state.payload = null;
    } finally {
      window.clearTimeout(timer);
      state.loading = false;
      renderAll();
    }
  }

  function createUi() {
    const launcher = document.createElement("button");
    launcher.id = LAUNCHER_ID;
    launcher.type = "button";
    launcher.textContent = "Brain frontier";
    launcher.setAttribute("aria-controls", DIALOG_ID);
    launcher.setAttribute("aria-expanded", "false");
    launcher.setAttribute("aria-label", "Open source-bound Brain Frontier v7");

    const dialog = document.createElement("section");
    dialog.id = DIALOG_ID;
    dialog.hidden = true;
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "bf7-title");
    dialog.setAttribute("aria-describedby", "bf7-subtitle");
    dialog.innerHTML = `
      <button class="bf7__dismiss" type="button" tabindex="-1" aria-label="Close Brain Frontier"></button>
      <article class="bf7__panel">
        <div class="bf7__layout">
          <header class="bf7__header">
            <div>
              <p class="bf7__eyebrow">A11oy Holographic v7 · source-bound review memory</p>
              <h2 class="bf7__title" id="bf7-title">The governed brain, visible without exposing its thoughts.</h2>
              <p class="bf7__subtitle" id="bf7-subtitle">Second Brain handles, formula authority, quant domains and Ouroboros HOLD receipts. Metadata only; no candidate content or execution authority.</p>
            </div>
            <button class="bf7__close" type="button" aria-label="Close Brain Frontier">×</button>
          </header>
          <div class="bf7__metrics" aria-label="Brain Frontier metrics">
            <div class="bf7__metric"><span class="bf7__metric-label">Review handles</span><strong class="bf7__metric-value" data-bf7-metric="handles">Loading</strong></div>
            <div class="bf7__metric"><span class="bf7__metric-label">Formula tissue</span><strong class="bf7__metric-value" data-bf7-metric="formulas">—</strong></div>
            <div class="bf7__metric"><span class="bf7__metric-label">Quant domains</span><strong class="bf7__metric-value" data-bf7-metric="domains">—</strong></div>
            <div class="bf7__metric"><span class="bf7__metric-label">Loop state</span><strong class="bf7__metric-value" data-bf7-metric="loop">HOLD</strong></div>
          </div>
          <div class="bf7__graph-shell">
            <canvas id="${CANVAS_ID}" role="img" aria-label="Graph of source handles around the A11oy review hold"></canvas>
            <span class="bf7__graph-label">Observe → orient → propose → verify → hold</span>
          </div>
          <div class="bf7__tools">
            <input class="bf7__search" type="search" maxlength="160" autocomplete="off" spellcheck="false" aria-label="Filter Brain Frontier handles" placeholder="Filter by formula, quant domain, source or handle…" />
            <button class="bf7__refresh" type="button">Refresh</button>
            <a class="bf7__link" href="https://betterwithage-anatomy.hf.space" target="_blank" rel="noopener noreferrer">Open Living Anatomy ↗</a>
          </div>
          <div class="bf7__stream" tabindex="0" aria-live="polite">
            <div class="bf7__cards" data-bf7-cards></div>
          </div>
          <footer class="bf7__footer">
            <span><i class="bf7__dot" data-bf7-dot></i><span data-bf7-state>Resolving exact snapshot</span></span>
            <span class="bf7__digest" data-bf7-digest>Candidate set: UNAVAILABLE</span>
          </footer>
        </div>
      </article>`;

    document.body.append(launcher, dialog);
    return { launcher, dialog };
  }

  function metric(name, value, status = "") {
    const element = document.querySelector(`[data-bf7-metric="${name}"]`);
    if (!element) return;
    element.textContent = String(value);
    if (status) element.dataset.state = status;
    else delete element.dataset.state;
  }

  function filteredHandles() {
    const handles = Array.isArray(state.payload?.handles) ? state.payload.handles : [];
    const terms = state.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!terms.length) return handles;
    return handles.filter((handle) => {
      const haystack = [
        handle.nodeId,
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

  function renderCard(handle) {
    const domain = handle.quantDomain
      ? `<span>${escapeHtml(handle.quantDomain)}</span>`
      : "";
    return `
      <article class="bf7__card">
        <div>
          <h3 class="bf7__card-title">${escapeHtml(handle.title || handle.nodeId)}</h3>
          <div class="bf7__card-meta">
            <span>${escapeHtml(compactRepo(handle.repository))}</span>
            <span>${escapeHtml(handle.kind)}</span>
            ${domain}
            <span>${escapeHtml(short(handle.revision, 8))}</span>
            <span>${escapeHtml(short(handle.sha256, 8))}</span>
          </div>
        </div>
        <span class="bf7__tag">Review required</span>
      </article>`;
  }

  function renderCards() {
    const container = document.querySelector("[data-bf7-cards]");
    if (!container) return;
    if (state.loading) {
      container.innerHTML = '<div class="bf7__empty">Loading one exact, same-origin, handles-only snapshot…</div>';
      return;
    }
    if (!state.payload) {
      container.innerHTML = '<div class="bf7__empty">The source-bound snapshot is unavailable. The instrument refuses to synthesize green state or substitute stale content.</div>';
      return;
    }
    const handles = filteredHandles();
    if (!handles.length) {
      container.innerHTML = '<div class="bf7__empty">No admitted source handle matches this filter.</div>';
      return;
    }
    container.innerHTML = handles.map(renderCard).join("");
  }

  function renderMetrics() {
    const payload = state.payload;
    const ready = Boolean(payload);
    metric("handles", ready ? payload.selected_handle_count : "Unavailable", ready ? "live" : "warn");
    metric("formulas", ready ? `${payload.formula_atlas.attributed_formula_count} + ${payload.formula_atlas.executable_formula_count}` : "—", ready ? "live" : "warn");
    metric("domains", ready ? payload.formula_atlas.quant_domain_count : "—", ready ? "live" : "warn");
    metric("loop", ready ? payload.loop.at(-1) : "Held", ready ? "live" : "warn");

    const dot = document.querySelector("[data-bf7-dot]");
    const stateLabel = document.querySelector("[data-bf7-state]");
    const digest = document.querySelector("[data-bf7-digest]");
    if (dot) dot.dataset.state = ready ? "live" : "offline";
    if (stateLabel) stateLabel.textContent = ready ? "Exact source snapshot · human review required" : "Unavailable · no green synthesized";
    if (digest) digest.textContent = `Candidate set: ${short(payload?.sources?.second_brain?.candidate_set_sha256)}`;
  }

  function hash(value) {
    let result = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      result ^= value.charCodeAt(index);
      result = Math.imul(result, 16777619);
    }
    return result >>> 0;
  }

  function drawGraph(timestamp = 0) {
    const canvas = document.getElementById(CANVAS_ID);
    if (!canvas) return;
    const shell = canvas.parentElement;
    const width = Math.max(1, shell.clientWidth);
    const height = Math.max(1, shell.clientHeight);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const physicalWidth = Math.floor(width * ratio);
    const physicalHeight = Math.floor(height * ratio);
    if (canvas.width !== physicalWidth || canvas.height !== physicalHeight) {
      canvas.width = physicalWidth;
      canvas.height = physicalHeight;
    }
    const context = canvas.getContext("2d");
    if (!context) return;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    const handles = filteredHandles().slice(0, 36);
    const centerX = width / 2;
    const centerY = height / 2 + 5;
    const rootRadius = Math.min(width, height) * 0.23;
    const outerRadius = Math.min(width, height) * 0.42;
    const pulse = REDUCED_MOTION.matches ? 0 : Math.sin(timestamp / 1050) * 2;
    const roots = [
      { id: "brain", label: "BRAIN", angle: -Math.PI / 2 },
      { id: "formula", label: "FORMULA", angle: 0 },
      { id: "loop", label: "LOOP", angle: Math.PI / 2 },
      { id: "anatomy", label: "ANATOMY", angle: Math.PI },
    ];
    const rootPositions = new Map();

    context.lineWidth = 1;
    for (const root of roots) {
      const point = {
        x: centerX + Math.cos(root.angle) * rootRadius,
        y: centerY + Math.sin(root.angle) * rootRadius,
      };
      rootPositions.set(root.id, point);
      context.strokeStyle = "rgba(58,244,200,.24)";
      context.beginPath();
      context.moveTo(centerX, centerY);
      context.lineTo(point.x, point.y);
      context.stroke();
    }

    handles.forEach((handle, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(1, handles.length) + ((hash(handle.nodeId) % 29) / 180) * Math.PI;
      const jitter = ((hash(handle.nodeId) % 21) - 10) * 0.7;
      const x = centerX + Math.cos(angle) * (outerRadius + jitter);
      const y = centerY + Math.sin(angle) * (outerRadius + jitter) * 0.66;
      const kind = String(handle.kind || "");
      const root = kind.includes("formula") || kind === "quant-domain"
        ? rootPositions.get("formula")
        : handle.repository === "szl-holdings/ouroboros"
          ? rootPositions.get("loop")
          : handle.repository === "szl-holdings/anatomy"
            ? rootPositions.get("anatomy")
            : rootPositions.get("brain");
      if (root) {
        context.strokeStyle = "rgba(148,170,168,.13)";
        context.beginPath();
        context.moveTo(root.x, root.y);
        context.lineTo(x, y);
        context.stroke();
      }
      context.fillStyle = kind === "quant-domain" ? "#d9bd7b" : "#3af4c8";
      context.beginPath();
      context.arc(x, y, 2.2, 0, Math.PI * 2);
      context.fill();
    });

    context.fillStyle = "rgba(4,16,22,.98)";
    context.strokeStyle = "rgba(58,244,200,.65)";
    context.lineWidth = 1.2;
    context.beginPath();
    context.arc(centerX, centerY, 20 + pulse, 0, Math.PI * 2);
    context.fill();
    context.stroke();
    context.fillStyle = "#edf8f5";
    context.font = "700 8px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText("HOLD", centerX, centerY);

    for (const root of roots) {
      const point = rootPositions.get(root.id);
      context.fillStyle = "rgba(8,24,31,.98)";
      context.strokeStyle = "rgba(58,244,200,.43)";
      context.beginPath();
      context.arc(point.x, point.y, 13, 0, Math.PI * 2);
      context.fill();
      context.stroke();
      context.fillStyle = "#94aaa8";
      context.font = "700 7px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
      context.fillText(root.label, point.x, point.y);
    }

    if (state.open && !REDUCED_MOTION.matches) {
      state.frame = window.requestAnimationFrame(drawGraph);
    }
  }

  function restartGraph() {
    window.cancelAnimationFrame(state.frame);
    state.frame = window.requestAnimationFrame(drawGraph);
  }

  function renderAll() {
    renderMetrics();
    renderCards();
    restartGraph();
  }

  function focusable(dialog) {
    return [...dialog.querySelectorAll('button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]
      .filter((element) => !element.hidden && element.getClientRects().length > 0);
  }

  function openDialog() {
    if (state.open) return;
    const dialog = document.getElementById(DIALOG_ID);
    const launcher = document.getElementById(LAUNCHER_ID);
    if (!dialog || !launcher) return;
    state.previousFocus = document.activeElement;
    state.open = true;
    dialog.hidden = false;
    launcher.setAttribute("aria-expanded", "true");
    document.documentElement.style.overflow = "hidden";
    dialog.querySelector(".bf7__close")?.focus();
    loadSnapshot();
    restartGraph();
  }

  function closeDialog() {
    if (!state.open) return;
    const dialog = document.getElementById(DIALOG_ID);
    const launcher = document.getElementById(LAUNCHER_ID);
    state.open = false;
    window.cancelAnimationFrame(state.frame);
    if (dialog) dialog.hidden = true;
    if (launcher) launcher.setAttribute("aria-expanded", "false");
    document.documentElement.style.overflow = "";
    if (state.previousFocus instanceof HTMLElement) state.previousFocus.focus();
    else launcher?.focus();
  }

  function bind(launcher, dialog) {
    launcher.addEventListener("click", openDialog);
    dialog.querySelector(".bf7__close")?.addEventListener("click", closeDialog);
    dialog.querySelector(".bf7__dismiss")?.addEventListener("click", closeDialog);
    dialog.querySelector(".bf7__refresh")?.addEventListener("click", loadSnapshot);
    dialog.querySelector(".bf7__search")?.addEventListener("input", (event) => {
      state.query = String(event.target.value || "").slice(0, 160);
      renderCards();
      restartGraph();
    });
    dialog.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDialog();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable(dialog);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    state.observer = new ResizeObserver(restartGraph);
    const shell = dialog.querySelector(".bf7__graph-shell");
    if (shell) state.observer.observe(shell);
    REDUCED_MOTION.addEventListener?.("change", restartGraph);
  }

  function boot() {
    if (document.getElementById(DIALOG_ID) || document.getElementById(LAUNCHER_ID)) return;
    const { launcher, dialog } = createUi();
    bind(launcher, dialog);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
