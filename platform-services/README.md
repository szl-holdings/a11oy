# platform-services — bounded source mirror

This directory holds a **bounded, source-only mirror** of selected files from the
separate server-side backend monorepo [`szl-holdings/platform`](https://github.com/szl-holdings/platform).

## Why this exists (consolidation decision — Agent A)

The `platform` repo is a large (~641 MB), genuinely server-side backend monorepo
(api-server, `services/{alloy-fabric-api,meridian_control_plane,vsp-otel,customer-portal,...}`,
`apps/{alloy-runtime-api,substrate-inference,...}`, db-migrations, workers, and 130+ packages).
It is the live backend that runs the whole ecosystem and is correctly **KEEP-SEPARATE** —
it is not vendored wholesale into `a11oy`.

However, two files in `platform/artifacts/api-server` document the **real api-server contract**
that a11oy's operator surface and organs depend on, so they are mirrored here (source only,
no `node_modules`, no build output, no lockfiles):

- `api-server/src/middlewares/global-auth-enforcer.ts` — the GUARDIAN deny-by-default
  authentication enforcer (`GUARDIAN_ENFORCE=true`) with the explicit public-route allowlist.
- `api-server/src/routes/ouroboros.ts` — the Ouroboros HTTP surface that lifts the
  Egyptian-mathematics primitives into the three deployable organs
  (`/api/ouroboros/a11oy/*`, `/api/ouroboros/amaru/*`, `/api/ouroboros/sentra/*`).

The rest of `platform` (services, apps, workers, db, the 130+ packages) is **not** mirrored:
it is server-side infrastructure that lives and runs in `szl-holdings/platform`.

Note: `platform/services/graphql-gateway` is an empty placeholder in the upstream repo
(only `.github/` boilerplate) and therefore has nothing unique to ingest.

Source of truth: https://github.com/szl-holdings/platform

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
