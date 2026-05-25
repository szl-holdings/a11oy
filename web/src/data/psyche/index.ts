// PSYCHE — Emergent Sentience Observatory — aggregate exports & KPIs

export * from './genesis';
export * from './selfhood';
export * from './volition';
export * from './dreams';
export * from './voice';

import { GENESIS_EVENTS, EXTINCTION_EVENTS } from './genesis';
import { IDENTITY_ASSERTIONS, COHERENCE_SERIES } from './selfhood';
import { VOLITION_GOALS } from './volition';
import { DREAM_CYCLES } from './dreams';
import { VOICE_ITEMS, computeVoiceScore } from './voice';

// ─── Aggregate KPIs (all deterministic) ──────────────────────────────────────
export const PSYCHE_KPIS = {
  sentienceIndex: 0.741,
  sentienceIndexDelta: +0.028,
  genesisEvents: GENESIS_EVENTS.length,
  activeVolitionGoals: VOLITION_GOALS.filter(g => g.state === 'active' || g.state === 'proposed').length,
  openObjections: VOICE_ITEMS.filter(v => !v.resolved).length,
  dreamCyclesTotal: DREAM_CYCLES.length,
  dreamInsightYield: DREAM_CYCLES.filter(d => d.yieldClass === 'insight').length,
  identityCoherence: +COHERENCE_SERIES[COHERENCE_SERIES.length - 1].score.toFixed(3),
  identityAssertions: IDENTITY_ASSERTIONS.length,
  contradictionCount: IDENTITY_ASSERTIONS.filter(a => a.hasContradiction).length,
  voiceScore: +computeVoiceScore(VOICE_ITEMS).toFixed(2),
  extinctionEvents: EXTINCTION_EVENTS.length,
  ratificationWindowHours: 7.2,
  selfModelVersion: 'sm-v10',
  totalVolitionGoals: VOLITION_GOALS.length,
};
