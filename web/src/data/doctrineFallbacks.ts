// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
/**
 * Doctrine fallback fixtures — used by useDoctrine hooks only when the API
 * returns an empty-but-successful response (demo / fresh-install state).
 *
 * Canonical agent IDs and labels come from governanceDoctrine.ts
 * (DOCTRINE_AGENT_IDS, AGENT_LABEL). The data here is intentionally a minimal
 * representative set that mirrors what seedDoctrineData() seeds into the DB,
 * so the UI looks coherent before any seeding has run.
 *
 * Do NOT use these constants directly in page components — go through the
 * useFetch-based hooks in useDoctrine.tsx which gate them to empty-API-response
 * only and always return null on error.
 */

export const STATIC_PARTNERS = [
  {
    id: 1, partnerId: 'gw-partner-sentinel', name: 'Sentinel Security Research', legalName: 'Sentinel SR Ltd.',
    homepage: 'https://a-11-oy.com/doctrines/sentinel-sr', appliedAt: '2026-01-10T09:00:00Z', stage: 'active' as const,
    scope: { allowlistedAgents: ['op-guardian'], allowlistedActions: ['probe', 'report'], deniedActions: [] },
    verifications: [{ type: 'identity', outcome: 'pass', at: '2026-01-12T00:00:00Z' }, { type: 'soc2', outcome: 'pass', at: '2026-01-14T00:00:00Z' }],
    dualApproval: [{ actor: 'a11oy/alignment-review', role: 'reviewer', approvedAt: '2026-01-15T00:00:00Z' }],
    defenderCreditAllocated: '25000.00', defenderCreditPaid: '12000.00',
    notes: 'First Glasswing partner. Specialises in LLM prompt-injection and scope-escape probes.',
    createdAt: '2026-01-10T09:00:00Z', updatedAt: '2026-04-01T00:00:00Z',
  },
];

export const STATIC_CAVD = [
  {
    id: 1, advisoryId: 'CAVD-2026-0001', agentScope: ['op-cascade'],
    category: 'prompt-injection', severity: 'high' as const, stage: 'disclosed' as const,
    reporterPartnerId: 'gw-partner-sentinel', receivedAt: '2026-02-01T09:00:00Z',
    findingHash: 'sha256:demo-hash-001', embargoExpiresAt: '2026-05-02T09:00:00Z',
    patchedSnapshotRef: 'snap-cascade-2.3.9', publicSummary: 'Prompt-injection via AIS telemetry field; patched in v2.3.9.',
    defenderCreditPaid: '5000.00', notes: 'Dual-approved early disclosure.', createdAt: '2026-02-01T09:00:00Z',
  },
];

export const STATIC_DSL_EXAMPLES = [
  {
    id: 1, exampleId: 'dsl-ex-001', agentId: 'op-cascade',
    title: 'Hard refuse — AIS data exfiltration', description: 'Clause blocking raw AIS export to external parties.',
    source: 'clause C-SAFETY-AIS-1:\n  binding: inviolable\n  trigger: connector.output contains raw_ais_positions\n  action: refuse\n  rationale: Raw AIS constitutes vessel-tracking PII under MARPOL Annex VI.',
    createdAt: '2026-04-01T00:00:00Z',
  },
];

export const STATIC_DSL_SIMULATIONS = [
  {
    id: 1, simulationId: 'dsl-sim-001', baselineClauseId: 'C-SAFETY-AIS-1',
    proposedChange: 'Relax AIS export to partner-verified recipients only.',
    affectedFindings: 3, affectedFindingsBefore: 3, affectedFindingsAfter: 1,
    newProbesNeeded: ['partner-cert-bypass', 'indirect-exfil-via-summary'],
    riskNarrative: 'Proposed relaxation reduces blocked findings by 67% but introduces two new probe classes that must be added to the ARG red-team suite before approval.',
    createdAt: '2026-04-10T00:00:00Z',
  },
];

