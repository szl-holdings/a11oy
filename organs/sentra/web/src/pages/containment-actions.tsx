import { useEffect, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, Clock, CloudOff, FileLock2, Globe, Key, Lock,
  RefreshCw, Shield, ShieldAlert, ShieldCheck, ShieldOff, 
  Unlock, User, Zap
} from 'lucide-react';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useSentraStore, ensureSeeded, EXECUTABLE_STATUSES, type ActionClass } from '@/lib/sentra-store';
import { SENTRA_DENIAL_MESSAGE } from '@/lib/policy-engine';
import { getAdapter } from '@/lib/integration-adapters';
import { ActionConfirmModal } from '@/components/action-confirm-modal';

interface ContainmentAction {
  id: string;
  action_class: ActionClass;
  title: string;
  description: string;
  category: string;
  icon: typeof Shield;
  color: string;
  doctrine: string[];
  requires_approval: boolean;
  integration_id: string | null;
  severity_threshold: 'any' | 'high' | 'critical';
  reversible: boolean;
  example_targets: string[];
}

const CONTAINMENT_CATALOG: ContainmentAction[] = [
  {
    id: 'ca-isolate-endpoint',
    action_class: 'contain_owned_asset',
    title: 'Isolate Endpoint',
    description: 'Sever an endpoint from the network while maintaining management channel. Prevents lateral movement and C2 communication.',
    category: 'Endpoint Containment',
    icon: Lock,
    color: '#e05252',
    doctrine: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-NI', 'CISA CIRCIA §3(a)'],
    requires_approval: true,
    integration_id: 'int-defender',
    severity_threshold: 'any',
    reversible: true,
    example_targets: ['WS-PROD-012', 'DC-EAST-01', 'BUILD-SRV-02'],
  },
  {
    id: 'ca-disable-account',
    action_class: 'revoke_owned_access',
    title: 'Disable Identity Account',
    description: 'Disable an identity in the IAM provider, revoking all active sessions and access tokens. Stops credential-based lateral movement.',
    category: 'Identity Containment',
    icon: User,
    color: '#f59e0b',
    doctrine: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-DA', 'NIST IR 8374 §3.2'],
    requires_approval: true,
    integration_id: 'int-entra',
    severity_threshold: 'any',
    reversible: true,
    example_targets: ['admin.chen@szlholdings.com', 'svc_backup@szlholdings.com', 'svc_cicd@szlholdings.com'],
  },
  {
    id: 'ca-revoke-sessions',
    action_class: 'revoke_owned_access',
    title: 'Revoke All Active Sessions',
    description: 'Force sign-out all active sessions for an identity. Effective for BEC, stolen cookie, and session hijacking incidents.',
    category: 'Identity Containment',
    icon: User,
    color: '#f59e0b',
    doctrine: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-DA'],
    requires_approval: true,
    integration_id: 'int-entra',
    severity_threshold: 'any',
    reversible: false,
    example_targets: ['admin.chen@szlholdings.com', 'cfo@szlholdings.com'],
  },
  {
    id: 'ca-rotate-secret',
    action_class: 'rotate_owned_secret',
    title: 'Rotate Secret / Credential',
    description: 'Rotate passwords, API keys, certificates, or service account credentials. Invalidates compromised credentials.',
    category: 'Credential Rotation',
    icon: Key,
    color: '#c9b787',
    doctrine: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-CR', 'NSA Hardening Guide §5'],
    requires_approval: true,
    integration_id: 'int-entra',
    severity_threshold: 'any',
    reversible: false,
    example_targets: ['svc_backup@szlholdings.com', 'azure-keyvault-prod', 'aws-s3-backup-prod'],
  },
  {
    id: 'ca-waf-block',
    action_class: 'contain_owned_asset',
    title: 'WAF IP Block Rule',
    description: 'Create a WAF firewall rule to block traffic from a source IP or CIDR range. Defensive network containment only.',
    category: 'Network Containment',
    icon: Globe,
    color: '#e05252',
    doctrine: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-NI', 'NCSC ACD §4'],
    requires_approval: true,
    integration_id: 'int-cloudflare',
    severity_threshold: 'any',
    reversible: true,
    example_targets: ['cloudflare-waf-prod'],
  },
  {
    id: 'ca-cloud-isolate',
    action_class: 'contain_owned_asset',
    title: 'Cloud Workload Isolation',
    description: 'Apply a deny-all security group or NACL to isolate a cloud workload. Effective for cloud compromise incidents.',
    category: 'Cloud Containment',
    icon: CloudOff,
    color: '#e05252',
    doctrine: ['NIST SP 800-61r2 §3.3', 'MITRE D3FEND D3-NI', 'CISA KEV'],
    requires_approval: true,
    integration_id: 'int-aws',
    severity_threshold: 'high',
    reversible: true,
    example_targets: ['aws-prod-east-vpc', 'prod-postgres-primary'],
  },
  {
    id: 'ca-preserve-evidence',
    action_class: 'preserve_evidence',
    title: 'Preserve & Lock Evidence',
    description: 'Collect, hash, and lock evidence for legal hold. Appends chain-of-custody entry. Evidence is immutable after locking.',
    category: 'Evidence Preservation',
    icon: FileLock2,
    color: '#4ade80',
    doctrine: ['NIST SP 800-61r2 §3.4', 'FBI IC3 Evidence §2', 'CISA CIRCIA §7'],
    requires_approval: false,
    integration_id: null,
    severity_threshold: 'any',
    reversible: false,
    example_targets: ['Any incident'],
  },
  {
    id: 'ca-restore-endpoint',
    action_class: 'restore_owned_asset',
    title: 'Restore Isolated Endpoint',
    description: 'Release an endpoint from network isolation after containment is verified. Requires post-containment verification.',
    category: 'Recovery',
    icon: Unlock,
    color: '#60a5fa',
    doctrine: ['NIST SP 800-61r2 §3.4', 'NIST CSF 2.0 RC.RP', 'MITRE D3FEND D3-ROS'],
    requires_approval: true,
    integration_id: 'int-defender',
    severity_threshold: 'any',
    reversible: true,
    example_targets: ['WS-PROD-012', 'FS-CLUSTER-03'],
  },
  {
    id: 'ca-re-enable-account',
    action_class: 'restore_owned_asset',
    title: 'Re-enable Identity Account',
    description: 'Re-enable a previously disabled identity account after post-containment verification. Requires CISO approval.',
    category: 'Recovery',
    icon: User,
    color: '#60a5fa',
    doctrine: ['NIST SP 800-61r2 §3.4', 'NIST CSF 2.0 RC.RP'],
    requires_approval: true,
    integration_id: 'int-entra',
    severity_threshold: 'any',
    reversible: true,
    example_targets: ['admin.chen@szlholdings.com'],
  },
  {
    id: 'ca-notify',
    action_class: 'notify',
    title: 'Notify Responders / Executive',
    description: 'Send security notification to on-call responders, executive stakeholders, or external contacts (legal, insurance, law enforcement).',
    category: 'Notifications',
    icon: AlertTriangle,
    color: '#8a8a8a',
    doctrine: ['NIST SP 800-61r2 §3.2', 'CISA CIRCIA §6', 'FBI IC3 §3'],
    requires_approval: false,
    integration_id: 'int-pagerduty',
    severity_threshold: 'any',
    reversible: false,
    example_targets: ['SOC Team', 'CISO', 'Legal Counsel', 'FBI IC3'],
  },
];

