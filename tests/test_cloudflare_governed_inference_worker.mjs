import assert from "node:assert/strict";
import test from "node:test";

import {
  buildContract,
  canonicalJson,
  extractModelText,
  handleRequest,
  normalizeInferenceRequest,
  observeSecondBrain,
  sanitizeModelOutput,
  sha256Hex,
  verifyDoctrine,
} from "../cloudflare/a11oy-governed-inference-worker.mjs";

const REVISION = "a".repeat(40);
const DOCTRINE = {
  organ: "a11oy",
  git_sha: "b".repeat(40),
  doctrine_lock: {
    doctrine: "v11",
    state: "LOCKED",
    lambda: "Conjecture 1",
    locked_formula_count: 8,
    locked_formula_ids: ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
  },
  locked_formula_count: 8,
  locked_formula_ids: ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
};
const BRAIN = {
  schema: "szl.khipu-second-brain-runtime/v1",
  state: "BLOCKED_ARTIFACT_AND_EVAL_GATES",
  ready_for_grounded_navigation: false,
  public_chunk_count: 0,
};

function evidenceFetch(url) {
  if (String(url).endsWith("/api/a11oy/v1/honest")) {
    return Promise.resolve(Response.json(DOCTRINE));
  }
  if (String(url).endsWith("/api/a11oy/v1/ayllu/second-brain")) {
    return Promise.resolve(Response.json(BRAIN));
  }
  return Promise.resolve(Response.json({ error: "not_found" }, { status: 404 }));
}

function request(path, init) {
  return new Request(`https://a-11-oy.com${path}`, init);
}

test("canonical JSON is key-order stable and SHA-256 is deterministic", async () => {
  assert.equal(canonicalJson({ b: 2, a: { d: 4, c: 3 } }), '{"a":{"c":3,"d":4},"b":2}');
  assert.equal(await sha256Hex("same"), await sha256Hex("same"));
  assert.notEqual(await sha256Hex("same"), await sha256Hex("different"));
});

test("doctrine verifier requires exact locked eight and Conjecture 1", () => {
  const verified = verifyDoctrine(DOCTRINE);
  assert.equal(verified.state, "LOCKED");
  assert.equal(verified.lambda_status, "CONJECTURE_1_ADVISORY");
  assert.equal(verified.lambda_can_authorize, false);
  assert.throws(
    () =>
      verifyDoctrine({
        ...DOCTRINE,
        doctrine_lock: { ...DOCTRINE.doctrine_lock, lambda: "Theorem" },
      }),
    /doctrine_not_locked/,
  );
  assert.throws(
    () =>
      verifyDoctrine({
        ...DOCTRINE,
        locked_formula_ids: ["F1"],
      }),
    /doctrine_not_locked/,
  );
});

test("request normalization bounds fields, evidence, effort, and tokens", () => {
  assert.deepEqual(
    normalizeInferenceRequest({
      prompt: "  prove it  ",
      evidence: [{ text: "operator evidence", source: "case-1" }],
      effort: "frontier",
      max_new_tokens: 128,
    }),
    {
      prompt: "prove it",
      evidence: [{ id: "U1", text: "operator evidence", source: "case-1" }],
      effort: "frontier",
      max_new_tokens: 128,
    },
  );
  assert.throws(
    () => normalizeInferenceRequest({ prompt: "x", tools: [] }),
    /unsupported_input_field/,
  );
  assert.throws(
    () => normalizeInferenceRequest({ prompt: "", effort: "fast" }),
    /invalid_prompt/,
  );
  assert.throws(
    () => normalizeInferenceRequest({ prompt: "x", effort: "unbounded" }),
    /invalid_effort/,
  );
});

test("model response extraction supports chat and strips reasoning blocks", () => {
  assert.equal(
    extractModelText({ choices: [{ message: { content: "answer" } }] }),
    "answer",
  );
  assert.equal(
    sanitizeModelOutput("<think>secret reasoning</think>\nFinal [E0]"),
    "Final [E0]",
  );
});

test("contract keeps external runtime, owned artifact, and action authority distinct", () => {
  const contract = buildContract(REVISION);
  assert.equal(contract.source_revision, REVISION);
  assert.equal(contract.runtime.action_authority, "NONE");
  assert.equal(contract.runtime.tools, false);
  assert.equal(contract.owned_model.repository, "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF");
  assert.equal(contract.owned_model.served_by_this_runtime, false);
  assert.equal(contract.governance.lambda.can_authorize, false);
});

