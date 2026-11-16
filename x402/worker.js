// x402 passport-gated inference gateway (reference skeleton)
// Deploy: wrangler deploy (worker name: szl-a11oy-governed-inference)

const MODELS = {
  "ternary-bonsai-2-27b-pq2_0": {
    upstream: "http://szl-inference-v3.internal",
    priceUSDC: "0.002",
    passportDigest: "REPLACE_WITH_MEASURED_DIGEST",
    promotion: "CANDIDATE"
  }
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors() });
    }
    if (url.pathname === "/v1/models") {
      const models = Object.entries(MODELS).map(([id, m]) => ({ id, price_usdc: m.priceUSDC, passport_digest: m.passportDigest, promotion: m.promotion }));
      return json({ object: "list", data: models });
    }
    if (url.pathname === "/v1/inference" && request.method === "POST") {
      const model = url.searchParams.get("model") || Object.keys(MODELS)[0];
      const m = MODELS[model];
      if (!m) return json({ error: "unknown model" }, 404);
      const payment = request.headers.get("x-payment") || request.headers.get("X-PAYMENT");
      if (!payment) {
        return new Response(JSON.stringify({ error: "x402 payment required", price_usdc: m.priceUSDC, model }), { status: 402, headers: { "Content-Type": "application/json", ...cors() } });
      }
      // NOTE: production verifies the x402 payment with the facilitator before proxying.
      const upstream = await fetch(m.upstream + "/v1/chat/completions", { method: "POST", body: request.body, headers: { "Content-Type": "application/json" } });
      const body = await upstream.text();
      const receiptId = crypto.randomUUID();
      const headers = new Headers({ "Content-Type": "application/json", ...cors() });
      headers.set("X-Ouroboros-Passport-Digest", m.passportDigest);
      headers.set("X-Ouroboros-Promotion", m.promotion);
      headers.set("X-Ouroboros-Model-Revision", model);
      headers.set("X-Ouroboros-Receipt-Id", receiptId);
      return new Response(body, { status: upstream.status, headers });
    }
    return json({ error: "unknown route" }, 404);
  }
};

function cors() { return { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS" }; }
function json(obj, status = 200) { return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors() } }); }
