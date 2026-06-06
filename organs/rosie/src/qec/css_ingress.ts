/**
 * css_ingress.ts — CSS classical-to-stabilizer bridge for Rosie ingress.
 *
 * Maps Calderbank-Shor-Steane (1996, DOI 10.1103/PhysRevA.54.1098) to
 * receipt ingress:
 *   • Classical 8-bit codeword = single-byte payload digest.
 *   • (X-parity, Z-parity) = cosignature pair binding.
 *
 * Innovation: CSS was a quantum-error-correcting code construction;
 * here we use it as a classical-to-cosigned receipt structure.
 */

import {
  classicalToCSS,
  cssConsistent,
  hammingDistByte,
  type StabilizerPair,
} from './qec_lineage.ts';

export interface IngressReceipt {
  readonly payloadDigest: number; // UInt8
  readonly stabilizer: StabilizerPair;
}

/** Wrap a classical payload digest into a CSS-style ingress receipt. */
export function wrapIngress(payloadDigest: number): IngressReceipt {
  return {
    payloadDigest: payloadDigest & 0xff,
    stabilizer: classicalToCSS(payloadDigest & 0xff),
  };
}

/** Verify an ingress receipt: CSS pair must be consistent AND
 *  payload digest must reproduce the X-parity. */
export function verifyIngress(r: IngressReceipt): boolean {
  return cssConsistent(r.stabilizer) && r.stabilizer.xParity === r.payloadDigest;
}

/** Hamming distance between two ingress receipts at the payload digest
 *  level — useful for batch drift detection across ingress streams. */
export function ingressDist(a: IngressReceipt, b: IngressReceipt): number {
  return hammingDistByte(a.payloadDigest, b.payloadDigest);
}

export { classicalToCSS, cssConsistent };
export type { StabilizerPair };
