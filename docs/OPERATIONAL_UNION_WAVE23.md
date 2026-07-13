# A11oy operational union wave 23

Date: 2026-07-13  
Branch: `codex/operational-union-wave23`  
Status: **local integration candidate; not merged or deployed**

This ledger separates repository presence, local verification, and public operational state. It is not a release announcement. A feature is not described as live merely because code, a model card, or a route exists.

## Verified local integration

- Frontier catalog preserves all 127 registered surfaces and adds responsive, searchable, keyboard-accessible navigation.
- Holographic command navigation is responsive, hash-addressable, modal-safe, and renderer-host resizing is observed.
- BrainQuery exposes server-side query latency receipts and keeps raw counts, distinct artifacts, and people separate.
- The current canonical Brain reconciliation records:
  - 9,464 raw nodes;
  - 4,229 distinct artifacts;
  - 5,235 person nodes; and
  - 14,234 links.
- All 9,464 raw Brain rows remain `QUARANTINE` and `training_eligible=false`.
- The formula-admission crosswalk contains 146 namespaced formula mappings plus two SZL-Lake evaluation examples. Its 148-row tranche is holdout-only and admits zero training rows.
- The M1 corpus ledger was regenerated from the canonical generator. Metadata, corpus, deterministic-rebuild, and formula-admission checks passed without promoting model quality.
- The numerical-engine registry freezes 1,328 comparison cases. MATLAB and Octave results remain absent.
- The fixed-scenario Ouroboros ablation passed its bounded local acceptance criteria. It does not establish general model-quality or real-world improvement.
- The companion dataset package `dataset_release/szl-proof-obligation-queue` contains 146 receipt-bound proof-obligation records, 148 holdout rows, deterministic checksums, schemas, provenance, citation metadata, and zero training-eligible rows.

## Public research records

The following two records were independently read back as public preprints. They are **not peer reviewed**.

1. *From Build Success to Admissible Proof: Evidence-Typed Governance for a Mixed Lean and Executable Formula Corpus*
   - DOI: https://doi.org/10.5281/zenodo.21332317
   - GitHub release: https://github.com/szl-holdings/evidence-typed-formula-governance/releases/tag/v0.1.0
2. *Readiness Is Not Evidence: Fail-Closed Epistemic Boundaries for Governed AI Services*
   - DOI: https://doi.org/10.5281/zenodo.21332338
   - GitHub release: https://github.com/szl-holdings/fail-closed-governed-ai-services/releases/tag/v0.1.0

Existing associated records remain separately typed:

- Ouroboros concept: https://doi.org/10.5281/zenodo.19944926
- Thesis/formal artifact record: https://doi.org/10.5281/zenodo.20434276
- Repository preservation records: `20434306`, `20162352`, and `21184984`

The companion dataset DOI and the A11oy `v1.1.0` software DOI remain pending. Repository-preservation DOIs are not substitutes for paper or dataset DOIs.

## Model program

### Existing M1 candidate

- Base: `unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit`
- Immutable revision: `d2f2dd02b071701d5100a04a7a49d6fb0bd305b7`
- Existing adapter SHA-256: `682e2f0ea480d47c284b9de12c2e3d2d5170934c065e82fc375e3f069b4730ac`
- Historical data: 167 rows; rights/privacy/contamination review incomplete
- Historical evaluation: directional 16-row loss observation only
- ORPO: 0/12 qualification checks; quarantined
- Release state: `NOT_PROMOTED`
- Quality: `NOT_ESTABLISHED`

### SZL-Forge / ReceiptAgent

The recommended public family name is **SZL-Forge-1.5B**. Its first profile is **ReceiptAgent**, a proof-carrying structured-output adapter. The profile must bind answers or abstentions to evidence hashes, formula namespaces/statuses, uncertainty, proposal-only tools, and an external receipt boundary.

The release contract exists. ReceiptAgent-specific weights do not. Planned Hugging Face model, evaluation set, schemas, Space, and collection are all `PLANNED_NOT_CREATED`.

