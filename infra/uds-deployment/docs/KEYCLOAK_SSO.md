# Keycloak SSO — realms, clients, and operator groups

How SSO works for the SZL substrate on UDS Core, what is generated automatically, and
what an operator must bootstrap once. Scoped to the hackathon demo.

## What is automatic (UDS Operator generates it)

Each app declares an `spec.sso` block in its `UDSPackage` CR
(`packages/<app>/uds-package.yaml`, and `charts/szl-receipts/templates/uds-package.yaml`).
The UDS Operator (the Pepr module inside UDS Core) reads those blocks and **generates the
Keycloak client** for each one — you do not hand-create clients.

- Human-facing apps (`rosie`, `vessels`, `szl-receipts`) use `redirectUris` +
  `enableAuthserviceSelector`, so the Operator wires the **authservice** sidecar in front
  of the pod. Every request then carries a verified OIDC identity before it reaches the app.
- Machine-to-machine apps (`a11oy`, `amaru`, `sentra`) use `standardFlowEnabled: false` +
  `serviceAccountsEnabled: true` — a client-credentials (machine-to-machine) client, no
  browser login UI.

Reference: the `spec.sso` field set is defined in
`defenseunicorns/uds-core@v1.5.0/schemas/package-v1alpha1.schema.json` and demonstrated in
`uds-packages/reference-package/chart/templates/uds-package.yaml` (the `secretTemplate` /
`clientField(...)` idiom that maps client fields into a k8s Secret).

## What an operator bootstraps once (NOT auto-generated)

1. **The realm.** UDS Core ships a default `uds` realm via
   `defenseunicorns/uds-identity-config@v0.27.0`. The demo uses that realm; we do not ship
   a custom realm for the hackathon.
2. **The `/szl/operators` group.** `rosie` and `vessels` gate human sign-in on
   `spec.sso.groups.anyOf: ["/szl/operators"]`. That group, and the operator user's
   membership in it, must exist in Keycloak before sign-in succeeds. For the local k3d demo
   this is the `setup:keycloak-user` step from
   `defenseunicorns/uds-common@v1.24.11/tasks/setup.yaml`, plus creating the group:
   - Sign in to Keycloak admin (the `INSECURE_ADMIN_PASSWORD_GENERATION=true` flow prints
     the admin password — see `uds zarf tools kubectl ... keycloak` and the UDS Core docs).
   - Realm `uds` → Groups → create `szl` → child group `operators` (path `/szl/operators`).
   - Assign your demo operator user to `/szl/operators`.

## Out of scope for the hackathon (documented, not shipped)

- A bespoke `szl` realm with custom claims/roles. The default `uds` realm is sufficient for
  the demo; a custom realm is a post-Warhacker item.
- Automated group/role provisioning (would belong in a `uds-identity-config`-style overlay).
  Tracked as a follow-up; not scripted here to keep this PR scope-tight (Operating Principle #8).

## Quick check (after deploy)

```
# Confirm the Operator created the clients from the spec.sso blocks:
uds zarf tools kubectl get secrets -A | grep -E 'sso|szl-(rosie|vessels|receipts)'
# rosie/vessels human login should redirect to https://sso.<domain>/realms/uds/...
```
