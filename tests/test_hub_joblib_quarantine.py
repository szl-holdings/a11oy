from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPEN = _load("hub_joblib_open", "scripts/hub_quarantine_joblib_estate.py")
MERGE = _load("hub_joblib_merge", "scripts/hub_merge_joblib_quarantine_prs.py")

GOOD_DIFF = """\
diff --git a/model.joblib b/model.joblib
deleted file mode 100644
index abcdef0..0000000
Binary files a/model.joblib and /dev/null differ
"""


class _DetailsApi:
    def __init__(self, details):
        self.details = details

    def get_discussion_details(self, **_kwargs):
        return self.details


def _details(**overrides):
    values = {
        "num": 7,
        "is_pull_request": True,
        "status": "open",
        "title": MERGE.TITLE,
        "author": "owner",
        "target_branch": "main",
        "conflicting_files": None,
        "diff": GOOD_DIFF,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_exact_single_file_deletion_is_accepted():
    details = _details()
    assert (
        MERGE._validate_candidate(_DetailsApi(details), "SZLHOLDINGS/example", details, "owner")
        is details
    )


@pytest.mark.parametrize(
    "diff",
    [
        GOOD_DIFF + "diff --git a/README.md b/README.md\n",
        "diff --git a/README.md b/README.md\ndeleted file mode 100644\n",
        "diff --git a/model.joblib b/model.joblib\nnew file mode 100644\n",
        "diff --git a/model.joblib b/model.joblib\nrename from model.joblib\nrename to old.joblib\n",
        "",
    ],
)
def test_unexpected_or_non_deletion_diff_is_rejected(diff):
    details = _details(diff=diff)
    with pytest.raises(RuntimeError):
        MERGE._validate_candidate(
            _DetailsApi(details),
            "SZLHOLDINGS/example",
            details,
            "owner",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("author", "attacker"),
        ("target_branch", "dev"),
        ("status", "draft"),
        ("is_pull_request", False),
        ("conflicting_files", ["model.joblib"]),
        ("title", "quarantine: remove model.joblib and README"),
    ],
)
def test_identity_target_state_and_conflict_mismatches_are_rejected(field, value):
    details = _details(**{field: value})
    with pytest.raises(RuntimeError):
        MERGE._validate_candidate(
            _DetailsApi(details),
            "SZLHOLDINGS/example",
            details,
            "owner",
        )


def test_open_pr_discovery_requires_exact_title_and_open_state():
    discussions = [
        SimpleNamespace(is_pull_request=True, status="open", title=OPEN.TITLE, num=1),
        SimpleNamespace(is_pull_request=True, status="closed", title=OPEN.TITLE, num=2),
        SimpleNamespace(is_pull_request=True, status="open", title=OPEN.TITLE + " extra", num=3),
        SimpleNamespace(is_pull_request=False, status="open", title=OPEN.TITLE, num=4),
    ]

    class Api:
        def get_repo_discussions(self, **_kwargs):
            return discussions

    assert [item.num for item in OPEN._matching_open_prs(Api(), "SZLHOLDINGS/example")] == [1]


def test_error_text_is_bounded_single_line_and_redacts_token():
    token = "hf_secret_value"
    error = RuntimeError(f"first\nsecond {token} " + ("x" * 2000))
    rendered = MERGE._safe_error(error, token)
    assert token not in rendered
    assert "<redacted>" in rendered
    assert "\n" not in rendered
    assert len(rendered) <= 1000
