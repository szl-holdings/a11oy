#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Revision-bound, source-aware frontend controller for the SZLHOLDINGS Hub estate.

The controller may update public cards and a small set of deterministic application
shells. It never changes model weights, tokenizer artifacts, dataset payloads,
visibility, hardware, storage, secrets, or repository allocation. GitHub-derived
Spaces are audited read-only and any drift must be repaired at their source repository.
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, HfHubHTTPError

START = "<!-- szl-universal-frontend:start -->"
END = "<!-- szl-universal-frontend:end -->"
STYLE_START = "/* szl-universal-frontend:start */"
STYLE_END = "/* szl-universal-frontend:end */"
RELEASE = "2026-08-17"
REPO_TYPES = ("model", "dataset", "space")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_MAP_SCHEMA = "szl.hf-space-source-map/v1"
SOURCE_MAP_STATES = frozenset({"EXACT", "INFERRED", "DIVERGENT", "UNAVAILABLE"})
DEFAULT_SOURCE_MAP = Path("docs/huggingface-space-source-map-v1.json")

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


@dataclasses.dataclass(frozen=True)
class SpaceAuthority:
    space_id: str
    hf_repository_sha: str
    readme_http_status: int
    readme_sha256: str | None
    state: str
    evidence: str
    canonical_repository: str | None = None
    canonical_revision: str | None = None


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
    source_mapping_state: str | None = None
    canonical_source_repository: str | None = None
    canonical_source_revision: str | None = None
    source_map_readme_sha256: str | None = None
    required_readback_paths: list[str] = dataclasses.field(default_factory=list)
    readback_sha256: dict[str, str] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(repo_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", repo_id)


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA40.fullmatch(value.strip().lower()))


def _require_sha40(value: Any, *, label: str) -> str:
    if not _valid_sha(value):
        raise ControlError(f"{label} must be an exact 40-character hexadecimal revision")
    return str(value).strip().lower()


