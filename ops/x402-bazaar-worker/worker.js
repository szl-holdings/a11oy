/**
 * SZL x402 Bazaar discovery shim — a11oy monetization edge lane.
 *
 * ARCHITECTURE (measured 2026-11-15, receipt: frontier-54-runs):
 * The Cloudflare Monetization Gateway (closed beta) emits x402 v2 challenges
 * for inference.a-11-oy.com/v1/* with NO extensions field, so the resource is
 * invisible to the CDP x402 Bazaar / agentic.market discovery layer (23k+
 * resources, opt-in: the resource server must advertise extensions.bazaar).
 * The managed gateway response shape is fixed; this first-party Worker adds
 * the Bazaar metadata without changing price, payee, or verification.
 *
 * FAIL-CLOSED CONTRACT:
 * - Unpaid request (no PAYMENT-SIGNATURE): respond 402 with a challenge
 *   parity to the live gateway challenge (same accepts / payTo / asset /
 *   amount / maxTimeoutSeconds / help) PLUS extensions.bazaar. Never a 200.
 * - Paid request (PAYMENT-SIGNATURE present): passthrough mode. This worker
 *   does NOT verify payments. It forwards the request with a sentinel header
 *   so the CF Monetization Gateway performs real verification on the inner
 *   subrequest. See README open-questions for the re-entry caveat — verify
 *   in staging before production; never assume the passthrough works.
 * - Route precedence: this worker claims a NARROWER route than the gateway
 *   (exact /v1/chat/completions vs /v1/*). CF runs only the first matching
 *   worker; the gateway keeps every other route.
 *
 * DEPLOYMENT: OWNER-GATED (Cloudflare dashboard route). This file is the
 * source of truth; the sha256 of the deployed worker must equal the receipted
 * sha (receipts before republish, doctrine).
 */

const BAZAAR_PASSTHROUGH_HEADER = "x-szl-bazaar-passthrough";

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

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname !== "/v1/chat/completions") {
      return new Response(JSON.stringify({ error: "not_found", detail: "bazaar shim covers only /v1/chat/completions" }), {
        status: 404,
        headers: { "content-type": "application/json", "x-szl-edge": "x402-bazaar-shim-v1" },
      });
    }

    // Inner subrequest re-entry: strip the sentinel and fall through to
    // origin. CAVEAT (README open-questions): if the inner fetch re-enters
    // THIS worker instead of the managed gateway, passthrough must be
    // redesigned to forward to a dedicated gateway-claimed path. Verify in
    // staging before production cutover.
    if (request.headers.get(BAZAAR_PASSTHROUGH_HEADER) === "1") {
      const inner = new Request(request);
      inner.headers.delete(BAZAAR_PASSTHROUGH_HEADER);
      return fetch(inner);
    }

    const hasPayment = request.headers.has("Payment-Signature") || request.headers.has("X-PAYMENT");

    if (hasPayment) {
      // Passthrough: mark the subrequest so this worker does not re-claim it,
      // letting the CF Monetization Gateway perform payment verification.
      const fwd = new Request(request);
      fwd.headers.set(BAZAAR_PASSTHROUGH_HEADER, "1");
      const upstream = await fetch(fwd);
      const resp = new Response(upstream.body, upstream);
      resp.headers.set("x-szl-edge", "x402-bazaar-shim-v1-passthrough");
      return resp;
    }

    // Unpaid: parity challenge + Bazaar metadata. Never serve content unpaid.
    const body = challengeBody();
    return new Response(body, {
      status: 402,
      headers: {
        "content-type": "application/json",
        "cache-control": "private, no-store",
        "x-szl-edge": "x402-bazaar-shim-v1",
        "access-control-expose-headers": "PAYMENT-REQUIRED, PAYMENT-RESPONSE",
      },
    });
  },
};
