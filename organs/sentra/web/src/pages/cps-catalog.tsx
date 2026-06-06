import { useEffect, useState } from 'react';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Shield,
  Network,
  Database,
  Play,
  ChevronRight,
  Tag,
  Eye,
  Zap,
  Bot,
  Target,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { cpsApi, type MaturityGate } from '@/lib/cps-api';

const CATEGORY_ICONS: Record<string, typeof Shield> = {
  'identity-defense': Shield,
  'network-defense': Network,
  'data-protection': Database,
};

const MATURITY_LABELS: Record<string, { label: string; color: string; icon: typeof Eye }> = {
  shadow: { label: 'Shadow', color: 'text-slate-400 bg-slate-500/20 border-slate-500/30', icon: Eye },
  'supervised-auto': { label: 'Supervised Auto', color: 'text-amber-400 bg-amber-500/20 border-amber-500/30', icon: Zap },
  autonomous: { label: 'Autonomous', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30', icon: Bot },
};

export default function CpsCatalog() {
  const [payloads, setPayloads] = useState<any[]>([]);
  const [gates, setGates] = useState<Record<string, MaturityGate>>({});
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);
  const [maturityError, setMaturityError] = useState<{ payloadId: string; message: string } | null>(null);

  useEffect(() => {
    Promise.all([
      cpsApi.payloads.list().catch(() => []),
      cpsApi.payloads.maturityGates().catch(() => ({ gates: {} as Record<string, MaturityGate> })),
    ]).then(([data, g]) => {
      setPayloads(Array.isArray(data) ? data : []);
      setGates(g?.gates ?? {});
      setLoading(false);
    });
  }, []);

  async function handleExecute(payloadId: string) {
    setExecutingId(payloadId);
    try {
      await cpsApi.runs.execute(payloadId);
    } catch { /* handled by UI */ }
    setExecutingId(null);
  }

  async function handleMaturityChange(payloadId: string, mode: string) {
    setMaturityError(null);
    try {
      const updated = await cpsApi.payloads.updateMaturity(payloadId, mode);
      setPayloads((prev) => prev.map((p) => (p.id === payloadId ? updated : p)));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update maturity';
      setMaturityError({ payloadId, message });
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-slate-500 font-mono text-sm">Loading CPS Payloads...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <header>
        <h1 className="text-3xl font-display font-bold text-slate-100">CPS Payload Catalog</h1>
        <p className="text-slate-400 mt-1">
          Cyber Payload Standard — detect / decide / act / approve / recover
        </p>
      </header>

      <div className="grid gap-4">
        {payloads.map((payload) => {
          const Icon = CATEGORY_ICONS[payload.category] ?? Shield;
          const maturity = MATURITY_LABELS[payload.defaultMaturityMode] ?? MATURITY_LABELS.shadow;
          const MatIcon = maturity.icon;
          const expanded = expandedId === payload.id;
          const gate = gates[payload.id];
          const promotionAllowed = gate?.allowed ?? false;
          const confidencePct =
            gate?.compositeConfidence != null ? Math.round(gate.compositeConfidence * 100) : null;

          return (
            <div key={payload.id} className="sentra-panel p-0 overflow-hidden">
              <div
                className="p-5 cursor-pointer hover:bg-white/[0.02] transition-colors"
                onClick={() => setExpandedId(expanded ? null : payload.id)}
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg bg-[#c9b787]/10 border border-[#c9b787]/20 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-5 h-5 text-[#c9b787]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-display font-semibold text-slate-100">{payload.name}</h3>
                      <span className="text-[10px] font-mono text-slate-500">v{payload.version}</span>
                    </div>
                    <p className="text-sm text-slate-400 mt-1 line-clamp-2">{payload.description}</p>
                    <div className="flex items-center gap-3 mt-3 flex-wrap">
                      <span className={cn('inline-flex items-center gap-1.5 text-[11px] font-mono px-2.5 py-1 rounded-full border', maturity.color)}>
                        <MatIcon className="w-3 h-3" />
                        {maturity.label}
                      </span>
                      {gate && (
                        <span
                          title={
                            promotionAllowed
                              ? 'Emulation scorecard gate passed — promotion allowed'
                              : `Promotion blocked: ${gate.blockers.join('; ')}`
                          }
                          className={cn(
                            'inline-flex items-center gap-1.5 text-[11px] font-mono px-2.5 py-1 rounded-full border',
                            promotionAllowed
                              ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                              : 'text-red-400 bg-red-500/10 border-red-500/30',
                          )}
                        >
                          {promotionAllowed ? (
                            <ShieldCheck className="w-3 h-3" />
                          ) : (
                            <ShieldAlert className="w-3 h-3" />
                          )}
                          Emulation gate: {promotionAllowed ? 'PASS' : 'BLOCKED'}
                          {confidencePct != null && ` · ${confidencePct}%`}
                        </span>
                      )}
                      {payload.mitreTactics?.map((t: string) => (
                        <span key={t} className="text-[10px] font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleExecute(payload.id); }}
                      disabled={executingId === payload.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-[#c9b787]/10 border border-[#c9b787]/30 text-[#c9b787] rounded-lg hover:bg-[#c9b787]/20 transition-colors disabled:opacity-50"
                    >
                      <Play className="w-3.5 h-3.5" />
                      {executingId === payload.id ? 'Running...' : 'Execute'}
                    </button>
                    <ChevronRight className={cn('w-4 h-4 text-slate-500 transition-transform', expanded && 'rotate-90')} />
                  </div>
                </div>
              </div>

              {expanded && (
                <div className="border-t border-white/5 p-5 space-y-5 bg-black/20">
                  <div>
                    <h4 className="text-xs font-mono text-slate-500 uppercase mb-3">Maturity Mode</h4>
                    <div className="flex gap-2 flex-wrap">
                      {(['shadow', 'supervised-auto', 'autonomous'] as const).map((mode) => {
                        const m = MATURITY_LABELS[mode];
                        const MATURITY_RANK: Record<string, number> = {
                          shadow: 0,
                          'supervised-auto': 1,
                          autonomous: 2,
                        };
                        const currentRank = MATURITY_RANK[payload.defaultMaturityMode] ?? 0;
                        const targetRank = MATURITY_RANK[mode] ?? 0;
                        const isPromotion = targetRank > currentRank;
                        const requiresGate = mode === 'supervised-auto' || mode === 'autonomous';
                        const wouldBeBlocked =
                          isPromotion && requiresGate && gate != null && !promotionAllowed;
                        return (
                          <button
                            key={mode}
                            onClick={() => handleMaturityChange(payload.id, mode)}
                            disabled={wouldBeBlocked && payload.defaultMaturityMode !== mode}
                            title={
                              wouldBeBlocked
                                ? `Emulation gate blocked: ${gate?.blockers.join('; ')}`
                                : undefined
                            }
                            className={cn(
                              'px-3 py-1.5 text-xs font-mono rounded-lg border transition-colors',
                              payload.defaultMaturityMode === mode
                                ? m.color
                                : wouldBeBlocked
                                  ? 'text-slate-600 border-slate-800 cursor-not-allowed opacity-50'
                                  : 'text-slate-500 border-slate-700 hover:border-slate-600',
                            )}
                          >
                            {m.label}
                            {wouldBeBlocked && payload.defaultMaturityMode !== mode && ' · gated'}
                          </button>
                        );
                      })}
                    </div>
                    {gate && !promotionAllowed && (
                      <div className="mt-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                        <div className="flex items-center gap-2 text-[11px] font-mono text-red-400">
                          <ShieldAlert className="w-3.5 h-3.5" />
                          Emulation scorecard gate is blocking promotion
                        </div>
                        <ul className="mt-2 space-y-1 text-[11px] text-slate-400 pl-5 list-disc">
                          {gate.blockers.map((b, i) => (
                            <li key={i}>{b}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {maturityError && maturityError.payloadId === payload.id && (
                      <div className="mt-3 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 text-[11px] font-mono text-amber-300">
                        {maturityError.message}
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="text-xs font-mono text-slate-500 uppercase mb-3">Detection Rules</h4>
                    <div className="grid gap-2">
                      {payload.detectionLogic?.map((rule: any) => (
                        <div key={rule.id} className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/50 border border-white/5">
                          <Target className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-slate-200">{rule.name}</div>
                            <div className="text-[11px] font-mono text-slate-500 mt-0.5">{rule.condition}</div>
                          </div>
                          <span className={cn(
                            'text-[10px] font-mono px-2 py-0.5 rounded',
                            rule.severity === 'critical' ? 'text-red-400 bg-red-500/10' : 'text-amber-400 bg-amber-500/10',
                          )}>
                            {rule.severity}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-xs font-mono text-slate-500 uppercase mb-3">Constrained Actions</h4>
                    <div className="grid gap-2">
                      {payload.constrainedActions?.map((action: any) => (
                        <div key={action.id} className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/50 border border-white/5">
                          <Zap className="w-4 h-4 text-[#c9b787] flex-shrink-0" />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-slate-200">{action.description}</div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              {action.reversible ? 'Reversible' : 'Irreversible'} · Approval: {action.approvalTier} · Impact: {action.impactLevel}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-xs font-mono text-slate-500 uppercase mb-3">
                      <Tag className="w-3 h-3 inline mr-1" />
                      Tags
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {payload.tags?.map((tag: string) => (
                        <span key={tag} className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full border border-white/5">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-xs font-mono text-slate-500 uppercase mb-3">Rollback Contract</h4>
                    <div className="p-3 rounded-lg bg-slate-900/50 border border-white/5">
                      <div className="flex items-center gap-2 text-sm">
                        <span className={cn(
                          'w-2 h-2 rounded-full',
                          payload.rollbackContract?.tested ? 'bg-emerald-400' : 'bg-red-400',
                        )} />
                        <span className="text-slate-300">
                          {payload.rollbackContract?.tested ? 'Tested' : 'Untested'}
                        </span>
                        <span className="text-slate-500 text-xs">·</span>
                        <span className="text-xs text-slate-500 font-mono">
                          {payload.rollbackContract?.steps?.length ?? 0} step(s)
                        </span>
                      </div>
                      {payload.rollbackContract?.verificationChecks?.map((check: string, i: number) => (
                        <div key={i} className="text-[11px] text-slate-500 mt-1 pl-4">
                          {i + 1}. {check}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
