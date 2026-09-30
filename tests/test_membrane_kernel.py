"""Membrane kernel honesty. Locked 8 stay 8. Lambda stays advisory. Miss = ABSTAIN."""

from szl_membrane_kernel import (
    LOCKED_FORMULA_IDS,
    f1_replay_digest,
    f4_chain_is_dag,
    f7_fifo,
    f18_singleton,
    lambda_aggregate,
    retrieve_membrane,
)


def test_locked_set_is_exactly_eight():
    assert len(LOCKED_FORMULA_IDS) == 8
    assert LOCKED_FORMULA_IDS == ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")


def test_f1_replay_is_deterministic():
    a = f1_replay_digest("Atlas cutover accepted")
    b = f1_replay_digest("Atlas cutover accepted")
    c = f1_replay_digest("different event")
    assert a["replay_ok"] is True
    assert a["digest"] == b["digest"]
    assert a["digest"] != c["digest"]


def test_f4_station_walk_is_acyclic():
    dag = f4_chain_is_dag()
    assert dag["acyclic"] is True
    assert dag["edges"][0]["dst_i"] < dag["edges"][0]["src_i"]


def test_f7_fifo_prefix():
    assert f7_fifo(["SOW", "STAFF"])["order_ok"] is True
    assert f7_fifo(["STAFF", "SOW"])["order_ok"] is False


def test_f18_needs_six_of_ten():
    assert f18_singleton(6)["recoverable"] is True
    assert f18_singleton(5)["recoverable"] is False
    assert f18_singleton(6)["singleton_distance"] == 5


def test_lambda_is_geo_mean_and_capped_advisory():
    raw = lambda_aggregate([0.97, 0.97, 0.97, 0.97])
    assert raw > 0.96
    body = retrieve_membrane(
        "Invoice INV-4502 accepted",
        handles={
            "SOW": "sow_atlas_cutover",
            "STAFF": "roster_atlas",
            "EXCEPTION": "exc_atlas_none",
            "INVOICE": "inv-4502",
        },
    )
    assert body["lambda"]["status"] == "CONJECTURE_1_ADVISORY"
    assert body["lambda"]["can_authorize_action"] is False
    assert body["lambda"]["value"] <= 0.97
    assert body["emit_allow"] is False
    assert body["gate"]["kernel_allow"] is False


def test_empty_event_abstains_and_never_invents():
    body = retrieve_membrane("not enough")
    assert body["overall"] == "ABSTAIN"
    assert body["blocked_at"] == "SOW"
    assert body["membrane"]["SOW"]["handle"] is None
    assert body["certified_production_ready"] is False
    assert body["hickok_untouched"] is True
    assert body["locked_formula_count"] == 8
    assert body["ouroboros"]["receiptsInEqOut"] is True
    assert body["ouroboros"]["clamped"] is False


def test_full_handles_admit_presence_not_action():
    body = retrieve_membrane(
        "Invoice INV-4502 for Atlas cutover. Accepted work is on file.",
        handles={
            "SOW": "sow_atlas_cutover",
            "STAFF": "roster_atlas",
            "EXCEPTION": "exc_atlas_none",
            "INVOICE": "inv-4502",
        },
        numbers={"promised": 87000, "billed": 87000},
    )
    assert body["overall"] == "ADMIT"
    assert body["blocked_at"] is None
    assert body["emit_allow"] is False
    assert body["formulas"]["F11"]["conserved"] is True
    assert body["station_formula_map_class"] == "MODELED_APPLICABILITY"
    assert body["formulas"]["F12"]["caveat"].startswith("Additive fragment")
