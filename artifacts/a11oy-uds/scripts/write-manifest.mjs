#!/usr/bin/env node
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";

const buildDir = process.argv[2];
if (!buildDir) {
  console.error("usage: write-manifest.mjs <buildDir>");
  process.exit(2);
}

const MANIFEST_NAME = "MANIFEST.json";

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      walk(full, acc);
    } else if (st.isFile()) {
      acc.push(full);
    }
  }
  return acc;
}

const files = walk(buildDir)
  .map((abs) => relative(buildDir, abs).split(sep).join("/"))
  .filter((rel) => rel !== MANIFEST_NAME)
  .sort();

const entries = files.map((rel) => {
  const abs = join(buildDir, rel);
  const buf = readFileSync(abs);
  return {
    path: rel,
    size: buf.byteLength,
    sha256: createHash("sha256").update(buf).digest("hex"),
  };
});

const manifest = {
  name: "a11oy-uds",
  version: process.env.VERSION ?? "0.0.0",
  gitSha: process.env.GIT_SHA ?? "unknown",
  builtAt: process.env.BUILD_TS ?? new Date().toISOString(),
  hashAlgorithm: "sha256",
  sourcePackaged: process.env.SOURCE_PACKAGED === "1",
  fileCount: entries.length,
  totalBytes: entries.reduce((n, e) => n + e.size, 0),
  files: entries,
};

writeFileSync(
  join(buildDir, MANIFEST_NAME),
  JSON.stringify(manifest, null, 2) + "\n",
);

console.log(
  `[a11oy-uds] manifest: ${entries.length} files, ${manifest.totalBytes} bytes`,
);
