<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Curation Atlas public inventory admission - 2026-10-21

Evidence class: **MEASURED** for the commands and byte comparisons below.
Locally tested source base: `61a525cff7ba92e27098ada02b3a5af15b1541d4`.
PR base: `00a4ead4571cb1c7e49a4c3b2a661ec2b972a724` after the separately reviewed
vertical-publisher repair. That base update changes only
`.github/workflows/hf-publish-vertical-flagships.yml` and
`tests/test_hf_vertical_convergence.py`; all inventory code, fixtures, generators,
and the 17 qualified test files are byte-identical between those bases. The
499-test local suite was not rerun after the base update. Hosted checks must
qualify the final pushed head separately.

The public inventory collector rejected `SZLHOLDINGS/curation-atlas` because the
Space was observed but absent from the closed classification contract. This
repair adds one `INVENTORY_ONLY` row with `governedKeep: false`, disposition
`FOLD`, and policy source `docs/series-a/hf-space-keep-list.yaml`. `FOLD` records
the existing policy classification only: this change does not pause, delete,
change visibility, publish to, or otherwise modify that Space. The keep policy,
topology, schema, admission validators, and application runtime are unchanged.

## Bounded source association

At 2026-10-21T08:22:37Z, the six files below were fetched from the public
[GitHub backend at f680e5b](https://github.com/szl-holdings/curation-atlas/tree/f680e5baf5d4109013ab92c72b16940307abce89/backend)
and the public
[Space at e09116c](https://huggingface.co/spaces/SZLHOLDINGS/curation-atlas/tree/e09116c1e587f72fc3916ccdcd17cd0bd19011ba).
Each pair was byte-identical. GitHub reported the source commit signature as
verified. This establishes a source association, not runtime attestation or
authorization.

| File | Bytes | SHA256 on both sources |
| --- | ---: | --- |
| README.md | 1776 | `332e2bf24edeebd4436c87e920dd2c8704756d6fa6093810f2f2b7f53f1a86d3` |
| app.py | 5739 | `95e0d8f3f269ddc4ac4b8fcb2658720f6fc3dcdb38cd19b58bb6cefb43507a18` |
| audit.py | 24616 | `c31721f25e4bd132cf39a1ef3447e48fc8461d85b500aef51d1d66a0234a97bb` |
| Dockerfile | 371 | `f09a991ff3e329e6953c3267963f2c051c53f42352aee33b37876612a8fb314e` |
| requirements.txt | 47 | `84a881e9260d74fe5a6cd147d1de97a75f2c4478a917f7a9374f64e0ebf2a5ca` |
| .dockerignore | 48 | `bf61cbf7934665cfa488cb4fea1a71883389b3ad0b2e9f582f2a6651ba233967` |

The bounded public health GET returned `PROCESS_ALIVE`, the same declared
source revision, `sourceBinding: DECLARED`, and `upstreamReadiness: UNKNOWN`.
Provider metadata reported `RUNNING`; executable runtime bytes were not
attested. The organization-audit endpoint was not invoked.

## Native inventory and generated consumers

`python -B scripts/audit_huggingface_ecosystem.py` completed successfully at
2026-10-21T08:19:49Z. Its public-only anonymous inventory contains 48 model IDs,
37 dataset IDs, 39 Space IDs, and 14 kernel IDs. These are separate namespace
counts, not a unique-project or trained-model total. The independent native
`scripts.hf_public_inventory.collect('SZLHOLDINGS')` traversal reached the end
of every public author listing: one page each containing 48 models, 37 datasets,
38 Spaces, and 14 kernels, plus the separately verified public reserved README
Space. All namespace memberships matched. No authenticated or private inputs
were included; no model weights were downloaded.

Native candidate validation accepted freshness, source revisions, exact public
membership, classification, and model inference support. Both unclassified and
unobserved Space lists were empty. All 48 model records and all 14 kernel records
are unchanged. Existing public dataset/Space observations were refreshed;
`curation-atlas` is the sole new membership, with no removed memberships.

The following commands all exited 0:

```text
python -B scripts/build_ecosystem_stage_matrix.py
python -B scripts/render_public_estate_alignment.py
python -B scripts/build_model_pretraining_projection.py --write
python -B scripts/build_ecosystem_stage_matrix.py --check
python -B scripts/render_public_estate_alignment.py --check
python -B scripts/build_model_pretraining_projection.py --check
python -B scripts/audit_huggingface_ecosystem.py --check
```

The final live inventory check completed at 2026-10-21T08:24:11Z. This is a
point-in-time observation. A later provider change requires the existing
semantic-drift check before merge; there is no requirement to chase unrelated
mutable dataset commits. Model projection refresh is presentation consistency,
not model qualification. The unchanged keep-policy SHA256 is
`d05230627eb095fd61ac1fa9ae8c11056e39e8c44729645e88930d6261ee9e04`.

## Qualification and retained limitations

The following exact pytest command ran against a read-only source bind mount
in an isolated Linux container, with networking disabled, a temporary `/tmp`,
all capabilities dropped, and `no-new-privileges`. Environment:
`PYTHONPATH=/source:/source/tests`, `PYTHONDONTWRITEBYTECODE=1`, and
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

```text
python -B -m pytest -q -p no:cacheprovider --basetemp /tmp/pytest scripts/test_audit_huggingface_ecosystem.py tests/test_hf_public_inventory.py tests/test_public_estate_alignment.py tests/test_hf_inventory_refresh_branch.py tests/test_hf_inventory_refresh_sequence.py tests/test_model_inference_support.py tests/test_command_centre_view.py tests/test_model_pretraining.py tests/test_model_pretraining_blueprints.py tests/test_model_pretraining_container.py tests/test_model_pretraining_html_diagnostics.py tests/test_model_pretraining_live.py tests/test_model_pretraining_response_ownership.py tests/test_model_pretraining_shell.py tests/test_model_pretraining_source_pointers.py tests/test_model_pretraining_source_reference.py tests/test_model_pretraining_workflow_source.py
```

Result: **499 passed, 289 subtests passed, zero skips, exit 0**, in 108.72s;
two dependency deprecation warnings. The run completed at
2026-10-21T08:25:59Z. Image identity:
`sha256:f12adc874792ac446ec869df3153e3d60b7b843a27c23023276bc645628b907e`.
Log SHA256: `fddc3ce23ea7d2208b0976a923a7dc11367223f31165cdb4e3e756e5ec85aaa7`.
The test extends the existing inventory-only fixture loop, retaining unknown
classification, duplicate membership, and keeper-promotion rejection checks.

Additional native commands passed: `python -B scripts/test_audit_huggingface_ecosystem.py`
(22 tests) and `python -B -m unittest discover -s tests -p 'test_hf*inventory*.py' -v`
(104 tests). These overlap the Linux suite and are not additional unique tests.

Failed attempts remain in the local evidence bundle: the first host pytest
collection lacked the tests import path; native Windows model tests ran 226
tests with one symlink-privilege error; another Windows pytest run had 100
passing tests and 48 setup errors from denied access to its shared temporary
directory. The first Linux image lacked `jsonschema` and stopped during
collection. The successful isolated test image added pinned test dependencies
only; production requirements and test assertions were not changed to clear
these failures.

Operator-local evidence bundle: `outputs/a11oy-curation-inventory-20261021/`.
It retains command arrays, timestamps, exit codes, public pagination evidence,
source-file hashes, and all failed and successful logs. Source association
receipt `source-association.json` SHA256:
`1804b8a9bdee946cfd7691086e44a4626b0a36df1ae01075af3b794de0717c27`.
Live-check log SHA256:
`85d6ffd5973202e19934bb08f649ca3cde8d09ee0241c0742c44f441ebc619e3`.
This note records source qualification only; deployment, durable-state
readiness, and independent runtime verification are separate release steps.
