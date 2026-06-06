// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { AnimatedCounter } from '@szl-holdings/shared-ui/animated-counter';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@szl-holdings/shared-ui/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@szl-holdings/shared-ui/ui/dialog';
import { Input } from '@szl-holdings/shared-ui/ui/input';
import { Label } from '@szl-holdings/shared-ui/ui/label';
import { Progress } from '@szl-holdings/shared-ui/ui/progress';
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
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  Loader2 as LoaderIcon,
  Plus,
  Shield,
  ShieldAlert,
  Target,
  Trash2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { AegisGraphQLPanel } from '@/components/graphql-data-panel';
import { api } from '@/lib/api';

const statusColors: Record<string, string> = {
  draft: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  in_progress: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  completed: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  archived: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
};

function AnimatedProgress({ value, className }: { value: number; className?: string }) {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => setCurrent(value), 100);
    return () => clearTimeout(timer);
  }, [value]);
  return <Progress value={current} className={`${className} transition-all duration-1000`} />;
}

function StatCardSkeleton() {
  return (
    <Card className="bg-card border-border">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="skeleton h-3 w-24" />
            <div className="skeleton h-7 w-12" />
          </div>
          <div className="skeleton w-10 h-10 rounded-lg" />
        </div>
      </CardContent>
    </Card>
  );
}

function AssessmentSkeleton() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="skeleton h-5 w-40" />
          <div className="skeleton h-5 w-20 rounded-full" />
        </div>
        <div className="skeleton h-3 w-56 mt-2" />
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-2 w-full rounded-full" />
        <div className="skeleton h-3 w-48" />
      </CardContent>
    </Card>
  );
}

