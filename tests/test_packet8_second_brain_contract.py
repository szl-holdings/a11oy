# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACES = ("terra-assurance", "puriq-markets", "counsel-assurance")
RETIRED = ("aegis-assurance",)
SUBSTRATE_SHA = "ad2e04374717ef79dbf7dbb91aea5a8480ed10c3"
LOCKED = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
PUBLISHER = ROOT / ".github" / "scripts" / "publish_packet8_vertical_spaces.py"


def test_active_packet8_adapters_install_same_pinned_substrate_and_brain() -> None:
    canonical_app = None
    canonical_brain = None
    for name in SPACES:
        folder = ROOT / "huggingface" / "spaces" / name
        dockerfile = (folder / "Dockerfile").read_text(encoding="utf-8")
        app = (folder / "app.py").read_text(encoding="utf-8")
        brain = (folder / "szl_space_brain.py").read_text(encoding="utf-8")
        assert SUBSTRATE_SHA in dockerfile
        assert "szl_space_brain.py" in dockerfile
        assert "/api/second-brain" in app
        assert "/api/formulas" in app
        assert '"formula_authority":"NONE"' in brain or '"formula_authority": "NONE"' in brain
        assert '"Conjecture 1"' in brain
        for formula_id in LOCKED:
            assert formula_id in brain
        if canonical_app is None:
            canonical_app = app
            canonical_brain = brain
        else:
            assert app == canonical_app
            assert brain == canonical_brain
        py_compile.compile(str(folder / "app.py"), doraise=True)
        py_compile.compile(str(folder / "szl_space_brain.py"), doraise=True)


def test_packet8_second_brain_never_claims_production_or_formula_authority() -> None:
    for name in SPACES:
        folder = ROOT / "huggingface" / "spaces" / name
        brain = (folder / "szl_space_brain.py").read_text(encoding="utf-8")
        app = (folder / "app.py").read_text(encoding="utf-8")
        assert '"product_certified":False' in brain or '"product_certified": False' in brain
        assert '"proven_trust":False' in brain or '"proven_trust": False' in brain
        assert 'formula authority NONE' in app
        assert 'status":"OPEN"' in brain or '"status": "OPEN"' in brain


def test_aegis_source_is_preserved_but_cannot_be_republished() -> None:
    for name in RETIRED:
        assert (ROOT / "huggingface" / "spaces" / name).is_dir()
    publisher = PUBLISHER.read_text(encoding="utf-8")
    assert 'RETIRED_SPACE_IDS = frozenset({"SZLHOLDINGS/aegis-assurance"})' in publisher
    assert '"space_id": "SZLHOLDINGS/aegis-assurance"' not in publisher.split("SPACES = [", 1)[1]
    assert "retired Space reached Packet 8 publisher" in publisher
    py_compile.compile(str(PUBLISHER), doraise=True)
