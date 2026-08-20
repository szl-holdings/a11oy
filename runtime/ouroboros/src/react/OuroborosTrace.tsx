import type { CSSProperties } from 'react';
import type { LoopTrace } from '../types.js';

export interface OuroborosTraceProps<S, O = unknown> {
  trace: LoopTrace<S, O>;
  /** Render a one-line description of an intermediate output. Optional. */
  describeOutput?: (output: O | undefined, step: number) => string;
  /** Accent color for the converged step. Defaults to gold. */
  accent?: string;
  /** Width in pixels. Default 'auto' (100%). */
  width?: number | string;
  /** Compact mode strips the header and exit footer. */
  compact?: boolean;
}

const COLORS = {
  bg: 'rgba(255,255,255,0.02)',
  surface: 'rgba(255,255,255,0.04)',
  border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.14)',
  text: 'rgba(255,255,255,0.88)',
  dim: 'rgba(255,255,255,0.55)',
  muted: 'rgba(255,255,255,0.32)',
  delta: 'rgba(120,180,255,0.85)',
  consistency: 'rgba(120,255,180,0.78)',
  warning: 'rgba(255,180,120,0.85)',
  exitConverged: 'rgba(120,255,180,0.85)',
  exitConsistent: 'rgba(120,180,255,0.85)',
  exitBudget: 'rgba(255,180,120,0.85)',
  exitAborted: 'rgba(255,120,120,0.85)',
};

const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';

export function OuroborosTrace<S, O = unknown>({
  trace,
  describeOutput,
  accent = '#c9b787',
  width = '100%',
  compact = false,
}: OuroborosTraceProps<S, O>) {
  const maxDelta = Math.max(...trace.steps.map((s) => s.deltaMagnitude), 1e-9);

  const exitColor =
    trace.exitReason === 'converged'
      ? COLORS.exitConverged
      : trace.exitReason === 'consistent'
        ? COLORS.exitConsistent
        : trace.exitReason === 'budgetExhausted'
          ? COLORS.exitBudget
          : COLORS.exitAborted;

  const containerStyle: CSSProperties = {
    width,
    background: COLORS.bg,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 6,
    fontFamily: MONO,
    color: COLORS.text,
    overflow: 'hidden',
  };

  return (
    <div style={containerStyle}>
      {!compact ? (
        <div
          style={{
            padding: '10px 14px',
            borderBottom: `1px solid ${COLORS.border}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontSize: 10,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: COLORS.dim,
              }}
            >
              Ouroboros Trace
            </span>
            <span style={{ fontSize: 12, color: COLORS.text }}>{trace.label}</span>
          </div>
          <div style={{ display: 'flex', gap: 14, fontSize: 11, color: COLORS.dim }}>
            <span>
              steps <span style={{ color: COLORS.text }}>{trace.stepsRun}/{trace.maxSteps}</span>
            </span>
            <span>
              {trace.totalDurationMs.toFixed(1)}<span style={{ color: COLORS.muted }}>ms</span>
            </span>
            <span style={{ color: exitColor }}>{trace.exitReason}</span>
          </div>
        </div>
      ) : null}

      <div>
        {trace.steps.map((s) => {
          const widthPct = (s.deltaMagnitude / maxDelta) * 100;
          const consistencyPct =
            s.consistency !== undefined ? Math.round(s.consistency * 100) : null;
          const isConverged =
            s.index === trace.steps.length - 1 && trace.exitReason === 'converged';
          const isSafeExit = s.index === trace.earliestSafeExit;

          return (
            <div
              key={s.index}
              style={{
                display: 'grid',
                gridTemplateColumns: '36px 1fr 90px 80px 60px',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                borderBottom: `1px solid ${COLORS.border}`,
                background: isConverged ? `${accent}10` : 'transparent',
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: isConverged ? accent : COLORS.dim,
                  fontFamily: MONO,
                }}
              >
                #{s.index}
                {isSafeExit && !isConverged ? (
                  <span style={{ color: COLORS.exitConsistent, marginLeft: 4 }}>✓</span>
                ) : null}
              </span>

              {/* delta bar */}
              <div
                style={{
                  position: 'relative',
                  height: 10,
                  background: COLORS.surface,
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: `${widthPct}%`,
                    background: isConverged ? accent : COLORS.delta,
                    transition: 'width 200ms ease',
                  }}
                />
              </div>

              <span style={{ fontSize: 10, color: COLORS.dim, textAlign: 'right' }}>
                Δ {s.deltaMagnitude.toExponential(2)}
              </span>
              <span
                style={{
                  fontSize: 10,
                  color: consistencyPct !== null ? COLORS.consistency : COLORS.muted,
                  textAlign: 'right',
                }}
                title="Cross-step consistency vs final output"
              >
                {consistencyPct !== null ? `c=${consistencyPct}%` : '—'}
              </span>
              <span style={{ fontSize: 10, color: COLORS.muted, textAlign: 'right' }}>
                {s.durationMs.toFixed(1)}ms
              </span>

              {describeOutput ? (
                <div
                  style={{
                    gridColumn: '2 / -1',
                    fontSize: 11,
                    color: COLORS.dim,
                    paddingTop: 2,
                  }}
                >
                  {describeOutput(s.output, s.index)}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {!compact ? (
        <div
          style={{
            padding: '8px 14px',
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 10,
            color: COLORS.muted,
            borderTop: `1px solid ${COLORS.border}`,
          }}
        >
          <span>id {trace.id}</span>
          <span>
            earliest safe exit{' '}
            <span style={{ color: COLORS.text }}>
              {trace.earliestSafeExit >= 0 ? `#${trace.earliestSafeExit}` : '—'}
            </span>
          </span>
        </div>
      ) : null}
    </div>
  );
}
