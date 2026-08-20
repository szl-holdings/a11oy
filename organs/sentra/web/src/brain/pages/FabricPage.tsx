// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import { useEffect, useRef, useState } from 'react';
import { DriftWatchPanel } from '../components/DriftWatchPanel';

interface KernelNode {
  id: string;
  label: string;
  role: string;
  pullsFrom: string;
  status: 'operational' | 'in-development' | 'planned';
  icon: string;
  color: string;
  previewPath: string;
  angle: number;
  radius: number;
}

const INNER_KERNELS: KernelNode[] = [
  { id: 'a11oy',     label: 'A11oy',     role: 'Governance & Constitution Fabric',  pullsFrom: 'Active constitution v1.0.0, playbooks, compliance controls, proof chain', status: 'operational',    icon: '◆', color: '#c9b787', previewPath: '/a11oy/',     angle: 0,   radius: 190 },
  { id: 'vessels',   label: 'Vessels',   role: 'Maritime Intelligence',              pullsFrom: 'Fleet positions, port windows, demurrage risk, berth utilization',          status: 'operational',    icon: '⚓', color: '#06b6d4', previewPath: '/vessels/',   angle: 60,  radius: 190 },
  { id: 'counsel',   label: 'Counsel',   role: 'Legal Matter Command',               pullsFrom: 'Matter staffing, obligation calendars, billing risk, attorney roster',       status: 'operational',    icon: '⚖', color: '#c9b787', previewPath: '/counsel/',   angle: 120, radius: 190 },
  { id: 'terra',     label: 'Terra',     role: 'Real Estate Intelligence',           pullsFrom: 'Portfolio positions, deal pipeline, valuations, market comps',               status: 'operational',    icon: '▣', color: '#10b981', previewPath: '/terra/',     angle: 180, radius: 190 },
  { id: 'sentra',    label: 'Sentra',    role: 'Cyber Resilience Command',           pullsFrom: 'Threat surface area, posture scores, incident queue, Glasswing patch state', status: 'operational',    icon: '⬡', color: '#a78bfa', previewPath: '/sentra/',    angle: 240, radius: 190 },
  { id: 'carlota',   label: 'Carlota Jo',role: 'Advisory Consulting',               pullsFrom: 'Client signals, engagement briefs, deliverables, revenue pipeline',          status: 'operational',    icon: '◎', color: '#f59e0b', previewPath: '/carlota-jo/',angle: 300, radius: 190 },
];

const OUTER_KERNELS: KernelNode[] = [
  { id: 'conduit',   label: 'Conduit',   role: 'Andean Reverse-ETL Fabric',         pullsFrom: 'Data sync state, convergence metrics, diff ledger, source entropy',          status: 'operational',    icon: '↻', color: '#06b6d4', previewPath: '/conduit/',   angle: 20,  radius: 290 },
  { id: 'api',       label: 'API',       role: 'Platform API Server',               pullsFrom: 'Doctrine CRUD, agent orchestration, WebSocket events, auth sessions',        status: 'operational',    icon: '◈', color: '#64748b', previewPath: '/api/',       angle: 80,  radius: 290 },
  { id: 'pulse',     label: 'Pulse',     role: 'Signal Intelligence',               pullsFrom: 'Market signals, alert cadence, forecast confidence, anomaly flags',          status: 'in-development', icon: '◉', color: '#f43f5e', previewPath: '/pulse/',     angle: 200, radius: 290 },
  { id: 'lyte',      label: 'Lyte',      role: 'License Intelligence Catalog',      pullsFrom: 'License exposure, contract terms, usage analytics, renewal windows',         status: 'operational',    icon: '◇', color: '#14b8a6', previewPath: '/lyte/',      angle: 260, radius: 290 },
  { id: 'command',   label: 'Command',   role: 'Agentic Control Plane',             pullsFrom: 'Agent task queue, tool invocations, escalation state, operator inbox',       status: 'in-development', icon: '⬟', color: '#3b82f6', previewPath: '/command/',   angle: 320, radius: 290 },
];

const ALL_KERNELS = [...INNER_KERNELS, ...OUTER_KERNELS];

