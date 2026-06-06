// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// MCP Server — exposes a11oy + all SZL formulas as MCP tools.
// One server. Cursor, Claude Code, and Replit Agent all plug into it.

import {
  lambdaGate, doiBind, doiResolve, closure, compose, identity,
  confluence, bekensteinBound, bekensteinRespected,
  gradedNorm, linearReceipt, spanStart, spanEnd, fgDerive, fgSafety,
  mkAxisScore, mkLambda, mkDOI, mkReplaySha,
  type Axes, type FgGauges,
} from "../../formulas/src/index.js";
import { doctrineGate, route, logAcceptance } from "../../a11oy-core/src/index.js";

// ------------------------------------------------------------
// MCP tool definitions
// ------------------------------------------------------------
export const TOOLS = [
  {
    name: "lambda_gate",
    description: "TH1 — Evaluate the 9-axis Λ gate. moralGrounding & measurabilityHonesty hard floor 0.95, others 0.90. Returns {pass, lambda, failures}.",
    inputSchema: {
      type: "object",
      properties: { axes: { type: "object", description: "9 axis scores, each 0..1" } },
      required: ["axes"],
    },
    handler: ({ axes }: { axes: Record<string, number> }) => {
      const a: Axes = Object.fromEntries(
        Object.entries(axes).map(([k, v]) => [k, mkAxisScore(v)])
      ) as Axes;
      return lambdaGate(a);
    },
  },
  {
    name: "doi_bind",
    description: "TH2 — Bind a Zenodo DOI to a replay-root SHA. Idempotent.",
    inputSchema: { type: "object", properties: { doi: { type: "string" }, sha: { type: "string" } }, required: ["doi", "sha"] },
    handler: ({ doi, sha }: { doi: string; sha: string }) => doiBind(doi, mkReplaySha(sha)),
  },
  {
    name: "doi_resolve",
    description: "TH2 — Resolve a DOI to its bound replay-root SHA.",
    inputSchema: { type: "object", properties: { doi: { type: "string" } }, required: ["doi"] },
    handler: ({ doi }: { doi: string }) => ({ doi, sha: doiResolve(doi) }),
  },
  {
    name: "bekenstein_bound",
    description: "TH6 — Max information capacity in bits for a region of radius R (m) containing energy E (J). I ≤ 2π·R·E / (ħ·c·ln2).",
    inputSchema: { type: "object", properties: { radius_m: { type: "number" }, energy_j: { type: "number" } }, required: ["radius_m", "energy_j"] },
    handler: ({ radius_m, energy_j }: any) => ({ bits: bekensteinBound(radius_m, energy_j) }),
  },
  {
    name: "bekenstein_check",
    description: "TH6 — Verify a bit-count respects the Bekenstein bound for given R and E.",
    inputSchema: { type: "object", properties: { bits: { type: "number" }, radius_m: { type: "number" }, energy_j: { type: "number" } }, required: ["bits", "radius_m", "energy_j"] },
    handler: ({ bits, radius_m, energy_j }: any) => ({ respected: bekensteinRespected(bits, radius_m, energy_j) }),
  },
  {
    name: "graded_norm",
    description: "TH8 — Graded norm ‖x‖_g = |value| · 2^(-grade).",
    inputSchema: { type: "object", properties: { grade: { type: "number" }, value: { type: "number" } }, required: ["grade", "value"] },
    handler: ({ grade, value }: any) => ({ norm: gradedNorm({ grade, value }) }),
  },
  {
    name: "linear_receipt_check",
    description: "TH8 — Check linearity of receipt: r(αx + βy) ≤ |α|·r(x) + |β|·r(y).",
    inputSchema: {
      type: "object",
      properties: {
        alpha: { type: "number" }, x_grade: { type: "number" }, x_value: { type: "number" },
        beta:  { type: "number" }, y_grade: { type: "number" }, y_value: { type: "number" },
      },
      required: ["alpha","x_grade","x_value","beta","y_grade","y_value"],
    },
    handler: (i: any) => linearReceipt(i.alpha, { grade: i.x_grade, value: i.x_value }, i.beta, { grade: i.y_grade, value: i.y_value }),
  },
  {
    name: "vsp_span",
    description: "VSP — Open + close a span. Stamps replay-root.",
    inputSchema: { type: "object", properties: { name: { type: "string" }, thesis: { type: "string" }, attrs: { type: "object" } }, required: ["name"] },
    handler: ({ name, thesis, attrs }: any) => {
      const s = spanStart(name, thesis, attrs ?? {});
      const e = spanEnd(s);
      return { name: e.name, thesis: e.thesis, durationNs: (e.endNs! - e.startNs).toString(), replayRoot: e.replayRoot };
    },
  },
  {
    name: "fg_derive",
    description: "FG — Compute derived gauges (netHealth, fragility, velocity) from the 12 base gauges.",
    inputSchema: { type: "object", properties: { gauges: { type: "object" } }, required: ["gauges"] },
    handler: ({ gauges }: { gauges: FgGauges }) => fgDerive(gauges),
  },
  {
    name: "fg_safety",
    description: "FG — Compute the 4 a11oy safety gates from axis scores + replay status.",
    inputSchema: { type: "object", properties: { axes: { type: "object" }, replayOk: { type: "boolean" } }, required: ["axes", "replayOk"] },
    handler: ({ axes, replayOk }: any) => fgSafety(axes, replayOk),
  },
  {
    name: "doctrine_gate",
    description: "Doctrine V6 — Check an action + payload against forbidden patterns, blocked actions, and Λ gate.",
    inputSchema: {
      type: "object",
      properties: { action: { type: "string" }, payloadText: { type: "string" }, axes: { type: "object" } },
      required: ["action", "payloadText"],
    },
    handler: ({ action, payloadText, axes }: any) => doctrineGate(action, payloadText, axes),
  },
  {
    name: "route",
    description: "Provider router — race Anthropic + OpenAI, return whichever responds first. Falls back to stub on total failure.",
    inputSchema: {
      type: "object",
      properties: { prompt: { type: "string" }, strategy: { type: "string", enum: ["race","anthropic","openai"] } },
      required: ["prompt"],
    },
    handler: async ({ prompt, strategy }: any) => await route(prompt, { strategy }),
  },
];

