import { Badge } from '@/components/ui';
import { AmaruWiringPanel } from '@/components/AmaruLive';
import {
  Cpu,
  Layers,
  MonitorDot,
  Network,
  Server,
  Workflow,
  Zap,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';

interface ClusterNode {
  id: string;
  name: string;
  type: 'gpu' | 'cpu' | 'tpu';
  hardware: string;
  status: 'active' | 'draining' | 'offline';
  utilization: number;
  memory: string;
  jobs: number;
  uptime: string;
}

const CLUSTER_NODES: ClusterNode[] = [
  { id: 'n1', name: 'lambda-h100-0', type: 'gpu', hardware: 'NVIDIA H100 SXM', status: 'active', utilization: 87, memory: '72/80 GB', jobs: 4, uptime: '14d 6h' },
  { id: 'n2', name: 'lambda-h100-1', type: 'gpu', hardware: 'NVIDIA H100 SXM', status: 'active', utilization: 93, memory: '76/80 GB', jobs: 5, uptime: '14d 6h' },
  { id: 'n3', name: 'lambda-a100-0', type: 'gpu', hardware: 'NVIDIA A100 80G', status: 'active', utilization: 62, memory: '48/80 GB', jobs: 3, uptime: '31d 2h' },
  { id: 'n4', name: 'lambda-a100-1', type: 'gpu', hardware: 'NVIDIA A100 80G', status: 'draining', utilization: 34, memory: '22/80 GB', jobs: 1, uptime: '31d 2h' },
  { id: 'n5', name: 'k8s-worker-0', type: 'cpu', hardware: 'AMD EPYC 9654', status: 'active', utilization: 41, memory: '128/256 GB', jobs: 12, uptime: '62d 18h' },
  { id: 'n6', name: 'k8s-worker-1', type: 'cpu', hardware: 'AMD EPYC 9654', status: 'active', utilization: 58, memory: '164/256 GB', jobs: 9, uptime: '62d 18h' },
  { id: 'n7', name: 'slurm-batch-0', type: 'cpu', hardware: 'Intel Xeon w9-3595X', status: 'active', utilization: 78, memory: '384/512 GB', jobs: 24, uptime: '7d 4h' },
  { id: 'n8', name: 'dstack-spot-0', type: 'gpu', hardware: 'NVIDIA H200 141G', status: 'active', utilization: 96, memory: '134/141 GB', jobs: 2, uptime: '0d 8h' },
];

const ORCHESTRATORS = [
  { name: 'Kubernetes', status: 'active', nodes: 4, icon: <Layers className="w-5 h-5" />, desc: 'Managed cluster with GPU scheduling' },
  { name: 'Slurm', status: 'active', nodes: 2, icon: <Server className="w-5 h-5" />, desc: 'HPC batch workloads' },
  { name: 'dstack', status: 'active', nodes: 1, icon: <Workflow className="w-5 h-5" />, desc: 'Open-source AI dev, spot instances' },
  { name: 'Lambda Cloud', status: 'active', nodes: 1, icon: <Zap className="w-5 h-5" />, desc: 'On-demand H200 inference' },
];

const UTILIZATION_HISTORY = Array.from({ length: 48 }, (_, i) => ({
  t: `${Math.floor(i / 2)}:${i % 2 === 0 ? '00' : '30'}`,
  gpu: Math.floor(60 + Math.sin(i / 6) * 25 + Math.random() * 10),
  cpu: Math.floor(40 + Math.cos(i / 8) * 20 + Math.random() * 8),
  mem: Math.floor(55 + Math.sin(i / 4) * 15 + Math.random() * 5),
}));

function StatusDot({ status }: { status: string }) {
  const color = status === 'active' ? 'bg-green-500' : status === 'draining' ? 'bg-yellow-500' : 'bg-red-500';
  return <div className={`w-2 h-2 rounded-full ${color} ${status === 'active' ? 'animate-pulse' : ''}`} />;
}

export default function ComputePage() {
  const totalGpu = CLUSTER_NODES.filter(n => n.type === 'gpu').length;
  const totalCpu = CLUSTER_NODES.filter(n => n.type === 'cpu').length;
  const avgUtil = Math.round(CLUSTER_NODES.reduce((s, n) => s + n.utilization, 0) / CLUSTER_NODES.length);
  const totalJobs = CLUSTER_NODES.reduce((s, n) => s + n.jobs, 0);

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">AMARU · COMPUTE · ORCHESTRATION</p>
        <h1 className="text-2xl font-display font-bold tracking-tight">Compute Orchestration</h1>
        <p className="text-sm text-muted-foreground mt-1">
          GPU/CPU cluster management across Kubernetes, Slurm, dstack, and Lambda Cloud.
          Inspired by Lambda AI's flexible orchestration architecture.
        </p>
      </div>

      <AmaruWiringPanel />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {ORCHESTRATORS.map(o => (
          <div key={o.name} className="conduit-card p-4 flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary flex-shrink-0">
              {o.icon}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-mono font-bold">{o.name}</p>
                <StatusDot status={o.status} />
              </div>
              <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{o.desc}</p>
              <p className="text-[10px] text-muted-foreground font-mono">{o.nodes} node{o.nodes > 1 ? 's' : ''}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="conduit-stat p-4 text-center">
          <Cpu className="w-5 h-5 text-primary mx-auto mb-2 opacity-60" />
          <p className="text-2xl font-mono font-bold">{totalGpu}</p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">GPU Nodes</p>
        </div>
        <div className="conduit-stat p-4 text-center">
          <Server className="w-5 h-5 text-primary mx-auto mb-2 opacity-60" />
          <p className="text-2xl font-mono font-bold">{totalCpu}</p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">CPU Nodes</p>
        </div>
        <div className="conduit-stat p-4 text-center">
          <MonitorDot className="w-5 h-5 text-primary mx-auto mb-2 opacity-60" />
          <p className="text-2xl font-mono font-bold">{avgUtil}%</p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Avg Util</p>
        </div>
        <div className="conduit-stat p-4 text-center">
          <Network className="w-5 h-5 text-primary mx-auto mb-2 opacity-60" />
          <p className="text-2xl font-mono font-bold">{totalJobs}</p>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Active Jobs</p>
        </div>
      </div>

      <div className="conduit-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-mono font-semibold uppercase tracking-wider">Cluster Utilization · 24h</h2>
          <div className="flex items-center gap-4 text-[10px] font-mono text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#06b6d4]" /> GPU</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#a78bfa]" /> CPU</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#4ade80]" /> MEM</span>
          </div>
        </div>
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={UTILIZATION_HISTORY} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gGpu" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gCpu" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gMem" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4ade80" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#4ade80" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} axisLine={false} fontFamily="JetBrains Mono" interval={5} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={9} tickLine={false} axisLine={false} fontFamily="JetBrains Mono" domain={[0, 100]} tickFormatter={v => `${v}%`} />
              <Tooltip content={({ active, payload, label }) => {
                if (active && payload?.length) {
                  return (
                    <div className="bg-card border border-border rounded p-2 text-[10px] font-mono shadow-xl space-y-0.5">
                      <p className="text-muted-foreground">{label}</p>
                      <p style={{ color: '#06b6d4' }}>GPU: {payload[0]?.value}%</p>
                      <p style={{ color: '#a78bfa' }}>CPU: {payload[1]?.value}%</p>
                      <p style={{ color: '#4ade80' }}>MEM: {payload[2]?.value}%</p>
                    </div>
                  );
                }
                return null;
              }} />
              <Area type="monotone" dataKey="gpu" stroke="#06b6d4" strokeWidth={1.5} fillOpacity={1} fill="url(#gGpu)" />
              <Area type="monotone" dataKey="cpu" stroke="#a78bfa" strokeWidth={1.5} fillOpacity={1} fill="url(#gCpu)" />
              <Area type="monotone" dataKey="mem" stroke="#4ade80" strokeWidth={1.5} fillOpacity={1} fill="url(#gMem)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="conduit-card overflow-hidden">
        <div className="p-5 border-b border-border">
          <h2 className="text-sm font-mono font-semibold uppercase tracking-wider">Node Inventory</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left px-5 py-3 font-medium uppercase tracking-wider">Node</th>
                <th className="text-left px-3 py-3 font-medium uppercase tracking-wider">Hardware</th>
                <th className="text-left px-3 py-3 font-medium uppercase tracking-wider">Status</th>
                <th className="text-right px-3 py-3 font-medium uppercase tracking-wider">Util</th>
                <th className="text-right px-3 py-3 font-medium uppercase tracking-wider">Memory</th>
                <th className="text-right px-3 py-3 font-medium uppercase tracking-wider">Jobs</th>
                <th className="text-right px-5 py-3 font-medium uppercase tracking-wider">Uptime</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {CLUSTER_NODES.map(n => (
                <tr key={n.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-5 py-3 flex items-center gap-2">
                    <StatusDot status={n.status} />
                    <span className="font-bold">{n.name}</span>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{n.hardware}</td>
                  <td className="px-3 py-3">
                    <Badge variant={n.status === 'active' ? 'success' : n.status === 'draining' ? 'running' : 'failed'} className="text-[10px] capitalize">
                      {n.status}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span style={{ color: n.utilization > 80 ? '#fb923c' : n.utilization > 60 ? '#facc15' : '#4ade80' }}>
                      {n.utilization}%
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right text-muted-foreground">{n.memory}</td>
                  <td className="px-3 py-3 text-right">{n.jobs}</td>
                  <td className="px-5 py-3 text-right text-muted-foreground">{n.uptime}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
