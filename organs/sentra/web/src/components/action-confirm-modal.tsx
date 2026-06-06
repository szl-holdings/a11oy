import { useMemo } from 'react';
import { CheckCircle2, ShieldAlert, ShieldOff, X, Zap } from 'lucide-react';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useSentraStore, type ActionClass, type RegistryAsset } from '@/lib/sentra-store';
import { runPolicyGate, requiresApproval, SENTRA_DENIAL_MESSAGE } from '@/lib/policy-engine';

export interface ActionConfirmModalProps {
  open: boolean;
  asset: RegistryAsset | null;
  actionClass: ActionClass;
  actionLabel: string;
  reversible?: boolean;
  doctrineCitations?: string[];
  integrationId?: string | null;
  onCancel: () => void;
  onConfirm: (decision: {
    allowed: boolean;
    needsApproval: boolean;
    reason: string;
    denialMessage: string | null;
    doctrineCitations: string[];
  }) => void;
}

export function ActionConfirmModal({
  open, asset, actionClass, actionLabel, reversible = true,
  doctrineCitations, integrationId, onCancel, onConfirm,
}: ActionConfirmModalProps) {
  const store = useSentraStore();

  const gate = useMemo(() => {
    if (!asset) return null;
    // Pre-flight evaluates ownership/scope/tenant/rollback only. For high-impact
    // actions we pass approval_status='approved' so the gate doesn't reject the
    // pre-flight — the modal itself routes confirmation to createApproval() when
    // requiresApproval(actionClass) is true, so the actual approval gate still
    // occurs at execution time inside the Approval Queue.
    return runPolicyGate({
      action_class: actionClass,
      target_asset_id: asset.id,
      target_ownership_status: asset.ownership_status,
      integration_tenant_id: asset.tenant_id,
      requesting_tenant_id: asset.tenant_id,
      asset_tenant_id: asset.tenant_id,
      approval_status: 'approved',
      audit_logging_enabled: true,
      rollback_strategy_exists: true,
      asset_exists: true,
    });
  }, [asset, actionClass]);

  const blast = useMemo(() => {
    if (!asset || !gate?.allowed) return null;
    return store.computeBlastRadius(asset.id, actionClass);
  }, [asset, actionClass, gate, store]);

  if (!open || !asset || !gate) return null;

  const needsApproval = requiresApproval(actionClass);
  const rollbackColor = blast ? { low: '#4ade80', medium: '#f59e0b', high: '#e05252' }[blast.rollback_cost] : '#8a8a8a';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onCancel}>
      <div className="w-full max-w-2xl rounded-lg border max-h-[90vh] overflow-y-auto"
        style={{ background: '#0a0a0a', borderColor: 'rgba(201,183,135,0.25)' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            {gate.allowed ? (
              <ShieldAlert className="w-4 h-4 text-[#f59e0b]" />
            ) : (
              <ShieldOff className="w-4 h-4 text-red-400" />
            )}
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
              {gate.allowed ? 'Confirm Containment Action' : 'Safety Gate — Action Denied'}
            </span>
          </div>
          <button onClick={onCancel} className="text-slate-500 hover:text-slate-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">Pending Action</div>
            <div className="text-base font-display font-bold text-slate-100">{actionLabel}</div>
            <div className="text-xs text-slate-400 mt-1">
              Target: <span className="text-slate-200 font-mono">{asset.name}</span>
              <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-slate-400 border border-slate-700">
                {asset.ownership_status}
              </span>
            </div>
          </div>

          {gate.allowed && blast ? (
            <>
              <div className="rounded-lg border p-3" style={{ background: 'rgba(245,158,11,0.04)', borderColor: 'rgba(245,158,11,0.15)' }}>
                <div className="text-[10px] font-mono uppercase text-[#f59e0b] mb-2">Counterfactual Blast Radius</div>
                <div className="text-[11px] text-slate-300 mb-3 leading-relaxed">{blast.description}</div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: 'Unreachable', value: blast.unreachable_assets.length },
                    { label: 'Revoked Sessions', value: blast.revoked_sessions },
                    { label: 'Downstream', value: blast.downstream_services.length },
                    { label: 'Recovery (min)', value: blast.estimated_recovery_minutes },
                  ].map(({ label, value }) => (
                    <div key={label} className="text-center">
                      <div className="text-lg font-bold text-slate-200">{value}</div>
                      <div className="text-[9px] font-mono text-slate-500">{label}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-[10px] font-mono">
                  Rollback cost: <span style={{ color: rollbackColor }} className="font-bold">{blast.rollback_cost.toUpperCase()}</span>
                  <span className="ml-3 text-slate-500">Reversible: {reversible ? 'YES' : 'NO'}</span>
                </div>
              </div>

              {needsApproval && (
                <div className="rounded-md border border-[#f59e0b]/20 bg-[#f59e0b]/05 p-2.5 text-[10px] font-mono text-[#f59e0b]">
                  HIGH-IMPACT — On confirm, an approval will be queued (not executed). Audit + policy log entries are written immediately.
                </div>
              )}

              {doctrineCitations && doctrineCitations.length > 0 && (
                <div>
                  <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">Doctrine</div>
                  <div className="flex flex-wrap gap-1">
                    {doctrineCitations.map(c => (
                      <span key={c} className="px-1.5 py-0.5 rounded text-[9px] font-mono text-[#c9b787] bg-[#c9b787]/05 border border-[#c9b787]/15">{c}</span>
                    ))}
                  </div>
                </div>
              )}

              {integrationId && (
                <div className="text-[10px] font-mono text-slate-500">
                  Integration: <span className="text-slate-300">{integrationId}</span>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-lg border p-3 space-y-2" style={{ background: 'rgba(224,82,82,0.06)', borderColor: 'rgba(224,82,82,0.25)' }}>
              <div className="text-[10px] font-mono uppercase text-red-400">Safety Gate Denial</div>
              <div className="text-xs text-red-300 leading-relaxed">{gate.denial_message ?? SENTRA_DENIAL_MESSAGE}</div>
              <div className="text-[10px] font-mono text-slate-500 leading-relaxed border-t border-red-500/15 pt-2">
                Reason: {gate.reason}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-slate-800">
          <button onClick={onCancel}
            className="px-4 py-2 rounded text-[10px] font-mono border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-500">
            Cancel
          </button>
          {gate.allowed ? (
            <button
              onClick={() => onConfirm({
                allowed: true,
                needsApproval,
                reason: gate.reason,
                denialMessage: null,
                doctrineCitations: gate.doctrine_citations,
              })}
              className={cn('flex items-center gap-1.5 px-4 py-2 rounded text-[10px] font-mono font-bold border transition-all',
                needsApproval
                  ? 'border-[#f59e0b] text-[#f59e0b] bg-[#f59e0b]/10 hover:bg-[#f59e0b]/15'
                  : 'border-[#e05252] text-[#e05252] bg-[#e05252]/10 hover:bg-[#e05252]/15')}>
              {needsApproval ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Zap className="w-3.5 h-3.5" />}
              {needsApproval ? 'Queue Approval' : 'Confirm & Execute'}
            </button>
          ) : (
            <button
              onClick={() => onConfirm({
                allowed: false,
                needsApproval,
                reason: gate.reason,
                denialMessage: gate.denial_message ?? SENTRA_DENIAL_MESSAGE,
                doctrineCitations: gate.doctrine_citations,
              })}
              className="flex items-center gap-1.5 px-4 py-2 rounded text-[10px] font-mono font-bold border border-red-500/40 text-red-300 bg-red-500/05 hover:bg-red-500/10">
              <ShieldOff className="w-3.5 h-3.5" /> Log Denial & Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
