// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
//
// khipu-consensus (TypeScript reference) — Byzantine-fault-tolerant multi-party
// signed agreement. Each witness ("organ") signs an action hash with its own
// ECDSA-P256 key over the DSSE Pre-Authentication Encoding. >= threshold valid
// `allow` signatures over the same action hash ⇒ CANONICAL.
//
// Uses Node's built-in `crypto`. Verifies the same deterministic vectors as the
// Python and Go reference implementations.

import { createVerify, createSign, KeyObject, createPublicKey, createPrivateKey } from "node:crypto";

export const ORGAN_VERDICT_PAYLOAD_TYPE = "application/vnd.szl.khipu.organ-verdict+json";

/** Deterministic canonical JSON: sorted keys, compact separators, UTF-8. */
export function canonicalJson(obj: unknown): Buffer {
  return Buffer.from(canon(obj), "utf-8");
}

function canon(obj: unknown): string {
  if (obj === null || typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj)) return "[" + obj.map(canon).join(",") + "]";
  const keys = Object.keys(obj as Record<string, unknown>).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + canon((obj as any)[k])).join(",") + "}";
}

/** DSSE Pre-Authentication Encoding (DSSEv1). */
export function pae(payloadType: string, body: Buffer): Buffer {
  const t = Buffer.from(payloadType, "utf-8");
  return Buffer.concat([
    Buffer.from("DSSEv1 "), Buffer.from(String(t.length)), Buffer.from(" "), t,
    Buffer.from(" "), Buffer.from(String(body.length)), Buffer.from(" "), body,
  ]);
}

export interface OrganVerdict {
  organ: string;
  keyid: string;
  payloadType?: string;
  payload: string;     // base64 canonical signed statement
  signature: string;   // base64 ECDSA-P256-SHA256 over PAE
  verdict?: string;
  reason?: string;
}

export interface OrganCheck {
  organ: string | null;
  keyid: string | null;
  valid: boolean;
  verdict: string | null;
  actionHashMatch: boolean;
  counts: boolean;
  reason?: string;
}

export interface ConsensusResult {
  actionHash: string;
  threshold: number;
  n: number;
  consensusCount: number;
  decision: "canonical" | "rejected";
  khipuConsensus: string;
  checks: OrganCheck[];
}

/** Sign one organ verdict. ts must be supplied for deterministic output. */
export function signVerdict(
  organ: string, actionHash: string, verdict: string, privateKeyPem: string,
  reason = "", leanSha = "", ts = "",
): OrganVerdict {
  const keyid = `${organ}-cosign`;
  const statement = {
    schema: "szl.khipu.organ_verdict/v1", organ, keyid, action_hash: actionHash,
    verdict, reason, lean_sha: leanSha, ts: ts || new Date().toISOString(),
  };
  const body = canonicalJson(statement);
  const key: KeyObject = createPrivateKey(privateKeyPem);
  const signer = createSign("SHA256");
  signer.update(pae(ORGAN_VERDICT_PAYLOAD_TYPE, body));
  signer.end();
  const sig = signer.sign({ key, dsaEncoding: "der" });
  return {
    organ, keyid, payloadType: ORGAN_VERDICT_PAYLOAD_TYPE,
    payload: body.toString("base64"), signature: sig.toString("base64"),
    verdict, reason,
  };
}

/** Verify one organ's signature against its public key + action hash. */
export function verifyVerdict(v: OrganVerdict, publicKeyPem: string, actionHash: string): OrganCheck {
  const base: OrganCheck = {
    organ: v.organ, keyid: v.keyid, valid: false, verdict: null,
    actionHashMatch: false, counts: false,
  };
  if (!v.payload || !v.signature) return { ...base, reason: "missing payload/signature" };
  try {
    const body = Buffer.from(v.payload, "base64");
    const toVerify = pae(v.payloadType ?? ORGAN_VERDICT_PAYLOAD_TYPE, body);
    const pub: KeyObject = createPublicKey(publicKeyPem);
    const verifier = createVerify("SHA256");
    verifier.update(toVerify);
    verifier.end();
    const ok = verifier.verify({ key: pub, dsaEncoding: "der" }, Buffer.from(v.signature, "base64"));
    if (!ok) return { ...base, reason: "signature mismatch" };
    const decoded = JSON.parse(body.toString("utf-8"));
    const ahMatch = decoded.action_hash === actionHash;
    const verdict = decoded.verdict;
    return {
      organ: v.organ, keyid: v.keyid, valid: true, verdict,
      actionHashMatch: ahMatch, counts: ahMatch && verdict === "allow",
    };
  } catch (e) {
    return { ...base, reason: String(e) };
  }
}

/** Tally consensus. `verdicts` entries may be null (abstain/timeout). */
export function tally(
  actionHash: string, verdicts: (OrganVerdict | null)[],
  pubkeys: Record<string, string>, threshold = 3, n = 4,
): ConsensusResult {
  const checks: OrganCheck[] = [];
  let count = 0;
  for (const v of verdicts) {
    if (v === null) {
      checks.push({ organ: null, keyid: null, valid: false, verdict: null, actionHashMatch: false, counts: false, reason: "abstain/timeout" });
      continue;
    }
    const pem = pubkeys[v.organ];
    if (!pem) {
      checks.push({ organ: v.organ, keyid: v.keyid, valid: false, verdict: null, actionHashMatch: false, counts: false, reason: "no public key" });
      continue;
    }
    const chk = verifyVerdict(v, pem, actionHash);
    checks.push(chk);
    if (chk.counts) count++;
  }
  const decision = count >= threshold ? "canonical" : "rejected";
  return { actionHash, threshold, n, consensusCount: count, decision, khipuConsensus: `${count}-of-${n}`, checks };
}
