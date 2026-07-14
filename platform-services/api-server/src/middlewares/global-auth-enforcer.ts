// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — artifacts/api-server/src/middlewares/global-auth-enforcer.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Global Auth Enforcer (Deny-by-default)
 *
 * This middleware runs AFTER the auth hydrator (authMiddleware.ts) which populates
 * req.user / req.oidcUser. It enforces authentication for all /api/* routes by
 * default, returning 401 for unauthenticated requests unless the request path is
 * in the explicit public allowlist below.
 *
 * Public route groups:
 *  - Health endpoints (/api/health*)
 *  - Auth/login/register (/api/auth/*)
 *  - OIDC callbacks (/api/oidc/*)
 *  - Contact form (/api/contact)
 *  - Demo requests (/api/demo-requests)
 *  - Public status (/api/public/*)
 *  - Webhooks (/api/webhooks/*) — use HMAC authentication internally
 *  - SCIM 2.0 (/api/scim/*) — uses scimTokensTable bearer token auth (RFC 7643/7644);
 *    the SCIM auth is enforced within the SCIM router via scimBearerAuth middleware
 *  - Streaming webhook ingestion endpoints (/api/stream/webhook/*,
 *    /api/stream/ais-nmea) — use source token authentication (streamed-ingestion authToken)
 *  - SIEM webhook (/api/stream/webhook-siem) — NOT public; requires Bearer token auth
 *    (SIEM_WEBHOOK_TOKEN env var or a registered SIEM webhook data source authToken)
 *  - Streaming SSE read endpoints (/api/stream/siem-events, /api/stream/market-data,
 *    /api/stream/ais-tracking, /api/stream/status) — read-only live feeds used by dashboards
 *  - A2A Federation discovery endpoints (/api/federation/agents*, /api/federation/health)
 *    POST /federation/agents/:id/chat uses its own FEDERATION_API_TOKENS bearer token
 *  - DOS Public API (/api/v1/*)
 *  - API docs (/api/docs*, /api/docs.json)
 *  - CSRF token endpoint (/api/csrf-token)
 *  - Per-service health probes
 */

import { timingSafeEqual } from "node:crypto";
import type { Request, Response, NextFunction } from "express";
import { serverTelemetry } from "@szl-holdings/observability";
import { sendUnauthorized } from "../lib/api-response";
import { verifyInternalHeader } from "../lib/internal-tokens";

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      /**
       * Set by globalAuthEnforcer when a request is allowed through under a
       * narrow trust condition (rather than session/token auth). Downstream
       * middlewares can opt to relax their own checks for a specific reason
       * — e.g. tenantScope skips membership for `"nexus_loopback"` because
       * the orchestrator is a platform principal.
       */
      authBypassReason?: "nexus_loopback";
    }
  }
}

