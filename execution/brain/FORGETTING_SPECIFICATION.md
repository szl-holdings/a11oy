# Forgetting specification

Status: MODELED

Forgetting is a governed lifecycle operation with evidence. Expiration, user deletion,
source retraction, legal hold, scope closure, and supersession are distinct events.

1. Authorize the request and record its scope.
2. Write a tombstone referencing the original digest without copying protected content.
3. Remove the record from lexical, vector, graph, cache, and context indexes.
4. Block future propagation and training eligibility.
5. Apply the declared backup-retention policy and record unavoidable delay.
6. Mint a deletion receipt and verify the record is no longer retrievable.

Legal holds suspend deletion but must be explicit, time-scoped, and auditable. A hidden
model-weight contribution cannot be claimed deleted; training remains disabled until a
separate reproducible unlearning or rebuild process exists.
