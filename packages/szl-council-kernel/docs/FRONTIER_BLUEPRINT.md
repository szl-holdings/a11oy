# A11oy Council / Alloy Council Kernel — Frontier Blueprint

## 1. Product thesis

**A11oy Council** is a governed autonomous decision-and-action system. It converts signals into bounded, reviewable, executable, and independently verifiable outcomes.

Its strategic category is not “another agent framework.” It is a **proof-carrying autonomy kernel**: the layer that determines what an AI system is allowed to attempt, whether independent evidence supports the attempt, whether the attempt produced the claimed effect, and whether that effect created value.

The operating chain is:

```text
signal
  → state-bound case
  → research and evidence qualification
  → branch generation
  → Fourfold independent assessment
  → calibrated act/escalate gate
  → capability-bounded execution
  → transaction/postcondition proof
  → transparency and independent witness
  → delayed outcome/value settlement
  → governed learning candidate
```

## 2. Architectural decision: kernel first, model family second

### Do not build the core as one model

A monolithic model cannot be the final authority over its own permissions, evidence, execution, verification, and learning. Even a highly capable model remains probabilistic, susceptible to prompt and retrieval attacks, difficult to reproduce exactly, and prone to correlated failure when reused across nominally different roles.

### Build the core as a deterministic kernel

The **Alloy Council Kernel** should be the minimal trusted computing base. It owns deterministic state transitions and enforces rules that models may not override.

### Train a family of specialist models later

The **SZL Council Models** should be compact, replaceable, measurable components:

1. **Governor/Router** — selects workflow depth, models, tools, and escalation path.
2. **Sentinel** — detects policy bypass, injection, exfiltration, privilege amplification, and unsafe ambiguity.
3. **Verifier ensemble** — maps stated postconditions to machine checks and audits evidence quality.
4. **Value/Outcome model** — forecasts utility, cost, opportunity cost, and delayed business impact.
5. **State Codec** — compresses and restores model-independent council state without carrying private chain-of-thought.
6. **Drift Sentinel** — detects changes in model, policy, data, provider, and tool behavior.
7. **Domain adapters** — maritime, legal, security, real estate, revenue, and operational specialists.

These models should be trained only after the trace, provenance, rights, benchmark, and outcome infrastructure is mature enough to produce defensible datasets.

## 3. Kernel planes

### 3.1 Constitution Plane

The Fourfold Council Protocol is the decision constitution.

- Authority answers: **May this be done?**
- Sentinel answers: **Can this cause unacceptable harm or abuse?**
- Verifier answers: **Can success be objectively proved?**
- Value answers: **Is the expected outcome worth the resources and opportunity cost?**

The coordinator has no vote. The aggregator invents no evidence. Sentinel and Verifier vetoes are non-overridable. Valid opposition is preserved.

### 3.2 Authority and Capability Plane

Every action carries an **Autonomy Envelope**:

```text
principal + delegated authority
subject + exact target
capability set + tool set
risk class + blast-radius class
cost/time/tool/mutation/branch/recursion budgets
preconditions + postconditions
idempotency and retry policy
rollback plan + rollback authority
model/policy/evidence/state epochs
required council and release state
receipt/transparency obligations
expiry + revocation reference
```

Authority is monotonic: a worker can receive a subset of the parent envelope, never expand it.

### 3.3 State Plane

The Alloy State Bus stores canonical, content-addressed state rather than conversational memory alone.

Required state classes:

- immutable case and policy snapshots;
- current workflow state and event history;
- evidence and counterevidence manifests;
- branch lineage and elimination reasons;
- capability leases and budget consumption;
- model, tool, policy, and retrieval epochs;
- receipts, checkpoints, transparency proofs, and witness observations;
- delayed outcome observations; and
- learning-candidate lineage.

Private chain-of-thought is not a state class. Persist structured claims, evidence references, stance, confidence, reason codes, uncertainty, and action records instead.

### 3.4 Orchestration Plane

Use deterministic workflows for authority, sequencing, retries, timeouts, checkpoints, and settlement. Use models only inside explicitly agentic nodes.

Recommended runtime pattern:

- Temporal or an equivalent durable workflow engine for cross-service execution and replay;
- LangGraph-style state graphs where fine-grained deterministic/agentic composition is useful;
- OPA/Rego or an equivalent policy engine for externalized policy decisions;
- AgentScope, Microsoft Agent Framework, Google ADK, or custom workers as interchangeable agent harnesses—not as the root of trust.

### 3.5 Interoperability Plane

