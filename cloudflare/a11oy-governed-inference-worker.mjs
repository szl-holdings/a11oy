/*
 * A11oy governed inference edge v1.
 *
 * Public authority: proposal-only inference on /api/v2/*.
 * Model authority: Cloudflare-hosted external candidate; never mislabeled as the
 * owned SZL Khipu GGUF. Tools and consequential action authority are absent.
 * Persistence: none. Receipts are deterministic, unsigned edge evidence.
 */

const PRODUCT_HOST = "a-11-oy.com";
const API_PREFIX = "/api/v2/";
const EDGE_VERSION = "a11oy-governed-inference-v1";
const CONTRACT_SCHEMA = "szl.cloudflare-governed-inference-contract/v1";
const RESPONSE_SCHEMA = "szl.cloudflare-governed-inference-response/v1";
const RECEIPT_SCHEMA = "szl.cloudflare-governed-inference-receipt/v1";
const DOCTRINE_URL = "https://a-11-oy.com/api/a11oy/v1/honest";
const SECOND_BRAIN_URL =
  "https://a-11-oy.com/api/a11oy/v1/ayllu/second-brain";
const LOCKED_FORMULAS = Object.freeze([
  "F1",
  "F4",
  "F7",
  "F11",
  "F12",
  "F18",
  "F19",
  "F22",
]);
const OWNED_MODEL_ARTIFACT = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF";
const MODEL_CANDIDATES = Object.freeze({
  fast: Object.freeze([
    "@cf/zai-org/glm-4.7-flash",
    "@cf/google/gemma-4-26b-a4b-it",
  ]),
  frontier: Object.freeze([
    "@cf/google/gemma-4-26b-a4b-it",
    "@cf/zai-org/glm-4.7-flash",
  ]),
});
const MAX_BODY_BYTES = 65536;
const MAX_PROMPT_CHARS = 12000;
const MAX_EVIDENCE_ITEMS = 8;
const MAX_EVIDENCE_ITEM_CHARS = 4000;
const MAX_EVIDENCE_TOTAL_CHARS = 12000;
const MAX_OUTPUT_CHARS = 24000;
const ALLOWED_INPUT_KEYS = new Set([
  "prompt",
  "effort",
  "evidence",
  "max_new_tokens",
]);

class GovernedError extends Error {
  constructor(code, status = 400) {
    super(code);
    this.name = "GovernedError";
    this.code = code;
    this.status = status;
  }
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    const result = {};
    for (const key of Object.keys(value).sort()) {
      result[key] = canonicalize(value[key]);
    }
    return result;
  }
  return value;
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

