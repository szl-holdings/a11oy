// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Disabled reference only: no verified payment path, serving passport, or receipt store.
// Header presence cannot authorize inference. See WORKER_CONTRACT.md before integration.

const HEADERS = Object.freeze({
  "content-type": "application/json",
  "cache-control": "private, no-store",
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "Content-Type",
});

export default {
  async fetch(request) {
    const { pathname } = new URL(request.url);
    const method = pathname === "/v1/models" ? "GET" :
      pathname === "/v1/inference" ? "POST" : null;
    if (method === null) return json({ error: "unknown_route" }, 404);
    const allowed = method + ", OPTIONS";
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: { ...HEADERS, "access-control-allow-methods": allowed },
      });
    }
    if (request.method !== method) {
      return json({ error: "method_not_allowed" }, 405, { allow: allowed });
    }
    if (pathname === "/v1/models") {
      return json({ object: "list", data: [], state: "BLOCKED" });
    }
    // Do not emit a payment challenge for a service with no admitted model or verifier.
    return json({ error: "reference_gateway_unconfigured", state: "BLOCKED" }, 503);
  },
};

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), { status, headers: { ...HEADERS, ...extra } });
}
