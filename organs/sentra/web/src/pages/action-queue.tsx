// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { EmptyState } from '@szl-holdings/shared-ui/EmptyState';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { useRealtimeChannel } from '@szl-holdings/shared-ui/use-realtime-channel';
import { useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowUpRight,
  Bell,
  CheckCircle,
  Clock,
  RefreshCw,
  Shield,
  Target,
  User,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { LiveDataBadge } from '@/lib/live-badge';
import { api } from '../lib/api';

type ActionQueuePriority = 'critical' | 'high' | 'medium' | 'low';
type ActionQueueStatus = 'open' | 'in_progress' | 'blocked' | 'escalated' | 'completed';

interface ActionCreatedPayload {
  id: string;
  title: string;
  description?: string;
  priority: ActionQueuePriority;
  status: ActionQueueStatus;
  assignedTo?: string | null;
  dueDate?: string | null;
  incidentId?: string | null;
  source?: string;
  createdAt: string;
}

interface AuditEntry {
  actor: string;
  action: string;
  at: string;
  note?: string;
}

interface ActionQueueItem {
  id: string;
  title: string;
  description: string;
  priority: ActionQueuePriority;
  status: ActionQueueStatus;
  assignedTo?: string;
  dueDate?: string;
  dueAt?: string;
  type?: string;
  blocker?: string;
  incidentId?: string;
  auditTrail: AuditEntry[];
  completedAt?: string;
  createdAt: string;
}

const ACCENT = 'hsl(220 72% 56%)';
const ACCENT_DIM = 'hsl(220 72% 40%)';

function relTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return `${Math.ceil(Math.abs(diff) / 86400000)}d overdue`;
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
function isDue(iso?: string) {
  return iso ? new Date(iso).getTime() < Date.now() : false;
}

const PRIORITY_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  critical: { color: '#f5f5f5', bg: '#5e5e5e10', border: '#5e5e5e40' },
  high: { color: '#c04a2a', bg: '#c04a2a08', border: '#c04a2a25' },
  medium: { color: '#c08a2c', bg: '#c08a2c08', border: '#c08a2c20' },
  low: {
    color: 'rgba(255,255,255,0.4)',
    bg: 'rgba(255,255,255,0.02)',
    border: 'rgba(255,255,255,0.06)',
  },
};

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  open: { color: '#c04a2a', bg: '#c04a2a20' },
  in_progress: { color: '#c08a2c', bg: '#c08a2c20' },
  blocked: { color: '#f5f5f5', bg: '#5e5e5e20' },
  completed: { color: '#40856a', bg: '#40856a20' },
};

const TYPE_ICONS: Record<string, React.ElementType> = {
  containment: Shield,
  remediation: Target,
  investigation: AlertTriangle,
  governance: User,
  communication: User,
};

