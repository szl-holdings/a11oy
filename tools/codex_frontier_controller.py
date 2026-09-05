#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded evidence controller for the SZL Frontier Codex payload.

This controller performs no provider mutation, no push, no merge, no issue
mutation, and no credential readback. It records source state, executes local
verification commands, checks a narrow set of estate invariants, and can issue
anonymous GET/HEAD-style public probes when --live is explicitly supplied.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Sequence


EXPECTED_REPOSITORY = "szl-holdings/a11oy"
LOCKED_FORMULAS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
SENTRA_DIRECTIVE_ID = "owner-2026-09-04-sentra-assurance-command"
EXPECTED_VERTICAL_FLAGSHIPS = frozenset({"terra", "counsel", "finance", "lyte", "sentra"})
EXPECTED_FOLDED_CAPABILITIES = frozenset({"vessels"})

CANONICAL_PRODUCTS = {
    "a11oy": "https://szlholdings-a11oy.hf.space/",
    "killinchu": "https://szlholdings-killinchu.hf.space/",
    "sentra": "https://szlholdings-sentra.hf.space/",
    "lyte": "https://szlholdings-lyte.hf.space/",
    "finance": "https://szlholdings-finance.hf.space/",
    "terra": "https://szlholdings-terra.hf.space/",
    "counsel": "https://szlholdings-counsel.hf.space/",
}

PUBLIC_PROBES: dict[str, dict[str, Any]] = {
    "apex_root": {
        "url": "https://a-11-oy.com/",
        "content": "html",
    },
    "apex_honest": {
        "url": "https://a-11-oy.com/api/a11oy/v1/honest",
        "content": "json",
    },
    "apex_build_info": {
        "url": "https://a-11-oy.com/api/build-info",
        "content": "json",
        "require_source_identity": True,
    },
    "proof_registry": {
        "url": "https://a11oy.net/",
        "content": "html",
    },
    **{
        f"hf_{name}": {"url": url, "content": "html"}
        for name, url in CANONICAL_PRODUCTS.items()
    },
}

REQUIRED_TARGETED_TESTS = (
    "tests/test_codex_frontier_controller.py",
    "tests/test_hf_publish_vertical_flagships_v4.py",
    "tests/test_hf_sync_supersession_contract.py",
    "tests/test_frontend_source_boundaries.py",
    "tests/test_hf_frontend_live_canary_v1.py",
    "tests/test_finance_feed_readiness.py",
    "tests/test_feed_cache_singleflight.py",
    "tests/test_feed_route_event_loop_responsiveness.py",
    "tests/test_inference_engine_registry.py",
    "tests/test_inference_engine_benchmark.py",
    "tests/test_operation_schemas.py",
)
READINESS_MATRIX = "tools/readiness-harness/gen_tabs_matrix.py"

TEXT_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".jsx", ".md", ".mjs", ".py", ".sh",
    ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}

SECRET_PATTERNS = {
    "pem_private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "huggingface_token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "bearer_token": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
}

SAFE_CHILD_ENV_NAMES = {
    # Process discovery and platform runtime.  Everything else is denied by
    # default so a newly named credential cannot slip through this boundary.
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
    # Trust-store paths contain no credential value and are needed in some
    # hermetic enterprise environments.
    "CURL_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
}
SOURCE_IDENTITY_KEYS = {
    "commit",
    "git_commit",
    "git_sha",
    "github_sha",
    "revision",
    "source_commit",
    "source_revision",
    "source_sha",
    "szl_git_sha",
}

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA_IN_TEXT = re.compile(r"\b[0-9a-f]{40}\b")


@dataclasses.dataclass(frozen=True)
class Command:
    name: str
    argv: tuple[str, ...]
    required: bool = True
    timeout_s: int = 900
    local_mutations: tuple[str, ...] = ()
    network_access: str = "NONE"


