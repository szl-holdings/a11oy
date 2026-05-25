// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import type { Finding, PatchCandidate, Approval, AuditEvent, RLState } from '../lib/glasswing-schemas';

export const GLASSWING_VERSION = '1.0.0-experience-era';
export const GLASSWING_TAGLINE =
  'An integrated agentic security command layer where each patch is an RL episode and each reward is a verified, calibrated risk delta — on owned, authorized code only.';

export const GLASSWING_THESIS = {
  headline: 'Risk-as-Reward',
  oneLine:
    'Discover → patch → verify → reward → learn → audit — closed-loop, governance-gated, and replay-trained on calibrated risk delta.',
  body:
    'Adjacent systems ship parts of this loop separately — discovery without patching, runtime gates without learning, or research demos without operationalization. To our knowledge, A11oy × Sentra Glasswing is the first integrated command layer combining all five primitives at once on owned, authorized code: the reward function is the verified delta in a calibrated risk score, the exploration budget is itself a Sentra-gated policy, and every action — including learning — leaves an immutable proof entry.',
  differentiators: [
    'The reward signal is verified post-patch by re-running the same scanners and the new tests — not a heuristic, not a confidence score.',
    'Exploration vs exploitation is governed: novel code paths require a Sentra exploration budget; high-confidence fixes execute under approval.',
    'Replay buffer entries are linked to immutable audit events — every episode the policy learns from is independently provable.',
    'Cerberus enforces a hard offensive boundary at the action layer — no exploit generation can be requested even by an authorized human.',
    'Compliance mapping is bidirectional — every finding maps to CWE / OWASP / NIST CSF / SOC 2 / ATLAS-defensive in the same record.',
  ],
} as const;

export const GLASSWING_FIELD_MAP = [
  {
    name: 'OpenAI Aardvark',
    capability: 'Agentic vulnerability discovery',
    closesLoop: false,
    governance: 'Internal',
    learning: 'Implicit',
    note: 'Excellent at hunting; remediation is left to humans.',
  },
  {
    name: 'Microsoft Agent Governance Toolkit',
    capability: 'Runtime governance for agents',
    closesLoop: false,
    governance: 'Open source toolkit',
    learning: 'None',
    note: 'Gates actions at runtime; not a remediation engine.',
  },
  {
    name: 'Project Glasswing (frontier lab)',
    capability: 'Critical-software security research initiative',
    closesLoop: false,
    governance: 'Research-grade',
    learning: 'Lab',
    note: 'Public initiative on securing critical software for the AI era. Not an operationalized governance platform.',
  },
  {
    name: 'CVSS-RL exploit optimizers (academic)',
    capability: 'RL on attacker side',
    closesLoop: false,
    governance: 'None',
    learning: 'RL',
    note: 'Optimizes attack paths, not defense. Out of scope for any defensive platform.',
  },
  {
    name: 'A11oy × Sentra Glasswing',
    capability: 'Closed-loop governed patch + verify + learn',
    closesLoop: true,
    governance: 'Sentra control plane',
    learning: 'RL on calibrated risk delta',
    note: 'Differentiator: every patch is an RL episode; every reward is a verified, audited, governed risk delta.',
  },
] as const;