def load_space_source_map(path: Path, org: str) -> dict[str, SpaceAuthority]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ControlError(f"immutable Space source map is unavailable: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ControlError(f"immutable Space source map is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ControlError("immutable Space source map root must be an object")
    if payload.get("schema") != SOURCE_MAP_SCHEMA:
        raise ControlError(f"immutable Space source map schema must be {SOURCE_MAP_SCHEMA}")
    if payload.get("organization") != org:
        raise ControlError(f"immutable Space source map organization must be {org}")
    if payload.get("github_organization") != "szl-holdings":
        raise ControlError("immutable Space source map GitHub organization must be szl-holdings")
    if payload.get("remote_mutation") is not False:
        raise ControlError("immutable Space source map must declare remote_mutation=false")
    spaces = payload.get("spaces")
    if not isinstance(spaces, list) or not spaces:
        raise ControlError("immutable Space source map spaces must be a nonempty list")

    authorities: dict[str, SpaceAuthority] = {}
    normalized_space_ids: set[str] = set()
    for index, raw in enumerate(spaces):
        if not isinstance(raw, dict):
            raise ControlError(f"immutable Space source map entry {index} must be an object")
        space_id = raw.get("space_id")
        if not isinstance(space_id, str) or not re.fullmatch(
            rf"{re.escape(org)}/[A-Za-z0-9][A-Za-z0-9._-]*", space_id
        ):
            raise ControlError(f"immutable Space source map entry {index} has an invalid space_id")
        normalized_space_id = space_id.casefold()
        if normalized_space_id in normalized_space_ids:
            raise ControlError(f"immutable Space source map repeats {space_id}")
        normalized_space_ids.add(normalized_space_id)
        hf_repository_sha = _require_sha40(
            raw.get("hf_repository_sha"),
            label=f"{space_id} Hugging Face repository revision",
        )
        readme = raw.get("readme")
        if not isinstance(readme, dict):
            raise ControlError(f"{space_id} immutable README evidence must be an object")
        readme_revision = _require_sha40(
            readme.get("revision"),
            label=f"{space_id} README evidence revision",
        )
        if readme_revision != hf_repository_sha:
            raise ControlError(f"{space_id} README evidence revision does not match its Hub revision")
        readme_status = readme.get("http_status")
        if (
            not isinstance(readme_status, int)
            or isinstance(readme_status, bool)
            or not 100 <= readme_status <= 599
        ):
            raise ControlError(f"{space_id} README evidence HTTP status is invalid")
        expected_readme_urls = {
            f"https://huggingface.co/spaces/{space_id}/{route}/"
            f"{hf_repository_sha}/README.md"
            for route in ("raw", "resolve")
        }
        if readme.get("url") not in expected_readme_urls:
            raise ControlError(f"{space_id} README evidence URL is not revision-bound")
        if readme_status == 200:
            readme_sha256 = readme.get("sha256")
            if not isinstance(readme_sha256, str) or not re.fullmatch(
                r"[0-9a-f]{64}", readme_sha256.lower()
            ):
                raise ControlError(f"{space_id} README evidence hash is unavailable")
            readme_sha256 = readme_sha256.lower()
        else:
            readme_sha256 = None
        mapping = raw.get("source_mapping")
        if not isinstance(mapping, dict):
            raise ControlError(f"{space_id} source_mapping must be an object")
        state = mapping.get("state")
        if not isinstance(state, str) or state not in SOURCE_MAP_STATES:
            raise ControlError(f"{space_id} source_mapping state is unsupported: {state!r}")
        evidence = mapping.get("evidence")
        if not isinstance(evidence, str) or not evidence:
            raise ControlError(f"{space_id} source_mapping evidence is unavailable")
        candidates = mapping.get("candidates")
        if not isinstance(candidates, list) or not all(
            isinstance(candidate, dict) for candidate in candidates
        ):
            raise ControlError(f"{space_id} source_mapping candidates must be a list of objects")

        canonical_repository = None
        canonical_revision = None
        canonical = mapping.get("canonical")
        if state in {"EXACT", "INFERRED"}:
            if not isinstance(canonical, dict):
                raise ControlError(f"{space_id} {state} mapping requires a canonical repository")
            full_name = canonical.get("full_name")
            if not isinstance(full_name, str) or not re.fullmatch(
                r"szl-holdings/[A-Za-z0-9_.-]+", full_name
            ):
                raise ControlError(
                    f"{space_id} canonical repository identity is invalid or outside szl-holdings"
                )
            canonical_repository = full_name
            canonical_revision = _require_sha40(
                canonical.get("default_branch_sha"),
                label=f"{space_id} canonical GitHub repository revision",
            )
            matching_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("full_name") == canonical_repository
                and candidate.get("default_branch_sha") == canonical_revision
            ]
            if len(matching_candidates) != 1:
                raise ControlError(
                    f"{space_id} canonical repository revision is not uniquely bound to its candidate"
                )
            workflows = raw.get("workflow_candidates")
            if not isinstance(workflows, dict) or workflows.get("github_ref") != canonical_revision:
                raise ControlError(
                    f"{space_id} workflow evidence is not bound to its canonical GitHub revision"
                )
        elif canonical is not None:
            raise ControlError(f"{space_id} {state} mapping must not claim a canonical repository")

        authorities[space_id] = SpaceAuthority(
            space_id=space_id,
            hf_repository_sha=hf_repository_sha,
            readme_http_status=readme_status,
            readme_sha256=readme_sha256,
            state=state,
            evidence=evidence,
            canonical_repository=canonical_repository,
            canonical_revision=canonical_revision,
        )
    return authorities


def _read_bytes(api: HfApi, asset: Asset, path: str, token: str | bool | None) -> bytes | None:
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


def _read_text(api: HfApi, asset: Asset, path: str, token: str | bool | None) -> str | None:
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
    start_count = text.count(START)
    end_count = text.count(END)
    if start_count != end_count or start_count > 1:
        raise ControlError("managed card markers must form at most one balanced block")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    match = pattern.search(text)
    if start_count == 1 and match is None:
        raise ControlError("managed card markers are out of order")
    if match:
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
| Frontend contract release | `{RELEASE}` |
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


def _read_revision_bytes(
    asset: Asset,
    revision: str,
    path: str,
    token: str | None,
) -> bytes | None:
    try:
        local = hf_hub_download(
            repo_id=asset.repo_id,
            filename=path,
            repo_type=asset.repo_type,
            revision=revision,
            token=token,
        )
        return Path(local).read_bytes()
    except EntryNotFoundError:
        return None


