// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings
// Exercise the installed tarball with plain Node, outside the source checkout.
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const temporary = mkdtempSync(join(tmpdir(), "szl-rae1-packed-"));
assert.equal(dirname(resolve(temporary)), resolve(tmpdir()));
assert.ok(basename(temporary).startsWith("szl-rae1-packed-"));
const npmCli = process.env.npm_execpath;
assert.ok(npmCli, "run this check with npm run test:package");

function run(executable, args, cwd) {
  const result = spawnSync(executable, args, {
    cwd, encoding: "utf8", timeout: 120_000, shell: false,
  });
  if (result.error || result.status !== 0) {
    throw new Error(`${executable} failed: ${result.error ?? result.stderr}\n${result.stdout}`);
  }
  return result.stdout;
}

try {
  // npm pack runs this package's prepack build. Install the resulting archive,
  // never a source-directory link. Node declarations are its only dependency.
  const packed = JSON.parse(run(process.execPath,
    [npmCli, "pack", "--json", "--pack-destination", temporary], root));
  assert.equal(packed.length, 1);
  const paths = new Set(packed[0].files.map((file) => file.path));
  const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  for (const entry of Object.values(manifest.exports)) {
    assert.ok(paths.has(entry.import.replace(/^\.\//, "")), entry.import);
    assert.ok(paths.has(entry.types.replace(/^\.\//, "")), entry.types);
  }
  assert.ok(![...paths].some((path) => path.includes("node_modules") || path.endsWith(".test.ts")));
  writeFileSync(join(temporary, "package.json"), JSON.stringify({ private: true, type: "module" }));
  // A fresh npm ci caches tarballs but may lack dependency registry metadata.
  run(process.execPath, [npmCli, "install", join(temporary, packed[0].filename),
    "--prefer-offline", "--ignore-scripts", "--legacy-peer-deps", "--no-audit", "--no-fund"], temporary);
  const consumer = `
import assert from 'node:assert/strict';
import { createHash, createHmac, randomBytes } from 'node:crypto';
import * as rae from '@szl-holdings/rae1';
import * as schema from '@szl-holdings/rae1/schema';
import * as validation from '@szl-holdings/rae1/validate';
import * as chain from '@szl-holdings/rae1/chain';
import * as hmac from '@szl-holdings/rae1/hmac';
assert.equal(rae.RAE1_SCHEMA_VERSION, schema.RAE1_SCHEMA_VERSION);
assert.equal(rae.validateRAE1Schema, validation.validateRAE1Schema);
assert.equal(rae.computeLineHash, chain.computeLineHash);
assert.equal(rae.makeKeyId, hmac.makeKeyId);
const key = randomBytes(32);
const expectedId = 'hmac-sha256:' + createHash('sha256').update(key).digest('hex');
assert.equal(rae.makeKeyId(key), expectedId);
const type = 'application/json';
const body = Buffer.from('abc€!');
const envelope = {payloadType: type, payload: body.toString('base64url'), signatures: []};
const expectedPae = Buffer.from('DSSEv1 16 application/json 7 abc€!');
assert.deepEqual(rae.pae([type, envelope.payload]), expectedPae);
const signed = rae.signEnvelope(envelope, key, expectedId);
assert.equal(envelope.signatures.length, 0);
assert.equal(signed.signatures[0].sig, createHmac('sha256', key).update(expectedPae).digest('base64url'));
assert.equal(rae.verifyHMAC(signed, key), true);
assert.equal(rae.verifyHMAC(signed, randomBytes(32)), false);
assert.equal(rae.verifyHMAC({...signed, payload: Buffer.from('tampered').toString('base64url')}, key), false);
assert.equal(rae.verifyHMAC({...signed, signatures: [{keyid: expectedId, sig: 'short'}]}, key), false);
assert.equal(rae.validateRAE1Schema({}).valid, false);
assert.equal(rae.computeChainHead('').chain_head, rae.CHAIN_GENESIS);
assert.equal(rae.computeLineHash('receipt'), createHash('sha256').update('receipt').digest('hex'));
console.log('Installed RAE-1 tarball: all public imports, HMAC verification, tamper rejection, and chain hashing passed');
`;
  writeFileSync(join(temporary, "consumer.mjs"), consumer, "utf8");
  process.stdout.write(run(process.execPath, [join(temporary, "consumer.mjs")], temporary));
  // Check the declarations from the installed archive, without relying on
  // ambient Node types from this checkout or the caller's TypeScript project.
  writeFileSync(join(temporary, "consumer.mts"), `
import {Buffer} from 'node:buffer';
import {makeKeyId, RAE1_SCHEMA_VERSION, type DSSEEnvelope} from '@szl-holdings/rae1';
import {validateRAE1Schema} from '@szl-holdings/rae1/validate';
const version: string = RAE1_SCHEMA_VERSION;
const envelope: DSSEEnvelope = {payloadType: 'application/vnd.szl.rae1+json', payload: '', signatures: []};
export function check(key: Buffer): string {
  const id: string = makeKeyId(key);
  const valid: boolean = validateRAE1Schema(envelope).valid;
  return version + id + valid;
}
`, "utf8");
  writeFileSync(join(temporary, "tsconfig.json"), JSON.stringify({
    compilerOptions: { target: "ES2022", module: "NodeNext", moduleResolution: "NodeNext",
      strict: true, noEmit: true, types: ["node"], typeRoots: ["./node_modules/@types"],
      skipLibCheck: false },
    files: ["consumer.mts"],
  }));
  run(process.execPath, [join(root, "node_modules/typescript/lib/tsc.js"),
    "-p", join(temporary, "tsconfig.json")], temporary);
  console.log("Installed RAE-1 declarations: clean TypeScript consumer passed");
} finally {
  // Only remove the unique temporary directory created by this check.
  rmSync(temporary, { recursive: true, force: true });
}
