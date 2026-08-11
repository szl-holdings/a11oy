# SZL Regulatory Spine — Round 5 Convergence Addendum

This addendum captures the minimum governance and compliance posture required for
the Round 5 frontier convergence launch and gates every production release gate.

## 1) Regulatory baseline that must be treated as the doctrine source

The applicable legal baseline is now this:

- EU AI Act transparency and recordkeeping obligations are active around
  deployment and operation, with implementation pressure anchored in the EU GPAI
  enforcement model.
- The highest-risk trigger points are:
  - EU AI Act Article 12 (runtime recordkeeping, traceability, and auditability),
  - EU AI Act Article 26(6) (record retention floor),
  - operational retention and monitoring duties driven by high-risk post-market
    controls.
- Article 12 and related obligations are the canonical standard we implement against.
  If the evidence map cannot prove the events and policy checks, the claim is
  rejected as evidence debt.

## 2) Receipt envelope decision (hard architecture lock)

No proprietary ad-hoc envelope format is used for governed actions.

- The receipt envelope is in-toto (`https://in-toto.io/Statement/v1`).
- `predicateType` is a governed-action predicate under SZL control.
- Signature format is implementation detail:
  - Any Sigstore/cosign compatible in-toto statement is accepted by verification
    tooling.
- `szl.dev/GovernedAction/v1` is registered as the predicate namespace for this
  product line.

This replaces previous bespoke envelope drafts and avoids verifier lock-in.

## 3) Evidence posture and Article 12 mapping

Conformance for Article 12 is represented as a 12-field audit profile where each
field is independently auditable:

1. who requested,
2. who authorized,
3. human identity must be authenticated and non-service-account,
4. action context,
5. decision intent,
6. policy version and policy hash,
7. evidence inputs (prompt/model/tool/resource),
8. decision evidence (receipt lineage),
9. safety and risk annotations,
10. side-effects and impact class,
11. deployment / tenant / trace bindings,
12. retention and immutable storage bindings.

No default for missing evidence is a pass.

- `FAIL` states: `INCOMPLETE`, `UNKNOWN`, `CONTRADICTED` are never release pass.
- Every conformance report must include a machine-verifiable status per field and an
  aggregate release verdict.

## 4) Retention architecture (operational floor + separation of duties)

- Active telemetry/incident logs: 12–24 months queryable.
- Archive tier: 3–7 years immutable, cryptographically signed, write-once.
- Audit store and producer control planes must be separated from systems under test.
- No update/delete semantics are permitted for signed audit records.
- Batch signatures and periodic hash reconciliation are required at archive tier.

## 5) Product taxonomy discipline (lexicon lock)

There is only one product family narrative:

> **SZL Holdings builds a11oy: AI that can demonstrate its work through governed
> execution and offline-verifiable receipts.**

Legacy or conflicting naming in user-facing claims is blocked by gate control.

## 6) 26-space / 5-space doctrine guard

- Public copy must not flatten all spaces into a single doctrinal claim.
- A generated, evidence-linked registry may list all spaces.
- User-facing doctrine may explicitly distinguish flagship/primary surfaces and
  supporting/archival surfaces.
- Contradiction is fail-closed: if 26-space disclosure and 5-space doctrine are
  both claimed as equivalent facts, release is blocked.

## 7) Evidence debt that must stay explicit

Stale metrics, stale download figures, stale repository claims, and stale audit
snapshots are explicit debt:

- Snapshoted values are accepted only with explicit `SNAPSHOT(...)` state.
- Unknown/undiscovered values are explicit `UNKNOWN`, not silent success.
- A stale value is not a pass; it is a release blocker when used in a claim.

## 8) Operational command contract expected by this repo

At least this sequence is required for frontier convergence readiness:

1. `python3 tools/szl_convergence_bootstrap.py --run`
2. `python3 tools/lexicon_gate.py`
3. `python3 tools/release_gate.py`

All three are fail-closed and produce machine-consumable artifacts in `audit/`.
