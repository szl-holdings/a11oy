import { useEffect, useRef } from 'react';

interface SpinLatticeProps {
  width?: number;
  height?: number;
  animated?: boolean;
  energyHistory?: number[];
  solving?: boolean;
}

interface Spin {
  x: number;
  y: number;
  value: 1 | -1;
  targetValue: 1 | -1;
  energy: number;
  phase: number;
}

export function SpinLattice({ width = 400, height = 200, animated = true, energyHistory, solving = false }: SpinLatticeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<{ spins: Spin[]; frame: number; raf: number }>({
    spins: [],
    frame: 0,
    raf: 0,
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const COLS = Math.floor(width / 22);
    const ROWS = Math.floor(height / 22);
    const SPACING_X = width / COLS;
    const SPACING_Y = height / ROWS;

    const spins: Spin[] = [];
    for (let row = 0; row < ROWS; row++) {
      for (let col = 0; col < COLS; col++) {
        const v = Math.random() > 0.5 ? 1 : -1 as 1 | -1;
        spins.push({
          x: SPACING_X * col + SPACING_X / 2,
          y: SPACING_Y * row + SPACING_Y / 2,
          value: v,
          targetValue: v,
          energy: Math.random(),
          phase: Math.random() * Math.PI * 2,
        });
      }
    }
    stateRef.current.spins = spins;

    let frame = 0;

    const draw = () => {
      frame++;
      stateRef.current.frame = frame;
      const t = frame * 0.018;

      ctx.clearRect(0, 0, width, height);

      ctx.fillStyle = 'rgba(3, 7, 18, 0)';
      ctx.fillRect(0, 0, width, height);

      if (animated) {
        if (frame % 12 === 0) {
          const idx = Math.floor(Math.random() * spins.length);
          spins[idx].targetValue = spins[idx].targetValue === 1 ? -1 : 1;
        }
        for (const spin of spins) {
          spin.value = spin.targetValue;
          spin.phase += 0.015;
        }
      }

      for (let i = 0; i < spins.length - 1; i++) {
        const a = spins[i];
        for (let j = i + 1; j < spins.length; j++) {
          const b = spins[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist > SPACING_X * 1.6) continue;
          const aligned = a.value === b.value;
          const alpha = aligned ? 0.18 : 0.06;
          const pulse = solving ? (Math.sin(t * 3 + i * 0.1) * 0.5 + 0.5) * 0.1 : 0;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = aligned
            ? `rgba(6, 182, 212, ${alpha + pulse})`
            : `rgba(124, 58, 237, ${alpha * 0.5 + pulse})`;
          ctx.lineWidth = aligned ? 0.8 : 0.4;
          ctx.stroke();
        }
      }

      for (const spin of spins) {
        const isUp = spin.value === 1;
        const pulse = solving
          ? Math.sin(t * 2 + spin.phase) * 0.5 + 0.5
          : Math.sin(spin.phase + t) * 0.3 + 0.7;
        const r = 4 + pulse * 2;

        const grad = ctx.createRadialGradient(spin.x, spin.y, 0, spin.x, spin.y, r * 2);
        if (isUp) {
          grad.addColorStop(0, `rgba(6, 182, 212, ${0.8 + pulse * 0.2})`);
          grad.addColorStop(1, 'rgba(6, 182, 212, 0)');
        } else {
          grad.addColorStop(0, `rgba(124, 58, 237, ${0.6 + pulse * 0.2})`);
          grad.addColorStop(1, 'rgba(124, 58, 237, 0)');
        }

        ctx.beginPath();
        ctx.arc(spin.x, spin.y, r * 1.8, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(spin.x, spin.y, r * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = isUp ? '#06b6d4' : '#7c3aed';
        ctx.globalAlpha = 0.9;
        ctx.fill();
        ctx.globalAlpha = 1;

        if (solving) {
          ctx.beginPath();
          ctx.moveTo(spin.x, spin.y - r - 3);
          ctx.lineTo(spin.x, spin.y + r + 3);
          ctx.strokeStyle = isUp ? 'rgba(6,182,212,0.6)' : 'rgba(124,58,237,0.6)';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      if (solving) {
        ctx.fillStyle = 'rgba(6, 182, 212, 0.06)';
        const rippleR = ((frame % 60) / 60) * Math.max(width, height);
        ctx.beginPath();
        ctx.arc(width / 2, height / 2, rippleR, 0, Math.PI * 2);
        ctx.fill();
      }

      stateRef.current.raf = requestAnimationFrame(draw);
    };

    stateRef.current.raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(stateRef.current.raf);
  }, [width, height, animated, solving]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ display: 'block', borderRadius: 8 }}
    />
  );
}
