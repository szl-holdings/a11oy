import { GitBranch, Loader2, RefreshCw, ZoomIn, ZoomOut } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

interface GraphNode {
  id: string;
  label: string;
  type: 'domain' | 'entity' | 'signal';
  domain: string;
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info';
  value?: number;
  description?: string;
  live?: boolean;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  strength: number;
  type: 'causal' | 'correlative' | 'escalation' | 'dependency';
  description: string;
  lastActive: number;
}

const DOMAIN_COLORS: Record<string, string> = {
  vessels: 'var(--gi-accent-blue)',
  aegis: '#ef4444',
  firestorm: '#ef4444',
  terra: '#22c55e',
  prism: '#8b5cf6',
  lyte: '#f59e0b',
  'szl-holdings': '#8b7ac8',
  carlota: '#ec4899',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#6b7280',
  info: '#22c55e',
};

const EDGE_COLORS: Record<string, string> = {
  causal: '#ef4444',
  escalation: '#f59e0b',
  correlative: '#3b82f6',
  dependency: '#6b7280',
};

const DEMO_NODES: GraphNode[] = [
  {
    id: 'domain-vessels',
    label: 'SEXTANT',
    type: 'domain',
    domain: 'vessels',
    description: 'Maritime fleet operations across 14 active vessels',
  },
  {
    id: 'domain-aegis',
    label: "PARAGON",
    type: 'domain',
    domain: 'aegis',
    description: 'Cybersecurity posture and threat intelligence',
  },
  {
    id: 'domain-terra',
    label: 'DOMAINE',
    type: 'domain',
    domain: 'terra',
    description: 'Real estate portfolio — 127 assets across 9 markets',
  },
  {
    id: 'domain-prism',
    label: 'PRAXIS',
    type: 'domain',
    domain: 'prism',
    description: 'Cross-domain intelligence and pattern detection',
  },
  {
    id: 'domain-lyte',
    label: 'KORA',
    type: 'domain',
    domain: 'lyte',
    description: 'Platform reliability and SLO management',
  },
  {
    id: 'domain-szl',
    label: 'Holdings',
    type: 'domain',
    domain: 'szl-holdings',
    description: 'SZL Holdings executive overview',
  },
  {
    id: 'entity-mv-meridian',
    label: 'MV Meridian',
    type: 'entity',
    domain: 'vessels',
    severity: 'medium',
    description: 'Vessel delayed — Bay of Bengal corridor',
  },
  {
    id: 'entity-sg-port',
    label: 'SG Port Auth',
    type: 'entity',
    domain: 'aegis',
    severity: 'low',
    description: 'Singapore port authority access event',
  },
  {
    id: 'entity-dfw-7',
    label: 'DFW-Industrial-7',
    type: 'entity',
    domain: 'terra',
    severity: 'low',
    description: 'Asset appreciation signal — DFW corridor',
  },
  {
    id: 'signal-fleet-eta',
    label: 'Fleet ETA Gap',
    type: 'signal',
    domain: 'vessels',
    severity: 'medium',
    value: 0.78,
  },
  {
    id: 'signal-perimeter',
    label: 'Perimeter Scan',
    type: 'signal',
    domain: 'aegis',
    severity: 'info',
    value: 0.45,
  },
  {
    id: 'signal-market-vol',
    label: 'Market Volatility',
    type: 'signal',
    domain: 'szl-holdings',
    severity: 'medium',
    value: 0.72,
  },
  {
    id: 'signal-pattern',
    label: 'Pattern Match',
    type: 'signal',
    domain: 'prism',
    severity: 'low',
    value: 0.61,
  },
];

