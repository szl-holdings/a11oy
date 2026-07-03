/**
 * Amaru — Codex Loop.
 *
 * Visible surface for the @workspace/codex-kernel: runs the Dresden Venus
 * reference loop in two postures (governance ON vs OFF) and shows the
 * hash-chained transitions, decision receipts, validator severities, and
 * a live replay verifier.
 *
 * This is the page where "what does replay-grade actually look like?" gets
 * answered with a button you can press.
 */

import { useMemo, useState } from 'react';
import {
  DRESDEN_DEFAULT_CONFIG,
  DRESDEN_INITIAL_STATE,
  type DresdenSimConfig,
  dresdenSteps,
  type KernelRunResult,
  ProofLedger,
  replay,
  runLoop,
  serializeTraceJsonl,
  shortHash,
  type VenusState,
} from '@workspace/codex-kernel';
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  Download,
  Flag,
  Gauge,
  Link2,
  Loader2,
  PlayCircle,
  ScanEye,
  ShieldCheck,
  ShieldOff,
  XCircle,
} from 'lucide-react';

interface RunBundle {
  result: KernelRunResult<VenusState>;
  jsonl: string;
  replayed: ReturnType<typeof replay<VenusState>>;
  ledgerDigest: string;
}

/** Rebuild the append-only ProofLedger from the committed entries to obtain
 *  its canonical digest (covers every governance field of every entry). */
function ledgerDigestOf(result: KernelRunResult<VenusState>): string {
  const ledger = new ProofLedger();
  for (const entry of result.ledger) ledger.append(entry);
  return ledger.digest();
}

function executeRun(
  cfg: DresdenSimConfig,
  governance_enabled: boolean,
): RunBundle {
  const result = runLoop<VenusState>({
    experiment_id: 'E4',
    initial_state: DRESDEN_INITIAL_STATE,
    policy_version: 'covenant-v1',
    budgets: { time_budget_ms: 5_000, step_budget: 30, retry_budget: 0 },
    loop_policy: {
      max_steps: 30,
      adaptive_depth: { enabled: false },
      entropy_regularized_exit: { enabled: false },
    },
    governance_enabled,
    steps: dresdenSteps(cfg),
  });
  const jsonl = serializeTraceJsonl(result.trace);
  const replayed = replay<VenusState>(
    DRESDEN_INITIAL_STATE,
    result.trace,
    result.summary.final_state_hash,
  );
  return { result, jsonl, replayed, ledgerDigest: ledgerDigestOf(result) };
}

function severityChip(sev: 'pass' | 'soft_fail' | 'hard_fail') {
  if (sev === 'pass')
    return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
  if (sev === 'soft_fail')
    return 'bg-amber-500/10 text-amber-300 border-amber-500/30';
  return 'bg-rose-500/10 text-rose-300 border-rose-500/30';
}

