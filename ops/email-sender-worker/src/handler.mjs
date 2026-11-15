// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
//
// Server-to-server mail endpoint. No CORS: no estate browser caller exists, so
// a browser can never be handed the bearer secret. Every failure is JSON.

import { MessageInputError, assertAddress, buildMimeMessage } from "./mime.mjs";

export const WORKER_NAME = "szl-email-sender";
// Email Routing's send_email binding only signs mail for the zone it runs on.
export const SENDER_DOMAIN = "a-11-oy.com";
export const REVISION_PATH = "/.well-known/szl-worker-revision";
export const SEND_PATHS = new Set(["/send", "/"]);
export const MAX_REQUEST_BYTES = 64 * 1024;
export const MIN_SECRET_LENGTH = 32;

const REQUEST_FIELDS = new Set(["to", "subject", "body"]);
const REVISION = /^[0-9a-f]{40}$/;
const BEARER = /^Bearer +([\x21-\x7e]+)$/i;

class PayloadTooLargeError extends Error {}

function json(status, payload, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      ...extraHeaders,
    },
  });
}

function sourceRevision(env) {
  const value = env?.SOURCE_REVISION;
  return typeof value === "string" && REVISION.test(value) ? value : null;
}

/** Returns the validated sender address, or null when configuration is unusable. */
export function configuredSender(env) {
  const secret = env?.API_SECRET;
  if (typeof secret !== "string" || secret.length < MIN_SECRET_LENGTH) {
    return null;
  }
  if (!env.SEND_EMAIL || typeof env.SEND_EMAIL.send !== "function") {
    return null;
  }
  try {
    return assertAddress(env.MAIL_FROM, "invalid_from") === SENDER_DOMAIN ? env.MAIL_FROM : null;
  } catch {
    return null;
  }
}

async function sha256(value) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}

/**
 * Compares fixed-length SHA-256 digests so neither the content nor the length
 * of the configured secret influences timing.
 */
export async function secretMatches(presented, expected) {
  const [left, right] = await Promise.all([sha256(presented), sha256(expected)]);
  if (typeof crypto.subtle.timingSafeEqual === "function") {
    return crypto.subtle.timingSafeEqual(left, right);
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

async function readBoundedText(request, maxBytes) {
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) {
    throw new PayloadTooLargeError();
  }
  if (!request.body) {
    return "";
  }
  const reader = request.body.getReader();
  const chunks = [];
  let received = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      received += value.byteLength;
      if (received > maxBytes) {
        await reader.cancel().catch(() => {});
        throw new PayloadTooLargeError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new MessageInputError("invalid_encoding");
  }
}

function isJson(contentType) {
  const mediaType = (contentType ?? "").split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json";
}

function parseSendRequest(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new MessageInputError("invalid_json");
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new MessageInputError("invalid_json");
  }
  for (const key of Object.keys(payload)) {
    if (!REQUEST_FIELDS.has(key)) {
      throw new MessageInputError("unknown_field");
    }
  }
  for (const key of REQUEST_FIELDS) {
    if (!Object.hasOwn(payload, key)) {
      throw new MessageInputError("missing_field");
    }
  }
  return payload;
}

export async function handleRequest(
  request,
  env,
  { EmailMessage, now = () => new Date(), newMessageId = () => crypto.randomUUID() } = {},
) {
  const url = new URL(request.url);

  if (url.pathname === REVISION_PATH) {
    if (request.method !== "GET") {
      return json(405, { error: "method_not_allowed" }, { allow: "GET" });
    }
    return json(200, {
      worker: WORKER_NAME,
      source_revision: sourceRevision(env),
      ready: configuredSender(env) !== null && typeof EmailMessage === "function",
    });
  }
  if (!SEND_PATHS.has(url.pathname)) {
    return json(404, { error: "not_found" });
  }
  if (request.method !== "POST") {
    return json(405, { error: "method_not_allowed" }, { allow: "POST" });
  }

  const from = configuredSender(env);
  if (from === null || typeof EmailMessage !== "function") {
    console.error(JSON.stringify({ event: "email_sender_not_configured" }));
    return json(503, { error: "not_configured" });
  }

  const presented = BEARER.exec(request.headers.get("authorization") ?? "");
  if (!presented || !(await secretMatches(presented[1], env.API_SECRET))) {
    return json(401, { error: "unauthorized" }, { "www-authenticate": "Bearer" });
  }
  if (!isJson(request.headers.get("content-type"))) {
    return json(415, { error: "unsupported_media_type" });
  }

  let payload;
  let raw;
  const messageId = newMessageId();
  try {
    payload = parseSendRequest(await readBoundedText(request, MAX_REQUEST_BYTES));
    raw = buildMimeMessage({
      from,
      to: payload.to,
      subject: payload.subject,
      body: payload.body,
      date: now(),
      messageId,
    });
  } catch (error) {
    if (error instanceof PayloadTooLargeError) {
      return json(413, { error: "payload_too_large" });
    }
    if (error instanceof MessageInputError) {
      return json(400, { error: error.code });
    }
    throw error;
  }

  try {
    await env.SEND_EMAIL.send(new EmailMessage(from, payload.to, raw));
  } catch (error) {
    // The provider message can name the recipient; log only the class.
    console.error(
      JSON.stringify({
        event: "email_send_failed",
        error_class: error instanceof Error ? error.name : "UnknownError",
      }),
    );
    return json(502, { error: "send_failed" });
  }
  console.log(JSON.stringify({ event: "email_sent", message_id: messageId }));
  return json(200, {
    success: true,
    to: payload.to,
    message_id: `<${messageId}@${SENDER_DOMAIN}>`,
  });
}
