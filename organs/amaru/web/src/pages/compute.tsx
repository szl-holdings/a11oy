import { AmaruWiringPanel } from '@/components/AmaruLive';

function UnavailablePanel({ title, source, detail }: { title: string; source: string; detail: string }) {
  return (
    <div className="conduit-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-mono font-semibold uppercase tracking-wider">{title}</h2>
        <span className="font-mono text-[10px] text-muted-foreground">{source}</span>
      </div>
      <div className="font-mono text-[11px] text-muted-foreground p-3 border border-border rounded bg-background flex items-start gap-2">
        <span className="text-amber-400 font-bold shrink-0">UNAVAILABLE</span>
        <span>{detail}</span>
      </div>
    </div>
  );
}

export default function ComputePage() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">AMARU · COMPUTE · ORCHESTRATION</p>
        <h1 className="text-2xl font-display font-bold tracking-tight">Compute Orchestration</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Live scheduler wiring is served by the Amaru sidecar. Cluster telemetry
          (orchestrator fleet, node inventory, GPU/CPU utilization) is not connected
          to a metrics source on this surface, so it is reported as unavailable
          rather than simulated.
        </p>
      </div>

      <AmaruWiringPanel />

      <UnavailablePanel
        title="Orchestrator Fleet"
        source="no orchestrator inventory endpoint"
        detail="No orchestrator inventory (Kubernetes / Slurm / dstack / cloud) is wired to this surface yet. Fleet membership and status will appear here once a real source is connected."
      />

      <UnavailablePanel
        title="Cluster Utilization · 24h"
        source="no telemetry endpoint"
        detail="GPU / CPU / memory utilization history requires a live telemetry source, which is not connected on this surface. No simulated series is shown."
      />

      <UnavailablePanel
        title="Node Inventory"
        source="no node inventory endpoint"
        detail="Per-node hardware, status, memory, and job counts require a real cluster inventory source, which is not connected on this surface."
      />
    </div>
  );
}
