// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import {
  AlertTriangle,
  Bot,
  Clock,
  GitBranch,
  Loader2,
  Network,
  Shield,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  type AiSwarmDefenseResponse,
  getAiSwarmDefensePage,
} from '../lib/sentra-api';

const ROLE_COLORS: Record<string, string> = {
  detector: '#c9b787',
  analyzer: '#8a8a8a',
  disruptor: '#f5f5f5',
  coordinator: '#c9b787',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  engaged: 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10',
  standby: 'text-zinc-400 border-zinc-700 bg-zinc-800/50',
  deploying: 'text-[#8a8a8a] border-[#8a8a8a]/30 bg-[#8a8a8a]/10',
  mitigated: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  analyzing: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
};

export default function AISwarmDefense() {
  const [data, setData] = useState<AiSwarmDefenseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getAiSwarmDefensePage()
      .then((res) => {
        if (!active) return;
        if (!res) {
          setError('Unable to load AI Swarm Defense data.');
        } else {
          setData(res);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setPulse((p) => p + 1), 2000);
    return () => clearInterval(iv);
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-xs text-zinc-400">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading AI Swarm Defense data…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-[#f5f5f5]/30 bg-[#f5f5f5]/5 p-4 text-xs text-[#f5f5f5]">
          {error ?? 'AI Swarm Defense data unavailable.'}
        </div>
      </div>
    );
  }

  const { defenseAgents, swarmPatterns, killChainDisruptions, counterSwarm, metrics } = data;
  const totalBlocked = defenseAgents.reduce((s, a) => s + a.threatsBlocked, 0);
  const activeAgents = defenseAgents.filter((a) => a.status === 'active' || a.status === 'engaged').length;

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Shield className="w-5 h-5 text-[#c9b787]" />
            <h1 className="text-lg font-semibold text-white">AI Swarm Defense</h1>
            <span className="text-[9px] px-2 py-0.5 rounded-full border border-[#c9b787]/30 bg-[#c9b787]/10 text-[#c9b787] font-mono uppercase">
              Counter-Swarm Active
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            Parallel detection agent deployment, swarm pattern recognition, distributed kill-chain disruption
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Defense Agents', value: `${activeAgents}/${defenseAgents.length}`, sub: 'active / total deployed', color: '#c9b787', icon: Bot },
          { label: 'Swarm Attacks Detected', value: swarmPatterns.length.toString(), sub: `${swarmPatterns.filter(p => p.status === 'active').length} currently active`, color: '#f5f5f5', icon: AlertTriangle },
          { label: 'Threats Blocked (24h)', value: totalBlocked.toLocaleString(), sub: 'across all defense agents', color: '#c9b787', icon: Shield },
          { label: 'Avg Disruption Latency', value: metrics.avgDisruptionLatency, sub: 'from detection to block', color: '#8a8a8a', icon: Clock },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-xl font-bold text-white font-mono">{m.value}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Bot className="w-3.5 h-3.5 text-[#c9b787]" />
            Parallel Detection Agent Deployment
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {defenseAgents.map((agent) => {
              const isActive = agent.status === 'active' || agent.status === 'engaged';
              return (
                <div key={agent.id} className={cn(
                  'rounded-xl border p-3 transition-all',
                  agent.status === 'engaged' ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/3' : 'border-white/8 bg-white/3',
                )}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: isActive ? ROLE_COLORS[agent.role] : '#555' }} />
                      <span className="text-[10px] font-medium text-white">{agent.name}</span>
                    </div>
                    <span className={cn('text-[9px] px-1.5 py-0.5 rounded border', STATUS_COLORS[agent.status])}>
                      {agent.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 mb-1.5">
                    <span className="capitalize">{agent.role}</span>
                    <span>{agent.region}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-white/5">
                      <div className="h-full rounded-full transition-all" style={{
                        width: `${agent.load}%`,
                        background: agent.load > 80 ? '#f5f5f5' : '#c9b787',
                      }} />
                    </div>
                    <span className="text-[9px] text-zinc-500 font-mono">{agent.load}%</span>
                  </div>
                  {agent.threatsBlocked > 0 && (
                    <div className="text-[10px] text-[#c9b787] mt-1">{agent.threatsBlocked} blocked</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Network className="w-3.5 h-3.5 text-[#f5f5f5]" />
            Swarm Pattern Recognition
          </h2>
          <div className="space-y-2">
            {swarmPatterns.map((pattern) => (
              <div key={pattern.id} className={cn(
                'rounded-xl border p-3',
                pattern.status === 'active' ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/3' : 'border-white/8 bg-white/3',
              )}>
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <span className="text-[11px] font-medium text-white">{pattern.name}</span>
                  <span className={cn('text-[9px] px-1.5 py-0.5 rounded border shrink-0', STATUS_COLORS[pattern.status])}>
                    {pattern.status}
                  </span>
                </div>
                <p className="text-[10px] text-zinc-400 mb-1.5 leading-relaxed">{pattern.description}</p>
                <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                  <span className="text-[#c9b787] font-mono">{pattern.agentCount.toLocaleString()} sources</span>
                  <span>{pattern.confidence}% confidence</span>
                  <span>First seen: {pattern.firstSeen}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-[#c9b787]" />
          Distributed Kill-Chain Disruption
        </h2>
        <div className="grid grid-cols-7 gap-1.5">
          {killChainDisruptions.map((d, i) => {
            const isHighlight = pulse % killChainDisruptions.length === i;
            return (
              <div key={d.phase} className={cn(
                'rounded-xl border p-3 text-center transition-all',
                isHighlight ? 'border-[#c9b787]/40 bg-[#c9b787]/5' : 'border-white/8 bg-white/3',
              )}>
                <div className="text-lg font-bold text-white font-mono mb-1">{d.blocked.toLocaleString()}</div>
                <div className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1.5">{d.phase}</div>
                <div className="text-[9px] text-zinc-400">{d.method}</div>
                <div className="text-[9px] text-[#c9b787] mt-1 font-mono">{d.latency}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-[#c9b787]" />
          <span className="text-xs font-semibold text-[#c9b787]">Autonomous Counter-Swarm Response</span>
          <span className="text-[9px] text-zinc-500 font-mono ml-auto">Real-time · Coordinated defense</span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Active Counter-Swarms', value: counterSwarm.activeCounterSwarms.toString(), color: '#c9b787' },
            { label: 'IPs Blacklisted (24h)', value: counterSwarm.ipsBlacklisted24h.toLocaleString(), color: '#f5f5f5' },
            { label: 'Auto-Playbooks Executed', value: counterSwarm.autoPlaybooksExecuted.toString(), color: '#c9b787' },
            { label: 'False Positive Rate', value: counterSwarm.falsePositiveRate, color: '#8a8a8a' },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-lg font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
              <div className="text-[9px] text-zinc-500">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
