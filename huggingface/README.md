---
license: other
license_name: proprietary
license_link: https://github.com/szl-holdings/a11oy/blob/main/LICENSE
language:
  - en
tags:
  - governance
  - agentic-ai
  - policy
  - provenance
  - zarf
  - uds
pretty_name: A11oy Governed Agentic Execution Fabric
---

# A11oy

A11oy is the SZL Holdings vertical alignment substrate for governed agentic
execution: policy gates, signal measurement, knowledge routing, and QEC-derived
receipt integrity.

This Hugging Face payload is a distribution mirror, not a model checkpoint. It
packages the public doctrine/build metadata needed by reviewers, partners, and
operators to verify the standalone A11oy substrate.

## What ships

- Source README, roadmap, changelog, and organization repository map.
- Deployment payload metadata from `deploy/`, including `zarf.yaml` and
  `MANIFEST.json` with per-file SHA-256 hashes.
- Standalone doctrine workspace metadata for:
  - `pnpm test:doctrine`
  - `pnpm typecheck:doctrine`
  - `pnpm build:doctrine`
  - `pnpm payload:verify`

## Canonical source

- GitHub: <https://github.com/szl-holdings/a11oy>
- DOI: <https://doi.org/10.5281/zenodo.20434276>
- Organization map: <https://github.com/szl-holdings/a11oy/blob/main/docs/org-repo-map.md>

## Operational status

The canonical release, CI, and provenance records remain in GitHub. Hugging Face
is used as a public discovery and distribution surface for the Series-A review
packet and operator payload metadata.
