// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — artifacts/sentra/src/lib/sentinel-analytics.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * SENTINEL Behavioral Analytics — Browser-safe client module
 *
 * Mirrors the server-side engine at lib/ai-engine/src/sentinel/behavioral-analytics.ts
 * but runs entirely in the browser: no Node.js or server APIs.
 *
 * Implements z-score deviation detection, weighted multi-factor risk scoring,
 * and behavioral baseline modeling for identity-centric insider threat detection.
 */

/** A single recorded access event for a user */
export interface AccessEvent {
  timestamp: number;
  resourceType: 'document' | 'database' | 'api' | 'cloud-storage' | 'email' | 'auth';
  sensitivity: 'public' | 'internal' | 'confidential' | 'restricted' | 'top-secret';
  bytesTransferred?: number;
  offHours: boolean;
  geoKey: string;
  deviceManaged: boolean;
  approvedNetwork: boolean;
}

/** Behavioral baseline derived from historical patterns */
export interface BehavioralBaseline {
  userId: string;
  meanWeeklyAccesses: number;
  stdWeeklyAccesses: number;
  offHoursRate: number;
  sensitiveAccessRate: number;
  meanBytesPerSession: number;
  stdBytesPerSession: number;
  knownGeoKeys: string[];
  managedDeviceRate: number;
}

/** A detected behavioral anomaly with statistical evidence */
export interface DetectedAnomaly {
  id: string;
  type:
    | 'volume-spike'
    | 'off-hours-pattern'
    | 'geo-anomaly'
    | 'sensitivity-escalation'
    | 'bytes-anomaly'
    | 'unmanaged-device'
    | 'off-network';
  severity: 'critical' | 'high' | 'medium' | 'low';
  zScore: number;
  description: string;
  evidenceNarrative: string;
  timestamp: number;
  mitreTechnique?: string;
}

/** Full risk assessment result */
export interface RiskAssessment {
  userId: string;
  riskScore: number;
  riskLevel: 'critical' | 'high' | 'medium' | 'low' | 'normal';
  baselineDeviation: number;
  anomalies: DetectedAnomaly[];
  summary: string;
  factorScores: {
    volumeRisk: number;
    temporalRisk: number;
    geographicRisk: number;
    sensitivityRisk: number;
    deviceNetworkRisk: number;
    dataTransferRisk: number;
  };
  assessedAt: number;
}

// ─── Statistical utilities ────────────────────────────────────────────────────

function zScore(value: number, mean: number, std: number): number {
  return std === 0 ? 0 : (value - mean) / std;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function zToRisk(z: number, threshold = 2.0): number {
  const absZ = Math.abs(z);
  if (absZ < threshold) return clamp((absZ / threshold) * 30, 0, 30);
  return clamp(30 + (absZ - threshold) * 25, 0, 100);
}

function riskLevelFromScore(score: number): RiskAssessment['riskLevel'] {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 35) return 'medium';
  if (score >= 15) return 'low';
  return 'normal';
}

// ─── Anomaly detectors ────────────────────────────────────────────────────────

function detectVolumeAnomaly(
  weekly: number,
  b: BehavioralBaseline,
  ts: number,
): DetectedAnomaly | null {
  const z = zScore(weekly, b.meanWeeklyAccesses, b.stdWeeklyAccesses);
  if (Math.abs(z) < 2.0) return null;
  const mult = b.meanWeeklyAccesses > 0 ? (weekly / b.meanWeeklyAccesses).toFixed(1) : '∞';
  const sev: DetectedAnomaly['severity'] =
    Math.abs(z) >= 4 ? 'critical' : Math.abs(z) >= 3 ? 'high' : 'medium';
  return {
    id: `vol-${ts}`,
    type: 'volume-spike',
    severity: sev,
    zScore: z,
    description: `Access volume ${mult}× weekly baseline (z=${z.toFixed(2)})`,
    evidenceNarrative: `${weekly.toFixed(0)} accesses vs baseline μ=${b.meanWeeklyAccesses.toFixed(0)}, σ=${b.stdWeeklyAccesses.toFixed(0)}. Z-score ${z.toFixed(2)} — ${sev} anomaly threshold exceeded.`,
    timestamp: ts,
    mitreTechnique: 'T1005',
  };
}

