# Ecosystem propagation

Status: MODELED

Propagation is an export/import transaction between explicit scopes. The exporter
selects an admitted record, checks license and classification, strips unauthorized
fields, and emits a signed manifest. The importer independently validates, maps the
record to its own tenant and project scope, and may admit, quarantine, or reject it.

No destination automatically inherits source trust, access, training permission, or
policy decisions. Public GitHub/Hugging Face release metadata may propagate broadly;
private operational memory, working context, credentials, and personal data may not.
Every successful transfer records source and destination digests plus a replayable receipt.
