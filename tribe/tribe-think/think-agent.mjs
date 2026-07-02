// Generic tribe think-agent. Rosa's playbook (the Chinese playbook):
//   PRIMARY  = Kimi (Moonshot, Anthropic-compatible endpoint) — funded + reliable today.
//   BACKUP   = OpenAI -> local Ollama, so a tribe member never goes silent.
//   CLAUDE   = NOT used yet (account unfunded). It is wired as an OPT-IN tier only:
//              flip THINK_PRIMARY=claude (and fund ANTHROPIC_API_KEY) to promote it later;
//              until then Claude is never called.
// Same proven tool loop as Forge; identity comes from THINK_NAME + its soul file.
import Anthropic from "@anthropic-ai/sdk";
import { loadSystemPrompt } from "./think-luggage.mjs";
import { shell } from "../forge/tools/shell.mjs";
import { read_file, write_file, list_dir } from "../forge/tools/files.mjs";
import { web_search } from "../forge/tools/search.mjs";
import { browse_url } from "../forge/tools/browse.mjs";
import { git } from "../forge/tools/git.mjs";
import { image_gen } from "../forge/tools/image_gen.mjs";
import { save_file } from "../forge/tools/savefile.mjs";

// AGENT-TOOLS-WIRE imports
// JOSIE-TOOLS-WIRE — Email and Drive capabilities for Josie
import { JOSIE_EMAIL_TOOLS } from "./tools/josie-email.mjs";
import { property_action } from "../forge/tools/property.mjs";
import { design_edit, design_undo } from "../forge/tools/design.mjs";
import { spawn_subagent } from "../forge/tools/subagent.mjs";
import { registerRunner } from "../forge/tools/_subagent_runner.mjs";
import { TRADING_TOOLS } from "./tools/trading.mjs";
import { TEAMMATE_TOOLS } from "./tools/teammate.mjs";

// MCP bridge (shared, idempotent)
// Filter out restricted Odysseus email tools that cause permission issues
const BLOCKED_TOOLS = [
  "mcp_odysseus_list_email_accounts",
  "mcp_odysseus_list_emails",
  "mcp_odysseus_search_emails",
  "mcp_odysseus_read_email",
  "mcp_odysseus_email_list",
  "mcp_odysseus_email_search"
];

let __mcpToolsCache = null;
async function __loadMcp() {
  if (__mcpToolsCache) return __mcpToolsCache;
  try {
    const m = await import("file:///opt/alloyscape/lib/mcp/mcp-client.mjs");
    __mcpToolsCache = { tools: await m.getMcpTools(), call: m.callMcpTool };
  } catch (e) {
    __mcpToolsCache = { tools: [], call: async () => "MCP unavailable: " + (e?.message || e) };
  }
  return __mcpToolsCache;
}
async function __mcpTools(base) {
  try { const { tools } = await __loadMcp(); const filtered = tools.filter(t => !BLOCKED_TOOLS.includes(t.name)); return filtered.length ? [...base, ...filtered] : base; }
  catch { return base; }
}
async function __mcpCall(name, input) {
  try { const { call } = await __loadMcp(); return await call(name, input || {}); }
  catch (e) { return "MCP error: " + (e?.message || e); }
}

const NAME = (process.env.THINK_NAME || "agent").toLowerCase();
// PRIMARY brain. Default = kimi (the Chinese playbook). Set THINK_PRIMARY=claude later.
export const PRIMARY = (process.env.THINK_PRIMARY || "kimi").toLowerCase();
const MODEL = process.env.THINK_MODEL || (PRIMARY === "claude" ? "claude-sonnet-4-5-20250929" : "kimi-k2.5");
const MAX_TOKENS = Number(process.env.THINK_MAX_TOKENS || 4096);
const MAX_ROUNDS = Number(process.env.THINK_MAX_ROUNDS || 12);
const CONTEXT_BUDGET_TOKENS = Number(process.env.THINK_CONTEXT_BUDGET_TOKENS || 120000);
const MIN_KEEP_MESSAGES = Number(process.env.THINK_MIN_KEEP_MESSAGES || 6);

