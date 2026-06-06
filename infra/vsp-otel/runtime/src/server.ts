// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: vsp-otel  HTTP verifier server
// Doctrine V6 preflight: ✓

import http from "node:http";
import { exportSpans, signSpan, type OtelSpan } from "./exporter.js";
import { getReceipt, verifyReceipt } from "@szl/ouroboros-lambda-gate";

function readBody(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let buf = "";
    req.on("data", (c: Buffer) => { buf += c.toString(); });
    req.on("end", () => { try { resolve(JSON.parse(buf)); } catch (e) { reject(e); } });
    req.on("error", reject);
  });
}

function send(res: http.ServerResponse, status: number, body: unknown): void {
  const json = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(json) });
  res.end(json);
}

export function createVspServer(): http.Server {
  return http.createServer(async (req, res) => {
    const url    = req.url ?? "/";
    const method = req.method?.toUpperCase() ?? "GET";

    try {
      // POST /spans/verify — accept span(s), sign and return {lambda, axes, pass}
      if (method === "POST" && url === "/spans/verify") {
        const body = await readBody(req);
        const spans: OtelSpan[] = Array.isArray(body) ? body : [body as OtelSpan];
        const result = exportSpans(spans);
        const response = result.signed.map((s) => ({
          spanId:      s.span.spanId,
          lambda:      s.lambda,
          axes:        s.axes,
          pass:        s.pass,
          receiptHash: s.receiptHash,
        }));
        send(res, 200, response.length === 1 ? response[0] : response);
        return;
      }

      // POST /spans/export — batch export without verification response
      if (method === "POST" && url === "/spans/export") {
        const body  = await readBody(req);
        const spans: OtelSpan[] = Array.isArray(body) ? body : [body as OtelSpan];
        const result = exportSpans(spans);
        send(res, 200, { total: result.total, passed: result.passed, failed: result.failed });
        return;
      }

      // GET /spans/:hash — retrieve stored receipt for a span
      const hashMatch = url.match(/^\/spans\/([0-9a-f]{64})$/);
      if (method === "GET" && hashMatch) {
        const r = getReceipt(hashMatch[1]);
        if (!r) { send(res, 404, { error: "receipt not found" }); return; }
        send(res, 200, r);
        return;
      }

      send(res, 404, { error: "not found" });
    } catch (err) {
      send(res, 400, { error: err instanceof Error ? err.message : String(err) });
    }
  });
}

if (process.argv[1]?.endsWith("server.js") || process.argv[1]?.endsWith("server.ts")) {
  const port = Number(process.env["VSP_PORT"] ?? 3004);
  createVspServer().listen(port, () => console.log(`vsp-otel listening :${port}`));
}