test("health is READY only with exact source, AI binding, and locked doctrine", async () => {
  const response = await handleRequest(
    request("/api/v2/governed-health"),
    { SZL_SOURCE_REVISION: REVISION, AI: { run: async () => ({}) } },
    evidenceFetch,
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.status, "READY");
  assert.equal(body.source_revision, REVISION);
  assert.equal(body.doctrine.state, "LOCKED");
  assert.equal(body.second_brain.ready_for_grounded_navigation, false);
  assert.equal(body.owned_model_served, false);

  const missingAi = await handleRequest(
    request("/api/v2/governed-health"),
    { SZL_SOURCE_REVISION: REVISION },
    evidenceFetch,
  );
  assert.equal(missingAi.status, 503);
  assert.equal((await missingAi.json()).status, "UNAVAILABLE");
});

test("governed inference emits proposal-only receipt without raw prompt persistence", async () => {
  const calls = [];
  const env = {
    SZL_SOURCE_REVISION: REVISION,
    AI: {
      async run(model, input) {
        calls.push({ model, input });
        return {
          choices: [
            {
              message: {
                content:
                  "<think>private chain</think>The doctrine keeps Lambda advisory [E0]. The supplied fact is bounded [U1].",
              },
            },
          ],
        };
      },
    },
  };
  const prompt = "Explain the control boundary without executing anything.";
  const response = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        prompt,
        evidence: [{ text: "A bounded operator fact.", source: "operator" }],
      }),
    }),
    env,
    evidenceFetch,
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("x-szl-governed-inference"), "v1");
  const body = await response.json();
  assert.equal(body.state, "PROPOSAL");
  assert.equal(body.decision, "review");
  assert.equal(body.executed, false);
  assert.equal(body.authority_state, "NO_ACTION_AUTHORITY");
  assert.equal(body.tool_execution, false);
  assert.equal(body.model.kind, "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE");
  assert.equal(body.model.owned_model_served, false);
  assert.equal(body.formula_authority.lambda.can_authorize, false);
  assert.deepEqual(body.citations, ["E0", "U1"]);
  assert.equal(body.nemo.length, 2);
  assert.equal(body.nemo[0].decision, "ALLOW_PROPOSAL_ONLY");
  assert.equal(body.receipt.signature.status, "UNSIGNED_EDGE");
  assert.equal(body.receipt.prompt_or_evidence_text_persisted, false);
  assert.equal(
    body.receipt.receipt_sha256,
    await sha256Hex(canonicalJson(body.receipt.payload)),
  );
  assert.equal(JSON.stringify(body.receipt).includes(prompt), false);
  assert.equal(
    body.anatomy_observation.event.private_reasoning_present,
    false,
  );
  assert.equal(body.output.includes("private chain"), false);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].model, "@cf/deepseek-ai/deepseek-v4.1-flash-1017");
  assert.equal("tools" in calls[0].input, false);
  assert.equal(calls[0].input.store, false);
});

test("frontier model falls back without changing proposal-only boundary", async () => {
  const models = [];
  const env = {
    SZL_SOURCE_REVISION: REVISION,
    AI: {
      async run(model) {
        models.push(model);
        if (models.length === 1) throw new Error("candidate unavailable");
        return { response: "Fallback proposal [E0]." };
      },
    },
  };
  const response = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "Bounded request", effort: "frontier" }),
    }),
    env,
    evidenceFetch,
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.deepEqual(models, [
    "@cf/zai-org/glm-5.3",
    "@cf/deepseek-ai/deepseek-v4.1-flash-1017",
  ]);
  assert.equal(body.model.fallback_count, 1);
  assert.equal(body.authority_state, "NO_ACTION_AUTHORITY");
});

