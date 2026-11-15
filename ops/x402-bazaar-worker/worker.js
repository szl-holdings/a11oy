// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
/**
 * Source-only x402 discovery shim; deployment remains owner-gated.
 * A payment header is a request for verification, not proof of payment.
 * Forward only through an explicitly configured PAYMENT_GATEWAY service
 * binding. Never use same-zone fetch or a caller-controlled bypass header.
 * The bound service must verify and settle before releasing inference.
 * Local tests cannot establish that the managed gateway is bindable,
 * that settlement succeeds, or that Bazaar accepts the discovery metadata.
 */
const BAZAAR_PASSTHROUGH_HEADER = "x-szl-bazaar-passthrough";
const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "Content-Type, PAYMENT-SIGNATURE, X-PAYMENT",
  "access-control-expose-headers": "PAYMENT-REQUIRED, PAYMENT-RESPONSE, EXTENSION-RESPONSES",
};
const ALLOWED_REQUEST_HEADERS = new Set(["content-type", "payment-signature", "x-payment"]);

// Parity constants — verified against the live gateway 402 (2026-11-15,
// probe from owner laptop, C:\SZL\edge-debug\bazaar_probe.txt).
const CHALLENGE = {
  x402Version: 2,
  resource: {
    url: "https://inference.a-11-oy.com/v1/chat/completions",
  },
  accepts: [
    {
      scheme: "exact",
      network: "eip155:8453",
      amount: "20000",
      asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      payTo: "0x7b133ef996852c223379d6d1245430300970291A",
      maxTimeoutSeconds: 3600,
      extra: { name: "USD Coin", version: "2" },
    },
  ],
  help: {
    docs: "https://developers.cloudflare.com/monetization-gateway/",
    spec: "https://github.com/x402-foundation/x402",
    instructions:
      "Pay by re-sending this request with a PAYMENT-SIGNATURE header carrying an authorization for the advertised payment requirement.\nScheme exact: the advertised amount is the full price. Authorize exactly that amount; any other figure is rejected.\nAmounts are atomic units of the asset's contract; decimals belong to the contract, not to the token name.\nIf you cannot authorize for that asset on that network, stop and report it. Do not retry unpaid.",
  },
};

// CDP x402 Bazaar discovery metadata (docs.cdp.coinbase.com/x402/seller/get-discovered).
// Non-SDK path: declare per-route metadata, validate via
// POST https://api.cdp.coinbase.com/platform/v2/x402/validate (no API key),
// then one PAID call triggers indexing (requires a funded wallet — owner item).
const BAZAAR_EXTENSION = {
  name: "x402-bazaar",
  version: "1",
  bazaar: {
    method: "POST",
    description:
      "SZL governed inference completions (Bonsai-2-27B) behind the a11oy x402 monetization wall. OpenAI-compatible chat completions; 0.02 USDC per request on Base.",
    input: {
      schema: {
        type: "object",
        required: ["model", "messages"],
        properties: {
          model: { type: "string", description: "Model identifier served by the origin." },
          messages: {
            type: "array",
            description: "OpenAI-style message list.",
            items: {
              type: "object",
              required: ["role", "content"],
              properties: {
                role: { type: "string", enum: ["system", "user", "assistant"] },
                content: { type: "string" },
              },
            },
          },
          max_tokens: { type: "integer", description: "Optional cap on generated tokens." },
        },
      },
      example: {
        model: "bonsai2-27b",
        messages: [{ role: "user", content: "Summarize the x402 payment flow in one paragraph." }],
      },
    },
    output: {
      example: {
        id: "chatcmpl-szl",
        object: "chat.completion",
        choices: [
          {
            index: 0,
            message: { role: "assistant", content: "The x402 flow returns HTTP 402 with an accepts block..." },
            finish_reason: "stop",
          },
        ],
        usage: { prompt_tokens: 12, completion_tokens: 48, total_tokens: 60 },
      },
    },
  },
};

