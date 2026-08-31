import { useState, useEffect } from 'react';
import { useApiQuery } from '@/lib/use-api-query';
import { api } from '@/lib/api';

const T = {
  bg: '#060608',
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.08)',
  text: '#f0f0f0',
  dim: '#8a8a8a',
  muted: '#5e5e5e',
  accent: '#c9b787',
  purple: '#8b5cf6',
  green: '#22c55e',
  orange: '#f97316',
  blue: '#3b82f6',
};

interface AgentTrace {
  id: string;
  name: string;
  domain: 'adversary-swarm' | 'covenant-gate' | 'countermove-proposer' | 'proof-chain' | 'prediction-engine';
  status: 'reasoning' | 'awaiting-approval' | 'proof-complete' | 'idle';
  current_step: string;
  proof_id: string;
  covenant_clause?: string;
  started_at: string;
  cyber_context: string;
}

const AGENT_TRACES: AgentTrace[] = [
  {
    id: 'agent-apt29-shadow', name: 'APT29 Shadow Agent', domain: 'adversary-swarm',
    status: 'reasoning',
    current_step: 'Executing lateral movement sequence #7 — pass-the-hash against twin identity layer',
    proof_id: 'proof-swarm-2941a4f',
    covenant_clause: 'Article IX, §2 — bounded by identity-layer scope',
    started_at: new Date(Date.now() - 42 * 60000).toISOString(),
    cyber_context: 'Swarm run #0041 — APT29 profile vs. digital twin',
  },
  {
    id: 'agent-cortex-predict', name: 'Cortex Prediction Engine', domain: 'prediction-engine',
    status: 'reasoning',
    current_step: 'Aggregating 3 swarm run outcomes → updating 72h horizon predictions',
    proof_id: 'proof-predict-7f2c1b',
    started_at: new Date(Date.now() - 12 * 60000).toISOString(),
    cyber_context: 'Future Threat Horizon update cycle',
  },
  {
    id: 'agent-covenant-gate', name: 'Covenant Gate', domain: 'covenant-gate',
    status: 'awaiting-approval',
    current_step: 'Evaluating countermove proposal cm-001 — Art. IX §2 credential rotation check',
    proof_id: 'proof-gate-9e3d2a',
    covenant_clause: 'Article IX, §2 — identity hardening tier',
    started_at: new Date(Date.now() - 8 * 60000).toISOString(),
    cyber_context: 'Countermove proposal for fth-001 (APT29)',
  },
  {
    id: 'agent-countermove', name: 'Countermove Proposer', domain: 'countermove-proposer',
    status: 'proof-complete',
    current_step: 'Countermove cm-002 staged — deception identity clone placed along APT29 path',
    proof_id: 'proof-cm-002a',
    covenant_clause: 'Article IX, §2 — deception placement pre-approved tier',
    started_at: new Date(Date.now() - 25 * 60000).toISOString(),
    cyber_context: 'fth-001 deception response — approved and staged',
  },
  {
    id: 'agent-lazarus-shadow', name: 'Lazarus Shadow Agent', domain: 'adversary-swarm',
    status: 'proof-complete',
    current_step: 'Swarm run complete — spear-phishing simulation finished. 3 predictions generated.',
    proof_id: 'proof-swarm-1ba9c7',
    started_at: new Date(Date.now() - 68 * 60000).toISOString(),
    cyber_context: 'Swarm run #0039 — Lazarus profile vs. digital twin',
  },
];

const DOMAIN_COLORS: Record<string, string> = {
  'adversary-swarm': '#ef4444',
  'covenant-gate': '#f59e0b',
  'countermove-proposer': '#22c55e',
  'proof-chain': '#c9b787',
  'prediction-engine': '#8b5cf6',
};
const STATUS_COLORS: Record<string, string> = {
  reasoning: '#3b82f6',
  'awaiting-approval': '#f97316',
  'proof-complete': '#22c55e',
  idle: '#5e5e5e',
};
const STATUS_ICONS: Record<string, string> = {
  reasoning: '◌',
  'awaiting-approval': '⏳',
  'proof-complete': '✓',
  idle: '○',
};

interface SwarmAgent {
  id: string;
  name: string;
  profile: string;
  status: string;
  current_step: string;
  covenant_gates_passed: number;
  swarm_run_id: string;
}

interface SwarmStatusData {
  active_agents: SwarmAgent[];
  twin_fidelity: number;
  total_runs_completed: number;
  covenant_gates_total: number;
  covenant_gates_blocked: number;
  last_updated: string;
}

const SWARM_FALLBACK: SwarmStatusData = {
  active_agents: [],
  twin_fidelity: 97.3,
  total_runs_completed: 41,
  covenant_gates_total: 287,
  covenant_gates_blocked: 12,
  last_updated: new Date().toISOString(),
};

const DOMAIN_MAP: Record<string, AgentTrace['domain']> = {
  'apt29-shadow': 'adversary-swarm',
  'lazarus-shadow': 'adversary-swarm',
  'cortex-predict': 'prediction-engine',
  'countermove': 'countermove-proposer',
};

