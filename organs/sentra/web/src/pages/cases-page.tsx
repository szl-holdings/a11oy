import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { EmptyState } from '@szl-holdings/shared-ui/EmptyState';
import {
  OperationalAuditTimeline,
  OperationalOwnerChip,
} from '@szl-holdings/shared-ui/operational-primitives';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Input } from '@szl-holdings/shared-ui/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@szl-holdings/shared-ui/ui/select';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Briefcase,
  Calendar,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  FileText,
  Filter,
  Plus,
  Search,
  Shield,
  User,
  XCircle,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { TradecraftPanel } from '@/components/tradecraft-panel';
import { api } from '@/lib/api';

interface CaseNote {
  content: string;
  author: string;
  at: string;
}
interface TraceBundleNode {
  id: string;
  name?: string | null;
  hopDistance?: number | null;
  domain?: string | null;
  entityType?: string | null;
}
interface TraceBundleEdge {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  relationshipType?: string;
}
interface TraceBundle {
  origin?: { id: string; name?: string | null };
  nodes?: TraceBundleNode[];
  edges?: TraceBundleEdge[];
  depth?: number;
}
interface ConstellationTraceEvidence {
  source?: 'constellation_graph';
  origin?: {
    id: string;
    name?: string | null;
    entityType?: string;
    domain?: string;
    canonicalId?: string | null;
  };
  hostDomain?: string;
  hopCount?: number;
  nodeCount?: number;
  edgeCount?: number;
  truncated?: boolean;
  generatedAt?: string;
  bundle?: TraceBundle | unknown;
}

/**
 * Renders a small radial preview of a constellation_trace bundle. Origin sits
 * at the centre and neighbours are placed on concentric rings keyed by
 * `hopDistance` so operators can recognise the shape of the trace at a glance
 * without opening the full Constellation canvas.
 */
function TraceMiniGraph({ bundle }: { bundle: TraceBundle }) {
  const width = 240;
  const height = 120;
  const cx = width / 2;
  const cy = height / 2;
  const ringStep = 22;

  const layout = useMemo(() => {
    const nodes = (bundle.nodes ?? []).filter((n) => n?.id);
    if (nodes.length === 0) return null;
    const originId = bundle.origin?.id ?? nodes[0]?.id;
    const byRing = new Map<number, TraceBundleNode[]>();
    for (const n of nodes) {
      const hop = n.id === originId ? 0 : Math.max(1, Math.min(4, n.hopDistance ?? 1));
      const list = byRing.get(hop) ?? [];
      list.push(n);
      byRing.set(hop, list);
    }
    const positions = new Map<string, { x: number; y: number; hop: number }>();
    for (const [hop, ringNodes] of byRing.entries()) {
      if (hop === 0) {
        for (const n of ringNodes) positions.set(n.id, { x: cx, y: cy, hop });
        continue;
      }
      const r = ringStep * hop;
      const count = ringNodes.length;
      ringNodes.forEach((n, i) => {
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
        positions.set(n.id, { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r, hop });
      });
    }
    const edges = (bundle.edges ?? []).filter(
      (e) => positions.has(e.fromNodeId) && positions.has(e.toNodeId),
    );
    const maxHop = Math.max(0, ...Array.from(byRing.keys()));
    return { positions, edges, maxHop, originId };
  }, [bundle]);

  if (!layout) return null;

  const ringColors = ['#c9b787', '#22d3ee', '#8a8a8a', '#c9b787', '#f5f5f5'];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-label={`Trace preview · ${layout.positions.size} nodes`}
      data-testid="case-evidence-trace-minigraph"
      style={{ display: 'block' }}
    >
      {Array.from({ length: layout.maxHop }, (_, i) => i + 1).map((hop) => (
        <circle
          key={`ring-${hop}`}
          cx={cx}
          cy={cy}
          r={ringStep * hop}
          fill="none"
          stroke="rgba(251, 191, 36, 0.08)"
          strokeDasharray="2 3"
        />
      ))}
      {layout.edges.map((e) => {
        const from = layout.positions.get(e.fromNodeId)!;
        const to = layout.positions.get(e.toNodeId)!;
        return (
          <line
            key={e.id}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            stroke="rgba(251, 191, 36, 0.35)"
            strokeWidth={0.7}
          />
        );
      })}
      {Array.from(layout.positions.entries()).map(([id, pos]) => {
        const isOrigin = id === layout.originId;
        const color = ringColors[Math.min(pos.hop, ringColors.length - 1)] ?? '#c9b787';
        return (
          <circle
            key={id}
            cx={pos.x}
            cy={pos.y}
            r={isOrigin ? 4 : 2.4}
            fill={color}
            stroke={isOrigin ? '#fff' : 'rgba(10,13,20,0.9)'}
            strokeWidth={isOrigin ? 1.2 : 0.6}
          />
        );
      })}
    </svg>
  );
}
type EvidenceItem = {
  name: string;
  type: string;
  url?: string;
  addedAt: string;
} & ConstellationTraceEvidence;
interface AuditEntry {
  action: string;
  user: string;
  at: string;
}

