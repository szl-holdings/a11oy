# A11oy operational union wave 23

Date: 2026-07-13<br>
Branch: `codex/operational-union-wave23`<br>
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

### Ayllu model council and Yupaq compute boundary

Ayllu is now locally integrated with `SZL-Forge-1.5B` as a governed model-facing council. Its eleven personas are prompt/runtime roles sharing the routed A11oy model backend; they are not eleven independently trained weights. Every persona has a declared Forge profile intent, and every turn records the actual routed model separately.

The binding remains `ROUTER_INTEGRATED_FORGE_PROFILE_NOT_PINNED`. A model name in configuration is not proof that Forge weights loaded. Promotion requires a receipt binding the immutable base revision, adapter SHA-256, served model identity, load event, and reload evaluation.

The council is proposal-only. It cannot dispatch tools, execute external actions, approve its own proposals, sign evidence, or certify its own output. Yupaq is exposed as a typed external computation plane with fixed operations. Its stateful routes now require a bearer hash held in the secret store and isolate the process-local job cache by derived owner ID. Automatic Ayllu-to-Yupaq dispatch remains disabled pending durable replay storage, independent approval, and killable worker-isolation evidence.

Local no-key OpenAI-compatible inference is treated as live only when the configured endpoint answers its liveness probe. An unreachable local URL does not make the router path live without a real remote credential. Model replies are labeled `model-unverified`; they are not mislabeled as grounded Brain answers or automatically republished into the public lounge.

## Verification matrix

Current branch validation at the pre-ledger model commit executed 183 of 236 newly added test cases with zero assertion failures. Additional focused publication/model checks passed after that matrix:

- ReceiptAgent contract and card: 12/12
- Companion dataset: 9/9
- Publication surfaces: 2/2
- M1/formula reconciliation: 10/10 reported by the focused generator/gate run
- Ayllu/Forge/Yupaq/ReceiptAgent/OpenAPI/publication union: 135 tests and 21 subtests passed
- Formula implementation suite: 51/51 passed in a separate focused run (some overlap with the union gate)

Other checks that passed:

- tracked secret scan across 4,198 files;
- all changed JSON/JSONL parsing;
- changed Python compilation;
- changed JavaScript and inline-module parsing;
- Frontier 127-surface self-test;
- current-tree and integration-range whitespace checks; and
- Git object integrity.

The assembled FastAPI OpenAPI document now generates successfully. Pre-existing duplicate operation-ID warnings remain visible and are not being described as resolved.

A compatible local verification environment is now available, and the focused Ayllu/Forge/Yupaq/ReceiptAgent route and OpenAPI checks pass. This does not replace the repository's full CI matrix or production deployment verification. Computed-layout browser verification and an exact deployed-build readback remain pending. An earlier offline `pnpm` restore attempted npm attestation lookups and was denied by the network sandbox; no dependency versions were changed.

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

## Post-wave 23 local verification addendum — 2026-07-15

This addendum does not rewrite the July 13 snapshot above. It records a later local
integration measurement and does not imply merge, release, Hugging Face publication,
or deployment to `a-11-oy.com`, `a11oy.net`, or Killinchu.

- The exact local tags `receiptagent:latest` and `khipu:latest` were observed and
  used for ReceiptAgent/Yupaq and BrainNavigator/Maskaq turns respectively.
- Both local turn envelopes were independently verified under DSSE. The Maskaq turn
  also bound its model attestation, grounding, and six-handle evidence set to the
  receipt. The verification key was process-boot-ephemeral, so these are scoped local
  receipts rather than organization-identity signatures or transparency-log entries.
- The earlier 29-file seed observation was superseded by the atomic-generation
  rebuild below and is not a release candidate. The stale local attestation is
  intentionally excluded from staging.
- ReceiptAgent and BrainNavigator remain unpromoted. Their exact local tags and signed
  turns do not reconcile the declared adapter/full-weight hashes with published
  artifacts; the release identity remains unbound or in conflict.
- The fail-closed row-level admission engine in
  `szl_brain_training_admission.py` is implemented and covered by focused local
  regression tests. Its v2 contract requires stable source identity,
  author/rightsholder permission, signed privacy/PII clearance, held-out
  contamination checks, allowlisted signed review, and an explicit default-off
  training switch. It does not bulk-admit the Brain inventory. All 9,464 canonical
  raw rows remain outside gradients, the admitted training-row count remains zero,
  and no training run was started.
- The current scoped verification summary is versioned at
  `attestations/forge-second-brain-live-2026-07-15.json`. Its claims boundary keeps
  model promotion, dense retrieval, and training explicitly false.
- A fresh ReceiptAgent training preflight verified the 30-row train / 8-row eval
  curriculum and the exact immutable 1.5B base snapshot, including its
  `model.safetensors` hash. Training correctly remained blocked: the RTX 5050 had
  6,369 MiB free against the non-weakenable 6,656 MiB admission floor. The measured
  refusal is versioned at
  `attestations/forge-training-preflight-local-2026-07-15.json`; no training,
  upload, publication, or deployment occurred.
- After the atomic generation upgrade, the local RAG seed rebuilt with 488 corpus
  chunks and a separate 9,464-handle canonical Brain plane. A second process boot
  revalidated the persisted generation as `VERIFIED_ON_REHYDRATE`. The independent
  live harness then exercised Maskaq (`khipu:latest`) and Yupaq
  (`receiptagent:latest`), verified both DSSE signatures and every prompt, model,
  grounding, evidence, handle, citation, answer, and turn digest, and wrote PASS
  artifact SHA-256
  `0cfc363216624561f8faa080908fef4757db8267c40dafe07526b1cc502c9d8a`.
  A privacy-safe copy is versioned at
  `attestations/forge-second-brain-live-2026-07-15.json`.
- The stale port-8765 process was replaced with the current runtime-bound API.
  `SZL-Nemo` then served the exact local `szl-nemo:latest` tag whose manifest is
  `0d7777be553e3a9000b0a6d266936184f64cef1d5e567a85b74c418cf79d8c27`,
  bound to upstream `nemotron-3-nano:4b` manifest
  `6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197`.
  The call returned a real answer in `847.435 ms`; its DSSE signature and declared
  PAE digest were independently verified against the same-origin process-boot key.
  The evidence is versioned at `attestations/szl-nemo-live-2026-07-15.json`.
  This is a runtime-qualified governed NVIDIA recipe, not an SZL fine-tune; quality
  remains `UNVERIFIED_MODEL_OUTPUT`.
- A governed ReceiptAgent training queue is running with fixed, non-weakenable
  admission thresholds. It remains `WAITING_FOR_ADMISSION`; no training, upload,
  publication, or deployment has occurred. After the Nemo receipt the model was
  explicitly unloaded, but the latest GPU sample still failed the fixed thermal and
  free-VRAM gates, so the queue correctly continued waiting.
- `model_release/szl-hf-bucket-topology.json` now specifies separated mutable build,
  held-out evaluation, and sanitized runtime-evidence planes. Every consumable prefix
  requires a signed manifest, full SHA-256 and byte-count readback, and a final
  conditionally-created `COMPLETED.json`. Buckets remain noncanonical and are still
  `DECLARED_PLAN_NOT_CREATED`; versioned Hub repositories, signed release receipts,
  GitHub releases, and Zenodo records remain the publication authorities. The three
  private buckets were then created and independently read back as private and empty
  (`0` bytes, `0` files); no object was uploaded and no release was published.
