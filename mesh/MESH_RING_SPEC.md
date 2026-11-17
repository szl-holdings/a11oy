# SZL Ouroboros Mesh Ring — Specification v0.2

Status: AMENDMENT (v0.2, additive; v0.1 merged as squash 47bb9a6b, PR #3631). No runtime code changed by this PR.
Owner directive (2026-11-17): the Salad supercomputer fleet meshes and talks, an ORO (ouroboros) loop and invariants run through it, using Second Brain and Living Anatomy, all owner datasets, and the best models as teachers.
Owner amendment directive (2026-11-17, later): doctrine and principles are baked in as a loop-carried invariant, not an optional flavor.

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
| CURATE | curriculum fused from owner corpora (Second Brain, Living Anatomy, **doctrine + invariants (required slice, v0.2 §4.6)**, verticals); synthesis cycles by teacher models, owner-gated | ring-curriculum-v1 = anatomy-brain-datasets-corpus-v1 (89 rows) + brain-synthesized-corpus cycle-1 (67 rows), concatenation only, manifest in dataset repo |
| TRAIN | Salad GPU groups, workers fetch `salad_worker.py`, heartbeats to mesh/lanelogs | v2c fleet pattern; lap-1: `szl-ring-v1b`, Qwen3-1.7B, 200 steps |
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
6. **Doctrine presence (v0.2, owner amendment 2026-11-17): every lap's curriculum MUST include the estate doctrine and invariants slices (e.g. doctrine-corpus-v2, lean-invariants-sft-v1, szl-1-doctrine-sft) alongside domain corpora; every ring receipt carries a `doctrine_presence` gate. A lap whose curriculum carries no doctrine slice records `doctrine_presence: FAIL` honestly and CANNOT close the ring (`closed: true` is unreachable). Doctrine is a loop-carried invariant, not an optional flavor: the ring that trains students also trains them in how the estate governs itself.**

## 5. Ring receipt

`mesh/ring_receipt_schema.json` — `ring-receipt-v1`. A ring only closes (`closed: true`) when all six stations carry MEASURED evidence and all gates PASS. Gates are a free-form list; `doctrine_presence` (§4.6) is a required gate name from lap 2 onward. Absence of evidence never closes a ring.

## 6. Curriculum registry

`mesh/curriculum_registry.json` — all 128 owner datasets indexed with roles (keyword-heuristic-v1, honest: owner review pending): curriculum ×64, evidence-telemetry ×21, govern-state ×7, eval-bench ×3, unmapped-quarantine ×33. Quarantined datasets are NOT used for training until owner-promoted. From v0.2 the registry carries `lap_assignments` (lap_1 honest TRAINED status; lap_2 = ring-curriculum-v2, doctrine-baked).

## 7. Teachers: the best models in the world

Teachers reach students through `szl-router` (measured: glm-5.3, deepseek, mistral invocations). Distillation precedent: governed-distill / szl-distill corpora. Synthesis cycles (brain-synthesized-corpus cycle-1 pattern) generate new curriculum candidates; promotion is owner-gated.

## 8. Astra slot (owner-gated, fail-closed absent)

Measured census (2026-11-17) found NO estate asset named Astra. If Astra means an external vector-memory service, it requires owner-provided credentials; this spec leaves a slot in the LEARN station for an external vector-memory plane and stays fail-closed (no credentials minted, none requested in-band).

## 9. Honest constraints

Finite Salad credit; no money-in; no P2P on Salad; parallel-lane territory respected (oro envelope, frontier loop, x402 lanes untouched); single-page API reads (25s CDP limits) for dash-plane evidence.

## 10. Lap status at v0.2 PR time (honest, MEASURED only)

- **Lap 1** (ring-curriculum-v1, Qwen3-1.7B): first attempt `szl-ring-v1` crashed fail-closed at CUDA precheck (root cause: v2c boot sed bug corrupting worker precheck; fleet-wide latent issue flagged to owning lanes). Retry `szl-ring-v1b` TRAINED: 200/200 steps in 422.6s, train_loss 1.6121, final-epoch loss 0.5342, mean_token_accuracy 0.8934, RTX 5090, energy MEASURED (zeus window 35,779.2 J; nvml delta 35,892.2 J). Adapter published to SZLHOLDINGS/salad-ring-v1b (checkpoint ladder 25→200 + final/). Genesis ring receipt uploaded: mesh/ring/ring-v1-lap-1-receipt.json, chain_tip 3538d48af4efcd23bfe43ab25c43a6c20d5db0c49abaf828b5871880454f9cbc, closed=false (MEASURE/SERVE/LEARN NOT_RUN; doctrine_presence FAIL recorded honestly — pre-amendment lap).
- **Lap 2** (ring-curriculum-v2, doctrine-baked: ring-curriculum-v1 156 + doctrine-corpus-v2 236 + lean-invariants-sft-v1 304 + szl-1-doctrine-sft 41 = 737 rows; measurement-honesty-v1 HONESTLY DEFERRED — datasets-lib load stall, noted in manifest): `szl-ring-v2` IN FLIGHT (booted 2026-11-17T03:26:45Z, Qwen3-1.7B, 200 steps, stop-on-receipt watcher armed). No completion claimed.

— Vibe CTO lane, SZL Holdings estate, 2026-11-17.
