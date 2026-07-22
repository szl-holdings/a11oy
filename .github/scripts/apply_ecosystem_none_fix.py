#!/usr/bin/env python3
"""Apply a null-safe CHAPAQ read-only contract fix and regression."""
from pathlib import Path

source_path = Path("szl_ecosystem_routes.py")
source = source_path.read_text(encoding="utf-8")
old = '''    chapaq_lambda = None
    if chapaq and isinstance(chapaq.get("data", {}).get("lambda_value"), (int, float)):
        chapaq_lambda = float(chapaq["data"]["lambda_value"])
'''
new = '''    chapaq_data = chapaq.get("data") if isinstance(chapaq, dict) else None
    chapaq_lambda = None
    if isinstance(chapaq_data, dict) and isinstance(
        chapaq_data.get("lambda_value"), (int, float)
    ):
        chapaq_lambda = float(chapaq_data["lambda_value"])
'''
if source.count(old) != 1:
    raise SystemExit(f"expected one CHAPAQ lambda block, found {source.count(old)}")
source_path.write_text(source.replace(old, new, 1), encoding="utf-8")

test_path = Path("tests/test_command_center_readonly_contract.py")
tests = test_path.read_text(encoding="utf-8")
marker = '''def test_ecosystem_gets_contain_no_hidden_posts():
'''
regression = '''def test_null_chapaq_result_remains_read_only_and_non_crashing(monkeypatch):
    ecosystem = importlib.import_module("szl_ecosystem_routes")

    def observed(url: str, timeout: float = 12.0):
        if url.endswith("/api/a11oy/v1/honest"):
            return {
                "doctrine_lock": {
                    "locked_formula_ids": ecosystem.LOCKED8,
                    "locked_formula_count": 8,
                }
            }
        if url.endswith("/api/a11oy/v1/lambda"):
            return {"lambda": 0.7, "axes": [{"score": 0.95}]}
        if url.endswith("/api/killinchu/v1/gov/chapaq-verdict"):
            return None
        return None

    monkeypatch.setattr(ecosystem, "_get_json", observed)
    board = ecosystem.build_kpi_board("a11oy")
    assert board["chapaq_verdict"] is None
    assert board["chapaq_source"].startswith("NOT_EVALUATED")


'''
if marker not in tests:
    raise SystemExit("test insertion marker missing")
if "test_null_chapaq_result_remains_read_only_and_non_crashing" not in tests:
    tests = tests.replace(marker, regression + marker, 1)
test_path.write_text(tests, encoding="utf-8")
print("null-safe CHAPAQ repair applied")
