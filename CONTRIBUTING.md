# Contributing

Thank you for your interest in this repository. This project is part of the [SZL Holdings](https://github.com/szl-holdings) platform — governed AI decision infrastructure built on the Ouroboros Thesis.

## Maintainer

**Stephen P. Lutar Jr.**  
ORCID: [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)  
Email: [stephen@szlholdings.com](mailto:stephen@szlholdings.com)  
GitHub: [@stephenlutar2-hash](https://github.com/stephenlutar2-hash)

## Contribution Model

This repository is published under its stated license. Contributions are welcomed under the following model:

### What you can do without prior agreement

- **Bug reports.** Open a [GitHub issue](../../issues/new) with reproduction steps, environment details, and expected vs. actual behavior.
- **Security disclosures.** Do **not** open a public issue. Follow [`SECURITY.md`](./SECURITY.md). Primary channel: [stephen@szlholdings.com](mailto:stephen@szlholdings.com).
- **Documentation corrections.** Typo, link, and factual fixes to public docs are welcome via PR. Open an issue first describing the change.
- **Questions and feedback.** Email [stephen@szlholdings.com](mailto:stephen@szlholdings.com).

### Pull request requirements (Doctrine v2)

All PRs must:

1. Pass all CI checks (lint, test, type-check) before requesting review.
2. Include or update tests for every changed behavior.
3. Reference the related issue (`Fixes #N`) in the PR description.
4. Receive at least one approving review from `@stephenlutar2-hash` (CODEOWNER).
5. Have all review conversations resolved before merge.
6. Use a conventional commit prefix: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.

No force pushes. No direct commits to `main`. Draft PRs are welcome for early feedback.

### Contribution license

By submitting a PR, you confirm that:

- You have the right to submit the contribution.
- You grant SZL Holdings, LLC a perpetual, irrevocable, royalty-free license to use, modify, and redistribute the contribution under this repository's license.
- The contribution does not include third-party code without proper attribution and a compatible license.

## Code of Conduct

All interactions are governed by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## Standards

- Code follows the style and conventions documented in [szl-holdings/szl-cookbook](https://github.com/szl-holdings/szl-cookbook).
- All workflows must use SHA-pinned actions (not version tags).
- Security-sensitive changes require a note in the PR description explaining the threat model.