const PUBLIC_EXACT_PATHS = new Set([
  "/api/contact",
  "/api/demo-requests",
  "/api/csrf-token",
  // Mobile OIDC token exchange — called before the user has a session, so must be public.
  // The route validates the OIDC authorization code and issues a session token.
  "/api/mobile-auth/token-exchange",
  "/api/docs.json",
  "/api/openapi",
  "/api/openapi.json",
  "/api/version",
  "/api/ready",
  // Carlota Jo invoice email — public, unauthenticated (same model as
  // /api/booking/time-entries and /api/booking/services). The route handler
  // applies its own validation (400 for missing fields) and rate limiting.
  "/api/booking/invoices/email",
  // Carlota Jo AI advisor chat — public endpoint for website visitors to engage
  // with the AI qualification assistant before booking. Rate-limited (5 req/hour
  // per IP) inside the route handler. No PII required; session key is client-generated.
  "/api/carlota/advisor/chat",
  // Carlota Jo booking paths used by the embedded inline scheduler in AdvisorChat.
  // Both are needed without a session: availability is read-only, reservations POST
  // is the visitor-facing booking action (same model as /api/contact / /api/demo-requests).
  // Admin CRUD on reservations (GET list, PATCH, DELETE) is protected by authMiddleware
  // in the route handler itself.
  // NOTE: routes live at /booking/... in carlota-jo.ts (no /carlota prefix there).
  "/api/booking/availability",
  "/api/booking/reservations",
  "/api/stream/ais-nmea",
  "/api/stream/siem-events",
  "/api/stream/market-data",
  "/api/stream/ais-tracking",
  "/api/stream/status",
  "/api/federation/health",
  "/api/federation/agents",
  // A2A delegation endpoint — public so external agents can delegate tasks without a
  // browser session. Bearer-token auth (API key or OAuth JWT with federation:write scope)
  // is enforced inside the route handler.
  "/api/federation/delegate",
  // OAuth 2.0 token endpoint — public so services can exchange client credentials
  // for an access token before they have a session. The endpoint validates
  // client_id + hashed client_secret internally.
  "/api/oauth/token",
  // Enterprise MCP internal endpoints — called by the substrate-mcp-gateway
  // service. Uses x-internal-token (ALLOY_INTERNAL_TOKEN) verified inside
  // each handler; no user session is present during inter-service calls.
  "/api/enterprise-mcp/audit",
  "/api/enterprise-mcp/link-user",
  "/api/enterprise-mcp/internal-revoke",
  "/api/enterprise-mcp/revoked-subjects",
  "/api/enterprise-mcp/idp-configs",
  // Self-healing orchestrator — read-only GET endpoints.
  // Exact-path matches ensure the mutating PATCH /policies/:id/toggle
  // (which requires auth) is NOT covered by these allowlist entries.
  "/api/self-healing/stats",
  "/api/self-healing/policies",
  // Shared action store SSE stream — read-only live feed used by the Business
  // State / Enterprise State pages. GET /api/action-store is allowed below via
  // a method-specific check so the deny-by-default enforcer still rejects
  // anonymous PATCH requests as a first line of defence; route-level requireAuth
  // in action-store.ts provides defence-in-depth for the mutating path.
  "/api/action-store/stream",
  // Continuum Policy Authoring Studio — read-only state endpoint for the demo
  // surface (lets the studio render its initial state without a session).
  // Mutating routes (POST/DELETE on /versions, /versions/:id/sign,
  // /test-cases) are NOT whitelisted and enforce auth via authMiddleware.
  "/api/continuum/policy-compiler/state",
  // Shared risk evidence store — backs the Save-run-as-evidence button on
  // Terra/Vessels Risk Simulation panels so cited Monte Carlo runs are
  // visible to external reviewers and lender briefings (instead of being
  // stuck in per-browser localStorage). Public under the same model as the
  // rest of the Terra/Vessels demo surfaces.
  // Lyte legacy surfaces — read-only public GET endpoints backing the 5
  // decision-intelligence pages (Ownership Drift, Pressure Map, Action Debt
  // Index, Decision Replay, Board View). See routes/lyte-surfaces.ts.
  "/api/lyte/ownership-drift",
  "/api/lyte/pressure-map",
  "/api/lyte/action-debt",
  "/api/lyte/decision-replay",
  "/api/lyte/board-view",
  // Mapbox publishable-token discovery endpoint. Returns a pk.* token that is
  // intentionally public (Mapbox enforces URL allowlists on the token itself),
  // so demo-mode visitors and pre-auth marketing pages can render the Vessels
  // fleet map and Terra property maps without a session. Rate-limited inline.
  "/api/config/mapbox-token",
  // Lyte intel surfaces — Signal Fusion, Governance Posture, Decision Schema
  // Library. See routes/lyte-intel.ts.
  "/api/lyte/signal-fusion",
  "/api/lyte/governance-domains",
  "/api/lyte/decision-schemas",
  // Lyte macro market indicators — delayed/EOD feed via Alpha Vantage.
  // Public read surface; same pattern as lyte-surfaces.ts routes above.
  // Refresh POST is also public — no user data involved; worst case is an
  // extra Alpha Vantage API call which is rate-limited by the adapter.
  "/api/lyte/market-indicators",
  "/api/lyte/market-indicators/refresh",
  // Lyte market feed adapters (FRED, Yahoo Finance) — read-only public endpoints.
  // List adapters, fetch all adapter data, or fetch a specific adapter's data.
  // No user data involved; feeds are read-only macro indicators.
  "/api/lyte/market-feeds",
  "/api/lyte/market-feeds/data",
  // Investor Hub company fundamentals — read-only descriptive metrics keyed by
  // category='fundamentals' in holdings_metrics. Public so the marketing
  // /investors page can render live values without a session, with a static
  // fallback baked into the page when the API is unavailable.
  "/api/holdings/fundamentals",
  // Investor sub-page content (overview, architecture, moat, roadmap, trust,
  // founder) — read-only descriptive content keyed by category='investor-content'
  // in holdings_metrics. Public so the marketing /investors/* pages can render
  // live content without a session, with a static fallback baked into each page
  // when the API is unavailable.
  "/api/holdings/investor-content",
  // Decision Runtime v1 — list endpoint GET /api/decisions/cards.
  // Per-card GET routes are whitelisted by prefix in PUBLIC_PREFIXES below.
  // Mutating routes (approve/reject/request-changes, simulate-policy) are NOT
  // whitelisted here — they enforce auth via requireAuth in the route handler.
  "/api/decisions/cards",
  // CONSTELLATION World Model live SSE stream — read-only, demo-pool driven
  // entity/edge updates that drive the live indicator on the World Model
  // Explorer. The mutating /api/graph/* endpoints are NOT covered here and
  // continue to enforce auth + tenant scope via routes/groups/graph.ts.
  "/api/graph/stream",
  // Mission Runbooks list endpoint — exact path covers GET /api/mission-runbooks
  // (the bare list URL without a trailing slash). Sub-paths are covered by the
  // "/api/mission-runbooks/" prefix entry in PUBLIC_PREFIXES below.
  "/api/mission-runbooks",
  // Helios — Frontier Intelligence & Evolution Engine read-only GET endpoints.
  // Exact-path entries ensure mutating routes (PATCH /proposals/:id/status,
  // PATCH /scanners/:id/toggle, POST /scanners/:id/run, POST /mcp) remain
  // protected by session auth and are NOT reachable anonymously.
  "/api/helios/stats",
  "/api/helios/signals",
  "/api/helios/hatun",
  "/api/helios/proposals",
  "/api/helios/benchmarks",
  "/api/helios/scanners",
  "/api/helios/memos",
  "/api/helios/frontier-briefing",
  "/api/hf-mcp/health",
  "/api/mcp/health",
  // HuggingFace ML Intelligence — legal NLP, threat correlation, AIS decode, property
  // valuation, summarization, and embeddings. All POST endpoints are public demo surfaces
  // with no destructive side-effects. Model catalog GET is also public.
  "/api/hf-intelligence/models",
  // Terra AI Deal Sourcing — public read-only GET routes. The candidates list and
  // adapters list are accessible without a session so the Terra demo works.
  // GET /candidates/:propertyId is covered by the prefix entry in PUBLIC_PREFIXES.
  // POST /save-to-portfolio, GET /saved-deals, GET /alert-bus/events are NOT here;
  // they require a session and return 401 to unauthenticated callers.
  "/api/terra/sourcing/candidates",
  "/api/terra/sourcing/adapters",
  // Notification badge count — safe to expose unauthenticated; returns
  // { unreadCount: 0 } when no session is present. Exact-path entry ensures
  // only the bare /count URL is public; sub-paths remain protected.
  "/api/notifications/count",
  // SZL Holdings public attestation surface (Track C-02). Both endpoints MUST
  // be reachable without a session: the public Ed25519 key publication is the
  // root of trust for independent verifiers, and /governance/stats backs the
  // public /governance ledger header. POST /api/v1/replay-attestation is
  // already covered by the /api/v1/ prefix entry below.
  "/api/.well-known/szl-attestation-keys.json",
  "/api/governance/stats",
  // Agent Mesh — genuinely-public read-only paths. Listed here (exact match
  // via Set.has) rather than in PUBLIC_PREFIXES (startsWith) to prevent any
  // future /api/agent-mesh/state* or /api/agent-mesh/scan* route from being
  // accidentally bypassed. Gateway telemetry sub-paths (/gateway, /gateway/stream,
  // /gateway/export.csv, /gateway/latency) are NOT included; those require
  // operator-only auth enforced at route level.
  "/api/agent-mesh/state",
  "/api/agent-mesh/index",
  "/api/agent-mesh/scan",
  "/api/hf/hub/status",
]);

