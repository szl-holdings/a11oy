---
layout: home

hero:
  name: SZL Holdings
  text: Governed AI. Evidence you can inspect.
  tagline: Documentation for a11oy and killinchu, with formal proof, source checks, receipt verification and deployment boundaries stated separately.
  image:
    dark: /szl/logos/szl_logo_mono_white.svg
    light: /szl/logos/szl_logo_mono_navy.svg
    alt: SZL Holdings
  actions:
    - theme: brand
      text: Quickstart →
      link: /quickstart
    - theme: alt
      text: Products and frontier roles
      link: /flagships/
    - theme: alt
      text: PURIQ Doctrine
      link: /doctrine/puriq
    - theme: alt
      text: Evidence
      link: /evidence/
    - theme: alt
      text: Verify a receipt
      link: https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/01-verify-a-receipt-end-to-end.md
    - theme: alt
      text: Cite
      link: /#citation

features:
  - title: a11oy — execution fabric
    details: Governed agentic execution source. Policy, measurement, knowledge-graph and QEC-integrity packages; formal claims retain their stated assumptions.
    link: /flagships/a11oy
  - title: Provenance Anchor — frontier role
    details: Source and model documentation for governance-receipt anchoring. Publication and deployed readiness require their own evidence.
    link: /flagships/amaru
  - title: Policy — frontier role
    details: Posture-drift detection and policy research documentation. The mathematical model and deployed behavior have separate qualification boundaries.
    link: /flagships/sentra
  - title: killinchu — drone intelligence
    details: Counter-UAS rule-engine source with Remote-ID / ADS-B / MAVLink parsing, geofence checks, 13-axis admission and DSSE receipts. Runtime qualification is separate.
    link: /flagships/killinchu
  - title: Operator — frontier role
    details: Receipt-orchestration source and formal models. Conditional invariants, source checks and deployed receipt verification are documented separately.
    link: /flagships/rosie
---

## What is SZL?

SZL Holdings builds **governed-AI infrastructure**: an *anatomy* of composable organs that
turns a model from a thing that *evaluates* into an agent that *acts under proof*. The
core claim is narrow and falsifiable — **an action is "agentic" only if it is
Λ-bounded, Yuyay-gated, HUKLLA-safe, and Khipu-receipted** — and it is stated as a
single Lean-checkable operator, `P(x,t)`, defined in [Doctrine v12 (PURIQ)](/doctrine/puriq).

Everything ships under the **Zero-Bandaid Law**: every formula is Lean-stateable (open
goals are `sorry`-tagged, never hidden), every claim is verifiable on disk, and every act
emits a receipt. We use **no mystical language** anywhere — every name below is either a
cited Quechua common noun or a math primitive carried from the formal corpus.

The Lean corpus that backs these claims is, at the Doctrine v11 lock,
<span class="locked">749 declarations</span> · <span class="locked">14 unique axioms</span> ·
<span class="locked">163 tracked sorries</span>, with a
<span class="locked">13-axis yuyay_v3</span> heart whose replay hash is
<span class="locked">bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5</span>
(see [Doctrine v11 + v12](/doctrine/v11-v12) for the locked register and
[Evidence](/evidence/) for reproduction commands).

## The five flagships

