export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}

const noop = (..._args: any[]): any => null;
const noopAsync = async (..._args: any[]): Promise<any> => {};
const NoopComponent = (props: any) => props?.children ?? null;

export const toast = Object.assign(noop, {
  success: noop, error: noop, warning: noop, info: noop, loading: noop, dismiss: noop, promise: noopAsync,
});
export async function apiFetch(..._args: any[]): Promise<any> { return {}; }

export const UsageIndicator = NoopComponent;
export const AnalyticsProvider = NoopComponent;
export const AppModeBanner = noop;
export const AppModeProvider = NoopComponent;
export const CommandPalette = noop;
export const useCommandPalette = (_commands: any[]) => ({ open: false, setOpen: (_v: boolean) => {} });
export function createBaselineWebActions(_nav: any): any[] { return []; }
export function getEcosystemSwitchCommands(_app: string): any[] { return []; }
export const DashboardShell = NoopComponent;
export const SharedDashboardShell = NoopComponent;
export const SidebarNav = noop;
export type SidebarNavSection = { id: string; label?: string; items: any[] };
export const EcosystemNav = noop;
export const SentientLayer = noop;
export const useSentientLayer = () => ({ open: false, show: noop, hide: noop });
export const Toaster = noop;
export const useSessionRevocationToast = noop;
export const useEffectiveAccent = (fallback: string) => fallback;
export const useUserPreferences = () => ({ prefs: { sidebar_collapsed: false } as any, setPreference: noop, isLoaded: true });
export const ErrorBoundary = NoopComponent;
export const PolicyResultBanner = noop;
export const ProofPanel = noop;
export const DataStateBadge = noop;
export const Badge = NoopComponent;
export const Card = NoopComponent;
export const CardContent = NoopComponent;
export const CardHeader = NoopComponent;
export const CardTitle = NoopComponent;
export const Button = NoopComponent;
export const Input = NoopComponent;
export const Label = NoopComponent;
export const Textarea = NoopComponent;
export const Select = NoopComponent;
export const SelectContent = NoopComponent;
export const SelectItem = NoopComponent;
export const SelectTrigger = NoopComponent;
export const SelectValue = NoopComponent;
export const Dialog = NoopComponent;
export const DialogContent = NoopComponent;
export const DialogDescription = NoopComponent;
export const DialogFooter = NoopComponent;
export const DialogHeader = NoopComponent;
export const DialogTitle = NoopComponent;
export const DialogTrigger = NoopComponent;
export const Progress = NoopComponent;
export const Tabs = NoopComponent;
export const TabsList = NoopComponent;
export const TabsTrigger = NoopComponent;
export const TabsContent = NoopComponent;
export const EmptyState = NoopComponent;
export const LiveClock = noop;
export const AnimatedCounter = NoopComponent;
export const ContactModal = NoopComponent;
export const NewsletterSubscribe = NoopComponent;
export const AgentInsightsWidget = NoopComponent;
export const MicroFeedbackWidget = NoopComponent;
export const DocumentEditor = NoopComponent;
export const DocumentViewer = NoopComponent;
export const DocumentEngineProvider = NoopComponent;
export const OperatorGatedAction = NoopComponent;
export const ActivationBanner = NoopComponent;
export const HelpTip = NoopComponent;
export const useActivationState = () => ({ steps: [], completed: false });
export const useOnboardingAnalytics = () => ({ track: noop });
export type ActivationStep = { id: string; label: string; completed: boolean };
export type CommandItem = { id: string; label: string; group?: string; action: () => void };
export type SentientAction = any;
export type SentientCrossLink = any;
export type SentientUpdate = any;

export default NoopComponent;

