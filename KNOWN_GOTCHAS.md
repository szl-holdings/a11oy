# KNOWN_GOTCHAS.md — a11oy

> Things that have burned developers before. Read this before making changes.
> Doctrine v11 LOCKED · 749/14/163 · Λ = Conjecture 1.

---

## 1. GitHub ↔ HF Space drift (the silent footgun)

**What happens**: You push Python changes to GitHub `main`. CI goes green.
The HF Space (`SZLHOLDINGS/a11oy`) keeps running old code. No error, no alert.

**Why**: `hf-sync.yml` only syncs `README.md`. The Space runs a Docker image
from GHCR. Application code only reaches the Space when:
(a) the GHCR image is rebuilt (`ghcr-build-push.yml`) AND
(b) the Space's `Dockerfile` or Space config is updated to reference the new tag.

**Fix**: After merging a Python change, trigger `ghcr-build-push.yml` manually
and confirm the Space restarts with the new image. Check `GET /api/a11oy/healthz`
— the response includes the git commit.

---

## 2. Dockerfile per-file COPY discipline — missing module = silent 404

**What happens**: You add a new Python module (e.g. `my_feature.py`), push it to
GitHub, rebuild the image — but routes silently fall through to the SPA catch-all
returning HTML 200 instead of JSON. No import error appears in the logs.

**Why**: The Dockerfile uses per-file `COPY` (no `COPY . .`). A module that is not
explicitly `COPY`-ed into the image is absent at runtime. FastAPI's startup import
of that module fails, the try/except swallows the error (logged to stderr, not
surfaced as a crash), and the route never registers.

**Fix**: For every new `.py` file you add, add a corresponding line in the
Dockerfile:
```dockerfile
COPY my_feature.py /app/my_feature.py
```
Then check the Space startup logs for `[a11oy] BE hardening NOT registered:`
style warnings after each deploy.

---

## 3. `from __future__ import annotations` + FastAPI Pydantic models

**What happens**: A Pydantic model with `from __future__ import annotations` at
the top of the file causes FastAPI's dependency injection or response model
validation to fail at runtime with a cryptic `TypeError` or `NameError`, even
though the code looks correct.

**Why**: `from __future__ import annotations` makes all type annotations lazy
strings (PEP 563). FastAPI/Pydantic needs to evaluate them at class creation time.
In Python 3.10+ with Pydantic v1 this silently breaks certain model patterns.

**Fix**: Do not use `from __future__ import annotations` in any file that defines
FastAPI route handlers or Pydantic models with complex generics. If you need it
for the type checker, move the Pydantic models to a separate file that doesn't
have the import.

This affects: `serve.py`, any file ending in `_routes.py` or `_endpoints.py`.

---

## 4. Shallow clone wipe risk

**What happens**: Running `git clone --depth 1` and then pushing back to `main`
can corrupt the branch history or silently lose commits that other workflows
depend on (e.g. the `slsa-provenance.yml` which needs the full commit graph).

**Rule**: ALWAYS use a full clone (`git clone` with no `--depth` flag) before
any operation that writes to the repo. The CI safety check is:
```bash
git ls-files | wc -l   # should be ~1061 for a11oy
```
If the count is < 50, you have a shallow or partial checkout. Stop.

---

## 5. DSSE receipt signatures are PLACEHOLDER until CI signing is wired

**Status**: The `szl_dsse.py` module produces real ECDSA-P256-SHA256 signatures
when `SZL_COSIGN_PRIVATE_KEY_PEM` is present in the environment. In the live HF
Space, this secret IS set (the SZLHOLDINGS demo keypair). In local dev without
the secret, receipts carry `"sig": "PLACEHOLDER — Sigstore CI signing not yet wired"`.

**Honest label**: This is intentional and documented in `szl_dsse.py`. Do not
replace the placeholder with a fabricated signature. The `/v1/honest` endpoint
discloses the signing status.

**For local testing**: Generate a test keypair with `cosign generate-key-pair` and
set `SZL_COSIGN_PRIVATE_KEY_PEM` in your shell. The public key in `szl_dsse.py`
is the org-level key; for local dev you can set `SZL_COSIGN_PUB_SHA256` to skip
the fingerprint pin check.

---

## 6. Lambda (Λ) is a Conjecture, NOT a proven theorem

**What happens**: A developer reads the codebase, sees "Λ uniqueness", and assumes
it is a closed mathematical result. They write docs or code comments saying Λ is
"proven". Doctrine audit catches it and requires a PR revert.

**Facts**: Λ (Lambda-Aggregator Uniqueness) is labeled **Conjecture 1** throughout
the codebase. It depends on an open `CAUCHY_ND` sorry in `Lutar/Uniqueness.lean:120`
and a missing symmetry axiom. It is not closed. Every surface mentioning Λ
uniqueness must say "Conjecture", never "Theorem" or "proven".

The canonical check: `GET /api/a11oy/v1/honest` returns
`"lambda_status": "conjecture"` — use this to verify in CI.

---

## 7. Doctrine numbers are frozen until the next version bump

**The locked numbers**: `749 declarations / 14 unique axioms / 163 sorries / c7c0ba17`

Do not bump these numbers in comments, README, or code without:
1. A genuine new Lean kernel build that changes the numbers.
2. A doctrine version bump (v11 → v12) with a full cross-repo update.
3. CTO approval.

The `doctrine-grep.yml` CI workflow fails PRs that introduce conflicting numbers.

---

## 8. SLSA level honest disclosure

**Current status**: SLSA L1 honest — the GHCR image is cosign-signed keyless and
verifiable via `cosign verify`. The build workflow contains an
`actions/attest-build-provenance@v2` step, but it has NOT yet produced a
verifiable attestation on the deployed image: `cosign verify-attestation
--type slsaprovenance ghcr.io/szl-holdings/a11oy:uds-v0.2.0` currently returns
"no matching attestations". So **L2 is NOT yet earned** (roadmap via Wire D; the
likely blocker is org-level `attestations: write`, a founder action). L3 is NOT
claimed (no hardened isolated build pipeline).

Do not upgrade the SLSA badge to L2 or L3 until `cosign verify-attestation`
actually returns the attestation on the deployed image. The `/v1/honest` endpoint
is the authoritative live source; the README badge must match it.

---

*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
*Doctrine v11 LOCKED · 749/14/163.*
