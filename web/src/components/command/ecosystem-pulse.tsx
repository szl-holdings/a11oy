import { motion } from 'framer-motion';
import { Minus, TrendingDown, TrendingUp } from 'lucide-react';
import type { DomainData } from '../types';

interface EcosystemPulseProps {
  domains: DomainData[];
  compositeScore: number;
  compositeStatus: string;
}

function scoreToTrend(score: number): 'up' | 'down' | 'neutral' {
  if (score >= 80) return 'up';
  if (score <= 65) return 'down';
  return 'neutral';
}

function scoreToColor(score: number): string {
  if (score >= 80) return 'var(--color-low)';
  if (score >= 70) return 'var(--color-high)';
  return 'var(--color-critical)';
}

const GAUGE_CX = 70;
const GAUGE_CY = 72;
const GAUGE_R = 58;

const GAUGE_PATH = `M ${GAUGE_CX - GAUGE_R} ${GAUGE_CY} A ${GAUGE_R} ${GAUGE_R} 0 0 1 ${GAUGE_CX + GAUGE_R} ${GAUGE_CY}`;

function CompositeGauge({ score, status }: { score: number; status: string }) {
  const color = scoreToColor(score);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <svg width="140" height="80" viewBox="0 0 140 80" aria-label={`Composite health: ${score}`}>
          <path
            d={GAUGE_PATH}
            stroke="var(--color-surface-border)"
            strokeWidth={10}
            fill="none"
            strokeLinecap="round"
          />
          <motion.path
            key={score}
            d={GAUGE_PATH}
            stroke={color}
            strokeWidth={10}
            fill="none"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: score / 100 }}
            transition={{ duration: 1.1, ease: 'easeOut' }}
          />
          <motion.text
            key={`label-${score}`}
            x={GAUGE_CX}
            y={GAUGE_CY - 4}
            textAnchor="middle"
            dominantBaseline="auto"
            fontSize="26"
            fontWeight="700"
            letterSpacing="-1"
            fill="var(--color-fg-primary)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            {score}
          </motion.text>
        </svg>
      </div>

      <span
        className="text-xs font-medium uppercase tracking-wider px-2 py-0.5 rounded border"
        style={{
          color,
          borderColor: color,
          backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
        }}
      >
        {status}
      </span>

      <h2
        className="text-[10px] font-bold tracking-widest uppercase"
        style={{ color: 'var(--color-fg-muted)' }}
      >
        Composite Health
      </h2>
    </div>
  );
}

export function EcosystemPulse({ domains, compositeScore, compositeStatus }: EcosystemPulseProps) {
  return (
    <div className="flex flex-col md:flex-row items-center justify-between gap-8 p-8 bg-[var(--color-surface-base)] border border-[var(--color-surface-border)] rounded-xl">
      <div className="shrink-0">
        <CompositeGauge score={compositeScore} status={compositeStatus} />
      </div>

      <div className="flex-1 grid grid-cols-2 md:grid-cols-3 gap-3 w-full">
        {domains.map((d, i) => (
          <motion.div
            key={d.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.06 }}
            className="flex flex-col gap-1 p-3 rounded-lg border"
            style={{
              backgroundColor: 'var(--color-bg-primary)',
              borderColor: 'var(--color-surface-border)',
            }}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold" style={{ color: d.color }}>
                {d.name}
              </span>
              <div className="flex items-center gap-1">
                <motion.span
                  key={d.score}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm font-bold"
                  style={{ color: 'var(--color-fg-primary)' }}
                >
                  {d.score}
                </motion.span>
                {scoreToTrend(d.score) === 'up' ? (
                  <TrendingUp className="w-3 h-3" style={{ color: 'var(--color-low)' }} />
                ) : scoreToTrend(d.score) === 'down' ? (
                  <TrendingDown className="w-3 h-3" style={{ color: 'var(--color-critical)' }} />
                ) : (
                  <Minus className="w-3 h-3" style={{ color: 'var(--color-fg-muted)' }} />
                )}
              </div>
            </div>
            <span className="text-[10px] truncate" style={{ color: 'var(--color-fg-muted)' }}>
              {d.status}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