def _space_authority_decision(
    api: HfApi,
    asset: Asset,
    authorities: Mapping[str, SpaceAuthority],
) -> Decision:
    authority = authorities.get(asset.repo_id)
    if authority is None:
        return Decision(
            asset.repo_id,
            asset.repo_type,
            asset.sha,
            "SOURCE_MAP_MISSING",
            "SOURCE_AUTHORITY_BLOCKED",
            blockers=["immutable source-map entry is missing; direct Space Hub writes are denied"],
        )

    decision = Decision(
        asset.repo_id,
        asset.repo_type,
        asset.sha,
        "SOURCE_MAPPING_BLOCKED",
        "SOURCE_AUTHORITY_BLOCKED",
        source_mapping_state=authority.state,
        canonical_source_repository=authority.canonical_repository,
        canonical_source_revision=authority.canonical_revision,
        source_map_readme_sha256=authority.readme_sha256,
    )
    if asset.sha != authority.hf_repository_sha:
        decision.state = "SOURCE_MAP_STALE"
        decision.blockers.append(
            "immutable source-map Hugging Face revision "
            f"{authority.hf_repository_sha} does not match observed {asset.sha}"
        )
        return decision
    if authority.state == "EXACT":
        decision.framework = "GITHUB_SOURCE_BOUND"
        existing_readme = _read_bytes(api, asset, "README.md", False)
        if authority.readme_http_status == 200:
            if existing_readme is None or _sha256(existing_readme) != authority.readme_sha256:
                decision.state = "SOURCE_MAP_STALE"
                decision.blockers.append(
                    "immutable source-map README hash does not match the revision-bound Hub bytes"
                )
                return decision
        elif existing_readme is not None:
            decision.state = "SOURCE_MAP_STALE"
            decision.blockers.append(
                "immutable source-map README status does not match the revision-bound Hub bytes"
            )
            return decision

        readme_text = existing_readme.decode("utf-8") if existing_readme is not None else None
        framework, adapter_ops, adapter_blockers = classify_space(api, asset, False)
        decision.framework = framework
        planned = {
            "README.md": normalize_readme(asset, readme_text, True, framework),
            **dict(adapter_ops),
        }
        decision.required_readback_paths = sorted(planned)
        for path, expected in sorted(planned.items()):
            observed = _read_bytes(api, asset, path, False)
            if observed != expected:
                decision.changes.append(f"{path}:{_sha256(expected)}")
            elif observed is not None:
                decision.readback_sha256[path] = _sha256(observed)
        if adapter_blockers or decision.changes:
            decision.state = "SOURCE_BOUND_REPAIR_REQUIRED"
            decision.blockers.extend(adapter_blockers)
            decision.blockers.append(
                "canonical source is "
                f"{authority.canonical_repository}@{authority.canonical_revision}; "
                "repair through that source repository"
            )
            return decision

        decision.state = "SOURCE_BOUND_VERIFIED"
        return decision
    if authority.state == "INFERRED":
        decision.state = "SOURCE_MAPPING_REVIEW_REQUIRED"
        decision.framework = "GITHUB_SOURCE_INFERRED"
        decision.blockers.append(
            "inferred canonical source requires owner review before source-native repair"
        )
        return decision
    decision.blockers.append(
        f"source mapping is {authority.state} ({authority.evidence}); direct Space Hub writes are denied"
    )
    return decision


def _run_authority_guard(path: Path) -> None:
    try:
        subprocess.run(
            ["bash", str(path)],
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ControlError("exact protected-main authority check failed") from exc


def _python_with_pathlib(text: str) -> str:
    """Insert ``Path`` after the legal Python preamble without moving it."""
    try:
        module = ast.parse(text)
    except SyntaxError as exc:
        raise ControlError(f"Python application source is not syntactically valid: {exc.msg}") from exc

    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
            if any(alias.name == "Path" and alias.asname in {None, "Path"} for alias in node.names):
                return text

    lines = text.splitlines(keepends=True)
    insertion_line = 0
    if lines and lines[0].startswith("#!"):
        insertion_line = 1
    coding = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-_.a-zA-Z0-9]+")
    for line_number, line in enumerate(lines[:2], start=1):
        if coding.match(line):
            insertion_line = max(insertion_line, line_number)

    body_index = 0
    if module.body:
        first = module.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            insertion_line = max(insertion_line, first.end_lineno or first.lineno)
            body_index = 1
    while body_index < len(module.body):
        node = module.body[body_index]
        if not isinstance(node, ast.ImportFrom) or node.module != "__future__":
            break
        insertion_line = max(insertion_line, node.end_lineno or node.lineno)
        body_index += 1

    offset = sum(len(line) for line in lines[:insertion_line])
    prefix = text[:offset]
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += "\n"
    return prefix + "from pathlib import Path\n" + text[offset:]


def _validate_python_adapter(text: str, entry: str) -> None:
    try:
        compile(text, entry, "exec")
    except SyntaxError as exc:
        raise ControlError(f"{entry}: generated Python adapter is invalid: {exc.msg}") from exc


