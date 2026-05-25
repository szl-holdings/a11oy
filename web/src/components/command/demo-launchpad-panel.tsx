import { DEMO_SCENARIOS, type DemoScenarioKey, useDemoMode } from '../../lib/operations/demo-mode';
import { ArrowRight, Clock, Play, Sparkles, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useLocation } from 'wouter';

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
const STORAGE_KEY = 'command_demo_launchpad_dismissed';

type RouteKey = 'exec5' | 'operator15';

interface RouteOption {
  key: RouteKey;
  label: string;
  minutes: number;
  audience: string;
  description: string;
  steps: { label: string; href: string }[];
}

const ROUTES: RouteOption[] = [
  {
    key: 'exec5',
    label: '5-Minute Executive',
    minutes: 5,
    audience: 'C-suite, investors, board',
    description: 'One full governed decision cycle — signal to outcome, with proof.',
    steps: [
      { label: 'Governed Decision Loop', href: '/operations/governed-decision-loop' },
      { label: 'Policy Gate', href: '/operations/governed-decision-loop?tab=policy' },
      { label: 'Approval Chain', href: '/operations/governed-decision-loop?tab=approval' },
      { label: 'Proof Chain', href: '/operations/governed-decision-loop?tab=proof' },
      { label: 'Outcome', href: '/operations/governed-decision-loop?tab=outcome' },
    ],
  },
  {
    key: 'operator15',
    label: '15-Minute Operator',
    minutes: 15,
    audience: 'VP Ops, Chief of Staff, enterprise buyers',
    description: 'Signal triage, full nine-step loop, audit surface, cross-domain intelligence.',
    steps: [
      { label: 'Signal Feed', href: '/operations/prism' },
      { label: 'Governed Decision Loop', href: '/operations/governed-decision-loop' },
      { label: 'Approvals', href: '/operations/policy-approvals' },
      { label: 'Trust Console', href: '/operations/trust-audit' },
      { label: 'Executive Briefing', href: '/strategy/executive-briefing' },
    ],
  },
];

function isLive(): boolean {
  const override = (import.meta.env.VITE_DEPLOY_ENV as string | undefined)?.toLowerCase();
  if (override) return override === 'live';
  return import.meta.env.PROD === true;
}

export function DemoLaunchpadPanel() {
  const [, navigate] = useLocation();
  const { activate } = useDemoMode();
  const [dismissed, setDismissed] = useState(true);
  const [selectedRoute, setSelectedRoute] = useState<RouteKey>('exec5');
  const [selectedScenario, setSelectedScenario] = useState<DemoScenarioKey>('aegis');

  useEffect(() => {
    if (isLive()) return;
    const stored = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : '1';
    setDismissed(stored === '1');
  }, []);

  if (isLive() || dismissed) return null;

  const route = ROUTES.find((r) => r.key === selectedRoute) ?? ROUTES[0];

  const handleDismiss = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      /* ignore */
    }
    setDismissed(true);
  };

  const goTo = (href: string) => {
    if (href.startsWith('http')) {
      window.location.href = href;
      return;
    }
    const path = href.startsWith(BASE) ? href.slice(BASE.length) || '/' : href;
    navigate(path);
  };

  const handleStart = () => {
    activate(selectedScenario);
    goTo('/operations/governed-decision-loop');
  };

  return (
    <div
      data-testid="demo-launchpad-panel"
      className="rounded-xl overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        border: '1px solid color-mix(in srgb, #d4a054 30%, transparent)',
        padding: '20px 24px',
        position: 'relative',
      }}
    >
      <button
        type="button"
        aria-label="Dismiss demo launchpad"
        onClick={handleDismiss}
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--color-fg-muted)',
          padding: 4,
        }}
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="w-4 h-4" style={{ color: '#d4a054' }} />
        <span
          className="text-[10px] font-bold uppercase tracking-widest"
          style={{ color: '#d4a054' }}
        >
          Demo Launchpad
        </span>
      </div>
      <p className="text-xs mb-4" style={{ color: 'var(--color-fg-muted)' }}>
        One-click start for presenters. Pick a route, pick a scenario, then launch the governed
        decision loop.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {ROUTES.map((r) => {
          const isActive = r.key === selectedRoute;
          return (
            <button
              key={r.key}
              type="button"
              onClick={() => setSelectedRoute(r.key)}
              style={{
                textAlign: 'left',
                padding: '12px 14px',
                borderRadius: 10,
                background: isActive
                  ? 'color-mix(in srgb, #d4a054 12%, transparent)'
                  : 'var(--color-bg-primary)',
                border: `1px solid ${isActive ? 'color-mix(in srgb, #d4a054 40%, transparent)' : 'var(--color-surface-border)'}`,
                cursor: 'pointer',
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <Clock
                  className="w-3 h-3"
                  style={{ color: isActive ? '#d4a054' : 'var(--color-fg-muted)' }}
                />
                <span
                  className="text-xs font-bold uppercase tracking-wider"
                  style={{ color: isActive ? '#d4a054' : 'var(--color-fg-primary)' }}
                >
                  {r.label}
                </span>
              </div>
              <p className="text-[11px]" style={{ color: 'var(--color-fg-muted)' }}>
                {r.description}
              </p>
              <p className="text-[10px] mt-1 font-mono" style={{ color: 'var(--color-fg-muted)' }}>
                Audience: {r.audience}
              </p>
            </button>
          );
        })}
      </div>

      <div className="mb-4">
        <p
          className="text-[10px] font-bold uppercase tracking-widest mb-2"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          Step Navigation — {route.label}
        </p>
        <div className="flex flex-wrap gap-2">
          {route.steps.map((step, i) => (
            <button
              key={`${route.key}-${step.href}-${i}`}
              type="button"
              onClick={() => goTo(step.href)}
              className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-lg transition-opacity hover:opacity-80"
              style={{
                backgroundColor: 'var(--color-bg-primary)',
                border: '1px solid var(--color-surface-border)',
                color: 'var(--color-fg-muted)',
              }}
            >
              <span style={{ color: '#d4a054' }}>{String(i + 1).padStart(2, '0')}</span>
              {step.label}
              <ArrowRight className="w-3 h-3" />
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Scenario:
          </span>
          {DEMO_SCENARIOS.map((s) => {
            const isActive = s.key === selectedScenario;
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => setSelectedScenario(s.key)}
                className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-lg"
                style={{
                  backgroundColor: isActive
                    ? `color-mix(in srgb, ${s.color} 15%, transparent)`
                    : 'var(--color-bg-primary)',
                  border: `1px solid ${isActive ? s.color : 'var(--color-surface-border)'}`,
                  color: isActive ? s.color : 'var(--color-fg-muted)',
                  cursor: 'pointer',
                }}
              >
                <span aria-hidden>{s.icon}</span>
                {s.name}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={handleStart}
          data-testid="demo-launchpad-start"
          className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider px-4 py-2 rounded-lg transition-opacity hover:opacity-90"
          style={{
            backgroundColor: '#d4a054',
            color: '#1a1410',
            border: '1px solid #d4a054',
            cursor: 'pointer',
          }}
        >
          <Play className="w-3.5 h-3.5" />
          Start Demo
        </button>
      </div>
    </div>
  );
}

export default DemoLaunchpadPanel;
