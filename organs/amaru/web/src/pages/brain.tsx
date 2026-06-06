/**
 * Conduit /brain — Amaru Brain panel.
 *
 * Live state of all 7 chakra kernels (root → crown):
 *   – Last evaluation (output / error / stub status / receipt seq) per chakra
 *   – Fire a manual scheduler tick and watch the receipt chain extend
 *   – Static SVG of the chakana wiring (Andean cross + ouroboros closure)
 *   – Live tripwire (huklla-10) status
 *
 * Data sources:
 *   – GET  /amaru/state         — per-chakra last evaluation snapshot (polled)
 *   – GET  /amaru/tripwires     — huklla-10 status (polled)
 *   – POST /amaru/scheduler/tick — manual tick
 *
 * The page subscribes to /amaru/events (SSE) for `amaru.chakra` and
 * `amaru.scheduler` envelopes — the exact topic names Amaru publishes to the
 * yawar-bus (Prism Bus). A 2-second poll on /amaru/state is kept as a
 * fallback for when the SSE connection drops (proxies, restarts, etc.).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Brain } from 'lucide-react';

const AMARU_BASE = '/api/amaru';
const CHAKRAS = ['root', 'sacral', 'solar', 'heart', 'throat', 'third_eye', 'crown'] as const;
type ChakraName = (typeof CHAKRAS)[number];

const CHAKRA_LABELS: Record<ChakraName, string> = {
  root: 'Root · muladhara',
  sacral: 'Sacral · svadhisthana',
  solar: 'Solar · manipura',
  heart: 'Heart · anahata',
  throat: 'Throat · vishuddha',
  third_eye: 'Third-Eye · ajna',
  crown: 'Crown · sahasrara',
};

interface ChakraEvaluation {
  chakra: string;
  output: Record<string, unknown> | null;
  error: string | null;
  stubbed: boolean;
  receipt?: { seq?: number };
  via?: string;
  tick_id?: number;
}

interface RuntimeState {
  chakras: ChakraName[];
  last_evaluation: Record<ChakraName, ChakraEvaluation | null>;
  scheduler_ticks: number;
  receipts: number;
  bus: { publishes: number; failures: number };
}

interface TripwireRow {
  id: string;
  title: string;
  status: 'pass' | 'warn' | 'trip';
  detail: string;
}

interface TripwireResponse {
  summary: { pass: number; warn: number; trip: number; total: number };
  tripwires: TripwireRow[];
}

interface TickStep {
  chakra: string;
  output: Record<string, unknown> | null;
  error: string | null;
  stubbed: boolean;
  receipt_seq: number;
}

interface TickResult {
  tick_id: number;
  steps: TickStep[];
  closure: number | null;
  handoff: { to: string; via: string } | null;
}

async function safeFetch<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await fetch(url, init);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

function statusBadge(status: 'pass' | 'warn' | 'trip') {
  const palette: Record<typeof status, { bg: string; fg: string; label: string }> = {
    pass: { bg: 'rgba(201,183,135,0.12)', fg: '#c9b787', label: 'PASS' },
    warn: { bg: 'rgba(245,245,245,0.10)', fg: '#f5f5f5', label: 'WARN' },
    trip: { bg: 'rgba(245,80,80,0.14)', fg: '#ff8a8a', label: 'TRIP' },
  };
  const p = palette[status];
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono"
      style={{ backgroundColor: p.bg, color: p.fg }}
    >
      {p.label}
    </span>
  );
}

function ChakraCard({
  name,
  evaluation,
}: {
  name: ChakraName;
  evaluation: ChakraEvaluation | null;
}) {
  const stub = evaluation?.stubbed;
  const error = evaluation?.error;
  const output = evaluation?.output;
  const seq = evaluation?.receipt?.seq;

  return (
    <div
      className="rounded-lg border p-4 flex flex-col gap-2"
      style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase tracking-wide" style={{ color: '#c9b787' }}>
          {CHAKRA_LABELS[name]}
        </div>
        {stub ? (
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded"
            style={{ backgroundColor: 'rgba(245,245,245,0.08)', color: '#f5f5f5' }}
          >
            STUBBED · upstream not vendored
          </span>
        ) : evaluation ? (
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded"
            style={{ backgroundColor: 'rgba(201,183,135,0.12)', color: '#c9b787' }}
          >
            {error ? 'ERROR' : 'OK'}
          </span>
        ) : (
          <span className="text-[10px] font-mono" style={{ color: '#5e5e5e' }}>
            idle
          </span>
        )}
      </div>
      {error && (
        <div className="text-xs font-mono" style={{ color: '#ff8a8a', whiteSpace: 'pre-wrap' }}>
          {error}
        </div>
      )}
      {output && (
        <pre
          className="text-[11px] font-mono leading-snug overflow-auto rounded p-2"
          style={{ backgroundColor: '#000', color: '#e6e6e6', maxHeight: 160 }}
        >
          {JSON.stringify(output, null, 2)}
        </pre>
      )}
      <div className="text-[10px] font-mono" style={{ color: '#5e5e5e' }}>
        receipt seq: {seq ?? '—'}
        {evaluation?.tick_id ? `  ·  tick ${evaluation.tick_id}` : ''}
      </div>
    </div>
  );
}

function ChakanaWiringSvg() {
  // Static topology — chakana ascent root→crown + ouroboros closure crown→root.
  const cx = 280;
  const top = 40;
  const dy = 56;
  const order: ChakraName[] = [...CHAKRAS];
  return (
    <svg viewBox="0 0 560 460" className="w-full h-auto">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#c9b787" />
        </marker>
      </defs>
      {order.map((name, i) => {
        const y = top + i * dy;
        return (
          <g key={name}>
            <circle
              cx={cx}
              cy={y}
              r={18}
              fill="#0a0a0a"
              stroke="#c9b787"
              strokeOpacity={0.5}
              strokeWidth={1.5}
            />
            <text
              x={cx}
              y={y + 4}
              textAnchor="middle"
              fontFamily="monospace"
              fontSize="10"
              fill="#c9b787"
            >
              {i + 1}
            </text>
            <text
              x={cx + 28}
              y={y + 4}
              fontFamily="monospace"
              fontSize="11"
              fill="#e6e6e6"
            >
              {CHAKRA_LABELS[name]}
            </text>
            {i < order.length - 1 && (
              <line
                x1={cx}
                y1={y + 18}
                x2={cx}
                y2={y + dy - 18}
                stroke="#c9b787"
                strokeOpacity={0.4}
                strokeWidth={1.2}
                markerEnd="url(#arrow)"
              />
            )}
          </g>
        );
      })}
      {/* Ouroboros closure: crown → root */}
      <path
        d={`M ${cx - 18} ${top + (order.length - 1) * dy} C ${cx - 200} ${top + (order.length - 1) * dy + 40}, ${cx - 200} ${top - 40}, ${cx - 18} ${top}`}
        fill="none"
        stroke="#c9b787"
        strokeOpacity={0.55}
        strokeWidth={1.5}
        strokeDasharray="4 4"
        markerEnd="url(#arrow)"
      />
      <text
        x={50}
        y={top + ((order.length - 1) * dy) / 2}
        fontFamily="monospace"
        fontSize="10"
        fill="#c9b787"
        opacity={0.6}
      >
        ouroboros
      </text>
    </svg>
  );
}