test("lora effort serves the estate-trained finetune with honest labeling", async () => {
  const runs = [];
  const env = {
    SZL_SOURCE_REVISION: REVISION,
    AI: {
      async run(model, options) {
        runs.push({ model, options });
        return { response: "Bounded lora proposal [E0]." };
      },
    },
  };
  const response = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "Bounded request", effort: "lora" }),
    }),
    env,
    evidenceFetch,
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(runs.length, 1);
  assert.equal(runs[0].model, "@cf/mistral/mistral-7b-instruct-v0.2-lora");
  assert.equal(runs[0].options.lora, "21892cd9-b4ca-4032-8058-280835c0402a");
  assert.equal(runs[0].options.reasoning_effort, undefined);
  assert.equal(runs[0].options.store, undefined);
  assert.equal(
    body.model.kind,
    "SZL_TRAINED_LORA_ADAPTER_ON_CLOUDFLARE",
  );
  assert.equal(
    body.model.finetune_id,
    "21892cd9-b4ca-4032-8058-280835c0402a",
  );
  assert.equal(
    body.model.finetune_adapter_repository,
    "SZLHOLDINGS/salad-lora-mistral7b-quant-v1",
  );
  assert.equal(body.model.owned_model_served, false);
  assert.equal(body.honesty.output_is_owned_khipu_inference, false);
  assert.equal(body.authority_state, "NO_ACTION_AUTHORITY");
  assert.equal(body.executed, false);
  assert.equal(
    body.receipt.payload.model_kind,
    "SZL_TRAINED_LORA_ADAPTER_ON_CLOUDFLARE",
  );
  assert.equal(
    body.receipt.payload.finetune_adapter_repository,
    "SZLHOLDINGS/salad-lora-mistral7b-quant-v1",
  );
  assert.equal(
    body.receipt.payload.owned_model_served,
    false,
  );
});

test("invalid calls and missing governance fail closed", async () => {
  const env = {
    SZL_SOURCE_REVISION: REVISION,
    AI: { run: async () => ({ response: "should not run" }) },
  };
  const wrongHost = await handleRequest(
    new Request("https://example.com/api/v2/governed-health"),
    env,
    evidenceFetch,
  );
  assert.equal(wrongHost.status, 421);

  const wrongType = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "text/plain" },
      body: "hello",
    }),
    env,
    evidenceFetch,
  );
  assert.equal(wrongType.status, 415);

  const governanceDown = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "hello" }),
    }),
    env,
    async () => Response.json({ error: "down" }, { status: 503 }),
  );
  assert.equal(governanceDown.status, 503);
  assert.equal(
    (await governanceDown.json()).authority_state,
    "NO_ACTION_AUTHORITY",
  );
});

test("Anatomy last endpoint refuses to fabricate durable observation", async () => {
  const response = await handleRequest(
    request("/api/v2/anatomy/last"),
    { SZL_SOURCE_REVISION: REVISION },
    evidenceFetch,
  );
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    schema: "szl.anatomy.last-observation/v1",
    state: "UNAVAILABLE_NO_DURABLE_BINDING",
    observer_authority: "NONE",
    persistence: "NONE",
    last: null,
  });
});

const COMPOUND_BRAIN = {
  schema: "szl.khipu.compound-second-brain.v1",
  state: "UNAVAILABLE_MODEL_TAG_MISSING",
  ready_for_grounded_navigation: false,
  profile: {
    profile_id: "BrainNavigator-v1",
    expected_model: "khipu:latest",
    served_model: null,
    exact_tag_observed: false,
    artifact_binding: "UNBOUND",
  },
  memory: {
    built: true,
    document_count: 55,
    corpus_chunk_count: 484,
    brain_handle_count: 9465,
    integrity_state: "VERIFIED_AT_PUBLISH",
    training_authority_rows: 0,
  },
};

test("canonical Second Brain counts remain independent of missing model readiness", () => {
  const observed = observeSecondBrain(COMPOUND_BRAIN);
  assert.equal(observed.state, "UNAVAILABLE_MODEL_TAG_MISSING");
  assert.equal(observed.ready_for_grounded_navigation, false);
  assert.equal(observed.public_chunk_count, null);
  assert.equal(observed.memory_observation.status, "OBSERVED_INDEX_METADATA");
  assert.equal(observed.memory_observation.document_count, 55);
  assert.equal(observed.memory_observation.corpus_chunk_count, 484);
  assert.equal(observed.memory_observation.brain_handle_count, 9465);
  assert.equal(observed.memory_observation.training_authority, "NONE");
  assert.equal(observed.model_binding.expected_model, "khipu:latest");
  assert.equal(observed.model_binding.served_model, null);
  assert.equal(observed.model_binding.exact_tag_observed, false);
  assert.equal(observed.content_access, "HANDLES_ONLY");
});