The 9,464 Brain nodes and 148 formula holdout rows are external retrieval/evaluation substrates, not training data. No claim of training on "all nodes" or "200 formulas" is supported by current admission evidence.

## Verification matrix

Current branch validation at the pre-ledger model commit executed 183 of 236 newly added test cases with zero assertion failures. Additional focused publication/model checks passed after that matrix:

- ReceiptAgent contract and card: 12/12
- Companion dataset: 9/9
- Publication surfaces: 2/2
- M1/formula reconciliation: 10/10 reported by the focused generator/gate run

Other checks that passed:

- tracked secret scan across 4,198 files;
- all changed JSON/JSONL parsing;
- changed Python compilation;
- changed JavaScript and inline-module parsing;
- Frontier 127-surface self-test;
- current-tree and integration-range whitespace checks; and
- Git object integrity.

Exactly 53 route/integration tests remain environment-blocked because the permitted runtime lacks compatible `pytest`, `fastapi`, and `starlette` dependencies. The full API server and computed-layout browser verification have therefore not run in this workspace. An offline `pnpm` restore also attempted npm attestation lookups and was denied by the network sandbox; no dependency versions were changed.

## GPU state

The governed verifier queue is allowed to start work only after fixed GPU admission criteria pass. During this wave, receipts repeatedly returned `REFUSED`; no model load or training was started. A later sample observed the RTX 5050 Laptop GPU near saturation while LM Studio was resident. The verifier did not stop user processes, weaken thresholds, or claim work completed.

Training requires:

1. an admitted, rights-reviewed curriculum;
2. available GPU resources under the fixed policy;
3. an immutable base and environment lock;
4. a receipted run;
5. clean reload/inference receipts; and
6. the frozen base-vs-existing-SFT-vs-new-model evaluation matrix.

## GitHub and deployment state

The local branch is ahead of the locally known `origin/main`. The remote branch named `codex/operational-union-wave23` currently resolves to the same commit as remote `main`, so it does not contain this local union. There is no verified PR.

Publishing is blocked because GitHub CLI is installed but has no authenticated GitHub host. The connected GitHub application can read repository state but does not replace the local authenticated push required for this 155-file, multi-commit branch.

Consequences:

- the union is not merged into `main`;
- GitHub Actions have not evaluated the current union;
- `a-11-oy.com`, `a11oy.net`, A11oy Space, and Killinchu have not been proven to run this commit;
- no A11oy `v1.1.0` tag/release or software DOI has been read back; and
- no ReceiptAgent/SZL-Forge weights or Space have been published.

The Zenodo credential previously pasted into chat must be revoked and replaced in an approved secret store before any deposit operation.

## Required release train

1. Rotate the exposed Zenodo credential.
2. Authenticate GitHub CLI without pasting credentials into source or chat.
3. Push this branch, open a draft PR, and let the full CI/security/reliability matrix run.
4. Resolve any CI failures, review, and merge to `main`.
5. Verify the exact deployed build SHA independently on both domains and both Hugging Face Spaces.
6. Create the immutable `v1.1.0` GitHub release and verify SBOM, signatures, attestations, and assets.
7. Allow Zenodo preservation and read the public software DOI back before changing citations.
8. Rights-review and publish the companion dataset as a separate archival record; then read its DOI back.
9. Train SZL-Forge only after data and GPU admission; publish weights only after load, inference, evaluation, energy, restart, and provenance receipts pass.
10. Publish the CTO/defense launch post only after every included DOI, GitHub, Hugging Face, and production URL resolves.

## Research direction

The defensible frontier is not a persona clone or an unverifiable claim that a small model solved open mathematics. It is a compact sovereign model whose outputs carry typed evidence and whose external runtime can prove what was retrieved, proposed, approved, executed, and observed. That combination is unusual; rarity and market leadership still require independent evaluation, adoption, and reproducible public receipts.
