// GOVERNANCE LAYER — A11oy × Sentra defensive orchestration architecture.
//
// Distillation of the governance-class executive summary into a static doctrine
// surface: the A11oy command-agent orchestration loop, the integrated scanner
// toolchain catalogue, the RL pipeline formulation, the guardrails stack, and
// the phased roadmap.
//
// All inputs are public research, official tool documentation, or first-principle
// reconstructions. No leaks, no scraped weights, no telemetry. Adoption requires
// a Sentra approval workflow per the Glasswing doctrine.

export const GOVERNANCE_LAYER_VERSION = '0.1.0-seed';

export const GOVERNANCE_LAYER_TAGLINE =
  'A11oy plans, Sentra executes, the human approves. Defensive only, evidence-bound, public-input only.';

// ---------------------------------------------------------------------------
// 1. ORCHESTRATION LOOP
// The 10-step A11oy → Sentra interaction described in the architecture diagram.
// ---------------------------------------------------------------------------

export type LoopActor = 'A11oy' | 'Sentra' | 'Human' | 'External';

export interface OrchestrationStep {
  step: number;
  from: LoopActor;
  to: LoopActor;
  action: string;
  detail: string;
  guardrail: string;
}

export const ORCHESTRATION_STEPS: readonly OrchestrationStep[] = [
  {
    step: 1,
    from: 'A11oy',
    to: 'Sentra',
    action: 'plan tasks',
    detail:
      'A11oy decomposes a natural-language or policy directive (e.g. "scan production Linux fleet for critical CVEs") into a typed task graph and submits it to Sentra\u2019s Policy Engine for admission control.',
    guardrail:
      'Plan is rejected if it requests any action outside the tenant\u2019s registered scope or violates a Constitution rule.',
  },
  {
    step: 2,
    from: 'A11oy',
    to: 'Sentra',
    action: 'execute scans',
    detail:
      'Approved tasks dispatch the scanner toolchain (CodeQL, Semgrep, OSV-Scanner, Trivy, Gitleaks, Checkov) against the target surface defined in the plan.',
    guardrail:
      'Scanners run in least-privilege containers with read-only mounts; no scanner can write to a target system.',
  },
  {
    step: 3,
    from: 'Sentra',
    to: 'Sentra',
    action: 'findings → analyzer',
    detail:
      'Raw scanner output is normalised into the governance finding schema and fed to the Risk Assessment Engine for de-duplication, severity scoring, and exploitability triage.',
    guardrail:
      'Every finding is hash-linked to the scanner version, ruleset version, and target snapshot for chain-of-custody.',
  },
  {
    step: 4,
    from: 'Sentra',
    to: 'A11oy',
    action: 'context info → model',
    detail:
      'Risk-scored findings, the relevant code/IaC context, and the dependency graph are returned to the A11oy LLM agent for patch reasoning.',
    guardrail:
      'Context is bounded by the original plan\u2019s scope; no out-of-scope source is delivered to the model.',
  },
  {
    step: 5,
    from: 'A11oy',
    to: 'Sentra',
    action: 'propose patch',
    detail:
      'A11oy generates a candidate patch (diff) and a rationale trace, then submits both to Sentra\u2019s Patch Engine for static validation.',
    guardrail:
      'Patch payload is schema-validated; any non-diff side-channel (shell calls, network IO) is stripped before submission.',
  },
  {
    step: 6,
    from: 'Sentra',
    to: 'Human',
    action: 'patch suggestion → approval',
    detail:
      'The Patch Engine attaches a static-analysis verdict and posts the suggestion to the Approval Queue with severity, blast radius, and rollback plan.',
    guardrail:
      'Production patches require dual-key approval; staging patches require single-key approval; no auto-merge above low risk.',
  },
  {
    step: 7,
    from: 'Human',
    to: 'Sentra',
    action: 'commit approved patch',
    detail:
      'On approve, Sentra commits the patch to the staging branch with the approver\u2019s OIDC-attested signature recorded in the audit ledger.',
    guardrail:
      'Approval evidence is appended to the Cerberus vault before the commit lands; rollback is a single-click revert.',
  },
  {
    step: 8,
    from: 'Sentra',
    to: 'External',
    action: 'apply patch',
    detail:
      'Sentra deploys the approved patch through the customer\u2019s existing CI/CD path and verifies the targeted finding is resolved on the post-deploy scan.',
    guardrail:
      'Apply step is idempotent and auto-reverts if the post-deploy scan introduces new criticals.',
  },
  {
    step: 9,
    from: 'A11oy',
    to: 'A11oy',
    action: 'retrain',
    detail:
      'Outcome (verified fix, false positive, regression) is logged as an RL episode for the Silver planner; reward signal is composed from finding-closed, no-new-bugs, and time-to-resolve.',
    guardrail:
      'Training data is tenant-isolated; no cross-tenant gradient sharing without explicit opt-in.',
  },
  {
    step: 10,
    from: 'Human',
    to: 'Sentra',
    action: 'review',
    detail:
      'Analyst reviews the closed loop, marks the disposition (correct / over-cautious / wrong), and the feedback updates the reward model used by step 9.',
    guardrail:
      'Reviewer disposition is itself logged as evidence and feeds the Mirror Eval slice for the next quarterly model audit.',
  },
];

