# SPDX-License-Identifier: Apache-2.0
"""The lexicon and commercial gates fail a release-path job.

A release path is a push to refs/heads/main or refs/tags/*. On every other
ref the same steps still run and still return the tool status, and
continue-on-error keeps the job from failing. An unconditional
continue-on-error: true is the soft-fail this contract forbids.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/truth-gates.yml"
JOB_MARKER = "  workspace-disposition-contract:\n"

RELEASE_PREDICATE = (
    "github.event_name == 'push' && "
    "(github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/'))"
)
BLOCKING_ENV = 'TRUTH_GATE_BLOCKING: "${{ ' + RELEASE_PREDICATE + ' }}"'
OBSERVE_UNLESS_RELEASE = 'continue-on-error: "${{ !(' + RELEASE_PREDICATE + ') }}"'

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


def is_release_path(event: str, ref: str) -> bool:
    """Same predicate as TRUTH_GATE_BLOCKING in the workflow."""
    return event == "push" and (
        ref == "refs/heads/main" or ref.startswith("refs/tags/")
    )


def continue_on_error(event: str, ref: str) -> bool:
    """True only when the step must not fail the job."""
    return not is_release_path(event, ref)


def test_release_path_predicate_matches_the_job_failure_rule():
    cases = [
        ("push", "refs/heads/main", False),
        ("push", "refs/tags/v1.2.3", False),
        ("push", "refs/tags/release", False),
        ("push", "refs/heads/feature", True),
        ("push", "refs/heads/main-backup", True),
        ("pull_request", "refs/pull/17/merge", True),
        ("pull_request", "refs/heads/main", True),
        ("workflow_dispatch", "refs/heads/main", True),
    ]
    for event, ref, observe in cases:
        assert continue_on_error(event, ref) is observe
        assert is_release_path(event, ref) is (not observe)


def test_lexicon_and_commercial_gates_block_only_on_release_paths():
    job = _truth_job()
    assert job.count(BLOCKING_ENV) == 1
    assert job.count(OBSERVE_UNLESS_RELEASE) == 2
    assert "continue-on-error: true" not in job
    assert "|| true" not in job
    for name, command in (
        ("Docs lexicon gate", "python3 tools/docs_lexicon_gate.py --root ."),
        ("Commercial release gate", "python3 tools/commercial_release_gate.py --root ."),
    ):
        step = _step(job, name)
        assert step.count(OBSERVE_UNLESS_RELEASE) == 1
        assert command in step
        assert 'exit "$rc"' in step
        assert "|| true" not in step
        assert 'if [ "$TRUTH_GATE_BLOCKING" = "true" ]; then' in step


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
    contract = _step(job, "Verify release-path gates fail the job")
    assert "continue-on-error" not in contract
    assert "python3 tests/test_truth_gates_release_blocking.py" in contract


if __name__ == "__main__":
    test_release_path_predicate_matches_the_job_failure_rule()
    test_lexicon_and_commercial_gates_block_only_on_release_paths()
    test_non_release_gates_admission_pins_and_secrets_stay_put()
    print("truth-gates release-path contract: PASS")
