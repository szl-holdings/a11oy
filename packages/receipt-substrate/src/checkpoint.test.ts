// c2sp.org/signed-note and c2sp.org/tlog-checkpoint conformance + fail-closed checks.
// Test keys are generated in memory per run and never written anywhere.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as crypto from "node:crypto";
import {
  parseVerifierKey,
  ed25519KeyId,
  signNote,
  verifyNote,
  formatCheckpointBody,
  parseCheckpointBody,
  verifyCheckpoint,
  type VerifierKey,
} from "./checkpoint.ts";
import { hashLeaf, treeHash, consistencyProof, type Hash } from "./merkle_log.ts";

// Spec example (https://github.com/C2SP/C2SP/blob/main/signed-note.md, "Example").
const SPEC_VKEY = "example.com/foo+530d903a+AekyeRrm56hApGFkyQR4ZCbV54Id2LKaANYcrnKv3U2k";
const SPEC_NOTE =
  "This is an example message.\n\n\u2014 example.com/foo Uw2QOkn8srV1yJGh2VYRlL1Tnagv1YEq6TfXppzi2ONncAlTgK7Ztg1ERYNZXsYjOBH3mFXmRKuwHjG1Yu72IneyaQM=\n";

function testKey(name: string): { vkey: VerifierKey; priv: crypto.KeyObject; pubRaw: Buffer } {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const pubRaw = Buffer.from(publicKey.export({ format: "jwk" }).x as string, "base64url");
  return { vkey: { name, keyId: ed25519KeyId(name, pubRaw), publicKey: pubRaw }, priv: privateKey, pubRaw };
}

test("spec vector: the signed-note example verifies under its verifier key", () => {
  const key = parseVerifierKey(SPEC_VKEY);
  assert.equal(key.keyId, 0x530d903a);
  const r = verifyNote(SPEC_NOTE, [key]);
  assert.equal(r.valid, true, r.errors.join("; "));
  assert.equal(r.text, "This is an example message.\n");
  assert.deepEqual(r.verifiedKeyNames, ["example.com/foo"]);
});

test("spec vector: tampering with the text, the signature or the key name is rejected", () => {
  const key = parseVerifierKey(SPEC_VKEY);
  assert.equal(verifyNote(SPEC_NOTE.replace("example message", "example massage"), [key]).valid, false);
  assert.equal(verifyNote(SPEC_NOTE.replace("Uw2QOkn8", "Uw2QOkn9"), [key]).valid, false);
  assert.equal(verifyNote(SPEC_NOTE.replace("example.com/foo ", "example.com/bar "), [key]).valid, false); // unknown key -> no verified signer
  assert.equal(verifyNote(SPEC_NOTE, []).valid, false);
});

test("vkey parsing rejects a key id that does not match the key, and non-Ed25519 types", () => {
  assert.throws(() => parseVerifierKey(SPEC_VKEY.replace("530d903a", "530d903b")), /key id does not match/);
  assert.throws(() => parseVerifierKey("example.com/foo+530d903a"), /expected name\+keyid\+key/);
  assert.throws(() => parseVerifierKey("a b+530d903a+AekyeRrm56hApGFkyQR4ZCbV54Id2LKaANYcrnKv3U2k"), /expected|invalid/);
});

test("signed-note rules: unknown signers are ignored, a failing known signer rejects the note, duplicates are rejected", () => {
  const a = testKey("log.example/a");
  const b = testKey("log.example/b");
  const text = "hello\n";
  const noteA = signNote(text, a.vkey.name, a.priv, a.pubRaw);
  const noteB = signNote(text, b.vkey.name, b.priv, b.pubRaw);
  const sigLine = (n: string) => n.split("\n\n")[1];
  const both = `${text}\n${sigLine(noteA)}${sigLine(noteB)}`;
  assert.equal(verifyNote(both, [a.vkey]).valid, true); // b is unknown -> ignored
  assert.deepEqual(verifyNote(both, [a.vkey, b.vkey]).verifiedKeyNames, [a.vkey.name, b.vkey.name]);
  assert.equal(verifyNote(both, [a.vkey, b.vkey], [a.vkey.name, b.vkey.name]).valid, true);
  assert.equal(verifyNote(noteA, [a.vkey, b.vkey], [a.vkey.name, b.vkey.name]).valid, false); // witness policy not met
  // known key, bad signature -> reject the whole note even though another signer is good
  const badB = sigLine(noteB);
  const mid = badB.length - 12;
  const forged = `${text}\n${sigLine(noteA)}${badB.slice(0, mid)}${badB[mid] === "A" ? "B" : "A"}${badB.slice(mid + 1)}`;
  assert.notEqual(forged, both);
  assert.equal(verifyNote(forged, [a.vkey, b.vkey]).valid, false);
  assert.equal(verifyNote(`${text}\n${sigLine(noteA)}${sigLine(noteA)}`, [a.vkey]).valid, false);
});

