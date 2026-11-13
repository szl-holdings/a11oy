#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Print one GitHub error annotation for a stopped inventory review-branch run.

Runs only after scripts/prepare_hf_inventory_refresh.py failed. A designed stop
such as SOURCE_REVIEW_REQUIRED otherwise shows only "exit code 1" on the run
page; this reads the report that step wrote and prints exactly one ``::error``
workflow command naming the state, the step, the reason and any governed
revision changes. Every report field is untrusted text: it is escaped here and
never reaches a shell. Visibility only: this script decides nothing, and the
job's verdict stays the prepare step's own exit status.
"""
import argparse
import json
from pathlib import Path
import sys
import unicodedata

TITLE = 'HF inventory refresh stopped'
SCHEMA = 'szl.hf-inventory-review-branch/v2'
MAX_LINE = 900
MAX_REPORT_BYTES = 1024 * 1024
UNRECORDED = 'UNRECORDED'


def escape_data(text: str) -> str:
    return text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def escape_property(text: str) -> str:
    return escape_data(text).replace(':', '%3A').replace(',', '%2C')


def printable(value: object, fallback: str = UNRECORDED) -> str:
    """Return report text with no character that could end or disguise the line.

    CR and LF survive here and are escaped later. Other controls, bidi/format
    characters, lone surrogates (which would crash UTF-8 output) and line or
    paragraph separators become '?'.
    """
    if type(value) is not str or not value.strip():
        return fallback
    return ''.join(
        ch if ch in '\r\n' or not (unicodedata.category(ch)[0] == 'C' or unicodedata.category(ch) in ('Zl', 'Zp'))
        else '?' for ch in value)


def governed_changes(report: dict) -> list[str]:
    revisions = report.get('governedRevisions')
    changed = revisions.get('changed') if type(revisions) is dict else None
    if type(changed) is not list:
        return []
    rendered = []
    for row in changed:
        row = row if type(row) is dict else {}
        fields = row.get('fields')
        names = ','.join(printable(item) for item in fields) if type(fields) is list and fields else UNRECORDED
        rendered.append(f"{printable(row.get('repoType'))}:{printable(row.get('id'))} ({names})")
    return rendered


def describe(report: dict) -> str:
    message = (f"{printable(report.get('state'))} at {printable(report.get('preparationStep'))}: "
               f"{printable(report.get('reason'), 'no reason recorded')}")
    changes = governed_changes(report)
    if changes:
        message += '; governed changes: ' + ', '.join(changes)
    return message


def load(path: Path) -> tuple[dict | None, str]:
    """Return (report, '') or (None, why the report cannot be used)."""
    shown = printable(str(path))
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
    except FileNotFoundError:
        return None, f'stop report is missing: {shown}'
    except OSError as exc:
        return None, f'stop report could not be read ({type(exc).__name__}): {shown}'
    if len(raw) > MAX_REPORT_BYTES:
        return None, f'stop report exceeds {MAX_REPORT_BYTES} bytes: {shown}'

    def reject(_: str) -> None:
        raise ValueError('nonfinite JSON')
    try:
        report = json.loads(raw.decode('utf-8'), parse_constant=reject)
    except (ValueError, RecursionError):
        return None, f'stop report is not valid JSON: {shown}'
    if type(report) is not dict or report.get('schema') != SCHEMA:
        return None, f'stop report is not a {SCHEMA} object: {shown}'
    return report, ''


def annotation(message: str, limit: int = MAX_LINE) -> str:
    """Escape the message and cap the whole command line without splitting an escape."""
    prefix = f'::error title={escape_property(TITLE)}::'
    pieces = [escape_data(ch) for ch in message]
    budget = limit - len(prefix)
    if sum(map(len, pieces)) <= budget:
        return prefix + ''.join(pieces)
    kept, size, marker = [], 0, '...'
    for piece in pieces:
        if size + len(piece) > budget - len(marker):
            break
        kept.append(piece)
        size += len(piece)
    return prefix + ''.join(kept) + marker


def render(path: Path) -> str:
    report, problem = load(path)
    return annotation(problem if report is None else describe(report))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='JSON report written by prepare_hf_inventory_refresh.py --output')
    args = parser.parse_args(argv)
    sys.stdout.buffer.write((render(args.report) + '\n').encode('utf-8'))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
