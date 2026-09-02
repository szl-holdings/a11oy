#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Repair only deterministic Hugging Face Space entrypoint metadata failures.

A repair is permitted only when all conditions hold:

* the Space is non-folded and reports a source/config/build/runtime failure;
* its configured ``app_file`` is absent or empty;
* exactly one SDK-compatible, already-committed root entrypoint exists;
* the only content change is the README YAML ``app_file`` field;
* the updated repository passes structural validation before push.

The script never fabricates an app, copies unrelated source, changes hardware,
visibility, secrets, variables, or billing, or rewrites a valid entrypoint.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Any
import urllib.parse

import hf_estate_recover as estate_base

TARGET_STAGES = {"NO_APP_FILE", "CONFIG_ERROR", "BUILD_ERROR", "RUNTIME_ERROR"}
CANDIDATES = {
    "gradio": ("app.py", "serve.py", "main.py"),
    "streamlit": ("app.py", "streamlit_app.py", "main.py"),
    "static": ("index.html",),
}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def parse_frontmatter(text: str) -> tuple[list[str], list[str], bool]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], lines, False
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return [], lines, False
    return lines[1:end], lines[end + 1 :], True


def scalar(lines: list[str], key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*?)\s*$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip().strip("'\"")
        return value or None
    return None


def set_scalar(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*:\s*.*$", re.IGNORECASE)
    updated: list[str] = []
    replaced = False
    for line in lines:
        match = pattern.match(line)
        if match and not replaced:
            updated.append(f"{match.group(1)}{key}: {value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"{key}: {value}")
    return updated


def render_frontmatter(meta: list[str], body: list[str]) -> str:
    return "\n".join(["---", *meta, "---", *body]).rstrip() + "\n"


def choose_candidate(root: Path, sdk: str) -> tuple[str | None, list[str]]:
    names = CANDIDATES.get(sdk, ())
    existing = [name for name in names if (root / name).is_file()]
    return (existing[0] if len(existing) == 1 else None), existing


def safe_git_environment(token: str, temp_root: Path) -> dict[str, str]:
    askpass = temp_root / "git-askpass.sh"
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
    env.update(
        {
            "GIT_ASKPASS": str(askpass),
            "GIT_TERMINAL_PROMPT": "0",
            "HF_GIT_TOKEN": token,
        }
    )
    return env


def clone_space(repo_id: str, target: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in repo_id.split("/"))
    return run(
        [
            "git",
            "-c",
            "credential.helper=",
            "clone",
            "--depth",
            "1",
            f"https://huggingface.co/spaces/{encoded}",
            str(target),
        ],
        env=env,
        timeout=300,
    )


def validate_candidate(root: Path, sdk: str, app_file: str) -> tuple[bool, str]:
    path = root / app_file
    if not path.is_file():
        return False, "candidate disappeared before validation"
    if sdk in {"gradio", "streamlit"} and path.suffix == ".py":
        result = run([os.sys.executable, "-m", "py_compile", app_file], cwd=root, timeout=60)
        if result.returncode != 0:
            return False, "existing Python entrypoint does not compile: " + (result.stderr or result.stdout)[-800:]
    if sdk == "static" and path.stat().st_size == 0:
        return False, "existing static entrypoint is empty"
    return True, "structural validation passed"


def repo_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("repo_id") or item.get("name") or "").strip()


def item_sdk(item: dict[str, Any], meta: list[str]) -> str:
    sdk_data = item.get("sdkData") if isinstance(item.get("sdkData"), dict) else {}
    value = item.get("sdk") or sdk_data.get("sdk") or scalar(meta, "sdk") or ""
    return str(value).strip().lower()


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SZLHOLDINGS Deterministic Entrypoint Repair",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Spaces inventoried: **{report.get('spaces_inventoried', 0)}**",
        f"- Target failures inspected: **{report.get('targets_inspected', 0)}**",
        f"- README entrypoints repaired: **{sum(1 for row in report.get('actions', []) if row.get('pushed'))}**",
        f"- Residual targets: **{len(report.get('residual', []))}**",
        "",
        "## Actions",
        "",
    ]
    if report.get("actions"):
        for row in report["actions"]:
            lines.append(
                f"- `{row.get('space')}` — `{row.get('stage_before')}` — {row.get('result')}"
            )
    else:
        lines.append("- No deterministic metadata repair was applicable.")
    lines += ["", "## Residual source failures", ""]
    if report.get("residual"):
        for row in report["residual"]:
            lines.append(
                f"- `{row.get('space')}` — `{row.get('stage')}`: {row.get('reason')}"
            )
    else:
        lines.append("- None in the deterministic entrypoint-repair scope.")
    lines += [
        "",
        "## Scope boundary",
        "",
        "- No application source was invented or replaced.",
        "- No Dockerfile was generated.",
        "- No hardware, visibility, billing, secret, or variable was changed.",
        "- Ambiguous or non-compiling candidate entrypoints remain explicit residuals.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default="SZLHOLDINGS")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json-out", default="hf-entrypoint-repair.json")
    parser.add_argument("--markdown-out", default="hf-entrypoint-repair.md")
    parser.add_argument("--settle-seconds", type=int, default=240)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        meta, body, ok = parse_frontmatter("---\nsdk: gradio\n---\n# Demo\n")
        assert ok and scalar(meta, "sdk") == "gradio"
        assert "app_file: app.py" in render_frontmatter(set_scalar(meta, "app_file", "app.py"), body)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            assert choose_candidate(root, "gradio") == ("app.py", ["app.py"])
        print("hf_entrypoint_repair self-test: PASS")
        return 0

    token, token_source = estate_base.token_from_environment()
    report: dict[str, Any] = {
        "schema": "SZL.HF.EntrypointRepair.v1",
        "generated_at": utcnow(),
        "credential": {"present": bool(token), "source": token_source},
        "spaces_inventoried": 0,
        "targets_inspected": 0,
        "intentional_folds": [],
        "actions": [],
        "residual": [],
        "errors": [],
    }
    json_out = Path(args.json_out)
    md_out = Path(args.markdown_out)

    def persist() -> None:
        json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_out.write_text(report_markdown(report), encoding="utf-8")

    if not token:
        report["errors"].append("No managed Hugging Face credential is available.")
        persist()
        return 2

    folds, _ = estate_base.discover_intentional_folds(Path(args.repo_root).resolve())
    report["intentional_folds"] = sorted(folds)
    estate = estate_base.HfEstate(token, args.org)
    try:
        inventory = estate.list_spaces()
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        persist()
        return 2
    report["spaces_inventoried"] = len(inventory)

    for item in sorted(inventory, key=repo_id):
        rid = repo_id(item)
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

        with tempfile.TemporaryDirectory(prefix="hf-entrypoint-") as directory:
            temp_root = Path(directory)
            checkout = temp_root / "space"
            env = safe_git_environment(token, temp_root)
            cloned = clone_space(rid, checkout, env)
            if cloned.returncode != 0:
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": "Space repository clone failed; no source was changed."}
                )
                continue

            readme = checkout / "README.md"
            if not readme.is_file():
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": "README.md is absent; SDK metadata cannot be repaired safely."}
                )
                continue
            original = readme.read_text(encoding="utf-8", errors="strict")
            meta, body, valid_frontmatter = parse_frontmatter(original)
            if not valid_frontmatter:
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": "README YAML front matter is absent or malformed; broad reconstruction is outside the deterministic scope."}
                )
                continue

            sdk = item_sdk(item, meta)
            configured = scalar(meta, "app_file")
            if sdk == "docker":
                if not (checkout / "Dockerfile").is_file():
                    report["residual"].append(
                        {"space": rid, "stage": before, "reason": "Docker Space has no Dockerfile; application source repair is required."}
                    )
                else:
                    report["residual"].append(
                        {"space": rid, "stage": before, "reason": "Dockerfile exists; the persistent build/runtime failure is not an app_file metadata defect."}
                    )
                continue
            if sdk not in CANDIDATES:
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": f"SDK {sdk or 'UNKNOWN'} is outside the deterministic entrypoint repair allowlist."}
                )
                continue
            if configured and (checkout / configured).is_file():
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": f"Configured app_file {configured!r} exists; failure requires application/dependency diagnosis."}
                )
                continue

            candidate, existing = choose_candidate(checkout, sdk)
            if candidate is None:
                reason = (
                    "No SDK-compatible root entrypoint exists."
                    if not existing
                    else "Multiple SDK-compatible root entrypoints exist; choosing one would be ambiguous."
                )
                report["residual"].append({"space": rid, "stage": before, "reason": reason})
                continue
            valid, validation = validate_candidate(checkout, sdk, candidate)
            if not valid:
                report["residual"].append({"space": rid, "stage": before, "reason": validation})
                continue

            readme.write_text(render_frontmatter(set_scalar(meta, "app_file", candidate), body), encoding="utf-8")
            diff_check = run(["git", "diff", "--check"], cwd=checkout, env=env, timeout=60)
            changed = run(["git", "diff", "--name-only"], cwd=checkout, env=env, timeout=60)
            changed_files = [line for line in changed.stdout.splitlines() if line.strip()]
            if diff_check.returncode != 0 or changed_files != ["README.md"]:
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": "Repair failed the one-file diff boundary; push was refused."}
                )
                continue

            run(["git", "config", "user.name", "SZL Holdings Automation"], cwd=checkout, env=env)
            run(["git", "config", "user.email", "eng@szlholdings.com"], cwd=checkout, env=env)
            add = run(["git", "add", "README.md"], cwd=checkout, env=env)
            commit = run(
                ["git", "commit", "-s", "-m", f"fix(space): bind existing {candidate} entrypoint"],
                cwd=checkout,
                env=env,
            )
            pushed = run(["git", "push", "origin", "HEAD:main"], cwd=checkout, env=env, timeout=300)
            row = {
                "space": rid,
                "stage_before": before,
                "sdk": sdk,
                "configured_before": configured,
                "candidate": candidate,
                "validated": validation,
                "committed": add.returncode == 0 and commit.returncode == 0,
                "pushed": pushed.returncode == 0,
                "result": "README app_file repaired and pushed" if pushed.returncode == 0 else "validated repair could not be pushed",
            }
            report["actions"].append(row)
            if pushed.returncode != 0:
                report["residual"].append(
                    {"space": rid, "stage": before, "reason": "Validated README-only repair was rejected by the Space repository."}
                )
                continue
            encoded = urllib.parse.quote(rid, safe="/")
            status, payload = estate.http.request(
                "POST",
                f"{estate_base.HF_ENDPOINT}/api/spaces/{encoded}/restart",
                payload={"factory": True},
                timeout=60,
            )
            row["restart_http_status"] = status
            row["restart_accepted"] = 200 <= status < 300

    if report["actions"] and args.settle_seconds > 0:
        time.sleep(args.settle_seconds)

    remaining: list[dict[str, Any]] = []
    seen = {(row["space"], row["reason"]) for row in report["residual"]}
    for row in report["actions"]:
        if not row.get("pushed"):
            continue
        runtime = estate.runtime(str(row["space"]))
        after = estate_base.stage_name(runtime)
        row["stage_after"] = after
        if after != "RUNNING":
            key = (str(row["space"]), "README entrypoint was repaired, but the Space has not reached RUNNING.")
            if key not in seen:
                remaining.append({"space": row["space"], "stage": after, "reason": key[1]})
    report["residual"].extend(remaining)
    report["completed_at"] = utcnow()
    report["terminal_green_within_scope"] = not report["residual"] and not report["errors"]
    persist()
    return 0 if report["terminal_green_within_scope"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
