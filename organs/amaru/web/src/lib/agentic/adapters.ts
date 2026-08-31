/**
 * Amaru connector adapter interfaces + demo adapters.
 *
 * Real connectors live behind these contracts in the API server. The demo
 * adapters here are deterministic stand-ins so the cockpit can demonstrate
 * dry-runs and shadow planning without real external calls.
 */

import type { RelayDestination, RelayMapping, RelayModel, RelaySource } from '@/data/fabric/types';

export interface ProfileResult {
  readonly source: RelaySource;
  readonly tablesProfiled: number;
  readonly piiCandidatesFound: number;
  readonly samplesRedacted: number;
  readonly profileLatencyMs: number;
}

export interface RelaySourceAdapter {
  readonly id: string;
  readonly name: string;
  profile(source: RelaySource): ProfileResult;
  extract(model: RelayModel, batchSize: number): { batchId: string; estRecords: number; cursor: string };
}

export interface DeliveryAck {
  readonly destinationId: string;
  readonly batchId: string;
  readonly accepted: number;
  readonly rejected: number;
  readonly witnessHash: string;
  readonly latencyMs: number;
}

export interface RelayDestinationAdapter {
  readonly id: string;
  readonly name: string;
  validateContract(mapping: RelayMapping, destination: RelayDestination): { ok: boolean; reasons: readonly string[] };
  deliver(batchId: string, records: number, destination: RelayDestination): DeliveryAck;
}

export interface SyncPlan {
  readonly mappingId: string;
  readonly destinationId: string;
  readonly batches: readonly { batchId: string; records: number; estLatencyMs: number }[];
  readonly totalRecords: number;
  readonly estTotalLatencyMs: number;
  readonly notes: readonly string[];
}

export interface RelaySyncPlanner {
  plan(mapping: RelayMapping, model: RelayModel, destination: RelayDestination): SyncPlan;
}

// ── Demo adapters ──────────────────────────────────────────────────────────
function shortHash(seed: string) {
  let h = 0xa11_0a11;
  for (const c of seed) h = (Math.imul(h, 16777619) ^ c.charCodeAt(0)) >>> 0;
  return `0x${h.toString(16).padStart(8, '0').slice(0, 8)}`;
}

export class DemoSourceAdapter implements RelaySourceAdapter {
  readonly id = 'demo-source';
  readonly name = 'Demo Source Adapter';
  profile(source: RelaySource): ProfileResult {
    return {
      source,
      tablesProfiled: source.tableCount,
      piiCandidatesFound: source.piiClassesDetected.length,
      samplesRedacted: source.piiClassesDetected.length * 200,
      profileLatencyMs: 800 + source.tableCount * 6,
    };
  }
  extract(model: RelayModel, batchSize: number) {
    return {
      batchId: shortHash(`extract:${model.id}:${batchSize}`),
      estRecords: Math.min(batchSize, 50_000),
      cursor: `cursor:${model.id}:${shortHash(model.id)}`,
    };
  }
}

export class DemoDestinationAdapter implements RelayDestinationAdapter {
  readonly id = 'demo-destination';
  readonly name = 'Demo Destination Adapter';
  validateContract(mapping: RelayMapping, destination: RelayDestination) {
    const reasons: string[] = [];
    if (destination.authState !== 'connected') reasons.push(`auth state ${destination.authState}`);
    if (mapping.unmappedDestinationFieldCount > 0) reasons.push('required destination fields unmapped');
    if (!destination.piiAllowed && mapping.piiWarnings.length > 0) reasons.push('pii contract conflict');
    return { ok: reasons.length === 0, reasons };
  }
  deliver(batchId: string, records: number, destination: RelayDestination): DeliveryAck {
    const accepted = Math.max(0, records - Math.round(records * 0.012));
    const rejected = records - accepted;
    const latencyMs = 180 + Math.round((60_000 / Math.max(60, destination.rateLimitRpm)) * 4);
    return {
      destinationId: destination.id,
      batchId,
      accepted,
      rejected,
      witnessHash: shortHash(`ack:${batchId}:${destination.id}`),
      latencyMs,
    };
  }
}

export class DemoSyncPlanner implements RelaySyncPlanner {
  plan(mapping: RelayMapping, model: RelayModel, destination: RelayDestination): SyncPlan {
    const totalRecords = Math.min(50_000, model.fieldCount * 1200 + 3000);
    const ceiling = Math.min(5000, Math.max(500, destination.rateLimitRpm * 5));
    const batchCount = Math.max(1, Math.ceil(totalRecords / ceiling));
    const batches = Array.from({ length: batchCount }, (_, i) => {
      const records = i === batchCount - 1 ? totalRecords - ceiling * (batchCount - 1) : ceiling;
      return {
        batchId: shortHash(`batch:${mapping.id}:${i}`),
        records,
        estLatencyMs: 180 + Math.round((records / Math.max(60, destination.rateLimitRpm)) * 60_000),
      };
    });
    const notes: string[] = [];
    if (mapping.approvalRequired) notes.push(`Awaiting approval: ${mapping.approvalReason ?? 'flagged'}.`);
    if (destination.governanceState !== 'green') notes.push(`Destination governance ${destination.governanceState}.`);
    if (mapping.piiWarnings.length > 0) notes.push(`PII handling: ${mapping.piiWarnings.length} warning${mapping.piiWarnings.length === 1 ? '' : 's'}.`);
    return {
      mappingId: mapping.id,
      destinationId: destination.id,
      batches,
      totalRecords,
      estTotalLatencyMs: batches.reduce((s, b) => s + b.estLatencyMs, 0),
      notes,
    };
  }
}

export const DEMO_SOURCE_ADAPTER = new DemoSourceAdapter();
export const DEMO_DESTINATION_ADAPTER = new DemoDestinationAdapter();
export const DEMO_SYNC_PLANNER = new DemoSyncPlanner();
