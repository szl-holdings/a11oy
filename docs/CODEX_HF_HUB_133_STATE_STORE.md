# Hub 1.33 and Xet 1.7 compatibility for the active state store

The primary image dependency file pins `huggingface_hub==1.33.0` and
`hf-xet==1.7.0`. The Dockerfile installs that file and the dependency audit
includes it, retaining one source for these pins. This upgrade leaves all
retired `gdw_durable_*` v1 modules unchanged and adds no SDK-version admission
gate to `a11oy_state_store.py` (ADR-0001).

`tests/test_state_store_hub_sdk.py` imports the installed Hub SDK and native Xet
extension. An inert HTTP transport and native-transfer fixture surround the
real SDK request construction and response handling. The tests exercise:

- private dataset admission, immutable revision reads and exact HEAD bytes;
- `create_commit(parent_commit=...)`, exact body binding and a single submission
  on uncertain outcomes; only HTTP 412 is a definite conflict;
- bucket byte/file upload, path metadata, recursive listing and download;
- HTTP 200 partial batch failures, size bounds and corrupted readback;
- real SQLite capture, logical fingerprint preservation, verified restoration
  and refusal to publish failed or corrupt snapshots.

Existing state-store tests retain the broader lease, CAS uncertainty, path,
integrity, handover and recovery invariants. CI runs those tests and the actual
SDK adapters with the complete primary runtime dependencies on Python 3.12 and
3.14. The image job separately reads every declared primary version from the
built image, imports the native extension, checks dependency consistency, then
performs its existing application smoke tests and SBOM checks.

These fixtures do not perform a real Xet transfer or prove provider CAS,
credential scope, durability or live recovery. Image build, exact-head checks,
normal protected publication and source-bound runtime verification remain
required. The upgrade does not create buckets/datasets, enroll writers, run
models, publish to the Hub, or grant production authority. Historical 1.31
evidence remains historical and returns HOLD for this different runtime.
