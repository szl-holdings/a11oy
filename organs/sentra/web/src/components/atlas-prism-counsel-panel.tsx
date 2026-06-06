import {
  Activity,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  GitBranch,
  Lock,
  RefreshCw,
  Scale,
} from 'lucide-react';
import { useState } from 'react';

const BG = { surface: '#0a0d14', card: '#0f131e', inset: '#080b11' };
const BORDER = { muted: 'rgba(255,255,255,0.07)' };
const TEXT = {
  primary: 'rgba(255,255,255,0.88)',
  secondary: 'rgba(255,255,255,0.55)',
  tertiary: 'rgba(255,255,255,0.28)',
};
const ACCENT = {
  purple: '#8b7ac8',
  amber: '#c8953c',
  green: '#6b8f71',
  red: '#c45a4a',
  blue: '#4a90b8',
};

const PRISM_DEMO_SCENE = {
  sceneId: 'prism-matter-pressure-demo',
  domain: 'general',
  entityType: 'matter',
  entityId: 'MTR-2026-0891',
  driftScore: 0.55,
  state: {
    matterId: 'MTR-2026-0891',
    matterTitle: 'Holloway v. Meridian Capital Group',
    matterType: 'commercial_dispute',
    totalExposureUsd: 8400000,
    discoveryStatus: 'ongoing',
    keyDeadlineDays: 34,
    settlementOfferUsd: 3200000,
    clientPressureScore: 78,
  },
  branches: [
    {
      branchId: 'prism-settlement-path',
      branchLabel: 'Accelerated Settlement Path',
      hypothesis:
        'Accept modified settlement at $4.2M to avoid prolonged discovery and trial risk.',
      deltaState: {
        settlementTargetUsd: 4200000,
        discoveryTerminated: true,
        estimatedTrialRisk: 'avoided',
        netSavingsVsTrial: 2800000,
      },
      outcomeProjections: [
        {
          label: 'Settlement accepted at $4.2M',
          probability: 0.71,
          impact: 'medium — avoids $8.4M trial exposure',
          metrics: { settlementUsd: 4200000, totalCostUsd: 4200000, trialRiskAvoided: true },
        },
        {
          label: 'Counterparty rejects, trial proceeds',
          probability: 0.29,
          impact: 'high — full trial, outcome uncertain',
          metrics: { settlementUsd: 0, totalCostUsd: 8400000, trialRiskAvoided: false },
        },
      ],
    },
    {
      branchId: 'prism-discovery-completion',
      branchLabel: 'Complete Discovery Then Negotiate',
      hypothesis:
        'Complete discovery in 34 days, strengthen position, then counter-propose at $3.8M.',
      deltaState: {
        settlementTargetUsd: 3800000,
        discoveryCompleted: true,
        negotiationLeverageScore: 0.72,
        additionalCostUsd: 280000,
      },
      outcomeProjections: [
        {
          label: 'Improved position, settle at $3.8M',
          probability: 0.52,
          impact: 'medium — saves $400K vs. current offer',
          metrics: { settlementUsd: 3800000, totalCostUsd: 4080000, trialRiskAvoided: true },
        },
        {
          label: 'Counterparty hardens, trial proceeds',
          probability: 0.48,
          impact: 'high — full trial exposure remains',
          metrics: { settlementUsd: 0, totalCostUsd: 8680000, trialRiskAvoided: false },
        },
      ],
    },
  ],
  resolutionRecommendations: [
    {
      title: 'Accept $4.2M settlement within 5 business days',
      priority: 'critical',
      rationale: 'Client pressure score 78/100 and 34-day deadline create settlement urgency.',
    },
    {
      title: 'Demand privilege log from opposing counsel',
      priority: 'high',
      rationale: '14 documents flagged for privilege review — potential smoking gun protection.',
    },
    {
      title: 'Prepare emergency motion for continuance',
      priority: 'high',
      rationale: 'Contingency if settlement collapses: buys 60-90 days at nominal cost.',
    },
  ],
};

