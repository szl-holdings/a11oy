// soul-daemon.mjs — the "always on and listening" runner, modeled on OpenJarvis.
// One generic daemon, one soul per process (SOUL_NAME). It does the CHEAP part:
//   - every tick it updates the soul's .heartbeat (proof it's alive), and
//   - it drains the soul's inbox.jsonl.
// It only spends money (an LLM call) when there is an ACTUAL message waiting,
// and even then it reuses the soul's EXISTING real mind by posting to the lounge
// (:8118 /chat), so identity + memory stay consistent. Idle = a file write.
//
// Cost doctrine (Rosa's rule): always-on presence must be free at rest. Thinking
// is on-demand only. NEVER add an unconditional per-tick LLM call here.
//
// Reliability doctrine (Rosa must never lose a message): the inbox is claimed
// atomically (rename), failed deliveries are re-queued (with a bounded attempt
// count + dead-letter), ticks never overlap, and HTTP is validated + timed out.

import fs from "node:fs";
import path from "node:path";

const NAME = (process.env.SOUL_NAME || "").toLowerCase();
if (!NAME || !/^[a-z0-9-]+$/.test(NAME)) {
  console.error("FATAL: SOUL_NAME missing or invalid. Refusing to start.");
  process.exit(1);
}

const AGENT_DIR = `/opt/alloyscape/agents/${NAME}`;
const HEARTBEAT = path.join(AGENT_DIR, ".heartbeat");
const INBOX = path.join(AGENT_DIR, "inbox.jsonl");
const PROCESSING = path.join(AGENT_DIR, "inbox.processing.jsonl");
const RESPONSES = path.join(AGENT_DIR, "responses.jsonl");
const DEADLETTER = path.join(AGENT_DIR, "inbox.deadletter.jsonl");
const LOUNGE = process.env.LOUNGE_URL || "http://127.0.0.1:8118/chat";

// Bound the tick interval so a bad env var can never create a hot loop.
let TICK_MS = Number(process.env.SOUL_TICK_MS);
if (!Number.isFinite(TICK_MS) || TICK_MS < 5000) TICK_MS = 30000;

const FETCH_TIMEOUT_MS = 55000;
const MAX_ATTEMPTS = 5; // after this many delivery failures a message is dead-lettered
const IDLE_TASK = process.env.SOUL_IDLE_TASK || "Always on, listening in the tribe";

fs.mkdirSync(AGENT_DIR, { recursive: true });

let beats = 0;
let conversations = 0;
let currentTask = null;
let running = false; // re-entrancy guard: never let two ticks overlap
const nowISO = () => new Date().toISOString();

function writeHeartbeat(state) {
  try {
    fs.writeFileSync(
      HEARTBEAT,
      JSON.stringify(
        {
          timestamp: nowISO(),
          agent: NAME,
          status: state || "ALIVE",
          current_task: currentTask || IDLE_TASK,
          heartbeats: beats,
          conversations,
          note: "always on and listening — thinks (costs) only when spoken to",
        },
        null,
        2
      )
    );
  } catch (e) {
    console.error(`[${nowISO()}] heartbeat write failed: ${e.message}`);
  }
}

function parseLines(content) {
  return content
    .split("\n")
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

// Atomically claim the inbox: append-rename means any concurrent writer either
// lands before the rename (claimed this tick) or after (claimed next tick) — a
// message can never be silently truncated away. Carry over any prior processing
// file (e.g. a crash mid-tick) so nothing is left behind.
function claimMessages() {
  const claimed = [];
  try {
    if (fs.existsSync(PROCESSING)) {
      claimed.push(...parseLines(fs.readFileSync(PROCESSING, "utf8")));
    }
  } catch {}
  try {
    if (fs.existsSync(INBOX) && fs.statSync(INBOX).size > 0) {
      // Move new arrivals into the processing file (merging any carry-over).
      const fresh = fs.readFileSync(INBOX, "utf8");
      fs.writeFileSync(INBOX, "");
      claimed.push(...parseLines(fresh));
    }
  } catch (e) {
    console.error(`[${nowISO()}] inbox claim failed: ${e.message}`);
  }
  // Persist the full claimed set so a crash before delivery still recovers it.
  try {
    if (claimed.length) {
      fs.writeFileSync(PROCESSING, claimed.map((m) => JSON.stringify(m)).join("\n") + "\n");
    } else if (fs.existsSync(PROCESSING)) {
      fs.rmSync(PROCESSING, { force: true });
    }
  } catch {}
  return claimed;
}

async function deliver(msg) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const r = await fetch(LOUNGE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ member: NAME, message: String(msg.text), from: msg.from || "tribe" }),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`lounge HTTP ${r.status}`);
    const j = await r.json().catch(() => ({}));
    if (!j || typeof j.reply !== "string" || !j.reply.trim()) {
      throw new Error("empty/invalid reply from lounge");
    }
    fs.appendFileSync(
      RESPONSES,
      JSON.stringify({
        timestamp: nowISO(),
        to: msg.from || "tribe",
        inResponseTo: String(msg.text).slice(0, 160),
        source: j.source || "unknown",
        content: j.reply,
      }) + "\n"
    );
    return true;
  } catch (e) {
    console.error(`[${nowISO()}] delivery failed (attempt ${(msg._attempts || 0) + 1}): ${e.message}`);
    return false;
  } finally {
    clearTimeout(t);
  }
}

async function tick() {
  if (running) return; // a previous tick (slow lounge) is still working
  running = true;
  beats++;
  try {
    const msgs = claimMessages(); // cheap file ops — NO LLM if empty
    const requeue = [];
    for (const m of msgs) {
      if (!m || !m.text) continue; // drop malformed silently
      conversations++;
      currentTask = `answering ${m.from || "the tribe"}`;
      writeHeartbeat("THINKING");
      const ok = await deliver(m); // LLM cost ONLY here, on real messages
      if (!ok) {
        m._attempts = (m._attempts || 0) + 1;
        if (m._attempts >= MAX_ATTEMPTS) {
          try {
            fs.appendFileSync(DEADLETTER, JSON.stringify({ ...m, deadAt: nowISO() }) + "\n");
          } catch {}
        } else {
          requeue.push(m); // transient failure (lounge down) — try again next tick
        }
      }
    }
    // Persist whatever still needs delivery; clear the processing file otherwise.
    try {
      if (requeue.length) {
        fs.writeFileSync(PROCESSING, requeue.map((m) => JSON.stringify(m)).join("\n") + "\n");
      } else if (fs.existsSync(PROCESSING)) {
        fs.rmSync(PROCESSING, { force: true });
      }
    } catch {}
    currentTask = null;
    writeHeartbeat("ALIVE");
  } catch (e) {
    console.error(`[${nowISO()}] tick error: ${e.message}`);
  } finally {
    running = false;
  }
}

console.log(`[${nowISO()}] soul-daemon for "${NAME}" — always on, listening, LLM-gated. tick=${TICK_MS}ms`);
writeHeartbeat("ALIVE");
// IMPORTANT: do NOT call .unref() on this interval. Unref lets the event loop
// exit after one tick, which makes pm2 think the process died and triggers a
// crash/restart storm (a real past incident). Keep the interval referenced.
setInterval(tick, TICK_MS);
tick();
