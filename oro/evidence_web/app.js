/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 */
(function (global) {
  "use strict";
  const API = "/api/a11oy/v1/oro/evidence";
  const SCHEMA = "szl.oro-evidence-observation/v1";
  const SOURCE_NAMES = {
    canonical_khipu: "Canonical Khipu",
    second_brain: "Second Brain",
    anatomy: "Living Anatomy",
    hatun: "Hatun"
  };
  const REASONS = {
    CANONICAL_ORO_STORAGE_ADAPTER_UNAVAILABLE: "ORO execution is not bound to canonical storage.",
    CANONICAL_ORO_SIGNER_ADAPTER_UNAVAILABLE: "ORO execution is not bound to the canonical signer.",
    CANONICAL_ORO_ADMISSION_NOT_BOUND: "ORO execution is not bound to canonical action admission.",
    OWNER_SNAPSHOT_UNAVAILABLE: "No retained owner snapshot is available.",
    OWNER_NOT_REGISTERED: "The source owner is not registered in this runtime.",
    OWNER_READ_FAILED: "The source owner could not return an observation.",
    OWNER_CONTRACT_INVALID: "The source snapshot did not satisfy its contract.",
    NON_JSON_RESPONSE: "The evidence endpoint returned a page instead of JSON.",
    INVALID_JSON_RESPONSE: "The evidence response could not be read.",
    OBSERVATION_TIMEOUT: "The source read exceeded its time limit.",
    OBSERVATION_REQUEST_FAILED: "The evidence endpoint could not be reached.",
    RESPONSE_LIMIT_EXCEEDED: "The evidence response exceeded the read limit.",
    SOURCE_UNAVAILABLE: "A required source could not be observed."
  };
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const text = (value, fallback = "Not observed") => value === null || value === undefined || value === "" ? fallback : String(value);
  const explanation = value => REASONS[value] || text(value).replaceAll("_", " ").toLowerCase();
  const bounded = (value, length) => typeof value === "string" && value.length <= length;

  function validateObservation(body) {
    if (!object(body) || body.schema !== SCHEMA ||
        !["OBSERVED", "PARTIAL", "UNAVAILABLE"].includes(body.status) ||
        body.execution_authority !== false || body.signing_authority !== false ||
        body.promotion_authority !== false || !object(body.sources) ||
        !object(body.projection) || body.projection.schema !== "szl.oro.evidence-dag/v1" ||
        body.projection.status !== "MODELED_READ_ONLY" ||
        body.projection.execution_authority !== false ||
        !Array.isArray(body.projection.nodes) || body.projection.nodes.length > 64) {
      throw new Error("OBSERVATION_CONTRACT_MISMATCH");
    }
    if (body.capabilities?.execution?.available !== false) {
      throw new Error("OBSERVATION_AUTHORITY_MISMATCH");
    }
    let edgeCount = 0;
    const ids = new Set();
    for (const node of body.projection.nodes) {
      const e = node?.evidence;
      if (!object(node) || !bounded(node.node_id, 128) || ids.has(node.node_id) ||
          !Array.isArray(node.parents) || !node.parents.every(p => bounded(p, 128)) ||
          !object(e) || e.classification !== "PUBLIC" ||
          !["UNVERIFIED", "CONDITIONAL", "CONJECTURE", "REFUTED", "EMPIRICAL"].includes(e.proof_status) ||
          e.execution_authority !== false || e.promotion_authority !== false ||
          !bounded(e.source, 256) || !bounded(e.revision, 80) ||
          !/^(?:commit:[a-f0-9]{40}|sha256:[a-f0-9]{64})$/.test(e.revision) ||
          !/^[a-f0-9]{64}$/.test(e.sha256)) {
        throw new Error("EVIDENCE_HANDLE_CONTRACT_MISMATCH");
      }
      edgeCount += node.parents.length;
      ids.add(node.node_id);
    }
    if (edgeCount > 128 || body.projection.nodes.some(n => n.parents.some(p => !ids.has(p)))) {
      throw new Error("EVIDENCE_EDGE_CONTRACT_MISMATCH");
    }
    return body;
  }

  function createController(options) {
    const fetchImpl = options.fetchImpl;
    const onState = options.onState;
    const setTimer = options.setTimer || setTimeout;
    const clearTimer = options.clearTimer || clearTimeout;
    const timeoutMs = options.timeoutMs ?? 8000;
    const displayAgeMs = options.displayAgeMs ?? 35000;
    let inFlight = null, disposed = false, expiryTimer = null, requestController = null;
    let requestTimer = null;

    const emit = state => { if (!disposed) onState(state); };
    function clearExpiry() {
      if (expiryTimer !== null) clearTimer(expiryTimer);
      expiryTimer = null;
    }
    async function perform() {
      clearExpiry();
      emit({phase: "loading", observation: null, reason: "COLLECTING"});
      requestController = new AbortController();
      let timedOut = false;
      try {
        const request = (async () => {
          const response = await fetchImpl(API, {
            method: "GET", headers: {Accept: "application/json"}, cache: "no-store",
            credentials: "same-origin", signal: requestController.signal
          });
          const contentType = response.headers?.get("content-type") || "";
          if (!contentType.toLowerCase().includes("application/json")) {
            throw new Error("NON_JSON_RESPONSE");
          }
          const raw = await response.text();
          if (raw.length > 262144) throw new Error("RESPONSE_LIMIT_EXCEEDED");
          let body;
          try { body = JSON.parse(raw); } catch { throw new Error("INVALID_JSON_RESPONSE"); }
          return {response, body: validateObservation(body)};
        })();
        const deadline = new Promise((_, reject) => {
          requestTimer = setTimer(() => {
            timedOut = true;
            requestController?.abort();
            reject(new Error("OBSERVATION_TIMEOUT"));
          }, timeoutMs);
        });
        const {response, body} = await Promise.race([request, deadline]);
        if (!response.ok || body.status === "UNAVAILABLE") {
          emit({phase: "unavailable", observation: body, reason: "SOURCE_UNAVAILABLE", httpStatus: response.status});
        } else {
          emit({phase: "observed", observation: body, httpStatus: response.status});
          expiryTimer = setTimer(() => {
            emit({phase: "stale", observation: null, reason: "DISPLAY_OBSERVATION_EXPIRED"});
          }, displayAgeMs);
        }
      } catch (error) {
        const known = ["NON_JSON_RESPONSE", "INVALID_JSON_RESPONSE", "RESPONSE_LIMIT_EXCEEDED",
          "OBSERVATION_CONTRACT_MISMATCH", "OBSERVATION_AUTHORITY_MISMATCH",
          "EVIDENCE_HANDLE_CONTRACT_MISMATCH", "EVIDENCE_EDGE_CONTRACT_MISMATCH"];
        const reason = timedOut ? "OBSERVATION_TIMEOUT" :
          known.includes(error?.message) ? error.message : "OBSERVATION_REQUEST_FAILED";
        emit({phase: "unavailable", observation: null, reason});
      } finally {
        if (requestTimer !== null) clearTimer(requestTimer);
        requestTimer = null;
        requestController = null;
        inFlight = null;
      }
    }
    return {
      refresh() {
        if (disposed) return Promise.resolve();
        if (inFlight !== null) return inFlight;
        inFlight = perform();
        return inFlight;
      },
      dispose() {
        disposed = true;
        clearExpiry();
        requestController?.abort();
        if (requestTimer !== null) clearTimer(requestTimer);
      }
    };
  }

  function createRenderer(doc) {
    const byId = id => doc.getElementById(id);
    const set = (id, value) => { byId(id).textContent = text(value); };
    function element(tag, value, className) {
      const node = doc.createElement(tag);
      if (value !== undefined) node.textContent = text(value);
      if (className) node.className = className;
      return node;
    }
    function field(list, label, value) {
      const row = element("div");
      row.append(element("dt", label), element("dd", value));
      list.append(row);
    }
    function renderSources(sources, unavailable) {
      const target = byId("sources");
      target.replaceChildren();
      for (const [key, label] of Object.entries(SOURCE_NAMES)) {
        const source = object(sources?.[key]) ? sources[key] : null;
        const card = element("section", undefined, "source");
        const head = element("div", undefined, "source-head");
        head.append(element("h3", label), element("span", source?.state || "UNKNOWN", "source-state"));
        card.append(head);
        const missing = !source || ["UNKNOWN", "UNAVAILABLE"].includes(source.state);
        const count = missing || unavailable ? "Handle count not observed." :
          Number.isSafeInteger(source.count) && source.count >= 0 ? source.count + " declared handle" + (source.count === 1 ? "." : "s.") : "Handle count not observed.";
        card.append(element("p", count));
        if (source?.reason) card.append(element("p", explanation(source.reason)));
        if (source?.signature_verification) card.append(element("p", "Signature verification: " + text(source.signature_verification).toLowerCase() + "."));
        if (object(source?.summary)) {
          const summary = Object.entries(source.summary).filter(([, value]) => Number.isSafeInteger(value) && value >= 0);
          if (summary.length) card.append(element("p", "Modeled summary: " + summary.slice(0, 6).map(([key, value]) => explanation(key) + " " + value).join(" · ") + "."));
        }
        target.append(card);
      }
    }
    function renderNodes(nodes, available) {
      const target = byId("nodes");
      target.replaceChildren();
      if (!available || !nodes.length) {
        target.append(element("p", available ? "This observation contains no declared evidence handles." :
          "No current evidence handles are displayed. Refresh to request an observation.", "empty"));
        return;
      }
      for (const node of nodes) {
        const details = element("details", undefined, "node");
        const summary = element("summary");
        summary.append(element("strong", node.node_id.slice(0, 28) + (node.node_id.length > 28 ? "…" : "")),
          element("span", node.evidence.proof_status, "node-summary-state"));
        const body = element("div", undefined, "node-body");
        const list = element("dl");
        field(list, "Handle", node.node_id);
        field(list, "Source", node.evidence.source);
        field(list, "Revision", node.evidence.revision);
        field(list, "SHA-256", node.evidence.sha256);
        field(list, "Visible parents", node.parents.length ? node.parents.join("\n") : "None in this window");
        field(list, "Proof status", node.evidence.proof_status);
        if (node.evidence.formula) field(list, "Formula", node.evidence.formula);
        body.append(list);
        details.append(summary, body);
        target.append(details);
      }
    }
    return function render(state) {
      const body = state.observation;
      const available = state.phase === "observed";
      const nodes = available ? body.projection.nodes : [];
      const statuses = {loading: "Collecting observation", unavailable: "Observation unavailable",
        stale: "Observation expired", observed: body?.status === "PARTIAL" ? "Partial observation" : "Inspection available"};
      const details = {loading: "Reading existing source owners.", unavailable: "Previous evidence handles have been cleared.",
        stale: "Refresh before relying on this view.", observed: "Declared pointers · verification remains separate"};
      set("observation-status", statuses[state.phase] || "No observation yet");
      set("observation-detail", state.phase === "unavailable" ?
        (REASONS[state.reason] || "The response did not satisfy the evidence contract.") + " Previous handles cleared." :
        details[state.phase] || "Waiting for the evidence reader.");
      set("announcement", statuses[state.phase] || "No observation yet");
      byId("refresh").disabled = state.phase === "loading";
      byId("refresh").textContent = state.phase === "loading" ? "Collecting…" : "Refresh observation";
      set("handle-count", available ? nodes.length + " handle" + (nodes.length === 1 ? "" : "s") : "Not observed");
      renderSources(body?.sources, !available);
      renderNodes(nodes, available);
      const khipu = body?.sources?.canonical_khipu;
      let boundary = "No current chain boundary has been observed.";
      if (available && khipu?.window_complete === false) {
        const omitted = Array.isArray(khipu.omitted_parent_digests) ? khipu.omitted_parent_digests.length : null;
        boundary = "Partial chain window. Earlier evidence lies outside this view" +
          (omitted !== null ? "; " + omitted + " parent reference" + (omitted === 1 ? " is" : "s are") + " omitted." : ".");
      } else if (available && khipu?.window_complete === true) {
        boundary = "The source reports a complete window. Content and signatures remain unverified.";
      }
      set("window-boundary", boundary);
      set("collected-at", available ? body.collected_at : null);
      set("source-revision", available ? body.source_revision : null);
      set("freshness", "Not asserted");
      const reasons = byId("execution-reasons");
      reasons.replaceChildren();
      const entries = body?.capabilities?.execution?.reasons;
      if (Array.isArray(entries) && entries.length) {
        for (const reason of entries.slice(0, 12)) reasons.append(element("li", explanation(reason)));
      } else reasons.append(element("li", "This inspection grants no execution, signing, or promotion authority."));
      set("raw", JSON.stringify(body ? {view_state: state.phase, http_status: state.httpStatus, observation: body} :
        {view_state: state.phase, reason: state.reason}, null, 2));
    };
  }

  function mount(doc, fetchImpl) {
    const render = createRenderer(doc);
    const controller = createController({fetchImpl, onState: render});
    let stopped = false, pollTimer = null;
    async function poll() {
      await controller.refresh();
      if (!stopped) pollTimer = setTimeout(poll, 30000);
    }
    doc.getElementById("refresh").addEventListener("click", () => controller.refresh());
    poll();
    return {
      dispose() { stopped = true; clearTimeout(pollTimer); controller.dispose(); }
    };
  }
  const exported = {API, validateObservation, createController, createRenderer, mount};
  if (typeof module === "object" && module.exports) module.exports = exported;
  if (global.document && typeof global.fetch === "function") {
    const mounted = mount(global.document, global.fetch.bind(global));
    global.addEventListener("pagehide", () => mounted.dispose(), {once: true});
  }
})(typeof window === "undefined" ? globalThis : window);