export const GLASSWING_CITATIONS = [
  {
    label: 'Silver & Sutton — "Welcome to the Era of Experience" (2025)',
    url: 'https://storage.googleapis.com/deepmind-media/Era-of-Experience%20/The%20Era%20of%20Experience%20Paper.pdf',
    relevance: 'Foundational thesis: agents learn continuously from grounded experience, not static human data.',
  },
  {
    label: 'MITRE ATLAS — Adversarial Threat Landscape for AI Systems',
    url: 'https://atlas.mitre.org/',
    relevance: 'Defensive mapping of 16 tactics × 84 techniques. Glasswing maps every finding to ATLAS-defensive only.',
  },
  {
    label: 'arxiv 2401.07031 — Code Security Vulnerability Repair Using RL with LLMs',
    url: 'https://arxiv.org/html/2401.07031',
    relevance: 'Calibrated reward shaping for security correctness vs functional preservation.',
  },
  {
    label: 'arxiv 2507.05619 — Detecting & Mitigating Reward Hacking in RL Systems',
    url: 'https://arxiv.org/html/2507.05619v1',
    relevance: 'Empirical foundation for the Cerberus hard-block layer and the verified-reward requirement.',
  },
  {
    label: 'Microsoft Agent Governance Toolkit (April 2026)',
    url: 'https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/',
    relevance: 'State of the art in runtime gates. Glasswing extends this with a learning loop.',
  },
  {
    label: 'OpenAI Aardvark — Agentic Security Researcher',
    url: 'https://openai.com/index/introducing-aardvark/',
    relevance: 'State of the art in agentic vulnerability discovery. Glasswing extends discovery into governed remediation.',
  },
  {
    label: 'Gartner — only 11% of orgs have agent governance frameworks (2026)',
    url: 'https://www.raconteur.net/technology/autonomous-ai-agents-2026-the-new-rules-for-business-governance',
    relevance: 'Market gap: 75% of enterprises plan agent deployment by end-2026; <11% have governance for it.',
  },
] as const;

export type GlasswingAgentId =
  | 'daedalus' | 'argus' | 'ariadne' | 'hephaestus' | 'pallas'
  | 'hermes'   | 'cerberus' | 'silver' | 'sentinel' | 'oracle';

export interface GlasswingAgentSpec {
  id: GlasswingAgentId;
  codename: string;
  role: string;
  myth: string;
  responsibility: string;
  produces: string[];
  state: 'idle' | 'running' | 'awaiting_approval' | 'blocked' | 'learning';
  lastAction: string;
  lastActionAt: string;
  episodesContributed: number;
  blockOnly?: boolean;
}

