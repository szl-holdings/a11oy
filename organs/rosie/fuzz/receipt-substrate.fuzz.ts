/**
 * receipt-substrate.fuzz.ts — property-based fuzz tests for rosie's
 * TypeScript receipt-substrate tier.
 *
 * These replace the previous always-pass `fuzz.yml` stub with real
 * fast-check properties exercised against the code that actually exists
 * in this repo:
 *
 *   • src/axis-value-option.ts   — canonical AxisValue serialize/parse
 *   • src/horus-eye-weights.ts   — 6-bit dyadic weight encode/decode
 *   • src/khipu-receipt.ts       — receipt-DAG hash linkage + sum invariant
 *                                  + dual-attestation structural verify
 *   • src/qec/qec_lineage.ts     — Shor [[9,1,3]] majority decode
 *   • src/qec/css_ingress.ts     — CSS cosignature consistency
 *
 * Properties grouped to mirror the four classes requested in the brief:
 *   1. canonical encode/decode roundtrip:   decode(encode(x)) === x
 *   2. attestation verify roundtrip:        verify(valid)  === ok
 *   3. receipt chain / hash linkage:        invariant holds for any sequence
 *   4. mutation detection:                  any single tamper makes verify fail
 *
 * NOTE ON DSSE/Ed25519: rosie's repo does not contain a TypeScript
 * Ed25519/DSSE sign-verify implementation — that cryptographic surface
 * lives in the Python console tier / MCP receipts server, not here. We do
 * NOT fake a crypto roundtrip. Instead we fuzz the attestation and
 * hash-linkage invariants that the TS substrate genuinely implements, plus
 * the tamper-detection property (single mutation breaks verification) that
 * is the real bug class a signed-payload check is meant to catch.
 *
 * Run: npm run test:fuzz
 */

import { describe, it } from 'vitest';
import fc from 'fast-check';

import {
  serializeAxis,
  parseAxis,
  axisEqual,
  measuredAxis,
  AXIS_ABSENT,
  type AxisValue,
} from '../src/axis-value-option.ts';

import {
  encodeHorusEye,
  decodeHorusEye,
  HORUS_EYE_DENOMINATOR,
  HORUS_EYE_MAX_NUMERATOR,
} from '../src/horus-eye-weights.ts';

import {
  buildDecision,
  buildOrgan,
  buildRoot,
  verifySumInvariant,
  verifyDualAttestation,
  knotInvariantTag,
  type DecisionReceipt,
  type OrganReceipt,
  type KhipuRootReceipt,
} from '../src/khipu-receipt.ts';

import {
  shorEncode,
  shorMajorityPayload,
} from '../src/qec/qec_lineage.ts';

import { wrapIngress, verifyIngress } from '../src/qec/css_ingress.ts';

// Fixed seed so any counterexample is reproducible in CI.
const RUNS = { numRuns: 1000, seed: 0x5a4c20 } as const;

// --------------------------------------------------------------------------
// Arbitraries
// --------------------------------------------------------------------------

// AxisValue: either absent, or measured with a finite numeric value.
// measuredAxis rejects non-finite, so the arbitrary only emits finite doubles.
const axisArb: fc.Arbitrary<AxisValue> = fc.oneof(
  fc.constant(AXIS_ABSENT),
  fc
    .double({ noNaN: true, noDefaultInfinity: true })
    .map((v) => measuredAxis(v)),
);

// Horus-Eye codes are integers in [0, 63].
const horusCodeArb = fc.integer({ min: 0, max: HORUS_EYE_MAX_NUMERATOR });

// A single decision: non-negative integer value + arbitrary id.
const decisionArb: fc.Arbitrary<DecisionReceipt> = fc
  .tuple(fc.string(), fc.nat({ max: 1_000_000 }))
  .map(([id, v]) => buildDecision(id, v));

// An organ holds 0..6 decisions.
const organArb: fc.Arbitrary<OrganReceipt> = fc
  .tuple(fc.string(), fc.array(decisionArb, { maxLength: 6 }))
  .map(([id, ds]) => buildOrgan(id, ds));

// A root holds 0..5 organs.
const rootArb: fc.Arbitrary<KhipuRootReceipt> = fc
  .tuple(fc.string(), fc.array(organArb, { maxLength: 5 }))
  .map(([id, organs]) => buildRoot(id, organs));

