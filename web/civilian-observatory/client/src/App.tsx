import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link, Route, Router, Switch, useLocation } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowRight, ArrowUpRight, Check, ChevronRight, CircleHelp, CloudSun, FileCheck2, FlaskConical, FolderGit2, GitBranch, Globe2, LayoutDashboard, Loader2, LockKeyhole, Moon, Network, RefreshCw, Search, ShieldCheck, Sun } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { sha256 as digestBytes } from "@noble/hashes/sha2.js";
import { bytesToHex } from "@noble/hashes/utils.js";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Toaster } from "@/components/ui/toaster";
import { useToast } from "@/hooks/use-toast";
import type { Advisory, Analysis, ClaimType, DryRunPlan, Estate, HeaderScan, Overview, RepoAudit, ReviewBundle, SourceRecord, WeatherSnapshot } from "@shared/schema";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";

const nav = [
  { href: "/", title: "Overview", icon: LayoutDashboard },
  { href: "/review", title: "Vulnerability review", icon: ShieldCheck },
  { href: "/observe", title: "Civilian observations", icon: Globe2 },
  { href: "/estate", title: "Repository evidence", icon: FolderGit2 },
  { href: "/evidence", title: "Evidence map", icon: Network },
  { href: "/research", title: "Research frontier", icon: FlaskConical },
];
const sources = {
  kev: "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
  epss: "https://www.first.org/epss/faq",
  github: "https://github.com/szl-holdings",
  nws: "https://www.weather.gov/documentation/services-web-alerts",
};
const fmt = (n: number | string | undefined) => typeof n === "number" ? n.toLocaleString("en-US") : n ?? "Unknown";
const date = (s: string | null | undefined) => s && !Number.isNaN(Date.parse(s)) ? new Date(s).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC" : "Not available";
const percent = (n: number | null | undefined) => {
  if (n === null || n === undefined) return "Not available";
  if (n > 0 && n < 0.0001) return "<0.01%";
  if (n < 1 && n > 0.9999) return ">99.99%";
  return (n * 100).toFixed(2) + "%";
};

function Logo() {
  return <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M4 25 14 6h5L9 25H4Z" fill="currentColor"/><path d="m16 25 7-14 5 14h-5l-2-5-2.5 5H16Z" fill="currentColor"/><path d="M12 26h16" stroke="currentColor" strokeWidth="1.5"/></svg>;
}
function Tag({ children, kind = "FACT" }: { children?: ReactNode; kind?: ClaimType | "SIMULATED" | "OBSERVED" | "STALE" | "UNAVAILABLE" }) {
  return <span className={`tag tag-${kind.toLowerCase()}`} data-testid={`status-tag-${kind.toLowerCase()}`}>{children ?? kind}</span>;
}
function External({ href, children, id }: { href: string; children: ReactNode; id?: string }) {
  return <a className="source-link" href={href} target="_blank" rel="noreferrer noopener" data-testid={id ?? `link-${href.split("/").filter(Boolean).pop()}`} >{children}<ArrowUpRight size={13}/></a>;
}
function ErrorBox({ message }: { message: string }) {
  return <div className="error-box" role="alert" data-testid="status-error">{message}</div>;
}
function Panel({ title, eyebrow, action, children, className = "" }: { title: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><div className="panel-head"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2>{title}</h2></div>{action}</div>{children}</section>;
}
function Heading({ title, eyebrow, children, action }: { title: string; eyebrow: string; children: ReactNode; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1 data-testid="text-page-title">{title}</h1><p>{children}</p></div>{action}</div>;
}
function SourceLine({ source }: { source: SourceRecord }) {
  return <div className="source-line" data-testid={`source-${source.name}`}><div className="source-name"><span className={`dot ${source.status === "OBSERVED" ? "" : "muted-dot"}`}/><External href={source.source_url}>{source.name}</External><Tag kind={source.status}/></div><div className="small muted">Fetched {date(source.fetched_at)}{source.source_date ? ` · Source date ${source.source_date.slice(0, 10)}` : ""}</div>{source.error && <div className="small status-note">{source.error}</div>}</div>;
}
function AppNav() {
  const [location] = useLocation();
  const { setOpenMobile } = useSidebar();
  return <Sidebar><SidebarHeader className="brand-header"><Link href="/" className="brand" onClick={() => setOpenMobile(false)} data-testid="link-brand"><Logo/><span>a11oy<span className="brand-sub">CIVILIAN OBSERVATORY</span></span></Link></SidebarHeader>
    <SidebarContent><SidebarGroup><SidebarGroupLabel>WORKSPACE / 01</SidebarGroupLabel><SidebarGroupContent><SidebarMenu>{nav.map(item => <SidebarMenuItem key={item.href}><SidebarMenuButton asChild isActive={location === item.href}><Link href={item.href} onClick={() => setOpenMobile(false)} data-testid={`nav-${item.title.toLowerCase().replaceAll(" ", "-")}`}><item.icon size={17}/><span>{item.title}</span></Link></SidebarMenuButton></SidebarMenuItem>)}</SidebarMenu></SidebarGroupContent></SidebarGroup>
      <div className="sidebar-notice"><div className="eyebrow">BUILT TO INFORM</div><p>Observe. Explain.<br/>Keep people in control.</p><span>Public data and bounded checks.<br/>No autonomous response.</span></div>
    </SidebarContent><SidebarFooter className="sidebar-footer"><div className="flex items-center gap-2"><span className="dot"/><span>Experimental software</span></div><div className="small muted">SZL Holdings · Original prototype</div></SidebarFooter>
  </Sidebar>;
}
function Shell() {
  const [location, navigate] = useLocation();
  const [dark, setDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  const { toast } = useToast();
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); }, [dark]);
  useEffect(() => { document.querySelector(".main-scroll")?.scrollTo({ top: 0 }); }, [location]);
  const overview = useQuery<Overview>({ queryKey: ["/api/overview"], staleTime: 60_000, refetchInterval: 60_000 });
  const refresh = useMutation({
    mutationFn: async () => (await apiRequest("GET", "/api/refresh")).json(),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/overview"] }); toast({ title: "Source refresh completed", description: "Check each source status. Missing data stays unavailable." }); },
    onError: () => toast({ title: "Could not refresh sources", description: "The last snapshot is retained with its original timestamps." }),
  });
  return <SidebarProvider style={{ "--sidebar-width": "238px" } as CSSProperties}><div className="flex h-svh w-full"><AppNav/><div className="main-shell">
    <header className="topbar"><div className="flex items-center gap-3"><SidebarTrigger data-testid="button-sidebar-toggle"/><span className="top-crumb">Civilian workspace</span><ChevronRight size={13} className="muted"/><span className="top-section">{nav.find(n => n.href === location)?.title ?? "Workspace"}</span></div><div className="flex items-center gap-2"><span className="top-status">READ-ONLY + DRY-RUN</span><Button variant="ghost" size="icon" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setDark(!dark)} data-testid="button-theme">{dark ? <Sun size={17}/> : <Moon size={17}/>}</Button><Button variant="outline" onClick={() => refresh.mutate()} disabled={refresh.isPending} data-testid="button-refresh">{refresh.isPending ? <Loader2 size={14} className="animate-spin"/> : <RefreshCw size={14}/>}<span className="refresh-label">Refresh feeds</span></Button></div></header>
    <main className="main-scroll" data-testid="main-content"><div className="content-wrap">
      {overview.isLoading ? <div className="loading-panel" data-testid="status-loading"><Loader2 className="animate-spin" size={20}/><h1>Reading the evidence</h1><p>Loading timestamped source snapshots. No model inference is running.</p></div> : overview.isError ? <ErrorBox message="The evidence service is unavailable. Nothing is being reported as healthy; refresh to retry."/> : overview.data && <Switch>
        <Route path="/"><OverviewPage data={overview.data} onReview={() => navigate("/review")}/></Route>
        <Route path="/review"><ReviewPage initial={overview.data.analysis}/></Route>
        <Route path="/observe"><ObservePage/></Route>
        <Route path="/estate"><EstatePage estate={overview.data.estate}/></Route>
        <Route path="/evidence"><EvidencePage data={overview.data}/></Route>
        <Route path="/research"><ResearchPage/></Route>
        <Route><Heading title="This view does not exist." eyebrow="NOT FOUND">Return to the overview to inspect the evidence. No action was taken.</Heading><Button onClick={() => navigate("/")} data-testid="button-home">Back to overview</Button></Route>
      </Switch>}
      <footer className="page-footer"><span>Evidence before action.</span><span>Public sources · Model-free runtime · Human review</span></footer>
    </div></main></div></div><Toaster/></SidebarProvider>;
}

