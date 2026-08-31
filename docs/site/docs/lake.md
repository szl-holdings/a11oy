# Data Lake

The **SZL Data Lake** is the diligence-defensible corpus of governance receipts.

- **GitHub front door**: <https://github.com/szl-holdings/szl-lake>
- **HF dataset (canonical)**: <https://huggingface.co/datasets/SZLHOLDINGS/szl-lake>
- **DOI**: [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)

## Contents

- `attestations/` — Section 889, SLSA level, CMMC L1 self-attestation
- `doctrine/` — v11 snapshot (749 declarations · 14 axioms · 163 sorries) pinned to kernel commit `c7c0ba17`
- `keys/` — ECDSA P-256 cosign public keys per flagship
- `khipu/` — DSSE-signed receipts (NDJSON / Parquet, append-only)
- `papers/` — Zenodo paper record references
- `sboms/` — CycloneDX SBOM pointers
- `trajectories/` — Bounded-recursion execution traces

## Cross-references

- [Formal proofs (lutar-lean)](https://github.com/szl-holdings/lutar-lean)
- [Doctrine kernel commit `c7c0ba17`](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17)