test("Second Brain metadata allowlist never forwards private graph or content", () => {
  const secret = "PRIVATE_CONTENT_SENTINEL";
  const observed = observeSecondBrain({
    ...COMPOUND_BRAIN,
    token: secret,
    body: secret,
    graph: { nodes: [secret] },
    memory: {
      ...COMPOUND_BRAIN.memory,
      content: secret,
      db_path: secret,
      documents: [secret],
      graph: [secret],
      training_authority_rows: 500,
    },
    profile: { ...COMPOUND_BRAIN.profile, token: secret },
  });
  assert.equal(JSON.stringify(observed).includes(secret), false);
  assert.equal(observed.memory_observation.training_authority, "NONE");
  assert.equal(observed.memory_observation.raw_content_included, false);
  assert.equal(observed.private_graph_present, false);
});

test("count validation rejects malformed data and preserves measured zero", () => {
  for (const invalid of [true, "7", -1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    const observed = observeSecondBrain({
      ...COMPOUND_BRAIN,
      memory: {
        ...COMPOUND_BRAIN.memory,
        document_count: invalid,
        corpus_chunk_count: invalid,
        brain_handle_count: invalid,
      },
      public_chunk_count: invalid,
    });
    assert.equal(observed.memory_observation.document_count, null);
    assert.equal(observed.memory_observation.corpus_chunk_count, null);
    assert.equal(observed.memory_observation.brain_handle_count, null);
    assert.equal(observed.public_chunk_count, null);
  }
  const zero = observeSecondBrain({
    ...COMPOUND_BRAIN,
    memory: { ...COMPOUND_BRAIN.memory, corpus_chunk_count: 0 },
    public_chunk_count: 0,
  });
  assert.equal(zero.memory_observation.corpus_chunk_count, 0);
  assert.equal(zero.public_chunk_count, 0);
});

test("unsupported or unbuilt memory cannot supply grounding or index evidence", () => {
  const unknown = observeSecondBrain({
    ...COMPOUND_BRAIN,
    schema: "unrelated/private/v1",
    ready_for_grounded_navigation: true,
  });
  assert.equal(unknown.state, "UNAVAILABLE_SCHEMA");
  assert.equal(unknown.ready_for_grounded_navigation, false);
  assert.equal(unknown.memory_observation.document_count, null);
  assert.equal(unknown.model_binding.expected_model, null);
  const unbuilt = observeSecondBrain({
    ...COMPOUND_BRAIN,
    memory: { ...COMPOUND_BRAIN.memory, built: false },
  });
  assert.equal(unbuilt.memory_observation.status, "UNAVAILABLE");
  assert.equal(unbuilt.memory_observation.corpus_chunk_count, null);
  assert.equal(observeSecondBrain(null).ready_for_grounded_navigation, false);
  const legacy = observeSecondBrain({ ...BRAIN, corpus_n: 999 });
  assert.equal(legacy.public_chunk_count, 0);
  const ambiguousLegacy = observeSecondBrain({ ...BRAIN, public_chunk_count: undefined, corpus_n: 999 });
  assert.equal(ambiguousLegacy.public_chunk_count, null);
});

test("contract publishes server input bounds and distinct identity semantics", () => {
  const contract = buildContract(REVISION);
  assert.equal(contract.input_limits.prompt_chars, 12000);
  assert.equal(contract.input_limits.evidence_items, 8);
  assert.deepEqual(contract.input_limits.max_new_tokens, { minimum: 16, default: 256, maximum: 768 });
  assert.equal(contract.observability.attempt_id, "SERVER_GENERATED_UUID_PER_INFERENCE_POST");
  assert.equal(contract.observability.attempt_id_in_receipt_digest, false);
  assert.equal(contract.observability.durable_trace_storage, false);
  assert.equal(contract.runtime.finetune.eval_status, "NOT_RUN");
});

test("identical requests get distinct attempt IDs without changing deterministic receipts", async () => {
  const env = {
    SZL_SOURCE_REVISION: REVISION,
    AI: { run: async () => ({ response: "Bounded output [E0]." }) },
  };
  const make = () => request("/api/v2/governed-infer", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt: "identical input", effort: "lora" }),
  });
  const firstResponse = await handleRequest(make(), env, evidenceFetch);
  const secondResponse = await handleRequest(make(), env, evidenceFetch);
  const first = await firstResponse.json();
  const second = await secondResponse.json();
  assert.equal(firstResponse.status, 200);
  assert.match(first.attempt_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.notEqual(first.attempt_id, second.attempt_id);
  assert.equal(firstResponse.headers.get("x-szl-attempt-id"), first.attempt_id);
  assert.equal(first.anatomy_observation.event.attempt_id, first.attempt_id);
  assert.equal(second.anatomy_observation.event.attempt_id, second.attempt_id);
  assert.equal(first.request_id, second.request_id);
  assert.equal(first.receipt.receipt_sha256, second.receipt.receipt_sha256);
  assert.equal("attempt_id" in first.receipt.payload, false);
  assert.equal(first.receipt.signature.status, "UNSIGNED_EDGE");
});

