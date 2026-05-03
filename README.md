# A11oy

  > Orchestration and Decision Intelligence layer for the SZL Holdings governed platform.

  ## Status

  A11oy is the operator-facing orchestration surface for the SZL Holdings platform. It is now a working application inside the SZL Holdings monorepo (`szl-holdings/szl-holdings-platform`, private dev) with multiple operational surfaces: Atlas, Decision Intelligence, SIGIL, Lab, and a real streaming chat backed by Claude Sonnet 4.6 via the Replit AI Integrations Anthropic proxy.

  This public repository is the canonical landing page for the A11oy product. It does not yet serve a deployed instance; the live development surface is reachable to the operator via the SZL Holdings monorepo.

  ## Public proof of the underlying primitives

  The shipped open-source piece of the SZL Holdings work is the runtime in [`@szl-holdings/ouroboros`](https://github.com/szl-holdings/ouroboros) (release v6.2.0, full suite 172/172 tests passing) and the [Ouroboros Thesis](https://github.com/szl-holdings/ouroboros-thesis) (paper-v3-2.0.0, DOI [10.5281/zenodo.19983066](https://doi.org/10.5281/zenodo.19983066), concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926), published 2026-05-02, "The Loop Is the Product: Measuring Bounded Recursion as a System Primitive for Auditable AI").

  ## What A11oy actually does today

  - Orchestration control plane: agent registry, validator policy, approval gate, operator monitoring of bounded-loop runs from `@szl-holdings/ouroboros`.
  - Decision Intelligence surface: ranked decision queue, structured rationale envelope, operator-editable routing weights.
  - SIGIL (SZL Integrated Governance & Invariant Layer) endpoints: compose, witness, coherence, saturation.
  - Real Claude-class chat with streaming, multi-turn memory, code generation, and document analysis. Backed by claude-sonnet-4-6 via the Replit AI Integrations Anthropic proxy. System prompt restricts the model to truthful descriptions of the SZL Holdings platform and refuses fabricated metrics, contracts, certifications, or partnerships.
  - Lab: in-tenant prompt editor and pattern atlas.

  ## What this repo is not

  - Not a deployed product yet (the live surface lives inside the monorepo).
  - Not government-audited. The 2026-04-30 Empire APEX session with NYSTEC was procurement counseling, not an audit.
  - Not feature-complete.
  - Not in production.

  Earlier copies of this README claimed government-readiness scorecards, NYSTEC audit findings, NIST AI RMF coverage, deployed routes, and inflated test surfaces across seven products. Those were aspirational. The honest state is: working multi-surface orchestration application on top of a 172-test reference runtime and a Zenodo-pinned thesis.

  ## License

  See [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

  ## Contact

  [stephenlutar2@gmail.com](mailto:stephenlutar2@gmail.com)

  © 2026 SZL Holdings.
  