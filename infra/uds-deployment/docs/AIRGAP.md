# Airgap Deployment Guide — szl-uds-deployment

## Overview

`szl-receipts` and `szl-vessels-demo` are designed to operate in airgap (disconnected) environments. However, the `vessels` component includes a runtime call to the OFAC sanctions list feed that must be disabled in airgap deployments.

## OFAC Sanctions URL (R31 — Airgap Violation)

**Audit finding:** `uds/values.yaml` defaults `vessels.sanctionsUrl` to `https://sanctionslist.ofac.treas.gov/Home/SdnList`. In a network-connected environment this URL is called at runtime to screen vessel IMO numbers. In an airgap cluster, this call will fail and must be explicitly disabled.

**Fix:** Set the variable to an empty string at deploy time. When empty, the vessels service skips live sanctions screening and logs a warning.

### Disabling for airgap deploy

```bash
# Option 1: via uds-bundle variable override
uds deploy uds-bundle-szl-receipts-bundle-amd64-0.3.1.tar.zst \
  --set VESSELS_IMO_SANCTIONS_URL="" \
  --confirm

# Option 2: via Zarf package deploy
zarf package deploy zarf-package-szl-vessels-demo-amd64-0.3.1.tar.zst \
  --set VESSELS_IMO_SANCTIONS_URL="" \
  --confirm

# Option 3: via uds-bundle.yaml override (recommended for CI/CD)
# In uds-bundle.yaml overrides section:
overrides:
  szl-receipts:
    szl-receipts:
      values:
        - path: vessels.sanctionsUrl
          value: ""
```

### Enabling live screening (connected environments only)

```bash
uds deploy uds-bundle-szl-receipts-bundle-amd64-0.3.1.tar.zst \
  --set VESSELS_IMO_SANCTIONS_URL="https://sanctionslist.ofac.treas.gov/Home/SdnList" \
  --confirm
```

Or use `--enable-network-checks` flag if you have a custom wrapper script that sets this variable conditionally:

```bash
# In a deployment wrapper script:
if [[ "${ENABLE_NETWORK_CHECKS:-false}" == "true" ]]; then
  SANCTIONS_URL="https://sanctionslist.ofac.treas.gov/Home/SdnList"
else
  SANCTIONS_URL=""
  echo "WARN: Airgap mode — live OFAC sanctions screening disabled"
fi

uds deploy uds-bundle-szl-receipts-bundle-amd64-0.3.1.tar.zst \
  --set VESSELS_IMO_SANCTIONS_URL="${SANCTIONS_URL}" \
  --confirm
```

## Images pre-bundled for airgap

The Zarf package bundles the following images at create time. No runtime pull from docker.io or ghcr.io is needed after `zarf package create`:

| Image | Purpose |
|-------|---------|
| `docker.io/library/python:3.12-slim` | szl-receipts-server |
| `docker.io/library/nginx:1.27-alpine` | szl-dashboard, vessels nginx proxy |
| `ghcr.io/szl-holdings/vessels:<version>` | vessels maritime intelligence service |

## Airgap-safe checklist

Before deploying in a disconnected environment:

- [ ] Set `VESSELS_IMO_SANCTIONS_URL=""` (disables OFAC live feed)
- [ ] Confirm `ENABLE_NETWORK_CHECKS` is not set or is `false`
- [ ] Verify all images are bundled in the Zarf package (`zarf package inspect <pkg>`)
- [ ] Ensure UDS Core bundle was created in a connected environment and transferred airgap

## Reference

- [UDS Package Requirements — Airgap](https://github.com/defenseunicorns/uds-common/blob/main/docs/uds-packages/requirements/uds-package-requirements.md)
- [Zarf airgap documentation](https://docs.zarf.dev/tutorials/0-creating-a-zarf-package/)
- Audit finding: R31 in `/home/user/workspace/szl/audit_2026-05-30_cursor_offline/expert_audit/L_catalog_gaps.md`