export async function sha256Hex(value) {
  const bytes =
    value instanceof Uint8Array
      ? value
      : new TextEncoder().encode(String(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function exactStringArray(value, expected) {
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    value.every((item, index) => item === expected[index])
  );
}

export function verifyDoctrine(value) {
  const body = value && typeof value === "object" ? value : {};
  const lock =
    body.doctrine_lock && typeof body.doctrine_lock === "object"
      ? body.doctrine_lock
      : {};
  const ids = body.locked_formula_ids ?? lock.locked_formula_ids;
  const count = body.locked_formula_count ?? lock.locked_formula_count;
  if (
    body.organ !== "a11oy" ||
    lock.doctrine !== "v11" ||
    lock.state !== "LOCKED" ||
    lock.lambda !== "Conjecture 1" ||
    count !== LOCKED_FORMULAS.length ||
    !exactStringArray(ids, LOCKED_FORMULAS)
  ) {
    throw new GovernedError("doctrine_not_locked", 503);
  }
  return {
    doctrine: "v11",
    state: "LOCKED",
    lambda: "Conjecture 1",
    lambda_status: "CONJECTURE_1_ADVISORY",
    lambda_can_authorize: false,
    locked_formula_count: LOCKED_FORMULAS.length,
    locked_formula_ids: [...LOCKED_FORMULAS],
    observed_git_sha:
      typeof body.git_sha === "string" ? body.git_sha : null,
  };
}

function safeInteger(value, fallback, minimum, maximum) {
  if (value === undefined || value === null) return fallback;
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new GovernedError("invalid_max_new_tokens");
  }
  return value;
}

function normalizeEvidence(raw) {
  if (raw === undefined || raw === null) return [];
  if (!Array.isArray(raw) || raw.length > MAX_EVIDENCE_ITEMS) {
    throw new GovernedError("invalid_evidence");
  }
  let total = 0;
  return raw.map((item, index) => {
    let text;
    let source = "operator_supplied";
    if (typeof item === "string") {
      text = item.trim();
    } else if (item && typeof item === "object" && !Array.isArray(item)) {
      const keys = Object.keys(item);
      if (keys.some((key) => !["text", "source"].includes(key))) {
        throw new GovernedError("invalid_evidence");
      }
      text = typeof item.text === "string" ? item.text.trim() : "";
      if (item.source !== undefined) {
        if (
          typeof item.source !== "string" ||
          item.source.length > 512 ||
          /[\u0000-\u001f\u007f]/u.test(item.source)
        ) {
          throw new GovernedError("invalid_evidence_source");
        }
        source = item.source.trim() || source;
      }
    } else {
      throw new GovernedError("invalid_evidence");
    }
    if (!text || text.length > MAX_EVIDENCE_ITEM_CHARS) {
      throw new GovernedError("invalid_evidence");
    }
    total += text.length;
    if (total > MAX_EVIDENCE_TOTAL_CHARS) {
      throw new GovernedError("evidence_too_large");
    }
    return {
      id: `U${index + 1}`,
      source,
      text,
    };
  });
}

export function normalizeInferenceRequest(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new GovernedError("invalid_json_object");
  }
  if (Object.keys(value).some((key) => !ALLOWED_INPUT_KEYS.has(key))) {
    throw new GovernedError("unsupported_input_field");
  }
  const prompt =
    typeof value.prompt === "string" ? value.prompt.trim() : "";
  if (!prompt || prompt.length > MAX_PROMPT_CHARS) {
    throw new GovernedError("invalid_prompt");
  }
  const effort = value.effort === undefined ? "fast" : value.effort;
  if (!["fast", "frontier"].includes(effort)) {
    throw new GovernedError("invalid_effort");
  }
  return {
    prompt,
    effort,
    evidence: normalizeEvidence(value.evidence),
    max_new_tokens: safeInteger(value.max_new_tokens, 256, 16, 768),
  };
}

function jsonHeaders(extra = {}) {
  return {
    "access-control-allow-headers": "content-type",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-origin": "*",
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-szl-edge": EDGE_VERSION,
    ...extra,
  };
}

function jsonResponse(value, status = 200, extraHeaders = {}) {
  return new Response(canonicalJson(value), {
    status,
    headers: jsonHeaders(extraHeaders),
  });
}

function errorResponse(code, status = 400) {
  return jsonResponse(
    {
      schema: "szl.cloudflare-governed-inference-error/v1",
      error: code,
      executed: false,
      authority_state: "NO_ACTION_AUTHORITY",
    },
    status,
  );
}

async function fetchJson(fetchImpl, url) {
  let response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: {
        accept: "application/json",
        "cache-control": "no-cache, no-store, max-age=0",
        "user-agent": "a11oy-cloudflare-governed-inference/1",
      },
      cache: "no-store",
    });
  } catch (_) {
    throw new GovernedError("governance_evidence_unavailable", 503);
  }
  if (!response || response.status !== 200) {
    throw new GovernedError("governance_evidence_unavailable", 503);
  }
  try {
    const body = await response.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      throw new Error("not_object");
    }
    return body;
  } catch (_) {
    throw new GovernedError("governance_evidence_invalid", 503);
  }
}

function readCount(value, keys) {
  for (const key of keys) {
    const candidate = value?.[key];
    if (Number.isInteger(candidate) && candidate >= 0) return candidate;
  }
  return null;
}

function observeSecondBrain(value, available = true) {
  if (!available || !value || typeof value !== "object") {
    return {
      endpoint: SECOND_BRAIN_URL,
      state: "UNAVAILABLE",
      ready_for_grounded_navigation: false,
      public_chunk_count: null,
      private_graph_present: false,
      content_access: "HANDLES_ONLY",
    };
  }
  const ready = value.ready_for_grounded_navigation === true;
  const publicChunkCount = readCount(value, [
    "public_chunk_count",
    "indexed_chunk_count",
    "corpus_n",
    "chunks",
  ]);
  return {
    endpoint: SECOND_BRAIN_URL,
    state: ready
      ? "READY"
      : String(value.status || value.state || "NOT_READY").toUpperCase(),
    ready_for_grounded_navigation: ready,
    public_chunk_count: publicChunkCount,
    private_graph_present: false,
    content_access: "HANDLES_ONLY",
  };
}

