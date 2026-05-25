import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

const ACCENT = '#c9b787';
const ACCENT_DIM = '#a89868';
const BORDER = 'rgba(255,255,255,0.10)';
const BORDER_SOFT = 'rgba(255,255,255,0.05)';
const TEXT_DIM = '#8a8a8a';
const MONO = "'JetBrains Mono', 'Fira Code', monospace";
const ease = [0.22, 1, 0.36, 1] as [number, number, number, number];

const ORBITS = [
  { r: 70, dur: 38, dir: 1, count: 1 },
  { r: 110, dur: 52, dir: -1, count: 2 },
  { r: 158, dur: 78, dir: 1, count: 3 },
  { r: 210, dur: 110, dir: -1, count: 2 },
];

const STATIONS = [
  { angle: 18, r: 158, label: 'SEXTANT' },
  { angle: 102, r: 210, label: 'COUNSEL' },
  { angle: 198, r: 110, label: 'DOMAINE' },
  { angle: 286, r: 158, label: 'PARAGON' },
];

const TICKS = Array.from({ length: 36 }, (_, i) => i * 10);

function useTick(intervalMs: number) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => (t + 1) % 1_000_000), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return tick;
}

function pad(n: number, w = 2) {
  return n.toString().padStart(w, '0');
}

function formatStamp(now: Date) {
  return `${now.getUTCFullYear()}.${pad(now.getUTCMonth() + 1)}.${pad(now.getUTCDate())} ` +
    `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}Z`;
}

