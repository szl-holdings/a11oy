import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const specPath = path.join(root, "openapi.json");
const outputPath = path.join(root, "src", "shared", "contract.generated.mjs");
const staticOutputPath = path.join(root, "src", "shared", "static-manifest.generated.mjs");
const spec = JSON.parse(await readFile(specPath, "utf8"));

const requiredOperations = [
  "getImmuneStatus",
  "inspectImmuneInput",
  "authorizeImmuneTool",
  "getImmuneReceipt",
  "getImmuneTripwires",
  "getImmuneSessionState",
  "updateImmuneSessionState",
];

const operations = {};
for (const [route, pathItem] of Object.entries(spec.paths ?? {})) {
  for (const [method, operation] of Object.entries(pathItem)) {
    if (operation?.operationId) operations[operation.operationId] = { method: method.toUpperCase(), route };
  }
}
for (const operationId of requiredOperations) {
  if (!operations[operationId]) throw new Error(`OpenAPI operation missing: ${operationId}`);
}

const source = `// Generated from spaces/immune/openapi.json. Do not edit by hand.\n` +
  `export const CONTRACT_VERSION = ${JSON.stringify(spec.info.version)};\n` +
  `export const API_BASE = "/api/immune/v1";\n` +
  `export const OPERATIONS = Object.freeze(${JSON.stringify(operations, null, 2)});\n` +
  `export const DECISIONS = Object.freeze(["ALLOW", "REVIEW", "DENY", "UNAVAILABLE"]);\n` +
  `export const CLASSIFIER_STATES = Object.freeze(["UNAVAILABLE", "THIRD_PARTY_BASELINE", "SZL_TRAINED_CANDIDATE", "QUALIFIED"]);\n` +
  `export const TRIPWIRE_IMPLEMENTATION_STATES = Object.freeze(["IMPLEMENTED", "NOT_IMPLEMENTED"]);\n` +
  `export const TRIPWIRE_EVALUATION_STATES = Object.freeze(["FIRED", "CLEAR", "NOT_EVALUATED"]);\n`;

const staticFiles = [
  ["/", "index.html", "text/html; charset=utf-8"],
  ["/index.html", "index.html", "text/html; charset=utf-8"],
  ["/styles.css", "styles.css", "text/css; charset=utf-8"],
  ["/app.js", "app.js", "text/javascript; charset=utf-8"],
];
const staticManifest = {};
for (const [route, file, type] of staticFiles) {
  const bytes = await readFile(path.join(root, "src", "public", file));
  staticManifest[route] = { file, type, sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length };
}
const staticSource = `// Generated from the exact spaces/immune/src/public assets. Do not edit by hand.\n` +
  `export const STATIC_MANIFEST = Object.freeze(${JSON.stringify(staticManifest, null, 2)});\n`;

if (process.argv.includes("--check")) {
  const current = await readFile(outputPath, "utf8").catch(() => "");
  const currentStatic = await readFile(staticOutputPath, "utf8").catch(() => "");
  if (current !== source || currentStatic !== staticSource) {
    console.error("Generated Immune contract is stale. Run npm run contracts:generate in spaces/immune.");
    process.exitCode = 1;
  }
} else {
  await writeFile(outputPath, source, "utf8");
  await writeFile(staticOutputPath, staticSource, "utf8");
}
