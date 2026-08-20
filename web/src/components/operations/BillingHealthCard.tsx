import { useBillingHealth, type BillingHealthSummary } from '@szl-holdings/billing-client';
import {
  AlertTriangle,
  CreditCard,
  DollarSign,
  FileText,
  RefreshCw,
  RotateCcw,
} from 'lucide-react';
import { Link } from 'wouter';

function isDemoMode(): boolean {
  try {
    const env = (import.meta as unknown as { env?: Record<string, unknown> }).env;
    return env?.VITE_BILLING_DEMO_MODE === 'true' || env?.VITE_BILLING_DEMO_MODE === true;
  } catch {
    return false;
  }
}

function fmtCurrency(cents: number, currency = 'usd'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

interface MetricChipProps {
  icon: React.ElementType;
  label: string;
  value: string | number;
  accent?: string;
  alert?: boolean;
}

function MetricChip({ icon: Icon, label, value, accent = '#d4a054', alert = false }: MetricChipProps) {
  return (
    <div
      className="flex flex-col gap-1 rounded-xl px-4 py-3 border"
      style={{
        background: alert ? 'rgba(239,68,68,0.05)' : 'rgba(255,255,255,0.02)',
        borderColor: alert ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className="w-3.5 h-3.5" style={{ color: alert ? '#ef4444' : accent }} />
        <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: 'rgba(255,255,255,0.35)' }}>
          {label}
        </span>
      </div>
      <span className="text-lg font-bold text-white tabular-nums">{value}</span>
    </div>
  );
}

export function BillingHealthCard() {
  const { data: health, loading, error, refetch } = useBillingHealth();

  // Demo badge ONLY when explicitly opted in via the env flag, OR the API
  // hands us back demo fixtures (e.g. when the server side runs without a
  // live Stripe key and signals it). Live data must never carry the badge.
  const envDemo = isDemoMode();
  const showDemo = envDemo || (health?.demo === true);

  const summary: BillingHealthSummary | null = health ?? null;

  return (
    <div
      className="rounded-2xl border p-5"
      style={{
        background: 'rgba(255,255,255,0.02)',
        borderColor: 'rgba(255,255,255,0.08)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <CreditCard className="w-4 h-4" style={{ color: '#d4a054' }} />
          <h2 className="text-sm font-semibold text-white">Billing Health</h2>
          {showDemo && (
            <span
              className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded"
              style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b' }}
            >
              demo
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            className="p-1 rounded transition-colors hover:bg-white/5"
            title="Refresh billing health"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} style={{ color: 'rgba(255,255,255,0.3)' }} />
          </button>
          <Link href="/account/billing" className="text-[11px] transition-opacity hover:opacity-70" style={{ color: '#d4a054' }}>
            View billing →
          </Link>
        </div>
      </div>

      {summary ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricChip
              icon={DollarSign}
              label="MRR"
              value={fmtCurrency(summary.mrr, summary.mrrCurrency)}
              accent="#22c55e"
            />
            <MetricChip
              icon={FileText}
              label="Open invoices"
              value={fmtCurrency(summary.openInvoicesTotal, summary.openInvoicesCurrency)}
              accent="#d4a054"
              alert={summary.openInvoicesTotal > 0}
            />
            <MetricChip
              icon={AlertTriangle}
              label="Past due"
              value={summary.pastDueCount}
              accent="#ef4444"
              alert={summary.pastDueCount > 0}
            />
            <MetricChip
              icon={RotateCcw}
              label="Refund queue"
              value={summary.refundQueueDepth}
              accent="#8b5cf6"
              alert={summary.refundQueueDepth > 0}
            />
          </div>

          {(summary.pastDueCount > 0 || summary.refundQueueDepth > 0) && (
            <div
              className="mt-3 flex items-center gap-2 text-[12px] px-3 py-2 rounded-lg"
              style={{ background: 'rgba(239,68,68,0.06)', color: '#fca5a5' }}
            >
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-red-400" />
              {summary.pastDueCount > 0 && (
                <span>
                  {summary.pastDueCount} past-due {summary.pastDueCount === 1 ? 'account requires' : 'accounts require'} attention.
                </span>
              )}
              {summary.refundQueueDepth > 0 && (
                <span className="ml-1">
                  {summary.refundQueueDepth} refund {summary.refundQueueDepth === 1 ? 'request' : 'requests'} pending.
                </span>
              )}
            </div>
          )}
        </>
      ) : (
        <div
          className="flex items-center gap-2 text-[12px] px-3 py-3"
          style={{ color: 'rgba(255,255,255,0.35)' }}
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>
            {error
              ? `Billing data unavailable — ${error}`
              : loading
                ? 'Loading billing data…'
                : 'Billing data unavailable — configure the API server to see live metrics.'}
          </span>
        </div>
      )}
    </div>
  );
}
