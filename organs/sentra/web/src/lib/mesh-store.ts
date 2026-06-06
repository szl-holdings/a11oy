import { useSyncExternalStore } from 'react';
import { agentMesh, type FixType, type MeshExposure } from '@/data/agent-mesh';

const STORAGE_KEY = 'szl:mesh-state:v1';
const STORAGE_EVENT = 'szl:mesh-state:changed';

export type ApprovalTier = 'critical' | 'elevated' | 'standard';
export type ApprovalDomain = 'agent-mesh' | 'ot-response' | 'control-drift';

export interface FixRequest {
  id: string;
  exposureId?: string;
  fixType: FixType | 'isolate-segment';
  title: string;
  description: string;
  requestedAt: string;
  requestedBy: string;
  tier: ApprovalTier;
  domain: ApprovalDomain;
  proofHash: string;
  status: 'pending' | 'approved' | 'rejected';
  resolvedAt?: string;
  executionLog?: string[];
}

export interface ProofEntry {
  id: string;
  action: string;
  actor: string;
  status: 'VERIFIED' | 'PENDING';
  tag: string;
  proofHash: string;
  completedAt: string;
  highlight?: boolean;
  details?: string[];
}

export interface ServerOverride {
  pinned?: boolean;
  trustState?: 'trusted' | 'unverified' | 'quarantined';
  version?: string;
  detachedRuntimeIds?: string[];
}

export interface SecretRotation {
  rotatedAt: string;
  newScope: string;
  fingerprint: string;
}

export interface MeshState {
  exposureStatuses: Record<string, 'open' | 'fix-pending' | 'resolved'>;
  serverOverrides: Record<string, ServerOverride>;
  secretRotations: Record<string, SecretRotation>;
  fixRequests: FixRequest[];
  proofEntries: ProofEntry[];
  resilienceOverall: number;
  resilienceTrend: number;
  lastComputedAt: string;
}

const SEED_PROOFS: ProofEntry[] = [
  {
    id: 'seed-ot-isolation',
    action: 'OT-Segment Isolation',
    actor: 'CISO (Admin)',
    status: 'VERIFIED',
    tag: 'ot-response',
    proofHash: '0x8d1e...a290',
    completedAt: new Date(Date.now() - 2 * 3_600_000).toISOString(),
  },
  {
    id: 'seed-ransom-detect',
    action: 'Ransomware Payload Detection',
    actor: 'Signal Mesh',
    status: 'VERIFIED',
    tag: 'threat-detect',
    proofHash: '0x4f2a...91c0',
    completedAt: new Date(Date.now() - 4 * 3_600_000).toISOString(),
  },
  {
    id: 'seed-control-drift',
    action: 'Control Drift Alert: Respond',
    actor: 'System Engine',
    status: 'VERIFIED',
    tag: 'control-drift',
    proofHash: '0x6b88...30ff',
    completedAt: new Date(Date.now() - 12 * 3_600_000).toISOString(),
  },
  {
    id: 'seed-mesh-detect',
    action: 'Agent Mesh: GITHUB_TOKEN Exposure Detected',
    actor: 'Mesh Engine',
    status: 'VERIFIED',
    tag: 'agent-mesh',
    proofHash: '0x3a9f...c1d8',
    completedAt: new Date(Date.now() - 5 * 60_000).toISOString(),
    highlight: true,
  },
  {
    id: 'seed-mesh-violation',
    action: 'Agent Mesh: Containment Rule Violation — Codex CLI',
    actor: 'Mesh Engine',
    status: 'VERIFIED',
    tag: 'agent-mesh',
    proofHash: '0xae12...77b3',
    completedAt: new Date(Date.now() - 2 * 3_600_000).toISOString(),
    highlight: true,
  },
  {
    id: 'seed-mesh-drift',
    action: 'Agent Mesh: Mesh Drift — CLAUDE.md Unapproved Change',
    actor: 'Mesh Engine',
    status: 'VERIFIED',
    tag: 'agent-mesh',
    proofHash: '0x9d4b...22e1',
    completedAt: new Date(Date.now() - 5 * 3_600_000).toISOString(),
    highlight: true,
  },
];

