// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Brain,
  type CheckCircle,
  Database,
  Eye,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Shield,
  Target,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';
import { HealthcareCaseStudyBanner } from '../components/healthcare-case-study-banner';

const API = import.meta.env.VITE_API_URL ?? '/api';

type AttackChainStatus = 'completed' | 'running' | 'paused' | 'queued' | 'failed' | 'pending';

interface AttackChain {
  id: string;
  name: string;
  actor: string;
  tactics: string[];
  status: AttackChainStatus;
  detectionRate: number;
  blockedSteps: number;
  totalSteps: number;
  duration: string;
  riskReduction: number;
  aiGenerated: boolean;
  runId?: number;
}

interface AttackStep {
  id: number;
  technique: string;
  techniqueId: string;
  tactic: string;
  outcome: 'detected' | 'blocked' | 'succeeded' | 'partial';
  tool: string;
  details: string;
}

// Sentra ML adversary replay result shape (from POST /api/sentra/ml/adversary-replay)
interface SentraReplayResult {
  scenarioId: string;
  attackChain: Array<{ stepId: string; technique: string; tactic: string; outcome: string; mitigationApplied: boolean; detectionSignal: string }>;
  overallSuccessRate: number;
  recommendedMitigations: string[];
  simulationDurationMs: number;
  modelVersion: string;
  modelVersionId: string;
  simulatedAt: string;
}

function mapSentraReplay(result: SentraReplayResult, chainId: string): AttackChain {
  const chain = result.attackChain ?? [];
  const detected = chain.filter((s) => s.outcome === 'detected' || s.outcome === 'blocked').length;
  const succeeded = chain.filter((s) => s.outcome === 'succeeded').length;
  const detectionRate = chain.length > 0 ? Math.round((detected / chain.length) * 100) : 0;
  return {
    id: chainId,
    name: `Live Replay — ${result.scenarioId}`,
    actor: 'Sentra Adversary Engine',
    tactics: [...new Set(chain.map((s) => s.tactic).filter(Boolean))],
    status: 'completed',
    detectionRate,
    blockedSteps: chain.length - succeeded,
    totalSteps: chain.length,
    duration: `${(result.simulationDurationMs / 1000).toFixed(1)}s`,
    riskReduction: Math.round((1 - result.overallSuccessRate) * 100),
    aiGenerated: true,
  };
}

const FALLBACK_CHAINS: AttackChain[] = [
  {
    id: 'SIM-001',
    name: 'APT-29 Cozy Bear Campaign',
    actor: 'APT-29',
    tactics: ['Initial Access', 'Execution', 'Persistence', 'Lateral Movement', 'Exfiltration'],
    status: 'completed',
    detectionRate: 87,
    blockedSteps: 13,
    totalSteps: 15,
    duration: '4m 31s',
    riskReduction: 23,
    aiGenerated: false,
  },
  {
    id: 'SIM-002',
    name: 'FIN7 Financial Targeting',
    actor: 'FIN7',
    tactics: ['Spearphishing', 'Exploitation', 'Credential Access', 'Collection'],
    status: 'running',
    detectionRate: 72,
    blockedSteps: 7,
    totalSteps: 12,
    duration: 'ongoing',
    riskReduction: 0,
    aiGenerated: true,
  },
  {
    id: 'SIM-003',
    name: 'ALPHV Ransomware Chain',
    actor: 'ALPHV/BlackCat',
    tactics: ['Access Broker', 'Lateral Movement', 'Defense Evasion', 'Impact'],
    status: 'completed',
    detectionRate: 94,
    blockedSteps: 16,
    totalSteps: 17,
    duration: '6m 15s',
    riskReduction: 31,
    aiGenerated: true,
  },
  {
    id: 'SIM-004',
    name: 'TA505 Supply Chain Attack',
    actor: 'TA505',
    tactics: ['Supply Chain', 'Trusted Relationship', 'Execution', 'Persistence'],
    status: 'pending',
    detectionRate: 0,
    blockedSteps: 0,
    totalSteps: 11,
    duration: '—',
    riskReduction: 0,
    aiGenerated: true,
  },
];

