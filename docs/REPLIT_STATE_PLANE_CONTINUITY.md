# Replit and public-host state-plane continuity

This note prevents three independently managed surfaces from being collapsed
into one claim:

1. `a-11-oy.com` is the public product and API plane.
2. `a11oy.net` is the public GitHub Pages presentation plane owned by
   `szl-holdings/a11oy-net`.
3. Replit `Unified Control Hub` is a candidate authenticated control plane. It
   does not own `a11oy.net` and is not operationally verified by this checkout.

The auditable snapshot is
[`state-plane-continuity.v1.json`](state-plane-continuity.v1.json). Validate it
with:

```text
python scripts/validate_state_plane_continuity.py
```

## Reconciliation result

### Anatomy substrate v6

Anatomy v6 is not merely a Replit conversation claim. The source ratchet is on
the `szl-holdings/anatomy` default branch at commit
`c4bc67a4a0da76ca78eee2598618ab001eed1189`; the visible workflows for that
commit completed successfully, and the public Anatomy Space serves the v6
module plus its capability, evidence, and receipt routes.

The live `v6_alive.js` is an exact byte match to GitHub main: 13,405 bytes,
SHA-256
`65ee3306ff732d4d977ecec5014431e832c599900459c7016593d1f84010d380`.

The latest public harness envelope was also independently replayed against the
pinned `szlholdings-ec-p256` public key. Its DSSE signature verified and its
payload reports `GREEN`, `32/32` assertions, and `10/10` formula gates, finished
at `2026-07-21T03:40:29.453969Z`. This proves the integrity and signer identity
of that published harness record; it does not prove every depicted capability.

This is still not provenance-closed. The Space's live
`/.well-known/szl-source.json` response reports `PENDING_GITHUB_SYNC`, with a
declared source commit that differs from current GitHub main. The correct label
is therefore **MEASURED live with source alignment open**, not `PROVEN`.

### Unified Control Hub

The selected Replit app is `Unified Control Hub` (repl
`34870515-2d52-4ad8-9636-40cc3ced1771`) and the selected task is
`a1181f86-210d-4e5b-a612-a94c271366a7`. The task UI showed task 26 as complete,
but the authorized connector returned no inspection detail. No matching local
export, Git remote, branch, commit, preview receipt, or deployment receipt was
found in this workspace.

Consequently, the proposed rebuilt operational control plane remains
**OPEN / UNVERIFIED**. It can be promoted only after all of these exist:

- exact repository, branch, and immutable commit;
- a distinct Replit preview or deployment origin;
- test and build receipts bound to that commit;
- independent liveness/readiness and critical-flow probes;
- a reviewed integration record that preserves the public Pages owner.

### a11oy.net

`https://a11oy.net` returned HTTP 200 from GitHub Pages during this audit. It is
a presentation site, not the old Replit API. No Replit task may overwrite,
redirect, or claim ownership of that host without a separate reviewed migration.

The app-level `a11oy_canonical_domain.py` redirect applies only when an
`a11oy.net` Host header is routed into the a11oy application. It does not change
DNS or the independently hosted GitHub Pages site.

## Promotion rule

`TASK_COMPLETE != MERGED != DEPLOYED != LIVE_VERIFIED`.

Every plane needs its own source identity and runtime receipt. A successful
Anatomy deployment does not prove the Replit control plane, and a reachable
Pages site does not prove an API.
