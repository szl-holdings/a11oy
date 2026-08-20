/**
 * SZL Holdings government procurement readiness — operational data layer.
 *
 * Encodes the April 30, 2026 audit prepared for the Empire APEX Accelerator
 * (NYSTEC, Mercy McInnis) covering A11oy, Sentra, and Amaru against:
 *   - NIST AI RMF (Govern, Map, Measure, Manage)
 *   - DoD Responsible AI Tenets (Responsible, Equitable, Traceable,
 *     Reliable, Governable)
 *   - GSAR 552.239-7001 (proposed) — 10 procurement requirements
 *   - SAM.gov registration prerequisites + recommended NAICS codes
 *   - Pre-meeting action items (critical, for-meeting, 30-day)
 *
 * Source of truth: docs/audit/szl-government-readiness.md.
 *
 * All data is deeply frozen, pure, and replay-safe — the same call always
 * returns the same artifact, suitable for audit-grade attestation.
 */

// ---------------------------------------------------------------------------
// Platform identity + readiness scores
// ---------------------------------------------------------------------------
export type GovPlatformId = 'A11oy' | 'Sentra' | 'Amaru';

export interface PlatformReadiness {
  readonly platformId: GovPlatformId;
  readonly purpose: string;
  /** Whole-number readiness score out of 100 from the April 30, 2026 audit. */
  readonly readinessScore: number;
  /** Strength dimensions surfaced in the summary scorecard. */
  readonly scorecard: {
    readonly governance: 'strong' | 'in_progress' | 'gap';
    readonly proofChain: 'strong' | 'in_progress' | 'gap';
    readonly auditability: 'strong' | 'in_progress' | 'gap';
    readonly humanOversight: 'strong' | 'in_progress' | 'gap';
    readonly certPath: 'strong' | 'in_progress' | 'gap';
    readonly certNote: string;
  };
  /** Government-aligned strengths (plain-language capability ↔ alignment). */
  readonly strengths: readonly { readonly capability: string; readonly alignment: string }[];
  /** Best-fit government use cases (where called out in the audit). */
  readonly bestFitUseCases?: readonly string[];
  /** Audit-identified gaps to close before Tuesday's meeting. */
  readonly gaps: readonly string[];
}

