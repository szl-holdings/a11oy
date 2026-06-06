// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { copyrightLine } from '@szl-holdings/brand-registry';
import { ContactModal } from '@szl-holdings/shared-ui/contact-modal';
import { NewsletterSubscribe } from '@szl-holdings/shared-ui/newsletter-subscribe';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Brain,
  ChevronRight,
  Cpu,
  Eye,
  FileSearch,
  Layers,
  Lock,
  Menu,
  Radio,
  Server,
  Shield,
  Target,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'wouter';
import { AEGIS_MITRE_COVERAGE, metricDisplay } from '../lib/claims';

const BG = '#0b0d12';

const workspaces = [
  {
    id: 'defense',
    name: 'Defense',
    subtitle: 'Security Operations',
    color: '#c9b787',
    icon: Shield,
    href: '/soc',
    capabilities: [
      'SOC command with unified XDR correlation',
      `${metricDisplay(AEGIS_MITRE_COVERAGE)} — adversary emulation included`,
      'Threat hunting, forensics, identity threat detection',
      'Vulnerability management and hardening controls',
      'Compliance readiness across frameworks',
      'Adaptive Defense Shield — perimeter defense',
    ],
  },
  {
    id: 'command',
    name: 'Command',
    subtitle: 'Managed Operations',
    color: '#8a8a8a',
    icon: Server,
    href: '/ops/dashboard',
    capabilities: [
      'NOC operations and RMM console',
      'Client account management and SLA tracking',
      'Ticket queue, dispatch, and technician workflow',
      'Revenue analytics and MRR dashboards',
      'Service desk and escalation management',
      'Device lifecycle and patch orchestration',
    ],
  },
  {
    id: 'labs',
    name: 'Labs',
    subtitle: 'Intelligence Engine',
    color: '#5e5e5e',
    icon: Brain,
    href: '/intel/dashboard',
    capabilities: [
      'Agent Console — agent orchestration',
      'Neural explorer and model registry',
      'Experiment tracking and evaluation',
      'Signal Router — intelligence routing',
      'Prediction models with confidence scoring',
      'Research-to-action pipeline',
    ],
  },
  {
    id: 'legal',
    name: 'Legal',
    subtitle: 'Matter Intelligence',
    color: '#c9b787',
    icon: FileSearch,
    href: '/legal',
    capabilities: [
      'Matter health dashboard with PRISM observability pillars',
      'Deadline risk queue and calendar intelligence',
      'Settlement predictor with low/mid/high range modeling',
      'Privilege engine and attorney-client log',
      'AI recommendations and exposure tracking',
      'Compliance deadline management across jurisdictions',
    ],
  },
];

const convergences = [
  {
    from: 'Defense',
    to: 'Command',
    toHref: '/ops/dashboard',
    icon: AlertTriangle,
    desc: 'Incident INC-2847 impacts managed client Northgate. Lateral movement on DC-PROD-03 triggers automatic SLA escalation, client notification, and containment protocol — before the client knows.',
    color: '#c9b787',
    toColor: '#8a8a8a',
  },
  {
    from: 'Labs',
    to: 'Defense',
    toHref: '/soc',
    icon: Brain,
    desc: 'Neural explorer detects anomalous pattern matching APT29 TTPs. Intelligence model confidence: 94%. MITRE mapping and hunting queries generated automatically. Defense SOC receives enriched alert in < 60 seconds.',
    color: '#5e5e5e',
    toColor: '#c9b787',
  },
  {
    from: 'Command',
    to: 'Labs',
    toHref: '/intel/dashboard',
    icon: Radio,
    desc: 'Service desk ticket volume anomaly across 3 managed clients. Labs ingests the signal, generates churn risk model, and surfaces preventive actions to Command — within the same operating session.',
    color: '#8a8a8a',
    toColor: '#5e5e5e',
  },
  {
    from: 'Defense',
    to: 'Legal',
    toHref: '/legal',
    icon: AlertTriangle,
    desc: 'Ransomware containment on client Harfield Group triggers automatic legal intake. Matter opened, breach notification deadlines calculated across 7 jurisdictions, and privilege log initiated — all within the incident response window.',
    color: '#c9b787',
    toColor: '#c9b787',
  },
  {
    from: 'Legal',
    to: 'Command',
    toHref: '/ops/dashboard',
    icon: FileSearch,
    desc: 'Regulatory filing deadline for client Meridian Capital is 11 days out. Legal surfaces the hard constraint to Command, which auto-adjusts SLA priorities, reassigns support bandwidth, and flags any at-risk delivery commitments.',
    color: '#c9b787',
    toColor: '#8a8a8a',
  },
  {
    from: 'Labs',
    to: 'Legal',
    icon: Brain,
    desc: 'Contract risk model flags non-standard indemnification language in a managed client agreement with Vantage Partners — liability exposure estimated $2.4M above policy limits. Labs routes the signal to Legal automatically: matter opened, partner attorney assigned, and negotiation brief generated before the contract execution date.',
    color: '#5e5e5e',
    toColor: '#c9b787',
  },
];

