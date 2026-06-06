import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { FieldMapping, RelayDestination, RelayMapping, RelayOutcome } from '@/data/fabric/types';

/**
 * Layers mapping overrides (from approved drift repairs) on top of a seed
 * mapping definition. Returns a new mapping with applied transformations,
 * field count delta, and any governance promotion. Used by mappings.tsx for
 * display and by agents.tsx to feed the coalition runtime the post-repair
 * mapping. Pure function — same inputs produce same output.
 */
export function applyMappingOverrides(
  mapping: RelayMapping,
  overrides: readonly MappingOverride[],
): RelayMapping {
  const relevant = overrides.filter((o) => o.mappingId === mapping.id);
  if (relevant.length === 0) return mapping;
  const extraTransforms = relevant.map((o) => o.addedTransformation);
  const fieldDelta = relevant.reduce((s, o) => s + o.fieldDelta, 0);
  const promote = relevant.some((o) => o.governanceShift === 'amber_to_green') && mapping.governanceState === 'amber'
    ? 'green'
    : relevant.some((o) => o.governanceShift === 'red_to_amber') && mapping.governanceState === 'red'
      ? 'amber'
      : mapping.governanceState;
  return {
    ...mapping,
    transformations: [...mapping.transformations, ...extraTransforms],
    mappedFieldCount: Math.max(0, mapping.mappedFieldCount + fieldDelta),
    governanceState: promote,
  };
}

const STORAGE_KEY = 'conduit.innovation.store.v1';
const NOW_ISO = '2026-05-05T03:55:00Z';

export interface AudienceRecord {
  readonly id: string;
  readonly name: string;
  readonly modelId: string;
  readonly modelName: string;
  readonly sql: string;
  readonly estimatedRows: number;
  readonly destinationId: string;
  readonly destinationName: string;
  readonly piiGateResult: 'pass' | 'warn' | 'block';
  readonly createdAt: string;
}

export interface DriftDecision {
  readonly id: string;
  readonly proposalId: string;
  readonly fieldName: string;
  readonly sourceName: string;
  readonly severity: 'critical' | 'high' | 'medium' | 'low';
  readonly mappingIds: readonly string[];
  readonly status: 'approved' | 'deferred' | 'blocked';
  readonly resolvedAt: string;
}

export interface GoldenMerge {
  readonly clusterId: string;
  readonly entityName: string;
  readonly entityType: string;
  readonly confidence: number;
  readonly sourcesUnified: number;
  readonly mergedAt: string;
}

export interface ClosedLoopOutcomeRecord extends RelayOutcome {
  readonly reverseMutationId: string;
  readonly capturedFromDestinationId: string;
}

export interface DiscoveredDestinationRecord extends RelayDestination {
  readonly discoveredAt: string;
  readonly probeAtMs: number;
}

export interface MapperCalibrationStats {
  readonly totalDecided: number;
  readonly accepted: number;
  readonly rejected: number;
  readonly threshold: number;
  readonly updatedAt: string;
}

/**
 * A concrete repair applied to a mapping definition by the Schema Drift
 * Auto-Repair surface. These are layered on top of the seed mapping data by
 * `applyMappingOverrides` so downstream surfaces (mappings.tsx, agents.tsx /
 * coalition runtime) see the post-repair definition.
 */
export interface MappingOverride {
  readonly mappingId: string;
  readonly proposalId: string;
  readonly fieldName: string;
  readonly action: 'add_field' | 'drop_field' | 'rename_type' | 'tighten_nullable';
  readonly addedTransformation: FieldMapping;
  readonly fieldDelta: number;
  readonly governanceShift: 'none' | 'amber_to_green' | 'red_to_amber';
  readonly appliedAt: string;
}

/**
 * A persisted golden-record merge that is consumed by the coalition runtime
 * to substitute the unified account identity onto sync events; consumed by
 * mappings.tsx to show the merge badge for affected mappings.
 */
export interface DslVersionRecord {
  readonly version: number;
  readonly description: string;
  readonly savedAt: string;
  readonly ruleCount: number;
  readonly content: string;
}

interface InnovationState {
  audiences: readonly AudienceRecord[];
  driftDecisions: readonly DriftDecision[];
  goldenMerges: readonly GoldenMerge[];
  closedLoopOutcomes: readonly ClosedLoopOutcomeRecord[];
  discoveredDestinations: readonly DiscoveredDestinationRecord[];
  mapperStats: MapperCalibrationStats | null;
  dslVersions: readonly DslVersionRecord[];
  dslActiveRuleCount: number;
  mappingOverrides: readonly MappingOverride[];
}

