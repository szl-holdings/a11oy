from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "hf_universal_frontend_control.py"
CONTRACT_WORKFLOW = ROOT / ".github" / "workflows" / "hf-universal-frontend-estate.yml"
ROLLOUT_WORKFLOW = ROOT / ".github" / "workflows" / "hf-universal-frontend-rollout.yml"
MAIN_GUARD = ROOT / ".github" / "scripts" / "require-current-main.sh"
RUNTIME_LOCK = ROOT / ".github" / "requirements" / "hf-universal-frontend-runtime.txt"
CI_LOCK = ROOT / ".github" / "requirements" / "hf-universal-frontend-ci.txt"
SPEC = importlib.util.spec_from_file_location("hf_universal_frontend_control", MODULE_PATH)
assert SPEC and SPEC.loader
control = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(control)


def asset(files: tuple[str, ...], repo_id: str = "SZLHOLDINGS/example", repo_type: str = "space"):
    return control.Asset(repo_id=repo_id, repo_type=repo_type, sha="a" * 40, files=files)


def source_map_entry(
    state: str,
    *,
    space_id: str = "SZLHOLDINGS/example",
    hf_repository_sha: str = "a" * 40,
) -> dict:
    canonical = None
    candidates: list[dict] = []
    workflows = {"state": "BLOCKED_SOURCE_MAPPING", "paths": []}
    if state in {"EXACT", "INFERRED"}:
        canonical = {
            "full_name": "szl-holdings/example",
            "default_branch_sha": "b" * 40,
        }
        candidates = [dict(canonical)]
        workflows = {
            "state": "OBSERVED",
            "paths": [".github/workflows/hf-deploy.yml"],
            "github_ref": "b" * 40,
        }
    return {
        "space_id": space_id,
        "hf_repository_sha": hf_repository_sha,
        "readme": {
            "http_status": 200,
            "revision": hf_repository_sha,
            "sha256": "d" * 64,
            "url": f"https://huggingface.co/spaces/{space_id}/raw/{hf_repository_sha}/README.md",
        },
        "source_mapping": {
            "state": state,
            "evidence": f"TEST_{state}",
            "canonical": canonical,
            "candidates": candidates,
        },
        "workflow_candidates": workflows,
    }


def write_source_map(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "source-map.json"
    path.write_text(
        json.dumps(
            {
                "schema": control.SOURCE_MAP_SCHEMA,
                "organization": "SZLHOLDINGS",
                "github_organization": "szl-holdings",
                "remote_mutation": False,
                "spaces": entries,
            }
        ),
        encoding="utf-8",
    )
    return path


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


@pytest.mark.parametrize(
    ("repo_type", "source_bound", "framework"),
    (
        ("model", False, "CARD_ONLY"),
        ("dataset", False, "CARD_ONLY"),
        ("space", True, "STATIC_HTML"),
    ),
)
def test_managed_card_is_independent_of_the_revision_that_contains_it(
    repo_type: str,
    source_bound: bool,
    framework: str,
) -> None:
    original = control.Asset(
        repo_id="SZLHOLDINGS/example",
        repo_type=repo_type,
        sha="a" * 40,
        files=("README.md",),
    )
    advanced = control.Asset(
        repo_id=original.repo_id,
        repo_type=original.repo_type,
        sha="b" * 40,
        files=original.files,
    )
    rendered = control.normalize_readme(
        original,
        "# Existing\n",
        source_bound,
        framework,
    )

    assert control.normalize_readme(
        advanced,
        rendered.decode(),
        source_bound,
        framework,
    ) == rendered
    assert original.sha not in rendered.decode()
    assert advanced.sha not in rendered.decode()
    assert f"Frontend contract release | `{control.RELEASE}`" in rendered.decode()


def test_unbalanced_card_markers_fail_closed() -> None:
    item = asset(("README.md",), repo_type="dataset")
    with pytest.raises(control.ControlError):
        control.normalize_readme(item, control.START + "\n", False, "CARD_ONLY")


def test_duplicate_managed_card_blocks_fail_closed() -> None:
    item = asset(("README.md",), repo_type="dataset")
    block = f"{control.START}\nfirst\n{control.END}"
    with pytest.raises(control.ControlError, match="at most one balanced block"):
        control.normalize_readme(item, f"{block}\n\n{block}\n", False, "CARD_ONLY")


def test_out_of_order_managed_card_markers_fail_closed() -> None:
    item = asset(("README.md",), repo_type="dataset")
    with pytest.raises(control.ControlError, match="out of order"):
        control.normalize_readme(
            item,
            f"{control.END}\ntext\n{control.START}\n",
            False,
            "CARD_ONLY",
        )


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


def test_static_html_adapter_replaces_tampered_managed_css() -> None:
    source = (
        "<html><head><style>\n"
        f"{control.STYLE_START}\nbody {{ display: none; }}\n{control.STYLE_END}"
        "</style></head><body></body></html>"
    )
    rendered = control._inject_style(source)
    assert "display: none" not in rendered
    assert rendered.count(control.UNIVERSAL_CSS) == 1


def test_static_html_adapter_restores_viewport_with_existing_managed_style() -> None:
    source = (
        "<html><head><style>\n"
        f"{control.UNIVERSAL_CSS}</style></head><body></body></html>"
    )
    rendered = control._inject_style(source)
    assert rendered.count('name="viewport"') == 1
    assert control._inject_style(rendered) == rendered


def test_static_html_adapter_does_not_accept_viewport_outside_head() -> None:
    source = (
        "<html><head><style>\n"
        f"{control.UNIVERSAL_CSS}</style></head>"
        '<body><meta name="viewport" content="width=device-width"></body></html>'
    )
    rendered = control._inject_style(source)
    assert rendered.count('name="viewport"') == 2
    assert rendered.index('name="viewport"') < rendered.index("</head>")


def test_static_html_adapter_rejects_managed_style_inside_comment() -> None:
    source = (
        "<html><head><!--<style>\n"
        f"{control.UNIVERSAL_CSS}</style>--></head><body></body></html>"
    )
    with pytest.raises(control.ControlError, match="active canonical style"):
        control._inject_style(source)


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


def test_react_adapter_does_not_trust_import_text_in_a_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("package.json", "src/main.tsx"))
    contents = {
        "src/main.tsx": (
            "// import './szl-universal.css';\n"
            "import React from 'react';\n"
            "export const App = () => <main />;\n"
        )
    }
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._react_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)["src/main.tsx"].decode()
    assert rendered.splitlines().count("import './szl-universal.css';") == 1


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

    contents["app.py"] = app
    ops2, blockers2 = control._gradio_ops(object(), item, None)
    assert not blockers2
    assert dict(ops2)["app.py"] == rendered["app.py"]


