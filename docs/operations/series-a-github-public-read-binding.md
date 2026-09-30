<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Series-A installed signing authority and optional GitHub public reader

## Founder decision record

- Date: 2026-09-30
- Decision maker: Stephen Lutar, CEO, SZL Holdings
- Recorded instruction: "you are the CTO, I want it all"
- Decision: the canonical deploy stops holding on an unknown-authority state
  that no automated consumer could ever clear. It now proves one exact
  fact: the installed signing key matches the pinned runtime key. The
  GitHub public-read token becomes optional.

## Required and optional Space secrets

For the exact canonical Space `SZLHOLDINGS/a11oy`:

| Name | Status | Check |
| --- | --- | --- |
| `SZL_COSIGN_PRIVATE_PEM` | required | live public key must match the pinned runtime key |
| `GDW_CREDENTIALS_JSON` | required | name must be present; the downstream GDW live proof validates it at runtime |
| `A11OY_GITHUB_PUBLIC_READ_TOKEN` | optional | never blocking; if absent, the inventory runs `PUBLIC_ANONYMOUS` |

None of these names may appear as public Space variables. If one does, the
check reports `PUBLIC_VARIABLE_COLLISION` and blocks. The publisher still must
not forward `DOCS_AUTOMATION_TEAM_READ_TOKEN`, the workflow `github.token`, a
personal CLI credential or `GDW_OPERATOR_TOKEN` into Space secrets. It also
must not derive a replacement registry or delete `GDW_PRINCIPALS_JSON`. A
legacy principal registry still needs the owner to resolve it, and existing
credentials and principals are preserved.

## Verifier design

`scripts/verify_installed_authority.py` is stdlib-only, plus `cryptography`,
which it uses to parse the public key.

1. It fetches `GET <CANONICAL_ORIGIN>/cosign.pub`. Only the exact origin
   `https://szlholdings-a11oy.hf.space` is accepted. The fetch does not follow
   redirects, has a timeout and caps the body at 4 KiB. Any non-200 status,
   redirect, timeout, transport error, empty body or oversized body yields
   `ORIGIN_UNAVAILABLE`, reported as `credential_authority_state: UNKNOWN`.
   That state never counts as verified.
2. It parses the served key as a P-256 SubjectPublicKeyInfo and takes the
   SHA-256 of its DER encoding.
3. It compares that fingerprint with two independent pins. Both must agree:
   - the repository file `ayllu/keys/council-runtime-2026-07-21.pub`, which
     was recovered from two live council signatures (see `ayllu/keys/README.md`)
   - the hardcoded fingerprint
     `8e2d106c6995e11dbf7cbedfa9e5800bb50c82a635756e40dcd330364f6ea8ba`
   If the pin file and the hardcoded fingerprint disagree, or the pin file is
   missing, malformed or equal to the static fallback key, the check fails
   closed as `SIGNING_KEY_MISMATCH` / `PINNED_KEY_INCONSISTENT`.
4. It reads the static fallback key `szl_dsse.COSIGN_PUBLIC_PEM` from source
   with `ast`; the module is never imported. If the runtime serves this key,
   the installed private key is absent: `SIGNING_KEY_NOT_INSTALLED`.
5. Any other key, including an ephemeral per-boot key, is reported as
   `SIGNING_KEY_MISMATCH`.
6. It reads the `git_sha` from `/api/a11oy/v1/honest` for information only.
   This value never grants authority.

Both `configure_hf_series_a_runtime.py --check-only` and
`configure_hf_gdw_runtime.py --check-only` read secret names only, never
values. They then call the verifier. They report `state: READY`,
`credential_authority_state: VERIFIED`, `converged: true` and exit 0 only when
all of the following hold:

- the signing key is `VERIFIED_PINNED_RUNTIME_KEY`
- the required names are present
- there is no public-variable collision
- the storage and mount checks pass

`check_hf_manual_prerequisites.py` accepts a READY report only with exit code
0, a strict schema and the pinned fingerprints echoed back. The aggregate
summary is `READY` only when both reports are READY and the source SHA is
valid. A forged `PASS`, a boolean exit code, duplicate fields and oversized
reports all stay `SETUP_REQUIRED`. Ordinary (non-check-only) configuration now
proceeds only after the same verified result.

## What this proves (measured)

At observation time, the key the live runtime derives and serves from its
installed signing material has the same public key as the pinned council
runtime key. Serving the pinned key requires the installed private key to
derive it, unless the runtime is hostile (see below). A live run on
2026-09-30 measured `VERIFIED_PINNED_RUNTIME_KEY`, served-key DER SHA-256
`8e2d106c…6f4ea8ba`.

## What this does not prove

- **No proof of private-key possession.** There is no fresh challenge
  signature, so a hostile or modified runtime could serve a copied public key
  without holding the private key. This risk is mitigated, not eliminated, by
  the single-writer guard (`tests/test_hf_single_writer.py`), exact-source and
  default-branch-tip admission, drift, security and live-proof jobs, all of
  which remain unchanged. A signed challenge endpoint would close the gap;
  that is future work and needs its own review.
- **GDW credentials are checked by name only here.** Their runtime validity is
  measured later by the GDW live proof, not by this check.
- **The GitHub reader's value is never verified.** Without the token the
  inventory is `PUBLIC_ANONYMOUS` (public repositories and PRs only; no
  private organization completeness). A rejected token stays `UNAVAILABLE`,
  with no anonymous retry.
- This check does not show hosted readiness, successful deployment or any
  Series-A outcome. Where no measurement exists, reports say unavailable
  rather than modeled. Λ remains Conjecture 1. Nothing outside the locked-8
  proofs is described as proven.

## Unchanged boundaries

- Source-ownership, exact-head, drift, single-writer, security and live-proof
  jobs are not weakened.
- The `--blocked-proof` restart and GDW proof entrypoints still fail closed
  before any credential reads.
- Evidence belongs in Actions artifacts and summaries. Issue #1043 is not
  edited, closed, reopened or commented on.

Local check (public, no secrets):
`python scripts/verify_installed_authority.py` exits 0 only on
`VERIFIED_PINNED_RUNTIME_KEY`.
