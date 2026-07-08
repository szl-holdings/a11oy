<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
-->

# RUNTIME_ENV — canonical env / secret map (collision-proof)

**Why this file exists.** On **2026-07-08** the live a11oy HF Space
(`SZLHOLDINGS/a11oy` → https://a-11-oy.com) went **down**:

> `stage=CONFIG_ERROR, HTTP 503, errorMessage="Collision on variables and secrets names."`

That is a Hugging Face **Space *Settings*** fault, not a code bug: **HF forbids a
name from existing as BOTH a repo _Variable_ and a _Secret_ at the same time.**
When a name is duplicated across the two tabs, the Space refuses to boot. Only
the **founder** can fix it (devs cannot edit Space secrets).

This document is the **single canonical map** of every env name the app reads
that matters at boot, and — critically — **which tab each one belongs in**
(Secret vs Variable) so a name is **never configured in both**. It is mirrored
1:1 by the machine-readable registry in [`szl_boot_preflight.py`](../szl_boot_preflight.py)
and surfaced live at `GET /api/a11oy/v1/preflight` and in the `/api/a11oy/healthz`
rollup (`rollup.preflight`).

## The collision rule (read this before touching Space Settings)

1. **Each name below lives in exactly ONE tab.** A `secret` goes in
   Settings → **Secrets**; a `variable` goes in Settings → **Variables**.
2. **Never add the same name to both tabs.** That is the exact fault that 503'd
   the estate. If you must move a name between tabs, **delete it from the old tab
   first**, then add it to the new one.
3. **Secrets carry credentials** (API keys, tokens, private PEMs). **Variables
   carry non-sensitive config** (URLs, model names, ports, flags, public keys).
4. The code **degrades honestly** on a missing/renamed secret — the affected
   subsystem reports `DEGRADED` (or `UNAVAILABLE`), and the estate keeps serving.
   A missing secret is **never** allowed to crash the box. See *Boot resilience*.

## Boot resilience (what the code now guarantees)

- On boot, `serve.py` calls `szl_boot_preflight.run_preflight()` (guarded): it
  logs an **honest present/absent report of env NAMES** to stderr — **never a
  secret VALUE** — and computes per-subsystem readiness.
- A missing/renamed secret **DEGRADES** the affected subsystem; there are **no
  hard-required** secrets, so a totally empty env boots in honest `DEGRADED`
  mode rather than 503-ing.
- `GET /api/a11oy/healthz` stays **200** even on a bare env and surfaces
  `rollup.preflight` (per-subsystem `LIVE`/`DEGRADED`/`UNAVAILABLE`). An
  `UNAVAILABLE` preflight is the only preflight state that flips the overall
  health to `degraded` (a real fault an orchestrator should catch); an expected
  `DEGRADED` on a stock CPU Space does not.
- `GET /api/a11oy/v1/preflight` returns the full readiness + present/absent env
  **names** + this registry (**names only — no values**).
- The network-free CI gate [`test_boot_preflight.py`](../test_boot_preflight.py)
  (workflow `boot-preflight-selftest.yml`) asserts *missing-var → DEGRADED, not
  crash*, that `/healthz` stays 200 on a bare env, and that **no secret value
  ever leaks**. This gate is **added**, never weakening an existing gate.

## Canonical registry

Labels: **Kind** = which HF Settings tab (`secret` | `variable`); **Required** =
whether the *subsystem* is unavailable without it (never means "crash").

### billing

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `STRIPE_API_KEY` | secret | optional | Stripe secret key for joule billing. | (unset → subsystem DEGRADED) |
| `STRIPE_PRICE_PER_KWH_CENTS` | variable | optional | Pricing config in cents/kWh (non-secret). | (none / feature off) |

### brain

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | secret | optional | Anthropic Opus flagship key for the v3 Brain router. | (unset → subsystem DEGRADED) |
| `DEEPSEEK_API_KEY` | secret | optional | DeepSeek voter key. | (unset → subsystem DEGRADED) |
| `GEMINI_API_KEY` | secret | optional | Google Gemini voter key. | (unset → subsystem DEGRADED) |
| `GROQ_API_KEY` | secret | optional | Groq voter/provider key. | (unset → subsystem DEGRADED) |
| `MISTRAL_API_KEY` | secret | optional | Mistral voter key. | (unset → subsystem DEGRADED) |
| `OPENAI_API_KEY` | secret | optional | OpenAI voter/provider key. | (unset → subsystem DEGRADED) |
| `OPENROUTER_API_KEY` | secret | optional | OpenRouter voter/provider key. | (unset → subsystem DEGRADED) |
| `TOGETHER_API_KEY` | secret | optional | Together.ai voter key. | (unset → subsystem DEGRADED) |
| `VLLM_API_KEY` | secret | optional | Auth for a private vLLM endpoint. | (unset → subsystem DEGRADED) |
| `A11OY_BRAIN_URL` | variable | optional | Central Brain hub pulse URL (falls back to shipped organs). | (none / feature off) |
| `A11OY_LOCAL_MODEL` | variable | optional | Local model identifier for the sovereign path. | (none / feature off) |
| `A11OY_MODEL_BASE_URL` | variable | optional | Base URL for the hosted model router. | (none / feature off) |
| `HF_ROUTER_BASE` | variable | optional | HF Inference router base URL. | (none / feature off) |

### core

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `A11OY_CORS_EXTRA_ORIGINS` | variable | optional | Comma-list of extra CORS origins (additive to the allowlist). | (none) |
| `PORT` | variable | optional | HTTP listen port (HF injects 7860). | 7860 |
| `SPACE_COMMIT_SHA` | variable | optional | HF Space commit sha, surfaced at /healthz for drift detection. | (unset) |
| `SZL_BUILD_TIME` | variable | optional | Image build timestamp. | unknown |
| `SZL_GIT_SHA` | variable | optional | Deployed GitHub commit sha (build-arg / Space variable). | unknown |

### energy

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `A11OY_GPU_TOKEN` | secret | optional | Bearer token for the sovereign GPU node(s). Absent => joules are honest SAMPLE, never MEASURED. | (unset → subsystem DEGRADED) |
| `A11OY_ENERGY_OMEN_ENABLED` | variable | optional | Runbook alias: 1 flips OMEN live when STANDBY unset. | 0 |
| `A11OY_JOULE_METER_URL` | variable | optional | URL of a joule meter (energy MEASURED path). | (none / feature off) |
| `A11OY_OMEN_BASE_URL` | variable | optional | OMEN GPU-lung base URL (energy MEASURED path). | (none / feature off) |
| `A11OY_OMEN_STANDBY` | variable | optional | 1 => OMEN standby (default); 0 => live lung. | 1 |
| `SZL_ENERGY_LEDGER_PATH` | variable | optional | Persistent path for the energy/receipt ledger; ephemeral if unset. | (none / feature off) |

### feeds

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `ELECTRICITY_MAPS_API_KEY` | secret | optional | Electricity Maps grid-carbon key (carbon stays ROADMAP w/o it). | (unset → subsystem DEGRADED) |
| `GITHUB_TOKEN` | secret | optional | GitHub API token for live repo/citation feeds. | (unset → subsystem DEGRADED) |
| `NVD_API_KEY` | secret | optional | NIST NVD CVE feed key (higher rate limit). | (unset → subsystem DEGRADED) |
| `POLYGON_API_KEY` | secret | optional | Polygon markets key. | (unset → subsystem DEGRADED) |
| `SZL_FRED_API_KEY` | secret | optional | FRED economic-data key. | (unset → subsystem DEGRADED) |

### hf-hub

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `HF_ROUTER_TOKEN` | secret | optional | Token for the HF Inference router (voter proxy). | (unset → subsystem DEGRADED) |
| `HF_TOKEN` | secret | optional | HuggingFace Hub token (corpus bucket read/write, router proxy). | (unset → subsystem DEGRADED) |

### signing

| Env name | Kind | Required | Purpose | Honest default |
|---|---|---|---|---|
| `SZL_COSIGN_PRIVATE_PEM` | secret | optional | DSSE/cosign ECDSA-P256 PRIVATE key PEM. Absent => UNSIGNED-LOCAL receipts (honest), never a fabricated signature. | (unset → subsystem DEGRADED) |
| `COSIGN_KEYID` | variable | optional | Key identifier surfaced in verify receipts (non-secret). | (none / feature off) |
| `COSIGN_PUBLIC_PEM` | variable | optional | DSSE cosign PUBLIC key PEM (safe to expose; verification only). | (none / feature off) |

## Quick reference — tab assignment

Configure these in HF Space Settings → **Secrets** (credentials, never in Variables):

```
A11OY_GPU_TOKEN
ANTHROPIC_API_KEY
DEEPSEEK_API_KEY
ELECTRICITY_MAPS_API_KEY
GEMINI_API_KEY
GITHUB_TOKEN
GROQ_API_KEY
HF_ROUTER_TOKEN
HF_TOKEN
MISTRAL_API_KEY
NVD_API_KEY
OPENAI_API_KEY
OPENROUTER_API_KEY
POLYGON_API_KEY
STRIPE_API_KEY
SZL_COSIGN_PRIVATE_PEM
SZL_FRED_API_KEY
TOGETHER_API_KEY
VLLM_API_KEY
```

Configure these in HF Space Settings → **Variables** (non-sensitive, never in Secrets):

```
A11OY_BRAIN_URL
A11OY_CORS_EXTRA_ORIGINS
A11OY_ENERGY_OMEN_ENABLED
A11OY_JOULE_METER_URL
A11OY_LOCAL_MODEL
A11OY_MODEL_BASE_URL
A11OY_OMEN_BASE_URL
A11OY_OMEN_STANDBY
COSIGN_KEYID
COSIGN_PUBLIC_PEM
HF_ROUTER_BASE
PORT
SPACE_COMMIT_SHA
STRIPE_PRICE_PER_KWH_CENTS
SZL_BUILD_TIME
SZL_ENERGY_LEDGER_PATH
SZL_GIT_SHA
```

> **Founder unblock for the 2026-07-08 outage:** in HF Space Settings, find the
> name that appears in **both** the Variables and Secrets tabs, decide its
> canonical home from the tables above (credential → Secret, config → Variable),
> and **remove the duplicate from the other tab**. The Space will boot cleanly;
> `/api/a11oy/v1/preflight` will then show the subsystem `LIVE`.

## Honest scope

This registry covers the **boot-critical** env names read by `serve.py` and the
core `szl_*` subsystems. Additional module-local env vars exist (feature flags,
timeouts, probe intervals) and are read defensively with honest defaults by
their owning modules; they are not collision-risk credentials and are out of
scope here. When you add a **new** credential or a boot-critical variable, add it
to `szl_boot_preflight._REGISTRY` (the self-test enforces one-kind-per-name) and
it will appear here and at `/api/a11oy/v1/preflight` automatically.
