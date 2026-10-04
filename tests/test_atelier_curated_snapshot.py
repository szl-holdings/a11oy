"""Guard the scope and identity of Atelier's embedded Hub selection."""

import json
import re
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "pages" / "atelier.html"


def test_atelier_catalog_is_a_dated_curated_selection() -> None:
    html = PAGE.read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="atelier-models">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    catalog = json.loads(match.group(1))

    models = catalog["models"]
    assert catalog["n"] == len(models) == 40
    assert len({model["hf"] for model in models}) == len(models)
    assert catalog["snapshot_date"] == "2026-09-29"
    assert re.fullmatch(
        r"https://github\.com/szl-holdings/a11oy/blob/[0-9a-f]{40}/pages/atelier\.html",
        catalog["snapshot_source"],
    )
    assert catalog["snapshot_source"] in html

    # The page offers a fixed selection, including software and empty cards.
    # It must not imply that these entries exhaust today's Hub inventory.
    assert "not a live or complete inventory" in html
    assert "not the current Hub inventory" in html
    for old_claim in (
        "Walk all 40",
        "The Hub still has forty model ids",
        "Forty models. Walk them.",
        "Forty models. Grid.",
        "the whole catalog as a walk",
    ):
        assert old_claim not in html
