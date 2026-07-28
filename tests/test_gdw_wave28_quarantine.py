from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave26_is_the_only_registered_gdw_router():
    source = (ROOT / "serve.py").read_text(encoding="utf-8")

    assert "from szl_gdw.api import register as _register_gdw" in source
    assert "_register_gdw(" in source
    assert "from routers import gdw_frontier" not in source
    assert '"state": "QUARANTINED"' in source
    assert '"reason": "GOVERNANCE_AND_OUTBOX_PROOF_REQUIRED"' in source


def test_runtime_image_excludes_the_quarantined_wave28_modules():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY web/packages/a11oy-core/py/szl_gdw/" in dockerfile
    assert "COPY gdw_attention.py gdw_workspace.py gdw_telemetry.py gdw_proofs.py ./" not in dockerfile
