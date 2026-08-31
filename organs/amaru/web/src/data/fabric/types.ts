// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
/**
 * Amaru Activation Fabric — type system.
 *
 * The serpent's spine. Every surface in Amaru reads off these types: every
 * source it profiles, every model it activates, every destination it writes,
 * every mapping it governs, every policy it enforces, every run event it
 * emits, every outcome it learns from, every agent it ranks, every roadmap
 * phase it advances.
 *
 * All optional/nullable fields are explicit so the rendering layer never has
 * to guess. No banned competitor names. No PII. No real secrets.
 */

export type GovernanceState = 'green' | 'amber' | 'red';
export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type VerticalId =
  | 'terra'
  | 'vessels'
  | 'counsel'
  | 'carlota'
  | 'aegis'
  | 'lyte'
  | 'sentra';

// ─── Sources ─────────────────────────────────────────────────────────────────
export type SourceKind =
  | 'warehouse'
  | 'oltp_postgres'
  | 'event_stream'
  | 'object_store'
  | 'crm'
  | 'support'
  | 'ticketing'
  | 'lakehouse'
  | 'webhook';

export type FreshnessTier = 'realtime' | 'near_realtime' | 'hourly' | 'daily' | 'stale';
export type ReadinessTier = 'production' | 'governed_preview' | 'sandbox' | 'quarantined';

export interface RelaySource {
  readonly id: string;
  readonly name: string;
  readonly kind: SourceKind;
  readonly owner: string;
  readonly schemaCount: number;
  readonly tableCount: number;
  readonly rowCount: number;
  readonly freshnessTier: FreshnessTier;
  readonly freshnessLagSeconds: number;
  readonly piiDetected: boolean;
  readonly piiClassesDetected: readonly string[];
  readonly qualityScore: number;
  readonly governanceState: GovernanceState;
  readonly readinessTier: ReadinessTier;
  readonly verticalCoverage: readonly VerticalId[];
  readonly lastProfiledAt: string;
  readonly anchorHash: string;
}

// ─── Models ──────────────────────────────────────────────────────────────────
export type EntityType =
  | 'contact'
  | 'account'
  | 'lead'
  | 'opportunity'
  | 'ticket'
  | 'order'
  | 'invoice'
  | 'shipment'
  | 'voyage'
  | 'matter'
  | 'document'
  | 'asset'
  | 'inspection'
  | 'incident'
  | 'kpi_snapshot'
  | 'event';

export interface RelayField {
  readonly name: string;
  readonly type: 'string' | 'integer' | 'decimal' | 'boolean' | 'timestamp' | 'json' | 'enum' | 'uuid';
  readonly nullable: boolean;
  readonly piiClass: 'none' | 'email' | 'phone' | 'name' | 'address' | 'gov_id' | 'financial' | 'health';
  readonly description: string;
}

export interface RelayModel {
  readonly id: string;
  readonly name: string;
  readonly entityType: EntityType;
  readonly sourceId: string;
  readonly primaryKey: string;
  readonly cursorField: string | null;
  readonly fields: readonly RelayField[];
  readonly fieldCount: number;
  readonly piiFieldCount: number;
  readonly qualityScore: number;
  readonly piiScore: number;
  readonly activationReadiness: number;
  readonly governanceState: GovernanceState;
  readonly verticalId: VerticalId;
  readonly sqlPreview: string;
  readonly anchorHash: string;
  readonly lastValidatedAt: string;
}

// ─── Destinations ────────────────────────────────────────────────────────────
export type DestinationOp = 'insert' | 'upsert' | 'update' | 'delete' | 'mirror' | 'event';
export type RateLimitProfile = 'lenient' | 'moderate' | 'strict' | 'tight';
export type AuthState = 'connected' | 'expiring' | 'expired' | 'rotation_required' | 'untested';

export interface RelayDestination {
  readonly id: string;
  readonly name: string;
  readonly category: 'crm' | 'support' | 'marketing' | 'collab' | 'data' | 'webhook' | 'finance' | 'logistics';
  readonly accent: string;
  readonly supportedOps: readonly DestinationOp[];
  readonly supportedEntityTypes: readonly EntityType[];
  readonly rateLimit: RateLimitProfile;
  readonly rateLimitRpm: number;
  readonly authState: AuthState;
  readonly authRotatesAt: string | null;
  readonly piiAllowed: boolean;
  readonly fieldContractStrength: number;
  readonly observabilityCoverage: number;
  readonly healthScore: number;
  readonly governanceState: GovernanceState;
  readonly anchorHash: string;
}

// ─── Mappings ────────────────────────────────────────────────────────────────
export type TransformKind =
  | 'identity'
  | 'uppercase'
  | 'lowercase'
  | 'concat'
  | 'split'
  | 'format_date'
  | 'lookup'
  | 'json_extract'
  | 'constant'
  | 'conditional'
  | 'redact'
  | 'hash'
  | 'tokenize';

export interface FieldMapping {
  readonly sourceField: string;
  readonly destinationField: string;
  readonly transform: TransformKind;
  readonly confidence: number;
  readonly piiHandling: 'pass' | 'redact' | 'hash' | 'block';
  readonly note: string;
}

