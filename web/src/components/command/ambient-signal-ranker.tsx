import { useState, useEffect } from "react";
import { TrendingUp, AlertTriangle, Info, Clock, ArrowRight, RefreshCw } from "lucide-react";

interface AmbientSignal {
  id: string;
  domain: string;
  title: string;
  summary: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  score: number;
  timestamp: number;
  actionUrl?: string;
  actionLabel?: string;
  correlatedDomains?: string[];
  signalChainActive?: boolean;
  live?: boolean;
}

const DOMAIN_COLORS: Record<string, string> = {
  firestorm: "#ef4444",
  aegis: "#ef4444",
  vessels: "var(--gi-accent-blue)",
  terra: "#22c55e",
  prism: "#8b5cf6",
  lyte: "#f59e0b",
  "szl-holdings": "#8b7ac8",
  carlota: "#ec4899",
};

const DOMAIN_LABELS: Record<string, string> = {
  firestorm: "PARAGON",
  aegis: "PARAGON",
  vessels: "SEXTANT",
  terra: "DOMAINE",
  prism: "PRISM",
  lyte: "KORA",
  "szl-holdings": "Holdings",
  carlota: "Carlota Jo",
};

const SEVERITY_ICON: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="w-3.5 h-3.5" />,
  high: <AlertTriangle className="w-3.5 h-3.5" />,
  medium: <TrendingUp className="w-3.5 h-3.5" />,
  low: <Info className="w-3.5 h-3.5" />,
  info: <Info className="w-3.5 h-3.5" />,
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#3b82f6",
  low: "#6b7280",
  info: "#22c55e",
};