def _html_comment_ranges(html: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = html.find("<!--", cursor)
        stray_end = html.find("-->", cursor)
        if start == -1:
            if stray_end != -1:
                raise ControlError("static HTML has an unmatched comment terminator")
            return ranges
        if stray_end != -1 and stray_end < start:
            raise ControlError("static HTML has an unmatched comment terminator")
        end = html.find("-->", start + 4)
        if end == -1:
            raise ControlError("static HTML has an unclosed comment")
        ranges.append((start, end + 3))
        cursor = end + 3


def _mask_html_comments(html: str, ranges: list[tuple[int, int]]) -> str:
    masked = list(html)
    for start, end in ranges:
        masked[start:end] = " " * (end - start)
    return "".join(masked)


def _inject_style(html: str) -> str:
    comment_ranges = _html_comment_ranges(html)
    visible_html = _mask_html_comments(html, comment_ranges)
    heads = list(re.finditer(r"<head\b[^>]*>", visible_html, re.IGNORECASE))
    head_ends = list(re.finditer(r"</head\s*>", visible_html, re.IGNORECASE))
    if len(heads) != 1 or len(head_ends) != 1 or heads[0].end() > head_ends[0].start():
        raise ControlError("static HTML must contain exactly one head element")

    if STYLE_START in html or STYLE_END in html:
        if html.count(STYLE_START) != 1 or html.count(STYLE_END) != 1:
            raise ControlError("static style markers are duplicated or unbalanced")
        managed_style = re.compile(
            r"<style>\s*"
            + re.escape(STYLE_START)
            + r".*?"
            + re.escape(STYLE_END)
            + r"\s*</style>",
            re.IGNORECASE | re.DOTALL,
        )
        matches = list(managed_style.finditer(html))
        if len(matches) != 1 or any(
            match.start() < comment_end and match.end() > comment_start
            for match in matches
            for comment_start, comment_end in comment_ranges
        ):
            raise ControlError("static style markers must be inside one active canonical style element")
        html = managed_style.sub(f"<style>\n{UNIVERSAL_CSS}</style>", html, count=1)
    else:
        close_start = head_ends[0].start()
        html = html[:close_start] + f"<style>\n{UNIVERSAL_CSS}</style>\n" + html[close_start:]

    visible_head = visible_html[heads[0].end() : head_ends[0].start()]
    if not re.search(r'<meta\s+name=["\']viewport["\']', visible_head, re.IGNORECASE):
        head_end = heads[0].end()
        html = (
            html[:head_end]
            + '\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            + html[head_end:]
        )
    return html


def _react_ops(api: HfApi, asset: Asset, token: str | None) -> tuple[list[tuple[str, bytes]], list[str]]:
    candidates = ("src/main.tsx", "src/main.jsx", "src/main.js", "src/App.tsx", "src/App.jsx")
    entry = next((p for p in candidates if p in asset.files), None)
    if not entry:
        return [], ["React entrypoint not found"]
    text = _read_text(api, asset, entry, token) or ""
    import_line = "import './szl-universal.css';"
    css_import = re.compile(
        r"^[ \t]*import[ \t]+(?:'\./szl-universal\.css'|\"\./szl-universal\.css\")"
        r"[ \t]*;?[ \t]*(?://[^\r\n]*)?$"
    )
    had_newline = text.endswith(("\n", "\r"))
    lines = [line for line in text.splitlines() if not css_import.fullmatch(line)]
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("import ") or not lines[insert_at].strip()
    ):
        insert_at += 1
    lines.insert(insert_at, import_line)
    text = "\n".join(lines) + ("\n" if had_newline else "")
    return [(entry, text.encode()), ("src/szl-universal.css", UNIVERSAL_CSS.encode())], []


def _python_module_alias_available(tree: ast.Module, module: str, alias: str) -> bool:
    imported = any(
        (
            isinstance(node, ast.Import)
            and any(
                item.name == module and (item.asname or item.name) == alias
                for item in node.names
            )
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.module == module
            and any(
                item.name == alias and (item.asname or item.name) == alias
                for item in node.names
            )
        )
        for node in tree.body
    )
    shadowed = any(
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id == alias
        for node in ast.walk(tree)
    ) or any(isinstance(node, ast.arg) and node.arg == alias for node in ast.walk(tree))
    return imported and not shadowed


def _managed_css_read(expression: ast.AST) -> bool:
    if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Attribute):
        return False
    if expression.func.attr != "read_text" or expression.args:
        return False
    if len(expression.keywords) != 1:
        return False
    encoding = expression.keywords[0]
    if (
        encoding.arg != "encoding"
        or not isinstance(encoding.value, ast.Constant)
        or encoding.value.value != "utf-8"
    ):
        return False
    with_name = expression.func.value
    if (
        not isinstance(with_name, ast.Call)
        or len(with_name.args) != 1
        or with_name.keywords
        or not isinstance(with_name.func, ast.Attribute)
        or with_name.func.attr != "with_name"
        or not isinstance(with_name.args[0], ast.Constant)
        or with_name.args[0].value != "szl_universal.css"
    ):
        return False
    path = with_name.func.value
    return (
        isinstance(path, ast.Call)
        and not path.keywords
        and len(path.args) == 1
        and isinstance(path.func, ast.Name)
        and path.func.id == "Path"
        and isinstance(path.args[0], ast.Name)
        and path.args[0].id == "__file__"
    )


