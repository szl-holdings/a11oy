// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/pages/cognitive-attack-path.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardQuery } from '@szl-holdings/api-client-react';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle,
  ChevronRight,
  Eye,
  Network,
  RefreshCw,
  Server,
  Shield,
  Users,
} from 'lucide-react';
import { useState } from 'react';
import { AccessDeniedNotice, HttpError, isAccessDenied } from '../components/AccessDeniedNotice';
import { CognitiveBreadcrumbs } from '../components/CognitiveBreadcrumbs';
import { CopyLinkButton } from '../components/CopyLinkButton';
import { useDrilldown } from '../lib/cognitive-nav';

const API = import.meta.env.VITE_API_URL ?? '/api';

const DS = {
  surface: 'rgba(255,255,255,0.03)',
  border: 'rgba(255,255,255,0.07)',
  text: {
    primary: 'rgba(255,255,255,0.9)',
    secondary: 'rgba(255,255,255,0.55)',
    muted: 'rgba(255,255,255,0.28)',
  },
};

const NODE_COLORS: Record<string, string> = {
  asset: '#c9b787',
  identity: '#8a8a8a',
  control: '#c9b787',
  incident: '#f5f5f5',
  actor: '#c9b787',
};

const NODE_ICONS: Record<string, typeof Network> = {
  asset: Server,
  identity: Users,
  control: Shield,
  incident: AlertTriangle,
  actor: Network,
};

interface GraphNode {
  id: string;
  label: string;
  type: string;
  severity: string;
  x: number;
  y: number;
  compromised: boolean;
  technique?: string;
  techniqueId?: string;
  evidence?: string[];
  provenance: { source: string; traceId: string; verifiedBy: string; generatedAt: string };
}

interface GraphEdge {
  from: string;
  to: string;
  label: string;
  weight: number;
  blocked: boolean;
}

