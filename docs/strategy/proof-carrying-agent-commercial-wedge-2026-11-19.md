<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 SZL Holdings
-->

# Commercial evidence truth and the proof-carrying AI wedge
**Research / pilot hypothesis, 19 November 2026. Not a revenue claim or release approval.**

## Decision: sell one painful outcome before selling an ecosystem

**Proposed product:** SZL Proof-Carrying Agent Operations — an independent *release and incident evidence packet* that answers: "Can we prove which agent/model/configuration was authorized, what ran, what failed, which runtime and data version was used, and whether the action should be permitted?"

The target buyer is a **hypothesis**: an enterprise AI-platform engineering leader, regulated-workflow owner, AI-governance leader, or CTO with budget authority. No buyer has been interviewed or signed off on this persona in the canonical commercial ledger. An enterprise may already have Palantir, LangSmith, or telemetry tooling; **SZL must interoperate rather than require a replacement**.

### Why test this

- The September 2026 [EY US AI Risk and Governance Survey](https://www.ey.com/en_us/newsroom/2026/09/ey-survey-finds-that-autonomous-ai-implementation-outpaces-oversight-yielding-an-ai-governance-gap) says 47% of respondents had bypassed their AI governance process for urgent deployments despite 98% having policies. This is a survey claim about its respondents, not a measured SZL market opportunity.
- [G2's October 2026 AI Agents Insight Report](https://sell.g2.com/g2-2026-ai-agents-insight-report) discusses a "Distrust Tax": repeated manual oversight and unexpected operational costs. The quoted percentages describe the report's surveyed buyers, not all enterprises.
- [Palantir's AIP observability](https://www.palantir.com/docs/foundry/aip-observability/overview) already covers tracing, action metrics, execution history and evaluation. SZL cannot claim to have invented workflow observability. Differentiate with portable, offline-verifiable **source-to-model-to-policy-to-action-to-effect** evidence, precise missing-evidence states and cross-vendor reproducibility.
- [NVIDIA has deprecated NeMo Agent Toolkit as of October 2026](https://docs.nvidia.com/nemo/agent-toolkit/latest/index.html), recommending NeMo Relay, Helix and Fabric. Integrate with *current* governance/observability contracts and OpenTelemetry rather than building a new product around an EOL toolkit.
- [Cloudflare Monetization Gateway](https://developers.cloudflare.com/monetization-gateway/) can apply x402 requirements to selected APIs/MCP tools and datasets; [origin payment validation](https://developers.cloudflare.com/monetization-gateway/configuration/payment-validation/) requires verification of its signed PAYMENT-CONTEXT JWT. An HTTP 402 is a challenge, **not a payment, settlement, customer, recognized revenue or proof of correct origin validation**.

## Product contract: one release packet with noncompensating gates

| Dimension | Minimum field and pass condition | Fail-closed label when missing |
| --- | --- | --- |
| Identity | Immutable git commit, signed or trusted workload origin, exact deployed artifact/image digest | SOURCE_UNVERIFIED |
| Model and data | Base, adapter, tokenizer and dataset immutable revisions; model BOM and dataset rights current **at the same census revision** | ASSET_SCOPE_UNAVAILABLE |
| Evaluation | Task-specific held-out set and rights, denominator, failures/abstention, baseline, repeated seeds, costs and version-bound weights | EVAL_UNQUALIFIED |
| Policy | Owner generation, tenant, action scope, expiry, human approval for irreversible effects, explicit decision | AUTHORITY_UNVERIFIED |
| Execution | Correlation ID linking request, accepted operation, actual process/target, outcome and uncertain transport | EXECUTION_UNVERIFIED |
| Evidence integrity | Byte/object readback, trusted signature root, inclusion/checkpoint or independent attestation, freshness | PROVENANCE_UNVERIFIED |
| Recovery | Retained opaque full-state checkpoint, independently rehashed backup, exercised restore, no silent genesis | RECOVERY_UNQUALIFIED |
| Product behavior | Unpaid/protected endpoints scoped correctly; p95 latency, availability, errors, audited payloads, incident rollback | RUNTIME_NOT_READY |
| Economics | Measured cloud/GPU/LLM cost by authorized job and customer, **verified** invoice/settlement and recognized ARR | UNIT_ECONOMICS_UNKNOWN |

A model can be **TRAINED** and **ARTIFACT_VERIFIED** yet still not be **EVALUATED**, **DEPLOYED**, or **QUALIFIED**. No geometric mean, Yuyay score, or aggregate "green" badge compensates for a missing hard gate. Khipu hashes are not signer validation on their own; the Lutar Λ-uniqueness theorem requires stated factorization assumptions.

## Measured evidence and limitations at this research cut

| Surface | Observed source-scoped fact | What it does NOT establish |
| --- | --- | --- |
| A11oy public API | GET \`https://a-11-oy.com/api/a11oy/healthz\` returned JSON status OK, but \`operational_readiness.ready=false\` on 2026-11-19 20:05 UTC | Full production readiness, paid usage or signed real-world outcomes |
| Product source | Canonical GitHub \`szl-holdings/a11oy\` main was \`bfb64b3c6bf5a477762540a9685b4fd9524fdf76\` at 19:54 UTC; live public Series A status declared \`9467fa988ff63c919954adbd8e23e930412321b5\` at 20:05 UTC | Exact current-main runtime-source parity; separate Hub and image-byte verification needed |
| Proof domain | \`https://a11oy.net/record.json\` and \`/public-inventory.json\` returned \`403 cf-mitigated:challenge\` from one unauthenticated source at 20:05 UTC | Universal unavailability; the specific Cloudflare rule remains unobserved |
| Training fleet | One project-scoped Salad collection at 20:05 UTC returned 138 groups, 51 named \`szl-train-*\`, and **zero training-named groups with provider-reported running instances** | All-project census, zero billable GPUs, or historical training completeness |
| Payment | Unpaid HEAD on two inference routes returned HTTP 402 and \`PAYMENT-REQUIRED\` at 20:07 UTC | A signed payment, Coinbase settlement, wallet receipt, customer or ARR |
| BOM/license registry | The [SZLHOLDINGS/model-bom](https://huggingface.co/datasets/SZLHOLDINGS/model-bom) registry's Sep 25 card admits 44 BOMs covering 49 then-public models, last updated Sep 28. Canonical commercial ledger had asserted full August coverage for 43 public models and 28 datasets. | Up-to-date whole-estate model or dataset-rights coverage at 2026-11-19 |
| Financials / buyers | Canonical \`COMMERCIAL_LEDGER.yaml\` does not evidence verified signed ARR, current paying-customer counts, accepted pricing, or signed design partners | No revenue has ever existed or will exist; absence of verified evidence is not a zero |

Research sources and dated private operational observations cannot be promoted into signed externally attested proof without independent checks. Some prior company cards carry an older snapshot: **do not silently reconcile differing author, visibility and account scopes into one headline repository count**.

## 14-day design-partner pilot (proposal, not a commitment)

**Week 1:** Select one owner-approved workflow; use read-only data and rights-cleared synthetic negative tests. The buyer provides exact acceptable identities, policy versions, incidents, actions, and evaluation acceptance criteria. Collect one baseline operational audit and a version-pinned artifact list. Define signed receipt roots and the operator's security boundary.

**Week 2:** Deliver an offline-verifiable packet and CLI check, 3 incident/rollback traces, refusal evidence for missing signer, stale deployment, inconsistent transaction result, and a transparent cost/evaluation table. No access to live effectors by default. The buyer—not an SZL self-evaluator—confirms the result and signs an acceptance note.

**Pilot success thresholds, to negotiate before execution:**
1. 100% of injected unauthorized or inconsistent operations blocked by the strict gate in the bounded approved test suite.
2. 100% exact byte / revision association for the packet's *declared* release artifacts; unavailable pieces declared unavailable.
3. A decision can be reproduced offline by a second verifier without needing secret SZL model code or untrusted pickle deserialization.
4. Buyer measures the baseline and actual reduction in investigation time, with sample count and uncertainty.
5. Reproducible p95 latency, cost per verified event, user-visible errors and incident recovery under buyer-specified thresholds.

Do not claim SOC 2 certification, cryptographic key custody, accredited verification, deployed runtime source parity or commercial contracts unless separately substantiated.

## Commercial hypothesis and validation—not published terms

**Test buyer messages:** "release evidence in minutes, not anecdotes"; "prevent green CI from becoming false production claims"; "portable audit packets across GitHub, Hugging Face, cloud runtimes and customer workflows." The message is a proposed value proposition, not an established customer outcome.

**Discovery milestones (targets, not actuals):** 20 interviews across enterprise AI-platform/FinOps/governance leaders; 6 problem-qualified buyer calls; 2 rights-cleared paid-pilot proposals; 1 buyer-signed repeatable success criterion; zero unsupported performance claims. Capture evidence for objection/decision type and procurement authority.

**Price exploration:** fixed-fee pilot plus recurring per-workflow/verified-operation plan are hypotheses. Test willingness to pay in discovery; do not present a suggested amount as the actual published SKU or contracted ARR. Separately qualify wallet-funded x402 usage and enterprise invoices.

**Funding claim:** "unicorn" is a scaling aspiration, **not** a valuation. Do not infer investability from repo/model counts or academic formulas. Raise-readiness requires current contracts, collection/retention evidence, audited cash/burn, attribution, IP assignment and a credible growing customer cohort.

## Prioritized gates, no parallel platform

1. Restore independent **public proof routes** without weakening private or paid paths. Verify 6 public routes from separate unauthenticated vantage points.
2. Make A11oy's exact source/runtime/image and signer-root checks pass without changing readiness booleans by fiat.
3. Re-census the *same visibility/account scope* for model BOM/dataset rights, reconstruct immutable item-level coverage and a real CI blocklist.
4. Prove a complete signed offline release packet on one already approved SKU/workflow with a buyer-run negative suite and exercised recovery.
5. Run the design-partner pilot; report findings, numerator/denominator, price acceptance, retention and unit costs. Only then promote the commercial rows to VERIFIED.

**Competition:** Palantir is an established operational platform, and NVIDIA, LangSmith, Arize Phoenix, Sigstore/SLSA, MLflow and Temporal have relevant mature pieces. The wedge is the interoperable **proof and admission contract**, not owning another horizontally sprawling AI platform or training an unqualified foundation model.
