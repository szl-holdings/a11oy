# AGENTS.md

## Cursor Cloud specific instructions

This is a **specification/manifest repository** (no application source code). It contains OTEL span schemas, UDS bundle manifests, governance receipts, and pointer manifests.

### Testing

The only automated test is:

```sh
bash schemas/spans/test_graph_spans.sh
```

This validates the `schemas/spans/a11oy.graph.yaml` OTEL span schema (25 checks). Must be run from the repo root.

### Linting

Pre-commit hooks are configured (`.pre-commit-config.yaml`). Run with:

```sh
pre-commit run --all-files
```

**Known issue:** The `check-yaml` hook reports a parsing error on `schemas/spans/a11oy.graph.yaml` because the file uses YAML list items under a mapping key without the expected block-end marker. This is a pre-existing condition in the repository and does not affect the CI test script.

### CI checks (replicated locally)

The CI workflow (`.github/workflows/ci.yml`) validates:
1. Required governance files exist (`README.md`, `LICENSE`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `CITATION.cff`)
2. `CITATION.cff` contains the ORCID
3. `uds-bundle.yaml` manifest is present
4. Schema test passes (`bash schemas/spans/test_graph_spans.sh`)

### No build/run step

There is no application to build or run. The repo is purely declarative schemas and manifests.
