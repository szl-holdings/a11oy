import time
from .evidence import EvidenceClass
from .verifier import verify

REQUIRED_TERMS = ["tenant_isolated", "source_authorized", "provenance_complete",
                  "transform_chain_verified", "license_policy_clear", "split_disjoint",
                  "evaluation_passed", "runtime_witnessed", "rollback_available"]

def _flatten(sections):
    flat = {}
    for sec in sections.values():
        for ev in sec.get("evidence", []):
            flat.setdefault(ev["name"], []).append(ev)
    return flat

def evaluate(passport_dict):
    """Evaluate supplied evidence, without authorizing a deployment.

    Integrity must verify and each required term must occur exactly once as
    MEASURED with the boolean value True. A measured failure cannot promote.
    Digest integrity does not authenticate the issuer or the source receipts.
    """
    verification = verify(passport_dict)
    passed, blocking = [], []
    if not verification["valid"]:
        blocking.append({"term": "passport_integrity", "class": EvidenceClass.BLOCKED,
                         "issues": verification["issues"]})
    else:
        flat = _flatten(passport_dict.get("sections", {}))
        for term in REQUIRED_TERMS:
            observations = flat.get(term, [])
            if not observations:
                blocking.append({"term": term, "class": "MISSING"})
            elif len(observations) != 1:
                blocking.append({"term": term, "class": EvidenceClass.BLOCKED,
                                 "reason": "duplicate evidence"})
            else:
                ev = observations[0]
                cls = ev["class"]
                if cls != EvidenceClass.MEASURED:
                    blocking.append({"term": term, "class": cls})
                elif ev.get("value") is not True:
                    blocking.append({"term": term, "class": cls,
                                     "reason": "value is not boolean true"})
                else:
                    passed.append(term)
    return {"decision": "PROMOTED" if not blocking else "CANDIDATE",
            "eligible": not blocking, "passed": passed, "blocking": blocking,
            "verification": verification,
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
