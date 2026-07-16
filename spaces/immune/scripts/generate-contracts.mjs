import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const specPath = path.join(root, "openapi.json");
const outputPath = path.join(root, "src", "shared", "contract.generated.mjs");
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

if (process.argv.includes("--check")) {
  const current = await readFile(outputPath, "utf8").catch(() => "");
  if (current !== source) {
    console.error("Generated Immune contract is stale. Run npm run contracts:generate in spaces/immune.");
    process.exitCode = 1;
  }
} else {
  await writeFile(outputPath, source, "utf8");
}
