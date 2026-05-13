/**
 * DoctrineRadar — 9-axis SVG spider chart, mini/full sizes
 * File: a11oy/src/ui/DoctrineRadar.tsx
 *
 * Doctrine v2 binding.
 * Source: frontend_dev.md §5 "Shared Component", §3 SZL Re-Anchor Table
 *
 * 9 axes (from frontend_dev.md DoctrineScores interface):
 *   measurability, honesty, cleanliness, completeness, parsimony,
 *   groundedness, timeliness, diversity, novelty
 *
 * Visual spec (frontend_dev.md §5):
 *   Target polygon: dashed line in doctrine gold (#C8B26A)
 *   Actual polygon: filled teal (#01696F at 40% opacity)
 *   mini = 80×80px, full = 360×360px with labels + legend
 *   Respects prefers-reduced-motion for draw animation
 */

import React, { useId, useMemo, useRef, useEffect } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DoctrineScores {
  measurability: number;  // 0-10
  honesty: number;
  cleanliness: number;
  completeness: number;
  parsimony: number;
  groundedness: number;
  timeliness: number;
  diversity: number;
  novelty: number;
}

export interface DoctrineRadarProps {
  actual: DoctrineScores;
  target: DoctrineScores;
  size?: "mini" | "full";
  queryId?: string;
  showAxesLabels?: boolean;
  /** Callback fired when an axis is clicked (full size only) */
  onAxisClick?: (axis: keyof DoctrineScores, actual: number, target: number) => void;
  className?: string;
  style?: React.CSSProperties;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const AXES: Array<keyof DoctrineScores> = [
  "measurability",
  "honesty",
  "cleanliness",
  "completeness",
  "parsimony",
  "groundedness",
  "timeliness",
  "diversity",
  "novelty",
];

const AXIS_COUNT = AXES.length;

// SZL badge palette (frontend_dev.md §5 Color/Typography)
const COLOR_TEAL         = "#01696F";
const COLOR_DOCTRINE_GOLD = "#C8B26A";
const COLOR_GRID         = "#374151";  // gray-700
const COLOR_AXIS_LABEL   = "#9CA3AF";  // gray-400

// ─── Geometry helpers ─────────────────────────────────────────────────────────

function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleRad: number
): [number, number] {
  return [
    cx + radius * Math.cos(angleRad - Math.PI / 2),
    cy + radius * Math.sin(angleRad - Math.PI / 2),
  ];
}

