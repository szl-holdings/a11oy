# Offline Hugging Face promotion guard

This directory is the fail-closed boundary between local SZL model work,
mutable Hugging Face Buckets, and canonical Hub repositories. It performs no
network calls, never reads credentials, and has no upload implementation.

Current decisions:

- `SZL-Nemo-runtime-recipe-v1`: a locally runtime-qualified configuration
  recipe over NVIDIA weights. It is not SZL-fine-tuned and weight promotion is
  blocked.
- `SZL-Nemo-Governed-Adapter-v1`: a separate pinned training candidate with a
  project-authored 24/8 split. Native Windows is unavailable. Its OS-isolated
  WSL2/Linux Mamba import lane is qualified, while model load/capacity remains
  unrun. It is not trained, evaluated, or promoted, and no adapter payload exists.
- `SZL-Forge-1.5B-ReceiptAgent-v1`: a planned PEFT adapter. Training is still
  blocked by GPU admission and no ReceiptAgent-specific adapter exists.

Verified private staging stores (created empty on 2026-07-15):

- `SZLHOLDINGS/szl-forge-build-staging`
- `SZLHOLDINGS/szl-forge-eval-staging`
- `SZLHOLDINGS/szl-forge-runtime-evidence`

No object is uploaded by this guard. The checked-in topology contract is the
authority for their last independently observed privacy, size, and object count.

Run the offline integrity audit:

```powershell
python model_release/hf-promotion/promotion_guard.py audit
```

Manifest-bound text identities are strict UTF-8 normalized to LF before byte
counting and SHA-256. Binary identities remain raw-byte exact. This makes the
same reviewed commit verifiable from native Windows, WSL, and Linux clones.

The future `stage-plan` command inventories a local payload only after every
blocking gate in the checked-in manifest is `PASS`. Today it deliberately exits
`3` before reading a payload because both candidates remain blocked. It never
uploads.

```powershell
python model_release/hf-promotion/promotion_guard.py stage-plan `
  --candidate SZL-Forge-1.5B-ReceiptAgent-v1 `
  --payload-dir C:\path\to\qualified-candidate `
  --attempt-id 019f-example-never-reused
```

## Bucket layout

Every candidate uses a never-reused attempt ID and a candidate-specific prefix:

```text
build:   attempts/{attempt_id}/payload/{candidate_slug}/
eval:    attempts/{attempt_id}/payload/{candidate_slug}/
runtime: batches/{attempt_id}/payload/{candidate_slug}/
```

The existing Bucket completion contract still applies: content hashes and byte
counts are computed locally, every object is read back, a separately signed
completion marker is written last, and Buckets remain mutable/noncanonical.

## Promotion sequence

1. Pass the immutable base, data-rights, training, reload, held-out evaluation,
   license, DSSE/transparency, and human-approval gates for one exact candidate.
2. Produce a safe local inventory. PEFT publication accepts safetensors plus
   text/JSON metadata, never pickle/PyTorch checkpoint serialization or full
   base weights. `candidate-qualification.json` must validate against
   `candidate-qualification.schema.json` and bind the exact adapter/config,
   base file set, training, reload, evaluation, license, human approval, and
   DSSE digests before a stage plan can exist.
3. Stage under the private Bucket prefix and complete independent hash readback.
4. Publish separately to the correctly typed versioned Hub repository.
5. Read back the immutable Hub revision and all file/LFS digests before creating
   a collection, enabling a Space, or making a release claim.

Object presence, a model card, a local runtime tag, a completed training process,
or a Bucket audit event is never release authority.
