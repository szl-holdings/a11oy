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
import ast
import dataclasses
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request
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
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_MAP = ROOT / "docs" / "huggingface-space-source-map-v1.json"
PROTECTED_SPACES = {"SZLHOLDINGS/README", "SZLHOLDINGS/a11oy"}
SOURCE_BOUND_READBACK_URLS = {
    "SZLHOLDINGS/README": "https://szlholdings-readme.static.hf.space/deployment.json",
    "SZLHOLDINGS/a11oy": "https://szlholdings-a11oy.hf.space/api/build-info",
}
PROTECTED_WORKFLOW_SOURCE_SPACES = frozenset({"SZLHOLDINGS/a11oy"})
STATIC_MANIFEST_READBACK_SPACES = frozenset({"SZLHOLDINGS/README"})
REPO_TYPES = ("model", "dataset", "space")
TERMINAL_VERIFIED_STATES = frozenset({"CURRENT", "MERGED", "SOURCE_BOUND_VERIFIED"})
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_MAPPING_STATES = frozenset({"EXACT", "INFERRED", "DIVERGENT", "UNAVAILABLE"})

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
class SourceMapDocument:
    path: Path
    sha256: str
    organization: str
    entries: dict[str, dict[str, Any]]

    def report_identity(self) -> dict[str, Any]:
        return {
            "schema": "szl.hf-space-source-map/v1",
            "path": str(self.path),
            "sha256": self.sha256,
            "space_count": len(self.entries),
        }


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
    evidence: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(repo_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", repo_id)


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA40.fullmatch(value.strip().lower()))


def _value(node: Any, key: str) -> Any:
    if isinstance(node, dict):
        return node.get(key)
    return getattr(node, key, None)