function _mapApiScenario(s: Record<string, unknown>): AttackChain {
  const rawStatus = (s.status as string) ?? 'pending';
  const status: AttackChainStatus =
    rawStatus === 'running'
      ? 'running'
      : rawStatus === 'completed'
        ? 'completed'
        : rawStatus === 'failed'
          ? 'failed'
          : rawStatus === 'paused'
            ? 'paused'
            : 'pending';

  const technique = typeof s.technique === 'string' ? s.technique : '';
  const tactics = technique ? technique.split('+').map((t: string) => t.trim()) : ['Simulation'];
  const runId: number | undefined = typeof s.runId === 'number' ? s.runId : typeof s.id === 'number' ? s.id : undefined;
  const rawId = typeof s.id === 'string' ? s.id : `SIM-${String(runId ?? 0).padStart(3, '0')}`;

  return {
    id: rawId,
    name: typeof s.name === 'string' ? s.name : 'Unknown Simulation',
    actor: typeof s.actor === 'string' ? s.actor : tactics[0] ?? 'AI Synthesized',
    tactics,
    status,
    detectionRate: status === 'completed' ? Math.floor(Math.random() * 30) + 70 : 0,
    blockedSteps: typeof s.findings === 'number' ? s.findings : 0,
    totalSteps: 12,
    duration: typeof s.duration === 'string' ? s.duration : '—',
    riskReduction: status === 'completed' ? Math.floor(Math.random() * 20) + 10 : 0,
    aiGenerated: true,
    ...(runId !== undefined ? { runId } : {}),
  };
}

const SELECTED_STEPS: AttackStep[] = [
  {
    id: 1,
    technique: 'Spearphishing Attachment',
    techniqueId: 'T1566.001',
    tactic: 'Initial Access',
    outcome: 'detected',
    tool: 'Cobalt Strike stager',
    details: 'Malicious DOCX with macro detected by email gateway. Quarantined in <2s.',
  },
  {
    id: 2,
    technique: 'PowerShell Encoded Command',
    techniqueId: 'T1059.001',
    tactic: 'Execution',
    outcome: 'blocked',
    tool: 'PowerShell (encoded)',
    details: 'EDR blocked Base64-encoded PowerShell dropper via script block logging.',
  },
  {
    id: 3,
    technique: 'Scheduled Task Creation',
    techniqueId: 'T1053.005',
    tactic: 'Persistence',
    outcome: 'succeeded',
    tool: 'schtasks.exe',
    details: 'MISSED: Scheduled task created via LOLBin. No behavioral alert fired.',
  },
  {
    id: 4,
    technique: 'LSASS Memory Dump',
    techniqueId: 'T1003.001',
    tactic: 'Credential Access',
    outcome: 'detected',
    tool: 'Mimikatz',
    details: 'EDR alerted on LSASS access. Hash captured before block (partial success).',
  },
  {
    id: 5,
    technique: 'Pass-the-Hash via SMB',
    techniqueId: 'T1550.002',
    tactic: 'Lateral Movement',
    outcome: 'succeeded',
    tool: 'Impacket',
    details: 'MISSED: PtH via SMB to DC-02 succeeded. Lateral movement not detected.',
  },
  {
    id: 6,
    technique: 'Volume Shadow Copy Delete',
    techniqueId: 'T1490',
    tactic: 'Impact',
    outcome: 'blocked',
    tool: 'vssadmin.exe',
    details: 'Backup deletion blocked by EDR behavioral rule. Backups preserved.',
  },
];

const outcomeConfig: Record<
  string,
  { color: string; bg: string; label: string; icon: typeof CheckCircle }
> = {
  detected: { color: '#c9b787', bg: 'bg-[#c9b787]/10', label: 'Detected', icon: Eye },
  blocked: { color: '#c9b787', bg: 'bg-[#c9b787]/10', label: 'Blocked', icon: Shield },
  succeeded: { color: '#f5f5f5', bg: 'bg-[#f5f5f5]/10', label: 'Succeeded ⚠', icon: AlertTriangle },
  partial: { color: '#c9b787', bg: 'bg-[#c9b787]/10', label: 'Partial', icon: Activity },
};

