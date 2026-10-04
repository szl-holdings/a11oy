import type { Analysis, DryRunPlan, FeedSnapshot, SourceRecord } from "./schema";

export function rankAdvisories(cves: string[], feeds: FeedSnapshot): Analysis {
  const unique = [...new Set(cves)].sort();
  const kevAvailable = feeds.kev.source.status !== "UNAVAILABLE";
  const kev = new Map(feeds.kev.entries.map(item => [item.cveID, item]));
  const epss = new Map(feeds.epss.entries.map(item => [item.cve, item]));
  const rows: Analysis["rows"] = unique.map(cve => {
    const k = kevAvailable ? kev.get(cve) ?? null : null;
    const e = feeds.epss.source.status === "UNAVAILABLE" ? null : epss.get(cve) ?? null;
    return {
      cve,
      kev_status: k ? "LISTED" : kevAvailable ? "NOT_LISTED" : "UNKNOWN",
      kev: k,
      epss: e,
      exposure: "UNKNOWN",
      priority: k ? "REVIEW_KNOWN_EXPLOITATION" : e ? "REVIEW_ESTIMATE" : "INSUFFICIENT_DATA",
      explanation: k
        ? "This CVE is listed in the available CISA known-exploited snapshot, so the advisory policy places it ahead of non-listed records. This does not establish that your systems are affected."
        : e
          ? "This record is ordered using FIRST's EPSS estimate after KEV-listed records. EPSS is not your organization's attack probability; exposure and impact are unknown."
          : "Evidence is insufficient for a score-based ordering. Missing estimates are null, never zero, and lack of a KEV listing does not imply safety.",
    };
  });
  rows.sort((a, b) =>
    Number(b.kev_status === "LISTED") - Number(a.kev_status === "LISTED") ||
    (b.epss?.epss ?? -1) - (a.epss?.epss ?? -1) ||
    a.cve.localeCompare(b.cve)
  );
  return {
    analyzed_at: new Date().toISOString(),
    policy_version: "kev-first-epss-second/1.0",
    input: unique,
    rows,
    sources: [feeds.kev.source, feeds.epss.source],
    asset_inventory_connected: false,
    model_executed: false,
  };
}

export function sourceWithAge(source: SourceRecord, maxFetchAgeHours: number, now = Date.now()): SourceRecord {
  if (source.status === "UNAVAILABLE") return source;
  const fetched = source.fetched_at ? Date.parse(source.fetched_at) : NaN;
  if (!Number.isFinite(fetched) || fetched > now + 300_000 || now - fetched > maxFetchAgeHours * 3_600_000) {
    return { ...source, status: "STALE", error: source.error ?? "Snapshot is older than the configured freshness window or has an invalid clock." };
  }
  return source;
}

export function makeDryRun(scenario: DryRunPlan["scenario"], approval: boolean): DryRunPlan {
  const next = {
    cyber: "Would draft an internal software-risk review item for an authorized analyst.",
    weather: "Would draft a facilities review note linking to the official weather alert.",
    research: "Would draft a literature-review task containing citations, not biological procedures.",
  }[scenario];
  return {
    schema: "szl-observatory.dry-run.v1",
    classification: "SIMULATED",
    executed: false,
    external_calls: 0,
    scenario,
    steps: [
      { title: "Record a fictional observation", state: "SIMULATED", detail: "The scenario does not assert an incident, affected asset, patient result, or emergency." },
      { title: "Preserve the human boundary", state: approval ? "SIMULATED_APPROVAL" : "REVIEW_REQUIRED", detail: "This switch is a rehearsal input, not authentication or authorization." },
      { title: "Preview the next step", state: approval ? "WOULD_DRAFT" : "HELD", detail: approval ? next : "The simulated plan stops before a draft response until the reviewer input is selected." },
      { title: "Stop before external effects", state: "NO_ADAPTER", detail: "No ticket, alert, message, device command, network change, or laboratory action is executed." },
    ],
  };
}
