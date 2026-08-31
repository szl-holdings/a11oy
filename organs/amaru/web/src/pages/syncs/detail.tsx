import { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'wouter';
import {
  useSync, useRunSync, useDeleteSync, useSyncMappings,
  usePutSyncMappings, useSyncRuns, useDestinationFields, usePreviewSource,
} from '@/lib/api-hooks';
import { Badge, Button, Select } from '@/components/ui';
import type { SyncMapping, MappingTransform } from '@/lib/api';
import {
  ArrowLeft, Play, Trash2, Plus, X, ArrowRight, Save,
  RefreshCw, AlertTriangle, CheckCircle2, Clock, Eye, Settings2,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

type MappingRow = { sourceField: string; destinationField: string; transform: MappingTransform; transformConfig: Record<string, unknown>; sortOrder: number };

const TRANSFORMS: Array<{ value: string; label: string }> = [
  { value: '', label: 'None' },
  { value: 'uppercase', label: 'Uppercase' },
  { value: 'lowercase', label: 'Lowercase' },
  { value: 'format_date', label: 'Format Date' },
  { value: 'json_extract', label: 'JSON Extract' },
  { value: 'constant', label: 'Constant' },
  { value: 'concat', label: 'Concat' },
];

function SyncStatusBadge({ status }: { status: string }) {
  const variant = status === 'active' ? 'active' : status === 'error' ? 'error' : status === 'paused' ? 'paused' : 'draft';
  return <Badge variant={variant}>{status}</Badge>;
}

function formatTime(iso: string | null): string {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatDuration(ms: number | null): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

type TabId = 'mappings' | 'runs' | 'config';

export default function SyncsDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? '';
  const [, navigate] = useLocation();
  const [activeTab, setActiveTab] = useState<TabId>('mappings');

  const { data: sync, isLoading, refetch } = useSync(id);
  const { data: mappings = [], isLoading: mappingsLoading } = useSyncMappings(id);
  const { data: runsData } = useSyncRuns({ syncId: id, limit: 20 });
  const runs = runsData?.data ?? [];

  const destination = sync?.connection?.destination ?? '';
  const objectType = sync?.objectType ?? '';
  const sourceType = sync?.sourceType ?? 'postgres';

  const { data: destFields = [] } = useDestinationFields(destination, objectType);
  const previewSource = usePreviewSource();
  const putMappings = usePutSyncMappings();
  const runSync = useRunSync();
  const deleteSync = useDeleteSync();

  const [localMappings, setLocalMappings] = useState<MappingRow[]>([]);
  const [sourceFields, setSourceFields] = useState<string[]>([]);
  const [sourceRows, setSourceRows] = useState<Array<Record<string, unknown>>>([]);
  const [mappingsDirty, setMappingsDirty] = useState(false);

  // Sync remote mappings → local
  useEffect(() => {
    if (mappings.length > 0 && !mappingsDirty) {
      setLocalMappings(mappings.map(m => ({
        sourceField: m.sourceField,
        destinationField: m.destinationField,
        transform: m.transform,
        transformConfig: m.transformConfig,
        sortOrder: m.sortOrder,
      })));
    }
  }, [mappings, mappingsDirty]);

  // Load source preview
  useEffect(() => {
    if (id && sourceType) {
      previewSource.mutate({ sourceType, sourceMeta: sync?.sourceMeta }, {
        onSuccess: (data) => {
          setSourceFields(data.fields);
          setSourceRows(data.rows);
        },
      });
    }
  }, [id, sourceType]);

  const handleAddMapping = () => {
    setLocalMappings(prev => [...prev, {
      sourceField: sourceFields[0] ?? '',
      destinationField: destFields[0]?.name ?? '',
      transform: null,
      transformConfig: {},
      sortOrder: prev.length,
    }]);
    setMappingsDirty(true);
  };

  const handleRemoveMapping = (idx: number) => {
    setLocalMappings(prev => prev.filter((_, i) => i !== idx));
    setMappingsDirty(true);
  };

  const handleMappingChange = (idx: number, field: Partial<MappingRow>) => {
    setLocalMappings(prev => prev.map((m, i) => i === idx ? { ...m, ...field } : m));
    setMappingsDirty(true);
  };

  const handleSaveMappings = () => {
    putMappings.mutate({ syncId: id, mappings: localMappings }, {
      onSuccess: () => { toast.success('Mappings saved'); setMappingsDirty(false); },
      onError: () => toast.error('Failed to save mappings'),
    });
  };

  const handleRun = () => {
    runSync.mutate(id, {
      onSuccess: () => { toast.success('Sync triggered — run started'); refetch(); },
      onError: () => toast.error('Failed to trigger sync'),
    });
  };

  const handleDelete = () => {
    if (!confirm('Delete this sync and all its runs? This cannot be undone.')) return;
    deleteSync.mutate(id, {
      onSuccess: () => { toast.success('Sync deleted'); navigate('/syncs'); },
      onError: () => toast.error('Failed to delete sync'),
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 rounded skeleton-conduit" />
        <div className="h-24 rounded-lg skeleton-conduit" />
        <div className="h-96 rounded-lg skeleton-conduit" />
      </div>
    );
  }

  if (!sync) {
    return (
      <div className="conduit-card p-12 text-center">
        <p className="text-muted-foreground">Sync not found.</p>
        <Link href="/syncs"><Button variant="outline" size="sm" className="mt-4">Back to Syncs</Button></Link>
      </div>
    );
  }

  const tabs: Array<{ id: TabId; label: string }> = [
    { id: 'mappings', label: 'Field Mappings' },
    { id: 'runs', label: `Run History (${runs.length})` },
    { id: 'config', label: 'Configuration' },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link href="/syncs">
          <button className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors mt-0.5">
            <ArrowLeft className="w-4 h-4" />
          </button>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-display font-bold tracking-tight">{sync.name}</h1>
            <SyncStatusBadge status={sync.status} />
          </div>
          <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground font-mono">
            <span>{sync.sourceType}</span>
            <ArrowRight className="w-3 h-3" />
            <span>{sync.connection?.destination ?? sync.connectionId}</span>
            <span className="mx-1 text-border">·</span>
            <span>{sync.objectType}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button size="sm" variant="outline" onClick={handleDelete} className="text-rose-400 border-rose-400/20 hover:bg-rose-400/10 hover:border-rose-400/30">
            <Trash2 className="w-4 h-4" />
          </Button>
          <Button size="sm" isLoading={runSync.isPending} onClick={handleRun}>
            <Play className="w-4 h-4 mr-1.5" />
            Run Now
          </Button>
        </div>
      </div>

      {/* Last run status */}
      {sync.lastRunAt && (
        <div className={cn(
          "conduit-card px-4 py-3 flex items-center gap-3 text-sm",
          sync.lastRunStatus === 'success' && "border-green-500/20",
          sync.lastRunStatus === 'failed' && "border-rose-500/20",
          sync.lastRunStatus === 'partial' && "border-orange-500/20",
        )}>
          {sync.lastRunStatus === 'success' && <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />}
          {sync.lastRunStatus === 'failed' && <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />}
          {sync.lastRunStatus === 'partial' && <AlertTriangle className="w-4 h-4 text-orange-400 shrink-0" />}
          {(!sync.lastRunStatus || sync.lastRunStatus === 'running') && <Clock className="w-4 h-4 text-muted-foreground shrink-0" />}
          <span className="text-muted-foreground">Last run: <span className="text-foreground">{sync.lastRunStatus}</span> &mdash; {formatTime(sync.lastRunAt)}</span>
          {sync.lastRunId && (
            <Link href={`/runs/${sync.lastRunId}`} className="ml-auto text-primary text-xs hover:underline">View run</Link>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-border flex gap-0">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ─── Mappings Tab ─────────────────────────────────────────────────────── */}
      {activeTab === 'mappings' && (
        <div className="space-y-4">
          <div className="grid grid-cols-5 gap-4">
            {/* Source preview */}
            <div className="col-span-2 conduit-card overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Source Fields</span>
                <span className="ml-auto text-xs text-muted-foreground">{sourceType}</span>
              </div>
              <div className="overflow-auto max-h-[420px]">
                {previewSource.isPending ? (
                  <div className="p-4 space-y-2">
                    {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-7 rounded skeleton-conduit" />)}
                  </div>
                ) : sourceFields.length === 0 ? (
                  <div className="p-6 text-center text-xs text-muted-foreground">No fields loaded</div>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border bg-muted/30">
                        <th className="px-3 py-2 text-left text-muted-foreground font-medium">Field</th>
                        <th className="px-3 py-2 text-left text-muted-foreground font-medium">Sample</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {sourceFields.map(f => (
                        <tr key={f} className="hover:bg-muted/20">
                          <td className="px-3 py-2 font-mono text-primary">{f}</td>
                          <td className="px-3 py-2 text-muted-foreground font-mono truncate max-w-[80px]">
                            {String(sourceRows[0]?.[f] ?? '').slice(0, 20)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Mapping editor */}
            <div className="col-span-5 md:col-span-3 conduit-card overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border flex items-center gap-2">
                <Settings2 className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Field Mappings</span>
                <span className="ml-auto text-xs text-muted-foreground">{localMappings.length} rows</span>
              </div>

              <div className="overflow-auto max-h-[380px]">
                {mappingsLoading ? (
                  <div className="p-4 space-y-2">
                    {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-10 rounded skeleton-conduit" />)}
                  </div>
                ) : localMappings.length === 0 ? (
                  <div className="p-8 text-center">
                    <ArrowRight className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-40" />
                    <p className="text-xs text-muted-foreground">No mappings yet. Add a row to begin mapping fields.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {/* Header row */}
                    <div className="grid grid-cols-[1fr_24px_1fr_90px_32px] gap-2 px-3 py-2 text-xs text-muted-foreground uppercase tracking-wider font-medium bg-muted/20">
                      <div>Source Field</div>
                      <div></div>
                      <div>Destination Field</div>
                      <div>Transform</div>
                      <div></div>
                    </div>
                    {localMappings.map((m, idx) => (
                      <div key={idx} className="grid grid-cols-[1fr_24px_1fr_90px_32px] gap-2 px-3 py-2 items-center hover:bg-muted/10 transition-colors">
                        <Select
                          value={m.sourceField}
                          onChange={e => handleMappingChange(idx, { sourceField: e.target.value })}
                          className="text-xs h-8"
                        >
                          {sourceFields.map(f => <option key={f} value={f}>{f}</option>)}
                          {!sourceFields.includes(m.sourceField) && m.sourceField && (
                            <option value={m.sourceField}>{m.sourceField}</option>
                          )}
                        </Select>
                        <ArrowRight className="w-3.5 h-3.5 text-muted-foreground mx-auto shrink-0" />
                        <Select
                          value={m.destinationField}
                          onChange={e => handleMappingChange(idx, { destinationField: e.target.value })}
                          className="text-xs h-8"
                        >
                          {destFields.map(f => <option key={f.name} value={f.name}>{f.label}{f.required ? ' *' : ''}</option>)}
                          {!destFields.find(f => f.name === m.destinationField) && m.destinationField && (
                            <option value={m.destinationField}>{m.destinationField}</option>
                          )}
                        </Select>
                        <Select
                          value={m.transform ?? ''}
                          onChange={e => handleMappingChange(idx, { transform: (e.target.value || null) as MappingTransform })}
                          className="text-xs h-8"
                        >
                          {TRANSFORMS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </Select>
                        <button
                          onClick={() => handleRemoveMapping(idx)}
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-rose-400 transition-colors"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="px-3 py-2.5 border-t border-border flex items-center gap-2">
                <Button size="sm" variant="ghost" onClick={handleAddMapping} className="text-xs gap-1">
                  <Plus className="w-3.5 h-3.5" />
                  Add Row
                </Button>
                <div className="ml-auto flex items-center gap-2">
                  {mappingsDirty && (
                    <span className="text-xs text-yellow-400">Unsaved changes</span>
                  )}
                  <Button
                    size="sm"
                    isLoading={putMappings.isPending}
                    disabled={!mappingsDirty}
                    onClick={handleSaveMappings}
                    className="text-xs gap-1"
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save Mappings
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Destination fields reference */}
          {destFields.length > 0 && (
            <div className="conduit-card overflow-hidden">
              <div className="px-4 py-2 border-b border-border text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {destination} / {objectType} — Available Fields
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/30">
                      <th className="px-4 py-2 text-left text-muted-foreground">Field Name</th>
                      <th className="px-4 py-2 text-left text-muted-foreground">Label</th>
                      <th className="px-4 py-2 text-left text-muted-foreground">Type</th>
                      <th className="px-4 py-2 text-left text-muted-foreground">Required</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {destFields.map(f => (
                      <tr key={f.name} className="hover:bg-muted/10">
                        <td className="px-4 py-1.5 font-mono text-primary">{f.name}</td>
                        <td className="px-4 py-1.5 text-foreground">{f.label}</td>
                        <td className="px-4 py-1.5 text-muted-foreground font-mono">{f.type}</td>
                        <td className="px-4 py-1.5">
                          {f.required ? <span className="text-rose-400">Yes</span> : <span className="text-muted-foreground">No</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── Runs Tab ─────────────────────────────────────────────────────────── */}
      {activeTab === 'runs' && (
        <div className="space-y-2">
          {runs.length === 0 ? (
            <div className="conduit-card p-10 text-center">
              <Clock className="w-9 h-9 text-muted-foreground mx-auto mb-3 opacity-40" />
              <p className="text-sm text-muted-foreground">No runs yet. Click "Run Now" to trigger the first sync.</p>
            </div>
          ) : runs.map((run, i) => (
            <Link key={run.id} href={`/runs/${run.id}`}>
              <div className={cn("conduit-card px-4 py-3 flex items-center gap-4 cursor-pointer hover:border-primary/20 group animate-fade-in-up", `stagger-${Math.min(i + 1, 6)}`)}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'failed' : run.status === 'running' ? 'running' : run.status === 'partial' ? 'partial' : 'default'}>
                      {run.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground font-mono">{formatTime(run.startedAt)}</span>
                    {run.durationMs != null && <span className="text-xs text-muted-foreground font-mono">{formatDuration(run.durationMs)}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-6 text-xs text-right">
                  <div><span className="text-muted-foreground mr-1">Read</span><span className="font-mono">{run.rowsRead.toLocaleString()}</span></div>
                  <div><span className="text-muted-foreground mr-1">Written</span><span className="font-mono text-green-400">{run.rowsWritten.toLocaleString()}</span></div>
                  {run.rowsFailed > 0 && <div><span className="text-muted-foreground mr-1">Failed</span><span className="font-mono text-rose-400">{run.rowsFailed.toLocaleString()}</span></div>}
                  <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* ─── Config Tab ───────────────────────────────────────────────────────── */}
      {activeTab === 'config' && (
        <div className="conduit-card p-5">
          <h2 className="font-semibold mb-4 text-sm">Sync Configuration</h2>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
            <dt className="text-muted-foreground">Sync ID</dt>
            <dd className="font-mono text-xs">{sync.id}</dd>
            <dt className="text-muted-foreground">Source Type</dt>
            <dd className="font-mono">{sync.sourceType}</dd>
            <dt className="text-muted-foreground">Connection</dt>
            <dd>{sync.connection?.name ?? sync.connectionId}</dd>
            <dt className="text-muted-foreground">Destination</dt>
            <dd className="capitalize">{sync.connection?.destination ?? '—'}</dd>
            <dt className="text-muted-foreground">Object Type</dt>
            <dd className="font-mono">{sync.objectType}</dd>
            <dt className="text-muted-foreground">Run Mode</dt>
            <dd className="capitalize">{sync.runMode}</dd>
            {sync.scheduleExpr && (
              <>
                <dt className="text-muted-foreground">Schedule</dt>
                <dd className="font-mono">{sync.scheduleExpr}</dd>
              </>
            )}
            <dt className="text-muted-foreground">Semantics</dt>
            <dd className="capitalize">{sync.semantics}</dd>
            {sync.upsertKey && (
              <>
                <dt className="text-muted-foreground">Upsert Key</dt>
                <dd className="font-mono">{sync.upsertKey}</dd>
              </>
            )}
            <dt className="text-muted-foreground">Created</dt>
            <dd className="font-mono text-xs">{formatTime(sync.createdAt)}</dd>
            <dt className="text-muted-foreground">Updated</dt>
            <dd className="font-mono text-xs">{formatTime(sync.updatedAt)}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
