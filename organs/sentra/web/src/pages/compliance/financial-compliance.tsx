// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/pages/compliance/financial-compliance.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';
import { useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  AlertCircle,
  AlertTriangle,
  Archive,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Clock,
  Eye,
  FileText,
  RefreshCw,
  Scale,
  Shield,
  Zap,
} from 'lucide-react';
import { useState } from 'react';

interface CompliancePosture {
  overallRiskScore: number;
  regBiScore: number;
  archivalScore: number;
  supervisionScore: number;
  openSupervisionItems: number;
  criticalItems: number;
  overdueCalendarItems: number;
  pendingSuitabilityReviews: number;
  trend?: string;
  lastUpdated: string;
  source: string;
}

interface SupervisionItem {
  id: string;
  category: string;
  priority: string;
  status: string;
  title: string;
  description: string;
  assignedToName?: string;
  riskScore?: number;
  dueAt?: string;
  createdAt: string;
}

interface CalendarEvent {
  id: string;
  eventType: string;
  title: string;
  description?: string;
  dueAt: string;
  status: string;
  regulatoryBody?: string;
  assignedToName?: string;
}

interface FusionInsight {
  id: string;
  type: string;
  severity: string;
  title: string;
  description: string;
  crmAccountName?: string;
  marketData?: Record<string, unknown>;
  action: string;
  createdAt: string;
}

const SCORE_COLOR = (score: number) => {
  if (score >= 80) return '#c9b787';
  if (score >= 60) return '#c9b787';
  return '#f5f5f5';
};

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
  high: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  medium: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
  low: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
};

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-slate-500/10 text-slate-400',
  in_review: 'bg-[#c9b787]/10 text-[#c9b787]',
  escalated: 'bg-[#f5f5f5]/10 text-[#f5f5f5]',
  resolved: 'bg-[#c9b787]/10 text-[#c9b787]',
  closed: 'bg-gray-500/10 text-gray-400',
};