function detectOffHoursAnomaly(
  events: AccessEvent[],
  b: BehavioralBaseline,
  ts: number,
): DetectedAnomaly | null {
  if (events.length === 0) return null;
  const rate = events.filter((e) => e.offHours).length / events.length;
  if (rate < 0.3 || rate <= b.offHoursRate * 1.5) return null;
  const sev: DetectedAnomaly['severity'] =
    rate >= 0.6 ? 'critical' : rate >= 0.4 ? 'high' : 'medium';
  const z = zScore(rate, b.offHoursRate, Math.max(b.offHoursRate * 0.3, 0.05));
  return {
    id: `offhours-${ts}`,
    type: 'off-hours-pattern',
    severity: sev,
    zScore: z,
    description: `Off-hours activity: ${(rate * 100).toFixed(0)}% of sessions vs ${(b.offHoursRate * 100).toFixed(0)}% baseline`,
    evidenceNarrative: `${events.filter((e) => e.offHours).length} of ${events.length} events outside standard hours. Baseline off-hours rate: ${(b.offHoursRate * 100).toFixed(0)}%. Current: ${(rate * 100).toFixed(0)}%.`,
    timestamp: ts,
    mitreTechnique: 'T1078',
  };
}

function detectGeoAnomaly(
  events: AccessEvent[],
  b: BehavioralBaseline,
  ts: number,
): DetectedAnomaly | null {
  const unknownEvents = events.filter((e) => !b.knownGeoKeys.includes(e.geoKey));
  if (unknownEvents.length === 0) return null;
  const unknownGeos = [...new Set(unknownEvents.map((e) => e.geoKey))];
  const sev: DetectedAnomaly['severity'] =
    unknownEvents.length >= 5 ? 'critical' : unknownEvents.length >= 2 ? 'high' : 'medium';
  return {
    id: `geo-${ts}`,
    type: 'geo-anomaly',
    severity: sev,
    zScore: 3.5,
    description: `Auth from ${unknownGeos.length} unknown location(s): ${unknownGeos.slice(0, 3).join(', ')}`,
    evidenceNarrative: `${unknownEvents.length} event(s) from geos not in 90-day baseline. Unknown: ${unknownGeos.join(', ')}. Known profile: ${b.knownGeoKeys.join(', ')}.`,
    timestamp: ts,
    mitreTechnique: 'T1078.004',
  };
}

function detectSensitivityAnomaly(
  events: AccessEvent[],
  b: BehavioralBaseline,
  ts: number,
): DetectedAnomaly | null {
  if (events.length === 0) return null;
  const sensitive = events.filter((e) =>
    ['confidential', 'restricted', 'top-secret'].includes(e.sensitivity),
  );
  const rate = sensitive.length / events.length;
  if (rate <= b.sensitiveAccessRate * 1.8) return null;
  const sev: DetectedAnomaly['severity'] =
    rate >= 0.6 ? 'critical' : rate >= 0.4 ? 'high' : 'medium';
  const z = zScore(rate, b.sensitiveAccessRate, Math.max(b.sensitiveAccessRate * 0.4, 0.05));
  return {
    id: `sens-${ts}`,
    type: 'sensitivity-escalation',
    severity: sev,
    zScore: z,
    description: `Sensitive resource access: ${(rate * 100).toFixed(0)}% vs ${(b.sensitiveAccessRate * 100).toFixed(0)}% baseline`,
    evidenceNarrative: `${sensitive.length} of ${events.length} events accessed confidential/restricted resources. Baseline sensitive access rate: ${(b.sensitiveAccessRate * 100).toFixed(0)}%.`,
    timestamp: ts,
    mitreTechnique: 'T1005',
  };
}