const PUBLIC_PREFIXES = [
  "/api/health",
  "/api/auth/",
  "/api/oidc/",
  "/api/public/",
  // SIGIL — SZL Integrated Governance & Invariant Layer.
  // Pure-functional, stateless, validated by Zod, no PII. The framework's
  // demo UI in A11oy/Sentra/Amaru calls these endpoints from the browser
  // before any session exists. Compute-only; no data is read or written.
  "/api/sigil/",
  // Ouroboros · Gauß axis ONLY — operationalised v5 primitives 17 + 20.
  // Same compute-only posture as /api/sigil/ (stateless, Zod-validated, no
  // PII). The broader /api/ouroboros/ tree includes stateful routes
  // (anchor append/batch, fleet audit, reconcile-handoff) that MUST keep
  // their normal auth posture, so this allowlist is narrowed to gauss.
  "/api/ouroboros/gauss/",
  // Ouroboros · Guardrails axis ONLY — operationalised v6 SKU
  // (@workspace/ouroboros-guardrails). Same compute-only posture as gauss:
  // stateless, Zod-validated, no PII, no session, no server-side
  // persistence — each evaluate() call uses a fresh Guardrails instance,
  // so no tenant state leaks across requests. The broader /api/ouroboros/
  // tree retains its default auth, so this exemption stays narrowed.
  "/api/ouroboros/guardrails/",
  "/api/ouroboros/sovereign/propeller/",
  "/api/ouroboros/sovereign/sota/",
  "/api/ouroboros/sovereign/arbitrage/",
  "/api/ouroboros/sovereign/ultra/",
  "/api/ouroboros/sovereign/xi/",
  "/api/webhooks/",
  "/api/scim/",
  "/api/stream/webhook/",
  "/api/federation/agents/",
  "/api/v1/",
  "/api/docs/",
  // Terra Cognitive runtime — read-only GET routes use authMiddleware({ required: false })
  // and are intentionally accessible without a session (richer context shown when authed).
  // The POST mutation /submit-review is NOT included here; it enforces its own auth.
  "/api/terra/cognitive/",
  // Terra property-scoped intelligence modules — read-only GET routes serving deterministic
  // seed-based data per propertyId. Accessible without a session so the Terra demo shows
  // realistic intelligence results when navigating from the property detail page.
  "/api/terra/properties/",
  // Terra portfolio-scoped intelligence modules — read-only GET routes serving deterministic
  // seed-based portfolio/list data for the 6 intelligence modules. Public so the Terra demo
  // shows realistic results without a session.
  "/api/terra/portfolio/",
  // Terra "Why This Property Now" engine — distress decomposition, ownership chain,
  // financing stress, and neighborhood motion from live NYC open data. Public so the
  // demo works without a session; NYC SODA API calls are made server-side.
  "/api/terra/why-this-property/",
  // Terra AI Deal Sourcing — per-property candidates route: GET /candidates/:propertyId.
  // Exact list + adapters paths are in PUBLIC_EXACT_PATHS. This prefix covers only
  // the parametric sub-path so it does not inadvertently open save-to-portfolio,
  // saved-deals, or alert-bus/events to unauthenticated callers.
  "/api/terra/sourcing/candidates/",
  // Public contact form sub-paths: POST /contact/submit (lead capture from
  // every marketing surface) and the admin-guarded /contact/requests +
  // /contact/submissions GETs (those enforce adminGuard internally, so it is
  // safe to bypass the global enforcer here). Bare /api/contact above is
  // retained for the legacy fetch in szl-holdings/trust-center.
  // HuggingFace ML Intelligence — POST inference endpoints. All are public demo surfaces.
  "/api/hf-intelligence/",
  // Unified HuggingFace Hub — read-only search endpoints only. Model/dataset/space
  // search is public so the demo frontend can display results without a session.
  // Mutating routes (POST/DELETE /pinned, POST /inference) are NOT included here
  // and require authenticated sessions to prevent HF_TOKEN quota abuse and ensure
  // tenant isolation on pinned items. The status endpoint uses PUBLIC_EXACT_PATHS.
  "/api/hf/hub/models",
  "/api/hf/hub/datasets",
  "/api/hf/hub/spaces",
  // PRAXIS Tool Bridge — marketing-audit, seo-audit, and finance-terminal are
  // public audit execution endpoints called from Carlota Jo, KORA, and the NEXUS
  // Bridge without a browser session. No per-user authenticated state is read or
  // written; all routes are stateless skill-pack invocations. thirdPartyCall()
  // gates each execution through the PRAXIS policy engine.
  "/api/praxis-tools/",
  "/api/contact/",
  // Carlota Jo inquiry submission — public POST endpoint for the contact/inquiry
  // form on the marketing site. Rate-limited (10/hour) inside the route handler.
  // GET /booking/inquiries (staff inbox) enforces its own authMiddleware() so
  // listing is still protected; only the POST creation path is public.
  "/api/booking/inquiries",
  // Carlota Jo time tracking & invoice read access — GET list endpoints are
  // public so the time-tracking page renders without a session. Mutating routes
  // (POST, PATCH, DELETE on time-entries/time-invoices and the generate endpoint)
  // are allowed only via a method-specific GET check below so the deny-by-default
  // enforcer rejects anonymous write attempts as a first line of defence;
  // route-level requireAuth in carlota-time-tracking.ts provides defence-in-depth.
  "/api/booking/invoices/email-log/",
  "/api/booking/services",
  "/api/booking/health",
  // Carlota Jo dashboard KPI metrics — team capacity and engagements summary.
  // Public so the dashboard can show live DB-backed numbers without a session.
  "/api/booking/team",
  "/api/booking/engagements-summary",
  // LP portal — read-only GET routes use authMiddleware({ required: false }) so the
  // marketing demo at /fund/lp-portal can showcase seeded data, while authenticated
  // LPs see only their own real records (matched by contact email).
  "/api/lp-portal/",
  // Anonymous page-view tracking — public endpoint that captures pre-login
  // site traffic so the investor funnel Visitor stage reflects real visitors.
  "/api/track/",
  // Public-site funnel analytics ingest. Anonymous client-side events posted
  // from any marketing page (often pre-session). Server validates eventName /
  // domain / sourceApp shape and writes to the analytics_events table; no PII
  // is forwarded by the client (property allow-list in lib/analytics.ts).
  "/api/analytics-engine/events",
  // Newsletter subscribe proxy — public, unauthenticated. Visitors on any
  // portfolio marketing page can subscribe to SZL Command without logging in.
  "/api/newsletter/",
  // Email provider bounce/complaint webhooks — server-to-server POST calls from
  // SendGrid and Resend. Authenticated via provider-specific secret headers.
  "/api/email-webhooks/",
  // Self-service email unsubscribe — public GET link embedded in every transactional
  // email. Validates HMAC token and writes to the email_suppressions table.
  "/api/email/unsubscribe",
  // Digest-specific unsubscribe — public GET link in digest email footer.
  // Validates HMAC token and sets email_enabled = false in notification_preferences.
  "/api/notifications/unsubscribe",
  // Digest re-subscribe — public GET link on the unsubscribe confirmation page.
  // Validates the same HMAC token and sets email_enabled = true.
  "/api/notifications/resubscribe",
  // Self-healing orchestrator — only /runs and /runs/:id GET requests are
  // whitelisted here as a prefix (covers the list endpoint and per-run detail).
  // /stats and /policies use PUBLIC_EXACT_PATHS above so the path-prefix match
  // cannot bleed into /policies/:id/toggle (the mutating PATCH route).
  "/api/self-healing/runs",
  // Simulation what-if engine — POST route is public so the Strategy simulation
  // page can compute cross-domain scenario impacts in demo mode without a session.
  "/api/simulation/",
  // Causal scenario & shock-propagation engine — GET /scenarios/library and
  // POST /scenarios/run are public so Lyte's Scenario Composer and the SZL
  // Holdings portfolio card can run scenarios without a session (demo mode).
  "/api/scenarios/",
  // Adversarial red-team & crisis stress-drill suite.
  // GET /stress-drill/scenarios is fully public (scenario library).
  // POST /stress-drill/drills and lifecycle routes enforce auth via authMiddleware
  // in the route handler. Global enforcer passes all stress-drill paths through;
  // individual protected routes re-apply authentication themselves.
  "/api/stress-drill/",
  // Continuum Meridian — cognitive observability OS read-only surfaces: model router
  // status, agent constellation health, forecast council results, signal graph,
  // Decision Weather, Counterfactual Ledger, Flight Recorder, MCP registry, and
  // Founder Intent doctrine. All read-only. Governance mutation routes
  // (evaluate, mcp-governance/check) are POST but still safe to expose
  // unauthenticated since they perform no data writes.
  "/api/meridian/",
  // Meridian MCP Activation registry (Task #3717 thin slice) — read-only registry
  // of the 15 governed external MCP servers and their activation status. No data
  // writes. Public so the MCP Activation dashboard at /meridian/mcp-activation
  // can render in demo/unauthenticated mode without a session.
  "/api/meridian-mcp/",
  // Demo reset — POST /api/demo/reset is public so the Demo Launchpad presenter
  // can reset scenario state without being logged in. Mounted pre-auth in app.ts;
  // this PUBLIC_PREFIXES entry is kept as defense-in-depth, scoped to exact path only.
  "/api/demo/reset",
  // Infrastructure status — lightweight public health summary used by the
  // Legatus infrastructure console to show live AquilaScore and threat level.
  "/api/infrastructure/",
  // Agent Mesh telemetry — the three genuinely-public paths (state, index, scan)
  // are listed in PUBLIC_EXACT_PATHS above using exact Set.has() matching.
  // The broad "/api/agent-mesh/" prefix is intentionally absent here to prevent
  // any startsWith bypass of the gateway telemetry sub-paths
  // (/gateway, /gateway/stream, /gateway/export.csv, /gateway/latency),
  // which expose platform-wide MCP containment data and must stay behind
  // operator-only auth (authMiddleware + requireRole('super_admin', 'ops')).
  // NOTE: nothing to add here — see PUBLIC_EXACT_PATHS for the agent-mesh entries.
  // Sentra cyber resilience cockpit — incidents + alerts CRUD backed by an
  // in-memory store (no DB). Public so the Sentra demo surface can fetch
  // live incident/alert data and run the create→triage→resolve flow without
  // a session. Write routes are still covered by CSRF double-submit
  // protection (global csrfMiddleware in server.ts).
  "/api/sentra/",
  // RF Intelligence — satellite AIS correlation engine, anomaly detection,
  // and geo-intel surface. All endpoints are read-only GET routes backed by
  // an in-memory simulation store. Public so the Command geo-intel map and
  // the Vessels satellite RF dashboard can hydrate without a session.
  "/api/rf-intel/",
  // Crisis Arena — strictly public surfaces only: leaderboard ranking,
  // platform summary, and sanitized architect public profiles.
  // All engagement, submission, triage, award, and graduate endpoints require
  // a session (enforced both here and in route-level authMiddleware).
  "/api/crisis-arena/leaderboard",
  "/api/crisis-arena/summary",
  "/api/crisis-arena/architects/",
  "/api/crisis-arena/score",
  // Pulse one-click email unsubscribe — token-protected, accessed from
  // recipient's inbox without a session. Mounted before authMiddleware in
  // routes/pulse.ts; this entry whitelists it past the global auth enforcer.
  "/api/pulse/unsubscribe",
  // Demo narrative payloads (Sentra ransomware, Counsel deadline) — read-only.
  // Backs the Decision Center pages with the same signal/evidence/recommendation
  // bundle that gets seeded into the live signal mesh at boot.
  "/api/narratives/",
  // Shared risk evidence store — list/save/delete cited Monte Carlo runs
  // and resolve them server-side for lender briefing exports. See
  // routes/risk-evidence.ts for the endpoint contract.
  "/api/risk-evidence/",
  // Global Operations Fabric — snapshot + SSE stream for the Fabric page.
  // Public prefix bypasses this enforcer so the route handler can apply its own
  // production/demo guard: in production the handler checks req.user and returns
  // 401 for unauthenticated requests; in sandbox/demo mode it serves synthetic
  // seed data publicly. Never exposes live production signals to anonymous users.
  "/api/fabric/",
  // A11oy Live Enterprise Execution Fabric — all read-side endpoints are fully
  // public in Phase 1 (demo mode, in-memory data). Mutating endpoints return 501.
  // Phase 2 will add session-gated write paths; the prefix bypass is intentional
  // for now so the A11oy demo renders without a session.
  "/api/a11oy/",
  // n8n Automation Bridge — MCP-compatible proxy to a connected n8n instance.
  // Public so the Command Automations surface renders in demo mode without a
  // session. When N8N_INSTANCE_URL/N8N_API_KEY are not set, the proxy returns
  // 503 { configured: false } rather than forwarding any request.
  "/api/n8n/",
  // Competitive Intel monitor — backs the Command Competitive Atlas page with
  // RSS-derived "Intel Update" alerts about tracked champions (CrowdStrike,
  // Clio, CoStar, Windward, Palantir, ThoughtSpot). The Atlas page is internal-
  // facing but unauthenticated like the rest of the Command demo surface; the
  // underlying data is sourced exclusively from public product blogs / RSS feeds.
  "/api/competitive-intel/",
  // NEXUS unified agentic AI layer — Research Swarm, Memory Fabric, and
  // Cross-App Orchestrator endpoints power the mockup-sandbox NEXUS demo and
  // are intended to be reachable without a session, mirroring the rest of the
  // SZL demo surface. Mutating routes (POST /memory, POST /orchestrate, etc.)
  // remain protected by CSRF + per-user write rate limiting in the router.
  "/api/nexus/",
  // Geospatial intelligence feed — read-only GET endpoints returning live-
  // mutating GeoPin data for the Command Geospatial Intelligence map. Public
  // so the map loads without a session (same model as /api/agent-mesh/).
  // PATCH/POST/DELETE on /api/geo-intel/pins persist to `geo_intel_pins` and
  // are NOT covered by this prefix bypass — they enforce auth via requireAuth
  // + denyIfReadOnly inside routes/geo-intel.ts.
  "/api/geo-intel/",
  // Decision Runtime v1 — per-card GET endpoints (GET /api/decisions/cards/:id).
  // Public so the Decision Center demo works without a session; route handlers
  // apply authMiddleware({ required: false }) and scope to ws-demo-001 for
  // unauthenticated callers. POST mutating routes at /decisions/cards/:id/approve
  // etc. enforce auth via requireAuth in the route handler (not here).
  "/api/decisions/cards/",
  // Knowledge base public GET endpoints — /support/knowledge (list) and
  // /support/knowledge/:slug (article detail). These are read-only and
  // intentionally accessible without a session so the support portal and
  // any marketing page can surface KB articles without requiring login.
  // Mutating routes (create/edit/archive KB articles) are under
  // /admin/kb-articles and remain protected by admin auth.
  "/api/support/knowledge",
  // Counsel Knowledge Index — graph+vector RAG over matter documents.
  // All endpoints (upload, status, query, seed) are public in the demo
  // surface; the route handler scopes results per-matter via matterId.
  // Mutating write routes remain covered by CSRF double-submit protection.
  "/api/counsel-knowledge/",
  // Helios sub-resource read-only paths — covers /hatun/search and
  // /hatun/nodes/:id (graph exploration) and /memos/:id (individual memo
  // detail). Mutating routes (PATCH /proposals/:id/status,
  // PATCH /scanners/:id/toggle, POST /scanners/:id/run, POST /mcp)
  // are NOT covered here and enforce auth via session/token.
  "/api/helios/hatun/",
  "/api/helios/memos/",
  // Mission Runbooks — in-memory runbook library and run orchestration backing
  // the Unified Command "Mission Runbooks" page. Fully public (same model as
  // action-store / self-healing) because it operates on seeded demo state
  // and does not read or write any tenant-scoped production data.
  // Trailing slash ensures prefix match is boundary-safe and cannot bleed into
  // future routes beginning with /api/mission-runbooks- (e.g. a hypothetical
  // /api/mission-runbooks-archive route would not be accidentally whitelisted).
  "/api/mission-runbooks/",
  // Conduit Reverse ETL — connection CRUD, sync CRUD, mapping editor, run
  // orchestration, template library, destination metadata, and stats surface.
  // Fully public in demo mode (DB-backed, no tenant PII exposed). Write routes
  // are still protected by CSRF double-submit (global csrfMiddleware in app.ts).
  "/api/conduit/",
  // A11oy defense pages — read-only GET endpoints serving demo data for the
  // PrecisionAI, WeaponizedIntel, AgentZeroTrust, AtlasShield, SwarmOrchestrator,
  // and PlaybookEngine screens. No tenant PII; static educational/threat-model
  // payloads. Public in demo mode so the a11oy frontend can render without auth.
  "/api/internal/a11oy/defense/",
  // Cognitive Reflexivity Engine (#4570–#4572) — observability + operator
  // approval surface. The broad prefix lets the A11oy reflexivity dashboard
  // read strategies / traces / health / recent-signals without a session.
  // Mutating routes (approve / reject / observations) are NOT relying on
  // this allowlist — they enforce `authMiddleware()` + `requireRole(...)`
  // explicitly inside the route handler so any operator approval is bound
  // to a real authenticated identity, never a body-supplied string.
  "/api/cognitive-reflexivity/",
  // Ouroboros integrations (#4570 follow-on) — pure-functional adapters that
  // lift Egyptian-mathematics primitives (frustum / seked / unit-fractions /
  // doubling) into A11oy / Amaru / Sentra. The adapters are stateless except
  // for the in-memory Sentra accumulator (process-local). All inputs are
  // strictly Zod-validated. Public so the three artifact frontends can
  // render the live Ouroboros panels without an authenticated session in
  // demo mode. Mutating routes are still rate-limited by the route group's
  // perUserWriteSlidingLimiter and CSRF-double-submit on writes.
  "/api/ouroboros/",
  // Hatun Doctrine governance CRUD — read-only GET surfaces and POST seed
  // endpoint backing the A11oy Doctrine pages. Public in demo mode (DB-backed,
  // no tenant PII). Write routes are CSRF-protected via global csrfMiddleware.
  "/api/doctrine/",
];

