# Retrieval architecture

Status: MODELED

1. Authenticate the caller and resolve tenant, role, and explicit scope.
2. Apply classification, consumer allowlist, retention, and deletion filters.
3. Retrieve candidates from lexical, vector, and graph indexes.
4. Rank by source trust, freshness, scope distance, evidence support, and relevance.
5. Surface contradictions and retractions beside the candidate claim.
6. Return citations, source revisions, confidence, and an auditable query receipt.

The system must fail closed when authorization or provenance is absent. Ranking
cannot convert an inferred claim into observed evidence. Context assembly has a
token budget, deduplicates by content digest, and separates facts from proposals.