@dataclasses.dataclass
class Result:
    name: str
    status: str
    required: bool
    detail: dict[str, Any]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sanitized_child_environment(
    environment: dict[str, str] | None = None,
) -> tuple[dict[str, str], tuple[str, ...], tuple[str, ...]]:
    source = dict(os.environ if environment is None else environment)
    safe: dict[str, str] = {}
    removed_names: list[str] = []
    removed_values: list[str] = []
    for name, value in source.items():
        upper = name.upper()
        if upper not in SAFE_CHILD_ENV_NAMES:
            removed_names.append(name)
            if len(value) >= 8:
                removed_values.append(value)
            continue
        safe[name] = value

    safe.update(
        {
            "GCM_INTERACTIVE": "Never",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "NO_COLOR": "1",
            "NPM_CONFIG_IGNORE_SCRIPTS": "true",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return safe, tuple(sorted(removed_names)), tuple(sorted(set(removed_values)))


def run(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_s: int = 120,
    check: bool = False,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    child_environment, _, _ = sanitized_child_environment(environment)
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=False,
        env=child_environment,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            + scrub(completed.stdout[-4000:])
        )
    return completed


def run_bytes(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_s: int = 120,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run a command without lossy text decoding (used for Git blob evidence)."""

    child_environment, _, _ = sanitized_child_environment(environment)
    return subprocess.run(
        list(argv),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s,
        check=False,
        env=child_environment,
    )


def git(root: Path, *args: str, timeout_s: int = 120) -> str:
    return run(("git", *args), cwd=root, timeout_s=timeout_s, check=True).stdout.strip()


def repository_root() -> Path:
    completed = run(("git", "rev-parse", "--show-toplevel"), cwd=Path.cwd())
    if completed.returncode != 0:
        raise SystemExit("BLOCKED_WRONG_REPO: not inside a Git repository")
    return Path(completed.stdout.strip()).resolve()


def normalize_remote(url: str) -> str:
    value = url.strip()
    scp_match = re.match(r"^(?:[^@]+@)?github\.com:(?P<path>.+)$", value, re.IGNORECASE)
    if scp_match:
        value = scp_match.group("path")
    elif "://" in value:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.hostname or "").lower() == "github.com":
            value = parsed.path
    return value.removesuffix(".git").strip("/").lower()


def sanitize_remote_url(url: str) -> str:
    value = scrub(url.strip())
    if "://" not in value:
        return value
    parsed = urllib.parse.urlsplit(value)
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def scrub(text: str, secret_values: Iterable[str] = ()) -> str:
    safe = text
    for value in sorted({item for item in secret_values if len(item) >= 8}, key=len, reverse=True):
        safe = safe.replace(value, "[REDACTED_SECRET]")
    for pattern in SECRET_PATTERNS.values():
        safe = pattern.sub("[REDACTED_TOKEN]", safe)
    safe = re.sub(
        r"(?i)(https?://)([^/@\s]+)@",
        r"\1[REDACTED_USERINFO]@",
        safe,
    )
    safe = re.sub(
        r"(?i)\b(token|secret|password|passwd|api[_-]?key|private[_-]?key)"
        r"(\s*[:=]\s*)([^\s,;]{8,})",
        r"\1\2[REDACTED_VALUE]",
        safe,
    )
    return safe


def command_result(command: Command, root: Path) -> Result:
    started = time.monotonic()
    child_environment, removed_names, removed_values = sanitized_child_environment()
    try:
        completed = run(
            command.argv,
            cwd=root,
            timeout_s=command.timeout_s,
            check=False,
            environment=child_environment,
        )
        status = "PASS" if completed.returncode == 0 else "FAIL"
        output = scrub(completed.stdout, removed_values)
        lines = output.splitlines()
        retained = "\n".join(lines[-240:])
        return Result(
            name=command.name,
            status=status,
            required=command.required,
            detail={
                "argv": list(command.argv),
                "returncode": completed.returncode,
                "duration_s": round(time.monotonic() - started, 3),
                "output_tail": retained,
                "output_truncated": len(lines) > 240,
                "sensitive_environment_names_removed": list(removed_names),
                "local_mutations": list(command.local_mutations),
                "network_access": command.network_access,
            },
        )
    except subprocess.TimeoutExpired as exc:
        output = scrub((exc.stdout or "") + "\n" + (exc.stderr or ""), removed_values)
        return Result(
            name=command.name,
            status="TIMEOUT",
            required=command.required,
            detail={
                "argv": list(command.argv),
                "timeout_s": command.timeout_s,
                "duration_s": round(time.monotonic() - started, 3),
                "output_tail": "\n".join(output.splitlines()[-120:]),
                "sensitive_environment_names_removed": list(removed_names),
                "local_mutations": list(command.local_mutations),
                "network_access": command.network_access,
            },
        )
    except Exception as exc:
        return Result(
            name=command.name,
            status="ERROR",
            required=command.required,
            detail={
                "argv": list(command.argv),
                "duration_s": round(time.monotonic() - started, 3),
                "error": scrub(f"{type(exc).__name__}: {exc}", removed_values),
                "sensitive_environment_names_removed": list(removed_names),
                "local_mutations": list(command.local_mutations),
                "network_access": command.network_access,
            },
        )


def changed_files(root: Path, base: str) -> tuple[list[Path], Result]:
    commands = {
        "committed": ("git", "diff", "--name-only", "-z", f"{base}...HEAD"),
        "staged": ("git", "diff", "--cached", "--name-only", "-z"),
        "unstaged": ("git", "diff", "--name-only", "-z"),
        "untracked": ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    }
    categories: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    all_names: set[str] = set()
    for category, argv in commands.items():
        completed = run(argv, cwd=root, timeout_s=120, check=False)
        if completed.returncode != 0:
            errors[category] = scrub("\n".join(completed.stdout.splitlines()[-40:]))
            categories[category] = []
            continue
        names = sorted({name for name in completed.stdout.split("\0") if name})
        categories[category] = names
        all_names.update(names)

    invalid_paths: list[str] = []
    valid_names: list[str] = []
    resolved_root = root.resolve()
    for name in sorted(all_names):
        candidate = Path(name)
        resolved = (root / candidate).resolve()
        if candidate.is_absolute() or not resolved.is_relative_to(resolved_root):
            invalid_paths.append(name)
        else:
            valid_names.append(name)
    if invalid_paths:
        errors["path_validation"] = "Git returned paths outside the repository root"
    files = [root / name for name in valid_names]

    snapshot_hasher = hashlib.sha256()
    snapshot_hasher.update(
        json.dumps(categories, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    for path in files:
        relative = str(path.relative_to(root)).replace("\\", "/")
        snapshot_hasher.update(relative.encode("utf-8"))
        if path.is_file() and not path.is_symlink():
            try:
                snapshot_hasher.update(path.read_bytes())
            except OSError as exc:
                errors[f"snapshot:{relative}"] = f"{type(exc).__name__}: {exc}"
    inventory = result(
        "changed_file_inventory",
        not errors,
        {
            "count": len(files),
            "files": valid_names,
            "categories": categories,
            "errors": errors,
            "invalid_paths": invalid_paths,
            "coverage": ["committed", "staged", "unstaged", "untracked"],
            "worktree_snapshot_sha256": snapshot_hasher.hexdigest(),
            "snapshot_scope": "category inventory plus present worktree bytes",
        },
    )
    return files, inventory


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def result(name: str, passed: bool, detail: dict[str, Any], required: bool = True) -> Result:
    return Result(
        name=name,
        status="PASS" if passed else "FAIL",
        required=required,
        detail=detail,
    )


def check_repository(root: Path) -> Result:
    completed = run(("git", "remote", "get-url", "origin"), cwd=root, check=False)
    if completed.returncode != 0:
        return result(
            "repository_identity",
            False,
            {
                "expected": EXPECTED_REPOSITORY,
                "observed": "UNAVAILABLE",
                "error": scrub("\n".join(completed.stdout.splitlines()[-40:])),
            },
        )
    origin = completed.stdout.strip()
    normalized = normalize_remote(origin)
    return result(
        "repository_identity",
        normalized == EXPECTED_REPOSITORY,
        {
            "expected": EXPECTED_REPOSITORY,
            "observed": normalized,
            "origin": sanitize_remote_url(origin),
        },
    )


def check_git_state(root: Path, base: str, phase: str) -> Result:
    observations: dict[str, str] = {}
    errors: dict[str, str] = {}
    commands = {
        "head": ("git", "rev-parse", "--verify", "HEAD^{commit}"),
        "branch": ("git", "branch", "--show-current"),
        "status": ("git", "status", "--short", "--untracked-files=all"),
        "base_sha": ("git", "rev-parse", "--verify", f"{base}^{{commit}}"),
        "merge_base": ("git", "merge-base", base, "HEAD"),
    }
    for key, argv in commands.items():
        completed = run(argv, cwd=root, timeout_s=120, check=False)
        if completed.returncode == 0:
            observations[key] = completed.stdout.strip()
        else:
            observations[key] = "UNAVAILABLE"
            errors[key] = scrub("\n".join(completed.stdout.splitlines()[-40:]))

    ancestor = run(
        ("git", "merge-base", "--is-ancestor", base, "HEAD"),
        cwd=root,
        timeout_s=120,
        check=False,
    )
    base_is_ancestor = ancestor.returncode == 0
    if ancestor.returncode not in {0, 1}:
        errors["base_is_ancestor"] = scrub(
            "\n".join(ancestor.stdout.splitlines()[-40:])
        )

    head = observations["head"]
    branch = observations["branch"]
    status = observations["status"]
    base_sha = observations["base_sha"]
    merge_base = observations["merge_base"]
    dirty = status not in {"", "UNAVAILABLE"}
    valid_identity = (
        not errors
        and bool(SHA40.fullmatch(head))
        and bool(SHA40.fullmatch(base_sha))
        and bool(SHA40.fullmatch(merge_base))
        and merge_base == base_sha
        and base_is_ancestor
    )
    safe_branch = branch not in {"", "UNAVAILABLE"}
    dirty_on_protected_branch = dirty and branch in {"main", "master", ""}
    terminal_clean = phase != "terminal" or not dirty
    passed = (
        valid_identity
        and not dirty_on_protected_branch
        and terminal_clean
        and (safe_branch or (phase == "terminal" and not dirty))
    )

    return result(
        "git_state",
        passed,
        {
            "head": head,
            "branch": branch if safe_branch else "DETACHED",
            "base": base,
            "base_sha": base_sha,
            "merge_base": merge_base,
            "base_is_ancestor": base_is_ancestor,
            "dirty": dirty,
            "status": [] if status == "UNAVAILABLE" else status.splitlines(),
            "source_identity": "HEAD_PLUS_WORKTREE" if dirty else "HEAD_CLEAN",
            "errors": errors,
            "rules": {
                "base_must_resolve_to_ancestor": True,
                "dirty_changes_on_main_forbidden": True,
                "detached_dirty_worktree_forbidden": True,
                "terminal_requires_clean_worktree": phase == "terminal",
            },
        },
    )


def check_agent_law(root: Path) -> Result:
    agents = read_text(root / "AGENTS.md")
    observed = sorted(set(re.findall(r"\bF(?:1|4|7|11|12|18|19|22)\b", agents)))
    expected = sorted(LOCKED_FORMULAS)
    required_phrases = (
        "HONEST LABELS",
        "DENY-BY-DEFAULT",
        "RECEIPT-ON-WRITE",
        "NEVER COMMIT A KEY",
        "NEVER WEAKEN A CI GATE",
    )
    missing = [phrase for phrase in required_phrases if phrase not in agents]
    passed = observed == expected and not missing
    return result(
        "agent_law",
        passed,
        {
            "locked_formulas_expected": expected,
            "locked_formulas_observed": observed,
            "missing_doctrine_phrases": missing,
        },
    )


def python_literal_assignments(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        tree = ast.parse(path.read_bytes(), filename=str(path))
    except (OSError, SyntaxError, ValueError) as exc:
        return {}, [f"{type(exc).__name__}: {exc}"]

    assignments: dict[str, Any] = {}
    errors: list[str] = []
    for node in tree.body:
        name: str | None = None
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name = target.id
                value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            value_node = node.value
        if name not in {
            "PUBLIC_FLAGSHIP_SLUGS",
            "FOLDED_INTO_KILLINCHU",
            "KILLINCHU_SPACE",
            "SENTRA_SPACE",
        } or value_node is None:
            continue
        try:
            assignments[name] = ast.literal_eval(value_node)
        except (ValueError, TypeError, SyntaxError) as exc:
            errors.append(f"{name}: non-literal assignment ({type(exc).__name__})")
    return assignments, errors


def asset_slug(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    parsed = urllib.parse.urlsplit(raw)
    path = parsed.path if parsed.scheme.lower() in {"http", "https"} else raw
    return path.rstrip("/").rsplit("/", 1)[-1].split(":", 1)[0].lower()


def parse_directive_scalar(value: str) -> Any:
    """Parse the deliberately small scalar subset used by owner directives."""

    value = value.strip()
    if not value:
        return None
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [parse_directive_scalar(item) for item in body.split(",")]
    if value[:1] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"invalid quoted scalar: {value!r}") from exc
        if not isinstance(parsed, str):
            raise ValueError(f"quoted directive scalar must be text: {value!r}")
        return parsed
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.startswith(("{", "|", ">", "&", "*", "!")):
        raise ValueError(f"unsupported directive scalar: {value!r}")
    return value


def parse_owner_directive(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Parse the directive's fixed mapping/list shape without a YAML runtime.

    This is intentionally a strict shape parser, not a general YAML parser.
    Exact indentation and keys are used so comments or similarly named fields
    cannot satisfy an estate invariant.
    """

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return {}, [f"{type(exc).__name__}: {exc}"]

    document: dict[str, Any] = {"directive": {}, "states": []}
    errors: list[str] = []
    current_state: dict[str, Any] | None = None
    in_directive = False
    in_states = False
    root_seen = False
    states_seen = False
    ignored_nested_indent: int | None = None

    for line_number, raw_line in enumerate(raw_lines, start=1):
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            errors.append(f"line {line_number}: tabs are not valid indentation")
            continue
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if indent == 0:
            ignored_nested_indent = None
            if stripped != "directive:":
                errors.append(f"line {line_number}: unexpected root field")
                continue
            if root_seen:
                errors.append(f"line {line_number}: duplicate directive root mapping")
                continue
            root_seen = True
            in_directive = True
            in_states = False
            continue
        if not in_directive:
            errors.append(f"line {line_number}: content outside directive mapping")
            continue

        if indent == 2:
            ignored_nested_indent = None
            current_state = None
            if stripped == "states:":
                if states_seen:
                    errors.append(f"line {line_number}: duplicate states field")
                    continue
                states_seen = True
                in_states = True
                continue
            in_states = False
            if ":" not in stripped:
                errors.append(f"line {line_number}: malformed directive field")
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            if key in document["directive"]:
                errors.append(f"line {line_number}: duplicate directive field {key!r}")
                continue
            try:
                document["directive"][key] = parse_directive_scalar(value)
            except ValueError as exc:
                errors.append(f"line {line_number}: {exc}")
            continue

        if in_states and indent == 4 and stripped.startswith("- "):
            ignored_nested_indent = None
            item = stripped[2:]
            if ":" not in item:
                errors.append(f"line {line_number}: malformed state item")
                continue
            key, value = item.split(":", 1)
            current_state = {}
            document["states"].append(current_state)
            try:
                current_state[key.strip()] = parse_directive_scalar(value)
            except ValueError as exc:
                errors.append(f"line {line_number}: {exc}")
            continue

        if in_states and current_state is not None and indent == 6:
            if ":" not in stripped:
                errors.append(f"line {line_number}: malformed state field")
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            if key in current_state:
                errors.append(f"line {line_number}: duplicate state field {key!r}")
                continue
            try:
                parsed = parse_directive_scalar(value)
            except ValueError as exc:
                errors.append(f"line {line_number}: {exc}")
                continue
            current_state[key] = parsed
            ignored_nested_indent = indent if parsed is None else None
            continue

        if ignored_nested_indent is not None and indent > ignored_nested_indent:
            # Nested explanatory metadata such as ``supersedes`` does not
            # participate in the authority decision.
            continue
        errors.append(f"line {line_number}: unsupported directive structure")

    if not in_directive:
        errors.append("missing directive root mapping")
    return document, errors


def indexed_records(value: Any, key: str = "id") -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    records: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        slug = asset_slug(item.get(key))
        if slug:
            records[slug] = item
    return records


def retirement_identity_slugs(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    identity_fields = ("id", "hf_repository", "repo_id", "asset", "name", "slug")
    slugs: set[str] = set()
    for item in value:
        if isinstance(item, str):
            slug = asset_slug(item)
            if slug:
                slugs.add(slug)
            continue
        if not isinstance(item, dict):
            continue
        for field in identity_fields:
            slug = asset_slug(item.get(field))
            if slug:
                slugs.add(slug)
    return slugs


def check_effective_estate(root: Path) -> Result:
    directive_path = root / "governance/owner-directives/2026-09-04-sentra.yaml"
    publisher_path = root / "scripts/hf_publish_vertical_flagships_v4.py"
    directive, directive_errors = parse_owner_directive(directive_path)
    assignments, publisher_errors = python_literal_assignments(publisher_path)

    manifest_path = root / "governance/public-estate.v1.json"
    manifest_errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise TypeError("manifest root must be an object")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        manifest = {}
        manifest_errors.append(f"{type(exc).__name__}: {exc}")

    public_products = manifest.get("public_products")
    platforms = manifest.get("platforms")
    product_records = indexed_records(public_products)
    platform_records = indexed_records(platforms)
    product_ids = [
        asset_slug(item.get("id"))
        for item in public_products
        if isinstance(public_products, list) and isinstance(item, dict)
    ] if isinstance(public_products, list) else []
    platform_ids = [
        asset_slug(item.get("id"))
        for item in platforms
        if isinstance(platforms, list) and isinstance(item, dict)
    ] if isinstance(platforms, list) else []
    observed_public_products = {
        item for item in product_ids + platform_ids if isinstance(item, str)
    }
    expected_platforms = {"a11oy"}
    expected_vertical_products = set(CANONICAL_PRODUCTS) - expected_platforms
    expected_public_products = set(CANONICAL_PRODUCTS)
    public_flags_valid = all(
        item.get("public") is True
        for item in [*product_records.values(), *platform_records.values()]
    )
    identity_records = {**platform_records, **product_records}
    identity_contracts: dict[str, bool] = {}
    for slug, expected_url in CANONICAL_PRODUCTS.items():
        item = identity_records.get(slug, {})
        identity_contracts[slug] = (
            asset_slug(item.get("hf_repository")) == slug
            and str(item.get("base_url", "")).rstrip("/")
            == expected_url.rstrip("/")
        )
    exact_product_set = (
        set(platform_ids) == expected_platforms
        and set(product_ids) == expected_vertical_products
        and all(isinstance(item, str) for item in product_ids + platform_ids)
        and observed_public_products == expected_public_products
        and len(platform_ids) == len(expected_platforms)
        and len(product_ids) == len(expected_vertical_products)
        and len(product_ids) == len(set(product_ids))
        and len(platform_ids) == len(set(platform_ids))
        and public_flags_valid
        and all(identity_contracts.values())
        and manifest.get("public_vertical_product_count") == 6
        and manifest.get("platform_count") == 1
    )

    sentra = product_records.get("sentra", {})
    sentra_public = sentra.get("public") is True
    sentra_role_valid = sentra.get("class") == "assurance-command"
    killinchu_role_valid = (
        product_records.get("killinchu", {}).get("class")
        == "cyber-physical-resilience-and-maritime-command"
    )

    capability_planes = manifest.get("capability_planes")
    capability_records = indexed_records(capability_planes)
    capability_ids = (
        [asset_slug(item.get("id")) for item in capability_planes if isinstance(item, dict)]
        if isinstance(capability_planes, list)
        else []
    )
    exact_capability_set = (
        set(capability_ids) == {"aegis", "immune", "vessels"}
        and len(capability_ids) == 3
    )
    vessels = capability_records.get("vessels", {})
    vessels_folded = (
        str(vessels.get("status", "")).lower() == "folded"
        and asset_slug(vessels.get("runtime")) == "killinchu"
        and vessels.get("independent_public_space_allowed") is False
        and "vessels" not in observed_public_products
    )

    decommissioned = indexed_records(
        manifest.get("decommissioned_surfaces"), key="hf_repository"
    )
    aegis = decommissioned.get("aegis-assurance", {})
    aegis_successor_sentra = (
        str(aegis.get("state", "")).upper() == "DECOMMISSIONED"
        and asset_slug(aegis.get("mission_routes_to")) == "sentra"
        and aegis.get("history_preserved") is True
        and "aegis" not in observed_public_products
        and "aegis-assurance" not in observed_public_products
    )
    aegis_capability = capability_records.get("aegis", {})
    aegis_capability_valid = (
        str(aegis_capability.get("status", "")).lower() == "decommissioned"
        and asset_slug(aegis_capability.get("runtime")) == "sentra"
        and aegis_capability.get("independent_public_space_allowed") is False
    )
    immune = capability_records.get("immune", {})
    immune_under_sentra = (
        str(immune.get("status", "")).lower() == "engine-library"
        and asset_slug(immune.get("runtime")) == "sentra"
        and immune.get("independent_public_space_allowed") is False
        and "immune" not in observed_public_products
    )

    retirement_candidates = manifest.get("retirement_candidates")
    retirement_slugs = retirement_identity_slugs(retirement_candidates)
    retirement_exact = isinstance(retirement_candidates, list) and not retirement_candidates

    publisher_public = assignments.get("PUBLIC_FLAGSHIP_SLUGS")
    publisher_folded = assignments.get("FOLDED_INTO_KILLINCHU")
    publisher_public_normalized = (
        [str(item).lower() for item in publisher_public]
        if isinstance(publisher_public, (tuple, list))
        else []
    )
    publisher_folded_normalized = (
        [str(item).lower() for item in publisher_folded]
        if isinstance(publisher_folded, (tuple, list))
        else []
    )
    publisher_valid = (
        isinstance(publisher_public, (tuple, list))
        and all(isinstance(item, str) for item in publisher_public)
        and set(publisher_public_normalized) == EXPECTED_VERTICAL_FLAGSHIPS
        and len(publisher_public_normalized) == len(EXPECTED_VERTICAL_FLAGSHIPS)
        and isinstance(publisher_folded, (tuple, list))
        and all(isinstance(item, str) for item in publisher_folded)
        and set(publisher_folded_normalized) == EXPECTED_FOLDED_CAPABILITIES
        and len(publisher_folded_normalized) == len(EXPECTED_FOLDED_CAPABILITIES)
        and assignments.get("KILLINCHU_SPACE") == "SZLHOLDINGS/killinchu"
        and assignments.get("SENTRA_SPACE") == "SZLHOLDINGS/sentra"
    )

    directive_mapping = directive.get("directive", {})
    directive_states_value = directive.get("states", [])
    directive_states: dict[str, dict[str, Any]] = {}
    directive_state_ids: list[str] = []
    if isinstance(directive_states_value, list):
        for item in directive_states_value:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            normalized = item["id"].strip().lower()
            directive_state_ids.append(normalized)
            directive_states[normalized] = item
    sentra_directive = directive_states.get("szlholdings/sentra", {})
    aegis_directive = directive_states.get("szlholdings/aegis-assurance", {})
    killinchu_directive = directive_states.get("szlholdings/killinchu", {})
    immune_directive = directive_states.get("szlholdings/immune", {})
    directive_valid = (
        isinstance(directive_mapping, dict)
        and directive_mapping.get("id") == SENTRA_DIRECTIVE_ID
        and directive_mapping.get("authority") == "owner"
        and set(directive_state_ids)
        == {
            "szlholdings/sentra",
            "szlholdings/aegis-assurance",
            "szlholdings/killinchu",
            "szlholdings/immune",
        }
        and len(directive_state_ids) == 4
        and sentra_directive.get("state") == "FLAGSHIP_KEPT"
        and sentra_directive.get("role") == "sole-assurance-command"
        and set(sentra_directive.get("planes", [])) == {"gate", "yawar", "evidence"}
        and sentra_directive.get("absorbs") == ["SZLHOLDINGS/aegis-assurance"]
        and aegis_directive.get("state") == "DECOMMISSIONED"
        and aegis_directive.get("mission_routes_to") == "SZLHOLDINGS/sentra"
        and killinchu_directive.get("state") == "FLAGSHIP_KEPT"
        and killinchu_directive.get("role")
        == "sole-cyber-physical-resilience-command"
        and immune_directive.get("state") == "ENGINE_LIBRARY_UNDER_SENTRA"
    )
    passed = all(
        (
            not directive_errors,
            directive_valid,
            not publisher_errors,
            not manifest_errors,
            publisher_valid,
            exact_product_set,
            sentra_public,
            sentra_role_valid,
            killinchu_role_valid,
            retirement_exact,
            exact_capability_set,
            vessels_folded,
            aegis_successor_sentra,
            aegis_capability_valid,
            immune_under_sentra,
        )
    )
    return result(
        "effective_estate",
        passed,
        {
            "directive_errors": directive_errors,
            "directive_valid": directive_valid,
            "directive_state_ids": directive_state_ids,
            "publisher_assignments": assignments,
            "publisher_errors": publisher_errors,
            "publisher_valid": publisher_valid,
            "manifest_errors": manifest_errors,
            "public_products_expected": sorted(expected_public_products),
            "public_products_observed": sorted(observed_public_products),
            "identity_contracts": identity_contracts,
            "exact_product_set": exact_product_set,
            "sentra_public": sentra_public,
            "sentra_role_valid": sentra_role_valid,
            "killinchu_role_valid": killinchu_role_valid,
            "retirement_exact": retirement_exact,
            "exact_capability_set": exact_capability_set,
            "vessels_folded": vessels_folded,
            "aegis_successor_sentra": aegis_successor_sentra,
            "aegis_capability_valid": aegis_capability_valid,
            "immune_under_sentra": immune_under_sentra,
            "retirement_identity_slugs": sorted(retirement_slugs),
        },
    )


def check_changed_secrets(
    root: Path, files: Iterable[Path], *, base: str = "origin/main"
) -> Result:
    hits: list[dict[str, str]] = []
    scanned: list[str] = []
    unscanned: list[dict[str, str]] = []

    def scan_text(label: str, text: str) -> None:
        scanned.append(label)
        for pattern_label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append({"file": label, "pattern": pattern_label})

    paths = sorted(set(files), key=lambda item: str(item))
    for path in paths:
        if not path.exists() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = str(path.relative_to(root))
        if path.is_symlink():
            unscanned.append({"file": relative, "reason": "symlink"})
            continue
        try:
            if path.stat().st_size > 2_000_000:
                unscanned.append({"file": relative, "reason": "larger_than_2mb"})
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unscanned.append(
                {"file": relative, "reason": f"{type(exc).__name__}: {exc}"}
            )
            continue
        scan_text(f"worktree:{relative}", text)

    snapshot_specs = {
        "index": ("git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"),
        "head": (
            "git",
            "diff",
            "--name-only",
            "-z",
            "--diff-filter=ACMR",
            f"{base}...HEAD",
        ),
    }
    for snapshot, argv in snapshot_specs.items():
        listing = run(argv, cwd=root, timeout_s=120, check=False)
        if listing.returncode != 0:
            unscanned.append(
                {
                    "file": f"{snapshot}:*",
                    "reason": scrub("\n".join(listing.stdout.splitlines()[-20:])),
                }
            )
            continue
        for name in sorted({item for item in listing.stdout.split("\0") if item}):
            if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            object_spec = f":{name}" if snapshot == "index" else f"HEAD:{name}"
            blob = run_bytes(("git", "show", object_spec), cwd=root, timeout_s=120)
            if blob.returncode != 0:
                unscanned.append(
                    {
                        "file": f"{snapshot}:{name}",
                        "reason": scrub(
                            blob.stdout.decode("utf-8", errors="replace")[-2000:]
                        ),
                    }
                )
                continue
            if len(blob.stdout) > 2_000_000:
                unscanned.append(
                    {"file": f"{snapshot}:{name}", "reason": "larger_than_2mb"}
                )
                continue
            scan_text(
                f"{snapshot}:{name}", blob.stdout.decode("utf-8", errors="replace")
            )
    return result(
        "changed_file_secret_scan",
        not hits and not unscanned,
        {
            "files_scanned": scanned,
            "hits": hits,
            "unscanned": unscanned,
            "values_recorded": False,
        },
    )


def check_python_compile(
    root: Path, files: Iterable[Path], *, base: str = "origin/main"
) -> Result:
    failures: list[dict[str, str]] = []
    compiled: list[str] = []

    def compile_source(label: str, source: bytes | str) -> None:
        try:
            compile(source, label, "exec", dont_inherit=True)
            compiled.append(label)
        except (SyntaxError, ValueError, TypeError) as exc:
            failures.append(
                {"file": label, "error": scrub(f"{type(exc).__name__}: {exc}")}
            )

    for path in sorted(set(files), key=lambda item: str(item)):
        if not path.exists() or path.suffix != ".py":
            continue
        relative = str(path.relative_to(root))
        try:
            source = path.read_bytes()
        except OSError as exc:
            failures.append(
                {"file": relative, "error": scrub(f"{type(exc).__name__}: {exc}")}
            )
            continue
        compile_source(f"worktree:{relative}", source)

    snapshot_specs = {
        "index": ("git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"),
        "head": (
            "git",
            "diff",
            "--name-only",
            "-z",
            "--diff-filter=ACMR",
            f"{base}...HEAD",
        ),
    }
    for snapshot, argv in snapshot_specs.items():
        listing = run(argv, cwd=root, timeout_s=120, check=False)
        if listing.returncode != 0:
            failures.append(
                {
                    "file": f"{snapshot}:*",
                    "error": scrub("\n".join(listing.stdout.splitlines()[-20:])),
                }
            )
            continue
        for name in sorted({item for item in listing.stdout.split("\0") if item}):
            if Path(name).suffix.lower() != ".py":
                continue
            object_spec = f":{name}" if snapshot == "index" else f"HEAD:{name}"
            blob = run_bytes(("git", "show", object_spec), cwd=root, timeout_s=120)
            if blob.returncode != 0:
                failures.append(
                    {
                        "file": f"{snapshot}:{name}",
                        "error": scrub(
                            blob.stdout.decode("utf-8", errors="replace")[-2000:]
                        ),
                    }
                )
                continue
            compile_source(f"{snapshot}:{name}", blob.stdout)
    return result(
        "changed_python_compile",
        not failures,
        {
            "compiled": compiled,
            "failures": failures,
            "bytecode_written": False,
        },
    )


def check_changed_whitespace(root: Path, files: Iterable[Path]) -> Result:
    hits: list[dict[str, Any]] = []
    scanned: list[str] = []
    for path in sorted(set(files), key=lambda item: str(item)):
        if (
            not path.exists()
            or path.is_symlink()
            or path.suffix.lower() not in TEXT_SUFFIXES
        ):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        relative = str(path.relative_to(root))
        scanned.append(relative)
        for line_number, line in enumerate(lines, start=1):
            if line.endswith((" ", "\t")):
                hits.append({"file": relative, "line": line_number})
    return result(
        "changed_file_whitespace",
        not hits,
        {
            "files_scanned": scanned,
            "trailing_whitespace": hits,
            "includes_untracked_files": True,
        },
    )


def docker_copy_sources(dockerfile: str) -> set[str]:
    """Return normalized source operands from shell- and JSON-form COPY lines."""
    logical_lines: list[str] = []
    pending = ""
    for raw_line in dockerfile.splitlines():
        stripped = raw_line.strip()
        if not stripped or (not pending and stripped.startswith("#")):
            continue
        pending = f"{pending} {stripped}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        logical_lines.append(pending)
        pending = ""
    if pending:
        logical_lines.append(pending)

    sources: set[str] = set()
    for line in logical_lines:
        match = re.match(r"(?i)^COPY\s+(.+)$", line)
        if match is None:
            continue
        payload = match.group(1).strip()
        operands: list[str]
        if payload.startswith("["):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            operands = [str(item) for item in parsed] if isinstance(parsed, list) else []
        else:
            try:
                tokens = shlex.split(payload, posix=True)
            except ValueError:
                continue
            while tokens and tokens[0].startswith("--"):
                tokens.pop(0)
            operands = tokens
        for source in operands[:-1]:
            normalized = source.replace("\\", "/").removeprefix("./")
            sources.add(normalized.rstrip("/"))
    return sources


def check_new_top_level_python_copy(root: Path, files: Iterable[Path]) -> Result:
    dockerfile = read_text(root / "Dockerfile")
    copied_sources = docker_copy_sources(dockerfile)
    missing: list[str] = []
    candidates: list[str] = []
    for path in files:
        if not path.exists() or path.suffix != ".py" or path.parent != root:
            continue
        relative = path.name
        if relative.startswith("test_"):
            continue
        candidates.append(relative)
        if relative not in copied_sources:
            missing.append(relative)
    return result(
        "top_level_python_docker_copy",
        not missing,
        {
            "new_or_changed_top_level_python": candidates,
            "missing_copy_entries": missing,
            "note": (
                "This is intentionally conservative: changed top-level runtime modules "
                "must be explicitly present in the Docker deployment set."
            ),
        },
    )


def existing_targeted_tests(root: Path) -> list[str]:
    # Required targets remain in the command even when absent; pytest must
    # then fail instead of silently narrowing the acceptance surface.
    discovered: set[str] = set(REQUIRED_TARGETED_TESTS)
    patterns = (
        "test_*owner*directive*.py",
        "test_*public*estate*.py",
        "test_*space*frontend*.py",
        "test_*source*identity*.py",
        "test_*single*writer*.py",
        "test_*receipt*read*.py",
        "test_*no*sign*.py",
        "test_*docker*copy*.py",
    )
    tests_dir = root / "tests"
    if tests_dir.exists():
        for pattern in patterns:
            for path in tests_dir.glob(pattern):
                discovered.add(str(path.relative_to(root)))
    return sorted(discovered)


def verification_prerequisites(
    root: Path, *, full: bool, docker: bool
) -> list[Result]:
    required_files = (READINESS_MATRIX, *REQUIRED_TARGETED_TESTS)
    missing_files = [path for path in required_files if not (root / path).is_file()]
    prerequisites = [
        result(
            "required_verification_files",
            not missing_files,
            {
                "required": list(required_files),
                "missing": missing_files,
            },
        ),
        result(
            "pytest_available",
            importlib.util.find_spec("pytest") is not None,
            {
                "module": "pytest",
                "interpreter": sys.executable,
            },
        ),
    ]

    if full:
        full_paths = (
            "pnpm-workspace.yaml",
            "package.json",
            "packages/qec-integrity/src/qec_lineage.test.ts",
            "web/packages/a11oy-core/package.json",
        )
        missing_full_paths = [path for path in full_paths if not (root / path).is_file()]
        if not (root / "__tests__").is_dir():
            missing_full_paths.append("__tests__/")
        pnpm = shutil.which("pnpm")
        prerequisites.extend(
            [
                result(
                    "required_full_verification_files",
                    not missing_full_paths,
                    {"required": list(full_paths) + ["__tests__/"], "missing": missing_full_paths},
                ),
                result(
                    "pnpm_available",
                    pnpm is not None,
                    {"tool": "pnpm", "path": pnpm or "UNAVAILABLE"},
                ),
            ]
        )

    if docker:
        docker_path = shutil.which("docker")
        prerequisites.append(
            result(
                "docker_available",
                docker_path is not None,
                {"tool": "docker", "path": docker_path or "UNAVAILABLE"},
            )
        )
    return prerequisites


def verification_commands(
    root: Path, *, base: str, full: bool, docker: bool
) -> list[Command]:
    commands: list[Command] = [
        Command(
            "git_committed_diff_check",
            ("git", "diff", "--check", f"{base}...HEAD"),
            timeout_s=120,
        ),
        Command(
            "git_staged_diff_check",
            ("git", "diff", "--cached", "--check"),
            timeout_s=120,
        ),
        Command(
            "git_worktree_diff_check",
            ("git", "diff", "--check"),
            timeout_s=120,
        ),
    ]

    commands.append(
        Command(
            "readiness_matrix_check",
            (
                sys.executable,
                READINESS_MATRIX,
                "--check",
            ),
            timeout_s=180,
        )
    )

    targets = existing_targeted_tests(root)
    commands.append(
        Command(
            "targeted_pytest",
            (sys.executable, "-m", "pytest", "-q", *targets),
            timeout_s=1200,
            local_mutations=("pytest_cache_or_test_artifacts",),
        )
    )

    if full:
        commands.append(
            Command(
                "full_pytest",
                (sys.executable, "-m", "pytest", "-q"),
                timeout_s=3600,
                local_mutations=("pytest_cache_or_test_artifacts",),
            )
        )

        commands.extend(
            [
                Command(
                    "pnpm_install",
                    ("pnpm", "install", "--frozen-lockfile", "--ignore-scripts"),
                    timeout_s=1800,
                    local_mutations=("node_modules_and_pnpm_store",),
                    network_access="DEPENDENCY_REGISTRY_READ",
                ),
                Command(
                    "doctrine_tests",
                    ("pnpm", "test:doctrine"),
                    timeout_s=1800,
                    local_mutations=("node_test_cache_or_artifacts",),
                ),
                Command(
                    "doctrine_typecheck",
                    ("pnpm", "typecheck:doctrine"),
                    timeout_s=1800,
                    local_mutations=("typescript_build_cache",),
                ),
                Command(
                    "doctrine_build",
                    ("pnpm", "build:doctrine"),
                    timeout_s=1800,
                    local_mutations=("doctrine_build_artifacts",),
                ),
                Command(
                    "jest_compliance",
                    ("pnpm", "exec", "jest", "__tests__/", "--runInBand"),
                    timeout_s=1800,
                    local_mutations=("node_test_cache_or_artifacts",),
                ),
                Command(
                    "qec_lineage",
                    (
                        "pnpm",
                        "exec",
                        "tsx",
                        "packages/qec-integrity/src/qec_lineage.test.ts",
                    ),
                    timeout_s=600,
                    local_mutations=("node_test_cache_or_artifacts",),
                ),
                Command(
                    "a11oy_core_standalone",
                    (
                        "pnpm",
                        "--dir",
                        "web/packages/a11oy-core",
                        "run",
                        "test:standalone",
                    ),
                    timeout_s=1800,
                    local_mutations=("node_test_cache_or_artifacts",),
                ),
            ]
        )

    if docker:
        commands.append(
            Command(
                "docker_build",
                (
                    "docker",
                    "build",
                    "--pull=false",
                    "-t",
                    "a11oy:codex-frontier",
                    ".",
                ),
                timeout_s=3600,
                local_mutations=("docker_image:a11oy:codex-frontier",),
                network_access="DOCKERFILE_DEFINED_READS",
            )
        )

    return commands


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def collect_source_identities(value: Any) -> set[str]:
    identities: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if normalized_key in SOURCE_IDENTITY_KEYS and isinstance(item, str):
                candidate = item.strip().lower()
                if SHA40.fullmatch(candidate):
                    identities.add(candidate)
            identities.update(collect_source_identities(item))
    elif isinstance(value, list):
        for item in value:
            identities.update(collect_source_identities(item))
    return identities


def content_type_matches(content_type: str, expected: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if expected == "json":
        return media_type == "application/json" or media_type.endswith("+json")
    if expected == "html":
        return media_type in {"text/html", "application/xhtml+xml"}
    return False


def anonymous_probe(
    name: str,
    url: str,
    *,
    expected_content: str,
    expected_source_sha: str | None = None,
    require_source_identity: bool = False,
    timeout_s: int = 20,
) -> Result:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SZL-Codex-Frontier-Witness/1.0",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.5",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body_with_sentinel = response.read(1_000_001)
            body = body_with_sentinel[:1_000_000]
            body_within_limit = len(body_with_sentinel) <= 1_000_000
            content_type = response.headers.get("Content-Type", "")
            final_url = response.geturl()
            requested_parts = urllib.parse.urlsplit(url)
            final_parts = urllib.parse.urlsplit(final_url)
            final_origin_valid = (
                final_parts.scheme == "https"
                and final_parts.hostname == requested_parts.hostname
                and final_parts.port == requested_parts.port
            )
            content_type_valid = content_type_matches(content_type, expected_content)
            parsed: Any = None
            parse_valid = True
            if expected_content == "json":
                try:
                    parsed = json.loads(body)
                    parse_valid = isinstance(parsed, (dict, list))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    parse_valid = False
            elif expected_content == "html":
                parse_valid = bool(body.strip())

            source_identities = collect_source_identities(parsed)
            source_identity_verified = (
                expected_source_sha is not None
                and expected_source_sha.lower() in source_identities
            )
            if require_source_identity:
                if not source_identities:
                    verification = "SOURCE_IDENTITY_MISSING"
                elif source_identity_verified:
                    verification = "VERIFIED_SOURCE_IDENTITY"
                else:
                    verification = "SOURCE_IDENTITY_MISMATCH"
            elif content_type_valid and parse_valid:
                verification = "CONTENT_VERIFIED_SOURCE_UNVERIFIED"
            else:
                verification = "CONTENT_CONTRACT_FAILED"

            passed = all(
                (
                    response.status == 200,
                    final_origin_valid,
                    content_type_valid,
                    parse_valid,
                    body_within_limit,
                    source_identity_verified if require_source_identity else True,
                )
            )
            detail: dict[str, Any] = {
                "url": url,
                "final_url": final_url,
                "status": response.status,
                "content_type": content_type,
                "expected_content": expected_content,
                "content_type_valid": content_type_valid,
                "content_parse_valid": parse_valid,
                "final_origin_valid": final_origin_valid,
                "body_within_limit": body_within_limit,
                "bytes_hashed": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "duration_s": round(time.monotonic() - started, 3),
                "body_recorded": False,
                "reachability": "REACHABLE",
                "verification": verification,
                "source_identity_required": require_source_identity,
                "source_identity_expected": expected_source_sha,
                "source_identities_observed": sorted(source_identities),
            }
            return result(f"live_{name}", passed, detail)
    except urllib.error.HTTPError as exc:
        body = exc.read(1_000_000)
        return result(
            f"live_{name}",
            False,
            {
                "url": url,
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type", ""),
                "bytes_hashed": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "duration_s": round(time.monotonic() - started, 3),
                "body_recorded": False,
                "reachability": "REACHABLE_HTTP_ERROR",
                "verification": "UNVERIFIED",
                "source_identity_required": require_source_identity,
            },
        )
    except Exception as exc:
        return result(
            f"live_{name}",
            False,
            {
                "url": url,
                "duration_s": round(time.monotonic() - started, 3),
                "error": scrub(f"{type(exc).__name__}: {exc}"),
                "body_recorded": False,
                "reachability": "UNAVAILABLE",
                "verification": "UNVERIFIED",
                "source_identity_required": require_source_identity,
            },
        )


def www_redirect_probe() -> Result:
    source = "https://www.a-11-oy.com/__szl_codex_probe__?source=frontier"
    expected = "https://a-11-oy.com/__szl_codex_probe__?source=frontier"
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(
        source,
        headers={"User-Agent": "SZL-Codex-Frontier-Witness/1.0"},
        method="GET",
    )
    try:
        opener.open(request, timeout=20)
        return result(
            "live_www_canonical_redirect",
            False,
            {
                "source": source,
                "expected_location": expected,
                "error": "request did not return a redirect response",
                "reachability": "REACHABLE",
                "verification": "REDIRECT_CONTRACT_FAILED",
            },
        )
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location")
        return result(
            "live_www_canonical_redirect",
            exc.code == 301 and location == expected,
            {
                "source": source,
                "status": exc.code,
                "location": location,
                "expected_location": expected,
                "path_and_query_preserved": location == expected,
                "reachability": "REACHABLE",
                "verification": (
                    "VERIFIED_REDIRECT"
                    if exc.code == 301 and location == expected
                    else "REDIRECT_CONTRACT_FAILED"
                ),
            },
        )
    except Exception as exc:
        return result(
            "live_www_canonical_redirect",
            False,
            {
                "source": source,
                "expected_location": expected,
                "error": scrub(f"{type(exc).__name__}: {exc}"),
                "reachability": "UNAVAILABLE",
                "verification": "UNVERIFIED",
            },
        )


def write_report(
    root: Path,
    *,
    phase: str,
    base: str,
    results: list[Result],
    output_root: Path | None,
) -> Path:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = (
        output_root
        if output_root is not None
        else root / "reports" / "codex-frontier" / timestamp
    )
    destination.mkdir(parents=True, exist_ok=True)

    required_failures = [
        item.name
        for item in results
        if item.required and item.status != "PASS"
    ]
    command_results = [item for item in results if "argv" in item.detail]
    fetch_results = [item for item in command_results if item.name == "fetch_origin_main"]
    if fetch_results and fetch_results[0].status == "PASS":
        git_ref_mutation_evidence = "FETCH_SUCCEEDED_REF_CHANGE_NOT_COMPARED"
    elif fetch_results:
        git_ref_mutation_evidence = "ATTEMPTED_OUTCOME_UNCERTAIN"
    else:
        git_ref_mutation_evidence = "NOT_ATTEMPTED"
    declared_local_mutations = sorted(
        {
            mutation
            for item in command_results
            for mutation in item.detail.get("local_mutations", [])
        }
    )
    declared_network_access = sorted(
        {
            access
            for item in command_results
            for access in [item.detail.get("network_access", "NONE")]
            if access != "NONE"
        }
    )
    declared_provider_write = any(
        "PROVIDER" in access and "WRITE" in access
        for access in declared_network_access
    )
    live_witness_executed = any(item.name.startswith("live_") for item in results)
    if required_failures:
        terminal_status = "FAILED_CLOSED"
    elif phase == "terminal":
        terminal_status = "TERMINAL_WITNESS_PASS"
    elif phase == "verify":
        terminal_status = "VERIFICATION_PASS"
    else:
        terminal_status = "PREFLIGHT_PASS"
    report = {
        "schema": "szl.codex-frontier-controller/v2",
        "phase": phase,
        "generated_at": utc_now(),
        "repository": EXPECTED_REPOSITORY,
        "base": base,
        "complete": not required_failures,
        "terminal": phase == "terminal",
        "terminal_status": terminal_status,
        "acceptance_scope": (
            "LOCAL_SOURCE_BUILD_AND_PUBLIC_HTTP_WITNESS"
            if phase == "terminal"
            else "LOCAL_CONTROLLER_GATE"
        ),
        "operational_claim": "NOT_ESTABLISHED_BY_THIS_CONTROLLER_ALONE",
        "required_failures": required_failures,
        "results": [dataclasses.asdict(item) for item in results],
        "execution_evidence": {
            "command_count": len(command_results),
            "git_ref_mutation_evidence": git_ref_mutation_evidence,
            "declared_possible_local_mutations": declared_local_mutations,
            "declared_network_access": declared_network_access,
            "live_witness_executed": live_witness_executed,
            "provider_mutation": (
                "DECLARED_POSSIBLE"
                if declared_provider_write
                else "UNVERIFIED_NO_PROVIDER_WRITE_DECLARED"
            ),
            "provider_mutation_note": (
                "No before/after provider-state comparison is performed. Child-process "
                "effects cannot be inferred beyond their declared command metadata."
            ),
            "credential_handling": "VALUES_REDACTED_AND_CHILD_ENV_ALLOWLISTED",
        },
        "scope_limits": [
            "No CI completion or protected merge is inferred from local success.",
            "No provider deployment or revision convergence is inferred from HTTP 200.",
            "Public probes witness only their recorded response contracts and source identity.",
        ],
    }
    json_path = destination / f"{phase}.json"
    md_path = destination / f"{phase}.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# SZL Codex Frontier — {phase}",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Repository: `{EXPECTED_REPOSITORY}`",
        f"- Base: `{base}`",
        f"- Complete: `{report['complete']}`",
        f"- Terminal status: `{terminal_status}`",
        f"- Operational claim: `{report['operational_claim']}`",
        f"- Required failures: `{', '.join(required_failures) or 'none'}`",
        "",
        "| Gate | Required | Status |",
        "|---|---:|---|",
    ]
    for item in results:
        lines.append(f"| `{item.name}` | `{item.required}` | `{item.status}` |")
    lines.extend(
        [
            "",
            "## Detail",
            "",
            "```json",
            json.dumps(report, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded acceptance and evidence controller for the SZL frontier build."
    )
    parser.add_argument("phase", choices=("preflight", "verify", "terminal"))
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--docker", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = repository_root()
    os.chdir(root)

    results: list[Result] = []
    full = args.full or args.phase == "terminal"
    docker = args.docker or args.phase == "terminal"
    live = args.live or args.phase == "terminal"

    if not args.no_fetch:
        fetch = command_result(
            Command(
                "fetch_origin_main",
                (
                    "git",
                    "fetch",
                    "--prune",
                    "origin",
                    "+refs/heads/main:refs/remotes/origin/main",
                ),
                timeout_s=180,
                local_mutations=("git_remote_tracking_refs", "FETCH_HEAD"),
                network_access="GIT_REMOTE_READ",
            ),
            root,
        )
        results.append(fetch)
    else:
        results.append(
            result(
                "fetch_origin_main",
                False,
                {
                    "reason": "--no-fetch prevents a fresh remote-base witness",
                    "base_freshness": "UNVERIFIED",
                    "git_mutation": "NOT_ATTEMPTED",
                },
            )
        )

    repository_check = check_repository(root)
    git_state_check = check_git_state(root, args.base, args.phase)
    results.extend([repository_check, git_state_check, check_agent_law(root)])

    files, inventory = changed_files(root, args.base)
    results.append(inventory)

    if args.phase in {"verify", "terminal"}:
        results.extend(
            verification_prerequisites(root, full=full, docker=docker)
        )
        if args.phase == "terminal":
            results.append(
                result(
                    "terminal_profile",
                    full and docker and live and not args.no_fetch,
                    {
                        "full_suite": full,
                        "docker_build": docker,
                        "public_live_witness": live,
                        "fresh_base_required": True,
                        "fresh_base_requested": not args.no_fetch,
                        "worktree_must_be_clean": True,
                    },
                )
            )
        results.extend(
            [
                check_effective_estate(root),
                check_changed_secrets(root, files, base=args.base),
                check_python_compile(root, files, base=args.base),
                check_changed_whitespace(root, files),
                check_new_top_level_python_copy(root, files),
            ]
        )
        for command in verification_commands(
            root,
            base=args.base,
            full=full,
            docker=docker,
        ):
            results.append(command_result(command, root))

        if live:
            expected_source_sha = git_state_check.detail.get("head")
            if not isinstance(expected_source_sha, str) or not SHA40.fullmatch(
                expected_source_sha
            ):
                expected_source_sha = None
            for name, probe in PUBLIC_PROBES.items():
                results.append(
                    anonymous_probe(
                        name,
                        probe["url"],
                        expected_content=probe["content"],
                        expected_source_sha=expected_source_sha,
                        require_source_identity=bool(
                            probe.get("require_source_identity", False)
                        ),
                    )
                )
            results.append(www_redirect_probe())

    destination = write_report(
        root,
        phase=args.phase,
        base=args.base,
        results=results,
        output_root=args.output,
    )
    print(destination)

    failed = [
        item
        for item in results
        if item.required and item.status != "PASS"
    ]
    if failed:
        print(
            "Required failures: " + ", ".join(item.name for item in failed),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