/**
 * Returns true if the given full request path (e.g. "/api/federation/health")
 * is whitelisted as a public endpoint by this enforcer's PUBLIC_EXACT_PATHS
 * or PUBLIC_PREFIXES tables.
 *
 * Exported so other middlewares mounted further down the router tree can
 * honor the same allowlist. Historically, group-level guards like
 * `tenantScope({ required: true })` mounted at a path prefix
 * (e.g. `router.use("/federation", tenantScope({...}))`) would 401 their
 * own subset of paths even when the global enforcer would have let them
 * through, because the allowlist only existed inside this file. Anything
 * downstream that wants to enforce auth should consult this function
 * first to avoid that trap.
 */
export function isAllowlistedPublicPath(fullPath: string): boolean {
  if (PUBLIC_EXACT_PATHS.has(fullPath)) return true;
  for (const prefix of PUBLIC_PREFIXES) {
    if (fullPath === prefix || fullPath.startsWith(prefix)) return true;
  }
  return false;
}

/**
 * Resolves the `/api/...` form of the request from inside any nested router.
 * Express strips the matched prefix from `req.path` as routers are descended,
 * so `req.path` alone is `/command-feed` for a tenantScope mounted at
 * `/cortex` under `/api`. Concatenating `req.baseUrl` recovers the original
 * shape that this file's allowlist is keyed on.
 */
