/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 */
(() => {
  "use strict";

  const API = "/api/a11oy/v1/frontier-now";
  const SERIES_EVENTS = "/api/a11oy/v1/series-a/events";
  const TIMEOUT_MS = 8000;
  const INVENTORY_PAGE_SIZE = 50;
  const INVENTORY_MAX_PAGES = 10;
  const MIN_EVENT_RELOAD_MS = 5000;
  const STATES = new Set([
    "OBSERVED",
    "MODELED",
    "PENDING",
    "STALE",
    "BLOCKED",
    "FAILED_CLOSED",
    "UNAVAILABLE",
    "DISABLED",
    "UNKNOWN"
  ]);

  const byId = (id) => document.getElementById(id);
  const terminal = (value, fallback = "UNAVAILABLE") => {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  };
  const state = (value) => {
    const normalized = terminal(value, "UNAVAILABLE").toUpperCase();
    return STATES.has(normalized) ? normalized : "UNKNOWN";
  };
  const setText = (id, value, fallback) => {
    const node = byId(id);
    if (node) node.textContent = terminal(value, fallback);
  };
  const setState = (id, value) => {
    const node = byId(id);
    if (!node) return;
    const normalized = state(value);
    node.textContent = normalized;
    node.dataset.state = normalized;
  };
  const formatTime = (value) => {
    if (!value) return "NOT OBSERVED";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? String(value) : date.toISOString();
  };
  const shortHash = (value) => {
    const text = terminal(value, "UNAVAILABLE");
    return text.length > 24 ? `${text.slice(0, 12)}…${text.slice(-8)}` : text;
  };

  const activeControllers = new Set();
  const request = async (path) => {
    const controller = new AbortController();
    activeControllers.add(controller);
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(API + path, {
        method: "GET",
        cache: "no-store",
        credentials: "same-origin",
        headers: {accept: "application/json"},
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`HTTP_${response.status}`);
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error("NON_JSON_RESPONSE");
      }
      return await response.json();
    } finally {
      clearTimeout(timer);
      activeControllers.delete(controller);
    }
  };

  const requestInventory = async () => {
    let cursor = 0;
    let identity = null;
    let pageCount = 0;
    const items = [];
    while (pageCount < INVENTORY_MAX_PAGES) {
      const page = await request(
        `/inventory?provider=all&limit=${INVENTORY_PAGE_SIZE}&cursor=${cursor}`
      );
      const pageIdentity = [
        page.manifest_digest,
        page.observation_state,
        page.observed_at,
        page.valid_until
      ];
      if (identity && JSON.stringify(identity) !== JSON.stringify(pageIdentity)) {
        throw new Error("INVENTORY_CHANGED_DURING_PAGINATION");
      }
      identity = pageIdentity;
      items.push(...(Array.isArray(page.items) ? page.items : []));
      pageCount += 1;
      if (page.next_cursor === null || page.next_cursor === undefined) {
        return {...page, items};
      }
      if (!Number.isInteger(page.next_cursor) || page.next_cursor <= cursor) {
        throw new Error("INVALID_INVENTORY_CURSOR");
      }
      cursor = page.next_cursor;
    }
    throw new Error("INVENTORY_PAGINATION_BOUND_EXCEEDED");
  };

  const sameObservation = (summary, inventory) => (
    summary.observation?.manifest_digest === inventory.manifest_digest &&
    summary.observation?.state === inventory.observation_state &&
    summary.observation?.observed_at === inventory.observed_at &&
    summary.observation?.valid_until === inventory.valid_until
  );

  const readView = async () => {
    const settled = await Promise.allSettled([request("/summary"), requestInventory()]);
    if (settled[0].status !== "fulfilled") throw settled[0].reason;
    let summary = settled[0].value;
    if (settled[1].status !== "fulfilled") {
      return {summary, inventory: null, inventoryError: settled[1].reason};
    }
    let inventory = settled[1].value;
    if (sameObservation(summary, inventory)) {
      return {summary, inventory, inventoryError: null};
    }

    const retry = await Promise.allSettled([request("/summary"), requestInventory()]);
    if (retry[0].status === "fulfilled") summary = retry[0].value;
    if (retry[1].status !== "fulfilled") {
      return {summary, inventory: null, inventoryError: retry[1].reason};
    }
    inventory = retry[1].value;
    if (!sameObservation(summary, inventory)) {
      return {
        summary,
        inventory: null,
        inventoryError: new Error("SNAPSHOT_CHANGED_DURING_READ")
      };
    }
    return {summary, inventory, inventoryError: null};
  };

  const renderCoverage = (items, emptyMessage) => {
    const body = byId("coverage-rows");
    body.replaceChildren();
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 5;
      cell.textContent = emptyMessage || "UNAVAILABLE · no capability observations returned";
      row.append(cell);
      body.append(row);
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const provider = document.createElement("td");
      const capability = document.createElement("td");
      const statusCell = document.createElement("td");
      const count = document.createElement("td");
      const scope = document.createElement("td");
      const badge = document.createElement("span");

      provider.textContent = terminal(item.provider);
      capability.textContent = terminal(item.capability);
      badge.className = "status";
      badge.dataset.state = state(item.state);
      badge.textContent = state(item.state);
      statusCell.append(badge);
      count.textContent = item.count === null || item.count === undefined ? "—" : String(item.count);
      scope.textContent = terminal(item.scope);
      row.append(provider, capability, statusCell, count, scope);
      body.append(row);
    });
  };

  const renderProof = (items, proofState = "UNAVAILABLE") => {
    const list = byId("proof-rail");
    list.replaceChildren();
    const receipts = Array.isArray(items) ? items : [];
    if (!receipts.length) {
      const item = document.createElement("li");
      const observedEmpty = state(proofState) === "OBSERVED";
      item.textContent = observedEmpty
        ? "OBSERVED · no receipts persisted"
        : "UNAVAILABLE · receipt projection could not be read";
      list.append(item);
      setState("proof-state", observedEmpty ? "OBSERVED" : "UNAVAILABLE");
      return;
    }
    receipts.forEach((receipt) => {
      const item = document.createElement("li");
      const kind = document.createElement("span");
      const hash = document.createElement("a");
      const created = document.createElement("time");
      const signature = document.createElement("span");
      const digest = terminal(receipt.receipt_hash);

      kind.textContent = terminal(receipt.kind);
      hash.href = `/api/a11oy/v1/series-a/receipts/${encodeURIComponent(digest)}`;
      hash.textContent = shortHash(digest);
      hash.className = "text-link";
      hash.title = digest;
      hash.setAttribute("aria-label", `Open receipt SHA-256 ${digest}`);
      created.dateTime = terminal(receipt.created_at, "");
      created.textContent = formatTime(receipt.created_at);
      signature.className = "status";
      signature.dataset.state = "UNAVAILABLE";
      signature.textContent = `REPORTED ${terminal(receipt.signature_status)}`;
      item.append(kind, hash, created, signature);
      list.append(item);
    });
    setState("proof-state", "OBSERVED");
  };

  const renderCounts = (counts) => {
    document.querySelectorAll("[data-count]").forEach((node) => {
      const value = counts && Object.prototype.hasOwnProperty.call(counts, node.dataset.count)
        ? counts[node.dataset.count]
        : null;
      node.textContent = value === null || value === undefined ? "—" : String(value);
    });
  };

  let loadGeneration = 0;
  const load = async () => {
    activeControllers.forEach((controller) => controller.abort());
    activeControllers.clear();
    const generation = ++loadGeneration;
    const button = byId("refresh-view");
    button.disabled = true;
    setText("view-status", "Reading the persisted estate snapshot.");
    try {
      const {summary, inventory, inventoryError} = await readView();
      if (generation !== loadGeneration) return;

      setText("operating-mode", summary.operating_mode, "OBSERVE_ONLY");
      setState("estate-state", summary.observation?.state);
      setState("observe-state", summary.observation?.state);
      setState("claim-state", summary.claim_gate?.state);
      setText("observed-at", formatTime(summary.observation?.observed_at));
      setText("as-of", `OBSERVED ${formatTime(summary.observation?.observed_at)} · VALID UNTIL ${formatTime(summary.observation?.valid_until)}`);

      const revision = summary.identity?.runtime_reported_source_revision;
      setText("runtime-revision", revision, "NOT OBSERVED");
      setText("graph-source", shortHash(revision));
      byId("runtime-source-node").classList.toggle("reported", Boolean(revision));
      byId("runtime-source-node").classList.toggle("unavailable", !revision);
      setText("identity-reason", terminal(summary.identity?.reason));
      renderCounts(summary.counts || {});
      renderCoverage(
        inventory?.items || [],
        inventoryError
          ? `UNAVAILABLE · inventory projection: ${terminal(inventoryError.message)}`
          : undefined
      );
      renderProof(summary.proof_rail || [], summary.proof_rail_state);
      setText(
        "view-status",
        `View generated ${formatTime(summary.generated_at)} · ${terminal(summary.claim)}` +
          (inventoryError ? " · COVERAGE UNAVAILABLE" : "")
      );
    } catch (error) {
      if (generation !== loadGeneration) return;
      setState("estate-state", "UNAVAILABLE");
      setState("observe-state", "UNAVAILABLE");
      setState("claim-state", "FAILED_CLOSED");
      setState("proof-state", "UNAVAILABLE");
      renderCounts({});
      renderCoverage([], "UNAVAILABLE · capability projection could not be read");
      renderProof([], "UNAVAILABLE");
      setText("operating-mode", "OBSERVE_ONLY");
      setText("runtime-revision", "NOT OBSERVED");
      setText("graph-source", "NOT OBSERVED");
      byId("runtime-source-node").classList.remove("reported");
      byId("runtime-source-node").classList.add("unavailable");
      setText("observed-at", "NOT OBSERVED");
      setText("identity-reason", "CURRENT_PROJECTION_UNAVAILABLE");
      const reason = error && error.name === "AbortError"
        ? `UNAVAILABLE · timed out after ${TIMEOUT_MS / 1000} seconds`
        : `UNAVAILABLE · ${terminal(error && error.message)}`;
      setText("view-status", reason);
      setText("as-of", "TERMINAL UNAVAILABLE STATE");
    } finally {
      if (generation === loadGeneration) button.disabled = false;
    }
  };

  byId("refresh-view").addEventListener("click", load);

  const activateRailLink = (active) => {
    document.querySelectorAll('.rail a[href^="#"]').forEach((item) => {
      const selected = item === active;
      item.classList.toggle("active", selected);
      if (selected) item.setAttribute("aria-current", "location");
      else item.removeAttribute("aria-current");
    });
  };

  document.querySelectorAll('.rail a[href^="#"]').forEach((link) => {
    link.addEventListener("click", () => {
      activateRailLink(link);
    });
  });

  if ("IntersectionObserver" in window) {
    const links = new Map(
      [...document.querySelectorAll('.rail a[href^="#"]')].map((link) => [
        link.getAttribute("href").slice(1),
        link
      ])
    );
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      activateRailLink(links.get(visible.target.id));
    }, {rootMargin: "-20% 0px -65%", threshold: [0.05, 0.25, 0.6]});
    links.forEach((_link, id) => {
      const section = byId(id);
      if (section) observer.observe(section);
    });
  }

  let eventReloadTimer = null;
  let lastEventReload = 0;
  if ("EventSource" in window) {
    const events = new EventSource(SERIES_EVENTS);
    events.addEventListener("open", () => {
      setText("live-updates", "UPDATES CONNECTED");
    });
    events.addEventListener("error", () => {
      setText("live-updates", "UPDATES UNAVAILABLE · MANUAL REFRESH");
    });
    ["estate.refresh", "estate.refresh.failed"].forEach((eventName) => {
      events.addEventListener(eventName, () => {
        clearTimeout(eventReloadTimer);
        const wait = Math.max(250, MIN_EVENT_RELOAD_MS - (Date.now() - lastEventReload));
        eventReloadTimer = setTimeout(() => {
          lastEventReload = Date.now();
          load();
        }, wait);
      });
    });
  } else {
    setText("live-updates", "UPDATES UNAVAILABLE · MANUAL REFRESH");
  }

  load();
})();
