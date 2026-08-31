import { describe, expect, it } from 'vitest';
import { detect, type DetectorAdapter } from '../pipeline.js';

/**
 * Privacy invariant: the perception envelope is the only thing that
 * leaves the device-local in-memory pipeline. Raw frame bytes (the
 * adapter-opaque `Frame.payload`) must NEVER appear in the serialised
 * envelope — not under `consumerArtifact`, not under per-head
 * detections, not under liveness reasons.
 *
 * Re-expressed from the privacy contract in
 * docs/research/perception-bio-synthesis-2026.md §1 and reinforced by
 * the api-server `/perception/verify` rule that the server only ever
 * accepts feature vectors, never frames.
 */

const SECRET_FRAME_BYTES = new Uint8Array(64);
for (let i = 0; i < SECRET_FRAME_BYTES.length; i++) {
  SECRET_FRAME_BYTES[i] = 0xab; // distinctive byte so a search hit is unambiguous
}
const SECRET_TAG = 'super-secret-frame-payload-do-not-leak-2026';

describe('perception-loop privacy invariant', () => {
  it('never serialises raw frame bytes or payload tokens into the envelope', async () => {
    const frame = {
      frameHash: 'test-frame-hash',
      tMs: 0,
      // Payload carries both binary bytes and a unique searchable tag;
      // either appearing in the envelope JSON is a privacy regression.
      payload: { bytes: SECRET_FRAME_BYTES, tag: SECRET_TAG },
    };
    const adapter: DetectorAdapter = {
      head: 'face',
      costMs: 1,
      detect: async () => [
        {
          score: 0.9,
          box: [0.1, 0.1, 0.2, 0.2],
          modelVersion: 'mock@0',
        },
      ],
      livenessSignal: (f) => ({ tMs: f.tMs, irisMotion: 0.02, eyeAperture: 0.9, headPoseDelta: 0.0 }),
    };

    const envelope = await detect(frame, [adapter], {
      budgetMs: 100,
      consumerArtifact: 'a11oy-approvals-center',
    });

    const serialised = JSON.stringify(envelope);
    expect(serialised).not.toContain(SECRET_TAG);
    // 0xab repeated → if bytes leaked through any toJSON pathway they would
    // appear as a long run of `171` decimal integers.
    expect(serialised.includes('171,171,171,171,171')).toBe(false);
    expect(serialised).not.toMatch(/payload/i);

    // The feature-vector summary is what's allowed to leave the device.
    expect(envelope.frameHash).toBe('test-frame-hash');
    expect(envelope.liveness).toBeDefined();
    expect(envelope.detectionsSummary.counts.face).toBe(1);
  });
});
