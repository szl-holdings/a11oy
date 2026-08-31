import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { PolicyResultBanner } from '@szl-holdings/shared-ui/policy-result';
import { ProofPanel } from '@szl-holdings/shared-ui/proof-panel';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Lock,
  Shield,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { SubstrateWorkflowPanel } from '@/components/SubstrateWorkflowPanel';
import {
  EvidenceIndexPanel,
  RelatedCasesPanel,
  TradecraftPanel,
} from '@/components/tradecraft-panel';
import { api } from '@/lib/api';
import { cpsApi } from '@/lib/cps-api';
import { useStepUp } from '@/lib/use-step-up';

const DECISIONS = [
  {
    id: 'DEC-041',
    title: 'Lateral movement confirmed — APT29 TTP pattern overlap',
    caseRef: 'CASE-0041',
    analyst: 'J. Chen',
    createdAt: '34m ago',
    approvalState: 'pending',
    approver: 'SOC Manager',
    confidence: 88,
    sensitivityLabel: 'RESTRICTED',
    tenantLabel: 'NORTHGATE-CORP',
    envLabel: 'PRODUCTION',
    evidence: [
      { id: 'EV-01', name: 'network-capture-0881.pcap', trustLevel: 'verified' },
      { id: 'EV-02', name: 'edr-lsass-dump-2024.log', trustLevel: 'verified' },
      { id: 'EV-03', name: 'svc-accnt04-auth-trail.csv', trustLevel: 'verified' },
    ],
    keyAssumptions: [
      'SVC-ACCNT-04 credentials were compromised prior to observed activity',
      'DC-PROD-03 has not yet been used as a pivot to additional infrastructure',
      'No data exfiltration has occurred in the current intrusion window',
    ],
    alternatives: [
      {
        hypothesis: 'Insider threat — privileged misuse',
        confidence: 22,
        ruling: 'unlikely',
        rationale: 'C2 beacon to known APT29 IP makes insider-only scenario implausible',
      },
      {
        hypothesis: 'Automated attack tool — no human operator',
        confidence: 31,
        ruling: 'possible',
        rationale: 'TTPs are consistent with automation but lateral movement is precise',
      },
    ],
    recommendedOutcome:
      'Escalate to active response. Isolate DC-PROD-03. Revoke SVC-ACCNT-04. Block 103.45.18.22.',
    auditChain: [
      {
        action: 'Decision object created',
        user: 'J. Chen',
        at: '15:42 UTC',
        hash: 'sha256:a3f1...',
      },
      {
        action: 'Evidence linked (3 items)',
        user: 'J. Chen',
        at: '15:44 UTC',
        hash: 'sha256:b9c2...',
      },
      {
        action: 'Submitted for approval',
        user: 'J. Chen',
        at: '15:49 UTC',
        hash: 'sha256:c7d4...',
      },
    ],
  },
  {
    id: 'DEC-040',
    title: 'Brute force event — automated credential spray, not targeted',
    caseRef: 'CASE-0038',
    analyst: 'L. Kim',
    createdAt: '2h ago',
    approvalState: 'approved',
    approver: 'SOC Manager',
    confidence: 95,
    sensitivityLabel: 'INTERNAL',
    tenantLabel: 'CORTEX-LOGISTICS',
    envLabel: 'PRODUCTION',
    evidence: [{ id: 'EV-10', name: 'auth-fail-log-1204.csv', trustLevel: 'verified' }],
    keyAssumptions: [
      'Source IP cluster is consistent with commodity botnet, not APT infrastructure',
      'No successful authentication occurred during the spray window',
    ],
    alternatives: [
      {
        hypothesis: 'Targeted credential attack by known threat actor',
        confidence: 8,
        ruling: 'unlikely',
        rationale: 'Pattern, timing, and source ASN do not match known targeted campaigns',
      },
    ],
    recommendedOutcome:
      'Block source ASN range. Close as automated threat. No escalation required.',
    auditChain: [
      {
        action: 'Decision object created',
        user: 'L. Kim',
        at: '12:11 UTC',
        hash: 'sha256:f2a8...',
      },
      {
        action: 'Approved by SOC Manager',
        user: 'M. Walsh',
        at: '12:24 UTC',
        hash: 'sha256:g5b1...',
      },
    ],
  },
];

