#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Restore failed Hugging Face Space files only from exact canonical mappings.

This is not a generic code generator. A file is restorable only when:

1. the Space is non-folded and in a terminal source/build/runtime failure;
2. the file is missing, empty, or a Python entrypoint fails to parse;
3. the source map contains an exact record for that Space slug;
4. exactly one `szl-holdings/*` GitHub repository and one mapped source path
   resolve to the affected target path or basename;
5. the downloaded canonical file passes structural validation;
6. the resulting commit contains only the explicitly authorized restored files.

A valid entrypoint is never overwritten simply because a dependency or external
runtime failed. Hardware, billing, visibility, secrets, variables, and unrelated
Space content are outside scope.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Any, Iterable
import urllib.error
import urllib.parse
import urllib.request

import hf_estate_recover as estate_base

TARGET_STAGES = {"NO_APP_FILE", "CONFIG_ERROR", "BUILD_ERROR", "RUNTIME_ERROR"}
RESTORABLE_NAMES = {"Dockerfile", "requirements.txt", "packages.txt", "app.py", "serve.py", "main.py", "index.html"}
SOURCE_SUFFIXES = {".py", ".html", ".css", ".js", ".mjs", ".json", ".toml", ".txt", ".yaml", ".yml", ".sh"}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}
    values: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$", line)
        if match:
            values[match.group(1).lower()] = match.group(2).strip().strip("'\"")
    return values


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("repo_id") or item.get("name") or "").strip()


