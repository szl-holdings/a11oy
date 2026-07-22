# Security results

Status: PARTIALLY OPERATIONAL

Implemented and locally testable in this change: required provenance, explicit tenant
and scope, classification, consumer allowlist for restricted records, training-use human
review, WORKING-memory propagation denial, and SHA-256 digest shape.

Not yet evidenced: production tenant-isolation tests, secret-scanner recall, signed
receipt verification, authorization penetration tests, backup deletion, prompt-poisoning
resilience, and live connector least-privilege review. These remain release blockers for
claiming an operational ecosystem memory plane.
