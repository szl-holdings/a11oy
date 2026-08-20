# Sentra — Data Model & Route Contract

Sentra's operator surface is backed by `artifacts/api-server`. Every visible
panel reads from a real endpoint; nothing in the operational cockpit is a
hard-coded fixture. This document captures the contract for the **landing
surface and dashboard reads** added/extended for Doctrine V6 operational
readiness.

All facts are anchored to canonical Doctrine V6 payload at
`/packages/payload/raw/payload.json`. Live counters (incidents, alerts,
control drifts, asset state) are computed against the Sentra Postgres tables
and the in-memory cyber-twin stores in `artifacts/api-server/src/services`.

## Data sources

| Source | Path | Used by |
| --- | --- | --- |
| Postgres `sentra_incidents` | `@szl-holdings/db` | Incidents, summary, posture |
| Postgres `sentra_alerts` | `@szl-holdings/db` | Alerts, summary, posture |
| `cyberAssetsStore` (in-memory) | `services/sentra-domain-stores.ts` | Posture, twin |
| `controlDriftsStore` (in-memory) | `services/sentra-domain-stores.ts` | Controls coverage |
| Doctrine V6 payload | `packages/payload/raw/payload.json` | Governance reads |

## Endpoint contract

### `GET /api/sentra/summary`

```ts
{
  source: 'live',
  activeIncidents: number,
  criticalAlerts: number,
  totalAlerts: number,
  lastUpdated: string  // ISO timestamp
}
```

### `GET /api/sentra/incidents` and `GET /api/sentra/incidents/:id`

Full CRUD on incident records with embedded `timeline: TimelineEntry[]`. See
`artifacts/sentra/src/lib/sentra-api.ts` (`Incident`, `TimelineEntry`).

### `GET /api/sentra/posture`

Exposure summary used by the Exposure Board. Anchored to live Postgres
counters and the cyber-twin asset store.

```ts
{
  source: 'live',
  lastUpdated: string,
  financialExposure: number,         // dollars
  financialExposureLabel: string,    // e.g. "$2.8M"
  openIncidents: number,
  criticalAlerts: number,
  openAlerts: number,
  compromisedAssets: number,
  totalAssets: number,
  sevenDayTrend: number[],           // 7 buckets, 0–100
  trendDeltaPct: number,
  topCveFindings: CveFinding[],
  insurancePosture: {
    coverageLimit: number,
    retention: number,
    carrier: string,
    policyId: string,
    complianceStatus: 'pass' | 'fail',
    complianceReason: string
  }
}
```

The financial exposure formula (canonical):

```
financialExposure = 1_400_000          // baseline OT-segment unsegmented
                  + openIncidents * 350_000
                  + compromisedAssets * 700_000
```

### `GET /api/sentra/controls/coverage`

NIST CSF rollup from the in-memory control drift store.

```ts
{
  source: 'live',
  lastUpdated: string,
  framework: 'NIST CSF',
  overallCoveragePct: number,
  totals: { total, compliant, drifting, remediating },
  families: Array<{
    family: 'Identify' | 'Protect' | 'Detect' | 'Respond' | 'Recover',
    total, compliant, drifting, remediating, coveragePct
  }>
}
```

### `GET /api/sentra/governance/doctrine`

Doctrine V6 governance reads — payload-grounded with safe fallback to the
canonical defaults if `packages/payload/raw/payload.json` is unreadable.

```ts
{
  source: 'live',
  lastUpdated: string,
  doctrine: {
    version: 'V6',
    replayRoot: string,
    bylineCanonical: 'Lutar, Stephen P.',
    licenseAllowlist: string[],            // Apache-2.0, MIT, BSD-3-Clause, CC-BY-4.0
    ingestionPolicy: 'PUBLIC_ONLY',
    byteIdenticalReplaysRequired: 5,
    lambdaAxesCount: 9,
    lambdaConjunctiveFloor: 0.9,
    moralGroundingFloor: 0.95,
    measurabilityHonestyFloor: 0.95
  },
  orgPosture: {
    reposTotal, ciFailing, openPrs,
    openCodeScanningAlerts, openDependabotHighCritical,
    scorecardAvg, branchProtectionCompliant, branchProtectionWeak
  },
  sentraRepo: { repository, defaultBranch, latestTag }
}
```

## Auth posture

All `/api/sentra/*` routes are covered by the existing PUBLIC_PREFIX entry
`"/api/sentra/"` in
`artifacts/api-server/src/middlewares/global-auth-enforcer.ts`. Mutating
routes (POST/PATCH on incidents, alerts, agents, hunts) enforce CSRF
double-submit via the global middleware and validate bodies with Zod.

## Frontend wiring

The frontend lives in `artifacts/sentra/src`. The API client is
`src/lib/sentra-api.ts` and exposes typed wrappers for every endpoint above.
Pages that consume these reads:

| Page | Endpoint | State handling |
| --- | --- | --- |
| `pages/exposure-board.tsx` | `getSentraPosture()` | `loading` → `live` (or `error` falls back to canonical seed) |
| `pages/dashboard.tsx` | `getCyberTwinPosture()`, `listCyberTwinIncidents()`, `listCyberTwinControlDrifts()` | `useApiQuery` (live/seed/offline badge) |
| `pages/control-drift.tsx` | `listCyberTwinControlDrifts()` | `useApiQuery` |
| `pages/hardening-controls.tsx` | React Query | `loading`/`error`/`refetch` |
| `components/GovernancePanels.tsx` | `getDoctrineGovernance()` (optional enrichment) | Static-anchored, payload-grounded |

`useApiQuery` (in `src/lib/use-api-query.ts`) provides loading / error /
seed-fallback states for every async call so panels never render blank.

## Smoke flow

1. Land on `/sentra/` (the Sentra landing page) — `SentraGovernancePanels`
   render the Doctrine V6 posture chips.
2. Navigate to `/sentra/exposure` — the Exposure Board fetches
   `GET /api/sentra/posture` and replaces the seed numbers with live values
   (financial exposure, top CVEs, insurance posture).
3. Click any incident card on `/sentra/dashboard` — the timeline view reads
   `GET /api/sentra/incidents/:id` and renders the embedded timeline array.

## Changelog

- **2026-05-16** — Added `/api/sentra/posture`, `/api/sentra/controls/coverage`,
  and `/api/sentra/governance/doctrine` (file:
  `artifacts/api-server/src/routes/sentra-posture.ts`); wired
  `pages/exposure-board.tsx` to live data; added typed client wrappers in
  `src/lib/sentra-api.ts`.
