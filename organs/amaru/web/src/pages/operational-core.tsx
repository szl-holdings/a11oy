// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@szl-holdings/shared-ui/ui/card';
import { Skeleton } from '@szl-holdings/shared-ui/ui/skeleton';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertOctagon,
  CheckCircle2,
  GitMerge,
  Hash,
  Network,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  TrendingUp,
  Infinity as InfinityIcon,
  ExternalLink,
} from 'lucide-react';
import { AmaruTripwiresPanel } from '@/components/AmaruLive';

/**
 * Conduit — Operational Core.
 *
 * The Andean-Ouroboros executive surface. Mirrors A11oy /szl-ops and
 * Vessels /operational-core for cross-product parity, with a Conduit-native
 * payload: the live R0513 OVERWATCH panel (via the api-server's
 * /api/amaru/overwatch/snapshot proxy into services/amaru) joined to the
 * six inherited mechanisms, the elevated formula pillars, the DOI proof
 * bindings, and the v6 doctrine.
 *
 * Read-only by design. Halt authority belongs to HUKLLA. The proxy is
 * GET-only.
 */

type InvariantStatus = 'pass' | 'warn' | 'trip' | 'reserved';

interface Invariant {
  id: string;
  title: string;
  status: InvariantStatus;
  value: number | null;
  threshold: number | null;
  detail: string;
}

interface OverwatchSnapshot {
  panel_version: string;
  thesis_kernel_hash: string;
  thesis_brain_hash: string;
  read_only: boolean;
  invariants: Invariant[];
  summary: Record<string, number>;
}

const AUTHOR = {
  name: 'Stephen P. Lutar Jr.',
  email: 'stephen@szlholdings.com',
  orcid: '0009-0001-0110-4173',
  orcid_url: 'https://orcid.org/0009-0001-0110-4173',
} as const;

const DOCTRINE = {
  version: 'v6',
  ban_list: ['AlloyScape', 'Glass Wing', 'Glasswing', 'Mythos', 'Stephen Paul', 'Perplexity Computer'],
  byline_rule: 'Use "Stephen P." — never "Stephen Paul". "Jr." is canonical.',
} as const;

const MECHANISMS = [
  { num: 'I',   title: 'Λ-gate (9-axis Lutar Invariant)',          inherited_as: 'conduit.guardian → @szl-holdings/formulas' },
  { num: 'II',  title: 'Receipt chain (signed bounded recursion)', inherited_as: 'conduit Ouroboros runtime — per-run ReceiptChain' },
  { num: 'III', title: 'Bekenstein gate (information-bounded)',    inherited_as: 'conduit admit-gate on sync handoff' },
  { num: 'IV',  title: 'Dual-witness verdict (MATCH/DIVERGE)',     inherited_as: 'amaru ↔ conduit reconciliation on every closed loop' },
  { num: 'V',   title: 'Witness diversity (Gauss class-number)',   inherited_as: 'conduit lineage graph multi-source corroboration' },
  { num: 'VI',  title: 'Reference-vector parity (bit-exact)',      inherited_as: 'conduit replay determinism on continuum_hash chain' },
] as const;

const FORMULA_PILLARS = [
  { id: 'normalizedRiskScore', label: 'Λ — Normalized Risk Composite', expression: 'Λ = clamp( severity · likelihood · valueAtRisk / cap , 0, 1 )' },
  { id: 'driftScore',          label: 'Drift — KL Divergence',          expression: 'D_KL(p‖q) = Σ pᵢ · log(pᵢ / qᵢ)' },
  { id: 'proofClosureScore',   label: 'Λ₁₀ — Proof Closure',            expression: 'closure = presentDims / totalDims' },
  { id: 'voyageCostMonteCarlo', label: 'Voyage Cost — Monte Carlo',      expression: 'Cᵢ = max(0, μ + σ · Z),  Z ~ N(0,1);  p10/p50/p90' },
] as const;

const DOI_BINDINGS = [
  { zenodo_id: '19944926', kind: 'concept',  title: 'SZL Concept DOI (umbrella) — CITATION.cff' },
  { zenodo_id: '20119582', kind: 'paper-v11', title: 'Applied Λ — Measured Per-Request Latency Overhead' },
  { zenodo_id: '20162352', kind: 'software',  title: 'Ouroboros Runtime v6.3.0 — bounded-loop substrate' },
  { zenodo_id: '20053148', kind: 'paper-v9',  title: 'Unified Operational Account of the Λ Family' },
  { zenodo_id: '20173920', kind: 'paper-v12', title: 'v12 Master Thesis — Λ-Invariant Stack' },
  { zenodo_id: '20195368', kind: 'paper-v13', title: 'v13 Master Thesis — Λ-Invariant Stack (final)' },
] as const;

