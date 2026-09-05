// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
//
// A11oy public experience controller v1.
//
// The Python experience API is authoritative. This controller never advances a
// lifecycle on a timer and never reconnects an event stream automatically. It
// renders only ordered server events, keeps the one-time approval capability in
// memory, and exposes the same actions through the semantic 2D interface.
(function a11oyPublicExperienceModule(global) {
  "use strict";

  var API_ROOT = "/api/experience/v1";
  var REQUEST_DEADLINE_MS = 12000;
  var STREAM_DEADLINE_MS = 20000;
  var PUBLIC_LINK_ORIGINS = new Set([
    "https://api.github.com",
    "https://huggingface.co",
    "https://szlholdings-a11oy.hf.space",
    "https://szlholdings-killinchu.hf.space",
    "https://szlholdings-lyte.hf.space",
    "https://szlholdings-finance.hf.space",
    "https://szlholdings-terra.hf.space",
    "https://szlholdings-counsel.hf.space",
  ]);
  var API_PATHS = Object.freeze({
    health: API_ROOT + "/health",
    estate: API_ROOT + "/estate",
    scenarios: API_ROOT + "/scenarios",
    sessions: API_ROOT + "/sessions",
  });

  var SCENARIO_ALLOWLIST = Object.freeze([
    Object.freeze({ id: "investigate-outage", title: "Investigate an outage" }),
    Object.freeze({ id: "screen-vessel", title: "Screen a vessel" }),
    Object.freeze({ id: "review-property", title: "Review a property" }),
    Object.freeze({ id: "review-contract", title: "Review a contract" }),
    Object.freeze({ id: "route-inference", title: "Route an inference request" }),
  ]);
  var ALLOWED_SCENARIOS = new Set(SCENARIO_ALLOWLIST.map(function itemId(item) {
    return item.id;
  }));

  var DATA_STATES = new Set([
    "LIVE",
    "MEASURED",
    "SIMULATION",
    "SNAPSHOT",
    "MODELED",
    "UNAVAILABLE",
  ]);
  var EXPERIENCE_STAGES = new Set([
    "CREATED",
    "PROPOSED",
    "EVIDENCE_BOUND",
    "QUALIFIED",
    "POLICY_EVALUATED",
    "APPROVAL_REQUIRED",
    "APPROVED",
    "EXECUTING",
    "VERIFIED",
    "RECEIPTED",
    "POLICY_DENIED",
    "BLOCKED",
    "VERIFICATION_FAILED",
    "RECOVERY_REQUIRED",
    "UNAVAILABLE",
  ]);
  var TERMINAL_STAGES = new Set([
    "RECEIPTED",
    "POLICY_DENIED",
    "BLOCKED",
    "VERIFICATION_FAILED",
    "RECOVERY_REQUIRED",
    "UNAVAILABLE",
  ]);
  var LIFECYCLE_STEPS = Object.freeze([
    "PROPOSE",
    "EVIDENCE",
    "POLICY",
    "APPROVAL",
    "EXECUTE",
    "VERIFY",
    "RECEIPT",
  ]);
  var STAGE_TO_STEP = Object.freeze({
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
  var COMPLETED_CURRENT_STAGES = new Set([
    "QUALIFIED",
    "POLICY_EVALUATED",
    "APPROVED",
    "VERIFIED",
    "RECEIPTED",
  ]);

  function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function boundedDeadline(value, fallback) {
    return Number.isFinite(value)
      ? Math.max(1, Math.min(60000, Math.floor(value)))
      : fallback;
  }

  function boundedText(value, limit) {
    if (typeof value !== "string") return "";
    var clean = value.replace(/\s+/g, " ").trim();
    return clean.slice(0, limit || 240);
  }

  function normalizeDataState(value) {
    var candidate = boundedText(value, 32).toUpperCase();
    return DATA_STATES.has(candidate) ? candidate : "UNAVAILABLE";
  }

  function lifecycleStepForEvent(event, events) {
    var stage = boundedText(event && event.stage, 40).toUpperCase();
    if (stage === "BLOCKED" && Array.isArray(events) &&
        events.some(function afterExecution(item) {
          return boundedText(item && item.stage, 40).toUpperCase() === "EXECUTING";
        })) {
      return "VERIFY";
    }
    return STAGE_TO_STEP[stage] || "PROPOSE";
  }

  function deriveLifecycleState(events) {
    var ordered = Array.isArray(events) ? events.filter(isRecord) : [];
    var current = ordered.length ? ordered[ordered.length - 1] : null;
    var currentStage = boundedText(current && current.stage, 40).toUpperCase();
    var currentStep = lifecycleStepForEvent(current, ordered);
    var observed = new Set(ordered.map(function mapStep(event) {
      return lifecycleStepForEvent(event, ordered);
    }));
    var receiptId = boundedText(
      current && (current.receiptId || current.receipt_id),
      200
    );
    var states = {};
    LIFECYCLE_STEPS.forEach(function deriveStep(step) {
      var status = "pending";
      if (step === "RECEIPT" && receiptId) {
        status = "complete";
      } else if (current && step === currentStep) {
        if (currentStage === "POLICY_DENIED") status = "blocked";
        else if (currentStage === "BLOCKED" ||
                 currentStage === "VERIFICATION_FAILED" ||
                 currentStage === "RECOVERY_REQUIRED") status = "failed";
        else if (currentStage === "UNAVAILABLE") status = "unavailable";
        else if (COMPLETED_CURRENT_STAGES.has(currentStage)) status = "complete";
        else status = "active";
      } else if (observed.has(step)) {
        status = "complete";
      }
      states[step] = status;
    });
    return Object.freeze({
      currentStep: currentStep,
      states: Object.freeze(states),
    });
  }

  function opaqueSegment(value, fieldName) {
    var candidate = boundedText(value, 200);
    if (!candidate || /[\u0000-\u001f]/.test(candidate)) {
      throw new Error((fieldName || "identifier") + " is unavailable");
    }
    return encodeURIComponent(candidate);
  }

  function sameOriginPath(value, explicitOrigin) {
    if (typeof value !== "string" || !value.trim()) return null;
    var origin = explicitOrigin ||
      (typeof window !== "undefined" && window.location ? window.location.origin : "");
    if (!origin) return null;
    try {
      var url = new URL(value, origin);
      if (url.origin !== origin || !/^https?:$/.test(url.protocol)) return null;
      return url.pathname + url.search + url.hash;
    } catch (_error) {
      return null;
    }
  }

  function safeSummary(value) {
    var summary = boundedText(value, 180);
    var sentence = summary.match(/^.*?[.!?](?:\s|$)/);
    return sentence ? sentence[0].trim() : summary;
  }

  function publicLink(value, explicitOrigin) {
    var local = sameOriginPath(value, explicitOrigin);
    if (local) return local;
    if (typeof value !== "string") return null;
    try {
      var url = new URL(value);
      if (url.username || url.password || !PUBLIC_LINK_ORIGINS.has(url.origin)) return null;
      return url.href;
    } catch (_error) {
      return null;
    }
  }

  function sanitizeScenario(raw) {
    if (!isRecord(raw)) return null;
    var id = boundedText(raw.id, 80);
    if (!ALLOWED_SCENARIOS.has(id)) return null;
    var fallback = SCENARIO_ALLOWLIST.find(function byId(item) {
      return item.id === id;
    });
    return Object.freeze({
      id: id,
      version: boundedText(raw.version, 80),
      title: boundedText(raw.title, 100) || fallback.title,
      prompt: boundedText(raw.prompt, 180),
      description: safeSummary(raw.description),
      domain: boundedText(raw.domain, 80),
      action: boundedText(raw.action, 140),
      dataState: normalizeDataState(raw.data_state),
      approvalRequired: raw.approval_required === true,
      approvalScope: boundedText(raw.approval_scope, 160),
      outcome: boundedText(raw.outcome, 64),
    });
  }

  function sanitizeAsset(raw, explicitOrigin) {
    if (!isRecord(raw) || raw.public !== true || raw.active !== true) return null;
    var id = boundedText(raw.id, 100);
    var title = boundedText(raw.title, 120);
    if (!id || !title || !/^[a-z0-9][a-z0-9._-]*$/i.test(id)) return null;
    return Object.freeze({
      id: id,
      title: title,
      summary: safeSummary(raw.summary),
      kind: boundedText(raw.kind, 48),
      vertical: boundedText(raw.vertical, 48),
      dataState: normalizeDataState(raw.data_state),
      visualMode: boundedText(raw.visual_mode, 64),
      livePath: publicLink(raw.live_url, explicitOrigin),
      evidencePath: publicLink(raw.evidence_url, explicitOrigin),
      tags: Array.isArray(raw.tags)
        ? raw.tags.map(function cleanTag(tag) { return boundedText(tag, 40); }).filter(Boolean).slice(0, 12)
        : [],
      scenarioIds: Array.isArray(raw.scenario_ids)
        ? raw.scenario_ids.map(function cleanId(item) { return boundedText(item, 80); })
          .filter(function allowed(idValue) { return ALLOWED_SCENARIOS.has(idValue); })
        : [],
    });
  }

  function sanitizeEvidence(raw) {
    if (!isRecord(raw)) return null;
    var id = boundedText(raw.id, 120);
    var title = boundedText(raw.title, 180);
    if (!id || !title) return null;
    var confidence = typeof raw.confidence === "number" && Number.isFinite(raw.confidence)
      ? Math.max(0, Math.min(1, raw.confidence))
      : null;
    return Object.freeze({
      id: id,
      title: title,
      sourceClass: normalizeDataState(raw.source_class),
      observedAt: boundedText(raw.observed_at, 80),
      confidence: confidence,
      digest: boundedText(raw.digest, 180),
      availability: boundedText(raw.availability_state, 48) ||
        normalizeDataState(raw.source_class),
    });
  }

  function eventPath(sessionId, afterSequence) {
    var path = API_ROOT + "/sessions/" + opaqueSegment(sessionId, "session id") + "/events";
    return Number.isInteger(afterSequence) && afterSequence >= 0
      ? path + "?after=" + String(afterSequence)
      : path;
  }

  function sessionPath(sessionId) {
    return API_ROOT + "/sessions/" + opaqueSegment(sessionId, "session id");
  }

  function approvalPath(sessionId) {
    return sessionPath(sessionId) + "/approve";
  }

  function receiptPath(receiptId) {
    return API_ROOT + "/receipts/" + opaqueSegment(receiptId, "receipt id");
  }

  function receiptVerifyPath(receiptId) {
    return receiptPath(receiptId) + "/verify";
  }

  function createSSEParser(onFrame) {
    if (typeof onFrame !== "function") throw new TypeError("onFrame must be a function");
    var buffer = "";
    var frame = { event: "message", id: "", data: [] };

    function dispatch() {
      if (!frame.data.length) {
        frame = { event: "message", id: "", data: [] };
        return;
      }
      onFrame(Object.freeze({
        event: frame.event || "message",
        id: frame.id,
        data: frame.data.join("\n"),
      }));
      frame = { event: "message", id: "", data: [] };
    }

    function consumeLine(line) {
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (!line) {
        dispatch();
        return;
      }
      if (line.charAt(0) === ":") return;
      var separator = line.indexOf(":");
      var field = separator < 0 ? line : line.slice(0, separator);
      var value = separator < 0 ? "" : line.slice(separator + 1);
      if (value.charAt(0) === " ") value = value.slice(1);
      if (field === "event") frame.event = value;
      else if (field === "id" && !value.includes("\u0000")) frame.id = value;
      else if (field === "data") frame.data.push(value);
    }

    return Object.freeze({
      push: function push(chunk, done) {
        buffer += String(chunk || "");
        var newline;
        while ((newline = buffer.indexOf("\n")) >= 0) {
          consumeLine(buffer.slice(0, newline));
          buffer = buffer.slice(newline + 1);
        }
        if (done) {
          if (buffer) consumeLine(buffer);
          buffer = "";
          dispatch();
        }
      },
    });
  }

  function acceptOrderedEvent(tracker, payload, expectedSession, expectedScenario) {
    if (!tracker || !isRecord(payload)) throw new Error("Malformed experience event");
    var stage = boundedText(payload.stage, 40).toUpperCase();
    var scenarioId = boundedText(payload.scenario_id, 80);
    var sessionId = boundedText(payload.session_id, 200);
    var sequence = payload.sequence;
    var eventId = boundedText(payload.event_id, 200);

    if (!EXPERIENCE_STAGES.has(stage)) throw new Error("Unknown experience stage");
    if (!ALLOWED_SCENARIOS.has(scenarioId) || scenarioId !== expectedScenario) {
      throw new Error("Unexpected experience scenario");
    }
    if (!sessionId || sessionId !== expectedSession) throw new Error("Unexpected experience session");
    if (!Number.isInteger(sequence) || sequence < 0) throw new Error("Invalid experience sequence");
    if (!DATA_STATES.has(boundedText(payload.data_state, 32).toUpperCase())) {
      throw new Error("Unknown experience data state");
    }

    tracker.seenEventIds = tracker.seenEventIds || new Set();
    tracker.lastSequence = Number.isInteger(tracker.lastSequence) ? tracker.lastSequence : -1;
    if ((eventId && tracker.seenEventIds.has(eventId)) || sequence <= tracker.lastSequence) {
      return Object.freeze({ accepted: false, duplicate: true });
    }
    if (sequence !== tracker.lastSequence + 1) {
      throw new Error("Experience event sequence gap");
    }
    tracker.lastSequence = sequence;
    if (eventId) tracker.seenEventIds.add(eventId);
    return Object.freeze({ accepted: true, duplicate: false, stage: stage });
  }

  function validateEndFrame(payload, tracker, currentEvent, sessionId) {
    if (!isRecord(payload) || payload.session_id !== sessionId || !currentEvent ||
        payload.next_sequence !== tracker.lastSequence + 1 ||
        payload.stage !== currentEvent.stage ||
        boundedText(payload.receipt_id, 200) !== boundedText(currentEvent.receiptId, 200) ||
        typeof payload.terminal !== "boolean" ||
        payload.terminal !== TERMINAL_STAGES.has(payload.stage)) {
      throw new Error("Unexpected event stream terminator");
    }
    return payload;
  }

  function mount(root, options) {
    options = options || {};
    if (!root || typeof root.querySelector !== "function") {
      throw new TypeError("A semantic public-experience root is required");
    }
    if (root.__a11oyPublicExperience) return root.__a11oyPublicExperience;

    var doc = root.ownerDocument || document;
    var win = doc.defaultView || window;
    var requestControllers = new Set();
    var deadlineTimers = new Set();
    var listenerRemovers = [];
    var mediaRemovers = [];
    var openPanels = [];
    var restoreTargets = new Map();
    var modalIsolation = new Map();
    var evidenceById = new Map();
    var requestDeadlineMs = boundedDeadline(options.requestDeadlineMs, REQUEST_DEADLINE_MS);
    var streamDeadlineMs = boundedDeadline(options.streamDeadlineMs, STREAM_DEADLINE_MS);
    var scheduleTimeout = typeof win.setTimeout === "function"
      ? win.setTimeout.bind(win)
      : global.setTimeout.bind(global);
    var cancelTimeout = typeof win.clearTimeout === "function"
      ? win.clearTimeout.bind(win)
      : global.clearTimeout.bind(global);

    function armDeadline(controller, milliseconds, onTimeout) {
      var timer = scheduleTimeout(function deadlineExpired() {
        deadlineTimers.delete(timer);
        onTimeout();
        controller.abort();
      }, milliseconds);
      deadlineTimers.add(timer);
      return timer;
    }

    function disarmDeadline(timer) {
      if (timer == null) return;
      cancelTimeout(timer);
      deadlineTimers.delete(timer);
    }

    function element(id) {
      var candidate = doc.getElementById(id);
      return candidate && (candidate === root || root.contains(candidate)) ? candidate : null;
    }

    var els = {
      canvas: element("a11oy-stage-canvas"),
      lifecycle: element("a11oy-lifecycle"),
      runtime: element("a11oy-runtime-state"),
      runtimeDetail: element("a11oy-runtime-detail"),
      liveRegion: element("a11oy-live-region"),
      run: element("a11oy-run-demo"),
      inspect: element("a11oy-inspect-receipt"),
      scenarioList: element("a11oy-scenario-list"),
      scenarioSelect: element("a11oy-scenario-select"),
      commandOpen: element("a11oy-command-open"),
      commandDialog: element("a11oy-command-dialog"),
      commandInput: element("a11oy-command-input"),
      commandResults: element("a11oy-command-results"),
      focusPanel: element("a11oy-focus-panel"),
      focusTitle: element("a11oy-focus-title"),
      focusSummary: element("a11oy-focus-summary"),
      focusPrimary: element("a11oy-focus-primary"),
      focusSecondary: element("a11oy-focus-secondary"),
      evidenceDrawer: element("a11oy-evidence-drawer"),
      evidenceContent: element("a11oy-evidence-content"),
      receiptDrawer: element("a11oy-receipt-drawer"),
      receiptContent: element("a11oy-receipt-content"),
      receiptVerify: element("a11oy-receipt-verify"),
      receiptVerifyResult: element("a11oy-receipt-verify-result"),
      approval: element("a11oy-approval"),
      approvalDescription: element("a11oy-approval-description"),
      approvalSubmit: element("a11oy-approval-submit"),
    };

    var reducedMedia = win.matchMedia
      ? win.matchMedia("(prefers-reduced-motion: reduce)")
      : { matches: false };
    var forcedMedia = win.matchMedia
      ? win.matchMedia("(forced-colors: active)")
      : { matches: false };

    var state = {
      destroyed: false,
      healthState: "UNAVAILABLE",
      scenarios: [],
      assets: [],
      sessionId: "",
      scenarioId: "",
      eventTracker: { lastSequence: -1, seenEventIds: new Set() },
      events: [],
      currentEvent: null,
      receiptId: "",
      receipt: null,
      approvalCapability: null,
      transport: "IDLE",
      streamController: null,
      renderer: null,
      rendererPromise: null,
      rendererGeneration: 0,
      rendererController: null,
      runVersion: 0,
      receiptVersion: 0,
      approvalPending: false,
      focusAsset: null,
      searchResults: [],
      searchIndex: 0,
      searchOpen: false,
    };

    function listen(target, type, handler, opts) {
      if (!target || typeof target.addEventListener !== "function") return;
      target.addEventListener(type, handler, opts);
      listenerRemovers.push(function removeListener() {
        target.removeEventListener(type, handler, opts);
      });
    }

    function listenMedia(media, handler) {
      if (!media) return;
      if (typeof media.addEventListener === "function") {
        media.addEventListener("change", handler);
        mediaRemovers.push(function removeMedia() {
          media.removeEventListener("change", handler);
        });
      } else if (typeof media.addListener === "function") {
        media.addListener(handler);
        mediaRemovers.push(function removeLegacyMedia() {
          media.removeListener(handler);
        });
      }
    }

    function setText(target, value) {
      if (target) target.textContent = boundedText(String(value == null ? "" : value), 500);
    }

    function announce(message) {
      setText(els.liveRegion, message);
    }

    function setRuntime(dataState, detail) {
      var normalized = normalizeDataState(dataState);
      root.dataset.experienceState = normalized.toLowerCase();
      setText(els.runtime, normalized);
      setText(els.runtimeDetail, detail || "");
    }

    function apiUrl(path) {
      if (typeof path !== "string" ||
          !(path === API_ROOT || path.indexOf(API_ROOT + "/") === 0)) {
        throw new Error("Refused non-experience API path");
      }
      var url = new URL(path, win.location.origin);
      if (url.origin !== win.location.origin) throw new Error("Refused cross-origin API request");
      return url.pathname + url.search;
    }

    async function requestJSON(path, init) {
      if (state.destroyed) throw new DOMException("Experience destroyed", "AbortError");
      var controller = new AbortController();
      var timedOut = false;
      requestControllers.add(controller);
      var requestInit = Object.assign({
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
        headers: { Accept: "application/json" },
      }, init || {});
      requestInit.signal = controller.signal;
      requestInit.headers = Object.assign({ Accept: "application/json" }, (init && init.headers) || {});
      var deadline = armDeadline(controller, requestDeadlineMs, function requestTimedOut() {
        timedOut = true;
      });
      try {
        var response = await win.fetch(apiUrl(path), requestInit);
        if (!response.ok) throw new Error("Experience API request failed with status " + response.status);
        return await response.json();
      } catch (error) {
        if (timedOut) {
          var timeoutError = new Error("Experience API request exceeded its deadline");
          timeoutError.name = "TimeoutError";
          throw timeoutError;
        }
        throw error;
      } finally {
        disarmDeadline(deadline);
        requestControllers.delete(controller);
      }
    }

    function createElement(tag, className, textValue) {
      var node = doc.createElement(tag);
      if (className) node.className = className;
      if (textValue != null) node.textContent = boundedText(String(textValue), 500);
      return node;
    }

    function appendFact(list, label, value, stateValue) {
      if (value == null || value === "") return;
      var wrap = createElement("div", "a11oy-fact");
      if (stateValue) wrap.dataset.state = normalizeDataState(stateValue).toLowerCase();
      wrap.appendChild(createElement("dt", "a11oy-fact-label", label));
      wrap.appendChild(createElement("dd", "a11oy-fact-value", value));
      list.appendChild(wrap);
    }

    function ensureTimeline() {
      if (!els.lifecycle) return;
      LIFECYCLE_STEPS.forEach(function ensureStep(step, index) {
        var item = els.lifecycle.querySelector('[data-a11oy-stage="' + step + '"]');
        if (!item) {
          item = createElement("li", "a11oy-lifecycle-step");
          item.dataset.a11oyStage = step;
          item.appendChild(createElement("span", "a11oy-stage-index", String(index + 1)));
          item.appendChild(createElement("span", "a11oy-stage-label", step));
          item.appendChild(createElement("span", "a11oy-stage-detail", "Pending"));
          els.lifecycle.appendChild(item);
        }
        item.dataset.status = "pending";
      });
    }

    function objectState(value) {
      if (!isRecord(value)) return "";
      return boundedText(
        value.state || value.status || value.result || value.decision || value.outcome,
        100
      );
    }

    function stageDetail(step, event) {
      if (!event) return "Pending";
      if (step === "PROPOSE") return event.action || "Proposal received";
      if (step === "EVIDENCE") {
        return event.evidence.length === 1
          ? "1 evidence handle"
          : String(event.evidence.length) + " evidence handles";
      }
      if (step === "POLICY") return objectState(event.policyResult) || event.stage;
      if (step === "APPROVAL") return objectState(event.approvalState) || event.stage;
      if (step === "EXECUTE") return objectState(event.effectResult) || event.stage;
      if (step === "VERIFY") return objectState(event.verificationResult) || event.stage;
      if (step === "RECEIPT") return event.receiptId || event.stage;
      return event.stage;
    }

    function renderTimeline(event) {
      if (!els.lifecycle) return;
      var lifecycle = deriveLifecycleState(state.events);
      var currentStep = lifecycle.currentStep;
      LIFECYCLE_STEPS.forEach(function renderStep(step) {
        var item = els.lifecycle.querySelector('[data-a11oy-stage="' + step + '"]');
        if (!item) return;
        var status = lifecycle.states[step] || "pending";
        item.dataset.status = status;
        if (step === currentStep && event) {
          item.setAttribute("aria-current", "step");
        } else {
          item.removeAttribute("aria-current");
        }
        var detail = item.querySelector(".a11oy-stage-detail");
        if (detail) {
          detail.textContent = step === currentStep && event
            ? boundedText(stageDetail(step, event), 180)
            : (step === "RECEIPT" && event && event.receiptId
              ? "Receipt emitted"
              : (status === "complete" ? "Complete" : "Pending"));
        }
      });
    }

    function toRendererState() {
      var lifecycle = deriveLifecycleState(state.events);
      return Object.freeze({
        dataState: state.transport === "UNAVAILABLE"
          ? "UNAVAILABLE"
          : (state.currentEvent ? state.currentEvent.dataState : state.healthState),
        stage: state.currentEvent ? state.currentEvent.stage : "CREATED",
        sequence: state.eventTracker.lastSequence,
        transport: state.transport,
        evidence: state.currentEvent ? state.currentEvent.evidence : [],
        receiptId: state.receiptId,
        focus: state.focusAsset,
        stages: state.events.map(function eventStage(event) { return event.stage; }),
        currentStep: lifecycle.currentStep,
        stepStates: lifecycle.states,
      });
    }

    function publishVisualState() {
      var view = toRendererState();
      if (state.renderer && typeof state.renderer.update === "function") {
        state.renderer.update(view);
      }
      root.dispatchEvent(new win.CustomEvent("a11oy:experience-state", {
        detail: view,
      }));
    }

    async function ensureRenderer() {
      if (!els.canvas || reducedMedia.matches || forcedMedia.matches || state.destroyed) {
        root.dataset.experienceRenderer = "2d";
        if (els.canvas) els.canvas.hidden = true;
        return null;
      }
      if (state.renderer) return state.renderer;
      if (state.rendererPromise) return state.rendererPromise;
      var generation = state.rendererGeneration;
      var controller = new AbortController();
      state.rendererController = controller;
      els.canvas.hidden = false;
      var loadRenderer = options.rendererLoader || function loadAdapter() {
        return import("/landing/app.js");
      };
      state.rendererPromise = Promise.resolve().then(loadRenderer)
        .then(function mountRenderer(moduleValue) {
          if (state.destroyed || controller.signal.aborted) return null;
          var mountRendererFn = moduleValue.mountExperienceRenderer || moduleValue.mountHero;
          if (typeof mountRendererFn !== "function") throw new Error("Renderer adapter unavailable");
          return mountRendererFn(els.canvas, {
            reducedMotion: reducedMedia.matches,
            forcedColors: forcedMedia.matches,
            signal: controller.signal,
          });
        })
        .then(function rendererReady(rendererValue) {
          if (generation !== state.rendererGeneration || state.destroyed ||
              reducedMedia.matches || forcedMedia.matches || controller.signal.aborted) {
            if (rendererValue && typeof rendererValue.destroy === "function") rendererValue.destroy();
            return null;
          }
          state.rendererPromise = null;
          if (!rendererValue || rendererValue.ok === false) {
            root.dataset.experienceRenderer = "2d";
            els.canvas.hidden = true;
            return null;
          }
          state.renderer = rendererValue;
          root.dataset.experienceRenderer = boundedText(rendererValue.backend, 32) || "3d";
          state.renderer.update(toRendererState());
          return rendererValue;
        })
        .catch(function rendererFailed() {
          if (generation !== state.rendererGeneration || state.destroyed) return null;
          state.rendererPromise = null;
          root.dataset.experienceRenderer = "2d";
          els.canvas.hidden = true;
          return null;
        });
      return state.rendererPromise;
    }

    function destroyRenderer() {
      state.rendererGeneration += 1;
      if (state.rendererController) state.rendererController.abort();
      state.rendererController = null;
      if (state.renderer && typeof state.renderer.destroy === "function") {
        state.renderer.destroy();
      }
      state.renderer = null;
      state.rendererPromise = null;
      root.dataset.experienceRenderer = "2d";
      if (els.canvas) els.canvas.hidden = true;
    }

    function renderApproval() {
      if (!els.approval) return;
      var isRequired = state.currentEvent &&
        state.currentEvent.stage === "APPROVAL_REQUIRED" &&
        state.approvalCapability;
      els.approval.hidden = !isRequired;
      if (!isRequired) return;
      var scope = boundedText(state.approvalCapability.scope, 160);
      setText(els.approvalDescription, scope);
      if (els.approvalSubmit) {
        els.approvalSubmit.disabled = state.approvalPending;
        els.approvalSubmit.textContent = scope || "Approve bounded simulation";
      }
    }

    function renderReceiptAvailability() {
      if (!els.inspect) return;
      els.inspect.disabled = !state.receiptId;
      if (state.receiptId) els.inspect.dataset.receiptAvailable = "true";
      else delete els.inspect.dataset.receiptAvailable;
    }

    function normalizeEvent(payload) {
      var evidence = Array.isArray(payload.evidence)
        ? payload.evidence.map(sanitizeEvidence).filter(Boolean)
        : [];
      return Object.freeze({
        eventId: boundedText(payload.event_id, 200),
        sessionId: boundedText(payload.session_id, 200),
        sequence: payload.sequence,
        stage: boundedText(payload.stage, 40).toUpperCase(),
        scenarioId: boundedText(payload.scenario_id, 80),
        scenarioVersion: boundedText(payload.scenario_version, 80),
        domain: boundedText(payload.domain, 80),
        action: boundedText(payload.action, 180),
        dataState: normalizeDataState(payload.data_state),
        evidence: evidence,
        policyResult: isRecord(payload.policy_result) ? payload.policy_result : null,
        approvalState: isRecord(payload.approval_state) ? payload.approval_state : null,
        effectResult: isRecord(payload.effect_result) ? payload.effect_result : null,
        verificationResult: isRecord(payload.verification_result) ? payload.verification_result : null,
        receiptId: boundedText(payload.receipt_id, 200),
        previousHash: boundedText(payload.previous_hash, 200),
        currentHash: boundedText(payload.current_hash, 200),
        emittedAt: boundedText(payload.emitted_at, 80),
      });
    }

    function applyExperienceEvent(payload) {
      var accepted = acceptOrderedEvent(
        state.eventTracker,
        payload,
        state.sessionId,
        state.scenarioId
      );
      if (!accepted.accepted) return false;
      var event = normalizeEvent(payload);
      state.events.push(event);
      if (state.events.length > 64) state.events.shift();
      state.currentEvent = event;
      event.evidence.forEach(function indexEvidence(evidence) {
        evidenceById.set(evidence.id, evidence);
      });
      if (event.receiptId) state.receiptId = event.receiptId;
      setRuntime(event.dataState, event.stage.replace(/_/g, " "));
      renderTimeline(event);
      renderApproval();
      renderReceiptAvailability();
      publishVisualState();
      announce(event.stage.replace(/_/g, " ") + ". " +
        stageDetail(lifecycleStepForEvent(event, state.events), event));
      return true;
    }

    function markTransportUnavailable(message) {
      if (state.destroyed) return;
      state.transport = "UNAVAILABLE";
      state.approvalCapability = null;
      state.approvalPending = false;
      root.dataset.experienceTransport = "unavailable";
      setRuntime("UNAVAILABLE", message);
      renderApproval();
      publishVisualState();
      announce(message);
    }

    async function consumeEvents(sessionId, afterSequence, runVersion) {
      if (state.streamController) state.streamController.abort();
      var controller = new AbortController();
      state.streamController = controller;
      state.transport = "STREAMING";
      root.dataset.experienceTransport = "streaming";
      var endFrame = null;
      var streamTimedOut = false;
      var deadline = armDeadline(controller, streamDeadlineMs, function streamTimedOutNow() {
        streamTimedOut = true;
      });
      function isCurrentStream() {
        return !state.destroyed && runVersion === state.runVersion &&
          sessionId === state.sessionId && state.streamController === controller &&
          !controller.signal.aborted;
      }
      try {
        var response = await win.fetch(apiUrl(eventPath(sessionId, afterSequence)), {
          method: "GET",
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
          headers: { Accept: "text/event-stream" },
        });
        if (!isCurrentStream()) return;
        if (!response.ok) throw new Error("Event stream failed with status " + response.status);
        var contentType = boundedText(response.headers.get("content-type"), 120).toLowerCase();
        if (contentType.indexOf("text/event-stream") < 0) {
          throw new Error("Event stream content type unavailable");
        }
        var decoder = new TextDecoder();
        var parser = createSSEParser(function onSseFrame(frame) {
          if (!isCurrentStream()) return;
          if (endFrame) throw new Error("Unexpected data after event stream terminator");
          var payload;
          try {
            payload = JSON.parse(frame.data);
          } catch (_error) {
            throw new Error("Malformed event stream payload");
          }
          if (frame.event === "experience") {
            if (frame.id !== String(payload.sequence)) throw new Error("Event stream id mismatch");
            applyExperienceEvent(payload);
          } else if (frame.event === "end") {
            validateEndFrame(payload, state.eventTracker, state.currentEvent, sessionId);
            endFrame = payload;
          } else {
            throw new Error("Unexpected event stream frame");
          }
        });

        if (response.body && typeof response.body.getReader === "function") {
          var reader = response.body.getReader();
          while (true) {
            var part = await reader.read();
            if (!isCurrentStream()) {
              await reader.cancel();
              return;
            }
            if (part.done) break;
            parser.push(decoder.decode(part.value, { stream: true }), false);
          }
          parser.push(decoder.decode(), true);
        } else {
          parser.push(await response.text(), true);
        }

        if (!isCurrentStream()) return;
        if (!endFrame) throw new Error("Event stream ended without a terminator");
        var endStage = boundedText(endFrame.stage, 40).toUpperCase();
        var terminal = endFrame.terminal === true;
        if (!EXPERIENCE_STAGES.has(endStage)) throw new Error("Unknown terminal stage");
        if (terminal !== TERMINAL_STAGES.has(endStage)) {
          throw new Error("Inconsistent terminal state");
        }
        if (terminal) {
          state.transport = "COMPLETE";
          root.dataset.experienceTransport = "complete";
        } else if (endStage === "APPROVAL_REQUIRED" && state.approvalCapability) {
          state.transport = "PAUSED";
          root.dataset.experienceTransport = "paused";
        } else {
          throw new Error("Event stream paused without an actionable approval");
        }
      } catch (error) {
        var streamStillOwned = !state.destroyed && runVersion === state.runVersion &&
          sessionId === state.sessionId && state.streamController === controller;
        if (streamStillOwned &&
            (streamTimedOut || !(error && error.name === "AbortError"))) {
          markTransportUnavailable("The ordered event stream is unavailable.");
        }
      } finally {
        disarmDeadline(deadline);
        if (state.streamController === controller) state.streamController = null;
      }
    }

    function idempotencyKey() {
      if (win.crypto && typeof win.crypto.randomUUID === "function") {
        return win.crypto.randomUUID();
      }
      return "";
    }

    function captureApprovalCapability(sessionView) {
      var capability = isRecord(sessionView.approval_capability)
        ? sessionView.approval_capability
        : null;
      var approval = isRecord(sessionView.approval) ? sessionView.approval : null;
      if (!capability || !approval) {
        state.approvalCapability = null;
        return;
      }
      var token = boundedText(capability.token, 500);
      var scope = boundedText(capability.scope, 160);
      var capabilityId = boundedText(capability.capability_id, 160);
      var issuedSequence = capability.issued_sequence;
      if (!token || !scope || !capabilityId || !Number.isInteger(issuedSequence) ||
          scope !== boundedText(approval.scope, 160) ||
          capabilityId !== boundedText(approval.capability_id, 160) ||
          issuedSequence !== approval.issued_sequence) {
        state.approvalCapability = null;
        return;
      }
      state.approvalCapability = {
        token: token,
        scope: scope,
        capabilityId: capabilityId,
        issuedSequence: issuedSequence,
        expiresAt: boundedText(capability.expires_at, 80),
      };
    }

    async function runScenario(scenarioId) {
      if (state.destroyed) return;
      var selectedId = boundedText(scenarioId, 80);
      var available = state.scenarios.some(function scenarioMatches(item) {
        return item.id === selectedId;
      });
      if (!ALLOWED_SCENARIOS.has(selectedId) || !available || state.destroyed) {
        markTransportUnavailable("That public scenario is unavailable.");
        return;
      }
      if (state.streamController) state.streamController.abort();
      var runVersion = ++state.runVersion;
      state.receiptVersion += 1;
      state.approvalPending = false;
      state.sessionId = "";
      state.scenarioId = selectedId;
      state.eventTracker = { lastSequence: -1, seenEventIds: new Set() };
      state.events = [];
      state.currentEvent = null;
      state.receiptId = "";
      state.receipt = null;
      state.approvalCapability = null;
      evidenceById.clear();
      renderTimeline(null);
      renderApproval();
      renderReceiptAvailability();
      root.dataset.experienceTransport = "creating";
      state.transport = "CREATING";
      setRuntime("SIMULATION", "Preparing bounded public demo");
      publishVisualState();
      if (els.run) els.run.disabled = true;
      announce("Creating a bounded simulation session.");
      try {
        var headers = {
          Accept: "application/json",
          "Content-Type": "application/json",
        };
        var key = idempotencyKey();
        if (key) headers["Idempotency-Key"] = key;
        var sessionView = await requestJSON(API_PATHS.sessions, {
          method: "POST",
          headers: headers,
          body: JSON.stringify({ scenario_id: selectedId }),
        });
        if (state.destroyed || runVersion !== state.runVersion) return;
        var returnedSessionId = boundedText(sessionView.session_id, 200);
        if (!returnedSessionId ||
            boundedText(sessionView.scenario_id, 80) !== selectedId ||
            normalizeDataState(sessionView.data_state) !== "SIMULATION") {
          throw new Error("Invalid session response");
        }
        state.sessionId = returnedSessionId;
        captureApprovalCapability(sessionView);
        setRuntime("SIMULATION", "Bounded public demo");
        await consumeEvents(returnedSessionId, null, runVersion);
      } catch (error) {
        if (!state.destroyed && runVersion === state.runVersion &&
            !(error && error.name === "AbortError")) {
          markTransportUnavailable("The demo session is unavailable.");
        }
      } finally {
        if (!state.destroyed && runVersion === state.runVersion && els.run) els.run.disabled = false;
      }
    }

    async function submitApproval() {
      if (state.destroyed || state.approvalPending) return;
      var capability = state.approvalCapability;
      var sessionId = state.sessionId;
      var runVersion = state.runVersion;
      if (!capability || !state.sessionId || !state.currentEvent ||
          state.currentEvent.stage !== "APPROVAL_REQUIRED") {
        announce("No bounded approval is available.");
        return;
      }
      if (els.approvalSubmit) els.approvalSubmit.disabled = true;
      state.approvalPending = true;
      try {
        var view = await requestJSON(approvalPath(sessionId), {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            capability_token: capability.token,
            scope: capability.scope,
            expected_sequence: capability.issuedSequence,
          }),
        });
        if (state.destroyed || runVersion !== state.runVersion) return;
        if (boundedText(view.session_id, 200) !== sessionId) {
          throw new Error("Invalid approval response");
        }
        state.approvalCapability = null;
        renderApproval();
        await consumeEvents(sessionId, state.eventTracker.lastSequence, runVersion);
      } catch (error) {
        if (!state.destroyed && runVersion === state.runVersion &&
            !(error && error.name === "AbortError")) {
          announce("The bounded approval was not accepted.");
          if (els.approvalSubmit) els.approvalSubmit.disabled = false;
        }
      } finally {
        if (runVersion === state.runVersion) state.approvalPending = false;
      }
    }

    function focusable(panel) {
      if (!panel) return [];
      return Array.prototype.slice.call(panel.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
        'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )).filter(function visible(node) {
        return !node.hidden && node.getAttribute("aria-hidden") !== "true";
      });
    }

    function restoreModalIsolation() {
      modalIsolation.forEach(function restore(previous, node) {
        if (previous.inert) node.setAttribute("inert", "");
        else node.removeAttribute("inert");
        if (previous.ariaHidden == null) node.removeAttribute("aria-hidden");
        else node.setAttribute("aria-hidden", previous.ariaHidden);
      });
      modalIsolation.clear();
    }

    function syncModalIsolation() {
      restoreModalIsolation();
      var panel = openPanels.length ? openPanels[openPanels.length - 1] : null;
      if (!panel) return;
      Array.prototype.slice.call(root.children).forEach(function isolate(node) {
        if (node === panel || node.contains(panel)) return;
        modalIsolation.set(node, {
          inert: node.hasAttribute("inert"),
          ariaHidden: node.getAttribute("aria-hidden"),
        });
        node.setAttribute("inert", "");
        node.setAttribute("aria-hidden", "true");
      });
    }

    function openPanel(panel, opener) {
      if (!panel) return;
      if (!restoreTargets.has(panel)) {
        var restoreTarget = opener || doc.activeElement;
        if (restoreTarget && panel.contains(restoreTarget)) restoreTarget = null;
        restoreTargets.set(panel, restoreTarget);
      }
      panel.hidden = false;
      panel.setAttribute("aria-hidden", "false");
      panel.dataset.open = "true";
      if (panel.tagName === "DIALOG" && typeof panel.showModal === "function" && !panel.open) {
        panel.showModal();
      }
      openPanels = openPanels.filter(function notSame(item) { return item !== panel; });
      openPanels.push(panel);
      syncModalIsolation();
      var targets = focusable(panel);
      var preferred = panel.querySelector("[data-a11oy-initial-focus]") ||
        panel.querySelector("[autofocus]") || targets[0] || panel;
      if (!panel.hasAttribute("tabindex") && preferred === panel) panel.tabIndex = -1;
      preferred.focus();
    }

    function closePanel(panel, restore) {
      if (!panel) return;
      if (panel.tagName === "DIALOG" && typeof panel.close === "function" && panel.open) {
        panel.close();
      }
      panel.hidden = true;
      panel.setAttribute("aria-hidden", "true");
      delete panel.dataset.open;
      openPanels = openPanels.filter(function notPanel(item) { return item !== panel; });
      syncModalIsolation();
      var target = restoreTargets.get(panel);
      restoreTargets.delete(panel);
      if (restore !== false && target && doc.contains(target) && typeof target.focus === "function") {
        target.focus();
      }
      if (panel === els.commandDialog) state.searchOpen = false;
    }

    function renderEvidence(evidenceId) {
      if (!els.evidenceContent) return;
      els.evidenceContent.textContent = "";
      var selected = evidenceId ? evidenceById.get(evidenceId) : null;
      if (selected) {
        var title = createElement("h3", "a11oy-drawer-title", selected.title);
        title.tabIndex = -1;
        title.dataset.a11oyInitialFocus = "true";
        els.evidenceContent.appendChild(title);
        var facts = createElement("dl", "a11oy-facts");
        appendFact(facts, "Source class", selected.sourceClass, selected.sourceClass);
        appendFact(facts, "Observed", selected.observedAt || "Not supplied");
        appendFact(facts, "Provenance handle", selected.digest || selected.id);
        appendFact(
          facts,
          "Confidence",
          selected.confidence == null ? "Not supplied" : Math.round(selected.confidence * 100) + "%"
        );
        appendFact(facts, "Availability", selected.availability, selected.sourceClass);
        els.evidenceContent.appendChild(facts);
        return;
      }
      var evidenceTitle = createElement("h3", "a11oy-drawer-title", "Evidence");
      evidenceTitle.tabIndex = -1;
      evidenceTitle.dataset.a11oyInitialFocus = "true";
      els.evidenceContent.appendChild(evidenceTitle);
      var evidence = Array.from(evidenceById.values());
      if (!evidence.length) {
        els.evidenceContent.appendChild(
          createElement("p", "a11oy-empty", "No evidence handles have been emitted.")
        );
        return;
      }
      var list = createElement("ul", "a11oy-evidence-list");
      evidence.forEach(function evidenceButton(item) {
        var li = createElement("li", "a11oy-evidence-item");
        var button = createElement("button", "a11oy-evidence-button", item.title);
        button.type = "button";
        button.dataset.a11oyEvidenceId = item.id;
        button.appendChild(createElement("span", "a11oy-evidence-state", item.sourceClass));
        li.appendChild(button);
        list.appendChild(li);
      });
      els.evidenceContent.appendChild(list);
    }

    function openEvidence(evidenceId, opener) {
      renderEvidence(evidenceId);
      openPanel(els.evidenceDrawer, opener);
    }

    function receiptField(receipt, key) {
      var value = receipt && receipt[key];
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return boundedText(String(value), 240);
      }
      return objectState(value);
    }

    function renderReceipt(receipt) {
      if (!els.receiptContent) return;
      els.receiptContent.textContent = "";
      var receiptTitle = createElement(
        "h3",
        "a11oy-drawer-title",
        "Receipt " + receiptField(receipt, "receipt_id")
      );
      receiptTitle.tabIndex = -1;
      receiptTitle.dataset.a11oyInitialFocus = "true";
      els.receiptContent.appendChild(receiptTitle);
      var facts = createElement("dl", "a11oy-facts a11oy-receipt-facts");
      appendFact(facts, "Data state", receiptField(receipt, "data_state"), receipt.data_state);
      appendFact(facts, "Namespace", receiptField(receipt, "namespace"));
      appendFact(facts, "Final stage", receiptField(receipt, "final_stage"));
      appendFact(facts, "Chain integrity", receiptField(receipt, "chain_integrity"));
      appendFact(facts, "Signer state", receiptField(receipt, "signer_state"));
      appendFact(facts, "Policy result", receiptField(receipt, "policy_result"));
      appendFact(facts, "Approval result", receiptField(receipt, "approval_result"));
      appendFact(facts, "Effect state", receiptField(receipt, "effect_state"));
      appendFact(facts, "Verification state", receiptField(receipt, "verification_state"));
      appendFact(facts, "Receipt digest", receiptField(receipt, "receipt_digest"));
      appendFact(facts, "Previous hash", receiptField(receipt, "previous_hash"));
      appendFact(facts, "Current hash", receiptField(receipt, "current_hash"));
      els.receiptContent.appendChild(facts);
      var note = createElement(
        "p",
        "a11oy-receipt-separation",
        "Chain integrity, signer state, effect state, and verification state are separate checks."
      );
      els.receiptContent.appendChild(note);
      var limitations = Array.isArray(receipt.limitations) ? receipt.limitations : [];
      if (limitations.length) {
        var limitList = createElement("ul", "a11oy-limitations");
        limitations.slice(0, 8).forEach(function limitation(item) {
          var value = boundedText(item, 240);
          if (value) limitList.appendChild(createElement("li", "", value));
        });
        if (limitList.childNodes.length) els.receiptContent.appendChild(limitList);
      }
    }

    async function openReceipt(receiptId, opener) {
      if (state.destroyed) return;
      var id = boundedText(receiptId || state.receiptId, 200);
      if (!id) {
        announce("No receipt has been emitted.");
        return;
      }
      var receiptVersion = ++state.receiptVersion;
      state.receipt = null;
      if (els.receiptVerify) els.receiptVerify.disabled = true;
      openPanel(els.receiptDrawer, opener);
      if (els.receiptContent) {
        els.receiptContent.textContent = "";
        els.receiptContent.appendChild(createElement("p", "a11oy-empty", "Loading receipt."));
      }
      if (els.receiptVerifyResult) els.receiptVerifyResult.textContent = "";
      try {
        var receipt = await requestJSON(receiptPath(id));
        if (state.destroyed || receiptVersion !== state.receiptVersion) return;
        if (boundedText(receipt.receipt_id, 200) !== id) throw new Error("Unexpected receipt");
        state.receipt = receipt;
        renderReceipt(receipt);
        if (els.receiptVerify) els.receiptVerify.disabled = false;
      } catch (_error) {
        if (state.destroyed || receiptVersion !== state.receiptVersion) return;
        if (els.receiptContent) {
          els.receiptContent.textContent = "";
          els.receiptContent.appendChild(
            createElement("p", "a11oy-empty", "The receipt is unavailable.")
          );
        }
        if (els.receiptVerify) els.receiptVerify.disabled = true;
      }
    }

    async function verifyReceipt() {
      if (state.destroyed || !state.receipt) return;
      var receiptId = boundedText(state.receipt.receipt_id, 200);
      var receiptVersion = state.receiptVersion;
      if (!receiptId) return;
      if (els.receiptVerify) els.receiptVerify.disabled = true;
      setText(els.receiptVerifyResult, "Checking the stored receipt.");
      try {
        var result = await requestJSON(receiptVerifyPath(receiptId), {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });
        if (state.destroyed || receiptVersion !== state.receiptVersion) return;
        var message = result.ok === true ? "Receipt checks passed. " : "Receipt checks did not pass. ";
        message += "Chain: " + (receiptField(result, "chain_integrity") || "UNAVAILABLE") + ". ";
        message += "Signer: " + (receiptField(result, "signer_state") || "UNAVAILABLE") + ". ";
        message += "Effect: " + (receiptField(result, "effect_state") || "UNAVAILABLE") + ". ";
        message += "Verification: " + (receiptField(result, "verification_state") || "UNAVAILABLE") + ".";
        setText(els.receiptVerifyResult, message);
      } catch (_error) {
        if (!state.destroyed && receiptVersion === state.receiptVersion) {
          setText(els.receiptVerifyResult, "Receipt verification is unavailable.");
        }
      } finally {
        if (!state.destroyed && receiptVersion === state.receiptVersion && els.receiptVerify) {
          els.receiptVerify.disabled = false;
        }
      }
    }

    function renderScenarioList() {
      if (els.scenarioList) {
        els.scenarioList.textContent = "";
        state.scenarios.forEach(function appendScenario(scenario) {
          var button = createElement("button", "a11oy-scenario", scenario.title);
          button.type = "button";
          button.dataset.a11oyScenarioId = scenario.id;
          button.appendChild(createElement("span", "a11oy-scenario-state", scenario.dataState));
          els.scenarioList.appendChild(button);
        });
      }
      if (els.scenarioSelect) {
        els.scenarioSelect.textContent = "";
        state.scenarios.forEach(function appendOption(scenario) {
          var option = createElement("option", "", scenario.title);
          option.value = scenario.id;
          els.scenarioSelect.appendChild(option);
        });
        els.scenarioSelect.disabled = !state.scenarios.length;
      }
      if (els.run) els.run.disabled = !state.scenarios.length;
    }

    function searchEntries(query) {
      var normalized = boundedText(query, 120).toLowerCase();
      var entries = state.scenarios.map(function scenarioEntry(scenario) {
        return {
          type: "scenario",
          id: scenario.id,
          title: scenario.title,
          summary: scenario.description || scenario.prompt,
          dataState: scenario.dataState,
          haystack: [scenario.title, scenario.description, scenario.domain, scenario.action].join(" "),
          value: scenario,
        };
      }).concat(state.assets.map(function assetEntry(asset) {
        return {
          type: "asset",
          id: asset.id,
          title: asset.title,
          summary: asset.summary,
          dataState: asset.dataState,
          haystack: [asset.title, asset.summary, asset.kind, asset.vertical].concat(asset.tags).join(" "),
          value: asset,
        };
      }));
      if (normalized) {
        entries = entries.filter(function matches(entry) {
          return entry.haystack.toLowerCase().indexOf(normalized) >= 0;
        });
      }
      return entries.slice(0, 12);
    }

    function renderSearchResults() {
      if (!els.commandResults) return;
      var query = els.commandInput ? els.commandInput.value : "";
      state.searchResults = searchEntries(query);
      if (state.searchIndex >= state.searchResults.length) state.searchIndex = 0;
      els.commandResults.textContent = "";
      if (!state.searchResults.length) {
        els.commandResults.appendChild(
          createElement("li", "a11oy-search-empty", "No public result.")
        );
        if (els.commandInput) els.commandInput.removeAttribute("aria-activedescendant");
        return;
      }
      state.searchResults.forEach(function appendResult(entry, index) {
        var li = createElement("li", "a11oy-search-item");
        li.setAttribute("role", "presentation");
        var button = createElement("button", "a11oy-search-result");
        button.type = "button";
        button.id = "a11oy-search-result-" + String(index);
        button.setAttribute("role", "option");
        button.setAttribute("aria-selected", index === state.searchIndex ? "true" : "false");
        button.dataset.a11oySearchIndex = String(index);
        button.appendChild(createElement("span", "a11oy-search-title", entry.title));
        button.appendChild(createElement("span", "a11oy-search-summary", entry.summary));
        button.appendChild(createElement("span", "a11oy-search-state", entry.dataState));
        li.appendChild(button);
        els.commandResults.appendChild(li);
      });
      if (els.commandInput) {
        els.commandInput.setAttribute(
          "aria-activedescendant",
          "a11oy-search-result-" + String(state.searchIndex)
        );
      }
    }

    function updateFocusLinks(asset) {
      var paths = [];
      if (asset.evidencePath) paths.push({ href: asset.evidencePath, label: "Open proof" });
      if (asset.livePath && asset.livePath !== asset.evidencePath) {
        paths.push({ href: asset.livePath, label: "Open surface" });
      }
      [els.focusPrimary, els.focusSecondary].forEach(function setLink(link, index) {
        if (!link) return;
        var path = paths[index];
        link.hidden = !path;
        if (path) {
          link.href = path.href;
          link.rel = "noopener noreferrer";
          link.textContent = path.label;
        } else {
          link.removeAttribute("href");
          link.textContent = "";
        }
      });
    }

    function focusAsset(asset, updateUrl) {
      if (!asset) return;
      state.focusAsset = asset;
      root.dataset.focusId = asset.id;
      if (els.focusPanel) els.focusPanel.hidden = false;
      setText(els.focusTitle, asset.title);
      setText(els.focusSummary, asset.summary);
      updateFocusLinks(asset);
      if (updateUrl !== false) {
        var url = new URL(win.location.href);
        url.searchParams.set("experience_focus", asset.id);
        win.history.replaceState(win.history.state, "", url.pathname + url.search + url.hash);
      }
      if (state.renderer && typeof state.renderer.setFocus === "function") {
        state.renderer.setFocus(asset);
      }
      publishVisualState();
      root.dispatchEvent(new win.CustomEvent("a11oy:experience-focus", {
        detail: Object.freeze({ id: asset.id, title: asset.title }),
      }));
    }

    function applyUrlFocus() {
      var params = new URL(win.location.href).searchParams;
      var id = boundedText(params.get("experience_focus"), 100);
      var asset = state.assets.find(function matches(item) { return item.id === id; });
      if (asset) focusAsset(asset, false);
      else {
        state.focusAsset = null;
        delete root.dataset.focusId;
        if (els.focusPanel) els.focusPanel.hidden = true;
        publishVisualState();
      }
    }

    function selectSearchResult(index) {
      if (!state.searchResults.length) return;
      var length = state.searchResults.length;
      state.searchIndex = (index + length) % length;
      renderSearchResults();
      var selected = doc.getElementById("a11oy-search-result-" + String(state.searchIndex));
      if (selected && typeof selected.scrollIntoView === "function") {
        selected.scrollIntoView({ block: "nearest" });
      }
    }

    function activateSearchResult(index) {
      var entry = state.searchResults[index];
      if (!entry) return;
      closePanel(els.commandDialog, true);
      if (entry.type === "scenario") runScenario(entry.id);
      else focusAsset(entry.value, true);
    }

    function openSearch(opener) {
      if (!els.commandDialog || !els.commandInput) return;
      state.searchOpen = true;
      state.searchIndex = 0;
      els.commandInput.value = "";
      renderSearchResults();
      openPanel(els.commandDialog, opener);
    }

    async function loadCatalogs() {
      var settled = await Promise.allSettled([
        requestJSON(API_PATHS.health),
        requestJSON(API_PATHS.scenarios),
        requestJSON(API_PATHS.estate),
      ]);
      if (state.destroyed) return;
      var health = settled[0].status === "fulfilled" ? settled[0].value : null;
      state.healthState = health && DATA_STATES.has(boundedText(health.data_state, 32).toUpperCase())
        ? normalizeDataState(health.data_state)
        : "UNAVAILABLE";
      setRuntime(state.healthState, state.healthState === "UNAVAILABLE"
        ? "Experience API unavailable"
        : "Experience API");

      var scenarioPayload = settled[1].status === "fulfilled" ? settled[1].value : null;
      state.scenarios = scenarioPayload && Array.isArray(scenarioPayload.scenarios)
        ? scenarioPayload.scenarios.map(sanitizeScenario).filter(Boolean)
        : [];
      var ordered = [];
      SCENARIO_ALLOWLIST.forEach(function preserveOrder(allowed) {
        var scenario = state.scenarios.find(function matches(item) { return item.id === allowed.id; });
        if (scenario) ordered.push(scenario);
      });
      state.scenarios = ordered;
      renderScenarioList();

      var estatePayload = settled[2].status === "fulfilled" ? settled[2].value : null;
      state.assets = estatePayload && Array.isArray(estatePayload.assets)
        ? estatePayload.assets.map(function cleanAsset(asset) {
          return sanitizeAsset(asset, win.location.origin);
        }).filter(Boolean)
        : [];
      applyUrlFocus();
      renderSearchResults();
      root.dataset.experienceReady = "true";
      root.dispatchEvent(new win.CustomEvent("a11oy:experience-ready", {
        detail: Object.freeze({
          scenarioCount: state.scenarios.length,
          publicAssetCount: state.assets.length,
          dataState: state.healthState,
        }),
      }));
    }

    function onRootClick(event) {
      var target = event.target && event.target.closest
        ? event.target.closest("button, a")
        : null;
      if (!target || !root.contains(target)) return;
      if (target.dataset.a11oyScenarioId) {
        event.preventDefault();
        runScenario(target.dataset.a11oyScenarioId);
      } else if (target.dataset.a11oyEvidenceId) {
        event.preventDefault();
        openEvidence(target.dataset.a11oyEvidenceId, target);
      } else if (target.dataset.a11oySearchIndex) {
        event.preventDefault();
        activateSearchResult(Number(target.dataset.a11oySearchIndex));
      } else if (target.dataset.a11oyClose) {
        event.preventDefault();
        var panel = target.closest("dialog, [data-a11oy-panel]");
        closePanel(panel, true);
      }
    }

    function onDocumentKeydown(event) {
      var target = event.target;
      var typing = target && (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      );
      if (event.key === "/" && !typing && !event.altKey && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        openSearch(els.commandOpen || doc.activeElement);
        return;
      }
      if (event.key === "Escape" && openPanels.length) {
        event.preventDefault();
        closePanel(openPanels[openPanels.length - 1], true);
        return;
      }
      if (event.key !== "Tab" || !openPanels.length) return;
      var panel = openPanels[openPanels.length - 1];
      var targets = focusable(panel);
      if (!targets.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      var first = targets[0];
      var last = targets[targets.length - 1];
      if (event.shiftKey && doc.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && doc.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    function onCommandKeydown(event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        selectSearchResult(state.searchIndex + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        selectSearchResult(state.searchIndex - 1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        activateSearchResult(state.searchIndex);
      }
    }

    function onMediaChange() {
      if (reducedMedia.matches || forcedMedia.matches) destroyRenderer();
      else ensureRenderer();
    }

    function destroy() {
      if (state.destroyed) return;
      state.destroyed = true;
      state.approvalCapability = null;
      if (state.streamController) state.streamController.abort();
      state.streamController = null;
      requestControllers.forEach(function abortRequest(controller) { controller.abort(); });
      requestControllers.clear();
      deadlineTimers.forEach(function clearDeadline(timer) { cancelTimeout(timer); });
      deadlineTimers.clear();
      openPanels.slice().reverse().forEach(function close(panel) {
        closePanel(panel, false);
      });
      restoreModalIsolation();
      listenerRemovers.splice(0).forEach(function remove(removeListener) { removeListener(); });
      mediaRemovers.splice(0).forEach(function remove(removeListener) { removeListener(); });
      destroyRenderer();
      delete root.dataset.experienceMounted;
      delete root.__a11oyPublicExperience;
    }

    ensureTimeline();
    renderTimeline(null);
    renderApproval();
    renderReceiptAvailability();
    setRuntime("UNAVAILABLE", "Checking experience API");

    listen(root, "click", onRootClick);
    listen(doc, "keydown", onDocumentKeydown);
    listen(els.commandInput, "input", function searchInput() {
      state.searchIndex = 0;
      renderSearchResults();
    });
    listen(els.commandInput, "keydown", onCommandKeydown);
    listen(els.commandOpen, "click", function commandOpen(event) {
      event.preventDefault();
      openSearch(els.commandOpen);
    });
    listen(els.run, "click", function runDefault(event) {
      event.preventDefault();
      var scenarioId = els.scenarioSelect && els.scenarioSelect.value
        ? els.scenarioSelect.value
        : (state.scenarios[0] ? state.scenarios[0].id : "");
      runScenario(scenarioId);
    });
    listen(els.inspect, "click", function inspectReceipt(event) {
      event.preventDefault();
      openReceipt(state.receiptId, els.inspect);
    });
    listen(els.approvalSubmit, "click", function approvalSubmit(event) {
      event.preventDefault();
      submitApproval();
    });
    listen(els.receiptVerify, "click", function receiptVerify(event) {
      event.preventDefault();
      verifyReceipt();
    });
    listen(els.commandDialog, "cancel", function cancelSearch(event) {
      event.preventDefault();
      closePanel(els.commandDialog, true);
    });
    listen(win, "popstate", applyUrlFocus);
    listen(win, "pagehide", destroy, { once: true });
    listenMedia(reducedMedia, onMediaChange);
    listenMedia(forcedMedia, onMediaChange);

    var handle = Object.freeze({
      destroy: destroy,
      runScenario: runScenario,
      openSearch: openSearch,
      openEvidence: openEvidence,
      openReceipt: openReceipt,
      state: function publicState() {
        return Object.freeze({
          dataState: state.currentEvent ? state.currentEvent.dataState : state.healthState,
          transport: state.transport,
          sessionId: state.sessionId,
          scenarioId: state.scenarioId,
          sequence: state.eventTracker.lastSequence,
          stage: state.currentEvent ? state.currentEvent.stage : "CREATED",
          receiptId: state.receiptId,
          focusId: state.focusAsset ? state.focusAsset.id : "",
        });
      },
    });
    root.__a11oyPublicExperience = handle;
    root.dataset.experienceMounted = "true";
    ensureRenderer();
    loadCatalogs().catch(function catalogsUnavailable() {
      markTransportUnavailable("The public experience catalogs are unavailable.");
    });
    return handle;
  }

  function autoMount() {
    if (typeof document === "undefined") return null;
    var root = document.getElementById("a11oy-experience") ||
      document.querySelector('main[data-a11oy-public-experience="v1"], section[data-a11oy-public-experience="v1"]');
    if (!root) return null;
    return mount(root);
  }

  var publicApi = Object.freeze({
    mount: mount,
    autoMount: autoMount,
    version: "1.0.0",
    __test: Object.freeze({
      API_PATHS: API_PATHS,
      SCENARIO_ALLOWLIST: SCENARIO_ALLOWLIST,
      acceptOrderedEvent: acceptOrderedEvent,
      createSSEParser: createSSEParser,
      normalizeDataState: normalizeDataState,
      deriveLifecycleState: deriveLifecycleState,
      validateEndFrame: validateEndFrame,
      publicLink: publicLink,
      sameOriginPath: sameOriginPath,
      sanitizeAsset: sanitizeAsset,
      sanitizeScenario: sanitizeScenario,
    }),
  });

  if (typeof module !== "undefined" && module.exports) module.exports = publicApi;
  if (global) global.A11oyPublicExperience = publicApi;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", autoMount, { once: true });
    } else {
      autoMount();
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