async function loadGovernanceEvidence(fetchImpl) {
  const doctrineBody = await fetchJson(fetchImpl, DOCTRINE_URL);
  const doctrine = verifyDoctrine(doctrineBody);
  let secondBrain;
  try {
    const brainBody = await fetchJson(fetchImpl, SECOND_BRAIN_URL);
    secondBrain = observeSecondBrain(brainBody, true);
  } catch (_) {
    secondBrain = observeSecondBrain(null, false);
  }
  return { doctrine, secondBrain };
}

function sourceRevision(env) {
  const value = String(env?.SZL_SOURCE_REVISION || "").trim().toLowerCase();
  return /^[0-9a-f]{40}$/u.test(value) ? value : null;
}

function aiReady(env) {
  return Boolean(env?.AI && typeof env.AI.run === "function");
}

export function buildContract(revision) {
  return {
    schema: CONTRACT_SCHEMA,
    version: "1.0.0",
    source_repository: "szl-holdings/a11oy",
    source_revision: revision,
    endpoint: {
      health: "/api/v2/governed-health",
      contract: "/api/v2/governed-contract",
      infer: "/api/v2/governed-infer",
      anatomy_last: "/api/v2/anatomy/last",
    },
    runtime: {
      provider: "Cloudflare Workers AI",
      model_kind: "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE",
      candidates: {
        fast: [...MODEL_CANDIDATES.fast],
        frontier: [...MODEL_CANDIDATES.frontier],
      },
      tools: false,
      autonomous_execution: false,
      action_authority: "NONE",
      output_state: "PROPOSAL_ONLY",
      persistence: "NONE",
    },
    owned_model: {
      repository: OWNED_MODEL_ARTIFACT,
      served_by_this_runtime: false,
      authority: "ARTIFACT_AND_LINEAGE_ONLY",
    },
    governance: {
      doctrine_endpoint: DOCTRINE_URL,
      doctrine: "v11",
      expected_state: "LOCKED",
      locked_formula_count: LOCKED_FORMULAS.length,
      locked_formula_ids: [...LOCKED_FORMULAS],
      lambda: {
        status: "CONJECTURE_1_ADVISORY",
        can_authorize: false,
      },
      second_brain_endpoint: SECOND_BRAIN_URL,
      second_brain_private_graph_allowed: false,
      nemo: {
        pre_generation: "doctrine-v11/E1-E10-compatible-bounded-witness",
        post_generation: "doctrine-v11/R1-R5-compatible-output-witness",
        semantic_equivalence_to_szl_nemo: false,
      },
    },
    receipts: {
      schema: RECEIPT_SCHEMA,
      signature_status: "UNSIGNED_EDGE",
      deterministic_digest: "SHA-256 over RFC8785-style sorted JSON subset",
      prompt_or_evidence_text_persisted: false,
      durable_storage: false,
      must_be_signed_before_consequential_action: true,
    },
  };
}

function evidencePrompt(evidence) {
  return evidence
    .map((item) => `[${item.id}] ${item.source}: ${item.text}`)
    .join("\n");
}

function buildModelMessages(request, evidence) {
  const system = [
    "You are the bounded proposal-only inference cortex for A11oy.",
    "Return a concise final answer only; never expose chain-of-thought, hidden reasoning, or private memory.",
    "You have no tools and no authority to execute actions.",
    "Use only the supplied evidence handles. Cite supporting evidence inline as [E0], [E1], [U1], etc.",
    "When the evidence is insufficient, say that directly rather than inventing facts.",
    "Lambda is Conjecture 1 and advisory; it cannot authorize an action.",
  ].join(" ");
  const user = [
    `Operator request:\n${request.prompt}`,
    `\nEvidence:\n${evidencePrompt(evidence)}`,
    "\nProduce the final proposal. Do not output analysis or tool calls.",
  ].join("\n");
  return [
    { role: "system", content: system },
    { role: "user", content: user },
  ];
}

