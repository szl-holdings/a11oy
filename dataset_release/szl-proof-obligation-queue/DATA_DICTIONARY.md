# Data dictionary

## Proof-obligation queue

Each line of `data/proof-obligation-queue.jsonl` is one JSON object conforming
to `schemas/proof-obligation-record.schema.json`.

| Field | Meaning |
|---|---|
| `queue_id` | Stable queue identifier derived from the namespace-scoped source record ID. |
| `record_id` | Original crosswalk record ID. |
| `formula_id` | Formula label within its namespace; not globally unique. |
| `formula_namespace` | Namespace required to interpret the formula ID. |
| `canonical_name` | Name recorded by the source crosswalk. |
| `claim_sha256` | Content hash of the source claim. |
| `resolved_status` | One of `KERNEL_ACCEPTED`, `CONDITIONAL`, `OPEN`, or `REFUTED`. |
| `obligation_state` | Derived review state; it does not change the source proof status. |
| `queue_membership` | `ACTION_REQUIRED` or `AUDIT_ONLY`. |
| `required_actions` | Deterministic next evidence obligations derived from source status and reasons. |
| `status_reasons` | Original source reasons supporting the resolved status. |
| `lean_reference` | Declared Lean identifier and whether that exact reference was observed. |
| `namespace_collision` | Explicit same-ID/different-statement relation, when present. |
| `proof_transfer_allowed` | Always false in version 0.1.0. |
| `split` | Always `HOLDOUT`. |
| `training_eligible` | Always false. |
| `receipt_scope` | Source artifact, crosswalk, and row receipt hashes. |
| `queue_record_sha256` | SHA-256 over the canonical JSON object before this field is added. |

## Derived obligation states

- `SATISFIED_LOCAL_ITEM_BINDING` preserves a source `KERNEL_ACCEPTED` status
  but keeps the record in the audit trail.
- `ACTION_REQUIRED_CONDITIONAL` requires the recorded condition to be resolved
  before any proof claim changes.
- `ACTION_REQUIRED_OPEN` requires a kernel-checked proof or retention of the
  open status.
- `CONFLICT_RECORDED_REFUTED` preserves refutation evidence and blocks a proof
  claim.

## Brain summary

`data/brain-evidence-summary.json` reports the source pilot protocol, receipts,
admission counts, summary metrics, and limitations. It deliberately excludes
all raw-node text, canonical document text, query text, and per-query results.
The source label `MEASURED_LOCAL_PILOT` is preserved and does not imply
independent replication or external validity.