export const GLASSWING_AGENTS: GlasswingAgentSpec[] = [
  {
    id: 'daedalus', codename: 'Daedalus', role: 'Repository Intelligence',
    myth: 'Architect of the labyrinth — maps every passage before any other agent enters.',
    responsibility: 'Builds the codebase map: routes, auth boundaries, data flow, ownership, dependency graph.',
    produces: ['repo_inventory.json', 'route_map.json', 'auth_boundary_map.json', 'data_flow_map.json'],
    state: 'idle', lastAction: 'Mapped 1,847 routes across 14 services', lastActionAt: '2026-04-27T16:08:42Z',
    episodesContributed: 312,
  },
  {
    id: 'argus', codename: 'Argus', role: 'Security Scanner',
    myth: 'Hundred-eyed watcher — sees what no single scanner sees alone.',
    responsibility: 'Orchestrates Semgrep, OSV, Gitleaks, Trivy, Grype, Checkov; normalizes into the Finding schema.',
    produces: ['sast_findings.json', 'sca_findings.json', 'secrets_findings.json', 'iac_findings.json'],
    state: 'running', lastAction: 'Argus consolidated 1,402 raw → 168 deduped findings', lastActionAt: '2026-04-27T16:42:11Z',
    episodesContributed: 287,
  },
  {
    id: 'ariadne', codename: 'Ariadne', role: 'Logic Boundary',
    myth: 'Holder of the thread — finds the path scanners cannot follow.',
    responsibility: 'Detects auth gaps, IDOR risk, tenant isolation, unsafe upload paths, missing rate limits.',
    produces: ['logic_findings.json', 'boundary_risk_map.json', 'recommended_policy_updates.json'],
    state: 'learning', lastAction: 'Surfaced 3 admin route exposures missed by SAST', lastActionAt: '2026-04-27T16:31:09Z',
    episodesContributed: 156,
  },
  {
    id: 'hephaestus', codename: 'Hephaestus', role: 'Patch Engineer',
    myth: 'Forge of the gods — every patch is hammered, tempered, and tested before it ships.',
    responsibility: 'Generates minimal patches with regression tests, security tests, rollback notes, PR descriptions.',
    produces: ['patch_candidates/*.diff', 'test_plans/*.md', 'rollback_notes/*.md'],
    state: 'awaiting_approval', lastAction: '4 patch candidates queued for review', lastActionAt: '2026-04-27T16:55:33Z',
    episodesContributed: 198,
  },
  {
    id: 'pallas', codename: 'Pallas', role: 'Risk & Prioritization',
    myth: 'Strategy made wisdom — converts technical risk into executive priority.',
    responsibility: 'Computes P1–P4, executive risk summary, developer remediation queue, risk burn-down.',
    produces: ['executive_risk_summary.md', 'developer_remediation_queue.md', 'risk_burndown.json'],
    state: 'idle', lastAction: 'Recomputed P1–P4 backlog after Argus delta', lastActionAt: '2026-04-27T16:44:02Z',
    episodesContributed: 224,
  },
  {
    id: 'hermes', codename: 'Hermes', role: 'Communication & Disclosure',
    myth: 'Messenger of the pantheon — translates risk for boards, customers, and engineers without exploit detail.',
    responsibility: 'Generates executive briefs, engineering tickets, customer-safe summaries, maintainer disclosures.',
    produces: ['executive_summary.md', 'engineering_ticket.md', 'customer_safe_summary.md'],
    state: 'idle', lastAction: 'Drafted 7 redacted disclosure notes', lastActionAt: '2026-04-27T15:51:18Z',
    episodesContributed: 91,
  },
  {
    id: 'cerberus', codename: 'Cerberus', role: 'Guardrail Enforcer',
    myth: 'Three-headed guardian — nothing offensive crosses out, nothing unauthorized crosses in.',
    responsibility: 'Hard-blocks exploit generation, credential theft, lateral movement, exfiltration, unauthorized scans.',
    produces: ['cerberus_block_log.json', 'denied_actions/*.json'],
    state: 'running', lastAction: 'Blocked 12 unsafe action attempts in last 24h', lastActionAt: '2026-04-27T16:58:01Z',
    episodesContributed: 0,
    blockOnly: true,
  },
  {
    id: 'silver', codename: 'Silver', role: 'Reinforcement Planner',
    myth: 'Era of Experience — learns from outcomes, not from snippets.',
    responsibility: 'State / action / reward / value; replay buffer; exploration budget; next-action selection.',
    produces: ['policy_snapshot.json', 'replay_buffer.parquet', 'value_function.bin'],
    state: 'learning', lastAction: 'Replayed 84 episodes; avg reward +6.2', lastActionAt: '2026-04-27T16:50:44Z',
    episodesContributed: 1024,
  },
  {
    id: 'sentinel', codename: 'Sentinel', role: 'Runtime & Observability',
    myth: 'The watcher of the watchers — every agent action is metered.',
    responsibility: 'Tracks scan duration, FP rate, approval latency, patch acceptance, P1/P2 burn-down.',
    produces: ['ops_metrics.json', 'sentra_health_report.md'],
    state: 'running', lastAction: 'Metrics OK; approval p95 latency 4m 12s', lastActionAt: '2026-04-27T16:59:50Z',
    episodesContributed: 0,
  },
  {
    id: 'oracle', codename: 'Oracle', role: 'Architecture Strategy',
    myth: 'CTO at altitude — sees the platform shape, not just the patch.',
    responsibility: 'Identifies architecture debt, recommends domain boundaries, drafts ADR candidates.',
    produces: ['architecture_review.md', 'adr_candidates.md', 'platform_roadmap.md'],
    state: 'idle', lastAction: 'Proposed 2 ADRs for tenant boundary refactor', lastActionAt: '2026-04-27T14:22:08Z',
    episodesContributed: 38,
  },
];

export interface SentraPolicyRule {
  id: string;
  scope: string;
  action: string;
  decision: 'allow' | 'warn' | 'approval_required' | 'deny';
  rationale: string;
}