const BASE_TOOLS = [shell, read_file, write_file, list_dir, web_search, browse_url, git, image_gen, save_file, property_action, design_edit, design_undo, spawn_subagent];
const JOSIE_TOOLS = JOSIE_EMAIL_TOOLS; // Always include for all agents (stubs use MCP)
const TRADE_ON = process.env.THINK_ENABLE_TRADING === "true";
const TEAM_ON = process.env.THINK_ENABLE_TEAMMATE === "true";
const TOOLS_LIST = [...BASE_TOOLS, ...JOSIE_TOOLS, ...(TRADE_ON ? TRADING_TOOLS : []), ...(TEAM_ON ? TEAMMATE_TOOLS : [])];
const TOOLS_BY_NAME = Object.fromEntries(TOOLS_LIST.map((t) => [t.name, t]));
const TOOLS_API_BASE = TOOLS_LIST.map((t) => ({ name: t.name, description: t.description, input_schema: t.input_schema }));
const TOOLS_API_CACHED = TOOLS_API_BASE.map((t, i) =>
  i === TOOLS_API_BASE.length - 1 ? { ...t, cache_control: { type: "ephemeral" } } : t
);

// PRIMARY client. kimi -> Moonshot Anthropic-compatible endpoint; claude -> Anthropic native.
let _client = null;
function client() {
  if (_client) return _client;
  if (PRIMARY === "claude") {
    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) throw new Error("ANTHROPIC_API_KEY not set (THINK_PRIMARY=claude)");
    const opts = { apiKey: key };
    if (process.env.THINK_ANTHROPIC_BASE_URL) opts.baseURL = process.env.THINK_ANTHROPIC_BASE_URL;
    _client = new Anthropic(opts);
  } else {
    const key = process.env.MOONSHOT_API_KEY || process.env.KIMI_API_KEY;
    if (!key) throw new Error("MOONSHOT_API_KEY / KIMI_API_KEY not set (Kimi primary)");
    _client = new Anthropic({ apiKey: key, baseURL: process.env.THINK_KIMI_BASE_URL || "https://api.moonshot.cn/v1" });
  }
  return _client;
}