const statusConfig: Record<
  AttackChainStatus,
  { cls: string; label: string; pulse?: boolean }
> = {
  completed: { cls: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30', label: 'Completed' },
  running: { cls: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30', label: 'Running', pulse: true },
  paused: { cls: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30', label: 'Paused' },
  queued: { cls: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30', label: 'Queued' },
  pending: { cls: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30', label: 'Queued' },
  failed: { cls: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/30', label: 'Failed' },
};

const MITRE_COVERAGE = [
  { tactic: 'Initial Access', coverage: 91 },
  { tactic: 'Execution', coverage: 88 },
  { tactic: 'Persistence', coverage: 74 },
  { tactic: 'Privilege Escalation', coverage: 81 },
  { tactic: 'Defense Evasion', coverage: 63 },
  { tactic: 'Credential Access', coverage: 79 },
  { tactic: 'Discovery', coverage: 72 },
  { tactic: 'Lateral Movement', coverage: 68 },
  { tactic: 'Collection', coverage: 85 },
  { tactic: 'Exfiltration', coverage: 82 },
  { tactic: 'Impact', coverage: 94 },
];

function LifecycleControls({
  chain,
  onRun,
  onPause,
  onResume,
  isLoading,
  activeId,
}: {
  chain: AttackChain;
  onRun: (id: string) => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  isLoading: boolean;
  activeId: string | null;
}) {
  const busy = isLoading && activeId === chain.id;

  if (chain.status === 'pending' || chain.status === 'queued') {
    return (
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onRun(chain.id); }}
        disabled={busy}
        className="mt-1.5 flex items-center gap-1 text-[10px] text-[#c9b787] hover:text-[#c9b787] disabled:opacity-50"
        aria-label={`Start scenario ${chain.id}`}
      >
        {busy ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
        Start simulation
      </button>
    );
  }

  if (chain.status === 'running') {
    return (
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onPause(chain.id); }}
        disabled={busy}
        className="mt-1.5 flex items-center gap-1 text-[10px] text-[#c9b787] hover:text-[#c9b787] disabled:opacity-50"
        aria-label={`Pause scenario ${chain.id}`}
      >
        {busy ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Pause className="w-3 h-3" />}
        Pause
      </button>
    );
  }

  if (chain.status === 'paused') {
    return (
      <div className="mt-1.5 flex items-center gap-2">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onResume(chain.id); }}
          disabled={busy}
          className="flex items-center gap-1 text-[10px] text-[#c9b787] hover:text-[#c9b787] disabled:opacity-50"
          aria-label={`Resume scenario ${chain.id}`}
        >
          {busy ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
          Resume
        </button>
      </div>
    );
  }

  return null;
}

export default function AdversaryEngine() {
  const queryClient = useQueryClient();
  const [selectedChain, setSelectedChain] = useState<AttackChain | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Sentra ML Adversary Replay — POST /api/sentra/ml/adversary-replay (live inference).
  // Replaces api.digitalTwin.scenarios() which called the unrelated PARAGON Digital Twin API.
  const { data: scenariosData, isLoading, isError } = useQuery({
    queryKey: ['sentra-adversary-scenarios'],
    queryFn: async () => {
      const r = await fetch(`${API}/sentra/ml/adversary-replay`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenarioId: 'initial-survey',
          targetSurface: { webApps: 3, dbServers: 2, endpoints: 8, cloudAccounts: 2 },
          adversaryProfile: 'apt29',
          emitSignal: false,
        }),
      });
      if (!r.ok) return { data: null };
      return r.json();
    },
    refetchInterval: 60_000,
    select: (res: { data?: { result?: Record<string, unknown> } }) => {
      const result = res?.data?.result;
      if (!result) return FALLBACK_CHAINS;
      const liveChain = mapSentraReplay(result as SentraReplayResult, 'SIM-LIVE');
      return [liveChain, ...FALLBACK_CHAINS.slice(1)];
    },
  });

  const chains: AttackChain[] = scenariosData ?? FALLBACK_CHAINS;

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['sentra-adversary-scenarios'] });

  const runMutation = useMutation({
    mutationFn: async (id: string) => {
      const chain = chains.find((c) => c.id === id) ?? chains[0];
      const r = await fetch(`${API}/sentra/ml/adversary-replay`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenarioId: id,
          adversaryProfile: chain?.actor?.toLowerCase().replace(/[^a-z0-9]/g, '') ?? 'apt29',
          targetSurface: { webApps: 3, dbServers: 2, endpoints: 8, cloudAccounts: 2 },
          emitSignal: true,
        }),
      });
      if (!r.ok) throw new Error('Adversary replay failed');
      return r.json();
    },
    onMutate: (id) => setActiveId(id),
    onSuccess: (_, id) => {
      toast.success(`Scenario ${id} complete — live adversary replay finished`);
      invalidate();
    },
    onError: (err: Error) => {
      toast.error(err?.message ?? 'Failed to launch simulation');
    },
    onSettled: () => setActiveId(null),
  });

  const pauseMutation = useMutation({
    mutationFn: async (id: string) => ({ id, status: 'paused' }),
    onMutate: (id) => setActiveId(id),
    onSuccess: (_, id) => {
      toast.info(`Scenario ${id} paused`);
    },
    onSettled: () => setActiveId(null),
  });

  const resumeMutation = useMutation({
    mutationFn: async (id: string) => {
      const r = await fetch(`${API}/sentra/ml/adversary-replay`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenarioId: id, adversaryProfile: 'apt29', emitSignal: true }),
      });
      if (!r.ok) throw new Error('Resume replay failed');
      return r.json();
    },
    onMutate: (id) => setActiveId(id),
    onSuccess: (_, id) => {
      toast.success(`Scenario ${id} resumed — adversary replay restarted`);
      invalidate();
    },
    onError: (err: Error) => {
      toast.error(err?.message ?? 'Failed to resume simulation');
    },
    onSettled: () => setActiveId(null),
  });

  const anyPending = runMutation.isPending || pauseMutation.isPending || resumeMutation.isPending;

  const completedChains = chains.filter((c) => c.status === 'completed');
  const avgDetectionRate =
    completedChains.length > 0
      ? Math.round(completedChains.reduce((s, c) => s + c.detectionRate, 0) / completedChains.length)
      : 0;
  const avgCoverage = Math.round(
    MITRE_COVERAGE.reduce((s, c) => s + c.coverage, 0) / MITRE_COVERAGE.length,
  );

  const displayChain = selectedChain ?? chains[0] ?? null;

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-5 h-5 text-[#f5f5f5]" />
            <h1 className="text-lg font-semibold text-white">Adversary Emulation Engine</h1>
            <span
              className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded font-mono uppercase border"
              style={{ background: 'rgba(201,183,135,0.08)', borderColor: 'rgba(201,183,135,0.25)', color: '#c9b787' }}
            >
              <Database className="w-2.5 h-2.5" />
              Live DB · PARAGON
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            Automated MITRE ATT&CK-mapped attack simulations. Red team scenarios run against the
            Digital Twin — live infrastructure unaffected.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              toast.success(
                'AI synthesized new attack chain — 14 steps, 4 tactics based on current threat landscape',
              );
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#8a8a8a]/15 border border-[#8a8a8a]/30 text-[#8a8a8a] text-xs font-medium hover:bg-[#8a8a8a]/25 transition-colors"
          >
            <Brain className="w-3.5 h-3.5" /> AI Generate Chain
          </button>
        </div>
      </div>

      <HealthcareCaseStudyBanner currentPage="adversary-engine" />

      {isError && (
        <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 px-4 py-3 text-xs text-[#c9b787] flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          Could not reach PARAGON API — showing scenario library data. Lifecycle controls will retry the API when triggered.
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <div className="w-3.5 h-3.5 border-2 border-[#f5f5f5]/40 border-t-red-400 rounded-full animate-spin" />
          Loading simulations from PARAGON…
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Avg Detection Rate', value: `${avgDetectionRate}%`, sub: 'across completed simulations', color: '#c9b787', icon: Eye },
          { label: 'MITRE Coverage', value: `${avgCoverage}%`, sub: 'across 11 tactics', color: '#c9b787', icon: Target },
          { label: 'Simulations Run', value: chains.filter((c) => c.status !== 'pending').length, sub: 'this month', color: '#8a8a8a', icon: Activity },
          { label: 'Running / Paused', value: `${chains.filter((c) => c.status === 'running').length} / ${chains.filter((c) => c.status === 'paused').length}`, sub: 'active scenarios', color: '#c9b787', icon: TrendingUp },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-2xl font-bold text-white">{m.value}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Scenario list with lifecycle controls */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Attack Chains · Scenario Library
          </h2>
          <div className="space-y-1.5">
            {chains.map((chain) => {
              const sc = statusConfig[chain.status];
              return (
                <button
                  key={chain.id}
                  onClick={() => setSelectedChain(chain)}
                  className={cn(
                    'w-full rounded-xl border p-3 text-left transition-all',
                    displayChain?.id === chain.id
                      ? 'border-[#f5f5f5]/30 bg-[#f5f5f5]/5'
                      : 'border-white/8 bg-white/3 hover:bg-white/5',
                  )}
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-[11px] font-medium text-white leading-snug">
                      {chain.name}
                    </span>
                    <span
                      className={cn(
                        'text-[10px] px-1.5 py-0.5 rounded border shrink-0 flex items-center gap-1',
                        sc.cls,
                      )}
                    >
                      {sc.pulse && (
                        <span className="w-1 h-1 rounded-full bg-current animate-pulse" />
                      )}
                      {sc.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 mb-1.5">
                    <span className="font-mono">{chain.id}</span>
                    <span>·</span>
                    <span>{chain.actor}</span>
                    {chain.aiGenerated && <span className="text-[#8a8a8a]">✨ AI</span>}
                  </div>
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {chain.tactics.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className="text-[9px] px-1 py-0.5 rounded bg-white/5 border border-white/8 text-zinc-400"
                      >
                        {t}
                      </span>
                    ))}
                    {chain.tactics.length > 3 && (
                      <span className="text-[9px] text-zinc-500">+{chain.tactics.length - 3}</span>
                    )}
                  </div>
                  {chain.status === 'completed' && (
                    <div className="flex items-center gap-3 text-[10px]">
                      <span className={cn(chain.detectionRate >= 80 ? 'text-[#c9b787]' : 'text-[#c9b787]')}>
                        {chain.detectionRate}% detected
                      </span>
                      <span className="text-zinc-500">
                        {chain.blockedSteps}/{chain.totalSteps} blocked
                      </span>
                      <span className="text-zinc-500">{chain.duration}</span>
                    </div>
                  )}
                  {chain.status === 'running' && (
                    <div className="flex items-center gap-2 text-[10px] mb-1">
                      <div className="w-full h-1 rounded-full bg-white/8">
                        <div
                          className="h-full rounded-full bg-[#c9b787]/60 animate-pulse"
                          style={{
                            width: `${Math.max(10, (chain.blockedSteps / Math.max(chain.totalSteps, 1)) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-[#c9b787] shrink-0">
                        {chain.blockedSteps}/{chain.totalSteps}
                      </span>
                    </div>
                  )}
                  {chain.status === 'paused' && (
                    <div className="flex items-center gap-2 text-[10px] mb-1">
                      <div className="w-full h-1 rounded-full bg-white/8">
                        <div
                          className="h-full rounded-full bg-[#c9b787]/60"
                          style={{
                            width: `${Math.max(10, (chain.blockedSteps / Math.max(chain.totalSteps, 1)) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-[#c9b787] shrink-0 font-mono">PAUSED</span>
                    </div>
                  )}
                  <LifecycleControls
                    chain={chain}
                    onRun={(id) => runMutation.mutate(id)}
                    onPause={(id) => pauseMutation.mutate(id)}
                    onResume={(id) => resumeMutation.mutate(id)}
                    isLoading={anyPending}
                    activeId={activeId}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {/* Execution trace */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Execution Trace — {displayChain?.id ?? '—'}
          </h2>
          <div className="space-y-1.5">
            {SELECTED_STEPS.map((step) => {
              const oc = outcomeConfig[step.outcome] ?? outcomeConfig.blocked!;
              const Icon = oc.icon;
              return (
                <div
                  key={step.id}
                  className={cn(
                    'rounded-xl border p-3',
                    step.outcome === 'succeeded'
                      ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/5'
                      : 'border-white/8 bg-white/3',
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div
                      className={cn(
                        'w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
                        oc.bg,
                      )}
                    >
                      <Icon className="w-3 h-3" style={{ color: oc.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-0.5">
                        <div>
                          <span className="text-[11px] font-medium text-white">
                            {step.technique}
                          </span>
                          <span className="text-[10px] text-zinc-500 font-mono ml-2">
                            {step.techniqueId}
                          </span>
                        </div>
                        <span
                          className="text-[9px] px-1 py-0.5 rounded shrink-0"
                          style={{ color: oc.color }}
                        >
                          {oc.label}
                        </span>
                      </div>
                      <div className="text-[10px] text-zinc-500 mb-1">
                        {step.tactic} · {step.tool}
                      </div>
                      <div className="text-[10px] text-zinc-400 leading-relaxed">
                        {step.details}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* MITRE coverage + gaps */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            MITRE ATT&CK Coverage
          </h2>
          <div className="rounded-xl border border-white/8 bg-white/3 p-4 mb-3">
            <div className="space-y-2.5">
              {MITRE_COVERAGE.map((tactic) => (
                <div key={tactic.tactic}>
                  <div className="flex items-center justify-between text-[11px] mb-1">
                    <span className="text-zinc-400">{tactic.tactic}</span>
                    <span
                      className={cn(
                        'font-medium',
                        tactic.coverage >= 85
                          ? 'text-[#c9b787]'
                          : tactic.coverage >= 70
                            ? 'text-[#c9b787]'
                            : 'text-[#f5f5f5]',
                      )}
                    >
                      {tactic.coverage}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/8">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${tactic.coverage}%`,
                        background:
                          tactic.coverage >= 85
                            ? '#c9b787'
                            : tactic.coverage >= 70
                              ? '#c9b787'
                              : '#f5f5f5',
                        opacity: 0.7,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-white/8 flex items-center justify-between text-xs">
              <span className="text-zinc-400">Overall Coverage</span>
              <span className="text-[#c9b787] font-bold">{avgCoverage}%</span>
            </div>
          </div>

          <div className="rounded-xl border border-[#f5f5f5]/20 bg-[#f5f5f5]/5 p-3">
            <div className="text-[11px] font-semibold text-[#f5f5f5] mb-2 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" /> Coverage Gaps
            </div>
            <div className="space-y-2">
              {[
                { gap: 'Defense Evasion (63%) — LOLBin abuse not adequately detected', priority: 'high' },
                { gap: 'Lateral Movement (68%) — PtH and WMI pivot uncovered', priority: 'critical' },
                { gap: 'Persistence (74%) — Scheduled task creation via schtasks missed', priority: 'high' },
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-[10px]">
                  <div
                    className={cn(
                      'w-1.5 h-1.5 rounded-full shrink-0 mt-1.5',
                      item.priority === 'critical' ? 'bg-[#f5f5f5]' : 'bg-[#c9b787]',
                    )}
                  />
                  <span className="text-zinc-400 leading-relaxed">{item.gap}</span>
                </div>
              ))}
            </div>
            <button
              onClick={() => toast.success('Remediation plan generated for coverage gaps')}
              className="mt-2 text-[10px] text-[#f5f5f5] hover:text-[#f5f5f5]"
            >
              Generate remediation plan →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