function OverviewPage({ data, onReview }: { data: Overview; onReview: () => void }) {
  const summary = data.estate.summary;
  const metrics = [
    ["Public repositories", fmt(summary.repo_count), `${fmt(summary.archived)} archived · not a health score`, "01"],
    ["Files indexed", fmt(summary.files_indexed), "File paths, not a line-by-line code audit", "02"],
    ["Known-exploited catalogue", data.feeds.kev.source.status === "UNAVAILABLE" ? "Unavailable" : fmt(data.feeds.kev.catalog_count ?? data.feeds.kev.entries.length), "CISA records · not your asset exposure", "03"],
    ["EPSS estimates in view", fmt(data.analysis.rows.filter(r => r.epss !== null).length), `of ${data.analysis.rows.length} public CVE examples`, "04"],
  ];
  return <>
    <Heading title="Clarity before action." eyebrow="A11OY / CIVILIAN DEFENSE" action={<Button onClick={onReview} data-testid="button-open-review">Open review queue<ArrowRight size={16}/></Button>}>A working observatory for software risk and civilian resilience. <br/>Inspect the source, understand the uncertainty, and decide what comes next.</Heading>
    <div className="snapshot-strip"><div><Tag/> <span>Public GitHub snapshot · {date(String(summary.observed_at))}</span></div><External href={sources.github}>szl-holdings</External></div>
    <div className="metrics-grid">{metrics.map(([label, value, note, idx]) => <div className="metric" key={label}><div className="metric-label">{label}<span className="mono muted">{idx}</span></div><div className="metric-value" data-testid={`metric-${idx}`}>{value}</div><div className="small muted">{note}</div></div>)}</div>
    <div className="overview-grid"><Panel title="An evidence path, not a black box" eyebrow="OBSERVE → EXPLAIN → REVIEW" action={<Link href="/evidence" data-testid="link-map" className="text-action">Inspect map<ArrowUpRight size={14}/></Link>}><EvidenceGraphic data={data} compact/><div className="graph-caption"><span className="dot"/><span>Lines show this prototype's data flow, not deployed integrations.</span></div></Panel>
      <Panel title="What the system knows" eyebrow="CLAIM BOUNDARIES"><div className="truth-list"><div><Tag/><p>Source records and repository paths were observed at the stated timestamps.</p></div><div><Tag kind="INFERENCE"/><p>The queue orders known exploitation first, then the available EPSS estimate.</p></div><div><Tag kind="BLOCKED">UNKNOWN</Tag><p>Your asset exposure is not connected. A public CVE is not an incident in your estate.</p></div></div><div className="quiet-note"><LockKeyhole size={16}/><span>Analysts decide. This software does not remediate, scan ports, or control devices.</span></div></Panel></div>
    <div className="overview-grid"><Panel title="Public vulnerability watch" eyebrow="REAL SOURCE DATA / NOT ASSET MATCHES" action={<Button variant="ghost" onClick={onReview} data-testid="button-view-all-cves">Review all<ArrowRight size={14}/></Button>}><AdvisoryTable rows={data.analysis.rows.slice(0, 5)} compact/><div className="panel-bottom"><External href={sources.kev}>CISA KEV</External><External href={sources.epss}>FIRST EPSS methodology</External></div></Panel>
      <Panel title="Source ledger" eyebrow="TIME AND PROVENANCE"><div className="source-stack"><SourceLine source={data.feeds.kev.source}/><SourceLine source={data.feeds.epss.source}/><div className="source-line"><div className="source-name"><span className="dot"/><External href={sources.github}>GitHub public metadata</External></div><div className="small muted">Snapshot {date(String(summary.observed_at))}. Manual audit refresh only.</div></div></div><div className="quiet-note"><CircleHelp size={16}/><span>Refresh updates public feeds, not the frozen GitHub audit. A recent fetch can still contain older source data.</span></div></Panel></div>
    <div className="next-lane"><div><div className="eyebrow">CIVILIAN OBSERVATIONS</div><h2>Look outward. Stay within scope.</h2><p>Check your public web headers or read official weather alerts. Rehearse a response without sending commands.</p></div><Link href="/observe" className="text-action" data-testid="link-observations">Open observations<ArrowRight size={18}/></Link></div>
  </>;
}

