from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


def test_gradio_adapter_preserves_python_preamble(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {
        "app.py": (
            "#!/usr/bin/env python3\n"
            "# -*- coding: utf-8 -*-\n"
            '"""Application module."""\n'
            "from __future__ import annotations\n"
            "import gradio as gr\n"
            "with gr.Blocks() as demo:\n"
            "    gr.Markdown('ok')\n"
        )
    }
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._gradio_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)["app.py"].decode()
    assert rendered.startswith("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n")
    assert rendered.index('"""Application module."""') < rendered.index("from __future__ import annotations")
    assert rendered.index("from __future__ import annotations") < rendered.index("from pathlib import Path")
    compile(rendered, "app.py", "exec")


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


def test_streamlit_adapter_preserves_docstring_and_future_import(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {
        "app.py": (
            '"""Application module."""\n'
            "from __future__ import annotations\n"
            "import streamlit as st\n"
            "st.set_page_config(page_title='x')\n"
            "st.title('x')\n"
        )
    }
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._streamlit_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)["app.py"].decode()
    assert rendered.index('"""Application module."""') < rendered.index("from __future__ import annotations")
    assert rendered.index("from __future__ import annotations") < rendered.index("from pathlib import Path")
    compile(rendered, "app.py", "exec")


def test_protected_spaces_are_source_bound() -> None:
    for repo_id in sorted(control.PROTECTED_SPACES):
        bound, reason = control._source_bound(object(), asset(tuple(), repo_id=repo_id), None)
        assert bound is True
        assert reason


def test_authenticated_inventory_excludes_private_repositories() -> None:
    public = SimpleNamespace(id="SZLHOLDINGS/public", private=False)
    private = SimpleNamespace(id="SZLHOLDINGS/private", private=True)
    observed: list[str] = []

    class FakeApi:
        def list_models(self, **kwargs):
            return [public, private]

        def list_datasets(self, **kwargs):
            return []

        def list_spaces(self, **kwargs):
            return []

        def repo_info(self, *, repo_id, **kwargs):
            observed.append(repo_id)
            assert repo_id != private.id
            return SimpleNamespace(sha="a" * 40, private=False)

        def list_repo_files(self, *, repo_id, **kwargs):
            assert repo_id != private.id
            return ["README.md"]

    assets = control.enumerate_assets(FakeApi(), "SZLHOLDINGS")
    assert [item.repo_id for item in assets] == [public.id]
    assert observed == [public.id]


def test_source_bound_evidence_requires_exact_public_runtime_readback() -> None:
    item = asset(("deployment.json",), repo_id="SZLHOLDINGS/a11oy")
    source_sha = "b" * 40
    repository = SimpleNamespace(
        sha=item.sha,
        runtime=SimpleNamespace(sha=item.sha, stage="RUNNING", raw={}),
    )
    evidence = control.evaluate_source_bound_evidence(
        item,
        repository,
        {"source_sha": source_sha},
        {"status": "OBSERVED", "build": {"revision": source_sha}},
    )
    assert evidence["status"] == "VERIFIED"
    assert evidence["failures"] == []

    diverged = control.evaluate_source_bound_evidence(
        item,
        repository,
        {"source_sha": source_sha},
        {"status": "OBSERVED", "build": {"revision": "c" * 40}},
    )
    assert diverged["status"] == "BLOCKED"
    assert "SERVED_SOURCE_REVISION_DIVERGED" in diverged["failures"]


def test_source_bound_verified_is_nonblocking_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item = asset(("deployment.json",), repo_id="SZLHOLDINGS/a11oy")
    monkeypatch.setattr(
        control,
        "verify_source_bound_asset",
        lambda api, candidate, protected_source_sha: {"status": "VERIFIED", "failures": []},
    )
    decision = control.process_asset(object(), item, None, True, True, tmp_path)
    assert decision.state == "SOURCE_BOUND_VERIFIED"
    assert decision.blockers == []
    report = control.build_report("SZLHOLDINGS", [decision], True, True)
    assert report["complete"] is True