export const PLATFORM_READINESS: Readonly<Record<GovPlatformId, PlatformReadiness>> =
  Object.freeze({
    A11oy: Object.freeze({
      platformId: 'A11oy' as GovPlatformId,
      purpose:
        'Orchestration control plane — agent ecosystem brain that routes tasks, enforces governance, powers Sentra and Amaru, and manages the Ouroboros loop kernel.',
      readinessScore: 72,
      scorecard: Object.freeze({
        governance: 'strong',
        proofChain: 'strong',
        auditability: 'strong',
        humanOversight: 'strong',
        certPath: 'in_progress',
        certNote: 'In progress',
      }),
      strengths: Object.freeze([
        Object.freeze({
          capability: 'Append-only trace runtime',
          alignment: 'GSA audit trail and traceability requirements; DoD Traceable tenet',
        }),
        Object.freeze({
          capability: 'Decision receipt system',
          alignment: 'Produce-evidence-on-demand audit requirements',
        }),
        Object.freeze({
          capability: 'Ouroboros loop with delta/consistency gates',
          alignment: 'DoD Reliable and Governable tenets',
        }),
        Object.freeze({
          capability: 'Human approval gate for R3/R4 risk tiers',
          alignment: 'GSA human oversight requirement; DoD Responsible tenet',
        }),
        Object.freeze({
          capability: 'Validator registry with hard stops',
          alignment: 'NIST AI RMF MANAGE function',
        }),
        Object.freeze({
          capability: 'Replay/golden run verification',
          alignment: 'Audit reproducibility requirements',
        }),
        Object.freeze({
          capability: 'Domain pack routing',
          alignment: 'NIST AI RMF MAP function',
        }),
        Object.freeze({
          capability: 'Budget governance',
          alignment: 'Economic stewardship requirements',
        }),
        Object.freeze({
          capability: 'Primary-source hash chain (Katzilla)',
          alignment: 'GSA RAG source attribution requirement',
        }),
      ]),
      gaps: Object.freeze([
        'FedRAMP authorization not yet held — disclose as roadmap with FedRAMP 20x or CSP partnership path.',
        'CMMC documentation: NIST SP 800-171 gap assessment needed if A11oy will handle CUI.',
        'Bias testing evidence: documented bias audit plan or results required.',
        'Data residency statement: explicit confirmation that data stays on US-controlled infrastructure.',
        'Incident response plan: documented IR procedure for the GSA 72-hour reporting requirement.',
        'NAICS codes: ensure SAM.gov registration carries the recommended NAICS codes.',
      ]),
    }),
    Sentra: Object.freeze({
      platformId: 'Sentra' as GovPlatformId,
      purpose:
        'Governed security and threat intelligence pack — recursive threat modeling, regulated monitoring, security review, escalation workflows, and evidence-bound decision artifacts.',
      readinessScore: 68,
      scorecard: Object.freeze({
        governance: 'strong',
        proofChain: 'strong',
        auditability: 'strong',
        humanOversight: 'strong',
        certPath: 'in_progress',
        certNote: 'Needs SOC 2',
      }),
      strengths: Object.freeze([
        Object.freeze({
          capability: 'Recursive threat loop with risk tiers R1–R4',
          alignment: 'NIST AI RMF MEASURE and MANAGE functions',
        }),
        Object.freeze({
          capability: 'Evidence pack generation',
          alignment: 'DoD documentation requirements for security conclusions',
        }),
        Object.freeze({
          capability: 'SHA-256 primary-source hash via Katzilla',
          alignment:
            'Chain-of-custody for regulated data (FDA, FEMA, Federal Register)',
        }),
        Object.freeze({
          capability: 'Source hash register in receipts',
          alignment: 'Audit trail for source attribution',
        }),
        Object.freeze({
          capability: 'Forced escalation at R4_critical',
          alignment: 'DoD Governable tenet and GSA human oversight requirement',
        }),
        Object.freeze({
          capability: 'Validator: VAL_SECURITY_PROOF_REQUIRED',
          alignment: 'No security conclusions without evidence',
        }),
        Object.freeze({
          capability: 'Validator: VAL_APPROVAL_FOR_CRITICAL_ACTION',
          alignment: 'Human-in-the-loop for high-stakes security actions',
        }),
      ]),
      bestFitUseCases: Object.freeze([
        'Cybersecurity monitoring for state/local agencies (NY Joint Security Operations Center covers 95,000 computers).',
        'Regulatory signal monitoring via primary-source Katzilla datasets (Federal Register, FEMA, CourtListener).',
        'Threat analysis support for DoD/defense subcontracting through the NYSTEC network.',
        'Audit support services — Sentra receipt and trace outputs as audit evidence.',
      ]),
      gaps: Object.freeze([
        'SOC 2 Type II not yet in place — government security buyers will ask for it.',
        'Incident response runbook tied to Sentra alert escalation paths.',
        'Threat intelligence feed documentation: formally document which primary-source feeds power Sentra.',
        'Penetration testing: government IT security will ask if the system has been pen-tested.',
      ]),
    }),
    Amaru: Object.freeze({
      platformId: 'Amaru' as GovPlatformId,
      purpose:
        'Convergent data synchronization and reconciliation engine — merge governance, conflict resolution, delta logging, and consistency enforcement across records, schema variants, and primary-source data.',
      readinessScore: 65,
      scorecard: Object.freeze({
        governance: 'strong',
        proofChain: 'strong',
        auditability: 'strong',
        humanOversight: 'strong',
        certPath: 'in_progress',
        certNote: 'Needs privacy docs',
      }),
      strengths: Object.freeze([
        Object.freeze({
          capability: 'Append-only delta log',
          alignment: 'Data lineage and audit trail requirements',
        }),
        Object.freeze({
          capability: 'Consistency gate before commit',
          alignment: 'Data integrity for government records',
        }),
        Object.freeze({
          capability: 'Source priority metadata',
          alignment: 'Data provenance requirements',
        }),
        Object.freeze({
          capability: 'Hash verification on ingest and replay',
          alignment: 'Chain-of-custody requirements',
        }),
        Object.freeze({
          capability: 'Consistency report output',
          alignment: 'Government records management standards',
        }),
        Object.freeze({
          capability: 'VAL_MERGE_SAFETY validator',
          alignment: 'Prevents unsafe data operations',
        }),
        Object.freeze({
          capability: 'Upstream hash register in receipts',
          alignment: 'Traceable data lineage artifacts',
        }),
      ]),
      bestFitUseCases: Object.freeze([
        'Government data consolidation — merging records from multiple agency systems.',
        'Census, BLS, FRED data reconciliation via Katzilla primary-source feeds.',
        'Property and asset record management across NY state agencies.',
        'Grant and contract data reconciliation across agencies.',
      ]),
      gaps: Object.freeze([
        'Data classification documentation: which classifications (CUI, PII, public) Amaru handles and how.',
        'Retention policy: government data has specific retention requirements.',
        'Integration documentation: how Amaru integrates with common government systems (e.g., COTS ERP).',
        'Privacy impact assessment for any system handling government PII.',
      ]),
    }),
  });