const DEMO_EDGES: GraphEdge[] = [
  {
    id: 'e1',
    source: 'domain-vessels',
    target: 'entity-mv-meridian',
    label: 'contains',
    strength: 0.9,
    type: 'dependency',
    description: 'MV Meridian is part of the active fleet',
    lastActive: Date.now() - 3600000,
  },
  {
    id: 'e2',
    source: 'entity-mv-meridian',
    target: 'signal-fleet-eta',
    label: 'triggers',
    strength: 0.78,
    type: 'causal',
    description: 'Vessel delay caused ETA compliance gap signal',
    lastActive: Date.now() - 1800000,
  },
  {
    id: 'e3',
    source: 'signal-fleet-eta',
    target: 'domain-terra',
    label: 'impacts',
    strength: 0.55,
    type: 'correlative',
    description: 'Port delays correlate with DFW property logistics',
    lastActive: Date.now() - 900000,
  },
  {
    id: 'e4',
    source: 'domain-aegis',
    target: 'entity-sg-port',
    label: 'monitors',
    strength: 0.82,
    type: 'dependency',
    description: 'PARAGON monitors Singapore port authority access',
    lastActive: Date.now() - 7200000,
  },
  {
    id: 'e5',
    source: 'entity-sg-port',
    target: 'domain-vessels',
    label: 'correlates',
    strength: 0.63,
    type: 'correlative',
    description: 'SG port access events correlate with fleet routing',
    lastActive: Date.now() - 5400000,
  },
  {
    id: 'e6',
    source: 'signal-market-vol',
    target: 'domain-terra',
    label: 'escalates',
    strength: 0.71,
    type: 'escalation',
    description: 'Volatility index crossing threshold escalates asset review',
    lastActive: Date.now() - 3600000,
  },
  {
    id: 'e7',
    source: 'domain-prism',
    target: 'signal-pattern',
    label: 'detects',
    strength: 0.88,
    type: 'dependency',
    description: 'PRAXIS intelligence layer detected cross-domain pattern',
    lastActive: Date.now() - 2700000,
  },
  {
    id: 'e8',
    source: 'signal-pattern',
    target: 'domain-aegis',
    label: 'informs',
    strength: 0.67,
    type: 'correlative',
    description: 'Pattern detection informs PARAGON threat posture',
    lastActive: Date.now() - 2700000,
  },
  {
    id: 'e9',
    source: 'domain-szl',
    target: 'signal-market-vol',
    label: 'emits',
    strength: 0.72,
    type: 'causal',
    description: 'Holdings portfolio movement emits volatility signal',
    lastActive: Date.now() - 3600000,
  },
  {
    id: 'e10',
    source: 'entity-dfw-7',
    target: 'domain-terra',
    label: 'belongs',
    strength: 0.9,
    type: 'dependency',
    description: 'DFW-Industrial-7 is part of the DOMAINE portfolio',
    lastActive: Date.now() - 86400000,
  },
];

const DEMO_STATS = { strongCorrelations: 4, activeEdges: 7 };

function layoutNodes(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
): GraphNode[] {
  const domainNodes = nodes.filter((n) => n.type === 'domain');
  const otherNodes = nodes.filter((n) => n.type !== 'domain');

  const cx = width / 2;
  const cy = height / 2;
  const domainRadius = Math.min(width, height) * 0.28;
  const entityRadius = Math.min(width, height) * 0.44;

  const placed = new Map<string, { x: number; y: number }>();

  domainNodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / domainNodes.length - Math.PI / 2;
    placed.set(n.id, {
      x: cx + domainRadius * Math.cos(angle),
      y: cy + domainRadius * Math.sin(angle),
    });
  });

  otherNodes.forEach((n) => {
    const _connectedDomain = edges.find((e) => {
      const srcNode = nodes.find((nd) => nd.id === e.source);
      const tgtNode = nodes.find((nd) => nd.id === e.target);
      return (
        (e.source === n.id || e.target === n.id) &&
        (srcNode?.type === 'domain' || tgtNode?.type === 'domain')
      );
    });

    const domainMatch = nodes.find((nd) => nd.type === 'domain' && nd.domain === n.domain);
    const domainPos = domainMatch ? placed.get(domainMatch.id) : null;

    if (domainPos) {
      const _angle = Math.random() * 2 * Math.PI;
      const r = entityRadius * (0.85 + Math.random() * 0.15);
      const dp = placed.get(domainMatch?.id ?? '')!;
      const angleFromCenter = Math.atan2(dp.y - cy, dp.x - cx);
      const spread = 0.6;
      const finalAngle = angleFromCenter + (Math.random() - 0.5) * spread;
      placed.set(n.id, {
        x: cx + r * Math.cos(finalAngle),
        y: cy + r * Math.sin(finalAngle),
      });
    } else {
      placed.set(n.id, {
        x: cx + (Math.random() - 0.5) * width * 0.7,
        y: cy + (Math.random() - 0.5) * height * 0.7,
      });
    }
  });

  return nodes.map((n) => ({ ...n, ...placed.get(n.id) }));
}

