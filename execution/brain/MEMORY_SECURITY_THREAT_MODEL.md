# Memory security threat model

Status: MODELED; production penetration results are not yet available.

| Threat | Primary control | Required evidence |
|---|---|---|
| Cross-tenant retrieval | tenant-bound filters and deny-by-default policy | negative isolation tests |
| Prompt or memory poisoning | quarantine, provenance, trust tiers, human review | adversarial corpus results |
| Secret ingestion | pre-admission secret scanning and redaction | seeded-secret tests |
| Unauthorized propagation | signed policy decision and consumer allowlist | replayable propagation receipt |
| Record tampering | canonical digest, append-only history, signed receipts | independent digest verification |
| Deletion bypass | tombstones, index purge, cache purge, backup policy | deletion propagation test |
| Stale evidence | validity intervals and source-revision checks | freshness benchmark |

The model and retrieval layer receive only authorized memory. Tool output is untrusted
input. No memory record can grant permissions or change governance policy by itself.
