# web/command-center — operational status

Measured 2026-09-04T23:12Z. Honesty doctrine v11.

This folder now contains a **live-probing operator pane** (`index.html`).
It is **not** a second flagship and does **not** replace the Python Space
runtime at a-11-oy.com.

## What is operational (MEASURED)

| Surface | URL | Note |
| --- | --- | --- |
| Product apex | https://a-11-oy.com | `server=szl` `x-szl-wire-d: LIVE` |
| Operator console | https://a-11-oy.com/console | existing Python Space UI |
| Elite command SPA | https://a-11-oy.com/command | existing |
| Verify | https://a-11-oy.com/verify | existing |
| Killinchu elite | https://szlholdings-killinchu.hf.space/elite | effector SIMULATED |
| Proof | https://a11oy.net | static |
| healthz | https://a-11-oy.com/healthz | ok · v11 · 749/14/163 · c7c0ba17 · signer ABSENT |
| Honest | https://a-11-oy.com/api/a11oy/v1/honest | LOCKED |
| Process ledger | https://a-11-oy.com/api/a11oy/v1/ledger | count=0 · mint false · UNSIGNED |
| Lake receipts | https://a-11-oy.com/api/lake/v1/receipts | ~100 · sha3_256 · energy UNAVAILABLE · payload MODELED |
| Mesh | https://a-11-oy.com/api/a11oy/v1/mesh/state | B/C/E/F LIVE · D LIVE_IN_PROCESS |
| Organs | https://a-11-oy.com/api/a11oy/v1/organs | 25 · per-organ evidence class |
| Killinchu ADS-B | https://szlholdings-killinchu.hf.space/api/killinchu/v1/adsb | LIVE community ADS-B |

## Pins that stay honest

- Λ uniqueness = Conjecture 1 (not a theorem, never 1.0)
- Apex signer ABSENT — do not say SIGNED
- Lake `payload.signed` is a modeled flag, not verified DSSE
- Killinchu public effector SIMULATED
- No FedRAMP / IL5 / ATO
- HTTP 200 is reachability, not a production certificate
- Do not flip a-11-oy.com DNS onto this folder
