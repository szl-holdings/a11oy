"""Card presentation preserves the publisher's scientific and runtime boundaries."""
from tests.test_hf_publish_vertical_flagships_v4 import load_overlay


def test_generated_cards_keep_exact_front_matter_and_original_body():
    module = load_overlay()
    assert module._BASE.readme is module.readme
    revised = set()
    for item in module.FLAGSHIPS:
        actual = module.readme(item)
        original = module._base_readme(item)
        if item["slug"] not in {"terra", "sentra", "counsel", "finance"}:
            assert actual == original
            continue
        revised.add(item["slug"])
        boundary = original.index("\n---\n", 4) + len("\n---\n")
        assert actual[:boundary] == original[:boundary]
        preserved = actual.split("<!-- szl:preserved-source-body:start -->\n", 1)[1].rsplit(
            "\n<!-- szl:preserved-source-body:end -->", 1
        )[0]
        assert preserved == original[boundary:]
        visible = actual[boundary:].split("<details>", 1)[0]
        assert "https://huggingface.co/spaces/SZLHOLDINGS/szl-command-lab" in visible
        assert "width=\"112\"" in visible
        assert "Capability-specific evidence required" in visible
        assert "This card grants no action authority" in visible
        assert "<table" not in visible and "width=\"100%\"" not in visible
    assert revised == {"terra", "sentra", "counsel", "finance"}