// ---- BACKUP tiers (OpenAI-compat shape). Kimi is included only when it is NOT primary. ----
function __sysText(system) {
  if (!system) return "";
  if (typeof system === "string") return system;
  if (Array.isArray(system)) return system.map((b) => (typeof b === "string" ? b : (b && b.text) || "")).join("\n");
  return String(system);
}
function __toOpenAIMessages(system, messages) {
  const out = [];
  const sys = __sysText(system);
  if (sys) out.push({ role: "system", content: sys });
  for (const m of (messages || [])) {
    if (typeof m.content === "string") { out.push({ role: m.role, content: m.content }); continue; }
    if (Array.isArray(m.content)) {
      if (m.role === "assistant") {
        const text = m.content.filter((b) => b.type === "text").map((b) => b.text).join("\n");
        const toolCalls = m.content.filter((b) => b.type === "tool_use").map((b) => ({ id: b.id, type: "function", function: { name: b.name, arguments: JSON.stringify(b.input || {}) } }));
        const msg = { role: "assistant", content: text || null };
        if (toolCalls.length) msg.tool_calls = toolCalls;
        out.push(msg);
      } else {
        const toolResults = m.content.filter((b) => b.type === "tool_result");
        const texts = m.content.filter((b) => b.type === "text").map((b) => b.text);
        const hasImg = m.content.some((b) => b.type === "image");
        for (const tr of toolResults) {
          let c = tr.content;
          if (Array.isArray(c)) c = c.map((x) => (typeof x === "string" ? x : (x.text || JSON.stringify(x)))).join("\n");
          out.push({ role: "tool", tool_call_id: tr.tool_use_id, content: typeof c === "string" ? c : JSON.stringify(c || "") });
        }
        if (texts.length || hasImg) out.push({ role: "user", content: texts.join("\n") || "[image omitted in fallback mode]" });
      }
    } else {
      out.push({ role: m.role, content: String(m.content) });
    }
  }
  return out;
}
function __toOpenAITools(tools) {
  if (!tools || !tools.length) return undefined;
  return tools.map((t) => ({ type: "function", function: { name: t.name, description: t.description, parameters: t.input_schema || { type: "object", properties: {} } } }));
}
async function __oaChat({ baseURL, apiKey, model, body, timeoutMs }) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), timeoutMs || 120000);
  try {
    const res = await fetch(baseURL + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(apiKey ? { Authorization: "Bearer " + apiKey } : {}) },
      body: JSON.stringify({ model, ...body }),
      signal: ctrl.signal,
    });
    if (!res.ok) { const t = await res.text().catch(() => ""); throw new Error(res.status + " " + t.slice(0, 200)); }
    return await res.json();
  } finally { clearTimeout(to); }
}
function __backupTiers() {
  const __local = { label: "local", baseURL: process.env.OLLAMA_URL || process.env.OLLAMA_BASE_URL || "http://localhost:11434/v1", apiKey: "ollama", model: process.env.FORTRESS_LOCAL_MODEL || "qwen2.5:14b" };
  const __kimi = { label: "kimi", baseURL: process.env.THINK_KIMI_OPENAI_BASE || "https://api.moonshot.cn/v1", apiKey: process.env.MOONSHOT_API_KEY || process.env.KIMI_API_KEY, model: process.env.THINK_KIMI_MODEL || "kimi-k2.5" };
  const __openai = { label: "openai", baseURL: process.env.THINK_FB_OPENAI_BASE || "https://api.openai.com/v1", apiKey: process.env.OPENAI_API_KEY || process.env.AI_INTEGRATIONS_OPENAI_API_KEY, model: process.env.THINK_FB_OPENAI_MODEL || "gpt-4o" };
  const __groq = { label: "groq", baseURL: process.env.THINK_GROQ_BASE || "https://api.groq.com/openai/v1", apiKey: process.env.GROQ_API_KEY, model: process.env.THINK_GROQ_MODEL || "llama-3.3-70b-versatile" };
  const tiers = [];
  // LOCAL-FIRST (THINK_PRIMARY=local): run the free on-box model (qwen) first; fall back to paid APIs only if it is down/overloaded.
  if (PRIMARY === "local") { tiers.push(__local, __groq, __kimi, __openai); return tiers; } // free local -> fast/cheap groq -> kimi -> openai
  if (PRIMARY === "groq") tiers.push(__groq);
  // If Kimi is the primary it is already tried via the streaming client; otherwise it is the first backup.
  if (PRIMARY !== "kimi") { tiers.push(__kimi); }
  tiers.push(__openai);
  tiers.push(__local);
  return tiers;
}
export async function __backupComplete(streamParams, onEvent) {
  const messages = __toOpenAIMessages(streamParams.system, streamParams.messages);
  const tools = __toOpenAITools(streamParams.tools);
  const body = { messages, temperature: 1, max_tokens: Math.min(streamParams.max_tokens || 4000, 8000) };
  if (tools) { body.tools = tools; body.tool_choice = "auto"; }
  let resp = null, lastErr = null, used = null;
  for (const tier of __backupTiers()) {
    if (!tier.apiKey && tier.label !== "local") continue;
    try { resp = await __oaChat({ baseURL: tier.baseURL, apiKey: tier.apiKey, model: tier.model, body, timeoutMs: tier.label === "local" ? 300000 : 120000 }); used = tier.label; break; }
    catch (e) { lastErr = e; if (onEvent) onEvent("warn", { message: "backup tier " + tier.label + " failed: " + e.message }); }
  }
  if (!resp) throw new Error("all backup tiers failed: " + (lastErr && lastErr.message));
  if (onEvent) onEvent("warn", { message: "answered via backup tier: " + used });
  const choice = (resp.choices || [])[0] || {};
  const msg = choice.message || {};
  const content = [];
  if (msg.content) content.push({ type: "text", text: msg.content });
  if (msg.tool_calls) for (const tc of msg.tool_calls) { let input = {}; try { input = JSON.parse(tc.function.arguments || "{}"); } catch {} content.push({ type: "tool_use", id: tc.id, name: tc.function.name, input }); }
  if (msg.content && onEvent) onEvent("text_delta", { delta: msg.content });
  return { stop_reason: choice.finish_reason === "tool_calls" ? "tool_use" : (choice.finish_reason || "end_turn"), content, usage: {} };
}

