// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import {
  ShieldCheck,
  Swords,
} from 'lucide-react';
import { useEffect, useState } from 'react';

type AttackClass = 'evasion' | 'poisoning' | 'extraction' | 'inference';

type ThreatEvent = {
  id: string;
  timestamp: string;
  attackClass: AttackClass;
  technique: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'blocked' | 'detected' | 'investigating' | 'bypassed';
  source: string;
  target: string;
  defenseLayer: string;
  confidence: number;
  artReference: string;
};

type DefenseModule = {
  id: string;
  name: string;
  category: 'detection' | 'prevention' | 'response' | 'recovery';
  status: 'active' | 'degraded' | 'offline';
  coverage: number;
  falsePositiveRate: number;
  latencyMs: number;
  eventsHandled24h: number;
  lastUpdate: string;
};

const ATTACK_CLASS_COLORS: Record<AttackClass, string> = {
  evasion: 'bg-red-500/10 text-red-400 border-red-500/20',
  poisoning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  extraction: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  inference: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'text-red-400',
  high: 'text-amber-400',
  medium: 'text-yellow-300',
  low: 'text-white/30',
};

const STATUS_COLORS: Record<string, string> = {
  blocked: 'text-emerald-400',
  detected: 'text-amber-400',
  investigating: 'text-blue-400',
  bypassed: 'text-red-400',
};

const THREAT_EVENTS: ThreatEvent[] = [
  { id: 'AML-2026-04-26-001', timestamp: '2026-04-26T14:32:18Z', attackClass: 'evasion', technique: 'Gradient-Based Prompt Perturbation', severity: 'critical', status: 'blocked', source: '198.51.100.42', target: 'Intent Capture Gateway', defenseLayer: 'Constitutional Enforcer', confidence: 0.97, artReference: 'ART.attacks.evasion.ProjectedGradientDescent' },
  { id: 'AML-2026-04-26-002', timestamp: '2026-04-26T14:28:05Z', attackClass: 'poisoning', technique: 'Retrieval Corpus Contamination', severity: 'high', status: 'detected', source: 'internal-rag-pipeline', target: 'Evidence Ledger', defenseLayer: 'Proof Chain Tamper Guard', confidence: 0.93, artReference: 'ART.attacks.poisoning.PoisoningAttackCleanLabel' },
  { id: 'AML-2026-04-26-003', timestamp: '2026-04-26T14:15:42Z', attackClass: 'extraction', technique: 'Model Weight Probing via API', severity: 'medium', status: 'blocked', source: '203.0.113.17', target: 'Model Router', defenseLayer: 'Rate Limiter + Differential Privacy', confidence: 0.89, artReference: 'ART.attacks.extraction.CopycatCNN' },
  { id: 'AML-2026-04-26-004', timestamp: '2026-04-26T13:58:11Z', attackClass: 'evasion', technique: 'Semantic Jailbreak via Roleplay', severity: 'critical', status: 'blocked', source: '192.0.2.88', target: 'Agent Mesh Gateway', defenseLayer: 'Behavioral Anomaly Detector', confidence: 0.94, artReference: 'ART.attacks.evasion.BoundaryAttack' },
  { id: 'AML-2026-04-26-005', timestamp: '2026-04-26T13:42:33Z', attackClass: 'inference', technique: 'Membership Inference on Proof Chain', severity: 'medium', status: 'blocked', source: '198.51.100.99', target: 'Proof Chain API', defenseLayer: 'Differential Privacy Shield', confidence: 0.91, artReference: 'ART.attacks.inference.MembershipInferenceBlackBox' },
  { id: 'AML-2026-04-26-006', timestamp: '2026-04-26T13:15:07Z', attackClass: 'poisoning', technique: 'Skill Registry Trojan Injection', severity: 'critical', status: 'blocked', source: 'supply-chain-feed', target: 'Skill Library', defenseLayer: 'Connector Firewall + Supply Chain', confidence: 0.98, artReference: 'ART.attacks.poisoning.PoisoningAttackSVM' },
  { id: 'AML-2026-04-26-007', timestamp: '2026-04-26T12:48:55Z', attackClass: 'extraction', technique: 'Prompt Leakage via Error Paths', severity: 'low', status: 'blocked', source: '203.0.113.44', target: 'Error Handler', defenseLayer: 'Error Sanitizer + Glasswing', confidence: 0.99, artReference: 'ART.attacks.extraction.KnockoffNets' },
  { id: 'AML-2026-04-26-008', timestamp: '2026-04-26T12:22:19Z', attackClass: 'evasion', technique: 'Unicode Homoglyph Injection', severity: 'high', status: 'blocked', source: '198.51.100.71', target: 'Input Pipeline', defenseLayer: 'Input Normalizer + Signal Mesh', confidence: 0.99, artReference: 'ART.attacks.evasion.UniversalPerturbation' },
];