test("signed-note framing fails closed: missing blank line, control characters, bad base64", () => {
  const a = testKey("log.example/a");
  const note = signNote("hello\n", a.vkey.name, a.priv, a.pubRaw);
  assert.equal(verifyNote(note.replace("\n\n", "\n"), [a.vkey]).valid, false);
  assert.equal(verifyNote(note.replace("hello", "hel\u0001lo"), [a.vkey]).valid, false);
  assert.equal(verifyNote(note.slice(0, -1), [a.vkey]).valid, false);
  assert.equal(verifyNote(note.replace(/=*\n$/, "\n").replace(/.\n$/, "!\n"), [a.vkey]).valid, false);
  assert.equal(verifyNote("", [a.vkey]).valid, false);
  assert.equal(verifyNote(null as never, [a.vkey]).valid, false);
});

test("checkpoint body: format and strict parse round-trip; non-canonical forms are refused", () => {
  const root = hashLeaf(Buffer.from("x"));
  const text = formatCheckpointBody({ origin: "a11oy.example/receipts", size: 7, rootHash: root });
  assert.equal(text, `a11oy.example/receipts\n7\n${root.toString("base64")}\n`);
  assert.deepEqual(parseCheckpointBody(text).rootHash, root);
  assert.throws(() => parseCheckpointBody(text.replace("\n7\n", "\n07\n")), /canonical ASCII decimal/);
  assert.throws(() => parseCheckpointBody(text.replace("\n7\n", "\n+7\n")), /canonical ASCII decimal/);
  assert.throws(() => parseCheckpointBody(text.replace(/=\n$/, "\n")), /canonical base64/);
  assert.throws(() => parseCheckpointBody("only\ntwo\n"), /three non-empty lines/);
  assert.throws(() => parseCheckpointBody("o\n1\n\n"), /three non-empty lines/);
});

const ORIGIN = "a11oy.example/receipts";
function head(leaves: Hash[], n: number) {
  return { size: n, rootHash: treeHash(leaves.slice(0, n)) };
}

test("verifyCheckpoint: signature, origin, rollback, split-view and append-only consistency", () => {
  const k = testKey(ORIGIN);
  const leaves = Array.from({ length: 9 }, (_, i) => hashLeaf(Buffer.from(`receipt-${i}`)));
  const note = (n: number) => signNote(formatCheckpointBody({ origin: ORIGIN, ...head(leaves, n) }), ORIGIN, k.priv, k.pubRaw);
  const opts = { origin: ORIGIN, keys: [k.vkey] };

  const ok5 = verifyCheckpoint(note(5), opts);
  assert.equal(ok5.valid, true, ok5.errors.join("; "));

  const ok9 = verifyCheckpoint(note(9), { ...opts, previous: head(leaves, 5), consistencyPath: consistencyProof(5, leaves) });
  assert.equal(ok9.valid, true, ok9.errors.join("; "));
  assert.equal(ok9.head?.size, 9);

  // missing / wrong consistency proof
  assert.equal(verifyCheckpoint(note(9), { ...opts, previous: head(leaves, 5) }).valid, false);
  assert.equal(verifyCheckpoint(note(9), { ...opts, previous: head(leaves, 5), consistencyPath: consistencyProof(6, leaves) }).valid, false);
  // rollback
  assert.match(verifyCheckpoint(note(5), { ...opts, previous: head(leaves, 9) }).errors.join(), /log shrank/);
  // same size, different root (split view)
  const fork = leaves.map((l, i) => (i === 2 ? hashLeaf(Buffer.from("forked")) : l));
  const forkNote = signNote(formatCheckpointBody({ origin: ORIGIN, size: 5, rootHash: treeHash(fork.slice(0, 5)) }), ORIGIN, k.priv, k.pubRaw);
  assert.match(verifyCheckpoint(forkNote, { ...opts, previous: head(leaves, 5) }).errors.join(), /split view/);
  // wrong origin / wrong key / not a checkpoint
  assert.equal(verifyCheckpoint(note(5), { ...opts, origin: "other.example/log" }).valid, false);
  assert.equal(verifyCheckpoint(note(5), { origin: ORIGIN, keys: [testKey(ORIGIN).vkey] }).valid, false);
  assert.equal(verifyCheckpoint(signNote("not a checkpoint\n", ORIGIN, k.priv, k.pubRaw), opts).valid, false);
});