function ActionCard({
  item,
  onComplete,
  onEscalate,
  completing,
  escalating,
}: {
  item: ActionQueueItem;
  onComplete: (id: string) => void;
  onEscalate: (id: string) => void;
  completing: boolean;
  escalating: boolean;
}) {
  const ps = PRIORITY_STYLE[item.priority] ?? PRIORITY_STYLE.low;
  const ss = STATUS_STYLE[item.status] ?? STATUS_STYLE.open;
  const overdue = isDue(item.dueDate) && item.status !== 'completed';
  const Icon = (item.type ? TYPE_ICONS[item.type] : null) ?? AlertTriangle;

  return (
    <div
      className="rounded-xl border p-4 transition-all"
      style={{ background: ps.bg, borderColor: overdue ? '#c04a2a40' : ps.border }}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg" style={{ background: `${ps.color}15` }}>
            <Icon size={12} style={{ color: ps.color }} />
          </div>
          <div>
            <div className="text-sm font-semibold" style={{ color: 'rgba(255,255,255,0.88)' }}>
              {item.title}
            </div>
            <div className="text-xs mt-0.5 capitalize" style={{ color: 'rgba(255,255,255,0.35)' }}>
              {item.type} action
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-xs px-2 py-0.5 rounded-full capitalize"
            style={{ background: ss.bg, color: ss.color }}
          >
            {item.status.replace('_', ' ')}
          </span>
          <span
            className="text-xs px-2 py-0.5 rounded-full capitalize"
            style={{ background: ps.bg, color: ps.color, border: `1px solid ${ps.border}` }}
          >
            {item.priority}
          </span>
        </div>
      </div>

      <p className="text-sm mb-3" style={{ color: 'rgba(255,255,255,0.5)' }}>
        {item.description}
      </p>

      {item.blocker && (
        <div
          className="flex items-center gap-1.5 text-xs mb-3 px-3 py-2 rounded-lg"
          style={{ background: '#5e5e5e10', border: '1px solid #5e5e5e30' }}
        >
          <AlertTriangle size={12} style={{ color: '#f5f5f5' }} />
          <span style={{ color: '#f5f5f5' }}>Blocked: {item.blocker}</span>
        </div>
      )}

      <div
        className="flex items-center gap-3 text-xs mb-3"
        style={{ color: 'rgba(255,255,255,0.3)' }}
      >
        {item.assignedTo && (
          <span className="flex items-center gap-1">
            <User size={10} />
            {item.assignedTo}
          </span>
        )}
        {item.dueDate && (
          <span
            className="flex items-center gap-1"
            style={{ color: overdue ? '#c04a2a' : 'rgba(255,255,255,0.3)' }}
          >
            <Clock size={10} />
            {overdue ? 'Overdue: ' : 'Due: '}
            {relTime(item.dueDate)}
          </span>
        )}
      </div>

      {item.auditTrail && item.auditTrail.length > 0 && (
        <div className="text-[10px] mb-3" style={{ color: 'rgba(255,255,255,0.2)' }}>
          Last action: {item.auditTrail[item.auditTrail.length - 1]?.action?.replace(/_/g, ' ')} by{' '}
          {item.auditTrail[item.auditTrail.length - 1]?.actor} ·{' '}
          {relTime(item.auditTrail[item.auditTrail.length - 1]?.at)}
        </div>
      )}

      {item.status !== 'completed' && (
        <div className="flex gap-2">
          <button
            onClick={() => onComplete(item.id)}
            disabled={completing}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium disabled:opacity-50"
            style={{ background: ACCENT_DIM, color: 'white' }}
          >
            {completing ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : (
              <CheckCircle size={12} />
            )}
            {completing ? 'Executing...' : 'Execute & Complete'}
          </button>
          <button
            onClick={() => onEscalate(item.id)}
            disabled={escalating}
            className="text-xs px-3 py-1.5 rounded-lg hover:bg-white/5 disabled:opacity-50"
            style={{ border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.4)' }}
          >
            <ArrowUpRight size={12} className="inline mr-1" />
            Escalate
          </button>
        </div>
      )}

      {item.status === 'completed' && item.completedAt && (
        <div className="text-[10px]" style={{ color: '#40856a' }}>
          <CheckCircle size={10} className="inline mr-1" />
          Completed {relTime(item.completedAt)}
        </div>
      )}
    </div>
  );
}

export default function ActionQueue() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState('open');
  const [activeAction, setActiveAction] = useState<{
    id: string;
    type: 'complete' | 'escalate';
  } | null>(null);

  const queueQuery = useStandardQuery({
    queryKey: ['action-queue'],
    queryFn: () => api.actionQueue.list(),
    refetchInterval: 15000,
  });

  const [liveAlert, setLiveAlert] = useState<ActionCreatedPayload | null>(null);
  const [newCount, setNewCount] = useState(0);
  const liveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seenIdsRef = useRef<Set<string>>(new Set());

  const { lastMessage, isConnected, status } =
    useRealtimeChannel<ActionCreatedPayload>('aegis-incidents');

  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.event !== 'action-created') return;
    const payload = lastMessage.data;
    if (!payload?.id || seenIdsRef.current.has(payload.id)) return;
    seenIdsRef.current.add(payload.id);

    qc.invalidateQueries({ queryKey: ['action-queue'] });
    setNewCount((c) => c + 1);

    const isUrgent = payload.priority === 'critical' || payload.status === 'blocked';
    if (isUrgent) {
      setLiveAlert(payload);
      if (liveTimerRef.current) clearTimeout(liveTimerRef.current);
      liveTimerRef.current = setTimeout(() => setLiveAlert(null), 12000);
      toast.error(
        `${payload.priority === 'critical' ? 'Critical' : 'Blocked'} action: ${payload.title}`,
        {
          description: payload.description,
          action: {
            label: 'View',
            onClick: () => {
              setFilter(payload.status === 'blocked' ? 'blocked' : 'open');
              setNewCount(0);
            },
          },
        },
      );
    } else {
      toast.success(`New action queued: ${payload.title}`);
    }
  }, [lastMessage, qc]);

  useEffect(() => {
    return () => {
      if (liveTimerRef.current) clearTimeout(liveTimerRef.current);
    };
  }, []);

  const dismissNewBadge = () => setNewCount(0);

  const completeMutation = useStandardMutation({
    mutationFn: (id: string) => api.actionQueue.complete(id, 'Executed via Action Queue'),
    onSuccess: (data: { data?: { message?: string } }) => {
      qc.invalidateQueries({ queryKey: ['action-queue'] });
      toast.success(data?.data?.message ?? 'Action completed — outcome recorded in audit trail');
      setActiveAction(null);
    },
    onError: () => {
      toast.error('Failed to complete action');
      setActiveAction(null);
    },
  });

  const escalateMutation = useStandardMutation({
    mutationFn: (id: string) => api.actionQueue.escalate(id),
    onSuccess: (data: { data?: { message?: string } }) => {
      qc.invalidateQueries({ queryKey: ['action-queue'] });
      toast.success(data?.data?.message ?? 'Action escalated');
      setActiveAction(null);
    },
    onError: () => {
      toast.error('Failed to escalate action');
      setActiveAction(null);
    },
  });

  const queueData = (
    queueQuery.data as {
      data?: {
        items?: ActionQueueItem[];
        openCount?: number;
        blockedCount?: number;
        overdueCount?: number;
        completedCount?: number;
      };
    } | null
  )?.data;
  const items: ActionQueueItem[] = queueData?.items ?? [];
  const openCount: number = queueData?.openCount ?? 0;
  const blockedCount: number = queueData?.blockedCount ?? 0;
  const overdueCount: number = queueData?.overdueCount ?? 0;
  const completedCount: number = queueData?.completedCount ?? 0;

  const displayed = items.filter(
    (a) =>
      filter === 'all' ||
      (filter === 'open' && a.status !== 'completed') ||
      a.status === filter ||
      a.priority === filter,
  );

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'rgba(255,255,255,0.95)' }}>
            Action Queue
          </h1>
          <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
            Pending containment, remediation, investigation, and governance actions — all executions
            recorded in audit trail
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LiveDataBadge
            isLive={isConnected}
            isLoading={status === 'reconnecting'}
            label={isConnected ? 'Live' : status === 'reconnecting' ? 'Reconnecting' : 'Offline'}
          />
          {newCount > 0 && (
            <button
              onClick={() => {
                dismissNewBadge();
                qc.invalidateQueries({ queryKey: ['action-queue'] });
              }}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-colors"
              style={{
                background: 'hsl(220 72% 56% / 0.15)',
                color: ACCENT,
                border: '1px solid hsl(220 72% 56% / 0.4)',
              }}
              title="Dismiss and refresh"
            >
              <Bell size={12} className="animate-pulse" /> {newCount} new
            </button>
          )}
          {blockedCount > 0 && (
            <span
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full"
              style={{ background: '#5e5e5e20', color: '#f5f5f5', border: '1px solid #5e5e5e40' }}
            >
              <AlertTriangle size={12} /> {blockedCount} blocked
            </span>
          )}
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ['action-queue'] })}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/5 transition-colors"
          >
            <RefreshCw size={14} className={queueQuery.isFetching ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {liveAlert && (
        <div
          className="mb-4 rounded-xl border p-4 flex items-start gap-3"
          style={{
            background: liveAlert.priority === 'critical' ? '#5e5e5e12' : '#c08a2c12',
            borderColor: liveAlert.priority === 'critical' ? '#5e5e5e50' : '#c08a2c50',
          }}
        >
          <div
            className="p-2 rounded-lg flex-shrink-0"
            style={{ background: liveAlert.priority === 'critical' ? '#5e5e5e25' : '#c08a2c25' }}
          >
            <AlertTriangle
              size={16}
              style={{ color: liveAlert.priority === 'critical' ? '#f5f5f5' : '#c9b787' }}
              className="animate-pulse"
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded"
                style={{
                  background: liveAlert.priority === 'critical' ? '#5e5e5e30' : '#c08a2c30',
                  color: liveAlert.priority === 'critical' ? '#f5f5f5' : '#c9b787',
                }}
              >
                {liveAlert.priority === 'critical' ? 'Critical' : 'Blocked'} · New
              </span>
              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                just now
              </span>
            </div>
            <div className="text-sm font-semibold" style={{ color: 'rgba(255,255,255,0.95)' }}>
              {liveAlert.title}
            </div>
            {liveAlert.description && (
              <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.55)' }}>
                {liveAlert.description}
              </div>
            )}
            <button
              onClick={() => {
                setFilter(liveAlert.status === 'blocked' ? 'blocked' : 'open');
                dismissNewBadge();
                setLiveAlert(null);
              }}
              className="text-xs mt-2 inline-flex items-center gap-1 hover:underline"
              style={{ color: ACCENT }}
            >
              Jump to action <ArrowUpRight size={11} />
            </button>
          </div>
          <button
            onClick={() => setLiveAlert(null)}
            className="p-1 rounded hover:bg-white/5 flex-shrink-0"
            style={{ color: 'rgba(255,255,255,0.4)' }}
            aria-label="Dismiss alert"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Open', value: openCount, color: '#c04a2a' },
          { label: 'Blocked', value: blockedCount, color: '#f5f5f5' },
          { label: 'Overdue', value: overdueCount, color: '#c08a2c' },
          { label: 'Completed', value: completedCount, color: '#40856a' },
        ].map((m) => (
          <div
            key={m.label}
            className="rounded-xl border p-4"
            style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.06)' }}
          >
            <div className="text-xs mb-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
              {m.label}
            </div>
            <div className="text-2xl font-bold" style={{ color: m.color }}>
              {queueQuery.isLoading ? <span className="text-zinc-500 text-base">—</span> : m.value}
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 mb-5">
        {['open', 'blocked', 'in_progress', 'completed', 'all'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="text-xs px-3 py-1 rounded-lg capitalize transition-colors"
            style={{
              background: filter === f ? 'hsl(220 72% 56% / 0.12)' : 'rgba(255,255,255,0.04)',
              color: filter === f ? ACCENT : 'rgba(255,255,255,0.4)',
              border: `1px solid ${filter === f ? 'hsl(220 72% 56% / 0.3)' : 'rgba(255,255,255,0.06)'}`,
            }}
          >
            {f.replace('_', ' ')}
          </button>
        ))}
      </div>

      {queueQuery.isLoading ? (
        <div className="text-center py-12 text-zinc-500 text-sm">Loading action queue…</div>
      ) : (
        <div className="space-y-3">
          {displayed.length === 0 ? (
            <EmptyState
              icon={CheckCircle}
              headline="No actions"
              description="No actions match the current filter."
              accentColor={ACCENT}
            />
          ) : (
            displayed.map((a: ActionQueueItem) => (
              <ActionCard
                key={a.id}
                item={a}
                onComplete={(id) => {
                  setActiveAction({ id, type: 'complete' });
                  completeMutation.mutate(id);
                }}
                onEscalate={(id) => {
                  setActiveAction({ id, type: 'escalate' });
                  escalateMutation.mutate(id);
                }}
                completing={
                  activeAction?.id === a.id &&
                  activeAction?.type === 'complete' &&
                  completeMutation.isPending
                }
                escalating={
                  activeAction?.id === a.id &&
                  activeAction?.type === 'escalate' &&
                  escalateMutation.isPending
                }
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