export default function BrainPage() {
  const [state, setState] = useState<RuntimeState | null>(null);
  const [tripwires, setTripwires] = useState<TripwireResponse | null>(null);
  const [tickHistory, setTickHistory] = useState<TickResult[]>([]);
  const [ticking, setTicking] = useState(false);
  const [runtimeUp, setRuntimeUp] = useState<boolean | null>(null);
  const [sseOpen, setSseOpen] = useState(false);

  const refresh = useCallback(async () => {
    const [s, t] = await Promise.all([
      safeFetch<RuntimeState>(`${AMARU_BASE}/state`),
      safeFetch<TripwireResponse>(`${AMARU_BASE}/tripwires`),
    ]);
    if (s) setState(s);
    if (t) setTripwires(t);
    setRuntimeUp(s !== null || t !== null);
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [refresh]);

  // Subscribe to Amaru's SSE stream so chakra/tripwire state updates push,
  // not poll. /amaru/events emits exact topic names: amaru.chakra (per
  // evaluation) and amaru.scheduler (per tick). The polling above is kept
  // as a fallback for when this stream is unavailable.
  useEffect(() => {
    const url = `${AMARU_BASE}/events`;
    let es: EventSource | null = null;
    try {
      es = new EventSource(url);
    } catch {
      return;
    }
    es.addEventListener('hello', () => setSseOpen(true));
    es.addEventListener('amaru.chakra', (e) => {
      try {
        const env = JSON.parse((e as MessageEvent).data) as {
          payload?: ChakraEvaluation & { chakra?: string };
        };
        const ev = env.payload;
        if (!ev?.chakra) return;
        setState((prev) =>
          prev
            ? {
                ...prev,
                last_evaluation: { ...prev.last_evaluation, [ev.chakra as ChakraName]: ev },
                receipts: Math.max(prev.receipts, ev.receipt?.seq ?? prev.receipts),
              }
            : prev,
        );
      } catch {
        /* ignore malformed frame */
      }
    });
    es.addEventListener('amaru.scheduler', (e) => {
      try {
        const env = JSON.parse((e as MessageEvent).data) as { payload?: TickResult };
        const tick = env.payload;
        if (!tick?.tick_id) return;
        setTickHistory((h) => {
          if (h[0]?.tick_id === tick.tick_id) return h;
          return [tick, ...h].slice(0, 8);
        });
      } catch {
        /* ignore */
      }
    });
    es.onerror = () => setSseOpen(false);
    return () => {
      es?.close();
      setSseOpen(false);
    };
  }, []);

  const tick = useCallback(async () => {
    setTicking(true);
    const r = await safeFetch<TickResult>(`${AMARU_BASE}/scheduler/tick`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        envelope: {
          signals: {
            grounded: 0.85,
            integrity: 0.9,
            novelty: 0.55,
            fluency: 0.78,
            care: 0.82,
            harm: 0.12,
            clarity: 0.84,
            truth: 0.88,
          },
        },
      }),
    });
    if (r) setTickHistory((h) => [r, ...h].slice(0, 8));
    setTicking(false);
    void refresh();
  }, [refresh]);

  const headSeq = state?.receipts ?? 0;
  const ticks = state?.scheduler_ticks ?? 0;
  const busOk = state ? state.bus.publishes - state.bus.failures : 0;

  const sortedChakras = useMemo(() => CHAKRAS, []);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-5 h-5" style={{ color: '#c9b787' }} />
            <span className="text-xs font-mono" style={{ color: '#c9b787' }}>
              AMARU BRAIN
            </span>
            <span
              className="text-[10px] font-mono px-2 py-0.5 rounded"
              style={{
                backgroundColor:
                  runtimeUp === null
                    ? 'rgba(94,94,94,0.15)'
                    : runtimeUp
                      ? 'rgba(201,183,135,0.12)'
                      : 'rgba(245,80,80,0.14)',
                color: runtimeUp === null ? '#8a8a8a' : runtimeUp ? '#c9b787' : '#ff8a8a',
              }}
            >
              {runtimeUp === null ? 'CHECKING' : runtimeUp ? 'RUNTIME UP' : 'RUNTIME DOWN'}
            </span>
            <span
              className="text-[10px] font-mono px-2 py-0.5 rounded"
              style={{
                backgroundColor: sseOpen ? 'rgba(201,183,135,0.12)' : 'rgba(94,94,94,0.15)',
                color: sseOpen ? '#c9b787' : '#8a8a8a',
              }}
              title="Live SSE subscription to /amaru/events (amaru.chakra + amaru.scheduler)"
            >
              {sseOpen ? 'SSE LIVE' : 'POLL FALLBACK'}
            </span>
          </div>
          <h1 className="text-2xl font-display font-semibold" style={{ color: '#e6e6e6' }}>
            7-chakra kernels · live runtime
          </h1>
          <p className="text-sm mt-1" style={{ color: '#8a8a8a' }}>
            Andean Ouroboros · root → crown · chakana wiring · huklla-10 tripwires
          </p>
        </div>
        <button
          onClick={tick}
          disabled={ticking || runtimeUp === false}
          className="px-4 py-2 rounded text-xs font-mono"
          style={{
            backgroundColor: ticking ? 'rgba(201,183,135,0.06)' : 'rgba(201,183,135,0.14)',
            color: '#c9b787',
            border: '1px solid rgba(201,183,135,0.4)',
            cursor: ticking || runtimeUp === false ? 'not-allowed' : 'pointer',
            opacity: runtimeUp === false ? 0.4 : 1,
          }}
        >
          {ticking ? 'TICKING…' : '▷ FIRE SCHEDULER TICK'}
        </button>
      </div>

      {runtimeUp === false && (
        <div
          className="mb-6 rounded-lg border p-4 text-xs font-mono"
          style={{
            backgroundColor: 'rgba(245,80,80,0.06)',
            borderColor: 'rgba(245,80,80,0.25)',
            color: '#ff8a8a',
          }}
        >
          Amaru runtime is not reachable on <code>/amaru/*</code>. Start the
          <code> artifacts/api-server: amaru</code> workflow to bring it up
          (autoStart is intentionally false per task #5176).
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="rounded-lg border p-3" style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}>
          <div className="text-[10px] font-mono uppercase" style={{ color: '#8a8a8a' }}>Scheduler ticks</div>
          <div className="text-xl font-display font-semibold" style={{ color: '#c9b787' }}>{ticks}</div>
        </div>
        <div className="rounded-lg border p-3" style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}>
          <div className="text-[10px] font-mono uppercase" style={{ color: '#8a8a8a' }}>Receipts in chain</div>
          <div className="text-xl font-display font-semibold" style={{ color: '#c9b787' }}>{headSeq}</div>
        </div>
        <div className="rounded-lg border p-3" style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}>
          <div className="text-[10px] font-mono uppercase" style={{ color: '#8a8a8a' }}>Yawar bus ok</div>
          <div className="text-xl font-display font-semibold" style={{ color: '#c9b787' }}>{busOk}</div>
        </div>
        <div className="rounded-lg border p-3" style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}>
          <div className="text-[10px] font-mono uppercase" style={{ color: '#8a8a8a' }}>Tripwires</div>
          <div className="text-xl font-display font-semibold" style={{ color: '#c9b787' }}>
            {tripwires
              ? `${tripwires.summary.pass}/${tripwires.summary.total}`
              : '—'}
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 grid sm:grid-cols-2 gap-3">
          {sortedChakras.map((name) => (
            <ChakraCard
              key={name}
              name={name}
              evaluation={state?.last_evaluation?.[name] ?? null}
            />
          ))}
        </div>
        <div className="flex flex-col gap-4">
          <div
            className="rounded-lg border p-3"
            style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}
          >
            <div className="text-xs font-mono uppercase tracking-wide mb-2" style={{ color: '#c9b787' }}>
              Chakana wiring
            </div>
            <ChakanaWiringSvg />
          </div>
          <div
            className="rounded-lg border p-3"
            style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}
          >
            <div className="text-xs font-mono uppercase tracking-wide mb-2 flex items-center justify-between" style={{ color: '#c9b787' }}>
              huklla-10 tripwires
              {tripwires && (
                <span className="text-[10px]" style={{ color: '#8a8a8a' }}>
                  pass {tripwires.summary.pass} · warn {tripwires.summary.warn} · trip {tripwires.summary.trip}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1">
              {(tripwires?.tripwires ?? []).map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-2 text-[11px]">
                  <div className="flex items-center gap-2 min-w-0">
                    {statusBadge(t.status)}
                    <span className="font-mono truncate" style={{ color: '#e6e6e6' }}>{t.title}</span>
                  </div>
                  <span className="font-mono truncate text-right" style={{ color: '#8a8a8a' }}>
                    {t.detail}
                  </span>
                </div>
              ))}
              {!tripwires && (
                <div className="text-[11px] font-mono" style={{ color: '#5e5e5e' }}>
                  No tripwire data yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="text-xs font-mono uppercase tracking-wide mb-2" style={{ color: '#c9b787' }}>
          Recent scheduler ticks (newest first)
        </div>
        {tickHistory.length === 0 && (
          <div className="text-[11px] font-mono" style={{ color: '#5e5e5e' }}>
            Fire a tick to extend the receipt chain.
          </div>
        )}
        <div className="flex flex-col gap-2">
          {tickHistory.map((tick) => (
            <div
              key={tick.tick_id}
              className="rounded-lg border p-3"
              style={{ backgroundColor: '#0f0f0f', borderColor: 'rgba(201,183,135,0.18)' }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono" style={{ color: '#c9b787' }}>
                  tick #{tick.tick_id}
                </span>
                <span className="text-[10px] font-mono" style={{ color: '#8a8a8a' }}>
                  closure {tick.closure?.toFixed(3) ?? '—'} · receipts seq {tick.steps[0]?.receipt_seq}–{tick.steps.at(-1)?.receipt_seq}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {tick.steps.map((s) => (
                  <span
                    key={s.chakra}
                    className="text-[10px] font-mono px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: s.error && !s.stubbed
                        ? 'rgba(245,80,80,0.14)'
                        : s.stubbed
                          ? 'rgba(245,245,245,0.08)'
                          : 'rgba(201,183,135,0.12)',
                      color: s.error && !s.stubbed ? '#ff8a8a' : s.stubbed ? '#f5f5f5' : '#c9b787',
                    }}
                  >
                    {s.chakra}#{s.receipt_seq}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
