// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import {
  ChevronRight,
  Database,
  Globe,
  Lock,
  Monitor,
  Network,
  Server,
  Shield,
} from 'lucide-react';
import { useState } from 'react';

const DS = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    tertiary: 'rgba(255,255,255,0.28)',
    muted: 'rgba(255,255,255,0.14)',
  },
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

interface PathNode {
  id: string;
  label: string;
  sublabel: string;
  type: 'internet' | 'perimeter' | 'workstation' | 'server' | 'dc' | 'crown';
  x: number;
  y: number;
  compromised: boolean;
  remediateCost: number;
  breachCost: number;
  technique: string;
  techniqueId: string;
  blocked?: boolean;
}

interface PathEdge {
  from: string;
  to: string;
  label: string;
  succeeded: boolean;
}

const NODES: PathNode[] = [
  {
    id: 'internet',
    label: 'APT29 Actor',
    sublabel: 'External Threat',
    type: 'internet',
    x: 60,
    y: 260,
    compromised: true,
    remediateCost: 0,
    breachCost: 0,
    technique: 'Initial Actor',
    techniqueId: 'TA0043',
  },
  {
    id: 'email',
    label: 'Finance Mailbox',
    sublabel: 'Spearphishing',
    type: 'workstation',
    x: 200,
    y: 160,
    compromised: true,
    remediateCost: 45_000,
    breachCost: 1_800_000,
    technique: 'Spearphishing Attachment',
    techniqueId: 'T1566.001',
  },
  {
    id: 'wks',
    label: 'WKS-FIN-047',
    sublabel: 'Finance Workstation',
    type: 'workstation',
    x: 360,
    y: 160,
    compromised: true,
    remediateCost: 28_000,
    breachCost: 1_200_000,
    technique: 'PowerShell Execution',
    techniqueId: 'T1059.001',
  },
  {
    id: 'vpn',
    label: 'VPN Gateway',
    sublabel: 'Edge Access',
    type: 'perimeter',
    x: 200,
    y: 360,
    compromised: false,
    remediateCost: 120_000,
    breachCost: 3_400_000,
    technique: 'External Remote Svcs',
    techniqueId: 'T1133',
    blocked: true,
  },
  {
    id: 'fs',
    label: 'FS-02 File Server',
    sublabel: 'Shared Drives',
    type: 'server',
    x: 520,
    y: 80,
    compromised: true,
    remediateCost: 95_000,
    breachCost: 4_200_000,
    technique: 'SMB Lateral Movement',
    techniqueId: 'T1021.002',
  },
  {
    id: 'dc',
    label: 'DC-PROD-03',
    sublabel: 'Domain Controller',
    type: 'dc',
    x: 520,
    y: 280,
    compromised: true,
    remediateCost: 320_000,
    breachCost: 14_200_000,
    technique: 'Lateral Movement → DC',
    techniqueId: 'T1021.002',
  },
  {
    id: 'db',
    label: 'SQL-PROD-01',
    sublabel: 'Customer Database',
    type: 'server',
    x: 680,
    y: 80,
    compromised: false,
    remediateCost: 180_000,
    breachCost: 9_800_000,
    technique: 'SQL Credential Abuse',
    techniqueId: 'T1078',
    blocked: true,
  },
  {
    id: 'creds',
    label: 'LSASS Dump',
    sublabel: 'Domain Credentials',
    type: 'server',
    x: 680,
    y: 280,
    compromised: true,
    remediateCost: 180_000,
    breachCost: 8_600_000,
    technique: 'OS Credential Dumping',
    techniqueId: 'T1003.001',
  },
  {
    id: 'crown',
    label: 'IP Repository',
    sublabel: 'Crown Jewels',
    type: 'crown',
    x: 840,
    y: 200,
    compromised: true,
    remediateCost: 450_000,
    breachCost: 22_000_000,
    technique: 'Exfiltration over C2',
    techniqueId: 'T1041',
  },
];

const EDGES: PathEdge[] = [
  { from: 'internet', to: 'email', label: 'Phishing', succeeded: true },
  { from: 'internet', to: 'vpn', label: 'Brute Force', succeeded: false },
  { from: 'email', to: 'wks', label: 'Payload Drop', succeeded: true },
  { from: 'wks', to: 'fs', label: 'SMB Spread', succeeded: true },
  { from: 'wks', to: 'dc', label: 'Lateral Move', succeeded: true },
  { from: 'fs', to: 'db', label: 'SQL Auth', succeeded: false },
  { from: 'dc', to: 'creds', label: 'LSASS', succeeded: true },
  { from: 'creds', to: 'crown', label: 'C2 Exfil', succeeded: true },
];