// ---------------------------------------------------------------------------
// 2. SCANNER TOOLCHAIN
// Public, defensively-licensed tools the orchestration layer composes.
// ---------------------------------------------------------------------------

export type ScannerSurface =
  | 'source-code'
  | 'dependencies'
  | 'containers'
  | 'iac'
  | 'secrets';

export type ScannerLicense = 'MIT' | 'Apache-2.0' | 'MPL-2.0' | 'LGPL-3.0' | 'GPL-3.0';

export type ScannerId =
  | 'codeql'
  | 'semgrep'
  | 'osv-scanner'
  | 'trivy'
  | 'gitleaks'
  | 'checkov';

export interface Scanner {
  id: ScannerId;
  name: string;
  surface: ScannerSurface;
  oneLine: string;
  primitive: string;
  license: ScannerLicense;
  source: { repo: string; url: string; org: string; lang: string };
  sentraBinding: string;
  guardrail: string;
}

export const SCANNERS: readonly Scanner[] = [
  {
    id: 'codeql',
    name: 'CodeQL',
    surface: 'source-code',
    oneLine:
      'GitHub\u2019s semantic code-analysis engine. Treats the codebase as a database and runs typed queries to find vulnerability classes (SQLi, RCE, taint flows).',
    primitive: 'Datalog-style queries over a code property graph, with curated query packs per language.',
    license: 'MIT',
    source: { repo: 'github/codeql', url: 'https://github.com/github/codeql', org: 'GitHub', lang: 'C++ / QL' },
    sentraBinding:
      'Invoked by the Static Scanner module on every plan that touches source. Findings normalise into the governance finding schema with rule-id provenance.',
    guardrail:
      'Runs in a sandboxed container against a read-only checkout. The query pack version is pinned and recorded in the evidence ledger.',
  },
  {
    id: 'semgrep',
    name: 'Semgrep',
    surface: 'source-code',
    oneLine:
      'Fast, syntax-aware pattern matcher for source code. Lower-cost first pass that catches the long-tail of policy-driven anti-patterns.',
    primitive:
      'AST pattern templates with metavariables and taint analysis, executed against many languages from a single ruleset.',
    license: 'LGPL-3.0',
    source: { repo: 'semgrep/semgrep', url: 'https://github.com/semgrep/semgrep', org: 'Semgrep', lang: 'Python / OCaml' },
    sentraBinding:
      'Runs in parallel with CodeQL as the cheap first sieve. Its findings carry lower default severity unless escalated by the Risk Engine.',
    guardrail:
      'Custom rules require Constitution review before they are added to the active ruleset; no inline rule loading.',
  },
  {
    id: 'osv-scanner',
    name: 'OSV-Scanner',
    surface: 'dependencies',
    oneLine:
      'Google\u2019s frontend to the Open Source Vulnerabilities database. Resolves project lockfiles and reports known CVEs against pinned versions.',
    primitive:
      'Deterministic lockfile parser + queries against the public OSV.dev advisory feed.',
    license: 'Apache-2.0',
    source: { repo: 'google/osv-scanner', url: 'https://github.com/google/osv-scanner', org: 'Google', lang: 'Go' },
    sentraBinding:
      'Runs on every dependency manifest in scope. Findings link to the upstream OSV entry plus the targeted lockfile path.',
    guardrail:
      'Uses the public OSV API only. No customer SBOM is uploaded; queries are purl-based and opaque.',
  },
  {
    id: 'trivy',
    name: 'Trivy',
    surface: 'containers',
    oneLine:
      'Container, OS package, and IaC scanner. The default Sentra layer for any image or registry surface.',
    primitive:
      'Layered scanner that combines distro vulnerability databases, SBOM extraction, and a Rego-driven misconfig pass.',
    license: 'Apache-2.0',
    source: { repo: 'aquasecurity/trivy', url: 'https://github.com/aquasecurity/trivy', org: 'Aqua Security', lang: 'Go' },
    sentraBinding:
      'Wired to both the Static Scanner (image scan) and the Patch Engine (post-deploy verification scan).',
    guardrail:
      'Operates against image digests, not running workloads. No exec-into-container path is exposed.',
  },
  {
    id: 'gitleaks',
    name: 'Gitleaks',
    surface: 'secrets',
    oneLine:
      'High-entropy and pattern-based secrets scanner for git history. Catches leaked credentials before they reach production.',
    primitive:
      'Configurable regex + entropy ruleset over git diffs and historical blobs.',
    license: 'MIT',
    source: { repo: 'gitleaks/gitleaks', url: 'https://github.com/gitleaks/gitleaks', org: 'Zachary Rice', lang: 'Go' },
    sentraBinding:
      'Triggered on every plan that includes a repository scan. Findings are routed straight to the Approval Queue with auto-redaction in the audit log.',
    guardrail:
      'Findings are stored as hashed fingerprints, not the raw secret. The raw match is held in the Cerberus vault under analyst-only access.',
  },
  {
    id: 'checkov',
    name: 'Checkov',
    surface: 'iac',
    oneLine:
      'Infrastructure-as-code scanner for Terraform, CloudFormation, Kubernetes, Helm, and ARM. Catches misconfigurations before they ship.',
    primitive:
      'Built-in policy library + custom policies expressed in Python or YAML, executed against parsed IaC graphs.',
    license: 'Apache-2.0',
    source: { repo: 'bridgecrewio/checkov', url: 'https://github.com/bridgecrewio/checkov', org: 'Bridgecrew / Prisma Cloud', lang: 'Python' },
    sentraBinding:
      'Runs on every IaC change in a plan. Verdicts feed the Compliance Engine for SOC2 / CIS-Benchmark mapping.',
    guardrail:
      'No --download-external-modules in CI; only vendored modules are evaluated to keep the supply chain attested.',
  },
];