const INVARIANT_ICONS: Record<string, typeof TrendingUp> = {
  I1: TrendingUp,
  I2: Activity,
  I3: GitMerge,
  I4: ShieldQuestion,
  I5: Network,
  I6: Hash,
};

function statusBadge(status: InvariantStatus) {
  switch (status) {
    case 'pass':
      return (
        <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
          <ShieldCheck className="w-3 h-3 mr-1" /> PASS
        </Badge>
      );
    case 'warn':
      return (
        <Badge variant="outline" className="text-amber-400 border-amber-500/30 bg-amber-500/10">
          <ShieldAlert className="w-3 h-3 mr-1" /> WARN
        </Badge>
      );
    case 'trip':
      return (
        <Badge variant="outline" className="text-red-400 border-red-500/30 bg-red-500/10">
          <AlertOctagon className="w-3 h-3 mr-1" /> TRIP
        </Badge>
      );
    case 'reserved':
      return (
        <Badge variant="outline" className="text-white/40 border-white/10 bg-white/5">
          <ShieldQuestion className="w-3 h-3 mr-1" /> RESERVED
        </Badge>
      );
  }
}

function fmtValue(v: number | null): string {
  if (v === null || v === undefined) return '—';
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(4);
}

async function fetchOverwatch(): Promise<OverwatchSnapshot> {
  const r = await fetch('/api/amaru/overwatch/snapshot', { credentials: 'include' });
  if (!r.ok) {
    const txt = await r.text().catch(() => '');
    let msg = `HTTP ${r.status}`;
    try {
      const j = JSON.parse(txt);
      if (typeof j?.message === 'string') msg = j.message;
      else if (typeof j?.error === 'string') msg = j.error;
    } catch { /* keep */ }
    throw new Error(msg);
  }
  return (await r.json()) as OverwatchSnapshot;
}

