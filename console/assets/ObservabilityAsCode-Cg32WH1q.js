import{r as d,k as e}from"./index-BVfpSx5Q.js";const r=[{id:"oac-1",kind:"Monitor",name:"api-latency-p99",namespace:"production",version:12,status:"synced",lastApplied:Date.now()-36e5,source:"terraform",spec:`resource "a11oy_monitor" "api_latency_p99" {
  name      = "API Latency P99"
  query     = "avg:http.request.duration{service:api}.p99"
  threshold = 500
  window    = "5m"
  severity  = "critical"
  notify    = ["#ops-alerts", "pagerduty:api-team"]
}`},{id:"oac-2",kind:"Dashboard",name:"sre-golden-signals",namespace:"production",version:8,status:"synced",lastApplied:Date.now()-72e5,source:"yaml",spec:`apiVersion: a11oy.io/v1
kind: Dashboard
metadata:
  name: sre-golden-signals
  namespace: production
spec:
  panels:
    - title: Latency
      query: "avg:http.request.duration{env:prod}"
    - title: Traffic
      query: "sum:http.request.count{env:prod}"
    - title: Errors
      query: "sum:http.error.count{env:prod}"
    - title: Saturation
      query: "avg:system.cpu.percent{env:prod}"`},{id:"oac-3",kind:"SLO",name:"checkout-availability",namespace:"production",version:5,status:"synced",lastApplied:Date.now()-864e5,source:"terraform",spec:`resource "a11oy_slo" "checkout_avail" {
  name        = "Checkout Availability"
  target      = 99.95
  window      = "30d"
  good_events = "count:http.request{service:checkout,status:2xx}"
  total_events = "count:http.request{service:checkout}"
  burn_alert {
    fast_burn = { threshold = 14.4, window = "1h" }
    slow_burn = { threshold = 6, window = "6h" }
  }
}`},{id:"oac-4",kind:"Workflow",name:"pod-crash-recovery",namespace:"production",version:3,status:"drifted",lastApplied:Date.now()-1728e5,source:"yaml",spec:`apiVersion: a11oy.io/v1
kind: HealingWorkflow
metadata:
  name: pod-crash-recovery
spec:
  trigger:
    metric: container.restart_count
    condition: "> 3 within 5m"
  actions:
    - capture_logs
    - analyze_oom
    - scale_memory
    - restart_deployment
  verification:
    metric: container.restart_count
    condition: "= 0 for 5m"`},{id:"oac-5",kind:"AlertRule",name:"disk-space-critical",namespace:"infrastructure",version:6,status:"synced",lastApplied:Date.now()-144e5,source:"api",spec:`{
  "kind": "AlertRule",
  "name": "disk-space-critical",
  "query": "max:disk.used_percent{*} by {host}",
  "threshold": 90,
  "type": "threshold",
  "severity": "high",
  "escalation": {
    "after": "15m",
    "to": "pagerduty:infra-team"
  }
}`},{id:"oac-6",kind:"SyntheticMetric",name:"business-checkout-conversion",namespace:"analytics",version:2,status:"synced",lastApplied:Date.now()-288e5,source:"terraform",spec:`resource "a11oy_synthetic_metric" "checkout_conv" {
  name       = "checkout_conversion_rate"
  expression = "COUNT(logs WHERE event=checkout.complete) / COUNT(logs WHERE event=checkout.start) * 100"
  source     = "logs"
  mode       = "streaming"
  unit       = "%"
}`}],i=[{id:"ae-1",timestamp:Date.now()-18e5,actor:"ci-pipeline",action:"apply",resource:"Monitor/api-latency-p99",diff:"+threshold = 500 (was 400)"},{id:"ae-2",timestamp:Date.now()-36e5,actor:"sre-team",action:"create",resource:"SLO/checkout-availability",diff:"+target = 99.95%"},{id:"ae-3",timestamp:Date.now()-72e5,actor:"terraform-cloud",action:"apply",resource:"Dashboard/sre-golden-signals",diff:"+panel: Saturation"},{id:"ae-4",timestamp:Date.now()-144e5,actor:"api-user",action:"update",resource:"AlertRule/disk-space-critical",diff:"+escalation.after = 15m (was 30m)"},{id:"ae-5",timestamp:Date.now()-864e5,actor:"ci-pipeline",action:"plan",resource:"Workflow/pod-crash-recovery",diff:"drift detected: manual UI edit overrode spec"}];function n({status:s}){const a={synced:"bg-green-500/10 text-green-400 border-green-500/20",drifted:"bg-orange-500/10 text-orange-400 border-orange-500/20",pending:"bg-yellow-500/10 text-yellow-400 border-yellow-500/20",error:"bg-red-500/10 text-red-400 border-red-500/20"};return e.jsx("span",{className:`inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono rounded border uppercase ${a[s]||""}`,children:s})}function c({kind:s}){const a={Monitor:"text-blue-400",Dashboard:"text-purple-400",SLO:"text-green-400",Workflow:"text-orange-400",AlertRule:"text-red-400",SyntheticMetric:"text-cyan-400"};return e.jsx("span",{className:`text-[10px] font-mono font-bold ${a[s]||"text-white/50"}`,children:s})}function m(){const[s,a]=d.useState(r[0]),l=r.filter(t=>t.status==="synced").length,o=r.filter(t=>t.status==="drifted").length;return e.jsxs("div",{className:"space-y-6 max-w-[1400px] mx-auto",children:[e.jsxs("div",{children:[e.jsx("p",{className:"text-xs font-mono uppercase tracking-[0.2em] text-[#f5f5f5]/40 mb-1",children:"A11OY · PLATFORM · OBSERVABILITY AS CODE"}),e.jsx("h1",{className:"text-2xl font-bold tracking-tight text-[#f5f5f5]",children:"Observability as Code"}),e.jsx("p",{className:"text-sm text-[#f5f5f5]/50 mt-1 max-w-3xl",children:"Define monitors, dashboards, SLOs, healing workflows, and synthetic metrics declaratively via Terraform, YAML, or API. Full version control, drift detection, CI/CD integration, and audit trails. Your entire observability stack as reviewable, testable infrastructure."})]}),e.jsx("div",{className:"grid grid-cols-2 lg:grid-cols-5 gap-3",children:[{label:"Resources",value:r.length,color:"#06b6d4"},{label:"Synced",value:l,color:"#4ade80"},{label:"Drifted",value:o,color:o>0?"#fb923c":"#4ade80"},{label:"Providers",value:"3",color:"#a78bfa"},{label:"Audit Events",value:i.length,color:"#c9b787"}].map(t=>e.jsxs("div",{className:"bg-[#0a0a0f] border border-white/[0.06] rounded-lg p-3 space-y-1",children:[e.jsx("p",{className:"text-[10px] font-mono uppercase tracking-widest text-white/30",children:t.label}),e.jsx("p",{className:"text-xl font-mono font-bold",style:{color:t.color},children:t.value})]},t.label))}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-5 gap-4",children:[e.jsxs("div",{className:"lg:col-span-2 bg-[#0a0a0f] border border-white/[0.06] rounded-lg overflow-hidden",children:[e.jsx("div",{className:"p-4 border-b border-white/[0.06]",children:e.jsx("h2",{className:"text-sm font-mono font-semibold uppercase tracking-wider text-white/70",children:"Resources"})}),e.jsx("div",{className:"divide-y divide-white/[0.03] max-h-[500px] overflow-y-auto",children:r.map(t=>e.jsxs("button",{type:"button",className:`w-full text-left px-4 py-3 cursor-pointer transition-colors ${(s==null?void 0:s.id)===t.id?"bg-white/[0.04]":"hover:bg-white/[0.02]"}`,onClick:()=>a(t),children:[e.jsxs("div",{className:"flex items-center justify-between mb-1",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx(c,{kind:t.kind}),e.jsx("span",{className:"text-xs font-mono font-bold text-white/80",children:t.name})]}),e.jsx(n,{status:t.status})]}),e.jsxs("div",{className:"flex items-center gap-3 text-[10px] font-mono text-white/25",children:[e.jsx("span",{children:t.namespace}),e.jsxs("span",{children:["v",t.version]}),e.jsx("span",{children:t.source})]})]},t.id))})]}),e.jsx("div",{className:"lg:col-span-3 bg-[#0a0a0f] border border-white/[0.06] rounded-lg overflow-hidden",children:s?e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:"p-4 border-b border-white/[0.06] flex items-center justify-between",children:[e.jsxs("div",{className:"flex items-center gap-3",children:[e.jsx(c,{kind:s.kind}),e.jsx("span",{className:"text-sm font-mono font-bold text-white/80",children:s.name}),e.jsx(n,{status:s.status})]}),e.jsxs("div",{className:"flex items-center gap-3 text-[10px] font-mono text-white/30",children:[e.jsxs("span",{children:["v",s.version]}),e.jsxs("span",{children:["via ",s.source]})]})]}),e.jsx("div",{className:"p-4",children:e.jsx("pre",{className:"text-[11px] font-mono text-white/60 leading-relaxed whitespace-pre-wrap bg-white/[0.02] rounded p-4 border border-white/[0.04] overflow-x-auto",children:s.spec})})]}):e.jsx("div",{className:"p-12 text-center text-white/30 text-sm font-mono",children:"Select a resource to view its specification"})})]}),e.jsxs("div",{className:"bg-[#0a0a0f] border border-white/[0.06] rounded-lg overflow-hidden",children:[e.jsxs("div",{className:"p-5 border-b border-white/[0.06]",children:[e.jsx("h2",{className:"text-sm font-mono font-semibold uppercase tracking-wider text-white/70",children:"Audit Trail"}),e.jsx("p",{className:"text-[10px] font-mono text-white/30 mt-0.5",children:"Every change tracked, versioned, and reviewable"})]}),e.jsx("div",{className:"divide-y divide-white/[0.03]",children:i.map(t=>e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors",children:[e.jsxs("div",{className:"flex items-center gap-4",children:[e.jsx("span",{className:"text-[10px] font-mono text-white/30 w-20 flex-shrink-0",children:new Date(t.timestamp).toLocaleDateString("en-US",{month:"short",day:"numeric"})}),e.jsx("span",{className:`text-[10px] font-mono px-1.5 py-0.5 rounded border ${t.action==="apply"?"bg-green-500/10 text-green-400 border-green-500/20":t.action==="create"?"bg-blue-500/10 text-blue-400 border-blue-500/20":t.action==="update"?"bg-yellow-500/10 text-yellow-400 border-yellow-500/20":"bg-orange-500/10 text-orange-400 border-orange-500/20"}`,children:t.action}),e.jsx("span",{className:"text-xs font-mono text-white/60",children:t.resource})]}),e.jsxs("div",{className:"flex items-center gap-3 text-[10px] font-mono text-white/30",children:[e.jsx("span",{children:t.actor}),e.jsx("span",{className:"text-white/20",children:t.diff})]})]},t.id))})]})]})}export{m as ObservabilityAsCode};
