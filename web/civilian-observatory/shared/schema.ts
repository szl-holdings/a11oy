import { sqliteTable, text } from "drizzle-orm/sqlite-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// Only public-source cache data is persisted. Analyst decisions stay in browser memory.
export const snapshots = sqliteTable("snapshots", {
  key: text("key").primaryKey(),
  payload: text("payload").notNull(),
  observedAt: text("observed_at").notNull(),
});
export const insertSnapshotSchema = createInsertSchema(snapshots);
export type InsertSnapshot = z.infer<typeof insertSnapshotSchema>;
export type Snapshot = typeof snapshots.$inferSelect;

export const cveSchema = z.string().regex(/^CVE-\d{4}-\d{4,19}$/);
export const analyzeInputSchema = z.object({
  cves: z.array(cveSchema).min(1).max(50),
}).strict();
export type AnalyzeInput = z.infer<typeof analyzeInputSchema>;

export type ClaimType = "FACT" | "INFERENCE" | "PROPOSAL" | "BLOCKED";
export type SourceState = "OBSERVED" | "STALE" | "UNAVAILABLE";
export interface SourceRecord {
  name: string;
  source_url: string;
  fetched_at: string | null;
  source_date: string | null;
  sha256: string | null;
  status: SourceState;
  error: string | null;
}
export interface KevEntry {
  cveID: string;
  vendorProject: string;
  product: string;
  vulnerabilityName: string;
  shortDescription: string;
  requiredAction: string;
  dateAdded: string;
  knownRansomwareCampaignUse: string;
}
export interface EpssEntry {
  cve: string;
  epss: number;
  percentile: number;
  date: string;
}
export interface FeedSnapshot {
  schema_version: "1.0";
  generated_at: string;
  kev: { source: SourceRecord; catalog_version: string | null; catalog_count?: number; entries: KevEntry[] };
  epss: { source: SourceRecord; entries: EpssEntry[]; requested: string[] };
}
export interface Advisory {
  cve: string;
  kev_status: "LISTED" | "NOT_LISTED" | "UNKNOWN";
  kev: KevEntry | null;
  epss: EpssEntry | null;
  exposure: "UNKNOWN";
  priority: "REVIEW_KNOWN_EXPLOITATION" | "REVIEW_ESTIMATE" | "INSUFFICIENT_DATA";
  explanation: string;
}
export interface Analysis {
  analyzed_at: string;
  policy_version: "kev-first-epss-second/1.0";
  input: string[];
  rows: Advisory[];
  sources: SourceRecord[];
  asset_inventory_connected: false;
  model_executed: false;
}
export interface RepoAudit {
  name: string;
  full_name: string;
  url: string;
  visibility: string;
  archived: boolean;
  language: string | null;
  license: string | null;
  description: string | null;
  pushed_at: string;
  audit: {
    state: string;
    observed_at: string;
    tree_oid: string;
    truncated: boolean;
    file_count: number;
    license_file_present: boolean;
    security_policy_present: boolean;
    workflow_paths: string[];
    test_paths_count: number;
    lockfile_paths: string[];
  };
}
export interface Estate {
  summary: Record<string, number | string>;
  scope: string;
  repositories: RepoAudit[];
}
export interface Overview {
  estate: Estate;
  feeds: FeedSnapshot;
  analysis: Analysis;
  server_time: string;
}
export interface ReviewBundle {
  schema: "szl-observatory.bundle.v1";
  payload_json: string;
  sha256: string;
  signature: null;
  trust: "UNSIGNED_SELF_ASSERTED";
}
export interface HeaderScan {
  target: string;
  checked_at: string;
  method: "HEAD";
  http_status: number | null;
  headers: { name: string; value: string | null }[];
  source: SourceRecord;
  limitations: string[];
}
export interface WeatherSnapshot {
  area: "NY" | "CA" | "TX";
  source: SourceRecord;
  alerts: {
    id: string;
    event: string;
    headline: string;
    area: string;
    severity: string;
    certainty: string;
    expires: string | null;
    instruction: string;
    url: string;
  }[];
  count: number | null;
  reported_count: number | null;
}
export const planInputSchema = z.object({
  scenario: z.enum(["cyber", "weather", "research"]),
  simulatedApproval: z.boolean(),
  mode: z.literal("dry-run"),
}).strict();
export interface DryRunPlan {
  schema: "szl-observatory.dry-run.v1";
  classification: "SIMULATED";
  executed: false;
  external_calls: 0;
  scenario: "cyber" | "weather" | "research";
  steps: { title: string; state: string; detail: string }[];
}
