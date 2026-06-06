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
  PlayCircle,
  ShieldCheck,
  ShieldOff,
  XCircle,
} from 'lucide-react';

interface RunBundle {
  result: KernelRunResult<VenusState>;
  jsonl: string;
  replayed: ReturnType<typeof replay>;
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
  const replayed = replay(
    DRESDEN_INITIAL_STATE,
    result.trace,
    result.summary.final_state_hash,
  );
  return { result, jsonl, replayed };
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