def _direct_module_calls(tree: ast.Module) -> list[ast.Call]:
    calls: list[ast.Call] = []

    def collect(statements: list[ast.stmt]) -> None:
        for statement in statements:
            expression: ast.AST | None = None
            if isinstance(statement, ast.Expr):
                expression = statement.value
            elif isinstance(statement, ast.Assign):
                expression = statement.value
            elif isinstance(statement, ast.AnnAssign):
                expression = statement.value
            if isinstance(expression, ast.Call):
                calls.append(expression)
                continue
            if isinstance(statement, (ast.With, ast.AsyncWith)):
                calls.extend(
                    item.context_expr
                    for item in statement.items
                    if isinstance(item.context_expr, ast.Call)
                )
                collect(statement.body)

    collect(tree.body)
    return calls


def _managed_gradio_binding(text: str) -> bool:
    tree = ast.parse(text)
    if not _python_module_alias_available(tree, "gradio", "gr"):
        return False
    if not _python_module_alias_available(tree, "pathlib", "Path"):
        return False
    bindings = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "_SZL_UNIVERSAL_CSS"
        and _managed_css_read(node.value)
    ]
    stores = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id == "_SZL_UNIVERSAL_CSS"
    )
    if len(bindings) != 1 or stores != 1:
        return False
    for call in _direct_module_calls(tree):
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "gr"
            and call.func.attr == "Blocks"
        ):
            continue
        css_keywords = [keyword for keyword in call.keywords if keyword.arg == "css"]
        if (
            len(css_keywords) == 1
            and isinstance(css_keywords[0].value, ast.Name)
            and css_keywords[0].value.id == "_SZL_UNIVERSAL_CSS"
        ):
            return True
    return False


def _gradio_has_css_keyword(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ControlError(f"Gradio application source is not syntactically valid: {exc.msg}") from exc
    return any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "gr"
        and call.func.attr == "Blocks"
        and any(keyword.arg == "css" for keyword in call.keywords)
        for call in ast.walk(tree)
    )


def _managed_style_expression(expression: ast.AST) -> bool:
    if not isinstance(expression, ast.JoinedStr) or len(expression.values) != 3:
        return False
    start, css, end = expression.values
    return (
        isinstance(start, ast.Constant)
        and start.value == "<style>"
        and isinstance(css, ast.FormattedValue)
        and _managed_css_read(css.value)
        and isinstance(end, ast.Constant)
        and end.value == "</style>"
    )


def _managed_streamlit_binding(text: str) -> bool:
    marker = "# szl-universal-frontend:inject"
    if text.splitlines().count(marker) != 1:
        return False
    tree = ast.parse(text)
    if not _python_module_alias_available(tree, "streamlit", "st"):
        return False
    if not _python_module_alias_available(tree, "pathlib", "Path"):
        return False
    for call in _direct_module_calls(tree):
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "st"
            and call.func.attr == "markdown"
            and call.args
            and _managed_style_expression(call.args[0])
        ):
            continue
        unsafe = next(
            (keyword.value for keyword in call.keywords if keyword.arg == "unsafe_allow_html"),
            None,
        )
        if isinstance(unsafe, ast.Constant) and unsafe.value is True:
            return True
    return False


def _gradio_ops(api: HfApi, asset: Asset, token: str | None) -> tuple[list[tuple[str, bytes]], list[str]]:
    candidates = ("app.py", "src/app.py", "main.py")
    entry = next((p for p in candidates if p in asset.files), None)
    if not entry:
        return [], ["Gradio entrypoint not found"]
    text = _read_text(api, asset, entry, token) or ""
    if text.count("gr.Blocks(") != 1:
        return [], ["Gradio adapter requires exactly one gr.Blocks constructor"]
    managed_constructor = "gr.Blocks(css=_SZL_UNIVERSAL_CSS, "
    text = text.replace(managed_constructor, "gr.Blocks(", 1)
    try:
        has_css_keyword = _gradio_has_css_keyword(text)
    except ControlError as exc:
        return [], [str(exc)]
    if has_css_keyword:
        return [], ["existing Gradio css= contract is source-specific and requires manual integration"]
    text = _python_with_pathlib(text)
    definition = '_SZL_UNIVERSAL_CSS = Path(__file__).with_name("szl_universal.css").read_text(encoding="utf-8")\n'
    text = text.replace(definition, "")
    imports = list(re.finditer(r"^(?:from\s+\S+\s+import\s+.+|import\s+.+)$", text, re.MULTILINE))
    pos = imports[-1].end() if imports else 0
    text = text[:pos] + "\n\n" + definition + text[pos:].lstrip("\n")
    text = text.replace("gr.Blocks(", "gr.Blocks(css=_SZL_UNIVERSAL_CSS, ", 1)
    _validate_python_adapter(text, entry)
    if not _managed_gradio_binding(text):
        return [], ["generated Gradio CSS binding is not a direct unshadowed module operation"]
    stylesheet = str(PurePosixPath(entry).with_name("szl_universal.css"))
    return [(entry, text.encode()), (stylesheet, UNIVERSAL_CSS.encode())], []