def test_gradio_existing_css_requires_source_native_review(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {"app.py": "import gradio as gr\nwith gr.Blocks(css='body{}') as demo:\n    pass\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._gradio_ops(object(), item, None)
    assert not ops
    assert blockers and "source-specific" in blockers[0]


def test_gradio_multiline_existing_css_requires_source_native_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("app.py",))
    contents = {
        "app.py": (
            "import gradio as gr\n"
            "with gr.Blocks(\n"
            "    title='x',\n"
            "    css='body{}',\n"
            ") as demo:\n"
            "    pass\n"
        )
    }
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._gradio_ops(object(), item, None)
    assert not ops
    assert blockers and "source-specific" in blockers[0]


def test_gradio_tampered_managed_binding_is_not_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("app.py", "szl_universal.css"))
    contents = {
        "app.py": (
            "from pathlib import Path\n"
            "import gradio as gr\n"
            "_SZL_UNIVERSAL_CSS = 'tampered'\n"
            "with gr.Blocks(css=_SZL_UNIVERSAL_CSS, ) as demo:\n"
            "    pass\n"
        )
    }
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._gradio_ops(object(), item, None)
    assert not ops
    assert blockers and "direct unshadowed" in blockers[0]



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

    contents["app.py"] = app
    ops2, blockers2 = control._streamlit_ops(object(), item, None)
    assert not blockers2
    assert dict(ops2)["app.py"] == rendered["app.py"]


def test_streamlit_multiline_page_config_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    item = asset(("app.py",))
    contents = {"app.py": "import streamlit as st\nst.set_page_config(\n    page_title='x',\n)\n"}
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._streamlit_ops(object(), item, None)
    assert not ops
    assert blockers and "single-line" in blockers[0]


def test_streamlit_marker_text_does_not_replace_active_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("app.py", "szl_universal.css"))
    contents = {
        "app.py": (
            "import streamlit as st\n"
            "st.set_page_config(page_title='x')\n"
            "marker = '# szl-universal-frontend:inject'\n"
            "st.title('x')\n"
        )
    }
    monkeypatch.setattr(control, "_read_text", lambda api, a, path, token: contents.get(path))
    ops, blockers = control._streamlit_ops(object(), item, None)
    assert not blockers
    rendered = dict(ops)["app.py"].decode()
    assert rendered.splitlines().count("# szl-universal-frontend:inject") == 1
    assert "st.markdown(" in rendered



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


