import { useEffect, useState } from 'react';
import type { DriftBucketSnapshot } from '@szl-holdings/formulas';

interface DriftBucketsResponse {
  ok: boolean;
  data?: {
    buckets: DriftBucketSnapshot[];
    thresholds: { gapMin: number; samplesMin: number; windowSize: number };
    bucketCount: number;
    firingCount: number;
  };
}

const POLL_MS = 5000;

function pct(x: number): string {
  return `${Math.round(Math.max(0, Math.min(1, x)) * 100)}%`;
}

function fmtGap(g: number): string {
  return `${(g * 100).toFixed(1)}%`;
}

function MiniChart({ observed, baseline }: { observed: number[]; baseline: number[] }) {
  const n = Math.max(observed.length, baseline.length);
  if (n < 2) {
    return (
      <div style={{ fontSize: 11, color: '#64748b', padding: '0.5rem 0' }}>
        Not enough samples yet to chart.
      </div>
    );
  }
  const all = [...observed, ...baseline];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = Math.max(1e-9, max - min);
  const W = 280, H = 60, PAD = 4;
  const toPoints = (arr: number[]): string =>
    arr.map((v, i) => {
      const x = PAD + (i / Math.max(1, arr.length - 1)) * (W - PAD * 2);
      const y = H - PAD - ((v - min) / span) * (H - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  return (
    <svg width={W} height={H} style={{ display: 'block' }} aria-label="observed vs baseline">
      <rect x={0} y={0} width={W} height={H} fill="rgba(15,23,42,0.6)" rx={4} />
      <polyline fill="none" stroke="rgba(148,163,184,0.55)" strokeWidth={1.2} points={toPoints(baseline)} />
      <polyline fill="none" stroke="#06b6d4" strokeWidth={1.4} points={toPoints(observed)} />
    </svg>
  );
}

export function DriftWatchPanel({ apiBase = '' }: { apiBase?: string }) {
  const [data, setData] = useState<DriftBucketsResponse['data'] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const res = await fetch(`${apiBase}/api/a11oy/formulas/drift-buckets`, {
          headers: { accept: 'application/json' },
        });
        const json = (await res.json()) as DriftBucketsResponse;
        if (cancelled) return;
        if (!json.ok || !json.data) {
          setError('Drift watch endpoint returned an error.');
        } else {
          setData(json.data);
          setError(null);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Drift watch fetch failed.');
      }
    }
    void tick();
    const id = setInterval(tick, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  const buckets = data?.buckets ?? [];

  return (
    <div
      data-testid="drift-watch-panel"
      style={{
        background: 'rgba(15, 23, 42, 0.6)',
        border: '1px solid rgba(6, 182, 212, 0.12)',
        borderRadius: 12,
        padding: '1.25rem',
        marginTop: '1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <div>
          <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600 }}>
            ROSIE — DRIFT WATCH
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
            What's warming up in the evolution loop before a proposal is filed.
          </div>
        </div>
        <div style={{ fontSize: 11, color: '#64748b' }}>
          {data ? (
            <>
              <span style={{ color: '#06b6d4', fontWeight: 600 }}>{data.firingCount}</span>{' '}
              firing · {data.bucketCount} tracked · gapMin {fmtGap(data.thresholds.gapMin)} · samplesMin{' '}
              {data.thresholds.samplesMin}
            </>
          ) : (
            'loading…'
          )}
        </div>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            fontSize: 12,
            color: '#fca5a5',
            background: 'rgba(127,29,29,0.18)',
            border: '1px solid rgba(239,68,68,0.25)',
            padding: '0.4rem 0.6rem',
            borderRadius: 6,
            marginBottom: '0.5rem',
          }}
        >
          {error}
        </div>
      )}

      {data && buckets.length === 0 && !error && (
        <div style={{ fontSize: 12, color: '#64748b', padding: '0.6rem 0' }}>
          No drift buckets recorded yet. As instrumented formulas execute, their (formulaId, parameter)
          pairs will start accumulating here.
        </div>
      )}

      {buckets.map((b) => {
        const key = `${b.formulaId}::${b.parameter}`;
        const isOpen = expanded === key;
        return (
          <div
            key={key}
            style={{
              borderTop: '1px solid rgba(148,163,184,0.08)',
              padding: '0.55rem 0.25rem',
            }}
          >
            <button
              type="button"
              onClick={() => setExpanded(isOpen ? null : key)}
              aria-expanded={isOpen}
              style={{
                display: 'flex',
                width: '100%',
                gap: '0.75rem',
                alignItems: 'center',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: '#e2e8f0',
                textAlign: 'left',
                padding: 0,
              }}
            >
              <span
                aria-label={b.willFire ? 'firing' : 'warming'}
                style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: b.willFire ? '#f59e0b' : '#64748b',
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: b.willFire ? '#fbbf24' : '#cbd5e1' }}>
                  {b.formulaId}
                  <span style={{ color: '#64748b', fontWeight: 400 }}> · {b.parameter}</span>
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                  {b.sampleCount}/{b.samplesMinTarget} samples · mean gap {fmtGap(b.meanGap)} (target &gt;{' '}
                  {fmtGap(b.gapMinTarget)})
                </div>
              </div>
              <div style={{ width: 80, fontSize: 10, color: '#94a3b8', textAlign: 'right' }}>
                <div>samples {pct(b.progressSamples)}</div>
                <div style={{ marginTop: 2 }}>gap {pct(b.progressGap)}</div>
              </div>
              <div style={{ width: 14, color: '#475569', fontSize: 12 }}>{isOpen ? '▾' : '▸'}</div>
            </button>
            {isOpen && (
              <div style={{ marginTop: '0.5rem', paddingLeft: 18 }}>
                <MiniChart observed={b.observedTail} baseline={b.baselineTail} />
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 4, display: 'flex', gap: '0.75rem' }}>
                  <span><span style={{ color: '#06b6d4' }}>━</span> observed</span>
                  <span><span style={{ color: '#94a3b8' }}>━</span> baseline</span>
                  <span style={{ marginLeft: 'auto' }}>
                    v{b.fromVersion} · {b.oldValue} → {b.candidateValue}
                  </span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