test("failed inference attempts have identity but never call the model", async () => {
  let calls = 0;
  const response = await handleRequest(request("/api/v2/governed-infer", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt: "hello", attempt_id: "client-spoofed" }),
  }), {
    SZL_SOURCE_REVISION: REVISION,
    AI: { run: async () => { calls += 1; return {}; } },
  }, evidenceFetch);
  const body = await response.json();
  assert.equal(response.status, 400);
  assert.equal(body.error, "unsupported_input_field");
  assert.notEqual(body.attempt_id, "client-spoofed");
  assert.equal(response.headers.get("x-szl-attempt-id"), body.attempt_id);
  assert.equal(body.executed, false);
  assert.equal(calls, 0);
});

test("canonical nested metadata reaches health and bounded model evidence without contents", async () => {
  let input;
  const fetchCanonical = (url) => String(url).endsWith("/ayllu/second-brain")
    ? Promise.resolve(Response.json(COMPOUND_BRAIN))
    : evidenceFetch(url);
  const env = {
    SZL_SOURCE_REVISION: REVISION,
    AI: { run: async (_model, options) => { input = options; return { response: "Index available; model unavailable [E1]." }; } },
  };
  const healthResponse = await handleRequest(request("/api/v2/governed-health"), env, fetchCanonical);
  const healthBody = await healthResponse.json();
  assert.equal(healthBody.second_brain.memory_observation.corpus_chunk_count, 484);
  assert.equal(healthBody.second_brain.ready_for_grounded_navigation, false);
  const response = await handleRequest(request("/api/v2/governed-infer", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt: "Summarize the observed index." }),
  }), env, fetchCanonical);
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.second_brain.memory_observation.brain_handle_count, 9465);
  assert.match(input.messages[1].content, /corpus_chunk_count=484/);
  assert.match(input.messages[1].content, /Counts do not grant content access/);
  assert.equal(body.honesty.action_authority, false);
  assert.equal(body.receipt.signature.status, "UNSIGNED_EDGE");
});

test("canonical readiness fails closed when index or exact model observation contradicts it", () => {
  const ready = {
    ...COMPOUND_BRAIN,
    ready_for_grounded_navigation: true,
    memory: { ...COMPOUND_BRAIN.memory, built: true },
    profile: { ...COMPOUND_BRAIN.profile, exact_tag_observed: true },
  };
  assert.equal(observeSecondBrain(ready).state, "READY");
  assert.equal(observeSecondBrain(ready).ready_for_grounded_navigation, true);
  for (const inconsistent of [
    { ...ready, memory: { ...ready.memory, built: false } },
    { ...ready, memory: undefined },
    { ...ready, profile: { ...ready.profile, exact_tag_observed: false } },
    { ...ready, profile: undefined },
    { ...ready, ready_for_grounded_navigation: false, state: "READY" },
  ]) {
    const observed = observeSecondBrain(inconsistent);
    assert.equal(observed.state, "UNAVAILABLE_INCONSISTENT_READINESS");
    assert.equal(observed.ready_for_grounded_navigation, false);
  }
  const legacy = observeSecondBrain({
    schema: "szl.khipu-second-brain-runtime/v1",
    ready_for_grounded_navigation: true,
  });
  assert.equal(legacy.state, "READY");
});

test("each model receives its documented token-bound field and no unsupported alias", async () => {
  for (const effort of ["fast", "frontier", "lora"]) {
    for (const maxNewTokens of [16, 128, 768]) {
      let observed;
      const response = await handleRequest(request("/api/v2/governed-infer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt: "Bounded proposal", effort, max_new_tokens: maxNewTokens }),
      }), {
        SZL_SOURCE_REVISION: REVISION,
        AI: { run: async (_model, options) => { observed = options; return { response: "Proposal [E0]." }; } },
      }, evidenceFetch);
      assert.equal(response.status, 200);
      const expected = effort === "lora" ? "max_tokens" : "max_completion_tokens";
      const unsupported = effort === "lora" ? "max_completion_tokens" : "max_tokens";
      assert.equal(observed[expected], maxNewTokens);
      assert.equal(unsupported in observed, false);
      assert.equal(observed.raw, undefined);
    }
  }
});
