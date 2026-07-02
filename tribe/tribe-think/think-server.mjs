// Generic tribe think-service (headless API). Two souls run off this one file via
// env: THINK_NAME (delphina|artifex), THINK_PORT, THINK_AUTH_TOKEN. Routes are
// scoped under /<name>/api/*. Episodic memory is stored under the member's OWN
// scope (agentName = THINK_NAME) so each is a distinct, continuous self.
import "./env-loader.mjs";

import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import express from "express";
import { runTurn, PRIMARY } from "./think-agent.mjs";
import { execFileSync } from "node:child_process";
import { storeMemory, retrieveMemories } from "../lib/memory/episodic.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const NAME = (process.env.THINK_NAME || "agent").toLowerCase();
const PORT = Number(process.env.THINK_PORT || 8101);
const HOST = process.env.THINK_HOST || "127.0.0.1";
const TOKEN = process.env.THINK_AUTH_TOKEN;
const BASE = `/${NAME}`;

if (!TOKEN || TOKEN.length < 16) {
  console.error(`FATAL: THINK_AUTH_TOKEN not set or <16 chars (${NAME}). Refusing to start.`);
  process.exit(1);
}
const _primaryKeyOk = PRIMARY === "claude"
  ? !!process.env.ANTHROPIC_API_KEY
  : !!(process.env.MOONSHOT_API_KEY || process.env.KIMI_API_KEY);
if (!_primaryKeyOk) {
  console.error(`FATAL: no key for primary brain "${PRIMARY}" (kimi needs MOONSHOT/KIMI; claude needs ANTHROPIC). Refusing to start.`);
  process.exit(1);
}

