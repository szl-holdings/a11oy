// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'wouter';

const BASE = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '');

function b(path: string) {
  return path === '/' ? `${BASE}/` : `${BASE}${path}`;
}

const NAV_GROUPS = [
  {
    label: 'SYSTEM',
    items: [
      { href: '/',              label: 'Home' },
      { href: '/architecture',  label: 'Architecture' },
      { href: '/applications',  label: 'Applications' },
      { href: '/solutions',     label: 'Solutions' },
      { href: '/resources',     label: 'Resources' },
      { href: '/constellation', label: 'Constellation' },
    ],
  },
  {
    label: 'NOW',
    items: [
      { href: '/now',     label: 'Now Board' },
      { href: '/command-surface', label: 'Command' },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { href: '/recommendations', label: 'Recommendations' },
      { href: '/brief',           label: 'Executive Brief' },
      { href: '/frontier',        label: 'Frontier Engine' },
      { href: '/frontier/inbox',  label: 'Frontier Inbox' },
    ],
  },
  {
    label: 'FRONTIER INTELLIGENCE',
    items: [
      { href: '/frontier-intel',       label: 'Overview' },
      { href: '/frontier/feed',        label: 'Signal Feed' },
      { href: '/frontier/mythos',      label: 'Mythos Index' },
      { href: '/frontier/proposals',   label: 'Capability Proposals' },
      { href: '/frontier/memos',       label: 'Recalibration Memos' },
      { href: '/frontier/benchmarks',  label: 'Benchmark Scoreboard' },
      { href: '/frontier/scanners',    label: 'Scanner Admin' },
      { href: '/frontier/system',      label: 'System Health' },
      { href: '/mythos-layer',         label: 'Mythos Layer' },
      { href: '/signals',              label: 'Signal Mesh + KG' },
      { href: '/mythos-spec',          label: 'Open Spec' },
    ],
  },
  {
    label: 'COMMAND FABRIC',
    items: [
      { href: '/fabric',            label: 'Fabric Cockpit' },
      { href: '/fabric/verticals',  label: 'Verticals Command' },
      { href: '/fabric/twins',      label: 'Domain Twins' },
      { href: '/fabric/signals',    label: 'Signal Mesh' },
      { href: '/fabric/risks',      label: 'Risk Matrix' },
      { href: '/fabric/decisions',  label: 'Decision Queue' },
      { href: '/fabric/outcomes',   label: 'Outcome Memory' },
      { href: '/fabric/evidence',   label: 'Evidence Ledger' },
      { href: '/fabric/roadmap',    label: 'Ecosystem Roadmap' },
    ],
  },
  {
    label: 'FABRIC LEGACY',
    items: [
      { href: '/verticals',  label: 'Verticals' },
      { href: '/signals',    label: 'Signal Mesh + KG' },
      { href: '/outcomes',   label: 'Outcomes' },
      { href: '/actions',    label: 'Action Rail' },
      { href: '/proof',      label: 'Reasoning Proof Engine' },
      { href: '/governance', label: 'Governance' },
    ],
  },
  {
    label: 'PIPELINE',
    items: [
      { href: '/pipeline',          label: 'Live Pipeline' },
      { href: '/intent-router',     label: 'Intent Router' },
      { href: '/capability-fabric', label: 'Capability Fabric' },
      { href: '/planner',           label: 'Planner Canvas' },
      { href: '/ontology',        label: 'Ontology Graph' },
      { href: '/learning',        label: 'Learning Loop' },
      { href: '/counterfactuals', label: 'Counterfactuals' },
      { href: '/adversarial',     label: 'Adversarial' },
    ],
  },
  {
    label: 'RUNTIME',
    items: [
      { href: '/agents',         label: 'Operators' },
      { href: '/workcells',      label: 'Workcells' },
      { href: '/evals',          label: 'MirrorEval + Reasoning' },
      { href: '/approval-queue', label: 'Approval Queue' },
      { href: '/cognitive-reflexivity', label: 'Cognitive Reflexivity' },
      { href: '/verifier',       label: 'Verifier Agent' },
      { href: '/memory',         label: 'Memory Vault' },
      { href: '/pce',            label: 'PCE' },
    ],
  },
  {
    label: 'AGENTIC',
    items: [
      { href: '/orchestration',      label: 'Orchestration' },
      { href: '/agent-mesh',         label: 'Agent Mesh' },
      { href: '/a2a-interop',        label: 'A2A Interop' },
      { href: '/agent-identity',     label: 'Agent Identity' },
      { href: '/model-provenance',  label: 'Model Provenance' },
      { href: '/self-optimization',  label: 'Self-Optimization' },
      { href: '/security-agents',    label: 'Security Agents' },
      { href: '/agent-viz',          label: 'Visualization' },
      { href: '/sdk',                label: 'a11oy SDK' },
      { href: '/a11oy-code',         label: 'a11oy Code' },
    ],
  },
  {
    label: 'TENAX OPS ⬡',
    items: [
      { href: '/sentra-ops', label: 'TENAX Operations' },
    ],
  },
  {
    label: 'a1.1oy',
    items: [
      { href: '/praxis',         label: 'a1.1oy Chat' },
      { href: '/mcp-hub',        label: 'MCP Hub' },
      { href: '/agentic-rag',    label: 'Agentic RAG' },
      { href: '/hub-operations', label: 'Hub Operations' },
    ],
  },
  {
    label: 'INFRASTRUCTURE',
    items: [
      { href: '/substrate-compute', label: 'Substrate Compute' },
      { href: '/flexcache',         label: 'FlexCache Runtime' },
      { href: '/control-tower',     label: 'Control Tower' },
    ],
  },
  {
    label: 'OBSERVABILITY AI',
    items: [
      { href: '/toto-forecaster',       label: 'Toto Forecaster' },
      { href: '/causal-rca',            label: 'Causal RCA' },
      { href: '/synthetic-metrics',     label: 'Synthetic Metrics' },
      { href: '/self-healing',          label: 'Self-Healing Engine' },
      { href: '/alert-triage',          label: 'Alert Triage' },
      { href: '/cost-monitoring',       label: 'Cost Monitoring' },
      { href: '/observability-as-code', label: 'Observability as Code' },
    ],
  },
  {
    label: 'PLATFORM',
    items: [
      { href: '/tools',        label: 'Tools' },
      { href: '/skills',       label: 'Skills' },
      { href: '/forge',        label: 'FORGE — Skill Marketplace' },
      { href: '/model-router', label: 'Model Router' },
      { href: '/ai-gateway',   label: 'AI Gateway' },
      { href: '/connectors',   label: 'Agent Gateway' },
      { href: '/twins',        label: 'Twin Foundry' },
      { href: '/model-foundry', label: 'Model Foundry' },
      { href: '/foundry/deepseek-v4', label: 'DeepSeek-V4 · Lead' },
      { href: '/terminal',     label: 'Terminal' },
    ],
  },
  {
    label: 'AGI',
    items: [
      { href: '/convergence', label: 'AGI Convergence' },
    ],
  },
  {
    label: 'DOCTRINE',
    items: [
      { href: '/doctrine',              label: 'Mythos Overview' },
      { href: '/payload',                label: 'Payload' },
      { href: '/atlas/org',              label: 'Atlas · Org' },
      { href: '/atlas/thesis',           label: 'Atlas · Thesis' },
      { href: '/atlas/roadmap',          label: 'Atlas · Roadmap' },
      { href: '/risk-reports',           label: 'Risk Reports' },
      { href: '/behavioral-audit',       label: 'Behavioral Audit' },
      { href: '/covenant-lift',          label: 'Covenant Lift' },
      { href: '/code-behaviors',         label: 'Code Behaviors' },
      { href: '/reward-hacking',         label: 'Reward Hacking' },
      { href: '/alignment-review',       label: 'Alignment Review' },
      { href: '/snapshot-provenance',    label: 'Snapshot Provenance' },
      { href: '/ai-user-turn',           label: 'AI-User Turn' },
      { href: '/welfare',                label: 'Agent Welfare' },
      { href: '/red-team',               label: 'Red Team' },
      { href: '/glasswing',              label: 'Glasswing Mode' },
      { href: '/capability-trajectory',  label: 'Capability Trajectory' },
    ],
  },
  {
    label: 'RESILIENCE',
    items: [
      { href: '/resilience',          label: 'DARPA Hub' },
      { href: '/gard-robustness',     label: 'GARD Robustness' },
      { href: '/formal-verification', label: 'Formal Verification' },
      { href: '/supply-chain',        label: 'Supply Chain' },
      { href: '/explainability',      label: 'Explainability' },
      { href: '/compartments',        label: 'Compartments' },
      { href: '/cyber-resilience',    label: 'Cyber Resilience' },
      { href: '/sim-governance',      label: 'Sim Governance' },
    ],
  },
  {
    label: 'GLASSWING',
    items: [
      { href: '/mythos-spec',          label: 'Open Spec' },
      { href: '/glasswing-partners',   label: 'Partners' },
      { href: '/cavd',                 label: 'CAVD' },
      { href: '/robustness-wall',      label: 'Robustness Wall' },
      { href: '/constitution-dsl',     label: 'Constitution DSL' },
      { href: '/welfare-playbooks',    label: 'Welfare Playbooks' },
      { href: '/defender-credits',     label: 'Defender Credits' },
      { href: '/transparency-report',  label: '90-Day Report' },
    ],
  },
  {
    label: 'COMPLIANCE',
    items: [
      { href: '/compass',          label: 'Compass' },
      { href: '/agent-bom',        label: 'Agent-BOM' },
      { href: '/delegation-chain', label: 'Delegation Chain' },
      { href: '/trust-exchange',   label: 'Trust Exchange' },
      { href: '/care',             label: 'CARE Engine' },
    ],
  },
  {
    label: 'TRUST',
    items: [
      { href: '/trust',                label: 'Trust Center' },
      { href: '/trust-portal',         label: 'Public Trust Portal' },
      { href: '/constitution',         label: 'Constitution' },
      { href: '/security-compliance',  label: 'Security & Compliance' },
      { href: '/right-to-audit',       label: 'Right to Audit' },
      { href: '/sovereign',     label: 'Sovereign' },
      { href: '/boardroom',     label: 'Boardroom' },
      { href: '/investor-demo', label: 'Investor Demo' },
      { href: '/about',         label: 'About' },
      { href: '/uds',           label: 'UDS' },
    ],
  },
  {
    label: 'DEFENSE',
    items: [
      { href: '/precision-ai',       label: 'Precision AI' },
      { href: '/weaponized-intel',    label: 'Weaponized Intel' },
      { href: '/agent-zero-trust',    label: 'Agent Zero Trust' },
      { href: '/atlas-shield',        label: 'ATLAS Shield' },
      { href: '/swarm-orchestrator',  label: 'Swarm Orchestrator' },
      { href: '/playbook-engine',     label: 'Playbook Engine' },
    ],
  },
  {
    label: 'OPERATIONS',
    items: [
      { href: '/chat',               label: 'A11oy Chat' },
      { href: '/karpathy-evolution', label: 'Karpathy Evolution' },
    ],
  },
  {
    label: 'ATELIER',
    items: [
      { href: '/atelier',              label: 'Browse Spaces' },
      { href: '/atelier/leaderboards', label: 'Leaderboards' },
      { href: '/atelier/my-spaces',    label: 'My Spaces' },
      { href: '/atelier/new',          label: 'Create Space' },
      { href: '/atelier/manifesto',    label: 'Manifesto' },
    ],
  },
];

