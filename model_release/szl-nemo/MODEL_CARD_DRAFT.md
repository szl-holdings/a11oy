---
language:
- en
license: other
license_name: NVIDIA Nemotron Open Model License
license_link: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16/blob/main/LICENSE
base_model: nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16
pipeline_tag: text-generation
inference: false
tags:
- nemotron
- ollama
- governed-inference
- provenance
- experimental
---

# SZL-Nemo runtime recipe

> **CONFIGURATION RECIPE - NOT AN SZL WEIGHT RELEASE**
> Release: `RUNTIME_QUALIFIED_RECIPE_NOT_FINE_TUNED` | Quality: `NOT_ESTABLISHED` | SZL fine-tuned: `false` | Repository weights: `absent`

SZL-Nemo is a governed Ollama configuration recipe over NVIDIA Nemotron 3 Nano
4B. The current repository does not contain an SZL adapter or redistributed
base weights. The recipe has completed one signed local load-and-generate path;
that receipt does not establish broad model quality, safety, or a trained SZL
candidate.

## Truth fields

| Field | Value |
|---|---|
| Artifact kind | `OLLAMA_CONFIGURATION_RECIPE` |
| Upstream producer | NVIDIA |
| Upstream base | `nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16` |
| Local upstream tag | `nemotron-3-nano:4b` |
| Derived local tag | `szl-nemo:latest` |
| SZL fine-tuned | `false` |
| SZL-trained weights | `none` |
| Model quality | `NOT_ESTABLISHED` |
| Public inference | `disabled` |
| Runtime receipt | `LOCAL_LIVE_VERIFIED`, process-boot-ephemeral signature |
| Upstream license | NVIDIA Nemotron Open Model License |

The exact locally observed derived digest is
`0d7777be553e3a9000b0a6d266936184f64cef1d5e567a85b74c418cf79d8c27`.
The privacy-safe local evidence is
`attestations/szl-nemo-live-2026-07-15.json`, SHA-256
`8cbd3f5e0ece21e08fc2fdc06a947c71216ddc83415327b9501fa501d8cfa1fb`.

## Intended use

- bounded local evaluation of the governed A11oy/Nemotron recipe;
- testing exact served-tag disclosure, abstention, and signed response paths;
- preregistered research before any separate fine-tuning program.

## Not established

- No Nemotron-compatible SZL adapter has been trained.
- No training dataset, trainer state, or training receipt exists for SZL-Nemo.
- No held-out quality, safety, citation, energy, or tool-use suite has passed.
- The process-boot receipt key is not an organization release identity.
- A local runtime pass is not permission to publish upstream weights.

## Promotion boundary

A future trained candidate must be published as a distinct versioned artifact.
It requires an immutable NVIDIA base identity, compatible adapter hashes,
row-level data rights and split receipts, a reproducible training receipt,
clean reload, frozen held-out evaluation, organization-identity DSSE/in-toto
attestation, transparency logging, and independent Hub readback. Until every
applicable gate passes, `trained_and_weighted=false` and canonical weight upload
remains blocked.

## License and attribution

The upstream weights are NVIDIA's and remain governed by the NVIDIA Nemotron
Open Model License and required notices. This card is an engineering record,
not legal advice and not an endorsement by NVIDIA or Hugging Face.