export function fullApiPath(req: Request): string {
  const base = req.baseUrl ?? "";
  const path = req.path ?? "";
  if (!base) return path;
  if (path === "/" || path === "") return base;
  return base + path;
}

function isValidInternalToken(req: Request): boolean {
  const header = req.headers["x-internal-token"];
  if (typeof header !== "string") return false;
  return verifyInternalHeader(header, req.originalUrl || req.url) !== null;
}

/**
 * NEXUS Cross-App Orchestrator loopback bypass.
 * The orchestrator (artifacts/api-server/src/routes/nexus.ts) issues GET requests
 * to other internal SZL routes from the same process so the LLM has real data
 * to synthesize. We allow these only when ALL of the following are true:
 *   1. The TCP peer address (req.socket.remoteAddress — NOT req.ip, which is
 *      X-Forwarded-For-derived under app.set("trust proxy", 1) and therefore
 *      spoofable) is a loopback interface (127.0.0.1 / ::1).
 *   2. The request method is GET or HEAD.
 *   3. The request carries the `x-nexus-orchestrator: 1` header.
 *   4. The request path is in a hard-coded allowlist of safe, read-only
 *      orchestrator target endpoints.
 * Using req.socket.remoteAddress closes the X-Forwarded-For spoof vector: the
 * value comes from the kernel-reported TCP peer and cannot be set by a remote
 * client. The path allowlist further constrains the bypass to read-only
 * informational endpoints already exposed in PUBLIC_PREFIXES or via
 * authMiddleware({ required: false }).
 */