Each flagship is a real GitHub repository under [`szl-holdings`](https://github.com/szl-holdings),
cross-referenced to the Ouroboros Thesis ([DOI 10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276))
and the Lean kernel [`lutar-lean`](https://github.com/szl-holdings/lutar-lean).

| Flagship | Quechua etymology | One line |
|----------|-------------------|----------|
| **[a11oy](/flagships/a11oy)** | English *alloy* (a11y-styled) — a blended, hardened substrate | Governed agentic **execution fabric** (7 layers) |
| **[amaru](/flagships/amaru)** | *amaru* = **serpent** | **Provenance anchor** — Cardano + Shor-encoded receipts |
| **[sentra](/flagships/sentra)** | from *sentry* / Quechua-styled guard | **Drift detector** — Kitaev-surface posture monitoring |
| **[killinchu](/flagships/killinchu)** | *killinchu* = **kestrel** (a small Andean falcon) | **Drone intelligence** — counter-UAS Λ-gate |
| **[rosie](/flagships/rosie)** | Receipt-Orchestrated Signed Ingress Environment | **Receipt orchestration** — Khipu DAG + CSS ingress |

> Quechua glosses follow the standard lexica indexed at
> [kaikki.org Quechua](https://kaikki.org/eswiktionary/) and
> [Wiktionary *puriy*/*puriq*](https://en.wiktionary.org/wiki/puriy). *killinchu* = "kestrel";
> *amaru* = "serpent". `a11oy` and `rosie` are SZL coinages (the alloy metaphor and the
> ROSIE acronym), not Quechua words — labelled honestly as such.

## Core & proof

Beyond the five flagships, two repositories carry the load-bearing evidence:

- **[`lutar-lean` / lean-kernel](https://github.com/szl-holdings/lutar-lean)** — the
  machine-checked Lean proof corpus (749 declarations / 14 axioms / 163 sorries at
  `c7c0ba17`). See [Proof](/proof).
- **[`szl-lake`](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake)** — the public
  attestation lake: DSSE receipts, doctrine snapshots, Khipu chains, SBOMs. See [Data Lake](/lake).

## Start here

- **[Quickstart](/quickstart)** — five minutes to a first call against each flagship.
- **[Architecture](/architecture)** — the 7-organ anatomy and the master action-selection operator.
- **[Anatomy + Organs](/anatomy/)** — the twelve organs, each with its Quechua etymology, function, formula, and Lean stub.
- **3D Showcases** — interactive Anatomy-3D and Rosie-3D.
- **[Proof](/proof)** — Lean kernel, data lake, and Zenodo DOIs.
- **[Changelog](/changelog)** — aggregated v1.0.0 release notes (Keep a Changelog).
- **[UDS — Deploy & Hand-off](/uds)** — sign-verify-deploy a flagship as a UDS payload.
- **[Compliance & Security](/compliance)** — honest posture: SLSA L1, cosign PENDING, certification roadmap.

## Citation

If you build on SZL, please cite the archived release:

```bibtex
@software{szl_holdings_2026,
  author    = {Lutar, Stephen P.},
  title     = {SZL Holdings: Sovereign Governed AI --- a formally-verified governance substrate for agentic systems},
  year      = {2026},
  publisher = {Zenodo},
  version   = {Doctrine v11 LOCKED},
  doi       = {10.5281/zenodo.20434276},
  url       = {https://github.com/szl-holdings},
  note      = {749 declarations / 14 axioms / 163 sorries, kernel c7c0ba17}
}
```

## Built with / learned from

Our documentation and publication conventions were learned from open-source leaders — we
adapted their *patterns*, not their words. Inspired by patterns from **Polymathic AI**
([the_well](https://github.com/PolymathicAI/the_well), [walrus](https://github.com/PolymathicAI/walrus)),
**Anthropic**, **OpenAI** ([whisper](https://github.com/openai/whisper)), **Stripe** (docs craft),
Google DeepMind ([alphafold3](https://github.com/google-deepmind/alphafold3)),
Meta FAIR ([segment-anything](https://github.com/facebookresearch/segment-anything)),
EleutherAI ([lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)),
and Hugging Face ([transformers](https://github.com/huggingface/transformers)).
We are a precision substrate, not a vibes company.

<div class="quechua">
<strong>No mysticism.</strong> SZL's naming is etymological, not ritual. The Quechua words
are common nouns chosen for their precise meaning (serpent, kestrel, blood, light); the
math is the load-bearing part. If a claim is not yet proven, it is labelled a conjecture
or a tagged <code>sorry</code> — never dressed up.
</div>