// Canonical operational-primitives contract for the self-contained offline build.
export type OperationalStatus = string;
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type ApprovalState = 'none' | 'pending' | 'approved' | 'rejected' | 'expired';
export type ActorType = 'user' | 'system' | 'agent';
export type DataState = 'live' | 'demo' | 'loading' | 'error' | 'seeded' | 'simulated' | 'unavailable';
export type OperationalOwner = {
  userId?: string | number;
  name?: string;
  email?: string;
  role?: string;
  assignedAt?: string;
};
export type EvidenceItem = {
  id: string;
  label: string;
  value: string;
  source?: string;
  confidence?: number;
  timestamp?: string;
};
export type AuditHistoryEntry = Record<string, unknown>;
export type EscalationPath = Record<string, unknown>;
export type NextAction = Record<string, unknown>;
export type OperationalEntity = Record<string, unknown> & { id: string | number };
export type StatusConfig = {
  label: string;
  color: string;
  bg: string;
  dotColor?: string;
  terminal?: boolean;
};

export const STATUS_CONFIGS: Record<string, StatusConfig> = {};
export const RISK_CONFIGS: Record<string, { label: string; color: string; bg: string; score: number }> = {};
export const APPROVAL_CONFIGS: Record<string, { label: string; color: string; bg: string }> = {};

const OFFLINE_LANE_ACCENT = {
  primary: '#f5f5f5',
  secondary: '#a3a3a3',
  muted: '#737373',
} as const;

export const LANE_ACCENT_HEX = {
  alloy: OFFLINE_LANE_ACCENT,
  lyte: OFFLINE_LANE_ACCENT,
  terra: OFFLINE_LANE_ACCENT,
  aegis: OFFLINE_LANE_ACCENT,
  vessels: OFFLINE_LANE_ACCENT,
  counsel: OFFLINE_LANE_ACCENT,
  carlota: OFFLINE_LANE_ACCENT,
  sentra: OFFLINE_LANE_ACCENT,
} as const;

export function getStatusConfig(status: string): StatusConfig {
  return { label: status, color: '#7c85a0', bg: 'rgba(124,133,160,0.08)' };
}

export function getRiskConfig(level: string) {
  return { label: level, color: '#7c85a0', bg: 'rgba(124,133,160,0.08)', score: 0 };
}

export function getApprovalConfig(state: string) {
  return { label: state, color: '#7c85a0', bg: 'rgba(124,133,160,0.08)' };
}

export function riskScoreToLevel(score: number): RiskLevel {
  if (score >= 0.85) return 'critical';
  if (score >= 0.65) return 'high';
  if (score >= 0.35) return 'medium';
  return 'low';
}

export function severityToRiskLevel(severity: string): RiskLevel {
  return severity === 'critical' || severity === 'high' || severity === 'medium'
    ? severity
    : 'low';
}

export function isTerminalStatus(status: string): boolean {
  return ['completed', 'succeeded', 'failed', 'cancelled', 'rejected', 'resolved', 'closed'].includes(status);
}

export function formatAgo(value?: string): string {
  return value || '—';
}

export function formatDuration(startedAt?: string, completedAt?: string): string {
  return startedAt && completedAt ? `${startedAt} – ${completedAt}` : '—';
}

export function useContactModal(_source?: string) {
  return {
    isOpen: false,
    open: noop,
    close: noop,
  };
}

export function useRealtimeChannel<T = unknown>(_channel: string) {
  return {
    lastMessage: null as T | null,
    isConnected: false,
    status: 'offline' as const,
  };
}

export const BatchPdfPanel = NoopComponent;
export const BillingAccount = NoopComponent;
export const ConstellationGraph = NoopComponent;
export const DocumentEnginePanel = NoopComponent;
export const GraphQLDataPanel = NoopComponent;
export const SigningDashboard = NoopComponent;
export const OperationalStatusBadge = NoopComponent;
export const OperationalRiskBadge = NoopComponent;
export const OperationalApprovalBadge = NoopComponent;
export const OperationalOwnerChip = NoopComponent;
export const OperationalEvidencePanel = NoopComponent;
export const OperationalAuditTimeline = NoopComponent;
export const OperationalEscalationPanel = NoopComponent;
export const OperationalDetailPane = NoopComponent;
export const OperationalQueueRow = NoopComponent;