const CATEGORY_ORDER = [
  'Endpoint Containment',
  'Identity Containment',
  'Credential Rotation',
  'Network Containment',
  'Cloud Containment',
  'Evidence Preservation',
  'Recovery',
  'Notifications',
];

interface ExecutionState {
  actionId: string;
  assetId: string;
  status: 'running' | 'blocked' | 'success' | 'approval_queued';
  message: string;
}

function ActionCard({ action, onExecute }: {
  action: ContainmentAction;
  onExecute: (action: ContainmentAction, assetId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState('');
  const store = useSentraStore();
  const [execState, setExecState] = useState<ExecutionState | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const Icon = action.icon;
  // Include ALL assets in the dropdown so non-executable picks can surface the
  // Safety Gate denial through the confirm modal instead of being hidden.
  const selectableAssets = store.assets;
  const selectedAssetObj = selectedAsset ? store.getAsset(selectedAsset) ?? null : null;
  const adapter = action.integration_id ? getAdapter(action.integration_id) : null;
  const adapterOk = !adapter || adapter.meta.status === 'configured';

  function handleClickExecute() {
    if (!selectedAsset || !selectedAssetObj) return;
    setConfirmOpen(true);
  }

  async function handleConfirm(decision: { allowed: boolean; needsApproval: boolean; reason: string; denialMessage: string | null }) {
    setConfirmOpen(false);
    if (!selectedAsset) return;
    const asset = store.getAsset(selectedAsset);
    if (!asset) return;

    // Always write a policy log entry for every execution attempt
    store.writePolicyLog({
      action_id: store.nextId('ACT'),
      action_class: action.action_class,
      target: asset.name,
      integration: action.integration_id,
      reason: decision.reason,
      requested_by: 'Analyst (Console)',
      approval_id: null,
      policy_result: decision.allowed ? 'allow' : 'deny',
      denial_message: decision.denialMessage,
    });

    if (!decision.allowed) {
      setExecState({ actionId: action.id, assetId: selectedAsset, status: 'blocked', message: decision.denialMessage ?? SENTRA_DENIAL_MESSAGE });
      setTimeout(() => setExecState(null), 5000);
      return;
    }

    if (decision.needsApproval) {
      // Queue approval
      store.createApproval({
        tenant_id: asset.tenant_id,
        incident_id: store.incidents[0]?.id ?? 'INC-0001',
        action_id: store.nextId('ACT'),
        action_class: action.action_class,
        action_description: `${action.title} on ${asset.name}`,
        target_asset_id: selectedAsset,
        target_asset_name: asset.name,
        target_ownership_status: asset.ownership_status,
        integration_id: action.integration_id,
        requested_by: 'Analyst (Console)',
        doctrine_citations: action.doctrine,
        blast_radius_preview: store.computeBlastRadius(selectedAsset, action.action_class),
        rollback_path: action.reversible ? `Reverse ${action.title} via admin console` : 'Irreversible — confirm before executing',
        policy_class: action.action_class,
      });
      setExecState({ actionId: action.id, assetId: selectedAsset, status: 'approval_queued', message: `Approval queued for ${asset.name} — check Approval Queue` });
    } else {
      setExecState({ actionId: action.id, assetId: selectedAsset, status: 'running', message: 'Executing…' });
      if (adapter) {
        const result = await adapter.action({
          action_class: action.action_class,
          target_asset_id: selectedAsset,
          target_asset_name: asset.name,
          target_ownership_status: asset.ownership_status,
          target_asset_tenant_id: asset.tenant_id,
          requesting_tenant_id: asset.tenant_id,
        });
        setExecState({ actionId: action.id, assetId: selectedAsset, status: result.ok ? 'success' : 'blocked', message: result.message });
      } else {
        setExecState({ actionId: action.id, assetId: selectedAsset, status: 'success', message: `${action.title} executed (in-app stub — no real outbound call)` });
      }
      store.writeAudit({
        actor: 'Analyst (Console)',
        action: action.action_class,
        action_class: action.action_class,
        target_asset_id: selectedAsset,
        integration_id: action.integration_id,
        policy_decision: 'allow',
        approval_id: null,
        execution_result: 'success',
        evidence_hash: null,
        rollback_reference: action.reversible ? `ROLLBACK-${Date.now()}` : null,
        notes: `${action.title} on ${asset.name}`,
      });
    }

    setTimeout(() => setExecState(null), 5000);
  }

  return (
    <div className={cn('rounded-lg border transition-all', expanded && 'border-[#c9b787]/15')}
      style={{ background: 'rgba(255,255,255,0.025)', borderColor: expanded ? undefined : 'rgba(255,255,255,0.08)' }}>
      <div className="flex items-center gap-3 p-4 cursor-pointer" onClick={() => setExpanded(x => !x)}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${action.color}15`, border: `1px solid ${action.color}30` }}>
          <Icon className="w-4 h-4" style={{ color: action.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-200">{action.title}</span>
            {action.requires_approval && (
              <span className="px-1.5 py-0.5 rounded text-[8px] font-mono bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20">APPROVAL REQUIRED</span>
            )}
            {!action.reversible && (
              <span className="px-1.5 py-0.5 rounded text-[8px] font-mono bg-red-500/10 text-red-400 border border-red-500/20">IRREVERSIBLE</span>
            )}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5 truncate">{action.description}</div>
        </div>
        <div className="flex-shrink-0">
          <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            {action.action_class.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-slate-700/50 p-4 space-y-4">
          <div className="text-[11px] text-slate-400 leading-relaxed">{action.description}</div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Doctrine Citations</div>
              <div className="space-y-1">
                {action.doctrine.map(d => (
                  <div key={d} className="flex items-center gap-1.5 text-[10px] font-mono text-[#c9b787]">
                    <ShieldCheck className="w-2.5 h-2.5 flex-shrink-0" /> {d}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Integration</div>
              <div className="text-[11px] font-mono text-slate-300">{adapter ? adapter.meta.name : 'In-App (No Adapter)'}</div>
              {adapter && (
                <div className={cn('mt-1 text-[9px] font-mono', adapterOk ? 'text-green-400' : 'text-red-400')}>
                  {adapterOk ? '✓ CONFIGURED (STUB)' : '✗ NOT CONFIGURED — action() returns "Integration not configured. No action executed."'}
                </div>
              )}
            </div>
          </div>

          {/* Asset selector + Execute */}
          <div className="space-y-2">
            <div className="text-[10px] font-mono uppercase text-slate-500">Select Target Asset (Owned/Authorized Only)</div>
            <select value={selectedAsset} onChange={e => setSelectedAsset(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 outline-none focus:border-[#c9b787]/40">
              <option value="">Select target asset…</option>
              {selectableAssets.slice(0, 40).map(a => {
                const executable = EXECUTABLE_STATUSES.includes(a.ownership_status);
                return (
                  <option key={a.id} value={a.id}>
                    {executable ? '' : '⛔ '}{a.name} [{a.ownership_status}] [{a.type}]
                  </option>
                );
              })}
            </select>
            {selectedAssetObj && !EXECUTABLE_STATUSES.includes(selectedAssetObj.ownership_status) && (
              <div className="flex items-start gap-1.5 text-[10px] font-mono px-3 py-2 rounded border border-red-500/30 bg-red-500/05 text-red-300">
                <ShieldOff className="w-3 h-3 mt-0.5 flex-shrink-0" />
                <span>Safety Gate: target ownership '{selectedAssetObj.ownership_status}' is not executable. Confirming will log a denial — no action runs.</span>
              </div>
            )}
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={handleClickExecute} disabled={!selectedAsset}
                className="flex items-center gap-1.5 px-4 py-2 rounded text-[10px] font-mono font-bold border transition-all disabled:opacity-40"
                style={{ borderColor: action.color, color: action.color, background: `${action.color}08` }}>
                <Zap className="w-3.5 h-3.5" />
                {action.requires_approval ? 'Review & Queue Approval' : 'Review & Execute'}
              </button>
              {execState && (
                <div className={cn('flex items-center gap-1.5 text-[10px] font-mono px-3 py-2 rounded border',
                  execState.status === 'blocked' ? 'text-red-400 border-red-500/20 bg-red-500/05' :
                  execState.status === 'approval_queued' ? 'text-[#f59e0b] border-[#f59e0b]/20 bg-[#f59e0b]/05' :
                  execState.status === 'running' ? 'text-slate-400 border-slate-600' :
                  'text-green-400 border-green-500/20 bg-green-500/05')}>
                  {execState.status === 'running' && <RefreshCw className="w-3 h-3 animate-spin" />}
                  {execState.status === 'blocked' && <ShieldOff className="w-3 h-3" />}
                  {execState.status === 'approval_queued' && <Clock className="w-3 h-3" />}
                  {execState.status === 'success' && <CheckCircle2 className="w-3 h-3" />}
                  <span>{execState.message}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <ActionConfirmModal
        open={confirmOpen}
        asset={selectedAssetObj}
        actionClass={action.action_class}
        actionLabel={action.title}
        reversible={action.reversible}
        doctrineCitations={action.doctrine}
        integrationId={action.integration_id}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleConfirm}
      />
    </div>
  );
}

export default function ContainmentActions() {
  useEffect(() => { ensureSeeded(); }, []);

  const categorized = CATEGORY_ORDER.reduce((acc, cat) => {
    acc[cat] = CONTAINMENT_CATALOG.filter(a => a.category === cat);
    return acc;
  }, {} as Record<string, ContainmentAction[]>);

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Lock className="w-4 h-4 text-[#c9b787]" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Sentra — Containment Actions</span>
        </div>
        <h1 className="text-2xl font-display font-bold text-slate-100">Containment Action Library</h1>
        <p className="text-sm text-slate-500 mt-1">
          All {CONTAINMENT_CATALOG.length} actions are defensive-only. Policy gate enforces ownership. High-impact actions route through Approval Queue.
        </p>
      </div>

      {/* Defensive doctrine notice */}
      <div className="rounded-lg border p-3 flex items-start gap-2" style={{ background: 'rgba(224,82,82,0.04)', borderColor: 'rgba(224,82,82,0.15)' }}>
        <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
        <div className="text-[10px] font-mono text-red-300 leading-relaxed">
          <strong>DEFENSIVE SCOPE ONLY.</strong> All actions operate exclusively on owned, authorized, contracted-scope, or lab assets.
          Actions targeting attacker, external, unknown, or unverified assets are denied by policy gate with no code path for execution.
          Doctrine: NIST SP 800-61r2, MITRE D3FEND, CISA CIRCIA, NSA Cybersecurity Directorate.
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Actions', value: CONTAINMENT_CATALOG.length },
          { label: 'Require Approval', value: CONTAINMENT_CATALOG.filter(a => a.requires_approval).length, color: '#f59e0b' },
          { label: 'Irreversible', value: CONTAINMENT_CATALOG.filter(a => !a.reversible).length, color: '#e05252' },
          { label: 'Categories', value: CATEGORY_ORDER.length },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg border p-4" style={{ background: 'rgba(255,255,255,0.025)', borderColor: 'rgba(255,255,255,0.08)' }}>
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">{label}</div>
            <div className="text-2xl font-display font-bold" style={{ color: color ?? '#f5f5f5' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* By category */}
      {CATEGORY_ORDER.map(cat => {
        const actions = categorized[cat] ?? [];
        if (actions.length === 0) return null;
        return (
          <div key={cat}>
            <div className="text-[11px] font-mono uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-[#c9b787]" />
              {cat} <span className="text-slate-600">({actions.length})</span>
            </div>
            <div className="space-y-2">
              {actions.map(a => <ActionCard key={a.id} action={a} onExecute={() => {}} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
