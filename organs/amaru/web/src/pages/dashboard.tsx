import React, { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { toast } from 'sonner';
import { emitProof } from '@workspace/a11oy-orchestration/client';
import {
  RELAY_DESTINATIONS,
  RELAY_MAPPINGS,
  RELAY_OUTCOMES,
  RELAY_POLICIES,
  RELAY_RUN_EVENTS,
  RELAY_SOURCES,
  RELAY_MODELS,
  AMARU_AGENTS,
  VERTICAL_PLAYBOOKS,
} from '@/data/fabric';
import {
  buildApprovalQueue,
  buildCockpitKpis,
  calculateDestinationHealth,
  computeLutarSigma,
  rankSyncRisk,
  generateRecommendedAction,
} from '@/lib/agentic';
import { ConduitGovernancePanels } from '../components/GovernancePanels';
import {
  FabricCard,
  FabricStat,
  GovernanceDot,
  HeatCell,
  MicroBar,
  SeverityChip,
  Sparkline,
} from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { INNOVATION_CAPABILITIES } from '@/data/innovation/competitive';
import { useStats, useConnections, useSyncs } from '@/lib/api-hooks';
import { AmaruHealthPanel } from '@/components/AmaruLive';

export default function Dashboard() {
  const liveStats = useStats();
  const liveConnections = useConnections();
  const liveSyncs = useSyncs();
  const kpis = useMemo(
    () => buildCockpitKpis({ events: RELAY_RUN_EVENTS, destinations: RELAY_DESTINATIONS, mappings: RELAY_MAPPINGS, outcomes: RELAY_OUTCOMES, policies: RELAY_POLICIES }),
    [],
  );
  const approvals = useMemo(
    () => buildApprovalQueue(RELAY_MAPPINGS, (mid) => {
      const m = RELAY_MODELS.find((mo) => mo.id === mid);
      return m ? RELAY_SOURCES.find((s) => s.id === m.sourceId) ?? null : null;
    }),
    [],
  );
  const risk = useMemo(() => rankSyncRisk(RELAY_RUN_EVENTS).slice(0, 6), []);
  const sigma = useMemo(
    () => computeLutarSigma({
      P: 0.92,
      K: RELAY_DESTINATIONS.reduce((s, d) => s + d.fieldContractStrength, 0) / RELAY_DESTINATIONS.length,
      phi: RELAY_MAPPINGS.reduce((s, m) => s + m.confidence, 0) / RELAY_MAPPINGS.length,
      C: kpis.failedRecords24h === 0 ? 1 : Math.max(0.5, 1 - kpis.failedRecords24h / Math.max(1, kpis.recordsActivated24h)),
    }),
    [kpis],
  );
  const blockFeed = useMemo(
    () =>
      RELAY_POLICIES.flatMap((p) => p.recentHits.map((h) => ({ ...h, policy: p })))
        .sort((a, b) => (a.atIso < b.atIso ? 1 : -1))
        .slice(0, 8),
    [],
  );
  const throughput = useMemo(() => {
    const buckets = new Array(12).fill(0);
    const now = Date.now();
    for (const e of RELAY_RUN_EVENTS) {
      if (e.type !== 'completed') continue;
      const idx = Math.floor((now - Date.parse(e.atIso)) / (60 * 60 * 1000));
      if (idx >= 0 && idx < 12) buckets[11 - idx] += e.recordsAffected;
    }
    return buckets;
  }, []);
  const heat = useMemo(() => {
    const verticals = Array.from(new Set(RELAY_RUN_EVENTS.map((e) => e.verticalId))).slice(0, 7);
    const cats = Array.from(new Set(RELAY_DESTINATIONS.map((d) => d.category)));
    const grid: { vertical: string; category: string; count: number }[] = [];
    for (const v of verticals) {
      for (const c of cats) {
        const count = RELAY_RUN_EVENTS.filter(
          (e) => (e.type === 'failed' || e.type === 'rolled_back' || e.type === 'quarantined') && e.verticalId === v && RELAY_DESTINATIONS.find((d) => d.id === e.destinationId)?.category === c,
        ).length;
        grid.push({ vertical: v, category: c, count });
      }
    }
    const max = Math.max(1, ...grid.map((g) => g.count));
    return { verticals, cats, grid, max };
  }, []);

  const [handoffPending, setHandoffPending] = useState(false);
  async function handoffToA11oy() {
    if (handoffPending) return;
    setHandoffPending(true);
    const refId = `amaru-cycle-${Date.now().toString(36)}`;
    try {
      const proof = await emitProof({
        product: 'amaru',
        kind: 'action_executed',
        summary: `Amaru ouroboros cycle snapshot · ${kpis.activeSyncs} active syncs · LUTAR Σ ${(sigma.sigma * 100).toFixed(1)}%`,
        deepLink: '/conduit/',
        payload: {
          cycleRefId: refId,
          activeSyncs: kpis.activeSyncs,
          recordsActivated24h: kpis.recordsActivated24h,
          failedRecords24h: kpis.failedRecords24h,
          lutarSigma: sigma.sigma,
        },
      });
      toast.success(`Anchored to A11oy ledger · proof ${proof.id.slice(0, 12)}…`, {
        description: 'Inspect the cycle in A11oy → Conductor → Recent Proofs.',
      });
    } catch (err) {
      toast.error('A11oy handoff failed', { description: (err as Error).message });
    } finally {
      setHandoffPending(false);
    }
  }

  return (
    <div>
      {/* Hero */}
      <div className="hero-glow -mx-6 -mt-6 px-6 pt-8 pb-6 mb-6 border-b border-[rgba(255,255,255,0.04)]">
        <div className="flex items-end justify-between gap-6">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.32em] text-[#c9b787] mb-2">AMARU · COCKPIT</div>
            <h1 className="text-4xl font-light tracking-tight text-[#f5f5f5]"><span className="gradient-text">The Andean Ouroboros</span></h1>
            <p className="text-sm text-[#8a8a8a] mt-3 max-w-3xl leading-relaxed">
              Sovereign agentic activation. The serpent that holds the spine: discover sources, compose models,
              govern by policy, deliver with witness, and learn from outcomes — in one closed loop, replay-grade.
            </p>
            <div className="mt-4">
              <Button
                onClick={handoffToA11oy}
                disabled={handoffPending}
                variant="outline"
                className="gap-2 font-mono text-xs border-[rgba(201,183,135,0.25)] text-[#c9b787] hover:bg-[rgba(201,183,135,0.08)] hover:border-[rgba(201,183,135,0.4)]"
              >
                {handoffPending ? 'HANDING OFF…' : 'HANDOFF TO A11OY ↗'}
              </Button>
            </div>
          </div>
          <div className="conduit-card p-4 min-w-[260px]">
            <div className="label-mono text-[#c9b787] mb-1">LUTAR Σ — LIVE</div>
            <div className="text-3xl font-light tabular-nums text-[#c9b787]">{(sigma.sigma * 100).toFixed(1)}%</div>
            <div className="font-mono text-[10px] text-[#666] mt-1">{sigma.formula}</div>
            <div className="grid grid-cols-4 gap-1 mt-3 text-[10px]">
              {([['P', sigma.axes.P], ['K', sigma.axes.K], ['Φ', sigma.axes.phi], ['C', sigma.axes.C]] as const).map(([label, val]) => (
                <div key={label}><div className="label-mono">{label}</div><div className="font-mono tabular-nums text-[#f5f5f5]">{((val as number) * 100).toFixed(0)}</div></div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <AmaruHealthPanel />

      {/* Live KPI tiles — wired to /api/conduit/* */}
      {liveStats.isError || liveConnections.isError || liveSyncs.isError ? (
        <div className="mb-3 p-3 rounded border border-[rgba(212,84,80,0.3)] bg-[rgba(212,84,80,0.05)] text-[12px] text-[#d45450]">
          Live API unreachable — showing fabric reference values.
          {' '}<span className="font-mono text-[10px] text-[#888]">{(liveStats.error || liveConnections.error || liveSyncs.error)?.message}</span>
        </div>
      ) : null}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {liveStats.isLoading ? (
          Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="conduit-card p-4 animate-pulse">
              <div className="h-3 w-24 bg-[rgba(255,255,255,0.05)] rounded mb-2" />
              <div className="h-8 w-16 bg-[rgba(255,255,255,0.06)] rounded" />
            </div>
          ))
        ) : liveStats.data ? (
          <>
            <FabricStat label="Active syncs · live" value={liveStats.data.activeSyncs} tone="gold" />
            <FabricStat label="Total syncs · live" value={liveStats.data.totalSyncs} />
            <FabricStat label="Connections · live" value={liveConnections.data?.length ?? 0} />
            <FabricStat label="Total runs · live" value={liveStats.data.totalRuns.toLocaleString()} tone="good" />
            <FabricStat label="Successful runs · live" value={liveStats.data.successfulRuns.toLocaleString()} tone="good" />
            <FabricStat label="Failed runs · live" value={liveStats.data.failedRuns.toLocaleString()} tone={liveStats.data.failedRuns > 0 ? 'warn' : 'good'} />
            <FabricStat label="Rows written · live" value={liveStats.data.totalRowsWritten.toLocaleString()} />
            <FabricStat label="Success rate · live" value={`${(liveStats.data.successRate * 100).toFixed(1)}%`} tone={liveStats.data.successRate >= 0.95 ? 'good' : liveStats.data.successRate >= 0.8 ? 'warn' : 'bad'} />
          </>
        ) : (
          <>
            <FabricStat label="Active syncs" value={kpis.activeSyncs} tone="gold" />
            <FabricStat label="Records activated · 24h" value={(kpis.recordsActivated24h / 1000).toFixed(1) + 'k'} tone="good" />
            <FabricStat label="Failed records · 24h" value={kpis.failedRecords24h.toLocaleString()} tone={kpis.failedRecords24h > 5000 ? 'bad' : 'warn'} />
            <FabricStat label="Policy blocks · 24h" value={kpis.policyBlocks24h} tone={kpis.policyBlocks24h > 4 ? 'warn' : 'good'} />
            <FabricStat label="Approval queue" value={kpis.approvalQueue} tone="warn" />
            <FabricStat label="Avg destination health" value={kpis.destinationHealth} tone="good" />
            <FabricStat label="Avg latency · 24h" value={`${kpis.avgLatencyMs}ms`} />
            <FabricStat label="Outcome lift" value={`${(kpis.outcomeLiftPct * 100).toFixed(1)}%`} tone="good" />
          </>
        )}
      </div>

      {/* Live recent runs from /api/conduit/stats.recentRuns */}
      <FabricCard title="RECENT RUNS · LIVE" trailing={<Link href="/runs" className="text-[11px] text-[#c9b787] hover:underline">view all →</Link>} className="mb-6">
        {liveStats.isLoading ? (
          <div className="text-[12px] text-[#666] py-3">Loading recent runs…</div>
        ) : liveStats.isError ? (
          <div className="text-[12px] text-[#d45450] py-3">Failed to load: {liveStats.error?.message}</div>
        ) : !liveStats.data || liveStats.data.recentRuns.length === 0 ? (
          <div className="text-[12px] text-[#666] py-3">
            No runs yet. <Link href="/syncs/new" className="text-[#c9b787] hover:underline">Create your first sync →</Link>
          </div>
        ) : (
          <div className="space-y-2">
            {liveStats.data.recentRuns.slice(0, 6).map((run) => (
              <div key={run.id} className="text-[12px] p-2 rounded bg-[#0e0e0e] flex items-center gap-3">
                <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'failed' : 'partial'}>{run.status}</Badge>
                <span className="font-mono text-[#f5f5f5] truncate flex-1">{run.syncName ?? run.syncId}</span>
                <span className="font-mono text-[10px] text-[#8a8a8a] tabular-nums">{run.rowsWritten}/{run.rowsRead} rows</span>
                <span className="font-mono text-[10px] text-[#666]">{new Date(run.startedAt).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </FabricCard>

      {/* Activation flow */}
      <FabricCard title="ACTIVATION FLOW" trailing={<Sparkline values={throughput} width={160} height={32} tone="gold" />} className="mb-6">
        <div className="grid grid-cols-5 gap-3 text-center">
          {[
            { label: 'Sources', value: RELAY_SOURCES.length, href: '/sources' },
            { label: 'Models', value: RELAY_MODELS.length, href: '/models' },
            { label: 'Mappings', value: RELAY_MAPPINGS.length, href: '/mappings' },
            { label: 'Destinations', value: RELAY_DESTINATIONS.length, href: '/destinations' },
            { label: 'Outcomes', value: RELAY_OUTCOMES.length, href: '/outcomes' },
          ].map((step, i, arr) => (
            <Link key={step.label} href={step.href} className="block conduit-card p-4 hover:border-[rgba(201,183,135,0.3)] transition-all">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#c9b787]">{String(i + 1).padStart(2, '0')} {arr.length - 1 === i ? '' : '↓'}</div>
              <div className="text-2xl font-light text-[#f5f5f5] mt-2 tabular-nums">{step.value}</div>
              <div className="text-[12px] text-[#8a8a8a] mt-1">{step.label}</div>
            </Link>
          ))}
        </div>
      </FabricCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Top syncs at risk */}
        <FabricCard title="TOP SYNCS AT RISK">
          <div className="space-y-2">
            {risk.map((r) => (
              <div key={r.syncId} className="text-[12px] p-2 rounded bg-[#0e0e0e]">
                <div className="flex items-center justify-between">
                  <div className="font-mono text-[#f5f5f5] truncate flex-1">{r.syncName}</div>
                  <Badge variant={r.health === 'failing' ? 'failed' : r.health === 'degraded' ? 'partial' : 'success'}>{r.health}</Badge>
                </div>
                <div className="text-[10px] text-[#666] mt-1">{r.drivers.join(' · ') || 'no recent issues'}</div>
                <div className="text-[10px] text-[#c9b787] mt-1 italic">→ {generateRecommendedAction(r)}</div>
              </div>
            ))}
          </div>
        </FabricCard>

        {/* Approval queue */}
        <FabricCard title="APPROVAL QUEUE" trailing={<Link href="/mappings" className="text-[11px] text-[#c9b787] hover:underline">view all →</Link>}>
          <div className="space-y-2">
            {approvals.slice(0, 6).map((a) => (
              <div key={a.id} className="text-[12px] p-2 rounded bg-[#0e0e0e]">
                <div className="flex items-center justify-between mb-1">
                  <div className="font-mono text-[#f5f5f5] truncate flex-1">{a.syncName}</div>
                  <SeverityChip level={a.severity} />
                </div>
                <div className="text-[10px] text-[#8a8a8a]">{a.reason}</div>
                <div className="text-[10px] text-[#666] mt-0.5">{a.recordsImpacted.toLocaleString()} records · {a.verticalId}</div>
              </div>
            ))}
          </div>
        </FabricCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Risk heatmap */}
        <FabricCard title="RISK HEATMAP · vertical × destination category">
          <div className="text-[10px] font-mono text-[#666] mb-2">Failures + rollbacks + quarantines (last events)</div>
          <div className="overflow-x-auto">
            <div className="grid gap-1 min-w-[420px]" style={{ gridTemplateColumns: `auto repeat(${heat.cats.length}, minmax(38px, 1fr))` }}>
              <div></div>
              {heat.cats.map((c) => <div key={c} className="text-[9px] font-mono uppercase tracking-wider text-[#666] text-center pb-1 truncate">{c}</div>)}
              {heat.verticals.map((v) => (
                <React.Fragment key={`row-${v}`}>
                  <div className="text-[10px] font-mono text-[#8a8a8a] pr-2 self-center">{v}</div>
                  {heat.cats.map((c) => {
                    const cell = heat.grid.find((g) => g.vertical === v && g.category === c);
                    return <HeatCell key={`${v}-${c}`} value={cell?.count ?? 0} max={heat.max} />;
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        </FabricCard>

        {/* Policy block feed */}
        <FabricCard title="POLICY BLOCK FEED" trailing={<Link href="/policies" className="text-[11px] text-[#c9b787] hover:underline">view all →</Link>}>
          <div className="space-y-2">
            {blockFeed.map((h, i) => (
              <div key={i} className="text-[12px] p-2 rounded bg-[#0e0e0e]">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-[#f5f5f5] truncate flex-1">{h.policy.name}</div>
                  <Badge variant={h.outcome === 'block' ? 'failed' : h.outcome === 'rollback' ? 'failed' : 'partial'}>{h.outcome}</Badge>
                </div>
                <div className="text-[10px] text-[#8a8a8a]">{h.summary}</div>
                <div className="text-[10px] text-[#666] mt-0.5 font-mono">{h.syncId} · {new Date(h.atIso).toLocaleTimeString()}</div>
              </div>
            ))}
          </div>
        </FabricCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Destination health */}
        <FabricCard title="DESTINATION HEALTH" trailing={<Link href="/destinations" className="text-[11px] text-[#c9b787] hover:underline">view all →</Link>}>
          <div className="space-y-2">
            {RELAY_DESTINATIONS
              .map((d) => ({ d, h: calculateDestinationHealth(d, RELAY_RUN_EVENTS) }))
              .sort((a, b) => a.h - b.h)
              .slice(0, 7)
              .map(({ d, h }) => (
                <div key={d.id} className="flex items-center gap-3 text-[12px]">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: d.accent }} />
                  <span className="text-[#f5f5f5] truncate w-44">{d.name}</span>
                  <div className="flex-1"><MicroBar value={h} max={100} tone={h >= 85 ? 'good' : h >= 70 ? 'warn' : 'bad'} /></div>
                  <span className="font-mono tabular-nums w-8 text-right text-[#8a8a8a]">{h}</span>
                  <GovernanceDot state={d.governanceState} />
                </div>
              ))}
          </div>
        </FabricCard>

        {/* Agent activity */}
        <FabricCard title="AGENT ACTIVITY" trailing={<Link href="/agents" className="text-[11px] text-[#c9b787] hover:underline">view all →</Link>}>
          <div className="space-y-2">
            {AMARU_AGENTS.map((a) => (
              <div key={a.id} className="flex items-center gap-3 text-[12px]">
                <span className="w-6 text-[10px] font-mono text-[#c9b787] text-center">{a.lutarAxisAffinity}</span>
                <span className="text-[#f5f5f5] truncate w-28">{a.name}</span>
                <div className="flex-1"><MicroBar value={a.recentDecisionCount} max={Math.max(...AMARU_AGENTS.map((b) => b.recentDecisionCount))} tone="gold" /></div>
                <span className="font-mono tabular-nums w-12 text-right text-[#8a8a8a]">{a.recentDecisionCount}</span>
                <span className="font-mono tabular-nums w-8 text-right text-[#d4a853]">{a.recentBlockCount}</span>
              </div>
            ))}
          </div>
        </FabricCard>
      </div>

      {/* Vertical playbooks */}
      <FabricCard title="VERTICAL PLAYBOOKS — ACTIVATED BY AMARU" className="mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {VERTICAL_PLAYBOOKS.map((pb) => (
            <a key={pb.verticalId} href={pb.route} target="_blank" rel="noopener noreferrer" className="conduit-card p-4 hover:border-[rgba(201,183,135,0.3)]">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full" style={{ background: pb.accent }} />
                <div className="text-[#f5f5f5] text-sm font-medium flex-1 truncate">{pb.title}</div>
                <span className="text-[10px] text-[#c9b787]">↗</span>
              </div>
              <div className="space-y-1">
                {pb.entries.map((e, i) => (
                  <div key={i} className="text-[11px] flex items-start gap-2">
                    <GovernanceDot state={e.governanceState} />
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-[#8a8a8a] truncate">{e.trigger}</div>
                      <div className="text-[#666] truncate">→ {e.action}</div>
                    </div>
                  </div>
                ))}
              </div>
            </a>
          ))}
        </div>
      </FabricCard>

      <ConduitGovernancePanels />

      {/* One-of-One Innovation Panel */}
      <FabricCard
        title="ONE-OF-ONE — 10 INNOVATIONS"
        trailing={<Link href="/innovation" className="text-[11px] text-[#c9b787] hover:underline">Full competitive brief →</Link>}
      >
        <p className="text-[12px] text-[#8a8a8a] mb-4 leading-relaxed">
          Original capabilities assembled from field research across 10 public reverse ETL projects — re-implemented as A11oy-native, governed, proof-anchored primitives.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
          {INNOVATION_CAPABILITIES.map((cap) => (
            <Link key={cap.id} href={cap.route} className="conduit-card p-3 block hover:border-[rgba(201,183,135,0.3)] transition-all">
              <div className="flex items-start gap-2 mb-1.5">
                <span className="font-mono text-[10px] text-[#c9b787] shrink-0 mt-0.5">
                  {String(cap.number).padStart(2, '0')}
                </span>
                <div className="text-[#f5f5f5] text-[11px] font-medium leading-tight">{cap.title}</div>
              </div>
              <div className="text-[10px] text-[#666] leading-tight ml-5">{cap.tagline}</div>
            </Link>
          ))}
        </div>
      </FabricCard>
    </div>
  );
}
