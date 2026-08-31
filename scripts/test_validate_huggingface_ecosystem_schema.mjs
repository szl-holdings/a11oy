#!/usr/bin/env node
// Regression checks for full Hugging Face manifest/schema validation.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validateManifest } from "./validate_huggingface_ecosystem_schema.mjs";

const manifest = JSON.parse(
  readFileSync("docs/huggingface-ecosystem-manifest.json", "utf8"),
);
const schema = JSON.parse(
  readFileSync("docs/huggingface-ecosystem-manifest.schema.json", "utf8"),
);

validateManifest(manifest, schema);

const missingRevision = structuredClone(manifest);
delete missingRevision.inventory.models[0].sha;
assert.throws(
  () => validateManifest(missingRevision, schema),
  /must have required property 'sha'/,
);

const missingCardDigest = structuredClone(manifest);
delete missingCardDigest.inventory.models[0].cardSemanticSha256;
assert.throws(
  () => validateManifest(missingCardDigest, schema),
  /must have required property 'cardSemanticSha256'/,
);

const incompatibleSchema = structuredClone(schema);
incompatibleSchema.properties.schemaVersion.const = 999;
assert.throws(
  () => validateManifest(manifest, incompatibleSchema),
  /must be equal to constant/,
);

console.log("Hugging Face ecosystem schema regressions passed");
