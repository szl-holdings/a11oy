/**
 * @file packages/api/src/lib/receipt-substrate.ts
 * @description Wraps @szl-holdings/a11oy-receipt-substrate for emitting and
 * verifying DSSE receipts.
 *
 * Chicken-and-egg: @szl-holdings/a11oy-receipt-substrate is not published yet
 * (same problem the widget agent hits). We use `import type` only for
 * compile-time shapes, re-exported from ../types, and inject the runtime
 * emitter/signer from index.ts via dependency injection so the real substrate
 * can be wired in once published — without forcing this package to depend on an
 * unpublished artifact.
 *
 * Signing follows the Ed25519 software-key pattern from szl-uds-deployment#19
 * (the merged-conceptually receipts service): the private key is loaded at
 * RUNTIME from a PEM at SZL_ED25519_KEY_PATH. No key material is committed. If
 * no key is present the emitter runs in honest unsigned/degraded mode (it still
 * chains receipts) rather than fabricating a signature. See PhD Crypto verdict
 * findings A2 (asymmetric, not HMAC) and I (runtime key custody).
 */

import { createPrivateKey, createPublicKey, sign as nodeSign, verify as nodeVerify, createHash, type KeyObject } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { canonicalJson } from './canonical-json.ts';
import { dsseV1Pae, base64ToBytes } from './dsse-pae.ts';
import type { Receipt, ChainPointer, Verdict } from '../types/index.ts';

export const RECEIPT_PAYLOAD_TYPE = 'application/vnd.szl.receipt.v1+json' as const;
export const CHAIN_GENESIS = 'GENESIS' as const;

/** A runtime signer: takes PAE bytes, returns a base64url Ed25519 signature. */
export interface ReceiptSigner {
  readonly keyid: string;
  readonly alg: 'ed25519';
  /** Sign PAE bytes. Returns null in degraded/unsigned mode. */
  sign(pae: Uint8Array): string | null;
  /** Public key for verification, if available. */
  publicKey(): KeyObject | null;
}

/** The injected dependency surface — the real substrate satisfies this. */
export interface ReceiptSubstrate {
  /** Emit a receipt for an arbitrary body, chained on the prior head. */
  emit(body: unknown, prevHash: string | null, index: number): Receipt;
  /** Verify a receipt's DSSE signature and chain pointer self-consistency. */
  verify(receipt: Receipt): Verdict;
}

function b64url(b: Uint8Array): string {
  return Buffer.from(b).toString('base64url');
}

/**
 * Load an Ed25519 signer from a PEM at the given path. Returns a degraded
 * (unsigned) signer if the path is empty/absent — never a fake signature.
 */
export function loadEd25519Signer(keyPath: string | undefined, keyid: string): ReceiptSigner {
  let priv: KeyObject | null = null;
  let pub: KeyObject | null = null;
  if (keyPath) {
    try {
      const pem = readFileSync(keyPath, 'utf8');
      priv = createPrivateKey(pem);
      pub = createPublicKey(priv);
    } catch {
      priv = null;
      pub = null;
    }
  }
  return {
    keyid,
    alg: 'ed25519',
    sign(pae: Uint8Array): string | null {
      if (!priv) return null;
      // Ed25519: pass null algorithm; the curve fixes the hash.
      return b64url(new Uint8Array(nodeSign(null, Buffer.from(pae), priv)));
    },
    publicKey(): KeyObject | null {
      return pub;
    },
  };
}

/** SHA-256 hex of a UTF-8 string — the chain-link primitive. */
export function sha256Hex(s: string): string {
  return createHash('sha256').update(s, 'utf8').digest('hex');
}

/**
 * Build the in-memory substrate backed by an injected signer. This is what
 * index.ts wires; tests inject a deterministic test signer.
 */
export function createSubstrate(signer: ReceiptSigner): ReceiptSubstrate {
  return {
    emit(body: unknown, prevHash: string | null, index: number): Receipt {
      const canonical = canonicalJson(body);
      const payloadBytes = new TextEncoder().encode(canonical);
      const payloadB64 = Buffer.from(payloadBytes).toString('base64');
      const pae = dsseV1Pae(RECEIPT_PAYLOAD_TYPE, payloadBytes);
      const sig = signer.sign(pae);
      const chain: ChainPointer = {
        prev_hash: prevHash ?? CHAIN_GENESIS,
        index,
        ts: new Date().toISOString(),
      };
      return {
        payload: payloadB64,
        payloadType: RECEIPT_PAYLOAD_TYPE,
        signatures: sig
          ? [{ keyid: signer.keyid, sig, alg: signer.alg }]
          : [{ keyid: signer.keyid, sig: 'UNSIGNED-DEGRADED-NO-KEY', alg: signer.alg }],
        chain,
      };
    },

    verify(receipt: Receipt): Verdict {
      const errors: string[] = [];
      if (!receipt || typeof receipt !== 'object') {
        return { verified: false, errors: ['receipt is not an object'] };
      }
      if (receipt.payloadType !== RECEIPT_PAYLOAD_TYPE) {
        errors.push(`unexpected payloadType: ${String(receipt.payloadType)}`);
      }
      if (!Array.isArray(receipt.signatures) || receipt.signatures.length === 0) {
        errors.push('no signatures present');
      }
      if (!receipt.chain || typeof receipt.chain.index !== 'number') {
        errors.push('chain pointer missing or malformed');
      }
      const pub = signer.publicKey();
      const first = receipt.signatures?.[0];
      if (first && first.sig && first.sig !== 'UNSIGNED-DEGRADED-NO-KEY') {
        if (!pub) {
          errors.push('no public key available to verify signature');
        } else {
          try {
            const payloadBytes = base64ToBytes(receipt.payload);
            const pae = dsseV1Pae(receipt.payloadType, payloadBytes);
            const ok = nodeVerify(null, Buffer.from(pae), pub, Buffer.from(base64ToBytes(first.sig)));
            if (!ok) errors.push('Ed25519 signature does not verify over canonical PAE');
          } catch (e) {
            errors.push(`signature verification threw: ${(e as Error).message}`);
          }
        }
      } else if (first && first.sig === 'UNSIGNED-DEGRADED-NO-KEY') {
        errors.push('receipt is unsigned (degraded mode)');
      }
      return { verified: errors.length === 0, errors };
    },
  };
}