const NODE_ICONS: Record<string, React.ElementType> = {
  internet: Globe,
  perimeter: Shield,
  workstation: Monitor,
  server: Server,
  dc: Database,
  crown: Lock,
};

const NODE_COLORS: Record<string, string> = {
  internet: '#f5f5f5',
  perimeter: '#c9b787',
  workstation: '#c9b787',
  server: '#8a8a8a',
  dc: '#c9b787',
  crown: '#c9b787',
};

function GraphNode({
  node,
  selected,
  onClick,
}: {
  node: PathNode;
  selected: boolean;
  onClick: () => void;
}) {
  const _Icon = NODE_ICONS[node.type];
  const color = NODE_COLORS[node.type];
  const isCompromised = node.compromised;
  const isBlocked = node.blocked;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Glow */}
      {isCompromised && !isBlocked && (
        <circle cx={node.x} cy={node.y} r={28} fill={color} opacity={selected ? 0.15 : 0.06} />
      )}
      {/* Node circle */}
      <circle
        cx={node.x}
        cy={node.y}
        r={22}
        fill={selected ? `${color}25` : `${color}12`}
        stroke={isBlocked ? '#c9b787' : isCompromised ? color : 'rgba(255,255,255,0.12)'}
        strokeWidth={selected ? 2 : 1.5}
      />
      {/* Compromise indicator */}
      {isCompromised && !isBlocked && (
        <circle
          cx={node.x + 14}
          cy={node.y - 14}
          r={5}
          fill="#f5f5f5"
          stroke="#080B12"
          strokeWidth={1.5}
        />
      )}
      {isBlocked && (
        <circle
          cx={node.x + 14}
          cy={node.y - 14}
          r={5}
          fill="#c9b787"
          stroke="#080B12"
          strokeWidth={1.5}
        />
      )}
      {/* Label below */}
      <text
        x={node.x}
        y={node.y + 34}
        textAnchor="middle"
        fill={DS.text.secondary}
        fontSize={9}
        fontFamily="monospace"
      >
        {node.label}
      </text>
      <text x={node.x} y={node.y + 44} textAnchor="middle" fill={DS.text.muted} fontSize={8}>
        {node.sublabel}
      </text>
    </g>
  );
}

function GraphEdge({ edge, nodes }: { edge: PathEdge; nodes: PathNode[] }) {
  const from = nodes.find((n) => n.id === edge.from)!;
  const to = nodes.find((n) => n.id === edge.to)!;
  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2 - 18;
  const color = edge.succeeded ? '#f5f5f5' : '#c9b787';

  return (
    <g>
      <line
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        stroke={color}
        strokeWidth={edge.succeeded ? 2 : 1.5}
        strokeDasharray={edge.succeeded ? 'none' : '5,4'}
        opacity={edge.succeeded ? 0.7 : 0.4}
      />
      <text x={mx} y={my} textAnchor="middle" fill={color} fontSize={8} opacity={0.8}>
        {edge.label}
      </text>
    </g>
  );
}

