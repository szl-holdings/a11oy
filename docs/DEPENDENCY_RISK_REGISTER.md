# Dependency Risk Register — a11oy

<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory) -->

This register records **every known-vulnerable dependency that cannot currently be
remediated by upgrading**, together with its reachability analysis and mitigation.

Doctrine: *honest UNKNOWN over fabricated green.* A vulnerability with no upstream
patch is recorded here as an **accepted, scoped risk with evidence** — it is never
silently suppressed, and this file never claims a vulnerability is "fixed" when it
is not.

Last audited: **2026-08-30** · Tool: `pip-audit` against the real dependency
closure (Dockerfile pins + `requirements.txt`).

---

## Open findings

### 1. `diskcache` 5.6.3 — CVE-2025-69872 / GHSA-w8v5-vhqr-4h9v / PYSEC-2026-2447

| Field | Value |
|---|---|
| Package | `diskcache==5.6.3` |
| Severity class | Arbitrary code execution (deserialization) |
| Upstream fix | **NONE AVAILABLE.** 5.6.3 is the latest release on PyPI; `fix_versions` is empty. |
| Introduced by | `llama-cpp-python==0.3.19` → `diskcache>=5.6.1` (transitive, not a direct dependency) |
| Status | **ACCEPTED — SCOPED. NOT FIXED.** |

**Description.** DiskCache through 5.6.3 uses Python `pickle` for serialization by
default. An attacker with **write access to the cache directory** can achieve
arbitrary code execution when a victim application reads from that cache.

**Reachability analysis (this is the mitigating control, and it is measured, not assumed):**

`llama-cpp-python` — and therefore `diskcache` — is **not installed on the default
build**. `Dockerfile` sets:

```dockerfile
ARG A11OY_REQUIRE_LOCAL_LLM=0
```

and gates the wheel install on it:

```dockerfile
if [ "${A11OY_REQUIRE_LOCAL_LLM}" != "1" ]; then
  # no llama.cpp wheel built/installed — demo tier serves the HONEST
  # tower-side label (served_locally=False, never fake output)
else
  pip install --no-cache-dir /wheels/*.whl
fi
```

Consequently:

| Deployment | `A11OY_REQUIRE_LOCAL_LLM` | `diskcache` present | CVE reachable |
|---|---|---|---|
| HF Space / demo tier (serves `a-11-oy.com`) | `0` (default) | **No** | **No** |
| Strict GHCR-published image | `1` | Yes | Yes, if cache dir is writable by an untrusted principal |

**Required mitigations on the `=1` path:**

1. The `diskcache` directory MUST NOT be writable by any principal other than the
   application user. In the container the app runs as a single non-root user and no
   other principal has write access to the cache path.
2. The cache directory MUST NOT be placed on a shared or network-mounted volume, and
   MUST NOT be placed under the HF Storage Bucket mount used for the receipt ledger.
3. Do not pass a user-controlled path as the llama.cpp cache location.

**Review trigger.** Re-check for an upstream release on every scheduled audit run. If
`diskcache` publishes a fixed version, remove this entry and pin forward in the same PR.
Do not let this entry expire silently — the audit workflow fails once the
`review_by` date passes without a re-attestation.

```
review_by: 2026-11-30
```

---

## What this register deliberately does NOT do

- It does not claim OpenSSF Scorecard `Vulnerabilities` will read 10/10. It will not,
  while an unpatched transitive CVE is present in the `=1` image. Reporting 10/10
  here would be exactly the fabricated green the doctrine forbids.
- It does not blanket-ignore vulnerability IDs. Each suppression is scoped to one ID,
  carries a reachability analysis, and has a review date.
- It does not assert that the demo tier is "secure"; it asserts the narrower,
  checkable claim that `diskcache` is **absent** from that build.

## Reproducing this audit

```bash
python -m pip install pip-audit
python -m pip_audit -r requirements-audit.txt --progress-spinner off
```

`requirements-audit.txt` is the consolidated closure (Dockerfile pins +
`requirements.txt`) so the audit covers what actually ships, not just the
partial `requirements.txt`. See `.github/workflows/dependency-audit.yml`.