function DriftBar({ score }: { score: number }) {
  const color = score >= 0.75 ? ACCENT.red : score >= 0.5 ? ACCENT.amber : ACCENT.green;
  const label =
    score >= 0.75 ? 'Critical Pressure' : score >= 0.5 ? 'Elevated Pressure' : 'Nominal';
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span
          className="text-[9px] font-mono uppercase tracking-widest"
          style={{ color: TEXT.tertiary }}
        >
          Pressure Drift
        </span>
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color }}>
            {label}
          </span>
          <span className="text-sm font-bold font-mono tabular-nums" style={{ color }}>
            {score.toFixed(2)}
          </span>
        </div>
      </div>
      <div
        className="h-1.5 rounded-full overflow-hidden"
        style={{ background: 'rgba(255,255,255,0.06)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${score * 100}%`,
            background: `linear-gradient(90deg, ${color}99, ${color})`,
          }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[8px] font-mono" style={{ color: TEXT.tertiary }}>
          0.00 baseline
        </span>
        <span className="text-[8px] font-mono" style={{ color: TEXT.tertiary }}>
          1.00 max
        </span>
      </div>
    </div>
  );
}

function BranchCard({
  branch,
  defaultOpen = false,
}: {
  branch: (typeof PRISM_DEMO_SCENE.branches)[0];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className="rounded-lg overflow-hidden border"
      style={{ borderColor: BORDER.muted, background: BG.inset }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-2.5 px-3 py-2.5 hover:bg-white/[0.02] transition-colors text-left"
      >
        <GitBranch className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color: ACCENT.purple }} />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold leading-snug" style={{ color: TEXT.primary }}>
            {branch.branchLabel}
          </p>
          <p className="text-[10px] mt-0.5 line-clamp-2" style={{ color: TEXT.secondary }}>
            {branch.hypothesis}
          </p>
        </div>
        {open ? (
          <ChevronDown className="w-3 h-3 shrink-0 mt-0.5" style={{ color: TEXT.tertiary }} />
        ) : (
          <ChevronRight className="w-3 h-3 shrink-0 mt-0.5" style={{ color: TEXT.tertiary }} />
        )}
      </button>
      {open && (
        <div className="px-3 pb-3 border-t" style={{ borderColor: BORDER.muted }}>
          <p
            className="text-[9px] uppercase tracking-wider font-semibold mt-2.5 mb-1.5"
            style={{ color: TEXT.tertiary }}
          >
            Outcome Projections
          </p>
          <div className="space-y-1.5">
            {branch.outcomeProjections.map((proj, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded px-2 py-1.5"
                style={{ background: 'rgba(255,255,255,0.025)' }}
              >
                <div
                  className="text-[10px] font-bold font-mono tabular-nums mt-0.5 shrink-0 w-8 text-right"
                  style={{
                    color:
                      proj.probability >= 0.6
                        ? ACCENT.green
                        : proj.probability >= 0.4
                          ? ACCENT.amber
                          : ACCENT.red,
                  }}
                >
                  {Math.round(proj.probability * 100)}%
                </div>
                <div className="flex-1 min-w-0">
                  <p
                    className="text-[10px] font-medium leading-snug"
                    style={{ color: TEXT.primary }}
                  >
                    {proj.label}
                  </p>
                  <p className="text-[9px] mt-0.5" style={{ color: TEXT.secondary }}>
                    {proj.impact}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface AtlasPrismCounselPanelProps {
  matterId?: string;
  isDemo?: boolean;
}

export function AtlasPrismCounselPanel({ matterId, isDemo = true }: AtlasPrismCounselPanelProps) {
  const [scene] = useState(PRISM_DEMO_SCENE);
  const [loading] = useState(false);
  const [liveMode] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5" style={{ color: ACCENT.purple }} />
          <span
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: TEXT.secondary }}
          >
            ATLAS Scene
          </span>
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded"
            style={{
              background: 'rgba(139,122,200,0.12)',
              color: ACCENT.purple,
              border: '1px solid rgba(139,122,200,0.2)',
            }}
          >
            {scene.entityId}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {loading && (
            <RefreshCw className="w-3 h-3 animate-spin" style={{ color: TEXT.tertiary }} />
          )}
          <span
            className="text-[8px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded"
            style={{
              background: liveMode ? 'rgba(107,143,113,0.15)' : 'rgba(184,151,90,0.12)',
              color: liveMode ? ACCENT.green : ACCENT.amber,
              border: `1px solid ${liveMode ? 'rgba(107,143,113,0.25)' : 'rgba(200,149,60,0.25)'}`,
            }}
          >
            Demo
          </span>
        </div>
      </div>

      <div
        className="rounded-lg p-3"
        style={{ background: BG.card, border: `1px solid ${BORDER.muted}` }}
      >
        <DriftBar score={scene.driftScore} />
      </div>

      <div
        className="rounded-lg p-3 space-y-2"
        style={{ background: BG.card, border: `1px solid ${BORDER.muted}` }}
      >
        <p
          className="text-[9px] uppercase tracking-wider font-semibold"
          style={{ color: TEXT.tertiary }}
        >
          Scene State
        </p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
          <div className="col-span-2">
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Matter
            </span>
            <p className="text-[11px] font-semibold" style={{ color: TEXT.primary }}>
              {scene.state.matterTitle}
            </p>
          </div>
          <div>
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Total Exposure
            </span>
            <p className="text-[11px] font-bold" style={{ color: ACCENT.red }}>
              ${(scene.state.totalExposureUsd / 1e6).toFixed(1)}M
            </p>
          </div>
          <div>
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Settlement Offer
            </span>
            <p className="text-[11px] font-semibold" style={{ color: TEXT.primary }}>
              ${(scene.state.settlementOfferUsd / 1e6).toFixed(1)}M
            </p>
          </div>
          <div>
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Key Deadline
            </span>
            <p className="text-[11px] font-semibold" style={{ color: ACCENT.amber }}>
              {scene.state.keyDeadlineDays} days
            </p>
          </div>
          <div>
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Client Pressure
            </span>
            <p
              className="text-[11px] font-semibold"
              style={{ color: scene.state.clientPressureScore >= 75 ? ACCENT.red : ACCENT.amber }}
            >
              {scene.state.clientPressureScore}/100
            </p>
          </div>
          <div>
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Discovery
            </span>
            <p className="text-[11px] font-semibold capitalize" style={{ color: TEXT.primary }}>
              {scene.state.discoveryStatus}
            </p>
          </div>
          <div>
            <span className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Type
            </span>
            <p className="text-[11px] font-semibold capitalize" style={{ color: TEXT.primary }}>
              {scene.state.matterType.replace('_', ' ')}
            </p>
          </div>
        </div>
      </div>

      <div>
        <p
          className="text-[9px] uppercase tracking-wider font-semibold mb-2"
          style={{ color: TEXT.tertiary }}
        >
          Resolution Branches
        </p>
        <div className="space-y-2">
          {scene.branches.map((b, i) => (
            <BranchCard key={b.branchId} branch={b} defaultOpen={i === 0} />
          ))}
        </div>
      </div>

      <div
        className="rounded-lg p-3"
        style={{ background: BG.card, border: `1px solid ${BORDER.muted}` }}
      >
        <div className="flex items-center gap-1.5 mb-2.5">
          <Scale className="w-3 h-3" style={{ color: ACCENT.purple }} />
          <p
            className="text-[9px] uppercase tracking-wider font-semibold"
            style={{ color: TEXT.tertiary }}
          >
            Resolution Recommendations
          </p>
        </div>
        <div className="space-y-1.5">
          {scene.resolutionRecommendations.map((r, i) => {
            const col =
              r.priority === 'critical'
                ? ACCENT.red
                : r.priority === 'high'
                  ? ACCENT.amber
                  : ACCENT.green;
            return (
              <div
                key={i}
                className="flex items-start gap-2 rounded px-2 py-1.5"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${BORDER.muted}`,
                }}
              >
                <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" style={{ color: col }} />
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] font-semibold" style={{ color: TEXT.primary }}>
                    {r.title}
                  </p>
                  <p className="text-[9px] mt-0.5" style={{ color: TEXT.secondary }}>
                    {r.rationale}
                  </p>
                </div>
                <span
                  className="text-[8px] uppercase font-mono px-1 py-0.5 rounded shrink-0"
                  style={{ background: `${col}18`, color: col }}
                >
                  {r.priority}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div
        className="flex items-center gap-1.5 rounded px-2.5 py-1.5"
        style={{ background: 'rgba(255,255,255,0.025)', border: `1px solid ${BORDER.muted}` }}
      >
        <Lock className="w-3 h-3 shrink-0" style={{ color: TEXT.tertiary }} />
        <p className="text-[9px]" style={{ color: TEXT.tertiary }}>
          Branch execution requires <span style={{ color: TEXT.secondary }}>lead_counsel</span>{' '}
          approval — governed via Counsel proof chain
        </p>
      </div>
    </div>
  );
}
