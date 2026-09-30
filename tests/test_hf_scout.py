# SPDX-License-Identifier: Apache-2.0
from szl_hf_scout import (
    adjacent_protocols,
    classify_hub_row,
    conformal_abstain,
    hash_catalog,
    license_kind,
    likes_are_not_live,
    refuse_kernel_promotion,
    scout_status,
)


def test_kernel_card_not_live():
    k = classify_hub_row({"id": "SZLHOLDINGS/szl-maskmod", "library_name": "kernels", "downloads": 36, "likes": 0, "tags": ["license:apache-2.0"]})
    assert k["kind"] == "KERNEL_CARD"
    assert k["live"] is False
    assert k["promote"] is False


def test_weights_not_promoted():
    w = classify_hub_row({"id": "SZLHOLDINGS/SZL-Khipu-1.5B", "pipeline_tag": "text-generation", "library_name": "transformers", "downloads": 2982, "tags": ["license:apache-2.0"]})
    assert w["kind"] == "WEIGHTS_CARD"
    assert w["promote"] is False


def test_nc_forbidden():
    assert license_kind("cc-by-nc-4.0")["reuse"] == "FORBIDDEN_REUSE"


def test_apache_open_card():
    assert license_kind("apache-2.0")["reuse"] == "OPEN_SOURCE_CARD"


def test_likes_not_live():
    assert likes_are_not_live(15762, 7365368)["live"] is False


def test_conformal_abstains_without_calibration():
    out = conformal_abstain()
    assert out["abstain"] is True
    assert out["coverage_claim"] is False


def test_refuse_empty_v1():
    r = refuse_kernel_promotion("SZLHOLDINGS/szl-maskmod", git_has_v1=False, native_load=False)
    assert r["mint_v1"] is False
    assert r["decision"] == "BLOCKED"


def test_catalog_unsigned():
    cat = hash_catalog([{"id": "Qwen/Qwen3.8-27B", "likes": 15762, "tags": ["license:apache-2.0"]}])
    assert cat["signed"] is False
    assert cat["hash"].startswith("sha3-256:")
    assert cat["agi_claim"] is False


def test_adjacent_named_not_copied():
    ids = {a["id"] for a in adjacent_protocols()}
    assert "agent-receipts/obsigna" in ids


def test_status_hold():
    s = scout_status()
    assert s["agi_claim"] is False
    assert s["estate_gate"] == "HOLD"
    assert s["weight_download"] is False
