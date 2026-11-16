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

// Keep this corpus aligned with test_a11oy_governed_cortex.py.
for (const [name, raw, expected] of [
  [
    "plain answer",
    "Final [E0]",
    "Final [E0]"
  ],
  [
    "balanced think",
    "<think>private-a</think>\nFinal [E0]",
    "Final [E0]"
  ],
  [
    "balanced analysis",
    "<analysis>private-a</analysis>Final [E0]",
    "Final [E0]"
  ],
  [
    "balanced analysis fence",
    "```analysis\nprivate-a\n```\nFinal [E0]",
    "Final [E0]"
  ],
  [
    "mixed case",
    "<ThInK>private-a</ThInK><ANALYSIS>private-b</ANALYSIS>Final [E0]",
    "Final [E0]"
  ],
  [
    "nested same tags",
    "<think>private-a<think>private-b</think>private-c</think>Final [E0]",
    "Final [E0]"
  ],
  [
    "nested mixed tags",
    "<think>private-a<analysis>private-b</analysis>private-c</think>Final [E0]",
    "Final [E0]"
  ],
  [
    "multiple blocks",
    "First <think>private-a</think> last [E0]<analysis>private-b</analysis>",
    "First  last [E0]"
  ],
  [
    "ordinary code fence",
    "```python\nprint('ok')\n```",
    "```python\nprint('ok')\n```"
  ],
  [
    "unrelated tag names",
    "<thinker>display</thinker> <analysis_result>result</analysis_result>",
    "<thinker>display</thinker> <analysis_result>result</analysis_result>"
  ],
  [
    "unrelated fence language",
    "```analysis_json\n{}\n```",
    "```analysis_json\n{}\n```"
  ],
  [
    "XML text inside analysis fence",
    "```analysis\n<think>private-a\n```\nFinal [E0]",
    "Final [E0]"
  ],
  [
    "analysis fence inside think",
    "<think>private-a\n```analysis\nprivate-b\n```\nprivate-c</think>Final [E0]",
    "Final [E0]"
  ]
]) {
  test(`reasoning boundary preserves safe output: ${name}`, () => {
    assert.equal(sanitizeModelOutput(raw), expected);
  });
}

for (const [name, raw] of [
  [
    "orphan think close",
    "private-a</think>Final [E0]"
  ],
  [
    "orphan analysis close",
    "private-a</analysis>Final [E0]"
  ],
  [
    "unclosed think",
    "<think>private-a"
  ],
  [
    "unclosed analysis",
    "Final [E0]<analysis>private-a"
  ],
  [
    "truncated opening marker",
    "Final [E0]<think"
  ],
  [
    "truncated closing marker",
    "private-a</think"
  ],
  [
    "unsupported tag attributes",
    "<think role=\"private\">private-a</think>Final [E0]"
  ],
  [
    "unsupported tag whitespace",
    "< think >private-a</think>Final [E0]"
  ],
  [
    "unsupported fence whitespace",
    "``` analysis\nprivate-a\n```Final [E0]"
  ],
  [
    "unclosed analysis fence",
    "```analysis\nprivate-a"
  ],
  [
    "unclosed outer same tag",
    "<think>private-a<think>private-b</think>private-c"
  ],
  [
    "crossed tags",
    "<think>private-a<analysis>private-b</think>private-c</analysis>Final [E0]"
  ],
  [
    "reverse crossed tags",
    "<analysis>private-a<think>private-b</analysis>private-c</think>Final [E0]"
  ],
  [
    "nested analysis fences",
    "```analysis\nprivate-a```analysis\nprivate-b```\nFinal [E0]"
  ],
  [
    "extra closing tag",
    "<think>private-a</think>private-b</think>Final [E0]"
  ],
  [
    "code opener inside analysis fence",
    "```analysis\nprivate-a\n```python\nprivate-b\n```"
  ],
  [
    "inline backticks inside analysis fence",
    "```analysis\nprivate-a ``` private-b\n```"
  ],
  [
    "longer delimiter inside analysis fence",
    "```analysis\nprivate-a\n````analysis\nprivate-b\n```"
  ],
  [
    "inline closing analysis fence",
    "```analysis\nprivate-a```Final [E0]"
  ]
]) {
  test(`reasoning boundary rejects malformed output: ${name}`, () => {
    assert.throws(
      () => sanitizeModelOutput(raw),
      /model_reasoning_boundary_invalid/,
    );
  });
}

test("reasoning boundary checks the entire output before truncation", () => {
  assert.equal(sanitizeModelOutput("x".repeat(24_001)).length, 24_000);
  const ordinaryText = "<" + " ".repeat(16_000) + "x";
  assert.equal(sanitizeModelOutput(ordinaryText), ordinaryText);
  assert.throws(
    () => sanitizeModelOutput("x".repeat(24_001) + "</think>"),
    /model_reasoning_boundary_invalid/,
  );
  for (const raw of [" ", "<think>private-a</think>", "```analysis\nprivate-a\n```"]) {
    assert.throws(() => sanitizeModelOutput(raw), /empty_model_output/);
  }
});

test("malformed candidate output fails closed without a receipt or response text", async () => {
  const response = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "Bounded request", effort: "fast" }),
    }),
    {
      SZL_SOURCE_REVISION: REVISION,
      AI: { run: async () => ({ response: "private-marker</think>Final [E0]" }) },
    },
    evidenceFetch,
  );
  assert.equal(response.status, 502);
  const body = await response.json();
  assert.equal(body.error, "all_model_candidates_failed");
  assert.equal(body.authority_state, "NO_ACTION_AUTHORITY");
  assert.equal(body.executed, false);
  assert.equal(body.receipt, undefined);
  assert.equal(JSON.stringify(body).includes("private-marker"), false);
});

test("malformed candidate output can fall back to a clean candidate", async () => {
  let calls = 0;
  const response = await handleRequest(
    request("/api/v2/governed-infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "Bounded request", effort: "fast" }),
    }),
    {
      SZL_SOURCE_REVISION: REVISION,
      AI: {
        run: async () => ({
          response: ++calls === 1
            ? "private-marker</think>Final [E0]"
            : "Clean final [E0]",
        }),
      },
    },
    evidenceFetch,
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(calls, 2);
  assert.equal(body.model.fallback_count, 1);
  assert.equal(body.output, "Clean final [E0]");
  assert.equal(JSON.stringify(body).includes("private-marker"), false);
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
