import json
import re

from .schema import Passport
from .evidence import Evidence, now_utc, receipt_digest
from .promotion import REQUIRED_TERMS

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _report_evidence(report, name, key, *, source="training_report.json"):
    if key not in report:
        return Evidence.unknown(name).to_dict()
    value = report.get(key)
    if value in (None, "", "unknown"):
        return Evidence.unknown(name).to_dict()
    return Evidence.measured(name, value, source=source).to_dict()


def _dataset_evidence(report, dataset_digest):
    if not isinstance(dataset_digest, str) or not _HEX64.fullmatch(dataset_digest):
        return Evidence.unknown("dataset_digest").to_dict()
    return Evidence.measured(
        "dataset_digest",
        dataset_digest,
        source=report.get("dataset", "dataset_manifest"),
    ).to_dict()


def build_from_training_report(report, dataset_digest, tenant="szl-estate", revision="r1"):
    """Assemble an honest passport from a training receipt.

    A field is MEASURED only when the source report explicitly contains a
    non-empty value. Missing fields remain UNKNOWN and therefore cannot
    satisfy promotion. A tenant and a content-addressed dataset digest are
    required for a usable passport.
    """
    if not isinstance(report, dict):
        raise ValueError("training report must be an object")
    if not isinstance(tenant, str) or not tenant.strip():
        raise ValueError("tenant is required")
    run = report.get("run", "unknown")
    model_id = report.get("candidate") or ("szl/" + str(run))
    sections = {}
    sections["training"] = {"evidence": [
        _report_evidence(report, "training_completed", "training_completed"),
        _report_evidence(report, "base_model", "base"),
        _report_evidence(report, "corpus_examples", "corpus_examples"),
        _report_evidence(report, "method", "method"),
        _report_evidence(report, "wall_hours", "wall_hours"),
    ]}
    sections["dataset"] = {"evidence": [
        _report_evidence(report, "dataset", "dataset"),
        _dataset_evidence(report, dataset_digest),
    ]}
    sections["provenance"] = {"evidence": [
        _report_evidence(report, "curriculum_origin", "curriculum"),
        Evidence.measured(
            "training_receipt_digest",
            receipt_digest(report),
            source="training_report.json",
        ).to_dict(),
    ]}
    promotion_ev = []
    for term in REQUIRED_TERMS:
        promotion_ev.append(Evidence.unknown(term).to_dict())
    sections["promotion"] = {"evidence": promotion_ev}
    return Passport(
        model_id=model_id,
        tenant=tenant.strip(),
        sections=sections,
        parents=[receipt_digest(report)],
        created_at=now_utc(),
        revision=revision,
    ).to_dict()