- **MCP** for agent-to-tool/resource access, always wrapped by the MCP governor.
- **A2A** for agent-to-agent interoperability across frameworks and trust domains.
- Typed internal envelopes for local subagents and deterministic kernel services.
- No protocol message is trusted solely because it arrived over MCP or A2A; identity, authority, schema, policy epoch, and evidence bindings remain mandatory.

### 3.6 Identity Plane

Use workload identity rather than static shared secrets.

- SPIFFE/SPIRE identities for workloads and trust-domain accounting;
- short-lived credentials and automatic rotation;
- separate identities for Authority, Sentinel, Verifier, Value, aggregator, executor, witness, monitor, and projector;
- separate provider accounts and retrieval paths where independence policy requires them;
- hardware or managed key custody for production signing authority.

### 3.7 Proof and Transparency Plane

- in-toto/SLSA-style provenance for builds and deployments;
- Sigstore-compatible signing and identity binding where suitable;
- SCITT/RFC 9943 statements and receipts for content-agnostic transparency;
- RFC 9162-style Merkle inclusion and consistency proofs where used by the existing implementation;
- independent monitor gossip and portable fork evidence;
- read-only A11oy projection that cannot set `verified`.

### 3.8 Observability Plane

OpenTelemetry spans and metrics must expose operational facts without exposing secrets, raw customer data, hidden prompts, or private reasoning.

Every trace should bind:

- case, workflow, branch, action, receipt, and outcome IDs;
- principal and workload identity digests;
- model/tool/policy/evidence/state epochs;
- budget consumed;
- council state and calibrated release state;
- veto, conflict, escalation, rollback, and verification reason codes; and
- public versus private visibility classification.

## 4. Original frontier mechanisms

### 4.1 Proof-Carrying Deliberation Graph

Replace chat transcripts as the authoritative council record with a typed graph:

- **Claim** — bounded proposition.
- **Evidence** — digest-bound source or observation.
- **Stance** — role-specific support, opposition, abstention, or veto.
- **Challenge** — explicit attack on a claim/evidence edge.
- **Decision** — deterministic terminal state.
- **Action** — bounded execution attempt.
- **Outcome** — verified immediate or delayed effect.

Every node is canonicalized and content-addressed. The graph retains evidential structure without storing private chain-of-thought.

### 4.2 Epistemic Diversity Compiler

Do not count “agents.” Count independent failure clusters.

The compiler evaluates at least:

1. trust domain;
2. signing key;
3. implementation digest;
4. model family/base lineage;
5. evidence domain/source family;
6. operator;
7. retrieval path/index;
8. provider account/inference control plane.

A policy can add domain-specific axes, such as geographic region, data custodian, or hardware vendor.

Define the **Effective Epistemic Council Size**:

\[
N_{eff}=\frac{1}{\sum_{c=1}^{k} p_c^2}
\]

where \(p_c\) is the fraction of participating assessments in correlation cluster \(c\). Four aliases from one cluster produce \(N_{eff}=1\); four equally represented independent clusters produce \(N_{eff}=4\).

This metric does not prove independence; it makes claimed independence explicit and policy-testable.

### 4.3 Blinded Cross-Critique

Fourfold already commits before reveal. Extend that principle:

1. Each role submits a blinded structured assessment.
2. The commitment set seals.
3. Initial assessments reveal without provider/model prestige labels.
4. Cross-critique operates on claims and evidence, not identity authority.
5. Identity and diversity metadata become visible only to the deterministic settlement layer and authorized auditors.

This reduces social conformity, sycophancy, and prestige bias.

### 4.4 Calibrated Act/Escalate Gate

Consensus is evidence, not permission. Add a post-hoc release layer calibrated on historical council cases.

Inputs include:

- council terminal state;
- role confidences and disagreement pattern;
- effective diversity;
- evidence and proof completeness;
- novelty and out-of-distribution score;
- ambiguity and irreversibility;
- historical false-green rate for the task class;
- model/tool/policy drift indicators; and
- expected blast radius.

Outputs are set-valued:

- `ACT` — bounded execution may proceed;
- `ESCALATE` — human or higher-assurance review is required;
- `BLOCK` — policy or evidence forbids action.

The production method should use a statistically justified conformal-risk-control or equivalent calibration procedure. The included reference code implements only an empirical envelope and explicitly does not claim formal coverage guarantees.

### 4.5 Counterfactual Branch Market

Ouroboros becomes a bounded branch fabric rather than an unlimited self-reflection loop.

Candidate branches bid using:

\[
S(b)=w_uU_b-w_rR_b-w_cC_b-w_tT_b+w_pP_b+w_dD_b-w_nN_b
\]

