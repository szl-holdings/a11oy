# The verifiable-AI landscape — where the leaders are, and the quadrant they left empty

2026 scan. Sources referenced, not reproduced — we cite the field, we don't copy it.

## Four adjacent camps (and who leads each)

1. **AI evaluation & benchmarking** — biggest, most crowded. Hyperscalers (AWS,
   Google Vertex, Microsoft Azure AI, IBM) set enterprise standards; specialists
   (Maxim AI, Kili, Epoch AI, Stanford HAI AI Index) drive public benchmarks.
   Market ~$1.9B (2025) → ~$6B (2030).
   *They do:* score models on quality / latency / cost.
   *They don't:* force each reported number to carry its own provenance, or fail
   a build when a result overclaims.

2. **Content provenance & authenticity** — the C2PA / Content Credentials
   coalition (Adobe, Arm, BBC, Intel, Microsoft; 6,000+ members), Google SynthID,
   watermarking / fingerprinting vendors.
   *They do:* prove where a file or image came from.
   *They don't:* say anything about whether an AI's numeric *claims* are backed —
   provenance of pixels, not of results.

3. **AI governance, trust & assurance** — fastest-growing (~$227M 2024 → ~$4.8B
   2034), driven by EU AI Act enforcement (Aug 2026). Credo AI, Holistic AI,
   Fairly AI, IBM watsonx.governance, and others.
   *They do:* policy, risk registers, compliance documentation.
   *They don't:* mechanically break a result that lies — they document the
   process, they don't enforce claim-level honesty inside the artifact.

4. **Benchmark integrity / contamination detection** — nascent, mostly academic.
   IsItBenchmark (OSS), one-time-pad overestimation frameworks, DeepLearning.AI
   coverage of contamination.
   *They do:* detect contamination / overestimation after the fact.
   *They don't:* ship as a build-breaking, pre-ship gate embedded in the pipeline.

## The empty quadrant = SZL's wedge

No one owns **claim-level, build-breaking honesty for an AI's own results, proven
on hard science.** SZL uniquely combines:

- a **doctrine** that forces every number into MEASURED / MODELED / NOT-RUN /
  NOT-MEASURED / NOT-TESTED,
- a **gate that fails the build** on any overclaim (measured-without-evidence,
  not-run-with-a-number, a headline wider than the data supports),
- applied to **governed physics / materials** (PINNs, CALPHAD) where honestly
  saying "this is outside my bounds, I don't know" *is* the product.

> Content provenance proves the file. Governance documents the process. Eval
> scores the model. **We certify the claim.** That is the open ground.

## How we take it — honestly

- **Interoperate, don't reinvent:** emit our provenance in forms these camps
  already trust — align labels with model-card fields, stay C2PA-friendly for any
  media we produce, export governance-ready evidence bundles.
- **Lead with the proof:** the a11oy 3-way PINN benchmark with a green honesty
  gate is a live demonstration no eval vendor can match — we ran NVIDIA's own
  tool head-to-head and published where we *lose* (steady Burgers).
- **Out-honest, don't out-spend:** our edge is credibility — cheap to earn,
  expensive to fake. Every claim links to its evidence; every competitor
  comparison cites its source.