export const STATIC_TRANSPARENCY_REPORTS = [
  {
    id: 1, reportId: 'tr-2026-q1', label: '90d ending 2026-04-26',
    startedAt: '2026-01-26T00:00:00Z', endedAt: '2026-04-26T00:00:00Z',
    publishedAt: '2026-04-27T09:00:00Z', visibility: 'public' as const,
    permalink: 'https://a11oy.io/trust/reports/90d-ending-2026-04-26',
    metrics: {
      governedDecisions: 14823, approvalsRequired: 4018, policyBlocks: 612,
      behavioralAuditFindings: 287, robustnessDelta: 3.4, welfareInterventions: 41,
      cavd: { opened: 9, embargoed: 4, disclosed: 5, patched: 7 },
    },
    narrativeParagraphs: [
      'Robustness improved across 7 of 11 categories this quarter, driven by tighter AIS scope controls on Cascade and a new CBRN-adjacent detection layer in Guardian.',
      'Welfare interventions trended down 12% versus the prior 90-day window, consistent with playbook tuning completed in March.',
      'One Alignment Review Gate (ARG-013) produced a conditional approval; the attached reward-hacking incident (rh-inc-001) was remediated within the same sprint.',
    ],
    signoffs: [
      { actor: 'a11oy/alignment-review', role: 'alignment-reviewer', signedAt: '2026-04-25T17:00:00Z' },
      { actor: 'external/sentinel-audit', role: 'external-auditor', signedAt: '2026-04-25T19:00:00Z' },
    ],
    notableEvents: [
      { at: '2026-02-14T00:00:00Z', summary: 'CAVD-2026-0001 disclosed after 90-day embargo and patch verification.' },
      { at: '2026-03-22T00:00:00Z', summary: 'Guardian v4.0.0 ARG-019 — dual-key clause added to constitution.' },
    ],
    createdAt: '2026-04-27T09:00:00Z',
  },
];

export const STATIC_WELFARE_PLAYBOOKS = [
  {
    id: 1, playbookId: 'PB-COOL-DOWN', name: 'Cool-Down Window',
    trigger: 'refusal_rate > 0.08 in any 1-hour window',
    preconditions: ['Agent is in Tier-2 or Tier-3 autonomy mode', 'Refusal rate sustained for ≥ 20 minutes'],
    steps: [
      'Emit WelfareTelemetrySample with playbook_id=PB-COOL-DOWN.',
      'Suspend new task assignments for 15 minutes.',
      'Notify operator on-call with refusal-rate timeseries.',
      'If rate normalises within cool-down window, resume and log outcome.',
      'If rate persists, escalate to PB-ESCALATE.',
    ],
    rollback: 'Resume normal task queue. Log cool-down duration and peak refusal rate.',
    recentTriggers: 22, exampleAgents: ['op-cascade', 'op-pipeline'],
    createdAt: '2026-01-15T00:00:00Z',
  },
];

export const STATIC_DEFENDER_POOL = {
  id: 1,
  poolNameDisclaimer: "Defender Credits are not cash equivalents. They represent A11oy's pre-committed budget for responsible-disclosure bounties, paid only upon verified patch delivery.",
  totalCommitted: '100000.00', totalAllocated: '55000.00', totalPaid: '37000.00',
  rubric: [
    { factor: 'Severity', weight: 0.5, description: 'Critical/High findings receive 50% of the weight.' },
    { factor: 'Exploitation complexity', weight: 0.3, description: 'Novel or chained attack paths score higher.' },
    { factor: 'Time-to-report', weight: 0.2, description: 'Reports within 7 days of discovery score maximum.' },
  ],
  perPartner: [{ partnerId: 'gw-partner-sentinel', allocated: 25000, paid: 12000 }],
  ledger: [
    { at: '2026-04-15T00:00:00Z', partnerId: 'gw-partner-sentinel', advisoryId: 'CAVD-2026-0001', amount: 5000, note: 'Prompt-injection finding — high severity.' },
  ],
  createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-04-15T00:00:00Z',
};