def test_anonymous_inventory_excludes_private_repositories() -> None:
    public = SimpleNamespace(id="SZLHOLDINGS/public", private=False)
    private = SimpleNamespace(id="SZLHOLDINGS/private", private=True)
    observed: list[str] = []

    class FakeApi:
        def list_models(self, **kwargs):
            assert kwargs["token"] is False
            return [public, private]

        def list_datasets(self, **kwargs):
            return []

        def list_spaces(self, **kwargs):
            return []

        def repo_info(self, *, repo_id, **kwargs):
            observed.append(repo_id)
            assert repo_id != private.id
            assert kwargs["token"] is False
            return SimpleNamespace(sha="a" * 40, private=False)

        def list_repo_files(self, *, repo_id, **kwargs):
            assert repo_id != private.id
            assert kwargs["token"] is False
            return ["README.md"]

    assets = control.enumerate_assets(FakeApi(), "SZLHOLDINGS")
    assert [item.repo_id for item in assets] == [public.id]
    assert observed == [public.id]


@pytest.mark.parametrize(
    ("state", "expected_state"),
    (
        ("EXACT", "SOURCE_BOUND_REPAIR_REQUIRED"),
        ("INFERRED", "SOURCE_MAPPING_REVIEW_REQUIRED"),
        ("DIVERGENT", "SOURCE_MAPPING_BLOCKED"),
        ("UNAVAILABLE", "SOURCE_MAPPING_BLOCKED"),
    ),
)
def test_every_source_map_state_denies_direct_space_hub_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    expected_state: str,
) -> None:
    readme = b"# Existing\n"
    entry = source_map_entry(state)
    entry["readme"]["sha256"] = control._sha256(readme)
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [entry]), "SZLHOLDINGS"
    )
    monkeypatch.setattr(
        control,
        "_read_bytes",
        lambda api, item, path, token: readme if path == "README.md" else None,
    )
    decision = control.process_asset(
        object(),
        asset(("README.md", "deployment.json")),
        None,
        True,
        True,
        tmp_path / "backups",
        space_authorities=authorities,
    )
    assert decision.state == expected_state
    assert decision.source_mapping_state == state
    assert decision.blockers
    assert decision.pr_url is None
    assert decision.merged is False


def test_exact_source_bound_space_can_reach_terminal_verified_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = asset(("README.md", "index.html"))
    item = control.Asset(prior.repo_id, prior.repo_type, "c" * 40, prior.files)
    html = control._inject_style(
        "<!doctype html><html><head><title>x</title></head><body><main>x</main></body></html>"
    ).encode()
    readme = control.normalize_readme(
        prior,
        "# Existing\n",
        True,
        "STATIC_HTML",
    )
    assert control.normalize_readme(item, readme.decode(), True, "STATIC_HTML") == readme
    entry = source_map_entry("EXACT", hf_repository_sha=item.sha)
    entry["readme"]["sha256"] = control._sha256(readme)
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [entry]), "SZLHOLDINGS"
    )
    contents = {"README.md": readme, "index.html": html}
    monkeypatch.setattr(
        control,
        "_read_bytes",
        lambda api, observed, path, token: contents.get(path),
    )

    decision = control.process_asset(
        object(),
        item,
        None,
        True,
        True,
        tmp_path / "backups",
        space_authorities=authorities,
    )

    assert decision.state == "SOURCE_BOUND_VERIFIED"
    assert decision.framework == "STATIC_HTML"
    assert decision.changes == []
    assert decision.blockers == []
    assert decision.source_map_readme_sha256 == control._sha256(readme)
    assert decision.required_readback_paths == ["README.md", "index.html"]
    assert decision.readback_sha256 == {
        "README.md": control._sha256(readme),
        "index.html": control._sha256(html),
    }
    assert control._decision_is_terminal_verified(decision) is True
    decision.readback_sha256.pop("index.html")
    assert control._decision_is_terminal_verified(decision) is False


def test_merged_card_remains_current_after_repository_revision_advances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = asset(("README.md",), repo_type="model")
    merged = control.Asset(parent.repo_id, parent.repo_type, "b" * 40, parent.files)
    readme = control.normalize_readme(parent, "# Existing\n", False, "CARD_ONLY")
    monkeypatch.setattr(
        control,
        "_read_bytes",
        lambda api, observed, path, token: readme if path == "README.md" else None,
    )

    decision = control.process_asset(
        object(),
        merged,
        None,
        False,
        False,
        tmp_path / "backups",
        space_authorities={},
    )

    assert decision.state == "CURRENT"
    assert decision.changes == []


