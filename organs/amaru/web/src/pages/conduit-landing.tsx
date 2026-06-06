import { ContactModal } from '@szl-holdings/shared-ui/contact-modal';
import {
  Activity,
  ArrowRight,
  ChevronRight,
  Database,
  GitBranch,
  Layers,
  Network,
  Repeat,
  ShieldCheck,
  Workflow,
  Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'wouter';

const NAV_LINKS = [
  { label: 'Platform',   href: '#platform' },
  { label: 'Convergence', href: '#convergence' },
  { label: 'Doctrine',    href: '#doctrine' },
  { label: 'Outcomes',    href: '#outcomes' },
];

const PILLARS = [
  {
    icon: GitBranch,
    code: 'DLT.01',
    title: 'Append-only delta log',
    body: 'Every record change is a hashed, ordered delta. Replay any sync from genesis to now and recover the exact state — byte-identical.',
  },
  {
    icon: ShieldCheck,
    code: 'ING.02',
    title: 'Hash-verified ingest',
    body: 'Source rows are content-addressed before they touch the destination. Drift, corruption, and replay attacks fail loudly — never silently.',
  },
  {
    icon: Repeat,
    code: 'LOOP.03',
    title: 'Bounded convergence loop',
    body: 'Sources, models, and destinations close as a measurable feedback loop with a Λ floor of 0.90 — convergence is a number, not a promise.',
  },
  {
    icon: Network,
    code: 'MESH.04',
    title: 'Multi-source orchestration',
    body: 'Connectors, mappings, and policies composed as a graph. Add a source without rewriting destinations. Add a destination without rewriting sources.',
  },
  {
    icon: Workflow,
    code: 'GOV.05',
    title: 'Policy-gated activation',
    body: 'Approval queues, blast-radius caps, and outcome gates per destination. No record activated without an audited intent.',
  },
  {
    icon: Activity,
    code: 'OBS.06',
    title: 'Observability ledger',
    body: 'Latency, lift, failures, and policy blocks per sync, per destination — surfaced as a ledger, not a dashboard you have to babysit.',
  },
];

const SIGNAL_FEED = [
  { code: 'SYNC',  label: 'salesforce → warehouse · 968,142 records · convergence 0.94', t: '00:01', tone: 'ok' },
  { code: 'POL',   label: 'policy gate held · 10 records pending CFO approval',          t: '00:03', tone: 'med' },
  { code: 'DRIFT', label: 'source schema drift detected · netsuite.invoices · contained', t: '00:07', tone: 'high' },
  { code: 'REPL',  label: 'byte-identical replay verified · run #2,481',                  t: '00:11', tone: 'ok' },
  { code: 'LIFT',  label: 'outcome lift +6.0% · activation cohort A',                     t: '00:14', tone: 'ok' },
];

const TONE_DOT: Record<string, string> = {
  critical: '#b85450',
  high: '#d4a853',
  med: '#c9b787',
  ok: '#5a8a6e',
};

const PROOF_STAGES = [
  { code: '01', label: 'Source' },
  { code: '02', label: 'Hash' },
  { code: '03', label: 'Map' },
  { code: '04', label: 'Policy' },
  { code: '05', label: 'Activate' },
  { code: '06', label: 'Outcome' },
  { code: '07', label: 'Replay' },
];

const READINESS = [
  { k: 'Records activated · 24h',  v: '968k', sub: 'across 26 active syncs' },
  { k: 'Convergence (Λ)',          v: '0.91', sub: 'rolling, floor 0.90' },
  { k: 'Avg latency · 24h',        v: '511ms', sub: 'p50 source → destination' },
  { k: 'Outcome lift · activation', v: '+6.0%', sub: 'attested vs. control' },
];

const PROVENANCE = [
  { k: 'Λ floor',         v: '0.90' },
  { k: 'Moral grounding', v: '0.95' },
  { k: 'Measurability',   v: '0.95' },
  { k: 'Λ axes',          v: '9 · AND' },
  { k: 'Replays',         v: '5 · byte-identical' },
  { k: 'DOI ledger',      v: '13 entries' },
  { k: 'Ingestion',       v: 'PUBLIC_ONLY' },
];

function useReveal() {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const els = Array.from(document.querySelectorAll<HTMLElement>('.reveal'));
    if (reduce) {
      els.forEach((e) => e.classList.add('in'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            (e.target as HTMLElement).classList.add('in');
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

function OuroborosFrame() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let af = 0;
    let t = 0;
    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      c.width = c.offsetWidth * dpr;
      c.height = c.offsetHeight * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener('resize', resize);
    const draw = () => {
      if (document.hidden) {
        af = requestAnimationFrame(draw);
        return;
      }
      t += 0.004;
      const w = c.offsetWidth;
      const h = c.offsetHeight;
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2 + 40;
      // three concentric rings — the loop
      const rings = [
        { r: 220, w: 1.0, o: 0.45, s: 1 },
        { r: 280, w: 0.7, o: 0.28, s: -1 },
        { r: 350, w: 0.5, o: 0.18, s: 1 },
      ];
      for (const r of rings) {
        ctx.beginPath();
        ctx.arc(cx, cy, r.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(201,183,135,${r.o * 0.35})`;
        ctx.lineWidth = r.w;
        ctx.setLineDash([2, 8]);
        ctx.stroke();
        ctx.setLineDash([]);
        // moving record packets along ring
        for (let i = 0; i < 5; i++) {
          const ang = t * r.s + (i * Math.PI * 2) / 5;
          const x = cx + Math.cos(ang) * r.r;
          const y = cy + Math.sin(ang) * r.r;
          ctx.beginPath();
          ctx.arc(x, y, 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(201,183,135,${0.6 * r.o})`;
          ctx.fill();
        }
      }
      // ouroboros arrow (ring closing on itself)
      const innerR = 160;
      ctx.beginPath();
      ctx.arc(cx, cy, innerR, t * 0.4, t * 0.4 + Math.PI * 1.7);
      ctx.strokeStyle = 'rgba(201,183,135,0.22)';
      ctx.lineWidth = 1;
      ctx.stroke();
      // tail dot
      const tx = cx + Math.cos(t * 0.4 + Math.PI * 1.7) * innerR;
      const ty = cy + Math.sin(t * 0.4 + Math.PI * 1.7) * innerR;
      ctx.beginPath();
      ctx.arc(tx, ty, 2.6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(201,183,135,0.7)';
      ctx.fill();
      af = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(af);
      window.removeEventListener('resize', resize);
    };
  }, []);
  return (
    <canvas
      ref={ref}
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
      aria-hidden
    />
  );
}

export default function ConduitLandingPage() {
  const [demoOpen, setDemoOpen] = useState(false);
  useReveal();

  return (
    <div className="min-h-screen text-[#f5f5f5] antialiased" style={{ background: '#0a0a0a' }}>
      <style>{`
        .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
        .display { font-family: 'Space Grotesk', system-ui, sans-serif; }
        .editorial { font-family: 'Space Grotesk', Georgia, serif; }
        .corner-frame { position: relative; }
        .corner-frame::before, .corner-frame::after,
        .corner-frame > .cf-tl, .corner-frame > .cf-br {
          content: ''; position: absolute; width: 10px; height: 10px;
          border-color: rgba(201,183,135,0.45); border-style: solid; pointer-events: none;
        }
        .corner-frame::before { top: 0; left: 0; border-width: 1px 0 0 1px; }
        .corner-frame::after  { bottom: 0; right: 0; border-width: 0 1px 1px 0; }
        .corner-frame > .cf-tl { top: 0; right: 0; border-width: 1px 1px 0 0; }
        .corner-frame > .cf-br { bottom: 0; left: 0; border-width: 0 0 1px 1px; }
        .grid-bg {
          background-image:
            linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
          background-size: 56px 56px;
          mask-image: radial-gradient(ellipse at center, #000 30%, transparent 75%);
        }
        .ticker-row:hover { background: rgba(201,183,135,0.025); }
        .cream-section { background: #f1ece2; color: #1a1814; }
        .cream-section .rule { background: rgba(26,24,20,0.12); }
        .dropcap::first-letter {
          font-family: 'Space Grotesk', Georgia, serif;
          font-size: 4.2rem; line-height: 0.85; float: left;
          padding: 0.2rem 0.65rem 0 0; font-weight: 300; color: #6b5d3e;
        }
        @keyframes pulseDot { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
        .live-dot { animation: pulseDot 2.2s ease-in-out infinite; }
        .reveal { opacity: 0; transform: translateY(14px); transition: opacity .9s cubic-bezier(.2,.7,.2,1), transform .9s cubic-bezier(.2,.7,.2,1); }
        .reveal.in { opacity: 1; transform: translateY(0); }
        .reveal-d1 { transition-delay: .06s; }
        .reveal-d2 { transition-delay: .12s; }
        .reveal-d3 { transition-delay: .18s; }
        .reveal-d4 { transition-delay: .24s; }
        @media (prefers-reduced-motion: reduce) { .reveal { opacity: 1; transform: none; transition: none; } }
      `}</style>

      <header className="sticky top-0 z-40 border-b border-white/[0.04]" style={{ background: 'rgba(10,10,10,0.78)', backdropFilter: 'blur(10px)' }}>
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-5 h-5 inline-flex items-center justify-center rounded border border-[#c9b787]/40 mono text-[9px] text-[#c9b787]">A</span>
            <span className="text-[13px] font-medium tracking-tight">Amaru</span>
            <span className="mono text-[10px] text-[#555] ml-2">/ convergent multi-source sync</span>
          </div>
          <nav className="hidden md:flex items-center gap-7">
            {NAV_LINKS.map((l) => (
              <a key={l.href} href={l.href} className="text-[12px] text-[#888] hover:text-[#c9b787] transition-colors">{l.label}</a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button onClick={() => setDemoOpen(true)} className="hidden sm:inline-flex text-[12px] text-[#888] hover:text-[#c9b787] transition-colors px-3 py-1.5">
              Request demo
            </button>
            <Link href="/cockpit">
              <span className="inline-flex items-center gap-1.5 text-[12px] font-medium px-3 py-1.5 rounded bg-[#c9b787] text-[#0a0a0a] hover:bg-[#d6c69a] transition-colors cursor-pointer">
                Open cockpit <ArrowRight className="w-3 h-3" />
              </span>
            </Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 grid-bg pointer-events-none" />
        <div className="absolute inset-0 pointer-events-none"><OuroborosFrame /></div>
        <div className="absolute top-20 left-6 hidden lg:flex flex-col gap-1 mono text-[10px] text-[#444]">
          <span>FABRIC · GLOBAL</span>
          <span>LEDGER · APPEND-ONLY</span>
          <span>POSTURE · CONVERGENT</span>
        </div>
        <div className="absolute top-20 right-6 hidden lg:flex flex-col items-end gap-1 mono text-[10px] text-[#444]">
          <span>NODE · AMARU-01</span>
          <span>EPOCH · 2026.Q2</span>
          <span className="flex items-center gap-1.5">
            <span className="live-dot inline-block w-1.5 h-1.5 rounded-full" style={{ background: '#5a8a6e', boxShadow: '0 0 6px #5a8a6e' }} />
            LIVE · RT
          </span>
        </div>

        <div className="relative max-w-5xl mx-auto px-6 pt-28 pb-32 text-center">
          <div className="reveal inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#c9b787]/15 bg-[#c9b787]/[0.04] mb-10">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c9b787] live-dot" />
            <span className="mono text-[10px] tracking-[0.2em] text-[#c9b787] uppercase">Convergent Sync · Series A</span>
          </div>

          <h1 className="reveal reveal-d1 display text-[clamp(2.6rem,6vw,5.2rem)] font-light leading-[1.02] tracking-[-0.035em] mb-7">
            The data sync that<br />
            <span style={{ background: 'linear-gradient(120deg,#f5f5f5 20%,#c9b787 90%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              proves what it moved.
            </span>
          </h1>

          <p className="reveal reveal-d2 text-[17px] leading-relaxed text-[#9a9a9a] max-w-xl mx-auto mb-12">
            Amaru is the convergent sync fabric. Append-only delta logs, hash-verified ingest, bounded
            feedback loops with measurable convergence — and a replay you can audit byte-for-byte.
          </p>

          <div className="reveal reveal-d3 flex items-center justify-center gap-3 flex-wrap">
            <Link href="/cockpit">
              <span className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-medium rounded-md cursor-pointer bg-[#c9b787] text-[#0a0a0a] hover:bg-[#d6c69a] transition-colors">
                Open cockpit <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </Link>
            <Link href="/connections">
              <span className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-medium text-[#c9b787] border border-[#c9b787]/25 rounded-md hover:bg-[#c9b787]/[0.05] transition-colors cursor-pointer">
                Inspect a sync
              </span>
            </Link>
          </div>

          <div className="reveal reveal-d4 mt-20 grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.05] rounded-md overflow-hidden max-w-3xl mx-auto">
            {READINESS.map((r) => (
              <div key={r.k} className="px-4 py-5 text-left" style={{ background: '#0a0a0a' }}>
                <p className="display text-[26px] font-light text-[#f5f5f5] tracking-tight">{r.v}</p>
                <p className="text-[11px] text-[#9a9a9a] mt-1.5">{r.k}</p>
                <p className="mono text-[9px] text-[#555] mt-1.5 uppercase tracking-wider">{r.sub}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PLATFORM */}
      <section id="platform" className="border-t border-white/[0.05] px-6 py-28">
        <div className="max-w-6xl mx-auto">
          <div className="reveal flex items-end justify-between mb-14 flex-wrap gap-6">
            <div className="max-w-xl">
              <p className="mono text-[10px] tracking-[0.2em] text-[#666] uppercase mb-3">PLATFORM · 06 PILLARS</p>
              <h2 className="display text-[40px] font-light leading-tight tracking-tight">
                Activation, with provenance attached.
              </h2>
            </div>
            <p className="text-[14px] text-[#888] max-w-sm leading-relaxed">
              Reverse ETL moves rows. Amaru moves rows with proof — hashed at the source, gated by policy,
              measured at the destination, replayable at any time.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-white/[0.05]">
            {PILLARS.map((p, i) => (
              <div key={p.code} className={`reveal reveal-d${(i % 4) + 1} relative p-7 group transition-colors hover:bg-[#0e0e0e]`} style={{ background: '#0a0a0a' }}>
                <div className="flex items-center justify-between mb-5">
                  <p.icon className="w-4 h-4 text-[#c9b787]/70 group-hover:text-[#c9b787] transition-colors" />
                  <span className="mono text-[9px] tracking-[0.2em] text-[#555] uppercase">{p.code}</span>
                </div>
                <h3 className="display text-[18px] font-medium text-[#f5f5f5] mb-2.5 tracking-tight">{p.title}</h3>
                <p className="text-[13px] leading-relaxed text-[#888]">{p.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CONVERGENCE — live ticker */}
      <section id="convergence" className="border-t border-white/[0.05] px-6 py-28">
        <div className="max-w-4xl mx-auto">
          <div className="reveal text-center mb-12">
            <p className="mono text-[10px] tracking-[0.2em] text-[#666] uppercase mb-3">CONVERGENCE · LIVE</p>
            <h2 className="display text-[36px] font-light leading-tight tracking-tight">Every record carries a receipt.</h2>
            <p className="text-[14px] text-[#888] max-w-md mx-auto mt-4 leading-relaxed">
              The convergence stream is the operating record of the fabric — every sync, every gate, every
              replay — content-addressed and attestable.
            </p>
          </div>

          <div className="reveal corner-frame rounded-md overflow-hidden" style={{ background: '#0c0c0c', border: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="cf-tl" /><span className="cf-br" />
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.04]">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full live-dot" style={{ background: '#5a8a6e', boxShadow: '0 0 6px #5a8a6e' }} />
                <span className="mono text-[10px] tracking-[0.2em] uppercase text-[#888]">Convergence Stream</span>
              </div>
              <span className="mono text-[10px] text-[#555]">Λ · 0.91</span>
            </div>
            {SIGNAL_FEED.map((s) => (
              <div key={s.code + s.t} className="ticker-row flex items-center gap-4 px-5 py-3.5 border-b border-white/[0.025] last:border-b-0 transition-colors">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: TONE_DOT[s.tone] }} />
                <span className="mono text-[10px] tracking-wider text-[#666] w-14 shrink-0">{s.code}</span>
                <span className="text-[13px] text-[#c8c8c8] flex-1">{s.label}</span>
                <span className="mono text-[10px] text-[#555] shrink-0">+{s.t}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PROOF CHAIN */}
      <section className="border-t border-white/[0.05] px-6 py-24">
        <div className="max-w-5xl mx-auto">
          <div className="reveal text-center mb-12">
            <p className="mono text-[10px] tracking-[0.2em] text-[#666] uppercase mb-3">PROOF CHAIN · 07 STAGES</p>
            <h2 className="display text-[28px] font-light leading-tight tracking-tight">
              From source row to outcome, with provenance at every step.
            </h2>
          </div>
          <div className="reveal grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-px bg-white/[0.04]">
            {PROOF_STAGES.map((s) => (
              <div key={s.code} className="px-4 py-6 flex flex-col items-start gap-2" style={{ background: '#0a0a0a' }}>
                <span className="mono text-[9px] text-[#666] tracking-widest">{s.code}</span>
                <span className="text-[13px] text-[#c8c8c8]">{s.label}</span>
                <span className="w-6 h-px bg-[#c9b787]/30" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* DOCTRINE */}
      <section id="doctrine" className="cream-section px-6 py-32 border-t border-white/[0.05]">
        <div className="max-w-3xl mx-auto">
          <p className="reveal mono text-[10px] tracking-[0.2em] uppercase mb-8" style={{ color: '#6b5d3e' }}>
            Doctrine · A note from the founders
          </p>
          <h2 className="reveal reveal-d1 editorial text-[40px] md:text-[52px] font-light leading-[1.08] tracking-[-0.02em] mb-10" style={{ color: '#1a1814' }}>
            The serpent that holds the spine —<br />
            <span style={{ color: '#6b5d3e' }}>activation, governed and replayable.</span>
          </h2>
          <div className="reveal rule h-px w-16 mb-10" />
          <p className="reveal reveal-d2 dropcap editorial text-[17px] leading-[1.7] mb-6" style={{ color: '#1a1814' }}>
            Amaru — the Andean Ouroboros — was built around a single conviction: that the next decade of
            data movement is not won by another connector, another mapping UI, or another reverse-ETL pipe.
            It is won by closing the loop between source and destination as a measurable, replayable system,
            and by attaching a receipt to every record that ever activated a downstream decision.
          </p>
          <p className="reveal reveal-d3 editorial text-[17px] leading-[1.7] mb-6" style={{ color: '#1a1814' }}>
            Every Amaru run produces an append-only delta log. Every record is content-addressed before it
            ever touches a destination. Every activation passes through a policy gate with a measurable
            blast radius, and every outcome feeds a Λ score that closes the loop — convergence as a
            number, not a marketing word.
          </p>
          <p className="reveal reveal-d4 editorial text-[17px] leading-[1.7]" style={{ color: '#1a1814' }}>
            We did not build a sync tool. We built a chain of custody for activation, and it runs in
            production, today.
          </p>
          <div className="mt-12 flex items-center gap-3">
            <span className="w-8 h-px" style={{ background: '#6b5d3e' }} />
            <span className="mono text-[10px] tracking-[0.2em] uppercase" style={{ color: '#6b5d3e' }}>SZL Holdings · 2026</span>
          </div>
        </div>
      </section>

      {/* OUTCOMES */}
      <section id="outcomes" className="border-t border-white/[0.05] px-6 py-28">
        <div className="max-w-5xl mx-auto">
          <div className="reveal text-center mb-14">
            <p className="mono text-[10px] tracking-[0.2em] text-[#666] uppercase mb-3">OUTCOMES · IN PRODUCTION</p>
            <h2 className="display text-[36px] font-light leading-tight tracking-tight">
              Defensible numbers, not vendor claims.
            </h2>
          </div>
          <div className="reveal grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.05]">
            {[
              { v: '968k', k: 'Records activated · 24h', sub: 'across 26 active syncs' },
              { v: '0.91', k: 'Convergence (Λ)',         sub: 'rolling, floor 0.90' },
              { v: '511ms', k: 'Avg latency',            sub: 'p50 source → destination' },
              { v: '+6.0%', k: 'Outcome lift',           sub: 'attested vs. control' },
            ].map((o) => (
              <div key={o.k} className="p-7" style={{ background: '#0a0a0a' }}>
                <p className="display text-[34px] font-light text-[#c9b787] tracking-tight">{o.v}</p>
                <p className="text-[12px] text-[#c8c8c8] mt-2">{o.k}</p>
                <p className="mono text-[9px] text-[#555] mt-2 uppercase tracking-wider">{o.sub}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PROVENANCE */}
      <section className="border-t border-white/[0.05] px-6 py-20">
        <div className="max-w-6xl mx-auto">
          <div className="reveal flex items-center justify-between mb-8 flex-wrap gap-3">
            <p className="mono text-[10px] tracking-[0.2em] text-[#666] uppercase">PROVENANCE · COVENANT KERNEL</p>
            <span className="mono text-[10px] text-[#555]">payload · 2026-05-15</span>
          </div>
          <div className="reveal grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-px bg-white/[0.04]">
            {PROVENANCE.map((p) => (
              <div key={p.k} className="px-4 py-5" style={{ background: '#0a0a0a' }}>
                <p className="mono text-[10px] text-[#666] uppercase tracking-wider">{p.k}</p>
                <p className="display text-[15px] font-light text-[#c9b787] mt-2 tracking-tight">{p.v}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-white/[0.05] px-6 py-32 text-center">
        <div className="max-w-2xl mx-auto">
          <p className="reveal mono text-[10px] tracking-[0.2em] text-[#666] uppercase mb-6">SCHEDULE</p>
          <h2 className="reveal reveal-d1 display text-[40px] font-light leading-tight tracking-tight mb-6">
            See the cockpit.
          </h2>
          <p className="reveal reveal-d2 text-[15px] text-[#888] mb-10 leading-relaxed">
            A 30-minute walkthrough with the operators who built Amaru. We will run a live sync against
            your sources and show you the receipt behind every record.
          </p>
          <div className="reveal reveal-d3 flex items-center justify-center gap-3 flex-wrap">
            <Link href="/cockpit">
              <span className="inline-flex items-center gap-2 px-6 py-3 text-[13px] font-medium rounded-md cursor-pointer bg-[#c9b787] text-[#0a0a0a] hover:bg-[#d6c69a] transition-colors">
                Open cockpit <ChevronRight className="w-4 h-4" />
              </span>
            </Link>
            <Link href="/ouroboros">
              <span className="inline-flex items-center gap-2 px-6 py-3 text-[13px] font-medium text-[#c8c8c8] border border-white/[0.08] rounded-md hover:border-[#c9b787]/30 hover:text-[#c9b787] transition-colors cursor-pointer">
                See the loop
              </span>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/[0.04] px-6 py-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2.5">
            <Database className="w-3.5 h-3.5 text-[#c9b787]/60" />
            <span className="text-[12px] text-[#888]">Amaru</span>
            <span className="mono text-[10px] text-[#555]">/ by SZL Holdings</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Layers className="w-3 h-3 text-[#c9b787]/40" />
            <span className="mono text-[10px] text-[#555] tracking-wider uppercase">A11oy-orchestrated · Replay-grade</span>
          </div>
        </div>
      </footer>

      <ContactModal
        isOpen={demoOpen}
        onClose={() => setDemoOpen(false)}
        type="demo"
        app="conduit"
        subtitle="Amaru · Convergent Multi-Source Sync"
      />
    </div>
  );
}
