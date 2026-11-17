# Evidence

<!-- ARCHIVED-THESIS-NOTICE -->
> **⚠️ Archived thesis notice.** The `szl-holdings/ouroboros-thesis` repository has been retired; the Ouroboros Thesis is now archived at Zenodo DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276). Any `ouroboros-thesis` references below are **historical and not live**.

Every claim on this site is meant to be checked. This page is the evidence index: the DOIs,
commit anchors, Lean kernel, thesis PDFs, evaluation results, and example receipts that back
the [flagships](/flagships/), the [anatomy](/anatomy/), and the [doctrine](/doctrine/v11-v12).

## Single source of truth

Per Doctrine v11: **the README of each repo on `main` HEAD is the source of truth**, and you
must regenerate any number before citing it. Reproduce the canonical Lean figures:

```bash
gh repo clone szl-holdings/lutar-lean /tmp/lutar -- --depth 1
cd /tmp/lutar
git rev-parse HEAD
python .github/scripts/lean_numbers.py --repo-path . --out lean_numbers.current.json
cat lean_numbers.current.json
```

| Snapshot | Declarations | Unique axioms | Sorries | Anchor |
|----------|-------------|---------------|---------|--------|
| **v11 LOCKED (contract)** | <span class="locked">749</span> | <span class="locked">14</span> | <span class="locked">163</span> | tag `lutar-v18.0.0` / `c7c0ba17` |
| Historical authority snapshot (2026-05-31T11:00:00Z) | 749 | 14 | 163 (112 baseline + 51 Putnam) | `c7c0ba17` / `lean_numbers.json` |

The locked figures describe the doctrine baseline. The dated authority snapshot
does **not** establish current `main` HEAD counts. Cite a regenerated census with
its exact commit, scope, and counting method for a current claim.
Source: [immutable `lean_numbers.json`](https://github.com/szl-holdings/.github/blob/5cd00651972728f0264ac6348d3a8bf30749fcc0/.github/data/lean_numbers.json).
The eight locked-proven formulas remain `{F1,F4,F7,F11,F12,F18,F19,F22}`;
Lambda uniqueness remains Conjecture 1.

## Lean kernel

- **Kernel:** [`szl-holdings/lutar-lean`](https://github.com/szl-holdings/lutar-lean) — the
  machine-checked proof corpus (`Lutar/`).
- **Key files:** `Lutar/Axioms.lean` (A1–A4), `Lutar/Khipu/SummationInvariant.lean`,
  `Lutar/QEC/KitaevSurface`, `Lutar/DPI/DPIBound.lean` (Pinsker), `Lutar/Egyptian/AkhmimTable.lean`.
- **PURIQ obligations:** `formulas/PuriqLean.lean` — `puriq_halting_safety`,
  `puriq_lambda_monotone`, `puriq_khipu_integrity`, `puriq_bekenstein_bound` (all `sorry`-tagged).
- **Putnam:** **0/12 PROVED** at canonical `lutar-lean@baf483be3c832b64da47161b558e283d68da6650`; 10 DEMO and 2 OPEN. The pinned `lake build PutnamSet` job and `scripts/check_putnam_drift.py` gate this generated tally.

## Zenodo DOIs

The Ouroboros Thesis and supporting artifacts are deposited on Zenodo with persistent DOIs.

| DOI | Role |
|-----|------|
| [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) | **Ouroboros Thesis v18.0** (versioned) — cited by every flagship |
| [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) | **Concept DOI** (always-latest) |
| [10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308) | Supporting artifact |
| [10.5281/zenodo.20431181](https://doi.org/10.5281/zenodo.20431181) | Supporting artifact |
| [10.5281/zenodo.20195368](https://doi.org/10.5281/zenodo.20195368) · [20173920](https://doi.org/10.5281/zenodo.20173920) · [20162352](https://doi.org/10.5281/zenodo.20162352) | Versioned deposits |
| [10.5281/zenodo.19867281](https://doi.org/10.5281/zenodo.19867281) · [19934129](https://doi.org/10.5281/zenodo.19934129) · [19983066](https://doi.org/10.5281/zenodo.19983066) | Earlier versioned deposits |

A complete, versioned list is maintained in the thesis repository's `CITATION.cff`.

## GitHub commit anchors

| Anchor | Meaning |
|--------|---------|
| `lutar-v18.0.0` / `c7c0ba17` | Doctrine v11 LOCKED Lean snapshot (749/14/163) |
| `3de37e5` | Historical alternate 752/160 claim; not the authority manifest or a current census |
| `85de269` | lutar-lean `main` HEAD at 2026-05-30 verification |
| rosie PR #6 | CSS ingress + QEC lineage (v17) |

## Thesis PDFs (v18–v20)

The Ouroboros Thesis is the mathematical spine. Source and built PDFs live in
`szl-holdings/ouroboros-thesis` under
`papers/`. v18.0 corresponds to the versioned DOI above; v19/v20 are the active
revision line.

::: info In development
The public PDF mirror for **v18–v20** on this docs site is in development. Until it publishes,
fetch the built PDFs directly from the thesis repository's `papers/` directory (each version is
tagged) or from the Zenodo deposit.
:::

## Ouroboros evaluation results

The Ouroboros self-evaluation harness (`OUROBOROS_RUN_ALL`) exercises the governed loop
end-to-end and emits a self-test log. Results and the doctrine self-grade are published in the
thesis repo under `docs/audit/doctrine-pass-results.md`.
The self-grade artifact lives at `papers/v13/self_grade.md` in the ouroboros-thesis repo
(note: v13 here is the thesis paper version number, unrelated to governance versioning).
The Putnam suite is **0/12 PROVED**; its DEMO/OPEN files are not promoted to proof claims.

## Khipu receipt examples

A Khipu receipt is the atomic unit of provenance. The structure (from
[rosie](/flagships/rosie)):

```json
{
  "decisionId": "d-001",
  "value": 1,
  "organ": "a11oy.policy",
  "sha256": "<sha256 over canonical sort_keys JSON>",
  "prevRoot": "<previous chain root>",
  "lamport": 42,
  "signature": "DSSE-PLACEHOLDER",
  "chain_verified": true
}
```

The receipt rule is `packet → json.dumps(sort_keys=True) → sha256 → hexdigest → append`. The
summation invariant `rootValue = Σ pendantValues = Σ Σ decisionValues` is verified at runtime
(rosie's 10 tests) and formally in `Lutar/Khipu/SummationInvariant.lean`.

::: warning Honest signature status
The `signature` field is **`DSSE-PLACEHOLDER`**. Receipts carry a real SHA-256 Merkle digest
and a verified hash chain, but the **envelope is unsigned** until Sigstore/cosign CI lands
(see [Compliance & Security](/compliance)). $\mathrm{Khipu}_i(a)$ verifies the *chain*, not the
*signature*, today.
:::
