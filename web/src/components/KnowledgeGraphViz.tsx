import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

const GOLD = '#c9b787';
const GHOST = '#5e5e5e';
const TEXT = '#f5f5f5';
const DEEP = '#141414';
const BORDER = 'rgba(255,255,255,0.08)';

const VERTICAL_NODE_COLORS: Record<string, string> = {
  'lyte-revenue': '#c9b787',
  'vessels-maritime': '#6b8aad',
  'terra-real-estate': '#8fbc8f',
  'aegis-defense': '#e57373',
  'prism-counsel': '#b39ddb',
  'carlota-jo': '#ffb74d',
  'alloy-core': '#8a8a8a',
};

const VERTICAL_LABELS: Record<string, string> = {
  'lyte-revenue': 'KORA',
  'vessels-maritime': 'SEXTANT',
  'terra-real-estate': 'DOMAINE',
  'aegis-defense': 'PARAGON',
  'prism-counsel': 'Counsel',
  'carlota-jo': 'Carlota Jo',
  'alloy-core': 'Alloy',
};

const REL_COLORS: Record<string, string> = {
  SCHEDULED_AT: '#8a8a8a',
  GOVERNED_BY: GOLD,
  OWNED_BY: '#22c55e',
  SANCTIONS_CHECKED: '#f97316',
  ASSIGNED_TO: GOLD,
  OPPOSING_PARTY: '#ef4444',
  DEMURRAGE_RELATED: '#8a8a8a',
  TARGETING: '#ef4444',
  PROFILED_BY: '#8a8a8a',
  MONITORED_BY: '#22c55e',
  PARTY_TO: GOLD,
  CONTRACT_REVIEWED: GOLD,
};

interface KGEntity {
  id: string;
  label: string;
  type: string;
  vertical: string;
  properties: Record<string, string>;
  connections: { target: string; relation: string; strength: number }[];
}

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  vertical: string;
  isEntity: boolean;
  entity?: KGEntity;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  relation: string;
  strength: number;
}

interface Props {
  entities: KGEntity[];
  onSelectEntity: (entity: KGEntity | null) => void;
  selectedEntityId?: string | null;
}