interface CorrelationMapVizProps {
  apiBase?: string;
}

export function CorrelationMapViz({ apiBase = '' }: CorrelationMapVizProps) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState<boolean | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<GraphEdge | null>(null);
  const [zoom, setZoom] = useState(1);
  const [filter, setFilter] = useState<'all' | 'domain' | 'entity' | 'signal'>('all');
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ w: 800, h: 500 });

  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setDimensions({ w: entry.contentRect.width, h: Math.max(480, entry.contentRect.height) });
      }
    });
    if (svgRef.current?.parentElement) obs.observe(svgRef.current.parentElement);
    return () => obs.disconnect();
  }, []);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/correlation-map/live`);
      if (res.status === 401 || res.status === 403) {
        const laid = layoutNodes(DEMO_NODES, DEMO_EDGES, dimensions.w, dimensions.h);
        setNodes(laid);
        setEdges(DEMO_EDGES);
        setStats(DEMO_STATS);
        setIsDemo(true);
        return;
      }
      const data = await res.json();
      if (data.success) {
        const laid = layoutNodes(data.nodes, data.edges, dimensions.w, dimensions.h);
        setNodes(laid);
        setEdges(data.edges);
        setStats(data.stats ?? {});
        setIsDemo(false);
      } else {
        const laid = layoutNodes(DEMO_NODES, DEMO_EDGES, dimensions.w, dimensions.h);
        setNodes(laid);
        setEdges(DEMO_EDGES);
        setStats(DEMO_STATS);
        setIsDemo(true);
      }
    } catch {
      const laid = layoutNodes(DEMO_NODES, DEMO_EDGES, dimensions.w, dimensions.h);
      setNodes(laid);
      setEdges(DEMO_EDGES);
      setStats(DEMO_STATS);
      setIsDemo(true);
    } finally {
      setLoading(false);
    }
  }, [apiBase, dimensions.w, dimensions.h]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  const filteredNodes = filter === 'all' ? nodes : nodes.filter((n) => n.type === filter);
  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = edges.filter(
    (e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target),
  );

  function getNodeColor(n: GraphNode) {
    if (n.severity) return SEVERITY_COLORS[n.severity] ?? DOMAIN_COLORS[n.domain] ?? '#6b7280';
    return DOMAIN_COLORS[n.domain] ?? '#6b7280';
  }

  function getNodeRadius(n: GraphNode) {
    if (n.type === 'domain') return 22;
    if (n.type === 'signal') return 11;
    return 15;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4" style={{ color: '#8b7ac8' }} />
          <h2
            className="text-xs font-bold tracking-widest uppercase"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Correlation Map
          </h2>
          {!loading && isDemo === true && (
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
              title="Showing illustrative demo data — live API unavailable"
              style={{
                color: '#f59e0b',
                backgroundColor: 'color-mix(in srgb, #f59e0b 12%, transparent)',
                border: '1px solid color-mix(in srgb, #f59e0b 30%, transparent)',
              }}
            >
              Demo
            </span>
          )}
          {!loading && isDemo === false && (
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded inline-flex items-center gap-1"
              title="Connected to live data"
              style={{
                color: '#22c55e',
                backgroundColor: 'color-mix(in srgb, #22c55e 12%, transparent)',
                border: '1px solid color-mix(in srgb, #22c55e 30%, transparent)',
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ backgroundColor: '#22c55e' }}
              />
              Live
            </span>
          )}
          {!loading && (
            <span
              className="text-[10px] font-mono px-2 py-0.5 rounded"
              style={{
                backgroundColor: 'var(--color-surface-base)',
                color: 'var(--color-fg-muted)',
              }}
            >
              {filteredNodes.length} nodes · {filteredEdges.length} edges
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {(['all', 'domain', 'entity', 'signal'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded transition-all"
              style={{
                backgroundColor: filter === f ? '#8b7ac8' : 'var(--color-surface-base)',
                color: filter === f ? '#fff' : 'var(--color-fg-muted)',
                border: '1px solid var(--color-surface-border)',
              }}
            >
              {f}
            </button>
          ))}
          <button
            onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
            className="p-1.5 rounded"
            style={{
              backgroundColor: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              color: 'var(--color-fg-muted)',
            }}
          >
            <ZoomIn className="w-3 h-3" />
          </button>
          <button
            onClick={() => setZoom((z) => Math.max(0.4, z - 0.2))}
            className="p-1.5 rounded"
            style={{
              backgroundColor: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              color: 'var(--color-fg-muted)',
            }}
          >
            <ZoomOut className="w-3 h-3" />
          </button>
          <button
            onClick={fetchGraph}
            disabled={loading}
            className="p-1.5 rounded"
            style={{
              backgroundColor: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              color: 'var(--color-fg-muted)',
            }}
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div
        className="relative rounded-xl overflow-hidden"
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-surface-border)',
          height: '520px',
        }}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#8b7ac8' }} />
              <span
                className="text-[10px] font-mono uppercase tracking-widest"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                Building correlation graph…
              </span>
            </div>
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs" style={{ color: '#ef4444' }}>
              {error}
            </span>
          </div>
        )}

        <svg ref={svgRef} width="100%" height="100%" style={{ cursor: 'default' }}>
          <defs>
            {Object.entries(EDGE_COLORS).map(([type, color]) => (
              <marker
                key={type}
                id={`arrow-${type}`}
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
              >
                <path d="M0,0 L0,6 L8,3 z" fill={color} opacity="0.7" />
              </marker>
            ))}
          </defs>

          <g
            transform={`scale(${zoom}) translate(${(dimensions.w * (1 - zoom)) / (2 * zoom)}, ${(dimensions.h * (1 - zoom)) / (2 * zoom)})`}
          >
            {filteredEdges.map((edge) => {
              const src = nodeMap.get(edge.source);
              const tgt = nodeMap.get(edge.target);
              if (src?.x == null || src.y == null || tgt?.x == null || tgt.y == null) return null;
              const color = EDGE_COLORS[edge.type] ?? '#6b7280';
              const isHovered = hoveredEdge?.id === edge.id;
              const opacity = isHovered ? 0.9 : Math.max(0.15, edge.strength * 0.6);
              const sw = isHovered ? 2 : Math.max(0.5, edge.strength * 2);

              const mx = (src.x + tgt.x) / 2;
              const my = (src.y + tgt.y) / 2;
              const dx = tgt.x - src.x;
              const dy = tgt.y - src.y;
              const len = Math.sqrt(dx * dx + dy * dy);
              const cpx = mx - (dy / len) * 30;
              const cpy = my + (dx / len) * 30;

              return (
                <g key={edge.id}>
                  <path
                    d={`M${src.x},${src.y} Q${cpx},${cpy} ${tgt.x},${tgt.y}`}
                    fill="none"
                    stroke={color}
                    strokeWidth={sw}
                    strokeOpacity={opacity}
                    strokeDasharray={edge.type === 'correlative' ? '4 3' : undefined}
                    markerEnd={`url(#arrow-${edge.type})`}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredEdge(edge)}
                    onMouseLeave={() => setHoveredEdge(null)}
                  />
                  {isHovered && (
                    <text
                      x={cpx}
                      y={cpy - 6}
                      textAnchor="middle"
                      fontSize="9"
                      fill={color}
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}

            {filteredNodes.map((node) => {
              if (!node.x || !node.y) return null;
              const color = getNodeColor(node);
              const r = getNodeRadius(node);
              const isSelected = selectedNode?.id === node.id;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x},${node.y})`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedNode(isSelected ? null : node)}
                >
                  {isSelected && (
                    <circle
                      r={r + 6}
                      fill="none"
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray="4 2"
                      opacity={0.7}
                    />
                  )}
                  {node.live && (
                    <circle
                      r={r + 4}
                      fill="none"
                      stroke="#22c55e"
                      strokeWidth={1.5}
                      opacity={0.85}
                      data-testid={`live-ring-${node.id}`}
                    >
                      <animate
                        attributeName="r"
                        values={`${r + 4};${r + 9};${r + 4}`}
                        dur="1.6s"
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="opacity"
                        values="0.85;0.2;0.85"
                        dur="1.6s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}
                  <circle
                    r={r}
                    fill={`color-mix(in srgb, ${color} ${node.type === 'domain' ? 25 : 15}%, #0f1117)`}
                    stroke={color}
                    strokeWidth={node.type === 'domain' ? 2 : 1.5}
                    opacity={isSelected ? 1 : 0.9}
                  />
                  {node.live && <title>Live: real-time data from {node.domain} database</title>}
                  {node.type === 'signal' && <circle r={4} fill={color} opacity={0.8} />}
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={node.type === 'domain' ? '8' : '7'}
                    fontWeight={node.type === 'domain' ? 'bold' : 'normal'}
                    fill={color}
                    dy={r + 10}
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                  >
                    {node.label.length > 14 ? `${node.label.slice(0, 13)}…` : node.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {selectedNode && (
          <div
            className="absolute bottom-4 left-4 right-4 md:right-auto md:max-w-xs p-4 rounded-xl shadow-lg"
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              border: `1px solid ${getNodeColor(selectedNode)}`,
              zIndex: 20,
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span
                  className="text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                  style={{
                    color: getNodeColor(selectedNode),
                    backgroundColor: `color-mix(in srgb, ${getNodeColor(selectedNode)} 12%, transparent)`,
                  }}
                >
                  {selectedNode.type}
                </span>
                {selectedNode.live && (
                  <span
                    className="text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded inline-flex items-center gap-1"
                    style={{
                      color: '#22c55e',
                      backgroundColor: 'color-mix(in srgb, #22c55e 12%, transparent)',
                      border: '1px solid color-mix(in srgb, #22c55e 30%, transparent)',
                    }}
                    title={`Real-time data from ${selectedNode.domain} database`}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full animate-pulse"
                      style={{ backgroundColor: '#22c55e', boxShadow: '0 0 4px #22c55e' }}
                    />
                    Live
                  </span>
                )}
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-[10px]"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                ✕
              </button>
            </div>
            <div className="text-sm font-bold mb-1" style={{ color: 'var(--color-fg-primary)' }}>
              {selectedNode.label}
            </div>
            {selectedNode.description && (
              <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-fg-muted)' }}>
                {selectedNode.description}
              </p>
            )}
            {selectedNode.value !== undefined && (
              <div className="mt-2 text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                Signal strength:{' '}
                <span style={{ color: getNodeColor(selectedNode) }}>
                  {Math.round(selectedNode.value * 100)}
                </span>
              </div>
            )}
          </div>
        )}

        {hoveredEdge && !selectedNode && (
          <div
            className="absolute bottom-4 left-4 right-4 md:right-auto md:max-w-sm p-3 rounded-xl shadow-lg pointer-events-none"
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              border: `1px solid ${EDGE_COLORS[hoveredEdge.type]}`,
              zIndex: 20,
            }}
          >
            <div
              className="text-[10px] font-bold uppercase"
              style={{ color: EDGE_COLORS[hoveredEdge.type] }}
            >
              {hoveredEdge.type} · {Math.round(hoveredEdge.strength * 100)}% strength
            </div>
            <div className="text-xs mt-1" style={{ color: 'var(--color-fg-secondary)' }}>
              {hoveredEdge.description}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-4">
        <div className="flex items-center gap-3 flex-wrap">
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Edge types:
          </span>
          {Object.entries(EDGE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <div className="w-4 h-0.5" style={{ backgroundColor: color }} />
              <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                {type}
              </span>
            </div>
          ))}
        </div>
        {Object.keys(stats).length > 0 && (
          <div className="flex items-center gap-3 flex-wrap ml-auto">
            <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
              {stats.strongCorrelations} strong correlations · {stats.activeEdges} active edges
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
