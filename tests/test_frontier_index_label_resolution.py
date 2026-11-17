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


def test_unknown_resolves_only_as_a_whole_label_value() -> None:
    assert _extract_label({"label": "UNKNOWN"}) == "UNKNOWN"
    assert _extract_label({"label": "theorem proved; unknown"}) is None
    assert _extract_label({"claim": "PRODUCTION-GRADE, risk unknown"}) is None
    # A real token earlier in the same value still wins over the word.
    assert _extract_label({"label": "MODELED, scale unknown"}) == "MODELED"


def test_router_status_unprobed_sovereign_node_resolves_to_unknown() -> None:
    """Pins a deliberate, disclosed change. /llm/router/status carries no top-level label;
    its only label-bearing field is the unprobed sovereign sub-node (state UNPROBED, label
    UNKNOWN, see szl_llm_registry). Once UNKNOWN joined the vocabulary, the catalog resolves
    the router surface from this endpoint as UNKNOWN instead of skipping it and falling
    through to MODELED from /router/active-flux-crossover/info. UNKNOWN is the weaker claim,
    so this is a downgrade, never an upgrade."""
    payload = {
        "hub": "a11oy",
        "local_nodes": [{
            "backend_id": "sovereign", "live": None, "reachable": None,
            "operational": False, "state": "UNPROBED", "label": "UNKNOWN",
        }],
    }
    assert _extract_label(payload) == "UNKNOWN"


def test_whatsnew_vocabulary_covers_every_catalog_label() -> None:
    """The whatsnew feed copies each catalog label verbatim, so every token the shared resolver
    can return (UNKNOWN included) must be representable in the feed's vocabulary."""
    import szl_frontier_index as fi
    import szl_whatsnew as wn

    assert set(fi.HONEST_LABELS) <= set(wn.HONEST_LABELS), (
        sorted(set(fi.HONEST_LABELS) - set(wn.HONEST_LABELS)))
    assert "UNKNOWN" in wn.HONEST_LABELS