interface Case {
  id: number;
  caseNumber: string;
  title: string;
  description?: string | null;
  status: string;
  priority: string;
  assignedAnalyst?: string | null;
  relatedIncidentIds?: number[];
  relatedFindingIds?: number[];
  slaTriage: number;
  slaResolve: number;
  triagedAt?: string | null;
  resolvedAt?: string | null;
  notes?: CaseNote[];
  evidence?: EvidenceItem[];
  auditTrail?: AuditEntry[];
  createdAt: string;
  updatedAt: string;
}

const priorityConfig: Record<string, { label: string; color: string; dot: string }> = {
  p1_critical: {
    label: 'P1 Critical',
    color: 'bg-[#f5f5f5]/15 text-[#f5f5f5] border-[#f5f5f5]/30',
    dot: 'bg-[#f5f5f5] animate-pulse',
  },
  p2_high: {
    label: 'P2 High',
    color: 'bg-[#c9b787]/15 text-[#c9b787] border-[#c9b787]/30',
    dot: 'bg-[#c9b787]',
  },
  p3_medium: {
    label: 'P3 Medium',
    color: 'bg-[#c9b787]/15 text-[#c9b787] border-[#c9b787]/30',
    dot: 'bg-[#c9b787]',
  },
  p4_low: {
    label: 'P4 Low',
    color: 'bg-[#c9b787]/15 text-[#c9b787] border-[#c9b787]/30',
    dot: 'bg-[#c9b787]',
  },
};

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  open: {
    label: 'Open',
    color: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
    icon: AlertTriangle,
  },
  in_progress: {
    label: 'In Progress',
    color: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
    icon: Activity,
  },
  pending_review: {
    label: 'Pending Review',
    color: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
    icon: Clock,
  },
  resolved: {
    label: 'Resolved',
    color: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
    icon: CheckCircle,
  },
  closed: {
    label: 'Closed',
    color: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    icon: XCircle,
  },
};

