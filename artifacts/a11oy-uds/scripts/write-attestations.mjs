#!/usr/bin/env node
// Builds the in-bundle hash-chained attestation sidecar from the
// per-file MANIFEST.json produced by write-manifest.mjs.
//
// Format (ATTESTATIONS.json):
//   {
//     name, version, gitSha, builtAt, hashAlgorithm: "sha256",
//     manifestSha256,                          // sha256 of MANIFEST.json bytes
//     subjects: ["a11oy-core","a11oy-connection"],
//     chain: [
//       { index, subject, fileCount, totalBytes, subjectSha256,
//         prevHash, entryHash }
//     ],
//     head                                     // entryHash of last entry
//   }
//
// Subject hash:
//   sha256 over the canonical line-stream
//     "<relPath>\t<sha256>\t<size>\n"
//   for every MANIFEST.files entry whose path starts with "<subject>/",
//   sorted by relPath. This is purely a function of MANIFEST.json so the
//   chain is round-trippable.
//
// Entry hash (link in the chain):
//   sha256("<index>\n<subject>\n<subjectSha256>\n<prevHash>\n")
//   prevHash for index=0 is 64 zeros (genesis).
//
// Output is written under <attestDir>/ATTESTATIONS.json so it does NOT
// pollute build/ (verify-manifest.mjs rejects extra files there).

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const buildDir = process.argv[2];
const attestDir = process.argv[3];
if (!buildDir || !attestDir) {
  console.error("usage: write-attestations.mjs <buildDir> <attestDir>");
  process.exit(2);
}

const GENESIS = "0".repeat(64);
const SUBJECTS = [
  "a11oy-core",
  "a11oy-connection",
  "shared/perception-loop",
  "shared/sequence-pipeline",
  "shared/sparse-attention-kit",
];

const manifestPath = join(buildDir, "MANIFEST.json");
const manifestBytes = readFileSync(manifestPath);
const manifest = JSON.parse(manifestBytes.toString("utf8"));

function sha256Hex(input) {
  return createHash("sha256").update(input).digest("hex");
}

function subjectDigest(subject) {
  const prefix = subject + "/";
  const entries = manifest.files
    .filter((f) => f.path.startsWith(prefix))
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  if (entries.length === 0) {
    throw new Error(`no files in MANIFEST.json for subject '${subject}'`);
  }
  const canonical = entries
    .map((f) => `${f.path}\t${f.sha256}\t${f.size}\n`)
    .join("");
  const totalBytes = entries.reduce((n, f) => n + f.size, 0);
  return {
    fileCount: entries.length,
    totalBytes,
    subjectSha256: sha256Hex(canonical),
  };
}

const chain = [];
let prevHash = GENESIS;
for (let i = 0; i < SUBJECTS.length; i++) {
  const subject = SUBJECTS[i];
  const { fileCount, totalBytes, subjectSha256 } = subjectDigest(subject);
  const entryHash = sha256Hex(
    `${i}\n${subject}\n${subjectSha256}\n${prevHash}\n`,
  );
  chain.push({
    index: i,
    subject,
    fileCount,
    totalBytes,
    subjectSha256,
    prevHash,
    entryHash,
  });
  prevHash = entryHash;
}

const attestation = {
  name: "a11oy-attestations",
  version: manifest.version,
  gitSha: manifest.gitSha,
  builtAt: manifest.builtAt,
  hashAlgorithm: "sha256",
  manifestSha256: sha256Hex(manifestBytes),
  subjects: SUBJECTS,
  chain,
  head: prevHash,
};

mkdirSync(attestDir, { recursive: true });
writeFileSync(
  join(attestDir, "ATTESTATIONS.json"),
  JSON.stringify(attestation, null, 2) + "\n",
);

console.log(
  `[a11oy-uds] attestations: ${chain.length} subjects, head=${attestation.head.slice(0, 12)}…`,
);