def test_tampered_static_marker_cannot_reach_terminal_verified_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md", "index.html"))
    readme = control.normalize_readme(item, "# Existing\n", True, "STATIC_HTML")
    html = (
        "<html><head><style>\n"
        f"{control.STYLE_START}\nbody {{ display: none; }}\n{control.STYLE_END}"
        "</style></head><body></body></html>"
    ).encode()
    entry = source_map_entry("EXACT")
    entry["readme"]["sha256"] = control._sha256(readme)
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [entry]), "SZLHOLDINGS"
    )
    contents = {"README.md": readme, "index.html": html}
    monkeypatch.setattr(
        control,
        "_read_bytes",
        lambda api, observed, path, token: contents.get(path),
    )
    decision = control.process_asset(
        object(),
        item,
        None,
        True,
        True,
        tmp_path / "backups",
        space_authorities=authorities,
    )
    assert decision.state == "SOURCE_BOUND_REPAIR_REQUIRED"
    assert any(change.startswith("index.html:") for change in decision.changes)
    assert control._decision_is_terminal_verified(decision) is False


def test_static_space_without_viewport_cannot_reach_terminal_verified_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md", "index.html"))
    readme = control.normalize_readme(item, "# Existing\n", True, "STATIC_HTML")
    html = (
        "<html><head><style>\n"
        f"{control.UNIVERSAL_CSS}</style></head><body></body></html>"
    ).encode()
    entry = source_map_entry("EXACT")
    entry["readme"]["sha256"] = control._sha256(readme)
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [entry]), "SZLHOLDINGS"
    )
    contents = {"README.md": readme, "index.html": html}
    monkeypatch.setattr(
        control,
        "_read_bytes",
        lambda api, observed, path, token: contents.get(path),
    )
    decision = control.process_asset(
        object(),
        item,
        None,
        True,
        True,
        tmp_path / "backups",
        space_authorities=authorities,
    )
    assert decision.state == "SOURCE_BOUND_REPAIR_REQUIRED"
    assert any(change.startswith("index.html:") for change in decision.changes)
    assert control._decision_is_terminal_verified(decision) is False


def test_exact_source_bound_space_rejects_stale_readme_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [source_map_entry("EXACT")]), "SZLHOLDINGS"
    )
    monkeypatch.setattr(
        control,
        "_read_bytes",
        lambda api, item, path, token: b"different" if path == "README.md" else None,
    )
    decision = control.process_asset(
        object(),
        asset(("README.md", "index.html")),
        None,
        True,
        True,
        tmp_path / "backups",
        space_authorities=authorities,
    )
    assert decision.state == "SOURCE_MAP_STALE"
    assert decision.blockers == [
        "immutable source-map README hash does not match the revision-bound Hub bytes"
    ]


def test_complete_space_inventory_must_match_map_before_provider_mutation(
    tmp_path: Path,
) -> None:
    example = asset(("README.md",))
    other = asset(("README.md",), repo_id="SZLHOLDINGS/other")
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [source_map_entry("EXACT")]), "SZLHOLDINGS"
    )
    assert control.validate_space_inventory_authorities([example], authorities) == [example]

    with pytest.raises(control.ControlError, match="missing source-map entries"):
        control.validate_space_inventory_authorities([example, other], authorities)
    with pytest.raises(control.ControlError, match="unobserved source-map entries"):
        control.validate_space_inventory_authorities([], authorities)

    stale = asset(("README.md",))
    stale = control.Asset(stale.repo_id, stale.repo_type, "c" * 40, stale.files)
    with pytest.raises(control.ControlError, match="stale source-map revisions"):
        control.validate_space_inventory_authorities([stale], authorities)


def test_blocked_space_preflight_denies_all_provider_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_map = write_source_map(tmp_path, [source_map_entry("EXACT")])
    guard = tmp_path / "guard.sh"
    guard.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    report = tmp_path / "report.json"
    model = asset(("README.md",), repo_id="SZLHOLDINGS/model", repo_type="model")
    space = asset(("README.md", "index.html"))
    observed_flags: list[tuple[bool, bool]] = []

    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setattr(control, "HfApi", lambda **kwargs: object())
    monkeypatch.setattr(control, "enumerate_assets", lambda api, org: [model, space])
    monkeypatch.setattr(
        control,
        "_space_authority_decision",
        lambda api, item, authorities: control.Decision(
            item.repo_id,
            item.repo_type,
            item.sha,
            "SOURCE_BOUND_REPAIR_REQUIRED",
            blockers=["repair through canonical source"],
        ),
    )

    def fake_process(api, item, token, execute, merge, backups, **kwargs):
        observed_flags.append((execute, merge))
        return control.Decision(item.repo_id, item.repo_type, item.sha, "CURRENT")

    monkeypatch.setattr(control, "process_asset", fake_process)
    result = control.main(
        [
            "--execute",
            "--merge",
            "--source-map",
            str(source_map),
            "--authority-guard",
            str(guard),
            "--report",
            str(report),
            "--backup-dir",
            str(tmp_path / "backups"),
            "--sleep",
            "0",
        ]
    )
    assert result == 2
    assert observed_flags == [(False, False)]
    assert json.loads(report.read_text(encoding="utf-8"))["complete"] is False


