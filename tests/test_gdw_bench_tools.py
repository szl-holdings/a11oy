import importlib.util
import json
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_export_summary_and_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    dashboard = load_module(
        "gdw_dashboard_export",
        root / "benchmarks" / "gdw" / "dashboard_export.py",
    )
    document = {
        "persistence_integrity": {"ok": True},
        "requests_per_second": 10.0,
        "rows": [
            {
                "status": 200,
                "latency_ms": 10.0,
                "decision": "ACCEPT",
                "receipt_hash": "a" * 64,
                "scheduler_mode": "kda_local",
                "json_valid": True,
            },
            {
                "status": 200,
                "latency_ms": 20.0,
                "decision": "ACCEPT",
                "receipt_hash": "b" * 64,
                "scheduler_mode": "laguna_hybrid",
                "json_valid": True,
            },
        ],
    }
    summary = dashboard.build_summary(document)
    assert summary["acceptance"] == {
        "error_rate_under_1_percent": True,
        "json_valid": True,
        "receipts_complete": True,
        "persistence_clean": True,
    }
    assert summary["p95_ms"] > summary["p50_ms"]
    assert "universal throughput claim" in dashboard.render_html(summary)
