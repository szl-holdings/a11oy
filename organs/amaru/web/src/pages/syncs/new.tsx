import React from 'react';
import { useLocation } from 'wouter';
import { useConnections, useCreateSync } from '@/lib/api-hooks';
import { Button, Input, Select } from '@/components/ui';
import { toast } from 'sonner';
import { ArrowLeft, Save, ArrowRight } from 'lucide-react';
import { Link } from 'wouter';

export default function SyncsNew() {
  const [, setLocation] = useLocation();
  const { data: connections, isLoading: connectionsLoading } = useConnections();
  const createSync = useCreateSync();
  
  const [name, setName] = React.useState('');
  const [connectionId, setConnectionId] = React.useState('');
  const [sourceType, setSourceType] = React.useState('postgres');
  const [objectType, setObjectType] = React.useState('Contact');
  const [runMode, setRunMode] = React.useState<'manual' | 'scheduled' | 'on_change'>('manual');
  const [semantics, setSemantics] = React.useState<'insert' | 'upsert' | 'mirror'>('upsert');
  const [scheduleExpr, setScheduleExpr] = React.useState('0 * * * *');
  const [upsertKey, setUpsertKey] = React.useState('email');

  // Auto-select first connection when loaded
  React.useEffect(() => {
    if (connections?.length && !connectionId) {
      setConnectionId(connections[0].id);
    }
  }, [connections, connectionId]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !connectionId || !objectType) return;

    createSync.mutate(
      { 
        name, 
        connectionId, 
        objectType, 
        runMode, 
        semantics, 
        sourceType,
        scheduleExpr: runMode === 'scheduled' ? scheduleExpr : undefined,
        upsertKey: semantics === 'upsert' ? upsertKey : undefined,
        sourceMeta: { table: 'users_view' } // mock source meta
      },
      {
        onSuccess: (sync) => {
          toast.success('Sync created. Now configure mappings.');
          setLocation(`/syncs/${sync.id}`);
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to create sync');
        }
      }
    );
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in-up">
      <div className="flex items-center gap-4">
        <Link href="/syncs">
          <Button variant="ghost" size="icon" className="rounded-full">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">Create Sync</h1>
          <p className="text-sm text-muted-foreground">Configure a new data pipeline.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="conduit-card p-6 space-y-6">
          <h2 className="text-lg font-medium border-b border-border pb-2">1. Basic Info</h2>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Sync Name</label>
              <Input 
                placeholder="e.g. Users to Salesforce Contacts" 
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
              />
            </div>
          </div>
        </div>

        <div className="conduit-card p-6 space-y-6">
          <h2 className="text-lg font-medium border-b border-border pb-2">2. Source & Destination</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4 p-4 rounded-lg bg-muted/20 border border-border">
              <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">Source</h3>
              <div className="space-y-2">
                <label className="text-sm">Source Type</label>
                <Select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                  <option value="postgres">PostgreSQL Database</option>
                  <option value="api_resource">REST API Resource</option>
                  <option value="csv">CSV File (Blob Storage)</option>
                  <option value="snowflake">Snowflake Data Warehouse</option>
                </Select>
              </div>
            </div>

            <div className="space-y-4 p-4 rounded-lg bg-primary/5 border border-primary/20">
              <h3 className="font-medium text-sm text-primary uppercase tracking-wider">Destination</h3>
              <div className="space-y-2">
                <label className="text-sm">Connection</label>
                <Select 
                  value={connectionId} 
                  onChange={(e) => setConnectionId(e.target.value)}
                  required
                  disabled={connectionsLoading}
                >
                  <option value="" disabled>Select Connection</option>
                  {connections?.map(c => (
                    <option key={c.id} value={c.id}>{c.name} ({c.destination})</option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm">Target Object</label>
                <Input 
                  placeholder="e.g. Contact, Lead, Account" 
                  value={objectType}
                  onChange={(e) => setObjectType(e.target.value)}
                  required
                />
              </div>
            </div>
          </div>
        </div>

        <div className="conduit-card p-6 space-y-6">
          <h2 className="text-lg font-medium border-b border-border pb-2">3. Behavior</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Sync Mode</label>
                <Select value={runMode} onChange={(e) => setRunMode(e.target.value as any)}>
                  <option value="manual">Manual (API / UI Trigger)</option>
                  <option value="scheduled">Scheduled (Cron)</option>
                  <option value="on_change">On Change (CDC / Webhook)</option>
                </Select>
              </div>
              
              {runMode === 'scheduled' && (
                <div className="space-y-2 p-3 bg-muted/30 rounded-md border border-border animate-fade-in">
                  <label className="text-sm font-medium">Cron Expression</label>
                  <Input 
                    value={scheduleExpr}
                    onChange={(e) => setScheduleExpr(e.target.value)}
                    placeholder="0 * * * *"
                    className="font-mono"
                  />
                  <p className="text-xs text-muted-foreground">Runs every hour.</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Semantics</label>
                <Select value={semantics} onChange={(e) => setSemantics(e.target.value as any)}>
                  <option value="upsert">Upsert (Update or Insert)</option>
                  <option value="insert">Insert Only (Append)</option>
                  <option value="mirror">Mirror (Sync deletions too)</option>
                </Select>
              </div>

              {semantics === 'upsert' && (
                <div className="space-y-2 p-3 bg-muted/30 rounded-md border border-border animate-fade-in">
                  <label className="text-sm font-medium">Upsert Key (External ID)</label>
                  <Input 
                    value={upsertKey}
                    onChange={(e) => setUpsertKey(e.target.value)}
                    placeholder="e.g. email, user_id"
                  />
                  <p className="text-xs text-muted-foreground">Field used to match existing records.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4">
          <Link href="/syncs">
            <Button variant="ghost" type="button">Cancel</Button>
          </Link>
          <Button type="submit" isLoading={createSync.isPending} className="gap-2">
            Continue to Mappings
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
