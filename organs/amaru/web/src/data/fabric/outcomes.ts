import type { RelayOutcome } from './types';
import { RELAY_SYNC_SPECS } from './run-events';

function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

const METRIC_BY_VERTICAL: Record<string, { metric: string; unit: number }> = {
  lyte: { metric: 'arr_uplift_cents', unit: 1_000_000 },
  terra: { metric: 'leases_signed_per_week', unit: 5 },
  vessels: { metric: 'eta_accuracy_pct', unit: 1 },
  counsel: { metric: 'matter_response_hours', unit: 24 },
  carlota: { metric: 'engagement_pulse', unit: 1 },
  aegis: { metric: 'mttr_minutes', unit: 60 },
  sentra: { metric: 'detection_coverage_pct', unit: 1 },
};

function build(): readonly RelayOutcome[] {
  const out: RelayOutcome[] = [];
  const now = Date.parse('2026-05-05T03:00:00Z');
  let id = 0;
  for (const sync of RELAY_SYNC_SPECS) {
    const def = METRIC_BY_VERTICAL[sync.vertical];
    const rng = lcg(0xc0d30a55 ^ (id * 0x9e3779b1));
    // 2–3 outcome observations per sync over the last 14 days
    const obsCount = 2 + (id % 2);
    for (let i = 0; i < obsCount; i++) {
      const observedAt = new Date(now - (i + 1) * 86_400_000 * 2).toISOString();
      const predicted = (0.6 + rng() * 0.5) * def.unit;
      const errorPct = (rng() - 0.5) * 0.3; // -15%..+15%
      const actual = predicted * (1 + errorPct);
      const lift = (rng() * 0.18) - 0.02; // mostly positive
      out.push({
        id: `out-${sync.id}-${i}`,
        syncId: sync.id,
        syncName: sync.name,
        verticalId: sync.vertical,
        destinationId: sync.destinationId,
        observedAtIso: observedAt,
        predictedMetric: def.metric,
        predictedValue: Math.round(predicted * 100) / 100,
        actualValue: Math.round(actual * 100) / 100,
        predictionError: Math.round(errorPct * 1000) / 1000,
        liftPct: Math.round(lift * 1000) / 1000,
        lessonLearned:
          lift > 0.08
            ? 'Strong lift — recommend cadence increase.'
            : lift < 0
              ? 'Negative lift — propose retirement review.'
              : 'Within expected envelope; hold cadence.',
        policyUpdateCandidate: Math.abs(errorPct) > 0.12,
        evidenceRef: `evidence/${sync.id}/outcome/${i}`,
      });
      id++;
    }
  }
  return out.sort((a, b) => (a.observedAtIso < b.observedAtIso ? 1 : -1));
}

export const RELAY_OUTCOMES: readonly RelayOutcome[] = build();
