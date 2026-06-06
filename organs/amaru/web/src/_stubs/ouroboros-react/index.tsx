import type { LoopTrace } from '../ouroboros';

interface LoopGlyphProps {
  size?: number;
  convergence: number;
  spinning?: boolean;
  color?: string;
}

export function LoopGlyph({ size = 48, convergence, spinning, color = '#a0c4ff' }: LoopGlyphProps) {
  const r = (size - 8) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const dashLen = 2 * Math.PI * r * convergence;
  const totalLen = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
      <circle
        cx={cx} cy={cy} r={r}
        fill="none" stroke={color} strokeWidth={3}
        strokeDasharray={`${dashLen} ${totalLen - dashLen}`}
        strokeLinecap="round"
        style={{
          transform: 'rotate(-90deg)',
          transformOrigin: `${cx}px ${cy}px`,
          animation: spinning ? 'spin 1.2s linear infinite' : undefined,
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(270deg); } }`}</style>
    </svg>
  );
}

interface OuroborosTraceProps<S, O> {
  trace: LoopTrace<S, O>;
  describeOutput?: (output: O) => string;
}

export function OuroborosTrace<S, O>({ trace, describeOutput }: OuroborosTraceProps<S, O>) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 6,
      padding: 16,
    }}>
      <div style={{
        fontSize: 11, letterSpacing: '0.16em',
        textTransform: 'uppercase' as const,
        color: 'rgba(255,255,255,0.55)',
        marginBottom: 10,
      }}>
        Loop trace · {trace.steps.length} steps · {trace.converged ? 'converged' : 'did not converge'}
      </div>
      <div style={{ display: 'grid', gap: 4 }}>
        {trace.steps.map((step, i) => (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: '40px 80px 1fr',
            fontSize: 11,
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            padding: '4px 6px',
            borderRadius: 3,
            background: step.deltaMagnitude < 0.5 ? 'rgba(126,215,193,0.06)' : 'transparent',
            color: step.deltaMagnitude < 0.5 ? '#7ed7c1' : 'rgba(255,255,255,0.7)',
          }}>
            <span>#{step.stepIndex + 1}</span>
            <span>Δ {step.deltaMagnitude.toFixed(2)}</span>
            <span style={{ color: 'rgba(255,255,255,0.5)' }}>
              {describeOutput ? describeOutput(step.output as unknown as O) : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
