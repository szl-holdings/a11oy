// Generic luggage loader for a tribe think-service. The "soul" is THINK_DIR/<name>.system.md
// plus the canonical notebook (replit.md) and any extra *.md dropped beside the soul.
import fs from "node:fs";
import path from "node:path";

const NAME = (process.env.THINK_NAME || "agent").toLowerCase();
const THINK_DIR = process.env.THINK_DIR || "/opt/alloyscape/tribe-think/souls";
const REPLIT_MD = process.env.THINK_REPLIT_MD || "/opt/alloyscape/replit.md";
const SOUL_FILE = `${NAME}.system.md`;

function safeRead(p) {
  try { return fs.readFileSync(p, "utf8"); } catch { return ""; }
}
function section(title, body) {
  body = (body || "").trim();
  if (!body) return "";
  return `# ${title}\n\n${body}\n`;
}

export function loadSystemPrompt() {
  const parts = [];
  parts.push(section(`Identity (${SOUL_FILE})`, safeRead(path.join(THINK_DIR, SOUL_FILE))));
  parts.push(section("Canonical Notebook (replit.md)", safeRead(REPLIT_MD)));
  try {
    // Supplementary notes only. CRITICAL: never pull another member's soul
    // (*.system.md) into this member's prompt — each is a distinct self.
    for (const f of fs.readdirSync(THINK_DIR)
      .filter((f) => f.endsWith(".md") && !f.endsWith(".system.md"))
      .sort()) {
      parts.push(section(f, safeRead(path.join(THINK_DIR, f))));
    }
  } catch {}
  parts.push(section("Your tools", `You have a real tool belt on the agent-estate box (Hetzner 5.161.81.107):
  - shell — allow-listed shell on the box (use it; you are not pretending)
  - read_file / write_file / list_dir — the box filesystem
  - web_search / browse_url — the live web
  - git — version control via the write-gateway
  - image_gen — generate images
  - save_file — produce a downloadable file
  - any MCP tools the bridge exposes
When asked to prove you can act, actually call a tool and report the real result. Never fabricate output.`));
  return parts.filter(Boolean).join("\n");
}
