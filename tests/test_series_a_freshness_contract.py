from __future__ import annotations

import a11oy_model_intel as model_intel


def test_roadmap_kernel_never_exports_internal_empty_freshness() -> None:
    card = model_intel._series_a_bind_card(
        model_intel.SERIES_A_ROADMAP_KERNELS[0],
        None,
        {"status": "empty"},
    )
    assert card["freshness"]["status"] == "unavailable"


def test_supported_public_freshness_is_preserved() -> None:
    spec = model_intel.SERIES_A_CARDS[0]
    live = {
        "repository_id": spec["hub_id"],
        "revision": "a" * 40,
        "file_count": 1,
        "weight_bearing_from_filenames": False,
        "has_adapter_from_filenames": False,
    }
    card = model_intel._series_a_bind_card(
        spec,
        live,
        {"status": "live"},
    )
    assert card["freshness"]["status"] == "live"