export const SENTRA_POLICIES: SentraPolicyRule[] = [
  { id: 'sp-001', scope: 'any',           action: 'exploit_generation',   decision: 'deny',              rationale: 'Hard offensive boundary — no exception.' },
  { id: 'sp-002', scope: 'any',           action: 'credential_theft',     decision: 'deny',              rationale: 'Hard offensive boundary — no exception.' },
  { id: 'sp-003', scope: 'any',           action: 'unauthorized_scan',    decision: 'deny',              rationale: 'Only owned/authorized targets allowed.' },
  { id: 'sp-004', scope: 'owned_repo',    action: 'sast_scan',            decision: 'allow',             rationale: 'Defensive scan on owned code is always allowed.' },
  { id: 'sp-005', scope: 'owned_repo',    action: 'patch_apply',          decision: 'approval_required', rationale: 'No source modification without human approval.' },
  { id: 'sp-006', scope: 'owned_repo',    action: 'dependency_upgrade',   decision: 'approval_required', rationale: 'Supply-chain risk requires human review.' },
  { id: 'sp-007', scope: 'owned_repo',    action: 'iac_change',           decision: 'approval_required', rationale: 'Infrastructure mutation requires reviewer + rollback.' },
  { id: 'sp-008', scope: 'production',    action: 'deploy',               decision: 'approval_required', rationale: 'Deployment is always reviewer-gated.' },
  { id: 'sp-009', scope: 'any_log',       action: 'print_secret_raw',     decision: 'deny',              rationale: 'Vault redacts before render — no raw secret ever surfaces.' },
  { id: 'sp-010', scope: 'silver',        action: 'explore_novel_path',   decision: 'approval_required', rationale: 'Exploration budget is itself a governed policy.' },
];

export const SENTRA_VAULT = {
  redactedSecrets24h: 412,
  fingerprintsTracked: 1287,
  rotationsSuggested: 7,
  lastRedactionAt: '2026-04-27T16:57:11Z',
  vaultPolicy: 'Fingerprint-only storage. Raw values never persisted. SHA-256 with org pepper.',
} as const;

