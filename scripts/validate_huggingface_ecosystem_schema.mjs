#!/usr/bin/env node
// Validate the published Hugging Face manifest against its Draft 2020-12 schema.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1]
    ? process.argv[index + 1]
    : fallback;
}

export function validateManifest(manifest, schema) {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const validate = ajv.compile(schema);
  if (!validate(manifest)) {
    const detail = ajv.errorsText(validate.errors, {
      dataVar: "manifest",
      separator: "\n",
    });
    throw new Error(`Hugging Face ecosystem manifest violates its schema:\n${detail}`);
  }
}

export function main() {
  const manifestPath = arg(
    "manifest",
    "docs/huggingface-ecosystem-manifest.json",
  );
  const schemaPath = arg(
    "schema",
    "docs/huggingface-ecosystem-manifest.schema.json",
  );
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
  validateManifest(manifest, schema);
  console.log(
    `Hugging Face ecosystem schema validation passed: ${manifestPath}`,
  );
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