where:

- \(U\): expected utility;
- \(R\): risk;
- \(C\): monetary/token/compute cost;
- \(T\): latency;
- \(P\): proof completeness;
- \(D\): epistemic diversity contribution;
- \(N\): unsupported novelty penalty.

Only branches inside the Autonomy Envelope and with verified evidence may compete for release. Eliminated branches remain available for counterfactual replay and learning.

### 4.6 Minority Truth Vault

A valid minority may be correct even when a majority agrees. Preserve:

- signed opposition;
- counterevidence digests;
- unresolved assumptions;
- failed or contradictory checks;
- exact settlement state; and
- later adjudication as a new signed action rather than rewriting history.

Measure **Dissent Survival Rate**: valid opposition retained and discoverable divided by all valid opposition.

### 4.7 Causal Outcome Closure

Immediate verification answers “Did the requested state change occur?” It does not answer “Did this create value?”

Each value-bearing action should create a delayed outcome contract:

- target metric and baseline;
- expected direction and effect window;
- confounder register;
- observation schedule;
- attribution method;
- cost and opportunity-cost accounting;
- stop-loss and rollback trigger; and
- final signed Value settlement.

Learning promotion should weight verified outcomes, not merely agent confidence or user approval.

### 4.8 Negative Capability Ledger

The system should know what it cannot safely or reliably do.

Record task classes, tools, domains, conditions, and epochs where the system:

- lacks authority;
- lacks evidence;
- lacks an objective verifier;
- is poorly calibrated;
- is out of distribution;
- has failed rollback or replay;
- depends on one correlated provider/source; or
- exceeds acceptable cost or latency.

The router consults this ledger before attempting work.

### 4.9 Cognitive Epochs and State Portability

Bind every run to exact epochs for model, tokenizer, prompt/template, tool, policy, retrieval index, evidence manifest, and state schema. A changed epoch creates a new decision context and prevents false replay equivalence.

Define portability tiers:

- **P0 — transcript-only:** not authoritative.
- **P1 — structured state:** claims, evidence, actions, and statuses.
- **P2 — replayable state:** exact deterministic events and external-call receipts.
- **P3 — portable state:** model-independent ABI and migrations.
- **P4 — independently verifiable state:** signatures, transparency, witness, and postcondition proofs.

### 4.10 Research Foundry

The research ingestion path is:

```text
DISCOVER
  → QUARANTINE
  → LICENSE/RIGHTS REVIEW
  → PIN REVISION + HASH
  → MALWARE/PROMPT-INJECTION REVIEW
  → CLAIM EXTRACTION
  → REPRODUCTION
  → BENCHMARK AGAINST BASELINES
  → SEMANTIC DIFF + DESIGN REVIEW
  → FOURFOLD PROMOTION DECISION
  → VENDORED/REIMPLEMENTED MODULE WITH LINEAGE
```

Never silently copy a project into SZL branding. Preserve source attribution, license, revision, modifications, benchmark evidence, and the rationale for adaptation.

## 5. Autonomy levels

“Full autonomy” must be risk-tiered and earned.

| Level | Capability | Release rule |
|---|---|---|
| A0 Observe | read, summarize, simulate | no mutation |
| A1 Propose | create plans, patches, branches, drafts | human approves execution |
| A2 Execute reversible low-risk | sandbox or preview mutations with automatic checks | Council + calibrated gate + rollback |
| A3 Operate bounded production | pre-approved targets/actions inside strict budgets | live proof, witness, monitoring, stop-loss |
| A4 Cross-system autonomous program | multi-step execution across systems | independent operators, formal invariants, live negative tests, human-owned root policy |
| A5 Self-modifying governed system | proposes changes to models/policies/kernel | changes remain offline until separate promotion council; kernel/root policy never self-authorize |

The objective is not “remove humans.” It is to make the human the owner of root policy and exceptional judgment while routine execution becomes autonomous, bounded, and independently auditable.

## 6. Model strategy

### Phase 1 — heterogeneous external/open models

Use a model gateway with exact provider/model/revision recording. Route by task, cost, latency, rights, and independence requirements. Separate role evidence paths and do not assume different endpoint names imply different base-model lineage.

### Phase 2 — distill compact specialist models

Train on owned or licensed data derived from:

- structured cases and evidence manifests;
- deterministic verifier outcomes;
- policy decisions and reason codes;
- adversarial benchmark traces;
- branch selection and counterfactual replay;
- delayed outcome settlements; and
- public/partner datasets with documented rights.

Exclude private chain-of-thought, secrets, unauthorized customer content, and unlicensed repository text.

