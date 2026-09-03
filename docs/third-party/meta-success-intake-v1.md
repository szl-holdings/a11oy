# Meta-success reference intake — SZL Atelier Frontier Workbench v1

**Snapshot:** 2026-09-03
**Reference organization:** `meta-success`
**Affiliation:** none
**Implementation rule:** observe → abstract → recombine → govern → verify.

## Boundary

This intake does **not** import the reference organization, its site, its names, its mascot, its prompts, its screenshots, or its unlicensed source into SZL. Public visibility is not a software license. A repository whose license was not verified in this bounded audit is reference-only or clean-room-only.

The current implementation is original A11oy code. It adds a provenance registry, capability-lane map, hard-zero safety gate, 0.97 trust ceiling, deterministic derivation fingerprint, same-origin UI, and GET/HEAD-only runtime surface. It has no credential, signer, database, scheduler, model weight, or effector.

## Portfolio disposition

| Repository | License state | Reuse policy | Capability lanes | Boundary |
|---|---|---|---|---|
| `AI-agents` | `LICENSE_NOT_VERIFIED` | `CLEAN_ROOM_ONLY` | orchestration, language, multimodal, generation, alignment, training, evaluation, deployment | Multi-studio workbench and staged orchestration patterns only; no source, branding, mascot, prompts, or site assets copied. |
| `multimodal-vision-demo` | `LICENSE_NOT_VERIFIED` | `CLEAN_ROOM_ONLY` | multimodal, retrieval, identity | Independent evidence-envelope design only; no model glue or UI copied. |
| `football-analysis` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | sports_vision, evaluation | Frame-analysis capability reference; implementation requires independent design. |
| `AI-Image-PromptGenerator` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | generation, alignment | Prompt-governance reference only. |
| `n8n-automation` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | automation | Workflow ideas only; connector terms and source require separate review. |
| `certification` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | evaluation | Evaluation and certification workflow reference only. |
| `mujoco-drone-pong` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | simulation | Simulation pattern only; no environment or assets copied. |
| `NLP-chatbot` | `LICENSE_NOT_VERIFIED` | `CLEAN_ROOM_ONLY` | language, orchestration | Independent conversational pipeline design only. |
| `ai-generate-with-langchain` | `UPSTREAM_PROVENANCE_REQUIRED` | `UPSTREAM_REQUIRED` | orchestration, retrieval, generation | Documentation appears tied to external instructional material; original upstream license must be verified. |
| `meta-success` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | portfolio | Organization profile and navigation reference only. |
| `Table-tennis-anlaysis` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | sports_vision, evaluation | Frame-analysis capability reference only. |
| `VICE` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | multimodal, evaluation | Vision/evaluation pattern pending provenance review. |
| `AI-chatbot-MERN` | `UPSTREAM_PROVENANCE_REQUIRED` | `UPSTREAM_REQUIRED` | language, deployment | Documentation points to an external upstream project; preserve upstream notices after verification. |
| `Multi-Agent-System` | `EMPTY_OR_INSUFFICIENT` | `EMPTY_REFERENCE` | orchestration | No implementation was relied upon. |
| `bittensor-auto-register` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | automation, deployment | No wallet, credential, or registration automation copied. |
| `Make.com-automation` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | automation | Workflow ideas only. |
| `astro-project` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | deployment | Frontend/deployment pattern only. |
| `mujoco-cloth-hooking` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | simulation | Simulation pattern only; no environment or assets copied. |
| `RAG-pipeline-typescript` | `LICENSE_NOT_VERIFIED` | `CLEAN_ROOM_ONLY` | retrieval, deployment | Independent retrieval architecture only. |
| `face-ai-system` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | identity, multimodal | Biometric processing remains denied until consent, retention, bias, and jurisdiction controls are bound. |
| `solana-sniper-trading-mev-bot` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | markets, automation | No trading, MEV, key, or execution code copied; effectors remain disabled. |
| `chrome-livecaption` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | language, deployment | Speech/edge capability reference only. |
| `RAG-SYSTEM-NODE` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | retrieval, deployment | Documented capability and inspected source shape were not treated as reusable implementation. |
| `launchstack-custom` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | deployment | Deployment/frontend reference only. |
| `GPU-Accelerated-ML-Pipeline` | `VERIFIED_MIT` | `ADAPT_WITH_NOTICE` | gpu_lab, training, evaluation, deployment | Only verified permissive candidate. Current workbench independently implements the pattern and copies no source. |
| `booking-system` | `LICENSE_NOT_VERIFIED` | `REFERENCE_ONLY` | automation, deployment | Workflow/frontend reference only. |

## Public-site treatment

The public workbench site was used only to understand high-level interaction patterns such as capability navigation, staged agent workflows, evaluation controls, and telemetry affordances. It is not embedded, mirrored, screenscraped into the product, or reproduced visually. The SZL surface uses its own information architecture, typography, component geometry, copy, evidence model, and governance semantics.

## What A11oy changes

| Reference pattern | Original SZL recombination |
|---|---|
| Multi-studio AI workbench | One Atelier Frontier registry with explicit capability and provenance lanes |
| Agent workflow stages | Safety/evidence-first orchestration; failed safety is a hard zero |
| RAG demonstrations | Citation envelopes, stale/unavailable states, and source-bounded retrieval |
| GPU training demos | Runtime capability checks, deterministic configuration, benchmark evidence, and honest energy labels |
| Multimodal demos | Separate OCR/caption/detection claims until a governance gate authorizes fusion |
| Automation examples | No implicit writes; action passport, one bounded attempt, and receipt-on-write |
| Simulation examples | MODELED label remains attached and cannot become sensor truth |
| Deployment demos | Exact GitHub source → artifact → runtime identity and terminal verification |

## Verified permissive candidate

`meta-success/GPU-Accelerated-ML-Pipeline` exposed the following MIT license during the bounded audit. The complete notice is retained below. The v1 Frontier Workbench does not copy source from that repository; the notice records the only verified permissive candidate for a later, separately reviewed adaptation.

```text
MIT License

Copyright (c) 2026 meta-success

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Notice SHA-256: `13539d7d18cf3e67acc73a857861591095641f54ef194274638d1f1dcf56b568`

## Release gate

Before any future source-level adaptation:

1. Re-fetch the exact upstream commit and license.
2. Verify whether the repository is original or a mirror.
3. Preserve required copyright and license notices.
4. Record files and commits actually adapted.
5. Run security, dependency, doctrine, and provenance checks.
6. Keep third-party trademarks and visual identity out of SZL branding.
7. Deploy only through the canonical source-bound writer and verify the live runtime.
