/**
 * Detector Framework — operator view for the canonical
 * Detector / DetectorRun / Finding contract shipped by
 * `packages/sentra-detector-sdk`. Reads directly from the new
 * `/api/sentra/detectors` and `/api/sentra/findings` routes so this
 * page doubles as the round-trip target for the e2e spec at
 * `tests/e2e/detector-framework.spec.ts`.
 *
 * Intentionally minimal: this is the "alerts surface" for the new
 * framework, not a redesign of the existing alerts/findings pages.
 */
import { useEffect, useState } from 'react';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@szl-holdings/shared-ui/ui/card';

type DetectorRow = {
  id: string;
  label: string;
  description: string;
  runtime: 'ts' | 'py';
  kind: string;
  version: string | null;
  registeredAt: string;
  lastSeenAt: string;
};

type FindingRow = {
  id: string;
  detectorId: string;
  runId: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  title: string;
  summary: string;
  chainReceiptId: string | null;
  emittedAt: string;
};

const sevColor: Record<FindingRow['severity'], string> = {
  critical: 'bg-red-600 text-white',
  high: 'bg-orange-500 text-white',
  medium: 'bg-yellow-500 text-black',
  low: 'bg-blue-500 text-white',
  info: 'bg-zinc-500 text-white',
};

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: 'include' });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export default function DetectorFrameworkPage() {
  const [detectors, setDetectors] = useState<DetectorRow[]>([]);
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [d, f] = await Promise.all([
          fetchJson<{ detectors: DetectorRow[] }>('/api/sentra/detectors'),
          fetchJson<{ findings: FindingRow[] }>('/api/sentra/findings?limit=50'),
        ]);
        if (cancelled) return;
        setDetectors(d.detectors ?? []);
        setFindings(f.findings ?? []);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="p-6 space-y-6" data-testid="detector-framework-page">
      <header>
        <h1 className="text-2xl font-semibold">Detector Framework</h1>
        <p className="text-sm text-muted-foreground">
          Canonical detector registry &amp; live findings from
          <code className="mx-1">/api/sentra/detectors</code> +
          <code className="mx-1">/api/sentra/findings</code>.
        </p>
      </header>

      {loading && <p data-testid="df-loading">Loading…</p>}
      {error && (
        <p className="text-red-500" data-testid="df-error">
          {error}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            Registered detectors{' '}
            <span data-testid="df-detector-count">({detectors.length})</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2" data-testid="df-detector-list">
            {detectors.map((d) => (
              <li
                key={d.id}
                data-testid={`df-detector-${d.id}`}
                className="border rounded p-2 text-sm flex items-center justify-between"
              >
                <span>
                  <strong>{d.label}</strong>{' '}
                  <span className="text-muted-foreground">({d.id})</span>
                </span>
                <Badge>{d.runtime}</Badge>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            Recent findings{' '}
            <span data-testid="df-finding-count">({findings.length})</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2" data-testid="df-finding-list">
            {findings.map((f) => (
              <li
                key={f.id}
                data-testid={`df-finding-${f.id}`}
                data-detector-id={f.detectorId}
                data-chain-receipt={f.chainReceiptId ?? ''}
                className="border rounded p-2 text-sm flex items-start justify-between gap-3"
              >
                <div>
                  <div className="font-medium">{f.title}</div>
                  <div className="text-muted-foreground text-xs">
                    {f.detectorId} · {new Date(f.emittedAt).toLocaleString()}
                  </div>
                </div>
                <Badge className={sevColor[f.severity]}>{f.severity}</Badge>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