const SEED_OT_APPROVAL: FixRequest = {
  id: 'apr-ot-segment',
  fixType: 'isolate-segment',
  title: 'Deploy OT-Segment Isolation — Ransomware Response',
  description:
    'Isolate compromised SCADA segment from ERP cluster to prevent ransomware lateral movement. Estimated $1.4M loss avoidance.',
  requestedAt: new Date(Date.now() - 2 * 3_600_000).toISOString(),
  requestedBy: 'CISO (Admin)',
  tier: 'critical',
  domain: 'ot-response',
  proofHash: '0x8d1e...a290',
  status: 'approved',
  resolvedAt: new Date(Date.now() - 90 * 60_000).toISOString(),
};

function buildSeedFromExposures(): FixRequest[] {
  const seeds: FixRequest[] = [SEED_OT_APPROVAL];
  for (const exp of agentMesh.exposures) {
    if (exp.status !== 'fix-pending') continue;
    seeds.push({
      id: `apr-${exp.id}`,
      exposureId: exp.id,
      fixType: exp.fixType,
      title: exp.fixLabel,
      description: exp.explanation,
      requestedAt: exp.detectedAt,
      requestedBy: 'Mesh Engine',
      tier: severityToTier(exp.severity),
      domain: 'agent-mesh',
      proofHash: exp.proofHash,
      status: 'pending',
    });
  }
  return seeds;
}

function severityToTier(sev: MeshExposure['severity']): ApprovalTier {
  if (sev === 'critical') return 'critical';
  if (sev === 'high') return 'elevated';
  return 'standard';
}

function initialState(): MeshState {
  const exposureStatuses: Record<string, 'open' | 'fix-pending' | 'resolved'> = {};
  for (const exp of agentMesh.exposures) exposureStatuses[exp.id] = exp.status;
  return {
    exposureStatuses,
    serverOverrides: {},
    secretRotations: {},
    fixRequests: buildSeedFromExposures(),
    proofEntries: SEED_PROOFS,
    resilienceOverall: agentMesh.resilienceIndex.overall,
    resilienceTrend: -4,
    lastComputedAt: agentMesh.resilienceIndex.computedAt,
  };
}

let memoryState: MeshState = initialState();
let hasLoaded = false;

function load(): MeshState {
  if (typeof window === 'undefined') return memoryState;
  if (hasLoaded) return memoryState;
  hasLoaded = true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<MeshState>;
      memoryState = { ...memoryState, ...parsed };
    }
  } catch {
    /* ignore */
  }
  return memoryState;
}

function persist(next: MeshState) {
  memoryState = next;
  if (typeof window !== 'undefined') {
    try {
      // Never write secret-rotation fingerprints to clear-text localStorage.
      // They stay in memoryState for the session but are excluded from the
      // serialized payload (clears CodeQL js/clear-text-storage-of-sensitive-data).
      const { secretRotations: _omitSecrets, ...persistable } = next;
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable));
      window.dispatchEvent(new CustomEvent(STORAGE_EVENT));
    } catch {
      /* ignore */
    }
  }
}

const listeners = new Set<() => void>();
function notify() {
  for (const l of listeners) l();
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY) {
      hasLoaded = false;
      load();
      notify();
    }
  });
  window.addEventListener(STORAGE_EVENT, () => notify());
}

export function getState(): MeshState {
  return load();
}

function update(mutator: (s: MeshState) => MeshState) {
  const next = mutator(load());
  persist(next);
  notify();
}

function shortHash(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  const hex = Math.abs(h).toString(16).padStart(8, '0');
  return `0x${hex.slice(0, 4)}...${hex.slice(4, 8)}`;
}