export default function AttackPathViz() {
  const [selected, setSelected] = useState<PathNode | null>(NODES[8]);
  const [filter, setFilter] = useState<'all' | 'compromised' | 'blocked'>('all');

  const totalRemediateCost = NODES.filter((n) => n.remediateCost > 0).reduce(
    (s, n) => s + n.remediateCost,
    0,
  );
  const totalBreachCost = NODES.filter((n) => n.compromised && !n.blocked).reduce(
    (s, n) => s + n.breachCost,
    0,
  );
  const compromisedCount = NODES.filter((n) => n.compromised && !n.blocked).length;
  const blockedCount = NODES.filter((n) => n.blocked).length;

  const filteredNodes = NODES.filter((n) => {
    if (filter === 'compromised') return n.compromised && !n.blocked;
    if (filter === 'blocked') return n.blocked;
    return true;
  });

  return (
    <div
      className="min-h-screen p-6 space-y-5"
      style={{ background: '#080B12', color: DS.text.primary }}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{ background: 'rgba(138,138,138,0.15)' }}
            >
              <Network className="w-4 h-4 text-[#c9b787]" />
            </div>
            <h1 className="text-lg font-bold tracking-tight">Attack Path Visualization</h1>
          </div>
          <p className="text-sm" style={{ color: DS.text.secondary }}>
            Interactive lateral movement graph — each hop annotated with remediation cost vs. breach
            cost
          </p>
        </div>
        <div className="flex gap-2">
          {(['all', 'compromised', 'blocked'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all capitalize"
              style={{
                background: filter === f ? 'rgba(138,138,138,0.12)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${filter === f ? 'rgba(138,138,138,0.3)' : DS.border}`,
                color: filter === f ? '#c9b787' : DS.text.secondary,
              }}
            >
              {f === 'all' ? 'All Paths' : f === 'compromised' ? '⚠ Compromised' : '✓ Blocked'}
            </button>
          ))}
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: 'Total Remediation Cost',
            value: fmt(totalRemediateCost),
            color: '#c9b787',
            sub: 'to close all attack paths',
          },
          {
            label: 'Breach Cost Exposure',
            value: fmt(totalBreachCost),
            color: '#f5f5f5',
            sub: 'from compromised nodes',
          },
          {
            label: 'Nodes Compromised',
            value: `${compromisedCount}`,
            color: '#f5f5f5',
            sub: 'across attack chain',
          },
          {
            label: 'Attack Paths Blocked',
            value: `${blockedCount}`,
            color: '#c9b787',
            sub: 'defensive controls active',
          },
        ].map(({ label, value, color, sub }) => (
          <div
            key={label}
            className="rounded-xl p-4"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <p className="text-[10px] mb-2" style={{ color: DS.text.tertiary }}>
              {label}
            </p>
            <p className="text-2xl font-bold font-mono" style={{ color }}>
              {value}
            </p>
            <p className="text-[10px] mt-1" style={{ color: DS.text.muted }}>
              {sub}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Graph */}
        <div
          className="col-span-2 rounded-xl overflow-hidden"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <div className="px-4 pt-4 pb-2">
            <div className="flex items-center gap-4 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 bg-[#f5f5f5]/70 inline-block rounded" />
                Attack path succeeded
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className="w-4 h-0.5 bg-[#c9b787]/40 inline-block rounded border-t border-dashed border-[#c9b787]/40"
                  style={{ borderTop: '2px dashed #c9b78766' }}
                />
                Blocked attempt
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#f5f5f5] inline-block" />
                Compromised
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#c9b787] inline-block" />
                Blocked
              </div>
            </div>
          </div>
          <svg width="100%" viewBox="0 0 920 480" style={{ display: 'block' }}>
            {/* Background grid */}
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path
                  d="M 40 0 L 0 0 0 40"
                  fill="none"
                  stroke="rgba(255,255,255,0.03)"
                  strokeWidth="1"
                />
              </pattern>
            </defs>
            <rect width="920" height="480" fill="url(#grid)" />

            {/* Edges — only render edges between visible (filtered) nodes */}
            {EDGES.filter((e) => {
              const fromVisible = filteredNodes.some((n) => n.id === e.from);
              const toVisible = filteredNodes.some((n) => n.id === e.to);
              return fromVisible && toVisible;
            }).map((e, i) => (
              <GraphEdge key={i} edge={e} nodes={NODES} />
            ))}

            {/* Nodes — render all but dim hidden ones based on filter */}
            {NODES.map((node) => {
              const isInFilter = filteredNodes.some((n) => n.id === node.id);
              return (
                <g
                  key={node.id}
                  style={{ opacity: isInFilter ? 1 : 0.18, transition: 'opacity 0.3s' }}
                >
                  <GraphNode
                    node={node}
                    selected={selected?.id === node.id}
                    onClick={() =>
                      isInFilter && setSelected(selected?.id === node.id ? null : node)
                    }
                  />
                </g>
              );
            })}
          </svg>
        </div>

        {/* Detail panel */}
        <div className="space-y-4">
          {selected ? (
            <>
              <div
                className="rounded-xl p-5"
                style={{
                  background: DS.surface,
                  border: `1px solid ${selected.blocked ? 'rgba(201,183,135,0.2)' : selected.compromised ? 'rgba(245,245,245,0.2)' : DS.border}`,
                }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: `${NODE_COLORS[selected.type]}18` }}
                  >
                    {(() => {
                      const Icon = NODE_ICONS[selected.type];
                      return (
                        <Icon className="w-4 h-4" style={{ color: NODE_COLORS[selected.type] }} />
                      );
                    })()}
                  </div>
                  <div>
                    <p className="text-xs font-semibold">{selected.label}</p>
                    <p className="text-[10px]" style={{ color: DS.text.secondary }}>
                      {selected.sublabel}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mb-3">
                  {selected.blocked ? (
                    <Badge
                      className="text-[9px] px-1.5 py-0"
                      style={{
                        background: 'rgba(201,183,135,0.1)',
                        color: '#c9b787',
                        border: '1px solid rgba(201,183,135,0.2)',
                      }}
                    >
                      BLOCKED
                    </Badge>
                  ) : selected.compromised ? (
                    <Badge
                      className="text-[9px] px-1.5 py-0"
                      style={{
                        background: 'rgba(245,245,245,0.1)',
                        color: '#f5f5f5',
                        border: '1px solid rgba(245,245,245,0.2)',
                      }}
                    >
                      COMPROMISED
                    </Badge>
                  ) : (
                    <Badge
                      className="text-[9px] px-1.5 py-0"
                      style={{
                        background: 'rgba(201,183,135,0.1)',
                        color: '#c9b787',
                        border: '1px solid rgba(201,183,135,0.2)',
                      }}
                    >
                      SECURE
                    </Badge>
                  )}
                  <span className="text-[9px] font-mono" style={{ color: DS.text.tertiary }}>
                    {selected.techniqueId}
                  </span>
                </div>
                <p className="text-[10px] mb-3" style={{ color: DS.text.secondary }}>
                  {selected.technique}
                </p>

                {selected.remediateCost > 0 && (
                  <>
                    <div
                      className="flex items-center justify-between py-2"
                      style={{ borderTop: `1px solid ${DS.border}` }}
                    >
                      <span className="text-[10px]" style={{ color: DS.text.muted }}>
                        Remediation cost
                      </span>
                      <span className="text-sm font-mono font-bold text-[#c9b787]">
                        {fmt(selected.remediateCost)}
                      </span>
                    </div>
                    <div
                      className="flex items-center justify-between py-2"
                      style={{ borderTop: `1px solid ${DS.border}` }}
                    >
                      <span className="text-[10px]" style={{ color: DS.text.muted }}>
                        Cost if breached
                      </span>
                      <span className="text-sm font-mono font-bold text-[#f5f5f5]">
                        {fmt(selected.breachCost)}
                      </span>
                    </div>
                    <div
                      className="flex items-center justify-between py-2"
                      style={{ borderTop: `1px solid ${DS.border}` }}
                    >
                      <span className="text-[10px]" style={{ color: DS.text.muted }}>
                        ROI on remediation
                      </span>
                      <span className="text-sm font-mono font-bold text-[#c9b787]">
                        {Math.round(selected.breachCost / selected.remediateCost)}x
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Attack path hop sequence */}
              <div
                className="rounded-xl p-4"
                style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
              >
                <h3
                  className="text-[10px] font-semibold uppercase tracking-wider mb-3"
                  style={{ color: DS.text.tertiary }}
                >
                  Attack Chain Sequence
                </h3>
                <div className="space-y-1.5">
                  {NODES.filter((n) => n.compromised && !n.blocked).map((n, i) => (
                    <div key={n.id} className="flex items-center gap-2">
                      <span className="text-[9px] font-mono w-4" style={{ color: DS.text.muted }}>
                        {i + 1}
                      </span>
                      <ChevronRight className="w-3 h-3 text-[#f5f5f5]/60 shrink-0" />
                      <span
                        className="text-[10px]"
                        style={{
                          color: n.id === selected.id ? DS.text.primary : DS.text.secondary,
                        }}
                      >
                        {n.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div
              className="rounded-xl p-6 flex flex-col items-center justify-center text-center h-64"
              style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
            >
              <Network className="w-8 h-8 mb-2" style={{ color: DS.text.muted }} />
              <p className="text-xs" style={{ color: DS.text.tertiary }}>
                Click any node to see cost annotation and attack details
              </p>
            </div>
          )}

          {/* Cost comparison summary */}
          <div
            className="rounded-xl p-4"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <h3
              className="text-[10px] font-semibold uppercase tracking-wider mb-3"
              style={{ color: DS.text.tertiary }}
            >
              Full Chain Cost Analysis
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: DS.text.secondary }}>
                  Total remediate all hops
                </span>
                <span className="text-xs font-mono font-bold text-[#c9b787]">
                  {fmt(totalRemediateCost)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: DS.text.secondary }}>
                  Total breach exposure
                </span>
                <span className="text-xs font-mono font-bold text-[#f5f5f5]">
                  {fmt(totalBreachCost)}
                </span>
              </div>
              <div
                className="flex items-center justify-between pt-2"
                style={{ borderTop: `1px solid ${DS.border}` }}
              >
                <span className="text-[10px] font-semibold">Security ROI</span>
                <span className="text-sm font-mono font-bold text-[#c9b787]">
                  {Math.round(totalBreachCost / totalRemediateCost)}x
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
