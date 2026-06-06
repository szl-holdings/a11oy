/**
 * AmaruLive — shared live-feed cards backed by the read-only Amaru sidecar
 * proxy (artifacts/api-server/src/routes/amaru-proxy.ts → services/amaru on
 * port 6810). Round 5 / T003 wires real upstream evidence into Conduit tabs.
 *
 * All endpoints are GET-only and read-only by doctrine. No mock data: if the
 * sidecar is unreachable we render an explicit "unavailable" surface; if it
 * returns an empty stream we render an explicit "no data yet" surface.
 */
import { useEffect, useState } from 'react';

type FetchState<T> =
  | { kind: 'loading' }
  | { kind: 'error'; message: string; status?: number }
  | { kind: 'ok'; data: T };

function useAmaru<T>(path: string, intervalMs = 15_000): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({ kind: 'loading' });
  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const r = await fetch(path, { credentials: 'include' });
        const text = await r.text();
        if (!r.ok) {
          if (!cancelled) setState({ kind: 'error', status: r.status, message: text.slice(0, 240) });
          return;
        }
        const data = JSON.parse(text) as T;
        if (!cancelled) setState({ kind: 'ok', data });
      } catch (err) {
        if (!cancelled) setState({ kind: 'error', message: err instanceof Error ? err.message : String(err) });
      }
    }
    void tick();
    const id = window.setInterval(tick, intervalMs);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [path, intervalMs]);
  return state;
}

function Card({ title, source, children }: { title: string; source: string; children: React.ReactNode }) {
  return (
    <div className="conduit-card p-4 mb-4">
      <div className="flex items-baseline justify-between mb-3">
        <div className="label-mono text-[#c9b787]">{title}</div>
        <div className="font-mono text-[10px] text-[#666]">{source}</div>
      </div>
      {children}
    </div>
  );
}

function ErrorBlock({ s }: { s: { status?: number; message: string } }) {
  return (
    <div className="font-mono text-[11px] text-red-400 p-2 border border-red-500/20 rounded bg-red-500/5">
      Amaru sidecar unavailable{s.status ? ` (HTTP ${s.status})` : ''}: {s.message || 'no detail'}
    </div>
  );
}

interface AmaruStatePayload {
  chakras?: string[];
  last_evaluation?: Record<string, unknown>;
  scheduler_ticks?: number;
  receipts?: number;
  bus?: { publishes?: number; failures?: number };
}

