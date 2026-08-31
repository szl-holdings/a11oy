# Memory admission policy

Status: PARTIALLY OPERATIONAL through schema and executable validation.

Admission is a policy decision, not a side effect of model output.

- `AUTO_PUBLIC`: deterministic public observations with a source locator and digest.
- `QUARANTINE`: unknown license, weak provenance, contradiction, or sensitive content.
- `HUMAN_REVIEWED`: training eligibility, cross-project propagation, decisions, and overrides.
- `REJECTED`: secrets, malicious instructions, unverifiable identity claims, or forbidden data.

The validator checks structure and hard invariants. A production admission service
must additionally scan secrets and personal data, verify source access and license,
mint a signed receipt, and append the decision without rewriting prior history.
