import {
  productAccent,
  SubstrateWorkflowPanel as SharedSubstrateWorkflowPanel,
} from '@szl-holdings/design-system';

export function SubstrateWorkflowPanel() {
  return (
    <SharedSubstrateWorkflowPanel
      workflowId="aegis-threat-triage"
      title="Threat Triage and Escalation Routing"
      subtitle="Substrate · sentra-threat-triage · Phase 2"
      description="Classifies incoming threat alerts by severity and routes to the appropriate response team. CISO approval required before containment actions."
      accentColor={productAccent.sentra}
      workflowInput={{
        alertIds: ['aegis-alert-001', 'aegis-alert-002'],
        minSeverity: 'high',
        lookbackHours: 48,
      }}
      defaultConfidence={0.91}
      dryRunNote="DRY-RUN — containment actions and notifications suppressed."
      pendingApprovalNote="PENDING APPROVAL — paused at approval gate. CISO must review before containment commits."
    />
  );
}