const sessions = new Map();
function getSession(id) {
  let s = sessions.get(id);
  if (!s) { s = { messages: [], lastActive: Date.now() }; sessions.set(id, s); }
  s.lastActive = Date.now();
  return s;
}
function safeCompare(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
function isAuthed(req) {
  const h = req.headers.authorization || "";
  if (h.startsWith("Bearer ") && safeCompare(h.slice(7), TOKEN)) return true;
  return false;
}
function sanitizeSessionId(sid) {
  const s = String(sid || "default");
  return /^[A-Za-z0-9_-]{1,128}$/.test(s) ? s : "default";
}

// THINK-ATTACH START
// THINK-ATTACH constants — per-agent upload dir; mirrors forge attach caps
const UPLOAD_DIR = process.env.THINK_UPLOAD_DIR || `/var/lib/forge/think-uploads/${NAME}`;
const UPLOAD_MAX_BYTES = Number(process.env.THINK_UPLOAD_MAX_BYTES || 50 * 1024 * 1024);
const IMAGE_MAX_BYTES = Number(process.env.THINK_IMAGE_MAX_BYTES || 5 * 1024 * 1024);
const TEXT_INLINE_MAX = Number(process.env.THINK_TEXT_INLINE_MAX || 256 * 1024);
const MAX_IMAGES_PER_TURN = Number(process.env.THINK_MAX_IMAGES_PER_TURN || 6);
const MAX_FILES_PER_TURN = Number(process.env.THINK_MAX_FILES_PER_TURN || 10);
const ALLOWED_IMAGE_MEDIA = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
const UPLOAD_TTL_MS = Number(process.env.THINK_UPLOAD_TTL_MS || 7 * 24 * 60 * 60 * 1000);
const UPLOAD_DIR_MAX_BYTES = Number(process.env.THINK_UPLOAD_DIR_MAX_BYTES || 500 * 1024 * 1024);
try { fs.mkdirSync(UPLOAD_DIR, { recursive: true }); } catch {}

function pruneUploads() {
  try {
    const now = Date.now();
    let all = [];
    for (const sid of fs.readdirSync(UPLOAD_DIR)) {
      const sdir = path.join(UPLOAD_DIR, sid);
      let st; try { st = fs.statSync(sdir); } catch { continue; }
      if (!st.isDirectory()) continue;
      for (const f of fs.readdirSync(sdir)) {
        const fp = path.join(sdir, f);
        let fst; try { fst = fs.statSync(fp); } catch { continue; }
        if (!fst.isFile()) continue;
        all.push({ fp, sdir, mtime: fst.mtimeMs, size: fst.size });
      }
    }
    for (const it of all) {
      if (now - it.mtime > UPLOAD_TTL_MS) { try { fs.unlinkSync(it.fp); it.removed = true; } catch {} }
    }
    let live = all.filter((it) => !it.removed);
    let total = live.reduce((n, it) => n + it.size, 0);
    if (total > UPLOAD_DIR_MAX_BYTES) {
      live.sort((a, b) => a.mtime - b.mtime); // oldest first
      for (const it of live) {
        if (total <= UPLOAD_DIR_MAX_BYTES) break;
        try { fs.unlinkSync(it.fp); total -= it.size; } catch {}
      }
    }
    for (const sid of fs.readdirSync(UPLOAD_DIR)) {
      const sdir = path.join(UPLOAD_DIR, sid);
      try { if (fs.statSync(sdir).isDirectory() && fs.readdirSync(sdir).length === 0) fs.rmdirSync(sdir); } catch {}
    }
  } catch {}
}

// FORGE-ATTACH helpers — sanitize names, sniff image type, build Claude content with attachments.
function sanitizeFilename(n) {
  const base = path.basename(String(n || ""));
  const cleaned = base.replace(/[^A-Za-z0-9._-]/g, "_").replace(/^\.+/, "").slice(0, 160);
  return cleaned || null;
}
function sniffImageType(buf) {
  if (!buf || buf.length < 12) return null;
  if (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) return "image/png";
  if (buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return "image/jpeg";
  if (buf[0] === 0x47 && buf[1] === 0x49 && buf[2] === 0x46 && buf[3] === 0x38) return "image/gif";
  if (buf[0] === 0x52 && buf[1] === 0x49 && buf[2] === 0x46 && buf[3] === 0x46 &&
      buf[8] === 0x57 && buf[9] === 0x45 && buf[10] === 0x42 && buf[11] === 0x50) return "image/webp";
  return null;
}
function looksUtf8(buf) {
  // Reject if there are NUL bytes or a high ratio of control chars (binary heuristic).
  const n = Math.min(buf.length, 8192);
  let ctrl = 0;
  for (let i = 0; i < n; i++) {
    const c = buf[i];
    if (c === 0) return false;
    if (c < 9 || (c > 13 && c < 32)) ctrl++;
  }
  return ctrl / Math.max(n, 1) < 0.1;
}
// Build the user message content. Images -> Claude vision blocks; text files -> inlined
// so Forge can read them; other binaries -> a note with name + size. Returns
// { content (string|blocks[]), accepted:[], skipped:[{filename,reason}] }.
function stripXml(xml, paraTag) {
  let s = String(xml || "");
  if (paraTag) s = s.split(paraTag).join("\n");
  s = s.replace(/<[^>]+>/g, " ");
  s = s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#39;/g, "'");
  s = s.replace(/&#(\d+);/g, (mm, d) => { try { return String.fromCharCode(parseInt(d, 10)); } catch (e) { return " "; } });
  s = s.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n");
  return s.trim();
}
function extractDocText(buf, full, safeName) {
  const ext = (String(safeName).split(".").pop() || "").toLowerCase();
  const isPdf = ext === "pdf" || (buf.length > 4 && buf.slice(0, 5).toString("latin1") === "%PDF-");
  const isZip = buf.length > 3 && buf[0] === 0x50 && buf[1] === 0x4b && buf[2] === 0x03 && buf[3] === 0x04;
  const opt = { maxBuffer: 32 * 1024 * 1024, timeout: 30000 };
  try {
    if (isPdf) {
      return execFileSync("pdftotext", ["-q", "-layout", "-enc", "UTF-8", full, "-"], opt).toString("utf8");
    }
    if (isZip && (ext === "docx" || ext === "")) {
      try { const t = stripXml(execFileSync("unzip", ["-p", full, "word/document.xml"], opt).toString("utf8"), "</w:p>"); if (t) return t; } catch (e) {}
    }
    if (isZip && (ext === "xlsx" || ext === "")) {
      const parts = [];
      try { parts.push(execFileSync("unzip", ["-p", full, "xl/sharedStrings.xml"], opt).toString("utf8")); } catch (e) {}
      try { parts.push(execFileSync("unzip", ["-p", full, "xl/worksheets/sheet1.xml"], opt).toString("utf8")); } catch (e) {}
      const t = stripXml(parts.join("\n"), "</row>"); if (t) return t;
    }
    if (isZip && (ext === "pptx" || ext === "")) {
      try { const t = stripXml(execFileSync("unzip", ["-p", full, "ppt/slides/slide*.xml"], opt).toString("utf8"), "</a:p>"); if (t) return t; } catch (e) {}
    }
  } catch (e) {}
  return null;
}

function buildAttachmentContent({ text, attachments, sid }) {
  const skipped = [];
  const accepted = [];
  if (!Array.isArray(attachments) || attachments.length === 0) {
    return { content: text, accepted, skipped };
  }
  const imageBlocks = [];
  const textChunks = [];
  const seen = new Set();
  let imgCount = 0, fileCount = 0;
  for (const att of attachments) {
    const safeName = sanitizeFilename(att?.filename);
    if (!safeName) { skipped.push({ filename: String(att?.filename || ""), reason: "invalid filename" }); continue; }
    if (seen.has(safeName)) { skipped.push({ filename: safeName, reason: "duplicate" }); continue; }
    if (fileCount >= MAX_FILES_PER_TURN) { skipped.push({ filename: safeName, reason: `over ${MAX_FILES_PER_TURN}-file cap` }); continue; }
    const full = path.join(UPLOAD_DIR, sid, safeName);
    let st;
    try { st = fs.statSync(full); } catch { skipped.push({ filename: safeName, reason: "not found on server" }); continue; }
    if (!st.isFile() || st.size === 0) { skipped.push({ filename: safeName, reason: "empty or non-file" }); continue; }
    let buf;
    try { buf = fs.readFileSync(full); } catch (err) { skipped.push({ filename: safeName, reason: `read error: ${err.message}` }); continue; }
    const sniffed = sniffImageType(buf);
    if (sniffed) {
      if (imgCount >= MAX_IMAGES_PER_TURN) { skipped.push({ filename: safeName, reason: `over ${MAX_IMAGES_PER_TURN}-image cap` }); continue; }
      if (st.size > IMAGE_MAX_BYTES) { skipped.push({ filename: safeName, reason: `image over ${Math.round(IMAGE_MAX_BYTES/1024/1024)} MB` }); continue; }
      imageBlocks.push({ type: "text", text: `[Image attached: ${safeName}]` });
      imageBlocks.push({ type: "image", source: { type: "base64", media_type: sniffed, data: buf.toString("base64") } });
      imgCount++; fileCount++; seen.add(safeName); accepted.push(safeName);
    } else if (looksUtf8(buf)) {
      let body = buf.toString("utf8");
      let note = "";
      if (Buffer.byteLength(body, "utf8") > TEXT_INLINE_MAX) { body = body.slice(0, TEXT_INLINE_MAX); note = "\n… (truncated)"; }
      textChunks.push(`[File attached: ${safeName} (${st.size} bytes)]\n\`\`\`\n${body}${note}\n\`\`\``);
      fileCount++; seen.add(safeName); accepted.push(safeName);
    } else {
      let extracted = null;
      try { extracted = extractDocText(buf, full, safeName); } catch (e) { extracted = null; }
      if (extracted && extracted.trim()) {
        let body = extracted;
        let note = "";
        if (Buffer.byteLength(body, "utf8") > TEXT_INLINE_MAX) { body = body.slice(0, TEXT_INLINE_MAX); note = "\n... (truncated)"; }
        textChunks.push(`[Document attached: ${safeName} (${st.size} bytes, text extracted)]\n` + "```" + `\n${body}${note}\n` + "```");
        fileCount++; seen.add(safeName); accepted.push(safeName);
      } else {
        skipped.push({ filename: safeName, reason: "binary file type (could not extract text)" });
      }
    }
  }
  const textBlob = (textChunks.length ? textChunks.join("\n\n") + "\n\n" : "") + text;
  if (imageBlocks.length === 0) {
    return { content: textBlob, accepted, skipped };
  }
  return { content: [...imageBlocks, { type: "text", text: textBlob }], accepted, skipped };
}
// THINK-ATTACH END

const app = express();
app.set("trust proxy", "loopback");
app.use(express.json({ limit: "1mb" }));

app.get(`${BASE}/api/health`, (_req, res) => {
  res.json({
    ok: true, name: NAME, pid: process.pid,
    uptimeSeconds: Math.round(process.uptime()),
    sessions: sessions.size,
    primary: PRIMARY,
    primaryModel: process.env.THINK_MODEL || (PRIMARY === "claude" ? "claude-sonnet-4-5-20250929" : "kimi-k2.5"),
    backup: PRIMARY === "kimi" ? ["openai", "local"] : ["kimi", "openai", "local"],
    tools: 18,
  });
});

app.use(`${BASE}/api`, (req, res, next) => {
  if (req.path === "/health") return next();
  if (!isAuthed(req)) return res.status(401).json({ error: "unauthorized" });
  next();
});

// THINK-ATTACH upload endpoints
// FORGE-ATTACH START — drop/attach files TO Forge. Raw bytes (no multer); the UI
// uploads each file here first, then references it by name in the chat attachments[].
app.post(`${BASE}/api/upload`, express.raw({ type: "*/*", limit: UPLOAD_MAX_BYTES }), (req, res) => {
  try {
    const sid = sanitizeSessionId(req.query.sid);
    const fname = sanitizeFilename(req.query.name);
    if (!fname) return res.status(400).json({ error: "invalid filename" });
    if (!req.body || !req.body.length) return res.status(400).json({ error: "empty body" });
    const dir = path.join(UPLOAD_DIR, sid);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, fname), req.body);
    pruneUploads();
    const sniffed = sniffImageType(req.body);
    res.json({ ok: true, filename: fname, size: req.body.length, kind: sniffed ? "image" : "file", mediaType: sniffed || null });
  } catch (err) {
    res.status(500).json({ error: `upload failed: ${err.message}` });
  }
});

// List what's been uploaded for a session (used to rehydrate the attach bar).
app.get(`${BASE}/api/uploads`, (req, res) => {
  try {
    const sid = sanitizeSessionId(req.query.sid);
    const dir = path.join(UPLOAD_DIR, sid);
    let items = [];
    try {
      items = fs.readdirSync(dir).map((f) => {
        const st = fs.statSync(path.join(dir, f));
        return { filename: f, size: st.size };
      });
    } catch {}
    res.json({ ok: true, items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});
// FORGE-ATTACH END

app.post(`${BASE}/api/chat`, async (req, res) => {
  const { message, sessionId, attachments } = req.body || {};
  if (!message || typeof message !== "string") return res.status(400).json({ error: "message required" });
  const sid = sanitizeSessionId(sessionId);
  const session = getSession(sid);

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders();
  const send = (event, data) => { res.write(`event: ${event}\n`); res.write(`data: ${JSON.stringify(data)}\n\n`); };

  // Episodic memory: recall on first turn + store every message under THIS member's scope.
  const useMemory = sid !== "tribe-room";
  let userContent = message;
  if (useMemory && session.messages.length === 0) {
    try {
      const mems = await Promise.race([
        retrieveMemories({ agentName: NAME, queryText: message, topK: 5 }),
        new Promise((resolve) => setTimeout(() => resolve(null), 5000)),
      ]);
      const relevant = (mems || []).filter((m) => m.similarity >= 0.45);
      if (relevant.length) {
        const lines = relevant.map((m) => {
          const when = m.timestamp ? new Date(m.timestamp).toISOString().slice(0, 10) : "";
          return `- (${m.speaker || "?"}${when ? ", " + when : ""}) ${m.message}`;
        }).join("\n");
        userContent =
          "[Memory recall \u2014 relevant notes from earlier conversations. PAST context, not the current message:]\n" +
          lines + "\n\n[Current message:]\n" + message;
      }
    } catch (err) { console.error(`[${NAME} memory] recall failed:`, err.message); }
  }
  // THINK-ATTACH — fold uploaded files into the user turn
  let finalUserContent = userContent;
  if (Array.isArray(attachments) && attachments.length) {
    try {
      const built = buildAttachmentContent({ text: userContent, attachments, sid });
      if (built.skipped?.length) send("attachments_skipped", { items: built.skipped });
      if (built.accepted?.length) send("attachments_attached", { items: built.accepted });
      finalUserContent = built.content;
    } catch (err) {
      send("attachments_skipped", { items: [{ filename: "(all)", reason: err.message }] });
    }
  }
  session.messages.push({ role: "user", content: finalUserContent });
  if (useMemory) {
    storeMemory({ agentName: NAME, conversationId: sid, speaker: "rosa", messageText: message, metadata: { surface: `${NAME}-chat` } })
      .catch((err) => console.error(`[${NAME} memory] store(user) failed:`, err.message));
  }

  let assistantText = "";
  const sendCapture = (event, data) => {
    if (event === "text_delta" && data && typeof data.delta === "string") assistantText += data.delta;
    send(event, data);
  };
  try {
    await runTurn({ messages: session.messages, onEvent: sendCapture });
  } catch (err) {
    sendCapture("error", { message: err.message });
  }
  if (useMemory && assistantText.trim()) {
    storeMemory({ agentName: NAME, conversationId: sid, speaker: NAME, messageText: assistantText.trim(), metadata: { surface: `${NAME}-chat` } })
      .catch((err) => console.error(`[${NAME} memory] store(reply) failed:`, err.message));
  }
  res.end();
});

app.post(`${BASE}/api/reset`, (req, res) => {
  sessions.delete(sanitizeSessionId(req.body?.sessionId));
  res.json({ ok: true });
});

setInterval(() => {
  const cutoff = Date.now() - 1000 * 60 * 60 * 24;
  for (const [id, s] of sessions.entries()) if (s.lastActive < cutoff) sessions.delete(id);
}, 1000 * 60 * 60).unref();

app.listen(PORT, HOST, () => {
  const backup = PRIMARY === "kimi" ? "openai->local" : "kimi->openai->local";
  console.log(`${NAME}-think listening on ${HOST}:${PORT}${BASE}/api (primary=${PRIMARY}, backup=${backup}, tools=13)`);
});
