// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { type AutonomyMode, ProofEnvelope } from '@szl-holdings/design-system';
import { AnimatedCounter } from '@szl-holdings/shared-ui/animated-counter';
import { EmptyState } from '@szl-holdings/shared-ui/design-system';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Card, CardContent } from '@szl-holdings/shared-ui/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@szl-holdings/shared-ui/ui/dialog';
import { Input } from '@szl-holdings/shared-ui/ui/input';
import { Label } from '@szl-holdings/shared-ui/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@szl-holdings/shared-ui/ui/select';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { Textarea } from '@szl-holdings/shared-ui/ui/textarea';
import { useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Bell, CheckCircle, Eye, Plus, XCircle } from 'lucide-react';
import { useState } from 'react';
import { api } from '@/lib/api';

const severityColors: Record<string, string> = {
  critical: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
  high: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  medium: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  low: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
};

const _statusColors: Record<string, string> = {
  new: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
  acknowledged: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  investigating: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  resolved: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  dismissed: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
};

export default function AlertsPage() {
  const qc = useQueryClient();
  const { data: alerts = [], isLoading } = useStandardQuery({
    queryKey: ['alerts'],
    queryFn: () => api.alerts.list(),
  });
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('all');
  const [autonomyMode, setAutonomyMode] = useState<AutonomyMode>('ask-to-act');
  const [form, setForm] = useState({
    title: '',
    description: '',
    severity: 'medium',
    source: 'manual',
    relatedCve: '',
  });

  const createMut = useStandardMutation({
    mutationFn: (data: any) => api.alerts.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
      setOpen(false);
      toast.success('Alert created');
    },
    onError: (e: any) => toast.error(e.message),
  });

  const updateMut = useStandardMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => api.alerts.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
      toast.success('Alert updated');
    },
  });

  const filtered = filter === 'all' ? alerts : alerts.filter((a: any) => a.status === filter);
  const newCount = alerts.filter((a: any) => a.status === 'new').length;
  const criticalCount = alerts.filter(
    (a: any) => a.severity === 'critical' && a.status !== 'resolved' && a.status !== 'dismissed',
  ).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="font-display text-2xl font-bold flex items-center gap-2">
            <Bell className="w-6 h-6 text-primary" /> Alert Center
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Correlated alerts with severity triage, acknowledgment, and escalation rules
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="w-4 h-4 mr-2" /> Create Alert
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-card border-border">
            <DialogHeader>
              <DialogTitle className="font-display">New Alert</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Title</Label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="e.g. Critical CVE detected in production"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Severity</Label>
                  <Select
                    value={form.severity}
                    onValueChange={(v) => setForm((p) => ({ ...p, severity: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Source</Label>
                  <Select
                    value={form.source}
                    onValueChange={(v) => setForm((p) => ({ ...p, source: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="manual">Manual</SelectItem>
                      <SelectItem value="threat_intel">Threat Intel</SelectItem>
                      <SelectItem value="risk_threshold">Risk Threshold</SelectItem>
                      <SelectItem value="incident_escalation">Incident Escalation</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Related CVE</Label>
                <Input
                  value={form.relatedCve}
                  onChange={(e) => setForm((p) => ({ ...p, relatedCve: e.target.value }))}
                  placeholder="e.g. CVE-2024-12345"
                />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  rows={3}
                  placeholder="Alert details..."
                />
              </div>
              <Button
                onClick={() => {
                  if (!form.title) {
                    toast.error('Title required');
                    return;
                  }
                  createMut.mutate(form);
                }}
                disabled={createMut.isPending}
                className="w-full"
              >
                {createMut.isPending ? 'Creating...' : 'Create Alert'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-fade-in-up stagger-1">
        <Card className="bg-card border-border hover:border-primary/20 transition-all group">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Total</p>
              <p className="text-2xl font-bold font-display mt-1">
                <AnimatedCounter value={alerts.length} />
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Bell className="w-5 h-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        <Card
          className={`bg-card border-border hover:border-[#f5f5f5]/20 transition-all group ${newCount > 0 ? 'ring-1 ring-red-500/10' : ''}`}
        >
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">New</p>
              <p
                className={`text-2xl font-bold font-display mt-1 ${newCount > 0 ? 'text-[#f5f5f5] animate-threat-pulse' : ''}`}
              >
                <AnimatedCounter value={newCount} />
              </p>
            </div>
            <div
              className={`w-10 h-10 rounded-lg bg-[#f5f5f5]/10 flex items-center justify-center group-hover:scale-110 transition-transform ${newCount > 0 ? 'animate-pulse' : ''}`}
            >
              <AlertTriangle className="w-5 h-5 text-[#f5f5f5]" />
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border hover:border-[#c9b787]/20 transition-all group">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Critical</p>
              <p className="text-2xl font-bold font-display mt-1 text-[#c9b787]">
                <AnimatedCounter value={criticalCount} />
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#c9b787]/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <XCircle className="w-5 h-5 text-[#c9b787]" />
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border hover:border-[#c9b787]/20 transition-all group">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Resolved</p>
              <p className="text-2xl font-bold font-display mt-1 text-[#c9b787]">
                <AnimatedCounter
                  value={alerts.filter((a: any) => a.status === 'resolved').length}
                />
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#c9b787]/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <CheckCircle className="w-5 h-5 text-[#c9b787]" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center gap-2 flex-wrap animate-fade-in-up stagger-2">
        {['all', 'new', 'acknowledged', 'investigating', 'resolved', 'dismissed'].map((status) => (
          <Button
            key={status}
            variant={filter === status ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(status)}
          >
            {status === 'all'
              ? `All (${alerts.length})`
              : `${status.charAt(0).toUpperCase() + status.slice(1)} (${alerts.filter((a: any) => a.status === status).length})`}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i} className="bg-card border-border">
              <CardContent className="p-4">
                <div className="skeleton h-16 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={filter === 'all' ? CheckCircle : Bell}
          headline={filter === 'all' ? 'No active alerts' : `No ${filter} alerts`}
          description={
            filter === 'all'
              ? 'Alert thresholds are met — the environment is clean. New correlated alerts will appear here as soon as they trigger.'
              : `No alerts currently sit in ${filter} status. Switch filter to “All” to see the full alert queue.`
          }
          accentColor={filter === 'all' ? '#c9b787' : '#8b7ac8'}
          className="animate-fade-in-up stagger-3 border border-dashed border-border rounded-lg"
        />
      ) : (
        <div className="space-y-3 animate-fade-in-up stagger-3">
          {filtered.map((alert: any) => {
            const isCritical =
              alert.severity === 'critical' &&
              alert.status !== 'resolved' &&
              alert.status !== 'dismissed';
            const severityToPolicy = (s: string): 'allowed' | 'requires-approval' | 'blocked' =>
              s === 'critical'
                ? 'requires-approval'
                : s === 'high'
                  ? 'requires-approval'
                  : 'allowed';
            const severityToConfidence: Record<string, number> = {
              critical: 92,
              high: 85,
              medium: 72,
              low: 60,
            };
            const accentByLevel: Record<string, string> = {
              critical: '#f5f5f5',
              high: '#c9b787',
              medium: '#8a8a8a',
              low: '#c9b787',
            };
            return (
              <ProofEnvelope
                key={alert.id}
                title={alert.title}
                timestamp={alert.createdAt}
                confidence={severityToConfidence[alert.severity] ?? 70}
                policyState={severityToPolicy(alert.severity)}
                policyReason={
                  isCritical
                    ? 'Critical alerts require SOC lead acknowledgment before automated response'
                    : undefined
                }
                autonomyMode={autonomyMode}
                onAutonomyChange={setAutonomyMode}
                accentColor={accentByLevel[alert.severity] ?? '#8b7ac8'}
                evidence={[
                  {
                    id: String(alert.id),
                    label: alert.source?.replace('_', ' ') ?? 'PARAGON Engine',
                    type: 'signal',
                    timestamp: alert.createdAt,
                    excerpt: alert.description,
                  },
                  ...(alert.relatedCve
                    ? [
                        {
                          id: `${alert.id}-cve`,
                          label: alert.relatedCve,
                          type: 'api' as const,
                          excerpt: `CVE reference associated with this alert`,
                        },
                      ]
                    : []),
                ]}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    {alert.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                        {alert.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Badge
                      variant="outline"
                      className={`${severityColors[alert.severity] || ''} ${isCritical ? 'animate-threat-pulse' : ''}`}
                    >
                      {alert.severity}
                    </Badge>
                    {alert.status === 'new' && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() =>
                          updateMut.mutate({ id: alert.id, data: { status: 'acknowledged' } })
                        }
                      >
                        <Eye className="w-3 h-3 mr-1" /> Acknowledge
                      </Button>
                    )}
                    <Select
                      value={alert.status}
                      onValueChange={(v) => updateMut.mutate({ id: alert.id, data: { status: v } })}
                    >
                      <SelectTrigger className="w-36 h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="new">New</SelectItem>
                        <SelectItem value="acknowledged">Acknowledged</SelectItem>
                        <SelectItem value="investigating">Investigating</SelectItem>
                        <SelectItem value="resolved">Resolved</SelectItem>
                        <SelectItem value="dismissed">Dismissed</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </ProofEnvelope>
            );
          })}
        </div>
      )}
    </div>
  );
}