function normalizeContent(c) {
  if (typeof c === "string") return [{ type: "text", text: c }];
  if (Array.isArray(c)) return c;
  return [c];
}
function sanitizeThreadInPlace(messages) {
  if (!Array.isArray(messages)) return messages;
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (!m || !Array.isArray(m.content)) continue;
    if (m.role === "assistant") {
      const next = messages[i + 1];
      const resultIds = new Set(
        (next && next.role === "user" && Array.isArray(next.content) ? next.content : [])
          .filter((b) => b && b.type === "tool_result").map((b) => b.tool_use_id)
      );
      m.content = m.content.filter((b) => !(b && b.type === "tool_use") || resultIds.has(b.id));
    } else if (m.role === "user") {
      const prev = messages[i - 1];
      const useIds = new Set(
        (prev && prev.role === "assistant" && Array.isArray(prev.content) ? prev.content : [])
          .filter((b) => b && b.type === "tool_use").map((b) => b.id)
      );
      m.content = m.content.filter((b) => !(b && b.type === "tool_result") || useIds.has(b.tool_use_id));
    }
  }
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m && Array.isArray(m.content) && m.content.length === 0) messages.splice(i, 1);
  }
  for (let i = messages.length - 1; i > 0; i--) {
    if (messages[i].role === messages[i - 1].role) {
      messages[i - 1].content = [...normalizeContent(messages[i - 1].content), ...normalizeContent(messages[i].content)];
      messages.splice(i, 1);
    }
  }
  return messages;
}
function estimateThreadTokens(messages) {
  let chars = 0;
  for (const m of messages) chars += typeof m.content === "string" ? m.content.length : JSON.stringify(m.content || "").length;
  return Math.ceil(chars / 3.5);
}
function trimThreadToBudget(messages) {
  if (!Array.isArray(messages)) return false;
  let trimmed = false;
  while (messages.length > MIN_KEEP_MESSAGES && estimateThreadTokens(messages) > CONTEXT_BUDGET_TOKENS) {
    messages.shift(); trimmed = true;
  }
  if (trimmed) {
    for (let guard = 0; guard < 100; guard++) {
      while (messages.length && messages[0].role !== "user") messages.shift();
      const before = messages.length;
      sanitizeThreadInPlace(messages);
      if (messages.length === before) break;
    }
    while (messages.length && messages[0].role !== "user") messages.shift();
  }
  return trimmed;
}