const STATUS_MAP: Record<string, AgentTrace['status']> = {
  executing: 'reasoning',
  aggregating: 'reasoning',
  proposing: 'awaiting-approval',
  complete: 'proof-complete',
  idle: 'idle',
};

function mapSwarmAgentToTrace(a: SwarmAgent): AgentTrace {
  return {
    id: a.id,
    name: a.name,
    domain: DOMAIN_MAP[a.id] ?? 'adversary-swarm',
    status: STATUS_MAP[a.status] ?? 'idle',
    current_step: a.current_step,
    proof_id: `proof-${a.swarm_run_id}`,
    started_at: new Date(Date.now() - Math.floor(Math.random() * 3600000)).toISOString(),
    cyber_context: `Swarm run: ${a.swarm_run_id}`,
  };
}

function isSwarmAgentArray(agents: unknown[]): agents is SwarmAgent[] {
  return agents.length > 0 && typeof (agents[0] as SwarmAgent).swarm_run_id === 'string';
}

export default function A11oyBrainPanel() {
  const [tick, setTick] = useState(0);
  const [selectedTrace, setSelectedTrace] = useState<AgentTrace | null>(AGENT_TRACES[0]);

  const { data: swarmData } = useApiQuery<SwarmStatusData>(
    () => api.cortex.swarmStatus(),
    'data',
    SWARM_FALLBACK
  );
  const liveAgents: AgentTrace[] = (() => {
    const agents = swarmData.active_agents;
    if (!agents || agents.length === 0) return AGENT_TRACES;
    return isSwarmAgentArray(agents) ? agents.map(mapSwarmAgentToTrace) : AGENT_TRACES;
  })();

  useEffect(() => {
    const iv = setInterval(() => setTick(t => t + 1), 2500);
    return () => clearInterval(iv);
  }, []);

  const activeAgents = liveAgents.filter(a => a.status === 'reasoning' || a.status === 'awaiting-approval');
  const completedAgents = liveAgents.filter(a => a.status === 'proof-complete');

  return (
    <div className="min-h-screen p-6" style={{ background: T.bg, color: T.text }}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[10px] font-mono tracking-widest uppercase" style={{ color: T.purple }}>Cross-App Panel</span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded animate-pulse" style={{ background: 'rgba(139,92,246,0.1)', color: T.purple }}>a11oy CONNECTED</span>
          </div>
          <h1 className="text-3xl font-light mb-2" style={{ color: T.text, letterSpacing: '-0.02em' }}>a11oy Brain — Live Reasoning State</h1>
          <p className="text-sm" style={{ color: T.dim, maxWidth: 680 }}>
            a11oy is the brain; Sentra is its cyber lobe. This panel shows every a11oy agent currently reasoning about cyber state — adversary swarm agents, covenant gates, countermove proposers, and the prediction engine. Click any trace to jump to its proof chain.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            { label: 'Active Agents', value: activeAgents.length, color: T.blue },
            { label: 'Awaiting Approval', value: liveAgents.filter(a => a.status === 'awaiting-approval').length, color: T.orange },
            { label: 'Completed Runs', value: completedAgents.length, color: T.green },
            { label: 'Covenant Gates', value: liveAgents.filter(a => a.domain === 'covenant-gate').length, color: '#f59e0b' },
          ].map(kpi => (
            <div key={kpi.label} className="rounded-lg p-3 text-center" style={{ background: T.surface, border: `1px solid ${T.border}` }}>
              <div className="text-2xl font-mono font-bold" style={{ color: kpi.color }}>{kpi.value}</div>
              <div className="text-[9px] font-mono uppercase tracking-wide" style={{ color: T.muted }}>{kpi.label}</div>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 flex flex-col gap-3">
            <div className="text-[10px] font-mono uppercase tracking-widest mb-1" style={{ color: T.muted }}>Agent Traces — currently reasoning about cyber state</div>
            {liveAgents.map((trace, i) => (
              <button key={trace.id} onClick={() => setSelectedTrace(trace)} className="w-full text-left rounded-xl p-4 transition-all" style={{ background: selectedTrace?.id === trace.id ? 'rgba(139,92,246,0.05)' : T.surface, border: `1px solid ${selectedTrace?.id === trace.id ? 'rgba(139,92,246,0.2)' : T.border}`, cursor: 'pointer' }}>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-sm" style={{ background: `${DOMAIN_COLORS[trace.domain] ?? '#8b5cf6'}15`, color: DOMAIN_COLORS[trace.domain] ?? '#8b5cf6' }}>
                    {trace.status === 'reasoning' && i === tick % Math.max(1, liveAgents.filter(a => a.status === 'reasoning').length) ? '◉' : STATUS_ICONS[trace.status] ?? '○'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-xs font-semibold" style={{ color: T.text }}>{trace.name}</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: `${DOMAIN_COLORS[trace.domain]}12`, color: DOMAIN_COLORS[trace.domain] }}>{trace.domain.replace(/-/g, ' ')}</span>
                      <span className="text-[8px] font-mono px-1 py-0.5 rounded" style={{ background: `${STATUS_COLORS[trace.status]}10`, color: STATUS_COLORS[trace.status] }}>{trace.status.replace(/-/g, ' ')}</span>
                    </div>
                    <p className="text-[10px] mb-1" style={{ color: T.dim }}>{trace.current_step}</p>
                    <div className="text-[9px]" style={{ color: T.muted }}>{trace.cyber_context}</div>
                  </div>
                  <div className="flex-shrink-0 text-[9px] font-mono" style={{ color: T.muted }}>
                    {Math.round((Date.now() - new Date(trace.started_at).getTime()) / 60000)}m ago
                  </div>
                </div>
              </button>
            ))}
          </div>

          <div className="lg:col-span-2 flex flex-col gap-4">
            {selectedTrace ? (
              <>
                <div className="rounded-xl p-4" style={{ background: T.surface, border: `1px solid ${DOMAIN_COLORS[selectedTrace.domain]}25` }}>
                  <div className="text-[9px] font-mono uppercase tracking-widest mb-3" style={{ color: DOMAIN_COLORS[selectedTrace.domain] }}>Trace Detail</div>
                  <div className="text-sm font-semibold mb-1" style={{ color: T.text }}>{selectedTrace.name}</div>
                  <div className="text-[10px] mb-3" style={{ color: T.dim }}>{selectedTrace.cyber_context}</div>
                  <p className="text-[10px] mb-3 p-2.5 rounded" style={{ color: T.dim, background: 'rgba(255,255,255,0.02)', border: `1px solid ${T.border}` }}>{selectedTrace.current_step}</p>
                  {selectedTrace.covenant_clause && (
                    <div className="p-2.5 rounded mb-3" style={{ background: 'rgba(201,183,135,0.04)', border: '1px solid rgba(201,183,135,0.12)' }}>
                      <div className="text-[9px] font-mono mb-1" style={{ color: T.accent }}>Constitutional Citation</div>
                      <div className="text-[10px]" style={{ color: T.dim }}>{selectedTrace.covenant_clause}</div>
                    </div>
                  )}
                  <div className="flex items-center gap-2 p-2 rounded" style={{ background: 'rgba(34,197,94,0.04)', border: '1px solid rgba(34,197,94,0.12)' }}>
                    <span className="text-[10px] font-mono" style={{ color: T.green }}>Proof: {selectedTrace.proof_id}</span>
                    <button
                      onClick={() => {
                        const url = `/a11oy/proof-chain?proof=${encodeURIComponent(selectedTrace.proof_id)}&agent=${encodeURIComponent(selectedTrace.name)}`;
                        if (typeof window !== 'undefined') {
                          window.open(url, '_blank', 'noopener,noreferrer');
                        }
                      }}
                      className="ml-auto text-[9px] font-mono hover:underline"
                      style={{ color: T.accent, cursor: 'pointer', background: 'none', border: 'none' }}
                    >View in a11oy →</button>
                  </div>
                </div>

                <div className="rounded-xl p-4" style={{ background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.15)' }}>
                  <div className="text-[9px] font-mono uppercase tracking-widest mb-3" style={{ color: T.purple }}>One Brain, Many Lobes</div>
                  <div className="text-[10px] mb-3" style={{ color: T.dim }}>
                    This agent's reasoning is happening in a11oy — Sentra is its cyber lobe. The proof chain spans both apps. Every action this agent takes requires a constitutional citation.
                  </div>
                  <div className="flex gap-2">
                    <div className="flex-1 p-2 rounded text-center" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)' }}>
                      <div className="text-[10px] font-mono" style={{ color: T.purple }}>a11oy</div>
                      <div className="text-[9px]" style={{ color: T.muted }}>Brain</div>
                    </div>
                    <div className="flex items-center text-[10px]" style={{ color: T.muted }}>→</div>
                    <div className="flex-1 p-2 rounded text-center" style={{ background: 'rgba(201,183,135,0.08)', border: '1px solid rgba(201,183,135,0.2)' }}>
                      <div className="text-[10px] font-mono" style={{ color: T.accent }}>Sentra</div>
                      <div className="text-[9px]" style={{ color: T.muted }}>Cyber Lobe</div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-xl p-8 text-center" style={{ background: T.surface, border: `1px solid ${T.border}` }}>
                <div className="text-[10px]" style={{ color: T.muted }}>Select an agent trace to inspect</div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 p-3 rounded-lg text-[10px] flex items-center gap-2" style={{ background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.15)', color: T.muted }}>
          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: T.purple }} />
          a11oy Brain — {activeAgents.length} agents currently reasoning about your cyber state. Not a single action bypasses the brain.
          <span className="ml-auto font-mono" style={{ color: T.purple }}>a11oy Cyber Lobe · Art. IX</span>
        </div>
      </div>
    </div>
  );
}
