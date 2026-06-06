import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  CheckCircle2,
  Database,
  Eye,
  FileText,
  Globe,
  HardDrive,
  Key,
  Layers,
  Network,
  RefreshCw,
  Server,
  Shield,
  Timer,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useState } from 'react';
import { api } from '../lib/api';

interface Honeypot {
  id: string;
  name: string;
  type: string;
  ip: string;
  os: string;
  status: string;
  interactions: number;
  iocsPushed: number;
  deceptionScore: number;
  lastHit?: string;
  lastInteraction?: string;
  deployedAt: string;
  generated?: string;
  attackerProfile?: string;
}

interface DeceptionEvent {
  id: string;
  time: string;
  honeypot: string;
  event: string;
  severity: string;
  attackerIp?: string;
  technique?: string;
  intel?: string;
  pushedToFeed: boolean;
}

const typeIcon: Record<string, typeof Server> = {
  server: Server,
  database: Database,
  credential: Key,
  fileshare: HardDrive,
  api: Globe,
  email: FileText,
};

const typeColor: Record<string, string> = {
  server: '#c9b787',
  database: '#8a8a8a',
  credential: '#c9b787',
  fileshare: '#c9b787',
  api: '#8a8a8a',
  email: '#c9b787',
};

const statusConfig: Record<string, { color: string; label: string }> = {
  active: { color: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30', label: 'Active' },
  engaged: { color: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30', label: 'Engaged' },
  triggered: { color: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/30', label: '🔴 Triggered' },
  adapting: { color: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30', label: 'Adapting' },
};

function relTime(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return iso;
  }
}

export default function DeceptionGrid() {
  const qc = useQueryClient();
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const honeypotsQuery = useStandardQuery({
    queryKey: ['deception', 'honeypots'],
    queryFn: () => api.deception.honeypots(),
    refetchInterval: 20000,
  });

  const eventsQuery = useStandardQuery({
    queryKey: ['deception', 'events'],
    queryFn: () => api.deception.events(),
    refetchInterval: 10000,
  });

  type HoneypotsResponse = {
    data?: {
      honeypots?: Honeypot[];
      totalInteractions?: number;
      avgDeception?: number;
      intelItems?: number;
    };
  };
  type EventsResponse = { data?: { events?: DeceptionEvent[] } };

  const deployMutation = useStandardMutation({
    mutationFn: () => api.deception.deployHoneypot(),
    onSuccess: (data: { data?: { message?: string } }) => {
      qc.invalidateQueries({ queryKey: ['deception', 'honeypots'] });
      toast.success(data?.data?.message ?? 'New honeypot deployed');
    },
    onError: () => toast.error('Failed to deploy honeypot'),
  });

  const pushIocMutation = useStandardMutation({
    mutationFn: (eventId: string) => api.deception.pushIoc(eventId),
    onSuccess: (data: { data?: { message?: string } }) => {
      qc.invalidateQueries({ queryKey: ['deception', 'events'] });
      toast.success(data?.data?.message ?? 'IOC pushed to threat intel feeds');
    },
    onError: () => toast.error('Failed to push IOC'),
  });

  const honeypotsData = (honeypotsQuery.data as HoneypotsResponse | null)?.data;
  const honeypots: Honeypot[] = honeypotsData?.honeypots ?? [];
  const totalInteractions: number = honeypotsData?.totalInteractions ?? 0;
  const avgDeception: number = honeypotsData?.avgDeception ?? 0;
  const intelItems: number = honeypotsData?.intelItems ?? 0;

  const events: DeceptionEvent[] = (eventsQuery.data as EventsResponse | null)?.data?.events ?? [];
  const selectedEvent = events.find((e) => e.id === selectedEventId) ?? events[0] ?? null;

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Eye className="w-5 h-5 text-[#8a8a8a]" />
            <h1 className="text-lg font-semibold text-white">Threat Decoys</h1>
          </div>
          <p className="text-xs text-zinc-500">
            Generative AI creates hyper-realistic fake assets. Honeypots adapt to attacker
            interaction patterns in real time.
          </p>
        </div>
        <button
          onClick={() => deployMutation.mutate()}
          disabled={deployMutation.isPending}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#8a8a8a]/15 border border-[#8a8a8a]/30 text-[#8a8a8a] text-xs font-medium hover:bg-[#8a8a8a]/25 transition-colors disabled:opacity-50"
        >
          {deployMutation.isPending ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Deploying...
            </>
          ) : (
            <>
              <Zap className="w-3.5 h-3.5" /> Deploy New Decoy
            </>
          )}
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Active Honeypots',
            value: honeypots.length || '—',
            sub: 'across 4 network segments',
            color: '#8a8a8a',
            icon: Eye,
          },
          {
            label: 'Total Interactions',
            value: totalInteractions || '—',
            sub: 'attacker engagements captured',
            color: '#f5f5f5',
            icon: Activity,
          },
          {
            label: 'Threat Intel Items',
            value: intelItems || '—',
            sub: 'extracted from attacker behavior',
            color: '#c9b787',
            icon: TrendingUp,
          },
          {
            label: 'Avg Deception Score',
            value: avgDeception ? `${avgDeception}%` : '—',
            sub: 'realism rating',
            color: '#c9b787',
            icon: Shield,
          },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-2xl font-bold text-white">
                {honeypotsQuery.isLoading ? (
                  <span className="text-zinc-500 text-lg">loading…</span>
                ) : (
                  m.value
                )}
              </div>
              <div className="text-xs text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Honeypot Grid */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Deception Assets
          </h2>
          {honeypotsQuery.isLoading ? (
            <div className="text-xs text-zinc-500 text-center py-8">Loading honeypots…</div>
          ) : (
            <div className="grid grid-cols-1 gap-2">
              {honeypots.map((hp: Honeypot) => {
                const Icon = typeIcon[hp.type] ?? Server;
                const sc = statusConfig[hp.status] ?? statusConfig.active;
                return (
                  <div
                    key={hp.id}
                    className={cn(
                      'rounded-xl border p-3 transition-all',
                      hp.status === 'triggered'
                        ? 'border-[#f5f5f5]/30 bg-[#f5f5f5]/5'
                        : 'border-white/8 bg-white/3',
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                        style={{
                          background: `${typeColor[hp.type] ?? '#888'}20`,
                          border: `1px solid ${typeColor[hp.type] ?? '#888'}30`,
                        }}
                      >
                        <Icon className="w-4 h-4" style={{ color: typeColor[hp.type] ?? '#888' }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-white truncate">{hp.name}</span>
                          <span
                            className={cn(
                              'text-[10px] px-1.5 py-0.5 rounded border shrink-0',
                              sc.color,
                            )}
                          >
                            {sc.label}
                          </span>
                        </div>
                        <div className="text-[10px] text-zinc-500 mt-0.5">
                          {hp.ip} · {hp.generated}
                        </div>
                        <div className="flex items-center gap-3 mt-1.5">
                          <span className="text-[10px] text-zinc-400">
                            {hp.interactions} interactions
                          </span>
                          {hp.lastInteraction && (
                            <span className="text-[10px] text-zinc-500">
                              Last: {relTime(hp.lastInteraction)}
                            </span>
                          )}
                          <div className="ml-auto flex items-center gap-1">
                            <div className="w-12 h-1 rounded-full bg-white/5">
                              <div
                                className="h-full rounded-full bg-[#8a8a8a]/60"
                                style={{ width: `${hp.deceptionScore}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-[#8a8a8a]">
                              {hp.deceptionScore}%
                            </span>
                          </div>
                        </div>
                        {hp.attackerProfile && (
                          <div className="mt-1.5 text-[10px] text-[#c9b787] bg-[#c9b787]/10 rounded px-1.5 py-0.5">
                            {hp.attackerProfile}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Deception Telemetry */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Deception Telemetry Feed
          </h2>
          {eventsQuery.isLoading ? (
            <div className="text-xs text-zinc-500 text-center py-8">Loading events…</div>
          ) : (
            <>
              <div className="space-y-2 mb-4">
                {events.map((evt: DeceptionEvent) => (
                  <button
                    key={evt.id}
                    onClick={() => setSelectedEventId(evt.id)}
                    className={cn(
                      'w-full rounded-xl border p-3 text-left transition-all',
                      selectedEvent?.id === evt.id
                        ? 'border-[#8a8a8a]/40 bg-[#8a8a8a]/5'
                        : 'border-white/8 bg-white/3 hover:bg-white/5',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <span className="text-[11px] font-medium text-white leading-snug">
                        {evt.event}
                      </span>
                      <span
                        className={cn(
                          'text-[10px] px-1.5 py-0.5 rounded border shrink-0',
                          evt.severity === 'critical'
                            ? 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10'
                            : 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
                        )}
                      >
                        {evt.severity}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                      <span>{fmtTime(evt.time)}</span>
                      <span>·</span>
                      <span>{evt.honeypot}</span>
                      <span>·</span>
                      <span>{evt.attackerIp}</span>
                      {evt.pushedToFeed && (
                        <span className="text-[#c9b787] ml-1">✓ IOC pushed</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>

              {selectedEvent && (
                <div className="rounded-xl border border-[#8a8a8a]/20 bg-[#8a8a8a]/5 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Network className="w-3.5 h-3.5 text-[#8a8a8a]" />
                    <span className="text-xs font-semibold text-[#8a8a8a]">
                      Threat Intelligence Extracted
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wide mb-0.5">
                        MITRE Technique
                      </div>
                      <div className="text-xs text-white font-mono">{selectedEvent.technique}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wide mb-0.5">
                        Attacker IP
                      </div>
                      <div className="text-xs text-white font-mono">{selectedEvent.attackerIp}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wide mb-0.5">
                        Intel Analysis
                      </div>
                      <div className="text-[11px] text-zinc-300 leading-relaxed">
                        {selectedEvent.intel}
                      </div>
                    </div>
                    {!selectedEvent.pushedToFeed ? (
                      <button
                        onClick={() => pushIocMutation.mutate(selectedEvent.id)}
                        disabled={pushIocMutation.isPending}
                        className="w-full mt-2 py-1.5 rounded-lg bg-[#8a8a8a]/15 border border-[#8a8a8a]/30 text-[#8a8a8a] text-xs font-medium hover:bg-[#8a8a8a]/25 transition-colors disabled:opacity-50"
                      >
                        {pushIocMutation.isPending ? 'Pushing...' : 'Push IOC to Threat Intel'}
                      </button>
                    ) : (
                      <div className="w-full mt-2 py-1.5 rounded-lg bg-[#c9b787]/10 border border-[#c9b787]/20 text-[#c9b787] text-xs font-medium text-center">
                        ✓ IOC pushed to threat intel feeds
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-[#c9b787]" />
            Honeypot Fleet Management
          </h2>
          <div className="space-y-2">
            {[
              { name: 'HoneyDB-Oracle-1', type: 'High Interaction', protocol: 'Oracle TNS', interactions: 847, lastHit: '3m ago', status: 'engaged' },
              { name: 'HoneySSH-DMZ-4', type: 'High Interaction', protocol: 'SSH', interactions: 1234, lastHit: '1m ago', status: 'triggered' },
              { name: 'HoneyHTTP-Prod-2', type: 'Low Interaction', protocol: 'HTTP/S', interactions: 456, lastHit: '8m ago', status: 'active' },
              { name: 'HoneySMB-Internal', type: 'Low Interaction', protocol: 'SMB', interactions: 89, lastHit: '22m ago', status: 'active' },
              { name: 'HoneyRDP-VDI-1', type: 'High Interaction', protocol: 'RDP', interactions: 312, lastHit: '5m ago', status: 'engaged' },
            ].map((hp) => (
              <div key={hp.name} className={cn(
                'rounded-xl border p-3',
                hp.status === 'triggered' ? 'border-[#f5f5f5]/30 bg-[#f5f5f5]/5' :
                hp.status === 'engaged' ? 'border-[#c9b787]/20 bg-white/3' :
                'border-white/8 bg-white/3',
              )}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Server className="w-3.5 h-3.5 text-[#c9b787]" />
                    <span className="text-[11px] font-medium text-white">{hp.name}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#8a8a8a]/10 text-[#8a8a8a] border border-[#8a8a8a]/20">{hp.type}</span>
                  </div>
                  <span className={cn(
                    'text-[9px] px-1.5 py-0.5 rounded border',
                    hp.status === 'triggered' ? 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10' :
                    hp.status === 'engaged' ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10' :
                    'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
                  )}>
                    {hp.status}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                  <span>{hp.protocol}</span>
                  <span>{hp.interactions} interactions</span>
                  <span>Last: {hp.lastHit}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Key className="w-3.5 h-3.5 text-[#c9b787]" />
            Honeytoken Deployment Tracker
          </h2>
          <div className="space-y-2">
            {[
              { token: 'AWS_ACCESS_KEY_AKIAI...', type: 'Fake AWS Key', location: 'S3 bucket config', triggered: true, triggerCount: 3, lastTriggered: '12m ago' },
              { token: 'db_admin:P@ssw0rd_honey', type: 'Fake DB Credential', location: 'Internal wiki page', triggered: true, triggerCount: 1, lastTriggered: '2h ago' },
              { token: 'api_key_7f3d2e...', type: 'Fake API Key', location: 'GitHub private repo', triggered: false, triggerCount: 0, lastTriggered: 'never' },
              { token: 'vpn_cert_honeypot.pem', type: 'Fake VPN Cert', location: 'Shared drive /certs', triggered: false, triggerCount: 0, lastTriggered: 'never' },
              { token: 'admin@corp.com:Tr0ub4d', type: 'Fake Email Cred', location: 'Phishing response DB', triggered: true, triggerCount: 7, lastTriggered: '45m ago' },
            ].map((ht) => (
              <div key={ht.token} className={cn(
                'rounded-xl border p-3',
                ht.triggered ? 'border-[#c9b787]/20 bg-[#c9b787]/3' : 'border-white/8 bg-white/3',
              )}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-white truncate max-w-[180px]">{ht.token}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#c9b787]/10 text-[#c9b787] border border-[#c9b787]/20">{ht.type}</span>
                  </div>
                  {ht.triggered && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded border text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10 animate-pulse">TRIGGERED</span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                  <span>{ht.location}</span>
                  <span>{ht.triggerCount} triggers</span>
                  <span>Last: {ht.lastTriggered}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Timer className="w-3.5 h-3.5 text-[#8a8a8a]" />
            Tarpit Configuration
          </h2>
          <div className="space-y-2">
            {[
              { name: 'SSH Tarpit — Endlessh', protocol: 'SSH (22)', mode: 'Connection hold', avgDrain: '47 min', activeTraps: 12, status: 'active' },
              { name: 'HTTP Tarpit — Slow Loris', protocol: 'HTTP (80)', mode: 'Slow response drip', avgDrain: '23 min', activeTraps: 8, status: 'active' },
              { name: 'SMTP Tarpit', protocol: 'SMTP (25)', mode: 'Greylisting loop', avgDrain: '35 min', activeTraps: 4, status: 'active' },
              { name: 'DNS Tarpit — Sinkhole', protocol: 'DNS (53)', mode: 'Delayed NXDOMAIN', avgDrain: '12 min', activeTraps: 31, status: 'active' },
            ].map((tp) => (
              <div key={tp.name} className="rounded-xl border border-white/8 bg-white/3 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-medium text-white">{tp.name}</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded border text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10">{tp.status}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                  <span>{tp.protocol}</span>
                  <span>{tp.mode}</span>
                  <span className="text-[#c9b787]">Avg drain: {tp.avgDrain}</span>
                  <span>{tp.activeTraps} active</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-[#c9b787]" />
            Deception-as-a-Service Orchestration
          </h2>
          <div className="space-y-2">
            {[
              { service: 'Honeypot Auto-Deploy', description: 'Automatically deploys decoys based on threat landscape changes', status: 'running', lastAction: 'Deployed 2 new SSH decoys in DMZ' },
              { service: 'Honeynet Topology Sync', description: 'Mirrors production network topology for realistic honeynet placement', status: 'running', lastAction: 'Synced 47 network segments' },
              { service: 'Token Rotation Engine', description: 'Rotates honeytokens on a schedule to prevent attacker fingerprinting', status: 'running', lastAction: 'Rotated 12 tokens across 5 locations' },
              { service: 'Deception Analytics', description: 'Analyzes attacker behavior patterns to optimize decoy placement', status: 'running', lastAction: 'Updated placement model with 847 new interactions' },
            ].map((svc) => (
              <div key={svc.service} className="rounded-xl border border-white/8 bg-white/3 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-medium text-white">{svc.service}</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded border text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10">{svc.status}</span>
                </div>
                <p className="text-[10px] text-zinc-400 mb-1">{svc.description}</p>
                <p className="text-[10px] text-[#c9b787]">{svc.lastAction}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 p-4">
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle2 className="w-4 h-4 text-[#c9b787]" />
          <span className="text-xs font-semibold text-[#c9b787]">Zero False-Positive Deception Alert Feed</span>
          <span className="text-[9px] text-zinc-500 font-mono ml-auto">All alerts verified — 0% false positive rate</span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Total Deception Alerts', value: '2,847', color: '#f5f5f5' },
            { label: 'Verified True Positive', value: '2,847', color: '#c9b787' },
            { label: 'False Positive Rate', value: '0.00%', color: '#c9b787' },
            { label: 'Avg Alert-to-Intel', value: '4.2s', color: '#8a8a8a' },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-lg font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
              <div className="text-[9px] text-zinc-500">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
