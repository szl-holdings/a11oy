// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/lambda-gate  HTTP layer
// Doctrine V6 preflight: ✓

import http from "node:http";
import { gateTransit, getReceipt, allReceipts, verifyReceipt } from "./gate.js";

function readBody(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let buf = "";
    req.on("data", (c: Buffer) => { buf += c.toString(); });
    req.on("end", () => {
      try { resolve(JSON.parse(buf)); }
      catch (e) { reject(e); }
    });
    req.on("error", reject);
  });
}

function send(res: http.ServerResponse, status: number, body: unknown): void {
  const json = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type":   "application/json",
    "Content-Length": Buffer.byteLength(json),
  });
  res.end(json);
}

export function createServer(): http.Server {
  return http.createServer(async (req, res) => {
    const url = req.url ?? "/";
    const method = req.method?.toUpperCase() ?? "GET";

    try {
      // POST /receipts
      if (method === "POST" && url === "/receipts") {
        const body = await readBody(req);
        const result = gateTransit(body);
        send(res, result.stored ? 201 : 422, result);
        return;
      }

      // GET /receipts/:hash
      const hashMatch = url.match(/^\/receipts\/([0-9a-f]{64})$/);
      if (method === "GET" && hashMatch) {
        const r = getReceipt(hashMatch[1]);
        if (!r) { send(res, 404, { error: "not found" }); return; }
        send(res, 200, r);
        return;
      }

      // GET /receipts
      if (method === "GET" && url === "/receipts") {
        send(res, 200, allReceipts());
        return;
      }

      // POST /verify
      if (method === "POST" && url === "/verify") {
        const body = await readBody(req) as { hash?: string };
        if (!body.hash) { send(res, 400, { error: "hash required" }); return; }
        send(res, 200, verifyReceipt(body.hash));
        return;
      }

      send(res, 404, { error: "not found" });
    } catch (err) {
      // Log full error server-side for ops, but never leak details to caller (CWE-209).
      console.error("[lambda-gate] request error:", err);
      send(res, 400, { error: "bad request" });
    }
  });
}

// Entrypoint
if (process.argv[1]?.endsWith("server.js") || process.argv[1]?.endsWith("server.ts")) {
  const port = Number(process.env["PORT"] ?? 3001);
  createServer().listen(port, () => console.log(`lambda-gate listening :${port}`));
}