// Snapshot view of the Amaru event bus. The sidecar's /events is a Server-Sent
// Events stream and intentionally not proxied; /state exposes the same counters
// as a point-in-time snapshot (publishes, failures, scheduler_ticks, receipts).
export function AmaruEventsPanel() {
  const s = useAmaru<AmaruStatePayload>('/api/amaru/state', 10_000);
  return (
    <Card title="AMARU · EVENT BUS · LIVE COUNTERS" source="GET /api/amaru/state">
      {s.kind === 'loading' && <div className="font-mono text-[11px] text-[#666]">Loading…</div>}
      {s.kind === 'error' && <ErrorBlock s={s} />}
      {s.kind === 'ok' && (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <div className="border border-white/5 rounded p-2 bg-black/30">
              <div className="text-[10px] font-mono uppercase tracking-wider text-[#666]">publishes</div>
              <div className="text-xl font-mono text-[#c9b787]">{s.data.bus?.publishes ?? 0}</div>
            </div>
            <div className="border border-white/5 rounded p-2 bg-black/30">
              <div className="text-[10px] font-mono uppercase tracking-wider text-[#666]">failures</div>
              <div className="text-xl font-mono text-amber-400">{s.data.bus?.failures ?? 0}</div>
            </div>
            <div className="border border-white/5 rounded p-2 bg-black/30">
              <div className="text-[10px] font-mono uppercase tracking-wider text-[#666]">scheduler_ticks</div>
              <div className="text-xl font-mono text-[#c9b787]">{s.data.scheduler_ticks ?? 0}</div>
            </div>
            <div className="border border-white/5 rounded p-2 bg-black/30">
              <div className="text-[10px] font-mono uppercase tracking-wider text-[#666]">receipts</div>
              <div className="text-xl font-mono text-[#c9b787]">{s.data.receipts ?? 0}</div>
            </div>
          </div>
          {s.data.chakras && (
            <div className="space-y-1 max-h-48 overflow-auto">
              {s.data.chakras.map((c) => {
                const ev = s.data.last_evaluation?.[c];
                return (
                  <div key={c} className="font-mono text-[10px] text-[#bbb] flex gap-3 border-b border-white/5 py-1">
                    <span className="text-[#c9b787] w-20 shrink-0">{c}</span>
                    <span className="text-[#888] truncate">
                      {ev === null || ev === undefined ? 'no evaluation yet' : JSON.stringify(ev).slice(0, 240)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

interface WiringPayload { chakras: string[]; edges: { src: string; dst: string; role: string }[]; shape: string }

export function AmaruWiringPanel() {
  const s = useAmaru<WiringPayload>('/api/amaru/scheduler/wiring');
  return (
    <Card title="AMARU · SCHEDULER WIRING · LIVE" source="GET /api/amaru/scheduler/wiring">
      {s.kind === 'loading' && <div className="font-mono text-[11px] text-[#666]">Loading…</div>}
      {s.kind === 'error' && <ErrorBlock s={s} />}
      {s.kind === 'ok' && (
        <div>
          <div className="font-mono text-[11px] text-[#8a8a8a] mb-2">
            shape <span className="text-[#c9b787]">{s.data.shape}</span> · {s.data.chakras.length} chakras · {s.data.edges.length} edges
          </div>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {s.data.chakras.map((c) => (
              <span key={c} className="font-mono text-[10px] px-2 py-1 rounded border border-[#c9b787]/30 bg-[#c9b787]/10 text-[#c9b787]">
                {c}
              </span>
            ))}
          </div>
          <div className="space-y-1 max-h-48 overflow-auto">
            {s.data.edges.map((e, i) => (
              <div key={i} className="font-mono text-[10px] text-[#bbb] flex gap-2">
                <span className="text-[#888] w-12">{e.role}</span>
                <span className="text-[#f5f5f5]">{e.src}</span>
                <span className="text-[#666]">→</span>
                <span className="text-[#f5f5f5]">{e.dst}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

interface Tripwire { id: string; title: string; status: 'pass' | 'warn' | 'trip'; detail: string }
interface TripwiresPayload { summary: { pass: number; warn: number; trip: number; total: number }; tripwires: Tripwire[] }

const TRIP_TONE: Record<string, string> = {
  pass: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  warn: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  trip: 'text-red-400 border-red-500/30 bg-red-500/10',
};

export function AmaruTripwiresPanel() {
  const s = useAmaru<TripwiresPayload>('/api/amaru/tripwires');
  return (
    <Card title="AMARU · HUKLLA TRIPWIRES · LIVE" source="GET /api/amaru/tripwires">
      {s.kind === 'loading' && <div className="font-mono text-[11px] text-[#666]">Loading…</div>}
      {s.kind === 'error' && <ErrorBlock s={s} />}
      {s.kind === 'ok' && (
        <>
          <div className="flex gap-3 mb-3 font-mono text-[11px]">
            <span className="text-emerald-400">{s.data.summary.pass} PASS</span>
            <span className="text-amber-400">{s.data.summary.warn} WARN</span>
            <span className="text-red-400">{s.data.summary.trip} TRIP</span>
            <span className="text-[#666]">· {s.data.summary.total} total</span>
          </div>
          <div className="space-y-1">
            {s.data.tripwires.map((t) => (
              <div key={t.id} className="flex items-center gap-3 text-[11px] font-mono border border-white/5 rounded px-3 py-2 bg-black/30">
                <span className={`px-2 py-0.5 rounded border ${TRIP_TONE[t.status] ?? ''} text-[10px] uppercase`}>{t.status}</span>
                <span className="text-[#c9b787] w-20 shrink-0">{t.id}</span>
                <span className="text-[#f5f5f5] flex-1">{t.title}</span>
                <span className="text-[#888] truncate max-w-xs">{t.detail}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

interface Receipt { seq?: number; ts?: string | number; kind?: string; hash?: string; [k: string]: unknown }
interface ReceiptsPayload { total: number; head_seq: number; items: Receipt[] }

export function AmaruReceiptsPanel({ limit = 12 }: { limit?: number }) {
  const s = useAmaru<ReceiptsPayload>(`/api/amaru/receipts?limit=${limit}`);
  return (
    <Card title="AMARU · RECEIPT CHAIN · LIVE" source="GET /api/amaru/receipts">
      {s.kind === 'loading' && <div className="font-mono text-[11px] text-[#666]">Loading…</div>}
      {s.kind === 'error' && <ErrorBlock s={s} />}
      {s.kind === 'ok' && (
        <>
          <div className="font-mono text-[11px] text-[#8a8a8a] mb-2">
            head_seq <span className="text-[#c9b787]">{s.data.head_seq}</span> · total <span className="text-[#c9b787]">{s.data.total}</span>
          </div>
          {s.data.items.length === 0 ? (
            <div className="font-mono text-[11px] text-[#666]">No receipts yet — chain initialised, no signed runs recorded.</div>
          ) : (
            <div className="space-y-1 max-h-64 overflow-auto">
              {s.data.items.slice(0, limit).map((r, i) => (
                <div key={`${r.seq ?? i}`} className="font-mono text-[10px] text-[#bbb] flex gap-3 border-b border-white/5 py-1">
                  <span className="text-[#c9b787] w-12 shrink-0">#{r.seq ?? i}</span>
                  <span className="text-[#888] w-24 shrink-0 truncate">{String(r.kind ?? '—')}</span>
                  <span className="truncate">{JSON.stringify(r).slice(0, 240)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

interface OverwatchPayload { panel_version?: string; thesis_kernel_hash?: string; thesis_brain_hash?: string; read_only?: boolean; summary?: Record<string, number> }
interface StatePayload { [k: string]: unknown }

export function AmaruHealthPanel() {
  const s = useAmaru<OverwatchPayload>('/api/amaru/overwatch/snapshot', 30_000);
  const st = useAmaru<StatePayload>('/api/amaru/state', 30_000);
  return (
    <Card title="AMARU · KERNEL HEALTH · LIVE" source="GET /api/amaru/overwatch/snapshot + /state">
      {(s.kind === 'loading' || st.kind === 'loading') && <div className="font-mono text-[11px] text-[#666]">Loading…</div>}
      {s.kind === 'error' && <ErrorBlock s={s} />}
      {s.kind === 'ok' && (
        <div className="font-mono text-[11px] text-[#8a8a8a] space-y-1">
          <div>panel <span className="text-[#c9b787]">{s.data.panel_version ?? '—'}</span></div>
          <div>kernel <span className="text-[#c9b787]">{String(s.data.thesis_kernel_hash ?? '—').slice(0, 12)}</span></div>
          <div>brain <span className="text-[#c9b787]">{String(s.data.thesis_brain_hash ?? '—').slice(0, 12)}</span></div>
          {s.data.summary && (
            <div className="flex gap-3 pt-1">
              <span className="text-emerald-400">{s.data.summary.pass ?? 0} pass</span>
              <span className="text-amber-400">{s.data.summary.warn ?? 0} warn</span>
              <span className="text-red-400">{s.data.summary.trip ?? 0} trip</span>
            </div>
          )}
        </div>
      )}
      {st.kind === 'ok' && (
        <details className="mt-2">
          <summary className="font-mono text-[10px] text-[#666] cursor-pointer">/state payload</summary>
          <pre className="font-mono text-[10px] text-[#888] mt-1 overflow-auto max-h-40 bg-black/30 p-2 rounded">{JSON.stringify(st.data, null, 2)}</pre>
        </details>
      )}
    </Card>
  );
}
