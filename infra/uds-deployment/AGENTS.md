# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

Single-repo **SZL Governance Receipts** UDS add-on: Pepr admission policy emits DSSE HMAC receipts to an in-cluster Python receipts server + nginx dashboard. Primary workflow is Kubernetes-based (`uds run start`), not a local Node/Python app server.

### Services (see `docs/INSTALL.md` and `tasks.yaml`)

| Service | How to run |
|---------|------------|
| Full stack (k3d + UDS bundle) | `uds run start` (~90s on a laptop with working Docker/cgroups) |
| Demo workload | `uds run demo:workload` (needs cluster) |
| Receipt verification | `uds run demo:verify` |
| Dashboard (cluster) | `uds run port-forward` → http://localhost:8443 |
| Teardown | `uds run teardown` |

### Cloud VM caveats (Docker-in-Docker)

- **Docker daemon**: If `docker info` fails, start dockerd manually (this environment uses `fuse-overlayfs` + `iptables-legacy`). Ensure `/var/run/docker.sock` is usable (`sudo chmod 666 /var/run/docker.sock` if not in the `docker` group).
- **k3d / k3s**: Nested VMs often hit `failed to find memory cgroup (v2)` and k3s never becomes ready. Full `uds run start` may not complete here even when Docker runs. Validate Pepr/Helm/receipts server locally instead (below).
- **CLI install URLs**: `uds run install-deps` and `docs/INSTALL.md` use legacy asset names. Current releases use:
  - `uds-cli_v0.31.0_Linux_amd64` (not `uds-cli_linux_amd64`)
  - `zarf_v0.77.0_Linux_amd64` (not `zarf_linux_amd64`)
- **kubectl**: Not bundled with the repo; install from https://dl.k8s.io/ or use `k3d kubeconfig merge`.

### Pepr policy (`pepr/`)

```bash
cd pepr
npm ci --legacy-peer-deps
# Pepr CLI pulls optional deps at runtime; if `npx pepr build` fails on missing modules:
(cd node_modules/pepr && npm install --include=dev)
npm run build
```

`npm run test` (`npx pepr validate`) may error with "too many arguments" on some Pepr versions; **`npm run build`** is the reliable check. Output goes to `pepr/dist/`; copy to repo root for Zarf: `mkdir -p dist && cp -a pepr/dist dist/pepr`.

TypeScript in `package.json` is `^6.x` while Pepr 1.2.0 expects TS 5.8.x — use `--legacy-peer-deps`.

### Helm

```bash
helm lint charts/szl-receipts
```

### Local receipts server (no cluster)

Extract server from `charts/szl-receipts/templates/configmap.yaml` or run:

```bash
sed -n '20,180p' charts/szl-receipts/templates/configmap.yaml | sed 's/^    //' > /tmp/receipts_server.py
export SZL_HMAC_KEY=c3psLWRldi1kZW1vLWtleS0yMDI2LXdhcmhhY2tlcg==
export SZL_PORT=8443
python3 /tmp/receipts_server.py
curl -sf http://localhost:8443/health
```

### Zarf package create

Requires `dist/pepr` from Pepr build. As of this repo, `zarf.yaml` imports `name: szl-receipt-policy` but the built Pepr package metadata is `pepr-szl-receipt-policy` — `zarf package create` fails with "no compatible component named szl-receipt-policy" until that import name is aligned.

```bash
zarf package create . -f upstream --set DOMAIN=uds.dev --confirm
```

### Lint / test summary

| Check | Command |
|-------|---------|
| Helm | `helm lint charts/szl-receipts` |
| Pepr build | `cd pepr && npm run build` |
| Pepr validate | `cd pepr && npm run test` (may fail on CLI version) |
| E2E | `uds run start && uds run demo:workload && uds run demo:verify` (needs working k3d) |
