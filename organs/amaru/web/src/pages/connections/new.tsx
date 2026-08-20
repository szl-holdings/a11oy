import React from 'react';
import { useLocation } from 'wouter';
import { useCreateConnection, useValidateCredentials } from '@/lib/api-hooks';
import { DESTINATIONS } from '@/lib/api';
import { Button, Input, Select } from '@/components/ui';
import { toast } from 'sonner';
import { ArrowLeft, Save, Activity, CheckCircle2, XCircle } from 'lucide-react';
import { Link } from 'wouter';

export default function ConnectionsNew() {
  const [, setLocation] = useLocation();
  const createConnection = useCreateConnection();
  const validateCredentials = useValidateCredentials();
  
  const [name, setName] = React.useState('');
  const [destination, setDestination] = React.useState<string>(DESTINATIONS[0].id);
  const [credentials, setCredentials] = React.useState<Record<string, string>>({});
  const [validationResult, setValidationResult] = React.useState<{
    success: boolean;
    message: string;
    errors: string[];
  } | null>(null);

  const handleCredentialChange = (key: string, value: string) => {
    setCredentials(prev => ({ ...prev, [key]: value }));
    setValidationResult(null);
  };

  const handleTestCredentials = () => {
    setValidationResult(null);
    validateCredentials.mutate(
      { destination, credentials },
      {
        onSuccess: (data) => {
          setValidationResult({ success: data.success, message: data.message, errors: data.errors });
          if (data.success) {
            toast.success('Credentials validated successfully');
          } else {
            toast.error('Credential validation failed');
          }
        },
        onError: (err) => {
          toast.error(err.message || 'Validation request failed');
        },
      }
    );
  };

  const canSave = !!name && !!destination && validationResult?.success === true;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSave) {
      toast.error('Please test your credentials before saving');
      return;
    }

    createConnection.mutate(
      { name, destination, credentials },
      {
        onSuccess: () => {
          toast.success('Connection created successfully');
          setLocation('/connections');
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to create connection');
        }
      }
    );
  };

  const destObj = DESTINATIONS.find(d => d.id === destination);

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in-up">
      <div className="flex items-center gap-4">
        <Link href="/connections">
          <Button variant="ghost" size="icon" className="rounded-full">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">New Connection</h1>
          <p className="text-sm text-muted-foreground">Configure a new destination for data routing.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="conduit-card p-6 space-y-8">
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Connection Name</label>
            <Input 
              placeholder="e.g. Production Salesforce" 
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Destination Type</label>
            <Select 
              value={destination} 
              onChange={(e) => {
                setDestination(e.target.value);
                setCredentials({});
                setValidationResult(null);
              }}
              required
            >
              {DESTINATIONS.map(d => (
                <option key={d.id} value={d.id}>{d.label}</option>
              ))}
            </Select>
          </div>
        </div>

        <div className="space-y-4 pt-4 border-t border-border">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: destObj?.color }} />
            <h3 className="font-medium text-lg">{destObj?.label} Credentials</h3>
          </div>
          
          <p className="text-sm text-muted-foreground mb-4">
            Enter the authentication details for this destination. Credentials are encrypted at rest.
          </p>

          <div className="space-y-4 bg-muted/20 p-4 rounded-lg border border-border">
            <div className="space-y-2">
              <label className="text-sm font-medium">API Key / Token</label>
              <Input 
                type="password"
                placeholder="Enter API Key" 
                value={credentials.apiKey || ''}
                onChange={(e) => handleCredentialChange('apiKey', e.target.value)}
                required
              />
            </div>
            
            {['salesforce', 'hubspot', 'zendesk'].includes(destination) && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Instance URL / Subdomain</label>
                <Input 
                  type="text"
                  placeholder="e.g. https://my-domain.my.salesforce.com" 
                  value={credentials.instanceUrl || ''}
                  onChange={(e) => handleCredentialChange('instanceUrl', e.target.value)}
                  required
                />
              </div>
            )}

            <div className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTestCredentials}
                isLoading={validateCredentials.isPending}
                className="gap-2"
              >
                <Activity className="w-4 h-4" />
                Test Connection
              </Button>
            </div>

            {validationResult && (
              <div className={`flex items-start gap-2 p-3 rounded-md text-sm ${
                validationResult.success
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                  : 'bg-red-500/10 border border-red-500/30 text-red-400'
              }`}>
                {validationResult.success ? (
                  <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
                )}
                <div className="space-y-1">
                  <p className="font-medium">{validationResult.success ? 'Validation passed' : 'Validation failed'}</p>
                  {validationResult.errors.length > 0 && (
                    <ul className="list-disc list-inside space-y-0.5 text-xs opacity-90">
                      {validationResult.errors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-border">
          {!validationResult?.success && (
            <p className="text-xs text-muted-foreground">Test your credentials before saving.</p>
          )}
          {validationResult?.success && (
            <p className="text-xs text-emerald-400">Credentials validated — ready to save.</p>
          )}
          <Button type="submit" isLoading={createConnection.isPending} disabled={!canSave} className="gap-2">
            <Save className="w-4 h-4" />
            Save Connection
          </Button>
        </div>
      </form>
    </div>
  );
}