// ---------------------------------------------------------------------------
// NIST AI RMF alignment matrix (4 functions × 3 platforms)
// ---------------------------------------------------------------------------
export type NistRmfFunction = 'GOVERN' | 'MAP' | 'MEASURE' | 'MANAGE';

export interface NistRmfRow {
  readonly fn: NistRmfFunction;
  readonly description: string;
  readonly coverage: Readonly<Record<GovPlatformId, string>>;
}

export const NIST_RMF_ALIGNMENT: readonly NistRmfRow[] = Object.freeze([
  Object.freeze({
    fn: 'GOVERN' as NistRmfFunction,
    description: 'policies, accountability, risk culture',
    coverage: Object.freeze({
      A11oy: 'Validator registry, loop policy, operator modes',
      Sentra: 'Risk tier governance',
      Amaru: 'Source priority and merge safety',
    }),
  }),
  Object.freeze({
    fn: 'MAP' as NistRmfFunction,
    description: 'context, categorization, risk identification',
    coverage: Object.freeze({
      A11oy: 'Domain pack router, task-type routing',
      Sentra: 'Threat loop profiles',
      Amaru: 'Schema variant mapping',
    }),
  }),
  Object.freeze({
    fn: 'MEASURE' as NistRmfFunction,
    description: 'quantitative/qualitative risk assessment',
    coverage: Object.freeze({
      A11oy: 'Delta, consistency, uncertainty scores per step',
      Sentra: 'Risk tier scoring',
      Amaru: 'Consistency scoring',
    }),
  }),
  Object.freeze({
    fn: 'MANAGE' as NistRmfFunction,
    description: 'prioritize, respond, recover',
    coverage: Object.freeze({
      A11oy: 'Human approval gate, halt conditions, replay',
      Sentra: 'Evidence packs, escalation',
      Amaru: 'Conflict reconciliation',
    }),
  }),
]);

// ---------------------------------------------------------------------------
// DoD Responsible AI Tenets (5 tenets, status per platform stack)
// ---------------------------------------------------------------------------
export type DodTenet =
  | 'Responsible'
  | 'Equitable'
  | 'Traceable'
  | 'Reliable'
  | 'Governable';

export type ReadinessStatus = 'covered' | 'gap' | 'in_progress';

export interface DodTenetRow {
  readonly tenet: DodTenet;
  readonly description: string;
  readonly platformCoverage: string;
  readonly status: ReadinessStatus;
}