def _streamlit_ops(api: HfApi, asset: Asset, token: str | None) -> tuple[list[tuple[str, bytes]], list[str]]:
    candidates = ("app.py", "streamlit_app.py", "src/app.py")
    entry = next((p for p in candidates if p in asset.files), None)
    if not entry:
        return [], ["Streamlit entrypoint not found"]
    text = _read_text(api, asset, entry, token) or ""
    matches = list(re.finditer(r"^\s*st\.set_page_config\([^\n]*\)\s*$", text, re.MULTILINE))
    if len(matches) != 1:
        return [], ["Streamlit adapter requires one single-line st.set_page_config call"]
    inject = '\n# szl-universal-frontend:inject\nst.markdown(f"<style>{Path(__file__).with_name(\'szl_universal.css\').read_text(encoding=\'utf-8\')}</style>", unsafe_allow_html=True)'
    text = text.replace(inject, "")
    text = _python_with_pathlib(text)
    matches = list(re.finditer(r"^\s*st\.set_page_config\([^\n]*\)\s*$", text, re.MULTILINE))
    match = matches[0]
    text = text[: match.end()] + inject + text[match.end() :]
    _validate_python_adapter(text, entry)
    if not _managed_streamlit_binding(text):
        return [], ["generated Streamlit CSS binding is not a direct unshadowed module operation"]
    stylesheet = str(PurePosixPath(entry).with_name("szl_universal.css"))
    return [(entry, text.encode()), (stylesheet, UNIVERSAL_CSS.encode())], []


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
    listings = (
        (api.list_models(author=org, full=True, token=False), "model"),
        (api.list_datasets(author=org, full=True, token=False), "dataset"),
        (api.list_spaces(author=org, full=True, token=False), "space"),
    )
    for items, repo_type in listings:
        refs.extend(
            (item.id, repo_type)
            for item in items
            if getattr(item, "private", None) is False
        )
    assets: list[Asset] = []
    for repo_id, repo_type in sorted(set(refs), key=lambda x: (x[1], x[0].lower())):
        info = api.repo_info(
            repo_id=repo_id,
            repo_type=repo_type,
            revision="main",
            token=False,
        )
        if getattr(info, "private", None) is not False:
            continue
        sha = getattr(info, "sha", None)
        if not _valid_sha(sha):
            raise ControlError(f"{repo_id}: exact main SHA unavailable")
        files = tuple(
            sorted(
                api.list_repo_files(
                    repo_id=repo_id,
                    repo_type=repo_type,
                    revision=sha,
                    token=False,
                )
            )
        )
        assets.append(
            Asset(
                repo_id=repo_id,
                repo_type=repo_type,
                sha=str(sha).lower(),
                files=files,
            )
        )
    return assets


def validate_space_inventory_authorities(
    assets: Iterable[Asset],
    authorities: Mapping[str, SpaceAuthority],
) -> list[Asset]:
    spaces: dict[str, Asset] = {}
    normalized_ids: set[str] = set()
    for item in assets:
        if item.repo_type != "space":
            continue
        normalized_id = item.repo_id.casefold()
        if normalized_id in normalized_ids:
            raise ControlError(f"public Space inventory repeats {item.repo_id}")
        normalized_ids.add(normalized_id)
        spaces[item.repo_id] = item

    missing = sorted(set(spaces) - set(authorities), key=str.casefold)
    unobserved = sorted(set(authorities) - set(spaces), key=str.casefold)
    if missing or unobserved:
        details: list[str] = []
        if missing:
            details.append(f"missing source-map entries: {', '.join(missing)}")
        if unobserved:
            details.append(f"unobserved source-map entries: {', '.join(unobserved)}")
        raise ControlError("public Space inventory does not match immutable source map (" + "; ".join(details) + ")")

    stale = [
        f"{repo_id}: map {authorities[repo_id].hf_repository_sha}, observed {item.sha}"
        for repo_id, item in sorted(spaces.items(), key=lambda pair: pair[0].casefold())
        if item.sha != authorities[repo_id].hf_repository_sha
    ]
    if stale:
        raise ControlError("public Space inventory has stale source-map revisions (" + "; ".join(stale) + ")")
    return sorted(spaces.values(), key=lambda item: item.repo_id.casefold())


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