function AdvisoryTable({ rows, reviewed = new Set(), onSelect, compact = false }: { rows: Advisory[]; reviewed?: Set<string>; onSelect?: (row: Advisory) => void; compact?: boolean }) {
  return <div className="table-scroll"><table className="data-table" data-testid="table-advisories"><thead><tr><th>Vulnerability</th><th>Evidence</th><th>EPSS / 30 days</th>{!compact && <th>Review</th>}</tr></thead><tbody>{rows.map(row => <tr key={row.cve} data-testid={`row-${row.cve}`}><td>{onSelect ? <button onClick={() => onSelect(row)} className="table-button" data-testid={`button-detail-${row.cve}`}>{row.cve}<ArrowUpRight size={13}/></button> : <span className="mono">{row.cve}</span>}<div className="small muted truncate-name">{row.kev ? `${row.kev.vendorProject} · ${row.kev.product}` : "Product not provided by these sources"}</div></td><td><span className={`evidence-pill ${row.kev_status === "LISTED" ? "is-listed" : ""}`}>{row.kev_status === "LISTED" ? "KEV listed" : row.kev_status === "NOT_LISTED" ? "Not in KEV snapshot" : "KEV unavailable"}</span></td><td><span className="mono">{percent(row.epss?.epss)}</span>{row.epss && <div className="probability-bar" title="EPSS is a source probability estimate, not an environment-specific risk score"><span style={{ width: `${row.epss.epss * 100}%` }}/></div>}</td>{!compact && <td><button className={`review-chip ${reviewed.has(row.cve) ? "is-reviewed" : ""}`} onClick={() => onSelect?.(row)} data-testid={`button-review-${row.cve}`}>{reviewed.has(row.cve) ? <><Check size={13}/>Reviewed</> : <>Inspect<ChevronRight size={13}/></>}</button></td>}</tr>)}</tbody></table>{rows.length === 0 && <div className="empty-state">No records to display. Source availability is shown separately.</div>}</div>;
}
const reviewForm = z.object({ text: z.string().min(1, "Enter at least one CVE identifier.").max(1800, "Keep this review to 50 CVE identifiers.").refine(v => {
  const ids = v.toUpperCase().split(/[\s,;]+/).filter(Boolean);
  return ids.length <= 50 && ids.every(id => /^CVE-\d{4}-\d{4,19}$/.test(id));
}, "Use up to 50 CVE identifiers only, separated by spaces or commas. URLs and targets are not accepted here.") });
async function makeBundle(payload: unknown): Promise<ReviewBundle> {
  const payload_json = JSON.stringify(payload);
  // Portable hashing also works in opaque/insecure preview frames without Web Crypto.
  const sha256 = bytesToHex(digestBytes(new TextEncoder().encode(payload_json)));
  return { schema: "szl-observatory.bundle.v1", payload_json, sha256, signature: null, trust: "UNSIGNED_SELF_ASSERTED" };
}
function download(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function ReviewPage({ initial }: { initial: Analysis }) {
  const [analysis, setAnalysis] = useState(initial);
  const [selected, setSelected] = useState<Advisory | null>(null);
  const [reviewed, setReviewed] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [feedback, setFeedback] = useState("");
  const form = useForm<z.infer<typeof reviewForm>>({ resolver: zodResolver(reviewForm), defaultValues: { text: "" } });
  const mutation = useMutation({
    mutationFn: async (cves: string[]) => (await apiRequest("GET", `/api/analyze?cves=${encodeURIComponent(cves.join(","))}`)).json() as Promise<Analysis>,
    onSuccess: result => { setAnalysis(result); setReviewed(new Set()); setFeedback("Source lookup complete. Asset exposure remains unknown."); },
  });
  const exportReview = async () => {
    const bundle = await makeBundle({ type: "CIVILIAN_VULNERABILITY_REVIEW", created_at: new Date().toISOString(), classification: "EXPERIMENTAL_SOFTWARE", analysis, human_review: { identity_verified: false, reviewed_cves: [...reviewed], note: "User-asserted review marks; not approvals for external action." }, actions_executed: [], signature_status: "UNSIGNED" });
    download(bundle, "szl-review-bundle.json"); setFeedback("Bundle exported. The checksum checks integrity, not truth, identity, or authorization.");
  };
  return <>
    <Heading title="Vulnerability evidence, in context." eyebrow="DEFENSIVE SOFTWARE RISK" action={<Button onClick={exportReview} data-testid="button-export-review"><ArrowDownToLine size={15}/>Export evidence</Button>}>Start with public CVE identifiers and compare two independent source types. <br/>Known exploitation is a fact from a catalogue; EPSS is a probability estimate.</Heading>
    <div className="review-input panel"><Form {...form}><form onSubmit={form.handleSubmit(v => mutation.mutate([...new Set(v.text.toUpperCase().split(/[\s,;]+/).filter(Boolean))]))}><FormField control={form.control} name="text" render={({ field }) => <FormItem><FormLabel>Look up CVEs</FormLabel><FormControl><Textarea {...field} data-testid="input-cves" placeholder="CVE-2021-44228, CVE-2023-34362" rows={2}/></FormControl><FormMessage/></FormItem>}/><div className="form-actions"><span className="small muted">Up to 50 identifiers. Sent to FIRST for public score lookup; no system scanning.</span><Button type="submit" disabled={mutation.isPending} data-testid="button-lookup">{mutation.isPending ? <Loader2 size={15} className="animate-spin"/> : <Search size={15}/>}Look up evidence</Button></div></form></Form></div>
    {mutation.isError && <ErrorBox message="The lookup could not be completed. Existing rows are retained; no missing score is treated as zero."/>}
    {feedback && <div className="feedback" role="status" data-testid="status-review-feedback">{feedback}</div>}
    <div className="scope-notice"><Tag kind="INFERENCE"/><span>Policy: KEV first, then EPSS descending, then CVE ID. Exposure and impact are unknown; this is not a risk score or a vulnerability scan.</span></div>
    <Panel title="Evidence for analyst review" eyebrow={`${analysis.input.length} PUBLIC IDENTIFIERS / ${reviewed.size} USER-MARKED REVIEWS`} action={<div className="search-box"><Search size={15}/><Input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter CVEs or products" aria-label="Filter vulnerabilities" data-testid="input-filter-cves"/></div>}><AdvisoryTable rows={analysis.rows.filter(r => `${r.cve} ${r.kev?.product} ${r.kev?.vendorProject}`.toLowerCase().includes(filter.toLowerCase()))} reviewed={reviewed} onSelect={setSelected}/><div className="panel-bottom small muted">Review marks stay in this view until export. Reloading or leaving the view clears them; no approval or remediation is sent.</div></Panel>
    <div className="sources-inline">{analysis.sources.map(s => <SourceLine key={s.name} source={s}/>)}</div>
    <Dialog open={selected !== null} onOpenChange={open => !open && setSelected(null)}><DialogContent className="detail-dialog"><DialogHeader><DialogTitle className="mono">{selected?.cve}</DialogTitle><DialogDescription>Public evidence only. No asset match or compromise is established.</DialogDescription></DialogHeader>{selected && <><div className="detail-section"><Tag/><h3>{selected.kev?.vulnerabilityName ?? "No KEV entry in the available snapshot"}</h3><p>{selected.kev?.shortDescription ?? "Absence from the available KEV snapshot is not evidence that a vulnerability is safe or unexploited."}</p></div><div className="detail-metrics"><div><span>KEV status</span><strong>{selected.kev_status}</strong></div><div><span>EPSS estimate</span><strong>{percent(selected.epss?.epss)}</strong></div><div><span>Score date</span><strong>{selected.epss?.date ?? "Unavailable"}</strong></div></div><div className="detail-section"><Tag kind="INFERENCE"/><p>{selected.explanation}</p></div>{selected.kev && <div className="detail-section"><h3>CISA's required-action text</h3><p>{selected.kev.requiredAction}</p><External href={sources.kev}>Read the CISA catalogue</External></div>}<div className="scope-notice"><LockKeyhole size={16}/><span>This view does not establish affected versions or authorization. Confirm inventory, context, and vendor advice before changing systems.</span></div><Button onClick={() => { setReviewed(previous => { const next = new Set(previous); if (next.has(selected.cve)) next.delete(selected.cve); else next.add(selected.cve); return next; }); }} variant={reviewed.has(selected.cve) ? "outline" : "default"} data-testid="button-mark-reviewed">{reviewed.has(selected.cve) ? "Remove review mark" : "Mark evidence reviewed"}</Button></>}</DialogContent></Dialog>
  </>;
}

function EstatePage({ estate }: { estate: Estate }) {
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState("all");
  const [selected, setSelected] = useState<RepoAudit | null>(null);
  const [limit, setLimit] = useState(30);
  const rows = estate.repositories.filter(r => `${r.name} ${r.description ?? ""}`.toLowerCase().includes(search.toLowerCase()) && (scope === "all" || scope === "archived" && r.archived || scope === "active" && !r.archived || scope === "local-policy" && !r.audit.security_policy_present));
  return <>
    <Heading title="One view of the public estate." eyebrow="PUBLIC REPOSITORY EVIDENCE" action={<Button variant="outline" onClick={() => download(estate, "szl-public-repository-audit.json")} data-testid="button-export-estate"><ArrowDownToLine size={15}/>Export snapshot</Button>}>Every public repository visible in the audit is listed, including archived projects. <br/>These are metadata and file-path observations, not proof that code is secure or a service is running.</Heading>
    <div className="snapshot-strip"><Tag/><span>{fmt(estate.summary.repo_count)} public repositories · {fmt(estate.summary.files_indexed)} file paths · {date(String(estate.summary.observed_at))}</span></div>
    <div className="table-toolbar"><div className="search-box"><Search size={16}/><Input value={search} onChange={e => { setSearch(e.target.value); setLimit(30); }} placeholder="Find a repository or capability" aria-label="Find repository" data-testid="input-repo-search"/></div><select value={scope} onChange={e => { setScope(e.target.value); setLimit(30); }} aria-label="Repository filter" data-testid="select-repo-scope"><option value="all">All public repositories</option><option value="active">Not archived</option><option value="archived">Archived</option><option value="local-policy">No repo-local security policy found</option></select><span className="small muted">{rows.length} matches</span></div>
    <div className="panel table-scroll"><table className="data-table repo-table" data-testid="table-repositories"><thead><tr><th>Repository</th><th>Files</th><th>Workflows</th><th>Test paths</th><th>Local security policy</th><th>State</th></tr></thead><tbody>{rows.slice(0, limit).map(repo => <tr key={repo.name}><td><button className="table-button" onClick={() => setSelected(repo)} data-testid={`button-repo-${repo.name}`}>{repo.name}<ArrowUpRight size={13}/></button><div className="small muted">{repo.language ?? "Language unreported"} · {repo.license ?? "License metadata unreported"}</div></td><td className="mono">{fmt(repo.audit.file_count)}</td><td className="mono">{repo.audit.workflow_paths.length}</td><td className="mono">{repo.audit.test_paths_count}</td><td><span className="small">{repo.audit.security_policy_present ? "Path found" : "Not found locally"}</span></td><td><span className="evidence-pill">{repo.archived ? "Archived" : "Not archived"}</span></td></tr>)}</tbody></table>{!rows.length && <div className="empty-state">No matching repositories. Try a different search or filter.</div>}{limit < rows.length && <div className="load-more"><Button variant="outline" onClick={() => setLimit(v => v + 30)} data-testid="button-more-repos">Show 30 more</Button></div>}</div>
    <div className="scope-notice"><CircleHelp size={17}/><span>“Not found locally” is not “missing across the organization”: inherited policies may apply. Workflow and test-path counts do not establish successful execution.</span></div>
    <Dialog open={!!selected} onOpenChange={v => !v && setSelected(null)}><DialogContent className="detail-dialog"><DialogHeader><DialogTitle>{selected?.name}</DialogTitle><DialogDescription>Frozen structural observation, not a production-readiness judgment.</DialogDescription></DialogHeader>{selected && <><p>{selected.description ?? "No repository description supplied."}</p><dl className="metadata-list"><div><dt>Observed</dt><dd>{date(selected.audit.observed_at)}</dd></div><div><dt>Tree object ID</dt><dd className="mono hash">{selected.audit.tree_oid}</dd></div><div><dt>Recursive tree truncated</dt><dd>{String(selected.audit.truncated)}</dd></div><div><dt>Root license path</dt><dd>{selected.audit.license_file_present ? "Found" : "Not found"}</dd></div><div><dt>Lockfile paths</dt><dd>{selected.audit.lockfile_paths.length}</dd></div></dl><External href={selected.url}>Open repository</External><details><summary data-testid="toggle-workflow-paths">Inspect observed workflow paths ({selected.audit.workflow_paths.length})</summary><ul className="path-list">{selected.audit.workflow_paths.map(p => <li className="mono" key={p}>{p}</li>)}</ul></details></>}</DialogContent></Dialog>
  </>;
}

function ObservePage() {
  const [target, setTarget] = useState("a-11-oy.com");
  const [area, setArea] = useState("NY");
  const [scenario, setScenario] = useState<"cyber" | "weather" | "research">("cyber");
  const [approval, setApproval] = useState(false);
  const headers = useMutation({ mutationFn: async () => (await apiRequest("GET", `/api/observe/headers?target=${encodeURIComponent(target)}`)).json() as Promise<HeaderScan> });
  const weather = useQuery<WeatherSnapshot>({ queryKey: ["/api/weather", area], queryFn: async () => (await apiRequest("GET", `/api/weather?area=${area}`)).json() });
  const plan = useMutation({ mutationFn: async () => (await apiRequest("GET", `/api/plan?scenario=${scenario}&simulatedApproval=${approval}&mode=dry-run`)).json() as Promise<DryRunPlan> });
  return <>
    <Heading title="Useful observation. Bounded action." eyebrow="CIVILIAN RESILIENCE">Inspect your allowlisted public sites and official weather alerts. <br/>Rehearse a response in a simulator that has no external-action adapter.</Heading>
    <div className="scope-notice"><Tag/><span>Web checks send one ordinary HTTPS HEAD request to an allowlisted SZL hostname, with bounded same-host redirects. No port scans, exploitation, logins, or third-party targets.</span></div>
    <div className="observe-grid">
      <Panel title="Public web configuration" eyebrow="OWNER-SCOPED / LOW-IMPACT"><label htmlFor="target" className="field-label">Authorized public target</label><div className="control-row"><select id="target" value={target} onChange={e => { setTarget(e.target.value); headers.reset(); }} data-testid="select-scan-target"><option>a-11-oy.com</option><option>szlholdings.com</option></select><Button onClick={() => headers.mutate()} disabled={headers.isPending} data-testid="button-check-headers">{headers.isPending ? <Loader2 className="animate-spin" size={14}/> : <Search size={14}/>}Check headers</Button></div><p className="small muted pad-inline">An observed header is not a validated policy. This is a configuration observation, not a penetration test.</p>
        {headers.isError && <ErrorBox message="The bounded check could not complete. No alternate host or protocol was attempted."/>}
        {headers.data ? <><SourceLine source={headers.data.source}/><div className="small pad-inline">HTTP status: {headers.data.http_status ?? "Unavailable"} · checked {date(headers.data.checked_at)}</div><div className="header-results">{headers.data.headers.map(h => <div key={h.name}><span className="mono">{h.name}</span><span>{headers.data?.source.status === "UNAVAILABLE" ? "Unknown" : h.value ? "Observed" : "Not observed"}</span>{h.value && <code>{h.value}</code>}</div>)}</div></> : <div className="empty-state compact-empty"><ShieldCheck size={28}/><span>No check run yet.</span><span className="small muted">Select an allowlisted site, then inspect its response.</span></div>}
      </Panel>
      <Panel title="Official weather watch" eyebrow="NWS / PUBLIC ALERT FEED" action={<select value={area} onChange={e => setArea(e.target.value)} aria-label="Weather state" data-testid="select-weather-state"><option value="NY">New York</option><option value="CA">California</option><option value="TX">Texas</option></select>}>
        {weather.isLoading ? <div className="empty-state"><Loader2 className="animate-spin"/>Reading official alerts.</div> : weather.isError ? <ErrorBox message="The weather service is unavailable. No-alert status is not inferred."/> : weather.data && <><SourceLine source={weather.data.source}/><div className="weather-count"><strong>{weather.data.count === null ? "Unknown" : weather.data.count}</strong><span>{weather.data.count === null ? "Alert count unavailable" : "alerts returned in this snapshot"}</span></div><div className="alert-list">{weather.data.alerts.slice(0, 5).map(a => <div className="weather-alert" key={a.id}><div className="flex items-center justify-between gap-2"><h3>{a.event}</h3><span className="evidence-pill">{a.severity}</span></div><p>{a.headline}</p><div className="small muted">{a.area}</div><div className="small muted">Expires {date(a.expires)} · {a.certainty}</div><External href={a.url}>Official record</External></div>)}{weather.data.count === 0 && <div className="empty-state">No active alerts were returned for this area at fetch time. That is not a guarantee of safe conditions.</div>}{weather.data.count === null && <ErrorBox message="Unable to retrieve the feed. Use the official weather service for current conditions."/>}</div></>}
        <div className="quiet-note"><CloudSun size={17}/><span>Informational only, not an emergency-alert system. Cached for 10 minutes; follow official instructions.</span></div>
      </Panel>
    </div>
    <Panel title="Response rehearsal" eyebrow="SIMULATED / NO ACTIONS EXECUTED" action={<Tag kind="SIMULATED"/>}><div className="planner"><div><label className="field-label" htmlFor="scenario">Civilian scenario</label><select id="scenario" value={scenario} onChange={e => { setScenario(e.target.value as typeof scenario); plan.reset(); }} data-testid="select-plan-scenario"><option value="cyber">Software-risk review</option><option value="weather">Facilities weather review</option><option value="research">Biomedical literature review</option></select><label className="check-label"><input type="checkbox" checked={approval} onChange={e => { setApproval(e.target.checked); plan.reset(); }} data-testid="checkbox-simulate-approval"/>Simulate a reviewer approval</label><p className="small muted">This is a fictional state transition, not an authenticated approval. It cannot change a firewall, send an alert, control a device, or run a biological experiment.</p><Button onClick={() => plan.mutate()} disabled={plan.isPending} data-testid="button-run-dry-plan">Run dry-run plan<ArrowRight size={15}/></Button></div><div className="plan-output">{plan.isError && <ErrorBox message="The dry-run request was rejected. No fallback action ran."/>}{plan.data ? <><div className="plan-result" data-testid="status-plan-result"><span className="mono">EXTERNAL ACTIONS: 0</span><span>Execution adapter: absent</span></div>{plan.data.steps.map((s, i) => <div className="plan-step" key={s.title}><span className="step-number">{String(i + 1).padStart(2, "0")}</span><div><h3>{s.title}<span className="small mono muted">{s.state}</span></h3><p>{s.detail}</p></div></div>)}</> : <div className="empty-state compact-empty"><GitBranch size={28}/><span>Rehearse the decision path.</span><span className="small muted">Nothing runs against the selected target.</span></div>}</div></div></Panel>
  </>;
}

function EvidenceGraphic({ data, compact = false }: { data: Overview; compact?: boolean }) {
  const [active, setActive] = useState(0);
  const stages = [
    { name: "Observe", subtitle: "Public source records", count: data.feeds.kev.source.status === "UNAVAILABLE" ? "KEV unavailable" : `${(data.feeds.kev.catalog_count ?? data.feeds.kev.entries.length).toLocaleString()} KEV entries`, text: "CISA KEV and FIRST EPSS are read separately. Repository metadata is a frozen public snapshot." },
    { name: "Bind", subtitle: "Source + time + digest", count: "SHA-256 / unsigned", text: "Source bytes receive a digest and fetch timestamp. These self-reported hashes are not signatures or independent witnesses." },
    { name: "Explain", subtitle: "Deterministic ordering", count: "KEV → EPSS → ID", text: "Known exploitation is ordered first. Missing estimates remain null; no organization-specific risk score is invented." },
    { name: "Review", subtitle: "Human interpretation", count: "No action authority", text: "A review mark records only the user's inspection in this browser view. It grants no permissions and triggers no external action." },
  ];
  return <div className={`evidence-graphic ${compact ? "compact-graphic" : ""}`}><div className="flow-stages">{stages.map((s, i) => <button key={s.name} className={`flow-stage ${active === i ? "flow-stage-active" : ""}`} onClick={() => setActive(i)} data-testid={`button-flow-${i}`}><span className="flow-index">{String(i + 1).padStart(2, "0")}</span><div className="layer-figure" aria-hidden="true"><svg viewBox="0 0 120 88"><path d="m12 52 48-24 48 24-48 24Z" fill="none" stroke="currentColor" opacity=".15"/><path d="m12 41 48-24 48 24-48 24Z" fill="none" stroke="currentColor" opacity=".35"/><path d="m12 30 48-24 48 24-48 24Z" fill="var(--layer-fill)" stroke="currentColor"/>{i === 0 && <><circle cx="45" cy="28" r="3" fill="currentColor"/><circle cx="64" cy="34" r="3" fill="currentColor"/><circle cx="72" cy="24" r="3" fill="currentColor"/></>}{i === 1 && <path d="m47 29 9 5 18-11m-32 9 13 7 22-12" stroke="currentColor" fill="none"/>}{i === 2 && <path d="m42 32 11-11 6 12 14-8" stroke="currentColor" fill="none"/>}{i === 3 && <path d="m47 28 11 7 17-13" stroke="currentColor" strokeWidth="2" fill="none"/>}</svg></div><strong>{s.name}</strong><span className="small muted">{s.subtitle}</span><span className="mono flow-count">{s.count}</span>{i < 3 && <ChevronRight size={15} className="flow-arrow"/>}</button>)}</div><div className="flow-description" data-testid="text-flow-description"><span className="mono">{String(active + 1).padStart(2, "0")}</span><p>{stages[active].text}</p></div></div>;
}
function EvidencePage({ data }: { data: Overview }) {
  const [result, setResult] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  async function verify(file: File | undefined) {
    if (!file) return;
    if (file.size > 2_000_000) { setResult("Rejected: file is larger than the 2 MB verification limit."); return; }
    try {
      const envelope = JSON.parse(await file.text());
      if (envelope.schema !== "szl-observatory.bundle.v1" || typeof envelope.payload_json !== "string" || typeof envelope.sha256 !== "string" || envelope.signature !== null || envelope.trust !== "UNSIGNED_SELF_ASSERTED") throw new Error("Unsupported bundle schema.");
      JSON.parse(envelope.payload_json);
      // Verify the original bytes, not JSON reserialization.
      const actual = bytesToHex(digestBytes(new TextEncoder().encode(envelope.payload_json)));
      setResult(actual === envelope.sha256 ? "Checksum matches. This bundle is UNSIGNED: identity, truth, completeness, and action authority are not verified." : "CHECKSUM MISMATCH. The payload does not match the supplied digest; do not rely on this bundle.");
    } catch { setResult("Rejected: this is not a valid observatory evidence bundle."); }
  }
  return <>
    <Heading title="Make the reasoning inspectable." eyebrow="EVIDENCE MAP">Follow the actual data path through this prototype. <br/>The layered view describes provenance and decisions, not a live sensor network.</Heading>
    <Panel title="Source to review" eyebrow="INTERACTIVE / SELECT A LAYER"><EvidenceGraphic data={data}/></Panel>
    <div className="overview-grid"><Panel title="Inspect a review bundle" eyebrow="OFFLINE CHECKSUM VERIFICATION"><div className="verify-area"><FileCheck2 size={36}/><h3>Recheck the exact payload bytes.</h3><p>Choose a bundle exported from Vulnerability review. Verification happens in your browser; the file is not uploaded.</p><input type="file" ref={fileInput} accept=".json,application/json" className="sr-only" onChange={e => verify(e.target.files?.[0])} data-testid="input-bundle-file"/><Button variant="outline" onClick={() => fileInput.current?.click()} data-testid="button-verify-bundle">Choose evidence bundle</Button>{result && <div className="feedback" role="status" data-testid="status-bundle-verification">{result}</div>}</div></Panel>
    <Panel title="Integrity is not truth" eyebrow="TRUST BOUNDARY"><div className="truth-list"><div><Tag/><p>A matching digest means the payload and its stated hash agree.</p></div><div><Tag kind="BLOCKED">NOT PROVEN</Tag><p>Anyone can replace both. There is no signer identity, independent witness, or external timestamp in this prototype.</p></div><div><Tag kind="PROPOSAL"/><p>A production successor can add pinned signer identities, append-only storage, and independently verified receipts.</p></div></div><div className="panel-bottom"><External href="https://github.com/sigstore/model-transparency">Study Sigstore's trust model</External></div></Panel></div>
  </>;
}

const methods = [
  { n: "01", title: "Know when not to answer", field: "UNCERTAINTY", people: "Anastasios Angelopoulos · Stephen Bates", method: "Conformal prediction", equation: "P(Y ∈ C(X)) ≥ 1 − α", idea: "Set-valued civilian alert triage that abstains when evidence cannot support one class.", constraint: "Marginal coverage requires exchangeability. It is not an individual safety guarantee under arbitrary drift.", url: "https://www.nowpublishers.com/article/DownloadSummary/MAL-101" },
  { n: "02", title: "Learn a small physical model", field: "CIVILIAN RELIABILITY", people: "Steven Brunton · Joshua Proctor · J. Nathan Kutz", method: "Sparse identification of nonlinear dynamics", equation: "dX/dt = Θ(X)Ξ", idea: "Study sparse equipment or energy dynamics and flag unexplained residuals for a maintainer.", constraint: "A poor function library, noisy derivatives, or hidden state can invalidate the inferred model. No control actions.", url: "https://arxiv.org/abs/1509.03580" },
  { n: "03", title: "Respect physical constraints", field: "APPLIED PHYSICS", people: "Maziar Raissi · Paris Perdikaris · George Karniadakis", method: "Physics-informed neural networks", equation: "L = Ldata + λ Lphysics", idea: "Research energy and environmental estimation using explicitly stated conservation-law residuals.", constraint: "Proposed loss sketch, not a reproduced result. A physics penalty is not proof of physical correctness.", url: "https://neuralfields.cs.brown.edu/paper_4.html" },
  { n: "04", title: "Share insights, not records", field: "PRIVACY", people: "Cynthia Dwork · Aaron Roth", method: "Differential privacy", equation: "P[M(D)∈S] ≤ exp(ε) P[M(D′)∈S] + δ", idea: "Share aggregate civilian incident statistics with an explicit privacy budget and release ledger.", constraint: "Requires an adjacency definition, sensitivity bounds, privacy accounting, and a reviewed implementation.", url: "https://www.cis.upenn.edu/~aaroth/privacybook.html" },
  { n: "05", title: "Specify before automating", field: "FORMAL METHODS", people: "Leslie Lamport", method: "TLA+ state-machine specifications", equation: "Execute ⇒ Authorized ∧ Approved", idea: "Model expiry, replay, review separation, and idempotency before adding a real response connector.", constraint: "A checked specification does not prove implementation equivalence or the safety of an external system.", url: "https://lamport.azurewebsites.net/tla/book.html" },
  { n: "06", title: "Separate correlation from cause", field: "CAUSAL REASONING", people: "Judea Pearl · Madelyn Glymour · Nicholas Jewell", method: "Causal intervention models", equation: "P(Y | do(X)) ≠ P(Y | X)", idea: "Design civilian studies of whether a patch, maintenance change, or workflow actually improves outcomes.", constraint: "Effects require defensible causal assumptions and a suitable design. Observed associations alone are insufficient.", url: "https://bayes.cs.ucla.edu/PRIMER/primer-ch3.pdf" },
];
function ResearchPage() {
  const [category, setCategory] = useState("all");
  const cards = category === "all" ? methods : methods.filter(m => category === "physical" ? ["02", "03"].includes(m.n) : ["01", "04", "05", "06"].includes(m.n));
  return <>
    <Heading title="Study the method. Build the test." eyebrow="RESEARCH FRONTIER / NOT TRAINED CAPABILITIES">Recombine useful ideas around civilian safety and measurable evidence. <br/>Every adaptation here is a proposal, not a novelty claim or a completed experiment.</Heading>
    <div className="scope-notice"><Tag kind="PROPOSAL"/><span>Before promotion: licensed data, a frozen evaluation, meaningful baselines, at least three training seeds where applicable, uncertainty intervals, and a fresh release receipt.</span></div>
    <div className="research-toolbar">{[["all", "All methods"], ["cyber", "Trust & decisions"], ["physical", "Physics & reliability"]].map(([value, label]) => <button className={category === value ? "filter-tab active" : "filter-tab"} key={value} onClick={() => setCategory(value)} data-testid={`button-research-${value}`}>{label}</button>)}</div>
    <div className="research-grid">{cards.map(m => <article className="research-card" key={m.n} data-testid={`card-method-${m.n}`}><div className="flex items-center justify-between"><span className="eyebrow">{m.field}</span><span className="mono muted">{m.n}</span></div><h2>{m.title}</h2><div className="small muted">{m.people}</div><div className="equation" aria-label={m.method}>{m.equation}</div><h3>{m.method}</h3><p>{m.idea}</p><div className="method-constraint">{m.constraint}</div><External href={m.url}>Read the primary work</External></article>)}</div>
    <Panel title="Learn from builders without copying their claims" eyebrow="PUBLIC METHODS / ORIGINAL IMPLEMENTATION"><div className="leader-rows">
      {[["Wazuh", "Collect defensible endpoint evidence. Any future connector must be tenant-authorized and read-only by default.", "https://github.com/wazuh/wazuh"], ["OCSF + Sigma", "Normalize events and preserve rule provenance. OCSF is Apache-2.0; SigmaHQ rule licensing has attribution requirements.", "https://ocsf.io/"], ["OpenSSF GUAC", "Connect software components to supply-chain evidence instead of treating every CVE as relevant to every asset.", "https://docs.guac.sh/guac/"], ["Sigstore", "Bind artifacts to configured signer identities. Do not confuse an intact signature with a correct or safe model.", "https://github.com/sigstore/model-transparency"], ["Ai2", "Study the openly released model flow, data recipes, checkpoints, and evaluations. No external weights are loaded here.", "https://allenai.org/blog/olmo3"], ["Dropzone AI", "Study the evidence-to-conclusion investigation workflow. Product documentation is a vendor claim, not an independent benchmark.", "https://docs.dropzone.ai/dropzone-101/terms-and-defs/investigations"]].map(([name, text, url]) => <div key={name}><h3>{name}</h3><p>{text}</p><External href={url}>Primary material</External></div>)}
    </div></Panel>
    <div className="next-lane"><div><div className="eyebrow">BIOMEDICAL CIVILIAN DIRECTION / PROPOSAL</div><h2>Monitor evidence, not biological targets.</h2><p>Start with literature provenance, retraction checks, study-design labels, and measurement calibration. This prototype does not diagnose, design organisms, or execute experiments.</p></div><External href="https://www.ncbi.nlm.nih.gov/sites/books/NBK25497/">NCBI data-access guidance</External></div>
  </>;
}

export default function App() {
  return <QueryClientProvider client={queryClient}><Router hook={useHashLocation}><Shell/></Router></QueryClientProvider>;
}
