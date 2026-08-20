import { Link } from 'wouter';
import { useConnections, useDeleteConnection, useTestConnection } from '@/lib/api-hooks';
import { DESTINATIONS } from '@/lib/api';
import { Badge, Button } from '@/components/ui';
import { formatDate } from '@/lib/utils';
import { toast } from 'sonner';
import { Cable, MoreVertical, Plus, Trash2, Activity } from 'lucide-react';
import React from 'react';

export default function ConnectionsList() {
  const { data: connections, isLoading } = useConnections();
  const deleteConnection = useDeleteConnection();
  const testConnection = useTestConnection();
  const [deletingId, setDeletingId] = React.useState<string | null>(null);

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this connection? Syncs using it will fail.')) {
      setDeletingId(id);
      deleteConnection.mutate(id, {
        onSuccess: () => {
          toast.success('Connection deleted');
          setDeletingId(null);
        },
        onError: (err) => {
          toast.error(err.message);
          setDeletingId(null);
        }
      });
    }
  };

  const handleTest = (id: string) => {
    const promise = testConnection.mutateAsync(id);
    toast.promise(promise, {
      loading: 'Validating credentials...',
      success: (data) => data.success
        ? `Credentials validated (${data.latencyMs}ms)`
        : `Validation failed: ${data.message}`,
      error: (err) => `Test failed: ${err.message}`
    });
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex flex-col sm:flex-row gap-4 sm:items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">Connections</h1>
          <p className="text-sm text-muted-foreground">Manage destinations for your data syncs.</p>
        </div>
        <Link href="/connections/new">
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            Add Connection
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
                <th className="px-6 py-4 font-medium">Last Tested</th>
                <th className="px-6 py-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                [1, 2, 3].map(i => (
                  <tr key={i}>
                    <td className="px-6 py-4"><div className="h-4 w-32 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-4 w-24 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-6 w-16 skeleton-conduit rounded-full" /></td>
                    <td className="px-6 py-4"><div className="h-4 w-24 skeleton-conduit" /></td>
                    <td className="px-6 py-4"><div className="h-8 w-8 skeleton-conduit ml-auto" /></td>
                  </tr>
                ))
              ) : connections?.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">
                    <Cable className="w-12 h-12 mx-auto mb-4 opacity-20" />
                    <p className="text-lg font-medium text-foreground mb-1">No connections yet</p>
                    <p className="mb-4">Create your first destination connection to start syncing data.</p>
                    <Link href="/connections/new">
                      <Button variant="outline">Add Connection</Button>
                    </Link>
                  </td>
                </tr>
              ) : (
                connections?.map((conn) => {
                  const dest = DESTINATIONS.find(d => d.id === conn.destination);
                  return (
                    <tr key={conn.id} className="hover:bg-muted/30 transition-colors group">
                      <td className="px-6 py-4 font-medium text-foreground">
                        {conn.name}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: dest?.color || '#ccc' }} />
                          {dest?.label || conn.destination}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={conn.status === 'active' ? 'active' : conn.status === 'error' ? 'error' : 'default'} className="capitalize">
                          {conn.status}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-muted-foreground">
                        {formatDate(conn.testedAt)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="sm" onClick={() => handleTest(conn.id)} title="Test connection">
                            <Activity className="w-4 h-4 text-muted-foreground hover:text-primary" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleDelete(conn.id)} 
                            disabled={deletingId === conn.id}
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4 text-muted-foreground hover:text-destructive" />
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
