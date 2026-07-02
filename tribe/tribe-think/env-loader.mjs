// Bulletproof env loader. MUST be the first import in think-server.mjs so it runs
// (per ESM linking order) before any other module's top-level code reads
// process.env. Tolerant of comments, blank lines, quoted values. Loads multiple
// files in order; later files do NOT override existing vars.
import fs from "node:fs";

const files = (process.env.THINK_ENV_FILES || "/opt/alloyscape/.env,/opt/alloyscape/artifacts/api-server/.env")
  .split(",").map((s) => s.trim()).filter(Boolean);

for (const file of files) {
  let text;
  try { text = fs.readFileSync(file, "utf8"); } catch { continue; }
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 1) continue;
    const key = line.slice(0, eq).trim();
    if (!/^[A-Z_][A-Z0-9_]*$/i.test(key)) continue;
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = val;
  }
}