function hasToolCall(value) {
  if (!value || typeof value !== "object") return false;
  const direct = value.tool_calls;
  if (Array.isArray(direct) && direct.length > 0) return true;
  if (Array.isArray(value.choices)) {
    return value.choices.some((choice) => {
      const calls = choice?.message?.tool_calls;
      return Array.isArray(calls) && calls.length > 0;
    });
  }
  return false;
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((item) =>
        typeof item === "string"
          ? item
          : typeof item?.text === "string"
            ? item.text
            : "",
      )
      .join("");
  }
  return "";
}

export function extractModelText(value) {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return "";
  if (typeof value.response === "string") return value.response;
  if (value.response && typeof value.response === "object") {
    if (typeof value.response.answer === "string") return value.response.answer;
    if (typeof value.response.output === "string") return value.response.output;
  }
  const first = Array.isArray(value.choices) ? value.choices[0] : null;
  if (first?.message) {
    const text = contentText(first.message.content);
    if (text) return text;
  }
  if (typeof first?.text === "string") return first.text;
  if (value.result) return extractModelText(value.result);
  return "";
}

export function sanitizeModelOutput(value) {
  let text = String(value || "")
    .replace(/<think>[\s\S]*?<\/think>/giu, "")
    .replace(/<analysis>[\s\S]*?<\/analysis>/giu, "")
    .replace(/```analysis[\s\S]*?```/giu, "")
    .trim();
  if (!text) throw new GovernedError("empty_model_output", 502);
  if (text.length > MAX_OUTPUT_CHARS) {
    text = text.slice(0, MAX_OUTPUT_CHARS).trimEnd();
  }
  return text;
}

async function runModel(env, request, evidence) {
  if (!aiReady(env)) {
    throw new GovernedError("ai_binding_unavailable", 503);
  }
  const messages = buildModelMessages(request, evidence);
  const failures = [];
  for (const model of MODEL_CANDIDATES[request.effort]) {
    try {
      const raw = await env.AI.run(model, {
        messages,
        max_completion_tokens: request.max_new_tokens,
        reasoning_effort: request.effort === "frontier" ? "high" : "low",
        seed: 17,
        store: false,
        stream: false,
        temperature: 0.2,
        top_p: 0.9,
      });
      if (hasToolCall(raw)) {
        throw new GovernedError("model_attempted_tool_call", 502);
      }
      const output = sanitizeModelOutput(extractModelText(raw));
      return {
        model,
        output,
        fallback_count: failures.length,
      };
    } catch (error) {
      failures.push(
        error instanceof GovernedError ? error.code : "provider_candidate_failed",
      );
    }
  }
  throw new GovernedError("all_model_candidates_failed", 502);
}

function extractCitationHandles(output, allowed) {
  const found = [];
  const seen = new Set();
  for (const match of output.matchAll(/\[(E[01]|U[1-8])\]/gu)) {
    const id = match[1];
    if (allowed.has(id) && !seen.has(id)) {
      seen.add(id);
      found.push(id);
    }
  }
  return found;
}

async function publicEvidenceItems(governance, userEvidence) {
  const doctrineText =
    `Doctrine v11 is LOCKED. Lambda is Conjecture 1 and advisory. ` +
    `Locked formulas: ${LOCKED_FORMULAS.join(", ")}.`;
  const brain = governance.secondBrain;
  const brainText =
    `Second Brain state is ${brain.state}; ready_for_grounded_navigation=` +
    `${brain.ready_for_grounded_navigation}; public_chunk_count=` +
    `${brain.public_chunk_count === null ? "UNAVAILABLE" : brain.public_chunk_count}.`;
  const raw = [
    { id: "E0", source: DOCTRINE_URL, text: doctrineText },
    { id: "E1", source: SECOND_BRAIN_URL, text: brainText },
    ...userEvidence,
  ];
  const items = [];
  for (const item of raw) {
    items.push({
      ...item,
      sha256: await sha256Hex(item.text),
      characters: item.text.length,
    });
  }
  return items;
}

