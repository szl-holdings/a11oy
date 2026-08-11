from szl_frontier_index import _extract_label


def test_label_resolution_uses_backend_document_order_recursively() -> None:
    payload = {
        "evidence": {"data_label": "SAMPLE"},
        "label": "LIVE",
    }

    assert _extract_label(payload) == "SAMPLE"


def test_label_resolution_preserves_top_level_label_when_it_comes_first() -> None:
    payload = {
        "label": "MODELED",
        "evidence": {"data_label": "SAMPLE"},
    }

    assert _extract_label(payload) == "MODELED"
