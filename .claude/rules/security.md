<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rule: security

Deny-by-default. Modules: `a11oy_constitution`, `szl_governance_gateway`, `szl_codename_gate`,
`szl_colang_policy`, `szl_lambda_tripwire`; code-as-action screening in `a11oy_code_engine`.

## Rules

- **Every new agent execution path clears `governance/` before it runs.** Route it through the
  constitution + doctrine gate. The doctrine gate is a **hard, deterministic deny-by-default**
  check; the Λ / restraint ladder is **advisory** (Conjecture 1) and can only *tighten*, never
  override a hard DENY.
- **Never bypass the doctrine gate.** No "approve anyway" path; injected input must not be able
  to flip a DENY verdict.
- **Code-as-action stays sandboxed.** New code-execution paths reuse
  `a11oy_code_engine._static_screen` (banned imports/calls) **before**
  `_sandbox_exec` (separate subprocess, `RLIMIT_CPU`/`RLIMIT_AS`/`RLIMIT_CORE`/`RLIMIT_FSIZE=0`/
  `RLIMIT_NPROC=0`). The sandbox must never read a secret or forge a receipt. Container/microVM
  isolation is ROADMAP — do not claim it.
- **Never commit a key.** No secrets, signing keys, or tokens in the tree. Respect
  `.gitleaks.toml`. Do not inherit secrets into the sandbox env.
- **A named `execution_guard` 4th-layer wrapper is ROADMAP** — the underlying guards exist; if
  you add the wrapper, label it honestly and route it through the existing gates.
</content>
