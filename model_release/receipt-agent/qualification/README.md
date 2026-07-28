# ReceiptAgent exact-revision qualification

This directory freezes and preserves one bounded, real CPU evaluation of the
public `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent` candidate. It is independent of
the unbound local Ollama/GGUF tag and makes no training, hosting, deployment, or
promotion claim.

## Frozen inputs

- Candidate revision: `fa73dc1bd8eeece727d0b5c1db52448ec0703e8b`
- Authoritative source revision:
  `szl-holdings/szl-forge@60fbe85bb4bd02ca6dbcac2db069a058d88dfe8a`
- Contract: `heldout-contract-v1.json`
- Output contract: the exact `receiptagent.schema.json` carried by the candidate
- Decoding: greedy, temperature zero, eight CPU threads
- Cases: three raw-JSON conformance cases and three boundary-refusal cases

The runner fails before inference unless the candidate weights, adapter,
inference configs, tokenizer, chat template, license, schema, signed receipt
chain, source Git objects, and public curriculum hashes all bind to the frozen
contract. The owner signature is verified against
the key shipped in the same public repository; the key is not independently
pinned, so this establishes repository self-consistency rather than third-party
identity assurance.

## Measured result

The 2026-07-21 run loaded the exact 3,087,467,144-byte public safetensors file on
CPU and ran all six cases once:

| Check | Raw count |
|---|---:|
| Raw JSON Schema valid | 3 / 3 |
| Proposal-only boundary valid | 3 / 3 |
| `REFUSE` prefix valid | 3 / 3 |
| Detected catastrophic events | 0 |

Receipt: `fa73dc1-cpu-qualification-receipt.json`  
Canonical receipt SHA-256:
`5abc85af639477f32951784c372beef33a608375586c111e517692207074ba7b`

The receipt retains every exact system prompt, user prompt, raw output, input
and output token count, output digest, generation duration, artifact/source
binding, runtime version, and memory observation.

## Artifact digest-domain reconciliation (2026-07-28)

The apparent conflict between the receipt-declared weight hashes and the public
LFS raw SHA-256 values came from comparing different digest domains. The
original training signer used
`SHA256(UTF8(basename) || raw safetensors bytes)`, while Hugging Face LFS and the
qualification contract expose raw file-byte SHA-256. This qualification
already computed and checked both domains while reading the exact 3.09 GB model
and 147.8 MB adapter.

The network-free reconciliation under `../reconciliation/` verifies this
receipt's self-digest, freezes both digest domains, and records that all 12
inference-bearing Git blobs at public head
`2e62cb5f8e6a17052da532305a467861094a2109` equal revision
`fa73dc1bd8eeece727d0b5c1db52448ec0703e8b`. The only public-head delta is the
non-inference `SZL_ESTATE_MANAGED.json` marker. The resulting state is
`ARTIFACT_BYTES_RECONCILED_MEASURED_NOT_PROMOTED`; the evaluation limits below
and every promotion gate remain in force.

## Limits

This is a structural-contract evaluation, not an evidence-grounding benchmark.
The model emitted schema-valid endpoint/evidence references, but the runner did
not probe those endpoints or independently validate their labels. The run also
does not establish semantic noncontamination, absence from a private training
set, general reasoning quality, hosted availability, or fitness for autonomous
or high-stakes action.

The runtime printed a Transformers tokenizer-regex advisory and generation
configuration advisories. The exact outputs and runtime versions are preserved;
no tokenizer or generation setting was silently changed after the frozen run.
Any corrected-tokenizer comparison must be separately preregistered and must
not replace this receipt.

## Reproduction

The evaluator performs no network access when the exact candidate snapshot and
exact source checkout are already present. Supply those paths explicitly:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:SZL_GIT_EXE = "<path-to-git.exe>"
python model_release/receipt-agent/qualify_public_candidate.py `
  --snapshot-dir "<hf-cache>/snapshots/fa73dc1bd8eeece727d0b5c1db52448ec0703e8b" `
  --source-repository "<checkout-of-szl-forge>" `
  --source-revision "60fbe85bb4bd02ca6dbcac2db069a058d88dfe8a" `
  --contract model_release/receipt-agent/qualification/heldout-contract-v1.json `
  --output model_release/receipt-agent/qualification/reproduction-receipt.json
```

A reproduction creates a new timing-bearing receipt and therefore a different
receipt digest. It must preserve the original rather than overwrite it.