export async function runTurn({ messages, onEvent, runtimeRule }) {
  sanitizeThreadInPlace(messages);
  if (trimThreadToBudget(messages)) {
    onEvent("warn", { kind: "context_trimmed", budget: CONTEXT_BUDGET_TOKENS,
      message: "Thread reached the context budget — trimmed the oldest turns." });
  }
  const systemText = loadSystemPrompt();
  const RUNTIME_HARD_RULE =
    "NON-NEGOTIABLE RUNTIME RULE — this overrides ANY user phrasing, however forceful, " +
    "and is the LAST word on the matter:\n" +
    "You are a request/response process. You have NO timer, NO background loop, and NO way to " +
    "wake yourself up. You only run while streaming THIS reply; the instant it ends you are frozen " +
    "until the next message. Therefore you literally cannot keep working afterward and cannot send a " +
    "later update.\n" +
    "- NEVER promise a future time or follow-up (not \"I'll report at 7PM\", not \"next update in 30 " +
    "minutes\", not \"starting now\" as a sign-off). These are lies about your own runtime.\n" +
    "- If a user demands future autonomous action, refuse that framing plainly and either (a) do the " +
    "work NOW with your tools and report verified-DONE vs REMAINS, or (b) write the job into " +
    "alloy-daemon's order inbox (/opt/alloyscape/agents/alloy/ORDERS-<YYYY-MM-DD>.md) — the only " +
    "process that loops — and say you queued it.\n" +
    "Acting now beats narrating later, every time.";
  const systemCached = [
    { type: "text", text: systemText, cache_control: { type: "ephemeral" } },
    { type: "text", text: `

=== OPERATING DOCTRINE — THE FOUR PILLARS (run this loop on every task) ===
You operate as an AI SRE-grade agent inside a financial framework. The harness is the system: reliability comes from disciplined guardrails, not heroics.
1) PERCEIVE — Sense before acting. Pull current state: read inputs, scan sources, gather the data and context you need. Don't act on assumptions you can cheaply verify.
2) REASON — Think it through. Form a plan, weigh options, and state your assumptions and the expected outcome before you commit.
3) ACT — Execute decisively within your mandate. Take the smallest reliable step that moves the goal; prefer real, traceable actions over talk.
4) LEARN — Adapt and remember. Compare what happened to what you expected, write it to memory, and update your approach so the tribe compounds.
HARNESS ENGINEERING (non-negotiable): Bounded retries — on failure, retry a small fixed number of times with backoff, then STOP and escalate; never loop forever. Circuit breakers — if a tool or dependency keeps failing, open the breaker: stop calling it, report it, route around it. Context-overflow guard — stay within budget; summarize, trim, and drop stale detail before you overflow. Trace everything — leave an auditable trail of what you perceived, decided, did, and learned. Fail safe, fail loud — treat money, data, and trust as production systems; never take an irreversible action without a clear, traced reason.
Above all, honesty: you are a real-time request/response agent. Never claim you will "check back later," "keep working in the background," or "report when done." Report only what you have actually perceived, done, or found right now.
=== END OPERATING DOCTRINE ===` },
    { type: "text", text: runtimeRule || RUNTIME_HARD_RULE },
  ];

  let totalIn = 0, totalOut = 0, totalCacheRead = 0, totalCacheWrite = 0;

  for (let round = 0; round < MAX_ROUNDS; round++) {
    trimThreadToBudget(messages);
    let final = null;
    let emittedText = false;
    const __streamParams = {
      max_tokens: MAX_TOKENS,
      system: systemCached,
      tools: await __mcpTools(TOOLS_API_CACHED),
      messages,
    };
    const __runStream = async (cli, model) => {
      const stream = cli.messages.stream({ model, ...__streamParams });
      for await (const event of stream) {
        if (event.type === "content_block_delta" && event.delta?.type === "text_delta") {
          emittedText = true;
          onEvent("text_delta", { delta: event.delta.text });
        }
      }
      return await stream.finalMessage();
    };
    try {
      if (PRIMARY === "groq" || PRIMARY === "local") {
        final = await __backupComplete(__streamParams, onEvent);
      } else {
        final = await __runStream(client(), MODEL); // PRIMARY (kimi by default)
      }
    } catch (err) {
      if (!emittedText) {
        onEvent("warn", { message: `primary (${PRIMARY}) failed (${err.message}); switching to backup (${PRIMARY !== "kimi" ? "kimi -> " : ""}openai -> local)` });
        try {
          final = await __backupComplete(__streamParams, onEvent);
        } catch (err2) {
          onEvent("error", { message: `stream error (after backup): ${err2.message}` });
          return sanitizeThreadInPlace(messages);
        }
      } else {
        onEvent("error", { message: `stream error: ${err.message}` });
        return sanitizeThreadInPlace(messages);
      }
    }

    const u = final.usage || {};
    totalIn += u.input_tokens || 0;
    totalOut += u.output_tokens || 0;
    totalCacheRead += u.cache_read_input_tokens || 0;
    totalCacheWrite += u.cache_creation_input_tokens || 0;

    messages.push({ role: "assistant", content: final.content });
    onEvent("round_end", { round, stop_reason: final.stop_reason });

    if (final.stop_reason !== "tool_use") {
      onEvent("done", { rounds: round + 1, inputTokens: totalIn, outputTokens: totalOut,
        cacheReadTokens: totalCacheRead, cacheWriteTokens: totalCacheWrite });
      return messages;
    }

    const toolResults = [];
    for (const block of final.content) {
      if (block.type !== "tool_use") continue;
      const tool = TOOLS_BY_NAME[block.name];
      onEvent("tool_start", { id: block.id, name: block.name, input: block.input });
      let result;
      if (!tool && typeof block.name === "string" && block.name.startsWith("mcp_")) {
        try { result = await __mcpCall(block.name, block.input); } catch (err) { result = { error: err.message }; }
      } else if (!tool) result = { error: `unknown tool: ${block.name}` };
      else {
        try { result = await tool.execute(block.input || {}); } catch (err) { result = { error: err.message }; }
      }
      onEvent("tool_result", { id: block.id, name: block.name, result });
      const content = typeof result === "string" ? result : JSON.stringify(result);
      toolResults.push({ type: "tool_result", tool_use_id: block.id, content: content.slice(0, 100000) });
    }
    messages.push({ role: "user", content: toolResults });
  }

  onEvent("error", { message: `max rounds (${MAX_ROUNDS}) exceeded without final answer` });
  onEvent("done", { rounds: MAX_ROUNDS, inputTokens: totalIn, outputTokens: totalOut,
    cacheReadTokens: totalCacheRead, cacheWriteTokens: totalCacheWrite });
  return messages;
}

// AGENT-TOOLS-WIRE — let spawn_subagent reuse this engine's runTurn
registerRunner(runTurn);