def iter_dicts(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_dicts(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_dicts(value)


def strings(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def mentions_slug(record: dict[str, Any], slug: str) -> bool:
    slug = slug.lower()
    for value in strings(record):
        normalized = value.strip().lower().rstrip("/")
        if normalized == slug or normalized.endswith("/" + slug):
            return True
        if f"huggingface.co/spaces/szlholdings/{slug}" in normalized:
            return True
        if f"szlholdings-{slug}.hf.space" in normalized:
            return True
    return False


def canonical_repos(record: dict[str, Any]) -> set[str]:
    repos: set[str] = set()
    for value in strings(record):
        for match in re.findall(r"(?:https?://github\.com/)?(szl-holdings/[A-Za-z0-9._-]+)", value, flags=re.IGNORECASE):
            repo = match.rstrip("/.,;:)")
            if repo.lower() != "szl-holdings/.github":
                repos.add(repo)
    return repos


def looks_like_source_path(value: str) -> bool:
    value = value.strip().strip("`'\"")
    if not value or value.startswith(("http://", "https://")):
        return False
    path = PurePosixPath(value)
    if path.name in RESTORABLE_NAMES:
        return True
    return path.suffix.lower() in SOURCE_SUFFIXES and " " not in value and not value.startswith("/")


def canonical_paths(record: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for value in strings(record):
        clean = value.strip().strip("`'\"")
        if looks_like_source_path(clean):
            paths.add(clean.replace("\\", "/").lstrip("./"))
    return paths


def mapped_candidates(source_map: Any, slug: str, target: str) -> list[tuple[str, str]]:
    target_path = PurePosixPath(target)
    pairs: set[tuple[str, str]] = set()
    for record in iter_dicts(source_map):
        if not mentions_slug(record, slug):
            continue
        repos = canonical_repos(record)
        paths = canonical_paths(record)
        for repo in repos:
            for path in paths:
                source_path = PurePosixPath(path)
                if str(source_path) == str(target_path) or source_path.name == target_path.name:
                    pairs.add((repo, path))
    return sorted(pairs)


def fetch_raw(repo: str, path: str) -> tuple[bytes | None, str]:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    errors: list[str] = []
    for ref in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{encoded}"
        request = urllib.request.Request(url, headers={"User-Agent": "szl-hf-canonical-source-repair/1.0", "Accept": "application/octet-stream"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(5 * 1024 * 1024)
                if int(response.status) == 200:
                    return data, ref
        except urllib.error.HTTPError as exc:
            errors.append(f"{ref}:HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            errors.append(f"{ref}:{type(exc).__name__}")
    return None, ",".join(errors)


def valid_source(target: str, data: bytes) -> tuple[bool, str]:
    if not data:
        return False, "canonical source is empty"
    if len(data) > 5 * 1024 * 1024:
        return False, "canonical source exceeds bounded size"
    suffix = PurePosixPath(target).suffix.lower()
    if suffix == ".py":
        try:
            ast.parse(data.decode("utf-8", "strict"), filename=target)
        except (UnicodeDecodeError, SyntaxError) as exc:
            return False, f"canonical Python source is invalid: {type(exc).__name__}"
    if PurePosixPath(target).name == "Dockerfile" and b"FROM " not in data.upper():
        return False, "canonical Dockerfile has no FROM instruction"
    if suffix == ".html" and b"<" not in data:
        return False, "canonical HTML source is structurally empty"
    return True, "canonical source validated"


def target_needs_restore(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return True, "missing"
    if path.stat().st_size == 0:
        return True, "empty"
    if path.suffix.lower() == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="strict"), filename=str(path))
        except (UnicodeDecodeError, SyntaxError) as exc:
            return True, f"invalid_python:{type(exc).__name__}"
    return False, "valid"


def docker_copy_sources(dockerfile: Path) -> set[str]:
    if not dockerfile.is_file():
        return set()
    sources: set[str] = set()
    for raw in dockerfile.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or not re.match(r"^(COPY|ADD)\s+", line, re.IGNORECASE):
            continue
        body = re.sub(r"^(COPY|ADD)\s+", "", line, flags=re.IGNORECASE).strip()
        if body.startswith("["):
            try:
                values = json.loads(body)
                for value in values[:-1]:
                    if isinstance(value, str):
                        sources.add(value.lstrip("./"))
            except json.JSONDecodeError:
                continue
        else:
            tokens = [token for token in body.split() if not token.startswith("--")]
            for value in tokens[:-1]:
                if not any(char in value for char in ("*", "?", "[")):
                    sources.add(value.lstrip("./"))
    return sources


def auth_env(token: str, temp_root: Path) -> dict[str, str]:
    askpass = temp_root / "askpass.sh"
    askpass.write_text(
        "#!/usr/bin/env sh\n"
        "case \"$1\" in\n"
        "  *Username*) printf '%s\\n' hf ;;\n"
        "  *Password*) printf '%s\\n' \"$HF_GIT_TOKEN\" ;;\n"
        "  *) printf '%s\\n' \"\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    askpass.chmod(askpass.stat().st_mode | stat.S_IXUSR)
    env = os.environ.copy()
    env.update({"GIT_ASKPASS": str(askpass), "GIT_TERMINAL_PROMPT": "0", "HF_GIT_TOKEN": token})
    return env


def clone_space(repo_id: str, destination: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in repo_id.split("/"))
    return run(["git", "-c", "credential.helper=", "clone", "--depth", "1", f"https://huggingface.co/spaces/{encoded}", str(destination)], env=env, timeout=300)


def render(report: dict[str, Any]) -> str:
    lines = [
        "# SZLHOLDINGS Canonical Source Repair Receipt",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Spaces inventoried: **{report.get('spaces_inventoried', 0)}**",
        f"- Failed Spaces inspected: **{report.get('targets_inspected', 0)}**",
        f"- Exact canonical files restored: **{sum(len(row.get('restored', [])) for row in report.get('actions', []))}**",
        f"- Residual failures: **{len(report.get('residual', []))}**",
        "",
        "## Restorations",
        "",
    ]
    if report.get("actions"):
        for row in report["actions"]:
            restored = ", ".join(f"`{item['target']}` ← `{item['repo']}:{item['path']}@{item['ref']}`" for item in row.get("restored", [])) or "none"
            lines.append(f"- `{row.get('space')}` — {restored}; push={row.get('pushed')}; after=`{row.get('stage_after', 'not observed')}`")
    else:
        lines.append("- No exact canonical restoration was applicable.")
    lines += ["", "## Residuals", ""]
    if report.get("residual"):
        for row in report["residual"]:
            lines.append(f"- `{row.get('space')}` — `{row.get('stage')}`: {row.get('reason')}")
    else:
        lines.append("- None in this exact-restoration scope.")
    lines += [
        "",
        "## Scope boundary",
        "",
        "- Existing valid application files were not overwritten.",
        "- Every restoration was bound to one exact Space record, GitHub repository, and source path.",
        "- Ambiguous mappings, dependency-only failures, and external-service failures remain residuals.",
        "- No hardware, billing, visibility, secret, variable, or unrelated file was changed.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default="SZLHOLDINGS")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pre-observe-seconds", type=int, default=480)
    parser.add_argument("--post-settle-seconds", type=int, default=300)
    parser.add_argument("--json-out", default="hf-canonical-source-repair.json")
    parser.add_argument("--markdown-out", default="hf-canonical-source-repair.md")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        fixture = {"space": "SZLHOLDINGS/demo", "source_repo": "szl-holdings/demo", "paths": ["app.py"]}
        assert mapped_candidates(fixture, "demo", "app.py") == [("szl-holdings/demo", "app.py")]
        assert valid_source("app.py", b"print('ok')\n")[0]
        assert not valid_source("app.py", b"def broken(:\n")[0]
        print("hf_canonical_source_repair self-test: PASS")
        return 0

    token, source = estate_base.token_from_environment()
    report: dict[str, Any] = {
        "schema": "SZL.HF.CanonicalSourceRepair.v1",
        "generated_at": utcnow(),
        "credential": {"present": bool(token), "source": source},
        "spaces_inventoried": 0,
        "targets_inspected": 0,
        "actions": [],
        "residual": [],
        "errors": [],
    }
    json_out = Path(args.json_out)
    markdown_out = Path(args.markdown_out)

    def persist() -> None:
        json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        markdown_out.write_text(render(report), encoding="utf-8")

    if not token:
        report["errors"].append("No managed Hugging Face credential is available.")
        persist()
        return 2

    root = Path(args.repo_root).resolve()
    map_path = root / "docs" / "huggingface-space-source-map-v1.json"
    if not map_path.is_file():
        report["errors"].append("Canonical Hugging Face source map is absent.")
        persist()
        return 2
    try:
        source_map = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report["errors"].append(f"Source map cannot be parsed: {type(exc).__name__}")
        persist()
        return 2

    folds, _ = estate_base.discover_intentional_folds(root)
    estate = estate_base.HfEstate(token, args.org)
    if args.pre_observe_seconds > 0:
        time.sleep(args.pre_observe_seconds)
    try:
        inventory = estate.list_spaces()
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        persist()
        return 2
    report["spaces_inventoried"] = len(inventory)

    for item in sorted(inventory, key=item_id):
        rid = item_id(item)
        if not rid:
            continue
        slug = rid.rsplit("/", 1)[-1].lower()
        if slug in folds or bool(item.get("disabled")):
            continue
        runtime = item.get("runtime") if isinstance(item.get("runtime"), dict) else estate.runtime(rid)
        before = estate_base.stage_name(runtime)
        if before not in TARGET_STAGES:
            continue
        report["targets_inspected"] += 1

        with tempfile.TemporaryDirectory(prefix="hf-canonical-") as directory:
            temp_root = Path(directory)
            checkout = temp_root / "space"
            env = auth_env(token, temp_root)
            cloned = clone_space(rid, checkout, env)
            if cloned.returncode != 0:
                report["residual"].append({"space": rid, "stage": before, "reason": "Space clone failed; exact source restoration was not attempted."})
                continue
            readme = checkout / "README.md"
            metadata = parse_frontmatter(readme.read_text(encoding="utf-8", errors="replace")) if readme.is_file() else {}
            sdk_data = item.get("sdkData") if isinstance(item.get("sdkData"), dict) else {}
            sdk = str(item.get("sdk") or sdk_data.get("sdk") or metadata.get("sdk") or "").lower()
            configured = str(metadata.get("app_file") or sdk_data.get("app_file") or "").strip()

            targets: set[str] = set()
            if sdk == "docker":
                targets.add("Dockerfile")
                dockerfile = checkout / "Dockerfile"
                for source_path in docker_copy_sources(dockerfile):
                    if not (checkout / source_path).exists():
                        targets.add(source_path)
            elif configured:
                targets.add(configured)
            elif sdk in {"gradio", "streamlit"}:
                targets.add("app.py")
            elif sdk == "static":
                targets.add("index.html")

            restored: list[dict[str, Any]] = []
            diagnostics: list[str] = []
            for target in sorted(targets):
                needs, why = target_needs_restore(checkout / target)
                if not needs:
                    diagnostics.append(f"{target}:valid")
                    continue
                candidates = mapped_candidates(source_map, slug, target)
                if len(candidates) != 1:
                    diagnostics.append(f"{target}:{why}:mapping_count={len(candidates)}")
                    continue
                repo, source_path = candidates[0]
                data, ref = fetch_raw(repo, source_path)
                if data is None:
                    diagnostics.append(f"{target}:{why}:canonical_fetch_failed={ref}")
                    continue
                valid, validation = valid_source(target, data)
                if not valid:
                    diagnostics.append(f"{target}:{why}:{validation}")
                    continue
                destination = checkout / target
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                restored.append({"target": target, "repo": repo, "path": source_path, "ref": ref, "reason": why})

            if not restored:
                report["residual"].append({"space": rid, "stage": before, "reason": "No missing/invalid file had exactly one validated canonical mapping. " + "; ".join(diagnostics)[:1200]})
                continue

            allowed = sorted(item["target"] for item in restored)
            diff = run(["git", "diff", "--name-only"], cwd=checkout, env=env, timeout=60)
            changed = sorted(line.strip() for line in diff.stdout.splitlines() if line.strip())
            if changed != allowed:
                report["residual"].append({"space": rid, "stage": before, "reason": f"Restoration violated the exact-file boundary: expected {allowed}, observed {changed}."})
                continue
            check = run(["git", "diff", "--check"], cwd=checkout, env=env, timeout=60)
            if check.returncode != 0:
                report["residual"].append({"space": rid, "stage": before, "reason": "Canonical restoration failed git diff --check."})
                continue
            run(["git", "config", "user.name", "SZL Holdings Automation"], cwd=checkout, env=env)
            run(["git", "config", "user.email", "eng@szlholdings.com"], cwd=checkout, env=env)
            run(["git", "add", "--", *allowed], cwd=checkout, env=env)
            commit = run(["git", "commit", "-s", "-m", "fix(space): restore exact mapped canonical sources"], cwd=checkout, env=env)
            pushed = run(["git", "push", "origin", "HEAD:main"], cwd=checkout, env=env, timeout=300)
            action = {"space": rid, "stage_before": before, "sdk": sdk, "restored": restored, "committed": commit.returncode == 0, "pushed": pushed.returncode == 0, "diagnostics": diagnostics}
            report["actions"].append(action)
            if pushed.returncode != 0:
                report["residual"].append({"space": rid, "stage": before, "reason": "Validated exact-source commit was rejected by the Space repository."})
                continue
            encoded = urllib.parse.quote(rid, safe="/")
            status, payload = estate.http.request("POST", f"{estate_base.HF_ENDPOINT}/api/spaces/{encoded}/restart", payload={"factory": True}, timeout=60)
            action["restart_http_status"] = status
            action["restart_accepted"] = 200 <= status < 300

    if report["actions"] and args.post_settle_seconds > 0:
        time.sleep(args.post_settle_seconds)
    for action in report["actions"]:
        if not action.get("pushed"):
            continue
        after = estate_base.stage_name(estate.runtime(str(action["space"])))
        action["stage_after"] = after
        if after != "RUNNING":
            report["residual"].append({"space": action["space"], "stage": after, "reason": "Exact canonical source was restored, but the Space has not reached RUNNING."})

    report["completed_at"] = utcnow()
    report["terminal_green_within_scope"] = not report["residual"] and not report["errors"]
    persist()
    return 0 if report["terminal_green_within_scope"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