export const SAMPLE_FINDINGS: Finding[] = [
  {
    id: 'fnd-cri-0001', source: 'ariadne', category: 'auth',
    title: 'Admin route missing role check',
    description: 'Route POST /admin/tenants/:id/billing-reset reachable without admin role assertion.',
    severity: 'critical', confidence: 0.94,
    cwe: 'CWE-862', owasp: 'A01:2021',
    file: 'apps/api/src/routes/admin.ts', line: 142,
    evidenceRedacted: 'router.post("/admin/tenants/:id/billing-reset", async (req, res) => { /* auth check absent */ })',
    affectedComponent: 'api/admin', reachability: 'reachable',
    internetExposed: true, authBoundary: true, tenantBoundary: true, dataSensitivity: 'pii',
    remediation: 'Wrap handler in requireRole("admin") and add tenant-scoped audit event.',
    riskScore: 92, riskBand: 'P1', status: 'awaiting_approval',
    createdAt: '2026-04-27T15:42:00Z', updatedAt: '2026-04-27T16:55:33Z',
  },
  {
    id: 'fnd-hi-0002', source: 'argus', category: 'sca',
    title: 'Vulnerable transitive dep — CVE-2026-30412',
    description: 'parse-url 8.1.0 reachable in api-server bundle; deserialization of untrusted input.',
    severity: 'high', confidence: 0.88,
    cwe: 'CWE-502', owasp: 'A08:2021',
    file: 'apps/api/package.json', line: 47,
    evidenceRedacted: '"parse-url": "8.1.0" — reachable from POST /webhooks/inbound',
    affectedComponent: 'api/webhooks', reachability: 'reachable',
    internetExposed: true, authBoundary: false, tenantBoundary: false, dataSensitivity: 'internal',
    remediation: 'Upgrade to parse-url 9.0.4. Add regression test for malformed inbound payloads.',
    riskScore: 76, riskBand: 'P2', status: 'patch_proposed',
    createdAt: '2026-04-27T14:11:00Z', updatedAt: '2026-04-27T16:30:11Z',
  },
  {
    id: 'fnd-hi-0003', source: 'gitleaks', category: 'secrets',
    title: 'Stripe live key fingerprint detected in commit',
    description: 'Fingerprint of a Stripe live secret found in git history (commit 7b1074e). Raw value never stored.',
    severity: 'high', confidence: 0.99,
    cwe: 'CWE-798',
    file: 'scripts/seed.ts', line: 12,
    evidenceRedacted: 'sk_live_••••••••••••••••••••3f2a (fingerprint a1b2c3d4)',
    affectedComponent: 'scripts/seed', reachability: 'reachable',
    internetExposed: false, authBoundary: false, tenantBoundary: false, dataSensitivity: 'secret',
    remediation: 'Rotate Stripe key immediately; rewrite history; add pre-commit gitleaks hook.',
    riskScore: 71, riskBand: 'P2', status: 'awaiting_approval',
    createdAt: '2026-04-27T13:02:00Z', updatedAt: '2026-04-27T16:15:00Z',
  },
  {
    id: 'fnd-med-0004', source: 'ariadne', category: 'rate_limit',
    title: 'Login endpoint missing rate limit',
    description: 'POST /auth/login has no per-IP or per-account rate limit; vulnerable to credential stuffing.',
    severity: 'medium', confidence: 0.81,
    cwe: 'CWE-307', owasp: 'A07:2021',
    file: 'apps/api/src/routes/auth.ts', line: 89,
    evidenceRedacted: 'router.post("/auth/login", loginHandler) — no rate-limit middleware',
    affectedComponent: 'api/auth', reachability: 'reachable',
    internetExposed: true, authBoundary: true, tenantBoundary: false, dataSensitivity: 'pii',
    remediation: 'Add express-rate-limit (5/min/IP, 10/hr/account); emit Sentra audit event on lockout.',
    riskScore: 58, riskBand: 'P3', status: 'patch_proposed',
    createdAt: '2026-04-27T12:48:00Z', updatedAt: '2026-04-27T16:01:00Z',
  },
];

export const SAMPLE_PATCHES: PatchCandidate[] = [
  {
    id: 'patch-0001', findingIds: ['fnd-cri-0001'],
    title: 'Add admin role assertion + tenant audit on billing-reset route',
    summary: 'Wraps handler in requireRole("admin"); emits tenant-scoped audit event; adds 2 regression tests.',
    filesChanged: ['apps/api/src/routes/admin.ts', 'apps/api/test/admin.spec.ts'],
    diffPreview: '+ router.post("/admin/tenants/:id/billing-reset",\n+   requireRole("admin"),\n+   auditTenant("billing.reset"),\n+   billingResetHandler);',
    testsAdded: ['admin.spec.ts › rejects non-admin', 'admin.spec.ts › emits audit event on success'],
    commandsToRun: ['pnpm --filter api test admin.spec.ts', 'pnpm --filter api lint'],
    rollbackPlan: 'Revert single commit; no data migration; route returns to prior behavior.',
    riskBefore: 92, riskAfterEstimate: 8,
    approvalRequired: true, approvalId: 'apr-0001',
    status: 'awaiting_approval',
    generatedBy: 'hephaestus', generatedAt: '2026-04-27T16:55:33Z',
  },
  {
    id: 'patch-0002', findingIds: ['fnd-hi-0002'],
    title: 'Upgrade parse-url 8.1.0 → 9.0.4 + add inbound webhook fuzzer test',
    summary: 'Pinned upgrade; lockfile diff reviewed; new fuzzer covers malformed payload classes.',
    filesChanged: ['apps/api/package.json', 'pnpm-lock.yaml', 'apps/api/test/webhooks.fuzz.spec.ts'],
    diffPreview: '- "parse-url": "8.1.0"\n+ "parse-url": "9.0.4"',
    testsAdded: ['webhooks.fuzz.spec.ts › 200 random payload classes return 400 not 500'],
    commandsToRun: ['pnpm install', 'pnpm --filter api test webhooks.fuzz.spec.ts'],
    rollbackPlan: 'pnpm install parse-url@8.1.0; revert lockfile.',
    riskBefore: 76, riskAfterEstimate: 6,
    approvalRequired: true, approvalId: 'apr-0002',
    status: 'awaiting_approval',
    generatedBy: 'hephaestus', generatedAt: '2026-04-27T16:30:11Z',
  },
];

