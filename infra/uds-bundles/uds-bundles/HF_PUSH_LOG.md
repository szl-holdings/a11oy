# HF PUSH LOG — UDS Productionization (SZL Crew)

**Agent:** UDS Productionization subagent (signing as Yachay)
**Date:** 2026-06-01
**Auth:** founder admin token at `.secret/hf_token` via `HfApi(token=...)` DIRECT
(per PURIQ charter HARD RULE — never the connector). `whoami` confirmed SZLHOLDINGS
org membership before push.

## Result: PUSH_OK ✅ (verified live 200)

| Field | Value |
|---|---|
| Target | `SZLHOLDINGS/uds-bundles-v1` (dataset) |
| Path in repo | `uds_productionization/` |
| `whoami` | `betterwithage` → orgs include **SZLHOLDINGS** |
| Commit SHA | `bcfd121a0e56969c48a09045c282508d46fd0d81` |
| Live check (resolve, 307→CDN) | `200` on `.../PER_BUNDLE/a11oy/uds-bundle.yaml` (followed redirect) |
| Excluded | `artifacts/*`, `*.log`, `airgap_screenshots/*` (build outputs, produced on build host) |
| ADDITIVE | yes — new dataset path; no HF Space touched |

## What was uploaded (all 5 flagships + combined + scripts + reports)
- `PER_BUNDLE/{a11oy,amaru,sentra,killinchu,rosie}/` — Dockerfile, serve.py, zarf.yaml,
  uds-bundle.yaml, uds-package.yaml, chart/ (Chart+values+templates), manifests/ (ns, VS, AuthPolicy, NetPol)
- `PER_BUNDLE/szl-crew-full-stack/uds-bundle.yaml` — combined 5-package bundle
- `build_sign_all.sh`, `airgap_test.sh`
- `INVENTORY.md`, `AIRGAP_TEST_REPORT.md`, `COSIGN_SIGNING_LOG.md`, `HF_PUSH_LOG.md`,
  `GH_PUSH_LOG.md`, `FOUNDER_DEPLOY_QUICKSTART.md`, `GAP_CHECK.md`

## Reproduce
```bash
python3 /home/user/workspace/hf_push_uds.py   # uses .secret/hf_token, founder direct
```

— Yachay, 2026-06-01. Founder token, SZLHOLDINGS verified, live 200. ADDITIVE.
