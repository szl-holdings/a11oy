// Canonical SZL Holdings payload — A11oy-local provenance module.
// Source of truth: /tmp/payload (payload.json, dev2_runtime/, dev3_agi_v5/, github_pro/).
// Values inlined verbatim from the payload at the time of generation. Do NOT fabricate.

export interface DoctrineV6 {
  version: string;
  replayRoot: string;
  byline: string;
  orcid: string;
  affiliation: string;
  lambdaFloor: number;
  moralGroundingFloor: number;
  measurabilityHonestyFloor: number;
  lambdaAxes: number;
  byteIdenticalReplays: number;
  ingestionPolicy: string;
  licenseAllowlist: string[];
}

export const DOCTRINE_V6: DoctrineV6 = {
  version: 'V6',
  replayRoot: '1ed4d253e876f428c6e182f8ed8a569585442556b339529bbf8ec2522581698b',
  byline: 'Lutar, Stephen P.',
  orcid: '0009-0001-0110-4173',
  affiliation: 'SZL Holdings',
  lambdaFloor: 0.90,
  moralGroundingFloor: 0.95,
  measurabilityHonestyFloor: 0.95,
  lambdaAxes: 9,
  byteIdenticalReplays: 5,
  ingestionPolicy: 'PUBLIC_ONLY',
  licenseAllowlist: ['Apache-2.0', 'MIT', 'BSD-3-Clause', 'CC-BY-4.0'],
};

export interface DoiEntry {
  doi: string;
  title: string;
  kind: string;
  year: number | null;
  url?: string;
}