def test_protected_workflow_source_can_verify_without_hub_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md",), repo_id="SZLHOLDINGS/a11oy")
    expected = "b" * 40

    class FakeApi:
        def repo_info(self, **kwargs):
            return SimpleNamespace(
                sha=item.sha,
                runtime=SimpleNamespace(sha=item.sha, stage="RUNNING", raw={}),
            )

    monkeypatch.setattr(control, "_read_text", lambda api, candidate, path, token: None)
    monkeypatch.setattr(
        control,
        "_read_json_url",
        lambda url: {"status": "OBSERVED", "build": {"revision": expected}},
    )
    evidence = control.verify_source_bound_asset(FakeApi(), item, expected)
    assert evidence["status"] == "VERIFIED"
    assert evidence["canonical_source_revision"] == expected


def test_static_manifest_readback_can_verify_without_runtime_sha() -> None:
    item = asset(("deployment.json",), repo_id="SZLHOLDINGS/README")
    deployment = {"source": {"revision": "b" * 40}}
    repository = SimpleNamespace(
        sha=item.sha,
        runtime=SimpleNamespace(stage="RUNNING", raw={}),
    )
    evidence = control.evaluate_source_bound_evidence(
        item,
        repository,
        deployment,
        deployment,
    )
    assert evidence["status"] == "VERIFIED"


def test_report_cannot_be_complete_with_blockers() -> None:
    decisions = [
        control.Decision("SZLHOLDINGS/a", "model", "a" * 40, "CURRENT"),
        control.Decision("SZLHOLDINGS/b", "space", "b" * 40, "SOURCE_BOUND_AUDIT_ONLY", blockers=["source-bound"]),
    ]
    report = control.build_report("SZLHOLDINGS", decisions, False, False)
    assert report["complete"] is False
    assert report["blocked_assets"] == ["SZLHOLDINGS/b"]


def test_report_requires_execution_merge_and_terminal_verified_states() -> None:
    current = control.Decision("SZLHOLDINGS/a", "model", "a" * 40, "CURRENT")
    assert control.build_report("SZLHOLDINGS", [current], False, False)["complete"] is False
    assert control.build_report("SZLHOLDINGS", [current], True, False)["complete"] is False

    pending = control.Decision("SZLHOLDINGS/b", "model", "b" * 40, "PR_CREATED")
    pending_report = control.build_report("SZLHOLDINGS", [pending], True, True)
    assert pending_report["complete"] is False
    assert pending_report["nonterminal_assets"] == ["SZLHOLDINGS/b"]

    unverified_merge = control.Decision("SZLHOLDINGS/u", "model", "e" * 40, "MERGED")
    assert control.build_report("SZLHOLDINGS", [unverified_merge], True, True)["complete"] is False

    merged = control.Decision(
        "SZLHOLDINGS/c",
        "model",
        "c" * 40,
        "MERGED",
        merged=True,
        resulting_sha="d" * 40,
    )
    assert control.build_report("SZLHOLDINGS", [current, merged], True, True)["complete"] is True
    assert control.build_report("SZLHOLDINGS", [], True, True)["complete"] is False


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


def test_manual_workflow_binds_protected_source_revision() -> None:
    rollout = (ROOT / ".github/workflows/hf-universal-frontend-rollout.yml").read_text(
        encoding="utf-8"
    )
    assert rollout.count('--protected-source-sha "$GITHUB_SHA"') == 2
    assert "if: inputs.operation == 'execute' && github.ref == 'refs/heads/main'" in rollout
    assert rollout.count("git/ref/heads/main") == 2
    assert "id: evidence" in rollout
    assert "if: ${{ always() && steps.evidence.outcome == 'success' }}" in rollout
    assert "mapfile -t issue_matches" in rollout
    assert "head -n 1" not in rollout
    assert "gh issue close" in rollout and "gh issue close" + ' "$number"' in rollout
    assert "gh issue reopen" in rollout
    assert "|| true" not in rollout