export const DOD_TENETS: readonly DodTenetRow[] = Object.freeze([
  Object.freeze({
    tenet: 'Responsible' as DodTenet,
    description: 'no unintended harm',
    platformCoverage: 'Human approval at R3/R4, validator hard stops',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    tenet: 'Equitable' as DodTenet,
    description: 'no bias across populations',
    platformCoverage: 'Bias testing plan needed',
    status: 'gap' as ReadinessStatus,
  }),
  Object.freeze({
    tenet: 'Traceable' as DodTenet,
    description: 'transparent operations',
    platformCoverage: 'Full trace runtime, append-only logs, receipts',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    tenet: 'Reliable' as DodTenet,
    description: 'consistent under varying conditions',
    platformCoverage: 'Golden runs, replay verification, consistency gates',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    tenet: 'Governable' as DodTenet,
    description: 'human intervention mechanisms',
    platformCoverage: 'Approval gate, halt conditions, operational modes',
    status: 'covered' as ReadinessStatus,
  }),
]);

// ---------------------------------------------------------------------------
// GSAR 552.239-7001 (proposed) clause readiness — 10 requirements
// ---------------------------------------------------------------------------
export interface GsarRow {
  readonly requirement: string;
  readonly platformResponse: string;
  readonly status: ReadinessStatus;
}

export const GSAR_552_239_7001_READINESS: readonly GsarRow[] = Object.freeze([
  Object.freeze({
    requirement: 'Human oversight and intervention mechanism',
    platformResponse: 'Approval gate, operational modes',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'Summarized intermediate processing actions',
    platformResponse: 'Step-level trace with delta and consistency scores',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'Model routing decisions with rationale',
    platformResponse: 'Domain pack router with explicit routing rules',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'RAG source attribution with direct links',
    platformResponse: 'Citation runtime, citation_map.json output',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'Complete audit trail on demand',
    platformResponse: 'trace.jsonl, decision_receipt.json per run',
    status: 'covered' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'NIST AI RMF alignment documentation',
    platformResponse: 'Needs formal written documentation',
    status: 'gap' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: '72-hour incident reporting',
    platformResponse: 'Needs IR procedure',
    status: 'gap' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'Data not used to train models for other customers',
    platformResponse: 'Needs explicit contractual commitment',
    status: 'gap' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'American AI Systems requirement',
    platformResponse: 'Needs vendor disclosure for all model providers',
    status: 'gap' as ReadinessStatus,
  }),
  Object.freeze({
    requirement: 'Bias and truthfulness documentation',
    platformResponse: 'Needs formal bias audit plan',
    status: 'gap' as ReadinessStatus,
  }),
]);

// ---------------------------------------------------------------------------
// SAM.gov registration + NAICS codes
// ---------------------------------------------------------------------------
export interface NaicsCode {
  readonly code: string;
  readonly title: string;
}

export const RECOMMENDED_NAICS_CODES: readonly NaicsCode[] = Object.freeze([
  Object.freeze({ code: '541511', title: 'Custom Computer Programming Services' }),
  Object.freeze({ code: '541512', title: 'Computer Systems Design Services' }),
  Object.freeze({ code: '541519', title: 'Other Computer Related Services' }),
  Object.freeze({
    code: '541690',
    title: 'Other Scientific and Technical Consulting Services',
  }),
  Object.freeze({
    code: '541715',
    title:
      'Research and Development in the Physical, Engineering, and Life Sciences',
  }),
]);

export interface SamGovStep {
  readonly order: number;
  readonly action: string;
  readonly note?: string;
}

export const SAM_GOV_REGISTRATION_STEPS: readonly SamGovStep[] = Object.freeze([
  Object.freeze({
    order: 1,
    action: 'Get your UEI (Unique Entity Identifier) at SAM.gov',
    note: 'Free, takes 10–15 business days.',
  }),
  Object.freeze({
    order: 2,
    action: 'Register your entity',
    note: 'Legal business name must exactly match IRS records.',
  }),
  Object.freeze({
    order: 3,
    action: 'Select NAICS codes',
    note: 'See RECOMMENDED_NAICS_CODES for the SZL Consulting LTD shortlist.',
  }),
  Object.freeze({
    order: 4,
    action: 'Complete Reps & Certs',
    note: 'Certify small business status, compliance with FAR provisions.',
  }),
  Object.freeze({
    order: 5,
    action: 'Annual renewal',
    note: 'SAM registration must be renewed every year.',
  }),
]);