function AttackGraphCanvas({
  nodes,
  edges,
  onNodeClick,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (n: GraphNode) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const scale = { x: 800 / 960, y: 440 / 520 };

  return (
    <div
      className="relative w-full"
      style={{
        height: 440,
        background: 'rgba(10,13,20,0.95)',
        border: `1px solid ${DS.border}`,
        borderRadius: 12,
        overflow: 'hidden',
      }}
    >
      <svg width="100%" height="100%" viewBox="0 0 800 440" preserveAspectRatio="xMidYMid meet">
        <defs>
          <filter id="glow-red">
            <feGaussianBlur stdDeviation="3" result="c" />
            <feMerge>
              <feMergeNode in="c" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-blue">
            <feGaussianBlur stdDeviation="2" result="c" />
            <feMerge>
              <feMergeNode in="c" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#f5f5f5" opacity="0.7" />
          </marker>
          <marker id="arrow-green" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#c9b787" opacity="0.7" />
          </marker>
          <marker id="arrow-blue" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#c9b787" opacity="0.5" />
          </marker>
        </defs>

        {edges.map((e, i) => {
          const src = nodes.find((n) => n.id === e.from);
          const dst = nodes.find((n) => n.id === e.to);
          if (!src || !dst) return null;
          const sx = src.x * scale.x;
          const sy = src.y * scale.y;
          const dx = dst.x * scale.x;
          const dy = dst.y * scale.y;
          const color = e.blocked ? '#c9b787' : e.weight > 0.8 ? '#f5f5f5' : '#c9b787';
          const marker = e.blocked
            ? 'url(#arrow-green)'
            : e.weight > 0.8
              ? 'url(#arrow-red)'
              : 'url(#arrow-blue)';
          return (
            <g key={i}>
              <line
                x1={sx}
                y1={sy}
                x2={dx}
                y2={dy}
                stroke={color}
                strokeWidth={e.weight * 1.5}
                opacity={0.5}
                strokeDasharray={e.blocked ? '4 3' : undefined}
                markerEnd={marker}
              />
              <text
                x={(sx + dx) / 2}
                y={(sy + dy) / 2 - 4}
                fontSize="7"
                fill={color}
                opacity={0.7}
                textAnchor="middle"
              >
                {e.label}
              </text>
            </g>
          );
        })}

        {nodes.map((n) => {
          const cx = n.x * scale.x;
          const cy = n.y * scale.y;
          const color = NODE_COLORS[n.type] ?? '#94a3b8';
          const isHovered = hovered === n.id;
          const r = n.type === 'actor' ? 22 : n.type === 'incident' ? 18 : 16;
          return (
            <g
              key={n.id}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onNodeClick?.(n)}
            >
              <title>
                {n.type === 'identity' || n.type === 'incident'
                  ? `Click to drill into ${n.label}`
                  : n.label}
              </title>
              {n.compromised && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={r + 6}
                  fill="none"
                  stroke="#f5f5f5"
                  strokeWidth="1"
                  opacity="0.25"
                >
                  <animate
                    attributeName="r"
                    values={`${r + 4};${r + 10};${r + 4}`}
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.25;0.05;0.25"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={`${color}22`}
                stroke={color}
                strokeWidth={isHovered ? 2.5 : 1.5}
                filter={n.compromised ? 'url(#glow-red)' : undefined}
                opacity={0.95}
              />
              {!n.compromised && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={r}
                  fill="none"
                  stroke="#c9b787"
                  strokeWidth="1"
                  strokeDasharray="3 2"
                  opacity="0.4"
                />
              )}
              <text
                x={cx}
                y={cy + 4}
                fontSize={n.type === 'actor' ? '9' : '8'}
                fill={color}
                textAnchor="middle"
                fontWeight="600"
              >
                {n.type === 'actor' ? 'APT' : n.type.slice(0, 3).toUpperCase()}
              </text>
              <text
                x={cx}
                y={cy + r + 12}
                fontSize="7"
                fill={DS.text.secondary}
                textAnchor="middle"
                style={{ maxWidth: 70 }}
              >
                {n.label.slice(0, 14)}
                {n.label.length > 14 ? '…' : ''}
              </text>
              {n.techniqueId && (
                <text
                  x={cx}
                  y={cy + r + 21}
                  fontSize="6"
                  fill={color}
                  textAnchor="middle"
                  opacity={0.7}
                >
                  {n.techniqueId}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div
        className="absolute bottom-3 right-3 flex items-center gap-3 text-[10px]"
        style={{ color: DS.text.muted }}
      >
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function CognitiveAttackPath() {
  // Live backend route — /firestorm/* path is an active api-server endpoint.
  // Follow-up task #1715 will rename it to /aegis/* once the server migration lands.
  const { data, isLoading, error, refetch, dataUpdatedAt } = useStandardQuery({
    queryKey: ['cognitive-attack-path-graph'],
    queryFn: async () => {
      const r = await fetch(`${API}/firestorm/cognitive/attack-path-graph`, {
        credentials: 'include',
      });
      if (!r.ok) throw new HttpError(r.status, 'Failed to load attack path graph');
      return r.json();
    },
    staleTime: 30_000,
    retry: (failureCount, err) => !isAccessDenied(err) && failureCount < 1,
  });

  const denied = isAccessDenied(error);

  const graph = data?.data?.graph ?? { nodes: [], edges: [] };
  const summary = data?.data?.summary ?? {};
  const provenance = data?.data?.provenance ?? {};
  const nodes: GraphNode[] = graph.nodes ?? [];
  const edges: GraphEdge[] = graph.edges ?? [];

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const drilldown = useDrilldown();

  const drillNode = (n: GraphNode) => {
    if (n.type === 'identity') {
      drilldown(`/identity-blast-radius?id=${encodeURIComponent(n.label)}`, {
        fromContext: n.label,
      });
    } else if (n.type === 'incident') {
      const id = n.id.replace(/^incident-/, '');
      drilldown(`/compliance/incident-proof?id=${encodeURIComponent(id)}`, {
        fromContext: n.label,
      });
    } else {
      setSelectedNode(selectedNode?.id === n.id ? null : n);
    }
  };

  return (
    <div className="p-6 space-y-6" style={{ maxWidth: 1280, margin: '0 auto' }}>
      <CognitiveBreadcrumbs accent="#f5f5f5" />
      <div className="flex items-start justify-between">
        <div>
          <h1
            className="text-xl font-bold flex items-center gap-2"
            style={{ color: DS.text.primary }}
          >
            <Network className="w-5 h-5 text-[#f5f5f5]" />
            Cognitive Attack Path Graph
          </h1>
          <p className="text-sm mt-1" style={{ color: DS.text.secondary }}>
            CONSTELLATION-rendered live attack path — cyber assets, identities, controls, and
            incidents with evidence provenance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {provenance.traceId && (
            <span
              className="text-[10px] font-mono px-2 py-1 rounded"
              style={{
                background: 'rgba(245,245,245,0.08)',
                color: '#f5f5f5',
                border: '1px solid rgba(245,245,245,0.2)',
              }}
            >
              TRACE: {provenance.traceId.slice(-10)}
            </span>
          )}
          <CopyLinkButton accent="#f5f5f5" />
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
            style={{
              background: 'rgba(245,245,245,0.08)',
              color: '#f5f5f5',
              border: '1px solid rgba(245,245,245,0.2)',
            }}
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          {
            label: 'Total Nodes',
            value: summary.totalNodes ?? nodes.length,
            color: 'text-[#c9b787]',
            icon: Network,
          },
          {
            label: 'Compromised',
            value: summary.compromisedNodes ?? nodes.filter((n) => n.compromised).length,
            color: 'text-[#f5f5f5]',
            icon: AlertTriangle,
          },
          {
            label: 'Critical Paths',
            value: summary.criticalPaths ?? 0,
            color: 'text-[#c9b787]',
            icon: ChevronRight,
          },
          {
            label: 'Blocked Paths',
            value: summary.blockedPaths ?? 0,
            color: 'text-[#c9b787]',
            icon: CheckCircle,
          },
        ].map(({ label, value, color, icon: Icon }) => (
          <div
            key={label}
            className="rounded-xl p-4"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className={cn('w-3.5 h-3.5', color)} />
              <span className="text-[11px]" style={{ color: DS.text.muted }}>
                {label}
              </span>
            </div>
            {isLoading ? (
              <div className="h-7 w-12 rounded animate-pulse" style={{ background: DS.border }} />
            ) : (
              <p className={cn('text-2xl font-bold', color)}>{value}</p>
            )}
          </div>
        ))}
      </div>

      {denied ? (
        <AccessDeniedNotice
          status={(error as HttpError).status}
          accent="#f5f5f5"
          resourceLabel="the attack path graph"
        />
      ) : isLoading ? (
        <div
          className="flex items-center justify-center"
          style={{
            height: 440,
            background: DS.surface,
            borderRadius: 12,
            border: `1px solid ${DS.border}`,
          }}
        >
          <div className="w-6 h-6 border-2 border-[#f5f5f5]/40 border-t-red-400 rounded-full animate-spin" />
        </div>
      ) : (
        <AttackGraphCanvas nodes={nodes} edges={edges} onNodeClick={drillNode} />
      )}

      <div className="grid grid-cols-2 gap-4">
        <div
          className="rounded-xl p-4 space-y-3"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <h3
            className="text-xs font-semibold uppercase tracking-widest"
            style={{ color: DS.text.muted }}
          >
            High-Risk Nodes
          </h3>
          <div className="space-y-2">
            {nodes
              .filter((n) => n.compromised)
              .slice(0, 5)
              .map((node) => {
                const Icon = NODE_ICONS[node.type] ?? Network;
                const color = NODE_COLORS[node.type] ?? '#94a3b8';
                return (
                  <div
                    key={node.id}
                    className="flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors"
                    style={{
                      background: 'rgba(245,245,245,0.05)',
                      border: '1px solid rgba(245,245,245,0.12)',
                    }}
                    onClick={() => drillNode(node)}
                  >
                    <div
                      className="w-6 h-6 rounded flex items-center justify-center shrink-0"
                      style={{ background: `${color}18` }}
                    >
                      <Icon className="w-3.5 h-3.5" style={{ color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className="text-xs font-medium truncate"
                        style={{ color: DS.text.primary }}
                      >
                        {node.label}
                      </p>
                      <p className="text-[10px]" style={{ color: DS.text.muted }}>
                        {node.type} · {node.techniqueId ?? 'unknown'}
                      </p>
                    </div>
                    <Badge className="text-[9px] bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20 shrink-0">
                      COMPROMISED
                    </Badge>
                  </div>
                );
              })}
          </div>
        </div>

        <div
          className="rounded-xl p-4 space-y-3"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <h3
            className="text-xs font-semibold uppercase tracking-widest"
            style={{ color: DS.text.muted }}
          >
            Active Critical Paths
          </h3>
          <div className="space-y-2">
            {edges
              .filter((e) => !e.blocked && e.weight > 0.7)
              .slice(0, 5)
              .map((edge, i) => {
                const src = nodes.find((n) => n.id === edge.from);
                const dst = nodes.find((n) => n.id === edge.to);
                return (
                  <div
                    key={i}
                    className="flex items-center gap-2 p-2.5 rounded-lg"
                    style={{
                      background: 'rgba(245,245,245,0.04)',
                      border: '1px solid rgba(245,245,245,0.1)',
                    }}
                  >
                    <AlertTriangle className="w-3 h-3 text-[#f5f5f5] shrink-0" />
                    <span
                      className="text-[10px] flex-1 truncate"
                      style={{ color: DS.text.secondary }}
                    >
                      {src?.label?.slice(0, 16) ?? edge.from} →{' '}
                      {dst?.label?.slice(0, 16) ?? edge.to}
                    </span>
                    <span className="text-[10px] font-mono" style={{ color: '#c9b787' }}>
                      {(edge.weight * 100).toFixed(0)}%
                    </span>
                  </div>
                );
              })}
            {edges
              .filter((e) => e.blocked)
              .slice(0, 3)
              .map((edge, i) => {
                const src = nodes.find((n) => n.id === edge.from);
                const dst = nodes.find((n) => n.id === edge.to);
                return (
                  <div
                    key={`blocked-${i}`}
                    className="flex items-center gap-2 p-2.5 rounded-lg"
                    style={{
                      background: 'rgba(201,183,135,0.04)',
                      border: '1px solid rgba(201,183,135,0.1)',
                    }}
                  >
                    <CheckCircle className="w-3 h-3 text-[#c9b787] shrink-0" />
                    <span className="text-[10px] flex-1 truncate" style={{ color: DS.text.muted }}>
                      {src?.label?.slice(0, 16) ?? edge.from} →{' '}
                      {dst?.label?.slice(0, 16) ?? edge.to}
                    </span>
                    <span className="text-[10px] font-mono text-[#c9b787]">BLOCKED</span>
                  </div>
                );
              })}
          </div>
        </div>
      </div>

      {selectedNode && (
        <div
          className="rounded-xl p-4 space-y-3"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <div className="flex items-center justify-between">
            <h3
              className="text-xs font-semibold uppercase tracking-widest flex items-center gap-2"
              style={{ color: DS.text.muted }}
            >
              <Eye className="w-3.5 h-3.5" /> Node Detail — {selectedNode.label}
            </h3>
            <div className="flex items-center gap-3">
              {(selectedNode.type === 'identity' || selectedNode.type === 'incident') && (
                <button
                  onClick={() => drillNode(selectedNode)}
                  className="flex items-center gap-1 text-[10px] px-2 py-1 rounded transition-colors"
                  style={{
                    background: 'rgba(245,245,245,0.1)',
                    color: '#f5f5f5',
                    border: '1px solid rgba(245,245,245,0.25)',
                  }}
                >
                  Open {selectedNode.type === 'identity' ? 'Blast Radius' : 'Proof Chain'}
                  <ArrowUpRight className="w-3 h-3" />
                </button>
              )}
              <button
                onClick={() => setSelectedNode(null)}
                className="text-[10px]"
                style={{ color: DS.text.muted }}
              >
                ✕ Close
              </button>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-[11px]">
            <div>
              <span style={{ color: DS.text.muted }}>Type: </span>
              <span style={{ color: DS.text.primary }}>{selectedNode.type}</span>
            </div>
            <div>
              <span style={{ color: DS.text.muted }}>Severity: </span>
              <span style={{ color: '#f5f5f5' }}>{selectedNode.severity}</span>
            </div>
            <div>
              <span style={{ color: DS.text.muted }}>Technique: </span>
              <span style={{ color: DS.text.primary }}>{selectedNode.techniqueId ?? '—'}</span>
            </div>
          </div>
          {selectedNode.evidence && (
            <div className="space-y-1.5">
              <p
                className="text-[10px] font-semibold uppercase tracking-widest"
                style={{ color: DS.text.muted }}
              >
                Evidence Citations
              </p>
              <div className="flex flex-wrap gap-1.5">
                {selectedNode.evidence.map((ev, i) => (
                  <span
                    key={i}
                    className="text-[10px] px-2 py-0.5 rounded font-mono"
                    style={{
                      background: 'rgba(201,183,135,0.08)',
                      color: '#c9b787',
                      border: '1px solid rgba(201,183,135,0.2)',
                    }}
                  >
                    {ev}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="text-[10px] pt-1" style={{ color: DS.text.muted }}>
            <Activity className="w-3 h-3 inline mr-1" />
            Verified by: {selectedNode.provenance.verifiedBy} · Trace:{' '}
            {selectedNode.provenance.traceId}
          </div>
        </div>
      )}

      <div className="flex items-center gap-6 text-[10px] pt-2" style={{ color: DS.text.muted }}>
        <span>Verified by: {provenance.verifiedBy ?? 'CONSTELLATION Engine'}</span>
        <span>Runtime: {provenance.cognitiveRuntime ?? 'v2.1.0'}</span>
        {dataUpdatedAt > 0 && <span>Updated: {new Date(dataUpdatedAt).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}
