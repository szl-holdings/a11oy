# Consolidation: a11oy is the platform home

Per CEO directive, **a11oy** (`github.com/szl-holdings/a11oy`) is the TRUE consolidated
home of the SZL platform. This repository ingests the real source of the other organs
and shared infrastructure so that a11oy is self-contained — not merely a UI that calls
remote services.

## What lives where

- **`organs/sentra/`** — ingested source of the **policy** organ (Sentra). Includes
  `serve.py`, `console/`, `src/`, `szl_shared_formulas/`, and web/runtime source.
- **`organs/amaru/`** — ingested source of the **reasoning** organ (Amaru). Includes
  `serve.py`, `amaru_cortex_console.py`, `amaru_proof_tabs.py`,
  `amaru_formula_endpoints.py`, `sidecar/`, and `src/amaru/`.
- **Rosie (operator) — no `organs/rosie/` ingest.** Rosie has **no** ingested source
  tree in this repo; its runtime is served **in-process** by the root-level
  `szl_rosie_companion.py`. The organ-source ingest under `organs/` is **amaru + sentra
  only**; a standalone Rosie source ingest is pending.
- **`mcp/`** — shared **MCP** (Model Context Protocol) infra: `mcp_server.py`,
  `test_mcp_stdio.py`, MCP client config, and integration docs.
- **`infra/`** — pointer READMEs to the canonical szl-holdings repos. Full external
  repo sources are **not** vendored here (they silently drifted from canonical);
  reference the canonical repo each `infra/<name>/README.md` links to instead.
  The shared **vsp-otel** OpenTelemetry middleware lives at
  `github.com/szl-holdings/vsp-otel`; a11oy's own importable copy is the
  root-level `vsp_otel/` package (left intact).

a11oy's own existing files (`serve.py`, `pages/`, `vsp_otel/`, top-level `szl_*.py`,
etc.) are left intact. The ingested organ source is added strictly under the new
top-level directories listed above.

## Honest status (no overclaiming)

- This is a **source-only ingest** for consolidation. The organ code has been copied
  into a11oy; it has **NOT** yet been merged into a single runtime or wired together.
  The commit is *"ingest organ source for consolidation"*, not *"merged and wired"*.
- The **live Hugging Face Spaces** for sentra, amaru, and rosie currently run as
  backends that a11oy's UI calls. They remain the live backends for now and will be
  **retired only after** their endpoints are ported into the consolidated a11oy
  runtime. They are not touched by this ingest.
- Build artifacts, vendored dependencies, and large binaries were **not** ingested
  (see `team/INGEST_REPORT.md` for skip rules and counts).

## Doctrine (unchanged, kept honest)

- **Λ-uniqueness = Conjecture 1** (machine-checked FALSE unconditionally; a conjecture, NOT a proven theorem). Khipu BFT = Conjecture 2.
- **8 locked-proven formulas** {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel `c7c0ba17` (749 declarations / 14 unique axioms / 163 sorries). Source of truth: the in-repo `DOCTRINE_LOCK` (`locked_formula_count: 8`, `szl_be_hardening.py`) + the kernel measurement at `proofs/lutar-lean/.github/data/lean_numbers.json`, pinned to `lutar-lean@c7c0ba17`.
- Supply-chain posture: **SLSA L1 honest** (L2 attested only on the a11oy/killinchu container images; L3/FedRAMP/Iron Bank/CMMC = roadmap, not claimed).
- Honesty doctrine **v11** — never overclaim.

— Stephen P. Lutar Jr. · SZL Holdings
