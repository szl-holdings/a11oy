# A11oy — Data Model & API Contract

A11oy is a public, demo-grade artifact. Every visible surface is backed by a real
HTTP endpoint on `@workspace/api-server`. No mock data, no GraphQL auth-walls.

## Routes

All routes live under the `/api/a11oy/` prefix and are exempt from
`globalAuthEnforcer` via `PUBLIC_PREFIXES` in
`artifacts/api-server/src/middlewares/global-auth-enforcer.ts`. Mutating routes
self-enforce auth + CSRF at the route level (`routes/doctrine-crud.ts`).

| Surface (frontend)              | Endpoint                                          | Source file                                |
| ------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| `HomePage` hero / metrics strip | `GET  /api/a11oy/dashboard`                       | `routes/a11oy-dashboard-api.ts` (new)      |
| `NowPage` live ticker           | `GET  /api/a11oy/now`                             | `routes/a11oy-now-api.ts`                  |
| Capability Fabric panels        | `GET  /api/a11oy/fabric/*`                        | `routes/a11oy-fabric-api.ts`               |
| Doctrine V6 readouts            | `GET  /api/a11oy/doctrine/*`                      | `routes/doctrine-api.ts`                   |
| Doctrine CRUD (admin)           | `POST/PUT/DELETE /api/a11oy/doctrine/*`           | `routes/doctrine-crud.ts` (auth + CSRF)    |
| `GovernancePanels`              | `GET  /api/a11oy/fabric/proof-packets`, `/policy` | `routes/a11oy-fabric-api.ts` (preserved)   |

## `GET /api/a11oy/dashboard`

Returns `AlloyDashboardStats` aggregated from the alloy_* drizzle tables
(`alloyWorkflows`, `alloyWorkflowRuns`, `alloyApprovals`, `alloyAuditLog`).
Falls back to a zero-filled response when the tables are empty so the
HomePage hero never renders nulls.

```json
{
  "ok": true,
  "data": {
    "totalWorkflows": 0,
    "totalRuns": 0,
    "runningRuns": 0,
    "pendingApprovals": 0,
    "failedRuns": 0,
    "successRate": 100,
    "avgDurationMs": null,
    "workflowsByStatus": [],
    "recentActivity": []
  },
  "meta": {
    "timestamp": "2026-05-16T02:33:17.057Z",
    "source": "db",
    "visibility": "public",
    "doctrine": "V6"
  }
}
```

The frontend hook (`useDashboardSnapshot` in `pages/HomePage.tsx`) treats
`successRate` as already-percent (0–100); the resolver converts the raw
0–1 ratio before returning.

## Notes

- The legacy GraphQL `alloyDashboard` resolver
  (`graphql/domains/alloy.ts`) remains for parity but is no longer used by
  HomePage — it required a session and 401'd anonymous demo loads.
- `GovernancePanels` was already payload-grounded on
  `/api/a11oy/fabric/proof-packets` + `/api/a11oy/fabric/policy` and is
  preserved unchanged.
