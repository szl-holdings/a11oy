import { useEffect, useRef, useState } from 'react';
import type { AppPage } from '../App';
import { SpinLattice } from '../components/SpinLattice';

interface Props { onNavigate: (p: AppPage) => void; }

const THREADS = [
  {
    id: 'ising',
    glyph: '⬡',
    title: 'Ising / Quantum-Inspired Optimization',
    color: '#06b6d4',
    description:
      'Combinatorial decisions modeled as spin-glass problems. Variables become spins; constraints encode interaction energies; the solver finds the global minimum of the Hamiltonian using simulated annealing — the classical analogue of quantum tunneling.',
  },
  {
    id: 'cuda-q',
    glyph: '◉',
    title: 'CUDA-Q Orchestration Fabric',
    color: '#7c3aed',
    description:
      'ROSIE is positioned as the orchestration layer over the SZL artifact ecosystem — each artifact is a "kernel" plugged into ROSIE\'s governance fabric. The same Ising Hamiltonian ROSIE solves classically is forward-compatible with NVIDIA CUDA-Q for hardware-accelerated QUBO.',
  },
  {
    id: 'rtx',
    glyph: '✦',
    title: 'RTX Visual Intelligence',
    color: '#c9b787',
    description:
      'A rich, GPU-feel operator interface: animated spin-lattice visualization, 3D ecosystem fabric, and an always-learning research pulse. The visual layer makes the optimization process tangible — operators see the solve in real time, not just the result.',
  },
];

const METRICS = [
  { label: 'Artifacts Governed', value: '10', unit: 'kernels' },
  { label: 'Constitution Version', value: '1.0.0', unit: '' },
  { label: 'Research Entries', value: '32', unit: 'papers' },
  { label: 'Solve Engine', value: 'SA/QUBO', unit: 'Ising' },
];