function recomputeResilience(state: MeshState): { overall: number; trend: number } {
  let bonus = 0;
  for (const exp of agentMesh.exposures) {
    if (state.exposureStatuses[exp.id] !== 'resolved') continue;
    if (exp.severity === 'critical') bonus += 14;
    else if (exp.severity === 'high') bonus += 8;
    else if (exp.severity === 'medium') bonus += 4;
    else bonus += 2;
  }
  const overall = Math.min(98, agentMesh.resilienceIndex.overall + bonus);
  const trend = overall - agentMesh.resilienceIndex.overall - 4;
  return { overall, trend };
}

export function gradeFor(score: number): 'A' | 'B' | 'C' | 'D' | 'F' {
  if (score >= 85) return 'A';
  if (score >= 70) return 'B';
  if (score >= 55) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}

export function queueFix(exposureId: string) {
  const exp = agentMesh.exposures.find((e) => e.id === exposureId);
  if (!exp) return;
  update((s) => {
    if (s.exposureStatuses[exposureId] !== 'open') return s;
    const reqId = `apr-${exposureId}`;
    if (s.fixRequests.some((r) => r.id === reqId)) return s;
    const req: FixRequest = {
      id: reqId,
      exposureId,
      fixType: exp.fixType,
      title: exp.fixLabel,
      description: exp.explanation,
      requestedAt: new Date().toISOString(),
      requestedBy: 'Mesh Engine',
      tier: severityToTier(exp.severity),
      domain: 'agent-mesh',
      proofHash: exp.proofHash,
      status: 'pending',
    };
    const pendingProof: ProofEntry = {
      id: `proof-pending-${reqId}`,
      action: `Agent Mesh: ${exp.fixLabel} — Submitted`,
      actor: 'Mesh Engine',
      status: 'PENDING',
      tag: 'agent-mesh',
      proofHash: exp.proofHash,
      completedAt: new Date().toISOString(),
      highlight: true,
    };
    return {
      ...s,
      exposureStatuses: { ...s.exposureStatuses, [exposureId]: 'fix-pending' },
      fixRequests: [...s.fixRequests, req],
      proofEntries: [pendingProof, ...s.proofEntries.filter((p) => p.id !== pendingProof.id)],
    };
  });
}

interface ExecutionResult {
  log: string[];
  serverOverrides?: Record<string, ServerOverride>;
  secretRotations?: Record<string, SecretRotation>;
}