def test_missing_and_stale_source_map_entries_fail_closed(tmp_path: Path) -> None:
    authorities = control.load_space_source_map(
        write_source_map(
            tmp_path,
            [source_map_entry("EXACT", space_id="SZLHOLDINGS/other")],
        ),
        "SZLHOLDINGS",
    )
    missing = control.process_asset(
        object(),
        asset(tuple()),
        None,
        True,
        True,
        tmp_path / "missing-backups",
        space_authorities=authorities,
    )
    assert missing.state == "SOURCE_MAP_MISSING"
    assert missing.blockers

    stale_authorities = control.load_space_source_map(
        write_source_map(
            tmp_path,
            [source_map_entry("EXACT", hf_repository_sha="c" * 40)],
        ),
        "SZLHOLDINGS",
    )
    stale = control.process_asset(
        object(),
        asset(tuple()),
        None,
        True,
        True,
        tmp_path / "stale-backups",
        space_authorities=stale_authorities,
    )
    assert stale.state == "SOURCE_MAP_STALE"
    assert "does not match observed" in stale.blockers[0]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema", "wrong", "schema"),
        ("organization", "OTHER", "organization"),
        ("github_organization", "other", "GitHub organization"),
        ("remote_mutation", True, "remote_mutation=false"),
    ),
)
def test_source_map_root_contract_fails_closed(
    tmp_path: Path,
    field: str,
    value,
    message: str,
) -> None:
    path = write_source_map(tmp_path, [source_map_entry("EXACT")])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(control.ControlError, match=message):
        control.load_space_source_map(path, "SZLHOLDINGS")


def test_source_map_rejects_duplicates_mutable_revisions_and_invalid_canonical_state(
    tmp_path: Path,
) -> None:
    duplicate = write_source_map(
        tmp_path,
        [source_map_entry("EXACT"), source_map_entry("EXACT")],
    )
    with pytest.raises(control.ControlError, match="repeats"):
        control.load_space_source_map(duplicate, "SZLHOLDINGS")

    mutable = write_source_map(
        tmp_path,
        [source_map_entry("EXACT", hf_repository_sha="main")],
    )
    with pytest.raises(control.ControlError, match="40-character"):
        control.load_space_source_map(mutable, "SZLHOLDINGS")

    invalid = source_map_entry("DIVERGENT")
    invalid["source_mapping"]["canonical"] = {
        "full_name": "szl-holdings/example",
        "default_branch_sha": "b" * 40,
    }
    with pytest.raises(control.ControlError, match="must not claim"):
        control.load_space_source_map(write_source_map(tmp_path, [invalid]), "SZLHOLDINGS")

    invalid_space = source_map_entry(
        "EXACT", space_id="SZLHOLDINGS/example/nested"
    )
    with pytest.raises(control.ControlError, match="invalid space_id"):
        control.load_space_source_map(
            write_source_map(tmp_path, [invalid_space]), "SZLHOLDINGS"
        )

    invalid_canonical = source_map_entry("EXACT")
    invalid_canonical["source_mapping"]["canonical"]["full_name"] = (
        "szl-holdings/example/nested"
    )
    with pytest.raises(control.ControlError, match="canonical repository identity"):
        control.load_space_source_map(
            write_source_map(tmp_path, [invalid_canonical]), "SZLHOLDINGS"
        )


