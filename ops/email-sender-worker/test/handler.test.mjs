// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_REQUEST_BYTES,
  REVISION_PATH,
  handleRequest,
  secretMatches,
} from "../src/handler.mjs";

const SECRET = "s".repeat(24) + "-synthetic-test-secret-0123456789";
const REVISION = "0123456789abcdef0123456789abcdef01234567";
const ORIGIN = "https://szl-email-sender.example.workers.dev";

// Stand-in for the workerd class: records exactly what the runtime receives.
class RecordingEmailMessage {
  constructor(from, to, raw) {
    this.from = from;
    this.to = to;
    this.raw = raw;
  }
}

function mockBinding({ fail = false } = {}) {
  const sent = [];
  return {
    sent,
    async send(message) {
      if (fail) {
        throw new Error(`destination ${message.to} is not verified`);
      }
      sent.push(message);
    },
  };
}

function environment(overrides = {}) {
  return {
    API_SECRET: SECRET,
    MAIL_FROM: "betterwithage@a-11-oy.com",
    SOURCE_REVISION: REVISION,
    SEND_EMAIL: mockBinding(),
    ...overrides,
  };
}

function sendRequest({
  path = "/send",
  method = "POST",
  token = SECRET,
  contentType = "application/json",
  payload = { to: "owner@example.org", subject: "Canary", body: "One bounded message." },
  body,
  headers = {},
} = {}) {
  const init = {
    method,
    headers: {
      ...(token === null ? {} : { authorization: `Bearer ${token}` }),
      ...(contentType === null ? {} : { "content-type": contentType }),
      ...headers,
    },
  };
  if (method !== "GET" && method !== "HEAD") {
    init.body = body ?? JSON.stringify(payload);
  }
  return new Request(`${ORIGIN}${path}`, init);
}

async function call(request, env = environment(), options = {}) {
  const response = await handleRequest(request, env, {
    EmailMessage: RecordingEmailMessage,
    now: () => new Date(Date.UTC(2026, 10, 6, 16, 20, 0)),
    newMessageId: () => "00000000-0000-4000-8000-000000000001",
    ...options,
  });
  return { response, payload: await response.json() };
}

function assertJsonError(response) {
  assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("access-control-allow-origin"), null);
}

test("an authenticated request sends one EmailMessage with matching MIME", async () => {
  const env = environment();
  const { response, payload } = await call(sendRequest(), env);
  assert.equal(response.status, 200);
  assert.deepEqual(payload, {
    success: true,
    to: "owner@example.org",
    message_id: "<00000000-0000-4000-8000-000000000001@a-11-oy.com>",
  });
  assert.equal(env.SEND_EMAIL.sent.length, 1);
  const [message] = env.SEND_EMAIL.sent;
  assert.ok(message instanceof RecordingEmailMessage);
  assert.equal(message.from, "betterwithage@a-11-oy.com");
  assert.equal(message.to, "owner@example.org");
  assert.match(message.raw, /^From: betterwithage@a-11-oy\.com\r\nTo: owner@example\.org\r\nSubject: Canary\r\n/);
  assert.match(message.raw, /\r\nMessage-ID: <00000000-0000-4000-8000-000000000001@a-11-oy\.com>\r\n/);
  const body = message.raw.slice(message.raw.indexOf("\r\n\r\n") + 4).replace(/\r\n/g, "");
  assert.equal(Buffer.from(body, "base64").toString("utf8"), "One bounded message.");
});

test("the legacy root path keeps the deployed request contract", async () => {
  const env = environment();
  const { response } = await call(sendRequest({ path: "/" }), env);
  assert.equal(response.status, 200);
  assert.equal(env.SEND_EMAIL.sent.length, 1);
});

test("bearer authentication fails closed before the body is read", async () => {
  for (const token of [null, "", "wrong", `${SECRET}x`, SECRET.slice(1), SECRET.toUpperCase()]) {
    const env = environment();
    const request = token === "" ? sendRequest({ token: null, headers: { authorization: "Bearer " } }) : sendRequest({ token });
    const { response, payload } = await call(request, env);
    assert.equal(response.status, 401, `token ${JSON.stringify(token)}`);
    assert.deepEqual(payload, { error: "unauthorized" });
    assert.equal(response.headers.get("www-authenticate"), "Bearer");
    assert.equal(env.SEND_EMAIL.sent.length, 0);
    assert.equal(request.bodyUsed, false);
    assertJsonError(response);
  }
  const basic = sendRequest({ token: null, headers: { authorization: `Basic ${btoa(`api:${SECRET}`)}` } });
  assert.equal((await call(basic)).response.status, 401);
  const lowerScheme = sendRequest({ token: null, headers: { authorization: `bearer ${SECRET}` } });
  assert.equal((await call(lowerScheme)).response.status, 200);
});

test("an unset, short, or undefined secret never authenticates anything", async () => {
  for (const API_SECRET of [undefined, "", "undefined", "short-secret", "x".repeat(31)]) {
    const env = environment({ API_SECRET });
    for (const token of ["undefined", "", API_SECRET ?? "x"]) {
      const { response, payload } = await call(sendRequest({ token }), env);
      assert.equal(response.status, 503);
      assert.deepEqual(payload, { error: "not_configured" });
    }
    assert.equal(env.SEND_EMAIL.sent.length, 0);
  }
});