export function IdentityPage({ onNavigate }: Props) {
  const [scrollY, setScrollY] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = () => setScrollY(window.scrollY);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  return (
    <div style={{ minHeight: '100vh', paddingBottom: '6rem' }}>
      {/* Hero */}
      <section
        ref={heroRef}
        style={{
          position: 'relative', overflow: 'hidden',
          minHeight: '85vh',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '4rem 1.5rem',
          textAlign: 'center',
        }}
      >
        {/* Lattice Background */}
        <div style={{
          position: 'absolute', inset: 0, zIndex: 0,
          opacity: 0.35,
          transform: `translateY(${scrollY * 0.2}px)`,
        }}>
          <SpinLattice width={1280} height={600} animated={true} />
        </div>

        {/* Glow rings */}
        <div style={{
          position: 'absolute', top: '40%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 600, height: 600,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Content */}
        <div style={{ position: 'relative', zIndex: 1, maxWidth: 800 }}>
          {/* Badge */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.35rem 1rem',
            background: 'rgba(6, 182, 212, 0.08)',
            border: '1px solid rgba(6, 182, 212, 0.25)',
            borderRadius: 20, marginBottom: '2rem',
            fontSize: 12, color: '#06b6d4', fontWeight: 600, letterSpacing: '0.06em',
          }}>
            <span style={{ animation: 'spin-pulse 2s ease-in-out infinite' }}>◎</span>
            r0513 · UNIFIED DECISION FABRIC · A11OY-GOVERNED
          </div>

          {/* Title */}
          <h1 style={{
            fontSize: 'clamp(3rem, 8vw, 6rem)',
            fontWeight: 900, letterSpacing: '-0.03em',
            lineHeight: 0.95,
            margin: '0 0 1.5rem',
            color: '#e2e8f0',
          }}>
            <span style={{
              background: 'linear-gradient(135deg, #06b6d4 0%, #7c3aed 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}>ROSIE</span>
          </h1>

          <p style={{
            fontSize: 'clamp(1rem, 2.5vw, 1.35rem)',
            color: '#94a3b8', lineHeight: 1.6,
            maxWidth: 640, margin: '0 auto 1rem',
          }}>
            The governed Ising-style decision optimizer and agentic AI orchestration fabric.
            Combinatorial allocation, scheduling, and assignment — solved with quantum-inspired heuristics,
            checked against your active constitution, and written to the proof ledger.
          </p>

          <p style={{
            fontSize: 14, color: '#475569', fontStyle: 'italic',
            marginBottom: '2.5rem',
          }}>
            "Rosie" — the callsign for r0513. Named after the AI that keeps the systems running.
          </p>

          {/* CTAs */}
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={() => onNavigate('optimizer')}
              style={{
                padding: '0.85rem 2rem',
                background: 'linear-gradient(135deg, #06b6d4, #7c3aed)',
                border: 'none', borderRadius: 8,
                color: '#fff', fontSize: 15, fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 0 30px rgba(6,182,212,0.3)',
              }}
            >
              ⬡ Launch Optimizer
            </button>
            <button
              onClick={() => onNavigate('fabric')}
              style={{
                padding: '0.85rem 2rem',
                background: 'transparent',
                border: '1px solid rgba(6, 182, 212, 0.3)',
                borderRadius: 8,
                color: '#06b6d4', fontSize: 15, fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              ✦ Explore Fabric
            </button>
          </div>
        </div>

        {/* Metrics strip */}
        <div style={{
          position: 'absolute', bottom: '2rem', left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: '2rem', flexWrap: 'wrap', justifyContent: 'center',
          zIndex: 1,
        }}>
          {METRICS.map(m => (
            <div key={m.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#06b6d4', lineHeight: 1 }}>
                {m.value}
                {m.unit && <span style={{ fontSize: 12, color: '#475569', marginLeft: 4 }}>{m.unit}</span>}
              </div>
              <div style={{ fontSize: 11, color: '#475569', marginTop: 2, letterSpacing: '0.06em' }}>{m.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Three NVIDIA Threads */}
      <section style={{ maxWidth: 1100, margin: '0 auto', padding: '0 1.5rem 4rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
          <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 600, marginBottom: 8 }}>
            THREE THREADS · ONE FABRIC
          </div>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', margin: 0 }}>
            What ROSIE Is Built On
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
          {THREADS.map(t => (
            <div key={t.id} style={{
              background: 'rgba(15, 23, 42, 0.6)',
              border: `1px solid ${t.color}22`,
              borderRadius: 12, padding: '1.75rem',
              position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                background: `linear-gradient(90deg, ${t.color}, transparent)`,
              }} />
              <div style={{
                fontSize: 28, marginBottom: '0.75rem',
                color: t.color, display: 'block',
              }}>{t.glyph}</div>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0', margin: '0 0 0.75rem' }}>
                {t.title}
              </h3>
              <p style={{ fontSize: 13, color: '#64748b', lineHeight: 1.7, margin: 0 }}>
                {t.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* A11oy Governance Banner */}
      <section style={{ maxWidth: 1100, margin: '0 auto', padding: '0 1.5rem 4rem' }}>
        <div style={{
          background: 'rgba(201, 183, 135, 0.04)',
          border: '1px solid rgba(201, 183, 135, 0.15)',
          borderRadius: 12, padding: '2rem',
          display: 'grid', gridTemplateColumns: '1fr auto', gap: '2rem', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: 11, color: '#c9b787', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 8 }}>
              ◆ A11OY GOVERNANCE INTEGRATION
            </div>
            <h3 style={{ fontSize: 20, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.75rem' }}>
              Every solve is governed, audited, and proof-chained.
            </h3>
            <p style={{ fontSize: 13, color: '#64748b', lineHeight: 1.7, margin: 0, maxWidth: 600 }}>
              ROSIE reads A11oy's active constitution and playbooks before each optimization run.
              Constitution clauses constrain the objective function, validate the solution,
              and write a signed proof-ledger entry — making every allocation decision traceable,
              auditable, and reproducible.
            </p>
          </div>
          <button
            onClick={() => onNavigate('proof')}
            style={{
              padding: '0.75rem 1.5rem',
              background: 'rgba(201, 183, 135, 0.1)',
              border: '1px solid rgba(201, 183, 135, 0.3)',
              borderRadius: 8, color: '#c9b787',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            View Proof Ledger →
          </button>
        </div>
      </section>
    </div>
  );
}