function downloadJsonl(jsonl: string, name: string) {
  const blob = new Blob([jsonl], { type: 'application/x-jsonlines' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

const SCENARIOS: Array<{ id: string; label: string; cfg: DresdenSimConfig }> = [
  {
    id: 'stable',
    label: 'Stable (no drift)',
    cfg: { ...DRESDEN_DEFAULT_CONFIG, drift_per_cycle: 0, rows_to_emit: 8 },
  },
  {
    id: 'drift-corrected',
    label: 'Drift +1d/cycle (auto-correcting)',
    cfg: {
      ...DRESDEN_DEFAULT_CONFIG,
      drift_per_cycle: 1,
      rows_to_emit: 10,
    },
  },
  {
    id: 'runaway',
    label: 'Runaway drift +3d/cycle',
    cfg: {
      ...DRESDEN_DEFAULT_CONFIG,
      drift_per_cycle: 3,
      hard_threshold: 8,
      rows_to_emit: 8,
    },
  },
];

export default function CodexLoop() {
  const [scenarioId, setScenarioId] = useState<string>('drift-corrected');
  const scenario = useMemo(
    () => SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0],
    [scenarioId],
  );
  const [runs, setRuns] = useState<{ on: RunBundle; off: RunBundle } | null>(
    null,
  );
  const [selectedStep, setSelectedStep] = useState<number | null>(null);

  const triggerRun = () => {
    const on = executeRun(scenario.cfg, true);
    const off = executeRun(scenario.cfg, false);
    setRuns({ on, off });
    setSelectedStep(1);
  };

  return (
    <div className="space-y-6 p-6">
      <header className="space-y-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
          <Activity className="h-3.5 w-3.5" /> Codex-Kernel · E4 · governed loop
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Codex Loop — Dresden Venus reference run
        </h1>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
          A replay-grade governed iteration. Each step proposes a delta, gets
          validated, and — if it passes — appends a hash-chained entry to the
          proof ledger with a decision receipt. The Maya astronomers tracked
          Venus this way: idealized 584-day cycles plus explicit drift
          corrections. Toggle the governance posture to see what the kernel
          actually changes.
        </p>
      </header>

      <section className="rounded-lg border border-border bg-card/50 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground">
              Scenario
            </label>
            <select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              className="mt-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div className="text-xs text-muted-foreground">
            cycle_days={scenario.cfg.cycle_days} · drift/cycle=
            {scenario.cfg.drift_per_cycle} · warn={scenario.cfg.warning_threshold}{' '}
            · hard={scenario.cfg.hard_threshold}
          </div>
          <div className="flex-1" />
          <button
            type="button"
            onClick={triggerRun}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <PlayCircle className="h-4 w-4" />
            Run loop (both postures)
          </button>
        </div>
      </section>

      {!runs && (
        <div className="rounded-lg border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          Press <span className="font-medium">Run loop</span> to execute the
          kernel and produce a hash-chained trace + replay attestation.
        </div>
      )}

      {runs && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <PostureCard
            title="Governance ON"
            icon={<ShieldCheck className="h-4 w-4 text-emerald-400" />}
            bundle={runs.on}
            selectedStep={selectedStep}
            onSelectStep={setSelectedStep}
            filename={`dresden-${scenario.id}-governance-on.jsonl`}
          />
          <PostureCard
            title="Governance OFF"
            icon={<ShieldOff className="h-4 w-4 text-amber-400" />}
            bundle={runs.off}
            selectedStep={selectedStep}
            onSelectStep={setSelectedStep}
            filename={`dresden-${scenario.id}-governance-off.jsonl`}
          />
        </div>
      )}

      {runs && selectedStep !== null && (
        <ReceiptInspector bundle={runs.on} step={selectedStep} />
      )}

      <LoopPropertiesPanel />
    </div>
  );
}

interface PostureCardProps {
  title: string;
  icon: React.ReactNode;
  bundle: RunBundle;
  selectedStep: number | null;
  onSelectStep: (step: number) => void;
  filename: string;
}

function PostureCard({
  title,
  icon,
  bundle,
  selectedStep,
  onSelectStep,
  filename,
}: PostureCardProps) {
  const { result, jsonl, replayed } = bundle;
  const summary = result.summary;
  return (
    <div className="rounded-lg border border-border bg-card/40 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-base font-semibold">{title}</h2>
        </div>
        <button
          type="button"
          onClick={() => downloadJsonl(jsonl, filename)}
          className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted/40"
        >
          <Download className="h-3 w-3" /> trace.jsonl
        </button>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <dt className="text-muted-foreground">status</dt>
        <dd
          className={
            summary.status === 'ok' ? 'text-emerald-400' : 'text-rose-400'
          }
        >
          {summary.status}
        </dd>
        <dt className="text-muted-foreground">steps_executed</dt>
        <dd>{summary.steps_executed}</dd>
        <dt className="text-muted-foreground">hard_stop_failures</dt>
        <dd>{summary.hard_stop_failures}</dd>
        <dt className="text-muted-foreground">soft_failures</dt>
        <dd>{summary.soft_failures}</dd>
        <dt className="text-muted-foreground">stop_reason</dt>
        <dd className="font-mono text-[11px]">{summary.stop_reason ?? '—'}</dd>
        <dt className="text-muted-foreground">final_state_hash</dt>
        <dd className="font-mono text-[11px]">
          {shortHash(summary.final_state_hash)}
        </dd>
        <dt className="text-muted-foreground">ledger_digest</dt>
        <dd className="font-mono text-[11px]">{shortHash(bundle.ledgerDigest)}</dd>
        <dt className="text-muted-foreground">replay</dt>
        <dd
          className={
            replayed.ok
              ? 'flex items-center gap-1 text-emerald-400'
              : 'flex items-center gap-1 text-rose-400'
          }
        >
          {replayed.ok ? (
            <CheckCircle2 className="h-3 w-3" />
          ) : (
            <XCircle className="h-3 w-3" />
          )}
          {replayed.ok
            ? `verified · ${replayed.steps_replayed} steps`
            : `failed at step ${replayed.failed_step}`}
        </dd>
      </dl>

      <div className="mt-4 max-h-80 overflow-auto rounded border border-border/60">
        <table className="min-w-full text-xs">
          <thead className="bg-muted/30 text-muted-foreground">
            <tr>
              <th className="px-2 py-1 text-left">step</th>
              <th className="px-2 py-1 text-left">stage</th>
              <th className="px-2 py-1 text-left">prev →</th>
              <th className="px-2 py-1 text-left">next</th>
              <th className="px-2 py-1 text-left">validators</th>
            </tr>
          </thead>
          <tbody>
            {result.trace.map((event) => (
              <tr
                key={event.step}
                onClick={() => onSelectStep(event.step)}
                className={`cursor-pointer border-t border-border/40 hover:bg-muted/30 ${
                  selectedStep === event.step ? 'bg-primary/10' : ''
                }`}
              >
                <td className="px-2 py-1 font-mono">{event.step}</td>
                <td className="px-2 py-1 text-muted-foreground">
                  {event.pipeline_stage}
                </td>
                <td className="px-2 py-1 font-mono">
                  {shortHash(event.state_prev_hash)}
                </td>
                <td className="px-2 py-1 font-mono">
                  {shortHash(event.state_next_hash)}
                </td>
                <td className="px-2 py-1">
                  <div className="flex flex-wrap gap-1">
                    {event.validator_results.map((v) => (
                      <span
                        key={v.name}
                        title={v.summary}
                        className={`rounded border px-1 py-px text-[10px] ${severityChip(v.severity)}`}
                      >
                        {v.name}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// SGH loop-properties panel — visualizes, from REAL emitted receipts of the live
// governed /agent/cycle endpoint, the four properties the position paper
// "From Agent Loops to Structured Graphs" (arXiv:2604.11378) says agent loops
// need: BOUNDED, INSPECTABLE POLICY, IMMUTABLE HISTORY, TERMINATION.
//
// Honesty discipline: this is a DEMONSTRATION + ATTESTATION, advisory only, NOT
// a formal proof (a formal termination proof is future Lean work). It NEVER
// fabricates receipts: if the live cycle is OFF (founder-gated env
// A11OY_OUROBOROS / A11OY_SGH not enabled on the Space) it renders the honest
// OFF-state, not fake data.
// --------------------------------------------------------------------------- //

interface CycleTraceRow {
  iteration: number;
  trust_score: number | null;
  decision: string | null;
  precondition_hash: string | null;
  chain_final_hash: string | null;
}
interface CycleChainEntry {
  seq: number;
  kind: string;
  prev_hash: string;
  hash: string;
}
interface SghLayer {
  plan_version?: string;
  sgh_final_state?: string;
  sgh_halt_reason?: string;
  bounded?: boolean;
  escalated?: boolean;
  recover_attempts?: number;
  max_recover?: number;
  label?: string;
  node_state_trace?: Array<Record<string, unknown>>;
  plan_dag?: { nodes?: unknown[]; immutable?: boolean };
}
interface CycleResponse {
  cycle?: boolean;
  enabled?: boolean;
  note?: string;
  budget?: number;
  eps?: number;
  iterations_run?: number;
  final_status?: string;
  final_status_note?: string;
  convergence?: string;
  trust_trace?: CycleTraceRow[];
  cycle_receipt_chain?: CycleChainEntry[];
  cycle_chain_final_hash?: string;
  sgh?: SghLayer;
}

const A11OY_ORIGIN =
  (import.meta.env.VITE_A11OY_ORIGIN as string | undefined) ??
  (typeof window !== 'undefined' ? window.location.origin : '');

/** Verify the prev_hash linkage of the cycle receipt chain in-browser. This is
 *  an honest linkage check (each entry commits the previous entry's hash and the
 *  chain seeds at GENESIS) — NOT a full cryptographic re-hash, and it is labeled
 *  as such. Operates only on REAL emitted receipts. */
function verifyChainLinkage(chain: CycleChainEntry[] | undefined): {
  ok: boolean;
  length: number;
  failedAt: number | null;
} {
  if (!chain || chain.length === 0)
    return { ok: false, length: 0, failedAt: null };
  if (chain[0].prev_hash !== 'GENESIS')
    return { ok: false, length: chain.length, failedAt: 0 };
  for (let i = 1; i < chain.length; i++) {
    if (chain[i].prev_hash !== chain[i - 1].hash)
      return { ok: false, length: chain.length, failedAt: i };
  }
  return { ok: true, length: chain.length, failedAt: null };
}

function terminationTone(status: string | undefined): string {
  if (status === 'converged') return 'text-emerald-300 border-emerald-500/30';
  if (status === 'halted_by_gate') return 'text-sky-300 border-sky-500/30';
  if (status === 'budget_exhausted' || status === 'halted_by_banach')
    return 'text-amber-300 border-amber-500/30';
  return 'text-muted-foreground border-border';
}

function PropertyCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card/40 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold">
        {icon}
        {title}
      </div>
      <div className="mt-3 space-y-1.5 text-xs">{children}</div>
    </div>
  );
}

function LoopPropertiesPanel() {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>(
    'idle',
  );
  const [resp, setResp] = useState<CycleResponse | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const probe = async () => {
    setState('loading');
    setErrMsg(null);
    try {
      const r = await fetch(`${A11OY_ORIGIN}/api/a11oy/v1/agent/cycle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          query: 'deploy a low-risk reversible change',
          severity: 'low',
          reversible: true,
          budget: 5,
          eps: 0.01,
        }),
      });
      const body = (await r.json()) as CycleResponse;
      setResp(body);
      setState('done');
    } catch (e) {
      setErrMsg(e instanceof Error ? e.message : String(e));
      setState('error');
    }
  };

  const chain = verifyChainLinkage(resp?.cycle_receipt_chain);
  const trace = resp?.trust_trace ?? [];
  const denies = trace.filter((t) => t.decision === 'DENY').length;
  const allows = trace.filter((t) => t.decision === 'ALLOW').length;
  const sgh = resp?.sgh;
  const enabledCycle = resp?.cycle === true;
  const offState = state === 'done' && !enabledCycle;

  return (
    <section className="rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/[0.03] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-fuchsia-300">
            <ScanEye className="h-3.5 w-3.5" /> Structured-graph loop properties
          </div>
          <h2 className="text-xl font-semibold tracking-tight">
            Live governed loop — bounded · inspectable · immutable · terminating
          </h2>
          <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
            Reads the four properties the position paper{' '}
            <span className="font-mono">
              "From Agent Loops to Structured Graphs" (arXiv:2604.11378)
            </span>{' '}
            says agent loops need, from REAL emitted receipts of the live{' '}
            <span className="font-mono">/api/a11oy/v1/agent/cycle</span>{' '}
            endpoint. Demonstration + attestation · advisory · NOT a formal proof
            (a formal termination proof is future Lean work). Λ is Conjecture 1 —
            an advisory heart-gate, never a theorem.
          </p>
        </div>
        <button
          type="button"
          onClick={probe}
          disabled={state === 'loading'}
          className="flex items-center gap-2 rounded-md border border-fuchsia-500/40 bg-fuchsia-500/10 px-3 py-2 text-sm font-medium text-fuchsia-200 hover:bg-fuchsia-500/20 disabled:opacity-50"
        >
          {state === 'loading' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Activity className="h-4 w-4" />
          )}
          Probe live /agent/cycle
        </button>
      </div>

      {state === 'idle' && (
        <div className="mt-4 rounded border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
          Press <span className="font-medium">Probe live /agent/cycle</span> to
          read the properties from real receipts. Nothing is fabricated — if the
          founder-gated loop is disabled, the honest OFF-state is shown.
        </div>
      )}

      {state === 'error' && (
        <div className="mt-4 rounded border border-rose-500/30 bg-rose-500/5 p-4 text-xs text-rose-300">
          Could not reach the live cycle endpoint ({errMsg}). No data is
          fabricated; try again when the a11oy origin is reachable.
        </div>
      )}

      {offState && (
        <div className="mt-4 rounded border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-amber-200">
          <div className="font-medium">Governed cycle is OFF (honest empty-state).</div>
          <p className="mt-1 text-amber-200/80">
            {resp?.note ??
              'The Ouroboros closed loop is disabled on this Space. Enable A11OY_OUROBOROS=1 (and A11OY_SGH=1 for the explicit node state machine) to populate these properties from live receipts.'}
          </p>
        </div>
      )}

      {state === 'done' && enabledCycle && (
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* (1) BOUNDED */}
          <PropertyCard
            icon={<Gauge className="h-4 w-4 text-emerald-400" />}
            title="1 · Bounded"
          >
            <Row label="budget ceiling" value={`${resp?.budget ?? '—'} (hard ≤ 64)`} />
            <Row label="iterations run" value={String(resp?.iterations_run ?? '—')} />
            {sgh?.node_state_trace && (
              <Row
                label="plan nodes · transitions"
                value={`${sgh.plan_dag?.nodes?.length ?? '?'} · ${sgh.node_state_trace.length}`}
              />
            )}
            <p className="pt-1 text-[11px] text-muted-foreground">
              Finite budget guarantees the loop always halts; the SGH layer adds
              a finite recover-attempt cap on top. Bounded by construction.
            </p>
          </PropertyCard>

          {/* (2) INSPECTABLE POLICY */}
          <PropertyCard
            icon={<ShieldCheck className="h-4 w-4 text-sky-400" />}
            title="2 · Inspectable policy (Λ-gate)"
          >
            <Row
              label="per-node decisions"
              value={`${allows} ALLOW · ${denies} DENY`}
            />
            <div className="max-h-24 overflow-auto rounded border border-border/50">
              <table className="min-w-full text-[11px]">
                <tbody>
                  {trace.map((t) => (
                    <tr key={t.iteration} className="border-t border-border/30">
                      <td className="px-2 py-0.5 font-mono text-muted-foreground">
                        #{t.iteration}
                      </td>
                      <td
                        className={`px-2 py-0.5 font-mono ${t.decision === 'DENY' ? 'text-rose-300' : 'text-emerald-300'}`}
                      >
                        {t.decision ?? '—'}
                      </td>
                      <td className="px-2 py-0.5 font-mono text-muted-foreground">
                        trust={t.trust_score ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="pt-1 text-[11px] text-muted-foreground">
              Λ = Conjecture 1 — advisory heart-gate, deny-by-default, never a
              theorem.
            </p>
          </PropertyCard>

          {/* (3) IMMUTABLE HISTORY */}
          <PropertyCard
            icon={<Link2 className="h-4 w-4 text-violet-400" />}
            title="3 · Immutable history (hash-chained DAG)"
          >
            <Row
              label="chain entries"
              value={String(resp?.cycle_receipt_chain?.length ?? 0)}
            />
            <Row
              label="prev-hash linkage"
              value={
                chain.ok
                  ? `verified · ${chain.length} entries · seeds GENESIS`
                  : `BROKEN at #${chain.failedAt}`
              }
            />
            <Row
              label="cycle_chain_final_hash"
              value={
                resp?.cycle_chain_final_hash
                  ? `${resp.cycle_chain_final_hash.slice(0, 16)}…`
                  : '—'
              }
            />
            <p className="pt-1 text-[11px] text-muted-foreground">
              In-browser prev-hash linkage check on real receipts (not a full
              re-hash). Tamper-evident, append-only.
            </p>
          </PropertyCard>

          {/* (4) TERMINATION */}
          <PropertyCard
            icon={<Flag className="h-4 w-4 text-amber-400" />}
            title="4 · Termination"
          >
            <div
              className={`inline-block rounded border px-2 py-0.5 font-mono text-[11px] ${terminationTone(resp?.final_status)}`}
            >
              {resp?.final_status ?? '—'}
            </div>
            {sgh && (
              <Row
                label="sgh halt"
                value={`${sgh.sgh_final_state ?? '—'} · recover ${sgh.recover_attempts ?? 0}/${sgh.max_recover ?? 0}${sgh.escalated ? ' · escalated' : ''}`}
              />
            )}
            <p className="pt-1 text-[11px] text-muted-foreground">
              {resp?.final_status_note ??
                'Halts on the first honest status: converged / halted_by_gate / budget_exhausted / halted_by_banach.'}
            </p>
            <p className="pt-1 text-[11px] text-fuchsia-300/80">
              Advisory (Conjecture 1) — bounded, always halts, but NOT claimed
              provably terminating.
            </p>
          </PropertyCard>
        </div>
      )}

      {state === 'done' && enabledCycle && (
        <p className="mt-3 text-[11px] text-muted-foreground">
          Inspiration: arXiv:2604.11378 (position paper). This panel is an
          own-code demonstration + attestation over real receipts — advisory,
          experimental, NOT a formal proof.
          {sgh?.label ? ` · ${sgh.label}` : ''}
        </p>
      )}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono text-[11px]">{value}</span>
    </div>
  );
}

interface ReceiptInspectorProps {
  bundle: RunBundle;
  step: number;
}

function ReceiptInspector({ bundle, step }: ReceiptInspectorProps) {
  const event = bundle.result.trace.find((e) => e.step === step);
  if (!event) return null;
  const receipt = event.decision_receipt;
  return (
    <section className="rounded-lg border border-border bg-card/40 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <ChevronRight className="h-4 w-4" /> Step {step} — decision receipt
      </div>
      {!receipt && (
        <p className="mt-3 text-xs text-muted-foreground">
          (no receipt — terminal or trivial step)
        </p>
      )}
      {receipt && (
        <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <h4 className="text-xs uppercase tracking-wider text-muted-foreground">
              Summary
            </h4>
            <p className="mt-1 text-sm">{receipt.summary}</p>
            <h4 className="mt-3 text-xs uppercase tracking-wider text-muted-foreground">
              Decision type
            </h4>
            <p className="mt-1 font-mono text-sm">{receipt.decision_type}</p>
            <h4 className="mt-3 text-xs uppercase tracking-wider text-muted-foreground">
              Policy
            </h4>
            <p className="mt-1 font-mono text-xs">
              {receipt.policy_version} · approval={receipt.approval_status}
              {receipt.mocked && ' · mocked'}
            </p>
          </div>
          <div>
            <h4 className="text-xs uppercase tracking-wider text-muted-foreground">
              Assumptions
            </h4>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {receipt.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
            <h4 className="mt-3 text-xs uppercase tracking-wider text-muted-foreground">
              Evidence
            </h4>
            <ul className="mt-1 space-y-1 text-xs">
              {receipt.evidence.map((ev, i) => (
                <li key={i} className="font-mono">
                  <span className="text-muted-foreground">{ev.kind}:</span>{' '}
                  {ev.ref}
                  {ev.mocked && (
                    <span className="ml-1 text-amber-400">(mocked)</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
