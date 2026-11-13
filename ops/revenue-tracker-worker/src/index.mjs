// Request tracker for the a-11-oy.com API routes. It forwards every request
// unchanged and records one Analytics Engine point per request so that people
// can be told apart from automation before any revenue figure is trusted.
// It stores no IP address, user agent, query string or cookie: visitors are a
// daily-rotating HMAC that cannot be reversed or linked across days without
// the secret, and is UNAVAILABLE when no secret is configured.

const SCHEMA = "v2";
const VISITOR_KEY_HEX = 32;
const MIN_SECRET_LENGTH = 32;
const encoder = new TextEncoder();

const CRAWLER = /bot\b|bot\/|crawl|spider|slurp|headless|lighthouse|facebookexternalhit|preview|monitor|uptime|pingdom|scan/i;
const CLI = /^(curl|wget|httpie|xh)\//i;
const LIBRARY = /^(python-requests|python-urllib|python-httpx|httpx|aiohttp|go-http-client|node-fetch|undici|node|axios|okhttp|java\/|libwww|scrapy|postmanruntime|insomnia|deno|bun)\b/i;
const BROWSER = /^Mozilla\/5\.0 .*(Chrome|Firefox|Safari|Edg|OPR)\//;

const INFERENCE_HOST = "inference.a-11-oy.com";
const INFERENCE_PATHS = ["/v1/completions", "/v1/chat/", "/v1/responses"];

function isInferenceRequest(request) {
  const url = new URL(request.url);
  return url.hostname === INFERENCE_HOST
    && INFERENCE_PATHS.some((path) => url.pathname.startsWith(path));
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Payment-Signature, X-PAYMENT",
    "Access-Control-Expose-Headers": "PAYMENT-REQUIRED, PAYMENT-RESPONSE",
    "Access-Control-Max-Age": "600",
  };
}

export function classifyClient(userAgent, verifiedBotCategory) {
  if (verifiedBotCategory) return "verified-bot";
  const ua = (userAgent || "").trim();
  if (!ua) return "empty";
  if (CRAWLER.test(ua)) return "crawler";
  if (CLI.test(ua)) return "cli";
  if (LIBRARY.test(ua)) return "library";
  if (BROWSER.test(ua)) return "browser";
  return "other";
}

export async function visitorKey(secret, day, ip, userAgent) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const tag = await crypto.subtle.sign("HMAC", key,
    encoder.encode(`szl-visitor-v1\0${day}\0${ip}\0${userAgent}`));
  return [...new Uint8Array(tag)].map((byte) => byte.toString(16).padStart(2, "0"))
    .join("").slice(0, VISITOR_KEY_HEX);
}

function usableSecret(secret) {
  return typeof secret === "string" && secret.length >= MIN_SECRET_LENGTH;
}

async function dataPoint(request, env, status, startedMs, finishedMs) {
  const url = new URL(request.url);
  const cf = request.cf || {};
  const userAgent = request.headers.get("user-agent") || "";
  const verified = typeof cf.verifiedBotCategory === "string" ? cf.verifiedBotCategory : "";
  let key = "";
  let keyState = "UNAVAILABLE";
  const ip = request.headers.get("cf-connecting-ip");
  if (usableSecret(env.VISITOR_KEY_SECRET) && ip) {
    const day = new Date(startedMs).toISOString().slice(0, 10);
    key = await visitorKey(env.VISITOR_KEY_SECRET, day, ip, userAgent);
    keyState = "HMAC_DAILY";
  }
  return {
    indexes: [url.pathname],
    blobs: [
      SCHEMA, request.method, url.pathname, url.hostname,
      typeof cf.country === "string" ? cf.country : "",
      cf.asn === undefined || cf.asn === null ? "" : String(cf.asn),
      typeof cf.colo === "string" ? cf.colo : "",
      classifyClient(userAgent, verified), verified, key, keyState,
    ],
    doubles: [startedMs, status, finishedMs - startedMs],
  };
}

async function record(request, env, status, startedMs, finishedMs) {
  if (!env.ANALYTICS) return "no-binding";
  try {
    env.ANALYTICS.writeDataPoint(await dataPoint(request, env, status, startedMs, finishedMs));
    return "written";
  } catch {
    return "error";
  }
}

export async function handleRequest(request, env, fetchImpl = fetch, now = Date.now) {
  const startedMs = now();
  if (request.method === "OPTIONS" && isInferenceRequest(request)) {
    const state = await record(request, env, 204, startedMs, now());
    const headers = new Headers(corsHeaders());
    headers.set("x-szl-tracker", state);
    return new Response(null, { status: 204, headers });
  }
  let response;
  try {
    response = await fetchImpl(request);
  } catch (error) {
    await record(request, env, 0, startedMs, now());
    throw error;
  }
  const state = await record(request, env, response.status, startedMs, now());
  const tracked = new Response(response.body, response);
  tracked.headers.set("x-szl-tracker", state);
  if (isInferenceRequest(request)) {
    for (const [name, value] of Object.entries(corsHeaders())) tracked.headers.set(name, value);
  }
  return tracked;
}

export default {
  fetch(request, env) {
    return handleRequest(request, env);
  },
};