export function KnowledgeGraphViz({ entities, onSelectEntity, selectedEntityId }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  const buildGraph = useCallback(() => {
    const nodeMap = new Map<string, GraphNode>();

    for (const entity of entities) {
      nodeMap.set(entity.label, {
        id: entity.id,
        label: entity.label,
        type: entity.type,
        vertical: entity.vertical,
        isEntity: true,
        entity,
      });
    }

    for (const entity of entities) {
      for (const conn of entity.connections) {
        if (!nodeMap.has(conn.target)) {
          nodeMap.set(conn.target, {
            id: `implicit-${conn.target}`,
            label: conn.target,
            type: 'Reference',
            vertical: '',
            isEntity: false,
          });
        }
      }
    }

    const nodes = Array.from(nodeMap.values());
    const links: GraphLink[] = [];

    for (const entity of entities) {
      const sourceNode = nodeMap.get(entity.label);
      if (!sourceNode) continue;
      for (const conn of entity.connections) {
        const targetNode = nodeMap.get(conn.target);
        if (!targetNode) continue;
        links.push({
          source: sourceNode,
          target: targetNode,
          relation: conn.relation,
          strength: conn.strength,
        });
      }
    }

    return { nodes, links };
  }, [entities]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height: Math.max(height, 400) });
        }
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;
    const svg = d3.select(svgEl);

    svg.selectAll('*').remove();

    const { width, height } = dimensions;
    const { nodes, links } = buildGraph();

    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', GHOST);

    defs.append('marker')
      .attr('id', 'arrowhead-highlight')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', GOLD);

    const g = svg.append('g');

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphLink>(links)
        .id(d => d.label)
        .distance(150)
        .strength(d => d.strength * 0.3))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    const linkGroup = g.append('g').attr('class', 'links');
    const linkElements = linkGroup.selectAll<SVGLineElement, GraphLink>('line')
      .data(links)
      .join('line')
      .attr('stroke', d => REL_COLORS[d.relation] ?? GHOST)
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', d => Math.max(1, d.strength * 2))
      .attr('marker-end', 'url(#arrowhead)');

    const linkLabelGroup = g.append('g').attr('class', 'link-labels');
    const linkLabels = linkLabelGroup.selectAll<SVGTextElement, GraphLink>('text')
      .data(links)
      .join('text')
      .text(d => d.relation.replace(/_/g, ' '))
      .attr('font-size', '7px')
      .attr('font-family', 'monospace')
      .attr('fill', GHOST)
      .attr('fill-opacity', 0.5)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .style('pointer-events', 'none');

    const nodeGroup = g.append('g').attr('class', 'nodes');
    const nodeElements = nodeGroup.selectAll<SVGGElement, GraphNode>('g')
      .data(nodes)
      .join('g')
      .style('cursor', d => d.isEntity ? 'pointer' : 'default');

    nodeElements.append('circle')
      .attr('r', d => d.isEntity ? 18 : 10)
      .attr('fill', d => {
        if (d.isEntity) {
          const c = VERTICAL_NODE_COLORS[d.vertical] ?? GHOST;
          return c + '25';
        }
        return `${GHOST}15`;
      })
      .attr('stroke', d => {
        if (d.isEntity) return VERTICAL_NODE_COLORS[d.vertical] ?? GHOST;
        return GHOST;
      })
      .attr('stroke-width', d => d.isEntity ? 2 : 1)
      .attr('stroke-opacity', d => d.isEntity ? 0.8 : 0.4);

    nodeElements.filter(d => d.isEntity)
      .append('text')
      .text(d => {
        const vl = VERTICAL_LABELS[d.vertical];
        return vl ? vl.charAt(0) : '?';
      })
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', '10px')
      .attr('font-family', 'monospace')
      .attr('font-weight', 'bold')
      .attr('fill', d => VERTICAL_NODE_COLORS[d.vertical] ?? GHOST)
      .style('pointer-events', 'none');

    nodeElements.append('text')
      .text(d => {
        const l = d.label;
        return l.length > 18 ? l.slice(0, 16) + '…' : l;
      })
      .attr('x', 0)
      .attr('y', d => (d.isEntity ? 18 : 10) + 12)
      .attr('text-anchor', 'middle')
      .attr('font-size', d => d.isEntity ? '9px' : '7px')
      .attr('font-family', 'monospace')
      .attr('fill', d => d.isEntity ? TEXT : GHOST)
      .attr('fill-opacity', d => d.isEntity ? 0.9 : 0.6)
      .style('pointer-events', 'none');

    nodeElements.filter(d => d.isEntity)
      .append('text')
      .text(d => d.type)
      .attr('x', 0)
      .attr('y', 40)
      .attr('text-anchor', 'middle')
      .attr('font-size', '7px')
      .attr('font-family', 'monospace')
      .attr('fill', d => VERTICAL_NODE_COLORS[d.vertical] ?? GHOST)
      .attr('fill-opacity', 0.5)
      .style('pointer-events', 'none');

    function highlightNode(selected: GraphNode | null) {
      if (!selected) {
        nodeElements.select('circle')
          .attr('stroke-opacity', d => (d as GraphNode).isEntity ? 0.8 : 0.4)
          .attr('fill-opacity', 1);
        nodeElements.selectAll<SVGTextElement, GraphNode>('text').attr('fill-opacity', d => {
          return d.isEntity !== undefined ? (d.isEntity ? 0.9 : 0.6) : 0.9;
        });
        linkElements
          .attr('stroke-opacity', 0.4)
          .attr('stroke-width', d => Math.max(1, d.strength * 2))
          .attr('marker-end', 'url(#arrowhead)');
        linkLabels.attr('fill-opacity', 0.5);
        return;
      }

      const connectedIds = new Set<string>();
      connectedIds.add(selected.label);
      for (const link of links) {
        const s = link.source as GraphNode;
        const t = link.target as GraphNode;
        if (s.label === selected.label) connectedIds.add(t.label);
        if (t.label === selected.label) connectedIds.add(s.label);
      }

      nodeElements.select('circle')
        .attr('stroke-opacity', d => connectedIds.has((d as GraphNode).label) ? 1 : 0.15)
        .attr('fill-opacity', d => connectedIds.has((d as GraphNode).label) ? 1 : 0.15);
      nodeElements.selectAll<SVGTextElement, GraphNode>('text')
        .attr('fill-opacity', d => connectedIds.has(d.label) ? 1 : 0.1);

      linkElements
        .attr('stroke-opacity', d => {
          const s = d.source as GraphNode;
          const t = d.target as GraphNode;
          return (s.label === selected.label || t.label === selected.label) ? 0.9 : 0.06;
        })
        .attr('stroke-width', d => {
          const s = d.source as GraphNode;
          const t = d.target as GraphNode;
          return (s.label === selected.label || t.label === selected.label)
            ? Math.max(2, d.strength * 3)
            : Math.max(1, d.strength * 2);
        })
        .attr('marker-end', d => {
          const s = d.source as GraphNode;
          const t = d.target as GraphNode;
          return (s.label === selected.label || t.label === selected.label)
            ? 'url(#arrowhead-highlight)'
            : 'url(#arrowhead)';
        });

      linkLabels.attr('fill-opacity', d => {
        const s = d.source as GraphNode;
        const t = d.target as GraphNode;
        return (s.label === selected.label || t.label === selected.label) ? 1 : 0.05;
      });
    }

    nodeElements.on('click', (event, d) => {
      event.stopPropagation();
      if (d.isEntity && d.entity) {
        const isSame = selectedEntityId === d.entity.id;
        onSelectEntity(isSame ? null : d.entity);
        highlightNode(isSame ? null : d);
      }
    });

    svg.on('click', () => {
      onSelectEntity(null);
      highlightNode(null);
    });

    const drag = d3.drag<SVGGElement, GraphNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    nodeElements.call(drag);

    simulation.on('tick', () => {
      linkElements
        .attr('x1', d => (d.source as GraphNode).x!)
        .attr('y1', d => (d.source as GraphNode).y!)
        .attr('x2', d => (d.target as GraphNode).x!)
        .attr('y2', d => (d.target as GraphNode).y!);

      linkLabels
        .attr('x', d => ((d.source as GraphNode).x! + (d.target as GraphNode).x!) / 2)
        .attr('y', d => ((d.source as GraphNode).y! + (d.target as GraphNode).y!) / 2);

      nodeElements.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    if (selectedEntityId) {
      const sel = nodes.find(n => n.id === selectedEntityId);
      if (sel) highlightNode(sel);
    }

    return () => {
      simulation.stop();
    };
  }, [dimensions, buildGraph, selectedEntityId, onSelectEntity]);

  const uniqueVerticals = [...new Set(entities.map(e => e.vertical))];

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={containerRef}
        className="relative rounded-xl border overflow-hidden"
        style={{
          backgroundColor: DEEP,
          borderColor: BORDER,
          minHeight: 420,
        }}
      >
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          style={{ display: 'block' }}
        />

        <div
          className="absolute top-3 left-3 flex flex-col gap-1 p-2 rounded-lg"
          style={{ backgroundColor: 'rgba(20,20,20,0.85)', border: `1px solid ${BORDER}` }}
        >
          <div className="text-[8px] font-mono uppercase tracking-widest mb-1" style={{ color: GHOST }}>
            DOMAINS
          </div>
          {uniqueVerticals.map(v => (
            <div key={v} className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: VERTICAL_NODE_COLORS[v] ?? GHOST }}
              />
              <span className="text-[8px] font-mono" style={{ color: VERTICAL_NODE_COLORS[v] ?? GHOST }}>
                {VERTICAL_LABELS[v] ?? v}
              </span>
            </div>
          ))}
          <div className="flex items-center gap-1.5 mt-1" style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 4 }}>
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: GHOST, opacity: 0.4 }}
            />
            <span className="text-[8px] font-mono" style={{ color: GHOST }}>
              Reference
            </span>
          </div>
        </div>

        <div
          className="absolute bottom-3 right-3 p-2 rounded-lg"
          style={{ backgroundColor: 'rgba(20,20,20,0.85)', border: `1px solid ${BORDER}` }}
        >
          <div className="text-[8px] font-mono" style={{ color: GHOST }}>
            Scroll to zoom · Drag to pan · Click node for details
          </div>
        </div>
      </div>
    </div>
  );
}