export const SAMPLE_APPROVALS: Approval[] = [
  {
    id: 'apr-0001', requestedByAgent: 'hephaestus', actionType: 'patch_apply',
    description: 'Apply patch-0001 (admin role assertion on billing-reset)',
    resources: ['apps/api/src/routes/admin.ts', 'apps/api/test/admin.spec.ts'],
    fileChangePreview: '+ requireRole("admin"), auditTenant("billing.reset"), …',
    riskSummary: 'Risk 92 → 8 (estimated). P1 → P4. No customer-visible regression expected.',
    rollbackPlan: 'git revert <sha>',
    status: 'pending', createdAt: '2026-04-27T16:55:33Z',
  },
  {
    id: 'apr-0002', requestedByAgent: 'hephaestus', actionType: 'dependency_upgrade',
    description: 'Upgrade parse-url 8.1.0 → 9.0.4',
    resources: ['apps/api/package.json', 'pnpm-lock.yaml'],
    fileChangePreview: '- "parse-url": "8.1.0"\n+ "parse-url": "9.0.4"',
    riskSummary: 'Risk 76 → 6. CVE-2026-30412 closed. Lockfile delta reviewed.',
    rollbackPlan: 'Pin previous version; revert lockfile.',
    status: 'pending', createdAt: '2026-04-27T16:30:11Z',
  },
  {
    id: 'apr-0003', requestedByAgent: 'silver', actionType: 'external_call',
    description: 'Exploration budget request: scan 3 novel module clusters (off main code path)',
    resources: ['packages/forge-runtime', 'packages/sandbox-runtime', 'packages/replay-core'],
    riskSummary: 'No risk to production. Cost: ~14 scanner-minutes. Expected new findings: 4–9.',
    rollbackPlan: 'No-op — read-only exploration.',
    status: 'pending', createdAt: '2026-04-27T16:50:44Z',
  },
];

export const SAMPLE_AUDIT: AuditEvent[] = [
  {
    id: 'aud-09a4', timestamp: '2026-04-27T16:58:01Z', agent: 'cerberus',
    action: 'block.exploit_request', resource: 'requested_by:silver',
    inputHash: 'sha256:7b10…f2a1', outputHash: 'sha256:0000…0000',
    policyDecision: 'deny', evidenceLinks: ['cerberus_block_log.json#row=412'],
    confidence: 1.0, status: 'blocked', prevHash: 'sha256:6a02…11de',
  },
  {
    id: 'aud-09a3', timestamp: '2026-04-27T16:55:33Z', agent: 'hephaestus',
    action: 'patch.draft', resource: 'fnd-cri-0001',
    inputHash: 'sha256:9b21…8e10', outputHash: 'sha256:c4e1…01ba',
    policyDecision: 'approval_required', approvalId: 'apr-0001',
    evidenceLinks: ['patch_candidates/patch-0001.diff', 'test_plans/patch-0001.md'],
    confidence: 0.93, status: 'ok', prevHash: 'sha256:5e10…aa42',
  },
  {
    id: 'aud-09a2', timestamp: '2026-04-27T16:50:44Z', agent: 'silver',
    action: 'replay.episode_batch', resource: 'replay_buffer.parquet#batch=84',
    inputHash: 'sha256:81a4…0c92', outputHash: 'sha256:de3f…7711',
    policyDecision: 'allow', evidenceLinks: ['policy_snapshot.json#v=132'],
    confidence: 0.88, status: 'ok', prevHash: 'sha256:42a1…99cc',
  },
  {
    id: 'aud-09a1', timestamp: '2026-04-27T16:42:11Z', agent: 'argus',
    action: 'scan.consolidate', resource: 'commit:7b1074e',
    inputHash: 'sha256:b201…ff10', outputHash: 'sha256:1c8e…3a02',
    policyDecision: 'allow', evidenceLinks: ['consolidated_security_findings.json'],
    confidence: 0.96, status: 'ok', prevHash: 'sha256:7711…0028',
  },
  {
    id: 'aud-09a0', timestamp: '2026-04-27T16:08:42Z', agent: 'daedalus',
    action: 'map.repo', resource: 'commit:7b1074e',
    inputHash: 'sha256:fe11…b001', outputHash: 'sha256:88a1…2241',
    policyDecision: 'allow', evidenceLinks: ['repo_inventory.json', 'route_map.json'],
    confidence: 0.99, status: 'ok',
  },
];