const APPROVAL_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> =
  {
    pending: {
      bg: 'bg-[#c9b787]/10',
      text: 'text-[#c9b787]',
      border: 'border-[#c9b787]/25',
      label: 'Awaiting Approval',
    },
    approved: {
      bg: 'bg-[#c9b787]/10',
      text: 'text-[#c9b787]',
      border: 'border-[#c9b787]/25',
      label: 'Approved',
    },
    rejected: {
      bg: 'bg-[#f5f5f5]/10',
      text: 'text-[#f5f5f5]',
      border: 'border-[#f5f5f5]/25',
      label: 'Rejected',
    },
    draft: { bg: 'bg-white/5', text: 'text-white/50', border: 'border-white/10', label: 'Draft' },
  };

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 80 ? '#c9b787' : value >= 60 ? '#c9b787' : '#f5f5f5';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${value}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-sm font-bold font-mono tabular-nums" style={{ color }}>
        {value}%
      </span>
      <span className="text-[10px]" style={{ color: 'rgba(255,255,255,0.35)' }}>
        confidence
      </span>
    </div>
  );
}

interface LiveFinding {
  id: number;
  title: string;
  severity: string;
  status: string;
  description?: string | null;
  recommendation?: string | null;
  affectedAsset?: string | null;
  remediationOwner?: string | null;
  auditTrail?: Array<{ action: string; user: string; at: string; hash?: string }> | null;
  createdAt: string;
  updatedAt: string;
}

interface DecisionsPayload {
  decisions: LiveFinding[];
  pendingCount?: number;
  ztEnvironment?: string;
  ztPermissionClass?: string;
  ztDataLabels?: { sensitivityLabel: string; retentionClass: string };
  fetchedAt: string;
}

