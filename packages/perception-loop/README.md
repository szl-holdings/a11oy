# @szl-holdings/perception-loop

Operator-loop perception envelope — typed wrapper around browser-native
multi-head perception (face / body / hand / iris / gesture / liveness)
with a single `PerceptionEnvelope` shape.

This is the sibling of `seeing-eye` (agent vision):
- **`seeing-eye`** → *what the agent sees* (image grounding for inference).
- **`perception-loop`** → *who is at the keyboard / in the scene*
  (operator presence, reviewer liveness, drone-side scene actors).

Both can emit receipts in the same session without conflict.

## Worked example

```ts
import { detect, type DetectorAdapter } from '@szl-holdings/perception-loop';

const faceAdapter: DetectorAdapter = {
  head: 'face',
  costMs: 8,
  async detect(frame) { return runFaceModel(frame.payload); },
  livenessSignal(frame) { return extractGazeSignal(frame); },
};

const envelope = await detect(
  { frameHash: hashFrame(frame), tMs: performance.now(), payload: frame },
  [faceAdapter, /* bodyAdapter, handAdapter, ... */],
  { budgetMs: 33, consumerArtifact: 'a11oy' }, // 30fps budget
);

if (envelope.liveness.livenessConfidence >= 0.66) {
  // emit `perception.envelope.v1` receipt and let the gate proceed.
}
```

## Receipt contract

The envelope is the source-of-truth for `perception.envelope.v1`
(Doctrine V6, Evidence-First + Policy-Aware). Mandatory fields:
`frameHash`, `ranHeads`, `skippedHeads`, `liveness.livenessConfidence`,
`detectionsSummary`, `budgetMs`, `consumerArtifact`.

## Source provenance

Architecture and envelope shape re-expressed (not copied) from
`github.com/standardgalactic/human` (Human.js — MIT). Models, weights,
and DOM glue are explicitly **not** in this package — they ship in
adapters per artifact.

## Consumers

| Artifact          | Use                                              |
|-------------------|--------------------------------------------------|
| A11oy             | Reviewer-presence gate on high-autonomy approvals |
| Sentra            | Operator-loop anomaly during incident response   |
| ROSIE Mobile      | Drone-POV scene-actor envelopes for evidence ledger |
| ROSIE             | Decision Theater operator presence telemetry     |

See [`docs/research/perception-bio-synthesis-2026.md`](../../docs/research/perception-bio-synthesis-2026.md) §1.

## Gotchas

- **WebGPU adapters require `crossOriginIsolated`.** A page that ships
  `perception-loop` over a WebGPU adapter must serve COOP/COEP headers
  or the adapter silently falls back to WebGL/CPU. Adapter
  implementations should fail loud rather than silently downgrade —
  silent fallbacks defeat the per-head receipt audit.