function buildPolygonPoints(
  cx: number,
  cy: number,
  maxR: number,
  scores: DoctrineScores,
  maxScore: number
): string {
  return AXES.map((axis, i) => {
    const angle = (2 * Math.PI * i) / AXIS_COUNT;
    const r = (scores[axis] / maxScore) * maxR;
    const [x, y] = polarToCartesian(cx, cy, r, angle);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

// ─── Component ────────────────────────────────────────────────────────────────

const DoctrineRadar: React.FC<DoctrineRadarProps> = ({
  actual,
  target,
  size = "full",
  queryId,
  showAxesLabels,
  onAxisClick,
  className,
  style,
}) => {
  const uid = useId();
  const isMini = size === "mini";

  const svgSize  = isMini ? 80  : 360;
  const cx       = svgSize / 2;
  const cy       = svgSize / 2;
  const maxR     = isMini ? 34  : 140;
  const labelR   = isMini ? 0   : 158;
  const maxScore = 10;
  const gridLevels = isMini ? 2 : 5;

  const showLabels = !isMini && (showAxesLabels !== false);

  // Animation — stroke-dasharray approach, respects prefers-reduced-motion
  const actualPolygonRef = useRef<SVGPolygonElement | null>(null);
  useEffect(() => {
    const polygon = actualPolygonRef.current;
    if (!polygon || isMini) return;
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;

    const length = polygon.getTotalLength?.() ?? 600;
    polygon.style.strokeDasharray = String(length);
    polygon.style.strokeDashoffset = String(length);
    polygon.style.transition = "stroke-dashoffset 500ms ease-out";
    requestAnimationFrame(() => {
      polygon.style.strokeDashoffset = "0";
    });
  }, [actual, isMini]);

  // Grid rings
  const gridRings = useMemo(
    () =>
      Array.from({ length: gridLevels }, (_, i) => {
        const r = ((i + 1) / gridLevels) * maxR;
        return AXES.map((_, j) => {
          const angle = (2 * Math.PI * j) / AXIS_COUNT;
          return polarToCartesian(cx, cy, r, angle);
        });
      }),
    [gridLevels, maxR, cx, cy]
  );

  // Axis lines
  const axisLines = useMemo(
    () =>
      AXES.map((_, i) => {
        const angle = (2 * Math.PI * i) / AXIS_COUNT;
        return polarToCartesian(cx, cy, maxR, angle);
      }),
    [cx, cy, maxR]
  );

  // Label positions
  const labelPositions = useMemo(
    () =>
      AXES.map((axis, i) => {
        const angle = (2 * Math.PI * i) / AXIS_COUNT;
        const [x, y] = polarToCartesian(cx, cy, labelR, angle);
        const actualScore = actual[axis];
        const targetScore = target[axis];
        const delta = actualScore - targetScore;
        return { axis, x, y, actualScore, targetScore, delta };
      }),
    [cx, cy, labelR, actual, target]
  );

  const actualPoints  = buildPolygonPoints(cx, cy, maxR, actual, maxScore);
  const targetPoints  = buildPolygonPoints(cx, cy, maxR, target, maxScore);

  // Screen-reader fallback table
  const a11yTable = (
    <table aria-hidden="false" className="sr-only">
      <caption>Doctrine Radar — 9-axis scores</caption>
      <thead>
        <tr>
          <th scope="col">Axis</th>
          <th scope="col">Actual (0–10)</th>
          <th scope="col">Target (0–10)</th>
          <th scope="col">Δ</th>
        </tr>
      </thead>
      <tbody>
        {AXES.map(axis => (
          <tr key={axis}>
            <th scope="row">{axis}</th>
            <td>{actual[axis].toFixed(1)}</td>
            <td>{target[axis].toFixed(1)}</td>
            <td>{(actual[axis] - target[axis]).toFixed(1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  const compositeActual  = (AXES.reduce((s, a) => s + actual[a],  0) / AXIS_COUNT).toFixed(1);
  const compositeTarget  = (AXES.reduce((s, a) => s + target[a], 0) / AXIS_COUNT).toFixed(1);

  return (
    <div
      className={className}
      style={{ display: "inline-block", ...style }}
      data-query-id={queryId}
    >
      <svg
        width={svgSize}
        height={svgSize}
        viewBox={`0 0 ${svgSize} ${svgSize}`}
        aria-label={`Doctrine Radar: actual ${compositeActual}/10, target ${compositeTarget}/10`}
        role="img"
        style={{ overflow: "visible" }}
      >
        {/* ── Grid rings ── */}
        {gridRings.map((ring, ringIdx) => (
          <polygon
            key={`ring-${ringIdx}`}
            points={ring.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ")}
            fill="none"
            stroke={COLOR_GRID}
            strokeWidth={isMini ? 0.5 : 1}
            opacity={0.5}
          />
        ))}

        {/* ── Axis lines ── */}
        {axisLines.map(([x, y], i) => (
          <line
            key={`axis-${i}`}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke={COLOR_GRID}
            strokeWidth={isMini ? 0.5 : 1}
            opacity={0.6}
          />
        ))}

        {/* ── Target polygon (dashed doctrine gold) ── */}
        <polygon
          points={targetPoints}
          fill="none"
          stroke={COLOR_DOCTRINE_GOLD}
          strokeWidth={isMini ? 1 : 1.5}
          strokeDasharray={isMini ? "2,2" : "4,3"}
          opacity={0.8}
        />

        {/* ── Actual polygon (filled teal, 40% opacity) ── */}
        <polygon
          ref={actualPolygonRef}
          points={actualPoints}
          fill={COLOR_TEAL}
          fillOpacity={0.4}
          stroke={COLOR_TEAL}
          strokeWidth={isMini ? 1 : 2}
          opacity={0.9}
        />

        {/* ── Axis labels (full size only) ── */}
        {showLabels &&
          labelPositions.map(({ axis, x, y, actualScore, targetScore, delta }) => {
            const textAnchor =
              Math.abs(x - cx) < 5 ? "middle" : x < cx ? "end" : "start";
            const isBelow = y > cy;
            const dyBase = isBelow ? 12 : -4;

            return (
              <g
                key={`label-${axis}`}
                role="button"
                tabIndex={0}
                aria-label={`${axis}: actual ${actualScore.toFixed(1)}, target ${targetScore.toFixed(1)}, delta ${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`}
                style={{ cursor: onAxisClick ? "pointer" : "default" }}
                onClick={() => onAxisClick?.(axis, actualScore, targetScore)}
                onKeyDown={e => {
                  if (e.key === "Enter" || e.key === " ") {
                    onAxisClick?.(axis, actualScore, targetScore);
                  }
                }}
              >
                <text
                  x={x}
                  y={y + dyBase}
                  textAnchor={textAnchor}
                  fontSize={11}
                  fill={COLOR_AXIS_LABEL}
                  fontFamily="Inter, -apple-system, sans-serif"
                >
                  {axis}
                </text>
                {/* Delta badge on hover — rendered always at this scale */}
                <text
                  x={x}
                  y={y + dyBase + 13}
                  textAnchor={textAnchor}
                  fontSize={9}
                  fill={delta >= 0 ? "#2DA44E" : "#EF4444"}
                  fontFamily="Inter, -apple-system, sans-serif"
                  fontWeight="600"
                >
                  {delta >= 0 ? "+" : ""}{delta.toFixed(1)}
                </text>
              </g>
            );
          })}

        {/* ── Legend (full size only) ── */}
        {!isMini && (
          <g transform={`translate(${svgSize - 110}, ${svgSize - 38})`}>
            <line x1={0} y1={8} x2={16} y2={8} stroke={COLOR_TEAL} strokeWidth={2} />
            <circle cx={8} cy={8} r={3} fill={COLOR_TEAL} />
            <text x={20} y={12} fontSize={10} fill={COLOR_AXIS_LABEL}
              fontFamily="Inter, -apple-system, sans-serif">Actual</text>
            <line x1={0} y1={24} x2={16} y2={24}
              stroke={COLOR_DOCTRINE_GOLD} strokeWidth={1.5} strokeDasharray="4,3" />
            <text x={20} y={28} fontSize={10} fill={COLOR_AXIS_LABEL}
              fontFamily="Inter, -apple-system, sans-serif">Target</text>
          </g>
        )}
      </svg>

      {/* Screen-reader fallback */}
      {a11yTable}
    </div>
  );
};

export default DoctrineRadar;

// ─── Composite score helper ───────────────────────────────────────────────────

/** Compute composite doctrine score (0-10) from 9-axis scores */
export function compositeDoctrineScore(scores: DoctrineScores): number {
  return AXES.reduce((sum, axis) => sum + scores[axis], 0) / AXIS_COUNT;
}

/** Default target scores (doctrine v2 minimum thresholds) */
export const DEFAULT_TARGET_SCORES: DoctrineScores = {
  measurability: 9,
  honesty: 9,
  cleanliness: 9,
  completeness: 9,
  parsimony: 9,
  groundedness: 9,
  timeliness: 9,
  diversity: 9,
  novelty: 9,
};
