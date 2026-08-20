from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "hf_universal_frontend_control.py"
SPEC = importlib.util.spec_from_file_location("hf_universal_frontend_control", MODULE_PATH)
assert SPEC and SPEC.loader
control = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(control)


def asset(files: tuple[str, ...], repo_id: str = "SZLHOLDINGS/example", repo_type: str = "space"):
    return control.Asset(repo_id=repo_id, repo_type=repo_type, sha="a" * 40, files=files)


def test_managed_card_preserves_frontmatter_and_is_idempotent() -> None:
    source = "---\ntags:\n- governed\n---\n# Existing\n"
    item = asset(("README.md",), repo_type="model")
    first = control.normalize_readme(item, source, False, "CARD_ONLY").decode()
    second = control.normalize_readme(item, first, False, "CARD_ONLY").decode()
    assert first == second
    assert first.startswith("---\ntags:\n- governed\n---\n")
    assert first.count(control.START) == 1
    assert first.count(control.END) == 1
    assert "hardcoded counters" in first
    assert "cryptographic signing" in first


def test_unbalanced_card_markers_fail_closed() -> None:
    item = asset(("README.md",), repo_type="dataset")
    with pytest.raises(control.ControlError):
        control.normalize_readme(item, control.START + "\n", False, "CARD_ONLY")


def test_static_html_adapter_adds_viewport_and_mobile_contract_once() -> None:
    source = "<!doctype html><html><head><title>x</title></head><body><main>x</main></body></html>"
    first = control._inject_style(source)
    second = control._inject_style(first)
    assert first == second
    assert first.count('name="viewport"') == 1
    assert first.count(control.STYLE_START) == 1
    assert "min-height: 44px" in first
    assert "prefers-reduced-motion" in first
    assert "overflow-wrap: anywhere" in first


def test_static_html_adapter_rejects_ambiguous_head() -> None:
    with pytest.raises(control.ControlError):
        control._inject_style("<html><body>no head</body></html>")


def test_react_adapter_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("package.json", "src/main.tsx"))
    contents = {"src/main.tsx": "import React from 'react';\nexport const App = () => <main />;\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._react_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)
    assert rendered["src/main.tsx"].decode().count("import './szl-universal.css';") == 1
    assert control.STYLE_START in rendered["src/szl-universal.css"].decode()

    contents["src/main.tsx"] = rendered["src/main.tsx"].decode()
    ops2, blockers2 = control._react_ops(object(), item, None)
    assert not blockers2
    assert dict(ops2)["src/main.tsx"] == rendered["src/main.tsx"]


def test_gradio_adapter_adds_local_css_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {"app.py": "import gradio as gr\nwith gr.Blocks() as demo:\n    gr.Markdown('ok')\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._gradio_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)
    app = rendered["app.py"].decode()
    assert "from pathlib import Path" in app
    assert "_SZL_UNIVERSAL_CSS" in app
    assert "gr.Blocks(css=_SZL_UNIVERSAL_CSS, " in app
    assert control.STYLE_START in rendered["szl_universal.css"].decode()


def test_gradio_existing_css_requires_source_native_review(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {"app.py": "import gradio as gr\nwith gr.Blocks(css='body{}') as demo:\n    pass\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._gradio_ops(object(), item, None)
    assert not ops
    assert blockers and "source-specific" in blockers[0]


def test_streamlit_adapter_injects_after_single_line_page_config(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {"app.py": "import streamlit as st\nst.set_page_config(page_title='x')\nst.title('x')\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._streamlit_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)
    app = rendered["app.py"].decode()
    assert app.index("st.set_page_config") < app.index("szl-universal-frontend:inject") < app.index("st.title")
    assert app.count("szl-universal-frontend:inject") == 1


def test_streamlit_multiline_page_config_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {"app.py": "import streamlit as st\nst.set_page_config(\n    page_title='x',\n)\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._streamlit_ops(object(), item, None)
    assert not ops
    assert blockers and "single-line" in blockers[0]


def test_protected_spaces_are_source_bound() -> None:
    for repo_id in sorted(control.PROTECTED_SPACES):
        bound, reason = control._source_bound(object(), asset(tuple(), repo_id=repo_id), None)
        assert bound is True
        assert reason


def test_report_cannot_be_complete_with_blockers() -> None:
    decisions = [
        control.Decision("SZLHOLDINGS/a", "model", "a" * 40, "CURRENT"),
        control.Decision("SZLHOLDINGS/b", "space", "b" * 40, "SOURCE_BOUND_AUDIT_ONLY", blockers=["source-bound"]),
    ]
    report = control.build_report("SZLHOLDINGS", decisions, False, False)
    assert report["complete"] is False
    assert report["blocked_assets"] == ["SZLHOLDINGS/b"]


def test_no_payload_mutation_contract_in_controller_source() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "update_repo_visibility",
        "request_space_hardware",
        "add_space_secret",
        "delete_repo(",
        "CommitOperationDelete",
    )
    assert not any(token in source for token in forbidden)
    assert "parent_commit=asset.sha" in source
    assert "create_pr=True" in source