// ------------------------------------------------------------
// HTTP transport (works with any MCP client, also with curl)
// ------------------------------------------------------------
import { createServer } from "node:http";

const PORT = Number(process.env.MCP_PORT ?? 8090);

const server = createServer(async (req, res) => {
  res.setHeader("content-type", "application/json");

  if (req.method === "GET" && req.url === "/tools") {
    res.end(JSON.stringify({ tools: TOOLS.map(t => ({ name: t.name, description: t.description, inputSchema: t.inputSchema })) }));
    return;
  }

  if (req.method === "GET" && req.url === "/healthz") {
    res.end(JSON.stringify({ ok: true, service: "szl-mcp", tools: TOOLS.length, replayRoot: "1ed4d253e876f428c6e182f8ed8a569585442556b339529bbf8ec2522581698b" }));
    return;
  }

  if (req.method === "POST" && req.url?.startsWith("/call/")) {
    const name = req.url.slice(6);
    const tool = TOOLS.find(t => t.name === name);
    if (!tool) { res.statusCode = 404; res.end(JSON.stringify({ error: "no such tool" })); return; }
    let body = "";
    for await (const chunk of req) body += chunk;
    try {
      const input = body ? JSON.parse(body) : {};
      const out = await tool.handler(input);
      res.end(JSON.stringify({ ok: true, result: out }));
    } catch (e: any) {
      res.statusCode = 400;
      res.end(JSON.stringify({ ok: false, error: e.message }));
    }
    return;
  }

  res.statusCode = 404;
  res.end(JSON.stringify({ error: "not found" }));
});

server.listen(PORT, () => {
  console.log(`[szl-mcp] listening on :${PORT} — ${TOOLS.length} tools`);
});