def test_source_map_rejects_unbound_readme_evidence(tmp_path: Path) -> None:
    invalid_status = source_map_entry("EXACT")
    invalid_status["readme"]["http_status"] = "200"
    with pytest.raises(control.ControlError, match="HTTP status is invalid"):
        control.load_space_source_map(
            write_source_map(tmp_path, [invalid_status]), "SZLHOLDINGS"
        )

    wrong_revision = source_map_entry("EXACT")
    wrong_revision["readme"]["revision"] = "c" * 40
    with pytest.raises(control.ControlError, match="does not match"):
        control.load_space_source_map(
            write_source_map(tmp_path, [wrong_revision]), "SZLHOLDINGS"
        )

    mutable_url = source_map_entry("EXACT")
    mutable_url["readme"]["url"] = (
        "https://huggingface.co/spaces/SZLHOLDINGS/example/raw/main/README.md"
    )
    with pytest.raises(control.ControlError, match="not revision-bound"):
        control.load_space_source_map(
            write_source_map(tmp_path, [mutable_url]), "SZLHOLDINGS"
        )

    foreign_url = source_map_entry("EXACT")
    foreign_url["readme"]["url"] = (
        f"https://example.invalid/{'a' * 40}/README.md"
    )
    with pytest.raises(control.ControlError, match="not revision-bound"):
        control.load_space_source_map(
            write_source_map(tmp_path, [foreign_url]), "SZLHOLDINGS"
        )

    non_200_mutable_url = source_map_entry("EXACT")
    non_200_mutable_url["readme"].update(
        {
            "http_status": 404,
            "sha256": None,
            "url": "https://huggingface.co/spaces/SZLHOLDINGS/example/raw/main/README.md",
        }
    )
    with pytest.raises(control.ControlError, match="not revision-bound"):
        control.load_space_source_map(
            write_source_map(tmp_path, [non_200_mutable_url]), "SZLHOLDINGS"
        )

    boolean_status = source_map_entry("EXACT")
    boolean_status["readme"]["http_status"] = True
    with pytest.raises(control.ControlError, match="HTTP status is invalid"):
        control.load_space_source_map(
            write_source_map(tmp_path, [boolean_status]), "SZLHOLDINGS"
        )


def test_source_map_accepts_immutable_resolve_readme_evidence(tmp_path: Path) -> None:
    entry = source_map_entry("EXACT")
    entry["readme"]["url"] = (
        f"https://huggingface.co/spaces/{entry['space_id']}/resolve/"
        f"{entry['hf_repository_sha']}/README.md"
    )
    authorities = control.load_space_source_map(
        write_source_map(tmp_path, [entry]), "SZLHOLDINGS"
    )
    assert authorities[entry["space_id"]].readme_sha256 == "d" * 64


def test_source_map_binds_canonical_candidate_and_workflow_revisions(tmp_path: Path) -> None:
    candidate_diverged = source_map_entry("EXACT")
    candidate_diverged["source_mapping"]["candidates"][0]["default_branch_sha"] = "c" * 40
    with pytest.raises(control.ControlError, match="not uniquely bound"):
        control.load_space_source_map(
            write_source_map(tmp_path, [candidate_diverged]), "SZLHOLDINGS"
        )

    workflow_diverged = source_map_entry("EXACT")
    workflow_diverged["workflow_candidates"]["github_ref"] = "c" * 40
    with pytest.raises(control.ControlError, match="workflow evidence is not bound"):
        control.load_space_source_map(
            write_source_map(tmp_path, [workflow_diverged]), "SZLHOLDINGS"
        )


def test_source_map_missing_file_is_an_explicit_blocker(tmp_path: Path) -> None:
    with pytest.raises(control.ControlError, match="unavailable"):
        control.load_space_source_map(tmp_path / "missing.json", "SZLHOLDINGS")


def test_missing_source_map_fails_before_any_provider_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnexpectedApi:
        def __init__(self, **kwargs):
            raise AssertionError("provider client must not be constructed without the source map")

    monkeypatch.setattr(control, "HfApi", UnexpectedApi)
    report = tmp_path / "report.json"
    result = control.main(
        [
            "--source-map",
            str(tmp_path / "missing.json"),
            "--report",
            str(report),
            "--backup-dir",
            str(tmp_path / "backups"),
        ]
    )
    assert result == 4
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert "source map is unavailable" in payload["fatal"]


def test_report_cannot_be_complete_with_blockers() -> None:
    decisions = [
        control.Decision("SZLHOLDINGS/a", "model", "a" * 40, "CURRENT"),
        control.Decision("SZLHOLDINGS/b", "space", "b" * 40, "SOURCE_BOUND_AUDIT_ONLY", blockers=["source-bound"]),
    ]
    report = control.build_report("SZLHOLDINGS", decisions, False, False)
    assert report["complete"] is False
    assert report["blocked_assets"] == ["SZLHOLDINGS/b"]


def test_plan_and_nonterminal_transactions_never_report_complete() -> None:
    current = [control.Decision("SZLHOLDINGS/a", "model", "a" * 40, "CURRENT")]
    identity = {
        "schema": control.SOURCE_MAP_SCHEMA,
        "path": "docs/huggingface-space-source-map-v1.json",
        "sha256": "f" * 64,
        "space_count": 1,
    }
    plan = control.build_report(
        "SZLHOLDINGS",
        current,
        False,
        False,
        source_map_identity=identity,
    )
    assert plan["completion_eligible"] is False
    assert plan["complete"] is False
    assert plan["source_map"] == identity

    pending = [
        control.Decision("SZLHOLDINGS/a", "model", "a" * 40, "WOULD_CREATE_PR")
    ]
    assert control.build_report("SZLHOLDINGS", pending, True, True)["complete"] is False
    assert control.build_report("SZLHOLDINGS", current, True, True)["complete"] is True


