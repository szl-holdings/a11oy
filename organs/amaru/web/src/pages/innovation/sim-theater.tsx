import { useState } from 'react';
import { Link } from 'wouter';
import { RELAY_MAPPINGS, RELAY_DESTINATIONS, AMARU_AGENTS } from '@/data/fabric';
import { FabricHeader, FabricCard, FabricStat, SeverityChip } from '@/components/fabric/primitives';
import { Badge, Button } from '@/components/ui';
import { ArrowLeft, Play, Square, Zap, AlertTriangle, CheckCircle, XCircle, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

type FailureInjection = 'none' | 'rate_limit' | 'schema_mismatch' | 'pii_flagged' | 'destination_5xx' | 'auth_expired';
type EventType = 'info' | 'warn' | 'error' | 'success' | 'agent';

interface SimEvent {
  readonly id: string;
  readonly agentId: string | null;
  readonly type: EventType;
  readonly message: string;
  readonly atMs: number;
}

interface SimRun {
  readonly id: string;
  readonly mappingId: string;
  readonly failure: FailureInjection;
  readonly events: SimEvent[];
  readonly outcome: 'success' | 'degraded' | 'failed';
  readonly durationMs: number;
  readonly recordsAttempted: number;
  readonly recordsDelivered: number;
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}
function hex8(n: number) { return n.toString(16).padStart(8, '0').slice(0, 8); }

const FAILURE_LABELS: Record<FailureInjection, string> = {
  none: 'No failure (clean run)',
  rate_limit: 'Rate limit hit',
  schema_mismatch: 'Schema mismatch',
  pii_flagged: 'PII flag triggered',
  destination_5xx: 'Destination 5xx',
  auth_expired: 'Auth expired',
};

function buildSimEvents(mappingId: string, failure: FailureInjection): Omit<SimRun, 'id'> {
  const events: SimEvent[] = [];
  let atMs = 0;
  const push = (agentId: string | null, type: EventType, message: string) => {
    events.push({ id: `ev-${events.length}`, agentId, type, message, atMs });
    atMs += 80 + fnv1a(`${atMs}:${message}`) % 120;
  };

  const mapping = RELAY_MAPPINGS.find((m) => m.id === mappingId);
  const dest = RELAY_DESTINATIONS.find((d) => d.id === mapping?.destinationId);
  const records = 24000;

  push('cartographer', 'info', `Cartographer: snapshot frozen at 2026-05-05T03:55:00Z (${records.toLocaleString()} records)`);
  push('cartographer', 'info', `Cartographer: schema profile validated — ${mapping?.mappedFieldCount ?? 12} fields, 0 drift detected`);
  push('mapper', 'agent', `Mapper: confidence=${mapping?.confidence.toFixed(2) ?? '0.87'}, proposing ${mapping?.transformations.length ?? 4} transforms`);
  push('sentinel', 'info', `Sentinel: policy gate evaluation — ${mapping?.governanceState === 'red' ? 'BLOCKED' : 'PASS'}`);

  if (failure === 'rate_limit') {
    push('courier', 'warn', `Courier: batch 3/120 — rate limit hit (${dest?.rateLimitRpm ?? 300} rpm envelope)`);
    push('courier', 'warn', `Courier: backoff applied — 1.8s delay, retry queue: 200 records`);
    push('fixer', 'agent', `Fixer: detected rate_limit pattern — adjusting batch size from 200 → 120`);
    push('courier', 'info', `Courier: resumed with reduced batch — throughput 60% of nominal`);
    push('verity', 'info', `Verity: field-contract assertions passed on delivered records`);
    push(null, 'success', `Run complete — degraded (rate limited). ${Math.round(records * 0.91).toLocaleString()} / ${records.toLocaleString()} delivered`);
    return { mappingId, failure, events, outcome: 'degraded', durationMs: atMs, recordsAttempted: records, recordsDelivered: Math.round(records * 0.91) };
  }

  if (failure === 'schema_mismatch') {
    push('courier', 'warn', `Courier: batch 1/120 — destination rejected field 'tax_id' (not in contract)`);
    push('fixer', 'agent', `Fixer: schema mismatch detected — consulting Mapper for fallback transform`);
    push('mapper', 'agent', `Mapper: proposing drop 'tax_id' from delivery set (confidence: 0.79)`);
    push('sentinel', 'warn', `Sentinel: schema mismatch policy — emitting governance event gov-evt-${hex8(fnv1a('schema_mismatch'))}`);
    push('courier', 'error', `Courier: cannot resolve mismatch without operator approval — halting run`);
    push(null, 'error', `Run failed — schema mismatch. 0 / ${records.toLocaleString()} delivered. Approval gate raised.`);
    return { mappingId, failure, events, outcome: 'failed', durationMs: atMs, recordsAttempted: records, recordsDelivered: 0 };
  }

  if (failure === 'pii_flagged') {
    push('sentinel', 'warn', `Sentinel: PII class 'financial' detected in field 'mrr_cents' — destination piiAllowed=${dest?.piiAllowed ?? false}`);
    push('sentinel', 'agent', `Sentinel: applying redaction transform — mrr_cents → [REDACTED]`);
    push('courier', 'info', `Courier: delivering with redacted financial fields (${records.toLocaleString()} records)`);
    push('verity', 'info', `Verity: PII-redacted delivery contract satisfied`);
    push('scribe', 'agent', `Scribe: PII event logged to proof ledger — anchor ${hex8(fnv1a('pii_flagged:' + mappingId))}`);
    push(null, 'success', `Run complete — pii redacted. ${records.toLocaleString()} / ${records.toLocaleString()} delivered (financial fields masked)`);
    return { mappingId, failure, events, outcome: 'success', durationMs: atMs, recordsAttempted: records, recordsDelivered: records };
  }

  if (failure === 'destination_5xx') {
    push('courier', 'warn', `Courier: batch 8/120 — destination returned HTTP 503`);
    push('courier', 'warn', `Courier: retrying with exponential backoff — attempt 1/3`);
    push('courier', 'error', `Courier: destination 503 persists after 3 retries — triggering rollback`);
    push('fixer', 'agent', `Fixer: rollback initiated — reversing last 1,600 delivered records`);
    push('sentinel', 'error', `Sentinel: destination_5xx policy triggered — quarantine for ${dest?.name ?? 'destination'}`);
    push('scribe', 'agent', `Scribe: incident logged — anchor ${hex8(fnv1a('5xx:' + mappingId))}`);
    push(null, 'error', `Run failed + rolled back. 0 net records delivered. Incident raised.`);
    return { mappingId, failure, events, outcome: 'failed', durationMs: atMs, recordsAttempted: records, recordsDelivered: 0 };
  }

  if (failure === 'auth_expired') {
    push('courier', 'error', `Courier: batch 1/120 — HTTP 401 Unauthorized (auth token expired)`);
    push('fixer', 'agent', `Fixer: auth_expired detected — pausing run, emitting rotation alert`);
    push('sentinel', 'error', `Sentinel: auth policy violated — destination ${dest?.name ?? 'destination'} blocked pending rotation`);
    push(null, 'error', `Run blocked — auth expired. 0 / ${records.toLocaleString()} delivered. Rotate credentials to resume.`);
    return { mappingId, failure, events, outcome: 'failed', durationMs: atMs, recordsAttempted: records, recordsDelivered: 0 };
  }

  // clean run
  push('courier', 'info', `Courier: batch delivery started — ${records.toLocaleString()} records across ${Math.ceil(records / 200)} batches`);
  push('verity', 'info', `Verity: field-contract assertions running per batch`);
  push('forecaster', 'agent', `Forecaster: predicted lift 6.2% — within confidence bounds`);
  push('scribe', 'agent', `Scribe: run events logged to proof ledger — anchor ${hex8(fnv1a('clean:' + mappingId))}`);
  push(null, 'success', `Run complete — clean. ${records.toLocaleString()} / ${records.toLocaleString()} delivered`);
  return { mappingId, failure, events, outcome: 'success', durationMs: atMs, recordsAttempted: records, recordsDelivered: records };
}

const EVENT_ICON: Record<EventType, React.ReactNode> = {
  info: <span className="w-1.5 h-1.5 rounded-full bg-[#8a8a8a] inline-block" />,
  warn: <AlertTriangle className="w-3 h-3 text-[#d4a853]" />,
  error: <XCircle className="w-3 h-3 text-[#b85450]" />,
  success: <CheckCircle className="w-3 h-3 text-[#5a8a6e]" />,
  agent: <Zap className="w-3 h-3 text-[#c9b787]" />,
};

const EVENT_TEXT: Record<EventType, string> = {
  info: 'text-[#8a8a8a]',
  warn: 'text-[#d4a853]',
  error: 'text-[#b85450]',
  success: 'text-[#5a8a6e]',
  agent: 'text-[#c9b787]',
};

export default function SimTheaterPage() {
  const [selectedMappingId, setSelectedMappingId] = useState(RELAY_MAPPINGS[0]?.id ?? '');
  const [selectedFailure, setSelectedFailure] = useState<FailureInjection>('none');
  const [runs, setRuns] = useState<SimRun[]>([]);
  const [running, setRunning] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  const startRun = () => {
    if (!selectedMappingId) return;
    setRunning(true);
    setTimeout(() => {
      const run: SimRun = {
        id: `run-${hex8(fnv1a(`${selectedMappingId}:${selectedFailure}:${runs.length}`))}`,
        ...buildSimEvents(selectedMappingId, selectedFailure),
      };
      setRuns((prev) => [run, ...prev]);
      setExpandedRunId(run.id);
      setRunning(false);
    }, 900);
  };

  const successCount = runs.filter((r) => r.outcome === 'success').length;
  const failedCount = runs.filter((r) => r.outcome === 'failed').length;

  return (
    <div>
      <FabricHeader
        eyebrow="ONE-OF-ONE · 07"
        title="Activation Simulation Theater"
        blurb="Replay any sync against a frozen state snapshot. Inject failures (rate limit, schema mismatch, PII flag, destination outage, auth expired) and watch the full agent coalition respond event by event."
        trailing={
          <Link href="/innovation" className="flex items-center gap-1.5 text-[11px] text-[#c9b787] hover:underline">
            <ArrowLeft className="w-3 h-3" /> Innovation Brief
          </Link>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="Runs simulated" value={runs.length} tone="gold" />
        <FabricStat label="Clean" value={successCount} tone="good" />
        <FabricStat label="Degraded" value={runs.filter((r) => r.outcome === 'degraded').length} tone="warn" />
        <FabricStat label="Failed" value={failedCount} tone={failedCount > 0 ? 'bad' : 'neutral'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <FabricCard title="SIMULATION CONTROLS">
          <div className="space-y-4">
            <div>
              <div className="label-mono mb-2">SYNC TO REPLAY</div>
              <select
                value={selectedMappingId}
                onChange={(e) => setSelectedMappingId(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-transparent px-3 text-sm"
              >
                {RELAY_MAPPINGS.slice(0, 14).map((m) => {
                  const dest = RELAY_DESTINATIONS.find((d) => d.id === m.destinationId);
                  return <option key={m.id} value={m.id}>{m.name} → {dest?.name ?? m.destinationId}</option>;
                })}
              </select>
            </div>

            <div>
              <div className="label-mono mb-2">FAILURE INJECTION</div>
              <div className="space-y-1">
                {(Object.keys(FAILURE_LABELS) as FailureInjection[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setSelectedFailure(f)}
                    className="flex items-center gap-3 w-full text-left px-3 py-2 rounded border transition-all text-[12px]"
                    style={{ borderColor: selectedFailure === f ? '#c9b787' : 'rgba(255,255,255,0.06)', background: selectedFailure === f ? 'rgba(201,183,135,0.05)' : 'transparent' }}
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 ${f === 'none' ? 'bg-[#5a8a6e]' : 'bg-[#b85450]'}`} />
                    <span className="text-[#f5f5f5] flex-1">{FAILURE_LABELS[f]}</span>
                    {selectedFailure === f && <span className="text-[10px] font-mono text-[#c9b787]">selected</span>}
                  </button>
                ))}
              </div>
            </div>

            <Button onClick={startRun} isLoading={running} className="w-full">
              {running ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
              Run Simulation
            </Button>
          </div>
        </FabricCard>

        <FabricCard title="AGENT COALITION">
          <div className="space-y-2">
            {AMARU_AGENTS.map((agent) => {
              const axisColor: Record<string, string> = { P: '#78aac8', K: '#5a8a6e', 'Φ': '#c9b787', C: '#d4a853' };
              const color = axisColor[agent.lutarAxisAffinity] ?? '#8a8a8a';
              return (
                <div key={agent.id} className="flex items-center gap-3 p-2 rounded text-[12px]" style={{ background: '#0e0e0e' }}>
                  <div className="w-6 h-6 rounded flex items-center justify-center shrink-0" style={{ background: `${color}18` }}>
                    <span style={{ color, fontSize: '0.7rem' }}>⬡</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-[#f5f5f5]">{agent.name}</div>
                    <div className="text-[10px] text-[#666] truncate">{agent.role}</div>
                  </div>
                  <span className="font-mono text-[10px]" style={{ color }}>{Math.round(agent.approvalRate * 100)}%</span>
                </div>
              );
            })}
          </div>
        </FabricCard>
      </div>

      {runs.length > 0 && (
        <div className="space-y-3">
          <div className="label-mono text-[#c9b787]">SIMULATION RUNS ({runs.length})</div>
          {runs.map((run) => {
            const mapping = RELAY_MAPPINGS.find((m) => m.id === run.mappingId);
            const isExpanded = expandedRunId === run.id;
            return (
              <div key={run.id} className="conduit-card overflow-hidden">
                <button className="w-full p-4 text-left" onClick={() => setExpandedRunId(isExpanded ? null : run.id)}>
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      {run.outcome === 'success' ? <CheckCircle className="w-4 h-4 text-[#5a8a6e]" /> : run.outcome === 'degraded' ? <AlertTriangle className="w-4 h-4 text-[#d4a853]" /> : <XCircle className="w-4 h-4 text-[#b85450]" />}
                      <div>
                        <div className="text-[#f5f5f5] text-sm">{mapping?.name ?? run.mappingId}</div>
                        <div className="text-[11px] text-[#666]">{FAILURE_LABELS[run.failure]} · {run.recordsDelivered.toLocaleString()}/{run.recordsAttempted.toLocaleString()} records · {run.durationMs.toLocaleString()}ms</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={run.outcome === 'success' ? 'success' : run.outcome === 'degraded' ? 'partial' : 'failed'}>{run.outcome}</Badge>
                      {isExpanded ? <ChevronUp className="w-4 h-4 text-[#666]" /> : <ChevronDown className="w-4 h-4 text-[#666]" />}
                    </div>
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-[rgba(255,255,255,0.04)] p-4 animate-fade-in">
                    <div className="label-mono mb-3">EVENT TIMELINE</div>
                    <div className="space-y-1.5 font-mono text-[11px]">
                      {run.events.map((ev) => (
                        <div key={ev.id} className="flex items-start gap-2">
                          <span className="text-[#444] shrink-0 tabular-nums w-14">+{ev.atMs}ms</span>
                          <span className="shrink-0 mt-0.5">{EVENT_ICON[ev.type]}</span>
                          {ev.agentId && <span className="text-[#c9b787] shrink-0 w-20">[{ev.agentId}]</span>}
                          <span className={EVENT_TEXT[ev.type]}>{ev.message.replace(/^[^:]+: /, '')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {runs.length === 0 && (
        <div className="text-center py-16 text-[#555]">
          <Square className="w-8 h-8 mx-auto mb-3 text-[#333]" />
          <div className="text-sm">No runs yet. Select a sync, inject a failure (or not), and run the simulation.</div>
        </div>
      )}
    </div>
  );
}
