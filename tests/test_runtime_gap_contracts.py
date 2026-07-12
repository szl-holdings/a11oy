from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

import szl_be_hardening
from scripts.audit_optional_runtime_imports import audit


ROOT = Path(__file__).resolve().parents[1]


def test_openapi_conventional_path_is_exact_alias_of_curated_schema(tmp_path):
    app = FastAPI(title="runtime-gap-test", version="1", openapi_url=None,
                  docs_url=None, redoc_url=None)
    report = szl_be_hardening.harden(
        app, organ="a11oy", khipu_path=str(tmp_path / "khipu.sqlite3"))
    assert any("alias:/openapi.json" in item for item in report["registered"])

    client = TestClient(app)
    canonical = client.get("/api/a11oy/openapi.json")
    alias = client.get("/openapi.json")
    assert canonical.status_code == alias.status_code == 200
    assert alias.json() == canonical.json()
    assert alias.json()["openapi"].startswith("3.")
    assert "/api/a11oy/v1/be/khipu/verify" in alias.json()["paths"]


def test_optional_runtime_audit_includes_formula_ops_without_claiming_it_live():
    report = audit(ROOT)
    modules = {row["module"]: row for row in report["modules"]}
    formula_ops = modules["szl_formula_ops"]
    assert formula_ops["serve_reference"] is True
    assert formula_ops["source_present"] is False
    assert formula_ops["status"] == "OPTIONAL-ABSENT"


def test_requirements_crypto_pin_matches_explicit_image_pin():
    requirement = "cryptography==49.0.0"
    assert requirement in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert f'"{requirement}"' in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_hub_preserves_conventional_openapi_alias_and_targets_curated_path():
    source = (ROOT / "szl_hub.py").read_text(encoding="utf-8")
    assert '_default_docs_paths = {"/docs", "/redoc"}' in source
    assert 'app.openapi_url = "/api/a11oy/openapi.json"' in source
    assert 'openapi_url="/api/a11oy/openapi.json"' in source