test("a sender outside the verified domain or a missing binding is not configured", async () => {
  for (const overrides of [
    { MAIL_FROM: "alerts@example.org" },
    { MAIL_FROM: "alerts@sub.a-11-oy.com" },
    { MAIL_FROM: "Alerts <alerts@a-11-oy.com>" },
    { MAIL_FROM: undefined },
    { SEND_EMAIL: undefined },
    { SEND_EMAIL: {} },
  ]) {
    const { response, payload } = await call(sendRequest(), environment(overrides));
    assert.equal(response.status, 503, JSON.stringify(overrides));
    assert.deepEqual(payload, { error: "not_configured" });
  }
  const { response } = await call(sendRequest(), environment(), { EmailMessage: undefined });
  assert.equal(response.status, 503);
});

test("header injection and multi-recipient attempts are rejected before sending", async () => {
  const cases = [
    [{ to: "owner@example.org\r\nBcc: attacker@example.net", subject: "s", body: "b" }, "invalid_to"],
    [{ to: "owner@example.org, attacker@example.net", subject: "s", body: "b" }, "invalid_to"],
    [{ to: ["owner@example.org"], subject: "s", body: "b" }, "invalid_to"],
    [{ to: "owner@example.org", subject: "s\r\nBcc: attacker@example.net", body: "b" }, "invalid_subject"],
    [{ to: "owner@example.org", subject: "s\nX-Injected: 1", body: "b" }, "invalid_subject"],
    [{ to: "owner@example.org", subject: "s", body: "" }, "invalid_body"],
    [{ to: "owner@example.org", subject: "s", body: "b", bcc: "attacker@example.net" }, "unknown_field"],
    [{ to: "owner@example.org", subject: "s" }, "missing_field"],
  ];
  for (const [payload, code] of cases) {
    const env = environment();
    const { response, payload: result } = await call(sendRequest({ payload }), env);
    assert.equal(response.status, 400, code);
    assert.deepEqual(result, { error: code });
    assert.equal(env.SEND_EMAIL.sent.length, 0);
    assertJsonError(response);
  }
});

test("malformed, oversized, and non-JSON bodies return JSON errors", async () => {
  const env = environment();
  const checks = [
    [sendRequest({ body: "{" }), 400, "invalid_json"],
    [sendRequest({ body: "[]" }), 400, "invalid_json"],
    [sendRequest({ body: "null" }), 400, "invalid_json"],
    [sendRequest({ body: new Uint8Array([0x7b, 0xff, 0x7d]) }), 400, "invalid_encoding"],
    [sendRequest({ contentType: "text/plain" }), 415, "unsupported_media_type"],
    [sendRequest({ contentType: null }), 415, "unsupported_media_type"],
    [sendRequest({ body: "x".repeat(MAX_REQUEST_BYTES + 1) }), 413, "payload_too_large"],
    [
      sendRequest({ headers: { "content-length": String(MAX_REQUEST_BYTES + 1) }, body: "{}" }),
      413,
      "payload_too_large",
    ],
  ];
  for (const [request, status, error] of checks) {
    const { response, payload } = await call(request, env);
    assert.equal(response.status, status, error);
    assert.deepEqual(payload, { error });
    assertJsonError(response);
  }
  assert.equal(env.SEND_EMAIL.sent.length, 0);
});

test("CORS is off: preflight and other methods are refused without CORS headers", async () => {
  for (const method of ["OPTIONS", "GET", "PUT", "DELETE"]) {
    const { response, payload } = await call(sendRequest({ method, headers: { origin: "https://evil.example" } }));
    assert.equal(response.status, 405, method);
    assert.equal(response.headers.get("allow"), "POST");
    assert.deepEqual(payload, { error: "method_not_allowed" });
    assertJsonError(response);
  }
  const { response } = await call(sendRequest({ path: "/admin" }));
  assert.equal(response.status, 404);
});

test("provider failures return 502 and never echo the recipient", async (t) => {
  const logged = [];
  t.mock.method(console, "error", (line) => logged.push(line));
  const env = environment({ SEND_EMAIL: mockBinding({ fail: true }) });
  const { response, payload } = await call(sendRequest(), env);
  assert.equal(response.status, 502);
  assert.deepEqual(payload, { error: "send_failed" });
  assert.equal(logged.length, 1);
  assert.deepEqual(JSON.parse(logged[0]), { event: "email_send_failed", error_class: "Error" });
  assert.equal(logged[0].includes("owner@example.org"), false);
});

test("the revision endpoint reports the deployed SHA and readiness without auth", async () => {
  const ready = await call(new Request(`${ORIGIN}${REVISION_PATH}`));
  assert.equal(ready.response.status, 200);
  assert.deepEqual(ready.payload, { worker: "szl-email-sender", source_revision: REVISION, ready: true });

  for (const SOURCE_REVISION of [undefined, "", "d739c95b", REVISION.toUpperCase(), `${REVISION}0`]) {
    const { payload } = await call(new Request(`${ORIGIN}${REVISION_PATH}`), environment({ SOURCE_REVISION }));
    assert.equal(payload.source_revision, null);
  }
  const unready = await call(new Request(`${ORIGIN}${REVISION_PATH}`), environment({ API_SECRET: "short" }));
  assert.equal(unready.payload.ready, false);
  assert.equal(JSON.stringify(unready.payload).includes("short"), false);

  const post = await call(new Request(`${ORIGIN}${REVISION_PATH}`, { method: "POST" }));
  assert.equal(post.response.status, 405);
  assert.equal(post.response.headers.get("allow"), "GET");
});

test("secret comparison hashes both sides and needs exact equality", async () => {
  assert.equal(await secretMatches(SECRET, SECRET), true);
  assert.equal(await secretMatches(`${SECRET} `, SECRET), false);
  assert.equal(await secretMatches("", SECRET), false);
  assert.equal(await secretMatches("a", "b"), false);
});
