# Hugging Face Space consolidation — measured 2026-09-02

Status: **TERMINAL GREEN**

Execution: GitHub Actions run `33684002630` (`HF Space Consolidate Now`)

Authenticated SZLHOLDINGS inventory at completion: **52 Spaces**.

Result:
- **7 canonical public Spaces**, all observed `RUNNING` after the apply pass.
- **45 folded private Spaces**.
- Dynamic folded Spaces were paused where the Hugging Face runtime supports pause.
- Static folded Spaces remain private because static Spaces do not support pause.
- **0 execution errors**.
- **0 missing canonical keep targets**.
- **0 Spaces deleted**.

Canonical public fleet:
1. `SZLHOLDINGS/a11oy` — product command center
2. `SZLHOLDINGS/killinchu` — defense vertical
3. `SZLHOLDINGS/david-leads` — insurance vertical
4. `SZLHOLDINGS/anatomy` — living system map
5. `SZLHOLDINGS/immune` — safety kernel
6. `SZLHOLDINGS/szl-real-estate` — public-records underwriting
7. `SZLHOLDINGS/szl-atelier` — artifact walk

`SZLHOLDINGS/szl-real-estate` was private at the beginning of this execution and was restored to public while remaining `RUNNING`. The other six canonical targets were already public and `RUNNING`.

Immutable Actions artifact: `hf-space-consolidation-33684002630-1`

Artifact digest: `sha256:f2ad9b440ce463089717eb4b38701e652024d64fbad9f4eb159b2a483f291d92`

The operator is intentionally bounded: it does not delete Spaces and does not change accelerator, billing, secrets, or hardware settings. Source modernization of the seven canonical Spaces is a separate workstream from fleet consolidation; a Space being `RUNNING` is not treated as evidence that its UX/model/runtime is state of the art.
