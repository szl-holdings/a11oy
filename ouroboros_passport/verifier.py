from .evidence import receipt_digest

def verify(passport_dict):
    """Independent verification: recompute the digest, check evidence hygiene."""
    issues = []
    d = dict(passport_dict)
    claimed = d.pop("digest", None)
    recomputed = receipt_digest(d) if claimed is not None else None
    digest_ok = (claimed == recomputed) if claimed is not None else None
    if claimed is not None and claimed != recomputed:
        issues.append("digest mismatch: passport was modified after signing")
    for sec_name, sec in d.get("sections", {}).items():
        for ev in sec.get("evidence", []):
            if ev.get("class") == "MEASURED" and not ev.get("source"):
                issues.append("MEASURED evidence without source: " + str(ev.get("name")))
    return {"valid": not issues, "digest_ok": digest_ok, "issues": issues}