async function governedInference(request, env, fetchImpl) {
  const revision = sourceRevision(env);
  if (!revision) throw new GovernedError("source_revision_unavailable", 503);
  const governance = await loadGovernanceEvidence(fetchImpl);
  const evidence = await publicEvidenceItems(governance, request.evidence);
  const inputDescriptor = {
    source_revision: revision,
    prompt_sha256: await sha256Hex(request.prompt),
    evidence: evidence.map(({ id, source, sha256, characters }) => ({
      id,
      source,
      sha256,
      characters,
    })),
    effort: request.effort,
    max_new_tokens: request.max_new_tokens,
  };
  const evidenceSetSha256 = await sha256Hex(
    canonicalJson(inputDescriptor.evidence),
  );
  const preInputSha256 = await sha256Hex(canonicalJson(inputDescriptor));
  const generated = await runModel(env, request, evidence);
  const outputSha256 = await sha256Hex(generated.output);
  const allowedHandles = new Set(evidence.map((item) => item.id));
  const citations = extractCitationHandles(
    generated.output,
    allowedHandles,
  );
  const requestId = (
    await sha256Hex(
      canonicalJson({
        source_revision: revision,
        prompt_sha256: inputDescriptor.prompt_sha256,
        evidence_set_sha256: evidenceSetSha256,
        model: generated.model,
        effort: request.effort,
      }),
    )
  ).slice(0, 32);
  const formulaAuthority = {
    locked_proven_count: LOCKED_FORMULAS.length,
    locked_proven_ids: [...LOCKED_FORMULAS],
    lambda: {
      status: "CONJECTURE_1_ADVISORY",
      can_authorize: false,
    },
  };
  const receiptPayload = {
    schema: RECEIPT_SCHEMA,
    request_id: requestId,
    source_repository: "szl-holdings/a11oy",
    source_revision: revision,
    prompt_sha256: inputDescriptor.prompt_sha256,
    evidence_set_sha256: evidenceSetSha256,
    output_sha256: outputSha256,
    model: generated.model,
    model_kind: "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE",
    owned_model_artifact: OWNED_MODEL_ARTIFACT,
    owned_model_served: false,
    decision: "REVIEW_PROPOSAL_ONLY",
    authority_state: "NO_ACTION_AUTHORITY",
    executed: false,
    formula_authority: formulaAuthority,
  };
  const receiptSha256 = await sha256Hex(canonicalJson(receiptPayload));
  const postInputSha256 = await sha256Hex(
    canonicalJson({
      output_sha256: outputSha256,
      citations,
      authority_state: "NO_ACTION_AUTHORITY",
      executed: false,
    }),
  );

  return {
    schema: RESPONSE_SCHEMA,
    request_id: requestId,
    state: "PROPOSAL",
    decision: "review",
    output: generated.output,
    output_sha256: outputSha256,
    executed: false,
    authority_state: "NO_ACTION_AUTHORITY",
    tool_execution: false,
    source_revision: revision,
    model: {
      provider: "Cloudflare Workers AI",
      candidate: generated.model,
      kind: "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE",
      fallback_count: generated.fallback_count,
      owned_model_artifact: OWNED_MODEL_ARTIFACT,
      owned_model_served: false,
    },
    second_brain: governance.secondBrain,
    formula_authority: formulaAuthority,
    evidence_handles: evidence.map(
      ({ id, source, sha256, characters }) => ({
        id,
        source,
        sha256,
        characters,
      }),
    ),
    citations,
    citations_sha256: await sha256Hex(canonicalJson(citations)),
    claims: [
      {
        claim_sha256: outputSha256,
        status: "MODEL_PROPOSAL_UNVERIFIED",
        evidence_handles: citations,
      },
    ],
    claims_sha256: await sha256Hex(
      canonicalJson([
        {
          claim_sha256: outputSha256,
          status: "MODEL_PROPOSAL_UNVERIFIED",
          evidence_handles: citations,
        },
      ]),
    ),
    nemo: [
      {
        stage: "PRE_GENERATION",
        decision: "ALLOW_PROPOSAL_ONLY",
        input_sha256: preInputSha256,
        rule_version: "doctrine-v11/E1-E10-compatible-bounded-witness",
      },
      {
        stage: "POST_GENERATION",
        decision: "ALLOW_PROPOSAL_ONLY",
        input_sha256: postInputSha256,
        rule_version: "doctrine-v11/R1-R5-compatible-output-witness",
      },
    ],
    receipt: {
      schema: RECEIPT_SCHEMA,
      payload: receiptPayload,
      receipt_sha256: receiptSha256,
      signature: {
        status: "UNSIGNED_EDGE",
        durable: false,
        must_be_signed_before_consequential_action: true,
      },
      prompt_or_evidence_text_persisted: false,
    },
    anatomy_observation: {
      schema: "szl.anatomy.ephemeral-inference-observation/v1",
      delivery: "DELIVERED_INLINE",
      persistence: "EPHEMERAL_ISOLATE_NO_DURABLE_BINDING",
      observer_authority: "NONE",
      observed_at: new Date().toISOString(),
      event: {
        request_id: requestId,
        prompt_sha256: inputDescriptor.prompt_sha256,
        output_sha256: outputSha256,
        receipt_sha256: receiptSha256,
        raw_prompt_present: false,
        raw_evidence_present: false,
        private_reasoning_present: false,
        private_graph_present: false,
      },
    },
    honesty: {
      output_is_model_proposal: true,
      output_is_owned_khipu_inference: false,
      output_is_signed: false,
      durable_receipt_persistence: false,
      lambda_is_theorem: false,
      action_authority: false,
    },
  };
}

