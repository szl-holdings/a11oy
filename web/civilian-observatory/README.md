# Civilian Observatory interface

FACT: This is an isolated React interface for the services-layer civilian observatory, not the parent `web/` application's build. It uses the existing a11oy Python runtime through GET-only same-origin endpoints.

PROPOSAL: Reproduce the shipped interface with:

```sh
npm ci --ignore-scripts
npm run check
npm test
VITE_OBSERVATORY_API_ROOT=/api/a11oy/v1/civilian npm run build
```

FACT: The output is `dist/public`; the canonical runtime copy is `civilian_observatory/static` at the repository root. The dedicated CI contract requires byte parity between that copy and a fresh source build.

FACT: The original interface concept takes layout inspiration from [BOb](https://bob.bzzzbx.com/dashboard.html), but copies no BOb code, assets, branding, or business data. Fonts and UI libraries retain their respective package licenses; application dependency versions are pinned in the lockfile.

FACT: The interface does not keep secrets in browser storage, load model weights, or confer action authority through its simulated reviewer switch. Evidence export is unsigned checksum consistency, not identity or truth verification.