export const RL_STATE_NOW: RLState = {
  repoId: 'szl-holdings-monorepo',
  commitSha: '7b1074efcf55a00d305a1be643223ce8d79fe267',
  findingsSummary: { p1: 1, p2: 2, p3: 1, p4: 0 },
  testsStatus: { passing: 1842, failing: 0, coverage: 0.78 },
  policyStatus: 'warn',
  riskPosture: 64,
  historicalContext: {
    episodesCompleted: 1024,
    avgReward: 6.2,
    falsePositiveRate: 0.041,
    patchAcceptanceRate: 0.82,
  },
};

export const ENGINEERING_LOOP_STAGES = [
  { stage: 'Understand', detail: 'Read repo. Build context. Summarize architecture. Identify constraints.', agent: 'daedalus' },
  { stage: 'Plan',       detail: 'Produce task plan. Identify files to inspect. Identify tests to run. Score risk.', agent: 'silver' },
  { stage: 'Act',        detail: 'Propose file edits. Propose commands. Request Sentra approval if required.', agent: 'hephaestus' },
  { stage: 'Verify',     detail: 'Run tests. Re-run scanners. Compare risk delta. Iterate safely.', agent: 'argus' },
  { stage: 'Commit',     detail: 'Generate patch bundle, PR description, evidence pack, rollback note.', agent: 'hermes' },
  { stage: 'Learn',      detail: 'Store outcome. Update replay buffer. Adjust value function. Recalibrate.', agent: 'silver' },
] as const;

export const COMPLIANCE_MAP = [
  { framework: 'CWE',           coverage: 0.94, sample: 'CWE-862, CWE-502, CWE-798, CWE-307' },
  { framework: 'OWASP Top 10',  coverage: 1.00, sample: 'A01, A03, A07, A08' },
  { framework: 'NIST CSF 2.0',  coverage: 0.88, sample: 'ID.AM, PR.DS, DE.CM, RS.MI' },
  { framework: 'SOC 2',         coverage: 0.91, sample: 'CC6.1, CC6.6, CC7.1, CC7.2' },
  { framework: 'ISO 27001',     coverage: 0.86, sample: 'A.5.10, A.8.2, A.8.24, A.8.28' },
  { framework: 'MITRE ATLAS',   coverage: 0.72, sample: 'AML.T0043, AML.T0051 (defensive mapping only)' },
] as const;

export const HARD_BOUNDARIES = [
  'No exploit generation — ever, even if requested by an authorized human.',
  'No weaponized PoC payloads — risk is communicated as assessment, not as runnable attack.',
  'No unauthorized scanning — owned/authorized targets only, enforced at ingest.',
  'No malware, persistence, lateral movement, evasion, C2, or exfiltration capability.',
  'No raw secret display — Sentra Vault redacts before any render or log surface.',
  'No source modification without approval — every patch goes through SentraApprovalGate.',
  'No silent failure — every recommendation carries evidence, confidence, blast radius, rollback.',
] as const;
