#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Revision-bound, source-aware frontend controller for the SZLHOLDINGS Hub estate.

The controller may update public cards and a small set of deterministic application
shells. It never changes model weights, tokenizer artifacts, dataset payloads,
visibility, hardware, storage, secrets, or repository allocation. GitHub-derived
Spaces are audit-only and must be repaired at their source repository.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, HfHubHTTPError

START = "<!-- szl-universal-frontend:start -->"
END = "<!-- szl-universal-frontend:end -->"
STYLE_START = "/* szl-universal-frontend:start */"
STYLE_END = "/* szl-universal-frontend:end */"
RELEASE = "2026-08-17"
PROTECTED_SPACES = {"SZLHOLDINGS/README", "SZLHOLDINGS/a11oy"}
REPO_TYPES = ("model", "dataset", "space")

UNIVERSAL_CSS = f"""{STYLE_START}
:root {{ color-scheme: dark; --szl-focus: #eef4fb; }}
*, *::before, *::after {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ min-width: 0; overflow-x: hidden; }}
img, svg, video, canvas {{ max-width: 100%; height: auto; }}
button, [role="button"], input, select, textarea, a.sz-control {{ min-height: 44px; }}
button, [role="button"], a, input, select, textarea {{ touch-action: manipulation; }}
:where(pre, code, kbd, samp, .mono, [data-revision], [data-receipt], [data-hash]) {{
  overflow-wrap: anywhere; word-break: break-word;
}}
:where(.grid, .cards, .card-grid, [data-grid]) {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr)); gap: 1rem;
}}
:where(.row, .actions, .button-row, [data-actions]) {{ display: flex; flex-wrap: wrap; gap: .75rem; }}
:where(.card, .panel, .tile, .column, .col, [data-card]) {{ min-width: 0; }}
:where(a, button, input, select, textarea):focus-visible {{ outline: 3px solid var(--szl-focus); outline-offset: 3px; }}
@media (max-width: 640px) {{
  :where(.row, .actions, .button-row, [data-actions]) {{ display: grid; grid-template-columns: 1fr; width: 100%; }}
  :where(.row, .actions, .button-row, [data-actions]) > :where(a, button, [role="button"]) {{ width: 100%; white-space: normal; }}
  :where(main, .container, .wrap, .content) {{ padding-inline: clamp(.875rem, 4vw, 1.25rem); }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }}
}}
{STYLE_END}
"""


class ControlError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class Asset:
    repo_id: str
    repo_type: str
    sha: str
    files: tuple[str, ...]


