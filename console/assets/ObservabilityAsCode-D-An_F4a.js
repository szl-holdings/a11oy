import{o as e}from"./chunk-CMxvf4Kt.js";import{t}from"./react-DrNXigiH.js";import{C as n}from"./index-BQgFo2NB.js";var r=e(t(),1),i=n(),a=[{id:`oac-1`,kind:`Monitor`,name:`api-latency-p99`,namespace:`production`,version:12,status:`synced`,lastApplied:Date.now()-36e5,source:`terraform`,spec:`resource "a11oy_monitor" "api_latency_p99" {
  name      = "API Latency P99"
  query     = "avg:http.request.duration{service:api}.p99"
  threshold = 500
  window    = "5m"
  severity  = "critical"
  notify    = ["#ops-alerts", "pagerduty:api-team"]
}`},{id:`oac-2`,kind:`Dashboard`,name:`sre-golden-signals`,namespace:`production`,version:8,status:`synced`,lastApplied:Date.now()-72e5,source:`yaml`,spec:`apiVersion: a11oy.io/v1
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
      query: "avg:system.cpu.percent{env:prod}"`},{id:`oac-3`,kind:`SLO`,name:`checkout-availability`,namespace:`production`,version:5,status:`synced`,lastApplied:Date.now()-864e5,source:`terraform`,spec:`resource "a11oy_slo" "checkout_avail" {
  name        = "Checkout Availability"
  target      = 99.95
  window      = "30d"
  good_events = "count:http.request{service:checkout,status:2xx}"
  total_events = "count:http.request{service:checkout}"
  burn_alert {
    fast_burn = { threshold = 14.4, window = "1h" }
    slow_burn = { threshold = 6, window = "6h" }
  }
}`},{id:`oac-4`,kind:`Workflow`,name:`pod-crash-recovery`,namespace:`production`,version:3,status:`drifted`,lastApplied:Date.now()-1728e5,source:`yaml`,spec:`apiVersion: a11oy.io/v1
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
    condition: "= 0 for 5m"`},{id:`oac-5`,kind:`AlertRule`,name:`disk-space-critical`,namespace:`infrastructure`,version:6,status:`synced`,lastApplied:Date.now()-144e5,source:`api`,spec:`{
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
}`},{id:`oac-6`,kind:`SyntheticMetric`,name:`business-checkout-conversion`,namespace:`analytics`,version:2,status:`synced`,lastApplied:Date.now()-288e5,source:`terraform`,spec:`resource "a11oy_synthetic_metric" "checkout_conv" {
  name       = "checkout_conversion_rate"
  expression = "COUNT(logs WHERE event=checkout.complete) / COUNT(logs WHERE event=checkout.start) * 100"
  source     = "logs"
  mode       = "streaming"
  unit       = "%"
}`}],o=[{id:`ae-1`,timestamp:Date.now()-18e5,actor:`ci-pipeline`,action:`apply`,resource:`Monitor/api-latency-p99`,diff:`+threshold = 500 (was 400)`},{id:`ae-2`,timestamp:Date.now()-36e5,actor:`sre-team`,action:`create`,resource:`SLO/checkout-availability`,diff:`+target = 99.95%`},{id:`ae-3`,timestamp:Date.now()-72e5,actor:`terraform-cloud`,action:`apply`,resource:`Dashboard/sre-golden-signals`,diff:`+panel: Saturation`},{id:`ae-4`,timestamp:Date.now()-144e5,actor:`api-user`,action:`update`,resource:`AlertRule/disk-space-critical`,diff:`+escalation.after = 15m (was 30m)`},{id:`ae-5`,timestamp:Date.now()-864e5,actor:`ci-pipeline`,action:`plan`,resource:`Workflow/pod-crash-recovery`,diff:`drift detected: manual UI edit overrode spec`}];function s({status:e}){return(0,i.jsx)(`span`,{className:`inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono rounded border uppercase ${{synced:`bg-green-500/10 text-green-400 border-green-500/20`,drifted:`bg-orange-500/10 text-orange-400 border-orange-500/20`,pending:`bg-yellow-500/10 text-yellow-400 border-yellow-500/20`,error:`bg-red-500/10 text-red-400 border-red-500/20`}[e]||``}`,children:e})}function c({kind:e}){return(0,i.jsx)(`span`,{className:`text-[10px] font-mono font-bold ${{Monitor:`text-blue-400`,Dashboard:`text-purple-400`,SLO:`text-green-400`,Workflow:`text-orange-400`,AlertRule:`text-red-400`,SyntheticMetric:`text-cyan-400`}[e]||`text-white/50`}`,children:e})}function l(){let[e,t]=(0,r.useState)(a[0]),n=a.filter(e=>e.status===`synced`).length,l=a.filter(e=>e.status===`drifted`).length;return(0,i.jsxs)(`div`,{className:`space-y-6 max-w-[1400px] mx-auto`,children:[(0,i.jsxs)(`div`,{children:[(0,i.jsx)(`p`,{className:`text-xs font-mono uppercase tracking-[0.2em] text-[#f5f5f5]/40 mb-1`,children:`A11OY · PLATFORM · OBSERVABILITY AS CODE`}),(0,i.jsx)(`h1`,{className:`text-2xl font-bold tracking-tight text-[#f5f5f5]`,children:`Observability as Code`}),(0,i.jsx)(`p`,{className:`text-sm text-[#f5f5f5]/50 mt-1 max-w-3xl`,children:`Define monitors, dashboards, SLOs, healing workflows, and synthetic metrics declaratively via Terraform, YAML, or API. Full version control, drift detection, CI/CD integration, and audit trails. Your entire observability stack as reviewable, testable infrastructure.`})]}),(0,i.jsx)(`div`,{className:`grid grid-cols-2 lg:grid-cols-5 gap-3`,children:[{label:`Resources`,value:a.length,color:`#06b6d4`},{label:`Synced`,value:n,color:`#4ade80`},{label:`Drifted`,value:l,color:l>0?`#fb923c`:`#4ade80`},{label:`Providers`,value:`3`,color:`#a78bfa`},{label:`Audit Events`,value:o.length,color:`#c9b787`}].map(e=>(0,i.jsxs)(`div`,{className:`bg-[#0a0a0f] border border-white/[0.06] rounded-lg p-3 space-y-1`,children:[(0,i.jsx)(`p`,{className:`text-[10px] font-mono uppercase tracking-widest text-white/30`,children:e.label}),(0,i.jsx)(`p`,{className:`text-xl font-mono font-bold`,style:{color:e.color},children:e.value})]},e.label))}),(0,i.jsxs)(`div`,{className:`grid grid-cols-1 lg:grid-cols-5 gap-4`,children:[(0,i.jsxs)(`div`,{className:`lg:col-span-2 bg-[#0a0a0f] border border-white/[0.06] rounded-lg overflow-hidden`,children:[(0,i.jsx)(`div`,{className:`p-4 border-b border-white/[0.06]`,children:(0,i.jsx)(`h2`,{className:`text-sm font-mono font-semibold uppercase tracking-wider text-white/70`,children:`Resources`})}),(0,i.jsx)(`div`,{className:`divide-y divide-white/[0.03] max-h-[500px] overflow-y-auto`,children:a.map(n=>(0,i.jsxs)(`button`,{type:`button`,className:`w-full text-left px-4 py-3 cursor-pointer transition-colors ${e?.id===n.id?`bg-white/[0.04]`:`hover:bg-white/[0.02]`}`,onClick:()=>t(n),children:[(0,i.jsxs)(`div`,{className:`flex items-center justify-between mb-1`,children:[(0,i.jsxs)(`div`,{className:`flex items-center gap-2`,children:[(0,i.jsx)(c,{kind:n.kind}),(0,i.jsx)(`span`,{className:`text-xs font-mono font-bold text-white/80`,children:n.name})]}),(0,i.jsx)(s,{status:n.status})]}),(0,i.jsxs)(`div`,{className:`flex items-center gap-3 text-[10px] font-mono text-white/25`,children:[(0,i.jsx)(`span`,{children:n.namespace}),(0,i.jsxs)(`span`,{children:[`v`,n.version]}),(0,i.jsx)(`span`,{children:n.source})]})]},n.id))})]}),(0,i.jsx)(`div`,{className:`lg:col-span-3 bg-[#0a0a0f] border border-white/[0.06] rounded-lg overflow-hidden`,children:e?(0,i.jsxs)(i.Fragment,{children:[(0,i.jsxs)(`div`,{className:`p-4 border-b border-white/[0.06] flex items-center justify-between`,children:[(0,i.jsxs)(`div`,{className:`flex items-center gap-3`,children:[(0,i.jsx)(c,{kind:e.kind}),(0,i.jsx)(`span`,{className:`text-sm font-mono font-bold text-white/80`,children:e.name}),(0,i.jsx)(s,{status:e.status})]}),(0,i.jsxs)(`div`,{className:`flex items-center gap-3 text-[10px] font-mono text-white/30`,children:[(0,i.jsxs)(`span`,{children:[`v`,e.version]}),(0,i.jsxs)(`span`,{children:[`via `,e.source]})]})]}),(0,i.jsx)(`div`,{className:`p-4`,children:(0,i.jsx)(`pre`,{className:`text-[11px] font-mono text-white/60 leading-relaxed whitespace-pre-wrap bg-white/[0.02] rounded p-4 border border-white/[0.04] overflow-x-auto`,children:e.spec})})]}):(0,i.jsx)(`div`,{className:`p-12 text-center text-white/30 text-sm font-mono`,children:`Select a resource to view its specification`})})]}),(0,i.jsxs)(`div`,{className:`bg-[#0a0a0f] border border-white/[0.06] rounded-lg overflow-hidden`,children:[(0,i.jsxs)(`div`,{className:`p-5 border-b border-white/[0.06]`,children:[(0,i.jsx)(`h2`,{className:`text-sm font-mono font-semibold uppercase tracking-wider text-white/70`,children:`Audit Trail`}),(0,i.jsx)(`p`,{className:`text-[10px] font-mono text-white/30 mt-0.5`,children:`Every change tracked, versioned, and reviewable`})]}),(0,i.jsx)(`div`,{className:`divide-y divide-white/[0.03]`,children:o.map(e=>(0,i.jsxs)(`div`,{className:`px-5 py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors`,children:[(0,i.jsxs)(`div`,{className:`flex items-center gap-4`,children:[(0,i.jsx)(`span`,{className:`text-[10px] font-mono text-white/30 w-20 flex-shrink-0`,children:new Date(e.timestamp).toLocaleDateString(`en-US`,{month:`short`,day:`numeric`})}),(0,i.jsx)(`span`,{className:`text-[10px] font-mono px-1.5 py-0.5 rounded border ${e.action===`apply`?`bg-green-500/10 text-green-400 border-green-500/20`:e.action===`create`?`bg-blue-500/10 text-blue-400 border-blue-500/20`:e.action===`update`?`bg-yellow-500/10 text-yellow-400 border-yellow-500/20`:`bg-orange-500/10 text-orange-400 border-orange-500/20`}`,children:e.action}),(0,i.jsx)(`span`,{className:`text-xs font-mono text-white/60`,children:e.resource})]}),(0,i.jsxs)(`div`,{className:`flex items-center gap-3 text-[10px] font-mono text-white/30`,children:[(0,i.jsx)(`span`,{children:e.actor}),(0,i.jsx)(`span`,{className:`text-white/20`,children:e.diff})]})]},e.id))})]})]})}export{l as ObservabilityAsCode};