async function health(env, fetchImpl) {
  const revision = sourceRevision(env);
  let governance = null;
  let governanceError = null;
  try {
    governance = await loadGovernanceEvidence(fetchImpl);
  } catch (error) {
    governanceError =
      error instanceof GovernedError ? error.code : "governance_check_failed";
  }
  const ready = Boolean(revision && aiReady(env) && governance);
  return {
    schema: "szl.cloudflare-governed-inference-health/v1",
    status: ready ? "READY" : "UNAVAILABLE",
    source_revision: revision,
    ai_binding: aiReady(env),
    doctrine:
      governance?.doctrine ?? {
        state: "UNAVAILABLE",
        lambda_status: "CONJECTURE_1_ADVISORY",
        lambda_can_authorize: false,
      },
    second_brain:
      governance?.secondBrain ?? observeSecondBrain(null, false),
    model_kind: "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE",
    owned_model_artifact: OWNED_MODEL_ARTIFACT,
    owned_model_served: false,
    tools: false,
    action_authority: "NONE",
    receipt_persistence: "NONE",
    error: governanceError,
  };
}

async function parseRequestJson(request) {
  const length = Number(request.headers.get("content-length") || "0");
  if (Number.isFinite(length) && length > MAX_BODY_BYTES) {
    throw new GovernedError("request_too_large", 413);
  }
  const contentType = request.headers.get("content-type") || "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    throw new GovernedError("content_type_must_be_json", 415);
  }
  let raw;
  try {
    raw = await request.text();
  } catch (_) {
    throw new GovernedError("request_body_unreadable");
  }
  if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) {
    throw new GovernedError("request_too_large", 413);
  }
  try {
    return JSON.parse(raw);
  } catch (_) {
    throw new GovernedError("invalid_json");
  }
}

export async function handleRequest(request, env, fetchImpl = fetch) {
  try {
    const url = new URL(request.url);
    if (url.hostname !== PRODUCT_HOST) {
      return errorResponse("misdirected_request", 421);
    }
    if (!url.pathname.startsWith(API_PREFIX)) {
      return errorResponse("not_found", 404);
    }
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: jsonHeaders() });
    }
    if (
      url.pathname === "/api/v2/governed-health" &&
      request.method === "GET"
    ) {
      const body = await health(env, fetchImpl);
      return jsonResponse(body, body.status === "READY" ? 200 : 503);
    }
    if (
      url.pathname === "/api/v2/governed-contract" &&
      request.method === "GET"
    ) {
      return jsonResponse(buildContract(sourceRevision(env)));
    }
    if (
      url.pathname === "/api/v2/anatomy/last" &&
      request.method === "GET"
    ) {
      return jsonResponse({
        schema: "szl.anatomy.last-observation/v1",
        state: "UNAVAILABLE_NO_DURABLE_BINDING",
        observer_authority: "NONE",
        persistence: "NONE",
        last: null,
      });
    }
    if (url.pathname === "/api/v2/governed-infer") {
      if (request.method !== "POST") {
        return errorResponse("method_not_allowed", 405);
      }
      const normalized = normalizeInferenceRequest(
        await parseRequestJson(request),
      );
      return jsonResponse(
        await governedInference(normalized, env, fetchImpl),
        200,
        {
          "x-szl-governed-inference": "v1",
          "x-szl-source-revision": sourceRevision(env) || "unavailable",
        },
      );
    }
    return errorResponse("not_found", 404);
  } catch (error) {
    if (error instanceof GovernedError) {
      return errorResponse(error.code, error.status);
    }
    return errorResponse("internal_error", 500);
  }
}

export default {
  async fetch(request, env) {
    return handleRequest(request, env);
  },
};
