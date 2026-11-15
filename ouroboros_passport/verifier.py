from .evidence import EvidenceClass, receipt_digest


def verify(passport_dict):
    """Independently verify digest and evidence hygiene.

    A passport without a digest, with an unknown evidence class, or with
    measured evidence that has no source is invalid. The verifier never
    promotes a model; it only reports whether the passport is structurally
    trustworthy.
    """
    issues = []
    if not isinstance(passport_dict, dict):
        return {"valid": False, "digest_ok": False, "issues": ["passport is not an object"]}

    d = dict(passport_dict)
    claimed = d.pop("digest", None)
    if not isinstance(claimed, str) or not claimed:
        digest_ok = False
        issues.append("missing digest")
    else:
        recomputed = receipt_digest(d)
        digest_ok = claimed == recomputed
        if not digest_ok:
            issues.append("digest mismatch: passport was modified after signing")

    sections = d.get("sections", {})
    if not isinstance(sections, dict):
        issues.append("sections must be an object")
        sections = {}

    for sec_name, sec in sections.items():
        if not isinstance(sec, dict):
            issues.append("section is not an object: " + str(sec_name))
            continue
        evidence = sec.get("evidence", [])
        if not isinstance(evidence, list):
            issues.append("section evidence must be a list: " + str(sec_name))
            continue
        for ev in evidence:
            if not isinstance(ev, dict):
                issues.append("evidence is not an object: " + str(sec_name))
                continue
            name = str(ev.get("name", ""))
            cls = ev.get("class")
            if cls not in EvidenceClass.ALL:
                issues.append("unknown evidence class for " + name + ": " + str(cls))
            if cls == EvidenceClass.MEASURED and not ev.get("source"):
                issues.append("MEASURED evidence without source: " + name)

    return {"valid": not issues, "digest_ok": digest_ok, "issues": issues}