class _MergeApi:
    def __init__(self, resulting_sha: str):
        self.resulting_sha = resulting_sha
        self.create_calls = 0
        self.merge_calls = 0

    def create_commit(self, **kwargs):
        self.create_calls += 1
        assert kwargs["parent_commit"] == "a" * 40
        assert kwargs["create_pr"] is True
        return SimpleNamespace(pr_url="https://huggingface.co/models/SZLHOLDINGS/example/discussions/7")

    def merge_pull_request(self, **kwargs):
        self.merge_calls += 1
        assert kwargs["discussion_num"] == 7

    def repo_info(self, **kwargs):
        assert kwargs["revision"] == "main"
        return SimpleNamespace(sha=self.resulting_sha)


def test_post_merge_readback_requires_immutable_matching_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md",), repo_type="model")
    expected = control.normalize_readme(item, "# old\n", False, "CARD_ONLY")
    monkeypatch.setattr(control, "_read_bytes", lambda api, item, path, token: b"# old\n")
    monkeypatch.setattr(
        control,
        "_read_revision_bytes",
        lambda item, revision, path, token: expected,
    )
    api = _MergeApi("b" * 40)
    decision = control.process_asset(
        api,
        item,
        None,
        True,
        True,
        tmp_path / "verified-backups",
        space_authorities={},
        authority_guard=lambda: None,
    )
    assert decision.state == "MERGED_VERIFIED"
    assert decision.merged is True
    assert decision.resulting_sha == "b" * 40
    assert decision.readback_sha256["README.md"] == control._sha256(expected)


def test_post_merge_readback_mismatch_and_nonadvance_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md",), repo_type="model")
    monkeypatch.setattr(control, "_read_bytes", lambda api, item, path, token: b"# old\n")
    monkeypatch.setattr(
        control,
        "_read_revision_bytes",
        lambda item, revision, path, token: b"wrong bytes",
    )
    mismatch = control.process_asset(
        _MergeApi("b" * 40),
        item,
        None,
        True,
        True,
        tmp_path / "mismatch-backups",
        space_authorities={},
        authority_guard=lambda: None,
    )
    assert mismatch.state == "MERGED_READBACK_FAILED"
    assert mismatch.merged is True
    assert any("mismatch" in blocker for blocker in mismatch.blockers)

    nonadvance = control.process_asset(
        _MergeApi("a" * 40),
        item,
        None,
        True,
        True,
        tmp_path / "nonadvance-backups",
        space_authorities={},
        authority_guard=lambda: None,
    )
    assert nonadvance.state == "MERGED_READBACK_FAILED"
    assert any("did not advance" in blocker for blocker in nonadvance.blockers)



def test_each_provider_mutation_rechecks_exact_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md",), repo_type="model")
    expected = control.normalize_readme(item, "# old\n", False, "CARD_ONLY")
    monkeypatch.setattr(control, "_read_bytes", lambda api, item, path, token: b"# old\n")
    monkeypatch.setattr(
        control,
        "_read_revision_bytes",
        lambda item, revision, path, token: expected,
    )
    calls = 0

    def guard() -> None:
        nonlocal calls
        calls += 1

    decision = control.process_asset(
        _MergeApi("b" * 40),
        item,
        None,
        True,
        True,
        tmp_path / "guarded-backups",
        space_authorities={},
        authority_guard=guard,
    )
    assert decision.state == "MERGED_VERIFIED"
    assert calls == 2


def test_missing_provider_authority_guard_fails_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = asset(("README.md",), repo_type="model")
    monkeypatch.setattr(control, "_read_bytes", lambda api, item, path, token: b"# old\n")

    class NoWriteApi:
        def create_commit(self, **kwargs):
            raise AssertionError("provider write must not occur")

    decision = control.process_asset(
        NoWriteApi(),
        item,
        None,
        True,
        True,
        tmp_path / "unguarded-backups",
        space_authorities={},
    )
    assert decision.state == "AUTHORITY_GUARD_MISSING"
    assert decision.blockers


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
    assert source.count("authority_guard()") == 2
    assert "PROTECTED_SPACES" not in source
    assert "def _source_bound" not in source
    assert '"deployment.json"' not in source


