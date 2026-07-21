# Brain row admission

`szl_brain_training_admission.py` is the authoritative bounded admission CLI.
It does not scrape, infer rights, train, publish, or promote a model. Raw Brain
inventory is ineligible by default.

Every candidate row must bind explicit source identity and immutable revision,
author/rightsholder and permission scope, signed PII clearance, freshness,
deduplication, held-out contamination analysis, immutable split history, and an
allowlisted signed review. `TRAIN` rows remain quarantined unless the operator
also supplies `--enable-train-admission`.

Trust is purpose-scoped and rooted. Source, rights, privacy, contamination,
review, split-ledger, policy-root, and terminal-artifact keys are distinct
authorities. Review evidence must be signed by the reviewed identity's
dedicated review key. The policy bundle is signed by a separate policy-root
key, the exact prior split-ledger envelope SHA-256 is pinned by policy, and a
different artifact key signs the terminal manifest. Public keys are parsed and
pinned once during policy construction; evidence verification never rereads a
mutable key path.

The CLI writes deterministic `admitted-train.jsonl`, `admitted-eval.jsonl`,
`quarantine.jsonl`, `admission-report.json`, and `admission-manifest.json`
artifacts. Each decision, report, ledger, and manifest is content-addressed.
Any admitted train or evaluation row requires a root-signed policy and an
Ed25519-signed terminal manifest binding the exact ledger head, report,
decision set, and output artifacts. Unrooted evaluation remains quarantine,
not a release-quality held-out set. A content hash alone is not authorization.
Quarantine records intentionally omit row content, row identifiers, source
locations, evidence paths, signer identities, and author/rightsholder fields.

The schemas in `schemas/` define candidate, decision, report, and artifact-manifest shapes.
Cryptographic and semantic verification remains implemented in the CLI and is
not replaced by JSON Schema validation.

The v2 trust-store and artifact-manifest contracts are the authorization path.
Older v1 receipts may be retained for inspection or migration evidence but are
not accepted as train authorization.

`szl_brain_snapshot.py` separately freezes the current raw M1 ledger before any
admission work. Its committed `raw-snapshot.json` binds 9,464 unique row IDs and
row payloads to the source-ledger SHA-256 and a domain-separated Merkle root.
The snapshot deliberately asserts zero rights, zero privacy clearance, zero
training authorization, and zero proof credit; it is an integrity anchor, not
an admission receipt.
