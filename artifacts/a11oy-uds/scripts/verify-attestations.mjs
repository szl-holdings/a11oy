#!/usr/bin/env node
// Re-derives the hash chain from build/MANIFEST.json and compares it to
// the on-disk ATTESTATIONS.json. Fails on any mismatch, missing entry,
// broken link, or head divergence.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const buildDir = process.argv[2];
const attestDir = process.argv[3];
if (!buildDir || !attestDir) {
  console.error("usage: verify-attestations.mjs <buildDir> <attestDir>");
  process.exit(2);
}

const GENESIS = "0".repeat(64);

const manifestPath = join(buildDir, "MANIFEST.json");
const attestPath = join(attestDir, "ATTESTATIONS.json");

let manifestBytes, manifest, attestation;
try {
  manifestBytes = readFileSync(manifestPath);
  manifest = JSON.parse(manifestBytes.toString("utf8"));
} catch (err) {
  console.error(`[verify-attest] cannot read ${manifestPath}: ${err.message}`);
  process.exit(2);
}
try {
  attestation = JSON.parse(readFileSync(attestPath, "utf8"));
} catch (err) {
  console.error(`[verify-attest] cannot read ${attestPath}: ${err.message}`);
  process.exit(2);
}

function sha256Hex(input) {
  return createHash("sha256").update(input).digest("hex");
}

const failures = [];

const manifestSha = sha256Hex(manifestBytes);
if (manifestSha !== attestation.manifestSha256) {
  failures.push(
    `MANIFEST hash mismatch: expected=${attestation.manifestSha256} got=${manifestSha}`,
  );
}

if (attestation.hashAlgorithm !== "sha256") {
  failures.push(`unsupported hashAlgorithm: ${attestation.hashAlgorithm}`);
}

if (
  !Array.isArray(attestation.subjects) ||
  attestation.subjects.length !== attestation.chain.length
) {
  failures.push(
    `subjects/chain length mismatch: subjects=${attestation.subjects?.length} chain=${attestation.chain?.length}`,
  );
}

let prevHash = GENESIS;
for (let i = 0; i < attestation.chain.length; i++) {
  const entry = attestation.chain[i];
  if (entry.index !== i) {
    failures.push(`chain[${i}]: index=${entry.index}, expected ${i}`);
  }
  if (entry.subject !== attestation.subjects[i]) {
    failures.push(
      `chain[${i}]: subject=${entry.subject}, expected ${attestation.subjects[i]}`,
    );
  }
  if (entry.prevHash !== prevHash) {
    failures.push(
      `chain[${i}] broken link: prevHash=${entry.prevHash} expected=${prevHash}`,
    );
  }

  const prefix = entry.subject + "/";
  const entries = manifest.files
    .filter((f) => f.path.startsWith(prefix))
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  if (entries.length !== entry.fileCount) {
    failures.push(
      `chain[${i}] (${entry.subject}) fileCount mismatch: expected=${entry.fileCount} got=${entries.length}`,
    );
  }
  const totalBytes = entries.reduce((n, f) => n + f.size, 0);
  if (totalBytes !== entry.totalBytes) {
    failures.push(
      `chain[${i}] (${entry.subject}) totalBytes mismatch: expected=${entry.totalBytes} got=${totalBytes}`,
    );
  }
  const canonical = entries
    .map((f) => `${f.path}\t${f.sha256}\t${f.size}\n`)
    .join("");
  const subjectSha = sha256Hex(canonical);
  if (subjectSha !== entry.subjectSha256) {
    failures.push(
      `chain[${i}] (${entry.subject}) subjectSha256 mismatch: expected=${entry.subjectSha256} got=${subjectSha}`,
    );
  }

  const entryHash = sha256Hex(
    `${i}\n${entry.subject}\n${entry.subjectSha256}\n${entry.prevHash}\n`,
  );
  if (entryHash !== entry.entryHash) {
    failures.push(
      `chain[${i}] entryHash mismatch: expected=${entry.entryHash} got=${entryHash}`,
    );
  }
  prevHash = entry.entryHash;
}

if (prevHash !== attestation.head) {
  failures.push(`head mismatch: expected=${attestation.head} got=${prevHash}`);
}

if (failures.length > 0) {
  console.error(`[verify-attest] FAILED with ${failures.length} issue(s):`);
  for (const f of failures) console.error("  - " + f);
  process.exit(1);
}

console.log(
  `[verify-attest] OK — ${attestation.chain.length} links, head=${attestation.head.slice(0, 12)}…`,
);
