# Warhacker Jack-In QUICKREF (print this, carry it)

**Founder directive 2026-05-30 16:46 EDT — real demo, no mocks, flex on the fly.**
Start: `./demo/jack-in.sh` (interactive) or `./demo/jack-in.sh <LETTER> --dry-run`.

> **One honesty line for the room:** "Vessels is deployed live as a signed UDS Zarf
> package and the Pepr receipts controller is active. Four more modules are real
> software, staged for the next release — the gap is module Zarf packaging (FA-001)."
> Never claim five modules boot together.

| DU gave me… | Run | Time | Config that changes |
|---|---|---|---|
| **A** kubectl to their UDS Core | `jack-in.sh A --kubeconfig <path>` | 2–4 min | `KUBECONFIG` |
| **B** vanilla k8s (no UDS Core) | `jack-in.sh B --kubeconfig <path>` | +10–15 min | `uds deploy` slim-dev / `-k overlays/k3s` |
| **C** SSH to air-gapped env | `jack-in.sh C --usb <usb>` | 5–8 min | `PLATFORM`, `PATH`→USB `bin/` |
| **D** OIDC issuer + client ID | `jack-in.sh D --oidc-issuer-url U --client-id ID` | 3–5 min | `SZL_COSIGN_OIDC_ISSUER`; CR `sso.clientId` |
| **E** private OCI registry | `jack-in.sh E --registry H:PORT` | 3–6 min | `--registry-url`; `server.image.repository` |
| **F** cosign SAN allowlist | `jack-in.sh F --sans "san1,san2"` | 1–2 min | `SZL_COSIGN_SAN_ALLOWLIST` |
| **G** OTel collector endpoint | `jack-in.sh G --otlp-endpoint U` | 2–3 min* | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| **H** Kafka/NATS bus | `jack-in.sh H` (DOC ONLY) | ~1 day | none — HTTP POST today |
| **I** IL5/FIPS crypto | `jack-in.sh I` (DOC ONLY) | 6–8 wks | none — Tier 0 today |
| **J** nothing (laptop) | `jack-in.sh J --usb <usb>` | 5–10 min | `.wslconfig` 24GB; `PLATFORM` |

\* Mode G is a real switch only if PR#19's receipts image is running; else say "no live spans."

**READY today (deployable for real):** A, C, F, J. **Config-tweak:** D, E. **PR-stage:** G (#19).
**Doc-only (not a switch):** H, I. **Default if DU gives nothing:** **J**.

**Always:** dry-run first. Empty SAN allowlist = deny everything (fail-closed, by design).
**FA-001:** only vessels has a real image; the other four `ImagePullBackOff` — that's expected.

Full detail: `JACK_IN_PLAYBOOK.md` · honest inventory: `REAL_DEMO_INVENTORY.md` ·
air-gap runbook: `warhacker/usb/DAY_OF_RUNBOOK.md` · hardware: `warhacker/HARDWARE_RECOMMENDATIONS_2026-05-30.md`.