export const NEW_YORK_STATE_REGISTRATION_STEPS = Object.freeze([
  'Register at NY Contract Reporter (nyscr.com) for state contracting opportunities.',
  'Consider MWBE certification (30% MWBE goals are common in NY state contracts).',
  'Consider SDVOB certification if applicable (6% SDVOB goals).',
] as const);

// ---------------------------------------------------------------------------
// Pre-meeting action items (Critical / For-Meeting / 30-Day)
// ---------------------------------------------------------------------------
export type ActionGroup = 'critical' | 'for_meeting' | 'thirty_day';

export interface ActionItem {
  readonly group: ActionGroup;
  readonly text: string;
}

export const PRE_MEETING_ACTION_ITEMS: readonly ActionItem[] = Object.freeze([
  // Critical (do before meeting)
  Object.freeze({ group: 'critical' as ActionGroup, text: 'Confirm SAM.gov registration status for SZL Consulting LTD.' }),
  Object.freeze({ group: 'critical' as ActionGroup, text: 'Prepare a one-page capability statement (required for government sales).' }),
  Object.freeze({ group: 'critical' as ActionGroup, text: 'Prepare a 3-slide platform overview: A11oy, Sentra, Amaru with government use cases.' }),
  Object.freeze({ group: 'critical' as ActionGroup, text: 'Draft a short data residency statement confirming US-only infrastructure.' }),
  Object.freeze({ group: 'critical' as ActionGroup, text: 'List all AI model providers used (required for "American AI Systems" compliance).' }),
  // For the meeting
  Object.freeze({ group: 'for_meeting' as ActionGroup, text: 'Ask Mercy McInnis which NAICS codes and certifications to prioritize.' }),
  Object.freeze({ group: 'for_meeting' as ActionGroup, text: 'Ask about NY DIGIT agency vendor registration process.' }),
  Object.freeze({ group: 'for_meeting' as ActionGroup, text: 'Ask about set-aside programs (small business, 8(a), HUBZone).' }),
  Object.freeze({ group: 'for_meeting' as ActionGroup, text: 'Ask about specific RFPs or upcoming opportunities the APEX program is tracking.' }),
  Object.freeze({ group: 'for_meeting' as ActionGroup, text: "Ask about cyber/IT opportunities through NYSTEC's DoD network." }),
  // 30-day roadmap
  Object.freeze({ group: 'thirty_day' as ActionGroup, text: 'Begin SAM.gov registration if not already active.' }),
  Object.freeze({ group: 'thirty_day' as ActionGroup, text: 'Engage a FedRAMP consultant to assess authorization path.' }),
  Object.freeze({ group: 'thirty_day' as ActionGroup, text: 'Draft bias testing methodology for A11oy and Sentra.' }),
  Object.freeze({ group: 'thirty_day' as ActionGroup, text: 'Draft NIST AI RMF alignment documentation (can reference this audit).' }),
  Object.freeze({ group: 'thirty_day' as ActionGroup, text: 'Draft privacy impact assessment for Amaru.' }),
  Object.freeze({ group: 'thirty_day' as ActionGroup, text: 'Draft incident response runbook.' }),
]);

// ---------------------------------------------------------------------------
// Competitive positioning statement (pinned exactly as drafted in the audit)
// ---------------------------------------------------------------------------
export const COMPETITIVE_POSITIONING_STATEMENT =
  'SZL Holdings builds governed AI decision infrastructure for high-consequence operations. Our three-platform stack — A11oy, Sentra, and Amaru — was built from the ground up with auditability, human oversight, and proof chains as first-class design requirements, not add-ons. Every agent action produces a cryptographically traceable receipt, append-only log, and source hash. We align with the DoD\'s five Responsible AI tenets, NIST AI RMF\'s Govern-Map-Measure-Manage functions, and the GSA\'s proposed traceability requirements. New York\'s new DIGIT agency and S.B. 7599 transparency law create exactly the procurement environment our platform was built for.' as const;

