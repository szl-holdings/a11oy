# A11oy and AYLLU integration

## Ownership

- The Council Kernel owns authority, settlement, mutation state, proof acceptance, and receipt issuance.
- A11oy receives read-only projections for command, evidence, and investor/operator presentation.
- AYLLU hosts model routing and specialist workcells but cannot mint capabilities or set `verified`.
- Agent Forge / Proof Mesh can carry Fourfold and effect receipts into external transparency paths.

## Integration sequence

1. Import the packaged schemas into the canonical schema registry.
2. Map AYLLU workcells to signed `CouncilIdentity` records.
3. Convert model output to `CouncilAssessment`; never persist hidden reasoning.
4. Submit commitments, seal, and reveal through the kernel.
5. Project `CouncilResult` through `a11oy_read_only_projection`.
6. Bind approved actions to `AutonomyEnvelope` and `CapabilityGrant`.
7. Use provider-specific executors behind the same idempotency/postcondition interface.
8. Project receipt state, signer state, and evidence links separately.
9. Open delayed outcome contracts for value-bearing actions.
10. Promote training data only through the Research Foundry and a separate council.

## UI contract

The interface may display:

- `VERIFIED` only when the signed CouncilResult state is `QUORUM_VERIFIED`;
- `SIGNED_TEST` versus `SIGNED_PERSISTENT` without collapsing them;
- `LOCAL_MERKLE_REFERENCE_ONLY` without calling it independent transparency;
- explicit `BLOCKED`, `CONFLICT`, `HUMAN_GATE`, and `INSUFFICIENT` states;
- dissent and counterevidence counts without exposing classified content.

The UI cannot submit a vote, open a commitment, resolve a conflict, rewrite a receipt, or write `verified`.
