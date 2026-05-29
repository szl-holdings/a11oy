# Public research brief for external analysts

Use this brief with Perplexity or any external analyst to validate the SZL
Holdings public substrate. The goal is evidence collection, not marketing copy.

## Research question

Validate that SZL Holdings has a public, GitHub-backed governed-AI substrate
centered on A11oy, with UDS/Zarf packaging, receipt-chain audit evidence,
formal-methods references, and a generated Hugging Face diligence mirror.

## Repositories to inspect

Active showcase:

- <https://github.com/szl-holdings/a11oy>
- <https://github.com/szl-holdings/platform>
- <https://github.com/szl-holdings/ouroboros>
- <https://github.com/szl-holdings/lutar-lean>
- <https://github.com/szl-holdings/ouroboros-thesis>
- <https://github.com/szl-holdings/rosie>
- <https://github.com/szl-holdings/amaru>
- <https://github.com/szl-holdings/sentra>
- <https://github.com/szl-holdings/uds-mesh>
- <https://github.com/szl-holdings/vsp-otel>
- <https://github.com/szl-holdings/vessels>
- <https://github.com/szl-holdings/agi-forecast>
- <https://github.com/szl-holdings/szl-trust>
- <https://github.com/szl-holdings/szl-brand>
- <https://github.com/szl-holdings/szl-cookbook>
- <https://github.com/szl-holdings/.github>

Excluded from active-demo claims until funded:

- <https://github.com/szl-holdings/counsel>
- <https://github.com/szl-holdings/terra>
- <https://github.com/szl-holdings/carlota-jo>

## Canonical evidence to request

1. A11oy current README and `docs/PROVENANCE.md`.
2. A11oy `docs/ecosystem-readiness-report.json`.
3. A11oy GitHub Actions runs for Doctrine Build, Operational Validation, SBOM,
   CodeQL, and Hugging Face publish.
4. A11oy releases `v1.0.1` and `uds-v0.2.0`.
5. Amaru, Sentra, Rosie, Vessels, and UDS Mesh UDS releases.
6. Thesis DOI `10.5281/zenodo.20434276`.
7. Lean proof substrate DOI `10.5281/zenodo.20434308`.
8. Hugging Face target `https://huggingface.co/SZLHOLDINGS/a11oy-v19-substrate`.

## Guardrails for the analyst

- Do not use `KORA`, `LUMINA`, `PARAGON`, or active `Lyte` framing.
- Do not report Counsel, Terra, or Carlota Jo as operational demo surfaces.
- Do not claim Defense Unicorns endorsement or UDS catalog acceptance.
- Do not claim every thesis statement is formally closed unless current
  `lutar-lean` CI and theorem reports prove that exact claim.
- Treat Hugging Face as a generated mirror; GitHub releases, CI, manifests, and
  DOI records are canonical.

## Suggested external prompt

```text
Deeply validate the public SZL Holdings governed-AI substrate. Focus on the
GitHub repositories and releases listed below. Determine what is actually
implemented, what is packaged for UDS/Zarf, what has CI/release evidence, what
has formal-methods or DOI evidence, and what is explicitly roadmap or scaffold.
Do not use stale product names KORA, LUMINA, PARAGON, or Lyte. Exclude Counsel,
Terra, and Carlota Jo from active-demo claims until funded. Produce an
evidence-cited report with a claim/status table and links to exact GitHub files,
releases, workflows, DOI pages, and Hugging Face mirror files.
```