def load_source_map(path: Path, org: str) -> SourceMapDocument:
    """Load the protected, read-only source authority map before any provider write."""
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError(f"source map {path} is unavailable or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ControlError("source map root must be a JSON object")
    if payload.get("schema") != "szl.hf-space-source-map/v1":
        raise ControlError("source map schema is not szl.hf-space-source-map/v1")
    if payload.get("organization") != org:
        raise ControlError(
            f"source map organization {payload.get('organization')!r} does not equal {org!r}"
        )
    if payload.get("remote_mutation") is not False:
        raise ControlError("source map must declare remote_mutation=false")
    spaces = payload.get("spaces")
    if not isinstance(spaces, list) or not spaces:
        raise ControlError("source map must contain at least one Space record")

    entries: dict[str, dict[str, Any]] = {}
    expected_prefix = org.lower() + "/"
    for position, record in enumerate(spaces):
        if not isinstance(record, dict):
            raise ControlError(f"source map Space record {position} is not an object")
        space_id = record.get("space_id")
        if not isinstance(space_id, str) or not space_id.lower().startswith(expected_prefix):
            raise ControlError(f"source map Space record {position} has invalid identity")
        key = space_id.lower()
        if key in entries:
            raise ControlError(f"source map contains duplicate Space identity {space_id}")
        if not _valid_sha(record.get("hf_repository_sha")):
            raise ControlError(f"source map {space_id} has no immutable Hugging Face revision")
        mapping = record.get("source_mapping")
        if not isinstance(mapping, dict) or mapping.get("state") not in SOURCE_MAPPING_STATES:
            raise ControlError(f"source map {space_id} has an invalid mapping state")
        canonical = mapping.get("canonical")
        if canonical is not None and not isinstance(canonical, dict):
            raise ControlError(f"source map {space_id} canonical source must be an object or null")
        candidates = mapping.get("candidates")
        if not isinstance(candidates, list) or not all(
            isinstance(candidate, dict) for candidate in candidates
        ):
            raise ControlError(f"source map {space_id} candidates must be objects")
        readme = record.get("readme")
        if not isinstance(readme, dict):
            raise ControlError(f"source map {space_id} has no README observation")
        entries[key] = record

    return SourceMapDocument(
        path=path,
        sha256=_sha256(raw),
        organization=org,
        entries=entries,
    )


def evaluate_space_source_mapping(
    asset: Asset,
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the only source-map decision that may admit a direct Hub proposal.

    `UNAVAILABLE` means Hub-native only when source discovery is bound to the exact
    currently observed Hub revision. Every other state remains source-native or
    blocked; unbound `EXACT`/`INFERRED` evidence never falls back to Hub mutation.
    """
    if asset.repo_type != "space":
        raise ControlError("source-map authority applies only to Spaces")
    evidence: dict[str, Any] = {
        "reported_state": None,
        "effective_state": "BLOCKED_SOURCE_MAPPING",
        "direct_hub_mutation_allowed": False,
        "canonical_repository": None,
        "canonical_source_revision": None,
        "failures": [],
    }
    failures: list[str] = evidence["failures"]
    if record is None:
        failures.append("SOURCE_MAP_ENTRY_MISSING")
        return evidence

    mapped_id = record.get("space_id")
    mapping = record.get("source_mapping")
    readme = record.get("readme")
    if not isinstance(mapping, dict) or not isinstance(readme, dict):
        failures.append("SOURCE_MAP_RECORD_INVALID")
        return evidence
    state = mapping.get("state")
    evidence["reported_state"] = state
    if mapped_id != asset.repo_id:
        failures.append("SOURCE_MAP_IDENTITY_DIVERGED")
    mapped_hf_sha = record.get("hf_repository_sha")
    if mapped_hf_sha != asset.sha:
        failures.append("SOURCE_MAP_HF_REVISION_DIVERGED")
    if readme.get("revision") != asset.sha:
        failures.append("SOURCE_MAP_README_REVISION_UNBOUND")
    readme_status = readme.get("http_status")
    readme_url = readme.get("url")
    readme_digest = readme.get("sha256")
    if (
        not isinstance(readme_status, int)
        or isinstance(readme_status, bool)
        or not 100 <= readme_status <= 599
    ):
        failures.append("SOURCE_MAP_README_STATUS_INVALID")
    if not isinstance(readme_url, str) or f"/{asset.sha}/README.md" not in readme_url:
        failures.append("SOURCE_MAP_README_URL_UNBOUND")
    if readme_status == 200 and not (
        isinstance(readme_digest, str) and SHA256.fullmatch(readme_digest.lower())
    ):
        failures.append("SOURCE_MAP_README_DIGEST_INVALID")
    if state not in SOURCE_MAPPING_STATES:
        failures.append("SOURCE_MAPPING_STATE_INVALID")
        return evidence

    canonical = mapping.get("canonical")
    if state in {"EXACT", "INFERRED"}:
        if not isinstance(canonical, dict):
            failures.append("CANONICAL_SOURCE_REPOSITORY_UNAVAILABLE")
        else:
            repository = canonical.get("full_name")
            revision = canonical.get("default_branch_sha")
            if not isinstance(repository, str) or not repository:
                failures.append("CANONICAL_SOURCE_REPOSITORY_UNAVAILABLE")
            else:
                evidence["canonical_repository"] = repository
            if not _valid_sha(revision):
                failures.append("CANONICAL_SOURCE_REVISION_UNAVAILABLE")
            else:
                evidence["canonical_source_revision"] = str(revision).lower()
            candidates = mapping.get("candidates")
            matching_candidates = [
                candidate
                for candidate in candidates
                if isinstance(candidate.get("full_name"), str)
                and isinstance(repository, str)
                and candidate["full_name"].lower() == repository.lower()
                and candidate.get("default_branch_sha") == revision
            ]
            if len(matching_candidates) != 1:
                failures.append("CANONICAL_SOURCE_CANDIDATE_UNBOUND")
            workflows = record.get("workflow_candidates")
            if not isinstance(workflows, dict) or workflows.get("github_ref") != revision:
                failures.append("SOURCE_WORKFLOW_REVISION_UNBOUND")
        if failures:
            return evidence
        if state == "INFERRED":
            evidence["effective_state"] = "SOURCE_REPOSITORY_REVIEW_REQUIRED"
            failures.append("INFERRED_SOURCE_REQUIRES_OWNER_CONFIRMATION")
        else:
            evidence["effective_state"] = "SOURCE_REPOSITORY_REQUIRED"
        return evidence

    if state == "DIVERGENT":
        failures.append("SOURCE_MAPPING_DIVERGENT")
        return evidence

    if canonical is not None or mapping.get("candidates") or mapping.get("missing_candidates"):
        failures.append("UNAVAILABLE_SOURCE_MAPPING_HAS_CANDIDATES")
    if failures:
        return evidence
    evidence["effective_state"] = "HUB_NATIVE_ELIGIBLE"
    evidence["direct_hub_mutation_allowed"] = True
    return evidence


def _find_source_revision(node: Any) -> str | None:
    if isinstance(node, dict):
        for key in ("source_sha", "source_revision", "github_sha", "commit_sha", "revision"):
            value = node.get(key)
            if _valid_sha(value):
                return str(value).strip().lower()
        for value in node.values():
            found = _find_source_revision(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_source_revision(value)
            if found:
                return found
    return None


def _read_json_url(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SZL-HF-universal-frontend/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ControlError(f"public source readback from {url} is not a JSON object")
    return payload


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


def _source_bound(api: HfApi, asset: Asset, token: str | bool | None) -> tuple[bool, str | None]:
    if asset.repo_id in PROTECTED_SPACES:
        return True, "protected canonical GitHub-derived Space"
    deployment = _read_text(api, asset, "deployment.json", token)
    if deployment:
        lowered = deployment.lower()
        if "github" in lowered or "source_revision" in lowered or "source-revision" in lowered:
            return True, "deployment.json records external source provenance"
    return False, None


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
        ast.parse(text, filename=entry)
    except SyntaxError as exc:
        raise ControlError(f"{entry}: generated Python adapter is invalid: {exc.msg}") from exc


def evaluate_source_bound_evidence(
    asset: Asset,
    repository: Any,
    deployment: dict[str, Any],
    public_readback: dict[str, Any],
) -> dict[str, Any]:
    repository_sha = _value(repository, "sha")
    runtime = _value(repository, "runtime")
    runtime_raw = _value(runtime, "raw")
    runtime_sha = _value(runtime, "sha") or _value(runtime_raw, "sha")
    runtime_stage = _value(runtime, "stage")
    deployment_source = _find_source_revision(deployment)
    served_source = _find_source_revision(public_readback)
    failures: list[str] = []
    if repository_sha != asset.sha:
        failures.append("HF_REPOSITORY_REVISION_DIVERGED")
    if runtime_stage != "RUNNING":
        failures.append("HF_RUNTIME_REVISION_NOT_RUNNING")
    if asset.repo_id not in STATIC_MANIFEST_READBACK_SPACES and runtime_sha != asset.sha:
        failures.append("HF_RUNTIME_REVISION_DIVERGED")
    if not deployment_source:
        failures.append("CANONICAL_SOURCE_REVISION_UNAVAILABLE")
    if not served_source:
        failures.append("SERVED_SOURCE_REVISION_UNAVAILABLE")
    if deployment_source and served_source and deployment_source != served_source:
        failures.append("SERVED_SOURCE_REVISION_DIVERGED")
    deployment_digest = _sha256(json.dumps(deployment, sort_keys=True, separators=(",", ":")).encode())
    readback_digest = _sha256(json.dumps(public_readback, sort_keys=True, separators=(",", ":")).encode())
    if asset.repo_id in STATIC_MANIFEST_READBACK_SPACES and deployment_digest != readback_digest:
        failures.append("SERVED_DEPLOYMENT_MANIFEST_DIVERGED")
    return {
        "status": "VERIFIED" if not failures else "BLOCKED",
        "hf_repository_sha": repository_sha,
        "hf_runtime_sha": runtime_sha,
        "hf_runtime_stage": runtime_stage,
        "canonical_source_revision": deployment_source,
        "served_source_revision": served_source,
        "deployment_digest": deployment_digest,
        "served_readback_digest": readback_digest,
        "failures": failures,
    }


def verify_source_bound_asset(
    api: HfApi,
    asset: Asset,
    protected_source_sha: str | None = None,
) -> dict[str, Any]:
    readback_url = SOURCE_BOUND_READBACK_URLS.get(asset.repo_id)
    if not readback_url:
        return {
            "status": "BLOCKED",
            "failures": ["PUBLIC_SOURCE_READBACK_UNCONFIGURED"],
        }
    try:
        deployment_text = _read_text(api, asset, "deployment.json", False)
        if deployment_text:
            deployment = json.loads(deployment_text)
        elif asset.repo_id in PROTECTED_WORKFLOW_SOURCE_SPACES and _valid_sha(protected_source_sha):
            deployment = {
                "source_revision": str(protected_source_sha).strip().lower(),
                "source_revision_authority": "protected_workflow_checkout",
            }
        else:
            raise ControlError("public deployment manifest or protected source revision is unavailable")
        if not isinstance(deployment, dict):
            raise ControlError("public deployment manifest is not a JSON object")
        repository = api.repo_info(
            repo_id=asset.repo_id,
            repo_type=asset.repo_type,
            revision="main",
            token=False,
        )
        public_readback = _read_json_url(readback_url)
    except (ControlError, HfHubHTTPError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "BLOCKED",
            "failures": [f"PUBLIC_SOURCE_READBACK_FAILED:{type(exc).__name__}"],
        }
    evidence = evaluate_source_bound_evidence(
        asset,
        repository,
        deployment,
        public_readback,
    )
    evidence["readback_url"] = readback_url
    return evidence


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
    text = _python_with_pathlib(text)
    definition = '_SZL_UNIVERSAL_CSS = Path(__file__).with_name("szl_universal.css").read_text(encoding="utf-8")\n'
    if definition not in text:
        imports = list(re.finditer(r"^(?:from\s+\S+\s+import\s+.+|import\s+.+)$", text, re.MULTILINE))
        pos = imports[-1].end() if imports else 0
        text = text[:pos] + "\n\n" + definition + text[pos:].lstrip("\n")
    text = text.replace("gr.Blocks(", "gr.Blocks(css=_SZL_UNIVERSAL_CSS, ", 1)
    _validate_python_adapter(text, entry)
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
        text = _python_with_pathlib(text)
        matches = list(re.finditer(r"^\s*st\.set_page_config\([^\n]*\)\s*$", text, re.MULTILINE))
        match = matches[0]
        inject = '\n# szl-universal-frontend:inject\nst.markdown(f"<style>{Path(__file__).with_name(\'szl_universal.css\').read_text(encoding=\'utf-8\')}</style>", unsafe_allow_html=True)'
        text = text[: match.end()] + inject + text[match.end() :]
    _validate_python_adapter(text, entry)
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
    source_mapping: dict[str, Any] | None,
    protected_source_sha: str | None = None,
) -> Decision:
    source_bound = False
    source_reason = None
    framework = "CARD_ONLY"
    app_ops: list[tuple[str, bytes]] = []
    blockers: list[str] = []
    mapping_evidence: dict[str, Any] | None = None

    if asset.repo_type == "space":
        mapping_evidence = evaluate_space_source_mapping(asset, source_mapping)
        source_bound, source_reason = _source_bound(api, asset, False)
        mapping_state = mapping_evidence["effective_state"]
        if mapping_state in {
            "SOURCE_REPOSITORY_REQUIRED",
            "SOURCE_REPOSITORY_REVIEW_REQUIRED",
        }:
            source_bound = True
            source_reason = (
                f"source map {mapping_evidence['reported_state']} binds "
                f"{mapping_evidence['canonical_repository']}@"
                f"{mapping_evidence['canonical_source_revision']}"
            )
        if not mapping_evidence["direct_hub_mutation_allowed"] and not source_bound:
            framework = "SOURCE_MAPPING_BLOCKED"
        elif source_bound:
            framework = "GITHUB_SOURCE_BOUND"
        else:
            framework, app_ops, blockers = classify_space(api, asset, token)

    decision = Decision(asset.repo_id, asset.repo_type, asset.sha, "PLANNED", framework)
    decision.blockers.extend(blockers)
    if mapping_evidence is not None:
        decision.evidence["source_mapping"] = mapping_evidence
        if not mapping_evidence["direct_hub_mutation_allowed"] and not source_bound:
            decision.state = "SOURCE_MAPPING_BLOCKED"
            decision.blockers.extend(mapping_evidence["failures"])
            if not decision.blockers:
                decision.blockers.append("SOURCE_MAP_DIRECT_HUB_MUTATION_DENIED")
            return decision
    if source_bound:
        evidence = verify_source_bound_asset(api, asset, protected_source_sha)
        decision.evidence["source_bound_readback"] = evidence
        mapping_failures = mapping_evidence["failures"] if mapping_evidence else []
        if (
            mapping_evidence
            and mapping_evidence["effective_state"] == "SOURCE_REPOSITORY_REQUIRED"
            and evidence.get("canonical_source_revision")
            != mapping_evidence["canonical_source_revision"]
        ):
            mapping_failures.append("SOURCE_MAP_DEPLOYMENT_REVISION_DIVERGED")
        if evidence.get("status") == "VERIFIED" and not mapping_failures:
            decision.state = "SOURCE_BOUND_VERIFIED"
        else:
            decision.state = "SOURCE_BOUND_AUDIT_ONLY"
            failures = evidence.get("failures") or []
            detail = ",".join(str(item) for item in failures)
            decision.blockers.append(
                f"{source_reason or 'external source authority'}; {detail or 'readback unavailable'}"
            )
            decision.blockers.extend(str(item) for item in mapping_failures)
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
        if not _valid_sha(decision.resulting_sha) or decision.resulting_sha == asset.sha:
            decision.blockers.append("merged Hugging Face pull request has no distinct immutable readback")
            decision.state = "MERGED_READBACK_FAILED"
            return decision
        decision.merged = True
        decision.state = "MERGED" if not blockers else "MERGED_CARD_BLOCKED_APP"
    return decision


def _decision_is_terminal_verified(decision: Decision) -> bool:
    if decision.state not in TERMINAL_VERIFIED_STATES or decision.blockers:
        return False
    if decision.state == "CURRENT":
        return not decision.changes
    if decision.state == "MERGED":
        return (
            decision.merged
            and _valid_sha(decision.resulting_sha)
            and decision.resulting_sha != decision.source_sha
        )
    source_evidence = decision.evidence.get("source_bound_readback")
    return isinstance(source_evidence, dict) and source_evidence.get("status") == "VERIFIED"


def build_report(
    org: str,
    decisions: list[Decision],
    execute: bool,
    merge: bool,
    *,
    source_map: SourceMapDocument | None = None,
) -> dict[str, Any]:
    states: dict[str, int] = {}
    for item in decisions:
        states[item.state] = states.get(item.state, 0) + 1
    blocked = [d.repo_id for d in decisions if d.blockers]
    failed = [d.repo_id for d in decisions if d.state.startswith("FAILED")]
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
        "source_map": source_map.report_identity() if source_map else None,
        "execute": execute,
        "merge": merge,
        "asset_count": len(decisions),
        "state_counts": states,
        "blocked_assets": blocked,
        "failed_assets": failed,
        "nonterminal_assets": nonterminal,
        "complete": complete,
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
    parser.add_argument("--protected-source-sha")
    parser.add_argument("--source-map", type=Path, default=DEFAULT_SOURCE_MAP)
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
    if args.protected_source_sha and not _valid_sha(args.protected_source_sha):
        print("--protected-source-sha must be one full hexadecimal commit SHA", file=sys.stderr)
        return 4

    try:
        source_map = load_source_map(args.source_map, args.org)
    except ControlError as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        fatal = {
            "schema": "szl.hf-universal-frontend-estate/v1",
            "complete": False,
            "fatal": str(exc),
        }
        args.report.write_text(
            json.dumps(fatal, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(fatal, indent=2, sort_keys=True), file=sys.stderr)
        return 2

    api = HfApi(token=token)
    public_inventory_api = HfApi()
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    decisions: list[Decision] = []
    try:
        assets = enumerate_assets(public_inventory_api, args.org)
    except Exception as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"schema": "szl.hf-universal-frontend-estate/v1", "complete": False, "fatal": str(exc)}, indent=2) + "\n")
        raise

    for asset in assets:
        try:
            decisions.append(
                process_asset(
                    api,
                    asset,
                    token,
                    args.execute,
                    args.merge,
                    args.backup_dir,
                    source_mapping=source_map.entries.get(asset.repo_id.lower())
                    if asset.repo_type == "space"
                    else None,
                    protected_source_sha=args.protected_source_sha,
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
        source_map=source_map,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("asset_count", "state_counts", "blocked_assets", "failed_assets", "complete")}, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