async function downloadAssessmentPDF(
  assessment: Record<string, unknown>,
  findings: unknown[],
): Promise<void> {
  const res = await fetch('/api/documents/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template: 'aegis-assessment-report',
      data: { assessment, findings },
    }),
  });
  if (!res.ok) throw new Error('PDF generation failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `aegis-assessment-${(assessment.id as number) || 'report'}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AssessmentDashboard() {
  const qc = useQueryClient();
  const { data: assessments = [], isLoading } = useStandardQuery({
    queryKey: ['assessments'],
    queryFn: api.assessments.list,
  });
  const { data: findings = [] } = useStandardQuery({
    queryKey: ['findings'],
    queryFn: () => api.findings.list(),
  });
  const { data: simulations = [] } = useStandardQuery({
    queryKey: ['simulations'],
    queryFn: api.simulations.list,
  });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '',
    assessmentType: 'penetration_test' as string,
    scope: '',
    targetEnvironment: '',
    description: '',
  });
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const createMut = useStandardMutation({
    mutationFn: (data: any) => api.assessments.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessments'] });
      setOpen(false);
      toast.success('Assessment created');
    },
    onError: (e: any) => toast.error(e.message),
  });

  const deleteMut = useStandardMutation({
    mutationFn: (id: number) => api.assessments.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessments'] });
      toast.success('Assessment deleted');
    },
  });

  const criticalFindings = findings.filter((f: any) => f.severity === 'critical');
  const activeAssessments = assessments.filter((a: any) => a.status === 'in_progress');

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="font-display text-2xl font-bold">Assessment Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Active engagements, finding severity, and assessment completion pipeline
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="w-4 h-4 mr-2" /> New Assessment
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-card border-border">
            <DialogHeader>
              <DialogTitle className="font-display">Create Assessment</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="e.g. Q1 Network Assessment"
                />
              </div>
              <div>
                <Label>Type</Label>
                <Select
                  value={form.assessmentType}
                  onValueChange={(v) => setForm((p) => ({ ...p, assessmentType: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="penetration_test">Penetration Test</SelectItem>
                    <SelectItem value="vulnerability_scan">Vulnerability Scan</SelectItem>
                    <SelectItem value="red_team">Red Team</SelectItem>
                    <SelectItem value="blue_team">Blue Team</SelectItem>
                    <SelectItem value="purple_team">Purple Team</SelectItem>
                    <SelectItem value="tabletop">Tabletop</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Scope</Label>
                <Input
                  value={form.scope}
                  onChange={(e) => setForm((p) => ({ ...p, scope: e.target.value }))}
                  placeholder="e.g. Internal network, Web apps"
                />
              </div>
              <div>
                <Label>Target Environment</Label>
                <Input
                  value={form.targetEnvironment}
                  onChange={(e) => setForm((p) => ({ ...p, targetEnvironment: e.target.value }))}
                  placeholder="e.g. Corporate Network"
                />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  placeholder="Assessment objectives..."
                  rows={3}
                />
              </div>
              <Button
                onClick={() => {
                  if (!form.name) {
                    toast.error('Name required');
                    return;
                  }
                  createMut.mutate({ ...form, status: 'draft' });
                }}
                disabled={createMut.isPending}
                className="w-full"
              >
                {createMut.isPending ? 'Creating...' : 'Create Assessment'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <Card className="bg-card border-border animate-fade-in-up stagger-1 hover:border-primary/20 transition-all duration-300 group">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Total Assessments
                    </p>
                    <p className="text-2xl font-bold font-display mt-1">
                      <AnimatedCounter value={assessments.length} />
                    </p>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Shield className="w-5 h-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card
              className={`bg-card border-border animate-fade-in-up stagger-2 hover:border-chart-3/20 transition-all duration-300 group ${activeAssessments.length > 0 ? 'ring-1 ring-chart-3/10' : ''}`}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      In Progress
                    </p>
                    <p className="text-2xl font-bold font-display mt-1">
                      <AnimatedCounter value={activeAssessments.length} />
                    </p>
                  </div>
                  <div
                    className={`w-10 h-10 rounded-lg bg-chart-3/10 flex items-center justify-center group-hover:scale-110 transition-transform ${activeAssessments.length > 0 ? 'animate-pulse' : ''}`}
                  >
                    <Clock className="w-5 h-5 text-chart-3" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border animate-fade-in-up stagger-3 hover:border-chart-4/20 transition-all duration-300 group">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Total Findings
                    </p>
                    <p className="text-2xl font-bold font-display mt-1">
                      <AnimatedCounter value={findings.length} />
                    </p>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-chart-4/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Target className="w-5 h-5 text-chart-4" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card
              className={`bg-card border-border animate-fade-in-up stagger-4 hover:border-chart-2/20 transition-all duration-300 group ${criticalFindings.length > 0 ? 'ring-1 ring-chart-2/20' : ''}`}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Critical
                    </p>
                    <p
                      className={`text-2xl font-bold font-display mt-1 ${criticalFindings.length > 0 ? 'text-chart-2 animate-threat-pulse' : ''}`}
                    >
                      <AnimatedCounter value={criticalFindings.length} />
                    </p>
                  </div>
                  <div
                    className={`w-10 h-10 rounded-lg bg-chart-2/10 flex items-center justify-center group-hover:scale-110 transition-transform ${criticalFindings.length > 0 ? 'animate-pulse' : ''}`}
                  >
                    <AlertTriangle className="w-5 h-5 text-chart-2" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <AssessmentSkeleton key={i} />
          ))}
        </div>
      ) : assessments.length === 0 ? (
        <Card className="bg-card border-border border-dashed animate-fade-in-up stagger-5">
          <CardContent className="p-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-primary/5 flex items-center justify-center mx-auto mb-4">
              <ShieldAlert className="w-8 h-8 text-muted-foreground/30" />
            </div>
            <p className="text-muted-foreground font-medium">No assessments yet</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Create one to get started with security testing
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {assessments.map((assessment: any, i: number) => {
            const aFindings = findings.filter((f: any) => f.assessmentId === assessment.id);
            const aSims = simulations.filter((s: any) => s.assessmentId === assessment.id);
            const critCount = aFindings.filter((f: any) => f.severity === 'critical').length;
            const highCount = aFindings.filter((f: any) => f.severity === 'high').length;
            const completionPct =
              assessment.status === 'completed'
                ? 100
                : assessment.status === 'in_progress'
                  ? 65
                  : 0;
            const isInProgress = assessment.status === 'in_progress';
            const hasCritical = critCount > 0;

            return (
              <Card
                key={assessment.id}
                className={`bg-card border-border hover:border-primary/20 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/5 animate-fade-in-up stagger-${Math.min(i + 1, 8)} ${hasCritical ? 'ring-1 ring-red-500/10' : ''}`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-display">{assessment.name}</CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`${statusColors[assessment.status] || ''} ${isInProgress ? 'animate-pulse' : ''}`}
                      >
                        {isInProgress && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#c9b787] mr-1.5 animate-pulse-dot" />
                        )}
                        {assessment.status?.replace('_', ' ')}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-primary"
                        disabled={downloadingId === assessment.id}
                        onClick={async () => {
                          setDownloadingId(assessment.id);
                          try {
                            await downloadAssessmentPDF(assessment, aFindings);
                          } catch {
                            toast.error('PDF generation failed');
                          } finally {
                            setDownloadingId(null);
                          }
                        }}
                        title="Export PDF"
                      >
                        {downloadingId === assessment.id ? (
                          <LoaderIcon className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Download className="w-3.5 h-3.5" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        onClick={() => deleteMut.mutate(assessment.id)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline" className="text-xs">
                      {assessment.assessmentType?.replace('_', ' ')}
                    </Badge>
                    {assessment.scope && <span>{assessment.scope}</span>}
                    {assessment.targetEnvironment && <span>{assessment.targetEnvironment}</span>}
                  </div>
                </CardHeader>
                <CardContent className="pt-0 space-y-3">
                  {assessment.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {assessment.description}
                    </p>
                  )}
                  {completionPct > 0 && (
                    <div>
                      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                        <span>Progress</span>
                        <span>{completionPct}%</span>
                      </div>
                      <AnimatedProgress value={completionPct} className="h-1.5" />
                    </div>
                  )}
                  <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1">
                    <span className="flex items-center gap-1">
                      <Target className="w-3 h-3" /> {aFindings.length} findings
                    </span>
                    <span
                      className={`flex items-center gap-1 ${hasCritical ? 'text-[#f5f5f5] animate-threat-pulse' : ''}`}
                    >
                      <AlertTriangle className="w-3 h-3" /> {critCount} critical, {highCount} high
                    </span>
                    <span className="flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" /> {aSims.length} exercises
                    </span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <AegisGraphQLPanel />
    </div>
  );
}
