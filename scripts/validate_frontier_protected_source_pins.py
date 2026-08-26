#!/usr/bin/env python3
"""Validate Frontier source pins without importing or executing candidate bytes."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path


SOLO_WORKFLOW = ".github/workflows/frontier-solo-qualification.yml"
BUILDER_WORKFLOW = ".github/workflows/frontier-v16-7-exact-source-builder.yml"
CONTRACT = "ops/frontier/v16_7/SOLO_EXECUTION_CONTRACT.json"
REPAIR_SCRIPT = "ops/frontier/v16_7/apply_current_main_repairs.py"
SOURCE_TEST = "ops/frontier/v16_7/test_frontier_v16_7_terminal_truth.py"

MANAGED_PATHS = (
    SOLO_WORKFLOW,
    BUILDER_WORKFLOW,
    CONTRACT,
    REPAIR_SCRIPT,
    SOURCE_TEST,
)

MAX_FILE_BYTES = 1_048_576
ORPHAN_DIGEST_LINE = re.compile(
    r"^[ \t]*\$[0-9a-fA-F]{32,}[ \t]*$", re.MULTILINE
)
PIN_NAMES = {
    "CONTRACT": CONTRACT,
    "REPAIR_SCRIPT": REPAIR_SCRIPT,
    "SOURCE_TEST": SOURCE_TEST,
}


class ValidationError(RuntimeError):
    """The inert candidate bundle does not satisfy the protected contract."""


def _read_candidate(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"managed path is absent or not a regular file: {relative}")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValidationError(
            f"managed path exceeds {MAX_FILE_BYTES} bytes: {relative} ({size})"
        )
    return path.read_bytes()


def _decode_workflow(data: bytes, relative: str) -> str:
    if b"\0" in data:
        raise ValidationError(f"workflow contains a NUL byte: {relative}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"workflow is not valid UTF-8: {relative}") from exc


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_count(source: str, token: str, expected: int, label: str) -> None:
    observed = source.count(token)
    if observed != expected:
        raise ValidationError(
            f"{label}: expected {expected} exact occurrence(s), found {observed}"
        )


def _shell_function(source: str, name: str, workflow: str) -> str:
    declaration = f"          {name}() {{"
    lines = source.splitlines()
    starts = [index for index, line in enumerate(lines) if line == declaration]
    if len(starts) != 1:
        raise ValidationError(
            f"{workflow}: expected one {name} shell function, found {len(starts)}"
        )
    start = starts[0]
    for end in range(start + 1, len(lines)):
        if lines[end] == "          }":
            return "\n".join(lines[start : end + 1])
    raise ValidationError(f"{workflow}: unterminated {name} shell function")


def _job_bounds(
    source: str, workflow: str, job_name: str
) -> tuple[list[str], int, int]:
    job_marker = f"  {job_name}:"
    lines = source.splitlines()
    job_starts = [index for index, line in enumerate(lines) if line == job_marker]
    if len(job_starts) != 1:
        raise ValidationError(
            f"{workflow}: expected one {job_name} job, found {len(job_starts)}"
        )
    start = job_starts[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and (
            not line.startswith(" ")
            or (line.startswith("  ") and not line.startswith("    "))
        ):
            end = index
            break
    return lines, start, end


def _job_env(source: str, workflow: str, job_name: str) -> str:
    lines, start, end = _job_bounds(source, workflow, job_name)
    env_starts = [
        index
        for index in range(start + 1, end)
        if lines[index] == "    env:"
    ]
    step_starts = [
        index
        for index in range(start + 1, end)
        if lines[index] == "    steps:"
    ]
    if len(env_starts) != 1 or len(step_starts) != 1:
        raise ValidationError(f"{workflow}: expected one job env and steps block")
    env_start = env_starts[0]
    steps_start = step_starts[0]
    if env_start >= steps_start:
        raise ValidationError(f"{workflow}: job env must precede steps")
    return "\n".join(lines[env_start + 1 : steps_start])


def _literal_run_block(source: str, workflow: str, job_name: str) -> str:
    marker = "        run: |"
    lines, job_start, job_end = _job_bounds(source, workflow, job_name)
    starts = [
        index
        for index in range(job_start + 1, job_end)
        if lines[index] == marker
    ]
    if len(starts) != 1:
        raise ValidationError(
            f"{workflow}: expected one literal run block, found {len(starts)}"
        )
    start = starts[0] + 1
    end = start
    while end < job_end:
        line = lines[end]
        if line and not line.startswith("          "):
            break
        end += 1
    return "\n".join(lines[start:end])


def _validate_pin_declarations(
    source: str,
    env_block: str,
    workflow: str,
    expected_digests: dict[str, str],
) -> None:
    orphan = ORPHAN_DIGEST_LINE.search(source)
    if orphan is not None:
        line = source.count("\n", 0, orphan.start()) + 1
        raise ValidationError(
            f"{workflow}: orphan digest-like shell expansion on line {line}"
        )

    for name, digest in expected_digests.items():
        broad = re.findall(
            rf"^[ \t]*{re.escape(name)}_SHA256[ \t]*:",
            source,
            re.MULTILINE,
        )
        if len(broad) != 1:
            raise ValidationError(
                f"{workflow}: expected one {name}_SHA256 declaration, "
                f"found {len(broad)}"
            )
        exact = re.findall(
            rf"^      {re.escape(name)}_SHA256: ([0-9a-f]{{64}})$",
            env_block,
            re.MULTILINE,
        )
        if exact != [digest]:
            observed = exact[0] if len(exact) == 1 else "malformed"
            raise ValidationError(
                f"{workflow}: {name}_SHA256 is {observed}, expected {digest}"
            )


def _validate_solo(source: str, expected_digests: dict[str, str]) -> None:
    env_block = _job_env(
        source,
        SOLO_WORKFLOW,
        "platform-solo-qualification",
    )
    run_block = _literal_run_block(
        source,
        SOLO_WORKFLOW,
        "platform-solo-qualification",
    )
    _validate_pin_declarations(source, env_block, SOLO_WORKFLOW, expected_digests)
    verify = _shell_function(
        run_block, "verify_protected_material", SOLO_WORKFLOW
    )
    pull_request = _shell_function(
        run_block, "validate_pull_request", SOLO_WORKFLOW
    )
    merge_group = _shell_function(run_block, "validate_merge_group", SOLO_WORKFLOW)

    _require_count(
        verify,
        'test "$observed_repair_digest" = "$REPAIR_SCRIPT_SHA256"',
        1,
        f"{SOLO_WORKFLOW} protected repair comparison",
    )
    _require_count(
        verify,
        'test "$contract_digest" = "$CONTRACT_SHA256"',
        1,
        f"{SOLO_WORKFLOW} protected contract comparison",
    )
    for function_name, function in (
        ("validate_pull_request", pull_request),
        ("validate_merge_group", merge_group),
    ):
        _require_count(
            function,
            'verify_protected_material "$base_sha"',
            1,
            f"{SOLO_WORKFLOW} {function_name} protected-material call",
        )
        _require_count(
            function,
            'test "$test_digest" = "$SOURCE_TEST_SHA256"',
            1,
            f"{SOLO_WORKFLOW} {function_name} source-test comparison",
        )

    _require_count(
        run_block,
        "            pull_request) validate_pull_request ;;",
        1,
        f"{SOLO_WORKFLOW} pull-request dispatcher",
    )
    _require_count(
        run_block,
        "            merge_group) validate_merge_group ;;",
        1,
        f"{SOLO_WORKFLOW} merge-group dispatcher",
    )
    _require_count(
        run_block,
        '            *) echo "unsupported event: $EVENT_NAME" >&2; exit 2 ;;',
        1,
        f"{SOLO_WORKFLOW} fail-closed event dispatcher",
    )


def _validate_builder(source: str, expected_digests: dict[str, str]) -> None:
    env_block = _job_env(source, BUILDER_WORKFLOW, "build-exact-source")
    run_block = _literal_run_block(
        source,
        BUILDER_WORKFLOW,
        "build-exact-source",
    )
    _validate_pin_declarations(
        source,
        env_block,
        BUILDER_WORKFLOW,
        expected_digests,
    )
    for token, label in (
        (
            'test "$contract" = "$CONTRACT_SHA256"',
            "contract comparison",
        ),
        (
            'test "$(sha256sum "$repair_script" | awk \'{print $1}\')" '
            '= "$REPAIR_SCRIPT_SHA256"',
            "repair-script comparison",
        ),
        (
            'test "$(sha256sum "$source_test" | awk \'{print $1}\')" '
            '= "$SOURCE_TEST_SHA256"',
            "source-test comparison",
        ),
    ):
        _require_count(
            run_block,
            token,
            1,
            f"{BUILDER_WORKFLOW} {label}",
        )


def validate(bundle_dir: Path) -> dict[str, str]:
    root = bundle_dir.resolve(strict=True)
    candidate = {relative: _read_candidate(root, relative) for relative in MANAGED_PATHS}
    expected_digests = {
        name: _digest(candidate[path]) for name, path in PIN_NAMES.items()
    }
    solo = _decode_workflow(candidate[SOLO_WORKFLOW], SOLO_WORKFLOW)
    builder = _decode_workflow(candidate[BUILDER_WORKFLOW], BUILDER_WORKFLOW)
    _validate_solo(solo, expected_digests)
    _validate_builder(builder, expected_digests)
    return expected_digests


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle-dir",
        required=True,
        type=Path,
        help="directory containing candidate files fetched as inert data",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        digests = validate(args.bundle_dir)
    except (OSError, ValidationError) as exc:
        print(f"Frontier protected source-pin qualification: FAIL: {exc}", file=sys.stderr)
        return 1
    print("Frontier protected source-pin qualification: PASS")
    for name in sorted(digests):
        print(f"{name}_SHA256={digests[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