const TOKENS = {
  bg: '#0a0a0a',
  bgPure: '#000000',
  surface: 'rgba(255,255,255,0.018)',
  border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.12)',
  text: '#f5f5f5',
  textDim: '#8a8a8a',
  textMuted: '#5e5e5e',
  accent: '#c9b787',
  mono: 'var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace)',
};

interface LayoutProps {
  children: ReactNode;
  fullscreen?: boolean;
}

export function Layout({ children, fullscreen = false }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [location] = useLocation();

  if (fullscreen) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: TOKENS.bg, color: TOKENS.text, display: 'flex', flexDirection: 'column' }}>
        {children}
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: TOKENS.bg, color: TOKENS.text, display: 'flex', flexDirection: 'column', fontFeatureSettings: '"ss01", "cv11"' }}>
      {/* TOP BAR — minimal, monochrome */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.25rem',
        height: 52,
        borderBottom: `1px solid ${TOKENS.border}`,
        position: 'sticky',
        top: 0,
        zIndex: 40,
        background: 'rgba(10,10,10,0.92)',
        backdropFilter: 'blur(12px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={() => setSidebarOpen(o => !o)}
            style={{
              width: 26, height: 26,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'none', border: 'none',
              color: TOKENS.textDim, cursor: 'pointer',
              fontSize: 13,
            }}
            aria-label="Toggle sidebar"
          >☰</button>
          <Link href={b('/')} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 18, height: 18,
              border: `1px solid ${TOKENS.borderStrong}`,
              borderRadius: 3,
              fontSize: 10, fontFamily: TOKENS.mono, color: TOKENS.text,
            }}>a</span>
            <span style={{ fontSize: '0.875rem', fontWeight: 500, color: TOKENS.text, letterSpacing: '-0.01em' }}>
              a11oy
            </span>
          </Link>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            fontSize: '0.6875rem', fontFamily: TOKENS.mono, color: TOKENS.textDim,
            letterSpacing: '0.04em',
          }}>
            <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: TOKENS.accent, boxShadow: `0 0 6px ${TOKENS.accent}`,
            }} />
            Fabric operational
          </div>
          <Link
            href={b('/investor-demo')}
            style={{
              padding: '0.4rem 0.875rem',
              fontSize: '0.75rem', fontWeight: 500,
              color: '#0a0a0a',
              background: TOKENS.text,
              borderRadius: 999,
              textDecoration: 'none',
              letterSpacing: '-0.005em',
            }}
          >
            Investor demo
          </Link>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {sidebarOpen && (
          <aside style={{
            width: 200,
            borderRight: `1px solid ${TOKENS.border}`,
            flexShrink: 0,
            overflowY: 'auto',
            padding: '1.5rem 0',
            background: TOKENS.bg,
            position: 'sticky',
            top: 52,
            height: 'calc(100vh - 52px)',
          }}>
            {NAV_GROUPS.map(group => (
              <div key={group.label} style={{ marginBottom: '1.5rem' }}>
                <div style={{
                  padding: '0 1.25rem',
                  marginBottom: '0.5rem',
                  fontSize: '0.625rem',
                  fontFamily: TOKENS.mono,
                  fontWeight: 500,
                  letterSpacing: '0.16em',
                  color: TOKENS.textMuted,
                }}>
                  {group.label}
                </div>
                {group.items.map(item => {
                  const fullHref = b(item.href);
                  const isActive =
                    item.href === '/'
                      ? location === fullHref || location === BASE || location === `${BASE}/`
                      : location.startsWith(fullHref);
                  return (
                    <Link
                      key={item.href}
                      href={fullHref}
                      style={{
                        display: 'block',
                        padding: '0.4rem 1.25rem',
                        fontSize: '0.8125rem',
                        textDecoration: 'none',
                        color: isActive ? TOKENS.text : TOKENS.textDim,
                        background: isActive ? 'rgba(255,255,255,0.03)' : 'transparent',
                        borderLeft: isActive ? `2px solid ${TOKENS.accent}` : '2px solid transparent',
                        fontWeight: isActive ? 500 : 400,
                        letterSpacing: '-0.005em',
                        transition: 'color 0.15s, background 0.15s',
                      }}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            ))}
          </aside>
        )}
        <main style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', minWidth: 0, background: TOKENS.bg }}>
          {children}
        </main>
      </div>
    </div>
  );
}