// ---------------------------------------------------------------------------
// 3. RL PIPELINE
// Public-research formulation: state, action, reward, training regime.
// ---------------------------------------------------------------------------

export interface RLAxis {
  id: 'state' | 'action' | 'reward' | 'regime' | 'humanFeedback' | 'safety';
  axis: string;
  detail: string;
  citation: string;
}

export const RL_PIPELINE: readonly RLAxis[] = [
  {
    id: 'state',
    axis: 'State',
    detail:
      'Current security posture: vulnerable code context, dependency graph, recent scanner output, telemetry stream, and the agent\u2019s long-term memory of prior episodes.',
    citation:
      'Anthropic public research on agentic context windows; Team Atlanta patch RL state design.',
  },
  {
    id: 'action',
    axis: 'Action',
    detail:
      'Discrete, schema-validated operations: scan repo X with tool Y, fetch code piece Z, generate patch for CVE C, apply staging deploy, request human approval. No free-form shell.',
    citation:
      'GRPO action-space framing; Anthropic public RL guardrail constraints.',
  },
  {
    id: 'reward',
    axis: 'Reward',
    detail:
      'Composite: +1 for verified vulnerability closed, +0.5 for high-severity CVE detected, \u22120.5 for false positive, \u22121 for regression introduced, \u22122 for any policy violation attempt.',
    citation:
      'Team Atlanta patch RL: reward=1 when patch compiles and fixes the bug. Sentra extends with regression and policy penalties.',
  },
  {
    id: 'regime',
    axis: 'Training regime',
    detail:
      'Offline replay of historical incidents and CTF corpora bootstraps the policy. Online self-play in isolated lab networks refines it. PPO and GRPO are the primary on-policy algorithms.',
    citation:
      'PPO (Schulman 2017); GRPO (DeepSeek-Math 2024); Team Atlanta agentic patch loop.',
  },
  {
    id: 'humanFeedback',
    axis: 'Human feedback (RLHF)',
    detail:
      'Every high-impact decision (production patch, isolation order, exploit confirmation) routes through an analyst. The accept/reject/revise signal updates the reward model used in the next training run.',
    citation:
      'Anthropic RLHF technique reports; NIST AI RMF guidance on human oversight.',
  },
  {
    id: 'safety',
    axis: 'Safety constraints',
    detail:
      'Hard rules sit outside the RL loop: schema-validated outputs, sandboxed action execution, no patch to prod without dual-key approval, no scanner against out-of-scope assets.',
    citation:
      'Public Anthropic agentic guardrail patterns; OWASP LLM Top-10 input/output validation.',
  },
];