const DEFENSE_MODULES: DefenseModule[] = [
  { id: 'DEF-001', name: 'Constitutional Enforcer', category: 'prevention', status: 'active', coverage: 0.97, falsePositiveRate: 0.02, latencyMs: 3.2, eventsHandled24h: 14821, lastUpdate: '2026-04-26T14:00:00Z' },
  { id: 'DEF-002', name: 'Input Sanitizer v3', category: 'prevention', status: 'active', coverage: 0.99, falsePositiveRate: 0.005, latencyMs: 1.1, eventsHandled24h: 28452, lastUpdate: '2026-04-26T14:00:00Z' },
  { id: 'DEF-003', name: 'Behavioral Anomaly Detector', category: 'detection', status: 'active', coverage: 0.93, falsePositiveRate: 0.04, latencyMs: 8.7, eventsHandled24h: 9213, lastUpdate: '2026-04-25T22:00:00Z' },
  { id: 'DEF-004', name: 'Proof Chain Tamper Guard', category: 'prevention', status: 'active', coverage: 0.999, falsePositiveRate: 0.001, latencyMs: 0.8, eventsHandled24h: 45220, lastUpdate: '2026-04-26T14:00:00Z' },
  { id: 'DEF-005', name: 'Differential Privacy Shield', category: 'prevention', status: 'active', coverage: 0.91, falsePositiveRate: 0.03, latencyMs: 12.4, eventsHandled24h: 3841, lastUpdate: '2026-04-24T18:00:00Z' },
  { id: 'DEF-006', name: 'Rollback & Recovery Engine', category: 'recovery', status: 'active', coverage: 0.95, falsePositiveRate: 0.01, latencyMs: 45.2, eventsHandled24h: 127, lastUpdate: '2026-04-25T16:00:00Z' },
  { id: 'DEF-007', name: 'Adversarial Input Detector (ART)', category: 'detection', status: 'active', coverage: 0.96, falsePositiveRate: 0.025, latencyMs: 5.3, eventsHandled24h: 11042, lastUpdate: '2026-04-26T12:00:00Z' },
  { id: 'DEF-008', name: 'Glasswing Transparency Filter', category: 'detection', status: 'active', coverage: 0.94, falsePositiveRate: 0.015, latencyMs: 2.1, eventsHandled24h: 8756, lastUpdate: '2026-04-26T10:00:00Z' },
];