def process_asset(
    api: HfApi,
    asset: Asset,
    token: str | None,
    execute: bool,
    merge: bool,
    backups: Path,
    *,
    space_authorities: Mapping[str, SpaceAuthority],
    authority_guard: Callable[[], None] | None = None,
) -> Decision:
    framework = "CARD_ONLY"
    blockers: list[str] = []

    if asset.repo_type == "space":
        return _space_authority_decision(api, asset, space_authorities)

    decision = Decision(asset.repo_id, asset.repo_type, asset.sha, "PLANNED", framework)
    decision.blockers.extend(blockers)

    existing_readme = _read_bytes(api, asset, "README.md", token)
    readme_text = existing_readme.decode("utf-8") if existing_readme is not None else None
    readme_new = normalize_readme(asset, readme_text, False, framework)
    planned: dict[str, bytes] = {"README.md": readme_new}

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

    if authority_guard is None:
        decision.state = "AUTHORITY_GUARD_MISSING"
        decision.blockers.append("exact protected-main authority guard is required before provider mutation")
        return decision
    try:
        authority_guard()
    except ControlError as exc:
        decision.state = "AUTHORITY_LOST"
        decision.blockers.append(str(exc))
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
        try:
            authority_guard()
        except ControlError as exc:
            decision.state = "PR_CREATED_AUTHORITY_LOST"
            decision.blockers.append(str(exc))
            return decision
        try:
            api.merge_pull_request(
                repo_id=asset.repo_id,
                discussion_num=number,
                repo_type=asset.repo_type,
            )
        except (HfHubHTTPError, OSError, ValueError) as exc:
            decision.state = "PR_CREATED_MERGE_FAILED"
            decision.blockers.append(f"Hugging Face pull-request merge failed: {exc}")
            return decision
        decision.merged = True
        try:
            after = api.repo_info(
                repo_id=asset.repo_id,
                repo_type=asset.repo_type,
                revision="main",
            )
        except (HfHubHTTPError, OSError, ValueError) as exc:
            decision.state = "MERGED_READBACK_FAILED"
            decision.blockers.append(f"post-merge Hugging Face main readback failed: {exc}")
            return decision
        resulting_sha = getattr(after, "sha", None)
        if _valid_sha(resulting_sha):
            decision.resulting_sha = str(resulting_sha).strip().lower()
        if not decision.resulting_sha:
            decision.state = "MERGED_READBACK_FAILED"
            decision.blockers.append("post-merge Hugging Face main revision is unavailable")
            return decision
        if decision.resulting_sha == asset.sha:
            decision.state = "MERGED_READBACK_FAILED"
            decision.blockers.append("post-merge Hugging Face main did not advance from the observed parent")
            return decision
        for path, expected in sorted(changed.items()):
            try:
                observed = _read_revision_bytes(
                    asset,
                    decision.resulting_sha,
                    path,
                    token,
                )
            except (HfHubHTTPError, OSError, ValueError) as exc:
                decision.blockers.append(f"post-merge readback failed for {path}: {exc}")
                continue
            if observed is None:
                decision.blockers.append(f"post-merge readback is missing {path}")
                continue
            observed_sha256 = _sha256(observed)
            decision.readback_sha256[path] = observed_sha256
            expected_sha256 = _sha256(expected)
            if observed_sha256 != expected_sha256:
                decision.blockers.append(
                    f"post-merge readback mismatch for {path}: "
                    f"expected {expected_sha256}, observed {observed_sha256}"
                )
        decision.state = "MERGED_READBACK_FAILED" if decision.blockers else "MERGED_VERIFIED"
    return decision