const NEXUS_ORCHESTRATOR_PATH_ALLOWLIST = [
  "/api/agent-mesh/state",
  "/api/agent-mesh/index",
  "/api/narratives/",
  "/api/infrastructure/status",
  "/api/core/health",
  "/api/core/metrics",
  "/api/fabric/snapshot",
  "/api/booking/services",
  "/api/vessels/live/fleet-summary",
  "/api/vessels/live/ais/combined",
  "/api/vessels/cognitive/route-anomalies",
  "/api/terra/live/mortgage-rates",
  "/api/terra/live/hud-fair-market-rents",
  "/api/terra/portfolio/overview",
  "/api/firestorm/live/threat-summary",
  "/api/firestorm/live/threats",
  "/api/firestorm/live/incidents",
  "/api/firestorm/live/compliance-summary",
  "/api/firestorm/live/asset-risk",
  "/api/firestorm/mitre/coverage",
  "/api/imperium/cloud/resources",
  "/api/imperium/cloud/metrics",
  "/api/imperium/cloud/sentinels",
  "/api/imperium/intelligence/briefs",
  "/api/imperium/supply-lines/status",
];

function isNexusOrchestratorLoopback(req: Request): boolean {
  if (req.method !== "GET" && req.method !== "HEAD") return false;
  const marker = req.headers["x-nexus-orchestrator"];
  if (marker !== "1") return false;
  // Use the kernel-reported TCP peer, not req.ip (which honors X-Forwarded-For
  // when trust proxy is enabled and is therefore spoofable from outside).
  const peer = req.socket?.remoteAddress ?? "";
  const isLoopback =
    peer === "127.0.0.1" || peer === "::1" || peer === "::ffff:127.0.0.1";
  if (!isLoopback) return false;
  const path = req.path;
  for (const allowed of NEXUS_ORCHESTRATOR_PATH_ALLOWLIST) {
    if (path === allowed || path.startsWith(`${allowed}/`)) return true;
  }
  return false;
}

