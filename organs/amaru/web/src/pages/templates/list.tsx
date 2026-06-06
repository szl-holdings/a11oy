import { useState } from 'react';
import { useLocation } from 'wouter';
import { useTemplates, useConnections, useApplyTemplate } from '@/lib/api-hooks';
import { Button, Select } from '@/components/ui';
import { LayoutTemplate, Building, Anchor, Scale, Briefcase, Zap, ArrowRight, X } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const ICON_MAP: Record<string, React.FC<{ className?: string }>> = {
  building: Building,
  anchor: Anchor,
  scale: Scale,
  briefcase: Briefcase,
  zap: Zap,
};

function TemplateIcon({ icon, className }: { icon: string; className?: string }) {
  const Comp = ICON_MAP[icon] ?? Zap;
  return <Comp className={className} />;
}

function ApplyModal({ template, onClose }: { template: { id: string; name: string }; onClose: () => void }) {
  const { data: connections = [] } = useConnections();
  const applyTemplate = useApplyTemplate();
  const [, navigate] = useLocation();
  const [connectionId, setConnectionId] = useState('');
  const [name, setName] = useState(template.name);

  const handleApply = () => {
    if (!connectionId) { toast.error('Select a connection'); return; }
    applyTemplate.mutate({ id: template.id, connectionId, name: name || undefined }, {
      onSuccess: (sync) => {
        toast.success('Template applied — sync created');
        onClose();
        navigate(`/syncs/${sync.id}`);
      },
      onError: () => toast.error('Failed to apply template'),
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="conduit-card p-6 w-full max-w-md mx-4 space-y-4 animate-scale-in">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold font-display">Apply Template</h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-muted text-muted-foreground transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-sm text-muted-foreground">Creating sync from: <strong className="text-foreground">{template.name}</strong></p>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground uppercase tracking-wider font-medium block mb-1.5">Sync Name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              placeholder="Name this sync"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground uppercase tracking-wider font-medium block mb-1.5">Connection</label>
            <Select value={connectionId} onChange={e => setConnectionId(e.target.value)}>
              <option value="">Select a connection…</option>
              {connections.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.destination})</option>
              ))}
            </Select>
            {connections.length === 0 && (
              <p className="text-xs text-muted-foreground mt-1">No connections yet. <a href="/connections/new" className="text-primary underline">Create one first.</a></p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" isLoading={applyTemplate.isPending} onClick={handleApply}>Apply Template</Button>
        </div>
      </div>
    </div>
  );
}

export default function TemplatesList() {
  const { data: templates = [], isLoading } = useTemplates();
  const [applyTarget, setApplyTarget] = useState<{ id: string; name: string } | null>(null);

  const categories = [...new Set(templates.map(t => t.category))];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold tracking-tight">Templates</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Start from a pre-built mapping configuration</p>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-48 rounded-lg skeleton-conduit" style={{ animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <div className="conduit-card p-12 text-center">
          <LayoutTemplate className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-muted-foreground">No templates available</p>
        </div>
      ) : (
        <div className="space-y-8">
          {categories.map(category => (
            <div key={category}>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-3">{category}</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {templates.filter(t => t.category === category).map((template, i) => (
                  <div
                    key={template.id}
                    className={cn("conduit-card p-5 flex flex-col gap-3 group animate-fade-in-up", `stagger-${Math.min(i + 1, 6)}`)}
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-9 h-9 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
                        <TemplateIcon icon={template.icon} className="w-4 h-4 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm leading-tight">{template.name}</div>
                        <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground font-mono">
                          <span>{template.sourceType}</span>
                          <ArrowRight className="w-3 h-3" />
                          <span>{template.destination}</span>
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-muted-foreground leading-relaxed flex-1">{template.description}</p>

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-xs text-muted-foreground">{template.mappingCount} field mappings</span>
                      <Button
                        size="sm"
                        onClick={() => setApplyTarget({ id: template.id, name: template.name })}
                        className="text-xs h-7"
                      >
                        Apply
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {applyTarget && (
        <ApplyModal template={applyTarget} onClose={() => setApplyTarget(null)} />
      )}
    </div>
  );
}