// --------------------------------------------------------------------------
// 1. Canonical encode/decode roundtrip
// --------------------------------------------------------------------------

describe('canonical encode/decode roundtrip', () => {
  it('parseAxis(serializeAxis(x)) equals x for any AxisValue', () => {
    fc.assert(
      fc.property(axisArb, (x) => {
        const round = parseAxis(serializeAxis(x));
        if (!axisEqual(round, x)) {
          throw new Error(
            `roundtrip mismatch: in=${JSON.stringify(x)} ` +
              `serialized=${serializeAxis(x)} out=${JSON.stringify(round)}`,
          );
        }
      }),
      RUNS,
    );
  });

  it('absent and measured(0) are NOT confused (Brahmi distinction)', () => {
    // This is the load-bearing semantic the module exists to guarantee.
    fc.assert(
      fc.property(fc.constant(0), () => {
        const a = serializeAxis(AXIS_ABSENT);
        const z = serializeAxis(measuredAxis(0));
        if (a === z) {
          throw new Error(`absent and measured(0) serialized identically: ${a}`);
        }
      }),
      RUNS,
    );
  });

  it('decodeHorusEye(encodeHorusEye(n/64)) === n/64 for every 6-bit code', () => {
    fc.assert(
      fc.property(horusCodeArb, (n) => {
        const weight = n / HORUS_EYE_DENOMINATOR;
        const code = encodeHorusEye(weight);
        const decoded = decodeHorusEye(code);
        if (code !== n) {
          throw new Error(`encode(${weight}) = ${code}, expected ${n}`);
        }
        if (decoded !== weight) {
          throw new Error(`decode(${code}) = ${decoded}, expected ${weight}`);
        }
      }),
      RUNS,
    );
  });
});

// --------------------------------------------------------------------------
// 2. Attestation verify roundtrip
// --------------------------------------------------------------------------

describe('dual-attestation verify roundtrip', () => {
  it('a structurally valid dual-attestation always verifies ok', () => {
    fc.assert(
      fc.property(
        rootArb,
        fc.string({ minLength: 1 }),
        fc.string({ minLength: 1 }),
        fc.string({ minLength: 1 }),
        fc.string({ minLength: 1 }),
        (root, sA, sB, sigA, sigB) => {
          // Force distinct, non-empty signer principals.
          const signerA = `A:${sA}`;
          const signerB = `B:${sB}`;
          const attested: KhipuRootReceipt = {
            ...root,
            dualAttestation: {
              signerA,
              signerB,
              signatureA: sigA,
              signatureB: sigB,
              attestedAt: new Date(0).toISOString(),
            },
          };
          const res = verifyDualAttestation(attested);
          if (!res.ok) {
            throw new Error(
              `valid attestation rejected: ${(res as { reason: string }).reason}`,
            );
          }
        },
      ),
      RUNS,
    );
  });

  it('same-signer attestation is always rejected', () => {
    fc.assert(
      fc.property(rootArb, fc.string({ minLength: 1 }), (root, s) => {
        const attested: KhipuRootReceipt = {
          ...root,
          dualAttestation: {
            signerA: s,
            signerB: s, // identical → must fail
            signatureA: 'x',
            signatureB: 'y',
            attestedAt: new Date(0).toISOString(),
          },
        };
        const res = verifyDualAttestation(attested);
        if (res.ok) {
          throw new Error(`same-signer attestation accepted for signer="${s}"`);
        }
      }),
      RUNS,
    );
  });
});

// --------------------------------------------------------------------------
// 3. Receipt chain / hash linkage invariant
// --------------------------------------------------------------------------

