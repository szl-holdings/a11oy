from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hugging_face_card_matches_canonical_payload_license() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    card = (ROOT / "huggingface" / "README.md").read_text(encoding="utf-8")
    payload_builder = (ROOT / "scripts" / "prepare_huggingface_payload.py").read_text(
        encoding="utf-8"
    )

    front_matter = card.split("---", 2)[1]
    assert "Apache License" in license_text
    assert "license: apache-2.0" in front_matter
    assert "license_name:" not in front_matter
    assert "license_link:" not in front_matter
    assert '("LICENSE", "LICENSE")' in payload_builder


def test_hugging_face_card_does_not_claim_model_weights() -> None:
    card = (ROOT / "huggingface" / "README.md").read_text(encoding="utf-8")

    assert "Weight-bearing model | No" in card
    assert "Transformers-loadable checkpoint | No" in card


def test_nested_test_results_card_matches_payload_license_without_relicensing_corpus() -> None:
    card = (ROOT / "huggingface" / "test-results" / "README.md").read_text(
        encoding="utf-8"
    )
    front_matter = card.split("---", 2)[1]

    assert "license: apache-2.0" in front_matter
    assert "license_name:" not in front_matter
    assert "license_link:" not in front_matter
    assert "does not grant redistribution rights" in card
    assert "row-level license and redistribution rights" in card