function challengeBody() {
  const body = {
    ...JSON.parse(JSON.stringify(CHALLENGE)),
    error: "PAYMENT-SIGNATURE header is required",
  };
  body.extensions = JSON.parse(JSON.stringify(BAZAAR_EXTENSION));
  return JSON.stringify(body);
}

function responseHeaders(extra = {}) {
  return {
    "content-type": "application/json",
    "cache-control": "private, no-store",
    "x-szl-edge": "x402-bazaar-shim-v2",
    ...CORS_HEADERS,
    ...extra,
  };
}

function errorResponse(status, error, extra = {}) {
  return new Response(JSON.stringify({ error }), { status, headers: responseHeaders(extra) });
}

function encodePaymentRequired(body) {
  const bytes = new TextEncoder().encode(body);
  return btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
}

function hasSettlementSuccess(header) {
  // Defensive shape check only; the trusted gateway owns cryptographic verification.
  if (!header || header.length > 16384) return false;
  try {
    const result = JSON.parse(atob(header));
    return result?.success === true &&
      result.network === CHALLENGE.accepts[0].network &&
      typeof result.transaction === "string" && result.transaction.trim().length > 0;
  } catch {
    return false;
  }
}

async function rejectUpstream(upstream, error) {
  try { await upstream.body?.cancel(); } catch { /* Do not disclose upstream errors. */ }
  return errorResponse(502, error);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/v1/chat/completions") {
      return errorResponse(404, "not_found");
    }
    // Reserved headers are untrusted input, including empty or non-1 values.
    if (request.headers.has(BAZAAR_PASSTHROUGH_HEADER)) {
      return errorResponse(400, "reserved_header_not_allowed");
    }
    if (request.method === "OPTIONS") {
      const method = request.headers.get("access-control-request-method");
      if (method && method !== "POST") {
        return errorResponse(405, "method_not_allowed", { allow: "POST, OPTIONS" });
      }
      const requested = (request.headers.get("access-control-request-headers") || "")
        .split(",").map((name) => name.trim().toLowerCase()).filter(Boolean);
      if (requested.some((name) => !ALLOWED_REQUEST_HEADERS.has(name))) {
        return errorResponse(400, "preflight_header_not_allowed");
      }
      return new Response(null, { status: 204, headers: responseHeaders() });
    }
    if (request.method !== "POST") {
      return errorResponse(405, "method_not_allowed", { allow: "POST, OPTIONS" });
    }
    const hasPayment = Boolean(
      request.headers.get("payment-signature")?.trim() ||
      request.headers.get("x-payment")?.trim()
    );
    if (!hasPayment) {
      const body = challengeBody();
      return new Response(body, {
        status: 402,
        headers: responseHeaders({ "PAYMENT-REQUIRED": encodePaymentRequired(body) }),
      });
    }
    if (typeof env?.PAYMENT_GATEWAY?.fetch !== "function") {
      return errorResponse(503, "payment_gateway_binding_unavailable");
    }
    try {
      const forwarded = new Request(request, { redirect: "manual" });
      const upstream = await env.PAYMENT_GATEWAY.fetch(forwarded);
      if (!(upstream instanceof Response)) {
        return errorResponse(502, "payment_gateway_invalid_response");
      }
      if (upstream.redirected || (upstream.status >= 300 && upstream.status < 400)) {
        return rejectUpstream(upstream, "payment_gateway_redirect_rejected");
      }
      if (upstream.ok && !hasSettlementSuccess(upstream.headers.get("payment-response"))) {
        return rejectUpstream(upstream, "payment_gateway_settlement_response_invalid");
      }
      const headers = new Headers(upstream.headers);
      for (const [name, value] of Object.entries(CORS_HEADERS)) headers.set(name, value);
      headers.delete("access-control-allow-credentials");
      headers.set("cache-control", "private, no-store");
      headers.set("x-szl-edge", "x402-bazaar-shim-v2-gateway");
      return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers });
    } catch {
      return errorResponse(502, "payment_gateway_unavailable");
    }
  },
};
