export type VerticalId = 'terra' | 'vessels' | 'counsel' | 'carlota' | 'aegis' | 'lyte' | 'sentra';

export type MaturityStage = 'seed' | 'operational' | 'scaling' | 'enterprise';
export type PriorityLevel = 'critical' | 'high' | 'medium' | 'low';

export type SignalStatus = 'new' | 'triaged' | 'routed' | 'approved' | 'resolved' | 'deferred' | 'blocked';
export type SignalType = 'risk' | 'opportunity' | 'deadline' | 'anomaly' | 'drift' | 'compliance' | 'cost' | 'vendor' | 'document' | 'operational' | 'security' | 'legal_workflow' | 'executive_decision';

export type RiskCategory = 'operational' | 'financial' | 'legal_workflow' | 'security' | 'compliance' | 'vendor' | 'asset' | 'deadline' | 'reputation' | 'data_quality' | 'decision_delay' | 'control_drift';
export type RiskStatus = 'open' | 'mitigating' | 'accepted' | 'closed';

export type DecisionStatus = 'draft' | 'awaiting_review' | 'approved' | 'rejected' | 'executed' | 'deferred';
export type DecisionType = 'approve_vendor' | 'escalate_risk' | 'adjust_route' | 'request_evidence' | 'assign_owner' | 'approve_patch' | 'update_policy' | 'schedule_service' | 'advance_deal' | 'prepare_attorney_packet' | 'close_exception';

export type EvidenceType = 'document' | 'ticket' | 'email_summary' | 'system_event' | 'scanner_result' | 'inspection_note' | 'legal_workflow_note' | 'voyage_signal' | 'vendor_update' | 'executive_decision' | 'approval_record' | 'audit_event' | 'policy_clause';
export type EvidenceStatus = 'collected' | 'verified' | 'disputed' | 'archived';

export type GovernanceState = 'green' | 'amber' | 'red';

export interface VerticalProfile {
  readonly id: VerticalId;
  readonly name: string;
  readonly tagline: string;
  readonly operatingModel: string;
  readonly primaryUsers: readonly string[];
  readonly coreEntities: readonly string[];
  readonly signalTypes: readonly string[];
  readonly workflowTypes: readonly string[];
  readonly riskTypes: readonly string[];
  readonly approvalTypes: readonly string[];
  readonly evidenceTypes: readonly string[];
  readonly outcomeTypes: readonly string[];
  readonly keyMetrics: readonly string[];
  readonly connectedA11oyLayers: readonly string[];
  readonly maturityStage: MaturityStage;
  readonly priorityLevel: PriorityLevel;
  readonly route: string;
  readonly colorToken: string;
  readonly icon: string;
  readonly innovationSeed: InnovationSeed;
}

export interface InnovationSeed {
  readonly name: string;
  readonly description: string;
  readonly researchBasis: string;
  readonly capability: string;
}

export interface DomainTwin {
  readonly id: string;
  readonly verticalId: VerticalId;
  readonly name: string;
  readonly description: string;
  readonly healthScore: number;
  readonly signalVolume: number;
  readonly activeRisks: number;
  readonly pendingDecisions: number;
  readonly openApprovals: number;
  readonly outcomeVelocity: number;
  readonly evidenceCompleteness: number;
  readonly chainlightConfidence: number;
  readonly sentraGovernanceState: GovernanceState;
  readonly psycheGovernanceState: GovernanceState;
  readonly argoLearningStatus: string;
  readonly proofChainCoverage: number;
  readonly topSignals: readonly string[];
  readonly topRisks: readonly string[];
  readonly nextBestActions: readonly string[];
  readonly linkedRoutes: readonly string[];
}

export interface FabricSignal {
  readonly id: string;
  readonly verticalId: VerticalId;
  readonly twinId: string;
  readonly title: string;
  readonly description: string;
  readonly signalType: SignalType;
  readonly source: string;
  readonly severity: PriorityLevel;
  readonly confidence: number;
  readonly timestamp: string;
  readonly relatedEntity: string;
  readonly recommendedAction: string;
  readonly sentraReviewRequired: boolean;
  readonly chainlightScenarioId: string;
  readonly proofChainAnchorId: string;
  readonly status: SignalStatus;
}

export interface FabricRisk {
  readonly id: string;
  readonly verticalId: VerticalId;
  readonly twinId: string;
  readonly title: string;
  readonly description: string;
  readonly riskCategory: RiskCategory;
  readonly riskScore: number;
  readonly probability: number;
  readonly impact: number;
  readonly velocity: number;
  readonly owner: string;
  readonly mitigation: string;
  readonly approvalRequired: boolean;
  readonly evidenceIds: readonly string[];
  readonly relatedSignals: readonly string[];
  readonly status: RiskStatus;
  readonly route: string;
}

export interface FabricDecision {
  readonly id: string;
  readonly verticalId: VerticalId;
  readonly twinId: string;
  readonly title: string;
  readonly decisionType: DecisionType;
  readonly summary: string;
  readonly options: readonly string[];
  readonly recommendedOption: string;
  readonly chainlightConfidence: number;
  readonly sentraApprovalState: DecisionStatus;
  readonly humanOwner: string;
  readonly deadline: string;
  readonly evidenceIds: readonly string[];
  readonly expectedOutcome: string;
  readonly downsideRisk: string;
  readonly status: DecisionStatus;
}

export interface FabricOutcome {
  readonly id: string;
  readonly verticalId: VerticalId;
  readonly twinId: string;
  readonly originatingDecisionId: string;
  readonly predictedOutcome: string;
  readonly actualOutcome: string;
  readonly predictionError: number;
  readonly rewardScore: number;
  readonly riskBefore: number;
  readonly riskAfter: number;
  readonly evidenceCompleteness: number;
  readonly operatorFeedback: string;
  readonly lessonLearned: string;
  readonly policyUpdateCandidate: boolean;
  readonly reviewed: boolean;
  readonly route: string;
}

export interface FabricEvidence {
  readonly id: string;
  readonly verticalId: VerticalId;
  readonly title: string;
  readonly evidenceType: EvidenceType;
  readonly sourceSystem: string;
  readonly summary: string;
  readonly authorityScore: number;
  readonly relatedSignals: readonly string[];
  readonly relatedRisks: readonly string[];
  readonly relatedDecisions: readonly string[];
  readonly relatedOutcomes: readonly string[];
  readonly proofChainAnchorId: string;
  readonly status: EvidenceStatus;
  readonly route: string;
}

export interface FabricAgent {
  readonly id: string;
  readonly name: string;
  readonly role: string;
  readonly verticalCoverage: readonly VerticalId[];
  readonly inputTypes: readonly string[];
  readonly outputTypes: readonly string[];
  readonly governanceLimits: readonly string[];
  readonly route: string;
}

export interface RoadmapPhase {
  readonly id: string;
  readonly phase: number;
  readonly title: string;
  readonly description: string;
  readonly items: readonly string[];
  readonly status: 'complete' | 'active' | 'planned';
  readonly verticalImpact: readonly VerticalId[];
}

export interface FabricKpis {
  readonly verticalHealth: number;
  readonly activeSignals: number;
  readonly openRisks: number;
  readonly pendingDecisions: number;
  readonly approvalQueue: number;
  readonly evidenceCompleteness: number;
  readonly outcomeVelocity: number;
  readonly chainlightConfidence: number;
}