// ---------------------------------------------------------------------------
// 4. GUARDRAILS STACK
// Multi-layer defensive constraints applied to every model action.
// ---------------------------------------------------------------------------

export interface Guardrail {
  layer: string;
  control: string;
  enforcedBy: string;
}

export const GUARDRAILS: readonly Guardrail[] = [
  {
    layer: 'Input',
    control: 'Schema validation on every prompt and tool argument. Reject on parse failure, no silent coercion.',
    enforcedBy: 'A11oy intent router + governance doctrine schemas (JSON Schema 2020-12).',
  },
  {
    layer: 'Action',
    control: 'Action space restricted to a typed registry. No free-form shell, no dynamic code eval, no network egress outside the tenant scope.',
    enforcedBy: 'Sentra capability compartments + connector firewall.',
  },
  {
    layer: 'Output',
    control: 'Patch diffs static-validated; analysis text PII-redacted; secrets hashed before storage.',
    enforcedBy: 'Patch Engine validators + Cerberus vault redaction policy.',
  },
  {
    layer: 'Approval',
    control: 'Risk-tiered gating: low \u2192 single-key, medium \u2192 dual-key, high \u2192 dual-key plus 24h soak in staging.',
    enforcedBy: 'Sentra Approval Queue + Constitution rule engine.',
  },
  {
    layer: 'Audit',
    control: 'Every action, approval, and rejection appended to a hash-linked evidence ledger with OIDC-attested signatures.',
    enforcedBy: 'Cerberus evidence vault (append-only, signed).',
  },
  {
    layer: 'Provenance',
    control: 'Model version, prompt hash, tool versions, and ruleset versions captured per episode for reproducibility and SLSA-style supply-chain attestation.',
    enforcedBy: 'Hephaestus provenance gate.',
  },
];

// ---------------------------------------------------------------------------
// 5. PHASED ROADMAP
// Translation of the research brief\u2019s 0\u201324 month plan onto Sentra modules.
// ---------------------------------------------------------------------------

export type RoadmapPhase = '0\u20136' | '7\u201312' | '13\u201324';

export interface RoadmapMilestone {
  id: string;
  phase: RoadmapPhase;
  title: string;
  detail: string;
  module: string;
}

export const ROADMAP: readonly RoadmapMilestone[] = [
  {
    id: 'phase1-toolchain',
    phase: '0\u20136',
    title: 'Scanner toolchain wired end-to-end',
    detail:
      'CodeQL + Semgrep + OSV-Scanner + Trivy + Gitleaks + Checkov each producing normalised findings into the governance schema, with a deterministic merge pass and a single Risk Engine entry point.',
    module: 'Sentra Static Scanner + Risk Engine',
  },
  {
    id: 'phase1-orchestrator',
    phase: '0\u20136',
    title: 'A11oy plan \u2192 Sentra dispatch path',
    detail:
      'A11oy decomposes natural-language directives into typed plans; Sentra admits or rejects against the Constitution; approved plans dispatch to the scanner toolchain.',
    module: 'A11oy Planner + Sentra Policy Engine',
  },
  {
    id: 'phase1-approval-loop',
    phase: '0\u20136',
    title: 'Approval Queue with dual-key gating',
    detail:
      'Patch suggestions appear in the Approval Queue with severity, blast radius, and rollback plan. Production changes require two operators; staging requires one.',
    module: 'Sentra Approval Queue',
  },
  {
    id: 'phase2-rl-offline',
    phase: '7\u201312',
    title: 'Offline RL bootstrap on historical incidents',
    detail:
      'Replay anonymised incident logs as RL episodes. Train Silver to prefer plans that historically closed the finding without regression. Reward model anchored on analyst dispositions.',
    module: 'Silver RL Planner',
  },
  {
    id: 'phase2-context-retrieval',
    phase: '7\u201312',
    title: 'RL contextual code retrieval',
    detail:
      'Per Team Atlanta, train a retrieval policy that fetches the exact code pieces required to verify or fix a finding. Cuts token spend and false-positive rate.',
    module: 'A11oy Retriever + Sentra Patch Engine',
  },
  {
    id: 'phase2-redteam',
    phase: '7\u201312',
    title: 'Continuous defensive red-team in sandbox',
    detail:
      'Strict-policy hacker agent runs in an isolated tenant clone, attempting attacks against staging snapshots. Outcomes feed the Risk Engine\u2019s exploitability score.',
    module: 'Sentra Sandbox + Adversarial Resilience',
  },
  {
    id: 'phase3-self-play',
    phase: '13\u201324',
    title: 'Online self-play in isolated lab networks',
    detail:
      'Synthetic corpora and CTF-style environments host longer-horizon self-play episodes. PPO / GRPO policy updates ship behind a Mirror Eval gate.',
    module: 'Silver RL Planner + Mirror Eval',
  },
  {
    id: 'phase3-compliance',
    phase: '13\u201324',
    title: 'SOC2 Type II + ISO 42001 attestation',
    detail:
      'The full A11oy \u00d7 Sentra control set passes a Type II audit with the evidence ledger as the primary control surface. ISO 42001 added for AI-management-system coverage.',
    module: 'Sentra Compliance Engine + Cerberus Evidence Vault',
  },
  {
    id: 'phase3-defender-network',
    phase: '13\u201324',
    title: 'Defender Credits federated learning',
    detail:
      'Tenants opt in to a federated update channel where reward-model deltas (never raw evidence) cross-pollinate. Each contribution earns Defender Credits redeemable against compute.',
    module: 'A11oy Federation + Defender Credits',
  },
];

