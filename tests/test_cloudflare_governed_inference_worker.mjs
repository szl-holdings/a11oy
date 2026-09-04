import assert from "node:assert/strict";
import test from "node:test";

import {
  buildContract,
  canonicalJson,
  extractModelText,
  handleRequest,
  normalizeInferenceRequest,
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
  assert.equal(calls[0].model, "@cf/zai-org/glm-4.7-flash");
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
    "@cf/google/gemma-4-26b-a4b-it",
    "@cf/zai-org/glm-4.7-flash",
  ]);
  assert.equal(body.model.fallback_count, 1);
  assert.equal(body.authority_state, "NO_ACTION_AUTHORITY");
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
