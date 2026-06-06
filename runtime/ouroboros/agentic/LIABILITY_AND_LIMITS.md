# Liability & Operating Limits

**Operator:** Lutar, Stephen P. — ORCID 0009-0001-0110-4173 — SZL Holdings
**Doctrine:** V6
**License:** Apache-2.0 (code) · CC-BY-4.0 (docs)

## What this stack does NOT promise

This is honest disclosure under doctrine measurabilityHonesty ≥ 0.95.

1. **No guarantee that an LLM will follow these rules.** The agent configs (`.cursorrules`, `CLAUDE.md`, `replit-agent.md`) instruct the models. The MCP envelope validator enforces the protocol layer. But a misbehaving or jailbroken model is still possible. Trust depends on the validator, not the prompt.
2. **No claim that 110/110 vitest tests prove correctness of every thesis.** They prove the runtime implements the formula as written. The mathematical correctness of the underlying theses lives in the Lean v2 proofs (TH8 has 1 honestly-blocked gap) and the arXiv submission. See `08_acceptance/ACCEPTANCE.md`.
3. **No claim that Bekenstein bound, graded norm, or any formula here represents original mathematics not derivable from public sources.** These are textbook implementations of established results, applied to the SZL doctrine framework. Citations live in the arXiv tarball.
4. **No claim of zero CVEs.** The 5 recurring audits surface CVEs as they're disclosed. Dependabot is on every repo.
5. **No claim of zero downtime.** Services are stateless and fail-closed; if FG or VSP can't be reached, dependent services return 503 — that's a design choice, not a bug.
6. **No claim that the runtime can replace human review.** Every commit, every PR, every merge still routes through the operator.

## What this stack DOES promise

1. **Doctrine V6 preflight passes** on every artifact in this payload, verified by `bash 02_doctrine/preflight.sh`.
2. **Every formula is implemented exactly once.** Three agents cannot disagree on the math.
3. **Every cross-agent message carries a replay-root stamp + evidence pointers.** Hallucinated claims are rejected at the envelope layer (see `M2M_ENVELOPE.md` rules R1–R10).
4. **Every accepted action is logged** to `cto_acceptance_log.jsonl`. Every rejection is logged to `cto_rejection_log.jsonl`. Full audit trail.
5. **Every Zenodo DOI bound here resolves to a single SHA.** DOI binding is idempotent and one-to-one.
6. **No forbidden patterns** in any tracked text file in this payload (definition documents excluded per preflight script comments).
7. **No bundled secrets.** Preflight scans for AWS, GitHub, Slack, OpenSSH, and OAuth token markers.

## Liability disclaimer (legal posture)

This software is provided under Apache-2.0 (code) and CC-BY-4.0 (docs). Both licenses include the standard disclaimer of warranties and limitation of liability. Specifically:

- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
- IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY.

Beyond the standard license terms, the operator (Lutar, Stephen P. / SZL Holdings) makes these additional commitments:

- The runtime will NOT take any of the actions in the CTO-blocked set on the operator's behalf (see Doctrine V6 §"CTO authority").
- The runtime will NOT auto-mint DOIs, submit to arXiv, publish to npm, force-push, delete branches/repos, edit profile/org settings, edit scheduled tasks, rename live products, spend money, or touch credentials. These all route through `confirm_action` to the live operator.
- The runtime will NOT bundle private data into commits.
- The runtime will NOT silently fall back to fabricated answers — `i_dont_know` is the required response when evidence is unavailable.

## How a third party should evaluate this stack

1. Read `00_README/README.md` (entry point).
2. Run `bash 02_doctrine/preflight.sh .` — must exit 0.
3. Read `12_agentic/M2M_ENVELOPE.md` (anti-hallucination contract).
4. Run `cd 04_runtime && pnpm install && pnpm -r test` — expect 110/110.
5. Run `cd 12_agentic && pnpm install && pnpm test` — formula + envelope tests.
6. Read `08_acceptance/ACCEPTANCE.md` (per-thesis definition of done).
7. Read `09_gaps_upgrades/GAP_REPORT.md` (honest gaps, no varnish).
8. Verify `MANIFEST.json` SHA-256s match.

If any of those fail, do not trust the payload. File issue against operator.

## Honest open gaps (do not paper over)

1. **TH8c full Mathlib adjunction** — ~3-4 weeks of dedicated math work. Currently `skeleton` + `axiom`, not proved.
2. **Branch protection deadlock on live repos** — self-only CODEOWNERS blocks all merges. Needs operator decision on second collaborator.
3. **Two platform-repo codenames** — D-01 in `09_gaps_upgrades/GAP_REPORT.md`. Doctrine exception or rename pending.
4. **GitHub display name** — contains 2 forbidden patterns. PATCH `gh api /user -f name='Lutar, Stephen P.'` required from operator.

## Contact

stephen@szlholdings.com — for liability, doctrine exceptions, or anything requiring `confirm_action`.