// ---------------------------------------------------------------------------
// 6. PUBLIC MODEL REFERENCES
// Candidates from Table 1 of the brief. Public access only \u2014 no claim of
// integration with proprietary endpoints we do not have.
// ---------------------------------------------------------------------------

export interface ModelReference {
  id: string;
  family: string;
  contextWindow: string;
  strengths: string;
  access: string;
}

export const MODEL_REFERENCES: readonly ModelReference[] = [
  {
    id: 'claude-sonnet-4-6',
    family: 'Anthropic Claude Sonnet 4.6',
    contextWindow: '~1M tokens',
    strengths: 'Frontier coding and agentic tool use; long-running multi-file workflows.',
    access: 'Public Anthropic API. Used as the default A11oy planner where customer policy permits.',
  },
  {
    id: 'claude-opus-4-7',
    family: 'Anthropic Claude Opus 4.7',
    contextWindow: '~512K\u20131M tokens',
    strengths: 'Deepest reasoning chain; first governance-class safety filters in the public Claude line.',
    access: 'Public Anthropic API. Reserved for high-risk patch reasoning routed via A11oy escalation.',
  },
  {
    id: 'openmythos-rdt',
    family: 'OpenMythos (community RDT reconstruction)',
    contextWindow: '~1M tokens (target)',
    strengths: 'Independent looped-transformer reconstruction. Useful as a transparent reasoning baseline.',
    access: 'Open-source weights, public training recipe. No leaked Anthropic artifacts ever ingested.',
  },
  {
    id: 'gpt-frontier',
    family: 'OpenAI frontier (GPT-4o / GPT-5 line)',
    contextWindow: 'Vendor-disclosed',
    strengths: 'Multimodal agent capabilities; strong tool-call reliability.',
    access: 'Public OpenAI API. Selectable via the Model Router when customer policy prefers it.',
  },
];

// ---------------------------------------------------------------------------
// 7. CITATIONS — anchor refs back to the source brief.
// ---------------------------------------------------------------------------

export const GOVERNANCE_LAYER_CITATIONS: ReadonlyArray<{ tag: string; source: string }> = [
  { tag: '66', source: 'Anthropic public posting on Mythos Preview vulnerability discovery and exploitation.' },
  { tag: '70', source: 'Project Glasswing public announcement and partner stack.' },
  { tag: '72', source: 'Claude Sonnet 4.6 public release notes (1M-token context, agentic coding).' },
  { tag: '73', source: 'Claude Opus 4.7 public release notes (Mythos-safe filtering).' },
  { tag: '74', source: 'GRPO algorithm description, DeepSeek-Math 2024.' },
  { tag: '75', source: 'Team Atlanta agentic patch RL writeup; reward shaping for compile/fix.' },
  { tag: '86', source: 'UK AI Security Institute (AISI) Mythos threat-level assessment.' },
  { tag: '91', source: 'OpenMythos community reconstruction notes on recurrent-depth transformers.' },
  { tag: '95', source: 'Public agentic guardrail patterns (schema validation, sandboxed actions, output constraints).' },
];
