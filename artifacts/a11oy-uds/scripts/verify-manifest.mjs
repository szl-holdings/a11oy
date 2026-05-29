#!/usr/bin/env node
// Re-hashes every file listed in MANIFEST.json and fails on mismatch,
// missing file, or extra file in the build tree.
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const buildDir = process.argv[2] ?? join(process.cwd(), "build");
const manifestPath = join(buildDir, "MANIFEST.json");

let manifest;
try {
  manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
} catch (err) {
  console.error(`[verify] cannot read ${manifestPath}: ${err.message}`);
  process.exit(2);
}

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, acc);
    else if (st.isFile()) acc.push(full);
  }
  return acc;
}

const onDisk = new Set(
  walk(buildDir)
    .map((abs) => relative(buildDir, abs).split(sep).join("/"))
    .filter((rel) => rel !== "MANIFEST.json"),
);

const declared = new Set(manifest.files.map((f) => f.path));
const failures = [];

for (const entry of manifest.files) {
  const abs = join(buildDir, entry.path);
  let buf;
  try {
    buf = readFileSync(abs);
  } catch (err) {
    failures.push(`MISSING ${entry.path}: ${err.message}`);
    continue;
  }
  const sha = createHash("sha256").update(buf).digest("hex");
  if (sha !== entry.sha256) {
    failures.push(
      `HASH MISMATCH ${entry.path}: expected=${entry.sha256} got=${sha}`,
    );
  }
  if (buf.byteLength !== entry.size) {
    failures.push(
      `SIZE MISMATCH ${entry.path}: expected=${entry.size} got=${buf.byteLength}`,
    );
  }
}

for (const rel of onDisk) {
  if (!declared.has(rel)) failures.push(`EXTRA FILE ${rel} not in manifest`);
}

if (failures.length > 0) {
  console.error(`[verify] FAILED with ${failures.length} issue(s):`);
  for (const f of failures) console.error("  - " + f);
  process.exit(1);
}

console.log(
  `[verify] OK — ${manifest.files.length} files verified (${manifest.totalBytes} bytes, sha256)`,
);