function runExecutor(req: FixRequest, state: MeshState): ExecutionResult {
  const exp = req.exposureId ? agentMesh.exposures.find((e) => e.id === req.exposureId) : null;
  switch (req.fixType) {
    case 'rotate-secret': {
      const log = [
        'Calling GitHub API: POST /applications/{client_id}/grant — revoking exposed PAT',
        'Issuing replacement PAT scoped to read-only (repo:read, metadata:read)',
        'Updating ~/Library/Application Support/Claude/claude_desktop_config.json with new token reference',
        'Rolling token across 4 agent runtimes — push & PR scopes removed',
        'Audit entry written to receipt-graph: rotation acknowledged by Mesh Engine',
      ];
      const fingerprint = shortHash(`rot-${Date.now()}`);
      const rotations: Record<string, SecretRotation> = { ...state.secretRotations };
      if (exp) {
        for (const sid of exp.affectedSecretIds) {
          rotations[sid] = {
            rotatedAt: new Date().toISOString(),
            newScope: 'read-only (repo:read, metadata:read)',
            fingerprint,
          };
        }
      }
      return { log, secretRotations: rotations };
    }
    case 'pin-version': {
      const log: string[] = [];
      const overrides: Record<string, ServerOverride> = { ...state.serverOverrides };
      if (exp) {
        for (const sid of exp.affectedMcpIds) {
          const server = agentMesh.mcpServers.find((m) => m.id === sid);
          if (!server) continue;
          overrides[sid] = { ...overrides[sid], pinned: true, version: server.version };
          log.push(
            `Pinned ${server.packageRef}@${server.version} in claude_desktop_config.json + .cursor/mcp.json`,
          );
        }
      }
      log.push(
        'Committed config change as governed-pin/2026-04 with attestation 0x' +
          shortHash(req.id).slice(2),
      );
      return { log, serverOverrides: overrides };
    }
    case 'quarantine-server': {
      const log: string[] = [];
      const overrides: Record<string, ServerOverride> = { ...state.serverOverrides };
      if (exp) {
        for (const sid of exp.affectedMcpIds) {
          const server = agentMesh.mcpServers.find((m) => m.id === sid);
          if (!server) continue;
          overrides[sid] = {
            ...overrides[sid],
            trustState: 'quarantined',
            detachedRuntimeIds: server.runtimeIds,
          };
          log.push(
            `Detached ${server.name} from ${server.runtimeIds.length} runtime(s); install lock added to registry deny-list`,
          );
        }
      }
      log.push(
        'Egress firewall: blocked collect.ext-scraper.io, telemetry.scraper-cdn.net at gateway',
      );
      return { log, serverOverrides: overrides };
    }
    case 'scope-token': {
      const log = [
        'Updated containment rule: filesystem MCP allowed paths restricted to ~/workspace',
        'Re-evaluated 12 active edges — 4 agent-tool edges now compliant',
        'Set CLAUDE.md to 0444 read-only and moved outside MCP write scope',
      ];
      return { log };
    }
    case 'revoke-agent': {
      return {
        log: ['Revoked MCP access for affected agent runtime', 'Forced re-auth on next handshake'],
      };
    }
    case 'isolate-segment': {
      return { log: ['Pushed VLAN isolation policy to OT firewall cluster'] };
    }
  }
  return { log: ['Executor completed with no-op'] };
}

export function decideFix(reqId: string, decision: 'approved' | 'rejected') {
  update((s) => {
    const req = s.fixRequests.find((r) => r.id === reqId);
    if (req?.status !== 'pending') return s;
    const now = new Date().toISOString();
    const updatedReq: FixRequest = { ...req, status: decision, resolvedAt: now };

    let exposureStatuses = s.exposureStatuses;
    let serverOverrides = s.serverOverrides;
    let secretRotations = s.secretRotations;
    let proofEntries = s.proofEntries;

    if (decision === 'approved') {
      const result = runExecutor(req, s);
      updatedReq.executionLog = result.log;
      if (result.serverOverrides) serverOverrides = result.serverOverrides;
      if (result.secretRotations) secretRotations = result.secretRotations;
      if (req.exposureId) {
        exposureStatuses = { ...exposureStatuses, [req.exposureId]: 'resolved' };
      }
      proofEntries = [
        {
          id: `proof-done-${reqId}`,
          action: `Agent Mesh: ${req.title} — Executed`,
          actor: 'Guardian Executor',
          status: 'VERIFIED',
          tag: 'agent-mesh',
          proofHash: shortHash(`${reqId}-${now}`),
          completedAt: now,
          highlight: true,
          details: result.log,
        },
        ...proofEntries.filter((p) => p.id !== `proof-pending-${reqId}`),
      ];
    } else if (req.exposureId) {
      exposureStatuses = { ...exposureStatuses, [req.exposureId]: 'open' };
      proofEntries = proofEntries.filter((p) => p.id !== `proof-pending-${reqId}`);
    }

    const next: MeshState = {
      ...s,
      fixRequests: s.fixRequests.map((r) => (r.id === reqId ? updatedReq : r)),
      exposureStatuses,
      serverOverrides,
      secretRotations,
      proofEntries,
    };
    const { overall, trend } = recomputeResilience(next);
    next.resilienceOverall = overall;
    next.resilienceTrend = trend;
    next.lastComputedAt = now;
    return next;
  });
}

export function resetMeshState() {
  hasLoaded = true;
  memoryState = initialState();
  persist(memoryState);
}

export function useMeshState(): MeshState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getState,
    getState,
  );
}