const operatingModel = [
  {
    phase: 'OBSERVE',
    desc: 'Ingest telemetry, logs, alerts, and signals from every connected surface — endpoints, networks, cloud, tickets, models.',
    icon: Eye,
    color: 'rgba(255,255,255,0.15)',
  },
  {
    phase: 'UNDERSTAND',
    desc: 'Correlate signals across modules. A threat in Defense becomes a service risk in Command. A model output in Labs becomes a detection rule.',
    icon: FileSearch,
    color: 'rgba(255,255,255,0.15)',
  },
  {
    phase: 'DECIDE',
    desc: 'Surface prioritized recommendations with evidence, confidence, and business impact. Every decision carries an audit trail.',
    icon: Target,
    color: 'rgba(255,255,255,0.15)',
  },
  {
    phase: 'EXECUTE',
    desc: 'Route actions to the right person or automation. Contain, remediate, escalate, or approve — with full context and accountability.',
    icon: Activity,
    color: 'rgba(255,255,255,0.15)',
  },
];

function useInView(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

function Reveal({
  children,
  className = '',
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const { ref, visible } = useInView();
  return (
    <div
      ref={ref}
      className={`transition-all duration-1000 ease-out ${visible ? 'translate-y-0' : 'translate-y-8'} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

export default function AegisHomePage() {
  const [mobileNav, setMobileNav] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeWs, setActiveWs] = useState(0);
  const [demoOpen, setDemoOpen] = useState(false);

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', h, { passive: true });
    return () => window.removeEventListener('scroll', h);
  }, []);

  return (
    <div
      className="min-h-screen text-slate-300 overflow-x-hidden"
      style={{ background: BG, fontFamily: "'Inter', system-ui, sans-serif" }}
    >
      <nav
        className={`fixed top-0 left-0 right-0 z-50 h-14 flex items-center transition-all duration-500 ${scrolled ? 'bg-[#0b0d12]/90 backdrop-blur-2xl border-b border-white/[0.04]' : 'bg-transparent'}`}
      >
        <div className="max-w-[1200px] mx-auto px-6 w-full flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{
                background: 'rgba(245,245,245,0.08)',
                border: '1px solid rgba(245,245,245,0.15)',
              }}
            >
              <Shield size={13} className="text-[#c9b787]" />
            </div>
            <span className="font-bold text-[15px] tracking-tight text-white">PARAGON</span>
            <span aria-hidden="true" className="hidden sm:inline text-[9px] tracking-[0.15em] uppercase text-white/60 font-mono ml-1">
              Defense & Intelligence
            </span>
          </div>
          <div className="hidden md:flex items-center gap-7">
            {[
              { label: 'Architecture', href: '#architecture' },
              { label: 'Convergence', href: '#convergence' },
              { label: 'Operating Model', href: '#model' },
            ].map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-[11px] text-white/65 hover:text-white/60 transition-colors tracking-[0.08em] uppercase font-medium"
              >
                {l.label}
              </a>
            ))}
            <Link href="/soc?demo=true">
              <span className="text-[12px] font-semibold text-white bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.08] rounded-lg px-5 py-1.5 transition-all cursor-pointer">
                Enter Platform
              </span>
            </Link>
          </div>
          <button
            className="md:hidden p-2 text-white/70"
            onClick={() => setMobileNav(!mobileNav)}
            aria-label={mobileNav ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileNav}
          >
            {mobileNav ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      {mobileNav && (
        <div className="fixed inset-0 z-40 bg-[#0b0d12]/98 backdrop-blur-xl flex flex-col items-center justify-center gap-8 md:hidden">
          {[
            { label: 'Architecture', href: '#architecture' },
            { label: 'Convergence', href: '#convergence' },
            { label: 'Operating Model', href: '#model' },
          ].map((l) => (
            <a
              key={l.label}
              href={l.href}
              onClick={() => setMobileNav(false)}
              className="text-lg text-white/50 hover:text-white tracking-wide transition-colors"
            >
              {l.label}
            </a>
          ))}
          <Link href="/soc?demo=true">
            <span
              className="mt-4 text-sm font-semibold text-white bg-white/[0.08] rounded-lg px-8 py-3 cursor-pointer"
              onClick={() => setMobileNav(false)}
            >
              Enter Platform
            </span>
          </Link>
        </div>
      )}

      <div className="absolute top-0 left-0 right-0 h-[800px] overflow-hidden pointer-events-none">
        <div
          className="absolute top-[100px] left-[20%] w-[600px] h-[400px] rounded-full"
          style={{
            background: 'radial-gradient(ellipse, rgba(245,245,245,0.03) 0%, transparent 70%)',
          }}
        />
        <div
          className="absolute top-[200px] right-[15%] w-[500px] h-[400px] rounded-full"
          style={{
            background: 'radial-gradient(ellipse, rgba(138,138,138,0.02) 0%, transparent 70%)',
          }}
        />
      </div>

      <section className="relative pt-32 sm:pt-40 pb-20 sm:pb-28 max-w-[1200px] mx-auto px-6">
        <Reveal>
          <p aria-hidden="true" className="text-[10px] font-semibold tracking-[0.2em] uppercase text-white/60 mb-8 font-mono">
            PARAGON &middot; Unified Defense & Intelligence
          </p>
        </Reveal>

        <Reveal delay={100}>
          <h1 className="text-[clamp(2.5rem,6vw,4.5rem)] font-extrabold leading-[1.04] tracking-[-0.03em] text-white max-w-[900px]">
            Four workspaces.
          </h1>
        </Reveal>
        <Reveal delay={200}>
          <h1 className="text-[clamp(2.5rem,6vw,4.5rem)] font-extrabold leading-[1.04] tracking-[-0.03em] max-w-[900px] mb-8">
            <span className="text-white/70">One shared intelligence layer.</span>
          </h1>
        </Reveal>

        <Reveal delay={300}>
          <p className="text-[17px] sm:text-[19px] leading-[1.75] text-white/65 max-w-[640px] mb-12">
            PARAGON unifies security operations, managed services, and AI-driven intelligence into a
            single console. Defense detects. Legal protects. Command operates. Labs reasons. All
            four share one data context, one correlation engine, one operating model.
          </p>
        </Reveal>

        <Reveal delay={400}>
          <div className="flex flex-wrap gap-3 mb-20">
            <Link href="/soc?demo=true">
              <span className="text-[13px] font-semibold bg-white/[0.07] hover:bg-white/[0.12] text-white border border-white/[0.08] rounded-lg px-7 py-3 flex items-center gap-2 transition-all cursor-pointer">
                Enter SOC Command <ArrowRight size={14} />
              </span>
            </Link>
            <button
              onClick={() => setDemoOpen(true)}
              className="text-[13px] font-medium text-white/60 hover:text-white border border-white/[0.06] hover:border-white/[0.20] rounded-lg px-7 py-3 transition-all"
            >
              Request a Demo
            </button>
          </div>
        </Reveal>

        <Reveal delay={500}>
          <div
            className="grid grid-cols-2 sm:grid-cols-4 gap-px rounded-xl overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            {[
              { value: '< 4 min', label: 'Mean time to detect' },
              { value: '99.1%', label: 'Managed device uptime' },
              { value: '94%', label: 'AI model confidence' },
              { value: '12.8K', label: 'Endpoints managed' },
            ].map((s) => (
              <div key={s.label} className="bg-[#0b0d12] py-5 px-5">
                <span className="text-[22px] font-extrabold font-mono text-white block">
                  {s.value}
                </span>
                <span aria-hidden="true" className="text-[10px] tracking-[0.08em] uppercase text-white/65 mt-1 block">
                  {s.label}
                </span>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <Reveal>
        <section id="architecture" className="relative py-24 sm:py-32 px-6">
          <div className="max-w-[1200px] mx-auto">
            <div className="max-w-[600px] mb-16">
              <p aria-hidden="true" className="text-[10px] font-semibold tracking-[0.2em] uppercase text-white/60 mb-4">
                Architecture
              </p>
              <h2 className="text-[clamp(1.5rem,3.5vw,2.5rem)] font-bold leading-[1.15] tracking-tight text-white mb-4">
                One platform. Four operating surfaces.
              </h2>
              <p className="text-[16px] leading-[1.8] text-white/65">
                Each workspace is a full operating environment for its domain. Together, they share
                a unified data context — a threat in Defense informs a service risk in Command, and
                a Labs model improves detection in real time.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-6">
              <div className="flex lg:flex-col gap-1">
                {workspaces.map((ws, i) => (
                  <button
                    key={ws.id}
                    onClick={() => setActiveWs(i)}
                    className="flex items-center gap-2.5 px-4 py-3 rounded-xl text-left transition-all w-full"
                    style={{
                      background: activeWs === i ? `${ws.color}08` : 'transparent',
                      border: `1px solid ${activeWs === i ? `${ws.color}20` : 'transparent'}`,
                    }}
                  >
                    <ws.icon
                      size={16}
                      style={{ color: activeWs === i ? ws.color : 'rgba(255,255,255,0.15)' }}
                    />
                    <div>
                      <span
                        className={`text-[13px] font-semibold block ${activeWs === i ? 'text-white' : 'text-white/70'}`}
                      >
                        {ws.name}
                      </span>
                      <span aria-hidden="true" className="text-[10px] text-white/60">{ws.subtitle}</span>
                    </div>
                  </button>
                ))}
              </div>

              <div
                className="border border-white/[0.05] rounded-2xl p-8 sm:p-10 transition-all"
                style={{ background: `${workspaces[activeWs].color}03` }}
              >
                <div className="flex items-center gap-3 mb-2">
                  {(() => {
                    const Icon = workspaces[activeWs].icon;
                    return <Icon size={22} style={{ color: workspaces[activeWs].color }} />;
                  })()}
                  <h3 className="text-[22px] font-bold text-white">{workspaces[activeWs].name}</h3>
                </div>
                <p
                  className="text-[12px] font-semibold tracking-[0.12em] uppercase mb-8"
                  style={{ color: workspaces[activeWs].color }}
                >
                  {workspaces[activeWs].subtitle}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {workspaces[activeWs].capabilities.map((cap) => (
                    <div key={cap} className="flex items-start gap-2.5 py-2">
                      <div
                        className="w-1 h-1 rounded-full mt-[7px] shrink-0"
                        style={{ background: workspaces[activeWs].color, opacity: 0.4 }}
                      />
                      <span className="text-[13px] leading-relaxed text-white/70">{cap}</span>
                    </div>
                  ))}
                </div>

                <Link href={workspaces[activeWs].href}>
                  <span
                    className="mt-8 inline-flex items-center gap-2 text-[12px] font-semibold rounded-lg px-5 py-2.5 cursor-pointer transition-all"
                    style={{
                      background: `${workspaces[activeWs].color}10`,
                      color: workspaces[activeWs].color,
                      border: `1px solid ${workspaces[activeWs].color}20`,
                    }}
                  >
                    Enter {workspaces[activeWs].name} <ArrowRight size={12} />
                  </span>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section id="convergence" className="relative py-24 sm:py-32 px-6">
          <div className="max-w-[900px] mx-auto">
            <p aria-hidden="true" className="text-[10px] font-semibold tracking-[0.2em] uppercase text-white/60 mb-4">
              Convergence
            </p>
            <h2 className="text-[clamp(1.5rem,3.5vw,2.5rem)] font-bold leading-[1.15] tracking-tight text-white mb-4">
              Cross-module intelligence in action
            </h2>
            <p className="text-[16px] leading-[1.8] text-white/65 mb-16 max-w-[560px]">
              The real power of PARAGON is convergence. When Defense, Legal, Command, and Labs share
              one data layer, correlations emerge that siloed tools miss entirely.
            </p>

            <div className="flex flex-col gap-4">
              {convergences.map((c, i) => (
                <Link key={i} href={c.toHref}>
                  <div
                    className="group border border-white/[0.05] rounded-2xl p-7 sm:p-8 transition-all hover:border-white/[0.12] hover:bg-white/[0.02] cursor-pointer"
                  >
                    <div className="flex items-center gap-3 mb-5">
                      <span
                        className="text-[11px] font-bold px-3 py-1 rounded-lg"
                        style={{ background: `${c.color}10`, color: "rgba(255,255,255,0.9)" }}
                      >
                        {c.from}
                      </span>
                      <div className="flex items-center gap-1">
                        <div
                          className="w-8 h-px"
                          style={{
                            background: `linear-gradient(90deg, ${c.color}40, ${c.toColor}40)`,
                          }}
                        />
                        <ChevronRight aria-hidden="true" size={10} className="text-white/60" />
                      </div>
                      <span
                        className="text-[11px] font-bold px-3 py-1 rounded-lg"
                        style={{ background: `${c.toColor}10`, color: "rgba(255,255,255,0.9)" }}
                      >
                        {c.to}
                      </span>
                      <ArrowRight
                        size={13}
                        className="ml-auto text-white/20 group-hover:text-white/50 transition-colors shrink-0"
                        aria-hidden="true"
                      />
                    </div>
                    <p className="text-[14px] leading-[1.85] text-white/65">{c.desc}</p>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section id="model" className="relative py-24 sm:py-32 px-6">
          <div className="max-w-[1200px] mx-auto">
            <div className="max-w-[560px] mb-16">
              <p aria-hidden="true" className="text-[10px] font-semibold tracking-[0.2em] uppercase text-white/60 mb-4">
                Operating Model
              </p>
              <h2 className="text-[clamp(1.5rem,3.5vw,2.5rem)] font-bold leading-[1.15] tracking-tight text-white mb-4">
                Observe. Understand. Decide. Execute.
              </h2>
              <p className="text-[16px] leading-[1.8] text-white/65">
                The same decision framework whether you're triaging a breach, managing an SLA, or
                validating a model. One loop. Every domain.
              </p>
            </div>

            <div
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px rounded-2xl overflow-hidden"
              style={{ background: 'rgba(255,255,255,0.04)' }}
            >
              {operatingModel.map((step, i) => (
                <div key={step.phase} className="bg-[#0b0d12] p-8">
                  <div className="flex items-center gap-3 mb-5">
                    <span aria-hidden="true" className="text-[36px] font-extrabold text-white/[0.55] font-mono leading-none">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                  </div>
                  <step.icon size={20} className="text-white/60 mb-4" />
                  <h3 className="text-[13px] font-bold text-white uppercase tracking-[0.1em] mb-3">
                    {step.phase}
                  </h3>
                  <p className="text-[12px] leading-[1.85] text-white/65">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="relative py-24 sm:py-32 px-6">
          <div className="max-w-[1200px] mx-auto">
            <p aria-hidden="true" className="text-[10px] font-semibold tracking-[0.2em] uppercase text-white/60 mb-6">
              Why One Platform
            </p>
            <div
              className="grid grid-cols-1 sm:grid-cols-2 gap-px rounded-2xl overflow-hidden"
              style={{ background: 'rgba(255,255,255,0.04)' }}
            >
              {[
                {
                  icon: Lock,
                  title: 'One security context',
                  desc: 'Shared authentication, shared RBAC, shared audit trails. No credential sprawl. No integration tax. One identity model across Defense, Command, and Labs.',
                },
                {
                  icon: Layers,
                  title: 'One data layer',
                  desc: 'Incidents, endpoints, tickets, models, and intelligence all live in one database. Cross-module queries are native — not piped through APIs.',
                },
                {
                  icon: Cpu,
                  title: 'One correlation engine',
                  desc: 'Every signal — threat, service event, model output — passes through the same engine. Patterns that span modules surface automatically.',
                },
                {
                  icon: Eye,
                  title: 'One operating model',
                  desc: "OBSERVE \u2192 UNDERSTAND \u2192 DECIDE \u2192 EXECUTE. The same decision framework applies whether you're triaging a breach or validating a model.",
                },
              ].map((item) => (
                <div key={item.title} className="bg-[#0b0d12] p-8">
                  <item.icon size={20} className="text-white/60 mb-5" />
                  <h3 className="text-[14px] font-bold text-white mb-3">{item.title}</h3>
                  <p className="text-[12px] leading-[1.85] text-white/65">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </Reveal>

      {/* PRODUCT TOUR */}
      <Reveal>
        <section className="py-24 sm:py-32 px-6 max-w-[1140px] mx-auto">
          <div className="text-center mb-16">
            <p className="text-[10px] font-mono tracking-[0.3em] uppercase mb-3 text-[#c9b787]">
              Platform Walkthrough
            </p>
            <h2 className="text-[clamp(1.6rem,3vw,2.1rem)] font-bold text-white mb-3 tracking-tight">
              How PARAGON works in practice
            </h2>
            <p className="text-[14px] max-w-xl mx-auto text-white/65">
              From deployment to full command in under an hour. Four workspaces, one unified
              console.
            </p>
          </div>
          <div className="relative">
            <div className="hidden md:block absolute left-[39px] top-0 bottom-0 w-px bg-white/[0.03]" />
            <div className="space-y-10">
              {[
                {
                  step: '01',
                  title: 'Provision your workspace',
                  body: 'Choose your deployment model — cloud, on-premises, or air-gapped. Ingest your first data sources: endpoint telemetry, network flows, identity events. PARAGON normalizes everything into a unified event schema.',
                  tag: 'Setup',
                },
                {
                  step: '02',
                  title: 'SOC command activates immediately',
                  body: 'The SOC dashboard surfaces your threat landscape within minutes of ingestion: active alerts, open incidents, MITRE ATT&CK coverage gaps, and CVE exposure. No tuning period. No custom rules required to get started.',
                  tag: 'Detection',
                },
                {
                  step: '03',
                  title: 'Incidents route with full context',
                  body: 'Every incident carries a full evidence chain — correlated events, affected assets, MITRE technique mapping, and recommended response. Analysts see what happened, how, and what to do next.',
                  tag: 'Response',
                },
                {
                  step: '04',
                  title: 'Compliance readiness runs continuously',
                  body: 'Framework scorecards track your posture against NIST, SOC 2, ISO 27001, and others in real-time. Every control maps to your actual configuration — not a point-in-time assessment.',
                  tag: 'Compliance',
                },
                {
                  step: '05',
                  title: 'Intelligence layer compounds over time',
                  body: "Sentinel's reasoning engine learns your environment. Anomaly baselines improve. False positive rates drop. Each week, the command surface gets more precise — without manual tuning.",
                  tag: 'Intelligence',
                },
              ].map((item) => (
                <div key={item.step} className="flex items-start gap-8 md:gap-10">
                  <div className="flex-shrink-0 w-20 text-right">
                    <div className="inline-flex items-center justify-center w-10 h-10 rounded-full text-[11px] font-bold bg-[#c9b787]/10 text-[#c9b787] border border-[#c9b787]/20">
                      {item.step}
                    </div>
                  </div>
                  <div className="flex-1 pb-10 border-b border-white/[0.03]">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-[16px] font-semibold text-white">{item.title}</h3>
                      <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-[#c9b787]/8 text-[#c9b787] border border-[#c9b787]/10">
                        {item.tag}
                      </span>
                    </div>
                    <p className="text-[13.5px] leading-relaxed text-white/65">{item.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section className="relative py-24 sm:py-32 px-6">
          <div className="max-w-[640px] mx-auto text-center">
            <h2 className="text-[clamp(1.5rem,3.5vw,2.25rem)] font-bold text-white mb-4 tracking-tight">
              Total command. Zero compromise.
            </h2>
            <p className="text-[16px] text-white/65 mb-10">
              See what unified defense, operations, and intelligence looks like in one console.
            </p>
            <div className="flex justify-center flex-wrap gap-3">
              <Link href="/soc?demo=true">
                <span className="text-[14px] font-semibold bg-white/[0.07] hover:bg-white/[0.12] text-white border border-white/[0.08] rounded-lg px-8 py-3.5 flex items-center gap-2 transition-all cursor-pointer">
                  Enter SOC Command <ArrowRight size={15} />
                </span>
              </Link>
              <button
                onClick={() => setDemoOpen(true)}
                className="text-[14px] font-medium text-white/65 border border-white/[0.06] hover:border-white/[0.12] rounded-lg px-8 py-3.5 transition-all"
              >
                Schedule a Demo
              </button>
            </div>
          </div>
        </section>
      </Reveal>

      {/* Machine Identity + Hybrid Audit Chain attestation surface (G10) */}
      <section style={{ padding: '64px 24px', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          <p style={{ fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.25em', color: '#5e5e5e', marginBottom: 12, textTransform: 'uppercase' as const }}>
            Trust Substrate
          </p>
          <p style={{ fontSize: 20, fontWeight: 600, color: '#f5f5f5', marginBottom: 8 }}>
            Machine identity. Cryptographic proof.
          </p>
          <p style={{ fontSize: 13, color: '#8a8a8a', lineHeight: 1.8, maxWidth: 600, marginBottom: 28 }}>
            Every AI decision and agent action in PARAGON is written to a tamper-evident hybrid-signed audit chain. Each entry carries an Ed25519 + ML-DSA-65 dual signature bound to a platform DID, verified against a key-custody registry on every read.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            {[
              { label: 'Signing Scheme', value: 'Ed25519 + ML-DSA-65', note: 'NIST PQC Level 3', color: '#c9b787' },
              { label: 'Identity Anchor', value: 'did:plat:*', note: 'Platform DID registry', color: '#8b7ac8' },
              { label: 'Key Custody', value: 'Software-encrypted', note: 'HSM-ready interface', color: '#8a8a8a' },
              { label: 'Rollout Mode', value: 'Warn → Enforce', note: 'Zero-disruption rollout', color: '#5e5e5e' },
            ].map((item) => (
              <div key={item.label} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 10, padding: '14px 16px' }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase' as const, letterSpacing: '0.5px', marginBottom: 6 }}>
                  {item.label}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: item.color, fontFamily: 'monospace', marginBottom: 3 }}>
                  {item.value}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>{item.note}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, fontSize: 11, color: 'rgba(255,255,255,0.25)', fontFamily: 'monospace' }}>
            <Lock size={11} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
            Audit entries are classified: hybrid_verified · legacy_unsigned · broken — tamper detection at the row level.
          </div>
        </div>
      </section>

      <section style={{ padding: '80px 24px', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <div style={{ maxWidth: 640, margin: '0 auto', textAlign: 'center' }}>
          <p style={{ fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.25em', color: '#5e5e5e', marginBottom: 20, textTransform: 'uppercase' as const }}>
            Orchestrated by a11oy
          </p>
          <p style={{ fontSize: 22, fontWeight: 600, color: '#f5f5f5', marginBottom: 14 }}>
            Orchestrated by <span style={{ color: '#c9b787' }}>a11oy</span>
          </p>
          <p style={{ fontSize: 13, color: '#8a8a8a', lineHeight: 1.8, maxWidth: 520, margin: '0 auto' }}>
            Every decision in PARAGON follows the same governed path — Signal, Context, Recommendation, Simulation, Policy, Execution, Proof, Outcome. The same proof chain. The same attribution. The same governance.
          </p>
        </div>
      </section>

      <section className="py-16 px-6 border-t border-white/[0.04]">
        <div className="max-w-[560px] mx-auto">
          <NewsletterSubscribe
            utmSource="aegis"
            variant="banner"
            heading="Intelligence from the front line"
            subheading="Essays on governed AI, defense operations, and the decision infrastructure behind PARAGON — delivered weekly."
          />
        </div>
      </section>

      <section className="px-6 py-10 max-w-[1200px] mx-auto">
        <a
          href="/conduit/"
          className="block bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 hover:border-[#c9b787]/40 transition-colors"
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/40">Activation Fabric</div>
              <div className="text-white font-medium mt-1">Activated by Amaru — Andean Ouroboros</div>
              <div className="text-xs text-white/50 mt-1">PARAGON's adversary intelligence and identity signals are activated by Amaru's 8-agent governance coalition.</div>
            </div>
            <span className="text-[#c9b787] text-sm font-mono">Open Amaru →</span>
          </div>
        </a>
      </section>

      <footer className="border-t border-white/[0.04] py-12 px-6 max-w-[1200px] mx-auto">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Shield size={12} className="text-white/60" />
            <span className="text-[12px] font-semibold text-white/85">PARAGON</span>
            <span aria-hidden="true" className="text-[10px] text-white/60 font-mono">by a11oy</span>
          </div>
          <p className="text-[10px] text-white/60">{copyrightLine()}</p>
        </div>
      </footer>

      <ContactModal
        isOpen={demoOpen}
        onClose={() => setDemoOpen(false)}
        type="demo"
        app="aegis"
        subtitle="PARAGON — Unified Defense & Intelligence Command"
      />
    </div>
  );
}