function timeAgo(ts: number) {
  const diff = Date.now() - ts;
  if (diff < 60000) return "Just now";
  if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.round(diff / 3600000)}h ago`;
  return `${Math.round(diff / 86400000)}d ago`;
}

const STATIC_SIGNALS: AmbientSignal[] = [
  {
    id: "sig-critical-1",
    domain: "firestorm",
    title: "APT-41 Lateral Movement Detected",
    summary: "Nation-state threat actor active across 3 subsidiaries. Legal hold triggered. Risk score elevated 72→81.",
    severity: "critical",
    score: 0.97,
    timestamp: Date.now() - 1800000,
    correlatedDomains: ["prism", "szl-holdings"],
    signalChainActive: true,
    actionLabel: "View Incident",
  },
  {
    id: "sig-high-1",
    domain: "vessels",
    title: "Port Delay: MV Pacific Star +32h",
    summary: "Shanghai congestion causing 32-hour delay. 12 DOMAINE properties and 8 PRISM contracts flagged via signal chain.",
    severity: "high",
    score: 0.88,
    timestamp: Date.now() - 3600000,
    correlatedDomains: ["terra", "prism"],
    signalChainActive: true,
    actionLabel: "View Fleet",
  },
  {
    id: "sig-high-2",
    domain: "terra",
    title: "18 Properties Above Distress Threshold",
    summary: "Rate volatility refresh flagged 18 properties. Correlated with market volatility signal from Holdings.",
    severity: "high",
    score: 0.79,
    timestamp: Date.now() - 7200000,
    correlatedDomains: ["szl-holdings"],
    actionLabel: "View Portfolio",
  },
  {
    id: "sig-medium-1",
    domain: "szl-holdings",
    title: "Market Volatility Index: 0.72",
    summary: "Threshold crossed. Portfolio rebalance signal chain triggered across DOMAINE, SEXTANT, and fund ops.",
    severity: "medium",
    score: 0.71,
    timestamp: Date.now() - 3600000,
    correlatedDomains: ["terra", "vessels"],
    signalChainActive: true,
    actionLabel: "View Dashboard",
  },
  {
    id: "sig-medium-2",
    domain: "prism",
    title: "Judicial Pattern Shift: SDNY",
    summary: "Ruling pattern shift in Southern District detected. Strategy brief update recommended for 3 active matters.",
    severity: "medium",
    score: 0.66,
    timestamp: Date.now() - 172800000,
    actionLabel: "View Patterns",
  },
  {
    id: "sig-info-1",
    domain: "lyte",
    title: "Self-Healing: 94% Autonomous Resolve",
    summary: "Highest self-healing rate on record. KORA autonomously resolved all P1 incidents without human intervention.",
    severity: "info",
    score: 0.38,
    timestamp: Date.now() - 86400000,
    actionLabel: "View Platform",
  },
];

interface AmbientSignalRankerProps {
  apiBase?: string;
}

export function AmbientSignalRanker({ apiBase = "" }: AmbientSignalRankerProps) {
  const [signals, setSignals] = useState<AmbientSignal[]>(STATIC_SIGNALS);
  const [loading, setLoading] = useState(false);
  const [isDemo, setIsDemo] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(Date.now());

  async function fetchSignals() {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/innovation-engine/ambient-signals`);
      if (res.ok) {
        const data: AmbientSignal[] = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          const enriched = data.map((s) => ({
            ...s,
            correlatedDomains: STATIC_SIGNALS.find((st) => st.domain === s.domain)?.correlatedDomains,
            signalChainActive: STATIC_SIGNALS.find((st) => st.domain === s.domain)?.signalChainActive,
            live: s.live === true,
          }));
          setSignals(enriched.sort((a, b) => b.score - a.score));
          setIsDemo(false);
          return;
        }
      }
      setSignals(STATIC_SIGNALS);
      setIsDemo(true);
    } catch {
      setSignals(STATIC_SIGNALS);
      setIsDemo(true);
    } finally {
      setLoading(false);
      setLastRefreshed(Date.now());
    }
  }

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 120000);
    return () => clearInterval(interval);
  }, []);

  const topSignals = signals.slice(0, 6);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-bold tracking-widest uppercase" style={{ color: "var(--color-fg-muted)" }}>
            Ambient Signal Ranker
          </h2>
          {!loading && isDemo && (
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
              title="Showing illustrative demo data — live API unavailable"
              style={{
                color: "#f59e0b",
                backgroundColor: "color-mix(in srgb, #f59e0b 12%, transparent)",
                border: "1px solid color-mix(in srgb, #f59e0b 30%, transparent)",
              }}
            >
              Demo
            </span>
          )}
          {!loading && !isDemo && (
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded inline-flex items-center gap-1"
              title="Connected to live data"
              style={{
                color: "#22c55e",
                backgroundColor: "color-mix(in srgb, #22c55e 12%, transparent)",
                border: "1px solid color-mix(in srgb, #22c55e 30%, transparent)",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ backgroundColor: "#22c55e" }}
              />
              Live
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono flex items-center gap-1" style={{ color: "var(--color-fg-muted)" }}>
            <Clock className="w-3 h-3" />
            {timeAgo(lastRefreshed)}
          </span>
          <button
            onClick={fetchSignals}
            disabled={loading}
            className="text-[10px] flex items-center gap-1 px-2 py-1 rounded transition-opacity hover:opacity-80 disabled:opacity-40"
            style={{ backgroundColor: "var(--color-surface-base)", border: "1px solid var(--color-surface-border)", color: "var(--color-fg-muted)" }}
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {topSignals.map((sig, idx) => {
          const domainColor = DOMAIN_COLORS[sig.domain] ?? "#6b7280";
          const severityColor = SEVERITY_COLOR[sig.severity] ?? "#6b7280";
          const label = DOMAIN_LABELS[sig.domain] ?? sig.domain;

          return (
            <div
              key={sig.id}
              className="flex items-start gap-4 p-4 rounded-xl transition-all hover:scale-[1.005]"
              style={{
                backgroundColor: "var(--color-bg-elevated)",
                border: "1px solid var(--color-surface-border)",
                borderLeftWidth: "3px",
                borderLeftColor: severityColor,
              }}
            >
              <div className="flex flex-col items-center gap-1 shrink-0" style={{ minWidth: "32px" }}>
                <span
                  className="text-[10px] font-mono font-bold w-6 h-6 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: "var(--color-surface-base)", color: "var(--color-fg-muted)" }}
                >
                  {idx + 1}
                </span>
                <div className="text-[9px] font-bold" style={{ color: severityColor }}>
                  {Math.round(sig.score * 100)}
                </div>
              </div>

              <div className="flex-1 min-w-0 flex flex-col gap-1.5">
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                      style={{ color: domainColor, backgroundColor: `color-mix(in srgb, ${domainColor} 12%, transparent)`, border: `1px solid color-mix(in srgb, ${domainColor} 25%, transparent)` }}
                    >
                      {label}
                    </span>
                    {sig.live && (
                      <span
                        className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded inline-flex items-center gap-1"
                        style={{ color: "#22c55e", backgroundColor: "color-mix(in srgb, #22c55e 12%, transparent)", border: "1px solid color-mix(in srgb, #22c55e 25%, transparent)" }}
                        title={`Real-time data from ${label} database`}
                        aria-label={`Real-time data from ${label} database`}
                        data-testid={`live-indicator-${sig.domain}`}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full animate-pulse"
                          style={{ backgroundColor: "#22c55e", boxShadow: "0 0 4px #22c55e" }}
                        />
                        Live
                      </span>
                    )}
                    {sig.signalChainActive && (
                      <span
                        className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded flex items-center gap-1"
                        style={{ color: "#8b7ac8", backgroundColor: "color-mix(in srgb, #8b7ac8 10%, transparent)", border: "1px solid color-mix(in srgb, #8b7ac8 25%, transparent)" }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                        Chain Active
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-[10px]" style={{ color: severityColor }}>
                    {SEVERITY_ICON[sig.severity]}
                    <span className="font-bold uppercase">{sig.severity}</span>
                  </div>
                </div>

                <h3 className="text-sm font-bold leading-tight" style={{ color: "var(--color-fg-primary)" }}>
                  {sig.title}
                </h3>

                <p className="text-[11px] leading-relaxed" style={{ color: "var(--color-fg-muted)" }}>
                  {sig.summary}
                </p>

                <div className="flex items-center justify-between gap-3 mt-1 flex-wrap">
                  <div className="flex items-center gap-2">
                    {sig.correlatedDomains?.map((cd) => (
                      <span
                        key={cd}
                        className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                        style={{ color: DOMAIN_COLORS[cd] ?? "#6b7280", backgroundColor: `color-mix(in srgb, ${DOMAIN_COLORS[cd] ?? "#6b7280"} 10%, transparent)` }}
                      >
                        ↔ {DOMAIN_LABELS[cd] ?? cd}
                      </span>
                    ))}
                  </div>
                  <span className="text-[10px] font-mono" style={{ color: "var(--color-fg-muted)" }}>
                    {timeAgo(sig.timestamp)}
                  </span>
                </div>
              </div>

              {sig.actionLabel && (
                <button
                  className="shrink-0 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-1.5 rounded-lg transition-opacity hover:opacity-80"
                  style={{ backgroundColor: `color-mix(in srgb, ${severityColor} 12%, transparent)`, color: severityColor, border: `1px solid color-mix(in srgb, ${severityColor} 25%, transparent)` }}
                >
                  {sig.actionLabel}
                  <ArrowRight className="w-3 h-3" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
