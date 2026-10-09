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
  const FORUM_REPOSITORY = "szl-holdings/szl-science-forum-corpus";
  const FORUM_PATH = "dataset/sources.public.jsonl";
  const RESEARCH_REPOSITORIES = new Set(["public-metadata/arxiv", "public-metadata/crossref"]);
  const METADATA_REVISION_KIND = "metadata-capture-sha256";
  const REQUIRED_SOURCE_REPOSITORIES = new Set([
    "szl-holdings/szl-formulas",
    "szl-holdings/anatomy",
    "szl-holdings/szl-ouroboros",
    "szl-holdings/a11oy",
    "szl-holdings/szl-forge",
    "szl-holdings/szl-nemo",
    "szl-holdings/szl-kernels",
  ]);
  const SOURCE_REPOSITORIES = new Set([...REQUIRED_SOURCE_REPOSITORIES, FORUM_REPOSITORY,
    ...RESEARCH_REPOSITORIES]);
  const HANDLE_KINDS = new Set([
    "formula-authority", "quant-domain", "attributed-formula", "executable-formula",
    "python-contract", "estate-authority", "estate-surface", "source-document", "forum-insight",
    "research-metadata",
  ]);
  const HANDLE_ADMISSIONS = new Set([
    "DISCOVERED_REVIEW_REQUIRED",
    "EXECUTABLE_CONSTRAINT_REVIEW_REQUIRED",
    "OPEN_NOT_EXECUTION_AUTHORITY",
    "REFERENCE_AND_CONSTRAINT_INPUT_ONLY",
    "REFERENCE_ONLY_EXECUTION_AUTHORITY_NONE",
    "REFERENCE_ONLY_NO_PROVIDER_MUTATION",
    "REFERENCE_ONLY_UNLESS_EXECUTABLE_MATCH_IS_EXPLICIT",
    "SOURCE_RECEIPT_REQUIRED_FOR_CURRENT_CLAIM",
  ]);
  const LOOP = ["OBSERVE", "ORIENT", "PROPOSE", "VERIFY", "HOLD"];
  const REVIEW_WORKFLOW = ".github/workflows/codex-continuous-frontier.yml";
  const OBSERVATION_STATES = new Set(["OBSERVED", "UNAVAILABLE", "PENDING", "FAILED", "STALE", "REJECTED"]);
  const MAX_SNAPSHOT_BYTES = 256 * 1024;
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
  const state = {
    open: false,
    loading: false,
    payload: null,
    query: "",
    frame: 0,
    observer: null,
    previousFocus: null,
    expiryTimer: 0,
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

  const record = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);
  const matches = (value, pattern) => typeof value === "string" && pattern.test(value);
  const exactKeys = (value, required, optional = []) => record(value)
    && required.every((key) => Object.hasOwn(value, key))
    && Object.keys(value).every((key) => required.includes(key) || optional.includes(key));
  const safeTitle = (value) => typeof value === "string" && value.trim().length > 0
    && [...value].length <= 180 && !/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(value);
  const safePath = (value) => typeof value === "string" && value.length <= 512
    && value.split("/").every((part) => /^[A-Za-z0-9_.-]+$/.test(part) && part !== "." && part !== "..");
  const safeDomain = (value) => matches(value, /^[a-z0-9][a-z0-9_-]{0,79}$/);
  const positiveInteger = (value) => Number.isSafeInteger(value) && value > 0;
  const sameList = (value, expected) => Array.isArray(value) && value.length === expected.length
    && value.every((item, index) => item === expected[index]);

  function validateObservation(value, sources) {
    if (!exactKeys(value, ["schema", "state", "reason", "source", "run", "artifact", "observation",
      "freshness", "authority", "claims", "observation_sha256"])) return false;
    if (value.schema !== "szl.ouroboros.frontier-observation/v1" || !OBSERVATION_STATES.has(value.state)
      || !matches(value.reason, /^[A-Z][A-Z0-9_]{0,95}$/) || !matches(value.observation_sha256, DIGEST)) return false;
    const source = value.source;
    if (!exactKeys(source, ["controller_repository", "controller_revision", "workflow",
      "second_brain_repository", "second_brain_revision", "state_file_sha256", "candidate_file_sha256",
      "candidate_set_sha256", "candidate_count"])) return false;
    if (source.controller_repository !== sources.ouroboros.repository
      || source.controller_revision !== sources.ouroboros.revision || source.workflow !== REVIEW_WORKFLOW
      || source.second_brain_repository !== sources.second_brain.repository
      || source.second_brain_revision !== sources.second_brain.revision
      || source.state_file_sha256 !== sources.second_brain.state_sha256
      || source.candidate_file_sha256 !== sources.second_brain.candidate_file_sha256
      || source.candidate_set_sha256 !== sources.second_brain.candidate_set_sha256
      || source.candidate_count !== sources.second_brain.candidate_count) return false;
    if (!exactKeys(value.authority, ["training", "promotion", "execution", "merge", "provider_mutation"])
      || !Object.values(value.authority).every((item) => item === "NONE")) return false;
    if (!exactKeys(value.claims, ["signature_verified", "review_is_accepted_truth", "production_verified",
      "private_graph_loaded", "measurement_scope"]) || value.claims.signature_verified !== false
      || value.claims.review_is_accepted_truth !== false || value.claims.production_verified !== false
      || value.claims.private_graph_loaded !== false
      || value.claims.measurement_scope !== "RECORDED_REVIEW_ATTEMPT") return false;
    const run = value.run;
    if (run !== null && (!exactKeys(run, ["id", "attempt", "head_sha", "status", "conclusion", "url", "updated_at"])
      || !positiveInteger(run.id) || !positiveInteger(run.attempt) || !matches(run.head_sha, REVISION)
      || !["queued", "in_progress", "completed", "waiting", "pending", "requested"].includes(run.status)
      || (run.conclusion !== null && !["success", "failure", "cancelled", "skipped", "timed_out",
        "action_required", "neutral", "stale", "startup_failure"].includes(run.conclusion))
      || run.url !== `https://github.com/szl-holdings/szl-ouroboros/actions/runs/${run.id}`
      || typeof run.updated_at !== "string" || !Number.isFinite(Date.parse(run.updated_at)))) return false;
    const freshness = value.freshness;
    if (!exactKeys(freshness, ["observed_at", "expires_at", "max_age_seconds"])
      || freshness.max_age_seconds !== 21600) return false;
    if (freshness.observed_at !== null || freshness.expires_at !== null) {
      if (!run || freshness.observed_at !== run.updated_at
        || typeof freshness.expires_at !== "string"
        || Date.parse(freshness.expires_at) - Date.parse(freshness.observed_at) !== 21600000) return false;
    }
    const measured = value.observation;
    if (!exactKeys(measured, ["bounded", "terminated", "receipt_closed", "steps", "max_budget", "wall_ms",
      "exit", "review_state", "review_sha256", "recommendation_count"])) return false;
    if (value.state !== "OBSERVED") {
      return value.artifact === null && Object.values(measured).every((item) => item === null);
    }
    const artifact = value.artifact;
    return run !== null && run.status === "completed" && run.conclusion === "success"
      && run.head_sha === source.controller_revision && freshness.observed_at !== null
      && exactKeys(artifact, ["id", "name", "archive_sha256", "receipt_sha256"])
      && positiveInteger(artifact.id) && artifact.name === `ouroboros-frontier-${run.id}-${run.attempt}`
      && matches(artifact.archive_sha256, DIGEST) && matches(artifact.receipt_sha256, DIGEST)
      && measured.bounded === true && measured.terminated === true && measured.receipt_closed === true
      && measured.steps === 1 && measured.max_budget === 1
      && typeof measured.wall_ms === "number" && Number.isFinite(measured.wall_ms) && measured.wall_ms >= 0
      && measured.exit === "converged" && ["REVIEW_PROPOSED", "NO_ACTION_RECOMMENDED"].includes(measured.review_state)
      && matches(measured.review_sha256, DIGEST)
      && Number.isSafeInteger(measured.recommendation_count) && measured.recommendation_count >= 0
      && measured.recommendation_count <= 12;
  }

  function validateAdvisoryDag(value, sources) {
    if (!exactKeys(value, ["ok", "schema", "graph_id", "contract_digest", "plan_id", "implementation_status",
      "evidence_label", "decision", "execution", "topology", "contracts", "gates", "normalized_contract"])) return false;
    if (value.ok !== true || value.schema !== "szl.governed-graph.analysis/v1"
      || !matches(value.contract_digest, DIGEST) || value.implementation_status !== "REAL"
      || value.evidence_label !== "MODELED" || value.decision !== "READY_TO_ORCHESTRATE"
      || value.plan_id !== `ggp-${value.contract_digest.slice(0, 20)}`) return false;
    const execution = value.execution;
    if (!exactKeys(execution, ["mode", "authorized", "effectors", "provider_calls", "writes", "note"])
      || execution.mode !== "PLAN_ONLY" || execution.authorized !== false || execution.effectors !== 0
      || execution.provider_calls !== 0 || execution.writes !== 0 || typeof execution.note !== "string") return false;
    const graph = value.normalized_contract;
    if (!exactKeys(graph, ["schema", "graph_id", "goal", "external_inputs", "nodes", "anchors", "budget"])
      || graph.schema !== "szl.governed-graph/v1" || graph.graph_id !== value.graph_id
      || graph.graph_id !== `brain-frontier-review-${sources.second_brain.candidate_set_sha256.slice(0, 20)}`
      || typeof graph.goal !== "string" || graph.goal.length > 2048
      || !sameList(graph.external_inputs, [`brain-candidates:sha256:${sources.second_brain.candidate_set_sha256}`,
        `ouroboros-controller:git:${sources.ouroboros.revision}`])
      || !Array.isArray(graph.nodes) || !sameList(graph.nodes.map((node) => node?.id), LOOP)) return false;
    const dependencies = [[], ["OBSERVE"], ["ORIENT"], ["OBSERVE", "PROPOSE"], ["VERIFY"]];
    const roles = ["scope", "reducer", "loop", "verifier", "governance"];
    const inputs = [graph.external_inputs, ["source.packet"], ["review.input"],
      ["source.packet", "untrusted.review"], ["advisory.observation"]];
    const outputs = ["source.packet", "review.input", "untrusted.review", "advisory.observation", "public.aggregate"];
    if (!graph.nodes.every((node, index) => exactKeys(node, ["id", "label", "role", "depends_on", "control_after",
      "consumes", "produces", "reads", "writes", "resources", "fresh_context", "verifier_for", "side_effecting",
      "authority", "max_iterations", "exit_conditions"]) && node.role === roles[index]
      && typeof node.label === "string" && node.label.length <= 128 && sameList(node.depends_on, dependencies[index])
      && ["control_after", "reads", "writes", "resources"].every((key) => sameList(node[key], []))
      && ["consumes", "produces", "exit_conditions", "verifier_for"].every((key) => Array.isArray(node[key])
        && node[key].length <= 8 && node[key].every((item) => typeof item === "string" && item.length <= 128))
      && node.side_effecting === false && node.authority === (index === 2 ? "PROPOSE" : "READ_ONLY")
      && sameList(node.consumes, inputs[index]) && sameList(node.produces, [outputs[index]])
      && node.fresh_context === (index === 3) && sameList(node.verifier_for, index === 3 ? ["PROPOSE"] : [])
      && node.max_iterations === (index === 2 ? 1 : null)
      && sameList(node.exit_conditions, index === 2 ? ["review_returned", "review_failed", "budget_exhausted"] : []))) return false;
    if (!exactKeys(graph.budget, ["max_nodes", "max_parallel", "max_depth", "max_total_iterations"])
      || graph.budget.max_nodes !== 5 || graph.budget.max_parallel !== 1 || graph.budget.max_depth !== 5
      || graph.budget.max_total_iterations !== 1 || !Array.isArray(graph.anchors) || graph.anchors.length !== 1) return false;
    const anchor = graph.anchors[0];
    const expectedTopology = {
      node_count: 5, data_edge_count: 5, control_edge_count: 0, layer_count: 5,
      max_declared_parallel: 1, scheduled_parallel_cap: 1, layers: LOOP.map((id) => [id]),
      schedule: LOOP.map((id, index) => ({batch: index, topology_layer: index, nodes: [id]})),
      critical_path: LOOP, critical_path_nodes: 5, terminals: ["HOLD"],
      edges: dependencies.flatMap((parents, index) => parents.map((id) =>
        ({source: id, target: LOOP[index], kind: "data"}))),
    };
    const expectedContracts = {fake_edges: [], input_gaps: [], hidden_resource_edges: [], fan_in: [],
      anchor_types: ["source"], anchored_nodes: ["HOLD", "OBSERVE", "VERIFY"], bounded_loop_iterations: 1};
    const expectedGates = {pass: true, blocker_count: 0, advisory_count: 0, blockers: [], advisories: []};
    return exactKeys(anchor, ["id", "type", "nodes", "required", "description"])
      && anchor.id === "exact-source-and-advisory-boundary" && anchor.type === "source" && anchor.required === true
      && sameList(anchor.nodes, ["OBSERVE", "VERIFY", "HOLD"]) && typeof anchor.description === "string"
      && canonicalJson(value.topology) === canonicalJson(expectedTopology)
      && canonicalJson(value.contracts) === canonicalJson(expectedContracts)
      && canonicalJson(value.gates) === canonicalJson(expectedGates);
  }

  function effectiveObservationState(payload, now = Date.now()) {
    const value = payload?.ouroboros_observation;
    if (!value) return "UNAVAILABLE";
    if (value.state !== "OBSERVED") return value.state;
    if (Date.parse(value.freshness.observed_at) > now + 300000) return "REJECTED";
    return Date.parse(value.freshness.expires_at) <= now ? "STALE" : "OBSERVED";
  }

  function validateHandle(handle) {
    if (!exactKeys(handle, ["nodeId", "title", "sha256", "repository", "revision", "path",
      "kind", "admission", "candidateState", "contentAccess", "authority"], ["quantDomain", "revisionKind"])) return false;
    if (!matches(handle.nodeId, HANDLE_ID)) return false;
    if (!matches(handle.sha256, DIGEST)) return false;
    if (!SOURCE_REPOSITORIES.has(handle.repository)) return false;
    if (!HANDLE_KINDS.has(handle.kind)) return false;
    if (handle.kind === "research-metadata" || RESEARCH_REPOSITORIES.has(handle.repository)) {
      if (handle.kind !== "research-metadata" || !RESEARCH_REPOSITORIES.has(handle.repository)
        || handle.revisionKind !== METADATA_REVISION_KIND || !matches(handle.revision, DIGEST)
        || !safeTitle(handle.title) || handle.admission !== "DISCOVERED_REVIEW_REQUIRED"
        || Object.hasOwn(handle, "quantDomain")) return false;
      const identifier = handle.repository === "public-metadata/arxiv"
        ? /^\d{4}\.\d{4,5}v[1-9]\d{0,2}$/ : /^10\.\d{4,9}\/[a-z0-9._;()/:-]{1,180}$/;
      if (!matches(handle.path, identifier)) return false;
    } else if (!matches(handle.revision, REVISION) || Object.hasOwn(handle, "revisionKind")
      || !safeTitle(handle.title) || !safePath(handle.path)) return false;
    if (!HANDLE_ADMISSIONS.has(handle.admission)) return false;
    if (handle.kind === "forum-insight" || handle.repository === FORUM_REPOSITORY) {
      if (handle.kind !== "forum-insight" || handle.repository !== FORUM_REPOSITORY
        || handle.path !== FORUM_PATH || handle.admission !== "DISCOVERED_REVIEW_REQUIRED"
        || Object.hasOwn(handle, "quantDomain")) return false;
    }
    if (Object.hasOwn(handle, "quantDomain") && !safeDomain(handle.quantDomain)) return false;
    if (handle.kind === "quant-domain" && !safeDomain(handle.quantDomain)) return false;
    if (handle.candidateState !== "DISCOVERED_REVIEW_REQUIRED") return false;
    if (handle.contentAccess !== "HANDLES_ONLY") return false;
    if (handle.authority !== "NONE") return false;
    if (Object.hasOwn(handle, "content") || Object.hasOwn(handle, "text")) return false;
    return true;
  }

  function validatePayload(payload) {
    if (!exactKeys(payload, ["schema", "state", "surface", "snapshot_sha256", "handles",
      "selected_handle_count", "sources", "formula_atlas", "authority", "loop"],
    ["ouroboros_observation", "advisory_dag"])) return false;
    const hasObservation = Object.hasOwn(payload, "ouroboros_observation");
    if (hasObservation !== Object.hasOwn(payload, "advisory_dag")) return false;
    if (payload.schema !== "szl.a11oy.brain-frontier-holographic-v7/v1") return false;
    if (payload.state !== "SOURCE_BOUND_REVIEW_MEMORY") return false;
    if (payload.surface !== "A11OY_HOLOGRAPHIC_V7_BRAIN_FRONTIER") return false;
    if (!matches(payload.snapshot_sha256, DIGEST)) return false;
    if (!Array.isArray(payload.handles) || payload.handles.length !== 72) return false;
    if (!payload.handles.every(validateHandle)) return false;
    if (new Set(payload.handles.map((handle) => handle.nodeId)).size !== 72) return false;
    const repositories = new Set(payload.handles.map((handle) => handle.repository));
    if (![...REQUIRED_SOURCE_REPOSITORIES].every((repository) => repositories.has(repository))) return false;
    if (payload.selected_handle_count !== payload.handles.length) return false;
    const kindCount = (kind) => payload.handles.filter((handle) => handle.kind === kind).length;
    if (kindCount("forum-insight") > 2) return false;
    if (kindCount("formula-authority") !== 1 || kindCount("attributed-formula") !== 30
      || kindCount("executable-formula") !== 21 || kindCount("quant-domain") !== 9) return false;
    const domains = new Set(payload.handles.filter((handle) => handle.kind === "quant-domain")
      .map((handle) => handle.quantDomain));
    if (domains.size !== 9 || payload.handles.some((handle) => handle.quantDomain
      && !domains.has(handle.quantDomain))) return false;
    if (!Array.isArray(payload.loop) || payload.loop.length !== LOOP.length
      || !payload.loop.every((step, index) => step === LOOP[index])) return false;
    if (!exactKeys(payload.sources, ["second_brain", "anatomy", "formulas", "ouroboros"])) return false;
    const brain = payload.sources?.second_brain;
    const anatomy = payload.sources?.anatomy;
    const formula = payload.formula_atlas;
    const authority = payload.authority;
    if (!exactKeys(brain, ["repository", "revision", "candidate_set_sha256", "candidate_count",
      "state_sha256", "candidate_file_sha256"])) return false;
    if (brain.repository !== "szl-holdings/szl-second-brain" || !matches(brain.revision, REVISION)) return false;
    if (![brain.candidate_set_sha256, brain.state_sha256, brain.candidate_file_sha256]
      .every((digest) => matches(digest, DIGEST))) return false;
    if (!Number.isSafeInteger(brain.candidate_count) || brain.candidate_count < 72) return false;
    if (!exactKeys(anatomy, ["repository", "revision", "live_origin", "holographic_v7_path"])) return false;
    if (anatomy.repository !== "szl-holdings/anatomy" || !matches(anatomy.revision, REVISION)) return false;
    if (anatomy.live_origin !== "https://betterwithage-anatomy.hf.space"
      || anatomy.holographic_v7_path !== "/api/anatomy/v1/holographic-v7") return false;
    const formulas = payload.sources.formulas;
    const ouroboros = payload.sources.ouroboros;
    if (!exactKeys(formulas, ["repository", "revision"]) || formulas.repository !== "szl-holdings/szl-formulas"
      || !matches(formulas.revision, REVISION)) return false;
    if (!exactKeys(ouroboros, ["repository", "revision", "review_workflow"])
      || ouroboros.repository !== "szl-holdings/szl-ouroboros" || !matches(ouroboros.revision, REVISION)
      || ouroboros.review_workflow !== (hasObservation ? REVIEW_WORKFLOW : ".github/workflows/codex-frontier-review.yml")) return false;
    if (hasObservation && (!validateObservation(payload.ouroboros_observation, payload.sources)
      || !validateAdvisoryDag(payload.advisory_dag, payload.sources))) return false;
    if (!exactKeys(formula, ["attributed_formula_count", "executable_formula_count", "quant_domain_count",
      "locked_proven_formula_count", "f_number_to_executable_mapping", "lambda"])) return false;
    if (formula.attributed_formula_count !== 30) return false;
    if (formula.executable_formula_count !== 21 || formula.quant_domain_count !== 9) return false;
    if (formula.locked_proven_formula_count !== 8) return false;
    if (formula.f_number_to_executable_mapping !== "UNKNOWN_NOT_INFERRED") return false;
    if (formula.lambda !== "CONJECTURE_1") return false;
    if (!exactKeys(authority, ["public_content_access", "controller_content_access", "training", "promotion",
      "execution", "merge", "provider_mutation", "private_graph_present", "raw_graph_nodes_admitted_to_gradients",
      "human_review_required"])) return false;
    if (authority.public_content_access !== "HANDLES_ONLY"
      || authority.controller_content_access !== "NOT_EXPOSED_BY_A11OY_HOLOGRAPHIC") return false;
    if (authority.training !== "NONE" || authority.promotion !== "NONE") return false;
    if (authority.execution !== "NONE" || authority.merge !== "NONE") return false;
    if (authority.provider_mutation !== "NONE" || authority.private_graph_present !== false) return false;
    if (authority.raw_graph_nodes_admitted_to_gradients !== 0) return false;
    if (authority.human_review_required !== true) return false;
    return true;
  }

  function canonicalJson(value) {
    // The validated schema has ASCII keys, Unicode scalar strings and safe integers only.
    // This matches the materializer's sorted compact JSON encoded as UTF-8.
    if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
    if (record(value)) return `{${Object.keys(value).sort().map((key) =>
      `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
    return JSON.stringify(value);
  }

  async function verifySnapshot(payload) {
    if (!validatePayload(payload) || !window.crypto?.subtle) return false;
    const { snapshot_sha256: expected, ...body } = payload;
    try {
      const bytes = new TextEncoder().encode(canonicalJson(body));
      if (bytes.byteLength > MAX_SNAPSHOT_BYTES) return false;
      const digest = await window.crypto.subtle.digest("SHA-256", bytes);
      const measured = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
      if (measured !== expected) return false;
      if (payload.ouroboros_observation) {
        const { observation_sha256, ...observation } = payload.ouroboros_observation;
        for (const [value, hash] of [[observation, observation_sha256],
          [payload.advisory_dag.normalized_contract, payload.advisory_dag.contract_digest]]) {
          const inner = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(value)));
          if ([...new Uint8Array(inner)].map((byte) => byte.toString(16).padStart(2, "0")).join("") !== hash) return false;
        }
      }
      return true;
    } catch (_error) {
      return false;
    }
  }

  async function readSnapshot(response) {
    if (!response.headers.get("content-type")?.split(";", 1)[0].trim().match(/^application\/json$/i)) {
      throw new Error("SNAPSHOT_CONTENT_TYPE_REJECTED");
    }
    if (!response.body) throw new Error("SNAPSHOT_BODY_UNAVAILABLE");
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_SNAPSHOT_BYTES) throw new Error("SNAPSHOT_SIZE_REJECTED");
        chunks.push(value);
      }
    } catch (error) {
      await reader.cancel().catch(() => {});
      throw error;
    } finally {
      reader.releaseLock();
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  }

  async function loadSnapshot() {
    if (state.loading) return;
    state.loading = true;
    state.payload = null;
    window.clearTimeout(state.expiryTimer);
    renderAll();
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
      const payload = await readSnapshot(response);
      if (!await verifySnapshot(payload)) throw new Error("SNAPSHOT_CONTRACT_REJECTED");
      state.payload = payload;
      if (payload.ouroboros_observation?.state === "OBSERVED") {
        const delay = Date.parse(payload.ouroboros_observation.freshness.expires_at) - Date.now() + 1;
        if (delay > 0) state.expiryTimer = window.setTimeout(renderMetrics, Math.min(delay, 21600001));
      }
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
              <p class="bf7__subtitle" id="bf7-subtitle">Second Brain handles, formula authority, quant domains and recorded Ouroboros review observations. Public metadata and advisory topology; human admission is required.</p>
            </div>
            <button class="bf7__close" type="button" aria-label="Close Brain Frontier">×</button>
          </header>
          <div class="bf7__metrics" aria-label="Brain Frontier metrics">
            <div class="bf7__metric"><span class="bf7__metric-label">Review handles</span><strong class="bf7__metric-value" data-bf7-metric="handles">Loading</strong></div>
            <div class="bf7__metric"><span class="bf7__metric-label">Formula tissue</span><strong class="bf7__metric-value" data-bf7-metric="formulas">—</strong></div>
            <div class="bf7__metric"><span class="bf7__metric-label">Quant domains</span><strong class="bf7__metric-value" data-bf7-metric="domains">—</strong></div>
            <div class="bf7__metric"><span class="bf7__metric-label">Review attempt</span><strong class="bf7__metric-value" data-bf7-metric="loop">UNAVAILABLE</strong></div>
          </div>
          <div class="bf7__graph-shell">
            <canvas id="${CANVAS_ID}" role="img" aria-label="Graph of source handles around the A11oy review hold"></canvas>
            <span class="bf7__graph-label">Advisory plan only · observe → orient → propose → verify → hold</span>
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
            <span>${handle.revisionKind === METADATA_REVISION_KIND ? "Metadata SHA-256 " : "Git "}${escapeHtml(short(handle.revision, 8))}</span>
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
    const reviewState = effectiveObservationState(payload);
    metric("loop", reviewState, reviewState === "OBSERVED" ? "live" : "warn");

    const dot = document.querySelector("[data-bf7-dot]");
    const stateLabel = document.querySelector("[data-bf7-state]");
    const digest = document.querySelector("[data-bf7-digest]");
    if (dot) dot.dataset.state = ready ? "live" : "offline";
    if (stateLabel) stateLabel.textContent = ready
      ? `Exact source snapshot · review ${reviewState} · human admission required`
      : "Unavailable · no green synthesized";
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
        : handle.repository === "szl-holdings/szl-ouroboros"
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
