from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_holographic_shell_mounts_one_local_brain_frontier_asset_pair() -> None:
    html = read("static/3d/holographic.html")
    assert html.count('data-szl-brain-frontier-v7="style"') == 1
    assert html.count('data-szl-brain-frontier-v7="script"') == 1
    assert 'href="/assets/brain-frontier-v7.css"' in html
    assert 'src="/assets/brain-frontier-v7.js"' in html


def test_client_uses_one_same_origin_snapshot_without_persistence_or_telemetry() -> None:
    source = read("console/assets/brain-frontier-v7.js")
    assert 'const SNAPSHOT_PATH = "/assets/brain-frontier-v7.json"' in source
    assert "new URL(SNAPSHOT_PATH, window.location.origin)" in source
    assert "CROSS_ORIGIN_REJECTED" in source
    assert 'credentials: "same-origin"' in source
    assert 'cache: "no-store"' in source
    assert 'redirect: "error"' in source
    assert "HANDLES_ONLY" in source
    assert "DISCOVERED_REVIEW_REQUIRED" in source
    assert re.search(r"\bhandle\.content\b", source) is None
    assert "payload.content" not in source
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "WebSocket",
        "EventSource",
        "sendBeacon",
        "document.cookie",
        "eval(",
        "new Function",
        "gtag(",
        "mixpanel",
    ):
        assert forbidden not in source


def test_surface_is_accessible_mobile_safe_and_not_another_global_navigation() -> None:
    source = read("console/assets/brain-frontier-v7.js")
    css = read("console/assets/brain-frontier-v7.css")
    assert 'role", "dialog"' in source
    assert 'aria-modal", "true"' in source
    assert 'event.key === "Escape"' in source
    assert 'event.key !== "Tab"' in source
    assert "ResizeObserver" in source
    assert "prefers-reduced-motion: reduce" in css
    assert "forced-colors: active" in css
    assert "env(safe-area-inset-left)" in css
    assert "env(safe-area-inset-right)" in css
    assert "@media (max-width: 900px)" in css
    assert "@media (max-width: 560px)" in css
    assert "min-height: 44px" in css or "height: 44px" in css
    combined = source + "\n" + css
    assert "global-nav" not in combined
    assert "primary-nav" not in combined


def test_materialized_snapshot_is_handles_only_and_truth_bounded() -> None:
    payload = json.loads(read("console/assets/brain-frontier-v7.json"))
    assert payload["schema"] == "szl.a11oy.brain-frontier-holographic-v7/v1"
    assert payload["state"] == "SOURCE_BOUND_REVIEW_MEMORY"
    assert payload["selected_handle_count"] == len(payload["handles"]) == 72
    assert payload["formula_atlas"] == {
        "attributed_formula_count": 30,
        "executable_formula_count": 21,
        "quant_domain_count": 9,
        "locked_proven_formula_count": 8,
        "f_number_to_executable_mapping": "UNKNOWN_NOT_INFERRED",
        "lambda": "CONJECTURE_1",
    }
    assert payload["loop"] == ["OBSERVE", "ORIENT", "PROPOSE", "VERIFY", "HOLD"]
    assert payload["authority"]["public_content_access"] == "HANDLES_ONLY"
    assert payload["authority"]["training"] == "NONE"
    assert payload["authority"]["promotion"] == "NONE"
    assert payload["authority"]["execution"] == "NONE"
    assert payload["authority"]["provider_mutation"] == "NONE"
    assert payload["authority"]["private_graph_present"] is False
    assert payload["authority"]["raw_graph_nodes_admitted_to_gradients"] == 0
    assert payload["authority"]["human_review_required"] is True
    serialized = json.dumps(payload, sort_keys=True).lower()
    assert '"content"' not in serialized
    assert '"text"' not in serialized


def test_refresh_loop_can_only_open_a_review_pr() -> None:
    workflow = read(".github/workflows/brain-frontier-v7-refresh.yml")
    assert 'cron: "7 */2 * * *"' in workflow
    assert "scripts/materialize_brain_frontier_v7.py" in workflow
    assert "git diff --check" in workflow
    assert "gh pr create" in workflow
    assert "git push origin" in workflow
    assert "gh pr merge" not in workflow
    assert "provider" not in workflow.lower() or "provider_mutation" in workflow
    assert "contents: write" in workflow
    assert "pull-requests: write" in workflow


def test_assets_are_bounded_and_local() -> None:
    js = ROOT / "console" / "assets" / "brain-frontier-v7.js"
    css = ROOT / "console" / "assets" / "brain-frontier-v7.css"
    assert 5_000 < js.stat().st_size < 75_000
    assert 3_000 < css.stat().st_size < 35_000
    assert "@import" not in css.read_text(encoding="utf-8")
    assert "url(http" not in css.read_text(encoding="utf-8")
