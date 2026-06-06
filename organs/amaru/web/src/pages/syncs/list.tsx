import { Link } from 'wouter';
import { useSyncs, useRunSync, useUpdateSync } from '@/lib/api-hooks';
import { DESTINATIONS } from '@/lib/api';
import { Badge, Button } from '@/components/ui';
import { formatDate } from '@/lib/utils';
import { toast } from 'sonner';
import { FolderSync, Play, Plus, Pause, Power, Settings2, History } from 'lucide-react';
import React from 'react';

export default function SyncsList() {
  const { data: syncs, isLoading } = useSyncs();
  const runSync = useRunSync();
  const updateSync = useUpdateSync();
  const [runningId, setRunningId] = React.useState<string | null>(null);

  const handleRun = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    setRunningId(id);
    runSync.mutate(id, {
      onSuccess: () => {
        toast.success('Sync run started');
        setRunningId(null);
      },
      onError: (err) => {
        toast.error(err.message);
        setRunningId(null);
      }
    });
  };

  const toggleStatus = (e: React.MouseEvent, id: string, currentStatus: string) => {
    e.preventDefault();
    const newStatus = currentStatus === 'active' ? 'paused' : 'active';
    updateSync.mutate({ id, status: newStatus }, {
      onSuccess: () => toast.success(`Sync ${newStatus}`)
    });
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row gap-4 sm:items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">Syncs</h1>
          <p className="text-sm text-muted-foreground">Configure and manage data routing pipelines.</p>
        </div>
        <Link href="/syncs/new">
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            New Sync
          </Button>
        </Link>
      </div>

      <div className="conduit-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground uppercase bg-muted/30 border-b border-border">
              <tr>
                <th className="px-6 py-4 font-medium">Name</th>
                <th className="px-6 py-4 font-medium">Destination</th>
                <th className="px-6 py-4 font-medium">Status</th>
                <th className="px-6 py-4 font-medium">Mode</th>
                <th className="px-6 py-4 font-medium">Last Run</th>
                <th className="px-6 py-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                [1, 2, 3, 4].map(i => (
                  <tr key={i}>
                    <td className="px-6 py-4"><div className="h-4 w-40 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-4 w-32 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-6 w-16 skeleton-conduit rounded-full" /></td>
                    <td className="px-6 py-4"><div className="h-4 w-20 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-4 w-24 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-8 w-24 skeleton-conduit ml-auto" /></td>
                  </tr>
                ))
              ) : syncs?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    <FolderSync className="w-12 h-12 mx-auto mb-4 opacity-20" />
                    <p className="text-lg font-medium text-foreground mb-1">No syncs yet</p>
                    <p className="mb-4">Create a sync to start moving data to your destinations.</p>
                    <Link href="/syncs/new">
                      <Button variant="outline">Create Sync</Button>
                    </Link>
                  </td>
                </tr>
              ) : (
                syncs?.map((sync) => {
                  const dest = DESTINATIONS.find(d => d.id === sync.connection?.destination);
                  return (
                    <tr key={sync.id} className="hover:bg-muted/30 transition-colors group relative">
                      <td className="px-6 py-4">
                        <Link href={`/syncs/${sync.id}`} className="absolute inset-0 z-0" />
                        <div className="relative z-10">
                          <p className="font-medium text-foreground">{sync.name}</p>
                          <p className="text-xs text-muted-foreground mt-0.5 capitalize">{sync.sourceType} → {sync.objectType}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 relative z-10">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: dest?.color || '#ccc' }} />
                          <span>{sync.connection?.name || 'Unknown'}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 relative z-10">
                        <Badge variant={sync.status as any} className="capitalize">
                          {sync.status}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 relative z-10">
                        <div className="flex flex-col">
                          <span className="capitalize">{sync.runMode.replace('_', ' ')}</span>
                          {sync.scheduleExpr && <span className="text-xs text-muted-foreground font-mono mt-0.5">{sync.scheduleExpr}</span>}
                        </div>
                      </td>
                      <td className="px-6 py-4 relative z-10">
                        <div className="flex flex-col">
                          {sync.lastRunAt ? (
                            <>
                              <span className="flex items-center gap-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${sync.lastRunStatus === 'success' ? 'bg-green-500' : sync.lastRunStatus === 'failed' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                                {formatDate(sync.lastRunAt)}
                              </span>
                            </>
                          ) : (
                            <span className="text-muted-foreground">Never</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right relative z-10">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={(e) => toggleStatus(e, sync.id, sync.status)}
                            title={sync.status === 'active' ? 'Pause Sync' : 'Resume Sync'}
                          >
                            {sync.status === 'active' ? <Pause className="w-4 h-4" /> : <Power className="w-4 h-4 text-primary" />}
                          </Button>
                          <Link href={`/syncs/${sync.id}`}>
                            <Button variant="ghost" size="sm" title="Edit">
                              <Settings2 className="w-4 h-4" />
                            </Button>
                          </Link>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="ml-2 gap-1.5"
                            onClick={(e) => handleRun(e, sync.id)} 
                            isLoading={runningId === sync.id}
                          >
                            <Play className="w-3 h-3" />
                            Run
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