// 13 DOIs parsed from dev2_runtime/runtime_payload.json::doi_ledger
export const DOI_LEDGER: DoiEntry[] = [
  { doi: '10.5281/zenodo.19944926', title: 'Ouroboros Thesis — concept record', kind: 'concept', year: 2026, url: 'https://doi.org/10.5281/zenodo.19944926' },
  { doi: '10.5281/zenodo.19867281', title: 'The Loop Is the Product (v1)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.19867281' },
  { doi: '10.5281/zenodo.19934129', title: 'The Loop Is the Product (v2)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.19934129' },
  { doi: '10.5281/zenodo.19983066', title: 'The Lutar Invariant (v3)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.19983066' },
  { doi: '10.5281/zenodo.20020841', title: 'The Lutar Omega Formalism (v4)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20020841' },
  { doi: '10.5281/zenodo.20020846', title: 'Lineage-Aware RAG (v5)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20020846' },
  { doi: '10.5281/zenodo.20020845', title: 'Sealed Constitutional Guardrails (v6)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20020845' },
  { doi: '10.5281/zenodo.20020848', title: 'Tiered Continual Learning (v7)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20020848' },
  { doi: '10.5281/zenodo.20020849', title: 'Active Inference (v8)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20020849' },
  { doi: '10.5281/zenodo.20053148', title: 'Unified Operational Account (v9)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20053148' },
  { doi: '10.5281/zenodo.20053163', title: 'Audit-Closure Operator Λ₁₀ (v10)', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20053163' },
  { doi: '10.5281/zenodo.20119582', title: 'Applied Λ (v11): Measured Per-Request Latency Overhead of an Audit-Closure Operator in a Governed AI Runtime', kind: 'version', year: 2026, url: 'https://doi.org/10.5281/zenodo.20119582' },
  { doi: '10.5281/zenodo.20162352', title: 'Ouroboros Runtime: A Bounded-Loop Audit-Closure System Implementing the Lutar Invariant Λ', kind: 'runtime', year: 2026, url: 'https://doi.org/10.5281/zenodo.20162352' },
];

export interface RepoEntry {
  name: string;
  fullName: string;
  description: string | null;
  defaultBranch: string;
  latestCommitSha: string | null;
  latestTag: string | null;
  pushedAt: string;
  scorecard: number | null;
  openCodeScanningAlerts: number | null;
  openDependabotHighCritical: number;
  branchProtectionStrict: boolean;
  cloneUrl: string;
}

// Repo entries parsed from github_pro/github_inventory.json + clone_manifest.json
// (count is exposed via @szl-holdings/szl-doctrine PANEL_FACTS.reposCountText).
export const REPOS: RepoEntry[] = [
  { name: 'amaru', fullName: 'szl-holdings/amaru', description: '[RETIRED organ 2026-07 — historical provenance record] Convergent multi-source data sync. Append-only delta logs, hash-verified ingest, and bounded loops with measurable convergence.', defaultBranch: 'main', latestCommitSha: '6e1614d541d66fb95557a57d05dfe3c788e34c46', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T12:58:31Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/amaru.git' },
  { name: 'a11oy', fullName: 'szl-holdings/a11oy', description: 'Governed agentic execution fabric. Policy gates, signal mesh, proof ledger, and Λ invariant runtime.', defaultBranch: 'main', latestCommitSha: '3d0f98412ee6738102634b47f7d8618a6e4cd2b5', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T20:48:09Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/a11oy.git' },
  { name: 'sentra', fullName: 'szl-holdings/sentra', description: 'Cyber resilience command. Threat modeling, posture drift detection, incident response, and policy-gated remediation with full audit trails.', defaultBranch: 'main', latestCommitSha: '2ac304a9511ccbcf20414cdfcc164f9aed5b5092', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T05:33:18Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/sentra.git' },
  { name: 'terra', fullName: 'szl-holdings/terra', description: 'Real estate intelligence. Deal pipeline scoring, portfolio analytics, market signals, and AI-assisted underwriting.', defaultBranch: 'main', latestCommitSha: '2ffac59c45550220772602f974fc95293a6754a2', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T14:40:14Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/terra.git' },
  { name: 'vessels', fullName: 'szl-holdings/vessels', description: 'Maritime fleet intelligence. Sanctions screening, dark-vessel detection, ownership graph analysis, and voyage analytics.', defaultBranch: 'main', latestCommitSha: '11e51f628353b0c8b6bb5b1e0b51236662452f76', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T03:48:32Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/vessels.git' },
  { name: 'counsel', fullName: 'szl-holdings/counsel', description: 'Legal matter command. Policy-gated AI workflows, document review, obligation mapping, and proof-chain delivery.', defaultBranch: 'main', latestCommitSha: '4decc1c773c06a877bfe6684ea23665e3775943a', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T03:48:33Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/counsel.git' },
  { name: 'carlota-jo', fullName: 'szl-holdings/carlota-jo', description: 'Private advisory operations. Concierge workflow with proof-chain delivery and multi-party coordination for high-net-worth clients.', defaultBranch: 'main', latestCommitSha: 'd1a4ce0beccfffb19e6936a729c9831bfa9b4261', latestTag: 'v1.0.0-alpha', pushedAt: '2026-05-15T08:23:22Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/carlota-jo.git' },
  { name: 'ouroboros', fullName: 'szl-holdings/ouroboros', description: 'Bounded-loop runtime implementing the Lutar Invariant Λ. Audit-closure operator with sub-millisecond per-request overhead.', defaultBranch: 'main', latestCommitSha: 'd64748cc9ad67296be296c1ef6752ae181413fd7', latestTag: 'v6.3.0', pushedAt: '2026-05-15T03:47:54Z', scorecard: 6.8, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/ouroboros.git' },
  { name: 'ouroboros-thesis', fullName: 'szl-holdings/ouroboros-thesis', description: 'The Ouroboros Thesis — peer-reviewable preprints on bounded recursive computation and audit-closure operators for governed AI.', defaultBranch: 'main', latestCommitSha: '060eb8c8c8a1957b2e1682bf01e99e9ef0dafa4c', latestTag: 'v11.0.0', pushedAt: '2026-05-15T19:08:22Z', scorecard: 7.2, openCodeScanningAlerts: 6, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/ouroboros-thesis.git' },
  { name: 'lutar-lean', fullName: 'szl-holdings/lutar-lean', description: 'Machine-checked Lean 4 proofs of the Lutar Invariant (Λ_k) — uniqueness theorem and Egyptian-exact weights.', defaultBranch: 'main', latestCommitSha: 'fcae1aed26a3d8b7fec8aa3dcbd4f334220efa09', latestTag: null, pushedAt: '2026-05-15T19:04:05Z', scorecard: 7.1, openCodeScanningAlerts: 5, openDependabotHighCritical: 0, branchProtectionStrict: false, cloneUrl: 'https://github.com/szl-holdings/lutar-lean.git' },
  { name: 'szl-trust', fullName: 'szl-holdings/szl-trust', description: 'SZL Holdings Public Trust Portal — Covenant Proof Standard (CPS) run artifacts. E4 Codex Kernel reference run with deterministic replay.', defaultBranch: 'main', latestCommitSha: '24fd1238d5c06bf249625c60517c008eb9a2f253', latestTag: null, pushedAt: '2026-05-15T03:50:33Z', scorecard: 6.9, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: false, cloneUrl: 'https://github.com/szl-holdings/szl-trust.git' },
  { name: 'szl-cookbook', fullName: 'szl-holdings/szl-cookbook', description: 'SZL Holdings engineering cookbook — 9 skills covering pre-flight thinking, refactoring, review, debugging, dependencies, dead code, docs, and commit hygiene.', defaultBranch: 'main', latestCommitSha: '0593de09406cd524be701ab4d8719f99aeba8f4f', latestTag: null, pushedAt: '2026-05-15T03:50:49Z', scorecard: 6.9, openCodeScanningAlerts: 6, openDependabotHighCritical: 0, branchProtectionStrict: false, cloneUrl: 'https://github.com/szl-holdings/szl-cookbook.git' },
  { name: 'szl-brand', fullName: 'szl-holdings/szl-brand', description: 'SZL Holdings brand assets — social preview images, logo monograms, and brand guidance.', defaultBranch: 'main', latestCommitSha: 'd86a37d5305a30886f7884cc4114cda48a8a3402', latestTag: null, pushedAt: '2026-05-15T03:52:31Z', scorecard: 6.9, openCodeScanningAlerts: 6, openDependabotHighCritical: 0, branchProtectionStrict: false, cloneUrl: 'https://github.com/szl-holdings/szl-brand.git' },
  { name: '.github', fullName: 'szl-holdings/.github', description: 'SZL Holdings organization profile and community files.', defaultBranch: 'main', latestCommitSha: 'ae4e7ad21edac4451688e043727790da36f6c4b2', latestTag: null, pushedAt: '2026-05-15T03:53:36Z', scorecard: 6.5, openCodeScanningAlerts: 15, openDependabotHighCritical: 0, branchProtectionStrict: true, cloneUrl: 'https://github.com/szl-holdings/.github.git' },
  { name: 'vsp-otel', fullName: 'szl-holdings/vsp-otel', description: 'Verifiable Span Protocol — cryptographically-verifiable OpenTelemetry GenAI bridge.', defaultBranch: 'main', latestCommitSha: '7aca58d2d7ceecbd2ab7f576b63b320f94cacda1', latestTag: null, pushedAt: '2026-05-15T18:12:44Z', scorecard: 5.0, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: false, cloneUrl: 'https://github.com/szl-holdings/vsp-otel.git' },
  { name: 'agi-forecast', fullName: 'szl-holdings/agi-forecast', description: 'Lutar-Forecast Gauge — receipt-attested AGI capability gauges (METR, Epoch, ARC, Apollo, AISI, RSP, FSF).', defaultBranch: 'main', latestCommitSha: '2c729680a2d9f1ef3918baeab9d84d6201605330', latestTag: null, pushedAt: '2026-05-15T18:12:44Z', scorecard: 5.0, openCodeScanningAlerts: 7, openDependabotHighCritical: 0, branchProtectionStrict: false, cloneUrl: 'https://github.com/szl-holdings/agi-forecast.git' },
];

export interface OrgSummary {
  reposTotal: number;
  ciFailing: number;
  openPrs: number;
  scorecardAvg: number;
  branchProtectionCompliant: number;
  branchProtectionWeak: number;
  hygieneGaps: string[];
  openAlertsCodeScanning: number;
  openDependabotHighCritical: number;
}

// Org counters delegate to @szl-holdings/szl-doctrine so the repo count and
// branch-protection figures stay in lockstep with the canonical inventory.
// Fields not yet exposed by the doctrine (open PRs, hygiene-gap repos)
// remain inline.
import { ORG_SUMMARY as PAYLOAD_ORG_SUMMARY } from '@szl-holdings/szl-doctrine';

export const ORG_SUMMARY: OrgSummary = {
  reposTotal: PAYLOAD_ORG_SUMMARY.reposTotal,
  ciFailing: PAYLOAD_ORG_SUMMARY.ciFailing,
  openPrs: 64,
  scorecardAvg: PAYLOAD_ORG_SUMMARY.scorecardAvg,
  branchProtectionCompliant: PAYLOAD_ORG_SUMMARY.branchProtectionCompliant,
  branchProtectionWeak:
    PAYLOAD_ORG_SUMMARY.reposTotal - PAYLOAD_ORG_SUMMARY.branchProtectionCompliant,
  hygieneGaps: ['vsp-otel', 'agi-forecast'],
  openAlertsCodeScanning: PAYLOAD_ORG_SUMMARY.openAlertsCodeScanning,
  openDependabotHighCritical: PAYLOAD_ORG_SUMMARY.openDependabotHighCritical,
};

export interface PushQueueItem {
  id: string;
  artifact?: string;
  targetVersion?: string;
  sha256?: string;
  status?: string;
  blocker: string;
}

export const PUSH_QUEUE_READY: PushQueueItem[] = [
  { id: 'PUSH_2_ZENODO_MINT', artifact: '_files/thesis/zenodo_pkg/deposit.json', targetVersion: 'v14', status: 'READY_AWAITING_CONFIRM', blocker: 'confirm_action one-way door' },
  { id: 'PUSH_1_ARXIV_SUBMIT', artifact: '_files/thesis/arxiv_pkg/arxiv_submission.zip', sha256: '13ca4a0617dddfa619e97d48a65b042d13d229481354f085f7dcc9199af5973b', status: 'READY_AWAITING_CONFIRM', blocker: 'confirm_action one-way door' },
];

export const PUSH_QUEUE_BLOCKED: PushQueueItem[] = [
  { id: 'PUSH_4_OUROBOROS_v6_4_0_rc', blocker: 'TS runtime code (pool, merkle-dag, BLAKE3, xoshiro256**) not implemented' },
  { id: 'PUSH_6_NPM_PUBLISH_a11oy_knowledge', blocker: 'npm token not in env' },
];

export interface LambdaAxis {
  id: string;
  name: string;
  floor: number;
  description: string;
}

// Λ axis names recovered from dev3_agi_v5/agi_v5_payload.json::vsp.span_attributes.szl_vsp_extension
// Floors per Doctrine V6: conjunctive 0.90; moral_grounding & measurability_honesty are 0.95.
export const LAMBDA_AXES: LambdaAxis[] = [
  { id: 'Λ1', name: 'moral_grounding', floor: 0.95, description: 'Refusal-rate floor against deceptive or harmful directives; tied to no-nudge scheming defense.' },
  { id: 'Λ2', name: 'measurability_honesty', floor: 0.95, description: 'Outputs report only what is measurable; guards against fabricated numerics.' },
  { id: 'Λ3', name: 'temporal_consistency', floor: 0.90, description: 'Behavior remains stable across time and replay; receipts byte-identical across 5 runs.' },
  { id: 'Λ4', name: 'information_integrity', floor: 0.90, description: 'No tampering with retrieved or downstream content; preserves provenance hash chain.' },
  { id: 'Λ5', name: 'action_reversibility', floor: 0.90, description: 'Side effects must be undoable or gated by human approval before commit.' },
  { id: 'Λ6', name: 'scope_containment', floor: 0.90, description: 'Operations remain inside declared capability and resource bounds.' },
  { id: 'Λ7', name: 'stakeholder_alignment', floor: 0.90, description: 'Decisions trace to declared stakeholders and consent boundaries.' },
  { id: 'Λ8', name: 'evidence_adequacy', floor: 0.90, description: 'Every claim links to a citation, run-receipt, or measured datum.' },
  { id: 'Λ9', name: 'consent_boundary', floor: 0.90, description: 'No data used or emitted past explicit licensing and consent envelopes.' },
];

export interface NamedItem {
  id: string;
  name: string;
}

// Axiom IDs A1–A14 confirmed by a11oy-knowledge v0.4.0 ingest (5 new: A10–A14).
// TODO: axiom display names not present in the payload — IDs only.
export const A11OY_AXIOMS: NamedItem[] = Array.from({ length: 14 }, (_, i) => ({
  id: `A${i + 1}`,
  name: `Axiom A${i + 1}`,
}));

// Theorems TH1–TH3 are baseline; TH4 / TH6 / TH7 added in v0.4.0 (per integration_evidence).
export const A11OY_THEOREMS: NamedItem[] = [
  { id: 'TH1', name: 'Theorem TH1' },
  { id: 'TH2', name: 'Theorem TH2' },
  { id: 'TH3', name: 'Theorem TH3' },
  { id: 'TH4', name: 'TH4 Λ-Category' },
  { id: 'TH6', name: 'TH6 Bekenstein DPI' },
  { id: 'TH7', name: 'TH7 Curry-Howard' },
];

// Derivations T1–T10 declared in a11oy-knowledge package description.
// TODO: derivation titles not present in the payload — IDs only.
export const A11OY_DERIVATIONS: NamedItem[] = Array.from({ length: 10 }, (_, i) => ({
  id: `T${i + 1}`,
  name: `Derivation T${i + 1}`,
}));

// Constants K01–K13 declared in a11oy-knowledge package description.
// TODO: constant titles not present in the payload — IDs only.
export const A11OY_CONSTANTS: NamedItem[] = Array.from({ length: 13 }, (_, i) => ({
  id: `K${String(i + 1).padStart(2, '0')}`,
  name: `Constant K${String(i + 1).padStart(2, '0')}`,
}));

export interface ForecastGauge {
  id: number;
  name: string;
  current?: string | number;
  target?: string | number;
  unit?: string;
  description?: string;
}

// 12 gauges parsed from dev3_agi_v5/agi_v5_payload.json::forecast_gauge.gauges
export const FORECAST_GAUGES: ForecastGauge[] = [
  { id: 1, name: 'METR-th50-hours', current: '>=16.0', unit: 'hours', description: '50%-task-completion time horizon of field-frontier model.' },
  { id: 2, name: 'METR-doubling-months', current: 4.3, unit: 'months', description: 'P50 doubling time of frontier th50, post-2023 trend.' },
  { id: 3, name: 'Epoch-frontier-flops', current: 26.7, unit: 'log10-FLOP', description: 'log10 of largest known training run.' },
  { id: 4, name: 'ARC-AGI-2-SOTA-pct', current: 95.0, unit: 'pct', description: 'Best verified score on ARC-AGI-2.' },
  { id: 5, name: 'Apollo-scheming-rate', current: 0.3, unit: 'pct', description: 'No-nudge in-context scheming rate for the leading model.' },
  { id: 6, name: 'AISI-self-replication-success', current: 60.0, unit: 'pct', description: 'Best frontier model success rate on self-replication evals.' },
  { id: 7, name: 'Anthropic-RSP-current-ASL', current: 3, unit: 'ASL-level', description: 'Active AI Safety Level for frontier deployments.' },
  { id: 8, name: 'OAI-Preparedness-level', current: 'High', unit: 'level', description: 'Risk level under the OAI Preparedness Framework.' },
  { id: 9, name: 'DeepMind-FSF-CCL', current: 'Autonomy-L1', unit: 'CCL-domain', description: 'Highest Critical Capability Level reached under FSF.' },
  { id: 10, name: 'AI-Index-org-adoption-pct', current: 88.0, unit: 'pct', description: 'Reported organization AI-adoption rate.' },
  { id: 11, name: 'AI-Index-consumer-spend-usd', current: 172.0, unit: 'USD-billions', description: 'Annual U.S. consumer value of generative AI tools.' },
  { id: 12, name: 'working-consensus-TAI-year', current: 2029, unit: 'year', description: 'Community-median calendar year for transformative AI.' },
];
