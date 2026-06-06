# Roadmap

A snapshot of where Sentra is heading. Issues are the source of truth — this is a navigational summary, not a contract.

## Now — `uds-v0.1.x` line (shipped, hardening)

- ✅ Signed UDS/Zarf payload with offline cosign verify
- ✅ Doctrine demo (`doctrine-demo.mjs`) — 30 s post-deploy live verdict harness
- ✅ Public-URL smoke test (17/17 from a clean tmpdir)
- ✅ KS-18 witness with verified 2-regular cover and exhaustive unsatisfiability
- 🔄 Per-file MANIFEST.json with sha256 of every payload file (in v0.1.1; documenting)
- 🔄 SBOM hardening: pin every transitive dep version in the SBOM, not just direct

## Next — `uds-v0.2.0` (target: Warhacker week + 30 days)

- [ ] **Keyless / Fulcio signing path.** Currently we ship a dev cosign keypair. Add an optional keyless cosign signing flow against the public Sigstore Fulcio so downstream verifiers can use OIDC identity-based verification.
- [ ] **UDS bundle reference deployment.** A complete, tested `uds-bundle.yaml` that boots Sentra plus a sample policy gate in a minimal UDS cluster.
- [ ] **Doctrine demo expansion.** Add a 2-cover violation regression case so the demo itself would have caught the v0.1.0 KS-18 bug if it had been shipped.
- [ ] **POVM verdict streaming API.** A documented streaming interface so downstream pipelines can feed live observations into the verdict head without a request/response boundary.
- [ ] **CONTRIBUTING / GOVERNANCE hardening.** Codify the doctrine pre-flight as a required GitHub Action that blocks merge.

## Later — `uds-v0.3.0+`

- [ ] **Multi-party doctrine composition.** When two Sentra instances need to compose verdicts (e.g. coalition deployments), spell out and enforce the composition rules.
- [ ] **Hardware attestation hooks.** TPM / SEV-SNP attestation of the running Sentra binary tied back to the cosign signature.
- [ ] **Reference UDS catalog entry.** A pull request to [`defenseunicorns/uds-package`](https://github.com/defenseunicorns/uds-package) (only after discussion with Defense Unicorns).
- [ ] **Formal verification stub.** A small Lean / Coq / TLA+ formalization of the POVM completeness invariant.

## Out of scope (deliberately)

- Sentra is **not** a model. It does not train, fine-tune, or host LLMs. It is a verdict layer on top of model outputs.
- Sentra is **not** an MLOps platform. It does not manage GPU schedulers, datasets, or experiments.
- Sentra does **not** ship telemetry to any vendor. The shipped payload makes zero outbound network calls. This is a doctrine, not a default.

## How to influence the roadmap

- File a feature request issue.
- Comment on an existing tracking issue with your use case and constraints.
- For Defense Unicorns / UDS catalog operators: email `stephen@szlholdings.com` — we will prioritize anything that unblocks a UDS deployment.
