# Threat model

## Assets

- root policy and capability authority;
- workload and signing identities;
- case/evidence/policy epoch bindings;
- idempotency and budget state;
- target preimages and rollback evidence;
- receipts, transparency checkpoints, and minority counterevidence;
- customer data and private model inputs.

## Adversaries

- malicious or compromised model/provider;
- prompt-injected retrieved content or MCP resource;
- colluding council specialists;
- compromised coordinator or presentation layer;
- malicious tool server;
- operator with excess static credentials;
- supply-chain substitution;
- database or evidence tampering;
- replay, stale identity, policy drift, and cross-case substitution.

## Defenses implemented

- signed role-bound commitments and reveals;
- complete commitment-set sealing;
- unique key/member/role registry;
- exact case, subject, policy, identity, time, and content-type binding;
- correlation-axis minimums and effective council size;
- categorical Authority/Sentinel/Verifier stops;
- immutable dissent and counterevidence index;
- target normalization, traversal/symlink refusal, and sandbox confinement;
- monotonic capability attenuation and budget checks;
- idempotency conflict detection;
- atomic preimage restoration;
- canonical objects and append-only hash chain;
- signed receipt self-verification;
- local Merkle inclusion proofs;
- forbidden private fields in deliberation state;
- Research Foundry prompt-injection and rights gates;
- read-only projection.

## Residual risks

- declared diversity can be false when operators collude out of band;
- different providers may share model lineage, training data, or upstream evidence;
- local keys on one host do not establish organizational independence;
- SQLite owner compromise can rewrite data and recompute local chains unless an external checkpoint exists;
- postconditions can be incomplete or measure the wrong target;
- exact rollback may be impossible for non-transactional external APIs;
- empirical calibration can fail under drift;
- a tool may create side effects outside its declared response;
- a valid policy can still encode a bad organizational decision.

## Production controls still required

Separate trust domains, managed key custody, public/partner transparency checkpoints, independent monitors, provider read-back, workload attestation, egress controls, sandboxing, incident response, kill switch, disaster recovery, and live negative tests.
