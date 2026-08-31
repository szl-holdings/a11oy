import { useStandardQuery } from '@szl-holdings/api-client-react';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Card, CardContent } from '@szl-holdings/shared-ui/ui/card';
import { Progress } from '@szl-holdings/shared-ui/ui/progress';
import { AlertTriangle, CheckCircle, ClipboardCheck, Shield, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

const frameworkLabels: Record<string, string> = {
  nist_csf: 'NIST CSF',
  fedramp: 'StateRAMP',
  fisma: 'FISMA',
};

const statusColors: Record<string, string> = {
  implemented: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  partial: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  not_implemented: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
  not_applicable: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
};

const statusIcons: Record<string, any> = {
  implemented: CheckCircle,
  partial: AlertTriangle,
  not_implemented: XCircle,
  not_applicable: Shield,
};

function AnimatedProgress({ value, className }: { value: number; className?: string }) {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => setCurrent(value), 100);
    return () => clearTimeout(timer);
  }, [value]);
  return <Progress value={current} className={`${className} transition-all duration-1000`} />;
}

export default function CompliancePage() {
  const [framework] = useState<string>('nist_csf');
  const { data: controls = [], isLoading } = useStandardQuery({
    queryKey: ['compliance', framework],
    queryFn: () => api.compliance.list(framework),
  });

  const implemented = controls.filter((c: any) => c.status === 'implemented').length;
  const partial = controls.filter((c: any) => c.status === 'partial').length;
  const notImplemented = controls.filter((c: any) => c.status === 'not_implemented').length;
  const total = controls.length;
  const score = total > 0 ? Math.round(((implemented + partial * 0.5) / total) * 100) : 0;

  const categories = [...new Set(controls.map((c: any) => c.category))];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="font-display text-2xl font-bold flex items-center gap-2">
            <ClipboardCheck className="w-6 h-6 text-primary" /> Compliance Posture
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {frameworkLabels[framework] || framework} framework alignment — sourced from Readiness
            Report
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-fade-in-up stagger-1">
        <Card className="bg-card border-border hover:border-primary/20 transition-all group">
          <CardContent className="p-4 text-center">
            <div
              className="text-4xl font-bold font-display mt-2"
              style={{
                color:
                  score >= 80
                    ? 'hsl(var(--chart-4))'
                    : score >= 50
                      ? 'hsl(var(--chart-3))'
                      : 'hsl(var(--chart-2))',
              }}
            >
              {score}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">Overall Score</p>
            <AnimatedProgress value={score} className="h-2 mt-2" />
          </CardContent>
        </Card>
        <Card className="bg-card border-border hover:border-[#c9b787]/20 transition-all group">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Implemented</p>
              <p className="text-2xl font-bold font-display mt-1 text-[#c9b787]">{implemented}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#c9b787]/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <CheckCircle className="w-5 h-5 text-[#c9b787]" />
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border hover:border-[#c9b787]/20 transition-all group">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Partial</p>
              <p className="text-2xl font-bold font-display mt-1 text-[#c9b787]">{partial}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#c9b787]/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <AlertTriangle className="w-5 h-5 text-[#c9b787]" />
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card border-border hover:border-[#f5f5f5]/20 transition-all group">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Not Implemented
              </p>
              <p className="text-2xl font-bold font-display mt-1 text-[#f5f5f5]">{notImplemented}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-[#f5f5f5]/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <XCircle className="w-5 h-5 text-[#f5f5f5]" />
            </div>
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Card key={i} className="bg-card border-border">
              <CardContent className="p-4">
                <div className="skeleton h-16 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : controls.length === 0 ? (
        <Card className="bg-card border-border border-dashed animate-fade-in-up stagger-2">
          <CardContent className="p-16 text-center">
            <ClipboardCheck className="w-8 h-8 text-muted-foreground/30 mx-auto mb-4" />
            <p className="text-muted-foreground font-medium">
              No compliance controls for {frameworkLabels[framework] || framework}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6 animate-fade-in-up stagger-2">
          {categories.map((category) => {
            const catControls = controls.filter((c: any) => c.category === category);
            const catImpl = catControls.filter((c: any) => c.status === 'implemented').length;
            const catScore =
              catControls.length > 0 ? Math.round((catImpl / catControls.length) * 100) : 0;

            return (
              <div key={category}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-display text-lg font-semibold">{category}</h2>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {catImpl}/{catControls.length} implemented
                    </span>
                    <Badge
                      variant="outline"
                      className={
                        catScore >= 80
                          ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20'
                          : catScore >= 50
                            ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20'
                            : 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20'
                      }
                    >
                      {catScore}%
                    </Badge>
                  </div>
                </div>
                <div className="space-y-2">
                  {catControls.map((control: any) => {
                    const StatusIcon = statusIcons[control.status] || Shield;
                    return (
                      <Card
                        key={control.id}
                        className="bg-card border-border hover:border-primary/20 transition-all"
                      >
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <StatusIcon
                                  className={`w-4 h-4 ${control.status === 'implemented' ? 'text-[#c9b787]' : control.status === 'partial' ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}`}
                                />
                                <span className="font-mono text-xs text-muted-foreground">
                                  {control.controlId}
                                </span>
                                <h3 className="font-semibold text-sm">{control.controlName}</h3>
                              </div>
                              {control.description && (
                                <p className="text-xs text-muted-foreground ml-6">
                                  {control.description}
                                </p>
                              )}
                              {control.evidenceNotes && (
                                <p className="text-xs text-[#c9b787]/80 ml-6 mt-1">
                                  {control.evidenceNotes}
                                </p>
                              )}
                            </div>
                            <Badge variant="outline" className={statusColors[control.status] || ''}>
                              {control.status?.replace(/_/g, ' ') ?? 'unknown'}
                            </Badge>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