export default function DecisionConsole() {
  const queryClient = useQueryClient();
  const [selectedLiveId, setSelectedLiveId] = useState<number | null>(null);
  const [selectedMockId, setSelectedMockId] = useState(DECISIONS[0].id);
  const [expandedAudit, setExpandedAudit] = useState(false);

  const { data: decisionsData } = useStandardQuery<DecisionsPayload>({
    queryKey: ['command-decisions'],
    queryFn: () => api.command.decisions(),
    retry: false,
  });

  const { requestStepUp } = useStepUp();

  const approveMutation = useStandardMutation({
    mutationFn: async (findingId: string) => {
      const token = await requestStepUp('Approve finding decision');
      if (!token) throw new Error('Step-up verification cancelled by operator.');
      return api.command.approveDecision(findingId, 'Approved via Decision Console', token);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['command-decisions'] }),
  });

  const liveDecisions: LiveFinding[] = decisionsData?.decisions ?? [];
  const envLabel = decisionsData?.ztEnvironment;
  const sensitivityLabel = decisionsData?.ztDataLabels?.sensitivityLabel;

  // Use live decisions when available; fall back to mock data for display
  const usingLive = liveDecisions.length > 0;
  const selectedLive: LiveFinding | null = usingLive
    ? (liveDecisions.find((d) => d.id === selectedLiveId) ?? liveDecisions[0] ?? null)
    : null;
  const selectedMock = DECISIONS.find((d) => d.id === selectedMockId) ?? DECISIONS[0];
  const approvalState = selectedLive ? selectedLive.status : selectedMock.approvalState;
  const approvalStyle = APPROVAL_COLORS[approvalState] ?? APPROVAL_COLORS.draft;

  return (
    <div
      className="flex h-full min-h-screen"
      style={{ backgroundColor: '#070A10', color: 'var(--gi-text-primary)' }}
    >
      {/* Sidebar — Decision List */}
      <div className="w-72 shrink-0 border-r border-white/5 flex flex-col">
        <div className="px-4 py-3 border-b border-white/5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-[#c9b787]" />
              <span className="text-xs font-semibold text-white">Decision Console</span>
            </div>
            {envLabel && (
              <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/30 bg-[#c9b787]/5 text-[#c9b787]/70">
                {envLabel}
              </span>
            )}
          </div>
          <p className="text-[10px] mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
            {sensitivityLabel ? (
              <>
                <Lock className="w-2.5 h-2.5 inline mr-1" />
                {sensitivityLabel} ·{' '}
              </>
            ) : null}
            Structured analytical decisions
            {liveDecisions.length > 0 && (
              <span className="text-[#c9b787] ml-1">· {liveDecisions.length} live</span>
            )}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto divide-y divide-white/[0.04]">
          {usingLive
            ? liveDecisions.map((dec) => {
                const st = APPROVAL_COLORS[dec.status] ?? APPROVAL_COLORS.draft;
                const isActive = (selectedLive?.id ?? liveDecisions[0]?.id) === dec.id;
                return (
                  <button
                    key={dec.id}
                    onClick={() => setSelectedLiveId(dec.id)}
                    className={cn(
                      'w-full text-left px-4 py-3 transition-all',
                      isActive
                        ? 'bg-[#c9b787]/10 border-l-2 border-[#c9b787]'
                        : 'hover:bg-white/[0.02] border-l-2 border-transparent',
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] font-mono text-white/40">
                        FIND-{String(dec.id).padStart(4, '0')}
                      </span>
                      <span
                        className={cn(
                          'text-[8px] font-mono px-1 py-0.5 rounded border',
                          st.bg,
                          st.text,
                          st.border,
                        )}
                      >
                        {st.label}
                      </span>
                    </div>
                    <p className="text-[11px] font-medium text-white/85 leading-snug mb-1 line-clamp-2">
                      {dec.title}
                    </p>
                    <div
                      className="flex items-center gap-2 text-[10px]"
                      style={{ color: 'rgba(255,255,255,0.35)' }}
                    >
                      <span className="font-mono uppercase text-[9px]">{dec.severity}</span>
                      <span>·</span>
                      <span>{new Date(dec.createdAt).toLocaleDateString()}</span>
                    </div>
                  </button>
                );
              })
            : DECISIONS.map((dec) => {
                const st = APPROVAL_COLORS[dec.approvalState] ?? APPROVAL_COLORS.draft;
                return (
                  <button
                    key={dec.id}
                    onClick={() => setSelectedMockId(dec.id)}
                    className={cn(
                      'w-full text-left px-4 py-3 transition-all',
                      selectedMockId === dec.id
                        ? 'bg-[#c9b787]/10 border-l-2 border-[#c9b787]'
                        : 'hover:bg-white/[0.02] border-l-2 border-transparent',
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] font-mono text-white/40">{dec.id}</span>
                      <span
                        className={cn(
                          'text-[8px] font-mono px-1 py-0.5 rounded border',
                          st.bg,
                          st.text,
                          st.border,
                        )}
                      >
                        {st.label}
                      </span>
                    </div>
                    <p className="text-[11px] font-medium text-white/85 leading-snug mb-1">
                      {dec.title}
                    </p>
                    <div
                      className="flex items-center gap-2 text-[10px]"
                      style={{ color: 'rgba(255,255,255,0.35)' }}
                    >
                      <span>{dec.analyst}</span>
                      <span>·</span>
                      <span>{dec.createdAt}</span>
                    </div>
                  </button>
                );
              })}
        </div>
        <div className="p-3 border-t border-white/5">
          <button className="w-full py-2 rounded-lg text-xs font-semibold bg-[#c9b787]/10 border border-[#c9b787]/20 text-[#c9b787] hover:bg-[#c9b787]/20 transition-colors">
            + New Decision
          </button>
        </div>
      </div>

      {/* Main Panel */}
      <div className="flex-1 overflow-y-auto">
        {/* Decision Header */}
        <div
          className="px-6 py-4 border-b border-white/5 sticky top-0 z-10"
          style={{ backgroundColor: '#070A10' }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                {usingLive && selectedLive ? (
                  <span className="text-[9px] font-mono text-white/40">
                    FIND-{String(selectedLive.id).padStart(4, '0')}
                  </span>
                ) : (
                  <span className="text-[9px] font-mono text-white/40">{selectedMock.id}</span>
                )}
                <span className="text-[8px] font-mono text-white/30">→</span>
                <span className="text-[9px] font-mono text-white/40">
                  {usingLive && selectedLive
                    ? (selectedLive.affectedAsset ?? '—')
                    : selectedMock.caseRef}
                </span>
                <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/30 bg-[#c9b787]/5 text-[#c9b787]/70">
                  {envLabel ?? (usingLive ? 'PRODUCTION' : selectedMock.envLabel)}
                </span>
                {!usingLive && (
                  <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/30 bg-[#c9b787]/5 text-[#c9b787]/70">
                    {selectedMock.tenantLabel}
                  </span>
                )}
                <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-[#f5f5f5]/20 bg-[#f5f5f5]/5 text-[#f5f5f5]/70 flex items-center gap-0.5">
                  <Lock className="w-2 h-2" />
                  {sensitivityLabel ?? (usingLive ? 'RESTRICTED' : selectedMock.sensitivityLabel)}
                </span>
              </div>
              <h1 className="text-sm font-bold text-white leading-snug">
                {usingLive && selectedLive ? selectedLive.title : selectedMock.title}
              </h1>
              <div
                className="flex items-center gap-3 mt-1 text-[10px]"
                style={{ color: 'rgba(255,255,255,0.4)' }}
              >
                {usingLive && selectedLive ? (
                  <>
                    <span className="uppercase font-mono text-[9px]">{selectedLive.severity}</span>
                    <span>·</span>
                    <span>{new Date(selectedLive.createdAt).toLocaleString()}</span>
                  </>
                ) : (
                  <>
                    <span>{selectedMock.analyst}</span>
                    <span>·</span>
                    <span>{selectedMock.createdAt}</span>
                  </>
                )}
                <span>·</span>
                <span
                  className={cn(
                    'flex items-center gap-1 font-mono px-1.5 py-0.5 rounded border',
                    approvalStyle.bg,
                    approvalStyle.text,
                    approvalStyle.border,
                  )}
                >
                  {approvalState === 'approved' ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : approvalState === 'rejected' ? (
                    <XCircle className="w-3 h-3" />
                  ) : (
                    <Clock className="w-3 h-3" />
                  )}
                  {approvalStyle.label}
                </span>
              </div>
            </div>
            {(usingLive &&
              selectedLive &&
              (selectedLive.status === 'open' || selectedLive.status === 'confirmed')) ||
            (!usingLive && selectedMock.approvalState === 'pending') ? (
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => selectedLive && approveMutation.mutate(String(selectedLive.id))}
                  disabled={approveMutation.isPending || !selectedLive}
                  className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-[#c9b787]/10 border border-[#c9b787]/20 text-[#c9b787] hover:bg-[#c9b787]/20 transition-colors disabled:opacity-40"
                >
                  {approveMutation.isPending ? 'Queuing...' : 'Approve'}
                </button>
                <button className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 text-[#f5f5f5] hover:bg-[#f5f5f5]/20 transition-colors">
                  Reject
                </button>
              </div>
            ) : null}
          </div>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Confidence Score — mock only; live findings show severity */}
          {!usingLive && (
            <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-3 text-white/40">
                Analytical Confidence
              </div>
              <ConfidenceBar value={selectedMock.confidence} />
            </div>
          )}

          {/* Proof Chain — provenance and review state for the selected decision */}
          {!usingLive && (
            <ProofPanel
              proof={{
                sourceClass: 'human_authored',
                confidenceScore: selectedMock.confidence / 100,
                actorAttribution: selectedMock.analyst,
                reviewState:
                  selectedMock.approvalState === 'approved'
                    ? 'approved'
                    : selectedMock.approvalState === 'rejected'
                      ? 'flagged'
                      : 'unreviewed',
                exportSafetyState:
                  selectedMock.sensitivityLabel === 'RESTRICTED' ? 'restricted' : 'safe',
                inputSources: selectedMock.evidence.map((ev) => ({
                  type: 'evidence_file',
                  id: ev.id,
                  label: ev.name,
                })),
                lineage: selectedMock.auditChain.map((ac) => ({
                  label: `${ac.action} — ${ac.user} at ${ac.at}`,
                  sourceClass: 'human_authored' as const,
                })),
              }}
              variant="inline"
              showActions={selectedMock.approvalState === 'pending'}
            />
          )}

          {/* Policy Banner for pending approvals */}
          {selectedMock.approvalState === 'pending' && !usingLive && (
            <PolicyResultBanner
              decision={{
                effect: 'escalate',
                allowed: false,
                reason: `Confidence threshold at ${selectedMock.confidence}% meets escalation trigger. Requires ${selectedMock.approver} approval before actioning.`,
                escalationPath: [selectedMock.approver],
                whatNeedsToChange: [
                  `${selectedMock.approver} must review and approve`,
                  'Step-up verification required for approval',
                ],
              }}
            />
          )}

          {/* Recommended Outcome / Description */}
          <div className="bg-[#c9b787]/[0.05] border border-[#c9b787]/15 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <ArrowRight className="w-3.5 h-3.5 text-[#c9b787]" />
              <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#c9b787]/60">
                {usingLive && selectedLive ? 'Finding Description' : 'Recommended Outcome'}
              </span>
            </div>
            <p className="text-sm text-white/90 leading-relaxed">
              {usingLive && selectedLive
                ? (selectedLive.description ?? 'No description provided.')
                : selectedMock.recommendedOutcome}
            </p>
          </div>

          {usingLive && selectedLive?.recommendation && (
            <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-2 text-white/40">
                Recommendation
              </div>
              <p className="text-[11px] text-white/75 leading-relaxed">
                {selectedLive.recommendation}
              </p>
            </div>
          )}

          {usingLive && selectedLive?.affectedAsset && (
            <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-2 text-white/40">
                Affected Asset
              </div>
              <p className="text-[11px] font-mono text-white/80">{selectedLive.affectedAsset}</p>
            </div>
          )}

          {!usingLive && (
            <>
              {/* Evidence References (mock only) */}
              <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-3 text-white/40">
                  Evidence ({selectedMock.evidence.length})
                </div>
                <div className="space-y-2">
                  {selectedMock.evidence.map((ev) => (
                    <div
                      key={ev.id}
                      className="flex items-center gap-3 bg-white/[0.025] rounded-lg px-3 py-2"
                    >
                      <FileText className="w-3.5 h-3.5 text-[#8a8a8a] shrink-0" />
                      <span className="text-[11px] font-mono text-white/80 flex-1">{ev.name}</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#c9b787]/20 bg-[#c9b787]/5 text-[#c9b787]/70">
                        trust: {ev.trustLevel}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              {/* Key Assumptions (mock only) */}
              <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-3 text-white/40">
                  Key Assumptions
                </div>
                <ul className="space-y-2">
                  {selectedMock.keyAssumptions.map((a, i) => (
                    <li key={i} className="flex items-start gap-2 text-[11px] text-white/75">
                      <span className="w-4 h-4 rounded bg-white/5 flex items-center justify-center text-[9px] font-mono text-white/40 shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
              {/* Alternative Hypotheses (mock only) */}
              <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-3 text-white/40">
                  Alternative Hypotheses
                </div>
                <div className="space-y-3">
                  {selectedMock.alternatives.map((alt, i) => (
                    <div key={i} className="bg-white/[0.02] rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-medium text-white/85">
                          {alt.hypothesis}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-white/40 tabular-nums">
                            {alt.confidence}%
                          </span>
                          <span
                            className={cn(
                              'text-[8px] font-mono px-1.5 py-0.5 rounded border uppercase',
                              alt.ruling === 'unlikely'
                                ? 'border-[#c9b787]/20 bg-[#c9b787]/5 text-[#c9b787]/70'
                                : alt.ruling === 'possible'
                                  ? 'border-[#c9b787]/20 bg-[#c9b787]/5 text-[#c9b787]/70'
                                  : 'border-[#f5f5f5]/20 bg-[#f5f5f5]/5 text-[#f5f5f5]/70',
                            )}
                          >
                            {alt.ruling}
                          </span>
                        </div>
                      </div>
                      <p className="text-[10px] text-white/50 leading-relaxed">{alt.rationale}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Approval State */}
          <div className="bg-white/[0.025] border border-white/5 rounded-xl p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-3 text-white/40">
              Approval Chain
            </div>
            <div className="flex items-center gap-3 mb-3">
              <div
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold',
                  approvalStyle.bg,
                  approvalStyle.text,
                  approvalStyle.border,
                )}
              >
                {approvalState === 'approved' ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <Clock className="w-3.5 h-3.5" />
                )}
                {approvalStyle.label}
              </div>
              <span className="text-[11px]" style={{ color: 'rgba(255,255,255,0.4)' }}>
                requires: {usingLive ? 'soc_manager+' : selectedMock.approver}
              </span>
            </div>
            {usingLive && selectedLive?.remediationOwner && (
              <p className="text-[10px] text-white/40">
                Remediation owner: {selectedLive.remediationOwner}
              </p>
            )}
          </div>

          {/* Audit Chain */}
          <div className="bg-white/[0.025] border border-white/5 rounded-xl overflow-hidden">
            {(() => {
              const auditEntries =
                usingLive && selectedLive
                  ? (selectedLive.auditTrail ?? [])
                  : selectedMock.auditChain;
              return (
                <>
                  <button
                    className="w-full px-5 py-3 flex items-center justify-between border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                    onClick={() => setExpandedAudit(!expandedAudit)}
                  >
                    <div className="flex items-center gap-2">
                      <Shield className="w-3.5 h-3.5 text-[#c9b787]" />
                      <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-white/40">
                        Audit Chain ({auditEntries.length} entries)
                      </span>
                    </div>
                    {expandedAudit ? (
                      <ChevronDown className="w-3.5 h-3.5 text-white/30" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-white/30" />
                    )}
                  </button>
                  {expandedAudit && (
                    <div className="divide-y divide-white/[0.03]">
                      {auditEntries.length === 0 && (
                        <p className="px-5 py-3 text-[10px] text-white/30">No audit entries yet.</p>
                      )}
                      {auditEntries.map((entry, i) => (
                        <div key={i} className="px-5 py-3 flex items-center justify-between gap-4">
                          <div>
                            <p className="text-[11px] text-white/80">{entry.action}</p>
                            <div
                              className="flex items-center gap-2 mt-0.5 text-[10px]"
                              style={{ color: 'rgba(255,255,255,0.35)' }}
                            >
                              <span>{entry.user}</span>
                              <span>·</span>
                              <span>{entry.at}</span>
                            </div>
                          </div>
                          {entry.hash && (
                            <span className="text-[9px] font-mono text-white/20">{entry.hash}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              );
            })()}
          </div>

          <CpsApprovalLineage />

          {/* Tradecraft Decisions Panel */}
          {usingLive && selectedLive ? (
            <div className="space-y-3">
              <TradecraftPanel
                incidentId={String(selectedLive.id)}
                title="Tradecraft Analysis"
                compact
              />
              <RelatedCasesPanel incidentId={String(selectedLive.id)} />
              <EvidenceIndexPanel incidentId={String(selectedLive.id)} />
              <SubstrateWorkflowPanel />
            </div>
          ) : (
            <div className="space-y-3">
              <TradecraftPanel caseId={selectedMock.caseRef} title="Tradecraft Analysis" compact />
              <RelatedCasesPanel caseId={selectedMock.caseRef} />
              <EvidenceIndexPanel caseId={selectedMock.caseRef} />
              <SubstrateWorkflowPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CpsApprovalLineage() {
  const { data } = useStandardQuery({
    queryKey: ['cps-pending-approvals'],
    queryFn: () => cpsApi.approvals.list({ status: 'pending' }),
    retry: false,
  });

  const approvals: Array<{
    id: string;
    runId: string;
    tier: string;
    status: string;
    requestedAt: string;
    deadlineAt: string;
    approver?: string;
    dualApprovals?: Array<{ approver: string; approvedAt: string }>;
    requiredDualCount?: number;
  }> = data ?? [];

  if (approvals.length === 0) return null;

  return (
    <div className="bg-[#c9b787]/[0.04] border border-[#c9b787]/15 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Shield className="w-3.5 h-3.5 text-[#c9b787]" />
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#c9b787]/70">
          CPS Approval Queue ({approvals.length})
        </span>
      </div>
      <div className="space-y-2">
        {approvals.map((a) => {
          const deadline = new Date(a.deadlineAt);
          const remaining = deadline.getTime() - Date.now();
          const hoursLeft = Math.max(0, Math.floor(remaining / (60 * 60 * 1000)));
          const minutesLeft = Math.max(0, Math.floor((remaining % (60 * 60 * 1000)) / (60 * 1000)));
          const isUrgent = remaining < 60 * 60 * 1000;
          const isDual = a.tier === 'dual-executive';
          const dualProgress = isDual && a.requiredDualCount
            ? `${(a.dualApprovals ?? []).length}/${a.requiredDualCount}`
            : null;

          return (
            <div
              key={a.id}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2',
                isUrgent ? 'bg-[#f5f5f5]/5 border border-[#f5f5f5]/15' : 'bg-white/[0.025]',
              )}
            >
              <Clock className={cn('w-3.5 h-3.5 shrink-0', isUrgent ? 'text-[#f5f5f5]' : 'text-[#c9b787]')} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium text-white/85 truncate">
                    {a.tier.toUpperCase()} approval
                  </span>
                  {dualProgress && (
                    <span className="text-[9px] font-mono text-[#c9b787]/70 px-1.5 py-0.5 rounded bg-[#c9b787]/10 border border-[#c9b787]/20">
                      {dualProgress} signed
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-mono text-white/35">
                  Run {a.runId.slice(0, 8)}
                </span>
              </div>
              <span className={cn(
                'text-[10px] font-mono shrink-0',
                isUrgent ? 'text-[#f5f5f5]' : 'text-white/40',
              )}>
                {hoursLeft}h {minutesLeft}m
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
