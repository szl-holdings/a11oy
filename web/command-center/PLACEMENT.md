# Placement — do not invent a fourth origin

| Surface | Role | This package |
| --- | --- | --- |
| https://a-11-oy.com | Product origin. Command Center already lives at `/console` and `/command`. | Source of the Grok-built operator/estate UI. Not live on the apex until a human merges and cuts over. |
| https://a11oy.net | Proof / RECORD registry. Static. | Untouched. Never host this UI here. |
| https://huggingface.co/spaces/SZLHOLDINGS/a11oy | Existing Docker runtime of `szl-holdings/a11oy`. Port 7860. | KEEP. Do not replace this Space with the React app. |
| `szl-holdings/a11oy` @ `web/command-center/` | Inspectable source for this UI. | This folder. |

## Why not a new repo or a new Space

The org archives hologram repos and points them back at `a11oy`. A second flagship (`a11oy-console`) or a sixth pinned Space would be another hologram. This UI belongs inside the flagship source tree, beside the existing Alloy Fabric view in `web/`, not on top of it.

## What a merge does **not** do by itself

- Does not flip the `a-11-oy.com` CNAME.
- Does not rebuild `SZLHOLDINGS/a11oy`.
- Does not write to `a11oy.net`.
- Does not claim LIVE, SIGNED, SLSA L3, FedRAMP, or Λ-as-theorem.

Λ uniqueness remains Conjecture 1. Receipts from this surface are SHA-256 UNSIGNED-honest unless a separate signer probe is LIVE.
