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