export interface RelayMapping {
  readonly id: string;
  readonly name: string;
  readonly modelId: string;
  readonly destinationId: string;
  readonly verticalId: VerticalId;
  readonly compatibilityScore: number;
  readonly confidence: number;
  readonly mappedFieldCount: number;
  readonly unmappedSourceFieldCount: number;
  readonly unmappedDestinationFieldCount: number;
  readonly transformations: readonly FieldMapping[];
  readonly qualityWarnings: readonly string[];
  readonly piiWarnings: readonly string[];
  readonly approvalRequired: boolean;
  readonly approvalReason: string | null;
  readonly governanceState: GovernanceState;
  readonly proposedBy: 'mapper-agent' | 'operator' | 'cartographer-suggestion';
  readonly anchorHash: string;
}

// ─── Policies ────────────────────────────────────────────────────────────────
export type PolicyKind =
  | 'pii_control'
  | 'approval_gate'
  | 'rate_limit'
  | 'data_quality'
  | 'freshness'
  | 'destination_contract'
  | 'rollback'
  | 'audit'
  | 'retention'
  | 'consent'
  | 'suppression';

export type EnforcementAction = 'block' | 'require_approval' | 'warn' | 'redact' | 'quarantine' | 'rollback';

export interface PolicyHit {
  readonly atIso: string;
  readonly syncId: string;
  readonly outcome: EnforcementAction;
  readonly summary: string;
}

export interface RelayPolicy {
  readonly id: string;
  readonly name: string;
  readonly kind: PolicyKind;
  readonly severity: SeverityLevel;
  readonly condition: string;
  readonly enforcement: EnforcementAction;
  readonly scope: readonly VerticalId[];
  readonly recentHits: readonly PolicyHit[];
  readonly lutarWeight: { num: number; den: number };
  readonly governanceState: GovernanceState;
  readonly anchorHash: string;
}

// ─── Run events / observability ──────────────────────────────────────────────
export type RunEventType =
  | 'planned'
  | 'approved'
  | 'started'
  | 'extracted'
  | 'transformed'
  | 'policy_checked'
  | 'delivered'
  | 'failed'
  | 'retried'
  | 'quarantined'
  | 'rolled_back'
  | 'completed';

export type AgentId =
  | 'cartographer'
  | 'mapper'
  | 'courier'
  | 'sentinel'
  | 'verity'
  | 'forecaster'
  | 'fixer'
  | 'scribe';

export interface RelayRunEvent {
  readonly id: string;
  readonly syncId: string;
  readonly syncName: string;
  readonly destinationId: string;
  readonly verticalId: VerticalId;
  readonly type: RunEventType;
  readonly atIso: string;
  readonly agentId: AgentId | null;
  readonly summary: string;
  readonly recordsAffected: number;
  readonly latencyMs: number;
  readonly stateHash: string;
  readonly evidenceRef: string | null;
  readonly severity: SeverityLevel;
  readonly errorClass: string | null;
}

// ─── Outcomes / closed-loop learning ─────────────────────────────────────────
export interface RelayOutcome {
  readonly id: string;
  readonly syncId: string;
  readonly syncName: string;
  readonly verticalId: VerticalId;
  readonly destinationId: string;
  readonly observedAtIso: string;
  readonly predictedMetric: string;
  readonly predictedValue: number;
  readonly actualValue: number;
  readonly predictionError: number;
  readonly liftPct: number;
  readonly lessonLearned: string;
  readonly policyUpdateCandidate: boolean;
  readonly evidenceRef: string;
}

// ─── Agents ──────────────────────────────────────────────────────────────────
export interface AmaruAgent {
  readonly id: AgentId;
  readonly name: string;
  readonly mythosName: string;
  readonly role: string;
  readonly responsibilities: readonly string[];
  readonly allowedActions: readonly string[];
  readonly blockedActions: readonly string[];
  readonly governanceLimits: readonly string[];
  readonly inputs: readonly string[];
  readonly outputs: readonly string[];
  readonly lutarAxisAffinity: 'P' | 'K' | 'Φ' | 'C';
  readonly recentDecisionCount: number;
  readonly recentBlockCount: number;
  readonly approvalRate: number;
  readonly avgConfidence: number;
}

// ─── Roadmap ─────────────────────────────────────────────────────────────────
export interface RoadmapPhase {
  readonly id: string;
  readonly phase: number;
  readonly title: string;
  readonly tagline: string;
  readonly description: string;
  readonly status: 'complete' | 'active' | 'planned';
  readonly capabilities: readonly string[];
  readonly verticalImpact: readonly VerticalId[];
  readonly evidence: readonly string[];
}

// ─── Vertical playbooks ──────────────────────────────────────────────────────
export interface PlaybookEntry {
  readonly trigger: string;
  readonly modelId: string;
  readonly destinationId: string;
  readonly action: string;
  readonly governanceState: GovernanceState;
}

export interface VerticalPlaybook {
  readonly verticalId: VerticalId;
  readonly title: string;
  readonly route: string;
  readonly accent: string;
  readonly entries: readonly PlaybookEntry[];
}

// ─── Aggregated cockpit KPIs ─────────────────────────────────────────────────
export interface AmaruKpis {
  readonly activeSyncs: number;
  readonly recordsActivated24h: number;
  readonly failedRecords24h: number;
  readonly policyBlocks24h: number;
  readonly approvalQueue: number;
  readonly destinationHealth: number;
  readonly avgLatencyMs: number;
  readonly outcomeLiftPct: number;
}

// ─── Approval queue (computed from mappings + run events) ───────────────────
export interface ApprovalRequest {
  readonly id: string;
  readonly syncName: string;
  readonly mappingId: string;
  readonly verticalId: VerticalId;
  readonly destinationId: string;
  readonly reason: string;
  readonly proposedAtIso: string;
  readonly severity: SeverityLevel;
  readonly recordsImpacted: number;
}