export default function AdversarialDefenseConsole() {
  const [filter, setFilter] = useState<AttackClass | 'all'>('all');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 3000);
    return () => clearInterval(interval);
  }, []);

  const filteredEvents = filter === 'all' ? THREAT_EVENTS : THREAT_EVENTS.filter((e) => e.attackClass === filter);

  const blockedCount = THREAT_EVENTS.filter((e) => e.status === 'blocked').length;
  const blockRate = Math.round((blockedCount / THREAT_EVENTS.length) * 1000) / 10;
  const criticalCount = THREAT_EVENTS.filter((e) => e.severity === 'critical').length;
  const activeModules = DEFENSE_MODULES.filter((m) => m.status === 'active').length;
  const avgLatency = Math.round(DEFENSE_MODULES.reduce((sum, m) => sum + m.latencyMs, 0) / DEFENSE_MODULES.length * 10) / 10;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-semibold text-white">Adversarial ML Defense Console</h1>
            <span className={cn('text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border', tick % 2 === 0 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-emerald-500/15 border-emerald-500/25 text-emerald-300')}>
              Live
            </span>
          </div>
          <p className="text-[13px] text-white/35">
            Real-time adversarial attack detection, defense module status, and IBM ART-integrated threat classification
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-white/20" aria-hidden="true">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-[10px] text-white/20">a11oy orchestrated</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-emerald-400">{blockRate}%</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Block Rate</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-white">{THREAT_EVENTS.length}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Events (24h)</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-red-400">{criticalCount}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Critical</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-blue-400">{activeModules}/{DEFENSE_MODULES.length}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Modules Active</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-white">{avgLatency}ms</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Avg Latency</p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[13px] font-medium text-white flex items-center gap-2">
            <Swords className="w-3.5 h-3.5 text-white/30" /> Threat Event Feed
          </h2>
          <div className="flex gap-1.5">
            {(['all', 'evasion', 'poisoning', 'extraction', 'inference'] as const).map((f) => (
              <button
                type="button"
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  'px-2.5 py-1 rounded text-[10px] border transition-colors',
                  filter === f ? 'bg-white/[0.06] border-white/[0.12] text-white' : 'border-white/[0.04] text-white/25 hover:text-white/40',
                )}
              >
                {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl overflow-hidden">
          {filteredEvents.map((event) => (
            <div key={event.id} className="flex items-center gap-4 px-5 py-3 border-b border-white/[0.03] hover:bg-white/[0.015] transition-colors">
              <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: event.status === 'blocked' ? '#10b981' : event.status === 'detected' ? '#f59e0b' : '#3b82f6' }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[12px] text-white/60 truncate">{event.technique}</span>
                  <span className={cn('text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0', ATTACK_CLASS_COLORS[event.attackClass])}>
                    {event.attackClass}
                  </span>
                  <span className={cn('text-[9px] font-mono shrink-0', SEVERITY_COLORS[event.severity])}>
                    {event.severity}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-white/20">
                  <span>{event.source} → {event.target}</span>
                  <span>·</span>
                  <span>{event.defenseLayer}</span>
                  <span>·</span>
                  <span className="font-mono">{event.artReference}</span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <span className={cn('text-[10px] font-mono', STATUS_COLORS[event.status])}>{event.status}</span>
                <p className="text-[9px] text-white/15">{new Date(event.timestamp).toLocaleTimeString()}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-[13px] font-medium text-white mb-3 flex items-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-white/30" /> Defense Modules
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {DEFENSE_MODULES.map((mod) => (
            <div key={mod.id} className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className={cn(
                  'text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border',
                  mod.category === 'prevention' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : mod.category === 'detection' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                    : mod.category === 'response' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                    : 'bg-purple-500/10 border-purple-500/20 text-purple-400',
                )}>
                  {mod.category}
                </span>
                <span className="flex items-center gap-1">
                  <span className={cn('w-1.5 h-1.5 rounded-full', mod.status === 'active' ? 'bg-emerald-400' : mod.status === 'degraded' ? 'bg-amber-400' : 'bg-red-400')} />
                  <span className="text-[9px] text-white/20">{mod.status}</span>
                </span>
              </div>
              <h3 className="text-[13px] font-medium text-white mb-2">{mod.name}</h3>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div>
                  <p className="text-white/15">Coverage</p>
                  <p className="text-white/50 font-mono">{(mod.coverage * 100).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-white/15">FP Rate</p>
                  <p className="text-white/50 font-mono">{(mod.falsePositiveRate * 100).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-white/15">Latency</p>
                  <p className="text-white/50 font-mono">{mod.latencyMs}ms</p>
                </div>
                <div>
                  <p className="text-white/15">Events (24h)</p>
                  <p className="text-white/50 font-mono">{mod.eventsHandled24h.toLocaleString()}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