export function FabricPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedKernel, setSelectedKernel] = useState<KernelNode | null>(null);
  const [hoveredKernel, setHoveredKernel] = useState<KernelNode | null>(null);
  const frameRef = useRef(0);
  const rafRef = useRef(0);

  const CX = 400, CY = 310;

  const getNodePos = (k: KernelNode) => {
    const rad = (k.angle * Math.PI) / 180;
    return { x: CX + Math.cos(rad) * k.radius, y: CY + Math.sin(rad) * k.radius };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      frameRef.current++;
      const t = frameRef.current * 0.018;
      ctx.clearRect(0, 0, 800, 620);

      // Orbital rings
      for (const r of [190, 290]) {
        ctx.beginPath();
        ctx.arc(CX, CY, r, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.04)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 10]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Spoke lines + traveling particles
      for (const k of ALL_KERNELS) {
        const pos = getNodePos(k);
        const baseAlpha = 0.1 + Math.sin(t + k.angle * 0.05) * 0.04;
        const dashOffset = -(t * 25 + k.angle) % 20;

        ctx.save();
        ctx.setLineDash([4, 8]);
        ctx.lineDashOffset = dashOffset;
        ctx.beginPath();
        ctx.moveTo(CX, CY);
        ctx.lineTo(pos.x, pos.y);
        ctx.strokeStyle = k.status === 'operational'
          ? `rgba(6, 182, 212, ${baseAlpha})`
          : `rgba(100, 116, 139, ${baseAlpha * 0.5})`;
        ctx.lineWidth = k.radius < 240 ? 0.9 : 0.5;
        ctx.stroke();
        ctx.restore();

        // Traveling pulse particle
        const pulse = Math.sin(t * 1.3 + k.angle * 0.05) * 0.5 + 0.5;
        const px = CX + (pos.x - CX) * pulse;
        const py = CY + (pos.y - CY) * pulse;
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fillStyle = k.status === 'operational'
          ? `rgba(6, 182, 212, ${0.4 + pulse * 0.5})`
          : `rgba(100, 116, 139, 0.25)`;
        ctx.fill();
      }

      // Inner ring lateral connections
      for (let i = 0; i < INNER_KERNELS.length; i++) {
        const a = INNER_KERNELS[i];
        const b = INNER_KERNELS[(i + 1) % INNER_KERNELS.length];
        ctx.beginPath();
        ctx.moveTo(getNodePos(a).x, getNodePos(a).y);
        ctx.lineTo(getNodePos(b).x, getNodePos(b).y);
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.04)';
        ctx.lineWidth = 0.5;
        ctx.setLineDash([]);
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const resolveKernel = (mx: number, my: number): KernelNode | null => {
    for (const k of ALL_KERNELS) {
      const pos = getNodePos(k);
      const dx = mx - pos.x, dy = my - pos.y;
      if (Math.sqrt(dx * dx + dy * dy) < 28) return k;
    }
    return null;
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = (e.clientX - rect.left) * (800 / rect.width);
    const my = (e.clientY - rect.top)  * (620 / rect.height);
    const k = resolveKernel(mx, my);
    setSelectedKernel(prev => (prev?.id === k?.id ? null : k));
  };

  const handleMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = (e.clientX - rect.left) * (800 / rect.width);
    const my = (e.clientY - rect.top)  * (620 / rect.height);
    setHoveredKernel(resolveKernel(mx, my));
  };

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 600, marginBottom: 6 }}>
          ✦ ECOSYSTEM FABRIC
        </div>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.5rem' }}>Artifact Kernel Map</h1>
        <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>
          ROSIE at the center — {ALL_KERNELS.length} artifact kernels across two orbital rings. Click a kernel to explore what ROSIE reads from it.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.5rem', alignItems: 'start' }}>
        {/* Canvas */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(6, 182, 212, 0.12)',
          borderRadius: 12, overflow: 'hidden',
          position: 'relative',
          cursor: hoveredKernel ? 'pointer' : 'default',
        }}>
          <canvas
            ref={canvasRef}
            width={800} height={620}
            style={{ display: 'block', width: '100%', height: 'auto' }}
            onMouseMove={handleMove}
            onMouseLeave={() => setHoveredKernel(null)}
            onClick={handleClick}
          />

          {/* ROSIE center node */}
          <div style={{
            position: 'absolute',
            left: `${(CX / 800) * 100}%`, top: `${(CY / 620) * 100}%`,
            transform: 'translate(-50%, -50%)',
            width: 64, height: 64, borderRadius: '50%',
            background: 'linear-gradient(135deg, #06b6d4, #7c3aed)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 40px rgba(6,182,212,0.4), 0 0 80px rgba(124,58,237,0.2)',
            pointerEvents: 'none', zIndex: 2,
          }}>
            <div style={{ fontSize: 10, fontWeight: 800, color: '#fff' }}>ROSIE</div>
            <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.7)' }}>r0513</div>
          </div>

          {/* Kernel node overlays */}
          {ALL_KERNELS.map(k => {
            const pos = getNodePos(k);
            const isHov = hoveredKernel?.id === k.id;
            const isSel = selectedKernel?.id === k.id;
            const base = k.radius < 240 ? 44 : 36;
            const sz = isHov || isSel ? base + 12 : base;
            return (
              <div key={k.id} style={{
                position: 'absolute',
                left: `${(pos.x / 800) * 100}%`, top: `${(pos.y / 620) * 100}%`,
                transform: 'translate(-50%, -50%)',
                width: sz, height: sz, borderRadius: '50%',
                background: isSel ? k.color : k.status === 'operational' ? `${k.color}22` : 'rgba(15,23,42,0.8)',
                border: `${isSel ? 2.5 : 1.5}px solid ${k.status === 'operational' ? k.color : '#475569'}`,
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s',
                boxShadow: isHov || isSel ? `0 0 20px ${k.color}55` : 'none',
                zIndex: 1, pointerEvents: 'none',
              }}>
                <span style={{ fontSize: k.radius < 240 ? 14 : 10, lineHeight: 1, color: isSel ? '#030712' : k.status === 'operational' ? k.color : '#475569' }}>{k.icon}</span>
                <span style={{ fontSize: 7, fontWeight: 700, color: isSel ? '#030712' : k.status === 'operational' ? k.color : '#475569', lineHeight: 1, marginTop: 1 }}>
                  {k.label}
                </span>
              </div>
            );
          })}

          {/* Legend */}
          <div style={{ position: 'absolute', bottom: 8, left: 12, display: 'flex', gap: '1rem', pointerEvents: 'none' }}>
            {[['#10b981', 'Operational'], ['#f59e0b', 'In Development']].map(([c, l]) => (
              <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#475569' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: c }} /> {l}
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {selectedKernel ? (
            <div style={{
              background: 'rgba(15, 23, 42, 0.8)',
              border: `1px solid ${selectedKernel.color}33`,
              borderRadius: 12, padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <div style={{
                  width: 40, height: 40, borderRadius: '50%',
                  background: `${selectedKernel.color}22`,
                  border: `2px solid ${selectedKernel.color}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
                }}>{selectedKernel.icon}</div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{selectedKernel.label}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>{selectedKernel.role}</div>
                </div>
              </div>
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 4 }}>WHAT ROSIE READS</div>
                <div style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.6 }}>{selectedKernel.pullsFrom}</div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                <div style={{
                  display: 'inline-flex', padding: '0.2rem 0.6rem',
                  background: selectedKernel.status === 'operational' ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)',
                  border: `1px solid ${selectedKernel.status === 'operational' ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}`,
                  borderRadius: 20, fontSize: 11,
                  color: selectedKernel.status === 'operational' ? '#10b981' : '#f59e0b',
                }}>{selectedKernel.status}</div>
                <div style={{
                  display: 'inline-flex', padding: '0.2rem 0.6rem',
                  background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.15)',
                  borderRadius: 20, fontSize: 11, color: '#67e8f9',
                }}>{selectedKernel.radius > 240 ? 'outer ring' : 'inner ring'}</div>
              </div>
              {selectedKernel.status === 'operational' && (
                <a href={selectedKernel.previewPath} target="_blank" rel="noreferrer"
                  style={{
                    display: 'block', width: '100%', padding: '0.6rem',
                    background: `${selectedKernel.color}18`,
                    border: `1px solid ${selectedKernel.color}33`,
                    borderRadius: 8, textAlign: 'center',
                    color: selectedKernel.color, fontSize: 13, fontWeight: 600,
                    textDecoration: 'none',
                  }}>
                  Open {selectedKernel.label} →
                </a>
              )}
            </div>
          ) : (
            <div style={{
              background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(6,182,212,0.1)',
              borderRadius: 12, padding: '1.25rem', textAlign: 'center',
            }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>✦</div>
              <div style={{ fontSize: 13, color: '#64748b' }}>Click a kernel node to explore what ROSIE reads from it.</div>
            </div>
          )}

          {/* Kernel lists */}
          <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(6,182,212,0.12)', borderRadius: 12, padding: '1.25rem' }}>
            {[['INNER RING — CORE DOMAINS', INNER_KERNELS], ['OUTER RING — EXTENDED FABRIC', OUTER_KERNELS]].map(([title, kernels]) => (
              <div key={title as string}>
                <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.5rem', marginTop: title === 'INNER RING — CORE DOMAINS' ? 0 : '0.75rem' }}>
                  {title as string}
                </div>
                {(kernels as KernelNode[]).map(k => (
                  <button key={k.id}
                    onClick={() => setSelectedKernel(prev => prev?.id === k.id ? null : k)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: '0.6rem',
                      padding: '0.4rem 0.5rem', marginBottom: '0.2rem',
                      background: selectedKernel?.id === k.id ? `${k.color}12` : 'transparent',
                      border: selectedKernel?.id === k.id ? `1px solid ${k.color}33` : '1px solid transparent',
                      borderRadius: 6, cursor: 'pointer', textAlign: 'left',
                    }}>
                    <span style={{ fontSize: 11, color: k.status === 'operational' ? k.color : '#475569' }}>{k.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: k.status === 'operational' ? '#e2e8f0' : '#475569', fontWeight: 600 }}>{k.label}</div>
                    </div>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: k.status === 'operational' ? '#10b981' : '#f59e0b' }} />
                  </button>
                ))}
              </div>
            ))}
          </div>

          <DriftWatchPanel />
        </div>
      </div>
    </div>
  );
}
