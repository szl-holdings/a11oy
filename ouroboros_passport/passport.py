import json
from .schema import Passport
from .evidence import Evidence, now_utc, receipt_digest
from .promotion import REQUIRED_TERMS

def build_from_training_report(report, dataset_digest, tenant="szl-estate", revision="r1"):
    """Assemble an honest passport from a training receipt.
    Everything measured in the receipt is recorded as MEASURED.
    Every promotion term not yet measured is explicitly UNKNOWN.
    The passport never claims more than its receipts prove."""
    run = report.get("run", "unknown")
    model_id = report.get("candidate") or ("szl/" + run)
    sections = {}
    sections["training"] = {"evidence": [
        Evidence.measured("training_completed", True, source="training_report.json").to_dict(),
        Evidence.measured("base_model", report.get("base", "unknown"), source="training_report.json").to_dict(),
        Evidence.measured("corpus_examples", report.get("corpus_examples", 0), source="training_report.json").to_dict(),
        Evidence.measured("method", report.get("method", "unknown"), source="training_report.json").to_dict(),
        Evidence.measured("wall_hours", report.get("wall_hours", 0), source="training_report.json").to_dict(),
    ]}
    sections["dataset"] = {"evidence": [
        Evidence.measured("dataset", report.get("dataset", "unknown"), source="training_report.json").to_dict(),
        Evidence.measured("dataset_digest", dataset_digest, source=report.get("dataset", "")).to_dict(),
    ]}
    sections["provenance"] = {"evidence": [
        Evidence.measured("curriculum_origin", report.get("curriculum", "unknown"), source="training_report.json").to_dict(),
        Evidence.measured("training_receipt_digest", receipt_digest(report), source="training_report.json").to_dict(),
    ]}
    promotion_ev = [Evidence.measured("training_completed", True, source="training_report.json").to_dict()]
    for term in REQUIRED_TERMS:
        promotion_ev.append(Evidence.unknown(term).to_dict())
    sections["promotion"] = {"evidence": promotion_ev}
    p = Passport(model_id=model_id, tenant=tenant, sections=sections,
                 parents=[receipt_digest(report)], created_at=now_utc(), revision=revision)
    return p.to_dict()