const initialState: InnovationState = {
  audiences: [],
  driftDecisions: [],
  goldenMerges: [],
  closedLoopOutcomes: [],
  discoveredDestinations: [],
  mapperStats: null,
  dslVersions: [],
  dslActiveRuleCount: 0,
  mappingOverrides: [],
};

interface InnovationActions {
  addAudience(a: AudienceRecord): void;
  recordDriftDecision(d: DriftDecision): void;
  recordGoldenMerge(m: GoldenMerge): void;
  addClosedLoopOutcome(o: ClosedLoopOutcomeRecord): void;
  addDiscoveredDestination(d: DiscoveredDestinationRecord): void;
  setMapperStats(s: MapperCalibrationStats): void;
  recordDslVersion(v: DslVersionRecord): void;
  setDslActiveRuleCount(n: number): void;
  applyMappingOverride(o: MappingOverride): void;
}

const InnovationCtx = createContext<(InnovationState & InnovationActions) | null>(null);

function loadPersisted(): InnovationState {
  if (typeof window === 'undefined') return initialState;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return initialState;
    const parsed = JSON.parse(raw) as Partial<InnovationState>;
    return { ...initialState, ...parsed };
  } catch {
    return initialState;
  }
}

function persist(state: InnovationState) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* quota or disabled — ignore */
  }
}

export function InnovationStoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<InnovationState>(() => loadPersisted());

  useEffect(() => { persist(state); }, [state]);

  const addAudience = useCallback((a: AudienceRecord) => {
    setState((s) => ({ ...s, audiences: [a, ...s.audiences].slice(0, 64) }));
  }, []);

  const recordDriftDecision = useCallback((d: DriftDecision) => {
    setState((s) => {
      const existing = s.driftDecisions.filter((x) => x.proposalId !== d.proposalId);
      return { ...s, driftDecisions: [d, ...existing].slice(0, 64) };
    });
  }, []);

  const recordGoldenMerge = useCallback((m: GoldenMerge) => {
    setState((s) => {
      const existing = s.goldenMerges.filter((x) => x.clusterId !== m.clusterId);
      return { ...s, goldenMerges: [m, ...existing].slice(0, 64) };
    });
  }, []);

  const addClosedLoopOutcome = useCallback((o: ClosedLoopOutcomeRecord) => {
    setState((s) => ({ ...s, closedLoopOutcomes: [o, ...s.closedLoopOutcomes].slice(0, 64) }));
  }, []);

  const addDiscoveredDestination = useCallback((d: DiscoveredDestinationRecord) => {
    setState((s) => {
      const existing = s.discoveredDestinations.filter((x) => x.id !== d.id);
      return { ...s, discoveredDestinations: [d, ...existing].slice(0, 32) };
    });
  }, []);

  const setMapperStats = useCallback((stats: MapperCalibrationStats) => {
    setState((s) => ({ ...s, mapperStats: stats }));
  }, []);

  const recordDslVersion = useCallback((v: DslVersionRecord) => {
    setState((s) => {
      const existing = s.dslVersions.filter((x) => x.version !== v.version);
      return { ...s, dslVersions: [v, ...existing].sort((a, b) => b.version - a.version).slice(0, 32) };
    });
  }, []);

  const setDslActiveRuleCount = useCallback((n: number) => {
    setState((s) => (s.dslActiveRuleCount === n ? s : { ...s, dslActiveRuleCount: n }));
  }, []);

  const applyMappingOverride = useCallback((o: MappingOverride) => {
    setState((s) => {
      const existing = s.mappingOverrides.filter((x) => !(x.mappingId === o.mappingId && x.proposalId === o.proposalId));
      return { ...s, mappingOverrides: [o, ...existing].slice(0, 128) };
    });
  }, []);

  const value = useMemo(
    () => ({
      ...state,
      addAudience,
      recordDriftDecision,
      recordGoldenMerge,
      addClosedLoopOutcome,
      addDiscoveredDestination,
      setMapperStats,
      recordDslVersion,
      setDslActiveRuleCount,
      applyMappingOverride,
    }),
    [state, addAudience, recordDriftDecision, recordGoldenMerge, addClosedLoopOutcome, addDiscoveredDestination, setMapperStats, recordDslVersion, setDslActiveRuleCount, applyMappingOverride],
  );

  return <InnovationCtx.Provider value={value}>{children}</InnovationCtx.Provider>;
}

export function useInnovationStore() {
  const ctx = useContext(InnovationCtx);
  if (!ctx) throw new Error('useInnovationStore must be used within InnovationStoreProvider');
  return ctx;
}

export const __INNOVATION_NOW = NOW_ISO;
