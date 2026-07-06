// k6 stress suite for the a11oy console API surface.
//
// Ramps virtual users against the read-heavy, citation-bearing endpoints that
// back the console tabs, asserting they stay fast AND honest under load:
//   • http_req_failed stays low
//   • p95 latency stays within budget
//   • a custom "lies" counter (non-2xx on a contract endpoint, or an empty body
//     where the contract promises data) stays at zero
//
// Endpoint list is kept in sync with tabs.json by gen_tabs_matrix.py emitting
// stress-targets.json next to this file; we fall back to a baked core list if it
// is absent so the suite always runs.
//
//   k6 run -e A11OY_BASE=https://a-11-oy.com warhacker.js
//   k6 run -e A11OY_BASE=https://a-11-oy.com -e PROFILE=soak warhacker.js

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

const BASE = (__ENV.A11OY_BASE || "https://a-11-oy.com").replace(/\/$/, "");
const PROFILE = __ENV.PROFILE || "smoke";

const lies = new Counter("lies");
const ttfb = new Trend("contract_ttfb", true);

// Core, GET-only, cheap-to-serve contract endpoints. POST/decision endpoints are
// excluded from the stress run on purpose (they mutate / cost more).
let TARGETS = [
  "/api/a11oy/v1/lambda",
  "/api/a11oy/v1/gates",
  "/api/a11oy/v1/mcp/tools",
  "/api/a11oy/v1/llm/registry",
  "/api/a11oy/provenance",
  "/api/a11oy/v1/ledger",
  "/api/a11oy/cosign.pub",
  "/api/a11oy/v1/observability/summary",
  "/api/a11oy/v1/policy/gates",
  "/api/a11oy/v1/sec/cve",
  "/api/a11oy/v1/warhacker/index",
  "/api/a11oy/v1/readiness/tab-matrix",
];
try {
  // optional generated target list (GET endpoints only)
  const gen = JSON.parse(open("./stress-targets.json"));
  if (Array.isArray(gen) && gen.length) TARGETS = gen;
} catch (_) { /* use baked list */ }

const PROFILES = {
  smoke: { stages: [{ duration: "20s", target: 5 }, { duration: "20s", target: 5 }, { duration: "10s", target: 0 }] },
  load: { stages: [{ duration: "30s", target: 25 }, { duration: "1m", target: 25 }, { duration: "20s", target: 0 }] },
  soak: { stages: [{ duration: "1m", target: 15 }, { duration: "10m", target: 15 }, { duration: "1m", target: 0 }] },
};

export const options = {
  scenarios: { warhacker: { executor: "ramping-vus", startVUs: 1, ...PROFILES[PROFILE] } },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2500"],
    lies: ["count==0"],
  },
};

export default function () {
  const path = TARGETS[Math.floor(Math.random() * TARGETS.length)];
  const res = http.get(BASE + path, { headers: { accept: "application/json" }, tags: { ep: path } });
  ttfb.add(res.timings.waiting);

  const ok2xx = res.status >= 200 && res.status < 300;
  const rateLimited = res.status === 429; // honest backpressure, not a lie
  const nonEmpty = (res.body || "").length > 2;

  const honest = check(res, {
    "status ok or 429": () => ok2xx || rateLimited,
    "body non-empty when 2xx": () => !ok2xx || nonEmpty,
  });
  if (!honest && !rateLimited) lies.add(1, { ep: path });

  sleep(0.5 + Math.random());
}
