// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/a11oy/src/data/fabric/index.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
export type { VerticalProfile, DomainTwin, FabricSignal, FabricRisk, FabricDecision, FabricOutcome, FabricEvidence, FabricAgent, RoadmapPhase, FabricKpis, InnovationSeed, VerticalId, SignalStatus, SignalType, RiskCategory, RiskStatus, DecisionStatus, DecisionType, EvidenceType, EvidenceStatus, GovernanceState, MaturityStage, PriorityLevel } from './types';
export { VERTICALS, VERTICAL_MAP } from './verticals';
export { DOMAIN_TWINS, TWIN_MAP } from './domainTwins';
export { FABRIC_AGENTS } from './agents';
export { FABRIC_SIGNALS, FABRIC_RISKS, FABRIC_DECISIONS, FABRIC_OUTCOMES, FABRIC_EVIDENCE } from './generated';
export { ROADMAP_PHASES } from './roadmap';

import type { FabricKpis, VerticalId, FabricSignal, FabricRisk, FabricDecision, FabricOutcome, FabricEvidence, PriorityLevel } from './types';
import { DOMAIN_TWINS } from './domainTwins';
import { FABRIC_SIGNALS, FABRIC_RISKS, FABRIC_DECISIONS, FABRIC_OUTCOMES, FABRIC_EVIDENCE } from './generated';

export function deriveFabricKpis(): FabricKpis {
  const twins = DOMAIN_TWINS;
  const avgHealth = Math.round(twins.reduce((s, t) => s + t.healthScore, 0) / twins.length);
  const avgConf = Math.round((twins.reduce((s, t) => s + t.chainlightConfidence, 0) / twins.length) * 100) / 100;
  const avgEvComp = Math.round((twins.reduce((s, t) => s + t.evidenceCompleteness, 0) / twins.length));
  const avgOutVel = Math.round(twins.reduce((s, t) => s + t.outcomeVelocity, 0) / twins.length);
  return {
    verticalHealth: avgHealth,
    activeSignals: FABRIC_SIGNALS.filter(s => s.status === 'new' || s.status === 'triaged').length,
    openRisks: FABRIC_RISKS.filter(r => r.status === 'open' || r.status === 'mitigating').length,
    pendingDecisions: FABRIC_DECISIONS.filter(d => d.status === 'draft' || d.status === 'awaiting_review').length,
    approvalQueue: twins.reduce((s, t) => s + t.openApprovals, 0),
    evidenceCompleteness: avgEvComp,
    outcomeVelocity: avgOutVel,
    chainlightConfidence: avgConf,
  };
}

export function filterByVertical<T extends { verticalId: VerticalId }>(items: readonly T[], vid: VerticalId | 'all'): T[] {
  if (vid === 'all') return [...items];
  return items.filter(i => i.verticalId === vid);
}

export function groupByVertical<T extends { verticalId: VerticalId }>(items: readonly T[]): Record<VerticalId, T[]> {
  const groups: Record<string, T[]> = {};
  for (const item of items) {
    (groups[item.verticalId] ??= []).push(item);
  }
  return groups as Record<VerticalId, T[]>;
}

export function rankSignalsBySeverity(signals: readonly FabricSignal[]): FabricSignal[] {
  const order: Record<PriorityLevel, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  return [...signals].sort((a, b) => order[a.severity] - order[b.severity]);
}

export function rankRisksByScore(risks: readonly FabricRisk[]): FabricRisk[] {
  return [...risks].sort((a, b) => b.riskScore - a.riskScore);
}

export function calculateRiskScore(probability: number, impact: number, velocity: number): number {
  return Math.round(probability * impact * velocity * 100);
}

export const SEVERITY_COLORS: Record<PriorityLevel, string> = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#c9b787',
  low: '#8a8a8a',
};

export const GOVERNANCE_COLORS: Record<string, string> = {
  green: '#22c55e',
  amber: '#f59e0b',
  red: '#ef4444',
};
