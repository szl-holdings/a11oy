#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Render the labelled Hugging Face --check result for the drift issue body.

scripts/audit_huggingface_ecosystem.py --check prints
``Hugging Face ecosystem check result: <LABEL> (<meaning>)`` as its last line.
The drift job tees that output to a log; this keeps only the last line of
exactly that shape, from a fixed character set, and prints it as one Markdown
code span. Row ids and other log text never reach the issue. The label must
agree with the recorded exit code (only CURRENT exits 0); a mismatch is
reported as UNVERIFIED, never repaired. Visibility only: the job's STATE and
gate still come from the exit code alone.
"""
import argparse
from pathlib import Path
import re
import sys

PREFIX = 'Hugging Face ecosystem check result: '
LINE = re.compile(r'Hugging Face ecosystem check result: (CURRENT|DRIFT|INVALID|UNAVAILABLE) '
                  r'\(([A-Za-z0-9 ,;.()/_-]{1,200})\)\Z')
EXIT_CODE = re.compile(r'[0-9]{1,3}\Z')
TAIL_BYTES = 64 * 1024
NOT_RECORDED = 'UNAVAILABLE (no labelled check result line was recorded)'
UNEXPECTED = 'UNVERIFIED (the last labelled check result line did not have the expected shape)'


def last_result_line(text: str) -> str | None:
    # Only the collector's own '\n' ends a line; any other separator stays in
    # the line and fails the character set below.
    for line in reversed(text.split('\n')):
        if line.startswith(PREFIX):
            return line
    return None


def render(text: str | None, exit_code: str) -> str:
    line = last_result_line(text) if text is not None else None
    if line is None:
        return NOT_RECORDED
    match = LINE.fullmatch(line)
    if match is None:
        return UNEXPECTED
    label = match.group(1)
    code = int(exit_code) if EXIT_CODE.fullmatch(exit_code or '') else None
    if code is None or (code == 0) != (label == 'CURRENT'):
        return f'UNVERIFIED (labelled result {label} does not match the recorded exit code)'
    return f'`{label} ({match.group(2)})`'


def read_tail(path: Path) -> str | None:
    """The result line is printed last, so a bounded tail is enough."""
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - TAIL_BYTES))
            return stream.read().decode('utf-8', errors='replace')
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, required=True, help='tee output of audit_huggingface_ecosystem.py --check')
    parser.add_argument('--exit-code', default='', help='recorded exit code of that --check run')
    args = parser.parse_args(argv)
    sys.stdout.write(render(read_tail(args.log), args.exit_code) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
