# SZL Ouroboros Mesh Ring — Specification v0.1

Status: PROPOSED (owner-reviewed pick). Additive spec: no runtime code changed by this PR.
Owner directive (2026-11-17): the Salad supercomputer fleet meshes and talks, an ORO (ouroboros) loop and invariants run through it, using Second Brain and Living Anatomy, all owner datasets, and the best models as teachers.

## 1. Measured foundations (no unmeasured claims)

- The full ring fired once, end-to-end, on 2026-11-16: Salad train (final_loss 0.4051, RTX A5000, 1084.2s) → receipt → private HF adapter repo → Workers AI finetune `21892cd9-b4ca-4032-8058-280835c0402a` → serve via `szl-router` AI Gateway → live 200 behind the x402 wall (a11oy PR #3508, squash d472914f, deploy run 43862298823).
- Estate census 2026-11-17 (laptop HfApi): 128 datasets, 219 models in SZLHOLDINGS.
- Gateway analytics measured 2026-11-16: 20 invocations — mistral-lora ×7, glm-5.3 ×7, deepseek ×6 through `szl-router`.
- Lean fleet-topology invariants exist: `Lutar/Innovations/round7/CalugareanuFleetInvariant.lean` (Lk = Tw + Wr), KeplerFleetScale, EulerFleetTopology.
- Serving mesh exists: v4 fleet panel, 5 flagship HF Spaces with peer healthz and non-blocking peer I/O (test_fleet_event_loop.py).
- Receipt chain pattern exists: sha256-canonical-json-chain (`prev_hash` → `chain_tip`).

## 2. Mesh topology: broker fabric, not peer-to-peer

Salad containers are outbound-only (measured: no inbound connectivity). The mesh is therefore three broker planes:

- **Data plane** — HF Hub mailboxes. `SZLHOLDINGS/frontier-54-runs` (mesh/lanelogs, receipts, evals) is the mesh bus. Curriculum corpora and adapter repos live in the same org. `SZLHOLDINGS/mesh-liveness` is reserved for ring liveness pings.
- **Control plane** — Cloudflare: AI Gateway (`szl-router`) for serving and teacher access, Durable Objects/Queues for coordination, AE SQL for telemetry.
- **Cadence plane** — GitHub Actions: scheduled census, gate runs, promotion checks, countersign workflows.

## 3. Ring stations (one lap = one ring receipt)

CURATE → TRAIN → MEASURE → PUBLISH → SERVE → LEARN → (feeds CURATE: the ring closes on its own tail — ouroboros).

| Station | What happens | Measured precedent |
|---|---|---|
| CURATE | curriculum fused from owner corpora (Second Brain, Living Anatomy, doctrine, verticals); synthesis cycles by teacher models, owner-gated | ring-curriculum-v1 = anatomy-brain-datasets-corpus-v1 (89 rows) + brain-synthesized-corpus cycle-1 (67 rows), concatenation only, manifest in dataset repo |
| TRAIN | Salad GPU groups, workers fetch `salad_worker.py`, heartbeats to mesh/lanelogs | v2c fleet pattern; lap-1: `szl-ring-v1`, Qwen3-1.7B, 200 steps |
| MEASURE | receipt + 5-criteria bench/heldout on gate-1 GPU; diff-eval base vs adapter | x402-v2 diff-eval verdict ok, 2026-11-16 |
| PUBLISH | private HF adapter repo + honest model card | 208/208 zoo carded |
| SERVE | Workers AI finetune → `szl-router` gateway → x402 wall | finetune 21892cd9, live 200, request_id 5e0a9503 |
| LEARN | gateway analytics + revenue watch + eval deltas feed the next curriculum lap | gateway logs readback; x402 watcher v2 |

## 4. Loop-carried invariants (fail-closed, every lap)

1. Fail-closed everywhere; MEASURED receipts only; absence of evidence never promotes (ouroboros_passport 9-term predicate; countersign owner-gates at promotion).
2. Ring integrity = receipt chain: every lap extends the sha256-canonical-json-chain; broken chain = ring does not close.
3. Honest gates: eval status stated honestly (NOT_RUN allowed), energy MEASURED where claimed, cost ceiling per lap.
4. Stop-group-after-receipt: GPU groups stop the moment the adapter receipt lands (idle-burn lesson 2026-11-16).
5. Topology invariant: mesh events change fleet state in integer steps (Calugareanu Lk = Tw + Wr, Lean-checked).

## 5. Ring receipt

`mesh/ring_receipt_schema.json` — `ring-receipt-v1`. A ring only closes (`closed: true`) when all six stations carry MEASURED evidence and all gates PASS.

## 6. Curriculum registry

`mesh/curriculum_registry.json` — all 128 owner datasets indexed with roles (keyword-heuristic-v1, honest: owner review pending): curriculum ×64, evidence-telemetry ×21, govern-state ×7, eval-bench ×3, unmapped-quarantine ×33. Quarantined datasets are NOT used for training until owner-promoted.

## 7. Teachers: the best models in the world

Teachers reach students through `szl-router` (measured: glm-5.3, deepseek, mistral invocations). Distillation precedent: governed-distill / szl-distill corpora. Synthesis cycles (brain-synthesized-corpus cycle-1 pattern) generate new curriculum candidates; promotion is owner-gated.

## 8. Astra slot (owner-gated, fail-closed absent)

Measured census (2026-11-17) found NO estate asset named Astra. If Astra means an external vector-memory service, it requires owner-provided credentials; this spec leaves a slot in the LEARN station for an external vector-memory plane and stays fail-closed (no credentials minted, none requested in-band).

## 9. Honest constraints

Finite Salad credit; no money-in; no P2P on Salad; parallel-lane territory respected (oro envelope, frontier loop, x402 lanes untouched); single-page API reads (25s CDP limits) for dash-plane evidence.

## 10. Lap 1 status at PR time

IN FLIGHT: `szl-ring-v1` started 2026-11-17 (Qwen3-1.7B, ring-curriculum-v1, 200 steps, adapter → SZLHOLDINGS/salad-ring-v1, stop-on-receipt watcher armed). No completion is claimed in this spec.

— Vibe CTO lane, SZL Holdings estate, 2026-11-17.