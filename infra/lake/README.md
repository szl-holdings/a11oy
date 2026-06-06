# SZL Holdings Data Lake — `szl-lake`

[![HF Dataset](https://img.shields.io/badge/HF%20Dataset-SZLHOLDINGS%2Fszl--lake-FFD21E?style=flat-square&logo=huggingface&logoColor=000)](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake)
[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED_749%2F14%2F163-d4a444?style=flat-square)](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17)
[![License](https://img.shields.io/badge/License-Apache--2.0_%7C_CC--BY--4.0-blue?style=flat-square)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276)

> **GitHub front door.** This repository holds the README, small JSON indexes, and manifest pointers. The **HF dataset is canonical** for all NDJSON receipts and large binaries:
> **[huggingface.co/datasets/SZLHOLDINGS/szl-lake](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake)**

The SZL Data Lake is the diligence-defensible corpus of governance receipts for SZL Holdings. Every governed action in the SZL substrate emits an ECDSA P-256 DSSE-signed **Khipu receipt** onto a hash-linked Merkle DAG. This dataset aggregates those receipts with formal-verification doctrine snapshots, the Zenodo paper record, SBOM pointers, and compliance attestations — so a reviewer can verify claims end-to-end.

**Doctrine v11 LOCKED · 749 declarations / 14 unique axioms / 163 tracked sorries · kernel commit [`c7c0ba17`](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17)**

---

## Lake Directories (7)

| Directory | Contents |
|---|---|
| `attestations/` | Section 889, SLSA level, CMMC L1 self-attestation |
| `doctrine/` | v11 snapshot (749 declarations · 14 axioms · 163 sorries) pinned to kernel commit `c7c0ba17` |
| `keys/` | ECDSA P-256 cosign public keys per flagship |
| `khipu/` | DSSE-signed Khipu receipts (Parquet / NDJSON, append-only) |
| `papers/` | Zenodo paper record references |
| `sboms/` | CycloneDX SBOM pointers |
| `trajectories/` | Bounded-recursion execution traces |

---

## How to verify

### 1 — Fetch receipts from HF (canonical source)

```bash
# Pull a Khipu receipt parquet
curl -fsSL \
  "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main/khipu/amaru_receipts.parquet" \
  -o amaru_receipts.parquet

# Or read directly with Python
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('hf://datasets/SZLHOLDINGS/szl-lake/khipu/amaru_receipts.parquet')
print(t.to_pandas().head())
"
```

### 2 — Verify DSSE signature

```bash
# Get the org-level cosign public key
curl -fsSL \
  "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main/keys/org-cosign.pub" \
  -o cosign.pub

# Verify a receipt blob
cosign verify-blob --key cosign.pub --signature <dsse_sig_field> <receipt-payload>
```

### 3 — Check doctrine snapshot

```bash
curl -fsSL \
  "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main/doctrine/manifest.json"
# Must show: "doctrine": "v11", "declarations": 749, "axioms": 14, "sorries": 163,
# "kernel_commit": "c7c0ba17"
```

---

## Cross-references

- **Formal proofs**: [lutar-lean](https://github.com/szl-holdings/lutar-lean) — Lean 4 kernel at commit [`c7c0ba17`](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17)
- **DOI**: [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)
- **Docs**: [docs.szlholdings.com/lake](https://docs.szlholdings.com/lake)
- **HF org**: [huggingface.co/SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS)

---

## Index

See [`lake_index.json`](lake_index.json) for the current pointer manifest (HF SHA, sync timestamp, directory list, doctrine constants). Auto-refreshed every 6 hours via the [sync workflow](.github/workflows/sync-from-hf.yml).

---

## License

Data: [CC-BY-4.0](LICENSE) · Code/tooling: Apache-2.0

<sub>Doctrine v11 LOCKED · 749 / 14 / 163 · Λ = Conjecture 1 (open, not a theorem) · SLSA L1 honest · Signed-off-by: Yachay (CTO) · Co-Authored-By: Perplexity Computer Agent</sub>