function SLAIndicator({ case: c }: { case: Case }) {
  const now = Date.now();
  const created = new Date(c.createdAt).getTime();
  const elapsedMinutes = (now - created) / 60000;

  const triageBreached = !c.triagedAt && elapsedMinutes > c.slaTriage;
  const resolveBreached = !c.resolvedAt && c.status !== 'closed' && elapsedMinutes > c.slaResolve;
  const triagePct = c.triagedAt ? 100 : Math.min((elapsedMinutes / c.slaTriage) * 100, 100);
  const resolvePct =
    c.resolvedAt || c.status === 'closed'
      ? 100
      : Math.min((elapsedMinutes / c.slaResolve) * 100, 100);

  return (
    <div className="space-y-2">
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">
            Triage SLA
          </span>
          <span
            className={cn(
              'text-[9px] font-mono',
              c.triagedAt ? 'text-[#c9b787]' : triageBreached ? 'text-[#f5f5f5]' : 'text-[#c9b787]',
            )}
          >
            {c.triagedAt
              ? 'Met'
              : triageBreached
                ? `Breached +${Math.round(elapsedMinutes - c.slaTriage)}m`
                : `${Math.round(c.slaTriage - elapsedMinutes)}m left`}
          </span>
        </div>
        <div className="h-1.5 bg-border rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              c.triagedAt ? 'bg-[#c9b787]' : triageBreached ? 'bg-[#f5f5f5]' : 'bg-[#c9b787]',
            )}
            style={{ width: `${triagePct}%` }}
          />
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">
            Resolve SLA
          </span>
          <span
            className={cn(
              'text-[9px] font-mono',
              c.resolvedAt || c.status === 'closed'
                ? 'text-[#c9b787]'
                : resolveBreached
                  ? 'text-[#f5f5f5]'
                  : 'text-[#c9b787]',
            )}
          >
            {c.resolvedAt || c.status === 'closed'
              ? 'Met'
              : resolveBreached
                ? `Breached +${Math.round(elapsedMinutes - c.slaResolve)}m`
                : `${Math.round(c.slaResolve - elapsedMinutes)}m left`}
          </span>
        </div>
        <div className="h-1.5 bg-border rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              c.resolvedAt || c.status === 'closed'
                ? 'bg-[#c9b787]'
                : resolveBreached
                  ? 'bg-[#f5f5f5]'
                  : 'bg-[#c9b787]',
            )}
            style={{ width: `${resolvePct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function CaseDetailPanel({
  caseItem,
  onClose,
  onUpdate,
}: {
  caseItem: Case;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const qc = useQueryClient();
  const [noteText, setNoteText] = useState('');
  const [newStatus, setNewStatus] = useState(caseItem.status);

  const updateMutation = useStandardMutation({
    mutationFn: (data: any) => api.cases.update(caseItem.id, data),
    onSuccess: () => {
      toast.success('Case updated');
      qc.invalidateQueries({ queryKey: ['aegis-cases'] });
      onUpdate();
    },
    onError: () => toast.error('Failed to update case'),
  });

  const handleAddNote = () => {
    if (!noteText.trim()) return;
    updateMutation.mutate({ note: { content: noteText, author: 'Analyst' } });
    setNoteText('');
  };

  const handleStatusUpdate = () => {
    if (newStatus !== caseItem.status) {
      updateMutation.mutate({ status: newStatus });
    }
  };

  const pc = priorityConfig[caseItem.priority];
  const sc = statusConfig[caseItem.status];
  const StatusIcon = sc.icon;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-[#0A0D14] border-l border-white/10 h-full w-full max-w-2xl overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-white/10 sticky top-0 bg-[#0A0D14] z-10">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono text-muted-foreground/60">
                  {caseItem.caseNumber}
                </span>
                <Badge variant="outline" className={cn('text-[9px]', pc.color)}>
                  {pc.label}
                </Badge>
                <Badge variant="outline" className={cn('text-[9px]', sc.color)}>
                  <StatusIcon className="w-2.5 h-2.5 mr-1" />
                  {sc.label}
                </Badge>
              </div>
              <h2 className="font-display text-base font-bold text-foreground leading-snug">
                {caseItem.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {caseItem.description && (
            <p className="text-sm text-muted-foreground leading-relaxed">{caseItem.description}</p>
          )}

          <div className="bg-white/5 rounded-xl p-4 space-y-3">
            <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              SLA Status
            </div>
            <SLAIndicator case={caseItem} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider mb-1.5">
                Assigned Analyst
              </div>
              <OperationalOwnerChip
                owner={
                  caseItem.assignedAnalyst
                    ? { name: caseItem.assignedAnalyst, role: 'Analyst' }
                    : undefined
                }
                unassignedLabel="Unassigned"
              />
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider mb-1">
                Created
              </div>
              <div className="flex items-center gap-1.5 text-xs text-foreground">
                <Calendar className="w-3 h-3 text-muted-foreground" />
                {new Date(caseItem.createdAt).toLocaleDateString()}
              </div>
            </div>
          </div>

          {(caseItem.relatedIncidentIds?.length ?? 0) > 0 && (
            <div>
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2">
                Linked Incidents
              </div>
              <div className="flex flex-wrap gap-1.5">
                {caseItem.relatedIncidentIds?.map((id) => (
                  <Badge
                    key={id}
                    variant="outline"
                    className="text-[9px] bg-[#f5f5f5]/5 text-[#f5f5f5]/70 border-[#f5f5f5]/20"
                  >
                    INC-{id}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2">
              Update Status
            </div>
            <div className="flex gap-2">
              <Select value={newStatus} onValueChange={setNewStatus}>
                <SelectTrigger className="flex-1 h-8 text-xs bg-background border-border">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(statusConfig).map(([val, cfg]) => (
                    <SelectItem key={val} value={val} className="text-xs">
                      {cfg.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                size="sm"
                variant="outline"
                onClick={handleStatusUpdate}
                disabled={newStatus === caseItem.status || updateMutation.isPending}
              >
                Update
              </Button>
            </div>
          </div>

          <div>
            <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2">
              Case Notes ({caseItem.notes?.length ?? 0})
            </div>
            <div className="space-y-2 mb-3">
              {(caseItem.notes ?? []).map((note, i) => (
                <div key={i} className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono text-muted-foreground/70">
                      {note.author}
                    </span>
                    <span className="text-[9px] text-muted-foreground/50">
                      {new Date(note.at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-xs text-foreground/80">{note.content}</p>
                </div>
              ))}
              {(caseItem.notes?.length ?? 0) === 0 && (
                <p className="text-xs text-muted-foreground/50 italic">No notes yet</p>
              )}
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="Add analyst note..."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleAddNote()}
                className="flex-1 h-8 text-xs bg-background border-border"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={handleAddNote}
                disabled={!noteText.trim() || updateMutation.isPending}
              >
                Add
              </Button>
            </div>
          </div>

          {(caseItem.evidence?.length ?? 0) > 0 && (
            <div>
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2">
                Evidence ({caseItem.evidence?.length ?? 0} items)
              </div>
              <div className="space-y-1.5">
                {caseItem.evidence?.map((item, i) => {
                  const isTrace =
                    item.type === 'constellation_trace' || item.source === 'constellation_graph';
                  if (isTrace) {
                    const bundle = item.bundle as TraceBundle | undefined;
                    const hasGraph =
                      !!bundle && Array.isArray(bundle.nodes) && bundle.nodes.length > 0;
                    const originId = bundle?.origin?.id ?? item.origin?.id ?? null;
                    const depthForLink = bundle?.depth ?? item.hopCount ?? 2;
                    const constellationHref = originId
                      ? `/aegis/constellation?origin=${encodeURIComponent(originId)}&depth=${encodeURIComponent(String(depthForLink))}`
                      : null;
                    const downloadBundle = () => {
                      if (!item.bundle) return;
                      const blob = new Blob([JSON.stringify(item.bundle, null, 2)], {
                        type: 'application/json',
                      });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = item.name;
                      document.body.appendChild(a);
                      a.click();
                      document.body.removeChild(a);
                      setTimeout(() => URL.revokeObjectURL(url), 1000);
                    };
                    return (
                      <div
                        key={i}
                        data-testid="case-evidence-constellation-trace"
                        className="px-3 py-2.5 bg-[#c9b787]/5 border border-[#c9b787]/20 rounded-lg"
                      >
                        <div className="flex items-start gap-2">
                          <Activity className="w-3 h-3 text-[#c9b787] shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-medium text-foreground/90 truncate">
                                {item.name}
                              </span>
                              <Badge
                                variant="outline"
                                className="text-[9px] bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30 shrink-0"
                              >
                                Constellation trace
                              </Badge>
                            </div>
                            <div className="mt-1 text-[10px] font-mono text-muted-foreground/80 leading-relaxed">
                              <div>
                                <span className="text-muted-foreground/60">Origin:</span>{' '}
                                <span className="text-foreground/80">
                                  {item.origin?.name ?? item.origin?.id ?? 'Unknown'}
                                </span>
                                {item.origin?.entityType && (
                                  <span className="text-muted-foreground/60">
                                    {' '}
                                    · {item.origin.entityType}
                                  </span>
                                )}
                                {(item.origin?.domain ?? item.hostDomain) && (
                                  <span className="text-muted-foreground/60">
                                    {' '}
                                    · {item.origin?.domain ?? item.hostDomain}
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-x-3 mt-0.5">
                                <span>{item.hopCount ?? 0} hops</span>
                                <span>{item.nodeCount ?? 0} nodes</span>
                                <span>{item.edgeCount ?? 0} edges</span>
                                {item.truncated && (
                                  <span className="text-[#c9b787]">truncated</span>
                                )}
                              </div>
                              <div className="text-muted-foreground/50 mt-0.5">
                                Attached {new Date(item.addedAt).toLocaleString()}
                              </div>
                            </div>
                          </div>
                          <div className="flex flex-col gap-1.5 shrink-0">
                            {Boolean(item.bundle) && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={downloadBundle}
                                data-testid="case-evidence-trace-download"
                                className="h-6 px-2 text-[10px] border-[#c9b787]/30 text-[#c9b787] hover:bg-[#c9b787]/10"
                              >
                                JSON
                              </Button>
                            )}
                            {constellationHref && (
                              <a
                                href={constellationHref}
                                target="_blank"
                                rel="noreferrer"
                                data-testid="case-evidence-trace-open-constellation"
                                className="inline-flex items-center gap-1 h-6 px-2 rounded-md border border-[#c9b787]/30 bg-[#c9b787]/5 text-[#c9b787] text-[10px] font-medium hover:bg-[#c9b787]/10 transition-colors"
                              >
                                <ExternalLink className="w-2.5 h-2.5" />
                                Open in Constellation
                              </a>
                            )}
                          </div>
                        </div>
                        {hasGraph && bundle && (
                          <div className="mt-2 rounded-md border border-[#c9b787]/15 bg-black/30 px-2 py-1.5">
                            <TraceMiniGraph bundle={bundle} />
                          </div>
                        )}
                      </div>
                    );
                  }
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg"
                    >
                      <FileText className="w-3 h-3 text-muted-foreground shrink-0" />
                      <span className="text-xs text-foreground/80 flex-1 truncate">
                        {item.name}
                      </span>
                      <Badge
                        variant="outline"
                        className="text-[9px] bg-[#c9b787]/5 text-[#c9b787]/70 border-[#c9b787]/20 shrink-0"
                      >
                        {item.type}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <TradecraftPanel caseId={String(caseItem.id)} title="Tradecraft Analysis" />

          {(caseItem.auditTrail?.length ?? 0) > 0 && (
            <div>
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2">
                Audit Trail
              </div>
              <OperationalAuditTimeline
                entries={[...(caseItem.auditTrail ?? [])].reverse().map((entry, i) => ({
                  id: String(i),
                  action: entry.action,
                  actor: entry.user,
                  actorType: 'user' as const,
                  timestamp: entry.at,
                }))}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CasesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data: cases = [], isLoading } = useStandardQuery<Case[]>({
    queryKey: ['aegis-cases'],
    queryFn: () => api.cases.list(),
    refetchInterval: 30000,
  });

  const filtered = useMemo(() => {
    return cases.filter((c) => {
      if (
        search &&
        !c.title.toLowerCase().includes(search.toLowerCase()) &&
        !c.caseNumber.toLowerCase().includes(search.toLowerCase())
      )
        return false;
      if (statusFilter !== 'all' && c.status !== statusFilter) return false;
      if (priorityFilter !== 'all' && c.priority !== priorityFilter) return false;
      return true;
    });
  }, [cases, search, statusFilter, priorityFilter]);

  const stats = useMemo(
    () => ({
      total: cases.length,
      open: cases.filter((c) => ['open', 'in_progress'].includes(c.status)).length,
      p1: cases.filter(
        (c) => c.priority === 'p1_critical' && !['resolved', 'closed'].includes(c.status),
      ).length,
      slaBreached: cases.filter((c) => {
        if (c.resolvedAt || c.status === 'closed') return false;
        const elapsed = (Date.now() - new Date(c.createdAt).getTime()) / 60000;
        return elapsed > c.slaResolve;
      }).length,
      resolved: cases.filter((c) => ['resolved', 'closed'].includes(c.status)).length,
    }),
    [cases],
  );

  const handleCaseRefresh = () => {
    qc.invalidateQueries({ queryKey: ['aegis-cases'] });
    if (selectedCase) {
      const updated = cases.find((c) => c.id === selectedCase.id);
      if (updated) setSelectedCase(updated);
    }
  };

  // Deep-link support: when a tool (e.g. the Constellation attach-to-case
  // success card) opens /aegis/cases?case=<id>, auto-select that case so the
  // operator lands directly on its detail panel. We consume the query param
  // once on first match so closing the panel doesn't immediately re-open it.
  const [deepLinkConsumed, setDeepLinkConsumed] = useState(false);
  useEffect(() => {
    if (deepLinkConsumed || typeof window === 'undefined' || cases.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('case');
    if (!requested) {
      setDeepLinkConsumed(true);
      return;
    }
    const id = Number(requested);
    if (!Number.isFinite(id)) {
      setDeepLinkConsumed(true);
      return;
    }
    const match = cases.find((c) => c.id === id);
    if (match) {
      setSelectedCase(match);
      setDeepLinkConsumed(true);
      params.delete('case');
      const qs = params.toString();
      const newUrl = window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash;
      window.history.replaceState(null, '', newUrl);
    }
  }, [cases, deepLinkConsumed]);

  return (
    <div className="p-5 space-y-5">
      {selectedCase && (
        <CaseDetailPanel
          caseItem={selectedCase}
          onClose={() => setSelectedCase(null)}
          onUpdate={handleCaseRefresh}
        />
      )}

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[9px] font-mono text-[#f5f5f5]/50 uppercase tracking-widest">
              PARAGON / Cases
            </span>
            <span className="text-[#f5f5f5]/20">·</span>
            <span className="text-[9px] font-mono text-muted-foreground/40 uppercase tracking-widest">
              Case Management
            </span>
          </div>
          <h1 className="font-display text-xl font-bold flex items-center gap-2.5">
            <Briefcase className="w-5 h-5 text-[#f5f5f5]" />
            Case Management
          </h1>
          <p className="text-[11px] text-muted-foreground mt-1">
            Security cases with SLA tracking, analyst assignment, and evidence chain-of-custody
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="border-[#f5f5f5]/20 text-[#f5f5f5] hover:bg-[#f5f5f5]/10 hover:text-[#f5f5f5] shrink-0"
        >
          <Plus className="w-3.5 h-3.5 mr-1.5" />
          New Case
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Total Cases', value: stats.total, color: 'text-foreground' },
          { label: 'Active', value: stats.open, color: 'text-[#f5f5f5]' },
          { label: 'P1 Critical', value: stats.p1, color: 'text-[#f5f5f5]' },
          {
            label: 'SLA Breached',
            value: stats.slaBreached,
            color: stats.slaBreached > 0 ? 'text-[#f5f5f5]' : 'text-[#c9b787]',
          },
          { label: 'Resolved/Closed', value: stats.resolved, color: 'text-[#c9b787]' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-card border border-border rounded-xl p-4">
            <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider mb-1">
              {label}
            </div>
            <div className={cn('text-2xl font-bold font-display', color)}>{value}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-40">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <Input
            placeholder="Search cases..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-xs bg-background border-border"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-36 h-8 text-xs bg-background border-border">
            <Filter className="w-3 h-3 mr-1.5" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-xs">
              All Status
            </SelectItem>
            {Object.entries(statusConfig).map(([val, cfg]) => (
              <SelectItem key={val} value={val} className="text-xs">
                {cfg.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={priorityFilter} onValueChange={setPriorityFilter}>
          <SelectTrigger className="w-36 h-8 text-xs bg-background border-border">
            <Filter className="w-3 h-3 mr-1.5" />
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-xs">
              All Priority
            </SelectItem>
            {Object.entries(priorityConfig).map(([val, cfg]) => (
              <SelectItem key={val} value={val} className="text-xs">
                {cfg.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="divide-y divide-border/50">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-[#f5f5f5]/40 border-t-red-400 rounded-full animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            cases.length === 0 ? (
              <EmptyState
                icon={CheckCircle}
                headline="No open cases"
                description="The case queue is clear — every reported issue has been triaged or resolved."
                accentColor="#c9b787"
                compact
              />
            ) : (
              <EmptyState
                icon={Filter}
                headline="No cases match these filters"
                description="Try widening the search, status, or priority filter to see other cases."
                accentColor="#8b7ac8"
                action={{
                  label: 'Reset filters',
                  onClick: () => {
                    setSearch('');
                    setStatusFilter('all');
                    setPriorityFilter('all');
                  },
                }}
                compact
              />
            )
          ) : (
            filtered.map((c) => {
              const pc = priorityConfig[c.priority];
              const sc = statusConfig[c.status];
              const StatusIcon = sc.icon;
              const isExpanded = expandedId === c.id;
              const now = Date.now();
              const elapsed = (now - new Date(c.createdAt).getTime()) / 60000;
              const slaBreached = !c.resolvedAt && c.status !== 'closed' && elapsed > c.slaResolve;

              return (
                <div
                  key={c.id}
                  className={cn('transition-colors', slaBreached && 'border-l-2 border-[#f5f5f5]')}
                >
                  <div
                    className="px-5 py-3.5 hover:bg-muted/5 cursor-pointer"
                    onClick={() => setSelectedCase(c)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn('w-2 h-2 rounded-full shrink-0', pc.dot)} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                          <span className="text-[10px] font-mono text-muted-foreground/70">
                            {c.caseNumber}
                          </span>
                          <Badge variant="outline" className={cn('text-[9px]', pc.color)}>
                            {pc.label}
                          </Badge>
                          <Badge variant="outline" className={cn('text-[9px]', sc.color)}>
                            <StatusIcon className="w-2.5 h-2.5 mr-1" />
                            {sc.label}
                          </Badge>
                          {slaBreached && (
                            <Badge
                              variant="outline"
                              className="text-[9px] bg-[#f5f5f5]/15 text-[#f5f5f5] border-[#f5f5f5]/30 animate-pulse"
                            >
                              SLA Breached
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm font-medium text-foreground leading-snug">
                          {c.title}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 text-[10px] text-muted-foreground">
                        {c.assignedAnalyst && (
                          <div className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            <span>{c.assignedAnalyst}</span>
                          </div>
                        )}
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(c.createdAt).toLocaleDateString()}</span>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedId(isExpanded ? null : c.id);
                          }}
                          className="p-1 rounded hover:bg-white/10 transition-colors"
                        >
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="px-5 pb-4 border-t border-border/40 bg-muted/5">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3">
                        <div className="space-y-2">
                          {c.description && (
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              {c.description}
                            </p>
                          )}
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-[10px] h-7"
                              onClick={() => setSelectedCase(c)}
                            >
                              <Shield className="w-3 h-3 mr-1" /> Open Case
                            </Button>
                          </div>
                        </div>
                        <SLAIndicator case={c} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