@dataclasses.dataclass
class Decision:
    repo_id: str
    repo_type: str
    source_sha: str
    state: str
    framework: str = "CARD_ONLY"
    changes: list[str] = dataclasses.field(default_factory=list)
    blockers: list[str] = dataclasses.field(default_factory=list)
    pr_url: str | None = None
    merged: bool = False
    resulting_sha: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(repo_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", repo_id)


def _read_bytes(api: HfApi, asset: Asset, path: str, token: str | None) -> bytes | None:
    if path not in asset.files:
        return None
    try:
        local = hf_hub_download(
            repo_id=asset.repo_id,
            filename=path,
            repo_type=asset.repo_type,
            revision=asset.sha,
            token=token,
        )
        return Path(local).read_bytes()
    except EntryNotFoundError:
        return None


def _read_text(api: HfApi, asset: Asset, path: str, token: str | None) -> str | None:
    data = _read_bytes(api, asset, path, token)
    if data is None:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ControlError(f"{asset.repo_id}:{path} is not UTF-8 text") from exc


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    match = re.match(r"\A---\n.*?\n---\n", text, re.DOTALL)
    if not match:
        raise ControlError("README starts YAML frontmatter but has no closing delimiter")
    return match.group(0), text[match.end() :]


def _replace_managed(text: str, managed: str) -> str:
    if text.count(START) != text.count(END):
        raise ControlError("unbalanced managed card markers")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(managed, text, count=1)
    else:
        text = managed + "\n\n" + text.lstrip()
    return text.rstrip() + "\n"


def _card(asset: Asset, source_bound: bool, framework: str) -> str:
    type_label = {"model": "Model", "dataset": "Dataset", "space": "Space"}[asset.repo_type]
    live = "SOURCE-BOUND" if source_bound else ("RUNNING-READBACK-REQUIRED" if asset.repo_type == "space" else "ARTIFACT-CARD")
    return f"""{START}
## {asset.repo_id.split('/', 1)[-1]}

**{type_label} · SZL Holdings governed public estate**

| Contract | State |
|---|---|
| Canonical identity | `{asset.repo_id}` |
| Source revision at card generation | `{asset.sha}` |
| Frontend profile | `{framework}` |
| Evidence state | `{live}` |
| Receipt language | Hash-chain integrity and cryptographic signing are reported separately |

This page is mobile-safe by construction: identifiers wrap, controls target at least 44 px, layouts collapse to one column, keyboard focus remains visible, and reduced-motion preferences are honored where an application shell is present.

A reachable page proves reachability only. It does **not** independently establish model quality, training provenance, source/runtime parity, cryptographic signing, or production readiness. Current organization inventory belongs to the canonical live organization views rather than hardcoded counters in this card.

[Organization](https://huggingface.co/SZLHOLDINGS) · [Models](https://huggingface.co/SZLHOLDINGS/models) · [Datasets](https://huggingface.co/SZLHOLDINGS/datasets) · [Spaces](https://huggingface.co/SZLHOLDINGS/spaces) · [Collections](https://huggingface.co/SZLHOLDINGS/collections)
{END}"""


def normalize_readme(asset: Asset, existing: str | None, source_bound: bool, framework: str) -> bytes:
    front, body = _split_frontmatter(existing or "")
    rendered = front + _replace_managed(body, _card(asset, source_bound, framework))
    return rendered.encode("utf-8")


def _source_bound(api: HfApi, asset: Asset, token: str | None) -> tuple[bool, str | None]:
    if asset.repo_id in PROTECTED_SPACES:
        return True, "protected canonical GitHub-derived Space"
    deployment = _read_text(api, asset, "deployment.json", token)
    if deployment:
        lowered = deployment.lower()
        if "github" in lowered or "source_revision" in lowered or "source-revision" in lowered:
            return True, "deployment.json records external source provenance"
    return False, None


def _inject_style(html: str) -> str:
    if STYLE_START in html:
        if html.count(STYLE_START) != 1 or html.count(STYLE_END) != 1:
            raise ControlError("static style markers are duplicated or unbalanced")
        return html
    if html.lower().count("<head") != 1 or html.lower().count("</head>") != 1:
        raise ControlError("static HTML must contain exactly one head element")
    if not re.search(r'<meta\s+name=["\']viewport["\']', html, re.IGNORECASE):
        html = re.sub(
            r"(<head[^>]*>)",
            r'\1\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return re.sub(r"</head>", f"<style>\n{UNIVERSAL_CSS}</style>\n</head>", html, count=1, flags=re.IGNORECASE)


def _react_ops(api: HfApi, asset: Asset, token: str | None) -> tuple[list[tuple[str, bytes]], list[str]]:
    candidates = ("src/main.tsx", "src/main.jsx", "src/main.js", "src/App.tsx", "src/App.jsx")
    entry = next((p for p in candidates if p in asset.files), None)
    if not entry:
        return [], ["React entrypoint not found"]
    text = _read_text(api, asset, entry, token) or ""
    import_line = "import './szl-universal.css';"
    if import_line not in text:
        lines = text.splitlines()
        insert_at = 0
        while insert_at < len(lines) and (lines[insert_at].startswith("import ") or not lines[insert_at].strip()):
            insert_at += 1
        lines.insert(insert_at, import_line)
        text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return [(entry, text.encode()), ("src/szl-universal.css", UNIVERSAL_CSS.encode())], []


def _gradio_ops(api: HfApi, asset: Asset, token: str | None) -> tuple[list[tuple[str, bytes]], list[str]]:
    candidates = ("app.py", "src/app.py", "main.py")
    entry = next((p for p in candidates if p in asset.files), None)
    if not entry:
        return [], ["Gradio entrypoint not found"]
    text = _read_text(api, asset, entry, token) or ""
    if text.count("gr.Blocks(") != 1:
        return [], ["Gradio adapter requires exactly one gr.Blocks constructor"]
    if re.search(r"gr\.Blocks\([^\n]*\bcss\s*=", text):
        if "_SZL_UNIVERSAL_CSS" not in text:
            return [], ["existing Gradio css= contract is source-specific and requires manual integration"]
        return [("szl_universal.css", UNIVERSAL_CSS.encode())], []
    if "from pathlib import Path" not in text:
        text = "from pathlib import Path\n" + text
    definition = '_SZL_UNIVERSAL_CSS = Path(__file__).with_name("szl_universal.css").read_text(encoding="utf-8")\n'
    if definition not in text:
        imports = list(re.finditer(r"^(?:from\s+\S+\s+import\s+.+|import\s+.+)$", text, re.MULTILINE))
        pos = imports[-1].end() if imports else 0
        text = text[:pos] + "\n\n" + definition + text[pos:].lstrip("\n")
    text = text.replace("gr.Blocks(", "gr.Blocks(css=_SZL_UNIVERSAL_CSS, ", 1)
    return [(entry, text.encode()), ("szl_universal.css", UNIVERSAL_CSS.encode())], []


def _streamlit_ops(api: HfApi, asset: Asset, token: str | None) -> tuple[list[tuple[str, bytes]], list[str]]:
    candidates = ("app.py", "streamlit_app.py", "src/app.py")
    entry = next((p for p in candidates if p in asset.files), None)
    if not entry:
        return [], ["Streamlit entrypoint not found"]
    text = _read_text(api, asset, entry, token) or ""
    matches = list(re.finditer(r"^\s*st\.set_page_config\([^\n]*\)\s*$", text, re.MULTILINE))
    if len(matches) != 1:
        return [], ["Streamlit adapter requires one single-line st.set_page_config call"]
    marker = "# szl-universal-frontend:inject"
    if marker not in text:
        if "from pathlib import Path" not in text:
            text = "from pathlib import Path\n" + text
            matches = list(re.finditer(r"^\s*st\.set_page_config\([^\n]*\)\s*$", text, re.MULTILINE))
        match = matches[0]
        inject = '\n# szl-universal-frontend:inject\nst.markdown(f"<style>{Path(__file__).with_name(\'szl_universal.css\').read_text(encoding=\'utf-8\')}</style>", unsafe_allow_html=True)'
        text = text[: match.end()] + inject + text[match.end() :]
    return [(entry, text.encode()), ("szl_universal.css", UNIVERSAL_CSS.encode())], []


def classify_space(api: HfApi, asset: Asset, token: str | None) -> tuple[str, list[tuple[str, bytes]], list[str]]:
    files = set(asset.files)
    if "index.html" in files:
        html = _read_text(api, asset, "index.html", token) or ""
        try:
            return "STATIC_HTML", [("index.html", _inject_style(html).encode())], []
        except ControlError as exc:
            return "STATIC_HTML", [], [str(exc)]
    if any(p in files for p in ("package.json", "vite.config.ts", "vite.config.js")) and any(p.startswith("src/") for p in files):
        ops, blockers = _react_ops(api, asset, token)
        return "REACT", ops, blockers
    py_candidates = [p for p in ("app.py", "streamlit_app.py", "src/app.py", "main.py") if p in files]
    combined = "\n".join((_read_text(api, asset, p, token) or "") for p in py_candidates)
    if "gr.Blocks(" in combined:
        ops, blockers = _gradio_ops(api, asset, token)
        return "GRADIO", ops, blockers
    if "st.set_page_config" in combined or "import streamlit" in combined:
        ops, blockers = _streamlit_ops(api, asset, token)
        return "STREAMLIT", ops, blockers
    return "SOURCE_NATIVE_REQUIRED", [], ["unsupported or ambiguous application shell"]


def enumerate_assets(api: HfApi, org: str) -> list[Asset]:
    refs: list[tuple[str, str]] = []
    refs.extend((item.id, "model") for item in api.list_models(author=org, full=True))
    refs.extend((item.id, "dataset") for item in api.list_datasets(author=org, full=True))
    refs.extend((item.id, "space") for item in api.list_spaces(author=org))
    assets: list[Asset] = []
    for repo_id, repo_type in sorted(set(refs), key=lambda x: (x[1], x[0].lower())):
        info = api.repo_info(repo_id=repo_id, repo_type=repo_type, revision="main")
        sha = getattr(info, "sha", None)
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ControlError(f"{repo_id}: exact main SHA unavailable")
        files = tuple(sorted(api.list_repo_files(repo_id=repo_id, repo_type=repo_type, revision=sha)))
        assets.append(Asset(repo_id=repo_id, repo_type=repo_type, sha=sha, files=files))
    return assets


def _backup(asset: Asset, path: str, data: bytes | None, root: Path) -> None:
    target = root / asset.repo_type / _safe_name(asset.repo_id) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if data is None:
        (target.parent / (target.name + ".absent.json")).write_text(
            json.dumps({"repo_id": asset.repo_id, "repo_type": asset.repo_type, "source_sha": asset.sha, "path": path, "state": "ABSENT"}, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        target.write_bytes(data)


def _discussion_number(url: str | None) -> int | None:
    if not url:
        return None
    match = re.search(r"/discussions/(\d+)", urlparse(url).path)
    return int(match.group(1)) if match else None


def process_asset(api: HfApi, asset: Asset, token: str | None, execute: bool, merge: bool, backups: Path) -> Decision:
    source_bound = False
    source_reason = None
    framework = "CARD_ONLY"
    app_ops: list[tuple[str, bytes]] = []
    blockers: list[str] = []

    if asset.repo_type == "space":
        source_bound, source_reason = _source_bound(api, asset, token)
        if source_bound:
            framework = "GITHUB_SOURCE_BOUND"
        else:
            framework, app_ops, blockers = classify_space(api, asset, token)

    decision = Decision(asset.repo_id, asset.repo_type, asset.sha, "PLANNED", framework)
    decision.blockers.extend(blockers)
    if source_bound:
        decision.state = "SOURCE_BOUND_AUDIT_ONLY"
        decision.blockers.append(source_reason or "external source authority")
        return decision

    existing_readme = _read_bytes(api, asset, "README.md", token)
    readme_text = existing_readme.decode("utf-8") if existing_readme is not None else None
    readme_new = normalize_readme(asset, readme_text, source_bound, framework)
    planned: dict[str, bytes] = {"README.md": readme_new}
    for path, data in app_ops:
        planned[path] = data

    changed: dict[str, bytes] = {}
    for path, data in sorted(planned.items()):
        old = _read_bytes(api, asset, path, token)
        if old != data:
            changed[path] = data
            decision.changes.append(f"{path}:{_sha256(data)}")
            _backup(asset, path, old, backups)

    if not changed:
        decision.state = "CURRENT" if not blockers else "BLOCKED_SOURCE_NATIVE"
        return decision
    if not execute:
        decision.state = "WOULD_CREATE_PR" if not blockers else "WOULD_CREATE_PR_WITH_BLOCKERS"
        return decision

    operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=io.BytesIO(data)) for path, data in changed.items()]
    info = api.create_commit(
        repo_id=asset.repo_id,
        repo_type=asset.repo_type,
        operations=operations,
        commit_message=f"feat(frontend): align universal mobile card and shell ({RELEASE})",
        commit_description=(
            "Revision-bound SZLHOLDINGS universal frontend rollout. "
            "No weights, dataset payloads, hardware, visibility, secrets, or storage are changed."
        ),
        revision="main",
        create_pr=True,
        parent_commit=asset.sha,
    )
    decision.pr_url = getattr(info, "pr_url", None)
    decision.state = "PR_CREATED" if not blockers else "PR_CREATED_WITH_BLOCKERS"

    if merge:
        number = _discussion_number(decision.pr_url)
        if number is None:
            decision.blockers.append("Hugging Face PR discussion number unavailable")
            decision.state = "PR_CREATED_MERGE_BLOCKED"
            return decision
        api.merge_pull_request(repo_id=asset.repo_id, discussion_num=number, repo_type=asset.repo_type)
        after = api.repo_info(repo_id=asset.repo_id, repo_type=asset.repo_type, revision="main")
        decision.resulting_sha = getattr(after, "sha", None)
        decision.merged = True
        decision.state = "MERGED" if not blockers else "MERGED_CARD_BLOCKED_APP"
    return decision


def build_report(org: str, decisions: list[Decision], execute: bool, merge: bool) -> dict[str, Any]:
    states: dict[str, int] = {}
    for item in decisions:
        states[item.state] = states.get(item.state, 0) + 1
    blocked = [d.repo_id for d in decisions if d.blockers]
    failed = [d.repo_id for d in decisions if d.state.startswith("FAILED")]
    return {
        "schema": "szl.hf-universal-frontend-estate/v1",
        "release": RELEASE,
        "organization": org,
        "execute": execute,
        "merge": merge,
        "asset_count": len(decisions),
        "state_counts": states,
        "blocked_assets": blocked,
        "failed_assets": failed,
        "complete": not blocked and not failed,
        "boundaries": [
            "Model weights, tokenizer files, dataset rows/schemas/splits, visibility, hardware, storage, secrets, and allocations are outside this rollout.",
            "GitHub-source-bound Spaces are audit-only and must be repaired at their canonical source repository.",
            "Every write is based on an exact parent commit and is first created as a Hugging Face pull request.",
            "A card or reachable runtime is not evidence of model quality, training provenance, signing, or source/runtime parity.",
        ],
        "assets": [d.as_dict() for d in decisions],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default="SZLHOLDINGS")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args(argv)

    token = os.environ.get("HF_ORG_TOKEN") or os.environ.get("HF_TOKEN")
    if args.execute and not token:
        print("HF_ORG_TOKEN or HF_TOKEN is required for execution", file=sys.stderr)
        return 4
    if args.merge and not args.execute:
        print("--merge requires --execute", file=sys.stderr)
        return 4

    api = HfApi(token=token)
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    decisions: list[Decision] = []
    try:
        assets = enumerate_assets(api, args.org)
    except Exception as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"schema": "szl.hf-universal-frontend-estate/v1", "complete": False, "fatal": str(exc)}, indent=2) + "\n")
        raise

    for asset in assets:
        try:
            decisions.append(process_asset(api, asset, token, args.execute, args.merge, args.backup_dir))
        except (ControlError, HfHubHTTPError, OSError, ValueError) as exc:
            decisions.append(Decision(asset.repo_id, asset.repo_type, asset.sha, "FAILED", blockers=[str(exc)]))
        time.sleep(max(args.sleep, 0))

    report = build_report(args.org, decisions, args.execute, args.merge)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("asset_count", "state_counts", "blocked_assets", "failed_assets", "complete")}, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