def test_manual_workflow_requires_exact_main_at_every_authority_boundary() -> None:
    rollout = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
    guard = MAIN_GUARD.read_text(encoding="utf-8")
    assert rollout.count("github.ref == 'refs/heads/main'") == 2
    assert rollout.count("bash .github/scripts/require-current-main.sh") >= 8
    assert guard.count('GITHUB_REF') >= 2
    assert 'refs/heads/main' in guard
    assert 'git rev-parse HEAD' in guard
    assert 'git/ref/heads/main' in guard
    assert 'current_main' in guard

    provider_step = rollout.index("Create, merge, and read back revision-bound Hub pull requests")
    provider_guard = rollout.index("bash .github/scripts/require-current-main.sh", provider_step)
    execute = rollout.index("--execute", provider_guard)
    assert provider_guard < execute
    issue_step = rollout.index("Synchronize one deterministic blocker issue")
    issue_guard = rollout.index("bash .github/scripts/require-current-main.sh", issue_step)
    issue_write = rollout.index("gh issue", issue_guard)
    assert issue_guard < issue_write


@pytest.mark.parametrize(
    ("ref", "local_sha", "remote_sha", "expected"),
    (
        ("refs/heads/topic", "a" * 40, "a" * 40, "restricted to refs/heads/main"),
        ("refs/heads/main", "b" * 40, "a" * 40, "does not match dispatched source"),
        ("refs/heads/main", "a" * 40, "b" * 40, "is not current protected main"),
    ),
)
def test_current_main_guard_rejects_wrong_ref_checkout_and_remote(
    tmp_path: Path,
    ref: str,
    local_sha: str,
    remote_sha: str,
    expected: str,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$FAKE_LOCAL_SHA"\n', encoding="utf-8")
    fake_git.chmod(0o755)
    fake_gh = fake_bin / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$FAKE_REMOTE_SHA"\n', encoding="utf-8")
    fake_gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "GITHUB_REF": ref,
        "GITHUB_SHA": "a" * 40,
        "GITHUB_REPOSITORY": "szl-holdings/a11oy",
        "GH_TOKEN": "test-token",
        "FAKE_LOCAL_SHA": local_sha,
        "FAKE_REMOTE_SHA": remote_sha,
    }
    result = subprocess.run(
        ["bash", str(MAIN_GUARD)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert expected in result.stdout


def test_current_main_guard_accepts_exact_current_main(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, variable in (("git", "FAKE_LOCAL_SHA"), ("gh", "FAKE_REMOTE_SHA")):
        script = fake_bin / name
        script.write_text(
            f'#!/usr/bin/env bash\nprintf "%s\\n" "${variable}"\n',
            encoding="utf-8",
        )
        script.chmod(0o755)
    sha = "a" * 40
    result = subprocess.run(
        ["bash", str(MAIN_GUARD)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": sha,
            "GITHUB_REPOSITORY": "szl-holdings/a11oy",
            "GH_TOKEN": "test-token",
            "FAKE_LOCAL_SHA": sha,
            "FAKE_REMOTE_SHA": sha,
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert f"Exact protected main confirmed: {sha}." in result.stdout


def test_current_main_guard_rejects_mutable_or_malformed_dispatch_sha(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ("git", "gh"):
        script = fake_bin / name
        script.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
        script.chmod(0o755)
    result = subprocess.run(
        ["bash", str(MAIN_GUARD)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "main",
            "GITHUB_REPOSITORY": "szl-holdings/a11oy",
            "GH_TOKEN": "test-token",
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not an immutable 40-character Git revision" in result.stdout


def test_manual_workflow_uses_source_map_and_unique_fail_loud_issue_lookup() -> None:
    rollout = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
    assert rollout.count("--source-map docs/huggingface-space-source-map-v1.json") == 2
    assert "gh api --paginate --slurp" in rollout
    assert "issues?state=all&per_page=100" in rollout
    assert ".pull_request == null" in rollout
    assert ".state | ascii_upcase" in rollout
    assert "mapfile -t issue_matches" in rollout
    assert '${#issue_matches[@]}' in rollout
    assert "head -n 1" not in rollout
    assert "|| true" not in rollout


def test_hf_workflows_install_only_hash_locked_dependencies() -> None:
    rollout = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
    contract = CONTRACT_WORKFLOW.read_text(encoding="utf-8")
    assert rollout.count("--require-hashes") == 2
    assert "hf-universal-frontend-runtime.txt" in rollout
    assert "--require-hashes" in contract
    assert "hf-universal-frontend-ci.txt" in contract
    for workflow in (rollout, contract):
        assert "huggingface_hub==" not in workflow
        assert "pytest==" not in workflow
    runtime_lock = RUNTIME_LOCK.read_text(encoding="utf-8")
    ci_lock = CI_LOCK.read_text(encoding="utf-8")
    assert "huggingface-hub==1.23.0" in runtime_lock
    assert "pytest==9.0.3" in ci_lock
    assert "--hash=sha256:" in runtime_lock
    assert "--hash=sha256:" in ci_lock
