# demo/ — Warhacker Jack-In Mode Toolkit

**Founder directive 2026-05-30 16:46 EDT:** "real demo stuff no mock … able to
switch if they give us things to jack into." This directory is the on-the-fly
switch-over kit for whatever Defense Unicorns hands Stephen on-site.

## Start here
```bash
./demo/jack-in.sh            # interactive: "What did DU give you?" -> A..J
./demo/jack-in.sh --list     # list modes + readiness
./demo/jack-in.sh F --sans "https://github.com/szl-holdings/vessels/.github/workflows/*" --dry-run
```

## Modes
| Mode | What DU gives | Script | Readiness |
|---|---|---|---|
| A | kubectl to UDS Core | `modes/A-uds-core-kubectl/run.sh` | READY |
| B | vanilla k8s (no UDS Core) | `modes/B-vanilla-k8s/run.sh` | partial (installs slim-dev) |
| C | SSH to air-gapped env | `modes/C-airgap-usb/run.sh` | READY (wraps `warhacker/usb/`) |
| D | OIDC issuer + client ID | `modes/D-custom-oidc/run.sh` | config tweak |
| E | private OCI registry | `modes/E-private-registry/run.sh` | config tweak (vessels real) |
| F | cosign SAN allowlist | `modes/F-cosign-allowlist/run.sh` | READY (vessels#81 merged) |
| G | OTel collector endpoint | `modes/G-otel-endpoint/run.sh` | PR-stage (#19) |
| H | Kafka/NATS bus | `modes/H-message-bus/run.sh` | DOC ONLY (~1 day refactor) |
| I | IL5/FIPS crypto | `modes/I-il5-attestation/run.sh` | DOC ONLY (6–8 wks) |
| J | nothing (laptop) | `modes/J-laptop-k3d/run.sh` | READY (default) |

## Contract every script honours
- **Validate inputs, fail fast** — no silent assumptions; stable exit codes
  (`lib/common.sh`: 2 usage, 3 precond, 4 missing-tool, 5 cluster, 6 FA-001, 7 doc-only).
- **Print what it's about to do, then do it** — `run()` echoes each command.
- **`--dry-run`** on every script — changes nothing.
- **Honest about preconditions** — e.g. Mode B chains into Mode A; Modes H/I are doc-only.
- **FA-001 banner** on every deploy-class mode — only vessels has a real image.

## Portability
Bash 4+/5+ only. Tested for WSL2 (Stephen's Lenovo Yoga, Win 11). No zsh-isms.

## Honest-state references (read before narrating)
- `../REAL_DEMO_INVENTORY.md` (audit dir) — real vs theoretical, per component.
- `../JACK_IN_PLAYBOOK.md` (audit dir) — full per-mode procedure.
- `QUICKREF.md` — single-page printable.
- `docs/WARHACKER_DEMO.md`, `docs/KEY_CUSTODY_RUNBOOK.md` (PR#21), `warhacker/usb/DAY_OF_RUNBOOK.md`.