export function HeroCanvas() {
  const tick = useTick(1000);
  const now = new Date(Date.now());
  void tick;
  const stamp = formatStamp(now);
  const epoch = (Date.now() / 1000) | 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 1.2, delay: 0.25, ease }}
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '1 / 1',
        maxWidth: 520,
        margin: '0 auto',
        borderRadius: 18,
        overflow: 'hidden',
        background:
          'radial-gradient(circle at 50% 50%, rgba(201,183,135,0.06) 0%, rgba(201,183,135,0.02) 35%, rgba(0,0,0,0) 65%), #0d0d0d',
        border: `1px solid ${BORDER}`,
        boxShadow: '0 30px 80px -20px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(255,255,255,0.02)',
      }}
      aria-hidden
    >
      {/* corner crosshairs */}
      {[
        { top: 12, left: 12, rot: 0 },
        { top: 12, right: 12, rot: 90 },
        { bottom: 12, right: 12, rot: 180 },
        { bottom: 12, left: 12, rot: 270 },
      ].map((c, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            top: c.top,
            left: c.left,
            right: c.right,
            bottom: c.bottom,
            width: 14,
            height: 14,
            borderTop: `1px solid ${ACCENT}`,
            borderLeft: `1px solid ${ACCENT}`,
            opacity: 0.55,
            transform: `rotate(${c.rot}deg)`,
          }}
        />
      ))}

      {/* HUD top-left */}
      <div style={{
        position: 'absolute', top: 22, left: 22,
        fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.18em',
        textTransform: 'uppercase', color: TEXT_DIM, lineHeight: 1.7,
      }}>
        <div>NODE · A11OY-01</div>
        <div>ORBIT · NOMINAL</div>
        <div style={{ color: ACCENT_DIM }}>● TRACK · LIVE</div>
      </div>

      {/* HUD top-right */}
      <div style={{
        position: 'absolute', top: 22, right: 22, textAlign: 'right',
        fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.18em',
        textTransform: 'uppercase', color: TEXT_DIM, lineHeight: 1.7,
      }}>
        <div>{stamp}</div>
        <div>EPOCH {epoch}</div>
        <div>Λ ≥ 0.90</div>
      </div>

      {/* HUD bottom */}
      <div style={{
        position: 'absolute', bottom: 22, left: 22, right: 22,
        display: 'flex', justifyContent: 'space-between',
        fontFamily: MONO, fontSize: 9, letterSpacing: '0.2em',
        textTransform: 'uppercase', color: TEXT_DIM,
      }}>
        <span>SIG · 1024 · OK</span>
        <span style={{ color: ACCENT_DIM }}>9-AXIS ∧ · REPLAY 1ed4d253</span>
      </div>

      {/* scan line */}
      <motion.div
        initial={{ y: '-10%' }}
        animate={{ y: '110%' }}
        transition={{ duration: 5.5, repeat: Infinity, ease: 'linear' }}
        style={{
          position: 'absolute', left: 0, right: 0, height: 1,
          background: `linear-gradient(90deg, transparent, ${ACCENT} 50%, transparent)`,
          opacity: 0.35, mixBlendMode: 'screen',
        }}
      />

      <svg
        viewBox="0 0 500 500"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <defs>
          <radialGradient id="hc-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={ACCENT} stopOpacity="0.55" />
            <stop offset="55%" stopColor={ACCENT} stopOpacity="0.08" />
            <stop offset="100%" stopColor={ACCENT} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hc-halo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={ACCENT} stopOpacity="0.15" />
            <stop offset="100%" stopColor={ACCENT} stopOpacity="0" />
          </radialGradient>
        </defs>

        <circle cx="250" cy="250" r="240" fill="url(#hc-halo)" />

        {/* tick ring */}
        <g opacity="0.55">
          {TICKS.map((t) => {
            const a = (t * Math.PI) / 180;
            const long = t % 30 === 0;
            const r1 = long ? 232 : 236;
            const r2 = 240;
            return (
              <line
                key={t}
                x1={250 + r1 * Math.cos(a)}
                y1={250 + r1 * Math.sin(a)}
                x2={250 + r2 * Math.cos(a)}
                y2={250 + r2 * Math.sin(a)}
                stroke={long ? ACCENT_DIM : BORDER}
                strokeWidth={long ? 1 : 0.6}
              />
            );
          })}
          {[0, 90, 180, 270].map((t) => {
            const a = (t * Math.PI) / 180;
            return (
              <text
                key={`l-${t}`}
                x={250 + 222 * Math.cos(a)}
                y={250 + 222 * Math.sin(a) + 3}
                textAnchor="middle"
                fontFamily={MONO}
                fontSize="8"
                fill={ACCENT_DIM}
                letterSpacing="2"
              >
                {pad(t, 3)}
              </text>
            );
          })}
        </g>

        {/* orbit rings */}
        {ORBITS.map((o) => (
          <circle
            key={`r-${o.r}`}
            cx="250"
            cy="250"
            r={o.r}
            fill="none"
            stroke={BORDER}
            strokeWidth="0.75"
            strokeDasharray={o.r === 158 ? '0' : '2 6'}
            opacity={o.r === 158 ? 0.6 : 0.35}
          />
        ))}

        {/* radial guides */}
        {[0, 45, 90, 135].map((deg) => {
          const a = (deg * Math.PI) / 180;
          return (
            <line
              key={`g-${deg}`}
              x1={250 - 230 * Math.cos(a)}
              y1={250 - 230 * Math.sin(a)}
              x2={250 + 230 * Math.cos(a)}
              y2={250 + 230 * Math.sin(a)}
              stroke={BORDER_SOFT}
              strokeWidth="0.5"
            />
          );
        })}

        {/* stations */}
        {STATIONS.map((s) => {
          const a = (s.angle * Math.PI) / 180;
          const cx = 250 + s.r * Math.cos(a);
          const cy = 250 + s.r * Math.sin(a);
          return (
            <g key={s.label}>
              <circle cx={cx} cy={cy} r="9" fill="none" stroke={ACCENT} strokeWidth="1" opacity="0.7" />
              <circle cx={cx} cy={cy} r="3" fill={ACCENT} />
              <text
                x={cx + 14}
                y={cy + 3}
                fontFamily={MONO}
                fontSize="9"
                fill={ACCENT_DIM}
                letterSpacing="2"
              >
                {s.label}
              </text>
            </g>
          );
        })}

        {/* core */}
        <circle cx="250" cy="250" r="58" fill="url(#hc-core)" />
        <circle cx="250" cy="250" r="34" fill="none" stroke={ACCENT} strokeWidth="0.75" opacity="0.6" />
        <circle cx="250" cy="250" r="22" fill="none" stroke={ACCENT_DIM} strokeWidth="0.5" />
        <text
          x="250"
          y="254"
          textAnchor="middle"
          fontFamily={MONO}
          fontSize="13"
          fill="#f5f5f5"
          letterSpacing="3"
          fontWeight="500"
        >
          a11oy
        </text>
      </svg>

      {/* traveling pulses on each orbit */}
      <svg
        viewBox="0 0 500 500"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        {ORBITS.flatMap((o) =>
          Array.from({ length: o.count }).map((_, i) => {
            const offset = (i / o.count) * o.dur;
            return (
              <g key={`p-${o.r}-${i}`}>
                <motion.circle
                  r="3.2"
                  fill={ACCENT}
                  initial={false}
                  animate={{
                    rotate: o.dir > 0 ? 360 : -360,
                  }}
                  transition={{
                    duration: o.dur,
                    repeat: Infinity,
                    ease: 'linear',
                    delay: -offset,
                  }}
                  style={{
                    transformOrigin: '250px 250px',
                    transformBox: 'fill-box',
                  }}
                  cx={250 + o.r}
                  cy={250}
                />
              </g>
            );
          }),
        )}
      </svg>

      {/* core pulse */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0.5 }}
        animate={{ scale: [0.8, 1.4, 0.8], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: 'easeOut' }}
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: 110,
          height: 110,
          marginTop: -55,
          marginLeft: -55,
          borderRadius: '50%',
          border: `1px solid ${ACCENT}`,
          pointerEvents: 'none',
        }}
      />
    </motion.div>
  );
}
