import time
from .evidence import EvidenceClass

REQUIRED_TERMS = ["tenant_isolated", "source_authorized", "provenance_complete",
                  "transform_chain_verified", "license_policy_clear", "split_disjoint",
                  "evaluation_passed", "runtime_witnessed", "rollback_available"]

def _flatten(sections):
    flat = {}
    for sec in (sections or {}).values():
        for ev in sec.get("evidence", []):
            flat[ev["name"]] = ev["class"]
    return flat

def evaluate(passport_dict):
    """Promotion predicate: eligible iff every required term is MEASURED.
    UNKNOWN, ABSTAIN, NOT_RUN, BLOCKED, or MISSING all block promotion.
    Honesty rule: absence of evidence can never promote a model."""
    flat = _flatten(passport_dict.get("sections", {}))
    passed, blocking = [], []
    for term in REQUIRED_TERMS:
        cls = flat.get(term)
        if cls == EvidenceClass.MEASURED:
            passed.append(term)
        else:
            blocking.append({"term": term, "class": cls or "MISSING"})
    return {"decision": "PROMOTED" if not blocking else "CANDIDATE",
            "eligible": not blocking, "passed": passed, "blocking": blocking,
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
