# SPDX-License-Identifier: Apache-2.0
"""Lexicon and commercial gates fail the job on different refs.

The docs lexicon gate fails the job on a push to refs/heads/main or
refs/tags/*. The commercial release gate fails the job only on a tag
push. Every other ref still runs both tools and still returns the tool
status; continue-on-error keeps that ref from failing the job. An
unconditional continue-on-error: true is the soft-fail this contract
forbids.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/truth-gates.yml"
JOB_MARKER = "  workspace-disposition-contract:\n"

LEXICON_PREDICATE = (
    "github.event_name == 'push' && "
    "(github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/'))"
)
COMMERCIAL_PREDICATE = (
    "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')"
)
LEXICON_ENV = 'LEXICON_GATE_BLOCKING: "${{ ' + LEXICON_PREDICATE + ' }}"'
COMMERCIAL_ENV = 'COMMERCIAL_GATE_BLOCKING: "${{ ' + COMMERCIAL_PREDICATE + ' }}"'
LEXICON_OBSERVE = 'continue-on-error: "${{ !(' + LEXICON_PREDICATE + ') }}"'
COMMERCIAL_OBSERVE = 'continue-on-error: "${{ !(' + COMMERCIAL_PREDICATE + ') }}"'

CHECKOUT_PIN = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_PIN = "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0"


def _truth_job() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(JOB_MARKER) == 1
    return text.split(JOB_MARKER, 1)[0]


def _step(job: str, name: str) -> str:
    marker = f"      - name: {name}\n"
    assert job.count(marker) == 1
    rest = job.split(marker, 1)[1]
    boundaries = [
        index
        for index in (
            rest.find("\n      - name: "),
            rest.find("\n      - uses: "),
        )
        if index >= 0
    ]
    if not boundaries:
        return rest
    return rest[: min(boundaries)]


def lexicon_continue_on_error(event: str, ref: str) -> bool:
    """True when a lexicon failure must not fail the job."""
    blocking = event == "push" and (
        ref == "refs/heads/main" or ref.startswith("refs/tags/")
    )
    return not blocking


def commercial_continue_on_error(event: str, ref: str) -> bool:
    """True when a commercial-gate failure must not fail the job."""
    blocking = event == "push" and ref.startswith("refs/tags/")
    return not blocking


def test_failure_rules_differ_by_gate():
    cases = [
        ("push", "refs/heads/main", False, True),
        ("push", "refs/tags/v1.2.3", False, False),
        ("push", "refs/tags/release", False, False),
        ("push", "refs/heads/feature", True, True),
        ("push", "refs/heads/main-backup", True, True),
        ("pull_request", "refs/pull/17/merge", True, True),
        ("pull_request", "refs/heads/main", True, True),
        ("workflow_dispatch", "refs/heads/main", True, True),
        ("workflow_dispatch", "refs/tags/v1.2.3", True, True),
    ]
    for event, ref, lexicon_observe, commercial_observe in cases:
        assert lexicon_continue_on_error(event, ref) is lexicon_observe
        assert commercial_continue_on_error(event, ref) is commercial_observe


def test_lexicon_blocks_main_and_tags_commercial_blocks_tags_only():
    job = _truth_job()
    assert job.count(LEXICON_ENV) == 1
    assert job.count(COMMERCIAL_ENV) == 1
    assert "TRUTH_GATE_BLOCKING" not in job
    assert "continue-on-error: true" not in job
    assert "|| true" not in job
    lexicon = _step(job, "Docs lexicon gate")
    commercial = _step(job, "Commercial release gate")
    assert lexicon.count(LEXICON_OBSERVE) == 1
    assert COMMERCIAL_OBSERVE not in lexicon
    assert commercial.count(COMMERCIAL_OBSERVE) == 1
    assert "refs/heads/main" not in commercial
    assert "python3 tools/docs_lexicon_gate.py --root ." in lexicon
    assert "python3 tools/commercial_release_gate.py --root ." in commercial
    for step, blocking_name in (
        (lexicon, "LEXICON_GATE_BLOCKING"),
        (commercial, "COMMERCIAL_GATE_BLOCKING"),
    ):
        assert 'exit "$rc"' in step
        assert "|| true" not in step
        assert f'if [ "${blocking_name}" = "true" ]; then' in step


def test_non_release_gates_admission_pins_and_secrets_stay_put():
    text = WORKFLOW.read_text(encoding="utf-8")
    job = _truth_job()
    assert "on:\n  pull_request:\n  push:\n" in text
    assert "permissions:\n  contents: read\n" in text
    assert "secrets." not in job
    assert CHECKOUT_PIN in job
    assert SETUP_PYTHON_PIN in job
    demo = _step(job, "Acceptance demo (12 steps — hard gate)")
    assert "continue-on-error" not in demo
    assert "python3 tools/demo_harness.py --root ." in demo
    compile_step = _step(job, "Compile check (tools/*.py and src/)")
    assert "continue-on-error" not in compile_step
    assert "python3 -m py_compile tools/*.py" in compile_step
    contract = _step(job, "Verify lexicon and commercial gate failure rules")
    assert "continue-on-error" not in contract
    assert "python3 tests/test_truth_gates_release_blocking.py" in contract


if __name__ == "__main__":
    test_failure_rules_differ_by_gate()
    test_lexicon_blocks_main_and_tags_commercial_blocks_tags_only()
    test_non_release_gates_admission_pins_and_secrets_stay_put()
    print("truth-gates release-path contract: PASS")