/**
 * Trusted server-to-server Bearer token for POST /api/stream/webhook-siem.
 * Allows legitimate SIEM webhook providers to push events without a user
 * session. Scoped narrowly to that single route + method. The token must
 * match the SIEM_WEBHOOK_TOKEN environment variable exactly (timing-safe).
 * A missing or non-matching token is rejected here so the route handler is
 * never reached by unauthenticated callers; the route handler performs an
 * additional validation pass as defense-in-depth.
 */
function isValidSiemWebhookToken(req: Request): boolean {
  if (req.method !== "POST") return false;
  if (req.path !== "/api/stream/webhook-siem") return false;
  const secret = process.env.SIEM_WEBHOOK_TOKEN;
  if (!secret) return false;
  const authHeader = req.headers["authorization"];
  if (typeof authHeader !== "string" || !authHeader.startsWith("Bearer ")) return false;
  const provided = authHeader.slice(7);
  const a = Buffer.from(secret, "utf8");
  const b = Buffer.from(provided, "utf8");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

/**
 * Trusted server-to-server token for POST /api/orgs/:orgSlug/usage/events.
 * Lets internal collectors / background jobs record usage events without a
 * user session. Scoped narrowly to that single route + method to avoid
 * widening the bypass surface.
 */
function isValidUsageEventServiceToken(req: Request): boolean {
  if (req.method !== "POST") return false;
  // Match /api/orgs/<slug>/usage/events
  if (!/^\/api\/orgs\/[^/]+\/usage\/events\/?$/.test(req.path)) return false;
  const secret = process.env.USAGE_EVENT_SERVICE_TOKEN;
  if (!secret) return false;
  const header = req.headers["x-service-token"];
  if (typeof header !== "string") return false;
  const a = Buffer.from(secret, "utf8");
  const b = Buffer.from(header, "utf8");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export function globalAuthEnforcer(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  if (!req.path.startsWith("/api")) {
    next();
    return;
  }

  if (req.user || req.oidcUser) {
    next();
    return;
  }

  if (isValidInternalToken(req)) {
    next();
    return;
  }

  if (isNexusOrchestratorLoopback(req)) {
    // Authenticate the orchestrator loopback as an internal agent so that
    // downstream per-route authMiddleware() and group-level tenantScope()
    // see a valid principal and let the request through. This is the only
    // way the orchestrator can reach endpoints that apply additional auth
    // beyond the global enforcer (e.g. /api/firestorm/live/*, /api/imperium/*,
    // /api/vessels/live/* which are gated by tenantScope at the group mount).
    req.user = {
      id: 0,
      displayName: "NEXUS Orchestrator (loopback)",
      email: null,
      roles: ["ops"],
      orgs: [],
    };
    req.isInternalAgent = true;
    req.authBypassReason = "nexus_loopback";
    next();
    return;
  }

  if (isValidUsageEventServiceToken(req)) {
    next();
    return;
  }

  if (isValidSiemWebhookToken(req)) {
    next();
    return;
  }

  const path = req.path;

  if (isAllowlistedPublicPath(path)) {
    next();
    return;
  }

  // Action store read — GET /api/action-store is public (read-only snapshot).
  // PATCH /api/action-store is NOT covered here; it must carry a valid session
  // and is further gated by requireAuth in the route handler (defence-in-depth).
  if (req.method === "GET" && path === "/api/action-store") {
    next();
    return;
  }

  // Carlota Jo time tracking read — GET list/detail endpoints are public so
  // the time-tracking page renders without a session. POST, PATCH, DELETE, and
  // the /generate path are NOT covered here; they must carry a valid session
  // and are further gated by requireAuth in carlota-time-tracking.ts.
  if (
    req.method === "GET" &&
    (path.startsWith("/api/booking/time-entries") ||
      path.startsWith("/api/booking/time-invoices"))
  ) {
    next();
    return;
  }

  // Lyte Decision Replay sub-paths: /api/lyte/decision-replay/:id
  if (req.method === "GET" && path.startsWith("/api/lyte/decision-replay/")) {
    next();
    return;
  }

  // Lyte market feed adapter sub-paths: /api/lyte/market-feeds/:id (e.g. /fred, /yahoo)
  if (req.method === "GET" && path.startsWith("/api/lyte/market-feeds/")) {
    next();
    return;
  }

  // Non-production demo access routes: PIN-validated but session-free.
  // Completely disabled in production; route handlers apply timing-safe PIN check.
  // /api/pulse/demo/verify accepts PIN in POST body (never in URL).
  if (process.env.NODE_ENV !== "production" &&
    (path.startsWith("/api/pulse/demo/") || path === "/api/pulse/demo/verify")) {
    next();
    return;
  }

  // Cross-platform intelligence — read-only GET routes reading live trace-graph
  // data (signal correlations, evidence registry, run health, pilot intelligence).
  // Accessible without a session in non-production/demo environments so the Command
  // Surface can showcase cross-product intelligence without requiring login.
  // In production, auth is required (req.user check at the top of this function
  // already passes authenticated callers through before reaching this block).
  if (process.env.NODE_ENV !== "production" && path.startsWith("/api/cross-platform/")) {
    next();
    return;
  }

  serverTelemetry.recordAuthFailure();
  sendUnauthorized(res, "This endpoint requires a valid session. Please log in.");
}