// ---------------------------------------------------------------------------
// Top-level manifest summary (compact read-model for /gov-readiness/manifest)
// ---------------------------------------------------------------------------
export interface GovReadinessManifest {
  readonly auditTitle: 'SZL Holdings — A11oy, Sentra & Amaru: Exhaustive Audit & Government Readiness Report';
  readonly auditDate: '2026-04-30';
  readonly preparedBy: 'Stephen P. Lutar Jr. / SZL Consulting LTD';
  readonly meeting: 'Empire APEX Accelerator – NYSTEC (Mercy McInnis, Procurement Counselor)';
  readonly classification: 'Pre-Briefing — Government Sales Readiness';
  readonly overallScores: Readonly<Record<GovPlatformId, number>>;
  readonly counts: {
    readonly platforms: number;
    readonly nistRows: number;
    readonly dodTenets: number;
    readonly gsarRequirements: number;
    readonly naicsCodes: number;
    readonly samSteps: number;
    readonly actionItems: number;
  };
  readonly readinessByGroup: {
    readonly gsarCovered: number;
    readonly gsarGaps: number;
    readonly dodCovered: number;
    readonly dodGaps: number;
  };
}

export const GOV_READINESS_MANIFEST: GovReadinessManifest = Object.freeze({
  auditTitle:
    'SZL Holdings — A11oy, Sentra & Amaru: Exhaustive Audit & Government Readiness Report',
  auditDate: '2026-04-30',
  preparedBy: 'Stephen P. Lutar Jr. / SZL Consulting LTD',
  meeting: 'Empire APEX Accelerator – NYSTEC (Mercy McInnis, Procurement Counselor)',
  classification: 'Pre-Briefing — Government Sales Readiness',
  overallScores: Object.freeze({
    A11oy: PLATFORM_READINESS.A11oy.readinessScore,
    Sentra: PLATFORM_READINESS.Sentra.readinessScore,
    Amaru: PLATFORM_READINESS.Amaru.readinessScore,
  }),
  counts: Object.freeze({
    platforms: Object.keys(PLATFORM_READINESS).length,
    nistRows: NIST_RMF_ALIGNMENT.length,
    dodTenets: DOD_TENETS.length,
    gsarRequirements: GSAR_552_239_7001_READINESS.length,
    naicsCodes: RECOMMENDED_NAICS_CODES.length,
    samSteps: SAM_GOV_REGISTRATION_STEPS.length,
    actionItems: PRE_MEETING_ACTION_ITEMS.length,
  }),
  readinessByGroup: Object.freeze({
    gsarCovered: GSAR_552_239_7001_READINESS.filter((r) => r.status === 'covered').length,
    gsarGaps: GSAR_552_239_7001_READINESS.filter((r) => r.status === 'gap').length,
    dodCovered: DOD_TENETS.filter((r) => r.status === 'covered').length,
    dodGaps: DOD_TENETS.filter((r) => r.status === 'gap').length,
  }),
});

// ---------------------------------------------------------------------------
// Pure helpers — replay-safe lookups
// ---------------------------------------------------------------------------
export function getPlatformReadiness(platformId: string): PlatformReadiness | null {
  if (!Object.hasOwn(PLATFORM_READINESS, platformId)) return null;
  return PLATFORM_READINESS[platformId as GovPlatformId];
}

export function listGapsAcrossPlatforms(): readonly {
  readonly platformId: GovPlatformId;
  readonly gap: string;
}[] {
  const out: { platformId: GovPlatformId; gap: string }[] = [];
  for (const id of Object.keys(PLATFORM_READINESS) as GovPlatformId[]) {
    for (const gap of PLATFORM_READINESS[id].gaps) out.push({ platformId: id, gap });
  }
  return Object.freeze(out);
}

export function actionItemsByGroup(group: ActionGroup): readonly ActionItem[] {
  return Object.freeze(PRE_MEETING_ACTION_ITEMS.filter((i) => i.group === group));
}