describe('receipt chain hash linkage + sum invariant', () => {
  it('verifySumInvariant holds for any freshly-built root', () => {
    fc.assert(
      fc.property(rootArb, (root) => {
        const res = verifySumInvariant(root);
        if (!res.ok) {
          throw new Error(
            `built root failed sum invariant: ${(res as { reason: string }).reason}`,
          );
        }
      }),
      RUNS,
    );
  });

  it('rootHash is a deterministic function of the receipt contents', () => {
    // Re-building the same root from the same inputs yields the same hash
    // (hash linkage stability — the prev_hash analogue for this DAG).
    fc.assert(
      fc.property(
        fc.string(),
        fc.array(
          fc.tuple(fc.string(), fc.array(decisionArb, { maxLength: 4 })),
          { maxLength: 4 },
        ),
        (rid, organSpecs) => {
          const build = () =>
            buildRoot(
              rid,
              organSpecs.map(([oid, ds]) => buildOrgan(oid, ds)),
            );
          const a = build();
          const b = build();
          if (a.rootHash !== b.rootHash) {
            throw new Error(
              `non-deterministic rootHash: ${a.rootHash} vs ${b.rootHash}`,
            );
          }
          if (knotInvariantTag(a) !== knotInvariantTag(b)) {
            throw new Error('non-deterministic knotInvariantTag');
          }
        },
      ),
      RUNS,
    );
  });
});

// --------------------------------------------------------------------------
// 4. Mutation detection
// --------------------------------------------------------------------------

describe('mutation detection', () => {
  it('tampering a stored pendantValue breaks the sum invariant', () => {
    fc.assert(
      fc.property(
        // Need at least one organ with at least one decision so a tamper
        // actually changes a checked sum.
        fc
          .tuple(
            fc.string(),
            fc.array(
              fc.tuple(
                fc.string(),
                fc.array(decisionArb, { minLength: 1, maxLength: 4 }),
              ),
              { minLength: 1, maxLength: 4 },
            ),
            fc.nat(),
            fc.integer({ min: 1, max: 1000 }),
          )
          .map(([rid, specs, organPick, delta]) => {
            const organs = specs.map(([oid, ds]) => buildOrgan(oid, ds));
            const root = buildRoot(rid, organs);
            const idx = organPick % root.organs.length;
            // Flip one stored pendantValue by a non-zero delta.
            const tamperedOrgans = root.organs.map((o, i) =>
              i === idx ? { ...o, pendantValue: o.pendantValue + delta } : o,
            );
            const tampered: KhipuRootReceipt = {
              ...root,
              organs: tamperedOrgans,
            };
            return tampered;
          }),
        (tampered) => {
          const res = verifySumInvariant(tampered);
          if (res.ok) {
            throw new Error(
              'tampered pendantValue passed the sum invariant (undetected mutation)',
            );
          }
        },
      ),
      RUNS,
    );
  });

  it('any single-byte difference in CSS ingress payload is detectable', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 255 }),
        fc.integer({ min: 1, max: 255 }),
        (payload, xorMask) => {
          const flipped = (payload ^ xorMask) & 0xff; // guaranteed != payload
          const r = wrapIngress(payload);
          // Tamper: keep the original stabilizer but swap in a different
          // payload digest. verifyIngress must reject because the X-parity
          // no longer reproduces the payload.
          const tampered = { ...r, payloadDigest: flipped };
          if (verifyIngress(tampered)) {
            throw new Error(
              `tampered ingress (payload ${payload}->${flipped}) verified ok`,
            );
          }
          // Control: the untampered receipt must verify.
          if (!verifyIngress(r)) {
            throw new Error(`honest ingress for payload ${payload} failed verify`);
          }
        },
      ),
      RUNS,
    );
  });

  it('Shor [[9,1,3]] majority decode corrects up to 4 corrupted replicas', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 255 }),
        fc.integer({ min: 0, max: 255 }),
        fc.integer({ min: 0, max: 4 }),
        (payload, corruptByte, nCorrupt) => {
          const logical = { payload, lineage: 0 };
          // Worst case for majority decode: drive ALL corrupted replicas to
          // ONE shared wrong value, maximising the adversarial plurality.
          // ensure the wrong value differs from the honest payload.
          const wrong = corruptByte === payload ? (payload + 1) & 0xff : corruptByte;
          const bundle = shorEncode(logical).map((r, i) =>
            i < nCorrupt ? { ...r, payload: wrong } : r,
          );
          // With <= 4 of 9 replicas corrupted, the honest payload (>=5 copies)
          // still holds the strict plurality, so majority decode recovers it.
          const decoded = shorMajorityPayload(bundle);
          if (decoded !== payload) {
            throw new Error(
              `majority decode failed: payload=${payload} corrupt=${nCorrupt} ` +
                `decoded=${decoded}`,
            );
          }
        },
      ),
      RUNS,
    );
  });
});
