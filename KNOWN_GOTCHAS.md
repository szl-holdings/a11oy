# KNOWN_GOTCHAS.md — a11oy

> Things that have burned developers before. Read this before making changes.
> Doctrine v11 LOCKED · 749/14/163 · Λ = Conjecture 1.

---

## 1. GitHub ↔ HF Space drift (the silent footgun)

**What happens**: You push Python changes to GitHub `main`. CI goes green.
The HF Space (`SZLHOLDINGS/a11oy`) keeps running old code. No error, no alert.

**Why**: More than one automatically triggered workflow writing the same Space creates a race.
The later partial commit can supersede the complete Dockerfile-derived deployment,
leaving the application apparently healthy while immutable source attestation fails.

**Fix**: Keep `.github/workflows/hf-sync.yml` as the only automatic canonical
Space writer. It publishes the complete Dockerfile-derived set, binds the exact
GitHub SHA, waits for that immutable Space commit, and performs the live relock.
The `canonical HF single-writer guard` CI job rejects any competing automatic
writer. Check the Space API commit and `GET /api/build-info`; both must match the
release evidence before claiming relock.

**Promote path vs prod DNS**: `hf-sync.yml` publishes GitHub `main` → Space
`SZLHOLDINGS/a11oy`. Staging Space `szlholdings-a11oy.hf.space` ≠ prod DNS
`a-11-oy.com`. This repo does not change DNS. Keep Cloudflare orange-cloud
(proxied) on the apex. Stephen may add `_huggingface.a-11-oy.com` TXT later
**without** dropping that proxy. Do not grey-cloud (DNS-only) to make Hugging
Face report READY. HF custom domain stays PENDING/UNAVAILABLE in product.
Do not stamp LIVE. `www.a-11-oy.com` GET `/` is Cloudflare HTTP 404
(UNAVAILABLE until Cloudflare 301 www → apex). Do not add a second HF
custom domain. This repo does not change DNS. `x-szl-wire-d: LIVE` is
DSSE Wire D provenance, not domain LIVE.

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

**Current status**: SLSA L1 (source provenance documented). The GHCR image build
attaches SLSA L2 build-provenance attestation. L3 is NOT claimed (no hardened
isolated build pipeline).

Do not upgrade the SLSA badge to L2 or L3 without the infrastructure to back it.
The `/v1/honest` endpoint is the authoritative live source; the README badge must
match it.

---

## 9. Code execution, tools and agent/memory writes are operator-only (deny-by-default)

**Execution needs two server-held secrets**: `Authorization: Bearer <A11OY_CODE_ADMIN_KEY>`
plus a distinct `X-A11oy-Second-Approver: <A11OY_CODE_SECOND_APPROVER_KEY>` (the header is
in the CORS allow-list). Covered: `/api/a11oy/code/run`, `/api/a11oy/code/kernel/{run_id}/exec`,
`/api/a11oy/v1/agent/code/{compose,revise}`, and every sandbox reached through
`a11oy_code_engine.governed_turn` — `/api/<ns>/v1/code/{run,turn}`,
`/api/a11oy/v1/code/runstep`, `/api/a11oy/v1/agentloop/run` and
`/api/a11oy/v1/verify/transcript` (a GET never executes).

**Chokepoint:** `governed_turn(..., allow_exec=False)` reaches `_sandbox_exec` only when
`sandbox` and `allow_exec` are both true. Routes pass the header principal; `run_loop` and
`build_transcript` thread it through. Without it the turn still runs the gate and returns
`executed: false` with `execution_status` `NOT_EXECUTED — BLOCKED`, and no receipt claims
execution. A new caller that needs execution must pass `allow_exec=True` on purpose.

**Operator credential alone** covers tool calls (`run_tests` is state-changing, so it also
needs the second approver), RAG writes, profiles, conversation history, `/agent/run`,
`/agent/stream`, and the ReAct writes (`/api/a11oy/v1/agent/react/{run,resume,reflect,
memory/add,skills/admit}`). Anonymous `/chat/stream` still streams, without tools: it gets a
fresh conversation id, never reads stored history, and is never persisted. Agent turns use a
PURIQ gate bound to the header principal, so an anonymous turn cannot mint an `allow=true`
decision receipt. `POST /api/a11oy/code/v1/keys` answers `403` without the operator Bearer.
`szl_ken` `/mcp/call` two-person tools read the same headers, never the body.

**What `two_person_attested` means:** two distinct secrets arrived in one request. It is a
two-person control only if custody of the two keys is actually split between two people; it
is not cryptographic co-signing. Request bodies can never assert it. With a secret unset, the
matching role is held by nobody and the route answers `401 BLOCKED`.

**Kernel capacity:** at most `A11OY_MAX_KERNELS` persistent kernels (default 4; a malformed
value falls back to 4). At the cap, dead kernels and then the least-recently-used idle kernel
are evicted (its variables are lost); a kernel mid-cell is never evicted. Only when every slot
is executing does `/kernel/{run_id}/exec` answer `429 BLOCKED`, and nothing runs. A code-as-
action cell that finds no kernel is receipted `executed: false` with no energy-ledger entry.

The sandboxed child runs as the server UID, so it could read `/proc/<pid>/environ`; that is
why execution is not public. Container/microVM isolation stays ROADMAP.
Resolver: `szl_operator_auth.py` (governance/). Tests: `tests/test_operator_auth_code_routes.py`.

---

*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
*Doctrine v11 LOCKED · 749/14/163.*