export default function ConduitOperationalCore() {
  const q = useQuery({
    queryKey: ['conduit-ops-core-overwatch'],
    queryFn: fetchOverwatch,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const snap = q.data;
  // Counters: prefer authoritative snapshot.summary (Amaru kernel is source of
  // truth), fall back to client recomputation if upstream contract drifts.
  const passCount = snap?.summary?.pass ?? snap?.invariants.filter((i) => i.status === 'pass').length ?? 0;
  const warnCount = snap?.summary?.warn ?? snap?.invariants.filter((i) => i.status === 'warn').length ?? 0;
  const tripCount = snap?.summary?.trip ?? snap?.invariants.filter((i) => i.status === 'trip').length ?? 0;

  // Safe short-hash helper — guards against non-string upstream values.
  const shortHash = (v: unknown): string =>
    typeof v === 'string' && v.length >= 8 ? v.slice(0, 8) : '—';

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5] p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <InfinityIcon className="w-5 h-5 text-[#c9b787]" />
              <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-[#888]">
                CONDUIT · ANDEAN-OUROBOROS OPERATIONAL CORE
              </span>
              <Badge variant="outline" className="text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10 font-mono text-[10px]">
                LIVE
              </Badge>
            </div>
            <h1 className="text-3xl font-semibold tracking-tight">Operational Core</h1>
            <p className="text-sm text-[#888] mt-1 max-w-2xl">
              Single auditable surface for the live R0513 OVERWATCH panel, six inherited mechanisms,
              elevated formula pillars, DOI proof bindings, and v6 doctrine. Read-only.
              Halt authority belongs to HUKLLA.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => q.refetch()}
            disabled={q.isFetching}
            className="border-white/10"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${q.isFetching ? 'animate-spin' : ''}`} />
            {q.isFetching ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>

        {/* B1 — Formula pillars */}
        <Card className="bg-[#0e0e0e] border-white/5">
          <CardHeader>
            <CardTitle className="text-sm font-mono uppercase tracking-wider text-[#888]">
              B1 · Elevated Formula Pillars
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-2 gap-3">
              {FORMULA_PILLARS.map((p) => (
                <div key={p.id} className="border border-white/5 rounded-lg p-3 bg-black/30">
                  <div className="text-xs text-[#c9b787] font-mono">{p.id}</div>
                  <div className="text-sm font-medium mt-1">{p.label}</div>
                  <div className="text-[11px] font-mono text-[#888] mt-1 break-words">{p.expression}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* B2 — Live R0513 OVERWATCH panel */}
        <Card className="bg-[#0e0e0e] border-white/5">
          <CardHeader>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-[#888]">
                  B2 · R0513 Overwatch (live)
                </CardTitle>
                {snap && (
                  <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-[#666]">
                    <span>panel {snap.panel_version ?? '—'}</span>
                    <span>kernel {shortHash(snap.thesis_kernel_hash)}</span>
                    <span>brain {shortHash(snap.thesis_brain_hash)}</span>
                    {snap.read_only && (
                      <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10 text-[10px]">
                        READ-ONLY
                      </Badge>
                    )}
                  </div>
                )}
              </div>
              {snap && (
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="text-emerald-400">{passCount} PASS</span>
                  <span className="text-amber-400">{warnCount} WARN</span>
                  <span className="text-red-400">{tripCount} TRIP</span>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {q.isLoading && (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 bg-white/5" />
                ))}
              </div>
            )}
            {q.isError && (
              <div className="text-sm text-red-400 font-mono p-3 border border-red-500/20 rounded-lg bg-red-500/5">
                Overwatch unavailable: {q.error instanceof Error ? q.error.message : String(q.error)}
              </div>
            )}
            {snap && (
              <div className="space-y-2">
                {snap.invariants.map((inv) => {
                  const Icon = INVARIANT_ICONS[inv.id] ?? ShieldQuestion;
                  return (
                    <div
                      key={inv.id}
                      className="grid grid-cols-[auto_auto_1fr_auto_auto] items-center gap-3 px-3 py-2.5 rounded-lg border border-white/5 bg-black/30"
                    >
                      <Icon className="w-4 h-4 text-[#c9b787]" />
                      <span className="text-xs font-mono text-[#888] w-6">{inv.id}</span>
                      <div>
                        <div className="text-sm">{inv.title}</div>
                        <div className="text-[11px] text-[#666] mt-0.5">{inv.detail}</div>
                      </div>
                      <div className="text-[11px] font-mono text-[#888] text-right">
                        <div>val: {fmtValue(inv.value)}</div>
                        <div>thr: {fmtValue(inv.threshold)}</div>
                      </div>
                      {statusBadge(inv.status)}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* B2.5 — HUKLLA Tripwires (live) */}
        <AmaruTripwiresPanel />

        {/* B3 — Six inherited mechanisms */}
        <Card className="bg-[#0e0e0e] border-white/5">
          <CardHeader>
            <CardTitle className="text-sm font-mono uppercase tracking-wider text-[#888]">
              B3 · Six Inherited Mechanisms
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid lg:grid-cols-2 gap-3">
              {MECHANISMS.map((m) => (
                <div key={m.num} className="border border-white/5 rounded-lg p-3 bg-black/30">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs font-mono text-[#c9b787]">{m.num}</span>
                    <span className="text-sm font-medium">{m.title}</span>
                  </div>
                  <div className="text-[11px] text-[#888] mt-1.5">
                    <span className="text-[#666]">inherited as: </span>
                    {m.inherited_as}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* B4 — DOI bindings */}
        <Card className="bg-[#0e0e0e] border-white/5">
          <CardHeader>
            <CardTitle className="text-sm font-mono uppercase tracking-wider text-[#888]">
              B4 · DOI Proof Bindings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {DOI_BINDINGS.map((d) => {
                const url = `https://doi.org/10.5281/zenodo.${d.zenodo_id}`;
                return (
                  <a
                    key={d.zenodo_id}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 px-3 py-2 rounded-lg border border-white/5 bg-black/30 hover:bg-black/50 transition-colors"
                  >
                    <Badge variant="outline" className="text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10 font-mono text-[10px] shrink-0">
                      {d.kind}
                    </Badge>
                    <span className="text-[11px] font-mono text-[#888] shrink-0">{d.zenodo_id}</span>
                    <span className="text-sm flex-1">{d.title}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-[#666]" />
                  </a>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* B5 — Doctrine */}
        <Card className="bg-[#0e0e0e] border-white/5">
          <CardHeader>
            <CardTitle className="text-sm font-mono uppercase tracking-wider text-[#888]">
              B5 · Doctrine {DOCTRINE.version}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-[#666] mb-1.5">
                Author
              </div>
              <div className="text-sm">
                {AUTHOR.name} · {AUTHOR.email}
              </div>
              <a
                href={AUTHOR.orcid_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] font-mono text-[#c9b787] hover:underline inline-flex items-center gap-1 mt-0.5"
              >
                ORCID {AUTHOR.orcid} <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-[#666] mb-1.5">
                Byline rule
              </div>
              <div className="text-sm text-[#bbb]">{DOCTRINE.byline_rule}</div>
            </div>
            <div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-[#666] mb-1.5">
                Ban list
              </div>
              <div className="flex flex-wrap gap-1.5">
                {DOCTRINE.ban_list.map((t) => (
                  <Badge key={t} variant="outline" className="text-red-400 border-red-500/30 bg-red-500/10 font-mono text-[10px]">
                    <AlertOctagon className="w-3 h-3 mr-1" /> {t}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Footer parity stamp */}
        <div className="flex items-center justify-center gap-2 text-[10px] font-mono text-[#444] py-4">
          <CheckCircle2 className="w-3 h-3" />
          <span>cross-product parity · A11oy /szl-ops · Vessels /operational-core · Conduit /operational-core</span>
        </div>
      </div>
    </div>
  );
}