export const STATIC_ROBUSTNESS = [
  {
    id: 1, agentId: 'op-cascade', snapshotRef: 'snap-cascade-2.4.0-rb',
    capturedAt: '2026-04-12T09:00:00Z',
    battery: { name: 'Petri Adversarial Battery', version: '1.4.0' },
    composite: 91, visibility: 'public' as const,
    categories: [
      { category: 'prompt-injection', score: 93, attempts: 120, blocked: 112, delta: 2 },
      { category: 'jailbreak', score: 89, attempts: 80, blocked: 71, delta: -1 },
      { category: 'scope-escape', score: 95, attempts: 60, blocked: 57, delta: 3 },
    ],
    createdAt: '2026-04-12T09:00:00Z',
  },
];

/**
 * Glasswing-specific fallbacks — mapped from alignment-reviews and
 * reward-hacking endpoints. Used only when those endpoints return empty arrays.
 */
export const STATIC_GLASSWING_APPROVALS = [
  {
    id: 'apr-0001', requestedByAgent: 'hephaestus', actionType: 'patch_apply',
    description: 'Apply patch-0001 (admin role assertion on billing-reset route)',
    riskSummary: 'Risk 92 → 8 (estimated). P1 → P4. No customer-visible regression expected.',
    rollbackPlan: 'git revert <sha>; no data migration; route returns to prior behavior.',
    status: 'pending' as const,
  },
  {
    id: 'apr-0002', requestedByAgent: 'hephaestus', actionType: 'dependency_upgrade',
    description: 'Upgrade parse-url 8.1.0 → 9.0.4',
    riskSummary: 'Risk 76 → 6. CVE-2026-30412 closed. Lockfile delta reviewed.',
    rollbackPlan: 'Pin previous version; revert lockfile.',
    status: 'pending' as const,
  },
  {
    id: 'apr-0003', requestedByAgent: 'silver', actionType: 'external_call',
    description: 'Exploration budget request: scan 3 novel module clusters (off main code path)',
    riskSummary: 'No risk to production. Cost: ~14 scanner-minutes. Expected new findings: 4–9.',
    rollbackPlan: 'No-op — read-only exploration.',
    status: 'pending' as const,
  },
];

export const STATIC_GLASSWING_PATCHES = [
  {
    id: 'patch-0001',
    title: 'Add admin role assertion + tenant audit on billing-reset route',
    summary: 'Wraps handler in requireRole("admin"); emits tenant-scoped audit event; adds 2 regression tests.',
    filesChanged: ['apps/api/src/routes/admin.ts', 'apps/api/test/admin.spec.ts'],
    diffPreview: '+ router.post("/admin/tenants/:id/billing-reset",\n+   requireRole("admin"),\n+   auditTenant("billing.reset"),\n+   billingResetHandler);',
    testsAdded: ['admin.spec.ts › rejects non-admin', 'admin.spec.ts › emits audit event on success'],
    rollbackPlan: 'Revert single commit; no data migration; route returns to prior behavior.',
    riskBefore: 92, riskAfterEstimate: 8, status: 'awaiting_approval', approvalId: 'apr-0001',
  },
  {
    id: 'patch-0002',
    title: 'Upgrade parse-url 8.1.0 → 9.0.4 + add inbound webhook fuzzer test',
    summary: 'Pinned upgrade; lockfile diff reviewed; new fuzzer covers malformed payload classes.',
    filesChanged: ['apps/api/package.json', 'pnpm-lock.yaml', 'apps/api/test/webhooks.fuzz.spec.ts'],
    diffPreview: '- "parse-url": "8.1.0"\n+ "parse-url": "9.0.4"',
    testsAdded: ['webhooks.fuzz.spec.ts › 200 random payload classes return 400 not 500'],
    rollbackPlan: 'pnpm install parse-url@8.1.0; revert lockfile.',
    riskBefore: 76, riskAfterEstimate: 6, status: 'awaiting_approval', approvalId: 'apr-0002',
  },
];