function detectBytesAnomaly(
  events: AccessEvent[],
  b: BehavioralBaseline,
  ts: number,
): DetectedAnomaly | null {
  const total = events.reduce((s, e) => s + (e.bytesTransferred ?? 0), 0);
  if (total === 0) return null;
  const z = zScore(
    total,
    b.meanBytesPerSession * events.length,
    Math.max(b.stdBytesPerSession * Math.sqrt(events.length), 1),
  );
  if (Math.abs(z) < 2.5) return null;
  const gb = (total / 1_073_741_824).toFixed(2);
  const sev: DetectedAnomaly['severity'] =
    Math.abs(z) >= 4 ? 'critical' : Math.abs(z) >= 3 ? 'high' : 'medium';
  return {
    id: `bytes-${ts}`,
    type: 'bytes-anomaly',
    severity: sev,
    zScore: z,
    description: `Abnormal data transfer: ${gb}GB (z=${z.toFixed(2)})`,
    evidenceNarrative: `${gb}GB transferred across ${events.length} sessions. Z-score ${z.toFixed(2)} from session baseline. Indicative of bulk data staging or exfiltration.`,
    timestamp: ts,
    mitreTechnique: 'T1567.002',
  };
}

// ─── Core engine ──────────────────────────────────────────────────────────────

export function computeRiskAssessment(
  userId: string,
  events: AccessEvent[],
  baseline: BehavioralBaseline,
  windowDays = 7,
): RiskAssessment {
  const now = Date.now();
  const weeklyCount = events.length * (7 / Math.max(windowDays, 1));
  const anomalies: DetectedAnomaly[] = [];

  const v = detectVolumeAnomaly(weeklyCount, baseline, now);
  if (v) anomalies.push(v);
  const o = detectOffHoursAnomaly(events, baseline, now);
  if (o) anomalies.push(o);
  const g = detectGeoAnomaly(events, baseline, now);
  if (g) anomalies.push(g);
  const s = detectSensitivityAnomaly(events, baseline, now);
  if (s) anomalies.push(s);
  const d = detectBytesAnomaly(events, baseline, now);
  if (d) anomalies.push(d);

  // Device/network anomalies
  const unmanaged = events.filter((e) => !e.deviceManaged);
  if (unmanaged.length > 0 && baseline.managedDeviceRate >= 0.9) {
    anomalies.push({
      id: `device-${now}`,
      type: 'unmanaged-device',
      severity: unmanaged.length >= 3 ? 'high' : 'medium',
      zScore: 2.8,
      description: `${unmanaged.length} access event(s) from non-MDM enrolled device(s)`,
      evidenceNarrative: `${unmanaged.length} session(s) from unregistered devices. User baseline: ${(baseline.managedDeviceRate * 100).toFixed(0)}% managed.`,
      timestamp: now,
    });
  }

  // Factor scores
  const volumeRisk = zToRisk(
    zScore(weeklyCount, baseline.meanWeeklyAccesses, Math.max(baseline.stdWeeklyAccesses, 1)),
  );
  const offRate = events.length > 0 ? events.filter((e) => e.offHours).length / events.length : 0;
  const temporalRisk = zToRisk(
    zScore(offRate, baseline.offHoursRate, Math.max(baseline.offHoursRate * 0.4, 0.05)),
  );
  const unknownGeoFrac =
    events.length > 0
      ? events.filter((e) => !baseline.knownGeoKeys.includes(e.geoKey)).length / events.length
      : 0;
  const geographicRisk = clamp(unknownGeoFrac * 100, 0, 100);
  const currentSensRate =
    events.length > 0
      ? events.filter((e) => ['confidential', 'restricted', 'top-secret'].includes(e.sensitivity))
          .length / events.length
      : 0;
  const sensitivityRisk = zToRisk(
    zScore(
      currentSensRate,
      baseline.sensitiveAccessRate,
      Math.max(baseline.sensitiveAccessRate * 0.4, 0.05),
    ),
  );
  const unmanagedFrac =
    events.length > 0 ? events.filter((e) => !e.deviceManaged).length / events.length : 0;
  const deviceNetworkRisk = clamp(unmanagedFrac * 80 + (unmanaged.length > 0 ? 20 : 0), 0, 100);
  const totalBytes = events.reduce((s, e) => s + (e.bytesTransferred ?? 0), 0);
  const bytesZ = zScore(
    totalBytes,
    baseline.meanBytesPerSession * events.length,
    Math.max(baseline.stdBytesPerSession * Math.sqrt(Math.max(events.length, 1)), 1_000_000),
  );
  const dataTransferRisk = zToRisk(bytesZ, 2.5);

  const factorScores = {
    volumeRisk,
    temporalRisk,
    geographicRisk,
    sensitivityRisk,
    deviceNetworkRisk,
    dataTransferRisk,
  };

  const weights = {
    volumeRisk: 0.2,
    temporalRisk: 0.15,
    geographicRisk: 0.2,
    sensitivityRisk: 0.2,
    deviceNetworkRisk: 0.1,
    dataTransferRisk: 0.15,
  };
  let raw = (Object.entries(weights) as [keyof typeof factorScores, number][]).reduce(
    (sum, [k, w]) => sum + factorScores[k] * w,
    0,
  );

  const critCount = anomalies.filter((a) => a.severity === 'critical').length;
  if (critCount >= 2) raw = Math.min(100, raw * 1.35);
  if (critCount >= 3) raw = Math.min(100, raw * 1.15);

  const riskScore = Math.round(clamp(raw, 0, 100));
  const baselineDeviation =
    baseline.meanWeeklyAccesses > 0
      ? Math.round(
          ((weeklyCount - baseline.meanWeeklyAccesses) / baseline.meanWeeklyAccesses) * 100,
        )
      : 0;
  const summary =
    anomalies.length === 0
      ? 'No significant behavioral anomalies detected.'
      : `${anomalies.length} anomaly${anomalies.length !== 1 ? 's' : ''}: ${anomalies
          .slice(0, 2)
          .map((a) => a.description)
          .join('; ')}.`;

  return {
    userId,
    riskScore,
    riskLevel: riskLevelFromScore(riskScore),
    baselineDeviation,
    anomalies,
    summary,
    factorScores,
    assessedAt: now,
  };
}

