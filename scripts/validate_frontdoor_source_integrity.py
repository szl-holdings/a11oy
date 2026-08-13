#!/usr/bin/env python3
"""Fail closed on disabled HF drift controls or corrupted public UTF-8.

This standard-library guard runs from the independent ``Tests`` workflow. It
therefore remains active when ``hf-module-drift.yml`` itself is damaged.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = Path(".github/workflows/hf-module-drift.yml")
ALLOWLIST_PATH = Path(".github/hf-module-drift-allow.json")

TOOLS_REVISION = "0816263f1e83734658d6e5a8a7cd3834f36a2054"
REUSABLE_WORKFLOW = (
    "szl-holdings/.github/.github/workflows/"
    f"reusable-hf-module-drift-check.yml@{TOOLS_REVISION}"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
REMOTE_USE = re.compile(r"^[^\s@]+@([^\s]+)$")
WORKFLOW_SEMANTIC_SHA256 = (
    "7b1755d2963f14f5e9778e8b333562f907f848458d56474a08a6b1902b4a090c"
)

PUBLIC_UTF8_PATHS = (
    Path("a11oy_landing.html"),
    Path("govern_showcase.html"),
    Path("pages/assurance.html"),
    Path("pages/chaski.html"),
    Path("pages/console.html"),
    Path("pages/fabric.html"),
    Path("pages/landing.html"),
    Path("pages/pinn-console.html"),
    Path("pages/pricing.html"),
    Path("pages/substrate.html"),
    Path("pages/verify.html"),
)

JOB_FIELDS = {
    "hf-module-drift": {
        "name": "Source in sync with the live HF Space",
        "if": "github.event_name == 'pull_request'",
        "runs-on": "ubuntu-latest",
        "timeout-minutes": "15",
    },
    "hf-repository-parity": {
        "name": "Immutable live baseline + candidate delta",
        "if": "github.event_name == 'pull_request'",
        "uses": REUSABLE_WORKFLOW,
    },
    "hf-runtime-live": {
        "name": "Source in sync with the live HF Space",
        "if": "github.event_name != 'pull_request'",
        "uses": REUSABLE_WORKFLOW,
    },
}

JOB_ALLOWED_FIELDS = {
    "hf-module-drift": {"name", "if", "runs-on", "timeout-minutes", "steps"},
    "hf-repository-parity": {"name", "if", "uses", "with"},
    "hf-runtime-live": {"name", "if", "uses", "with"},
}

BASE_STEP_NAMES = (
    "Harden runner",
    "Checkout exact protected base verifier",
    "Checkout exact reusable tools revision",
    "Set up Python",
    "Prove stable immutable deployed-base repository parity",
    "Upload immutable deployed-base proof",
)

PARITY_RUN_LINES = (
    (10, "python3 baseline/.github/scripts/verify_hf_repository_parity.py \\"),
    (12, "--tools-script tools/.github/scripts/hf_module_drift_check.py \\"),
    (12, '--github-repo "$GITHUB_REPOSITORY" \\'),
    (12, '--github-ref "$SOURCE_REF" \\'),
    (12, "--hf-repo SZLHOLDINGS/a11oy \\"),
    (12, "--report-out hf-current-base-parity.out.json"),
)

CALL_INPUTS = {
    "hf-repository-parity": {
        "hf-repo": "SZLHOLDINGS/a11oy",
        "mode": "source-bound-baseline",
        "trusted-base-ref": "${{ github.event.pull_request.base.sha }}",
        "candidate-ref": "${{ github.event.pull_request.head.sha }}",
        "source-probe-path": "/api/build-info",
        "dockerfile-path": "Dockerfile",
    },
    "hf-runtime-live": {
        "hf-repo": "SZLHOLDINGS/a11oy",
        "mode": "source-bound-baseline",
        "trusted-base-ref": "${{ github.sha }}",
        "candidate-ref": "${{ github.sha }}",
        "source-probe-path": "/api/build-info",
        "dockerfile-path": "Dockerfile",
        "github-ref": "${{ github.sha }}",
        "hf-ref": "main",
    },
}


def _read_strict_utf8(root: Path, relative: Path) -> tuple[str | None, list[str]]:
    path = root / relative
    if not path.is_file():
        return None, [f"missing file: {relative.as_posix()}"]

    raw = path.read_bytes()
    errors: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"UTF-8 BOM is forbidden: {relative.as_posix()}")
    try:
        return raw.decode("utf-8"), errors
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8: {relative.as_posix()}: {exc}")
        return None, errors


def _semantic_lines(text: str) -> list[tuple[int, int, str]]:
    """Return non-comment lines as ``(number, indent, content)`` tuples."""

    result: list[tuple[int, int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        # The audited workflow has no value containing a space followed by '#'.
        # Removing that form prevents tokens in inline comments from proving shape.
        code = raw.split(" #", 1)[0].rstrip()
        if not code.strip():
            continue
        indent = len(code) - len(code.lstrip(" "))
        result.append((number, indent, code[indent:]))
    return result


def _find_block(
    lines: list[tuple[int, int, str]], key: str, indent: int
) -> tuple[list[tuple[int, int, str]], list[str]]:
    marker = f"{key}:"
    matches = [index for index, (_, level, body) in enumerate(lines) if level == indent and body == marker]
    if len(matches) != 1:
        return [], [f"workflow requires exactly one active {marker} at indent {indent}; observed {len(matches)}"]
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index][1] <= indent:
            end = index
            break
    return lines[start + 1 : end], []


def _find_value_block(
    lines: list[tuple[int, int, str]], key: str, value: str, indent: int
) -> tuple[list[tuple[int, int, str]], list[str]]:
    marker = f"{key}: {value}"
    matches = [
        index
        for index, (_, level, body) in enumerate(lines)
        if level == indent and body == marker
    ]
    if len(matches) != 1:
        return [], [
            f"workflow requires exactly one active {marker} at indent {indent}; "
            f"observed {len(matches)}"
        ]
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index][1] <= indent:
            end = index
            break
    return lines[start + 1 : end], []


def _find_named_step(
    lines: list[tuple[int, int, str]], name: str, indent: int = 6
) -> tuple[list[tuple[int, int, str]], list[str]]:
    marker = f"- name: {name}"
    matches = [
        index
        for index, (_, level, body) in enumerate(lines)
        if level == indent and body == marker
    ]
    if len(matches) != 1:
        return [], [
            f"workflow requires exactly one active step {name!r}; observed {len(matches)}"
        ]
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index][1] <= indent:
            end = index
            break
    return lines[start + 1 : end], []


def _direct_fields(
    block: list[tuple[int, int, str]], indent: int
) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    for number, level, body in block:
        if level != indent:
            continue
        match = re.fullmatch(r"([A-Za-z0-9_-]+):(?:\s*(.*))?", body)
        if not match:
            errors.append(
                "unsupported or noncanonical workflow mapping syntax "
                f"at line {number}: {body!r}"
            )
            continue
        key = match.group(1)
        value = match.group(2) or ""
        if key in fields:
            errors.append(f"duplicate active workflow field {key!r} at line {number}")
        fields[key] = value
    return fields, errors


def _require_exact_fields(
    label: str, actual: dict[str, str], expected: dict[str, str]
) -> list[str]:
    errors: list[str] = []
    for key, value in expected.items():
        if actual.get(key) != value:
            errors.append(
                f"{label} requires active {key}: {value}; observed {actual.get(key)!r}"
            )
    return errors


def _validate_workflow(workflow: str) -> list[str]:
    errors: list[str] = []
    for offset, character in enumerate(workflow):
        codepoint = ord(character)
        if character in {"\n", "\r"}:
            continue
        if 0x20 <= codepoint <= 0x7E:
            continue
        errors.append(
            "HF drift workflow contains a noncanonical or YAML-forbidden "
            f"character U+{codepoint:04X} at character offset {offset}"
        )
    if "\t" in workflow:
        errors.append("HF drift workflow must not contain tab characters")
    if len(workflow.splitlines()) < 100:
        errors.append(
            f"HF drift workflow is unexpectedly short: {len(workflow.splitlines())} lines (minimum 100)"
        )

    lines = _semantic_lines(workflow)
    semantic_contract = [(level, body) for _, level, body in lines]
    semantic_sha256 = hashlib.sha256(
        json.dumps(
            semantic_contract,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if semantic_sha256 != WORKFLOW_SEMANTIC_SHA256:
        errors.append(
            "HF drift semantic document must match the audited canonical contract; "
            f"observed sha256 {semantic_sha256}"
        )
    top_fields, field_errors = _direct_fields(lines, 0)
    errors.extend(field_errors)
    expected_top_fields = {
        "name": "HF Space module-drift guard",
        "on": "",
        "permissions": "",
        "concurrency": "",
        "jobs": "",
    }
    if top_fields != expected_top_fields:
        errors.append(
            "HF drift top-level fields must match the audited contract; "
            f"observed {top_fields!r}"
        )

    on_block, block_errors = _find_block(lines, "on", 0)
    errors.extend(block_errors)
    on_fields, field_errors = _direct_fields(on_block, 2)
    errors.extend(field_errors)
    expected_on_fields = {
        "pull_request": "",
        "schedule": "",
        "workflow_dispatch": "",
    }
    if on_fields != expected_on_fields:
        errors.append(
            "HF drift workflow events must be exact active mappings for "
            "pull_request, schedule, and workflow_dispatch; "
            f"observed {on_fields!r}"
        )
    pull_request_block, block_errors = _find_block(on_block, "pull_request", 2)
    errors.extend(block_errors)
    pull_request_fields, field_errors = _direct_fields(pull_request_block, 4)
    errors.extend(field_errors)
    if pull_request_fields != {"branches": "[main]"}:
        errors.append(
            "HF drift pull_request trigger must be exactly branches: [main]; "
            f"observed {pull_request_fields!r}"
        )
    schedule_block, block_errors = _find_block(on_block, "schedule", 2)
    errors.extend(block_errors)
    observed_schedule = tuple((level, body) for _, level, body in schedule_block)
    expected_schedule = ((4, "- cron: '37 6 * * 1'"),)
    if observed_schedule != expected_schedule:
        errors.append(
            "HF drift schedule must be exactly the active weekly cron; "
            f"observed {observed_schedule!r}"
        )
    workflow_dispatch_block, block_errors = _find_block(
        on_block, "workflow_dispatch", 2
    )
    errors.extend(block_errors)
    if workflow_dispatch_block:
        errors.append(
            "HF drift workflow_dispatch must be the exact empty manual trigger; "
            f"observed {workflow_dispatch_block!r}"
        )

    permission_block, block_errors = _find_block(lines, "permissions", 0)
    errors.extend(block_errors)
    permissions, field_errors = _direct_fields(permission_block, 2)
    errors.extend(field_errors)
    if permissions != {"contents": "read"}:
        errors.append(f"HF drift workflow permissions must be exactly contents: read; observed {permissions!r}")

    concurrency_block, block_errors = _find_block(lines, "concurrency", 0)
    errors.extend(block_errors)
    concurrency, field_errors = _direct_fields(concurrency_block, 2)
    errors.extend(field_errors)
    expected_concurrency = {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "true",
    }
    if concurrency != expected_concurrency:
        errors.append(
            "HF drift concurrency must match the exact per-workflow/ref contract; "
            f"observed {concurrency!r}"
        )

    jobs_block, block_errors = _find_block(lines, "jobs", 0)
    errors.extend(block_errors)
    jobs, field_errors = _direct_fields(jobs_block, 2)
    errors.extend(field_errors)
    if set(jobs) != set(JOB_FIELDS):
        errors.append(
            f"HF drift workflow jobs must be exactly {sorted(JOB_FIELDS)}; observed {sorted(jobs)}"
        )

    for job_name, expected in JOB_FIELDS.items():
        job_block, block_errors = _find_block(jobs_block, job_name, 2)
        errors.extend(block_errors)
        fields, field_errors = _direct_fields(job_block, 4)
        errors.extend(field_errors)
        errors.extend(_require_exact_fields(f"job {job_name}", fields, expected))
        if set(fields) != JOB_ALLOWED_FIELDS[job_name]:
            errors.append(
                f"job {job_name} fields must be exactly "
                f"{sorted(JOB_ALLOWED_FIELDS[job_name])}; observed {sorted(fields)}"
            )

        if job_name in CALL_INPUTS:
            with_block, block_errors = _find_block(job_block, "with", 4)
            errors.extend(block_errors)
            inputs, field_errors = _direct_fields(with_block, 6)
            errors.extend(field_errors)
            if inputs != CALL_INPUTS[job_name]:
                errors.append(
                    f"job {job_name} inputs must match the source-bound contract; observed {inputs!r}"
                )

    base_block, block_errors = _find_block(jobs_block, "hf-module-drift", 2)
    errors.extend(block_errors)
    observed_step_headers = tuple(
        body
        for _, level, body in base_block
        if level == 6
    )
    expected_step_headers = tuple(f"- name: {name}" for name in BASE_STEP_NAMES)
    if observed_step_headers != expected_step_headers:
        errors.append(
            "protected-base parity steps must match the exact ordered contract; "
            f"observed {observed_step_headers!r}"
        )

    harden_step, step_errors = _find_named_step(base_block, "Harden runner")
    errors.extend(step_errors)
    harden_fields, field_errors = _direct_fields(harden_step, 8)
    errors.extend(field_errors)
    expected_harden_fields = {
        "uses": "step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40",
        "with": "",
    }
    if harden_fields != expected_harden_fields:
        errors.append(
            "harden-runner step fields must match the immutable contract; "
            f"observed {harden_fields!r}"
        )
    harden_with, block_errors = _find_block(harden_step, "with", 8)
    errors.extend(block_errors)
    harden_inputs, field_errors = _direct_fields(harden_with, 10)
    errors.extend(field_errors)
    if harden_inputs != {"egress-policy": "audit"}:
        errors.append(
            "harden-runner inputs must be exactly egress-policy: audit; "
            f"observed {harden_inputs!r}"
        )

    base_checkout, step_errors = _find_named_step(
        base_block, "Checkout exact protected base verifier"
    )
    errors.extend(step_errors)
    base_checkout_fields, field_errors = _direct_fields(base_checkout, 8)
    errors.extend(field_errors)
    expected_checkout_fields = {
        "uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "with": "",
    }
    if base_checkout_fields != expected_checkout_fields:
        errors.append(
            "protected-base checkout fields must match the immutable contract; "
            f"observed {base_checkout_fields!r}"
        )
    base_checkout_with, block_errors = _find_block(base_checkout, "with", 8)
    errors.extend(block_errors)
    base_checkout_inputs, field_errors = _direct_fields(base_checkout_with, 10)
    errors.extend(field_errors)
    expected_checkout_inputs = {
        "path": "baseline",
        "ref": "${{ github.event.pull_request.base.sha }}",
        "persist-credentials": "false",
    }
    if base_checkout_inputs != expected_checkout_inputs:
        errors.append(
            "protected-base checkout inputs must match the exact PR base; "
            f"observed {base_checkout_inputs!r}"
        )

    tools_checkout, step_errors = _find_named_step(
        base_block, "Checkout exact reusable tools revision"
    )
    errors.extend(step_errors)
    tools_checkout_fields, field_errors = _direct_fields(tools_checkout, 8)
    errors.extend(field_errors)
    if tools_checkout_fields != expected_checkout_fields:
        errors.append(
            "tools checkout fields must match the immutable contract; "
            f"observed {tools_checkout_fields!r}"
        )
    tools_checkout_with, block_errors = _find_block(tools_checkout, "with", 8)
    errors.extend(block_errors)
    tools_checkout_inputs, field_errors = _direct_fields(tools_checkout_with, 10)
    errors.extend(field_errors)
    expected_tools_inputs = {
        "repository": "szl-holdings/.github",
        "ref": TOOLS_REVISION,
        "path": "tools",
        "persist-credentials": "false",
    }
    if tools_checkout_inputs != expected_tools_inputs:
        errors.append(
            "tools checkout inputs must match the pinned authority; "
            f"observed {tools_checkout_inputs!r}"
        )

    setup_step, step_errors = _find_named_step(base_block, "Set up Python")
    errors.extend(step_errors)
    setup_fields, field_errors = _direct_fields(setup_step, 8)
    errors.extend(field_errors)
    expected_setup_fields = {
        "uses": "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "with": "",
    }
    if setup_fields != expected_setup_fields:
        errors.append(
            "Python setup fields must match the immutable contract; "
            f"observed {setup_fields!r}"
        )
    setup_with, block_errors = _find_block(setup_step, "with", 8)
    errors.extend(block_errors)
    setup_inputs, field_errors = _direct_fields(setup_with, 10)
    errors.extend(field_errors)
    if setup_inputs != {"python-version": '"3.12"'}:
        errors.append(
            "Python setup must pin version 3.12; "
            f"observed {setup_inputs!r}"
        )

    parity_step, step_errors = _find_named_step(
        base_block, "Prove stable immutable deployed-base repository parity"
    )
    errors.extend(step_errors)
    parity_env, block_errors = _find_block(parity_step, "env", 8)
    errors.extend(block_errors)
    parity_env_fields, field_errors = _direct_fields(parity_env, 10)
    errors.extend(field_errors)
    expected_parity_env = {
        "GITHUB_TOKEN": "${{ github.token }}",
        "SOURCE_REF": "${{ github.event.pull_request.base.sha }}",
    }
    if parity_env_fields != expected_parity_env:
        errors.append(
            "protected-base parity environment must bind the exact PR base; "
            f"observed {parity_env_fields!r}"
        )
    parity_fields, field_errors = _direct_fields(parity_step, 8)
    errors.extend(field_errors)
    if parity_fields != {"env": "", "run": "|"}:
        errors.append(
            "protected-base parity step fields must be exactly env and run; "
            f"observed {parity_fields!r}"
        )
    parity_run, block_errors = _find_value_block(parity_step, "run", "|", 8)
    errors.extend(block_errors)
    observed_run_lines = tuple(
        (level, body) for _, level, body in parity_run
    )
    if observed_run_lines != PARITY_RUN_LINES:
        errors.append(
            "protected-base parity run script must match the exact fail-closed command; "
            f"observed {observed_run_lines!r}"
        )

    upload_step, step_errors = _find_named_step(
        base_block, "Upload immutable deployed-base proof"
    )
    errors.extend(step_errors)
    upload_fields, field_errors = _direct_fields(upload_step, 8)
    errors.extend(field_errors)
    expected_upload_fields = {
        "if": "always()",
        "uses": "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "with": "",
    }
    if upload_fields != expected_upload_fields:
        errors.append(
            "proof upload step fields must match the immutable contract; "
            f"observed {upload_fields!r}"
        )
    upload_with, block_errors = _find_block(upload_step, "with", 8)
    errors.extend(block_errors)
    upload_inputs, field_errors = _direct_fields(upload_with, 10)
    errors.extend(field_errors)
    expected_upload_inputs = {
        "name": "hf-current-base-parity",
        "path": "hf-current-base-parity.out.json",
        "if-no-files-found": "error",
        "retention-days": "90",
    }
    if upload_inputs != expected_upload_inputs:
        errors.append(
            "proof upload inputs must match the immutable contract; "
            f"observed {upload_inputs!r}"
        )

    for number, _, body in base_block:
        if re.fullmatch(r"continue-on-error:\s*.*", body):
            errors.append(
                f"protected-base parity job forbids continue-on-error at line {number}"
            )

    base_text = "\n".join(" " * indent + body for _, indent, body in base_block)
    required_base_lines = (
        "      - name: Checkout exact reusable tools revision",
        "          repository: szl-holdings/.github",
        f"          ref: {TOOLS_REVISION}",
        "      - name: Prove stable immutable deployed-base repository parity",
        "          python3 baseline/.github/scripts/verify_hf_repository_parity.py \\",
        "            --tools-script tools/.github/scripts/hf_module_drift_check.py \\",
        "            --github-ref \"$SOURCE_REF\" \\",
        "            --hf-repo SZLHOLDINGS/a11oy \\",
    )
    for required in required_base_lines:
        if required not in base_text:
            errors.append(f"protected-base parity step missing active line: {required.strip()}")

    for number, _, body in lines:
        match = re.search(r"(?:^|\s)uses:\s*([^\s]+)", body)
        if not match:
            continue
        use = match.group(1)
        remote = REMOTE_USE.fullmatch(use)
        if remote is None or FULL_SHA.fullmatch(remote.group(1)) is None:
            errors.append(f"workflow uses must be pinned to lowercase 40-hex revisions: line {number}: {use}")

    return errors


def _cp1252_byte(character: str) -> int | None:
    try:
        encoded = character.encode("cp1252")
    except UnicodeEncodeError:
        return None
    return encoded[0] if len(encoded) == 1 else None


def _reversible_mojibake_hits(content: str) -> list[tuple[str, str]]:
    """Find CP1252 glyph runs that reversibly decode as one UTF-8 code point."""

    hits: list[tuple[str, str]] = []
    for index, character in enumerate(content):
        lead = _cp1252_byte(character)
        if lead is None:
            continue
        if 0xC2 <= lead <= 0xDF:
            width = 2
        elif 0xE0 <= lead <= 0xEF:
            width = 3
        elif 0xF0 <= lead <= 0xF4:
            width = 4
        else:
            continue
        source = content[index : index + width]
        if len(source) != width:
            continue
        encoded = [_cp1252_byte(item) for item in source]
        if any(item is None for item in encoded):
            continue
        octets = bytes(item for item in encoded if item is not None)
        if any(not 0x80 <= item <= 0xBF for item in octets[1:]):
            continue
        try:
            repaired = octets.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if len(repaired) == 1 and ord(repaired) >= 0x80:
            hits.append((source, repaired))
    return hits


def _string_list(value: object, key: str) -> tuple[list[str], list[str]]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return [], [f"{key} must be a JSON array of strings"]
    return value, []


def _validate_allowlist(root: Path) -> list[str]:
    path = root / ALLOWLIST_PATH
    if not path.is_file():
        return [f"missing file: {ALLOWLIST_PATH.as_posix()}"]
    try:
        allowlist = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid HF drift allowlist: {exc}"]
    if not isinstance(allowlist, dict):
        return ["HF drift allowlist must be a JSON object"]

    errors: list[str] = []
    accepted = allowlist.get("accepted_divergences")
    if not isinstance(accepted, dict):
        errors.append("accepted_divergences must be a JSON object")
        accepted = {}
    ignore_paths, list_errors = _string_list(allowlist.get("ignore_paths", []), "ignore_paths")
    errors.extend(list_errors)
    ignore_extensions, list_errors = _string_list(
        allowlist.get("ignore_extensions", []), "ignore_extensions"
    )
    errors.extend(list_errors)
    folded_extensions = {extension.lower() for extension in ignore_extensions}

    for relative in PUBLIC_UTF8_PATHS:
        key = relative.as_posix()
        if key in accepted:
            errors.append(f"monitored public file cannot bypass HF parity: {key}")
        for pattern in ignore_paths:
            if fnmatch.fnmatch(key, pattern):
                errors.append(
                    f"ignore_paths pattern {pattern!r} bypasses monitored public file: {key}"
                )
        if relative.suffix.lower() in folded_extensions:
            errors.append(
                f"ignore_extensions entry {relative.suffix!r} bypasses monitored public file: {key}"
            )
    return errors


def validate(root: Path = REPO_ROOT) -> list[str]:
    """Return every integrity error; an empty list is PASS."""

    errors: list[str] = []
    workflow, workflow_errors = _read_strict_utf8(root, WORKFLOW_PATH)
    errors.extend(workflow_errors)
    if workflow is not None:
        errors.extend(_validate_workflow(workflow))
    errors.extend(_validate_allowlist(root))

    for relative in PUBLIC_UTF8_PATHS:
        content, file_errors = _read_strict_utf8(root, relative)
        errors.extend(file_errors)
        if content is None:
            continue
        mojibake_hits = _reversible_mojibake_hits(content)
        if mojibake_hits:
            examples = ", ".join(
                f"{source!r}->{repaired!r}"
                for source, repaired in mojibake_hits[:5]
            )
            errors.append(
                f"reversible CP1252/UTF-8 mojibake in {relative.as_posix()}: "
                f"{len(mojibake_hits)} occurrence(s); {examples}"
            )
        replacement_count = content.count("\ufffd")
        if replacement_count:
            errors.append(
                f"Unicode replacement character in {relative.as_posix()}: "
                f"{replacement_count} occurrence(s)"
            )
        controls = sorted({ord(char) for char in content if 0x80 <= ord(char) <= 0x9F})
        if controls:
            rendered = ", ".join(f"U+{codepoint:04X}" for codepoint in controls)
            errors.append(f"C1 control character(s) in {relative.as_posix()}: {rendered}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    result = {
        "status": "PASS" if not errors else "FAIL",
        "workflow": WORKFLOW_PATH.as_posix(),
        "public_files_checked": len(PUBLIC_UTF8_PATHS),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
