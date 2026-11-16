import copy

import pytest

from ouroboros_passport.evidence import Evidence, EvidenceClass, receipt_digest
from ouroboros_passport.hf_bind import bind
from ouroboros_passport.passport import build_from_training_report
from ouroboros_passport.promotion import REQUIRED_TERMS, evaluate
from ouroboros_passport.verifier import verify


def report(**extra):
    value = {
        "run": "test-run",
        "base": "Qwen/Qwen3-1.7B",
        "corpus_examples": 12,
        "dataset": "fixture-dataset",
        "wall_hours": 0.2,
        "method": "LoRA",
        "candidate": "SZLHOLDINGS/fixture",
        "curriculum": "fixture",
        "training_completed": True,
    }
    value.update(extra)
    return value


def test_built_passport_has_stable_digest_and_verifies():
    passport = build_from_training_report(report(), "a" * 64, tenant="tenant-1")
    assert verify(passport) == {
        "valid": True,
        "digest_ok": True,
        "issues": [],
    }
    assert passport["tenant"] == "tenant-1"
    assert passport["digest"] == receipt_digest({k: v for k, v in passport.items() if k != "digest"})


def test_tampered_or_missing_digest_is_invalid():
    passport = build_from_training_report(report(), "a" * 64)
    tampered = copy.deepcopy(passport)
    tampered["model_id"] = "SZLHOLDINGS/tampered"
    result = verify(tampered)
    assert result["valid"] is False
    assert "digest mismatch" in " ".join(result["issues"])

    missing = copy.deepcopy(passport)
    missing.pop("digest")
    result = verify(missing)
    assert result["valid"] is False
    assert result["digest_ok"] is False
    assert "missing digest" in result["issues"]


def test_unknown_evidence_class_and_measured_without_source_are_invalid():
    passport = build_from_training_report(report(), "a" * 64)
    passport["sections"]["training"]["evidence"].append(
        {"name": "bad", "class": "INVENTED"}
    )
    passport["sections"]["training"]["evidence"].append(
        {"name": "unproven", "class": EvidenceClass.MEASURED}
    )
    passport["digest"] = receipt_digest({k: v for k, v in passport.items() if k != "digest"})
    result = verify(passport)
    assert result["valid"] is False
    assert any("unknown evidence class" in issue for issue in result["issues"])
    assert any("MEASURED evidence without source" in issue for issue in result["issues"])


def test_missing_training_fields_remain_unknown():
    passport = build_from_training_report({"run": "partial"}, "a" * 64)
    classes = {
        ev["name"]: ev["class"]
        for section in passport["sections"].values()
        for ev in section["evidence"]
    }
    assert classes["base_model"] == EvidenceClass.UNKNOWN
    assert classes["method"] == EvidenceClass.UNKNOWN
    assert classes["corpus_examples"] == EvidenceClass.UNKNOWN
    assert classes["training_completed"] == EvidenceClass.UNKNOWN
    assert classes["dataset_digest"] == EvidenceClass.MEASURED
    assert evaluate(passport)["decision"] == "CANDIDATE"


def test_invalid_tenant_or_dataset_digest_is_rejected_or_blocked():
    with pytest.raises(ValueError, match="tenant"):
        build_from_training_report(report(), "a" * 64, tenant="")
    passport = build_from_training_report(report(), "not-a-digest")
    dataset_digest = next(
        ev for ev in passport["sections"]["dataset"]["evidence"]
        if ev["name"] == "dataset_digest"
    )
    assert dataset_digest["class"] == EvidenceClass.UNKNOWN
    assert evaluate(passport)["decision"] == "CANDIDATE"


def test_all_required_promotion_terms_are_required():
    sections = {"promotion": {"evidence": [
        Evidence.measured(term, True, source="fixture").to_dict()
        for term in REQUIRED_TERMS
    ]}}
    passport = {
        "passport_version": "ouroboros-passport/0.1",
        "model_id": "fixture",
        "tenant": "tenant-1",
        "revision": "r1",
        "created_at": "2026-01-01T00:00:00Z",
        "parents": [],
        "sections": sections,
    }
    passport["digest"] = receipt_digest(passport)
    decision = evaluate(passport)
    assert decision["decision"] == "PROMOTED"
    assert decision["eligible"] is True
    assert decision["blocking"] == []
    assert len(decision["passed"]) == len(REQUIRED_TERMS)


def test_hf_binder_is_importable_without_running_a_write():
    assert callable(bind)
