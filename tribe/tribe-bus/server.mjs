import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { appendJsonl, readJsonl, ensureDir } from "./storage.mjs";

const ROOT = "/opt/alloyscape";
const BUS_DIR = path.join(ROOT, "tribe-bus");
const QUEUE_FILE = path.join(BUS_DIR, "messages.jsonl");
const STATE_FILE = path.join(BUS_DIR, "state.json");
const ROUTES_FILE = path.join(BUS_DIR, "routes.json");
const AGENTS_DIR = path.join(ROOT, "agents");

const PORT = Number(process.env.TRIBE_BUS_PORT || 8787);
const ROUTER_INTERVAL_MS = Number(process.env.TRIBE_BUS_ROUTER_INTERVAL_MS || 500);
const MAX_DELIVER_PER_TICK = Number(process.env.TRIBE_BUS_MAX_DELIVER_PER_TICK || 200);

ensureDir(BUS_DIR);

/** in-memory SSE clients by member */
const sseClients = new Map(); // member -> Set<res>

function nowIso() {
  return new Date().toISOString();
}

function safeJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk;
      if (data.length > 2_000_000) {
        reject(new Error("payload too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

function loadRoutes() {
  try {
    const raw = fs.readFileSync(ROUTES_FILE, "utf8");
    return JSON.parse(raw);
  } catch {
    return { version: 1, default: "deny", allow: [] };
  }
}

function isAllowed(from, to) {
  const routes = loadRoutes();
  const rules = Array.isArray(routes.allow) ? routes.allow : [];
  const f = (from || "").toLowerCase();
  const t = (to || "").toLowerCase();

  for (const r of rules) {
    const rf = (r.from || "").toLowerCase();
    if (rf !== f) continue;
    if (r.to === "*") return true;
    if (Array.isArray(r.to)) {
      const list = r.to.map((x) => String(x).toLowerCase());
      if (list.includes(t)) return true;
    } else if (typeof r.to === "string") {
      if (String(r.to).toLowerCase() === t) return true;
    }
  }
  return false;
}

function agentInboxPath(member) {
  const m = String(member || "").toLowerCase();
  return path.join(AGENTS_DIR, m, "INBOX", "messages.jsonl");
}

function spoolPath(member) {
  const m = String(member || "").toLowerCase();
  return path.join(BUS_DIR, "spool", `${m}.jsonl`);
}

function loadState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return { queueOffset: 0, delivered: 0, lastTick: null };
  }
}

function saveState(st) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(st, null, 2), "utf8");
}

function pushSse(member, evt) {
  const m = String(member || "").toLowerCase();
  const set = sseClients.get(m);
  if (!set || set.size === 0) return;
  const payload = `event: message\ndata: ${JSON.stringify(evt)}\n\n`;
  for (const res of Array.from(set)) {
    try {
      res.write(payload);
    } catch {
      try { res.end(); } catch {}
      set.delete(res);
    }
  }
}

function enqueueMessage({ from, to, subject, body, meta }) {
  const msg = {
    id: crypto.randomUUID(),
    ts: nowIso(),
    from: String(from || "").toLowerCase(),
    to: String(to || "").toLowerCase(),
    subject: subject ? String(subject) : "",
    body: body ? String(body) : "",
    meta: meta && typeof meta === "object" ? meta : {},
    type: "tribe-bus.message",
    v: 1,
  };
  appendJsonl(QUEUE_FILE, msg);
  return msg;
}

function deliverToInbox(member, msg) {
  const inbox = agentInboxPath(member);
  try {
    appendJsonl(inbox, msg);
    pushSse(member, msg);
    return { ok: true, mode: "inbox" };
  } catch (e) {
    // if agent dir doesn't exist or permission issue, spool
    appendJsonl(spoolPath(member), { ...msg, spooledAt: nowIso(), reason: String(e?.message || e) });
    return { ok: false, mode: "spool", error: String(e?.message || e) };
  }
}

function routerTick() {
  const st = loadState();
  const { items, nextOffset, size } = readJsonl(QUEUE_FILE, { sinceOffset: st.queueOffset, limit: MAX_DELIVER_PER_TICK });

  let delivered = 0;
  for (const msg of items) {
    if (!msg || msg.type !== "tribe-bus.message") continue;
    const to = String(msg.to || "").toLowerCase();
    if (!to) continue;
    deliverToInbox(to, msg);
    delivered++;
  }

  st.queueOffset = nextOffset;
  st.delivered = (st.delivered || 0) + delivered;
  st.lastTick = nowIso();
  st.queueSizeBytes = size;
  saveState(st);
}

setInterval(routerTick, ROUTER_INTERVAL_MS).unref();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

  // CORS for internal dashboards/tools
  res.setHeader("access-control-allow-origin", "*");
  res.setHeader("access-control-allow-methods", "GET,POST,OPTIONS");
  res.setHeader("access-control-allow-headers", "content-type");
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === "GET" && url.pathname === "/healthz") {
    safeJson(res, 200, { status: "ok", ts: nowIso() });
    return;
  }

  if (req.method === "GET" && url.pathname === "/status") {
    const st = loadState();
    safeJson(res, 200, {
      status: "ok",
      ts: nowIso(),
      state: st,
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/send") {
    try {
      const raw = await readBody(req);
      const payload = JSON.parse(raw || "{}");
      const from = payload.from;
      const to = payload.to;
      if (!from || !to) return safeJson(res, 400, { error: "from and to are required" });
      if (!isAllowed(from, to)) return safeJson(res, 403, { error: "route denied" });
      const msg = enqueueMessage(payload);
      safeJson(res, 200, { ok: true, msg });
    } catch (e) {
      safeJson(res, 400, { error: "bad request", details: String(e?.message || e) });
    }
    return;
  }

  const inboxMatch = url.pathname.match(/^\/inbox\/([a-zA-Z0-9_-]+)$/);
  if (req.method === "GET" && inboxMatch) {
    const member = inboxMatch[1].toLowerCase();
    const inbox = agentInboxPath(member);
    const since = url.searchParams.get("sinceOffset");
    const sinceOffset = since ? Number(since) : 0;
    const limit = url.searchParams.get("limit") ? Number(url.searchParams.get("limit")) : 200;
    const result = readJsonl(inbox, { sinceOffset, limit });
    safeJson(res, 200, { ok: true, member, ...result });
    return;
  }

  const listenMatch = url.pathname.match(/^\/listen\/([a-zA-Z0-9_-]+)$/);
  if (req.method === "GET" && listenMatch) {
    const member = listenMatch[1].toLowerCase();
    res.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-store",
      connection: "keep-alive",
    });
    res.write(`event: hello\ndata: ${JSON.stringify({ ok: true, member, ts: nowIso() })}\n\n`);

    let set = sseClients.get(member);
    if (!set) {
      set = new Set();
      sseClients.set(member, set);
    }
    set.add(res);

    req.on("close", () => {
      try { res.end(); } catch {}
      set.delete(res);
    });
    return;
  }

  safeJson(res, 404, { error: "not found" });
});

server.listen(PORT, "0.0.0.0", () => {
  // eslint-disable-next-line no-console
  console.log(`[tribe-bus] listening on :${PORT}`);
});
