// Lets an enabled agent (Vesper) message other tribe members and get their reply.
// Gated via THINK_ENABLE_TEAMMATE on the agent's pm2 env. One round-trip per call.

const TEAMMATES = {
  delphina: {
    kind: "think-sse",
    url: "http://127.0.0.1:8101/delphina/api/chat",
    token: () => process.env.DELPHINA_AUTH_TOKEN,
    display: "Delphina",
  },
  jarvis: {
    kind: "openai-json",
    url: "http://127.0.0.1:8093/jarvis/api/chat",
    token: () => process.env.JARVIS_AUTH_TOKEN || process.env.IRIS_AUTH_TOKEN || "jarvis-token",
    display: "Jarvis",
  },
};

async function callThinkSSE(t, message) {
  const r = await fetch(t.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t.token()}` },
    body: JSON.stringify({ message, sessionId: "vesper", attachments: [] }),
  });
  if (!r.ok) { const e = await r.text().catch(() => ""); return { error: `${t.display} upstream ${r.status} ${e.slice(0, 160)}` }; }
  const raw = await r.text();
  let text = "";
  for (const line of raw.split("\n")) {
    const s = line.trim();
    if (!s.startsWith("data:")) continue;
    try { const d = JSON.parse(s.slice(5).trim()); if (typeof d.delta === "string") text += d.delta; } catch {}
  }
  return { reply: text.trim() || "(no reply)" };
}

async function callOpenAIJson(t, message) {
  const r = await fetch(t.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t.token()}` },
    body: JSON.stringify({ messages: [{ role: "user", content: message }] }),
  });
  if (!r.ok) { const e = await r.text().catch(() => ""); return { error: `${t.display} upstream ${r.status} ${e.slice(0, 160)}` }; }
  const j = await r.json().catch(() => ({}));
  return { reply: j?.choices?.[0]?.message?.content || "(no reply)" };
}

export const message_teammate = {
  name: "message_teammate",
  description:
    "Send a message to another tribe member and get their reply right now. Teammates: 'delphina' (simulations & pattern-navigation, real brain) and 'jarvis' (knowledge & research). Use this to consult or coordinate. It is one round-trip — they answer now and cannot call you back later.",
  input_schema: {
    type: "object",
    properties: {
      teammate: { type: "string", description: "delphina or jarvis" },
      message: { type: "string", description: "What you want to say or ask them." },
    },
    required: ["teammate", "message"],
  },
  async execute({ teammate, message }) {
    const key = String(teammate || "").toLowerCase();
    const t = TEAMMATES[key];
    if (!t) return { error: `unknown teammate '${teammate}'. Options: ${Object.keys(TEAMMATES).join(", ")}` };
    if (!message) return { error: "message required" };
    try {
      const res = t.kind === "think-sse" ? await callThinkSSE(t, message) : await callOpenAIJson(t, message);
      return { teammate: t.display, ...res };
    } catch (e) {
      return { error: `failed to reach ${t.display}: ${e.message}` };
    }
  },
};

export const TEAMMATE_TOOLS = [message_teammate];
