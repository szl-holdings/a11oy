# Public Hub Space recapture — 2026-08-30

**State:** OBSERVED at `2026-08-30T13:20:28Z`. Public-only,
unauthenticated Hugging Face API measurement.
**Mutation:** none. No Space was deleted, paused, or made private by this repair.
**Product:** https://a-11-oy.com
**Hub:** https://huggingface.co/SZLHOLDINGS

This recapture follows the operator's no-private-scope instruction. It does not
reuse the authenticated private totals in the historical 2026-08-29 action
record and does not infer that an absent public Space was deleted.

## Canonical public set (6)

| Space | SDK | Observed Hub stage | Consolidated destination |
|---|---|---|---|
| `SZLHOLDINGS/a11oy` | Docker | `RUNNING` | `https://a-11-oy.com` |
| `SZLHOLDINGS/killinchu` | Docker | `RUNNING` | isolated `/elite` Space app |
| `SZLHOLDINGS/immune` | Docker | `RUNNING` | `https://a-11-oy.com/immune` |
| `SZLHOLDINGS/szl-khipu` | Docker | `RUNNING` | `https://a-11-oy.com/khipu` |
| `SZLHOLDINGS/governed-receipt-verifier` | Static | `RUNNING` | `https://a-11-oy.com/verify` |
| `SZLHOLDINGS/szl-atelier` | Static | `RUNNING` | `https://a-11-oy.com/atelier` |

The inventory source is the public author-list endpoint:
`https://huggingface.co/api/spaces?author=SZLHOLDINGS&limit=100&full=true`.
Provider stage was read from each Space's individual public API record. The
normal Docker hosts and correct `.static.hf.space` hosts were probed. A static
Space's `.hf.space` 404 is not an outage.

## Operational contract

`RUNNING` is provider lifecycle evidence, not a blanket operational claim. The
application health endpoint checks exact `/healthz` and `/readyz` JSON markers
for all four Docker Spaces, plus root reachability and Hub stage for all six.
The two static applications have real interactive pages; the governed verifier's
published source attestation remains `UNSIGNED_STRUCTURAL`.

The three names present in the 2026-08-29 public snapshot but absent here —
`david-leads`, `anatomy`, and `szl-real-estate` — remain legacy handoffs into
the product ecosystem. Their absence from the public API is not presented as
proof of deletion or private state.

## Honesty boundary

- Private inventory was not queried.
- No download/like count is treated as adoption.
- No HTTP 200 is treated as proof that every feature works.
- No trained-model claim follows from a runtime profile, RAG index, or receipt.
- Deployment is established only after the source revision is published and
  the public runtime reports that revision.
