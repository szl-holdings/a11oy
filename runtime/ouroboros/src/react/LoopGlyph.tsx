import type { CSSProperties } from 'react';

export interface LoopGlyphProps {
  /** Pixel size; the glyph is square. Default 64. */
  size?: number;
  /** Stroke color. Default gold. */
  color?: string;
  /** Background fill. Default transparent. */
  background?: string;
  /**
   * Convergence value in [0, 1]. 0 = chaotic loop (unsettled), 1 = perfectly
   * stable. Drives stroke opacity and the inner pulse.
   */
  convergence?: number;
  /** Optional spinning animation (CSS keyframes); off by default. */
  spinning?: boolean;
  /** Style override. */
  style?: CSSProperties;
  /** Accessible label. */
  label?: string;
}

/**
 * The Ouroboros — a stylized infinity-as-serpent glyph. Draws a single
 * lemniscate (figure-8) with a head and a tail at the meeting point, suggesting
 * the snake biting itself. Used as the visual signature of any loop-native
 * surface.
 */
export function LoopGlyph({
  size = 64,
  color = '#c9b787',
  background,
  convergence = 1,
  spinning = false,
  style,
  label = 'Ouroboros loop',
}: LoopGlyphProps) {
  const c = clamp(convergence, 0, 1);
  const opacity = 0.4 + 0.6 * c;
  const innerR = 4 + 6 * c;

  return (
    <div
      role="img"
      aria-label={label}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background,
        borderRadius: 6,
        ...style,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-labelledby="loop-glyph-title"
        style={{
          animation: spinning ? 'ouroboros-spin 8s linear infinite' : undefined,
        }}
      >
        <title id="loop-glyph-title">{label}</title>
        {/* Lemniscate path: a figure-8 traced in one stroke */}
        <path
          d="M50,50 C 30,30 10,30 10,50 C 10,70 30,70 50,50 C 70,30 90,30 90,50 C 90,70 70,70 50,50 Z"
          stroke={color}
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={opacity}
          fill="none"
        />
        {/* Head (right tip) — small triangle suggesting the serpent's head */}
        <circle cx={86} cy={50} r={3} fill={color} opacity={opacity} />
        {/* Tail merge dot (the bite) at the centre */}
        <circle cx={50} cy={50} r={innerR / 2} fill={color} opacity={c} />
        {/* Inner convergence pulse */}
        <circle
          cx={50}
          cy={50}
          r={innerR}
          stroke={color}
          strokeWidth={1}
          opacity={0.18 + 0.6 * c}
          fill="none"
        />
      </svg>
      {/* Inline keyframes (CSS-in-JS without a runtime). */}
      <style>{`
        @keyframes ouroboros-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}