def _decision_is_terminal_verified(decision: Decision) -> bool:
    if decision.state == "SOURCE_BOUND_VERIFIED":
        return (
            decision.repo_type == "space"
            and not decision.blockers
            and not decision.changes
            and decision.source_mapping_state == "EXACT"
            and bool(decision.canonical_source_repository)
            and _valid_sha(decision.canonical_source_revision)
            and isinstance(decision.source_map_readme_sha256, str)
            and bool(SHA256.fullmatch(decision.source_map_readme_sha256))
            and decision.readback_sha256.get("README.md")
            == decision.source_map_readme_sha256
            and "README.md" in decision.required_readback_paths
            and set(decision.readback_sha256) == set(decision.required_readback_paths)
        )
    if decision.state not in {"CURRENT", "MERGED_VERIFIED"} or decision.blockers:
        return False
    if decision.state == "CURRENT":
        return not decision.changes
    return (
        decision.merged
        and _valid_sha(decision.resulting_sha)
        and decision.resulting_sha != decision.source_sha
        and bool(decision.readback_sha256)
    )


def build_report(
    org: str,
    decisions: list[Decision],
    execute: bool,
    merge: bool,
    *,
    source_map_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    states: dict[str, int] = {}
    for item in decisions:
        states[item.state] = states.get(item.state, 0) + 1
    blocked = [d.repo_id for d in decisions if d.blockers]
    failed = [
        d.repo_id
        for d in decisions
        if d.state.startswith("FAILED") or d.state.endswith("_FAILED")
    ]
    nonterminal = [
        d.repo_id
        for d in decisions
        if not _decision_is_terminal_verified(d)
    ]
    complete = bool(decisions) and execute and merge and not blocked and not failed and not nonterminal
    return {
        "schema": "szl.hf-universal-frontend-estate/v1",
        "release": RELEASE,
        "organization": org,
        "source_map": source_map_identity,
        "execute": execute,
        "merge": merge,
        "asset_count": len(decisions),
        "state_counts": states,
        "blocked_assets": blocked,
        "failed_assets": failed,
        "nonterminal_assets": nonterminal,
        "completion_eligible": bool(execute and merge),
        "complete": complete,
        "boundaries": [
            "Model weights, tokenizer files, dataset rows/schemas/splits, visibility, hardware, storage, secrets, and allocations are outside this rollout.",
            "GitHub-source-bound Spaces are audit-only; any drift must be repaired at their canonical source repository.",
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
    parser.add_argument("--source-map", type=Path, default=DEFAULT_SOURCE_MAP)
    parser.add_argument("--authority-guard", type=Path)
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
    if args.execute and args.authority_guard is None:
        print("--authority-guard is required for execution", file=sys.stderr)
        return 4

    args.backup_dir.mkdir(parents=True, exist_ok=True)
    decisions: list[Decision] = []
    try:
        space_authorities = load_space_source_map(args.source_map, args.org)
        source_map_identity = {
            "schema": SOURCE_MAP_SCHEMA,
            "path": str(args.source_map),
            "sha256": _sha256(args.source_map.read_bytes()),
            "space_count": len(space_authorities),
        }
        if args.authority_guard is not None and not args.authority_guard.is_file():
            raise ControlError(f"authority guard is unavailable: {args.authority_guard}")
        api = HfApi(token=token)
        public_inventory_api = HfApi()
        assets = enumerate_assets(public_inventory_api, args.org)
        spaces = validate_space_inventory_authorities(assets, space_authorities)
        space_preflight = {
            item.repo_id: _space_authority_decision(public_inventory_api, item, space_authorities)
            for item in spaces
        }
        provider_mutation_admitted = all(
            _decision_is_terminal_verified(decision)
            for decision in space_preflight.values()
        )
    except Exception as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"schema": "szl.hf-universal-frontend-estate/v1", "complete": False, "fatal": str(exc)}, indent=2) + "\n")
        print(json.dumps({"status": "BLOCKED", "fatal": str(exc)}, indent=2, sort_keys=True))
        return 4

    authority_guard = None
    if args.authority_guard is not None:
        authority_guard = lambda: _run_authority_guard(args.authority_guard)

    for asset in assets:
        if asset.repo_type == "space":
            decisions.append(space_preflight[asset.repo_id])
            time.sleep(max(args.sleep, 0))
            continue
        try:
            decisions.append(
                process_asset(
                    api,
                    asset,
                    token,
                    args.execute and provider_mutation_admitted,
                    args.merge and provider_mutation_admitted,
                    args.backup_dir,
                    space_authorities=space_authorities,
                    authority_guard=authority_guard,
                )
            )
        except (ControlError, HfHubHTTPError, OSError, ValueError) as exc:
            decisions.append(Decision(asset.repo_id, asset.repo_type, asset.sha, "FAILED", blockers=[str(exc)]))
        time.sleep(max(args.sleep, 0))

    report = build_report(
        args.org,
        decisions,
        args.execute,
        args.merge,
        source_map_identity=source_map_identity,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("asset_count", "state_counts", "blocked_assets", "failed_assets", "complete")}, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