const SEVERITY_COLORS: Record<string, string> = {
  high: 'border-l-red-500 bg-[#f5f5f5]/20',
  medium: 'border-l-amber-500 bg-[#c9b787]/20',
  info: 'border-l-blue-500 bg-[#c9b787]/20',
};

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const color = SCORE_COLOR(score);
  const circumference = 2 * Math.PI * 28;
  const strokeDash = (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-16 h-16">
        <svg className="w-16 h-16 -rotate-90" viewBox="0 0 70 70">
          <circle
            cx="35"
            cy="35"
            r="28"
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="6"
          />
          <circle
            cx="35"
            cy="35"
            r="28"
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeDasharray={`${strokeDash} ${circumference}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s ease' }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-white">
          {score}
        </span>
      </div>
      <span className="text-xs text-slate-400 text-center leading-tight">{label}</span>
    </div>
  );
}

function formatDue(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = d.getTime() - now.getTime();
  const days = Math.ceil(diff / 86400000);
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return 'Due today';
  if (days === 1) return 'Due tomorrow';
  return `Due in ${days}d`;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  form_adv: 'Form ADV',
  form_adv_part2: 'Form ADV Part 2',
  form_crs: 'Form CRS',
  annual_review: 'Annual Review',
  exam_prep: 'Exam Prep',
  retention_review: 'Retention Review',
  reg_bi_audit: 'Reg BI Audit',
  finra_exam: 'FINRA Exam',
  sec_exam: 'SEC Exam',
  state_exam: 'State Exam',
  board_review: 'Board Review',
  policy_review: 'Policy Review',
  other: 'Other',
};

export default function FinancialCompliancePage() {
  const [activeTab, setActiveTab] = useState<
    'posture' | 'supervision' | 'calendar' | 'archival' | 'fusion'
  >('posture');
  const queryClient = useQueryClient();

  const { data: postureData, isLoading: postureLoading } = useStandardQuery({
    queryKey: ['compliance-posture'],
    queryFn: () => apiFetch<{ data: CompliancePosture }>('/compliance/posture'),
    refetchInterval: 60000,
  });

  const { data: supervisionData, isLoading: supervisionLoading } = useStandardQuery({
    queryKey: ['compliance-supervision'],
    queryFn: () =>
      apiFetch<{ data: { items: SupervisionItem[]; count: number } }>('/compliance/supervision'),
    enabled: activeTab === 'supervision' || activeTab === 'posture',
    refetchInterval: 30000,
  });

  const { data: calendarData, isLoading: calendarLoading } = useStandardQuery({
    queryKey: ['compliance-calendar'],
    queryFn: () => apiFetch<{ data: { events: CalendarEvent[] } }>('/compliance/calendar'),
    enabled: activeTab === 'calendar' || activeTab === 'posture',
  });

  const { data: fusionData, isLoading: fusionLoading } = useStandardQuery({
    queryKey: ['compliance-fusion'],
    queryFn: () =>
      apiFetch<{ data: { insights: FusionInsight[] } }>('/compliance/intelligence-fusion'),
    enabled: activeTab === 'fusion',
  });

  const actionMutation = useStandardMutation({
    mutationFn: ({ itemId, action, notes }: { itemId: string; action: string; notes?: string }) =>
      apiFetch(`/compliance/supervision/${itemId}/action`, {
        method: 'PATCH',
        body: JSON.stringify({ action, notes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compliance-supervision'] });
      queryClient.invalidateQueries({ queryKey: ['compliance-posture'] });
    },
  });

  const posture = postureData?.data;
  const supervision = supervisionData?.data;
  const calendar = calendarData?.data;
  const fusion = fusionData?.data;

  const tabs = [
    { id: 'posture', label: 'Posture', icon: Shield },
    { id: 'supervision', label: 'Supervision Queue', icon: Scale },
    { id: 'calendar', label: 'Compliance Calendar', icon: Calendar },
    { id: 'archival', label: '17a-4 Archival', icon: Archive },
    { id: 'fusion', label: 'Intelligence Fusion', icon: Zap },
  ] as const;

  return (
    <div className="min-h-screen bg-[#070A10] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Scale className="w-5 h-5 text-[#c9b787]" />
              <span className="text-xs font-mono text-[#c9b787] uppercase tracking-widest">
                SEC/FINRA Compliance Command
              </span>
            </div>
            <h1 className="text-2xl font-bold text-white">Financial Regulatory Compliance</h1>
            <p className="text-slate-400 text-sm mt-1">
              Regulation Best Interest · Rule 17a-4 Archival · Supervision Workflow · Compliance
              Calendar
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['compliance-posture'] })}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>

        <div className="flex gap-1 bg-white/5 rounded-xl p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id ? 'bg-[#c9b787]/20 text-[#c9b787] shadow' : 'text-slate-400 hover:text-white'}`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'posture' && (
          <div className="space-y-6">
            {postureLoading ? (
              <div className="flex items-center justify-center h-48 text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading compliance posture...
              </div>
            ) : posture ? (
              <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    {
                      label: 'Overall Compliance Score',
                      score: posture.overallRiskScore,
                      icon: Shield,
                      color: 'amber',
                    },
                    {
                      label: 'Reg BI Suitability',
                      score: posture.regBiScore,
                      icon: Scale,
                      color: 'blue',
                    },
                    {
                      label: 'Rule 17a-4 Archival',
                      score: posture.archivalScore,
                      icon: Archive,
                      color: 'purple',
                    },
                    {
                      label: 'Supervision Workflow',
                      score: posture.supervisionScore,
                      icon: Eye,
                      color: 'green',
                    },
                  ].map((item) => (
                    <motion.div
                      key={item.label}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-white/5 border border-white/10 rounded-xl p-4 flex flex-col items-center gap-3"
                    >
                      <ScoreGauge score={item.score ?? 0} label={item.label} />
                    </motion.div>
                  ))}
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    {
                      label: 'Open Supervision Items',
                      value: posture.openSupervisionItems,
                      icon: AlertTriangle,
                      urgent: posture.openSupervisionItems > 0,
                    },
                    {
                      label: 'Critical Violations',
                      value: posture.criticalItems,
                      icon: AlertCircle,
                      urgent: posture.criticalItems > 0,
                    },
                    {
                      label: 'Overdue Calendar Events',
                      value: posture.overdueCalendarItems,
                      icon: Clock,
                      urgent: posture.overdueCalendarItems > 0,
                    },
                    {
                      label: 'Pending Reg BI Reviews',
                      value: posture.pendingSuitabilityReviews,
                      icon: FileText,
                      urgent: posture.pendingSuitabilityReviews > 0,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className={`rounded-xl border p-4 ${item.urgent ? 'bg-[#f5f5f5]/20 border-[#f5f5f5]/20' : 'bg-white/5 border-white/10'}`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <item.icon
                          className={`w-4 h-4 ${item.urgent ? 'text-[#f5f5f5]' : 'text-slate-400'}`}
                        />
                        <span className="text-xs text-slate-400">{item.label}</span>
                      </div>
                      <div
                        className={`text-2xl font-bold ${item.urgent ? 'text-[#f5f5f5]' : 'text-white'}`}
                      >
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>

                {supervision &&
                  supervision.items.filter(
                    (i) => i.priority === 'critical' || i.priority === 'high',
                  ).length > 0 && (
                    <div className="bg-[#f5f5f5]/20 border border-[#f5f5f5]/20 rounded-xl p-4">
                      <h3 className="text-sm font-semibold text-[#f5f5f5] mb-3 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" /> Critical Supervision Items Requiring
                        Immediate Action
                      </h3>
                      <div className="space-y-2">
                        {supervision.items
                          .filter((i) => i.priority === 'critical' || i.priority === 'high')
                          .slice(0, 3)
                          .map((item) => (
                            <div
                              key={item.id}
                              className="flex items-start justify-between p-3 bg-black/20 rounded-lg"
                            >
                              <div>
                                <span
                                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border mr-2 ${PRIORITY_COLORS[item.priority]}`}
                                >
                                  {item.priority}
                                </span>
                                <span className="text-sm text-white">{item.title}</span>
                                <p className="text-xs text-slate-400 mt-1">
                                  {item.assignedToName ?? 'Unassigned'}
                                </p>
                              </div>
                              <button
                                onClick={() => setActiveTab('supervision')}
                                className="text-xs text-[#c9b787] hover:text-[#c9b787] flex items-center gap-1"
                              >
                                Review <ChevronRight className="w-3 h-3" />
                              </button>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                {calendar &&
                  calendar.events.filter(
                    (e) =>
                      e.status === 'overdue' ||
                      new Date(e.dueAt) < new Date(Date.now() + 7 * 86400000),
                  ).length > 0 && (
                    <div className="bg-[#c9b787]/20 border border-[#c9b787]/20 rounded-xl p-4">
                      <h3 className="text-sm font-semibold text-[#c9b787] mb-3 flex items-center gap-2">
                        <Calendar className="w-4 h-4" /> Upcoming Regulatory Deadlines
                      </h3>
                      <div className="space-y-2">
                        {calendar.events.slice(0, 3).map((event) => (
                          <div
                            key={event.id}
                            className="flex items-center justify-between p-3 bg-black/20 rounded-lg"
                          >
                            <div>
                              <span className="text-sm text-white">{event.title}</span>
                              <p className="text-xs text-slate-400 mt-0.5">
                                {event.regulatoryBody} ·{' '}
                                {EVENT_TYPE_LABELS[event.eventType] ?? event.eventType}
                              </p>
                            </div>
                            <span
                              className={`text-xs font-medium ${event.status === 'overdue' ? 'text-[#f5f5f5]' : 'text-[#c9b787]'}`}
                            >
                              {formatDue(event.dueAt)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </>
            ) : null}
          </div>
        )}

        {activeTab === 'supervision' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Supervision Queue</h2>
              <div className="flex gap-2 text-sm text-slate-400">
                <span>{supervision?.count ?? 0} items</span>
              </div>
            </div>
            {supervisionLoading ? (
              <div className="flex items-center justify-center h-48 text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading...
              </div>
            ) : (
              <div className="space-y-3">
                {(supervision?.items ?? []).map((item) => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white/5 border border-white/10 rounded-xl p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${PRIORITY_COLORS[item.priority]}`}
                          >
                            {item.priority}
                          </span>
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${STATUS_COLORS[item.status]}`}
                          >
                            {item.status.replace('_', ' ')}
                          </span>
                          {item.riskScore !== undefined && (
                            <span className="text-xs text-slate-400">
                              Risk:{' '}
                              <span
                                className={
                                  item.riskScore >= 80 ? 'text-[#f5f5f5] font-bold' : 'text-white'
                                }
                              >
                                {item.riskScore}
                              </span>
                              /100
                            </span>
                          )}
                        </div>
                        <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                        <p className="text-xs text-slate-400 mt-1">{item.description}</p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                          {item.assignedToName && <span>Assigned: {item.assignedToName}</span>}
                          {item.dueAt && (
                            <span
                              className={new Date(item.dueAt) < new Date() ? 'text-[#f5f5f5]' : ''}
                            >
                              {formatDue(item.dueAt)}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col gap-2 shrink-0">
                        {item.status === 'open' && (
                          <>
                            <button
                              onClick={() =>
                                actionMutation.mutate({ itemId: item.id, action: 'assign' })
                              }
                              className="px-3 py-1.5 text-xs bg-[#c9b787]/20 text-[#c9b787] rounded-lg hover:bg-[#c9b787]/30 transition-colors"
                            >
                              Take Review
                            </button>
                            <button
                              onClick={() =>
                                actionMutation.mutate({
                                  itemId: item.id,
                                  action: 'escalate',
                                  notes: 'Escalated via compliance dashboard',
                                })
                              }
                              className="px-3 py-1.5 text-xs bg-[#f5f5f5]/20 text-[#f5f5f5] rounded-lg hover:bg-[#f5f5f5]/30 transition-colors"
                            >
                              Escalate
                            </button>
                          </>
                        )}
                        {item.status === 'in_review' && (
                          <button
                            onClick={() =>
                              actionMutation.mutate({
                                itemId: item.id,
                                action: 'resolve',
                                notes: 'Resolved after review',
                              })
                            }
                            className="px-3 py-1.5 text-xs bg-[#c9b787]/20 text-[#c9b787] rounded-lg hover:bg-[#c9b787]/30 transition-colors"
                          >
                            Mark Resolved
                          </button>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
                {(!supervision?.items || supervision.items.length === 0) && (
                  <div className="flex items-center justify-center h-48 text-slate-400 border border-white/10 rounded-xl">
                    <CheckCircle2 className="w-5 h-5 text-[#c9b787] mr-2" /> No open supervision
                    items
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'calendar' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Compliance Calendar</h2>
              <span className="text-sm text-slate-400">
                Form ADV · Form CRS · SEC/FINRA Exams · Annual Reviews
              </span>
            </div>
            {calendarLoading ? (
              <div className="flex items-center justify-center h-48 text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading calendar...
              </div>
            ) : (
              <div className="space-y-3">
                {(calendar?.events ?? []).map((event) => (
                  <div
                    key={event.id}
                    className={`border-l-4 rounded-r-xl p-4 bg-white/5 border border-white/10 ${event.status === 'overdue' ? 'border-l-red-500 bg-[#f5f5f5]/10' : event.status === 'in_progress' ? 'border-l-amber-500 bg-[#c9b787]/10' : 'border-l-blue-500'}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono text-slate-400 uppercase">
                            {EVENT_TYPE_LABELS[event.eventType] ?? event.eventType}
                          </span>
                          {event.regulatoryBody && (
                            <span className="text-xs text-[#c9b787]">· {event.regulatoryBody}</span>
                          )}
                        </div>
                        <h3 className="text-sm font-semibold text-white">{event.title}</h3>
                        {event.description && (
                          <p className="text-xs text-slate-400 mt-1">{event.description}</p>
                        )}
                        {event.assignedToName && (
                          <p className="text-xs text-slate-500 mt-1">
                            Assigned: {event.assignedToName}
                          </p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <div
                          className={`text-sm font-semibold ${event.status === 'overdue' ? 'text-[#f5f5f5]' : event.status === 'in_progress' ? 'text-[#c9b787]' : 'text-slate-300'}`}
                        >
                          {formatDue(event.dueAt)}
                        </div>
                        <div className="text-xs text-slate-500">
                          {new Date(event.dueAt).toLocaleDateString()}
                        </div>
                        <span
                          className={`mt-1 inline-block px-2 py-0.5 rounded text-xs ${event.status === 'overdue' ? 'bg-[#f5f5f5]/20 text-[#f5f5f5]' : event.status === 'in_progress' ? 'bg-[#c9b787]/20 text-[#c9b787]' : event.status === 'completed' ? 'bg-[#c9b787]/20 text-[#c9b787]' : 'bg-[#c9b787]/20 text-[#c9b787]'}`}
                        >
                          {event.status.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'archival' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                SEC Rule 17a-4 Communication Archival
              </h2>
            </div>
            <div className="bg-[#c9b787]/20 border border-[#c9b787]/20 rounded-xl p-4 text-sm">
              <div className="flex items-center gap-2 mb-2">
                <Archive className="w-4 h-4 text-[#c9b787]" />
                <span className="font-semibold text-[#c9b787]">Immutable Write-Once Archive</span>
              </div>
              <p className="text-slate-400">
                All communications are stored with SHA-256 hash chains per SEC Rule 17a-4(f).
                Records are retained for 3 years (general) or 6 years (account-level). Content is
                immutable once archived.
              </p>
            </div>
            <ArchivalPanel />
          </div>
        )}

        {activeTab === 'fusion' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Cross-Domain Intelligence Fusion</h2>
              <span className="text-xs text-slate-400">
                Market conditions × CRM pipeline × Compliance posture
              </span>
            </div>
            {fusionLoading ? (
              <div className="flex items-center justify-center h-48 text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading intelligence...
              </div>
            ) : (
              <div className="space-y-3">
                {(fusion?.insights ?? []).map((insight) => (
                  <motion.div
                    key={insight.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`border-l-4 rounded-r-xl p-4 border border-white/10 ${SEVERITY_COLORS[insight.severity] ?? 'border-l-slate-500 bg-white/5'}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`text-xs font-mono uppercase ${insight.severity === 'high' ? 'text-[#f5f5f5]' : insight.severity === 'medium' ? 'text-[#c9b787]' : 'text-[#c9b787]'}`}
                          >
                            {insight.type.replace('_', ' ')}
                          </span>
                          {insight.crmAccountName && (
                            <span className="text-xs text-slate-400">
                              · {insight.crmAccountName}
                            </span>
                          )}
                        </div>
                        <h3 className="text-sm font-semibold text-white">{insight.title}</h3>
                        <p className="text-xs text-slate-400 mt-1">{insight.description}</p>
                        {insight.marketData && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {Object.entries(insight.marketData).map(([k, v]) => (
                              <span
                                key={k}
                                className="text-xs bg-white/10 px-2 py-0.5 rounded font-mono text-slate-300"
                              >
                                {k}: {String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="mt-2 flex items-center gap-2">
                          <Zap className="w-3 h-3 text-[#c9b787]" />
                          <span className="text-xs text-[#c9b787]">{insight.action}</span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ArchivalPanel() {
  const { data, isLoading } = useStandardQuery({
    queryKey: ['compliance-archival'],
    queryFn: () =>
      apiFetch<{
        data: {
          items: Array<{
            entryId: string;
            communicationType: string;
            subject?: string;
            participants: Array<{ name: string }>;
            contentHash: string;
            retentionExpiresAt: string;
            archivedAt: string;
          }>;
        };
      }>('/compliance/archival'),
  });

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-32 text-slate-400">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading archival records...
      </div>
    );

  const items = data?.data?.items ?? [];

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.entryId} className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-[#8a8a8a] uppercase">
                  {item.communicationType.replace('_', ' ')}
                </span>
                <span className="text-xs text-slate-500">
                  · Archived {new Date(item.archivedAt).toLocaleDateString()}
                </span>
              </div>
              {item.subject && <h3 className="text-sm text-white">{item.subject}</h3>}
              <div className="flex items-center gap-2 mt-1">
                <Archive className="w-3 h-3 text-slate-500" />
                <span className="text-xs font-mono text-slate-500 truncate max-w-xs">
                  {item.contentHash.slice(0, 20)}...
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Retention expires: {new Date(item.retentionExpiresAt).toLocaleDateString()}
              </p>
            </div>
            <div className="flex items-center gap-1 bg-[#c9b787]/10 px-2 py-1 rounded-lg">
              <CheckCircle2 className="w-3 h-3 text-[#c9b787]" />
              <span className="text-xs text-[#c9b787]">Immutable</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
