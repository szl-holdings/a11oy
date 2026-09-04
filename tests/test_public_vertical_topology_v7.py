"""Lock the public product topology and operational vertical upstreams."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_flagships_v4_impl.py"
ENTRYPOINT = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"


def load_publisher():
    spec = importlib.util.spec_from_file_location("vertical_v4_impl", PUBLISHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a11oy_front_door_folds_aegis_sentra_and_vessels_into_killinchu() -> None:
    text = LANDING.read_text(encoding="utf-8")
    assert "Killinchu / Defend" in text
    assert "Killinchu / Maritime" in text
    assert "https://szlholdings-killinchu.hf.space/defend" in text
    assert "https://szlholdings-killinchu.hf.space/elite/maritime" in text
    assert "https://huggingface.co/spaces/SZLHOLDINGS/sentra" not in text
    assert "Vessels / Killinchu" not in text


def test_independent_vertical_spaces_use_shared_source_bound_runtime() -> None:
    module = load_publisher()
    by_slug = {item["slug"]: item for item in module.FLAGSHIPS}
    base = "https://szlholdings-vertical-services.hf.space/api/verticals"
    assert by_slug["terra"]["upstream"] == f"{base}/terra/intelligence"
    assert by_slug["counsel"]["upstream"] == f"{base}/counsel/intelligence"
    assert by_slug["finance"]["upstream"] == f"{base}/finance/intelligence"
    assert by_slug["lyte"]["upstream"] == f"{base}/lyte/intelligence"
    assert "SZLHOLDINGS/vertical-services" in module.HTML_TEMPLATE


def test_public_writer_admits_only_independent_spaces() -> None:
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert 'PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")' in text
    assert 'FOLDED_INTO_KILLINCHU = ("sentra", "vessels")' in text
    assert 'KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"' in text


def test_topology_document_names_shared_runtime_not_duplicate_product() -> None:
    text = (ROOT / "docs" / "estate" / "PUBLIC_VERTICAL_TOPOLOGY.md").read_text(
        encoding="utf-8"
    )
    assert "`david-leads`" in text
    assert "capability or mission planes inside Killinchu" in text
    assert "shared source-bound engine runtime" in text