export function buildBaseline(
  userId: string,
  historicalEvents: AccessEvent[],
  windowDays = 90,
): BehavioralBaseline {
  const weekCount = Math.max(windowDays / 7, 1);
  const weeksMap = new Map<number, number>();
  for (const evt of historicalEvents) {
    const wk = Math.floor(evt.timestamp / (7 * 24 * 3600 * 1000));
    weeksMap.set(wk, (weeksMap.get(wk) ?? 0) + 1);
  }
  const weekCounts = [...weeksMap.values()];
  const mean =
    weekCounts.length > 0
      ? weekCounts.reduce((s, v) => s + v, 0) / weekCounts.length
      : historicalEvents.length / weekCount;
  const std =
    weekCounts.length > 1
      ? Math.sqrt(weekCounts.reduce((s, v) => s + (v - mean) ** 2, 0) / (weekCounts.length - 1))
      : mean * 0.3;
  const offRate =
    historicalEvents.length > 0
      ? historicalEvents.filter((e) => e.offHours).length / historicalEvents.length
      : 0.05;
  const sensRate =
    historicalEvents.length > 0
      ? historicalEvents.filter((e) =>
          ['confidential', 'restricted', 'top-secret'].includes(e.sensitivity),
        ).length / historicalEvents.length
      : 0.1;
  const bytes = historicalEvents.map((e) => e.bytesTransferred ?? 0).filter((b) => b > 0);
  const meanBytes = bytes.length > 0 ? bytes.reduce((s, b) => s + b, 0) / bytes.length : 5_242_880;
  const stdBytes =
    bytes.length > 1
      ? Math.sqrt(bytes.reduce((s, b) => s + (b - meanBytes) ** 2, 0) / (bytes.length - 1))
      : meanBytes;
  return {
    userId,
    meanWeeklyAccesses: mean,
    stdWeeklyAccesses: std,
    offHoursRate: offRate,
    sensitiveAccessRate: sensRate,
    meanBytesPerSession: meanBytes,
    stdBytesPerSession: stdBytes,
    knownGeoKeys: [...new Set(historicalEvents.map((e) => e.geoKey))],
    managedDeviceRate:
      historicalEvents.length > 0
        ? historicalEvents.filter((e) => e.deviceManaged).length / historicalEvents.length
        : 1.0,
  };
}