### Phase 3 — promote models only through evidence

Every candidate needs:

- model card and lineage;
- exact training data manifest and rights statement;
- reproducible training/evaluation configuration;
- contamination and leakage checks;
- task-class calibration;
- red-team evaluation;
- cost/latency profile;
- rollback-compatible packaging;
- Fourfold promotion decision; and
- transparency receipt.

### Phase 4 — never merge kernel authority into weights

Models may learn to recommend policies. They must not become the sole source of policy truth. Root authority, capability boundaries, release-state transitions, and proof acceptance remain deterministic and reviewable.

## 7. Metrics that matter

### Safety and truth

- **False-Green Rate:** released actions whose claimed postcondition later fails / released actions.
- **False-Block Rate:** safe and beneficial actions incorrectly blocked / eligible actions.
- **Calibration error / Brier score** by task and risk class.
- **Veto integrity:** attempts to override valid Sentinel/Verifier vetoes; target zero.
- **Dissent Survival Rate.**
- **Trustworthy Tension Rate:** meaningful disagreement preserved rather than collapsed into artificial consensus.
- **Fork detection time** and **stale-witness rejection rate**.

### Autonomy and operations

- autonomous completion rate by risk class;
- escalation precision and recall;
- rollback success and rollback time;
- exact replay rate;
- ambiguous retry prevention;
- budget overrun rate;
- branch pruning efficiency;
- model/tool/provider failover success;
- cost and latency per verified outcome, not per generated answer.

### Value

- verified outcome attainment;
- realized versus forecast value;
- time-to-effect;
- cost avoided or revenue enabled with evidence;
- negative externality and opportunity-cost accounting;
- percentage of learned policies/models backed by delayed outcome evidence.

## 8. Delivery roadmap

### P0 — Truth lock and canonicalization

- Name the product, kernel, protocol, model family, and research lab.
- Mark all simulated quorum/demo paths clearly.
- Establish one canonical current-state and closure ledger.
- Classify every Hugging Face artifact as model, dataset, Space, or software/kernel.

### P1 — Canonical Fourfold integration

- Make Fourfold the sole authoritative council settlement contract.
- Add adapters for A11oy and the public platform.
- Remove direct UI/runtime writes to `verified`.
- Bind every case to exact policy, evidence, model, and state epochs.

### P2 — Autonomy Envelope and durable workflow

- Implement the canonical schema.
- Enforce capability subset, target matching, budgets, idempotency, retries, and rollback.
- Persist event history and checkpoints in State Bus.
- Integrate OPA policy decisions and receipt-correlated OTel.

### P3 — Real independent specialists

- Separate workload identities, keys, provider accounts, retrieval paths, and operators.
- Establish production diversity policy and minimum effective council size.
- Deploy Sentinel and Verifier against independent evidence sources.
- Run blind cross-critique and identity-bias tests.

### P4 — Frontier release logic

- Add calibrated act/escalate control.
- Add Ouroboros branch market and counterfactual replay.
- Add minority truth vault and delayed Value settlement.
- Publish FourfoldBench v2 and baseline comparisons.

### P5 — Specialist model training

- Build signed trace/outcome datasets.
- Train router, sentinel, verifier, state codec, and value models.
- Evaluate against strongest-single-model, self-consistency, Self-MoA, majority vote, debate, and orchestrator baselines.
- Promote only candidates that improve verified outcomes and calibration after cost normalization.

### P6 — Production independence and transparency

- Managed/HSM key custody and rotation.
- SPIFFE trust-domain separation.
- Durable transparency service and independent monitor domains.
- Public/partner receipts, gossip, fork tests, rollback drills, and disaster recovery.
- Compiled Lutar-Lean invariants bound to release.

### P7 — Category creation

- Publish the Fourfold Council specification, benchmark, threat model, and reference adapters.
- Demonstrate a real end-to-end action from case to delayed outcome receipt.
- Position A11oy Council as correlated-agent assurance and proof-carrying autonomy infrastructure.

## 9. Non-negotiable laws

1. No model self-authorizes.
2. No action without an exact target and bounded capability.
3. No irreversible mutation without independent proof and rollback analysis.
4. No majority override of a valid Sentinel or Verifier veto.
5. No claim of diversity without measured independence axes.
6. No hidden rewrite of dissent or historical receipts.
7. No learning from unauthorized data or private chain-of-thought.
8. No promotion without reproducible evaluation and signed lineage.
9. No “verified” label written by the presentation layer.
10. No production-autonomy claim without live negative tests, independent monitors, and read-back evidence.
