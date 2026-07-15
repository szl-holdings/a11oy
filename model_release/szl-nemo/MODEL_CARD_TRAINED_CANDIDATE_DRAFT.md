---
language:
- en
license: other
license_name: NVIDIA Nemotron Open Model License plus pending SZL adapter license review
license_link: https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/
base_model: nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16
base_model_relation: adapter
library_name: peft
pipeline_tag: text-generation
inference: false
tags:
- nemotron
- peft
- governed-inference
- provenance
- experimental
---

# SZL-Nemo Governed Adapter v1

> **TRAINING CANDIDATE - NO ADAPTER WEIGHTS YET**
> Release: `EXECUTABLE_CANDIDATE_NOT_TRAINED` | Quality: `NOT_ESTABLISHED` | Inference: `UNAVAILABLE`

This is the preregistered card for `SZL-Nemo-Governed-Adapter-v1`, a future
PEFT adapter over NVIDIA Nemotron 3 Nano 4B. It is separate from the existing
`SZL-Nemo-runtime-recipe-v1`. The recipe proves one local served-tag path; it
does not prove this candidate was trained.

## Truth fields

| Field | Value |
|---|---|
| Artifact class | `PEFT_ADAPTER` |
| Candidate ID | `SZL-Nemo-Governed-Adapter-v1` |
| Upstream producer | NVIDIA |
| Exact base repository | `nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16` |
| Exact base revision | `dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f` |
| SZL adapter weights | `ABSENT` |
| Training state | `NOT_TRAINED` |
| Evaluation state | `NOT_RUN` |
| Quality | `NOT_ESTABLISHED` |
| Public inference | `disabled` |
| Upstream license | NVIDIA Nemotron Open Model License |

## Preregistered data boundary

Only project-authored governance scenarios admitted by the immutable curriculum
manifest may enter gradients. Raw Brain nodes, formula holdouts, historical SFT
rows, legacy Brain/formula corpora, and the failed ORPO candidate remain outside
gradients. A repository or Bucket object is not evidence that this boundary was
obeyed; the exact training receipt and immutable split hashes must prove it.

## Required qualification

Publication remains blocked until the exact candidate has:

1. an immutable NVIDIA base file set and license acknowledgement;
2. GPU admission plus a completed bounded training receipt;
3. `adapter_model.safetensors` and `adapter_config.json` hashes;
4. clean adapter reload bound back to the exact base and tokenizer;
5. every preregistered held-out row passed with zero forbidden claims;
6. broader safety, identity, abstention, restart, latency, and resource receipts;
7. legal/license review for the separately authored adapter;
8. named human approval bound to the candidate digest;
9. asymmetric DSSE/in-toto provenance and a transparency-log reference; and
10. independent readback of the immutable Hugging Face revision and every file.

No model card, process exit code, local tag, Bucket object, or completion marker
can substitute for those gates. Until they all pass, there is no trained SZL-Nemo
adapter to download, and the card must remain `inference: false`.

## License and attribution

The NVIDIA base weights remain NVIDIA's and retain their upstream license and
notice requirements. Fine-tuning does not convert the base to Apache-2.0 or
transfer ownership. The license for any separately authored SZL adapter remains
pending exact lineage and legal review. This is an engineering record, not legal
advice or an endorsement by NVIDIA or Hugging Face.
